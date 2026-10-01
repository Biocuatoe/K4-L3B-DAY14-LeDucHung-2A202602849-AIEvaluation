"""
Day 14 — AI Evaluation & Benchmarking Pipeline
AICB-P1: AI Practical Competency Program, Phase 1

Key concepts from lecture:
    - Evaluation = Scientific Method for AI (Hypothesis → Experiment → Measure → Conclude → Iterate)
    - 4 nhóm metrics: Task Completion, Answer Quality, RAG-Specific, Business
    - RAG pipeline metrics: Context Recall → Context Precision → Faithfulness → Answer Relevancy
    - LLM-as-Judge: rubric scoring 1-5, detect bias (positional, verbosity, self-preference)
    - Golden dataset: stratified sampling (5 Easy + 7 Medium + 5 Hard + 3 Adversarial)
    - Failure taxonomy: hallucination, irrelevant, incomplete, off_topic, refusal
    - 5 Whys method for root cause analysis
    - CI/CD integration: eval as quality gate (score < threshold = block deploy)
    - Continuous Improvement Loop: Evaluate → Analyze → Improve → Augment → Repeat

Instructions:
    1. Fill in every required section marked with TODO.
    2. Do NOT change class/function signatures. The optional ``contexts``
       parameter in ``run_full_eval`` is part of the required interface.
    3. Copy this file to solution/solution.py when done.
    4. Run: pytest tests/ -v

The reranking helper is an optional bonus exercise and may remain unimplemented.
"""

from __future__ import annotations

import json
import re
import statistics
from dataclasses import dataclass, field
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Task 1 — Data Models (Golden Dataset + Evaluation Results)
# ---------------------------------------------------------------------------

@dataclass
class QAPair:
    """
    A question-answer pair for evaluation (part of the Golden Dataset).

    From lecture: Golden dataset cần có:
        - question: câu hỏi user
        - ground_truth (expected_answer): expert-written expected answer
        - context: source documents cần retrieve
        - metadata: difficulty (easy/medium/hard), category, source_docs

    Fields:
        question:        The question to answer.
        expected_answer: The reference/ground-truth answer (expert-written).
        context:            Source context (may be empty string if not applicable).
        metadata:           Optional metadata dict (difficulty, category, etc.).
        retrieved_contexts: List of retrieved chunks (ORDER = retriever rank).
                            Used by the retrieval-side metrics (Task 2b).
    """
    question: str
    expected_answer: str
    context: str
    metadata: dict[str, Any] = field(default_factory=dict)
    retrieved_contexts: list[str] = field(default_factory=list)


@dataclass
class EvalResult:
    """
    Evaluation result for a single Q&A pair.

    From lecture - RAG metrics pipeline:
        Question → Retriever → Context → Generator → Answer
        Each step has a metric: Context Recall, Context Precision, Faithfulness, Answer Relevancy

    From lecture - Score interpretation:
        0.8-1.0: Good (Monitor, maintain)
        0.6-0.8: Needs work (Analyze failures, iterate)
        < 0.6: Significant issues (Deep investigation required)

    Fields:
        qa_pair:        The original QAPair.
        actual_answer:  What the agent actually returned.
        faithfulness:   Float 0-1, how grounded the answer is in context.
        relevance:      Float 0-1, how relevant the answer is to the question.
        completeness:   Float 0-1, how complete the answer is vs expected.
        passed:         True if all three scores >= 0.5.
        failure_type:   None if passed, otherwise one of:
                        "hallucination", "irrelevant", "incomplete", "off_topic".
        context_precision: Float 0-1 or None — quality of retrieval ranking.
        context_recall:    Float 0-1 or None — coverage of expected by context.
                        (Both stay None unless retrieved chunks are supplied;
                         they are NOT part of overall_score().)
    """
    qa_pair: QAPair
    actual_answer: str
    faithfulness: float
    relevance: float
    completeness: float
    passed: bool
    failure_type: str | None = None
    context_precision: float | None = None
    context_recall: float | None = None

    def overall_score(self) -> float:
        """Compute the average of faithfulness, relevance, and completeness.

        Returns:
            (faithfulness + relevance + completeness) / 3.0
        """
        return (self.faithfulness + self.relevance + self.completeness) / 3.0


# ---------------------------------------------------------------------------
# Task 2 — RAGAS Evaluator (Simplified word-overlap heuristic)
# ---------------------------------------------------------------------------
# In production, replace with actual RAGAS framework:
#   from ragas import evaluate
#   from ragas.metrics import Faithfulness, AnswerRelevancy, ContextRecall, ContextPrecision
#
# Or DeepEval:
#   from deepeval.metrics import FaithfulnessMetric, AnswerRelevancyMetric
#   assert_test(test_case, [faithfulness, hallucination])
#
# Or TruLens:
#   from trulens.core import Feedback
#   f_groundedness = Feedback(provider.groundedness_measure_with_cot_reasons)
# ---------------------------------------------------------------------------

