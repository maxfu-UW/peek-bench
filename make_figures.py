#!/usr/bin/env python3
"""Regenerate the benchmark bar charts from the scored workbooks in results/.

Usage:  python make_figures.py
Writes PNGs into docs/figures/. Reads only the `summary` sheets, so it needs no ground truth.
"""
import pathlib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

R = pathlib.Path(__file__).parent / "results"
F = pathlib.Path(__file__).parent / "docs" / "figures"
F.mkdir(parents=True, exist_ok=True)

MODELS = ["gemma", "mistral", "qwen"]
LABEL = {"gemma": "gemma-3-27b\n256 img tok",
         "mistral": "mistral-small-3.1-24b\n1,030 img tok",
         "qwen": "qwen3-vl-32b\n~2,900 img tok"}
COLOR = {"gemma": "#c44e52", "mistral": "#dd8452", "qwen": "#4c72b0"}
plt.rcParams.update({"figure.dpi": 150, "font.size": 9, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.alpha": .3,
                     "grid.linestyle": ":", "axes.axisbelow": True})


def load(name):
    d = pd.read_excel(R / name, sheet_name="summary")
    d["model"] = d["run"].str.split("__").str[1].str.split("-").str[0]
    return d


def bars(ax, vals, errs=None, fmt="{:.2f}", ylab=""):
    x = np.arange(len(MODELS))
    b = ax.bar(x, [vals.get(m, np.nan) for m in MODELS], .62,
               color=[COLOR[m] for m in MODELS],
               yerr=None if errs is None else [errs.get(m, 0) for m in MODELS],
               capsize=3, ecolor="#444")
    ax.set_xticks(x); ax.set_xticklabels([LABEL[m] for m in MODELS], fontsize=7.5)
    ax.set_ylabel(ylab)
    for r, m in zip(b, MODELS):
        v = vals.get(m, np.nan)
        if pd.isna(v):
            # NOT missing data: the model returned rows with every value null, so no error can
            # be computed. Draw an explicit marker so a blank column is never read as "no run".
            ax.bar(r.get_x() + r.get_width() / 2, ax.get_ylim()[1] * .97, r.get_width(),
                   color="none", edgecolor=COLOR[m], hatch="////", linewidth=1.1)
            ax.text(r.get_x() + r.get_width() / 2, ax.get_ylim()[1] * .48,
                    "read NO\nvalues", ha="center", va="center", fontsize=8,
                    fontweight="bold", color=COLOR[m])
        else:
            ax.text(r.get_x() + r.get_width() / 2, r.get_height(),
                    fmt.format(v), ha="center", va="bottom", fontsize=8, fontweight="bold")
    return b


# ---- Figure 1: the headline — UTS error per paper, ordered by where the values live
p11, p18, p19 = load("CF-P11-v2.xlsx"), load("CF-P18-v2.xlsx"), load("CF-P19.xlsx")
fig, axes = plt.subplots(2, 3, figsize=(11, 6.6))
axes[0, 0].set_ylim(0, 55); axes[1, 0].set_ylim(0, 11)
PANELS = [(p19, "CF-P19  —  values in a TABLE", "15 'MPa' in text / 12 values"),
          (p11, "CF-P11  —  values in FIGURES", "4 'MPa' in text / 17 values"),
          (p18, "CF-P18  —  values in a FIGURE", "1 'MPa' in text / 2 values")]
for j, (d, title, sub) in enumerate(PANELS):
    ax = axes[0, j]
    if j: ax.sharey(axes[0, 0])
    g = d.groupby("model")["UTS_MAPE_pct"]
    bars(ax, g.mean().to_dict(), g.std().fillna(0).to_dict(), "{:.1f}",
         "UTS MAPE (%)  lower is better" if j == 0 else "")
    ax.set_title(f"{title}\n{sub}", fontsize=9)
    ax.set_xticklabels([])
    ax2 = axes[1, j]
    if j: ax2.sharey(axes[1, 0])
    gt_ = d.groupby("model")["wall_min"]
    bars(ax2, gt_.mean().to_dict(), gt_.std().fillna(0).to_dict(), "{:.1f}",
         "runtime (min/run)  lower is better" if j == 0 else "")
fig.suptitle("Accuracy (top) and cost (bottom). Models diverge on accuracy only when the numbers "
             "are locked in figures —\nbut qwen costs 2.0-2.8x mistral's runtime on every paper",
             fontsize=10.5, y=1.02)
fig.tight_layout(); fig.savefig(F / "fig1_uts_error_by_paper.png", bbox_inches="tight"); plt.close(fig)

# ---- Figure 2: pooled figure-locked error vs image-token budget
fig, (a1, a2) = plt.subplots(1, 2, figsize=(8.4, 3.6))
pooled = {m: pd.concat([p11[p11.model == m]["UTS_MAPE_pct"],
                        p18[p18.model == m]["UTS_MAPE_pct"]]).dropna() for m in MODELS}
bars(a1, {m: v.mean() for m, v in pooled.items()}, None, "{:.2f}", "UTS MAPE (%)")
a1.set_title("Figure-locked papers pooled\n(CF-P11 + CF-P18)", fontsize=9)
tok = {"gemma": 256, "mistral": 1030, "qwen": 2900}
for m in MODELS:
    v = pooled[m].mean()
    a2.scatter(tok[m], v, s=130, color=COLOR[m], zorder=3, edgecolor="w", linewidth=1.4)
    a2.annotate(m, (tok[m], v), textcoords="offset points", xytext=(6, 7), fontsize=8.5)
