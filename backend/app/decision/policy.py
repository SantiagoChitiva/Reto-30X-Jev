"""Umbrales, reglas de acción y antispam: lo que resuelve el harness, no el modelo (CONTRACTS.md).

La exigencia depende del riesgo de la acción:
- Enviar contenido es de bajo riesgo: basta con saber quién es la persona (`segment`) y el antispam.
- Avisar a ventas es de alto riesgo: además exige que JEV esté segura de que está lista, que el perfil
  tenga contexto y que el guardrail de JEV no la frene.
"""
from typing import Optional

from ..models import Answer, Person, Route

AUTO_MIN = 0.85       # p del segmento ≥ 0.85 → auto
SAFE_MIN = 0.60       # 0.60 ≤ p < 0.85 → safe: acción prudente, por confirmar
SALES_MIN = 0.85      # avisar a ventas exige p ≥ 0.85 de que está lista
GUARDRAIL_MIN = 0.50  # el guardrail frena el aviso si JEV se inclina por «no apropiado»
SAFE_ACTION = "send:nutricion"  # con confianza media solo se envía contenido gratuito; nunca se avisa a ventas


def route(segment: Answer) -> Route:
    """Ruta según qué tan segura está JEV de quién es la persona."""
    if segment.value == "otro":
        return "human"
    if segment.p >= AUTO_MIN:
        return "auto"
    if segment.p >= SAFE_MIN:
        return "safe"
    return "human"


def has_context(person: Person) -> bool:
    """Regla del harness: no se avisa a ventas de alguien de quien no se sabe ni el rol ni el dolor."""
    return bool(person.role or person.pain)


def ready_for_sales(sales_ready: Answer, person: Person) -> bool:
    return sales_ready.value is True and sales_ready.p >= SALES_MIN and has_context(person)


def choose_action(sales_ready: Answer, content: Answer, person: Person) -> Optional[str]:
    """`notify_sales` si está lista para ventas con certeza; si no, `send:<content>`."""
    if ready_for_sales(sales_ready, person):
        return "notify_sales"
    if content.value != "otro":
        return f"send:{content.value}"
    return None


SPAM_WINDOW = 3  # decisiones anteriores de la persona que revisa el antispam
SPAM_REASON = "Frenada por frecuencia"  # prefijo con el que se cuentan en /metrics


def repeated_action(action: Optional[str], recent_actions: list[Optional[str]]) -> bool:
    """Antispam en código: la misma acción ya salió en las últimas `SPAM_WINDOW` decisiones."""
    return action is not None and action in recent_actions[-SPAM_WINDOW:]
