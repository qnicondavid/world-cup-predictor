#!/usr/bin/env python3
"""research/ingest_2026_odds.py - normalize scraped 2026 World Cup odds into
data/odds_2026.csv, the flat file research/live_vs_market.py reads to score the
model against the bookmaker on the live tournament.

Same input shapes as ingest_odds_history.py, auto-detected:
  * OddsHarvester CSV (a 1x2_market blob of per-bookmaker {'1','X','2'} dicts,
    averaged across books), or
  * a flat CSV with match_date,home_team,away_team,home_odds,draw_odds,away_odds.

It does NOT touch data/odds_history.csv (the 2018/2022 backtest source). It reports
how many resolved 2026 matches are now covered, so you can see the gap shrink.

    python3 research/ingest_2026_odds.py data/wc2026_odds.csv [more.csv ...]

Then commit data/odds_2026.csv; the daily Action's scorer picks it up automatically.
"""
import csv
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.join(_HERE, "..")
_DATA = os.path.join(_ROOT, "data")
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from aliases import canon
from ingest_odds_history import load_source  # reuse the exact same parser


def main():
    args = sys.argv[1:] or [os.path.join(_DATA, "wc2026_odds.csv")]
    print("Merging 2026 odds sources:")
    merged = {}
    for path in args:
        if not os.path.exists(path):
            print(f"  (skip, not found: {os.path.basename(path)})")
            continue
        for d, h, a, oh, od, oa in load_source(path):
            merged[(d, h, a)] = (oh, od, oa)

    out = os.path.join(_DATA, "odds_2026.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["match_date", "home_team", "away_team", "home_odds", "draw_odds", "away_odds"])
        for (d, h, a), (oh, od, oa) in sorted(merged.items()):
            w.writerow([d, h, a, f"{oh:.4f}", f"{od:.4f}", f"{oa:.4f}"])
    print(f"wrote {len(merged)} odds rows -> {out}")

    # coverage against resolved 2026 matches (join on team pair; unique within a WC)
    tp = os.path.join(_ROOT, "docs", "data", "tracker.json")
    if os.path.exists(tp):
        try:
            res = json.load(open(tp, encoding="utf-8")).get("resolved", [])
        except (ValueError, OSError):
            res = []
        have = {(h, a) for (_, h, a) in merged}
        cov = sum(1 for m in res if (canon(m["home"]), canon(m["away"])) in have)
        print(f"coverage: {cov}/{len(res)} resolved 2026 matches now have odds")


if __name__ == "__main__":
    main()
