#!/usr/bin/env python3
"""Canonical metrics aggregation for the v2 campaign figures and tables.

Reads the private campaign result directories (raw per-run JSONs) and the private
ground truth via score10.score_one — exactly as the live progress board does — and
writes a METRICS-ONLY summary to results/aggregates_v2.json (safe to publish: no
ground-truth values, no paper content, only per-sweep means and between-sweep mean/SD).

  groups         : full Dev-13 leaderboard arms
  full_pairs     : engineered-vs-naive pairs on the full corpus
  villain_pairs  : engineered-vs-naive pairs on the six rogue papers
  villain_groups : EVERY arm restricted to the six rogue papers (villain subsets of
                   complete full sweeps + dedicated villain sweeps), plus villain-only arms

Policies: incomplete sweeps are excluded (partial-sweep SD inflation); villain metrics
come only from the six-paper mix and are never pooled into full-13 aggregates.

Env: PEEKBENCH_CAMPAIGN (dir holding results_*/ and score10.py), PEEKBENCH_GT_DIR (for score10).
"""
import glob, json, os, re, statistics as st, importlib.util, sys
from pathlib import Path
import pandas as pd

if "PEEKBENCH_CAMPAIGN" not in os.environ:
    sys.exit("set PEEKBENCH_CAMPAIGN to the private campaign directory (holds results_*/ and score10.py)")
C = Path(os.environ["PEEKBENCH_CAMPAIGN"])
OUT = Path(__file__).resolve().parent.parent / "results" / "aggregates_v2.json"
_s = importlib.util.spec_from_file_location("s10", C / "score10.py")
S10 = importlib.util.module_from_spec(_s); _s.loader.exec_module(S10)
_GT = S10.load_gt(); _GR = {}
VILLAINS = {"CF-P11", "CF-P13", "CF-P14", "CF-P18", "CF-P19", "CF-P24"}
MET = ["row_f1", "row_recall", "cell_acc", "UTS_MAPE_pct", "false_fill_rate"]
notes = []


def gt_rows(cid):
    if cid not in _GR:
        g = _GT[_GT.cf_paper_id == cid]
        _GR[cid] = [{k: (None if pd.isna(v) else v) for k, v in r.items()} for r in g.to_dict("records")]
    return _GR[cid]


def sweep(dirn, pat, papers=None):
    runs, ms, n = [], [], 0
    for f in sorted(glob.glob(str(C / dirn / "*.json"))):
        m = re.match(pat, os.path.basename(f))
        if not m:
            continue
        cid = m.group(1)
        if papers and cid not in papers:
            continue
        n += 1
        j = json.load(open(f)); rows = j.get("submitted_full") or j.get("rows") or []
        runs.append(j.get("wall_clock_min", 0))
        try:
            ms.append(S10.score_one(rows, gt_rows(cid), "x", cid)[0])
        except Exception as e:
            print(f"  SCORE FAIL {dirn}/{os.path.basename(f)}: {e}", file=sys.stderr)
    return runs, ms, n


def sweep_mean(ms):
    out = {}
    for k in MET:
        v = [x[k] for x in ms if x.get(k) is not None]
        out[k] = sum(v) / len(v) if v else None
    return out


def agg(per):
    out = {}
    for k in MET:
        v = [p[k] for p in per if p[k] is not None]
        out[k] = {"mean": st.mean(v), "sd": (st.stdev(v) if len(v) > 1 else None), "n": len(v)} if v else None
    return out


