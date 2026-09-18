#!/usr/bin/env python3
"""Villain-only ΔF1 (engineered − naive) bar chart with pooled-SD error bars.

Reads <repo>/results/aggregates_v2.json (villain_pairs) and writes
<repo>/docs/figures/eng_vs_naive_villains_sd.png.

One horizontal bar per model pair that has BOTH sides on the six rogue papers, sorted by Δ
descending so the engineered-prompt advantage (mid-range models) sits above the inversions
(frontier models, plus Ministral from below). Error bar = sqrt(SD_eng^2 + SD_naive^2); omitted
when either side is single-sweep. Style matches the repo's other Plotly-look figures.

    python3 runners/figures/gen_villain_delta.py
"""
import json
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
AGG = os.path.join(REPO, "results", "aggregates_v2.json")
OUT = os.path.join(REPO, "docs", "figures", "eng_vs_naive_villains_sd.png")

BLUE, ORANGE, PANEL, INK, MUTED = "#1D6FA8", "#E3A75C", "#E5ECF6", "#2A3F5F", "#5B6C8B"
LABEL = {
    "gemma4-E4B": "Gemma4-E4B",
    "glm-4.6V-flash": "GLM-4.6V-Flash",
    "qwen3.8-27B": "Qwen3.8-27B",
    "qwen3.6-35B": "Qwen3.6-35B",
    "qwen3.5-9B": "Qwen3.5-9B",
    "ministral-3-8B": "Ministral-3-8B",
    "fable5-agentic": "Fable5 agentic (API)",
    "opus4.8-agentic": "Opus4.8 agentic (API)",
    "opus5-agentic": "Opus5 agentic (API)",
}

plt.rcParams.update({
    "figure.facecolor": "white", "savefig.facecolor": "white", "axes.facecolor": PANEL,
    "axes.edgecolor": "none", "axes.grid": True, "grid.color": "white", "grid.linewidth": 1.2,
    "axes.axisbelow": True, "text.color": INK, "axes.labelcolor": INK,
    "xtick.color": INK, "ytick.color": INK, "font.family": "DejaVu Sans", "font.size": 10,
})

with open(AGG) as fh:
    data = json.load(fh)

rows = []
for key, sides in data["villain_pairs"].items():
    e, n = sides["eng"]["agg"]["row_f1"], sides["naive"]["agg"]["row_f1"]
    sde, sdn = e["sd"], n["sd"]
    rows.append({
        "key": key,
        "d": e["mean"] - n["mean"],
        "err": math.sqrt(sde ** 2 + sdn ** 2) if (sde is not None and sdn is not None) else None,
        "ne": sides["eng"]["n_sweeps"], "nn": sides["naive"]["n_sweeps"],
    })
rows.sort(key=lambda r: r["d"], reverse=True)

fig, ax = plt.subplots(figsize=(10.5, 0.78 * len(rows) + 1.9))
fig.subplots_adjust(left=0.20, right=0.965, top=0.79, bottom=0.145)
for sp in ax.spines.values():
    sp.set_visible(False)
ax.tick_params(length=0)
ax.grid(axis="x"); ax.grid(False, axis="y")

ypos = list(range(len(rows)))[::-1]
for y, r in zip(ypos, rows):
    ax.barh(y, r["d"], height=0.62, color=(BLUE if r["d"] >= 0 else ORANGE),
            zorder=3, edgecolor="white", linewidth=0.6)
    if r["err"] is not None:
        ax.errorbar(r["d"], y, xerr=r["err"], fmt="none", ecolor=INK,
                    elinewidth=1.3, capsize=3.5, capthick=1.3, zorder=4)
    pad = (r["err"] or 0) + 0.016
    x = r["d"] + pad if r["d"] >= 0 else r["d"] - pad
    ax.annotate(f"{r['d']:+.3f}  (n={r['ne']}×{r['nn']})", (x, y), va="center",
                ha="left" if r["d"] >= 0 else "right", fontsize=9.5, color=INK, zorder=5)

ax.set_yticks(ypos[::-1])
ax.set_yticklabels([LABEL.get(r["key"], r["key"]) for r in rows][::-1], fontsize=11)
ax.set_yticks(ypos); ax.set_yticklabels([LABEL.get(r["key"], r["key"]) for r in rows], fontsize=11)
ax.axvline(0, color=INK, linewidth=1.6, zorder=3.5)
lim = max(abs(r["d"]) + (r["err"] or 0) for r in rows) + 0.20
ax.set_xlim(-0.30, lim)
ax.set_xlabel("Δ row F1  (engineered − naive, six rogue papers)", fontsize=11.5, labelpad=8)
ax.annotate("← naive wins", (-0.012, -0.72), ha="right", fontsize=9.5,
            color=ORANGE, fontstyle="italic", annotation_clip=False)
ax.annotate("engineered wins →", (0.012, -0.72), ha="left", fontsize=9.5,
            color=BLUE, fontstyle="italic", annotation_clip=False)

fig.suptitle("Villain-only ΔF1 (engineered − naive): scaffolding helps the middle, not the edges",
             x=0.055, y=0.965, ha="left", fontsize=15, color=INK)
fig.text(0.055, 0.905, "six rogue papers (CF-P11/13/14/18/19/24); eng side pools dedicated villain "
                       "sweeps with villain subsets of full sweeps (same paper mix)",
         fontsize=9.5, color=MUTED)
fig.text(0.055, 0.877, "error bars = √(SD²eng + SD²naive) across sweeps; all nine pairs now carry "
                       "between-sweep SD on both sides", fontsize=9.5, color=MUTED)
fig.text(0.055, 0.034, "Agentic pairs: Claude API, six-villain subset of Dev-13. All other pairs: "
                       "local models. Δ is within-pair, so host differences cancel.",
         fontsize=8.5, color=MUTED)

fig.savefig(OUT, dpi=200)
print("wrote", OUT)
for r in rows:
    err = f"{r['err']:.4f}" if r["err"] is not None else "None"
    print(f"  {r['key']:18s} d={r['d']:+.4f} err={err} n={r['ne']}x{r['nn']}")
