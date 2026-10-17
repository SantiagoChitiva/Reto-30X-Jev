"""Genera personas y eventos para probar y para la demo.

Cada persona parte de un perfil del Excel anónimo de 30X (`data/perfiles_30x.json`)
y recorre el embudo: se inscribe a un evento, asiste, abre correos y su perfil
cambia (de lead a deal, aparece su rol, declara un dolor, avanza en el CRM).
Nada de datos personales: solo categorías.
"""
import asyncio
import json
import logging
import os
import random
from functools import lru_cache
from pathlib import Path
from typing import Any

from .decision import pipeline
from .models import EventIn, Person
from .store import get_store

log = logging.getLogger(__name__)

running = False  # lo lee GET /metrics


def data_dir() -> Path:
    """`DATA_DIR` o, por defecto, la carpeta `data/` de la raíz del repo (`/data` en Docker)."""
    return Path(os.getenv("DATA_DIR") or Path(__file__).resolve().parents[2] / "data")


@lru_cache
def base_profiles() -> list[dict[str, Any]]:
    path = data_dir() / "perfiles_30x.json"
    if not path.exists():
        raise FileNotFoundError(f"No está {path}. Genéralo con: python data/build_profiles.py <excel>")
    return json.loads(path.read_text(encoding="utf-8"))


# Eventos de 30X en Luma (genéricos, con los nombres de los programas del Excel)
EVENT_NAMES = ["Free Sales Training", "Masterclass AI Sales", "Webinar: IA para dueños de empresa",
               "Sesión informativa de Inmersión Ejecutiva", "Taller Sales Machine", "Demo day Hardcore AI"]
# Tema del correo según el interés de la persona
EMAIL_TOPICS = {
    "ai": "IA aplicada a tu negocio", "sales": "Cómo vender más con un proceso comercial",
    "ops": "Automatiza tus operaciones", "gtm": "Estrategia de salida al mercado",
    "leadership": "Delegar para crecer", "marketing": "Marketing que trae clientes",
    "fundraising": "Cómo levantar capital", "finance": "Finanzas para dueños", "product": "Construir con IA",
}

# Etapas del CRM en orden; el último paso termina en ganado o perdido
STAGES = ["Registrado", "Contactado", "Potencial", "Calificado", "En gestión"]
ROLES = ["Fundador, socio o CEO", "Líder comercial o de ventas", "Gerente o jefe de área",
         "Director, VP o C-level (no dueño)", "Perfil técnico (ingeniería, datos, producto)"]
ROLE_WEIGHTS = [107, 30, 23, 15, 13]  # proporción de roles entre los deals del Excel
PAINS = ["Procesos manuales y rezago tecnológico", "Falta de claridad estratégica para escalar",
         "No tiene proceso comercial estructurado", "Vive de referidos y prospecta a mano",
         "El dueño es el cuello de botella y no delega", "Ventas estancadas o cayendo"]
PAIN_WEIGHTS = [26, 19, 17, 11, 9, 7]
INFO_UP = {"Baja": "Media", "Media": "Alta", "Alta": "Alta"}


def _new_person(person_id: str, rng: random.Random) -> Person:
    base = rng.choice(base_profiles())
    fields = {k: v for k, v in base.items() if k in Person.model_fields}
    return Person(**fields, person_id=person_id)


def _profile_change(p: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    """Siguiente cambio de perfil: la persona avanza en el embudo o completa su información."""
    if p["relation"] != "Deal en el CRM":
        change = {"relation": "Deal en el CRM", "crm_status": "En proceso", "crm_stage": STAGES[0],
                  "info_level": INFO_UP[p["info_level"]]}
        if not p["role"]:  # el rol solo se conoce cuando hay deal
            change["role"] = rng.choices(ROLES, weights=ROLE_WEIGHTS)[0]
        return change
    if not p["pain"] and rng.random() < 0.5:
        return {"pain": rng.choices(PAINS, weights=PAIN_WEIGHTS)[0],
                "info_available": "Perfil con contexto (dolor u objetivo)", "info_level": INFO_UP[p["info_level"]]}
    if p["crm_stage"] in STAGES:
        i = STAGES.index(p["crm_stage"])
        if i + 1 < len(STAGES):
            return {"crm_stage": STAGES[i + 1]}
        if rng.random() < 0.3:
            return {"crm_stage": "Ganado Pagado Completo", "crm_status": "Cliente (pagó)"}
        return {"crm_stage": "Cierre perdido", "crm_status": "Oportunidad perdida"}
    return {"info_level": INFO_UP[p["info_level"]]}


def _person_chain(person_id: str, size: int, rng: random.Random) -> list[EventIn]:
    """Los eventos de una persona, en orden: signup y luego asistencias, correos y cambios de perfil."""
    person = _new_person(person_id, rng)
    chain = [EventIn(person_id=person_id, type="signup", data={"event_name": rng.choice(EVENT_NAMES)},
                     person=person)]
    profile = person.model_dump()
    for _ in range(size - 1):
        kind = rng.choices(["attendance", "email_open", "profile_update"], weights=[35, 40, 25])[0]
        if kind == "attendance":
            data = {"event_name": rng.choice(EVENT_NAMES)}
        elif kind == "email_open":
            topic = rng.choice(profile["interests"] or ["ai"])
            data = {"email_topic": EMAIL_TOPICS.get(topic, EMAIL_TOPICS["ai"])}
        else:
            data = _profile_change(profile, rng)
            profile.update(data)
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