# name | expected files per sweep | [(dir, filename pattern), ...]
GROUPS = [
 ("Gemma4-E4B eng x3", 39, [("results_dev13_g4e4b", r"(CF-P\d+)__g4e4b-r(\d)\.json"), ("results_dev13_g4e4b_run2", r"(CF-P\d+)__g4e4b-eng2-r(\d)\.json"), ("results_dev13_g4e4b_run3", r"(CF-P\d+)__g4e4b-eng3-r(\d)\.json")]),
 ("Qwen3.8-27B NAIVE", 39, [("results_naive_q3827b_mac", r"(CF-P\d+)__q3827bnv-r(\d)\.json")]),
 ("Qwen3.6-35B NAIVE", 39, [("results_naive_q36_mac_r1", r"(CF-P\d+)__q36nv1-r(\d)\.json"), ("results_naive_q36_mac_r2", r"(CF-P\d+)__q36nv2-r(\d)\.json"), ("results_naive_q36_mac_r3", r"(CF-P\d+)__q36nv3-r(\d)\.json")]),
 ("Gemma4-E4B naive x3", 39, [("results_naive_g4e4b", r"(CF-P\d+)__g4e4bnv-r(\d)\.json"), ("results_naive_g4e4b_run2", r"(CF-P\d+)__g4e4bnv2-r(\d)\.json"), ("results_naive_g4e4b_run3", r"(CF-P\d+)__g4e4bnv3-r(\d)\.json")]),
 ("Gemma4-12B Metal", 39, [("results_dev13_g412b_mac", r"(CF-P\d+)__g412bmac-r(\d)\.json")]),
 ("Gemma4-12B CUDA", 39, [("results_dev13_g412b_asus", r"(CF-P\d+)__g412basus-r(\d)\.json")]),
 ("Gemma4-26B-A4B MoE", 39, [("results_dev13_g4moe", r"(CF-P\d+)__g4moeeng-r(\d)\.json"), ("results_dev13_g4moe_run2", r"(CF-P\d+)__g4moer2-r(\d)\.json"), ("results_dev13_g4moe_run3", r"(CF-P\d+)__g4moer3-r(\d)\.json")]),
 ("Gemma4-31B dense", 39, [("results_dev13_g431b", r"(CF-P\d+)__g431beng-r(\d)\.json")]),
 ("Nemotron-30B-A3B", 39, [("results_dev13_nemo30b_mac", r"(CF-P\d+)__nemo30b-r(\d)\.json")]),
 ("Qwen3VL-30B-A3B", 39, [("results_dev13_q3vl30b_mac", r"(CF-P\d+)__q3vl30b-r(\d)\.json"), ("results_dev13_q3vl30b_mac_run2", r"(CF-P\d+)__q3vl30br2-r(\d)\.json"), ("results_dev13_q3vl30b_mac_run3", r"(CF-P\d+)__q3vl30br3-r(\d)\.json")]),
 ("InternVL3.5-30B(35)", 35, [("results_dev13_ivl35_mac", r"(CF-P\d+)__ivl35-r(\d)\.json")]),
 ("Qwen3.6-35B-A3B", 39, [("results_dev13_q36_mac", r"(CF-P\d+)__q36-r(\d)\.json"), ("results_dev13_q36_mac_run2", r"(CF-P\d+)__q36r2-r(\d)\.json"), ("results_dev13_q36_mac_run3", r"(CF-P\d+)__q36r3-r(\d)\.json")]),
 ("Qwen3VL-32B", 39, [("results_dev13_q3vl32b_mac", r"(CF-P\d+)__q3vl32b-r(\d)\.json"), ("results_dev13_q3vl32b_mac_run2", r"(CF-P\d+)__q3vl32br2-r(\d)\.json"), ("results_dev13_q3vl32b_mac_run3", r"(CF-P\d+)__q3vl32br3-r(\d)\.json")]),
 ("Gemma4-12BQAT CUDA", 39, [("results_dev13_g412bqat_asus", r"(CF-P\d+)__g412bqat-r(\d)\.json"), ("results_dev13_g412bqat_asus_run2", r"(CF-P\d+)__g412bqatr2-r(\d)\.json"), ("results_dev13_g412bqat_asus_run3", r"(CF-P\d+)__g412bqatr3-r(\d)\.json")]),
 ("Qwen3.5-9B", 39, [("results_dev13_qwen35_asus", r"(CF-P\d+)__qwen35-r(\d)\.json"), ("results_dev13_qwen35_asus_run2", r"(CF-P\d+)__qwen35r2-r(\d)\.json"), ("results_dev13_qwen35_asus_run3", r"(CF-P\d+)__qwen35r3-r(\d)\.json")]),
 ("Qwen3VL-8B (38)", 38, [("results_dev13_q3vl8b_asus", r"(CF-P\d+)__q3vl8b-r(\d)\.json"), ("results_dev13_q3vl8b_asus_run2", r"(CF-P\d+)__q3vl8br2-r(\d)\.json"), ("results_dev13_q3vl8b_asus_run3", r"(CF-P\d+)__q3vl8br3-r(\d)\.json")]),
 ("Qwen3.5-4B", 39, [("results_dev13_qwen354b_asus", r"(CF-P\d+)__qwen354b-r(\d)\.json"), ("results_dev13_qwen354b_asus_run2", r"(CF-P\d+)__qwen354br2-r(\d)\.json"), ("results_dev13_qwen354b_asus_run3", r"(CF-P\d+)__qwen354br3-r(\d)\.json")]),
 ("GLM-4.6V-Flash", 39, [("results_dev13_glm46v_asus", r"(CF-P\d+)__glm46v-r(\d)\.json"), ("results_dev13_glm46v_asus_run2", r"(CF-P\d+)__glm46vr2-r(\d)\.json"), ("results_dev13_glm46v_asus_run3", r"(CF-P\d+)__glm46vr3-r(\d)\.json")]),
 ("Qwen3.6-35B Q8_0", 39, [("results_dev13_q36q8_mac", r"(CF-P\d+)__q36q8-r(\d)\.json")]),
 ("Qwen3.8-27B", 39, [("results_dev13_q3827b_mac", r"(CF-P\d+)__q3827b-r(\d)\.json"), ("results_dev13_q3827b_mac_run2", r"(CF-P\d+)__q3827br2-r(\d)\.json"), ("results_dev13_q3827b_mac_run3", r"(CF-P\d+)__q3827br3-r(\d)\.json")]),
 ("Claude API (v1 era)", 39, [("results_claude", r"(CF-P\d+)__claude-r(\d)\.json")]),
 ("Fable5 agentic eng", 13, [("results_c3_fable_eng_r1", r"(CF-P\d+)__c3fableeng1\.json"), ("results_c3_fable_eng_r2", r"(CF-P\d+)__c3fableeng2\.json"), ("results_c3_fable_eng_r3", r"(CF-P\d+)__c3fableeng3\.json")]),
 ("Fable5 agentic naive", 13, [("results_c3_fable_nv_r1", r"(CF-P\d+)__c3fablenv1\.json"), ("results_c3_fable_nv_r2", r"(CF-P\d+)__c3fablenv2\.json"), ("results_c3_fable_nv_r3", r"(CF-P\d+)__c3fablenv3\.json")]),
 ("Opus4.8 agentic eng", 13, [("results_c3_opus_eng_r1", r"(CF-P\d+)__c3opuseng1\.json"), ("results_c3_opus_eng_r2", r"(CF-P\d+)__c3opuseng2\.json"), ("results_c3_opus_eng_r3", r"(CF-P\d+)__c3opuseng3\.json")]),
 ("Opus4.8 agentic nv", 13, [("results_c3_opus_nv_r1", r"(CF-P\d+)__c3opusnv1\.json"), ("results_c3_opus_nv_r2", r"(CF-P\d+)__c3opusnv2\.json"), ("results_c3_opus_nv_r3", r"(CF-P\d+)__c3opusnv3\.json")]),
 ("Opus5 agentic eng", 13, [("results_c3_opus5_eng_r1", r"(CF-P\d+)__c3o5eng1\.json"), ("results_c3_opus5_eng_r2", r"(CF-P\d+)__c3o5eng2\.json"), ("results_c3_opus5_eng_r3", r"(CF-P\d+)__c3o5eng3\.json")]),
 ("Opus5 agentic nv", 13, [("results_c3_opus5_nv_r1", r"(CF-P\d+)__c3o5nv1\.json"), ("results_c3_opus5_nv_r2", r"(CF-P\d+)__c3o5nv2\.json"), ("results_c3_opus5_nv_r3", r"(CF-P\d+)__c3o5nv3\.json")]),
 ("Muse Glimmer 30B", 39, [("results_dev13_museglim_mac", r"(CF-P\d+)__museglim-r(\d)\.json")]),
 ("Agents-A1-35B", 39, [("results_dev13_agentsa1_mac", r"(CF-P\d+)__agentsa1-r(\d)\.json")]),
 ("Qianfan-OCR (32)", 32, [("results_dev13_qianfan_mac", r"(CF-P\d+)__qianfan-r(\d)\.json")]),
 ("MiniCPM-V4.6 (36)", 36, [("results_dev13_mcpm46_mac", r"(CF-P\d+)__mcpm46-r(\d)\.json")]),
 ("Ministral-3-8B", 39, [("results_dev13_mini38b_asus", r"(CF-P\d+)__mini38b-r(\d)\.json"), ("results_dev13_mini38b_asus_run2", r"(CF-P\d+)__mini38br2-r(\d)\.json"), ("results_dev13_mini38b_asus_run3", r"(CF-P\d+)__mini38br3-r(\d)\.json")]),
]

