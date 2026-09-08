#!/usr/bin/env python3
"""Generate the five PEEK-Bench "Villain Fan" figures (six rogue papers only).

Reads  <repo>/results/aggregates_v2.json  (key "villain_groups") and writes

    <repo>/docs/figures/villain_fan_f1.svg      row F1
    <repo>/docs/figures/villain_fan_recall.svg  row recall
    <repo>/docs/figures/villain_fan_cell.svg    cell accuracy   (linear on 0.50-1.00)
    <repo>/docs/figures/villain_fan_mape.svg    UTS MAPE %      (log2, base ring 16 %)
    <repo>/docs/figures/villain_fan_ff.svg      false-fill rate (lower = better)

The visual language is that of docs/figures/campaign_fan.svg (the Precision Fan):
header band, radial blades around the "Claude Code" pivot, dashed reference rings,
+-SD whiskers, hatched NAIVE arms, family colours, two gray negative-result stubs,
legend top-left, team-credit "hand" box, footnotes bottom-left.  Villain-only arms
(no full-13 counterpart) additionally get a dashed blade outline.

Stdlib only.  Paths are resolved relative to this file, so it runs from anywhere:

    python3 runners/figures/gen_villain_fans.py
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
DATA = os.path.join(REPO, "results", "aggregates_v2.json")
OUT_DIR = os.path.join(REPO, "docs", "figures")

UPDATED = "2026-09-08"
VERSION = "PEEK-Bench v2.3"
PAPERS = "CF-P11 · P13 · P14 · P18 · P19 · P24"

# ----------------------------------------------------------------------------
# geometry (identical to campaign_fan.svg)
# ----------------------------------------------------------------------------
W = 1760
CX = 880
R0 = 190                 # inner (base) ring = blade root
RING = 105               # radial distance between reference rings
NRINGS = 5               # rings above the base ring
RMAX = R0 + NRINGS * RING  # 715 = axis edge
FAN_HALF = 78.0          # dashed rings span +-78 deg from vertical
BLADE_EDGE = 72.7        # centre of the outermost blade slot
BLADE_FRAC = 3.6 / 4.4   # blade width as a fraction of the slot pitch
STUB_R = 202             # negative-result stubs
CLAMP_R = 204            # off-scale (clamped) blades
VALUE_OFFSETS = (24, 40, 54)   # stagger ladder for the in-blade value text
LABEL_GAP = 16
TOP_CLEAR = 96           # nothing above this y (header band is 0..78)
LEGEND_BOX = (30, 100, 650, 214)
NOTES_BOX = (1340, 104, 1740, 146)

FAMILIES = {
    "gold": dict(fill="#d9a028", stroke="#9a7217", hatch="hatch-gold", tint="#f0d089"),
    "qwen": dict(fill="#2f78b8", stroke="#1a5182", hatch="hatch-qwen", tint="#aecde9"),
    "gemma": dict(fill="#2f9e63", stroke="#1c6b41", hatch="hatch-gemma", tint="#abd9c0"),
    "rust": dict(fill="#96522e", stroke="#6b3a20", hatch="hatch-rust", tint="#d5baab"),
}
STUB_FILL, STUB_STROKE, STUB_TEXT = "#d7dce1", "#8a939c", "#7c8690"
WHISKER = "#233340"
STUBS = ["EXAONE-4.5-33B — no protocol drive", "Fara1.5-9B — no protocol drive"]


def family_of(name):
    if "agentic" in name or "Claude API" in name:
        return "gold"
    if name.startswith("Qwen"):
        return "qwen"
    if "Gemma" in name:
        return "gemma"
    return "rust"


def is_naive(name):
    return any(k in name for k in ("NAIVE", "naive", "agentic nv"))


# ----------------------------------------------------------------------------
# metric specifications
# ----------------------------------------------------------------------------
LOG_BASE = 16.0


class Metric:
    def __init__(self, key, label, short, fname, dp, rings, ring_fmt, base_label,
                 to_r, sort_key, note, off_scale_txt, extra_foot=None):
        self.key, self.label, self.short, self.fname = key, label, short, fname
        self.dp, self.rings, self.ring_fmt, self.base_label = dp, rings, ring_fmt, base_label
        self.to_r, self.sort_key, self.note = to_r, sort_key, note
        self.off_scale_txt, self.extra_foot = off_scale_txt, extra_foot

    def fmt(self, v):
        return f"{v:.{self.dp}f}"


def _lin(lo, hi, invert=False):
    def f(v):
        t = (v - lo) / (hi - lo)
        if invert:
            t = 1.0 - t
        return R0 + NRINGS * RING * t
    return f


def _log2(v):
    if v <= 0:
        return math.inf
    return R0 + RING * math.log2(LOG_BASE / v)


def _f(a, m):
    return a["agg"][m]["mean"]


METRICS = [
    Metric("row_f1", "row F1", "F1", "villain_fan_f1.svg", 3,
           [0.25, 0.50, 0.75, 0.90, 1.00], lambda v: f"{v:.2f}", "row F1 0.00",
           _lin(0, 1), lambda a: (-_f(a, "row_f1"), -_f(a, "row_recall"), a["name"]),
           "longer blade → higher row F1 (linear scale, 0 → 1; ties broken by recall)",
           lambda v: f"{v:.3f} off-scale (clamped)"),
    Metric("row_recall", "row recall", "recall", "villain_fan_recall.svg", 3,
           [0.25, 0.50, 0.75, 0.90, 1.00], lambda v: f"{v:.2f}", "recall 0.00",
           _lin(0, 1), lambda a: (-_f(a, "row_recall"), -_f(a, "row_f1"), a["name"]),
           "longer blade → higher row recall (linear scale, 0 → 1; ties broken by row F1)",
           lambda v: f"{v:.3f} off-scale (clamped)"),
    Metric("cell_acc", "cell accuracy", "cell acc", "villain_fan_cell.svg", 3,
           [0.6, 0.7, 0.8, 0.9, 1.0], lambda v: f"{v:.2f}", "cell acc 0.50",
           _lin(0.5, 1.0), lambda a: (-_f(a, "cell_acc"), -_f(a, "row_f1"), a["name"]),
           "longer blade → higher cell accuracy (linear scale, 0.50 → 1.00; below 0.50 clamped; ties broken by row F1)",
           lambda v: f"{v:.3f} off-scale (clamped)"),
    Metric("UTS_MAPE_pct", "UTS MAPE %", "MAPE", "villain_fan_mape.svg", 2,
           [8, 4, 2, 1, 0.5], lambda v: (f"{v:g}%"), "MAPE 16%",
           _log2, lambda a: (_f(a, "UTS_MAPE_pct"), -_f(a, "row_f1"), a["name"]),
           "longer blade → lower UTS-MAPE (log scale, halving per ring)",
           lambda v: f"{v:.2f}% off-scale (clamped)",
           "CF-P14 MAPE undefined by design (schema-degenerate) — MAPE averages the other five papers"),
    Metric("false_fill_rate", "false-fill rate", "false-fill", "villain_fan_ff.svg", 3,
           [0.75, 0.50, 0.25, 0.10, 0.00], lambda v: f"{v:.2f}", "false-fill 1.00",
           _lin(0, 1, invert=True), lambda a: (_f(a, "false_fill_rate"), -_f(a, "row_f1"), a["name"]),
           "longer blade → lower false-fill rate (linear scale, 1 → 0; ties broken by row F1)",
           lambda v: f"{v:.3f} off-scale (clamped)"),
]

# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
_HB = {  # Helvetica-Bold advance widths (per 1000 em), used only for layout estimates
    " ": 278, ".": 278, ",": 278, "-": 333, "(": 333, ")": 333, "/": 278, ":": 333,
    "±": 584, "·": 278, "—": 1000, "%": 889, "&": 722, "+": 584, "'": 238, "x": 556,
    "A": 722, "B": 722, "C": 722, "D": 722, "E": 667, "F": 611, "G": 778, "H": 722, "I": 278,
    "J": 556, "K": 722, "L": 611, "M": 833, "N": 722, "O": 778, "P": 667, "Q": 778, "R": 722,
    "S": 667, "T": 611, "U": 722, "V": 667, "W": 944, "X": 667, "Y": 667, "Z": 611,
    "a": 556, "b": 611, "c": 556, "d": 611, "e": 556, "f": 333, "g": 611, "h": 611, "i": 278,
    "j": 278, "k": 556, "l": 278, "m": 889, "n": 611, "o": 611, "p": 611, "q": 611, "r": 389,
    "s": 556, "t": 333, "u": 611, "v": 556, "w": 778, "y": 556, "z": 500,
}


def est_w(s, size):
    return sum(_HB.get(c, 556 if c.isdigit() else 640) for c in s) * size / 1000.0


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def pos(cy, r, th):
    """Point at radius r, angle th (deg from vertical; negative = left)."""
    a = math.radians(th)
    return CX + r * math.sin(a), cy - r * math.cos(a)


def fmt(x):
    return f"{x:.1f}"


def blade_path(cy, r, th, hw, r_in=R0):
    x0, y0 = pos(cy, r_in, th - hw)
    x1, y1 = pos(cy, r, th - hw)
    x2, y2 = pos(cy, r, th + hw)
    x3, y3 = pos(cy, r_in, th + hw)
    return (f"M {fmt(x0)} {fmt(y0)} L {fmt(x1)} {fmt(y1)} A {fmt(r)} {fmt(r)} 0 0 1 {fmt(x2)} {fmt(y2)} "
            f"L {fmt(x3)} {fmt(y3)} A {r_in} {r_in} 0 0 0 {fmt(x0)} {fmt(y0)} Z")


def blade_width(r, hw):
    return 2 * r * math.sin(math.radians(hw))


# ----------------------------------------------------------------------------
# per-metric layout (independent of the pivot y; radii + angles only)
# ----------------------------------------------------------------------------
def layout(metric, arms):
    arms = sorted(arms, key=metric.sort_key)
    n_slots = len(arms) + len(STUBS)
    step = 2 * BLADE_EDGE / (n_slots - 1)
    hw = step * BLADE_FRAC / 2
    items = []
    prev_val_r = None
    run_prev_mean = None
    run_idx = 0
    for i, a in enumerate(arms):
        th = -BLADE_EDGE + i * step
        agg = a["agg"][metric.key]
        mean, sd = agg["mean"], agg["sd"]
        name = a["name"]
        fam = FAMILIES[family_of(name)]
        it = dict(kind="arm", name=name, th=th, hw=hw, fam=fam, naive=is_naive(name),
                  vonly=bool(a.get("villain_only_arm")), mean=mean, sd=sd, clamped=False,
                  origin=False, whisker=None, val_r=None, val_halo=False, fold=False)
        r = metric.to_r(mean)
        if r < R0 - 1e-9:  # off scale (worse than the base ring): stub + folded value
            it["clamped"] = True
            it["r"] = CLAMP_R
            it["label"] = f"{name} · {metric.off_scale_txt(mean)}"
            it["fold"] = True
            prev_val_r = None
        elif r < R0 + 2:  # sits on the axis origin: zero-length blade drawn as a stub
            it["origin"] = True
            it["r"] = CLAMP_R
            it["label"] = f"{name} · {metric.fmt(mean)} (at axis origin)"
            it["fold"] = True
            prev_val_r = None
        else:
            r = min(r, RMAX)
            it["r"] = r
            wh = None
            if sd is not None and sd > 0:
                ra, rb = metric.to_r(mean - sd), metric.to_r(mean + sd)
                lo, hi = min(ra, rb), max(ra, rb)
                wh = dict(lo=max(lo, R0), hi=min(hi, RMAX), lo_cap=lo >= R0, hi_cap=hi <= RMAX)
            it["whisker"] = wh
            it["sd"] = sd
            vtxt = metric.fmt(mean)
            vw = est_w(vtxt, 11.5)
            chosen = None
            for off in VALUE_OFFSETS:
                rv = r - off
                if rv < R0 + 4:
                    continue
                if vw > blade_width(rv, hw) + 8:  # would spill > 4 px past each blade edge
                    continue
                if wh and (rv - 3 < wh["hi"] + 3 and rv + 12 > wh["lo"] - 3):
                    continue
                if prev_val_r is not None and abs(rv - prev_val_r) < 14:
                    continue
                chosen = rv
                break
            # sd is None only for single-sweep arms; a multi-sweep arm with sd == 0.0 is a
            # real measurement and must not look like a single sweep
            sd_txt = f" ±{metric.fmt(sd)}" if sd is not None else ""
            if chosen is None:
                it["fold"] = True
                it["label"] = f"{name} · {vtxt}{sd_txt}"
                prev_val_r = None
            else:
                it["val_r"] = chosen
                it["val_txt"] = vtxt
                it["val_halo"] = it["naive"] or (vw + 2 > blade_width(chosen, hw))
                it["label"] = f"{name}{sd_txt}"
                prev_val_r = chosen
        # label anchor: past the blade tip or the outer whisker end
        outer = it["r"]
        if it["whisker"]:
            outer = max(outer, it["whisker"]["hi"])
        it["label_r"] = outer + LABEL_GAP
        # stagger label anchors inside runs of identical (displayed) means
        key = metric.fmt(mean)
        if key == run_prev_mean:
            run_idx += 1
        else:
            run_idx = 0
        run_prev_mean = key
        it["label_r"] += 12 if (run_idx % 2 == 1) else 0
        it["label_w"] = est_w(it["label"], 12)
        items.append(it)
    for j, s in enumerate(STUBS):
        th = -BLADE_EDGE + (len(arms) + j) * step
        items.append(dict(kind="stub", name=s, th=th, hw=hw, r=STUB_R, label=s,
                          label_r=STUB_R + LABEL_GAP, label_w=est_w(s, 12)))
    return items


def label_points(cy, it):
    """Sample points along the label's radial extent (for clearance checks)."""
    pts = []
    r = it["label_r"]
    end = r + it["label_w"]
    while r <= end:
        pts.append(pos(cy, r, it["th"]))
        r += 8
    pts.append(pos(cy, end, it["th"]))
    return pts


