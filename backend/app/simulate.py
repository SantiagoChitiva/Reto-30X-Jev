"""Genera personas y eventos falsos para probar y para la demo.

Todos los datos son simulados: nada de personas reales.
"""
import asyncio
import logging
import os
import random

from .decision import pipeline
from .models import EventIn, Person
from .store import get_store

log = logging.getLogger(__name__)

running = False  # lo lee GET /metrics

FIRST_NAMES = ["María", "Juan", "Camila", "Andrés", "Valentina", "Santiago", "Laura", "Carlos", "Daniela",
               "Felipe", "Natalia", "Diego", "Paula", "Sebastián", "Juliana", "Mateo", "Catalina", "Alejandro"]
LAST_NAMES = ["Gómez", "Rodríguez", "Martínez", "López", "García", "Pérez", "Sánchez", "Ramírez", "Torres",
              "Díaz", "Vargas", "Rojas", "Moreno", "Castro", "Herrera", "Ortiz"]
COMPANIES = [  # (empresa, industria)
    ("Banco Andino", "banca"), ("Seguros del Pacífico", "seguros"), ("Fintech Nova", "fintech"),
    ("TelcoNet", "telecomunicaciones"), ("Startup Labs", "tecnologia"), ("Retail Sur", "retail"),
    ("Clínica Central", "salud"), ("Logística Express", "logistica"), ("EduTech Latam", "educacion"),
    ("Energía Verde", "energia"), ("AgroCampo", "agro"), ("Manufacturas Unidas", "manufactura"),
]
SIZES = ["1-10", "11-50", "51-200", "201-1000", "1000+"]
SIZE_WEIGHTS = [10, 20, 25, 25, 20]

# Cargos de prueba agrupados por el segmento al que deberían caer
ROLES = {
    "explorador": ["Coordinador de proyectos", "Asistente administrativo", "Especialista de mercadeo",
                   "Ejecutivo de cuenta", "Profesional de calidad"],
    "equipo_adopcion": ["Analista de datos", "Ingeniero de software", "Científico de datos",
                        "Ingeniero de machine learning", "Desarrollador backend"],
    "lider_negocio": ["Gerente comercial", "Directora de marketing", "Gerente de operaciones", "CFO",
                      "Gerente general"],
    "lider_tecnico": ["CTO", "Director de tecnología", "Arquitecto de soluciones", "Gerente de TI",
                      "Líder técnico"],
    "lider_adopcion": ["Head of AI", "Chief Data Officer", "Director de Transformación Digital", "Líder de IA",
                       "Gerente de Innovación"],
    "otro": ["Estudiante", "Proveedor", "Consultor independiente"],
}
ROLE_WEIGHTS = {"explorador": 25, "equipo_adopcion": 25, "lider_negocio": 18, "lider_tecnico": 12,
                "lider_adopcion": 10, "otro": 10}

# Ascensos que produce un `profile_update`: así aparecen cambios de segmento (Sankey)
PROMOTIONS = {
    "Analista de datos": "Líder técnico",
    "Líder técnico": "Head of AI",
    "Ingeniero de software": "Arquitecto de soluciones",
    "Arquitecto de soluciones": "CTO",
    "Científico de datos": "Líder de IA",
    "Ingeniero de machine learning": "Líder de IA",
    "Desarrollador backend": "Líder técnico",
    "Coordinador de proyectos": "Gerente de operaciones",
    "Gerente de operaciones": "Director de Transformación Digital",
    "Especialista de mercadeo": "Directora de marketing",
    "Ejecutivo de cuenta": "Gerente comercial",
    "Gerente comercial": "Gerente general",
    "Gerente de TI": "Chief Data Officer",
    "Estudiante": "Analista de datos",
    "Consultor independiente": "Gerente de Innovación",
}

EVENT_NAMES = ["30X AI Summit", "Webinar: IA generativa en la empresa", "Taller de prompts",
               "Meetup de datos", "Sesión informativa del programa ejecutivo"]
EMAIL_TOPICS = ["casos de éxito en banca", "guía de adopción de IA", "nuevo taller práctico",
                "programa ejecutivo", "novedades de IA generativa"]


def _person_chain(person_id: str, size: int, rng: random.Random) -> list[EventIn]:
    """Los eventos de una persona, en orden: signup y luego asistencias, correos y cambios de perfil."""
    archetype = rng.choices(list(ROLE_WEIGHTS), weights=list(ROLE_WEIGHTS.values()))[0]
    company, industry = rng.choice(COMPANIES)
    person = Person(
        person_id=person_id,
        name=f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
        role=rng.choice(ROLES[archetype]),
        company=company,
        industry=industry,
        company_size=rng.choices(SIZES, weights=SIZE_WEIGHTS)[0],
        events_attended=rng.choice([0, 0, 1]),
    )
    chain = [EventIn(person_id=person_id, type="signup", data={"event_name": rng.choice(EVENT_NAMES)},
                     person=person)]
    role = person.role
    for _ in range(size - 1):
        kind = rng.choices(["attendance", "email_open", "profile_update"], weights=[45, 40, 15])[0]
        if kind == "attendance":
            data = {"event_name": rng.choice(EVENT_NAMES)}
        elif kind == "email_open":
            data = {"email_topic": rng.choice(EMAIL_TOPICS)}
        elif role in PROMOTIONS:
            role = PROMOTIONS[role]
            data = {"role": role}
        else:
            company, industry = rng.choice(COMPANIES)
            data = {"company": company, "industry": industry}
        chain.append(EventIn(person_id=person_id, type=kind, data=data))
    return chain


def build_chains(n: int, rng: random.Random) -> list[list[EventIn]]:
    """Reparte n eventos entre personas nuevas (de 1 a 9 eventos cada una)."""
    store = get_store()
    chains, total = [], 0
    while total < n:
        size = min(n - total, rng.randint(1, 9))
        chains.append(_person_chain(store.next_id("p"), size, rng))
        total += size
    return chains


async def run(n: int) -> None:
    """Procesa n eventos simulados. Hay varias personas en paralelo y los eventos de cada una van en orden."""
    global running
    running = True
    try:
        chains = build_chains(n, random.Random())
        sem = asyncio.Semaphore(int(os.getenv("MAX_CONCURRENCY", "50")))

        async def play(chain: list[EventIn]) -> None:
            for ev in chain:
                async with sem:
                    try:
                        await pipeline.process_event(ev)
                    except Exception:
                        log.exception("Falló el evento %s de %s", ev.type, ev.person_id)
                        return

        await asyncio.gather(*(play(c) for c in chains))
    finally:
        running = False
