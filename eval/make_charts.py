"""Generate presentation-ready charts from eval_results.json.

Usage:
    python eval/make_charts.py [path/to/eval_results.json]

Writes PNGs to output/charts/.
"""
from __future__ import annotations

import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = os.path.dirname(os.path.dirname(__file__))
OUT_DIR = os.path.join(ROOT, "output", "charts")

# Consistent palette
C_PRIMARY = "#2563eb"   # blue
C_ACCENT = "#16a34a"    # green
C_WARN = "#dc2626"      # red
C_MUTED = "#94a3b8"     # gray
C_PURPLE = "#7c3aed"

plt.rcParams.update({
    "font.size": 12,
    "axes.titlesize": 15,
    "axes.titleweight": "bold",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.dpi": 150,
})


def load(path: str) -> dict:
    with open(path) as fh:
        return json.load(fh)


def chart_headline(agg: dict, n: int, path: str) -> None:
    """The four numbers that tell the story, as big-number tiles."""
    fig, axes = plt.subplots(1, 4, figsize=(13, 3.2))
    tiles = [
        ("MRR", agg["MRR"], C_PURPLE, "first relevant case\nlands at rank ~1.1"),
        ("Hit@3", agg["Hit@3"], C_ACCENT, "a relevant case in\ntop 3 for every query"),
        ("Hit@1", agg["Hit@1"], C_PRIMARY, "right case is #1\nresult 85% of time"),
        ("Precision@1", agg["P@1"], C_PRIMARY, "top result is\nrelevant 85% of time"),
    ]
    for ax, (label, val, color, sub) in zip(axes, tiles):
        ax.axis("off")
        ax.text(0.5, 0.72, f"{val:.2f}", ha="center", va="center",
                fontsize=46, fontweight="bold", color=color)
        ax.text(0.5, 0.34, label, ha="center", va="center",
                fontsize=15, fontweight="bold", color="#1e293b")
        ax.text(0.5, 0.12, sub, ha="center", va="center",
                fontsize=9.5, color="#64748b")
    fig.suptitle(f"Retrieval Performance — Pilot Evaluation (n={n} questions)",
                 fontsize=16, fontweight="bold", y=1.02)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def chart_pr_curve(agg: dict, ks: list[int], path: str) -> None:
    """Precision / Recall / Hit as k increases — the core tradeoff."""
    fig, ax = plt.subplots(figsize=(8, 5))
    p = [agg[f"P@{k}"] for k in ks]
    r = [agg[f"R@{k}"] for k in ks]
    h = [agg[f"Hit@{k}"] for k in ks]

    ax.plot(ks, p, "o-", color=C_PRIMARY, linewidth=2.5, markersize=9, label="Precision@k")
    ax.plot(ks, r, "s-", color=C_ACCENT, linewidth=2.5, markersize=9, label="Recall@k")
    ax.plot(ks, h, "^--", color=C_PURPLE, linewidth=2.5, markersize=9, label="Hit@k")

    for k, val in zip(ks, p):
        ax.annotate(f"{val:.2f}", (k, val), textcoords="offset points",
                    xytext=(0, 10), ha="center", fontsize=10, color=C_PRIMARY)
    for k, val in zip(ks, r):
        ax.annotate(f"{val:.2f}", (k, val), textcoords="offset points",
                    xytext=(0, -16), ha="center", fontsize=10, color=C_ACCENT)
    for k, val in zip(ks, h):
        ax.annotate(f"{val:.2f}", (k, val), textcoords="offset points",
                    xytext=(0, 10), ha="center", fontsize=10, color=C_PURPLE)

    ax.set_xticks(ks)
    ax.set_xlabel("k (number of cases retrieved)")
    ax.set_ylabel("score")
    ax.set_ylim(0, 1.08)
    ax.set_title("Precision / Recall / Hit-rate vs. k")
    ax.legend(loc="center right", frameon=False)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def chart_rank_distribution(per_q: list[dict], path: str) -> None:
    """Where does the first relevant case land? Histogram of best rank."""
    best_ranks = []
    for row in per_q:
        rel = set(row["relevant_ids"])
        rank = next((i for i, pid in enumerate(row["retrieved_ids"], 1) if pid in rel), 0)
        best_ranks.append(rank)

    max_r = max(best_ranks)
    bins = list(range(1, max_r + 2))
    counts = [best_ranks.count(b) for b in range(1, max_r + 1)]
    colors = [C_ACCENT if b == 1 else C_PRIMARY if b <= 3 else C_WARN
              for b in range(1, max_r + 1)]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(range(1, max_r + 1), counts, color=colors, width=0.7)
    for bar, c in zip(bars, counts):
        if c:
            ax.text(bar.get_x() + bar.get_width() / 2, c + 0.15, str(c),
                    ha="center", fontsize=12, fontweight="bold")
    ax.set_xticks(range(1, max_r + 1))
    ax.set_xlabel("rank of first relevant case")
    ax.set_ylabel("number of questions")
    ax.set_title("How quickly the right case is found")
    ax.set_ylim(0, max(counts) + 1)
    # legend by color meaning
    from matplotlib.patches import Patch
    ax.legend(handles=[
        Patch(color=C_ACCENT, label="rank 1 (top result)"),
        Patch(color=C_PRIMARY, label="rank 2–3"),
        Patch(color=C_WARN, label="rank 4+"),
    ], frameon=False, loc="upper right")
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def chart_per_question(per_q: list[dict], path: str) -> None:
    """Horizontal bar of P@3 per question — shows spread and the few misses."""
    labels = [row["question"][:50] + ("…" if len(row["question"]) > 50 else "")
              for row in per_q]
    vals = [row["P@3"] for row in per_q]
    # sort best at top
    order = np.argsort(vals)
    labels = [labels[i] for i in order]
    vals = [vals[i] for i in order]
    colors = [C_WARN if v == 0 else C_MUTED if v < 0.5 else C_ACCENT for v in vals]

    fig, ax = plt.subplots(figsize=(10, 8))
    y = np.arange(len(labels))
    ax.barh(y, vals, color=colors)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlim(0, 1.05)
    ax.set_xlabel("Precision@3")
    ax.set_title("Per-question Precision@3 (sorted)")
    for yi, v in zip(y, vals):
        ax.text(v + 0.02, yi, f"{v:.2f}", va="center", fontsize=9)
    ax.axvline(np.mean(vals), color="#1e293b", linestyle="--", linewidth=1.2,
               alpha=0.7)
    ax.text(np.mean(vals), len(labels) - 0.3, f" mean {np.mean(vals):.2f}",
            fontsize=9, color="#1e293b")
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> int:
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "output", "eval_results.json")
    if not os.path.exists(src):
        print(f"Results file not found: {src}\nRun `python -m alz_finder.cli eval --output {src}` first.")
        return 1
    data = load(src)
    agg = data["aggregate"]
    ks = data["k_values"]
    per_q = data["per_question"]
    n = data["n_questions"]

    os.makedirs(OUT_DIR, exist_ok=True)
    chart_headline(agg, n, os.path.join(OUT_DIR, "1_headline.png"))
    chart_pr_curve(agg, ks, os.path.join(OUT_DIR, "2_precision_recall.png"))
    chart_rank_distribution(per_q, os.path.join(OUT_DIR, "3_rank_distribution.png"))
    chart_per_question(per_q, os.path.join(OUT_DIR, "4_per_question.png"))

    print(f"Wrote 4 charts to {OUT_DIR}/")
    for f in sorted(os.listdir(OUT_DIR)):
        print(f"  {f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
