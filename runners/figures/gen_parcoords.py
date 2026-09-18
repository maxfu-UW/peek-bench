#!/usr/bin/env python3
"""Interactive PEEK-Bench leaderboard: one parallel-coordinates line per arm.

Reads <repo>/results/aggregates_v2.json (key "groups" = the 32 full-Dev-13 arms) and writes

    <repo>/docs/interactive/leaderboard.html   plotly parcoords (plotly.js from the CDN)
    <repo>/docs/figures/parcoords_preview.png  static preview, 1400x750 @ scale 2 (kaleido)

Axes, left to right: arm (a labelled index axis, ranked best -> worst by UTS MAPE, so rank 1
sits at the top), row F1, recall, cell accuracy, UTS MAPE % (log10, reversed), false-fill
(reversed).  Every axis therefore reads up = better.  Lines are coloured by log10(MAPE) on a
reversed Viridis, so the brightest line is the best arm; the colorbar is ticked in real MAPE %.

There is deliberately NO min/run (wall-clock) axis: it is host-specific and undefined for the
Claude-API arms, which would silently drop those lines from the plot.

All numbers come from aggregates_v2.json -- nothing is hard-coded but the axis padding rules,
the tick ladder and the labels.  Paths resolve relative to this file, so it runs from anywhere:

    python3 runners/figures/gen_parcoords.py
"""
import json
import math
import os

import plotly.graph_objects as go

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
DATA = os.path.join(REPO, "results", "aggregates_v2.json")
OUT_HTML = os.path.join(REPO, "docs", "interactive", "leaderboard.html")
OUT_PNG = os.path.join(REPO, "docs", "figures", "parcoords_preview.png")

VERSION = "PEEK-Bench v2.4b"
UPDATED = "2026-09-17"

INK, MUTED, DIM = "#2a3f5f", "#5a6570", "#8a95a1"
RANK_METRIC = "UTS_MAPE_pct"          # arms are ranked best-first on this metric
DIV_ID = "peek-parcoords"             # stable, so a re-run is a no-op diff
# tick ladder for the log MAPE axis + colorbar; only the rungs inside the padded axis
# range are drawn, so the ladder survives a data refresh without falling off the axis
MAPE_TICK_LADDER = (0.1, 0.2, 0.25, 0.33, 0.5, 1, 2, 5, 10, 25, 50, 100)
LOG_PAD = 0.03                        # decades of head/tail room on the MAPE axis

# PNG-only chrome: the HTML page carries its own <h1>/<p> header instead
PNG_W, PNG_H, PNG_SCALE = 1400, 750, 2


def is_api(name):
    """Claude-API arms (the gold family in the fan figures) -- no local wall-clock."""
    return "agentic" in name or "Claude API" in name


def mean(arm, metric):
    return arm["agg"][metric]["mean"]


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ----------------------------------------------------------------------------
# axis construction
# ----------------------------------------------------------------------------
def dim_up_is_up(label, vals):
    """Linear 0-1 metric where bigger = better: floor the bottom to a 0.1 gridline."""
    lo = math.floor(min(vals) * 10) / 10
    return dict(label=label, values=vals, range=[lo, 1.0])


def dim_up_is_down(label, vals):
    """Linear 0-1 metric where smaller = better: reversed, top of axis = 0."""
    hi = math.ceil((max(vals) + 0.01) * 50) / 50
    return dict(label=label, values=vals, range=[hi, 0.0])


def log_mape_axis(mapes):
    """log10 values, reversed range and the real-% tick ladder for the MAPE axis."""
    logs = [math.log10(v) for v in mapes]
    lo, hi = min(logs) - LOG_PAD, max(logs) + LOG_PAD
    ticks = [t for t in MAPE_TICK_LADDER if lo <= math.log10(t) <= hi]
    tickvals = [math.log10(t) for t in ticks]
    ticktext = [f"{t:g}" for t in ticks]
    return logs, [hi, lo], tickvals, ticktext


def build_figure(arms, for_png):
    names = [a["name"] for a in arms]
    logs, mape_range, tickvals, ticktext = log_mape_axis([mean(a, "UTS_MAPE_pct") for a in arms])
    idx = list(range(len(arms)))

    dims = [
        dict(label="arm", values=idx, tickvals=idx, ticktext=names,
             range=[len(arms) - 0.5, -0.5]),                       # rank 1 at the top
        dim_up_is_up("row F1", [mean(a, "row_f1") for a in arms]),
        dim_up_is_up("recall", [mean(a, "row_recall") for a in arms]),
        dim_up_is_up("cell acc", [mean(a, "cell_acc") for a in arms]),
        dict(label="UTS MAPE % (log)", values=logs, range=mape_range,
             tickvals=tickvals, ticktext=ticktext),                # reversed: up = lower MAPE
        dim_up_is_down("false-fill", [mean(a, "false_fill_rate") for a in arms]),
    ]

    fig = go.Figure(go.Parcoords(
        dimensions=dims,
        line=dict(color=logs, colorscale="Viridis", reversescale=True,  # brightest = best
                  cmin=min(logs), cmax=max(logs),
                  colorbar=dict(title=dict(text="UTS<br>MAPE %", font=dict(size=11)),
                                tickvals=tickvals, ticktext=ticktext,
                                tickfont=dict(size=10), thickness=13, len=0.85, outlinewidth=0)),
        labelfont=dict(color=INK, size=13),
        tickfont=dict(color=MUTED, size=10),
        rangefont=dict(color="rgba(0,0,0,0)", size=1),   # hide the raw axis end values
    ))
    fig.update_layout(
        height=PNG_H if for_png else 700,
        margin=dict(l=175, r=90, t=103 if for_png else 50, b=30),   # PNG: room for the title
        paper_bgcolor="white",
        font=dict(family="system-ui, -apple-system, 'Segoe UI', sans-serif"),
    )
    if for_png:
        fig.update_layout(title=dict(
            text=f"{VERSION} — leaderboard parallel coordinates ({len(arms)} arms · updated "
                 f"{UPDATED} · up = better on all axes · color = UTS MAPE, brightest = best)",
            x=0.015, xanchor="left", y=0.98, yanchor="top",
            font=dict(size=15, color=INK)))
    return fig


