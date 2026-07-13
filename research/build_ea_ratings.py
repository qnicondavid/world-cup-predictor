#!/usr/bin/env python3
"""research/build_ea_ratings.py - build data/ea_ratings.csv (the committed per-team EA
Sports FC squad-rating aggregate) from the raw player dump.

WHAT IT READS (raw, kept out of the repo, data/ea_raw/ is gitignored):
    data/ea_raw/ea_players_legacy.csv   (stefanoleone992 FIFA 15-23, one row per player
                                         per edition; columns fifa_version, fifa_update_date,
                                         nationality_name, overall, player_positions, age,
                                         and the detailed sub-attributes used below)
    Extract it from the Kaggle "fifa-23-complete-player-dataset" archive:
        unzip -p archive.zip "male_players (legacy).csv" > data/ea_raw/ea_players_legacy.csv

WHAT IT WRITES (committed):
    data/ea_ratings.csv   17 columns, one row per team per edition snapshot:
      team, as_of, n_rated, ovr_top26, atk_top, def_top, gk_top, age_mean,
      gk_stop, sp_threat, sp_vuln, atk_fin, atk_create, atk_pen, def_win, ctrl, pace_trans

THE FIRST EIGHT COLUMNS are unchanged (top-26-by-overall squad proxy, same rule the
market-value proxy uses). ovr_top26 is the squad mean overall; atk_top and def_top are the
mean overall of the attack-side (forwards + midfielders) and defence-side (defenders +
goalkeepers) within the squad; gk_top is the best goalkeeper overall; age_mean is the squad
mean age. as_of is the edition release date, so the Java as-of lookup picks the pre-tournament
edition, leakage-safe like MarketValueTable. Rows are written only for teams with at least
5 rated players.

THE NINE TRAILING COLUMNS are the EA sub-attribute composites frozen in
notes/model/EA_SUBATTRIBUTES_PLAN.md (sections 3-4; freeze seal in
notes/model/ea_subattr_freeze.txt). Design rules, verbatim from the plan:
  - Composites use detailed sub-attributes only, never the six headline axes, never overall.
  - Position is the first token of player_positions.
  - Each pool is top-N-by-overall WITHIN a position token set over ALL rated players of the
    nationality that edition (not within the top-26 squad), so thin teams keep real pools.
  - A cell is blank when its pool is below floor. Blank means absent; nothing is imputed.
  - Composites live on the 1-99 attribute scale, so the Java column-agnostic standardization
    applies unchanged. height_cm is deliberately excluded (scale-incommensurate).
  - Composure fallback: for FIFA 15 and 16 (mentality_composure is blank there), any composite
    that uses composure drops that term and renormalizes the remaining weights to sum to one.
  - Internal component weights are frozen constants of the definition, never fitted here.

Then it audits coverage against the EA-gate surface (tournaments from 2015 on) and prints a
per-composite presence count, both structural (counts only, no outcomes, freeze-safe).

Run: python3 research/build_ea_ratings.py
"""
import csv
import math
import os
from collections import defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(REPO, "data", "ea_raw", "ea_players_legacy.csv")
OUT = os.path.join(REPO, "data", "ea_ratings.csv")
L020 = os.path.join(REPO, "research", "expanded_predictions_l020.csv")

SQUAD = 26
MIN_RATED = 5

# EA nationality_name -> results.csv team name (only where they differ).
ALIAS = {
    "Korea Republic": "South Korea", "Korea DPR": "North Korea", "China PR": "China",
    "IR Iran": "Iran", "Congo DR": "DR Congo", "Cote d'Ivoire": "Ivory Coast",
    "Côte d'Ivoire": "Ivory Coast",
    "Cape Verde Islands": "Cape Verde", "Chinese Taipei": "Taiwan",
    "Guinea Bissau": "Guinea-Bissau", "Curacao": "Curacao",
    "Bosnia and Herzegovina": "Bosnia and Herzegovina",
    "Republic of Ireland": "Republic of Ireland", "Northern Ireland": "Northern Ireland",
    "United States": "United States", "Trinidad and Tobago": "Trinidad and Tobago",
    "Antigua and Barbuda": "Antigua and Barbuda", "St Kitts Nevis": "St Kitts and Nevis",
}

