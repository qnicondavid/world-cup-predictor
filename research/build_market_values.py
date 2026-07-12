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


def current_participants(year):
    """Teams that play a FIFA World Cup match in `year`, read from results.csv. Used only to
    focus the staleness alarm on teams the model is actually pricing now, so a stale micro
    nation nobody predicts does not raise noise. Returns an empty set if results.csv is absent,
    which simply disables the alarm."""
    path = os.path.join(REPO, "data", "results.csv")
    teams = set()
    if not os.path.exists(path):
        return teams
    with open(path, "rb") as _fh:
        if b"\x00" in _fh.read():
            raise SystemExit(f"{path} contains NUL bytes (a OneDrive sync artifact); restore it with: git checkout -- {path}")
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("date", "")[:4] == str(year) and r.get("tournament") == "FIFA World Cup":
                for t in (r.get("home_team"), r.get("away_team")):
                    if t:
                        teams.add(t)
    return teams


def report_staleness(rows):
    """Warn when a current World Cup participant's squad value is older than the newest
    snapshot, meaning the model prices that team from a stale figure (Qatar, for example,
    last valued in 2022). Reads only; it does not touch the market_values.csv output, and it
    is non-fatal so the daily build never breaks over a data-freshness issue."""
    newest = max(SNAPSHOTS)
    team_newest = {}
    for team, as_of, _ in rows:
        d = date.fromisoformat(as_of)
        if team not in team_newest or d > team_newest[team]:
            team_newest[team] = d
    participants = current_participants(newest.year)
    if not participants:
        return
    stale = []
    for team in sorted(participants):
        d = team_newest.get(team)
        if d is None or d < newest:
            stale.append((team, d))
    if not stale:
        print(f"Squad values current: all {len(participants)} {newest.year} World Cup "
              f"participants have a {newest.isoformat()} valuation.")
        return
    print(f"WARNING: squad market value is stale for {len(stale)} of {len(participants)} "
          f"{newest.year} World Cup participant(s); the model prices them from an older snapshot:")
    for team, d in stale:
        if d is None:
            print(f"  {team:<26} no market-value row (check the ALIASES name mapping)")
        else:
            months = (newest.year - d.year) * 12 + (newest.month - d.month)
            print(f"  {team:<26} newest value {d.isoformat()} "
                  f"({months} months behind {newest.isoformat()})")
    print("  If the name is a mapping gap, fix the alias; otherwise the source data simply lacks")
    print("  recent coverage for that team (Qatar, for example), and the flag is expected.")


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
    report_staleness(rows)


if __name__ == "__main__":
    main()
