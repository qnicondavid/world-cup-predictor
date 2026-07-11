#!/usr/bin/env python3
"""research/parse_results_odds.py - build data/odds_2026.csv straight from OddsPortal
results-page text (no OddsHarvester needed; the results page shows the 1 / X / 2 odds
inline).

Workflow: on each paginated results page, select all (Ctrl+A), copy, paste into a plain
.txt file, then:

    python3 research/parse_results_odds.py page1.txt page2.txt ...

Each match on the page renders as: the H2H link, the two teams in display order, the
score, then the average 1 / X / 2 decimal odds. This pulls out (date, teamA, teamB,
o1, oX, o2). De-vigging happens later in live_vs_market.py, which also handles the
home/away orientation. Merges into data/odds_2026.csv; never touches odds_history.csv.
"""
import csv
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.join(_HERE, "..")
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
from aliases import canon

MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}
DATE_RE = re.compile(r'^(?:Today,\s*|Yesterday,\s*)?(\d{1,2})\s+([A-Z][a-z]{2})(?:\s+(\d{4}))?(?:\s*[-–].*)?$')
INT_RE = re.compile(r'^\d+$')
DEC_RE = re.compile(r'^\d+\.\d+$')


def parse(text):
    """Extract (match_date, teamA, teamB, o1, oX, o2) rows from pasted results text."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    out, cur, i = [], None, 0
    while i < len(lines):
        m = DATE_RE.match(lines[i])
        if m:
            d, mon, y = m.group(1), m.group(2), (m.group(3) or "2026")
            cur = f"{y}-{MONTHS.get(mon, 0):02d}-{int(d):02d}"
            i += 1
            continue
        if "/h2h/" in lines[i]:
            # the eight lines after the link: teamA, scoreA, dash, scoreB, teamB, o1, oX, o2
            blk = lines[i + 1:i + 9]
            if (len(blk) == 8 and INT_RE.match(blk[1]) and INT_RE.match(blk[3])
                    and DEC_RE.match(blk[5]) and DEC_RE.match(blk[6]) and DEC_RE.match(blk[7])):
                out.append((cur, blk[0], blk[4], blk[5], blk[6], blk[7]))
                i += 9
                continue
        i += 1
    return out


def main():
    files = sys.argv[1:]
    if not files:
        raise SystemExit("usage: parse_results_odds.py page1.txt [page2.txt ...]")
    out_path = os.path.join(_ROOT, "data", "odds_2026.csv")
    merged = {}
    if os.path.exists(out_path):
        for r in csv.DictReader(open(out_path, encoding="utf-8")):
            merged[(r["match_date"], r["home_team"], r["away_team"])] = (
                r["home_odds"], r["draw_odds"], r["away_odds"])
    for f in files:
        rows = parse(open(f, encoding="utf-8").read())
        for d, a, b, o1, ox, o2 in rows:
            merged[(d, canon(a), canon(b))] = (o1, ox, o2)
        print(f"  {os.path.basename(f)}: parsed {len(rows)} matches")
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["match_date", "home_team", "away_team", "home_odds", "draw_odds", "away_odds"])
        for (d, a, b), (o1, ox, o2) in sorted(merged.items()):
            w.writerow([d, a, b, o1, ox, o2])
    print(f"odds_2026.csv now has {len(merged)} matches -> {out_path}")


if __name__ == "__main__":
    main()
