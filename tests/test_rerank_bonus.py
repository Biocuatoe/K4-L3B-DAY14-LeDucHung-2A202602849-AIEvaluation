"""Focused tests for Exercise 3.5 (bonus): rerank_by_overlap().

Complements the single skip-able test in test_solution.py; does not replace it.
"""

import importlib.util
import sys
import unittest
from pathlib import Path

DAY_DIR = Path(__file__).parent.parent
_path = DAY_DIR / "solution" / "solution.py"
if not _path.exists():
    _path = DAY_DIR / "template.py"
_spec = importlib.util.spec_from_file_location("rerank_bonus_under_test", str(_path))
_m = importlib.util.module_from_spec(_spec)
sys.modules["rerank_bonus_under_test"] = _m
_spec.loader.exec_module(_m)

rerank_by_overlap = _m.rerank_by_overlap
RAGASEvaluator = _m.RAGASEvaluator

QUERY = "How long is the return window for opened devices"
NOISE = "Bananas are a tropical fruit rich in potassium"
PARTIAL = "Devices can be repaired at an authorized service center"
BEST = "The return window for opened devices is fourteen calendar days"


class TestRerankByOverlap(unittest.TestCase):
    def test_moves_most_overlapping_chunk_first(self):
        self.assertEqual(rerank_by_overlap([NOISE, PARTIAL, BEST], QUERY)[0], BEST)

    def test_same_chunks_text_preserved_exactly(self):
        original = [NOISE, PARTIAL, BEST]
        reranked = rerank_by_overlap(original, QUERY)
        self.assertEqual(sorted(reranked), sorted(original))
        self.assertEqual(len(reranked), len(original))

    def test_does_not_mutate_input(self):
        original = [NOISE, PARTIAL, BEST]
        snapshot = list(original)
        rerank_by_overlap(original, QUERY)
        self.assertEqual(original, snapshot)

    def test_deterministic_and_stable_on_ties(self):
        tie_a, tie_b = "alpha beta", "gamma delta"  # zero overlap with the query
        out = rerank_by_overlap([tie_a, tie_b], QUERY)
        self.assertEqual(out, [tie_a, tie_b])
        self.assertEqual(out, rerank_by_overlap([tie_a, tie_b], QUERY))

    def test_empty_inputs(self):
        self.assertEqual(rerank_by_overlap([], QUERY), [])
        self.assertEqual(rerank_by_overlap([NOISE, BEST], ""), [NOISE, BEST])

    def test_recall_unchanged_precision_not_worse(self):
        evaluator = RAGASEvaluator()
        expected = "The return window for opened devices is fourteen calendar days"
        before = [NOISE, PARTIAL, BEST]
        after = rerank_by_overlap(before, QUERY)
        self.assertAlmostEqual(
            evaluator.evaluate_context_recall(before, expected),
            evaluator.evaluate_context_recall(after, expected),
        )
        self.assertGreaterEqual(
            evaluator.evaluate_context_precision(after, expected),
            evaluator.evaluate_context_precision(before, expected),
        )


if __name__ == "__main__":
    unittest.main()
