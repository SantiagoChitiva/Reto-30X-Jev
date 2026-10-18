"""Mide a JEV contra el set etiquetado (`data/labeled_set.json`) y lo compara con un LLM.

Uso (desde backend/, o `docker compose exec backend python -m app.evaluate`):
    python -m app.evaluate

Usa JEV real o simulado según USE_MOCK_JEV y guarda el resultado en `data/eval_results.json`,
que es lo que devuelve GET /evaluation y lo que va al playbook.
"""
from dotenv import load_dotenv

load_dotenv()

import asyncio  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import time  # noqa: E402
from collections import Counter, defaultdict  # noqa: E402
from typing import Any  # noqa: E402

from .decision import jev, pipeline, policy  # noqa: E402
from .models import Event, Person  # noqa: E402
from .simulate import data_dir  # noqa: E402
from .store import _percentile, now  # noqa: E402

QUESTIONS = ("segment", "content", "sales_ready")
LLM_OUTPUT_TOKENS = 150  # una respuesta JSON corta por caso


def load_labeled() -> list[dict[str, Any]]:
    path = data_dir() / "labeled_set.json"
    if not path.exists():
        raise FileNotFoundError(f"No está {path}. Genéralo con: python data/build_profiles.py <excel>")
    return json.loads(path.read_text(encoding="utf-8"))


def state_for(item: dict[str, Any], i: int) -> dict[str, Any]:
    """El mismo estado que vería JEV si la persona se acabara de inscribir."""
    fields = {k: v for k, v in item["person"].items() if k in Person.model_fields}
    person = Person(**fields, person_id=f"eval_{i:04d}")
    event = Event(event_id=f"eval_e{i:04d}", person_id=person.person_id, type="signup", timestamp=now(),
                  data={"event_name": "Free Sales Training"})
    return pipeline.build_state(person, event, [])


async def _ask_all(states: list[dict[str, Any]]) -> list[tuple[jev.JevResult, float]]:
    sem = asyncio.Semaphore(int(os.getenv("MAX_CONCURRENCY", "50")))

    async def one(state: dict[str, Any]) -> tuple[jev.JevResult, float]:
        async with sem:
            t0 = time.perf_counter()
            result = await jev.ask(state)
            return result, (time.perf_counter() - t0) * 1000

    return await asyncio.gather(*(one(s) for s in states))


def _pct(hits: int, total: int) -> float:
    return round(100 * hits / total, 1) if total else 0.0


def _llm_estimate(states: list[dict[str, Any]]) -> dict[str, Any]:
    """Lo mismo con un LLM normal: tokens del caso × precio de OPENAI_USD_PER_M_*."""
    price_in = float(os.getenv("OPENAI_USD_PER_M_INPUT", "0.15"))
    price_out = float(os.getenv("OPENAI_USD_PER_M_OUTPUT", "0.60"))
    prompt = len(jev.LLM_SYSTEM_PROMPT) + len(json.dumps(jev.QUESTIONS, ensure_ascii=False))
    tokens_in = sum((prompt + len(json.dumps(s, ensure_ascii=False))) // 4 for s in states)
    cost = (tokens_in * price_in + len(states) * LLM_OUTPUT_TOKENS * price_out) / 1_000_000
    return {
        "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        "cost_usd": round(cost, 6),
        "cost_per_1k_usd": round(cost / len(states) * 1000, 6),
        "latency_ms_typical": float(os.getenv("LLM_TYPICAL_LATENCY_MS", "1500")),
        "estimated": True,
    }


def score(items: list[dict[str, Any]], answers: list[dict[str, Any]]) -> dict[str, Any]:
    """Precisión por pregunta, global y por ruta (la ruta `auto` debería acertar más)."""
    hits: defaultdict[str, Counter] = defaultdict(Counter)
    totals: Counter = Counter()
    for item, a in zip(items, answers):
        route = policy.route(a["segment"], a["sales_ready"])
        totals[route] += 1
        for q in QUESTIONS:
            ok = a[q].value == item[f"{q}_ref"]
            hits["all"][q] += ok
            hits[route][q] += ok
    n = len(items)
    return {
        "accuracy": {q: _pct(hits["all"][q], n) for q in QUESTIONS},
        "by_route": {
            r: {"n": totals[r], "pct": _pct(totals[r], n), **{q: _pct(hits[r][q], totals[r]) for q in QUESTIONS}}
            for r in ("auto", "llm", "human")
        },
    }


async def evaluate() -> dict[str, Any]:
    items = load_labeled()
    states = [state_for(item, i) for i, item in enumerate(items)]
    t0 = time.perf_counter()
    results = await _ask_all(states)
    wall_ms = (time.perf_counter() - t0) * 1000
    await jev.aclose()

    latencies = sorted(ms for _, ms in results)
    cost = sum(r.cost_usd for r, _ in results)
    out = {
        "created_at": now().isoformat(),
        "mock_jev": jev.use_mock(),
        "n": len(items),
        "labels": "content_ref = programa sugerido por 30X; sales_ready_ref = afinidad >= 7; "
                  "segment_ref = borrador por reglas pendiente de revisión manual",
        "reviewed_labels": sum(1 for i in items if i.get("revisado")),
        **score(items, [r.answers for r, _ in results]),
        "jev": {
            "cost_usd": round(cost, 6),
            "cost_per_1k_usd": round(cost / len(items) * 1000, 6),
            "latency_p50_ms": round(_percentile(latencies, 0.5), 1),
            "latency_p95_ms": round(_percentile(latencies, 0.95), 1),
            "wall_ms": round(wall_ms, 1),
        },
        "llm": _llm_estimate(states),
    }
    (data_dir() / "eval_results.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def main() -> None:
    out = asyncio.run(evaluate())
    kind = "simulado" if out["mock_jev"] else "real"
    print(f"JEV {kind} sobre {out['n']} perfiles etiquetados")
    for q, v in out["accuracy"].items():
        print(f"  precision {q:12} {v:5.1f} %")
    for r, v in out["by_route"].items():
        print(f"  ruta {r:6} {v['n']:4} casos ({v['pct']:.1f} %)  segment {v['segment']:.1f} %  "
              f"content {v['content']:.1f} %")
    j, llm = out["jev"], out["llm"]
    print(f"  JEV: US$ {j['cost_per_1k_usd']:.4f} por 1.000, p50 {j['latency_p50_ms']} ms")
    print(f"  LLM ({llm['model']}, estimado): US$ {llm['cost_per_1k_usd']:.4f} por 1.000, "
          f"~{llm['latency_ms_typical']:.0f} ms")
    print(f"Guardado en {data_dir() / 'eval_results.json'}")


if __name__ == "__main__":
    main()
