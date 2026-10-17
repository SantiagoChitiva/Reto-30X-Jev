"""Convierte el Excel de perfiles anónimos de 30X en los JSON que usa el prototipo.

Uso:
    python data/build_profiles.py "ruta/a/perfiles-30x-anonimo.xlsx"

Escribe, junto a este archivo:
- perfiles_30x.json: los perfiles con claves normalizadas (base de la simulación).
- labeled_set.json: 200 perfiles con etiquetas de referencia (el "examen" de JEV).

Lee el .xlsx con la librería estándar (un .xlsx es un zip con XML), sin dependencias.
"""
import json
import random
import re
import sys
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
LABELED_SIZE = 200
SEED = 30

_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_EMPTY = {"", "—", "-", "Sin dato", "Sin dato de rol", "No declaró ningún dolor"}

# Columna del Excel → clave del perfil
COLUMNS = {
    "ID": "source_id",
    "Relación con 30X": "relation",
    "Estado": "crm_status",
    "Etapa en el CRM": "crm_stage",
    "Programa": "program",
    "Rol": "role",
    "País": "country",
    "Dolor principal": "pain",
    "Objetivo principal": "objective",
    "Temas de interés": "interests",
    "Nivel de info": "info_level",
    "Información disponible": "info_available",
    # Calificaciones que ya hizo 30X: son la respuesta del examen, nunca se le pasan a JEV
    "Programa sugerido": "suggested_program",
    "Afinidad (0-10)": "affinity",
}
REF_FIELDS = ("suggested_program", "affinity")

# "Programa sugerido" del Excel → opción de la pregunta `content`
PROGRAM_TO_CONTENT = {
    "AI Sales": "ai_sales",
    "Inmersión Ejecutiva": "inmersion_ejecutiva",
    "Sales Machine": "sales_machine",
    "Hardcore AI": "hardcore_ai",
    "Achievers": "achievers",
    "Sin programa sugerido": "nutricion",
}

SALES_OBJECTIVES = {"Vender más", "Construir una máquina de ventas"}
SALES_PAINS = {"No tiene proceso comercial estructurado", "Vive de referidos y prospecta a mano",
               "Ventas estancadas o cayendo"}
SCALE_OBJECTIVES = {"Delegar y pasar a un rol estratégico", "Desarrollar liderazgo y equipo",
                    "Expandirse a otros países", "Levantar capital", "Entrar a una red de pares",
                    "Transformar el modelo de negocio"}
AI_OBJECTIVES = {"Automatizar con IA", "Formarse (sobre todo en IA)"}


def _text(node) -> str:
    return "".join(t.text or "" for t in node.iter(f"{{{_NS['m']}}}t"))