def _in_box(p, b):
    return b[0] <= p[0] <= b[2] and b[1] <= p[1] <= b[3]


def required_cy(items):
    cy = 900
    while True:
        ok = True
        for it in items:
            for p in label_points(cy, it):
                if p[1] - 10 < TOP_CLEAR or _in_box(p, LEGEND_BOX) or _in_box(p, NOTES_BOX):
                    ok = False
                    break
            if not ok:
                break
        if ok:
            return cy
        cy += 5


# ----------------------------------------------------------------------------
# rendering
# ----------------------------------------------------------------------------
def footnote_lines(metric, items, max_w=1650):
    clamps = [it for it in items if it["kind"] == "arm" and it["clamped"]]
    origins = [it for it in items if it["kind"] == "arm" and it["origin"]]
    uncapped = [it for it in items if it["kind"] == "arm" and it["whisker"]
                and not (it["whisker"]["lo_cap"] and it["whisker"]["hi_cap"])]
    pct = "%" if metric.key == "UTS_MAPE_pct" else ""
    notes = [("villain metrics = six-paper subsets of complete full sweeps pooled with dedicated villain-only "
              "sweeps (same paper mix); never pooled into the full-13 leaderboard")]
    if metric.extra_foot:
        notes.append(metric.extra_foot)
    notes.append("(v-only) arms exist only as villain sweeps (no full-13 counterpart)")
    notes.append(f"{metric.label} on the six rogue papers · whiskers = ±1 between-sweep SD (multi-sweep arms)")
    open_ended = [it for it in uncapped if metric.key == "UTS_MAPE_pct"
                  and it.get("sd") is not None and it["sd"] >= it["mean"]]
    edge_clamped = [it for it in uncapped if it not in open_ended]
    for it in open_ended:
        notes.append(f"{it['name']} lower whisker uncapped: SD > mean, open-ended on the log scale")
    if edge_clamped:
        notes.append("other uncapped whisker ends = ±SD reaches past the axis edge, clamped")
    for it in clamps:
        notes.append(f"{it['name']} off-scale at {metric.fmt(it['mean'])}{pct}, blade clamped")
    for it in origins:
        notes.append(f"{it['name']} sits at the axis origin ({metric.label} {metric.fmt(it['mean'])}{pct}): "
                     f"zero-length blade drawn as a stub")
    notes.append("gray stubs = negative results, not scored (EXAONE-4.5-33B & Fara1.5-9B: no protocol drive)")
    lines, cur = [], ""
    for n in notes:
        cand = n if not cur else f"{cur} · {n}"
        if cur and est_w(cand, 12.5) > max_w:
            lines.append(cur)
            cur = n
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines, clamps, origins, uncapped