# ----------------------------------------------------------------------------
# page
# ----------------------------------------------------------------------------
def arm_table(arms):
    out = ['<div class="armtable">']
    for i, a in enumerate(arms, 1):
        tag = " <span class='tag'>API</span>" if is_api(a["name"]) else ""
        out.append(f"<div class='cell'><span class='rk'>{i}.</span> "
                   f"<span class='nm'>{esc(a['name'])}</span>{tag} "
                   f"<span class='mp'>MAPE {mean(a, 'UTS_MAPE_pct'):.2f}% · "
                   f"x{a['n_sweeps']}</span></div>")
    out.append("</div>")
    return "\n".join(out)


def page(arms, plot_div, n_no_wallclock):
    title = f"{VERSION} — interactive leaderboard"
    return f"""<html>
<head>
<meta charset="utf-8" />
<title>{esc(title)}</title>
<style>
  body {{ font-family: system-ui, -apple-system, 'Segoe UI', sans-serif;
         margin: 24px auto; max-width: 1400px; color: {INK}; }}
  h1 {{ font-size: 22px; margin: 0 0 6px 0; }}
  p.sub {{ font-size: 13px; color: {MUTED}; margin: 0 0 4px 0; }}
  p.note {{ font-size: 12px; color: {DIM}; margin: 0 0 14px 0; }}
  .armtable {{ display: grid; grid-template-columns: repeat(3, 1fr);
               gap: 3px 22px; margin-top: 14px; font-size: 12px; }}
  .cell {{ white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .rk {{ color: {DIM}; }}
  .nm {{ font-weight: 600; }}
  .mp {{ color: {MUTED}; }}
  .tag {{ background: #eef1f4; color: {MUTED}; border-radius: 3px;
          padding: 0 4px; font-size: 10px; vertical-align: 1px; }}
  @media (max-width: 900px) {{ .armtable {{ grid-template-columns: 1fr 1fr; }} }}
</style>
</head>
<body>
<h1>{esc(title)}</h1>
<p class="sub">{len(arms)} arms · updated {UPDATED} · brush any axis to filter; drag axis titles \
to reorder. Wall-clock is host-specific (see README).</p>
<p class="note">All metric axes oriented so up = better (UTS MAPE on a log scale, false-fill \
reversed). Lines colored by UTS MAPE, brightest = best. min/run axis omitted: host-specific and \
undefined for the {n_no_wallclock} Claude-API arms — see the README table. Arms ranked by UTS \
MAPE below.</p>
{plot_div}
{arm_table(arms)}
</body>
</html>"""


def main():
    with open(DATA, encoding="utf-8") as fh:
        groups = json.load(fh)["groups"]
    arms = [dict(name=k, **v) for k, v in groups.items()]
    arms.sort(key=lambda a: (mean(a, RANK_METRIC), a["name"]))      # best -> worst
    n_no_wallclock = sum(1 for a in arms if a.get("min_per_run") is None)

    os.makedirs(os.path.dirname(OUT_HTML), exist_ok=True)
    os.makedirs(os.path.dirname(OUT_PNG), exist_ok=True)

    div = build_figure(arms, for_png=False).to_html(
        full_html=False, include_plotlyjs="cdn", div_id=DIV_ID,
        default_height="700px", default_width="100%",
        config={"responsive": True, "displaylogo": False})
    html = page(arms, div, n_no_wallclock)
    with open(OUT_HTML, "w", encoding="utf-8") as fh:
        fh.write(html)
    build_figure(arms, for_png=True).write_image(
        OUT_PNG, width=PNG_W, height=PNG_H, scale=PNG_SCALE)

    # ---- audit -------------------------------------------------------------
    missing = [a["name"] for a in arms if f">{esc(a['name'])}<" not in html]
    assert not missing, f"arm names missing from the page: {missing}"
    assert html.count("class='cell'") == len(arms), "arm table row count != arm count"
    assert "cdn.plot.ly" in html, "plotly.js not pulled from the CDN"
    assert VERSION in html and UPDATED in html, "version/date stamp missing"

    print(f"wrote {OUT_HTML} ({os.path.getsize(OUT_HTML)} bytes)")
    print(f"wrote {OUT_PNG} ({os.path.getsize(OUT_PNG)} bytes, "
          f"{PNG_W}x{PNG_H} @ x{PNG_SCALE})")
    print(f"{len(arms)} arms · {n_no_wallclock} without min/run (min-per-run axis omitted)")
    print(f"{'rank':>4}  {'arm':<21} {'MAPE %':>7} {'row F1':>7} {'recall':>7} "
          f"{'cell':>7} {'false-fill':>11} {'sweeps':>7}  src")
    for i, a in enumerate(arms, 1):
        print(f"{i:>4}  {a['name']:<21} {mean(a, 'UTS_MAPE_pct'):>7.2f} "
              f"{mean(a, 'row_f1'):>7.3f} {mean(a, 'row_recall'):>7.3f} "
              f"{mean(a, 'cell_acc'):>7.3f} {mean(a, 'false_fill_rate'):>11.3f} "
              f"{'x' + str(a['n_sweeps']):>7}  {'API' if is_api(a['name']) else 'local'}")


if __name__ == "__main__":
    main()
