import asyncio
import importlib.util
import json
import zipfile

from app import evaluate, simulate
from app.models import CONTENT, SEGMENTS, Person


def load_builder():
    path = simulate.data_dir() / "build_profiles.py"
    spec = importlib.util.spec_from_file_location("build_profiles", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HEADER = ["ID", "Relación con 30X", "Estado", "Etapa en el CRM", "Programa", "Rol", "País", "Dolor principal",
          "Objetivo principal", "Programa sugerido", "Afinidad (0-10)", "Banda de afinidad", "Temas de interés",
          "Nivel de info", "Información disponible"]
ROW = ["P-1", "Lead (sin deal)", "Lead sin oportunidad abierta", "—", "—", "Sin dato de rol", "Sin dato",
       "No declaró ningún dolor", "Vender más", "Sales Machine", "8", "7-8 (alta)", "sales, gtm", "Media",
       "Perfil con contexto (dolor u objetivo)"]


def tiny_xlsx(path):
    """Un .xlsx mínimo con cadenas en línea, como lo escribiría cualquier hoja de cálculo."""
    def row(values, r):
        cells = "".join(f'<c r="{chr(65 + i)}{r}" t="inlineStr"><is><t>{v}</t></is></c>' for i, v in enumerate(values))
        return f'<row r="{r}">{cells}</row>'

    sheet = ('<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
             + row(HEADER, 1) + row(ROW, 2) + "</sheetData></worksheet>")
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("xl/worksheets/sheet1.xml", sheet)


def test_build_profiles_lee_el_excel(tmp_path):
    builder = load_builder()
    xlsx = tmp_path / "perfiles.xlsx"
    tiny_xlsx(xlsx)
    [profile] = [builder.to_profile(r) for r in builder.read_xlsx(xlsx)]
    assert profile["role"] is None and profile["pain"] is None and profile["crm_stage"] is None
    assert profile["interests"] == ["sales", "gtm"] and profile["objective"] == "Vender más"
    assert profile["ref"] == {"suggested_program": "Sales Machine", "affinity": 8.0}
    item = builder.labeled_item(profile)
    assert item["content_ref"] == "sales_machine" and item["sales_ready_ref"] is True
    assert item["segment_ref"] == "fundador_ventas"
    assert "ref" not in item["person"]  # la respuesta del examen nunca llega a JEV


def test_los_json_del_repo_son_validos():
    profiles = simulate.base_profiles()
    assert len(profiles) > 600
    for p in profiles[:50]:
        Person(**{k: v for k, v in p.items() if k in Person.model_fields}, person_id="p_x")
    labeled = evaluate.load_labeled()
    assert len(labeled) == 200
    assert {i["segment_ref"] for i in labeled} <= set(SEGMENTS)
    assert {i["content_ref"] for i in labeled} <= set(CONTENT)


def test_evaluate_con_el_mock(tmp_path, monkeypatch):
    labeled = evaluate.load_labeled()[:20]
    (tmp_path / "labeled_set.json").write_text(json.dumps(labeled), encoding="utf-8")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    out = asyncio.run(evaluate.evaluate())
    assert out["n"] == 20 and out["mock_jev"] is True
    assert set(out["accuracy"]) == {"segment", "content", "sales_ready"}
    assert sum(r["n"] for r in out["by_route"].values()) == 20
    assert out["jev"]["cost_usd"] > 0 and out["llm"]["cost_usd"] > out["jev"]["cost_usd"]
    assert json.loads((tmp_path / "eval_results.json").read_text(encoding="utf-8"))["n"] == 20


def test_la_simulacion_parte_de_perfiles_reales():
    import random

    from app.simulate import _person_chain

    chain = _person_chain("p_0001", 9, random.Random(1))
    assert chain[0].type == "signup" and chain[0].person.person_id == "p_0001"
    for ev in chain[1:]:
        if ev.type == "profile_update":
            assert ev.data and set(ev.data) <= set(Person.model_fields)