# dedicated villain-only sweeps that extend a leaderboard arm's six-paper sample
V_EXTRA = {
 "Qwen3VL-30B-A3B":    [("results_vill_q3vl30b_run2", r"(CF-P\d+)__q3vl30bv2-r(\d)\.json", 18), ("results_vill_q3vl30b_run3", r"(CF-P\d+)__q3vl30bv3-r(\d)\.json", 18)],
 "Gemma4-26B-A4B MoE": [("results_vill_g4moe_run2", r"(CF-P\d+)__g4moev2-r(\d)\.json", 18), ("results_vill_g4moe_run3", r"(CF-P\d+)__g4moev3-r(\d)\.json", 18)],
 "Qwen3.6-35B-A3B":    [("results_vill_q36_run2", r"(CF-P\d+)__q36v2-r(\d)\.json", 18), ("results_vill_q36_run3", r"(CF-P\d+)__q36v3-r(\d)\.json", 18)],
 "Qwen3VL-32B":        [("results_vill_q3vl32b_run2", r"(CF-P\d+)__q3vl32bv2-r(\d)\.json", 18), ("results_vill_q3vl32b_run3", r"(CF-P\d+)__q3vl32bv3-r(\d)\.json", 18)],
 "Qwen3.5-9B":         [("results_vill_qwen35_v2", r"(CF-P\d+)__qwen35v2-r(\d)\.json", 18), ("results_vill_qwen35_v3", r"(CF-P\d+)__qwen35v3-r(\d)\.json", 18)],
 "Gemma4-31B dense":   [("results_vill_g431b_run2", r"(CF-P\d+)__g431bv2-r(\d)\.json", 18), ("results_vill_g431b_run3", r"(CF-P\d+)__g431bv3-r(\d)\.json", 18)],
 "Qwen3.8-27B":        [("results_vill_q3827b_run2", r"(CF-P\d+)__q3827bv2-r(\d)\.json", 18), ("results_vill_q3827b_run3", r"(CF-P\d+)__q3827bv3-r(\d)\.json", 18)],
 "Qwen3.8-27B NAIVE":  [("results_nvill_q3827b_r2", r"(CF-P\d+)__q3827bnvv2-r(\d)\.json", 18), ("results_nvill_q3827b_r3", r"(CF-P\d+)__q3827bnvv3-r(\d)\.json", 18)],
 "Muse Glimmer 30B":   [("results_vill_museglim_run2", r"(CF-P\d+)__museglimv2-r(\d)\.json", 18), ("results_vill_museglim_run3", r"(CF-P\d+)__museglimv3-r(\d)\.json", 18)],
}
# villain-only arms: no full-13 sweep exists for this model+prompt
V_ONLY = {
 "Ministral-3-8B NAIVE (v-only)": [("results_nvill_mini38bnv_r1", r"(CF-P\d+)__mini38bnv1-r(\d)\.json", 18), ("results_nvill_mini38bnv_r2", r"(CF-P\d+)__mini38bnv2-r(\d)\.json", 18), ("results_nvill_mini38bnv_r3", r"(CF-P\d+)__mini38bnv3-r(\d)\.json", 18)],
 "GLM-4.6V NAIVE (v-only)":       [("results_nvill_glm46vnv_r1", r"(CF-P\d+)__glm46vnv1-r(\d)\.json", 18), ("results_nvill_glm46vnv_r2", r"(CF-P\d+)__glm46vnv2-r(\d)\.json", 18), ("results_nvill_glm46vnv_r3", r"(CF-P\d+)__glm46vnv3-r(\d)\.json", 18)],
 "Gemma3-27B (v-sweeps)":         [("results_vill_g327b_run2", r"(CF-P\d+)__g327bv2-r(\d)\.json", 18), ("results_vill_g327b_run3", r"(CF-P\d+)__g327bv3-r(\d)\.json", 18)],
 "Qwen3.5-9B NAIVE (v-only)":     [("results_nvill_qwen35nv_r1", r"(CF-P\d+)__qwen35nv1-r(\d)\.json", 18), ("results_nvill_qwen35nv_r2", r"(CF-P\d+)__qwen35nv2-r(\d)\.json", 18), ("results_nvill_qwen35nv_r3", r"(CF-P\d+)__qwen35nv3-r(\d)\.json", 18)],
}
# eng-vs-naive pairs (group names)
PAIRS = {
 "gemma4-E4B": ("Gemma4-E4B eng x3", "Gemma4-E4B naive x3"),
 "qwen3.6-35B": ("Qwen3.6-35B-A3B", "Qwen3.6-35B NAIVE"),
 "qwen3.8-27B": ("Qwen3.8-27B", "Qwen3.8-27B NAIVE"),
 "fable5-agentic": ("Fable5 agentic eng", "Fable5 agentic naive"),
 "opus4.8-agentic": ("Opus4.8 agentic eng", "Opus4.8 agentic nv"),
 "opus5-agentic": ("Opus5 agentic eng", "Opus5 agentic nv"),
}
# villain pairs whose naive side is a villain-only arm
V_PAIRS_EXTRA = {
 "qwen3.5-9B": ("Qwen3.5-9B", "Qwen3.5-9B NAIVE (v-only)"),
 "ministral-3-8B": ("Ministral-3-8B", "Ministral-3-8B NAIVE (v-only)"),
 "glm-4.6V-flash": ("GLM-4.6V-Flash", "GLM-4.6V NAIVE (v-only)"),
}


