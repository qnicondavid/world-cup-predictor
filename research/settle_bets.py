#!/usr/bin/env python3
"""
research/settle_bets.py - grade the forward CLV ledger and report ROI + CLV.

Reads the never-edited data/forward_bets.csv (entries written by
fetch_odds_live.py), joins each bet to:
  * data/results.csv          -> the actual outcome, to settle won/lost
  * data/odds_live.csv         -> the LATEST captured price for that outcome,
                                  used as the closing line for CLV

It does NOT mutate forward_bets.csv. It writes a derived
data/forward_bets_settled.csv (one row per bet, status won/lost/open) and
prints the headline numbers:
  * record, amount staked, profit/loss, ROI on staked
  * mean closing-line value and % of bets that beat the close - CLV is the
    real test: a bet can lose and still have been +EV if you beat the closing
    price, and over many bets positive CLV is what predicts a real edge.

Run it after results land (re-run fetch_odds_live.py near kickoff first so the
ledger has a near-closing snapshot to measure CLV against).
"""
import csv
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA = os.path.join(_HERE, "..", "data")

if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from aliases import ALIASES, canon  # single source of truth for team-name canonicalization


def load_results():
    res = {}
    p = os.path.join(_DATA, "results.csv")
    for r in csv.DictReader(open(p, encoding="utf-8")):
        try:
            hs, as_ = int(r["home_score"]), int(r["away_score"])
        except (ValueError, KeyError):
            continue
        outcome = "home" if hs > as_ else "away" if as_ > hs else "draw"
        res[(r["date"][:10], canon(r["home_team"]), canon(r["away_team"]))] = outcome
    return res


def load_closing():
    """Latest BEST price per (date,home,away) for each outcome = closing line.

    CLV must be like-for-like: bets are entered at the best available price, so the
    close is also the best price. Grading entry-best against the cross-book AVERAGE
    would manufacture positive CLV out of book dispersion alone.
    """
    close = {}
    p = os.path.join(_DATA, "odds_live.csv")
    if not os.path.exists(p):
        return close
    for r in csv.DictReader(open(p, encoding="utf-8")):
        key = (r["match_date"], canon(r["home_team"]), canon(r["away_team"]))
        # rows are appended in capture order; last write wins = closest to kickoff
        close[key] = {"home": float(r["best_home"]), "draw": float(r["best_draw"]),
                      "away": float(r["best_away"])}
    return close


def main():
    bets_path = os.path.join(_DATA, "forward_bets.csv")
    if not os.path.exists(bets_path):
        raise SystemExit("No data/forward_bets.csv yet - run fetch_odds_live.py first.")
    results, closing = load_results(), load_closing()

    out_rows = []
    staked = pnl = clv_sum = clv_n = clv_pos = 0.0
    won = lost = open_ = 0
    for b in csv.DictReader(open(bets_path, encoding="utf-8")):
        key = (b["match_date"], canon(b["home_team"]), canon(b["away_team"]))
        o, price, stake = b["outcome"], float(b["offered_odds"]), float(b["stake"])
        # CLV: your decimal odds vs the closing best for that outcome.
        clv = ""
        c = closing.get(key)
        if c and c.get(o):
            clv_val = price / c[o] - 1.0  # positive = you beat the close
            clv = f"{clv_val:.4f}"
            clv_sum += clv_val; clv_n += 1; clv_pos += clv_val > 0
        actual = results.get(key)
        if actual is None:
            status, profit = "open", ""
            open_ += 1
        else:
            hit = (o == actual)
            profit = stake * (price - 1.0) if hit else -stake
            staked += stake; pnl += profit
            won += hit; lost += not hit
            status = "won" if hit else "lost"
            profit = f"{profit:.4f}"
        out_rows.append({**b, "actual": actual or "", "status": status,
                         "profit": profit, "clv": clv})

    out = os.path.join(_DATA, "forward_bets_settled.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()) if out_rows
                           else ["status"])
        w.writeheader(); w.writerows(out_rows)

    settled = won + lost
    print(f"bets: {len(out_rows)}  settled: {settled} (W{won}-L{lost})  open: {open_}")
    if settled:
        roi = pnl / staked * 100 if staked else 0.0
        print(f"staked {staked:.3f}u  P/L {pnl:+.3f}u  ROI {roi:+.1f}% of staked")
    if clv_n:
        print(f"CLV: mean {clv_sum/clv_n:+.4f} over {int(clv_n)} priced bets, "
              f"{100*clv_pos/clv_n:.0f}% beat the close")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
