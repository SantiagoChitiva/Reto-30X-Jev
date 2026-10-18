"""Umbrales, regla de acción y antispam (CONTRACTS.md)."""
from typing import Optional

from ..models import Answer, Route

AUTO_MIN = 0.85       # p ≥ 0.85 → auto (pasa por guardrail)
SAFE_MIN = 0.60       # 0.60 ≤ p < 0.85 → safe: acción prudente, por confirmar
GUARDRAIL_MIN = 0.85  # el guardrail aprueba si JEV confirma con p ≥ 0.85
SAFE_ACTION = "send:nutricion"  # con confianza media solo se envía contenido gratuito; nunca se avisa a ventas


def route(segment: Answer, sales_ready: Answer) -> Route:
    """Ruta según la probabilidad mínima de `segment` y `sales_ready`."""
    if segment.value == "otro":
        return "human"
    p = min(segment.p, sales_ready.p)
    if p >= AUTO_MIN:
        return "auto"
    if p >= SAFE_MIN:
        return "safe"
    return "human"


def choose_action(sales_ready: Answer, content: Answer) -> Optional[str]:
    """`notify_sales` si está lista para ventas; si no, `send:<content>`."""
    if sales_ready.value is True:
        return "notify_sales"
    if content.value != "otro":
        return f"send:{content.value}"
    return None


SPAM_WINDOW = 3  # decisiones anteriores de la persona que revisa el antispam
SPAM_REASON = "Frenada por frecuencia"  # prefijo con el que se cuentan en /metrics


def repeated_action(action: Optional[str], recent_actions: list[Optional[str]]) -> bool:
    """Antispam en código: la misma acción ya salió en las últimas `SPAM_WINDOW` decisiones."""
    return action is not None and action in recent_actions[-SPAM_WINDOW:]