def vsweeps(entries, min_files):
    per, counts = [], []
    for dirn, pat, exp in entries:
        rr, ms, n = sweep(dirn, pat, papers=VILLAINS)
        if n == 0:
            continue
        if n < min_files:
            notes.append(f"VILLAIN: {dirn} skipped ({n} villain files < {min_files})")
            continue
        if n < exp:
            notes.append(f"VILLAIN: {dirn} reduced-n {n}/{exp}")
        per.append(sweep_mean(ms)); counts.append(n)
    return per, counts


out = {"generated_by": "runners/make_aggregates.py", "groups": {}, "full_pairs": {},
       "villain_pairs": {}, "villain_groups": {}, "notes": notes}

for name, expect, dirs in GROUPS:
    per, walls, counts = [], [], []
    for dirn, pat in dirs:
        rr, ms, n = sweep(dirn, pat)
        if n == 0:
            continue
        if n < expect:
            notes.append(f"{name}: {dirn} has {n}/{expect} files (reduced-n or FINAL-set arm)")
        per.append(sweep_mean(ms)); walls += [w for w in rr if w]; counts.append(n)
    if per:
        out["groups"][name] = {"n_sweeps": len(per), "files_per_sweep": counts, "per_sweep": per,
                               "agg": agg(per), "min_per_run": (sum(walls) / len(walls) if walls else None)}

