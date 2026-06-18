"""Retrieval evaluation against a hand-labeled golden set.

Golden set format (JSONL, one question per line):
    {"question": "...", "relevant_ids": [18, 22], "notes": "optional"}

Metrics computed per question, then averaged:
    Precision@k  — fraction of top-k results that are relevant
    Recall@k     — fraction of relevant cases found in top-k
    Hit@k        — 1 if any relevant case appears in top-k (else 0)
    MRR          — 1/rank of the first relevant result (0 if none in top-k)

k values: 1, 3, 5
"""
from __future__ import annotations

import json
import os
import sys
from typing import NamedTuple

ROOT = os.path.dirname(os.path.dirname(__file__))
DEFAULT_GOLDEN = os.path.join(ROOT, "eval", "golden_set.jsonl")
DEFAULT_K_VALUES = (1, 3, 5)
DEFAULT_MAX_K = 10


class QuestionResult(NamedTuple):
    question: str
    relevant_ids: list[int]
    retrieved_ids: list[int]   # ordered, length = max_k
    scores: list[float]
    notes: str


def _load_golden(path: str) -> list[dict]:
    items = []
    with open(path) as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"golden set line {lineno}: {e}") from e
            if not rec.get("question"):
                raise ValueError(f"golden set line {lineno}: missing 'question'")
            if not rec.get("relevant_ids"):
                raise ValueError(f"golden set line {lineno}: missing 'relevant_ids'")
            items.append(rec)
    return items


def _precision_at_k(retrieved: list[int], relevant: set[int], k: int) -> float:
    top = retrieved[:k]
    if not top:
        return 0.0
    return sum(1 for r in top if r in relevant) / k


def _recall_at_k(retrieved: list[int], relevant: set[int], k: int) -> float:
    if not relevant:
        return 0.0
    top = retrieved[:k]
    return sum(1 for r in top if r in relevant) / len(relevant)


def _hit_at_k(retrieved: list[int], relevant: set[int], k: int) -> float:
    return float(any(r in relevant for r in retrieved[:k]))


def _reciprocal_rank(retrieved: list[int], relevant: set[int]) -> float:
    for rank, r in enumerate(retrieved, 1):
        if r in relevant:
            return 1.0 / rank
    return 0.0


def run_eval(
    golden_path: str = DEFAULT_GOLDEN,
    k_values: tuple[int, ...] = DEFAULT_K_VALUES,
    max_k: int = DEFAULT_MAX_K,
    quiet: bool = False,
) -> dict:
    """Run the golden-set evaluation and return a results dict."""
    from .embeddings import load_index, search  # lazy: needs voyageai/numpy

    index = load_index()
    if index is None:
        raise RuntimeError(
            "No embedding index found. Run `build-embeddings` first."
        )

    items = _load_golden(golden_path)
    if not items:
        raise ValueError(f"Golden set at {golden_path} is empty.")

    results: list[QuestionResult] = []

    for item in items:
        question = item["question"]
        relevant = set(item["relevant_ids"])
        hits = search(question, index, k=max_k)
        retrieved_ids = [int(h[0]["paper_id"]) for h in hits]
        scores = [h[1] for h in hits]
        results.append(QuestionResult(
            question=question,
            relevant_ids=list(relevant),
            retrieved_ids=retrieved_ids,
            scores=scores,
            notes=item.get("notes", ""),
        ))

    # Aggregate
    agg: dict[str, list[float]] = {
        f"P@{k}": [] for k in k_values
    }
    agg.update({f"R@{k}": [] for k in k_values})
    agg.update({f"Hit@{k}": [] for k in k_values})
    agg["MRR"] = []

    per_question = []
    for qr in results:
        rel = set(qr.relevant_ids)
        row: dict = {"question": qr.question, "relevant_ids": qr.relevant_ids,
                     "retrieved_ids": qr.retrieved_ids[:max(k_values)],
                     "cosine_scores": [round(s, 4) for s in qr.scores[:max(k_values)]]}
        for k in k_values:
            row[f"P@{k}"] = round(_precision_at_k(qr.retrieved_ids, rel, k), 4)
            row[f"R@{k}"] = round(_recall_at_k(qr.retrieved_ids, rel, k), 4)
            row[f"Hit@{k}"] = round(_hit_at_k(qr.retrieved_ids, rel, k), 4)
            agg[f"P@{k}"].append(row[f"P@{k}"])
            agg[f"R@{k}"].append(row[f"R@{k}"])
            agg[f"Hit@{k}"].append(row[f"Hit@{k}"])
        rr = round(_reciprocal_rank(qr.retrieved_ids, rel), 4)
        row["RR"] = rr
        agg["MRR"].append(rr)
        per_question.append(row)

    mean_agg = {metric: round(sum(vals) / len(vals), 4) for metric, vals in agg.items()}
    n = len(results)

    if not quiet:
        _print_report(per_question, mean_agg, k_values, n)

    return {
        "n_questions": n,
        "k_values": list(k_values),
        "aggregate": mean_agg,
        "per_question": per_question,
    }


def _print_report(per_question: list[dict], agg: dict, k_values: tuple, n: int) -> None:
    ks = list(k_values)
    print(f"\n{'='*70}")
    print(f"  Retrieval Evaluation — {n} questions")
    print(f"{'='*70}")

    header = f"  {'Question':<45}" + "".join(f"  P@{k}" for k in ks) + "".join(f"  H@{k}" for k in ks) + "    MRR"
    print(header)
    print(f"  {'-'*45}" + "-" * (len(header) - 47))

    for row in per_question:
        q = row["question"][:43] + ".." if len(row["question"]) > 45 else row["question"]
        p_cols = "".join(f"  {row[f'P@{k}']:.2f}" for k in ks)
        h_cols = "".join(f"  {row[f'Hit@{k}']:.0f}   " for k in ks)
        rr = row["RR"]
        print(f"  {q:<45}{p_cols}  {rr:.2f}")

        rel = set(row["relevant_ids"])
        for rank, (pid, score) in enumerate(zip(row["retrieved_ids"], row["cosine_scores"]), 1):
            marker = "✓" if pid in rel else " "
            print(f"    {rank}. [{marker}] paper_id={pid}  score={score:.4f}")
        print()

    print(f"{'='*70}")
    print(f"  AGGREGATE ({n} questions)")
    print(f"{'='*70}")
    for k in ks:
        print(f"  Precision@{k}: {agg[f'P@{k}']:.4f}   "
              f"Recall@{k}: {agg[f'R@{k}']:.4f}   "
              f"Hit@{k}: {agg[f'Hit@{k}']:.4f}")
    print(f"  MRR:         {agg['MRR']:.4f}")
    print(f"{'='*70}\n")
