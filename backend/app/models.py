"""Formatos de datos de 30X Pulse. La fuente de verdad es CONTRACTS.md."""
from datetime import datetime
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Opciones de las preguntas tipadas a JEV (CONTRACTS.md, v0)
SEGMENTS = ["explorador", "lider_negocio", "lider_tecnico", "equipo_adopcion", "lider_adopcion", "otro"]
MATURITY = ["baja", "media", "alta"]
CONTENT = ["intro_ia", "caso_de_exito", "taller_practico", "programa_ejecutivo", "otro"]

CompanySize = Literal["1-10", "11-50", "51-200", "201-1000", "1000+"]
EventType = Literal["signup", "attendance", "email_open", "profile_update"]
Route = Literal["auto", "llm", "human"]

# Campos de Person que puede cambiar un `profile_update`
UPDATABLE_FIELDS = ("name", "role", "company", "industry", "company_size")


def valid_action(action: Optional[str]) -> bool:
    """`action`: `send:<content>` | `notify_sales` | `null`."""
    if action is None or action == "notify_sales":
        return True
    return action.startswith("send:") and action[len("send:"):] in CONTENT


# --- Person / Event ---

class Person(BaseModel):
    person_id: str
    name: str
    role: str
    company: str
    industry: str
    company_size: CompanySize
    events_attended: int = Field(0, ge=0)


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


# --- Otros endpoints ---

class SimulateIn(BaseModel):
    n: int = Field(1000, ge=1, le=100_000)


class Metrics(BaseModel):
    total_decisions: int
    auto_pct: float
    llm_pct: float
    human_pct: float
    guardrail_blocked: int
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
