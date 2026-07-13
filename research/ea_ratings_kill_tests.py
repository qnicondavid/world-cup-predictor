#!/usr/bin/env python3
"""research/ea_ratings_kill_tests.py - the two cheap kill tests for the EA Sports FC
ratings idea (EA_RATINGS_PLAN.md, the new-data instance of BRIER_PLAN Candidate 3).

Before building any pipeline, two questions decide whether EA ratings can help:
  Kill test 1 (correlation wall): is the squad EA aggregate just standardized log
    market value in disguise? Kill if correlation >= 0.97 with unstructured residuals.
    Reported for the top-26 overall and for the attack, defence, and goalkeeper
    sub-aggregates, since the wall argument is weakest for the position-specific parts
    the value prior cannot express.
  Kill test 2 (residual predictiveness): do teams EA rates above their market value
    systematically beat the production model's expectation? Pass if the relationship is
    positive and sign-stable across 2018 and 2022.

Data: data/ea_raw/ea_players_legacy.csv (gitignored raw dump), FIFA 18 launch snapshot
(2017-09-18) for WC 2018 and FIFA 23 launch (2022-09-26) for WC 2022, both pre-tournament.
Aggregation mirrors the value proxy: top 26 players by overall per nationality.
Value from data/market_values.csv; held-out predictions from expanded_predictions_l020.csv.
Run: python3 research/ea_ratings_kill_tests.py
"""
import csv
import os
from collections import defaultdict

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EA = os.path.join(REPO, "data", "ea_raw", "ea_players_legacy.csv")
MV = os.path.join(REPO, "data", "market_values.csv")
L020 = os.path.join(REPO, "research", "expanded_predictions_l020.csv")

# fifa_version -> (l020 label, market-value as_of)
EDITION = {"18": ("WC2018", "2018-06-01"), "23": ("WC2022", "2022-11-01")}
SQUAD = 26

# EA nationality_name -> results.csv team name (only the ones that differ)
ALIAS = {
    "Korea Republic": "South Korea", "China PR": "China", "Congo DR": "DR Congo",
    "IR Iran": "Iran", "Republic of Ireland": "Republic of Ireland",
    "Ivory Coast": "Ivory Coast", "Cape Verde Islands": "Cape Verde",
    "Bosnia and Herzegovina": "Bosnia and Herzegovina",
}


def posgroup(player_positions):
    first = (player_positions or "").split(",")[0].strip().upper()
    if first == "GK":
        return "gk"
    if first in ("CB", "LB", "RB", "LWB", "RWB", "LCB", "RCB"):
        return "def"
    if first in ("CDM", "CM", "CAM", "LM", "RM", "LCM", "RCM", "LDM", "RDM", "RCAM", "LCAM"):
        return "mid"
    return "att"  # LW, RW, CF, ST, LF, RF, LS, RS and anything else attacking


