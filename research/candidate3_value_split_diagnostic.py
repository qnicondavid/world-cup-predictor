#!/usr/bin/env python3
"""research/candidate3_value_split_diagnostic.py - the cheap kill test for BRIER_PLAN
Candidate 3 (make the squad-value prior's data earn more) using the data already in
the repo: the Transfermarkt player dumps with position and date of birth.

The shipped value prior maps one number, standardized log of total squad value, onto
attack and defence symmetrically. Candidate 3's two testable upgrades that need no new
data are (a) an attack-versus-defence value split (the prior structurally cannot express
that a team's money is concentrated in forwards or in defenders), and (b) a squad-age
term (resale value undervalues aging cores). The project has been burned before: any
reasonable squad-value construction correlates about 0.99 with any other after
standardizing logs (the real-squads experiment died on that wall). So before touching
ValueAdjuster we check whether the split and the age term carry anything the total does
not.

Aggregation mirrors build_market_values.py exactly: per nationality and snapshot date,
players valued within 730 days, top 26 by value are the squad. We then split that squad
value by Transfermarkt position (Attack + Midfield = attack side, Defender + Goalkeeper
= defence side) and compute the mean squad age.

Kill test A (correlation wall): across the WC 2014/2018/2022 squads, how independent are
log attack value, log defence value, and mean age from log total value? If attack and
defence value both track total at ~0.97+ and correlate ~0.97+ with each other, no team
is meaningfully attack- or defence-heavy relative to its total, and the split is dead.

Kill test B (residual predictiveness): leave-one-tournament-out, does the attack-minus-
defence tilt differential (home minus away) or the age differential predict the
production model's outcome residual? Positive and sign-stable means signal a prior could
use; nothing there kills it.

Prerequisites: data/transfermarkt/{players,player_valuations}.csv(.gz),
research/expanded_predictions_l020.csv. Run: python3 research/candidate3_value_split_diagnostic.py
"""
import csv
import gzip
import os
from collections import defaultdict
from datetime import date

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAYERS = os.path.join(REPO, "data", "transfermarkt", "players.csv")
VALUATIONS = os.path.join(REPO, "data", "transfermarkt", "player_valuations.csv")
L020 = os.path.join(REPO, "research", "expanded_predictions_l020.csv")

SQUAD_SIZE = 26
ACTIVE_WINDOW_DAYS = 730
# snapshot per World Cup year -> the l020 tournament label
SNAPS = {2014: date(2014, 6, 1), 2018: date(2018, 6, 1), 2022: date(2022, 11, 1)}
LABEL = {2014: "WC2014", 2018: "WC2018", 2022: "WC2022"}

ALIASES = {
    "USA": "United States", "Korea, South": "South Korea", "Korea, North": "North Korea",
    "Cote d'Ivoire": "Ivory Coast", "Cote d`Ivoire": "Ivory Coast", "Czechia": "Czech Republic",
    "Turkiye": "Turkey", "Cabo Verde": "Cape Verde", "Congo DR": "DR Congo", "DR Congo": "DR Congo",
    "Curacao": "Curacao", "Bosnia-Herzegovina": "Bosnia and Herzegovina",
    "Ireland": "Republic of Ireland", "The Gambia": "Gambia",
}


def open_csv(path):
    if os.path.exists(path):
        return open(path, newline="", encoding="utf-8")
    if os.path.exists(path + ".gz"):
        return gzip.open(path + ".gz", mode="rt", newline="", encoding="utf-8")
    raise FileNotFoundError(path)


def col(row, *names):
    for n in names:
        if n in row and row[n] not in ("", "NA"):
            return row[n]
    return None


def posgroup(position):
    p = (position or "").lower()
    if "goalkeeper" in p:
        return "gk"
    if "defender" in p or "back" in p:
        return "def"
    if "midfield" in p:
        return "mid"
    if "attack" in p or "forward" in p or "winger" in p or "striker" in p:
        return "att"
    return "other"


def load_players():
    nat, pos, dob = {}, {}, {}
    with open_csv(PLAYERS) as f:
        for r in csv.DictReader(f):
            pid = col(r, "player_id")
            country = col(r, "country_of_citizenship", "country_of_birth")
            if not (pid and country):
                continue
            nat[pid] = ALIASES.get(country, country)
            pos[pid] = posgroup(col(r, "position", "sub_position"))
            d = col(r, "date_of_birth")
            if d:
                try:
                    y, m, dd = map(int, d[:10].split("-"))
                    dob[pid] = date(y, m, dd)
                except ValueError:
                    pass
    return nat, pos, dob


def load_valuations():
    vals = defaultdict(list)
    with open_csv(VALUATIONS) as f:
        for r in csv.DictReader(f):
            pid = col(r, "player_id")
            d = col(r, "date", "datetime")
            v = col(r, "market_value_in_eur", "market_value")
            if not (pid and d and v):
                continue
            try:
                y, m, dd = map(int, d[:10].split("-"))
                vals[pid].append((date(y, m, dd), float(v)))
            except ValueError:
                continue
    for pid in vals:
        vals[pid].sort()
    return vals