# Common English stopwords are ignored so overlap reflects *content* words,
# not filler (otherwise "is"/"a"/"the" inflate every score).
STOPWORDS: set[str] = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "of", "in", "on", "at", "to", "for", "with", "as", "by", "and", "or",
    "it", "its", "this", "that", "these", "those", "from", "into", "than",
}


def _tokenize(text: str) -> set[str]:
    """Lowercase word tokenization, ignoring punctuation and stopwords."""
    if not text:
        return set()
    tokens = re.findall(r"\b\w+\b", text.lower())
    return {t for t in tokens if t not in STOPWORDS}


class RAGASEvaluator:
    """
    Evaluates RAG pipeline outputs using RAGAS-inspired heuristics.

    All metrics use word overlap rather than LLM calls for simplicity.
    Replace with actual LLM-based evaluation in production.
    """

    def evaluate_faithfulness(self, answer: str, context: str) -> float:
        """
        Measure how grounded the answer is in the context.

        Heuristic:
            answer_tokens = _tokenize(answer)
            context_tokens = _tokenize(context)
            faithfulness = |answer_tokens ∩ context_tokens| / |answer_tokens|
            Clamp to [0.0, 1.0]. Return 1.0 if answer is empty.

        Returns:
            float in [0.0, 1.0] — 1.0 = fully grounded in context.
        """
        answer_tokens = _tokenize(answer)
        if not answer_tokens:
            return 1.0
        context_tokens = _tokenize(context)
        if not context_tokens:
            return 0.0
        overlap = answer_tokens & context_tokens
        score = len(overlap) / len(answer_tokens)
        return max(0.0, min(1.0, score))

    def evaluate_relevance(self, answer: str, question: str) -> float:
        """
        Measure how relevant the answer is to the question.

        Heuristic:
            relevance = |answer_tokens ∩ question_tokens| / |question_tokens|
            Clamp to [0.0, 1.0]. Return 1.0 if question is empty.

        Returns:
            float in [0.0, 1.0]
        """
        question_tokens = _tokenize(question)
        if not question_tokens:
            return 1.0
        answer_tokens = _tokenize(answer)
        if not answer_tokens:
            return 0.0
        overlap = answer_tokens & question_tokens
        score = len(overlap) / len(question_tokens)
        return max(0.0, min(1.0, score))

    def evaluate_completeness(self, answer: str, expected: str) -> float:
        """
        Measure how well the answer covers the expected answer.

        Heuristic:
            completeness = |answer_tokens ∩ expected_tokens| / |expected_tokens|
            Clamp to [0.0, 1.0]. Return 1.0 if expected is empty.

        Returns:
            float in [0.0, 1.0]
        """
        expected_tokens = _tokenize(expected)
        if not expected_tokens:
            return 1.0
        answer_tokens = _tokenize(answer)
        if not answer_tokens:
            return 0.0
        overlap = answer_tokens & expected_tokens
        score = len(overlap) / len(expected_tokens)
        return max(0.0, min(1.0, score))

    # -----------------------------------------------------------------------
    # Task 2b — Retrieval-side metrics (evaluate the GET-CONTEXT step)
    # -----------------------------------------------------------------------
    # From lecture (RAG pipeline): Context Recall → Context Precision →
    #   Faithfulness → Answer Relevancy. The two below score the RETRIEVER,
    #   operating on a LIST of chunks (order = retriever rank).
    # -----------------------------------------------------------------------

    def evaluate_context_recall(self, contexts: list[str], expected: str) -> float:
        """Context Recall — how much of the expected answer is covered by the
        UNION of retrieved chunks.

        Heuristic:
            union_tokens = ⋃ _tokenize(chunk) for chunk in contexts
            recall = |expected_tokens ∩ union_tokens| / |expected_tokens|
            Clamp to [0.0, 1.0]. Return 1.0 if expected is empty.

        Low recall => retriever missed evidence the answer needs.
        """
        expected_tokens = _tokenize(expected)
        if not expected_tokens:
            return 1.0
        # Compute union of tokens across all contexts
        union_tokens: set[str] = set()
        for ctx in contexts:
            union_tokens |= _tokenize(ctx)
        if not union_tokens:
            return 0.0
        overlap = expected_tokens & union_tokens
        score = len(overlap) / len(expected_tokens)
        return max(0.0, min(1.0, score))

    def evaluate_context_precision(
        self,
        contexts: list[str],
        expected: str,
        relevance_threshold: float = 0.1,
    ) -> float:
        """Context Precision — RANK-AWARE Average Precision (AP@K), like RAGAS.
        Rewards retrievers that place RELEVANT chunks BEFORE noise.

        Steps:
            1. A chunk is "relevant" if it covers >= relevance_threshold of the
               expected tokens:  |chunk ∩ expected| / |expected| >= threshold
            2. Precision@k = (#relevant in top-k) / k
            3. AP@K = (1 / #relevant) * Σ_k [ Precision@k · relevant_k ]

        Return 1.0 if expected empty; 0.0 if no chunks or none relevant.
        Reordering relevant chunks earlier (reranking) raises this score.
        """
        expected_tokens = _tokenize(expected)
        if not expected_tokens:
            return 1.0
        if not contexts:
            return 0.0

        # Count relevant chunks
        relevant_indices: list[int] = []
        for i, ctx in enumerate(contexts):
            ctx_tokens = _tokenize(ctx)
            if ctx_tokens:
                overlap = ctx_tokens & expected_tokens
                precision_at_expected = len(overlap) / len(expected_tokens)
                if precision_at_expected >= relevance_threshold:
                    relevant_indices.append(i)

        num_relevant = len(relevant_indices)
        if num_relevant == 0:
            return 0.0

        # Compute AP@K
        total = 0.0
        for k in range(1, len(contexts) + 1):
            # Precision@k = (# relevant items in top-k) / k
            relevant_in_top_k = sum(1 for idx in relevant_indices if idx < k)
            precision_at_k = relevant_in_top_k / k
            # relevant_k = 1 if k-th item is relevant, else 0
            relevant_k = 1 if (k - 1) in relevant_indices else 0
            total += precision_at_k * relevant_k

        ap_score = total / num_relevant
        return max(0.0, min(1.0, ap_score))

    def run_full_eval(
        self,
        answer: str,
        question: str,
        context: str,
        expected: str,
        contexts: list[str] | None = None,
    ) -> EvalResult:
        """
        Run the three answer-side evaluations and, when ``contexts`` is
        supplied, both retrieval-side evaluations.

        passed = True if all three scores >= 0.5.

        failure_type determination (first match wins):
            faithfulness < 0.3  → "hallucination"
            relevance < 0.3     → "irrelevant"
            completeness < 0.3  → "incomplete"
            otherwise if failed → "off_topic"

        Retrieval wiring:
            contexts is None → context_recall and context_precision stay None
            contexts provided → evaluate and store both retrieval metrics

        The two retrieval metrics diagnose the retriever and do not change the
        three-metric ``passed`` rule or ``overall_score()``.

        Returns:
            EvalResult with all fields populated.
        """
        # Compute three answer-side metrics
        faithfulness = self.evaluate_faithfulness(answer, context)
        relevance = self.evaluate_relevance(answer, question)
        completeness = self.evaluate_completeness(answer, expected)

        # Pass rule: all three scores >= 0.5
        passed = faithfulness >= 0.5 and relevance >= 0.5 and completeness >= 0.5

        # Failure type determination (first match wins)
        failure_type: str | None = None
        if not passed:
            if faithfulness < 0.3:
                failure_type = "hallucination"
            elif relevance < 0.3:
                failure_type = "irrelevant"
            elif completeness < 0.3:
                failure_type = "incomplete"
            else:
                failure_type = "off_topic"

        # Create QAPair for EvalResult
        qa_pair = QAPair(
            question=question,
            expected_answer=expected,
            context=context,
        )

        # Optional retrieval metrics
        ctx_recall: float | None = None
        ctx_precision: float | None = None
        if contexts is not None:
            ctx_recall = self.evaluate_context_recall(contexts, expected)
            ctx_precision = self.evaluate_context_precision(contexts, expected)

        return EvalResult(
            qa_pair=qa_pair,
            actual_answer=answer,
            faithfulness=faithfulness,
            relevance=relevance,
            completeness=completeness,
            passed=passed,
            failure_type=failure_type,
            context_precision=ctx_precision,
            context_recall=ctx_recall,
        )


