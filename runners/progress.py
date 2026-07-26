#!/usr/bin/env python3
"""Live progress for the CF-P18 re-run and the CF-P11 job queued behind it.

Each is 3 models x 3 repeats = 9 runs. Glyphs encode ROW COUNT against the paper's GT, because
for these two papers row count IS the headline behaviour under test: CF-P18 should yield exactly
2 rows (room-temperature FFF only) and CF-P11 exactly 17 (the 2% SCF sweeps). Before the scope
notes, runs returned 9 and 52-57 rows respectively.
"""
import glob, json, os, re, time
from datetime import datetime

C = os.path.dirname(os.path.abspath(__file__))
MODELS = ["gemma", "mistral", "qwen"]
JOBS = [
    {"cf": "CF-P18", "dir": "results_p18_v2", "log": "p18_v2.log", "gt": 2,
     "prior": {"gemma": 4.5, "mistral": 4.0, "qwen": 8.5}},
    {"cf": "CF-P11", "dir": "results_p11_v2", "log": "p11_v2.log", "gt": 17,
     "prior": {"gemma": 5.0, "mistral": 4.0, "qwen": 13.0}},
]


def started(log):
    try:
        for ln in open(os.path.join(C, log)):
            m = re.search(r"\(revised prompt\) started \w+ (\w+) +(\d+) ([\d:]+)", ln)
            if m:
                t = datetime.strptime(m.group(3), "%H:%M:%S").time()
                d = datetime.combine(datetime.now().date(), t)
                return d if d <= datetime.now() else d.replace(day=max(1, d.day - 1))
    except FileNotFoundError:
        pass
    return None


def render(job):
    got = {}
    for f in glob.glob(os.path.join(C, job["dir"], job["cf"] + "__*.json")):
        m = re.match(job["cf"] + r"__(\w+)-r(\d)\.json", os.path.basename(f))
        if not m:
            continue
        try:
            j = json.load(open(f))
        except Exception:
            continue
        rows = j.get("submitted_full") or j.get("rows") or []
        got[(m.group(1), int(m.group(2)))] = (j.get("wall_clock_min", 0), len(rows))

    n = len(got)
    means = {}
    for mo in MODELS:
        v = [t for (k, _), (t, _) in got.items() if k == mo]
        means[mo] = sum(v) / len(v) if v else job["prior"][mo]
    remaining = sum(means[mo] * (3 - sum(1 for k in got if k[0] == mo)) for mo in MODELS)

    st = started(job["log"])
    elapsed = (datetime.now() - st).total_seconds() / 60 if st else 0
    pct, W = n / 9.0, 30
    bar = "█" * int(W * pct) + "░" * (W - int(W * pct))
    hm = lambda x: "%dh%02dm" % (int(x) // 60, int(x) % 60) if x >= 60 else "%dm" % int(x)
    head = "  %-7s [%s] %d/9 %3.0f%%" % (job["cf"], bar, n, pct * 100)
    if n >= 9:
        print(head + "   COMPLETE")
    elif st:
        eta = time.strftime("%H:%M", time.localtime(time.time() + remaining * 60))
        print(head + "   elapsed %s  left ~%s  eta %s" % (hm(elapsed), hm(remaining), eta))
    else:
        print(head + "   QUEUED")

    for mo in MODELS:
        marks, cnt = [], []
        for r in (1, 2, 3):
            if (mo, r) in got:
                _, nr = got[(mo, r)]
                marks.append("●" if nr == job["gt"] else ("✗" if nr == 0 else "◐"))
                cnt.append("%dr" % nr)
            else:
                marks.append("·")
                cnt.append(" ·")
        done = [t for (k, _), (t, _) in got.items() if k == mo]
        avg = ("%.1fm" % (sum(done) / len(done))) if done else ("~%.0fm" % job["prior"][mo])
        print("     %-8s %s  rows %-11s %6s" % (mo, "".join(marks), " ".join(cnt), avg))
    print("     target %d rows   ● exact  ◐ off-target  ✗ zero  · pending" % job["gt"])


print()
for j in JOBS:
    render(j)
    print()