for name, expect, dirs in GROUPS:
    vexp = 6 if expect == 13 else 18
    ent = [(d, p, vexp) for d, p in dirs] + V_EXTRA.get(name, [])
    per, counts = vsweeps(ent, min_files=(4 if vexp == 6 else 12))
    if per:
        out["villain_groups"][name] = {"n_sweeps": len(per), "files_per_sweep": counts, "per_sweep": per,
                                       "agg": agg(per), "villain_only_arm": False}
for name, ent in V_ONLY.items():
    per, counts = vsweeps(ent, min_files=12)
    if per:
        out["villain_groups"][name] = {"n_sweeps": len(per), "files_per_sweep": counts, "per_sweep": per,
                                       "agg": agg(per), "villain_only_arm": True}

for pair, (e, n) in PAIRS.items():
    if e in out["groups"] and n in out["groups"]:
        out["full_pairs"][pair] = {"eng": out["groups"][e]["agg"], "naive": out["groups"][n]["agg"],
                                   "eng_n": out["groups"][e]["n_sweeps"], "naive_n": out["groups"][n]["n_sweeps"]}
for pair, (e, n) in {**PAIRS, **V_PAIRS_EXTRA}.items():
    vg = out["villain_groups"]
    if e in vg and n in vg:
        out["villain_pairs"][pair] = {"eng": {"agg": vg[e]["agg"], "n_sweeps": vg[e]["n_sweeps"]},
                                      "naive": {"agg": vg[n]["agg"], "n_sweeps": vg[n]["n_sweeps"]}}

OUT.parent.mkdir(parents=True, exist_ok=True)
json.dump(out, open(OUT, "w"), indent=1)
print(f"wrote {OUT}")
print(f"groups={len(out['groups'])} villain_groups={len(out['villain_groups'])} "
      f"full_pairs={len(out['full_pairs'])} villain_pairs={len(out['villain_pairs'])}")
for nte in notes:
    print(" NOTE:", nte)
