#!/usr/bin/env python3
"""research/live_vs_market.py - head-to-head probability quality, live.

The project's core question is whether the model's probabilities are sharper than
a bookmaker's, not whether they make money. For every 2026 match with both a locked
model prediction (docs/data/tracker.json) and a captured bookmaker price
(data/odds_live.csv), this de-vigs the market's average 1X2 odds and scores the
model's multiclass Brier against the market's on the actual result. It writes
docs/data/live_market.json for the site.

Caveats baked into the output: the sample is tiny, and the market probabilities come
from whatever odds snapshot was captured, which is not necessarily the closing line.
So this is a running check, not a verdict. The rigorous version is the 99-match
closing-line comparison in the README (2018/2022), which came out at parity.
"""
import csv
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.join(_HERE, "..")
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
from aliases import canon  # single source of truth for team-name canonicalization


def devig(oh, od, oa):
    """Strip the overround from average 1X2 decimal odds -> fair probabilities."""
    inv = [1.0 / oh, 1.0 / od, 1.0 / oa]
    s = sum(inv)
    return [x / s for x in inv]


def brier(p, actual):
    """Multiclass Brier: sum_k (p_k - y_k)^2. actual in {0=home, 1=draw, 2=away}."""
    return sum((p[k] - (1 if k == actual else 0)) ** 2 for k in range(3))


def main():
    # market price per (home, away); teams are unique within one World Cup.
    mkt = {}
    # Live captures first: average 1X2 snapshots grabbed before kickoff (data/odds_live.csv).
    op = os.path.join(_ROOT, "data", "odds_live.csv")
    if os.path.exists(op):
        for r in csv.DictReader(open(op, encoding="utf-8")):
            try:
                probs = devig(float(r["avg_home"]), float(r["avg_draw"]), float(r["avg_away"]))
            except (ValueError, KeyError, ZeroDivisionError):
                continue
            mkt[(canon(r["home_team"]), canon(r["away_team"]))] = {"date": r["match_date"], "p": probs}
    # Then scraped closing lines (data/odds_2026.csv, odds_history schema:
    # match_date,home_team,away_team,home_odds,draw_odds,away_odds). These are the sharper,
    # more rigorous benchmark, so they take precedence over the live snapshot where present.
    bp = os.path.join(_ROOT, "data", "odds_2026.csv")
    if os.path.exists(bp):
        for r in csv.DictReader(open(bp, encoding="utf-8")):
            try:
                probs = devig(float(r["home_odds"]), float(r["draw_odds"]), float(r["away_odds"]))
            except (ValueError, KeyError, ZeroDivisionError):
                continue
            mkt[(canon(r["home_team"]), canon(r["away_team"]))] = {"date": r["match_date"], "p": probs}

    tj = json.load(open(os.path.join(_ROOT, "docs", "data", "tracker.json"), encoding="utf-8"))
    rows = []
    ms = ks = 0.0
    for m in tj.get("resolved", []):
        mh, ma = canon(m["home"]), canon(m["away"])
        c = mkt.get((mh, ma))
        if c:
            market, mdate = c["p"], c["date"]
        else:                                    # odds stored in the other team order: swap
            c = mkt.get((ma, mh))
            if not c:
                continue
            market, mdate = [c["p"][2], c["p"][1], c["p"][0]], c["date"]
        try:
            hs, as_ = [int(x) for x in str(m["result"]).split("-")]
        except (ValueError, AttributeError):
            continue
        actual = 0 if hs > as_ else (2 if as_ > hs else 1)
        mb = brier([m["pHome"], m["pDraw"], m["pAway"]], actual)
        kb = brier(market, actual)
        ms += mb
        ks += kb
        rows.append({"date": mdate, "home": m["home"], "away": m["away"], "result": m["result"],
                     "model": round(mb, 4), "market": round(kb, 4),
                     "sharper": "model" if mb < kb else "market"})

    rows.sort(key=lambda r: r["date"])
    n = len(rows)
    out = {
        "note": ("Head-to-head multiclass Brier (lower is better) on 2026 matches with both a locked "
                 "model prediction and a captured bookmaker price. Market probabilities are the de-vigged "
                 "average 1X2 odds from data/odds_live.csv, the snapshot captured, not necessarily the "
                 "closing line. Small sample: read the running gap, not a verdict. The rigorous version is "
                 "the 99-match 2018/2022 closing-line comparison, which came out at parity."),
        "matches": n,
        "model": round(ms / n, 4) if n else None,
        "market": round(ks / n, 4) if n else None,
        "modelWins": sum(1 for r in rows if r["sharper"] == "model"),
        "rows": rows,
    }
    out_path = os.path.join(_ROOT, "docs", "data", "live_market.json")
    json.dump(out, open(out_path, "w", encoding="utf-8"), indent=0)
    print(f"live_vs_market: {n} matches, model {out['model']} vs market {out['market']}, "
          f"model sharper on {out['modelWins']}")


if __name__ == "__main__":
    main()