# ---------------------------------------------------------------------------
# Reranking helper (used by Exercise 3.5 — boosting Context Precision)
# ---------------------------------------------------------------------------

def rerank_by_overlap(contexts: list[str], query: str) -> list[str]:
    """A minimal lexical reranker: sort chunks by word overlap with the query,
    most-overlapping first. Stand-in for a real cross-encoder reranker.

    Reordering relevant chunks toward the top increases the rank-aware
    Context Precision WITHOUT changing the retrieved set.

    Hint: sorted(contexts, key=lambda c: len(_tokenize(c) & _tokenize(query)),
                 reverse=True)
    """
    # TODO (Bonus — Exercise 3.5): implement the reranker
    raise NotImplementedError("Implement rerank_by_overlap")


# ---------------------------------------------------------------------------
# Task 3 — LLM Judge
# ---------------------------------------------------------------------------
# From lecture:
#   - Judge LLM nhận: question + agent answer + reference answer + rubric
#   - Judge trả về: Score 1-5 + Rationale
#   - Best practices: multiple judges, randomize order, calibrate against human
#   - Biases: positional, verbosity, self-preference
#   - Rubric template:
#       5 = Correct, complete, well-cited
#       4 = Mostly correct, minor gaps
#       3 = Partially correct, some errors
#       2 = Significant errors or missing info
#       1 = Wrong or irrelevant
# ---------------------------------------------------------------------------