# Detailed sub-attributes parsed for the composites (never the six axes, never overall).
ATTRS = [
    "goalkeeping_diving", "goalkeeping_handling", "goalkeeping_positioning",
    "goalkeeping_reflexes",
    "attacking_heading_accuracy", "power_jumping",
    "skill_fk_accuracy", "skill_curve", "mentality_penalties",
    "attacking_finishing", "mentality_positioning", "power_shot_power", "mentality_composure",
    "attacking_short_passing", "mentality_vision", "skill_long_passing", "attacking_crossing",
    "skill_dribbling", "movement_sprint_speed", "movement_acceleration", "skill_ball_control",
    "defending_standing_tackle", "defending_sliding_tackle", "mentality_interceptions",
    "defending_marking_awareness", "power_strength", "power_stamina",
]

# Position token sets (first token of player_positions), per plan sections 3-4.
DEF_TOK = {"CB", "LB", "RB", "LWB", "RWB"}
CREATE_TOK = {"CDM", "CM", "CAM", "LM", "RM", "LW", "RW", "CF"}
PEN_TOK = {"ST", "CF", "LW", "RW", "LM", "RM"}
FIN_STCF = {"ST", "CF"}
FIN_WING = {"LW", "RW", "CAM"}
NO_COMPOSURE = {"15", "16"}   # editions where mentality_composure is blank


def posgroup(player_positions):
    """Four-way bucket for the unchanged first eight columns."""
    first = (player_positions or "").split(",")[0].strip().upper()
    if first == "GK":
        return "gk"
    if first in ("CB", "LB", "RB", "LWB", "RWB", "LCB", "RCB"):
        return "def"
    if first in ("CDM", "CM", "CAM", "LM", "RM", "LCM", "RCM", "LDM", "RDM"):
        return "mid"
    return "att"


def first_token(player_positions):
    return (player_positions or "").split(",")[0].strip().upper()


def mean(xs):
    return sum(xs) / len(xs) if xs else ""


def avg(xs):
    return sum(xs) / len(xs)


def fmt(x):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return ""
    return round(x, 3)


def fnum(v):
    if v is None or v == "":
        return math.nan
    try:
        return float(v)
    except ValueError:
        return math.nan


def top_by_pos(players, tokens, n):
    sel = [p for p in players if p["tok"] in tokens]
    sel.sort(key=lambda p: -p["ovr"])
    return sel[:n]


def outfield(players):
    return sorted((p for p in players if p["tok"] != "GK"), key=lambda p: -p["ovr"])


# ---- the nine frozen composites (plan section 4) ---------------------------------------

def c_gk_stop(players, ver):
    """Best goalkeeper shot-stopping. Defence channel. Floor: 1 GK."""
    gks = [p for p in players if p["tok"] == "GK"]
    if len(gks) < 1:
        return None
    g = max(gks, key=lambda p: p["ovr"])
    return (0.30 * g["goalkeeping_diving"] + 0.30 * g["goalkeeping_reflexes"]
            + 0.20 * g["goalkeeping_positioning"] + 0.20 * g["goalkeeping_handling"])


def c_sp_threat(players, ver):
    """Set-piece attacking threat over the top-10 outfield proxy eleven. Attack channel.
    Floor: 8 outfield rated."""
    outs = outfield(players)
    if len(outs) < 8:
        return None
    eleven = outs[:10]

    def aer(p):
        return (p["attacking_heading_accuracy"] + p["power_jumping"]) / 2.0

    top4 = sorted(eleven, key=lambda p: -aer(p))[:4]
    aerial = avg([aer(p) for p in top4])
    delivery = max((p["skill_fk_accuracy"] + p["skill_curve"]) / 2.0 for p in eleven)
    penalty = max(p["mentality_penalties"] for p in eleven)
    return 0.50 * aerial + 0.30 * delivery + 0.20 * penalty


def c_sp_vuln(players, ver):
    """Set-piece defensive vulnerability: aerial strength of the back line. Defence channel.
    Floor: 4 defenders."""
    defs = top_by_pos(players, DEF_TOK, 5)
    if len(defs) < 4:
        return None
    return avg([(p["attacking_heading_accuracy"] + p["power_jumping"]) / 2.0 for p in defs])


