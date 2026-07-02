"""
Build data/market_values.csv (team,as_of,value_eur) from the Transfermarkt
player-level data, so the model can use squad market value as a prior.

WHAT TO DOWNLOAD
----------------
You only need two files. The dcaribou/transfermarkt-datasets GitHub repo stores
its data with DVC, so the CSVs are NOT in the file tree — download them from one
of these instead:
  - the "Download Dataset" ZIP on the repo README (unzip, take the two files);
  - directly (gzipped):
        https://pub-e682421888d945d684bcae8890b0ec20.r2.dev/data/players.csv.gz
        https://pub-e682421888d945d684bcae8890b0ec20.r2.dev/data/player_valuations.csv.gz
  - or Kaggle davidcariboo/player-scores (plain .csv, needs a free login).

    players.csv             (has player_id, country_of_citizenship, name)
    player_valuations.csv   (has player_id, date, market_value_in_eur)

PUT THEM HERE (relative to the repo root) — either .csv or .csv.gz works:

    data/transfermarkt/players.csv      (or players.csv.gz)
    data/transfermarkt/player_valuations.csv   (or player_valuations.csv.gz)

THEN RUN (from the repo root):

    python research/build_market_values.py

It writes data/market_values.csv. The committed file is exactly this output, so
re-running reproduces it byte-for-byte. With it in place, `mvn compile exec:java
"-Dexec.args=--values"` compares the value-adjusted model against plain
Dixon-Coles on the held-out World Cups.

HOW IT APPROXIMATES A SQUAD
---------------------------
The raw data has no historical call-up lists, so for each (nation, snapshot
date) we take the players of that nationality who had a valuation in the two
years before the date, value each at its most recent valuation on/before the
date, and sum the top SQUAD_SIZE by value. That is a proxy for the squad, not
the exact 23/26 — good enough for a strength prior; document it as such.
"""
import csv
import gzip
import os
from collections import defaultdict
from datetime import date

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAYERS = os.path.join(REPO, "data", "transfermarkt", "players.csv")
VALUATIONS = os.path.join(REPO, "data", "transfermarkt", "player_valuations.csv")
OUTPUT = os.path.join(REPO, "data", "market_values.csv")

SQUAD_SIZE = 26
ACTIVE_WINDOW_DAYS = 730  # a player counts toward a squad only if valued this recently

# Snapshot dates: the five backtested World Cups + a current 2026 value.
SNAPSHOTS = [date(2006, 6, 1), date(2010, 6, 1), date(2014, 6, 1),
             date(2018, 6, 1), date(2022, 11, 1), date(2026, 6, 1)]

# country_of_citizenship -> results.csv team name (extend as needed).
ALIASES = {
    "USA": "United States", "Korea, South": "South Korea", "Korea, North": "North Korea",
    "Cote d'Ivoire": "Ivory Coast", "Côte d'Ivoire": "Ivory Coast", "Czechia": "Czech Republic",
    "Turkiye": "Turkey", "Türkiye": "Turkey", "Cabo Verde": "Cape Verde",
    "DR Congo": "DR Congo", "Congo DR": "DR Congo", "Curacao": "Curaçao",
    "Bosnia-Herzegovina": "Bosnia and Herzegovina", "Ireland": "Republic of Ireland",
    "The Gambia": "Gambia",
}


def open_csv(path):
    """Open a CSV, accepting either the plain file or its .gz form."""
    if os.path.exists(path):
        return open(path, newline="", encoding="utf-8")
    if os.path.exists(path + ".gz"):
        return gzip.open(path + ".gz", mode="rt", newline="", encoding="utf-8")
    raise FileNotFoundError(f"Put {os.path.basename(path)} (or .gz) in data/transfermarkt/")


def col(row, *names):
    for n in names:
        if n in row and row[n] not in ("", "NA"):
            return row[n]
    return None


def load_nationality():
    nat = {}
    with open_csv(PLAYERS) as f:
        for r in csv.DictReader(f):
            pid = col(r, "player_id")
            country = col(r, "country_of_citizenship", "country_of_birth")
            if pid and country:
                nat[pid] = ALIASES.get(country, country)
    return nat


def load_valuations():
    vals = defaultdict(list)  # player_id -> [(date, value)]
    with open_csv(VALUATIONS) as f:
        for r in csv.DictReader(f):
            pid = col(r, "player_id")
            d = col(r, "date", "datetime")
            v = col(r, "market_value_in_eur", "market_value")
            if not (pid and d and v):
                continue
            try:
                y, m, day = map(int, d[:10].split("-"))
                vals[pid].append((date(y, m, day), float(v)))
            except ValueError:
                continue
    for pid in vals:
        vals[pid].sort()
    return vals


def value_as_of(history, when):
    """Most recent valuation on/before `when`, if within the active window."""
    best = None
    for d, v in history:
        if d <= when:
            best = (d, v)
        else:
            break
    if best and (when - best[0]).days <= ACTIVE_WINDOW_DAYS:
        return best[1]
    return None


def main():
    nationality = load_nationality()
    valuations = load_valuations()
    rows = []
    for snap in SNAPSHOTS:
        by_team = defaultdict(list)
        for pid, history in valuations.items():
            team = nationality.get(pid)
            if not team:
                continue
            v = value_as_of(history, snap)
            if v:
                by_team[team].append(v)
        for team, player_values in by_team.items():
            squad = sorted(player_values, reverse=True)[:SQUAD_SIZE]
            if squad:
                rows.append((team, snap.isoformat(), int(sum(squad))))
    rows.sort()
    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["team", "as_of", "value_eur"])
        w.writerows(rows)
    print(f"Wrote {len(rows)} rows for {len({r[0] for r in rows})} teams to {OUTPUT}")


if __name__ == "__main__":
    main()
