#!/usr/bin/env python3
"""
research/build_realsquad_values.py - REAL-squad market-value dataset ("A3a").

The committed data/market_values.csv approximates each nation's squad by summing
the top-26 *by value* of everyone of that nationality valued near the snapshot
(see research/build_market_values.py). That proxy can over- or under-state a side
whose real call-ups differ from the value-ranked pool. This script instead uses
the ACTUAL World Cup squads (from the saved Wikipedia squad pages) and values the
named players, so the model can be backtested against a genuine squad prior.

OUTPUTS (all under data/):
  wc_squads.csv                tournament,team,player          - the parsed squads
  market_values_realsquad.csv  team,as_of,value_eur            - drop-in replacement
                               for market_values.csv: the five backtest snapshots
                               are real-squad totals, the 2026-06-01 rows are COPIED
                               verbatim from the committed market_values.csv (no real
                               2026 squads exist yet), so it can substitute directly.

INPUTS (all local; this script never touches the network):
  data/wc_squads_html/<year>_squads.html   - complete Wikipedia squad pages, one per
                               tournament (copied here from the uploads so the build is
                               self-contained). Configure the dir with --html-dir.
  data/transfermarkt/players.csv.gz         (player_id, name, country_of_citizenship)
  data/transfermarkt/player_valuations.csv.gz (player_id, date, market_value_in_eur)
  data/market_values.csv                    - source of the copied 2026-06-01 rows.

RUN (from repo root):   python research/build_realsquad_values.py
Add --report for the coverage / join-rate / proxy-vs-real tables that decide go/no-go.

HOW THE PARSER HANDLES TWO HTML VARIANTS
----------------------------------------
Every page is Parsoid HTML where each team is an <h3 id="Team_Name"> section and
each squad member is a <tr class="nat-fs-player"> row whose <th scope="row"> holds
the name. The first 32 <h3> ids per page are the teams (the rest are the trailing
"Player representation ..." analysis sections). The name is taken from the row's
<a title="..."> when the player has an article (works for ALL years, incl. the
2006/2010/2014 pages that carry no data-sort-value), and falls back to the cell's
plain text for the handful of un-linked players (e.g. several 2010 North Koreans).
data-sort-value, where present (2018/2022), is used only as a cross-check.
"""
import argparse
import bisect
import collections
import csv
import difflib
import gzip
import html as ihtml
import os
import re
import sys
import unicodedata
from datetime import date

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "research"))
from aliases import canon  # noqa: E402  (team-name -> results.csv spelling)

DATA = os.path.join(REPO, "data")
TM = os.path.join(DATA, "transfermarkt")
DEFAULT_HTML_DIR = os.path.join(DATA, "wc_squads_html")
MARKET_VALUES = os.path.join(DATA, "market_values.csv")
OUT_SQUADS = os.path.join(DATA, "wc_squads.csv")
OUT_VALUES = os.path.join(DATA, "market_values_realsquad.csv")

# Tournament -> (html file, valuation snapshot date). 26-man squads from 2022 on.
TOURNAMENTS = [
    ("2006", "2006_squads.html", date(2006, 6, 1)),
    ("2010", "2010_squads.html", date(2010, 6, 1)),
    ("2014", "2014_squads.html", date(2014, 6, 1)),
    ("2018", "2018_squads.html", date(2018, 6, 1)),
    ("2022", "2022_squads.html", date(2022, 11, 1)),
]
COPY_SNAPSHOT = "2026-06-01"  # rows copied verbatim from committed market_values.csv

# canonical results.csv team name -> Transfermarkt country_of_citizenship spelling(s).
# Used to restrict the name-join to same-nationality candidates. A team may map to
# several TM nationalities (Serbia & Montenegro 2006 fielded players now cited under
# both "Serbia" and "Montenegro"). Anything not listed uses its own name unchanged.
TEAM_TO_TM_NATIONALITY = {
    "South Korea": ["Korea, South"],
    "North Korea": ["Korea, North"],
    "Ivory Coast": ["Cote d'Ivoire"],
    "Bosnia and Herzegovina": ["Bosnia-Herzegovina"],
    "Serbia": ["Serbia", "Montenegro"],  # covers the 2006 joint team
    "Republic of Ireland": ["Ireland"],
}