def c_atk_fin(players, ver):
    """Finishing and composure. Probe-only. Floor: 2 in each of {ST,CF} and {LW,RW,CAM}."""
    stcf = top_by_pos(players, FIN_STCF, 3)
    wing = top_by_pos(players, FIN_WING, 3)
    if len(stcf) < 2 or len(wing) < 2:
        return None
    if ver in NO_COMPOSURE:
        def s(p):
            return (0.4375 * p["attacking_finishing"] + 0.3125 * p["mentality_positioning"]
                    + 0.25 * p["power_shot_power"])
    else:
        def s(p):
            return (0.35 * p["attacking_finishing"] + 0.25 * p["mentality_positioning"]
                    + 0.20 * p["power_shot_power"] + 0.20 * p["mentality_composure"])
    num = sum(s(p) for p in stcf) + 0.5 * sum(s(p) for p in wing)
    den = len(stcf) + 0.5 * len(wing)
    return num / den


def c_atk_create(players, ver):
    """Chance creation (supply). Probe-only. Floor: 5."""
    pool = top_by_pos(players, CREATE_TOK, 6)
    if len(pool) < 5:
        return None

    def s(p):
        return (0.30 * p["attacking_short_passing"] + 0.25 * p["mentality_vision"]
                + 0.15 * p["skill_long_passing"] + 0.15 * p["attacking_crossing"]
                + 0.15 * p["skill_dribbling"])
    return avg([s(p) for p in pool])


def c_atk_pen(players, ver):
    """Penetration (dribble and run in behind). Probe-only. Floor: 3."""
    pool = top_by_pos(players, PEN_TOK, 4)
    if len(pool) < 3:
        return None

    def s(p):
        return (0.30 * p["skill_dribbling"] + 0.25 * p["movement_sprint_speed"]
                + 0.20 * p["movement_acceleration"] + 0.25 * p["skill_ball_control"])
    return avg([s(p) for p in pool])


def c_def_win(players, ver):
    """Goals prevented outfield. Probe-only. Floor: 4 defenders (plus top CDM if present)."""
    defs = top_by_pos(players, DEF_TOK, 5)
    if len(defs) < 4:
        return None
    pool = defs + top_by_pos(players, {"CDM"}, 1)

    def s(p):
        return (0.30 * p["defending_standing_tackle"] + 0.15 * p["defending_sliding_tackle"]
                + 0.25 * p["mentality_interceptions"] + 0.20 * p["defending_marking_awareness"]
                + 0.10 * p["power_strength"])
    return avg([s(p) for p in pool])


def c_ctrl(players, ver):
    """Possession and control. Probe-only (draw channel). Floor: 8 outfield."""
    pool = outfield(players)[:10]
    if len(pool) < 8:
        return None
    if ver in NO_COMPOSURE:
        def s(p):
            return (0.375 * p["attacking_short_passing"] + 0.375 * p["skill_ball_control"]
                    + 0.25 * p["mentality_vision"])
    else:
        def s(p):
            return (0.30 * p["attacking_short_passing"] + 0.30 * p["skill_ball_control"]
                    + 0.20 * p["mentality_composure"] + 0.20 * p["mentality_vision"])
    return avg([s(p) for p in pool])


def c_pace_trans(players, ver):
    """Pace and transition. Probe-only. Floor: 3."""
    pool = top_by_pos(players, PEN_TOK, 4)
    if len(pool) < 3:
        return None

    def s(p):
        return (0.35 * p["movement_sprint_speed"] + 0.25 * p["movement_acceleration"]
                + 0.20 * p["power_stamina"] + 0.20 * p["power_strength"])
    return avg([s(p) for p in pool])


COMPOSITES = [
    ("gk_stop", c_gk_stop), ("sp_threat", c_sp_threat), ("sp_vuln", c_sp_vuln),
    ("atk_fin", c_atk_fin), ("atk_create", c_atk_create), ("atk_pen", c_atk_pen),
    ("def_win", c_def_win), ("ctrl", c_ctrl), ("pace_trans", c_pace_trans),
]


