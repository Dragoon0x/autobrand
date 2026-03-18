"""
analysis.py — Plot brand evolution progress.

Usage: uv run analysis.py
"""

import csv
import sys
from pathlib import Path

CSV_PATH = Path("history/evolution.csv")
OUTPUT_PATH = Path("history_preview.png")


def load_scores():
    if not CSV_PATH.exists():
        print("ERROR: history/evolution.csv not found.")
        sys.exit(1)
    rows = []
    with open(CSV_PATH) as f:
        for row in csv.DictReader(f):
            rows.append({"gen": int(row["gen"]), "score": int(row["score"])})
    return rows


def plot(rows):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed. Run: uv add matplotlib")
        text_summary(rows)
        return

    gens = [r["gen"] for r in rows]
    scores = [r["score"] for r in rows]

    window = min(8, len(scores))
    rolling = []
    for i in range(len(scores)):
        s = max(0, i - window + 1)
        rolling.append(sum(scores[s:i+1]) / (i - s + 1))

    best = []
    cb = 0
    for s in scores:
        cb = max(cb, s)
        best.append(cb)

    fig, ax = plt.subplots(1, 1, figsize=(14, 5))
    ax.scatter(gens, scores, s=14, alpha=0.25, color="#8B7355", label="individual", zorder=2)
    ax.plot(gens, rolling, color="#2D2016", linewidth=2.5, label=f"rolling avg ({window})", zorder=3)
    ax.plot(gens, best, color="#BF5630", linewidth=1.5, linestyle="--", label="best so far", zorder=3)

    ax.set_xlabel("generation", fontsize=12, color="#666")
    ax.set_ylabel("brief alignment score", fontsize=12, color="#666")
    ax.set_title("autobrand — overnight brand evolution", fontsize=15, fontweight="bold", color="#1E1915", pad=16)
    ax.legend(loc="lower right", fontsize=10, framealpha=0.9)
    ax.set_ylim(0, 100)
    ax.grid(True, alpha=0.1)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_alpha(0.3)
    ax.spines["bottom"].set_alpha(0.3)
    ax.tick_params(colors="#999")
    fig.patch.set_facecolor("#FAF8F5")
    ax.set_facecolor("#FAF8F5")

    fig.tight_layout()
    fig.savefig(OUTPUT_PATH, dpi=180, bbox_inches="tight")
    print(f"saved → {OUTPUT_PATH}")


def text_summary(rows):
    scores = [r["score"] for r in rows]
    print(f"generations: {len(rows)}")
    print(f"best: {max(scores)}, worst: {min(scores)}, avg: {sum(scores)/len(scores):.1f}")
    bars = "▁▂▃▄▅▆▇█"
    bucket = max(1, len(scores) // 40)
    spark = ""
    for i in range(0, len(scores), bucket):
        chunk = scores[i:i+bucket]
        spark += bars[int(sum(chunk)/len(chunk) / 100 * (len(bars)-1))]
    print(f"trajectory: {spark}")


if __name__ == "__main__":
    rows = load_scores()
    print(f"{len(rows)} generations loaded")
    plot(rows)
