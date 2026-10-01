"""Exercise 3.4 (bonus) - run real RAGAS metrics on the SAME 20 benchmark cases.

Compares the lab's token-overlap evaluator (template.py, already stored in
artifacts/benchmark_results.json) with the RAGAS library (LLM-as-judge metrics).

This script is read-only with respect to the core pipeline: it never modifies
golden_dataset.json, artifacts/actual_answers.json or artifacts/benchmark_results.json.
It writes only artifacts/bonus_ex34_ragas.json.

RAGAS is intentionally NOT in requirements.txt (bonus-only dependency). Install it
separately, e.g.:  pip install "ragas==0.4.3" "langchain-community==0.3.31" "langchain-core<1.0"

Judge LLM: any OpenAI-compatible endpoint, selected like domain_assistant.py via
LLM_PROVIDER / GROQ_* / OPENAI_* in .env. Per-case failures are stored as null with
the error text; nothing is imputed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
METRICS = ("faithfulness", "context_recall", "context_precision")


def _build_llm() -> tuple[Any, str, str]:
    from openai import AsyncOpenAI
    from ragas.llms import llm_factory

    provider = os.getenv("LLM_PROVIDER", "openai").strip().lower()
    if provider == "groq":
        client = AsyncOpenAI(
            api_key=os.environ["GROQ_API_KEY"],
            base_url="https://api.groq.com/openai/v1",
        )
        model = os.getenv("GROQ_MODEL", "").strip() or os.environ["OPENAI_MODEL"]
    else:
        client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
        model = os.environ["OPENAI_MODEL"]
    return llm_factory(model, provider="openai", client=client), provider, model


def _ctx_texts(retrieved: list[Any]) -> list[str]:
    return [c if isinstance(c, str) else str(c.get("text", "")) for c in retrieved]


async def _with_backoff(make_call: Any, attempts: int = 6) -> Any:
    """Retry only provider rate limits (HTTP 429); other errors surface immediately."""
    for attempt in range(attempts):
        try:
            return await make_call()
        except Exception as exc:  # noqa: BLE001
            if "429" not in str(exc) or attempt == attempts - 1:
                raise
            await asyncio.sleep(15 * (attempt + 1))


async def _score_case(
    sem: asyncio.Semaphore,
    metrics: dict[str, Any],
    answer: dict[str, Any],
    gold: dict[str, Any],
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contexts = _ctx_texts(answer["retrieved_contexts"])
    question, response, reference = answer["question"], answer["actual_answer"], gold["expected_answer"]
    calls = {
        "faithfulness": lambda: metrics["faithfulness"].ascore(
            user_input=question, response=response, retrieved_contexts=contexts
        ),
        "context_recall": lambda: metrics["context_recall"].ascore(
            user_input=question, retrieved_contexts=contexts, reference=reference
        ),
        "context_precision": lambda: metrics["context_precision"].ascore(
            user_input=question, reference=reference, retrieved_contexts=contexts
        ),
    }
    row: dict[str, Any] = {"id": answer["id"], "errors": {}}
    async with sem:
        for name, make_call in calls.items():
            if previous is not None and previous.get(name) is not None:
                row[name] = previous[name]  # keep an already-measured score (--resume)
                continue
            try:
                row[name] = float((await _with_backoff(make_call)).value)
            except Exception as exc:  # noqa: BLE001 - record, never impute
                row[name] = None
                row["errors"][name] = f"{type(exc).__name__}: {str(exc)[:200]}"
    return row


async def _run(limit: int | None, concurrency: int, resume_from: Path | None) -> dict[str, Any]:
    import ragas
    from ragas.metrics.collections import ContextPrecision, ContextRecall, Faithfulness

    llm, provider, model = _build_llm()
    metrics = {
        "faithfulness": Faithfulness(llm=llm),
        "context_recall": ContextRecall(llm=llm),
        "context_precision": ContextPrecision(llm=llm),
    }
    answers = json.loads((ROOT / "artifacts/actual_answers.json").read_text(encoding="utf-8"))["answers"]
    golden = {
        p["id"]: p
        for p in json.loads((ROOT / "golden_dataset.json").read_text(encoding="utf-8"))["qa_pairs"]
    }
    lab = {
        r["id"]: r
        for r in json.loads((ROOT / "artifacts/benchmark_results.json").read_text(encoding="utf-8"))["results"]
    }
    if limit:
        answers = answers[:limit]
    sem = asyncio.Semaphore(concurrency)
    prior: dict[str, dict[str, Any]] = {}
    if resume_from is not None and resume_from.exists():
        prior = {r["id"]: r for r in json.loads(resume_from.read_text(encoding="utf-8"))["results"]}
    rows = await asyncio.gather(
        *(_score_case(sem, metrics, a, golden[a["id"]], prior.get(a["id"])) for a in answers)
    )
    for row in rows:
        for name in METRICS:
            row[f"lab_{name}"] = lab[row["id"]][name]
        row["difficulty"] = lab[row["id"]]["difficulty"]
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "ragas_version": ragas.__version__,
        "judge": {"provider": provider, "model": model},
        "dataset": "golden_dataset.json + artifacts/actual_answers.json (same 20 cases as core benchmark)",
        "note": "answer_relevancy not run: it needs an embeddings model and none was configured.",
        "results": rows,
    }


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3 or statistics.pstdev(xs) == 0 or statistics.pstdev(ys) == 0:
        return None
    return statistics.correlation(xs, ys)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limit", type=int, default=None, help="score only the first N cases (smoke test)")
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument(
        "--resume", action="store_true", help="re-score only metrics that are null in the existing output file"
    )
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/bonus_ex34_ragas.json")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    artifact = asyncio.run(_run(args.limit, args.concurrency, args.output if args.resume else None))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"{'metric':18} {'n':>3} {'lab_avg':>8} {'ragas_avg':>9} {'pearson':>8}")
    for name in METRICS:
        pairs = [(r[f"lab_{name}"], r[name]) for r in artifact["results"] if r[name] is not None]
        if not pairs:
            print(f"{name:18} {0:>3}  (no successful scores)")
            continue
        lab_v, rag_v = zip(*pairs)
        corr = _pearson(list(lab_v), list(rag_v))
        corr_s = "n/a" if corr is None else f"{corr:8.3f}"
        print(f"{name:18} {len(pairs):>3} {statistics.mean(lab_v):8.3f} {statistics.mean(rag_v):9.3f} {corr_s:>8}")
    errors = sum(len(r["errors"]) for r in artifact["results"])
    print(f"metric-call errors: {errors}\nSaved: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