def read_xlsx(path: Path, sheet: int = 1) -> list[dict[str, str]]:
    """Filas de una hoja como diccionarios {encabezado: valor}."""
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            shared = [_text(si) for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", _NS)]
        data = ET.fromstring(z.read(f"xl/worksheets/sheet{sheet}.xml")).find("m:sheetData", _NS)

    def value(cell) -> str:
        kind, v = cell.get("t"), cell.find("m:v", _NS)
        if kind == "s" and v is not None:
            return shared[int(v.text)]
        if kind == "inlineStr":
            return _text(cell)
        return v.text if v is not None and v.text else ""

    def column(ref: str) -> int:
        n = 0
        for ch in re.match(r"[A-Z]+", ref).group():
            n = n * 26 + ord(ch) - 64
        return n - 1

    rows = []
    for row in data:
        cells = {column(c.get("r")): value(c) for c in row} if all(c.get("r") for c in row) \
            else dict(enumerate(value(c) for c in row))
        width = max(cells, default=-1) + 1
        rows.append([cells.get(i, "") for i in range(width)])
    rows = [r for r in rows if any(x.strip() for x in r)]
    header = [h.strip() for h in rows[0]]
    return [dict(zip(header, r + [""] * (len(header) - len(r)))) for r in rows[1:]]


def _clean(value: str):
    value = unicodedata.normalize("NFC", value.strip())
    return None if value in _EMPTY else value


def to_profile(row: dict[str, str]) -> dict:
    out: dict = {}
    for col, key in COLUMNS.items():
        raw = row.get(col, "")
        if key == "interests":
            out[key] = [t.strip() for t in raw.split(",") if _clean(t)]
        elif key == "affinity":
            out[key] = float(raw) if raw.strip() else None
        else:
            out[key] = _clean(raw)
    out["ref"] = {k: out.pop(k) for k in REF_FIELDS}
    return out


def reference_segment(p: dict) -> str:
    """Borrador de etiqueta de segmento por reglas. El equipo la revisa a mano (`revisado`)."""
    role, objective, pain = p.get("role"), p.get("objective"), p.get("pain")
    interests = set(p.get("interests") or [])
    sales_focus = objective in SALES_OBJECTIVES or pain in SALES_PAINS
    if p.get("info_available") == "Sin información" and not objective and not interests:
        return "otro"
    if role == "Perfil técnico (ingeniería, datos, producto)" or p.get("program") == "AI for devs":
        return "perfil_tecnico"
    if role == "Líder comercial o de ventas":
        return "lider_comercial"
    if role == "Fundador, socio o CEO":
        if sales_focus:
            return "fundador_ventas"
        if objective in SCALE_OBJECTIVES or pain:
            return "fundador_escala"
        return "ejecutivo_ia"
    if role in ("Director, VP o C-level (no dueño)", "Gerente o jefe de área"):
        return "lider_comercial" if sales_focus else "ejecutivo_ia"
    # Sin rol (casi siempre un lead): solo se sabe qué necesita y qué temas le interesan
    if p.get("info_available") != "Perfil con contexto (dolor u objetivo)":
        return "explorador"
    if sales_focus:
        return "fundador_ventas"
    if objective in SCALE_OBJECTIVES:
        return "fundador_escala"
    if objective == "Automatizar con IA" and "product" in interests:
        return "perfil_tecnico"
    if objective == "Automatizar con IA":
        return "ejecutivo_ia"
    return "explorador"


def labeled_item(p: dict) -> dict:
    ref = p["ref"]
    return {
        "person": {k: v for k, v in p.items() if k != "ref"},
        "segment_ref": reference_segment(p),
        "content_ref": PROGRAM_TO_CONTENT.get(ref["suggested_program"] or "", "nutricion"),
        "sales_ready_ref": (ref["affinity"] or 0) >= 7,
        "revisado": False,
    }


def stratified_sample(profiles: list[dict], size: int, rng: random.Random) -> list[dict]:
    """Muestra repartida por programa sugerido y banda de afinidad, en la proporción del Excel."""
    groups: defaultdict[tuple, list[dict]] = defaultdict(list)
    for p in profiles:
        aff = p["ref"]["affinity"] or 0
        band = 0 if aff <= 3 else 1 if aff <= 6 else 2
        groups[(p["ref"]["suggested_program"], band)].append(p)
    picked: list[dict] = []
    for members in groups.values():
        k = round(len(members) * size / len(profiles))
        picked += rng.sample(members, min(k, len(members)))
    rest = [p for p in profiles if p not in picked]
    rng.shuffle(rest)
    picked = (picked + rest)[:size]
    return sorted(picked, key=lambda p: p["source_id"] or "")


def main(xlsx: str) -> None:
    profiles = [to_profile(r) for r in read_xlsx(Path(xlsx)) if r.get("ID", "").strip()]
    labeled = [labeled_item(p) for p in stratified_sample(profiles, LABELED_SIZE, random.Random(SEED))]
    for name, payload in (("perfiles_30x.json", profiles), ("labeled_set.json", labeled)):
        (HERE / name).write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(profiles)} perfiles -> perfiles_30x.json, {len(labeled)} etiquetados -> labeled_set.json")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