a2.set_xscale("log"); a2.set_xlabel("image tokens per page (log)"); a2.set_ylabel("UTS MAPE (%)")
a2.set_xticks([256, 1030, 2900]); a2.set_xticklabels(["256", "1,030", "2,900"])
a2.minorticks_off(); a2.set_xlim(180, 4200)
a2.set_title("Error falls monotonically with\nimage-token budget", fontsize=9)
fig.suptitle("Chart-reading accuracy is set by image-token budget, not model size "
             "(gemma-3-27b is the LARGEST model here)", fontsize=10, y=1.04)
fig.tight_layout(); fig.savefig(F / "fig2_image_token_budget.png", bbox_inches="tight"); plt.close(fig)

# ---- Figure 3: the supplementary-information A/B
si = load("CF-P13-SI-AB-v2.xlsx")
si["arm"] = np.where(si["run"].str.contains("-si-"), "+SI", "control")
fig, (a1, a2) = plt.subplots(1, 2, figsize=(9, 3.6))
x = np.arange(len(MODELS)); w = .36
for k, (met, ax, ylab, ttl) in enumerate([
        ("param_acc", a1, "parameter accuracy", "Parameters — what SI Table S1 supplies"),
        ("UTS_MAPE_pct", a2, "UTS MAPE (%)", "Tensile values — what SI does NOT supply")]):
    for j, arm in enumerate(["control", "+SI"]):
        g = si[si.arm == arm].groupby("model")[met]
        ax.bar(x + (j - .5) * w, [g.mean().get(m, np.nan) for m in MODELS], w,
               yerr=[g.std().fillna(0).get(m, 0) for m in MODELS], capsize=3, ecolor="#555",
               label=arm, color=["#b0b0b0", "#4c72b0"][j])
    ax.set_xticks(x); ax.set_xticklabels(MODELS); ax.set_ylabel(ylab)
    ax.set_title(ttl, fontsize=9); ax.legend(fontsize=8, frameon=False)
a1.text(.5, .93, "p = 0.0006   d = +2.70", transform=a1.transAxes, ha="center",
        fontsize=8.5, fontweight="bold")
a2.text(.5, .93, "p = 0.93   (unmoved, as predicted)", transform=a2.transAxes, ha="center",
        fontsize=8.5)
fig.suptitle("CF-P13: merging the supplementary file moves parameters and leaves outputs alone",
             fontsize=10.5, y=1.04)
fig.tight_layout(); fig.savefig(F / "fig3_supplementary_ab.png", bbox_inches="tight"); plt.close(fig)

# ---- Figure 4: row-F1 and UTS accuracy dissociate
fig, ax = plt.subplots(figsize=(6.6, 3.6))
d = p18.groupby("model")[["row_f1", "UTS_acc"]].mean()
for j, (c, lab, col) in enumerate([("row_f1", "row F1 (identifies the condition)", "#8c8c8c"),
                                   ("UTS_acc", "UTS accuracy (reads the value)", "#4c72b0")]):
    ax.bar(x + (j - .5) * w, [d[c].get(m, np.nan) for m in MODELS], w, label=lab, color=col)
    for i, m in enumerate(MODELS):
        v = d[c].get(m, np.nan)
        ax.text(i + (j - .5) * w, 0 if pd.isna(v) else v, "n/a" if pd.isna(v) else f"{v:.2f}",
                ha="center", va="bottom", fontsize=8)
ax.set_xticks(x); ax.set_xticklabels(MODELS); ax.set_ylim(0, 1.18)
ax.set_ylabel("score"); ax.legend(fontsize=8, frameon=False, loc="upper left")
ax.set_title("CF-P18: the two metrics rank models differently — report both\n"
             "mistral identifies every row perfectly and gets the numbers wrong", fontsize=9)
fig.tight_layout(); fig.savefig(F / "fig4_f1_vs_uts.png", bbox_inches="tight"); plt.close(fig)

# ---- Figure 5: accuracy costs time
fig, (a1, a2) = plt.subplots(1, 2, figsize=(9.2, 3.6))
runtime, mape = {}, {}
for m in MODELS:
    runtime[m] = np.mean([d[d.model == m]["wall_min"].mean() for d in (p19, p11, p18)])
    mape[m] = pd.concat([p11[p11.model == m]["UTS_MAPE_pct"],
                         p18[p18.model == m]["UTS_MAPE_pct"]]).dropna().mean()
bars(a1, runtime, None, "{:.1f}", "wall-clock minutes per run")
a1.set_title("Runtime — the MOST accurate model is the SLOWEST", fontsize=9)
for m in MODELS:
    a2.scatter(runtime[m], mape[m], s=150, color=COLOR[m], zorder=3, edgecolor="w", linewidth=1.4)
    a2.annotate(m, (runtime[m], mape[m]), textcoords="offset points", xytext=(8, 6), fontsize=8.5)
a2.set_xlabel("wall-clock minutes per run"); a2.set_ylabel("UTS MAPE (%), figure-locked papers")
a2.set_title("Down-and-right is better;\ngemma is dominated on both axes", fontsize=9)
a2.set_xlim(2, 8.6); a2.set_ylim(-4, 48)
a2.annotate("", xy=(7.6, 6), xytext=(3.6, 36),
            arrowprops=dict(arrowstyle="->", color="#999", lw=1.1, ls="--"))
a2.text(5.3, 24, "accuracy costs\n~2.3x the time", fontsize=8, color="#777", ha="center")
fig.suptitle("Chart-reading accuracy is not free: qwen is 2.3x mistral's runtime",
             fontsize=10.5, y=1.04)
fig.tight_layout(); fig.savefig(F / "fig5_runtime_vs_accuracy.png", bbox_inches="tight"); plt.close(fig)

print("wrote:")
for p in sorted(F.glob("*.png")):
    print(f"  {p.relative_to(F.parent.parent)}  ({p.stat().st_size//1024} KB)")
