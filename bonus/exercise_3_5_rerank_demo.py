"""Exercise 3.5 (bonus) - measure Context Recall / Precision before and after reranking.

Uses the same 20 stored traces in artifacts/actual_answers.json. For each trace the
retrieved chunks are reordered with template.rerank_by_overlap(chunks, QUESTION)
(the question is the query; expected_answer is used only for scoring, never for
reranking). The chunk set is unchanged. Read-only on core artifacts; writes only
artifacts/bonus_ex35_rerank.json.

Run:  python bonus/exercise_3_5_rerank_demo.py
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from template import RAGASEvaluator, rerank_by_overlap  # noqa: E402


def _label(chunk: dict[str, Any]) -> str:
    return f"{chunk['source_doc']}#{chunk['chunk_id']}"


def main() -> int:
    answers = json.loads((ROOT / "artifacts/actual_answers.json").read_text(encoding="utf-8"))["answers"]
    golden = {
        p["id"]: p
        for p in json.loads((ROOT / "golden_dataset.json").read_text(encoding="utf-8"))["qa_pairs"]
    }
    evaluator = RAGASEvaluator()
    rows: list[dict[str, Any]] = []
    for record in answers:
        chunks = record["retrieved_contexts"]
        expected = golden[record["id"]]["expected_answer"]
        ranked_texts = rerank_by_overlap([c["text"] for c in chunks], record["question"])
        # Map reranked texts back to chunk metadata (duplicates consumed in order).
        pool = list(chunks)
        reranked = []
        for text in ranked_texts:
            index = next(i for i, c in enumerate(pool) if c["text"] == text)
            reranked.append(pool.pop(index))
        before_t, after_t = [c["text"] for c in chunks], [c["text"] for c in reranked]
        rows.append(
            {
                "id": record["id"],
                "order_before": [_label(c) for c in chunks],
                "order_after": [_label(c) for c in reranked],
                "same_chunk_set": sorted(before_t) == sorted(after_t),
                "recall_before": evaluator.evaluate_context_recall(before_t, expected),
                "recall_after": evaluator.evaluate_context_recall(after_t, expected),
                "precision_before": evaluator.evaluate_context_precision(before_t, expected),
                "precision_after": evaluator.evaluate_context_precision(after_t, expected),
            }
        )
    for row in rows:
        row["delta_precision"] = row["precision_after"] - row["precision_before"]

    summary = {
        "cases": len(rows),
        "all_same_chunk_set": all(r["same_chunk_set"] for r in rows),
        "order_changed": sum(r["order_before"] != r["order_after"] for r in rows),
        "precision_improved": sum(r["delta_precision"] > 1e-9 for r in rows),
        "precision_unchanged": sum(abs(r["delta_precision"]) <= 1e-9 for r in rows),
        "precision_worse": sum(r["delta_precision"] < -1e-9 for r in rows),
        "avg_recall_before": statistics.mean(r["recall_before"] for r in rows),
        "avg_recall_after": statistics.mean(r["recall_after"] for r in rows),
        "avg_precision_before": statistics.mean(r["precision_before"] for r in rows),
        "avg_precision_after": statistics.mean(r["precision_after"] for r in rows),
    }
    out = ROOT / "artifacts/bonus_ex35_rerank.json"
    out.write_text(
        json.dumps({"query": "question text", "summary": summary, "results": rows}, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"{'ID':4} {'R_before':>8} {'R_after':>8} {'P_before':>8} {'P_after':>8} {'dP':>7}  order_changed")
    for r in rows:
        print(
            f"{r['id']:4} {r['recall_before']:8.3f} {r['recall_after']:8.3f} "
            f"{r['precision_before']:8.3f} {r['precision_after']:8.3f} {r['delta_precision']:+7.3f}  "
            f"{r['order_before'] != r['order_after']}"
        )
    print(json.dumps(summary, indent=2))
    shown = max(rows, key=lambda r: abs(r["delta_precision"]))
    print(f"\nLargest |dP| case: {shown['id']}\n before: {shown['order_before']}\n after:  {shown['order_after']}")
    print(f"Saved: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
