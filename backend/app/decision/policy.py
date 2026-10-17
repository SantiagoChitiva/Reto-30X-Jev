"""Umbrales y regla de acción (CONTRACTS.md, v0)."""
from typing import Optional

from ..models import Answer, Route

AUTO_MIN = 0.85       # p ≥ 0.85 → auto (pasa por guardrail)
LLM_MIN = 0.60        # 0.60 ≤ p < 0.85 → llm
GUARDRAIL_MIN = 0.85  # el guardrail aprueba si JEV confirma con p ≥ 0.85


def route(segment: Answer, sales_ready: Answer) -> Route:
    """Ruta según la probabilidad mínima de `segment` y `sales_ready`."""
    if segment.value == "otro":
        return "human"
    p = min(segment.p, sales_ready.p)
    if p >= AUTO_MIN:
        return "auto"
    if p >= LLM_MIN:
        return "llm"
    return "human"


def choose_action(sales_ready: Answer, content: Answer) -> Optional[str]:
    """`notify_sales` si está lista para ventas; si no, `send:<content>`."""
    if sales_ready.value is True:
        return "notify_sales"
    if content.value != "otro":
        return f"send:{content.value}"
    return None
