import pytest

from app.decision import policy
from app.models import Answer, Person

CON_CONTEXTO = Person(person_id="p_0001", role="Fundador, socio o CEO", objective="Vender más")
SIN_CONTEXTO = Person(person_id="p_0002", objective="Vender más")


def seg(value="fundador_ventas", p=0.9):
    return Answer(value=value, p=p)


def sales(value=True, p=0.9):
    return Answer(value=value, p=p)


@pytest.mark.parametrize("p, expected", [
    (0.99, "auto"),
    (0.85, "auto"),
    (0.8499, "safe"),
    (0.60, "safe"),
    (0.5999, "human"),
    (0.10, "human"),
])
def test_umbrales(p, expected):
    assert policy.route(seg(p=p)) == expected


def test_segmento_otro_siempre_va_a_humano():
    assert policy.route(seg("otro", 0.99)) == "human"


def test_avisar_a_ventas_exige_certeza_y_contexto():
    oferta = Answer(value="ai_sales", p=0.9)
    assert policy.choose_action(sales(True, 0.9), oferta, CON_CONTEXTO) == "notify_sales"
    assert policy.choose_action(sales(True, 0.84), oferta, CON_CONTEXTO) == "send:ai_sales"  # duda: no molesta a ventas
    assert policy.choose_action(sales(True, 0.99), oferta, SIN_CONTEXTO) == "send:ai_sales"  # regla del harness
    assert policy.choose_action(sales(False, 0.9), oferta, CON_CONTEXTO) == "send:ai_sales"
    assert policy.choose_action(sales(False, 0.9), Answer(value="otro", p=0.9), CON_CONTEXTO) is None


def test_antispam():
    assert policy.repeated_action("send:ai_sales", ["notify_sales", "send:ai_sales"])
    assert not policy.repeated_action("send:ai_sales", ["send:ai_sales", None, None, "notify_sales"])
    assert not policy.repeated_action(None, [None])