def load_ea():
    """team, version -> dict(ovr, atk, deff, gk, age) using top-26 by overall."""
    bucket = defaultdict(list)  # (team, ver) -> [(overall, group, age)]
    with open(EA, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            ver = r.get("fifa_version")
            if ver not in EDITION:
                continue
            try:
                ovr = int(r["overall"])
            except (ValueError, KeyError):
                continue
            team = ALIAS.get(r.get("nationality_name", ""), r.get("nationality_name", ""))
            try:
                age = float(r["age"])
            except (ValueError, KeyError):
                age = None
            bucket[(team, ver)].append((ovr, posgroup(r.get("player_positions", "")), age))
    out = {}
    for (team, ver), players in bucket.items():
        squad = sorted(players, key=lambda x: -x[0])[:SQUAD]
        ovrs = [o for o, _, _ in squad]
        atk = [o for o, g, _ in squad if g in ("att", "mid")]
        deff = [o for o, g, _ in squad if g in ("def", "gk")]
        gk = [o for o, g, _ in squad if g == "gk"]
        ages = [a for _, _, a in squad if a is not None]
        out[(team, ver)] = dict(
            ovr=np.mean(ovrs), atk=np.mean(atk) if atk else np.nan,
            deff=np.mean(deff) if deff else np.nan, gk=max(gk) if gk else np.nan,
            age=np.mean(ages) if ages else np.nan, n=len(squad))
    return out


def load_value():
    v = {}
    for r in csv.DictReader(open(MV, encoding="utf-8")):
        v[(r["team"], r["as_of"])] = float(r["value_eur"])
    return v


def wc_rows():
    return [r for r in csv.DictReader(open(L020, encoding="utf-8"))
            if r["tournament"] in ("WC2018", "WC2022")]


def z(x):
    x = np.asarray(x, float)
    return (x - np.nanmean(x)) / np.nanstd(x)


def corr(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    m = ~(np.isnan(a) | np.isnan(b))
    return float(np.corrcoef(a[m], b[m])[0, 1])


def main():
    ea = load_ea()
    val = load_value()
    rows = wc_rows()
    wcteams = {lbl: set() for lbl in ("WC2018", "WC2022")}
    for r in rows:
        wcteams[r["tournament"]].add(r["home"])
        wcteams[r["tournament"]].add(r["away"])

    # assemble per (team, edition) records for WC participants
    recs = {}
    missing = []
    for ver, (lbl, asof) in EDITION.items():
        for team in sorted(wcteams[lbl]):
            e = ea.get((team, ver))
            mv = val.get((team, asof))
            if e is None or mv is None:
                missing.append(f"{lbl}:{team} (ea={'no' if e is None else 'ok'}, value={'no' if mv is None else 'ok'})")
                continue
            recs[(team, lbl)] = dict(logv=np.log(mv), **e)
    print(f"=== EA ratings kill tests: {len(recs)} of 64 WC 2018/2022 squads matched ===")
    if missing:
        print(f"  unmatched ({len(missing)}): " + "; ".join(missing[:12]))

    keys = list(recs.keys())
    logv = [recs[k]["logv"] for k in keys]
    print("\n=== Kill test 1: correlation wall (EA aggregate vs log market value) ===")
    for name in ("ovr", "atk", "deff", "gk", "age"):
        c = corr([recs[k][name] for k in keys], logv)
        tag = "  <- kill zone" if name == "ovr" and abs(c) >= 0.97 else ""
        print(f"  corr( EA {name:4} , log value ) = {c:+.3f}{tag}")

    # Kill test 2: residual predictiveness of the rating-minus-value differential.
    zovr = dict(zip(keys, z([recs[k]["ovr"] for k in keys])))
    zval = dict(zip(keys, z(logv)))
    diff = {k: zovr[k] - zval[k] for k in keys}  # EA rates above (>0) / below (<0) its value
    data = []
    for r in rows:
        hk, ak = (r["home"], r["tournament"]), (r["away"], r["tournament"])
        if hk not in diff or ak not in diff:
            continue
        ph, pd_, pa = float(r["p_home"]), float(r["p_draw"]), float(r["p_away"])
        res = (1.0 if r["actual"] == "home" else 0.5 if r["actual"] == "draw" else 0.0) - (ph + 0.5 * pd_)
        data.append((r["tournament"], diff[hk] - diff[ak], res))
    print(f"\n=== Kill test 2: residual predictiveness, n={len(data)} matches ===")
    pooled = corr([d[1] for d in data], [d[2] for d in data])
    per = []
    for lbl in ("WC2018", "WC2022"):
        sub = [d for d in data if d[0] == lbl]
        per.append(f"{lbl}:{corr([d[1] for d in sub], [d[2] for d in sub]):+.2f}")
    print(f"  corr(EA-minus-value differential , outcome residual) pooled = {pooled:+.3f} | " + " ".join(per))
    print("  (signal = non-trivial pooled correlation with the SAME sign in both tournaments)")


if __name__ == "__main__":
    main()
