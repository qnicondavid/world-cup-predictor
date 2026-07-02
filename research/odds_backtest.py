#!/usr/bin/env python3
"""
research/odds_backtest.py - backtest the model against historical bookmaker odds.

Supply data/odds_history.csv with (at least) these columns; extra columns are
ignored and column names are matched case-insensitively:

    match_date,home_team,away_team,home_odds,draw_odds,away_odds

odds are decimal (e.g. 1.80). Team names should match data/results.csv; a small
alias map below handles the common international naming differences. Get the odds
from OddsPortal / Betfair historical / a WC-covering Kaggle set; the 20k "Europe"
club datasets will NOT have these matches.

The script joins to research/export_predictions_form.csv (the production model's
held-out predictions) for WC2018 + WC2022, de-vigs the odds to market
probabilities, and reports:
  * coverage (matches joined)
  * model multiclass Brier vs the market (de-vigged closing-line) Brier on the
    SAME matches - the board's actual question: are we sharper than the price?
  * value bets the policy would flag (5% edge floor, quarter-Kelly) and their ROI
  * mean model-vs-market edge on the flagged bets (model prob minus market prob;
    positive by selection, NOT closing-line value - real CLV is in settle_bets.py)
"""
import csv
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA = os.path.join(_HERE, "..", "data")

if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from aliases import ALIASES, canon  # single source of truth for team-name canonicalization


def devig(o_home, o_draw, o_away):
    inv = [1.0 / o_home, 1.0 / o_draw, 1.0 / o_away]
    s = sum(inv)
    return [x / s for x in inv]


def mcb(p, y):
    e = [0, 0, 0]
    e[y] = 1
    return sum((p[i] - e[i]) ** 2 for i in range(3))


def _avg_blob(cell):
    """Average 1/X/2 across the per-bookmaker dicts in an OddsHarvester blob."""
    import ast
    try:
        books = ast.literal_eval(cell)
    except (ValueError, SyntaxError):
        return None
    H = [float(b["1"]) for b in books if "1" in b]
    D = [float(b["X"]) for b in books if "X" in b]
    A = [float(b["2"]) for b in books if "2" in b]
    return (sum(H) / len(H), sum(D) / len(D), sum(A) / len(A)) if H and D and A else None


def _from_scrapes(rows):
    """Fallback source: the raw OddsHarvester scrape CSVs (1x2_market blobs)."""
    for f in ("wc2018_odds.csv", "wc2022_odds.csv", "wc2018_full.csv", "wc2022_full.csv"):
        p = os.path.join(_DATA, f)
        if not os.path.exists(p):
            continue
        for row in csv.DictReader(open(p, encoding="utf-8")):
            avg = _avg_blob(row.get("1x2_market", "") or "")
            if not avg:
                continue
            d, h, a = row["match_date"][:10], canon(row["home_team"]), canon(row["away_team"])
            rows.setdefault((d, frozenset((h, a))), (h,) + avg)


def load_odds():
    """Return {(date, frozenset{teams}): (home_team, o_home, o_draw, o_away)}.

    Keyed on the UNORDERED team pair so a neutral-venue match joins regardless of
    which side each source calls 'home'; the stored home_team lets the caller
    orient the odds to the prediction. Robust to a NUL-corrupted or thin
    odds_history.csv: rebuilds from the scrape CSVs if needed.
    """
    rows = {}
    path = os.path.join(_DATA, "odds_history.csv")
    if os.path.exists(path):
        data = open(path, encoding="utf-8", errors="ignore").read().replace("\x00", "")
        r = csv.DictReader(data.splitlines())
        cols = {c.lower(): c for c in (r.fieldnames or [])}
        need = ("match_date", "home_team", "away_team", "home_odds", "draw_odds", "away_odds")
        if all(c in cols for c in need):
            for row in r:
                try:
                    d = row[cols["match_date"]][:10]
                    h, a = canon(row[cols["home_team"]]), canon(row[cols["away_team"]])
                    oh, od, oa = (float(row[cols["home_odds"]]), float(row[cols["draw_odds"]]),
                                  float(row[cols["away_odds"]]))
                except (ValueError, KeyError, TypeError):
                    continue
                rows[(d, frozenset((h, a)))] = (h, oh, od, oa)
    if len(rows) < 60:  # corrupt/thin odds_history.csv -> rebuild from scrape blobs
        _from_scrapes(rows)
    if not rows:
        raise SystemExit("No odds found (odds_history.csv and scrape CSVs both empty).")
    return rows


def main():
    odds = load_odds()
    EDGE_FLOOR, KELLY = 0.05, 0.25
    joined = []
    with open(os.path.join(_DATA, "..", "research", "export_predictions_form.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["tournament"] not in ("WC2018", "WC2022"):
                continue
            home, away = canon(r["home"]), canon(r["away"])
            rec = odds.get((r["date"][:10], frozenset((home, away))))
            if not rec:
                continue
            o_home, oh, od, oa = rec
            if o_home != home:  # source called the other side 'home' - orient to prediction
                oh, oa = oa, oh
            o = [oh, od, oa]
            y = {"home": 0, "draw": 1, "away": 2}[r["actual"]]
            model = [float(r["p_home"]), float(r["p_draw"]), float(r["p_away"])]
            market = devig(*o)
            joined.append((r["tournament"], model, market, o, y))

    n = len(joined)
    print(f"joined {n} of 128 WC2018+WC2022 matches with odds")
    if n == 0:
        raise SystemExit("No matches joined - check team-name aliases and date formats.")

    mb = sum(mcb(m, y) for _, m, _, _, y in joined) / n
    kb = sum(mcb(k, y) for _, _, k, _, y in joined) / n
    print(f"model Brier {mb:.4f}   market (de-vigged) Brier {kb:.4f}   diff {mb-kb:+.4f}")
    print("  (model sharper than the price only if diff is clearly negative)")

    # value bets: stake quarter-Kelly when model EV over an outcome clears the floor
    bankroll_units, staked, pnl, sel_edge = 0.0, 0.0, 0.0, []
    bets = 0
    for _, model, market, o, y in joined:
        for i in range(3):
            ev = model[i] * o[i] - 1.0
            if ev <= EDGE_FLOOR:
                continue
            kelly = max(0.0, (model[i] * o[i] - 1.0) / (o[i] - 1.0)) * KELLY
            stake = min(kelly, 0.05)
            bets += 1
            staked += stake
            pnl += stake * (o[i] - 1.0) if y == i else -stake
            # model-minus-market probability on a bet already selected for edge:
            # positive by construction (selection bias), NOT closing-line value.
            # Real CLV (entry price vs the closing best) is graded in settle_bets.py.
            sel_edge.append(model[i] - market[i])
    roi = (pnl / staked * 100) if staked else 0.0
    print(f"value bets flagged: {bets}   ROI {roi:+.1f}% of staked   "
          f"mean model-vs-market edge {sum(sel_edge)/len(sel_edge):+.4f} "
          f"(flagged bets; positive by selection, not CLV - real CLV in settle_bets.py)"
          if sel_edge else f"value bets flagged: {bets}")


if __name__ == "__main__":
    main()
