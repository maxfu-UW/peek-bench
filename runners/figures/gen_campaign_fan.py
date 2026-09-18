#!/usr/bin/env python3
"""Generate the PEEK-Bench "Precision Fan" — the full-Dev-13 leaderboard by UTS MAPE.

Reads  <repo>/results/aggregates_v2.json  (key "groups") and writes

    <repo>/docs/figures/campaign_fan.svg

One radial blade per leaderboard arm, sorted by UTS MAPE ascending (best leftmost)
on a log2 scale: the base ring is 8 % and every ring outward is another halving, so
a longer blade means a lower MAPE.  Whiskers are +-1 between-sweep SD pushed through
the same scale; an end that leaves the axis is drawn uncapped and footnoted.  Arms
worse than the base ring are clamped to a stub with the value folded into the label.
Two grey stubs carry the negative results (no protocol drive), which are not scored.

Sibling of runners/figures/gen_villain_fans.py and shares its visual language:
dark header band, family colours, hatched NAIVE arms, gold for the Claude API arms,
"Claude Code" pivot, team-credit box, legend top-left, footnotes bottom-left.

Stdlib only.  Paths are resolved relative to this file, so it runs from anywhere:

    python3 runners/figures/gen_campaign_fan.py
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
DATA = os.path.join(REPO, "results", "aggregates_v2.json")
OUT_DIR = os.path.join(REPO, "docs", "figures")
OUT = os.path.join(OUT_DIR, "campaign_fan.svg")

VERSION = "PEEK-Bench v2.4b"
UPDATED = "2026-09-17"
SUBTITLE = ("updated {d} · full frontier matrix: Fable 5 + Opus 4.8 + Opus 5 agentic "
            "×3 · gold = Claude API arms").format(d=UPDATED)

# ----------------------------------------------------------------------------
# geometry
# ----------------------------------------------------------------------------
W = 1760
CX = 880
R0 = 190                   # inner (base) ring = blade root = the 8 % ring
RING = 105                 # radial distance between reference rings (one halving)
NRINGS = 5                 # rings above the base ring
RMAX = R0 + NRINGS * RING  # 715 = axis edge
FAN_HALF = 78.0            # dashed rings span +-78 deg from vertical
BLADE_EDGE = 72.7          # centre of the outermost blade slot
BLADE_FRAC = 3.6 / 4.4     # blade width as a fraction of the slot pitch
STUB_R = 202               # negative-result stubs
CLAMP_R = 204              # off-scale (clamped) blades
VALUE_OFFSETS = (24, 40, 54)  # stagger ladder for the in-blade value text
VALUE_INSET = 2            # an in-blade value must clear each blade edge by this much;
                           # white value text that spills past the edge lands on the white
                           # page (or a neighbour's whisker) and loses its outer digits, so
                           # anything that does not fit is folded into the radial label
LABEL_GAP = 16
OPEN_END_PX = 72           # an undefined whisker end is drawn this far past the blade
                           # tip and left uncapped: it must read as "keeps going" without
                           # implying a finite bound (and without shoving the label off-canvas)
TOP_CLEAR = 96             # nothing above this y (header band is 0..78)
LEGEND_BOX = (30, 100, 650, 214)
NOTES_BOX = (1340, 104, 1740, 146)

FAMILIES = {
    "gold": dict(fill="#d9a028", stroke="#9a7217", hatch="hatch-gold", tint="#f0d089"),
    "qwen": dict(fill="#2f78b8", stroke="#1a5182", hatch="hatch-qwen", tint="#aecde9"),
    "gemma": dict(fill="#2f9e63", stroke="#1c6b41", hatch="hatch-gemma", tint="#abd9c0"),
    "rust": dict(fill="#96522e", stroke="#6b3a20", hatch="hatch-rust", tint="#d5baab"),
}
LEGEND_HATCH = "qwen"      # family whose hatch is shown in the legend swatch
STUB_FILL, STUB_STROKE, STUB_TEXT = "#d7dce1", "#8a939c", "#7c8690"
WHISKER = "#233340"
STUBS = ["EXAONE-4.5-33B — no protocol drive", "Fara1.5-9B — no protocol drive"]

METRIC = "UTS_MAPE_pct"
LOG_BASE = 8.0                              # value on the base ring
RING_VALUES = [8, 4, 2, 1, 0.5, 0.25]       # labelled rings, base ring first
BASE_RING_LABEL = "MAPE 8%"


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


def short_name(name):
    """Arm name without the trailing file-count parenthetical, for footnote prose."""
    i = name.rfind(" (")
    if i > 0 and name.endswith(")") and name[i + 2:-1].isdigit():
        return name[:i]
    return name


# ----------------------------------------------------------------------------
# the scale: log2, one ring per halving, base ring = LOG_BASE
# ----------------------------------------------------------------------------
def to_r(v):
    """Radius for a MAPE value (lower MAPE -> larger radius -> longer blade)."""
    if v <= 0:
        return math.inf
    return R0 + RING * math.log2(LOG_BASE / v)


def to_value(r):
    """Inverse of to_r — used to prove a drawn ring sits on its own label."""
    return LOG_BASE / 2.0 ** ((r - R0) / RING)


def ring_radii():
    """(value, radius) for each labelled reference ring.

    The rings are NOT an equally-spaced ladder: each one is drawn at the radius the
    scale assigns to its own value, so a blade tip can be read straight off them.
    The round-trip assertion below is what enforces that.
    """
    out = []
    for v in RING_VALUES:
        r = to_r(v)
        # 1. the radius must decode back to the value printed on the ring
        assert abs(to_value(r) - v) <= 1e-9 * v, \
            "ring %g drawn at r=%.4f decodes to %.6f" % (v, r, to_value(r))
        # 2. and it must sit on the axis
        assert R0 - 0.5 <= r <= RMAX + 0.5, "ring %g maps to r=%.1f outside the axis" % (v, r)
        out.append((v, r))
    # 3. spacing comes from the values, never from the ring index: consecutive rings are
    #    RING * log2(v_prev / v_next) apart, which is a constant only while the labels
    #    happen to halve.  Re-introducing an equally-spaced ladder trips this.
    for (v0, r0), (v1, r1) in zip(out, out[1:]):
        want = RING * math.log2(v0 / v1)
        assert abs((r1 - r0) - want) <= 1e-9 * RING, \
            "rings %g->%g are %.4f px apart, scale says %.4f" % (v0, v1, r1 - r0, want)
    return out


def fmt_value(v):
    return "%.2f" % v


def fmt_ring(v):
    return "%g%%" % v


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
_HB = {  # Helvetica-Bold advance widths (per 1000 em), used only for layout estimates
    " ": 278, ".": 278, ",": 278, "-": 333, "(": 333, ")": 333, "/": 278, ":": 333,
    "±": 584, "·": 278, "—": 1000, "%": 889, "&": 722, "+": 584, "'": 238,
    "x": 556, "×": 584,
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
    return "%.1f" % x


def blade_path(cy, r, th, hw, r_in=R0):
    x0, y0 = pos(cy, r_in, th - hw)
    x1, y1 = pos(cy, r, th - hw)
    x2, y2 = pos(cy, r, th + hw)
    x3, y3 = pos(cy, r_in, th + hw)
    return ("M %s %s L %s %s A %s %s 0 0 1 %s %s L %s %s A %d %d 0 0 0 %s %s Z"
            % (fmt(x0), fmt(y0), fmt(x1), fmt(y1), fmt(r), fmt(r), fmt(x2), fmt(y2),
               fmt(x3), fmt(y3), r_in, r_in, fmt(x0), fmt(y0)))


def blade_width(r, hw):
    """Chord width of a blade slot at radius r (px) — how much text can sit inside."""
    return 2 * r * math.sin(math.radians(hw))


# ----------------------------------------------------------------------------
# layout (radii + angles only; independent of the pivot y)
# ----------------------------------------------------------------------------
def layout(arms):
    arms = sorted(arms, key=lambda a: (a["agg"][METRIC]["mean"],
                                       -a["agg"]["row_f1"]["mean"], a["name"]))
    n_slots = len(arms) + len(STUBS)
    step = 2 * BLADE_EDGE / (n_slots - 1)
    hw = step * BLADE_FRAC / 2
    items = []
    prev_val_r = None          # radius of the last value text actually placed
    for i, a in enumerate(arms):
        th = -BLADE_EDGE + i * step
        agg = a["agg"][METRIC]
        mean, sd = agg["mean"], agg["sd"]
        name = a["name"]
        fam = FAMILIES[family_of(name)]
        it = dict(kind="arm", name=name, th=th, hw=hw, fam=fam, naive=is_naive(name),
                  mean=mean, sd=sd, n_sweeps=a.get("n_sweeps"),
                  min_per_run=a.get("min_per_run"), clamped=False, whisker=None,
                  val_r=None, val_txt=None, fold=False)
        r = to_r(mean)
        if r < R0 - 1e-9:      # worse than the base ring: stub + value folded into the label
            it["clamped"] = True
            it["r"] = CLAMP_R
            it["label"] = "%s · %s%% off-scale (clamped)" % (name, fmt_value(mean))
            it["fold"] = True
        else:
            r = min(r, RMAX)
            it["r"] = r
            wh = None
            # sd is None only for single-sweep arms; a multi-sweep arm with sd == 0.0 is a
            # real measurement and must not look like a single sweep
            if sd is not None and sd > 0:
                ra, rb = to_r(mean - sd), to_r(mean + sd)   # -SD is the OUTER end here
                lo, hi = min(ra, rb), max(ra, rb)
                open_end = hi > RMAX                        # mean - sd <= 0, or past the edge
                wh = dict(lo=max(lo, R0), hi=(r + OPEN_END_PX) if open_end else hi,
                          lo_cap=lo >= R0, hi_cap=not open_end)
            it["whisker"] = wh
            vtxt = fmt_value(mean)
            vw = est_w(vtxt, 11.5)
            chosen = None
            for off in VALUE_OFFSETS:
                rv = r - off
                if rv < R0 + 4:                                   # inside the pivot ring
                    continue
                if vw > blade_width(rv, hw) - 2 * VALUE_INSET:    # must fit inside the blade
                    continue
                if wh and (rv - 3 < wh["hi"] + 3 and rv + 8 > wh["lo"]):
                    continue                                      # would sit on the whisker
                if prev_val_r is not None and abs(rv - prev_val_r) < 14:
                    continue                                      # too close to its neighbour
                chosen = rv
                break
            sd_txt = (" ±%s" % fmt_value(sd)) if sd is not None else ""
            if chosen is None:
                it["fold"] = True
                it["label"] = "%s · %s%s" % (name, vtxt, sd_txt)
            else:
                it["val_r"] = chosen
                it["val_txt"] = vtxt
                it["label"] = "%s%s" % (name, sd_txt)
                prev_val_r = chosen
        # label anchor: past the blade tip or the outer whisker end
        outer = it["r"]
        if it["whisker"]:
            outer = max(outer, it["whisker"]["hi"])
        it["label_r"] = outer + LABEL_GAP
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
    """Lowest pivot y that keeps every label clear of the header, legend and notes."""
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
def footnote_lines(items, max_w=1200):
    """Wrap the reading notes into ' · '-joined lines no wider than one measure."""
    arms = [it for it in items if it["kind"] == "arm"]
    clamps = [it for it in arms if it["clamped"]]
    open_ended = [it for it in arms if it["whisker"] and not it["whisker"]["hi_cap"]]
    notes = ["MAPE on UTS", "whiskers = ±1 between-sweep SD"]
    for it in open_ended:
        notes.append("%s lower whisker uncapped: SD > mean, open-ended on the log scale"
                     % short_name(it["name"]))
    for it in clamps:
        notes.append("%s off-scale at %s%%, blade clamped"
                     % (short_name(it["name"]), fmt_value(it["mean"])))
    notes.append("EXAONE-4.5-33B & Fara1.5-9B: no protocol drive (negative results, not scored)")
    notes.append("min/run is host-specific — wall-clock never pooled across arms")
    notes.append("API arms have no min/run")
    lines, cur = [], ""
    for n in notes:
        cand = n if not cur else "%s · %s" % (cur, n)
        if cur and est_w(cand, 12.5) > max_w:
            lines.append(cur)
            cur = n
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines, clamps, open_ended


def render(items, cy):
    foot, _clamps, _open = footnote_lines(items)
    H = cy + 252 + 20 * (len(foot) - 1) + 18
    o = []
    o.append('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" '
             'font-family="Helvetica, Arial, sans-serif">' % (W, H))
    # hatch patterns, only for the families that actually use one
    used = {LEGEND_HATCH} | {k for k, f in FAMILIES.items()
                             for it in items if it["kind"] == "arm" and it["naive"]
                             and it["fam"] is f}
    o.append("<defs>")
    for key, fam in FAMILIES.items():
        if key not in used:
            continue
        o.append('<pattern id="%s" width="8" height="8" patternUnits="userSpaceOnUse" '
                 'patternTransform="rotate(45)"><rect width="8" height="8" fill="%s"/>'
                 '<rect width="3.4" height="8" fill="%s" fill-opacity="0.75"/></pattern>'
                 % (fam["hatch"], fam["tint"], fam["fill"]))
    o.append("</defs>")
    o.append('<rect width="%d" height="%d" fill="#ffffff"/>' % (W, H))
    # header band
    o.append('<rect x="0" y="0" width="%d" height="78" fill="#0f2a43"/>' % W)
    o.append('<text x="40" y="36" font-size="28" font-weight="bold" fill="#ffffff">'
             '%s — The Precision Fan (MAPE)</text>' % esc(VERSION))
    o.append('<text x="40" y="62" font-size="15.5" fill="#bcd5ea">%s</text>' % esc(SUBTITLE))
    # dashed reference rings, labelled at the right-hand end
    for k, (v, r) in enumerate(ring_radii()):
        x0, y0 = pos(cy, r, -FAN_HALF)
        x1, y1 = pos(cy, r, FAN_HALF)
        o.append('<path d="M %s %s A %.1f %.1f 0 0 1 %s %s" fill="none" stroke="#e3e8ee" '
                 'stroke-width="1.4" stroke-dasharray="5 6"/>'
                 % (fmt(x0), fmt(y0), r, r, fmt(x1), fmt(y1)))
        lab = BASE_RING_LABEL if k == 0 else fmt_ring(v)
        o.append('<text x="%s" y="%s" font-size="12.5" fill="#9aa7b4">%s</text>'
                 % (fmt(x1 + 5), fmt(y1 + 4), esc(lab)))
    # blades, best -> worst, left -> right
    for it in items:
        th, hw = it["th"], it["hw"]
        if it["kind"] == "stub":
            o.append('<path d="%s" fill="%s" fill-opacity="0.9" stroke="%s" stroke-width="1.5"/>'
                     % (blade_path(cy, it["r"], th, hw), STUB_FILL, STUB_STROKE))
            lx, ly = pos(cy, it["label_r"], th)
            o.append('<text x="%s" y="%s" font-size="12" font-weight="bold" fill="%s" '
                     'font-style="italic" text-anchor="start" transform="rotate(%s %s %s)">%s</text>'
                     % (fmt(lx), fmt(ly), STUB_TEXT, fmt(th - 90), fmt(lx), fmt(ly),
                        esc(it["label"])))
            continue
        fam = it["fam"]
        fill = ('fill="url(#%s)"' % fam["hatch"]) if it["naive"] \
            else ('fill="%s" fill-opacity="0.88"' % fam["fill"])
        o.append('<path d="%s" %s stroke="%s" stroke-width="1.5"/>'
                 % (blade_path(cy, it["r"], th, hw), fill, fam["stroke"]))
        # in-blade value text (tangential, reading outward)
        if it["val_r"] is not None:
            vx, vy = pos(cy, it["val_r"], th)
            if it["naive"]:   # hatching would swallow plain white text
                style = 'fill="%s" paint-order="stroke" stroke="#ffffff" stroke-width="3"' \
                    % fam["stroke"]
            else:
                style = 'fill="#ffffff"'
            o.append('<text x="%s" y="%s" font-size="11.5" font-weight="bold" %s '
                     'text-anchor="middle" transform="rotate(%s %s %s)">%s</text>'
                     % (fmt(vx), fmt(vy), style, fmt(th), fmt(vx), fmt(vy), it["val_txt"]))
        # whisker (+-1 SD through the same scale; an undefined end is left uncapped)
        wh = it["whisker"]
        if wh:
            a = math.radians(th)
            tx, ty = math.cos(a), math.sin(a)
            x1, y1 = pos(cy, wh["lo"], th)
            x2, y2 = pos(cy, wh["hi"], th)
            o.append('<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" stroke-width="2.6" '
                     'stroke-linecap="round"/>' % (fmt(x1), fmt(y1), fmt(x2), fmt(y2), WHISKER))
            for (px, py), cap in (((x1, y1), wh["lo_cap"]), ((x2, y2), wh["hi_cap"])):
                if cap:
                    o.append('<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" '
                             'stroke-width="2.6" stroke-linecap="round"/>'
                             % (fmt(px - 9 * tx), fmt(py - 9 * ty), fmt(px + 9 * tx),
                                fmt(py + 9 * ty), WHISKER))
        # radial name label
        lx, ly = pos(cy, it["label_r"], th)
        anchor, rot = ("end", th + 90) if th < 0 else ("start", th - 90)
        o.append('<text x="%s" y="%s" font-size="12" font-weight="bold" fill="%s" '
                 'text-anchor="%s" transform="rotate(%s %s %s)">%s</text>'
                 % (fmt(lx), fmt(ly), fam["stroke"], anchor, fmt(rot), fmt(lx), fmt(ly),
                    esc(it["label"])))
    # pivot
    o.append('<circle cx="%d" cy="%d" r="118" fill="#dcebfa" stroke="#4a86c2" stroke-width="3"/>'
             % (CX, cy))
    o.append('<text x="%d" y="%d" font-size="19" font-weight="bold" fill="#153c60" '
             'text-anchor="middle">Claude Code</text>' % (CX, cy - 26))
    o.append('<text x="%d" y="%d" font-size="13" fill="#2c567e" text-anchor="middle">'
             'fleet orchestration</text>' % (CX, cy - 2))
    o.append('<text x="%d" y="%d" font-size="12" fill="#2c567e" text-anchor="middle">'
             'verify · queue · gate ·</text>' % (CX, cy + 20))
    o.append('<text x="%d" y="%d" font-size="12" fill="#2c567e" text-anchor="middle">'
             'watchdog · score</text>' % (CX, cy + 38))
    # the hand
    o.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#c2711d" stroke-width="4"/>'
             % (CX, cy + 118, CX, cy + 130))
    o.append('<rect x="490" y="%d" width="780" height="94" rx="14" fill="#fff3df" '
             'stroke="#e3a75c" stroke-width="2.5"/>' % (cy + 130))
    o.append('<text x="%d" y="%d" font-size="17.5" font-weight="bold" fill="#8a4a05" '
             'text-anchor="middle">The hand that holds the fan — human direction '
             '&amp; ground truth</text>' % (CX, cy + 162))
    o.append('<text x="%d" y="%d" font-size="15" fill="#5c4326" text-anchor="middle">'
             'Huilong Fu (Research Lead) · Navid Zobeiry (Supervisor) · '
             'Ryan S. Hong (MS Student) — UW MSE</text>' % (CX, cy + 188))
    o.append('<text x="%d" y="%d" font-size="12.5" font-style="italic" fill="#a05b12" '
             'text-anchor="middle">benchmark design · private ground truth · '
             'policies &amp; approvals · review</text>' % (CX, cy + 210))
    # legend (top-left)
    for x, y, fam, txt in [(40, 112, FAMILIES["gold"], "Claude API arms (agentic + v1 era)"),
                           (40, 138, FAMILIES["qwen"], "Qwen family (local)"),
                           (40, 164, FAMILIES["gemma"], "Gemma family (local)"),
                           (40, 190, FAMILIES["rust"], "other local models")]:
        o.append('<rect x="%d" y="%d" width="20" height="13" rx="2" fill="%s" stroke="%s" '
                 'stroke-width="1.2"/>' % (x, y, fam["fill"], fam["stroke"]))
        o.append('<text x="%d" y="%d" font-size="12.5" fill="#233340">%s</text>'
                 % (x + 28, y + 11, esc(txt)))
    lh = FAMILIES[LEGEND_HATCH]
    o.append('<rect x="330" y="112" width="20" height="13" rx="2" fill="url(#%s)" stroke="%s" '
             'stroke-width="1.2"/>' % (lh["hatch"], lh["stroke"]))
    o.append('<text x="358" y="123" font-size="12.5" fill="#233340">hatched = NAIVE-prompt arm</text>')
    o.append('<rect x="330" y="138" width="20" height="13" rx="2" fill="%s" stroke="%s" '
             'stroke-width="1.2"/>' % (STUB_FILL, STUB_STROKE))
    o.append('<text x="358" y="149" font-size="12.5" fill="#233340" font-style="italic">'
             'gray stub = negative result</text>')
    o.append('<line x1="332" y1="170" x2="350" y2="170" stroke="%s" stroke-width="2.6" '
             'stroke-linecap="round"/>' % WHISKER)
    o.append('<line x1="332" y1="165" x2="332" y2="175" stroke="%s" stroke-width="2.6" '
             'stroke-linecap="round"/>' % WHISKER)
    o.append('<line x1="350" y1="165" x2="350" y2="175" stroke="%s" stroke-width="2.6" '
             'stroke-linecap="round"/>' % WHISKER)
    o.append('<text x="358" y="175" font-size="12.5" fill="#233340">'
             '±1 between-sweep SD (multi-sweep arms)</text>')
    # reading notes (top-right)
    o.append('<text x="1720" y="118" font-size="12.5" fill="#77828c" text-anchor="end">'
             'longer blade → lower UTS-MAPE (log scale, halving per ring)</text>')
    o.append('<text x="1720" y="136" font-size="12.5" fill="#77828c" text-anchor="end">'
             'blades sorted best → worst, left → right</text>')
    # footnotes (bottom-left)
    for k, line in enumerate(foot):
        o.append('<text x="40" y="%d" font-size="12.5" fill="#77828c">%s</text>'
                 % (cy + 252 + 20 * k, esc(line)))
    o.append("</svg>")
    return "\n".join(o) + "\n", H


def main():
    with open(DATA, encoding="utf-8") as fh:
        data = json.load(fh)
    groups = data["groups"]
    arms = [dict(name=k, **v) for k, v in groups.items()]
    items = layout(arms)
    cy = int(math.ceil(required_cy(items) / 10.0) * 10)
    svg, H = render(items, cy)
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(svg)

    # every arm name appears exactly once as a blade label
    blades = [it for it in items if it["kind"] == "arm"]
    got = sorted(it["label"].split(" ·")[0].split(" ±")[0] for it in blades)
    assert got == sorted(groups), set(got) ^ set(groups)

    # no in-blade value may spill past its blade edge: white text over the white page (or
    # over a neighbouring arm's whisker) silently loses its first and last digit
    for it in blades:
        if it["val_r"] is None:
            continue
        slack = blade_width(it["val_r"], it["hw"]) - est_w(it["val_txt"], 11.5)
        assert slack >= 2 * VALUE_INSET - 1e-9, \
            "%s value '%s' overflows its blade by %.2f px" % (it["name"], it["val_txt"], -slack)
        # and every arm's value is shown exactly once, in the blade or in the label
        assert not it["fold"], "%s both folded and placed in-blade" % it["name"]
    for it in blades:
        assert (it["val_r"] is not None) != it["fold"], \
            "%s shows its value %s" % (it["name"], "twice" if it["fold"] else "nowhere")

    # ---- audit table -------------------------------------------------------
    print("%s  ·  %s  ·  %s" % (VERSION, "The Precision Fan (MAPE)", UPDATED))
    print("%-24s %-6s %-14s %-8s %-9s %s" % ("arm", "MAPE", "SD", "sweeps", "blade r", "notes"))
    print("-" * 96)
    for i, it in enumerate(blades, 1):
        flags = []
        if it["clamped"]:
            flags.append("clamped off-scale")
        if it["fold"]:
            flags.append("value folded into label")
        if it["naive"]:
            flags.append("NAIVE (hatched)")
        if it["whisker"] and not it["whisker"]["hi_cap"]:
            flags.append("whisker open-ended")
        if it["sd"] is None:
            flags.append("single sweep")
        print("%2d %-24s %-6s %-14s %-8s %-9s %s"
              % (i, it["name"], fmt_value(it["mean"]),
                 fmt_value(it["sd"]) if it["sd"] is not None else "—",
                 it["n_sweeps"], "%.1f" % it["r"], "; ".join(flags)))
    folded = [it["name"] for it in blades if it["fold"]]
    print("-" * 96)
    print("blades: %d arms + %d negative-result stubs = %d slots"
          % (len(blades), len(STUBS), len(blades) + len(STUBS)))
    print("rings:  %s (base ring %g%%, one halving per ring)"
          % ("/".join(fmt_ring(v) for v in RING_VALUES), LOG_BASE))
    print("labels folded (%d): %s" % (len(folded), ", ".join(folded)))
    print("canvas: %dx%d  pivot y=%d" % (W, H, cy))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