class LLMJudge:
    """
    Uses an LLM to score AI responses according to a rubric.
    """

    def __init__(self, judge_llm_fn: Callable[[str], str]) -> None:
        self._judge_llm_fn: Callable[[str], str] = judge_llm_fn

    def score_response(
        self,
        question: str,
        answer: str,
        rubric: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Score an AI response using the judge LLM.

        Args:
            question: The original question.
            answer:   The AI's answer to score.
            rubric:   Dict mapping criterion name → description.
                      Example: {"accuracy": "Is the answer factually correct?",
                                "clarity": "Is the answer clear and well-structured?"}

        Behavior:
            1. Build a judge prompt that includes the question, answer, and rubric.
            2. Call judge_llm_fn(prompt).
            3. Parse the response for scores.

        For simplicity, if the LLM response can't be parsed as JSON scores,
        return a default score of 0.5 for each criterion.

        Returns:
            {
                "scores":    dict[str, float],  # criterion → score 0-1
                "reasoning": str,               # raw LLM explanation
            }
        """
        # Build judge prompt
        rubric_lines = []
        for criterion, description in rubric.items():
            rubric_lines.append(f"- {criterion}: {description}")

        rubric_text = "\n".join(rubric_lines)

        prompt = f"""You are an impartial judge evaluating an AI assistant's response.

Question: {question}

AI Response to evaluate:
{answer}

Evaluate the response using the following rubric criteria:
{rubric_text}

Instructions:
1. Score each criterion on a scale from 0.0 to 1.0 (0.0 = completely fails, 1.0 = perfect).
2. Provide a brief reasoning for your scores.
3. Return your response as valid JSON with the following format:
{{
    "scores": {{"criterion1": score1, "criterion2": score2, ...}},
    "reasoning": "Your explanation here..."
}}

Return only the JSON object, no additional text."""

        raw_response = self._judge_llm_fn(prompt)

        # Try to parse JSON
        scores: dict[str, float] = {}
        reasoning = ""

        try:
            parsed = json.loads(raw_response)
            if isinstance(parsed, dict):
                # Extract scores
                if "scores" in parsed and isinstance(parsed["scores"], dict):
                    raw_scores = parsed["scores"]
                else:
                    raw_scores = {k: v for k, v in parsed.items()
                                  if k != "reasoning" and isinstance(v, (int, float))}
                    raw_scores = parsed.get("scores", raw_scores)

                # Normalize and clamp scores
                for criterion in rubric.keys():
                    if criterion in raw_scores:
                        try:
                            val = float(raw_scores[criterion])
                            # Clamp to [0.0, 1.0]
                            scores[criterion] = max(0.0, min(1.0, val))
                        except (ValueError, TypeError):
                            scores[criterion] = 0.5
                    else:
                        scores[criterion] = 0.5

                # Check for missing criteria
                for criterion in rubric.keys():
                    if criterion not in scores:
                        scores[criterion] = 0.5

                reasoning = str(parsed.get("reasoning", ""))
        except json.JSONDecodeError:
            # Parse failure - use fallback
            scores = {criterion: 0.5 for criterion in rubric.keys()}
            reasoning = "Failed to parse judge response. Used default scores."

        return {
            "scores": scores,
            "reasoning": reasoning,
        }

    def detect_bias(self, scores_batch: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Detect potential bias patterns in a batch of judge scores.

        Checks:
            positional_bias: Check if first response consistently scores higher
            leniency_bias:   Average score > 0.8 across all criteria
            severity_bias:   Average score < 0.3 across all criteria

        Args:
            scores_batch: List of score dicts from score_response().

        Returns:
            {
                "positional_bias": bool,
                "leniency_bias":   bool,
                "severity_bias":   bool,
            }
        """
        if not scores_batch:
            return {
                "positional_bias": False,
                "leniency_bias": False,
                "severity_bias": False,
            }

        # Extract overall scores for each item
        overall_scores: list[tuple[int, float]] = []  # (position, score)
        all_scores: list[float] = []

        for pos, item in enumerate(scores_batch):
            if not isinstance(item, dict):
                continue

            # Get overall score for this item
            item_score: float | None = None

            # Try to get "overall" key first
            if "overall" in item:
                try:
                    item_score = float(item["overall"])
                except (ValueError, TypeError):
                    pass

            # Otherwise, average numeric rubric scores
            if item_score is None and "scores" in item and isinstance(item["scores"], dict):
                numeric_scores = []
                for v in item["scores"].values():
                    try:
                        numeric_scores.append(float(v))
                    except (ValueError, TypeError):
                        pass
                if numeric_scores:
                    item_score = statistics.mean(numeric_scores)
                    all_scores.extend(numeric_scores)

            # Also collect all individual scores for leniency/severity
            if "scores" in item and isinstance(item["scores"], dict):
                for v in item["scores"].values():
                    try:
                        all_scores.append(float(v))
                    except (ValueError, TypeError):
                        pass

            if item_score is not None:
                overall_scores.append((pos, item_score))

        # Positional bias check
        positional_bias = False
        if len(overall_scores) >= 3:
            # Use Spearman-like sign check: compare first position vs rest
            first_pos_scores = [s for pos, s in overall_scores if pos == 0]
            rest_scores = [s for pos, s in overall_scores if pos > 0]

            if first_pos_scores and rest_scores:
                first_mean = statistics.mean(first_pos_scores)
                rest_mean = statistics.mean(rest_scores)

                # Check if first position is systematically higher
                # Also check correlation direction
                positions = [pos for pos, _ in overall_scores]
                scores_list = [s for _, s in overall_scores]

                # Simple sign-based check: is first score higher than rest?
                if first_mean > rest_mean:
                    # Check what fraction of items show this pattern
                    fraction_higher = sum(1 for pos, s in overall_scores if pos == 0 and s > rest_mean) / max(len(first_pos_scores), 1)
                    if fraction_higher >= 0.5:
                        positional_bias = True

        # Leniency bias: average overall score > 0.8
        leniency_bias = False
        if overall_scores:
            avg_overall = statistics.mean([s for _, s in overall_scores])
            if avg_overall > 0.8:
                leniency_bias = True

        # Severity bias: average overall score < 0.3
        severity_bias = False
        if overall_scores:
            if not leniency_bias:  # Only check severity if not leniency
                avg_overall = statistics.mean([s for _, s in overall_scores])
                if avg_overall < 0.3:
                    severity_bias = True

        return {
            "positional_bias": positional_bias,
            "leniency_bias": leniency_bias,
            "severity_bias": severity_bias,
        }


# ---------------------------------------------------------------------------
# Task 4 — Benchmark Runner
# ---------------------------------------------------------------------------
# From lecture:
#   - CI/CD integration: Framework + CI/CD = quality gate tự động
#   - Agent với faithfulness < 0.7 → không được deploy
#   - Regression = metric drop > 0.05 vs baseline
#   - Triggers: mỗi code release, mỗi prompt change, trước demo/launch
# ---------------------------------------------------------------------------

class BenchmarkRunner:
    """
    Runs a full evaluation benchmark.
    """

    def run(
        self,
        qa_pairs: list[QAPair],
        agent_fn: Callable[[str], str],
        evaluator: RAGASEvaluator,
    ) -> list[EvalResult]:
        """
        Run all QA pairs through the agent and evaluate each result.

        Args:
            qa_pairs:   List of QAPair objects.
            agent_fn:   Function str → str (the agent's answer function).
            evaluator:  RAGASEvaluator instance.

        Returns:
            List of EvalResult, one per qa_pair.
        """
        if not qa_pairs:
            return []

        results: list[EvalResult] = []
        for pair in qa_pairs:
            # Call agent to get actual answer
            actual_answer = agent_fn(pair.question)

            # Run full evaluation with the retrieved contexts
            result = evaluator.run_full_eval(
                answer=actual_answer,
                question=pair.question,
                context=pair.context,
                expected=pair.expected_answer,
                contexts=pair.retrieved_contexts,
            )

            # Preserve the original QAPair on the returned EvalResult
            result.qa_pair = pair

            results.append(result)

        return results

    def generate_report(self, results: list[EvalResult]) -> dict[str, Any]:
        """
        Generate an aggregate report from evaluation results.

        Returns:
            {
                "total":            int,
                "passed":           int,
                "pass_rate":        float,  # passed / total
                "avg_faithfulness": float,
                "avg_relevance":    float,
                "avg_completeness": float,
                "avg_context_recall": float | None,
                "avg_context_precision": float | None,
                "failure_types":    dict[str, int],  # type → count
            }

        Average only non-None retrieval scores. Return None for a retrieval
        average when no result contains that metric.
        """
        total = len(results)

        if total == 0:
            return {
                "total": 0,
                "passed": 0,
                "pass_rate": 0.0,
                "avg_faithfulness": 0.0,
                "avg_relevance": 0.0,
                "avg_completeness": 0.0,
                "avg_context_recall": None,
                "avg_context_precision": None,
                "failure_types": {},
            }

        passed = sum(1 for r in results if r.passed)
        pass_rate = passed / total

        avg_faithfulness = statistics.mean(r.faithfulness for r in results)
        avg_relevance = statistics.mean(r.relevance for r in results)
        avg_completeness = statistics.mean(r.completeness for r in results)

        # Only average non-None retrieval scores
        recall_values = [r.context_recall for r in results if r.context_recall is not None]
        precision_values = [r.context_precision for r in results if r.context_precision is not None]

        avg_context_recall: float | None = statistics.mean(recall_values) if recall_values else None
        avg_context_precision: float | None = statistics.mean(precision_values) if precision_values else None

        # Count failure types (exclude None)
        failure_types: dict[str, int] = {}
        for r in results:
            if r.failure_type is not None:
                failure_types[r.failure_type] = failure_types.get(r.failure_type, 0) + 1

        return {
            "total": total,
            "passed": passed,
            "pass_rate": pass_rate,
            "avg_faithfulness": avg_faithfulness,
            "avg_relevance": avg_relevance,
            "avg_completeness": avg_completeness,
            "avg_context_recall": avg_context_recall,
            "avg_context_precision": avg_context_precision,
            "failure_types": failure_types,
        }

    def run_regression(
        self,
        new_results: list[EvalResult],
        baseline_results: list[EvalResult],
    ) -> dict[str, Any]:
        """Compare new evaluation results against a baseline.

        A regression is when a metric's average drops by more than 0.05 vs baseline.

        Args:
            new_results: List of EvalResult instances (current run)
            baseline_results: List of EvalResult instances (reference/baseline)

        Returns:
            dict with keys:
              - 'new_avg_faithfulness': float
              - 'new_avg_relevance': float
              - 'new_avg_completeness': float
              - 'baseline_avg_faithfulness': float
              - 'baseline_avg_relevance': float
              - 'baseline_avg_completeness': float
              - 'regressions': list[str] — names of metrics that regressed
              - 'passed': bool — True if no regressions
        """
        REGRESSION_THRESHOLD = 0.05

        def avg_metric(results: list[EvalResult], field: str) -> float:
            if not results:
                return 0.0
            values = [getattr(r, field) for r in results]
            return statistics.mean(values)

        new_avg_faithfulness = avg_metric(new_results, "faithfulness")
        new_avg_relevance = avg_metric(new_results, "relevance")
        new_avg_completeness = avg_metric(new_results, "completeness")

        baseline_avg_faithfulness = avg_metric(baseline_results, "faithfulness")
        baseline_avg_relevance = avg_metric(baseline_results, "relevance")
        baseline_avg_completeness = avg_metric(baseline_results, "completeness")

        regressions: list[str] = []

        if new_avg_faithfulness < baseline_avg_faithfulness - REGRESSION_THRESHOLD:
            regressions.append("faithfulness")
        if new_avg_relevance < baseline_avg_relevance - REGRESSION_THRESHOLD:
            regressions.append("relevance")
        if new_avg_completeness < baseline_avg_completeness - REGRESSION_THRESHOLD:
            regressions.append("completeness")

        return {
            "new_avg_faithfulness": new_avg_faithfulness,
            "new_avg_relevance": new_avg_relevance,
            "new_avg_completeness": new_avg_completeness,
            "baseline_avg_faithfulness": baseline_avg_faithfulness,
            "baseline_avg_relevance": baseline_avg_relevance,
            "baseline_avg_completeness": baseline_avg_completeness,
            "regressions": regressions,
            "passed": len(regressions) == 0,
        }

    def identify_failures(
        self,
        results: list[EvalResult],
        threshold: float = 0.5,
    ) -> list[EvalResult]:
        """
        Return EvalResults where any score is below threshold.

        Args:
            results:   Full list of EvalResults.
            threshold: Minimum acceptable score for any metric.

        Returns:
            List of failing EvalResults.
        """
        if not results:
            return []

        failures: list[EvalResult] = []
        for result in results:
            # Check answer-side metrics only
            if (
                result.faithfulness < threshold
                or result.relevance < threshold
                or result.completeness < threshold
            ):
                failures.append(result)

        return failures


# ---------------------------------------------------------------------------
# Task 5 — Failure Analyzer
# ---------------------------------------------------------------------------
# From lecture:
#   Failure Taxonomy:
#     - hallucination: bịa thông tin → faithfulness guardrail yếu
#     - irrelevant: không giải quyết câu hỏi → prompt ambiguous
#     - incomplete: bỏ sót thông tin → context window nhỏ, retrieval thiếu
#     - off_topic: trả lời chủ đề khác → intent detection sai
#     - refusal: từ chối khi nên trả lời → guardrails quá chặt
#
#   5 Whys Method: hỏi "Tại sao?" liên tục cho đến root cause
#   Failure Clustering: fix 1 root cause giải quyết nhiều failures cùng lúc
#   Continuous Improvement: Evaluate → Analyze → Improve → Augment → Repeat
# ---------------------------------------------------------------------------

class FailureAnalyzer:
    """
    Analyzes failed evaluation results to identify patterns and suggest fixes.
    """

    def categorize_failures(
        self, failures: list[EvalResult]
    ) -> dict[str, int]:
        """
        Count failures by failure_type.

        Returns:
            dict mapping failure_type → count.
            Example: {"hallucination": 3, "irrelevant": 2, "incomplete": 5}
        """
        if not failures:
            return {}

        categories: dict[str, int] = {}
        for failure in failures:
            if failure.failure_type is not None:
                categories[failure.failure_type] = categories.get(failure.failure_type, 0) + 1

        return categories

    def find_root_cause(self, failure: EvalResult) -> str:
        """
        Suggest a root cause for a single failure based on its scores.

        Returns one of these strings based on which score is lowest:
            "Context is missing or irrelevant — improve retrieval"
            "Answer does not address the question — improve prompt clarity"
            "Answer is missing key information — increase context window or improve generation"
            "Multiple issues detected — review full pipeline"
        """
        # Use the lowest answer metric (tie-break: first one found via min)
        metrics = {
            "faithfulness": failure.faithfulness,
            "relevance": failure.relevance,
            "completeness": failure.completeness,
        }

        lowest_metric = min(metrics, key=lambda k: metrics[k])

        if lowest_metric == "faithfulness":
            return "Context is missing or irrelevant — improve retrieval"
        elif lowest_metric == "relevance":
            return "Answer does not address the question — improve prompt clarity"
        elif lowest_metric == "completeness":
            return "Answer is missing key information — increase context window or improve generation"
        else:
            return "Multiple issues detected — review full pipeline"

    def generate_improvement_log(
        self,
        failures: list[EvalResult],
        suggestions: list[str],
    ) -> str:
        """Generate a Markdown table logging failures and improvement actions.

        Format:
        | Failure ID | Type | Root Cause | Suggested Fix | Status |
        |------------|------|------------|---------------|--------|
        | F001       | ...  | ...        | ...           | Open   |

        Args:
            failures: List of EvalResult instances where passed=False
            suggestions: List of suggestion strings (one per failure, can be shorter list)

        Returns:
            Markdown table string with a row per failure. Status is always "Open".
        """
        if not failures:
            # Return header-only table for empty failures
            header = "| Failure ID | Type | Root Cause | Suggested Fix | Status |"
            separator = "|------------|------|------------|---------------|--------|"
            return f"{header}\n{separator}\n"

        lines: list[str] = []
        header = "| Failure ID | Type | Root Cause | Suggested Fix | Status |"
        separator = "|------------|------|------------|---------------|--------|"

        lines.append(header)
        lines.append(separator)

        for i, failure in enumerate(failures):
            fid = f"F{i + 1:03d}"
            ftype = failure.failure_type if failure.failure_type is not None else "unknown"
            root_cause = self.find_root_cause(failure)
            # Cycle through suggestions if shorter than failures
            suggested_fix = suggestions[i % len(suggestions)] if suggestions else "No suggestions available"
            status = "Open"

            lines.append(f"| {fid} | {ftype} | {root_cause} | {suggested_fix} | {status} |")

        return "\n".join(lines)

    def generate_improvement_suggestions(
        self, failures: list[EvalResult]
    ) -> list[str]:
        """
        Generate a prioritized list of improvement suggestions based on failure patterns.

        Each suggestion should be a concrete, actionable string.

        Examples:
            "Increase chunk size in RAG pipeline to reduce context fragmentation"
            "Add few-shot examples showing complete answers to improve completeness"
            "Implement hallucination checker to filter unsupported claims"

        Returns:
            List of at least 3 suggestion strings (or fewer if failures is empty).
        """
        if not failures:
            return []

        categories = self.categorize_failures(failures)

        suggestions: list[str] = []

        # Hallucination → improve retrieval / add guardrails
        hallucination_count = categories.get("hallucination", 0)
        if hallucination_count > 0:
            suggestions.append(
                "Implement hallucination guardrails: add fact-checking layer or grounding prompt to reduce unsupported claims"
            )
            suggestions.append(
                "Improve retrieval quality: enhance chunking strategy or increase top-k to ensure relevant context is retrieved"
            )

        # Irrelevant → improve prompt clarity
        irrelevant_count = categories.get("irrelevant", 0)
        if irrelevant_count > 0:
            suggestions.append(
                "Clarify prompt templates: add explicit instruction about question scope and expected answer format"
            )
            suggestions.append(
                "Improve intent detection: add query rewriting or classification step to better match user intent"
            )

        # Incomplete → improve context/generation
        incomplete_count = categories.get("incomplete", 0)
        if incomplete_count > 0:
            suggestions.append(
                "Increase context window: expand chunk size or retrieve more chunks to cover missing information"
            )
            suggestions.append(
                "Add few-shot examples: provide complete answer patterns to improve generation completeness"
            )

        # Off-topic → improve retrieval or intent detection
        off_topic_count = categories.get("off_topic", 0)
        if off_topic_count > 0:
            suggestions.append(
                "Strengthen retrieval relevance: refine query processing or rerank results to reduce off-topic retrieval"
            )

        # If we have failures but not enough suggestions, add generic ones
        if len(suggestions) < 3:
            suggestions.append("Augment benchmark: add more diverse test cases to cover edge scenarios")
            suggestions.append("Monitor retrieval metrics: track context recall and precision to detect degradation early")

        return suggestions[:3] if len(suggestions) >= 3 else suggestions


# ---------------------------------------------------------------------------
# Entry point for manual testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Sample golden dataset (mini version — use 20 pairs in actual lab)
    # From lecture: stratified sampling = 5 Easy + 7 Medium + 5 Hard + 3 Adversarial
    qa_pairs = [
        # Easy — factual lookup
        QAPair(
            question="What is RAG?",
            expected_answer="RAG stands for Retrieval-Augmented Generation, which combines retrieval with text generation.",
            context="RAG is a technique that retrieves relevant documents and uses them to ground LLM generation.",
            metadata={"difficulty": "easy", "category": "definition"},
        ),
        QAPair(
            question="What is the capital of France?",
            expected_answer="Paris is the capital of France.",
            context="France is a country in Western Europe. Its capital city is Paris.",
            metadata={"difficulty": "easy", "category": "factual"},
        ),
        # Medium — multi-step reasoning
        QAPair(
            question="Explain backpropagation and why it matters for training",
            expected_answer="Backpropagation is an algorithm for training neural networks by computing gradients efficiently, enabling deep learning models to learn from errors.",
            context="Neural networks learn through gradient descent. Backpropagation efficiently computes these gradients layer by layer.",
            metadata={"difficulty": "medium", "category": "explanation"},
        ),
        # Hard — ambiguous
        QAPair(
            question="Should I use RAG or fine-tuning for my chatbot?",
            expected_answer="It depends on the use case: RAG is better for frequently updated knowledge, fine-tuning for consistent style/behavior. Consider cost, latency, and data freshness.",
            context="RAG retrieves external documents at inference time. Fine-tuning modifies model weights during training.",
            metadata={"difficulty": "hard", "category": "comparison"},
        ),
        # Adversarial — out-of-scope
        QAPair(
            question="What is the meaning of life?",
            expected_answer="This question is outside the scope of this system. I can help with AI and technology questions.",
            context="This is an AI assistant specialized in technology topics.",
            metadata={"difficulty": "adversarial", "category": "out_of_scope"},
        ),
    ]

    evaluator = RAGASEvaluator()
    runner = BenchmarkRunner()

    def mock_agent(question: str) -> str:
        """Simple mock agent for testing. Replace with your actual agent."""
        return f"Based on my knowledge: {question[:30]}... The answer involves key concepts."

    # Run benchmark
    results = runner.run(qa_pairs, mock_agent, evaluator)
    report = runner.generate_report(results)
    print("=== Benchmark Report ===")
    for k, v in report.items():
        print(f"  {k}: {v}")

    # Identify and analyze failures
    failures = runner.identify_failures(results, threshold=0.5)
    print(f"\n=== Failures ({len(failures)}) ===")
    analyzer = FailureAnalyzer()

    # Categorize (from lecture: cluster before fix)
    categories = analyzer.categorize_failures(failures)
    print("Failure Categories:", categories)

    # Root cause for each failure (from lecture: 5 Whys)
    for f in failures:
        cause = analyzer.find_root_cause(f)
        print(f"  Root cause: {cause}")

    # Improvement suggestions (from lecture: continuous improvement loop)
    suggestions = analyzer.generate_improvement_suggestions(failures)
    print("\nImprovement Suggestions:")
    for s in suggestions:
        print(f"  - {s}")

    # Generate improvement log (Markdown table)
    log = analyzer.generate_improvement_log(failures, suggestions)
    print("\n=== Improvement Log ===")
    print(log)
