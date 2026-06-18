"""Plain-language charts for a non-technical audience.

Same data as make_charts.py, but every label is in everyday words — no
"Precision@k", "MRR", or "Hit@k". Built for presenting to people who just
want to know: does it find the right case, and how often?

Usage:
    python eval/make_charts_friendly.py [path/to/eval_results.json]

Writes PNGs to output/charts_friendly/.
"""
from __future__ import annotations

import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Patch

ROOT = os.path.dirname(os.path.dirname(__file__))
OUT_DIR = os.path.join(ROOT, "output", "charts_friendly")

GREEN = "#16a34a"
BLUE = "#2563eb"
LIGHTBLUE = "#93c5fd"
GRAY = "#cbd5e1"
DARK = "#1e293b"
SLATE = "#475569"

plt.rcParams.update({
    "font.size": 13,
    "axes.titlesize": 18,
    "axes.titleweight": "bold",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.dpi": 150,
})


def load(path: str) -> dict:
    with open(path) as fh:
        return json.load(fh)


def _first_relevant_rank(row: dict) -> int:
    rel = set(row["relevant_ids"])
    return next((i for i, pid in enumerate(row["retrieved_ids"], 1) if pid in rel), 0)


def chart_summary(per_q: list[dict], n: int, path: str) -> None:
    """One big plain-English takeaway, with three supporting facts."""
    ranks = [_first_relevant_rank(r) for r in per_q]
    n_top1 = sum(1 for r in ranks if r == 1)
    n_top3 = sum(1 for r in ranks if 1 <= r <= 3)

    fig = plt.figure(figsize=(12, 6.5))
    fig.patch.set_facecolor("white")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")

    ax.text(0.5, 0.92, "Does it find the right case?", ha="center",
            fontsize=24, fontweight="bold", color=DARK)

    # Big headline statement
    ax.text(0.5, 0.72,
            "For every caregiver question we tested, a relevant\n"
            "real-life case appeared in the top 3 results.",
            ha="center", fontsize=20, color=GREEN, fontweight="bold",
            linespacing=1.4)

    # Three supporting fact cards
    facts = [
        (f"{n_top3} of {n}", "questions had a relevant\ncase in the top 3", GREEN),
        (f"{n_top1} of {n}", "questions had the right\ncase as the #1 result", BLUE),
        ("Top 3", "results are all the\nchatbot needs to answer", SLATE),
    ]
    x_positions = [0.19, 0.5, 0.81]
    for x, (big, small, color) in zip(x_positions, facts):
        card = FancyBboxPatch((x - 0.14, 0.18), 0.28, 0.28,
                              boxstyle="round,pad=0.01,rounding_size=0.02",
                              transform=ax.transAxes, facecolor="#f8fafc",
                              edgecolor="#e2e8f0", linewidth=1.5)
        ax.add_patch(card)
        ax.text(x, 0.38, big, ha="center", fontsize=30, fontweight="bold", color=color)
        ax.text(x, 0.245, small, ha="center", fontsize=12.5, color=SLATE,
                linespacing=1.3)

    ax.text(0.5, 0.06,
            f"Based on {n} realistic caregiver questions, each checked by hand "
            f"against the case library.",
            ha="center", fontsize=11, color="#94a3b8", style="italic")

    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def chart_waffle(per_q: list[dict], n: int, path: str) -> None:
    """20-square grid: where did the right case show up for each question?"""
    ranks = sorted(_first_relevant_rank(r) for r in per_q)

    def color_for(rank: int) -> str:
        if rank == 1:
            return GREEN
        if rank <= 3:
            return LIGHTBLUE
        return GRAY

    cols = 5
    rows = (n + cols - 1) // cols
    fig, ax = plt.subplots(figsize=(10, 8))
    ax.set_xlim(-0.5, cols - 0.5)
    ax.set_ylim(-0.6, rows - 0.4)
    ax.set_aspect("equal")
    ax.axis("off")

    # place squares left-to-right, top-to-bottom; best (rank 1) first
    for idx, rank in enumerate(ranks):
        r = idx // cols
        c = idx % cols
        y = rows - 1 - r
        box = FancyBboxPatch((c - 0.42, y - 0.42), 0.84, 0.84,
                             boxstyle="round,pad=0.01,rounding_size=0.08",
                             facecolor=color_for(rank), edgecolor="white",
                             linewidth=2)
        ax.add_patch(box)

    fig.suptitle("Each square is one caregiver question we tested",
                 fontsize=19, fontweight="bold", color=DARK, y=0.97)
    ax.set_title("Where did the right case appear in the results?",
                 fontsize=13.5, fontweight="normal", color=SLATE, pad=16)

    legend = [
        Patch(facecolor=GREEN, label="Right case was the #1 result"),
        Patch(facecolor=LIGHTBLUE, label="Right case was in the top 3"),
        Patch(facecolor=GRAY, label="Not found in top 3"),
    ]
    ax.legend(handles=legend, loc="upper center", bbox_to_anchor=(0.5, -0.04),
              ncol=3, frameon=False, fontsize=11.5)
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def chart_topk_bars(per_q: list[dict], n: int, path: str) -> None:
    """Two simple bars: right answer at #1 vs. in the top 3."""
    ranks = [_first_relevant_rank(r) for r in per_q]
    pct_top1 = 100 * sum(1 for r in ranks if r == 1) / n
    pct_top3 = 100 * sum(1 for r in ranks if 1 <= r <= 3) / n

    fig, ax = plt.subplots(figsize=(9, 5))
    labels = ["Right case was\nthe #1 result", "Right case was\nin the top 3"]
    vals = [pct_top1, pct_top3]
    colors = [BLUE, GREEN]
    bars = ax.bar(labels, vals, color=colors, width=0.55)
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, v + 2, f"{v:.0f}%",
                ha="center", fontsize=22, fontweight="bold", color=DARK)
    ax.set_ylim(0, 112)
    ax.set_ylabel("of questions")
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_yticklabels(["0%", "25%", "50%", "75%", "100%"])
    ax.set_title("How often the system found the right case", pad=16)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def chart_how_it_works(path: str) -> None:
    """A simple left-to-right explainer of what the system does."""
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 4)
    ax.axis("off")

    steps = [
        ("Caregiver\nasks a question", "“My mom keeps\nlosing words…”", BLUE),
        ("System searches\nthe case library", "92 real Alzheimer's\ncase studies", SLATE),
        ("Finds the most\nrelevant cases", "ranks them by\nhow well they match", GREEN),
        ("Answers, grounded\nin real cases", "with the source\ncase cited", GREEN),
    ]
    centers = [1.7, 4.6, 7.5, 10.4]
    for i, ((title, sub, color), cx) in enumerate(zip(steps, centers)):
        box = FancyBboxPatch((cx - 1.25, 1.1), 2.5, 1.8,
                             boxstyle="round,pad=0.02,rounding_size=0.15",
                             facecolor="#f8fafc", edgecolor=color, linewidth=2)
        ax.add_patch(box)
        ax.text(cx, 2.45, title, ha="center", va="center", fontsize=12.5,
                fontweight="bold", color=DARK, linespacing=1.2)
        ax.text(cx, 1.6, sub, ha="center", va="center", fontsize=10,
                color=SLATE, style="italic", linespacing=1.2)
        if i < len(steps) - 1:
            ax.annotate("", xy=(centers[i + 1] - 1.35, 2.0),
                        xytext=(cx + 1.35, 2.0),
                        arrowprops=dict(arrowstyle="-|>", color="#94a3b8", lw=2.5))

    ax.set_title("How the caregiver chatbot works", fontsize=18, pad=10)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> int:
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "output", "eval_results.json")
    if not os.path.exists(src):
        print(f"Results file not found: {src}\n"
              f"Run `python -m alz_finder.cli eval --output {src}` first.")
        return 1
    data = load(src)
    per_q = data["per_question"]
    n = data["n_questions"]

    os.makedirs(OUT_DIR, exist_ok=True)
    chart_how_it_works(os.path.join(OUT_DIR, "1_how_it_works.png"))
    chart_summary(per_q, n, os.path.join(OUT_DIR, "2_summary.png"))
    chart_waffle(per_q, n, os.path.join(OUT_DIR, "3_each_question.png"))
    chart_topk_bars(per_q, n, os.path.join(OUT_DIR, "4_how_often.png"))

    print(f"Wrote 4 plain-language charts to {OUT_DIR}/")
    for f in sorted(os.listdir(OUT_DIR)):
        print(f"  {f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