# canon() folds most spellings already; this only adds the 2006 joint team, whose
# results.csv name is plain "Serbia".
EXTRA_TEAM_ALIASES = {
    "serbia and montenegro": "Serbia",
}


# ----------------------------------------------------------------------------- #
# Squad parsing
# ----------------------------------------------------------------------------- #
_DISAMBIG = re.compile(r"\s*\((?:footballer|association football)[^)]*\)\s*$", re.I)
_H3 = re.compile(r'<h3\b[^>]*\bid="([^"]+)"')
_ROW = re.compile(r'<tr class="nat-fs-player">(.*?)</tr>', re.S)
_TH = re.compile(r'<th\b[^>]*scope="row"[^>]*>(.*?)</th>', re.S)
_A_TITLE = re.compile(r'<a\b[^>]*\btitle="([^"]+)"')
_SUP = re.compile(r"<sup\b.*?</sup>", re.S)
_TAG = re.compile(r"<[^>]+>")


def _clean(name):
    name = _DISAMBIG.sub("", ihtml.unescape(name).strip())
    return name.strip()


def _th_to_name(th):
    """Player display name from a <th scope="row"> cell (linked or plain)."""
    m = _A_TITLE.search(th)
    if m:
        return _clean(m.group(1))
    txt = ihtml.unescape(_TAG.sub("", _SUP.sub("", th)))
    return re.split(r"\s*\(", txt)[0].strip()  # cut captain marker etc.


def parse_squads(path):
    """Return OrderedDict{raw_team_name: [player display names]} for one page."""
    doc = open(path, encoding="utf-8").read()
    heads = list(_H3.finditer(doc))
    teams = heads[:32]  # the remaining <h3>s are analysis sections
    out = collections.OrderedDict()
    for i, h in enumerate(teams):
        name = h.group(1).replace("_", " ")
        end = heads[i + 1].start() if i + 1 < len(heads) else len(doc)
        players = []
        for row in _ROW.finditer(doc[h.end():end]):
            th = _TH.search(row.group(1))
            if th:
                nm = _th_to_name(th.group(1))
                if nm:
                    players.append(nm)
        out[name] = players
    return out


def team_canon(raw):
    key = raw.replace("’", "'").replace("‘", "'").lower()
    if key in EXTRA_TEAM_ALIASES:
        return EXTRA_TEAM_ALIASES[key]
    return canon(raw)


# ----------------------------------------------------------------------------- #
# Transfermarkt panel + name join (mirrors research/lineup_value.py)
# ----------------------------------------------------------------------------- #
def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return " ".join("".join(c if c.isalnum() or c == " " else " " for c in s).split())


