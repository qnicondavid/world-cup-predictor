#!/usr/bin/env python3
"""research/build_ea_ratings.py - build data/ea_ratings.csv (the committed per-team EA
Sports FC squad-rating aggregate) from the raw player dump, mirroring build_market_values.py.

WHAT IT READS (raw, kept out of the repo, data/ea_raw/ is gitignored):
    data/ea_raw/ea_players_legacy.csv   (stefanoleone992 FIFA 15-23, one row per player
                                         per edition; columns fifa_version, fifa_update_date,
                                         nationality_name, overall, player_positions, age)
    Extract it from the Kaggle "fifa-23-complete-player-dataset" archive:
        unzip -p archive.zip "male_players (legacy).csv" > data/ea_raw/ea_players_legacy.csv

WHAT IT WRITES (committed):
    data/ea_ratings.csv   columns: team, as_of, n_rated, ovr_top26, atk_top, def_top,
                          gk_top, age_mean  (one row per team per edition snapshot)

HOW IT AGGREGATES A SQUAD
Per nationality and edition, the top 26 players by overall are the squad proxy (the same
top-26 rule the market-value proxy uses). ovr_top26 is their mean overall; atk_top and
def_top are the mean overall of the attack-side (forwards + midfielders) and defence-side
(defenders + goalkeepers) players among them; gk_top is the best goalkeeper overall;
age_mean is their mean age. as_of is the edition's release date, so the Java as-of lookup
(latest snapshot on or before a tournament's start) picks the pre-tournament edition,
leakage-safe exactly like MarketValueTable. Rows are written only for teams with at least
5 rated players (below that the prior falls back to value-only anyway).

Then it audits coverage against the EA-gate surface (the expanded-surface tournaments from
2015 on, in research/expanded_predictions_l020.csv), so name-mapping gaps and thin teams
are visible before the gate is built.

Run: python research/build_ea_ratings.py
"""
import csv
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


def posgroup(player_positions):
    first = (player_positions or "").split(",")[0].strip().upper()
    if first == "GK":
        return "gk"
    if first in ("CB", "LB", "RB", "LWB", "RWB", "LCB", "RCB"):
        return "def"
    if first in ("CDM", "CM", "CAM", "LM", "RM", "LCM", "RCM", "LDM", "RDM"):
        return "mid"
    return "att"


def mean(xs):
    return sum(xs) / len(xs) if xs else ""


def main():
    if not os.path.exists(RAW):
        raise SystemExit(f"Missing {RAW}. Extract the legacy CSV into data/ea_raw/ first "
                         f"(see the header of this file).")

    # (version, team) -> list of (overall, group, age); and version -> release date
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
            bucket[(ver, team)].append((ovr, posgroup(r.get("player_positions", "")), age))

    rows = []
    for (ver, team), players in bucket.items():
        squad = sorted(players, key=lambda x: -x[0])[:SQUAD]
        if len(squad) < MIN_RATED:
            continue
        atk = [o for o, g, _ in squad if g in ("att", "mid")]
        deff = [o for o, g, _ in squad if g in ("def", "gk")]
        gk = [o for o, g, _ in squad if g == "gk"]
        ages = [a for _, _, a in squad if a is not None]
        rows.append((
            team, verdate[ver], len(squad),
            round(mean([o for o, _, _ in squad]), 3),
            round(mean(atk), 3) if atk else "",
            round(mean(deff), 3) if deff else "",
            max(gk) if gk else "",
            round(mean(ages), 2) if ages else "",
        ))
    rows.sort(key=lambda x: (x[0], x[1]))
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["team", "as_of", "n_rated", "ovr_top26", "atk_top", "def_top", "gk_top", "age_mean"])
        w.writerows(rows)
    editions = sorted(verdate.items(), key=lambda kv: kv[1])
    print(f"Wrote {len(rows)} rows for {len({r[0] for r in rows})} teams across "
          f"{len(editions)} editions to {OUT}")
    print("  editions: " + ", ".join(f"FIFA{v}({d})" for v, d in editions))

    # ---- coverage audit against the EA-gate surface (tournaments from 2015 on) ----
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
