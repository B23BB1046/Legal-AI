"""Benchmark metrics for the Legal AI evaluation dashboard."""

from __future__ import annotations

from statistics import mean
from typing import Any


def _set(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {str(item) for item in value}


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def calculate_metrics(cases: list[dict[str, Any]]) -> dict[str, float | int | None]:
    """Calculate aggregate metrics from labeled evaluation cases.

    Each case may contain expected_doc_ids, retrieved_doc_ids, expected_citations,
    cited_citations, supported_claims, total_claims, hallucinated_claims,
    expected_precedents, identified_precedents, completed, and search_iterations.
    """
    retrieval_hits = retrieval_total = expected_retrieval_total = 0
    citation_hits = citation_total = 0
    precedent_hits = expected_precedent_total = 0
    supported = total_claims = hallucinated = 0
    completed = 0
    iterations: list[float] = []

    for case in cases:
        retrieved = _set(case.get("retrieved_doc_ids"))
        expected_retrieved = _set(case.get("expected_doc_ids"))
        cited = _set(case.get("cited_citations"))
        expected_citations = _set(case.get("expected_citations"))
        precedents = _set(case.get("identified_precedents"))
        expected_precedents = _set(case.get("expected_precedents"))
        retrieval_hits += len(retrieved & expected_retrieved)
        retrieval_total += len(retrieved)
        expected_retrieval_total += len(expected_retrieved)
        citation_hits += len(cited & expected_citations)
        citation_total += len(cited)
        precedent_hits += len(precedents & expected_precedents)
        expected_precedent_total += len(expected_precedents)
        supported += int(case.get("supported_claims", 0) or 0)
        total_claims += int(case.get("total_claims", 0) or 0)
        hallucinated += int(case.get("hallucinated_claims", 0) or 0)
        completed += int(bool(case.get("completed", False)))
        if case.get("search_iterations") is not None:
            iterations.append(float(case["search_iterations"]))

    return {
        "retrieval_precision": _rate(retrieval_hits, retrieval_total),
        "retrieval_recall": _rate(retrieval_hits, expected_retrieval_total),
        "citation_accuracy": _rate(citation_hits, citation_total),
        "evidence_support_rate": _rate(supported, total_claims),
        "hallucination_rate": _rate(hallucinated, total_claims),
        "precedent_identification_accuracy": _rate(precedent_hits, expected_precedent_total),
        "research_completion_rate": _rate(completed, len(cases)),
        "average_search_iterations": mean(iterations) if iterations else None,
        "case_count": len(cases),
    }