def value_as_of(history, when):
    best = None
    for d, v in history:
        if d <= when:
            best = (d, v)
        else:
            break
    if best and (when - best[0]).days <= ACTIVE_WINDOW_DAYS:
        return best[1]
    return None


def wc_teams():
    teams = defaultdict(set)
    for r in csv.DictReader(open(L020, encoding="utf-8")):
        for lbl, yr in [(v, k) for k, v in LABEL.items()]:
            if r["tournament"] == lbl:
                teams[yr].add(r["home"])
                teams[yr].add(r["away"])
    return teams


def main():
    nat, pos, dob = load_players()
    vals = load_valuations()
    want = wc_teams()

    # team-year aggregates
    agg = {}  # (team, year) -> dict
    poscount = defaultdict(int)
    for year, snap in SNAPS.items():
        by_team = defaultdict(list)
        for pid, hist in vals.items():
            team = nat.get(pid)
            if team is None:
                continue
            v = value_as_of(hist, snap)
            if v is None:
                continue
            age = (snap - dob[pid]).days / 365.25 if pid in dob else None
            by_team[team].append((v, pos.get(pid, "other"), age))
        for team, players in by_team.items():
            if team not in want.get(year, set()):
                continue
            squad = sorted(players, key=lambda x: -x[0])[:SQUAD_SIZE]
            for _, g, _ in squad:
                poscount[g] += 1
            total = sum(v for v, _, _ in squad)
            att = sum(v for v, g, _ in squad if g in ("att", "mid"))
            deff = sum(v for v, g, _ in squad if g in ("def", "gk"))
            gk = max([v for v, g, _ in squad if g == "gk"], default=0.0)
            ages = [a for _, _, a in squad if a is not None]
            agemean = float(np.mean(ages)) if ages else None
            if total > 0 and att > 0 and deff > 0:
                agg[(team, year)] = dict(total=total, att=att, deff=deff, gk=gk, age=agemean)

    print("=== position distribution across the squads (sanity check) ===")
    print("  " + ", ".join(f"{k}={v}" for k, v in sorted(poscount.items())))
    print(f"  squads built: {len(agg)} (WC 2014/2018/2022, up to 96)")

    lt = np.array([np.log(a["total"]) for a in agg.values()])
    la = np.array([np.log(a["att"]) for a in agg.values()])
    ld = np.array([np.log(a["deff"]) for a in agg.values()])
    ages = np.array([a["age"] if a["age"] else np.nan for a in agg.values()])

    def z(x):
        return (x - np.nanmean(x)) / np.nanstd(x)

    def corr(a, b):
        m = ~(np.isnan(a) | np.isnan(b))
        return float(np.corrcoef(a[m], b[m])[0, 1])

    print("\n=== Kill test A: correlation wall ===")
    print(f"  corr(log attack , log total ) = {corr(la, lt):+.3f}")
    print(f"  corr(log defence, log total ) = {corr(ld, lt):+.3f}")
    print(f"  corr(log attack , log defence) = {corr(la, ld):+.3f}")
    print(f"  corr(mean age   , log total ) = {corr(ages, lt):+.3f}")
    tilt = z(la) - z(ld)  # attack-minus-defence tilt, residual of the split beyond scale
    print(f"  attack-minus-defence tilt: std={np.nanstd(tilt):.3f} "
          f"(0 = no independent split variation; larger = teams differ in balance)")

    # Kill test B: does the tilt / age differential predict the outcome residual, LOTO?
    zage = z(ages)
    tiltmap = {k: t for k, t in zip(agg.keys(), tilt)}
    agemap = {k: t for k, t in zip(agg.keys(), zage)}
    rows = list(csv.DictReader(open(L020, encoding="utf-8")))
    data = []
    for r in rows:
        yr = {v: k for k, v in LABEL.items()}.get(r["tournament"])
        if yr is None:
            continue
        hk, ak = (r["home"], yr), (r["away"], yr)
        if hk not in tiltmap or ak not in tiltmap:
            continue
        ph, pd_, pa = float(r["p_home"]), float(r["p_draw"]), float(r["p_away"])
        res = (1.0 if r["actual"] == "home" else 0.5 if r["actual"] == "draw" else 0.0) - (ph + 0.5 * pd_)
        data.append((yr, tiltmap[hk] - tiltmap[ak], agemap[hk] - agemap[ak], res))
    print(f"\n=== Kill test B: residual predictiveness (LOTO), n={len(data)} matches ===")
    yrs = sorted(set(d[0] for d in data))
    for feat, idx in [("tilt_diff", 1), ("age_diff", 2)]:
        pooled = np.corrcoef([d[idx] for d in data], [d[3] for d in data])[0, 1]
        signs = []
        for held in yrs:
            sub = [d for d in data if d[0] == held]
            if len(sub) > 3:
                c = np.corrcoef([d[idx] for d in sub], [d[3] for d in sub])[0, 1]
                signs.append((LABEL[held], c))
        print(f"  {feat:9} pooled corr with outcome residual = {pooled:+.3f} | "
              + " ".join(f"{lbl}:{c:+.2f}" for lbl, c in signs))
    print("(a real signal is a non-trivial pooled correlation with the SAME sign every tournament)")


if __name__ == "__main__":
    main()
