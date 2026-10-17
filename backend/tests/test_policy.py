import pytest

from app.decision import policy
from app.models import Answer


def seg(value="lider_adopcion", p=0.9):
    return Answer(value=value, p=p)


def sales(value=True, p=0.9):
    return Answer(value=value, p=p)


@pytest.mark.parametrize("p, expected", [
    (0.99, "auto"),
    (0.85, "auto"),
    (0.8499, "llm"),
    (0.60, "llm"),
    (0.5999, "human"),
    (0.10, "human"),
])
def test_umbrales(p, expected):
    assert policy.route(seg(p=p), sales(p=0.99)) == expected


def test_usa_la_probabilidad_minima():
    assert policy.route(seg(p=0.99), sales(p=0.70)) == "llm"
    assert policy.route(seg(p=0.99), sales(p=0.50)) == "human"


def test_segmento_otro_siempre_va_a_humano():
    assert policy.route(seg("otro", 0.99), sales(p=0.99)) == "human"


def test_accion():
    assert policy.choose_action(sales(True), Answer(value="caso_de_exito", p=0.9)) == "notify_sales"
    assert policy.choose_action(sales(False), Answer(value="caso_de_exito", p=0.9)) == "send:caso_de_exito"
    assert policy.choose_action(sales(False), Answer(value="otro", p=0.9)) is None
