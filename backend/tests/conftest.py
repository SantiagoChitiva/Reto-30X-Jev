import os

import pytest

# Siempre con JEV simulado y almacenamiento en memoria
os.environ["USE_MOCK_JEV"] = "true"
os.environ["USE_MOCK_LLM"] = "true"
os.environ.pop("DATABASE_URL", None)

from fastapi.testclient import TestClient  # noqa: E402

from app.decision import jev  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def sin_latencia(monkeypatch):
    monkeypatch.setattr(jev, "_mock_latency_s", lambda: 0)


@pytest.fixture(autouse=True)
def mock_sin_errores(monkeypatch):
    """El JEV simulado se equivoca a propósito cuando duda; en los tests responde siempre su heurística."""
    monkeypatch.setattr(jev, "_maybe_wrong", lambda options, chosen, p, rng: chosen)


@pytest.fixture
def client():
    with TestClient(app) as c:  # cada test arranca con un store en memoria nuevo
        yield c