def main():
    if not os.path.exists(RAW):
        raise SystemExit(f"Missing {RAW}. Extract the legacy CSV into data/ea_raw/ first "
                         f"(see the header of this file).")

    # (version, team) -> list of player dicts; and version -> release date
    bucket = defaultdict(list)
    verdate = {}
    with open(RAW, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            ver = r.get("fifa_version")
            if not ver:
                continue
            verdate.setdefault(ver, r.get("fifa_update_date", ""))
            try:
                ovr = int(r["overall"])
            except (ValueError, KeyError):
                continue
            team = ALIAS.get(r.get("nationality_name", ""), r.get("nationality_name", ""))
            try:
                age = float(r["age"])
            except (ValueError, KeyError, TypeError):
                age = None
            p = {"ovr": ovr, "tok": first_token(r.get("player_positions", "")),
                 "grp": posgroup(r.get("player_positions", "")), "age": age}
            for a in ATTRS:
                p[a] = fnum(r.get(a, ""))
            bucket[(ver, team)].append(p)

    rows = []
    for (ver, team), players in bucket.items():
        squad = sorted(players, key=lambda p: -p["ovr"])[:SQUAD]
        if len(squad) < MIN_RATED:
            continue
        atk = [p["ovr"] for p in squad if p["grp"] in ("att", "mid")]
        deff = [p["ovr"] for p in squad if p["grp"] in ("def", "gk")]
        gk = [p["ovr"] for p in squad if p["grp"] == "gk"]
        ages = [p["age"] for p in squad if p["age"] is not None]
        base = [
            team, verdate[ver], len(squad),
            round(mean([p["ovr"] for p in squad]), 3),
            round(mean(atk), 3) if atk else "",
            round(mean(deff), 3) if deff else "",
            max(gk) if gk else "",
            round(mean(ages), 2) if ages else "",
        ]
        comp = [fmt(fn(players, ver)) for _, fn in COMPOSITES]
        rows.append(tuple(base + comp))
    rows.sort(key=lambda x: (x[0], x[1]))

    header = (["team", "as_of", "n_rated", "ovr_top26", "atk_top", "def_top", "gk_top",
               "age_mean"] + [name for name, _ in COMPOSITES])
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    editions = sorted(verdate.items(), key=lambda kv: kv[1])
    print(f"Wrote {len(rows)} rows for {len({r[0] for r in rows})} teams across "
          f"{len(editions)} editions to {OUT} ({len(header)} columns)")
    print("  editions: " + ", ".join(f"FIFA{v}({d})" for v, d in editions))

    # ---- per-composite presence (structural: counts only, no outcomes) ----
    print("\n=== composite presence across all rows ===")
    for i, (name, _) in enumerate(COMPOSITES):
        col = 8 + i
        present = sum(1 for r in rows if r[col] != "")
        print(f"  {name:<11} {present}/{len(rows)} rows populated")

    # ---- coverage audit against the EA-gate surface (tournaments from 2015 on) ----
    if not os.path.exists(L020):
        print(f"\n(coverage audit skipped: {L020} not present; regenerable via --expanded-export)")
        return
    have = defaultdict(list)  # team -> sorted [(as_of, n_rated)]
    for team, asof, n, *_ in rows:
        have[team].append((asof, n))
    for t in have:
        have[t].sort()

    def as_of(team, when):
        best = None
        for d, n in have.get(team, []):
            if d <= when:
                best = n
        return best

    tour = {}
    for r in csv.DictReader(open(L020, encoding="utf-8")):
        tour.setdefault(r["tournament"], {"date": r["date"], "teams": set()})
        tour[r["tournament"]]["teams"].add(r["home"])
        tour[r["tournament"]]["teams"].add(r["away"])

    print("\n=== EA coverage audit (tournaments from 2015 on) ===")
    tot_teams = tot_cov = 0
    unmatched = defaultdict(list)
    for name, info in sorted(tour.items(), key=lambda kv: kv[1]["date"]):
        if info["date"][:4] < "2015":
            continue
        cov = thin = 0
        for team in info["teams"]:
            n = as_of(team, info["date"])
            if n is None:
                unmatched[name].append(team)
            else:
                cov += 1
                if n < 15:
                    thin += 1
        nt = len(info["teams"])
        tot_teams += nt
        tot_cov += cov
        flag = "" if cov == nt else f"  MISSING {nt - cov}"
        print(f"  {info['date']}  {name:<26} {cov}/{nt} covered ({thin} thin){flag}")
    print(f"\n  overall EA-surface coverage: {tot_cov}/{tot_teams} team-slots")
    miss = sorted({t for v in unmatched.values() for t in v})
    if miss:
        print(f"  unmatched team names ({len(miss)}) to add to ALIAS: " + ", ".join(miss))


if __name__ == "__main__":
    main()
