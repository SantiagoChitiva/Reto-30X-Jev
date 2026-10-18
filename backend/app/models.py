"""Formatos de datos de 30X Pulse. La fuente de verdad es CONTRACTS.md."""
from datetime import datetime
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Opciones de las preguntas tipadas a JEV (CONTRACTS.md)
SEGMENTS = ["fundador_ventas", "fundador_escala", "lider_comercial", "ejecutivo_ia", "perfil_tecnico",
            "explorador", "otro"]
MATURITY = ["baja", "media", "alta"]
# Ofertas reales de 30X (programas del Excel de perfiles) + contenido gratuito de nutrición
CONTENT = ["ai_sales", "inmersion_ejecutiva", "sales_machine", "hardcore_ai", "achievers", "nutricion", "otro"]

InfoLevel = Literal["Baja", "Media", "Alta"]
EventType = Literal["signup", "attendance", "email_open", "profile_update"]
Route = Literal["auto", "safe", "human"]
DecidedBy = Literal["jev", "jev_por_confirmar", "humano"]

# Campos de Person que puede cambiar un `profile_update`
UPDATABLE_FIELDS = ("relation", "crm_status", "crm_stage", "program", "role", "country", "pain", "objective",
                    "interests", "info_level", "info_available")


def valid_action(action: Optional[str]) -> bool:
    """`action`: `send:<content>` | `notify_sales` | `null`."""
    if action is None or action == "notify_sales":
        return True
    return action.startswith("send:") and action[len("send:"):] in CONTENT


# --- Person / Event ---

class Person(BaseModel):
    """Perfil anónimo con las mismas categorías del Excel de 30X. Sin nombres ni empresas.

    `None` = sin dato. `events_attended` y `emails_opened` se cuentan en código.
    """
    person_id: str
    relation: Optional[str] = None        # Lead (sin deal) | Deal en el CRM
    crm_status: Optional[str] = None
    crm_stage: Optional[str] = None
    program: Optional[str] = None         # programa en el que está o con el que llegó
    role: Optional[str] = None
    country: Optional[str] = None
    pain: Optional[str] = None
    objective: Optional[str] = None
    interests: list[str] = Field(default_factory=list)
    info_level: InfoLevel = "Baja"
    info_available: Optional[str] = None
    events_attended: int = Field(0, ge=0)
    emails_opened: int = Field(0, ge=0)


class EventIn(BaseModel):
    """Body de POST /events. `person` es obligatorio en `signup`."""
    person_id: str
    type: EventType
    data: dict[str, Any] = Field(default_factory=dict)
    person: Optional[Person] = None

    @model_validator(mode="after")
    def _signup_trae_person(self):
        if self.type == "signup":
            if self.person is None:
                raise ValueError("`person` es obligatorio cuando type = signup")
            if self.person.person_id != self.person_id:
                raise ValueError("`person.person_id` debe coincidir con `person_id`")
        return self


class Event(BaseModel):
    event_id: str
    person_id: str
    type: EventType
    timestamp: datetime
    data: dict[str, Any] = Field(default_factory=dict)


# --- Decision ---

class Answer(BaseModel):
    """Respuesta de JEV a una pregunta tipada: valor + probabilidad calibrada."""
    value: Union[bool, str]
    p: float = Field(ge=0, le=1)


class Guardrail(BaseModel):
    passed: bool
    p: float = Field(ge=0, le=1)
    reason: Optional[str] = None


class Decision(BaseModel):
    decision_id: str
    person_id: str
    event_id: str
    segment: Answer
    maturity: Answer
    sales_ready: Answer
    content: Answer
    route: Route
    guardrail: Optional[Guardrail] = None
    action: Optional[str] = None
    explanation: Optional[str] = None
    latency_ms: float
    cost_usd: float
    created_at: datetime


# --- Review (cola humana) ---

class Review(BaseModel):
    review_id: str
    decision_id: str
    status: Literal["pending", "resolved"] = "pending"
    resolved_segment: Optional[str] = None
    resolved_action: Optional[str] = None
    created_at: datetime


class ReviewIn(BaseModel):
    """Body de POST /review/{review_id}."""
    segment: str
    action: Optional[str] = None

    @field_validator("segment")
    @classmethod
    def _segmento_valido(cls, v: str) -> str:
        if v not in SEGMENTS:
            raise ValueError(f"segment debe ser uno de {SEGMENTS}")
        return v

    @field_validator("action")
    @classmethod
    def _accion_valida(cls, v: Optional[str]) -> Optional[str]:
        if not valid_action(v):
            raise ValueError("action debe ser `send:<content>`, `notify_sales` o null")
        return v


# --- Ficha en el CRM (lo que el sistema escribe de vuelta) ---

class CrmRecord(BaseModel):
    """Lo último que se decidió sobre una persona, como campos de su ficha en el CRM de 30X.

    Por ahora vive en la tabla `crm_profiles`; con el CRM real son las mismas propiedades.
    """
    person_id: str
    segment: str
    maturity: str
    sales_ready: bool
    suggested_program: str          # la oferta (`content`), igual que "Programa sugerido" del Excel
    confidence: float               # la `p` más baja entre segmento y lista para ventas; 1.0 si decidió una persona
    decided_by: DecidedBy
    last_action: Optional[str] = None
    decision_id: str
    updated_at: datetime


# --- Otros endpoints ---

class SimulateIn(BaseModel):
    n: int = Field(1000, ge=1, le=100_000)


class Metrics(BaseModel):
    total_decisions: int
    auto_pct: float
    safe_pct: float
    human_pct: float
    guardrail_blocked: int
    spam_suppressed: int
    total_cost_usd: float
    cost_per_1k_usd: float
    latency_p50_ms: float
    latency_p95_ms: float
    running: bool


class HistoryItem(BaseModel):
    at: datetime
    segment: str
    maturity: str
    sales_ready: bool


class PersonHistory(BaseModel):
    person: Person
    history: list[HistoryItem]


class Transition(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(alias="from")
    to: str
    count: int
