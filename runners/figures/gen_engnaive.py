#!/usr/bin/env python3
"""Engineered vs naive prompt on the full Dev-13 corpus — 2x2 paired-bar panel figure.

Reads <repo>/results/aggregates_v2.json (key "full_pairs") and writes
<repo>/docs/figures/eng_vs_naive.png.

One paired blue/orange bar group per model pair that has BOTH prompts on the full 13-paper
corpus, in a fixed reading order: the three local pairs first as a capability ladder (sorted by
engineered row F1 ascending), then the three frontier agentic pairs (Claude API) under a shaded
band that is keyed in the legend.  Four metric panels: row F1, recall, UTS MAPE % and false-fill
(the last two lower = better).  Panel 1 additionally annotates each pair's ΔF1 (engineered −
naive, computed from the UNROUNDED means, bold when negative — the frontier inversion) and
carries a "naive wins →" note over the frontier band.

Error bars are ±1 SD across sweeps, drawn only where a between-sweep SD exists; a single-sweep
arm (sd null) is marked "×1" over its bar in every panel instead.  Style matches the repo's
other Plotly-look figures (see gen_villain_delta.py for the same palette and rcParams).

Every number is read from aggregates_v2.json — nothing about the metrics is hard-coded here;
the only hard-coded values are canvas geometry (pixel positions, font sizes, palette).

Version/date stamp: "PEEK-Bench vX · YYYY-MM-DD" is printed flush right on the first caption
line, so the artefact identifies its own release when it travels without the README section
that embeds it.  VERSION/UPDATED are also written into the PNG metadata and printed with the
audit table.

Paths are resolved relative to this file, so it runs from anywhere:

    python3 runners/figures/gen_engnaive.py
"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
AGG = os.path.join(REPO, "results", "aggregates_v2.json")
OUT = os.path.join(REPO, "docs", "figures", "eng_vs_naive.png")

VERSION = "PEEK-Bench v2.4b"
UPDATED = "2026-09-17"

# ---------------------------------------------------------------------------
# house palette (identical to gen_villain_delta.py) + the frontier-band tint
# ---------------------------------------------------------------------------
BLUE, ORANGE, PANEL, INK, MUTED = "#1D6FA8", "#E3A75C", "#E5ECF6", "#2A3F5F", "#5B6C8B"
BAND = "#C7D5EA"          # frontier agentic band; drawn at BAND_ALPHA over PANEL
BAND_ALPHA = 0.75

LABEL = {
    "gemma4-E4B": "Gemma4-E4B",
    "qwen3.6-35B": "Qwen3.6-35B",
    "qwen3.8-27B": "Qwen3.8-27B",
    "fable5-agentic": "Fable5\nagentic (API)",
    "opus4.8-agentic": "Opus4.8\nagentic (API)",
    "opus5-agentic": "Opus5\nagentic (API)",
}

TITLE = "Engineered vs naive prompt — the advantage inverts at the frontier"
CAPTION = [
    "Same 13-paper Dev-13 corpus for every pair. Local pairs (Gemma4-E4B · Qwen3.6-35B · Qwen3.8-27B):",
    "39 runs/sweep (13 papers ×3 repeats), ×3 sweeps per arm; Qwen3.8-27B naive is a single sweep (marked ×1).",
    "Agentic pairs (Fable5 · Opus4.8 · Opus5): Claude API, 13 runs/sweep, ×3 sweeps. Error bars: ±1 SD across sweeps.",
]

# panels: (metric key, panel title, explicit y-limits or None for autoscale)
PANELS = [
    ("row_f1", "row F1", (0.0, 1.13)),
    ("row_recall", "recall", (0.0, 1.13)),
    ("UTS_MAPE_pct", "UTS MAPE % (lower=better)", None),
    ("false_fill_rate", "false-fill (lower=better)", None),
]

# ---------------------------------------------------------------------------
# canvas geometry, in output pixels at DPI (the published figure is 2920x1839)
# ---------------------------------------------------------------------------
DPI = 200
W_PX, H_PX = 2920, 1839
AX_L, AX_R, AX_T, AX_B = 175.19, 2876.2, 247.4, 1590.6   # outer bounds of the 2x2 block
COL_GAP, ROW_GAP = 200.01, 233.2                          # white space between panels

TITLE_XY = (175.2, 96.5)          # left edge, baseline
LEGEND_Y, LEGEND_H = 123.5, 37.0  # swatch top, swatch height
LEGEND_W = 47.0                   # swatch width
LEGEND_X = (175.2, 452.7, 700.7)  # swatch left edges
LEGEND_PAD = 14.4                 # swatch -> label gap
LEGEND_BASE = 153.5               # label baseline
CAPTION_X, CAPTION_BASE, CAPTION_STEP = 175.2, 1771.0, 28.5
STAMP_X = 2876.2                  # right edge of the panel block; release stamp is flush here

FS_TITLE, FS_LEGEND, FS_PANEL, FS_CAPTION = 15.5, 10.5, 13.0, 8.5
FS_XTICK, FS_YTICK, FS_DELTA, FS_MARK, FS_NOTE = 9.5, 10.0, 9.0, 8.5, 9.0
TITLE_PAD = 10                    # panel title clearance above the panel (points)

BAR_W, BAR_OFF = 0.35, 0.19       # bar width and ±offset from the pair centre
X_PAD = 0.55                      # x-limit padding either side of the first/last pair
BAND_EDGE = 0.45                  # frontier band starts this far left of the first agentic pair
DELTA_PAD, MARK_PAD = 3.90, 1.85  # annotation clearance above a bar (points)
NOTE_Y = 0.047                    # "naive wins →" height, in row-F1 units


def fx(px):
    """Output pixel column -> figure-fraction x."""
    return px / W_PX


def fy(px):
    """Output pixel row (from the top) -> figure-fraction y."""
    return 1.0 - px / H_PX


plt.rcParams.update({
    "figure.facecolor": "white", "savefig.facecolor": "white", "axes.facecolor": PANEL,
    "axes.edgecolor": "none", "axes.grid": False, "axes.axisbelow": True,
    "text.color": INK, "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK,
    "font.family": "DejaVu Sans", "font.size": 10,
})


def load_pairs():
    """Ordered [(key, pair)]: local ladder by engineered row F1 ascending, then agentic."""
    with open(AGG) as fh:
        data = json.load(fh)
    pairs = data["full_pairs"]
    agentic = [k for k in pairs if "agentic" in k]
    local = [k for k in pairs if k not in agentic]
    local.sort(key=lambda k: pairs[k]["eng"]["row_f1"]["mean"])
    order = local + agentic                      # agentic keep their campaign order
    missing = [k for k in order if k not in LABEL]
    assert not missing, f"no display label for {missing}"
    return [(k, pairs[k]) for k in order], len(local)


def sweeps(pair, side, key):
    """Sweep count for one side of a pair (falls back to the metric's own n)."""
    return pair.get(f"{side}_n", pair[side][key]["n"])


def draw_panel(ax, key, title, ylim, pairs, n_local):
    n = len(pairs)
    ax.axvspan(n_local - BAND_EDGE, n - 1 + X_PAD, color=BAND, alpha=BAND_ALPHA, zorder=0.5)
    for i, (_, pair) in enumerate(pairs):
        for side, colour, sign in (("eng", BLUE, -1), ("naive", ORANGE, +1)):
            agg = pair[side][key]
            mean, sd = agg["mean"], agg["sd"]
            x = i + sign * BAR_OFF
            ax.bar(x, mean, width=BAR_W, color=colour, edgecolor="white", linewidth=0.6, zorder=3)
            if sd is not None and sd > 0:
                ax.errorbar(x, mean, yerr=sd, fmt="none", ecolor=INK, elinewidth=1.1,
                            capsize=2.7, capthick=1.1, zorder=4)
            if sweeps(pair, side, key) == 1:
                ax.annotate("×1", (x, mean), textcoords="offset points", xytext=(0, MARK_PAD),
                            ha="center", va="bottom", fontsize=FS_MARK, color=MUTED, zorder=5)
    ax.set_title(title, fontsize=FS_PANEL, color=INK, pad=TITLE_PAD)
    ax.set_xlim(-X_PAD, n - 1 + X_PAD)
    if ylim is not None:
        ax.set_ylim(*ylim)
    ax.set_xticks(range(n))
    ax.set_xticklabels([LABEL[k] for k, _ in pairs])
    ax.tick_params(length=0)
    ax.tick_params(axis="y", labelsize=FS_YTICK)
    ax.tick_params(axis="x", labelsize=FS_XTICK)
    for sp in ax.spines.values():
        sp.set_visible(False)


def annotate_deltas(ax, pairs, key, n_local):
    """ΔF1 over each pair (from unrounded means) + the frontier 'naive wins' note."""
    rows = []
    for i, (pkey, pair) in enumerate(pairs):
        e, nv = pair["eng"][key], pair["naive"][key]
        d = e["mean"] - nv["mean"]
        top = max(m["mean"] + (m["sd"] or 0.0) for m in (e, nv))
        ax.annotate(f"Δ{d:+.3f}", (i, top), textcoords="offset points", xytext=(0, DELTA_PAD),
                    ha="center", va="bottom", fontsize=FS_DELTA, color=INK,
                    fontweight="bold" if d < 0 else "normal", zorder=5)
        rows.append((pkey, e["mean"], nv["mean"], d,
                     sweeps(pair, "eng", key), sweeps(pair, "naive", key)))
    frontier = [i for i in range(len(pairs)) if i >= n_local]
    ax.annotate("naive wins →", (sum(frontier) / len(frontier), NOTE_Y), ha="center",
                va="bottom", fontsize=FS_NOTE, color=INK, fontstyle="italic", zorder=5)
    return rows


def draw_furniture(fig):
    fig.text(fx(TITLE_XY[0]), fy(TITLE_XY[1]), TITLE, fontsize=FS_TITLE, color=INK)
    swatches = [(BLUE, "engineered"), (ORANGE, "naive"),
                (BAND, "frontier agentic pairs (Claude API)")]
    for x, (colour, text) in zip(LEGEND_X, swatches):
        # the band swatch shows the frontier tint at full strength (in the panels it is the
        # same colour at BAND_ALPHA over the panel ground)
        fig.add_artist(Rectangle((fx(x), fy(LEGEND_Y + LEGEND_H)), fx(LEGEND_W),
                                 LEGEND_H / H_PX, transform=fig.transFigure,
                                 facecolor=colour, edgecolor="none"))
        fig.text(fx(x + LEGEND_W + LEGEND_PAD), fy(LEGEND_BASE), text,
                 fontsize=FS_LEGEND, color=INK)
    for i, line in enumerate(CAPTION):
        fig.text(fx(CAPTION_X), fy(CAPTION_BASE + i * CAPTION_STEP), line,
                 fontsize=FS_CAPTION, color=MUTED)
    # release stamp, right-aligned on the first caption line (empty canvas there)
    fig.text(fx(STAMP_X), fy(CAPTION_BASE), f"{VERSION} · {UPDATED}", ha="right",
             fontsize=FS_CAPTION, color=MUTED)


def main():
    pairs, n_local = load_pairs()
    fig, axes = plt.subplots(2, 2, figsize=(W_PX / DPI, H_PX / DPI), dpi=DPI)
    w_ax = ((AX_R - AX_L) - COL_GAP) / 2.0
    h_ax = ((AX_B - AX_T) - ROW_GAP) / 2.0
    fig.subplots_adjust(left=fx(AX_L), right=fx(AX_R), top=fy(AX_T), bottom=fy(AX_B),
                        wspace=COL_GAP / w_ax, hspace=ROW_GAP / h_ax)
    rows = None
    for ax, (key, title, ylim) in zip(axes.ravel(), PANELS):
        draw_panel(ax, key, title, ylim, pairs, n_local)
        if key == "row_f1":
            rows = annotate_deltas(ax, pairs, key, n_local)
    draw_furniture(fig)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    fig.savefig(OUT, dpi=DPI, metadata={
        "Title": f"{VERSION} — engineered vs naive prompt (Dev-13, {UPDATED})",
        "Software": f"{VERSION} · runners/figures/gen_engnaive.py (matplotlib {matplotlib.__version__})",
        "Creation Time": UPDATED,
    })
    print(f"wrote {OUT}  [{VERSION} · {UPDATED}]")
    print(f"  {'pair':16s} {'eng F1':>8s} {'naive F1':>9s} {'ΔF1':>8s}  {'label':>8s}  sweeps")
    for pkey, e, nv, d, ne, nn in rows:
        print(f"  {pkey:16s} {e:8.6f} {nv:9.6f} {d:+8.5f}  {'Δ%+.3f' % d:>8s}  "
              f"eng ×{ne} / naive ×{nn}{'   (single sweep -> ×1)' if 1 in (ne, nn) else ''}")


if __name__ == "__main__":
    main()