def render(metric, items, cy, n_arms, report, n_foot_lines):
    foot, clamps, origins, uncapped = footnote_lines(metric, items)
    H = cy + 250 + 20 * (n_foot_lines - 1) + 18
    o = []
    o.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="Helvetica, Arial, sans-serif">')
    o.append("<defs>")
    for fam in FAMILIES.values():
        o.append(f'<pattern id="{fam["hatch"]}" width="8" height="8" patternUnits="userSpaceOnUse" '
                 f'patternTransform="rotate(45)"><rect width="8" height="8" fill="{fam["tint"]}"/>'
                 f'<rect width="3.4" height="8" fill="{fam["fill"]}" fill-opacity="0.75"/></pattern>')
    o.append("</defs>")
    o.append(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')
    # header band
    o.append(f'<rect x="0" y="0" width="{W}" height="78" fill="#0f2a43"/>')
    o.append(f'<text x="40" y="36" font-size="28" font-weight="bold" fill="#ffffff">'
             f'{esc(VERSION)} — The Villain Fan: {esc(metric.label)} (six rogue papers)</text>')
    o.append(f'<text x="40" y="62" font-size="15.5" fill="#bcd5ea">{esc(PAPERS)} — the papers that carry the '
             f'benchmark\'s discrimination · {n_arms} arms · updated {UPDATED}</text>')
    # dashed reference rings (base ring + NRINGS rings), labelled at the right-hand end
    ring_vals = [None] + list(metric.rings)
    for k, v in enumerate(ring_vals):
        # every labelled ring is drawn at the radius the metric's own scale assigns to its
        # value, so blade tips can be read against the rings on every fan
        r = R0 if v is None else metric.to_r(v)
        assert R0 - 0.5 <= r <= RMAX + 0.5, f"{metric.key}: ring {v} maps to r={r:.1f} outside the axis"
        x0, y0 = pos(cy, r, -FAN_HALF)
        x1, y1 = pos(cy, r, FAN_HALF)
        o.append(f'<path d="M {fmt(x0)} {fmt(y0)} A {r:.1f} {r:.1f} 0 0 1 {fmt(x1)} {fmt(y1)}" fill="none" '
                 f'stroke="#e3e8ee" stroke-width="1.4" stroke-dasharray="5 6"/>')
        lab = metric.base_label if v is None else metric.ring_fmt(v)
        o.append(f'<text x="{fmt(x1 + 5)}" y="{fmt(y1 + 4)}" font-size="12.5" fill="#9aa7b4">{esc(lab)}</text>')
    # blades, best -> worst, left -> right
    for it in items:
        th, hw = it["th"], it["hw"]
        if it["kind"] == "stub":
            o.append(f'<path d="{blade_path(cy, it["r"], th, hw)}" fill="{STUB_FILL}" fill-opacity="0.9" '
                     f'stroke="{STUB_STROKE}" stroke-width="1.5"/>')
            lx, ly = pos(cy, it["label_r"], th)
            o.append(f'<text x="{fmt(lx)}" y="{fmt(ly)}" font-size="12" font-weight="bold" fill="{STUB_TEXT}" '
                     f'font-style="italic" text-anchor="start" transform="rotate({fmt(th - 90)} {fmt(lx)} {fmt(ly)})">'
                     f'{esc(it["label"])}</text>')
            continue
        fam = it["fam"]
        fill = f'fill="url(#{fam["hatch"]})"' if it["naive"] else f'fill="{fam["fill"]}" fill-opacity="0.88"'
        dash = ' stroke-dasharray="6 3.5"' if it["vonly"] else ""
        o.append(f'<path d="{blade_path(cy, it["r"], th, hw)}" {fill} stroke="{fam["stroke"]}" '
                 f'stroke-width="1.5"{dash}/>')
        # in-blade value text (tangential, reading outward)
        if it["val_r"] is not None:
            vx, vy = pos(cy, it["val_r"], th)
            if it["val_halo"]:
                style = (f'fill="{fam["stroke"]}" paint-order="stroke" stroke="#ffffff" stroke-width="3"')
            else:
                style = 'fill="#ffffff"'
            o.append(f'<text x="{fmt(vx)}" y="{fmt(vy)}" font-size="11.5" font-weight="bold" {style} '
                     f'text-anchor="middle" transform="rotate({fmt(th)} {fmt(vx)} {fmt(vy)})">{it["val_txt"]}</text>')
        # whisker (+-1 SD through the same scale; clamped ends are uncapped)
        wh = it["whisker"]
        if wh:
            a = math.radians(th)
            tx, ty = math.cos(a), math.sin(a)
            x1, y1 = pos(cy, wh["lo"], th)
            x2, y2 = pos(cy, wh["hi"], th)
            o.append(f'<line x1="{fmt(x1)}" y1="{fmt(y1)}" x2="{fmt(x2)}" y2="{fmt(y2)}" stroke="{WHISKER}" '
                     f'stroke-width="2.6" stroke-linecap="round"/>')
            for (px, py), cap in (((x1, y1), wh["lo_cap"]), ((x2, y2), wh["hi_cap"])):
                if cap:
                    o.append(f'<line x1="{fmt(px - 9 * tx)}" y1="{fmt(py - 9 * ty)}" x2="{fmt(px + 9 * tx)}" '
                             f'y2="{fmt(py + 9 * ty)}" stroke="{WHISKER}" stroke-width="2.6" stroke-linecap="round"/>')
        # radial name label
        lx, ly = pos(cy, it["label_r"], th)
        if th < 0:
            anchor, rot = "end", th + 90
        else:
            anchor, rot = "start", th - 90
        o.append(f'<text x="{fmt(lx)}" y="{fmt(ly)}" font-size="12" font-weight="bold" fill="{fam["stroke"]}" '
                 f'text-anchor="{anchor}" transform="rotate({fmt(rot)} {fmt(lx)} {fmt(ly)})">{esc(it["label"])}</text>')
    # pivot
    o.append(f'<circle cx="{CX}" cy="{cy}" r="118" fill="#dcebfa" stroke="#4a86c2" stroke-width="3"/>')
    o.append(f'<text x="{CX}" y="{cy - 26}" font-size="19" font-weight="bold" fill="#153c60" text-anchor="middle">Claude Code</text>')
    o.append(f'<text x="{CX}" y="{cy - 2}" font-size="13" fill="#2c567e" text-anchor="middle">fleet orchestration</text>')
    o.append(f'<text x="{CX}" y="{cy + 20}" font-size="12" fill="#2c567e" text-anchor="middle">verify · queue · gate ·</text>')
    o.append(f'<text x="{CX}" y="{cy + 38}" font-size="12" fill="#2c567e" text-anchor="middle">watchdog · score</text>')
    # the hand
    o.append(f'<line x1="{CX}" y1="{cy + 118}" x2="{CX}" y2="{cy + 130}" stroke="#c2711d" stroke-width="4"/>')
    o.append(f'<rect x="490" y="{cy + 130}" width="780" height="94" rx="14" fill="#fff3df" stroke="#e3a75c" stroke-width="2.5"/>')
    o.append(f'<text x="{CX}" y="{cy + 162}" font-size="17.5" font-weight="bold" fill="#8a4a05" text-anchor="middle">'
             f'The hand that holds the fan — human direction &amp; ground truth</text>')
    o.append(f'<text x="{CX}" y="{cy + 188}" font-size="15" fill="#5c4326" text-anchor="middle">'
             f'Huilong Fu (Research Lead) · Navid Zobeiry (Supervisor) · Ryan S. Hong (MS Student) — UW MSE</text>')
    o.append(f'<text x="{CX}" y="{cy + 210}" font-size="12.5" font-style="italic" fill="#a05b12" text-anchor="middle">'
             f'benchmark design · private ground truth · policies &amp; approvals · review</text>')
    # legend (top-left)
    leg = [(40, 112, FAMILIES["gold"], "Claude API arms (agentic + v1 era)"),
           (40, 138, FAMILIES["qwen"], "Qwen family (local)"),
           (40, 164, FAMILIES["gemma"], "Gemma family (local)"),
           (40, 190, FAMILIES["rust"], "other local models")]
    for x, y, fam, txt in leg:
        o.append(f'<rect x="{x}" y="{y}" width="20" height="13" rx="2" fill="{fam["fill"]}" stroke="{fam["stroke"]}" stroke-width="1.2"/>')
        o.append(f'<text x="{x + 28}" y="{y + 11}" font-size="12.5" fill="#233340">{esc(txt)}</text>')
    o.append('<rect x="330" y="112" width="20" height="13" rx="2" fill="url(#hatch-qwen)" stroke="#1a5182" stroke-width="1.2"/>')
    o.append('<text x="358" y="123" font-size="12.5" fill="#233340">hatched = NAIVE-prompt arm</text>')
    o.append(f'<rect x="330" y="138" width="20" height="13" rx="2" fill="{STUB_FILL}" stroke="{STUB_STROKE}" stroke-width="1.2"/>')
    o.append('<text x="358" y="149" font-size="12.5" fill="#233340" font-style="italic">gray stub = negative result</text>')
    o.append(f'<line x1="332" y1="170" x2="350" y2="170" stroke="{WHISKER}" stroke-width="2.6" stroke-linecap="round"/>')
    o.append(f'<line x1="332" y1="165" x2="332" y2="175" stroke="{WHISKER}" stroke-width="2.6" stroke-linecap="round"/>')
    o.append(f'<line x1="350" y1="165" x2="350" y2="175" stroke="{WHISKER}" stroke-width="2.6" stroke-linecap="round"/>')
    o.append('<text x="358" y="175" font-size="12.5" fill="#233340">±1 between-sweep SD (multi-sweep arms)</text>')
    o.append('<rect x="330" y="190" width="20" height="13" rx="2" fill="url(#hatch-rust)" stroke="#6b3a20" stroke-width="1.2" stroke-dasharray="3 2"/>')
    o.append('<text x="358" y="201" font-size="12.5" fill="#233340">dashed outline = villain-only arm (v-only)</text>')
    # reading notes (top-right)
    o.append(f'<text x="1720" y="118" font-size="12.5" fill="#77828c" text-anchor="end">{esc(metric.note)}</text>')
    o.append('<text x="1720" y="136" font-size="12.5" fill="#77828c" text-anchor="end">blades sorted best → worst, left → right</text>')
    # footnotes (bottom-left)
    for k, line in enumerate(foot):
        o.append(f'<text x="40" y="{cy + 250 + 20 * k}" font-size="12.5" fill="#77828c">{esc(line)}</text>')
    o.append("</svg>")
    # report
    arms = [it for it in items if it["kind"] == "arm"]
    report[metric.fname] = dict(
        best=f"{arms[0]['name']} ({metric.fmt(arms[0]['mean'])})",
        worst=f"{arms[-1]['name']} ({metric.fmt(arms[-1]['mean'])})",
        value_folded_into_label=[it["name"] for it in arms if it["fold"] and not it["clamped"] and not it["origin"]],
        clamped_off_scale=[f"{it['name']} @ {metric.fmt(it['mean'])}" for it in clamps],
        axis_origin_stub=[f"{it['name']} @ {metric.fmt(it['mean'])}" for it in origins],
        whisker_clamped_at_axis_edge=[it["name"] for it in uncapped],
        canvas=f"{W}x{H}",
    )
    return "\n".join(o) + "\n"


def main():
    with open(DATA, encoding="utf-8") as fh:
        data = json.load(fh)
    vg = data["villain_groups"]
    arms = [dict(name=k, **v) for k, v in vg.items()]
    os.makedirs(OUT_DIR, exist_ok=True)
    layouts = [(m, layout(m, arms)) for m in METRICS]
    # one pivot height for the whole series: the tallest requirement wins
    cy = max(required_cy(items) for _, items in layouts)
    cy = int(math.ceil(cy / 10.0) * 10)
    n_foot = max(len(footnote_lines(m, items)[0]) for m, items in layouts)
    report = {}
    for m, items in layouts:
        svg = render(m, items, cy, len(arms), report, n_foot)
        path = os.path.join(OUT_DIR, m.fname)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(svg)
        # every arm name exactly once as a label
        labels = [it["label"] for it in items if it["kind"] == "arm"]
        names = sorted(vg)
        got = sorted(l.split(" ·")[0].split(" ±")[0] for l in labels)
        assert got == names, (m.fname, set(names) ^ set(got))
        report[m.fname]["bytes"] = os.path.getsize(path)
        report[m.fname]["arms_labelled_once"] = True
    print(json.dumps(dict(pivot_y=cy, figures=report), indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