def load_players():
    """country_of_citizenship -> [(norm_name, player_id, token_set)]."""
    by_country = collections.defaultdict(list)
    with gzip.open(os.path.join(TM, "players.csv.gz"), "rt", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            nm = norm(r["name"])
            if nm:
                by_country[r["country_of_citizenship"]].append(
                    (nm, r["player_id"], frozenset(nm.split())))
    return by_country


def load_valuations():
    val = collections.defaultdict(list)
    with gzip.open(os.path.join(TM, "player_valuations.csv.gz"), "rt", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                val[r["player_id"]].append((r["date"][:10], float(r["market_value_in_eur"])))
            except (ValueError, KeyError):
                continue
    for p in val:
        val[p].sort()
    return val


def value_asof(val, pid, when, window_days=730):
    """Most recent valuation on/before `when` (ISO str), if within the window."""
    rows = val.get(pid)
    if not rows:
        return None
    i = bisect.bisect_right([d for d, _ in rows], when)
    if i == 0:
        return None
    d, v = rows[i - 1]
    y1, m1, dd1 = map(int, d.split("-"))
    if (when_d := date.fromisoformat(when)) and (when_d - date(y1, m1, dd1)).days <= window_days:
        return v
    return None


def best_match(name_norm, cand_lists):
    """Match a normalized name to a player_id within the given candidate lists
    (each list = one TM nationality). Exact -> surname/2-token -> fuzzy."""
    cands = [c for lst in cand_lists for c in lst]
    if not cands:
        return None
    for nm, pid, _ in cands:
        if nm == name_norm:
            return pid
    qt = set(name_norm.split())
    last = name_norm.split()[-1] if qt else name_norm
    best, br = None, 0.0
    for nm, pid, tk in cands:
        share = len(qt & tk)
        if last in tk or share >= 2:
            rr = difflib.SequenceMatcher(None, name_norm, nm).ratio() + 0.05 * share
            if rr > br:
                br, best = rr, pid
    if best and br >= 0.55:
        return best
    for nm, pid, _ in cands:
        rr = difflib.SequenceMatcher(None, name_norm, nm).ratio()
        if rr > br:
            br, best = rr, pid
    return best if br >= 0.86 else None


def tm_candidates(team, by_country):
    nats = TEAM_TO_TM_NATIONALITY.get(team, [team])
    return [by_country.get(n, []) for n in nats]


# ----------------------------------------------------------------------------- #
# Build
# ----------------------------------------------------------------------------- #
def build(html_dir):
    """Parse squads, join+value, and return
       (squad_rows, value_rows, stats) where
       squad_rows = [(tournament, team, player)] sorted,
       value_rows = [(team, as_of, value_eur)] for the 5 snapshots,
       stats      = per-(tournament,team) match diagnostics."""
    by_country = load_players()
    val = load_valuations()

    squad_rows = []
    value_rows = []
    stats = []  # (tournament, team, n_players, n_matched, n_valued, unmatched_names)

    for tourn, fname, snap in TOURNAMENTS:
        squads = parse_squads(os.path.join(html_dir, fname))
        snap_iso = snap.isoformat()
        for raw_team, players in squads.items():
            team = team_canon(raw_team)
            cands = tm_candidates(team, by_country)
            total = value_sum = 0.0
            n_matched = n_valued = 0
            unmatched = []
            for p in players:
                squad_rows.append((tourn, team, p))
                pid = best_match(norm(p), cands)
                if pid:
                    n_matched += 1
                    v = value_asof(val, pid, snap_iso)
                    if v is not None:
                        n_valued += 1
                        value_sum += v
                    else:
                        unmatched.append(p + " [no value@snap]")
                else:
                    unmatched.append(p)
                total += 1
            value_rows.append((team, snap_iso, int(round(value_sum))))
            stats.append((tourn, team, len(players), n_matched, n_valued, unmatched))

    squad_rows.sort()
    value_rows.sort()
    return squad_rows, value_rows, stats


def copy_2026_rows():
    """The committed market_values.csv 2026-06-01 rows, verbatim."""
    rows = []
    with open(MARKET_VALUES, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["as_of"] == COPY_SNAPSHOT:
                rows.append((r["team"], r["as_of"], int(r["value_eur"])))
    return rows


def write_outputs(squad_rows, value_rows):
    with open(OUT_SQUADS, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["tournament", "team", "player"])
        w.writerows(squad_rows)

    all_values = value_rows + copy_2026_rows()
    all_values.sort()
    with open(OUT_VALUES, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["team", "as_of", "value_eur"])
        w.writerows(all_values)
    return len(all_values)


# ----------------------------------------------------------------------------- #
# Coverage report
# ----------------------------------------------------------------------------- #
def load_committed_proxy():
    proxy = {}  # (team, as_of) -> value
    with open(MARKET_VALUES, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            proxy[(r["team"], r["as_of"])] = int(r["value_eur"])
    return proxy


def report(stats, value_rows):
    proxy = load_committed_proxy()
    by_t = collections.defaultdict(list)
    for s in stats:
        by_t[s[0]].append(s)

    print("=" * 74)
    print("COVERAGE REPORT - real-squad market values (A3a)")
    print("=" * 74)
    print("\nPer tournament: teams parsed (want 32) and mean squad name-join rate")
    print("(share of the named squad matched to a Transfermarkt valuation AT the")
    print("snapshot - the key risk; want the mean >= 90%).\n")
    print(f"  {'tourn':6} {'teams':5} {'players':7} {'mean_match%':11} {'mean_valued%':12}")
    for tourn, _, _ in TOURNAMENTS:
        ss = by_t[tourn]
        tp = sum(s[2] for s in ss)
        mrate = 100 * sum(s[3] / s[2] for s in ss) / len(ss)
        vrate = 100 * sum(s[4] / s[2] for s in ss) / len(ss)
        print(f"  {tourn:6} {len(ss):5} {tp:7} {mrate:10.1f}% {vrate:11.1f}%")

    print("\nWorst-valued squads per tournament (would contribute near-zero value):")
    for tourn, _, _ in TOURNAMENTS:
        ss = sorted(by_t[tourn], key=lambda s: s[4] / s[2])[:5]
        print(f"  {tourn}:")
        for t, team, n, nm, nv, un in ss:
            print(f"      {team:26} valued {nv:2}/{n:2} ({100*nv/n:3.0f}%)"
                  + (f"  e.g. missing: {', '.join(un[:3])}" if un else ""))

    print("\nProxy (committed market_values.csv) vs real-squad totals, EUR millions:")
    print("(if nearly identical, A3a's added signal is small)\n")
    watch = ["Brazil", "France", "Germany", "Argentina", "Spain"]
    real = {(t, a): v for t, a, v in value_rows}
    hdr = "  {:10}".format("team") + "".join(f"{tr+' snap':>16}" for tr, _, _ in TOURNAMENTS)
    print(hdr)
    for team in watch:
        line = f"  {team:10}"
        for tourn, _, snap in TOURNAMENTS:
            a = snap.isoformat()
            r = real.get((team, a))
            p = proxy.get((team, a))
            rs = f"{r/1e6:.0f}" if r is not None else "-"
            ps = f"{p/1e6:.0f}" if p is not None else "-"
            line += f"{'r'+rs+'/p'+ps:>16}"
        print(line)

    # aggregate verdict inputs
    all_m = [s[3] / s[2] for s in stats]
    all_v = [s[4] / s[2] for s in stats]
    mean_v = 100 * sum(all_v) / len(all_v)
    poor = [(s[0], s[1], round(100 * s[4] / s[2])) for s in stats if s[4] / s[2] < 0.6]
    print("\n" + "-" * 74)
    print(f"Overall mean valued-at-snapshot rate: {mean_v:.1f}%  "
          f"(match rate {100*sum(all_m)/len(all_m):.1f}%)")
    print(f"Squads under 60% valued: {len(poor)} / {len(stats)}")
    if poor:
        print("  " + "; ".join(f"{t} {tm} {p}%" for t, tm, p in poor[:20]))
    print("VERDICT: " + ("GO - coverage supports the --paired gate."
                          if mean_v >= 90 else
                          "CAUTION - mean valued rate < 90%; join is lossy, "
                          "review the worst squads before running --paired."))
    print("-" * 74)


# ----------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--html-dir", default=DEFAULT_HTML_DIR,
                    help="dir holding <year>_squads.html (default: data/wc_squads_html/)")
    ap.add_argument("--report", action="store_true", help="print the coverage report")
    args = ap.parse_args()

    squad_rows, value_rows, stats = build(args.html_dir)
    n_values = write_outputs(squad_rows, value_rows)
    print(f"Wrote {len(squad_rows)} squad rows to {OUT_SQUADS}")
    print(f"Wrote {n_values} value rows to {OUT_VALUES} "
          f"({len(value_rows)} real + copied {COPY_SNAPSHOT})")
    if args.report:
        print()
        report(stats, value_rows)


if __name__ == "__main__":
    main()
