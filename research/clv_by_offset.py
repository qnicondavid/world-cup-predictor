#!/usr/bin/env python3
"""
research/clv_by_offset.py - closing-line value bucketed by how early a bet was entered.

Finding "A5": against a sharp closing line the model is at parity, so any edge is more
likely in softer, earlier prices than at the close. This asks the forward question: does
entering a flagged value bet earlier (further before kickoff) capture more closing-line
value than entering near the close? For each bet in the never-edited forward ledger it
compares the entry price to the closing best price and buckets the resulting CLV by the
entry offset (hours before kickoff), taken from data/odds_live.csv's commence_time.

This is a FORWARD, season-scale instrument, not a backtest: it needs odds captured at
several offsets across many matches. Capture with, at each offset before kickoff:
    python3 research/fetch_odds_live.py soccer_fifa_world_cup
Rows captured before the commence_time column existed have no kickoff time and are
skipped. No staking-policy change: the 5% edge floor / quarter-Kelly / 5% cap / 1.5x
outlier guard live in fetch_odds_live.py and settle_bets.py grades entry-vs-close CLV;
this only slices that CLV by entry offset.
"""
import csv
import os
import sys
from datetime import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA = os.path.join(_HERE, "..", "data")
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
from aliases import canon  # single source of truth for team-name canonicalization

# Entry-offset buckets by hours before kickoff, coarsest (earliest) first.
BUCKETS = [(48.0, "T-72h+  (>=48h)"),
           (24.0, "T-48h   (24-48h)"),
           (6.0,  "T-24h   (6-24h)"),
           (0.0,  "T-1h    (<6h)")]


def parse_iso(s):
    if not s:
        return None
    try:
        return datetime.strptime(s.strip(), "%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, AttributeError):
        return None


def bucket_for(hours):
    for lo, label in BUCKETS:
        if hours >= lo:
            return label
    return BUCKETS[-1][1]


def load_snapshots():
    """match key -> {commence: datetime|None, rows: [(captured_at, best-price dict)]}."""
    path = os.path.join(_DATA, "odds_live.csv")
    snaps = {}
    if not os.path.exists(path):
        return snaps
    for r in csv.DictReader(open(path, encoding="utf-8")):
        key = (r["match_date"], canon(r["home_team"]), canon(r["away_team"]))
        entry = snaps.setdefault(key, {"commence": None, "rows": []})
        try:
            best = {"home": float(r["best_home"]), "draw": float(r["best_draw"]),
                    "away": float(r["best_away"])}
        except (ValueError, KeyError, TypeError):
            continue  # short/malformed row (e.g. missing a price) -> skip
        entry["rows"].append((parse_iso(r["captured_at"]), best))
        commence = parse_iso(r.get("commence_time"))  # None on pre-A5 rows (short header)
        if commence and not entry["commence"]:
            entry["commence"] = commence
    return snaps


def closing_best(rows, commence, outcome):
    """Best price on the latest snapshot at or before kickoff (the closing line)."""
    usable = [(c, b) for c, b in rows if c is not None and (commence is None or c <= commence)]
    if not usable:
        return None
    usable.sort(key=lambda x: x[0])
    return usable[-1][1][outcome]


def main():
    snaps = load_snapshots()
    bets_path = os.path.join(_DATA, "forward_bets.csv")
    if not os.path.exists(bets_path):
        raise SystemExit("No data/forward_bets.csv yet - run fetch_odds_live.py first.")

    buckets = {label: {"clv": 0.0, "n": 0, "beat": 0} for _, label in BUCKETS}
    graded = skipped = 0
    for b in csv.DictReader(open(bets_path, encoding="utf-8")):
        key = (b["match_date"], canon(b["home_team"]), canon(b["away_team"]))
        snap = snaps.get(key)
        entry = parse_iso(b["captured_at"])
        if not snap or not snap["commence"] or entry is None:
            skipped += 1  # no captured kickoff time -> offset unknown
            continue
        close = closing_best(snap["rows"], snap["commence"], b["outcome"])
        if not close:
            skipped += 1
            continue
        hours = (snap["commence"] - entry).total_seconds() / 3600.0
        if hours < 0:
            skipped += 1
            continue
        clv = float(b["offered_odds"]) / close - 1.0  # positive = beat the close
        bk = buckets[bucket_for(hours)]
        bk["clv"] += clv
        bk["n"] += 1
        bk["beat"] += clv > 0
        graded += 1

    print("=== A5: closing-line value by entry offset (forward ledger) ===")
    print(f"graded {graded} bet(s); skipped {skipped} without a captured kickoff time.\n")
    print(f"  {'entry offset':16s} {'bets':>5s} {'mean CLV':>10s} {'% beat close':>13s}")
    for _, label in BUCKETS:
        bk = buckets[label]
        if bk["n"]:
            print(f"  {label:16s} {bk['n']:5d} {bk['clv'] / bk['n']:+10.4f} "
                  f"{100.0 * bk['beat'] / bk['n']:12.0f}%")
        else:
            print(f"  {label:16s} {0:5d} {'-':>10s} {'-':>13s}")
    if graded == 0:
        print("\nNo bets carry multi-offset kickoff data yet. Capture odds at several offsets")
        print("(T-72h/48h/24h/1h) before kickoff with fetch_odds_live.py to populate this; a")
        print("verdict needs a few hundred settled bets, so it is a season-scale instrument.")


if __name__ == "__main__":
    main()
