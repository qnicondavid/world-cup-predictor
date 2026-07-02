#!/usr/bin/env python3
"""
research/fetch_odds_live.py - capture pre-kickoff 1X2 odds for the forward CLV test.

The API key is read from the ODDS_API_KEY environment variable (or a local file
research/.odds_api_key). It is NEVER printed or committed - add both to
.gitignore. Get a free key at https://the-odds-api.com (free tier = live/upcoming
odds, ~500 requests/month).

Usage:
    # 1) list the soccer competitions that currently have odds (costs 0 credits):
    python3 research/fetch_odds_live.py
    # 2) capture odds for one of them (1 credit), e.g.:
    python3 research/fetch_odds_live.py soccer_fifa_world_cup

What it does for a given sport key:
  * pulls upcoming events' average + best 1X2 odds across bookmakers
  * appends a timestamped snapshot to data/odds_live.csv (append-only)
  * joins each event to the locked model predictions in
    predictions/predictions.csv, and for any outcome where the model's edge
    clears the 5% floor, appends a never-edited row to data/forward_bets.csv
    (entry price, model prob, market prob, edge, quarter-Kelly stake, status=open)

Run it at lock time and again near kickoff; the two snapshots let you compute
closing-line value once results land.
"""
import csv
import json
import os
import sys
import time
import urllib.parse
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.join(_HERE, "..")

if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from aliases import ALIASES, canon  # single source of truth for team-name canonicalization

BASE = "https://api.the-odds-api.com/v4"
EDGE_FLOOR, KELLY, STAKE_CAP = 0.05, 0.25, 0.05
# A genuine edge shows up across books, not in one stray line. Skip an outcome
# when the best price is an outlier vs the cross-book average - that is an
# illiquid/erroneous line, and "value" against it is noise, not signal.
OUTLIER_MULT = 1.5


def read_key():
    key = os.environ.get("ODDS_API_KEY")
    if not key:
        p = os.path.join(_HERE, ".odds_api_key")
        if os.path.exists(p):
            key = open(p, encoding="utf-8").read().strip()
    if not key:
        sys.exit("Set ODDS_API_KEY in your environment (or research/.odds_api_key). "
                 "The key is never printed or committed.")
    return key


def api_get(path, key, **params):
    params["apiKey"] = key
    url = path + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=60) as r:
        remaining = r.headers.get("x-requests-remaining")
        data = json.load(r)
    return data, remaining


def list_soccer(key):
    sports, _ = api_get(f"{BASE}/sports", key)
    print("Active soccer competitions with odds (re-run with one of these keys):")
    for s in sports:
        if s.get("group") == "Soccer" and s.get("active"):
            print(f"  {s['key']:34s} {s['title']}")


def avg_max(prices):
    return (sum(prices) / len(prices), max(prices)) if prices else (None, None)


def load_predictions():
    preds = {}
    p = os.path.join(_ROOT, "predictions", "predictions.csv")
    if os.path.exists(p):
        for r in csv.DictReader(open(p, encoding="utf-8")):
            preds[(r["match_date"], canon(r["home_team"]), canon(r["away_team"]))] = r
    return preds


def append_rows(path, header, rows):
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(header)
        w.writerows(rows)


def main():
    key = read_key()
    if len(sys.argv) < 2:
        list_soccer(key)
        return
    sport = sys.argv[1]
    events, remaining = api_get(f"{BASE}/sports/{sport}/odds", key,
                                regions="eu", markets="h2h", oddsFormat="decimal")
    print(f"{len(events)} events fetched ({remaining} API requests remaining this month)")

    preds = load_predictions()
    captured = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    snap_rows, bet_rows = [], []
    existing_bets = set()
    bets_path = os.path.join(_ROOT, "data", "forward_bets.csv")
    if os.path.exists(bets_path):
        for r in csv.DictReader(open(bets_path, encoding="utf-8")):
            existing_bets.add((r["match_date"], r["home_team"], r["away_team"], r["outcome"]))

    joined = flagged = 0
    for ev in events:
        home, away = canon(ev["home_team"]), canon(ev["away_team"])
        date = ev["commence_time"][:10]
        buckets = {"home": [], "draw": [], "away": []}
        for bk in ev.get("bookmakers", []):
            for m in bk.get("markets", []):
                if m["key"] != "h2h":
                    continue
                for oc in m["outcomes"]:
                    nm = canon(oc["name"])
                    side = "home" if nm == home else "away" if nm == away else "draw" if oc["name"] == "Draw" else None
                    if side:
                        buckets[side].append(oc["price"])
        (ah, mh), (ad, md), (aa, ma) = avg_max(buckets["home"]), avg_max(buckets["draw"]), avg_max(buckets["away"])
        if None in (ah, ad, aa):
            continue
        snap_rows.append([captured, date, home, away, f"{ah:.4f}", f"{ad:.4f}", f"{aa:.4f}",
                          f"{mh:.4f}", f"{md:.4f}", f"{ma:.4f}"])

        pr = preds.get((date, home, away))
        if not pr:
            continue
        joined += 1
        model = {"home": float(pr["p_home"]), "draw": float(pr["p_draw"]), "away": float(pr["p_away"])}
        avg = {"home": ah, "draw": ad, "away": aa}
        best = {"home": mh, "draw": md, "away": ma}
        inv = sum(1.0 / avg[o] for o in avg)
        market = {o: (1.0 / avg[o]) / inv for o in avg}
        for o in ("home", "draw", "away"):
            price = best[o]  # bet the best available price
            if price > OUTLIER_MULT * avg[o]:  # stray/illiquid line, not a real edge
                continue
            ev_edge = model[o] * price - 1.0
            if ev_edge <= EDGE_FLOOR:
                continue
            if (date, home, away, o) in existing_bets:
                continue
            stake = min(max(0.0, (model[o] * price - 1.0) / (price - 1.0)) * KELLY, STAKE_CAP)
            bet_rows.append([captured, date, home, away, o, f"{model[o]:.4f}",
                             f"{market[o]:.4f}", f"{price:.4f}", f"{ev_edge:.4f}", f"{stake:.4f}", "open"])
            flagged += 1

    append_rows(os.path.join(_ROOT, "data", "odds_live.csv"),
                ["captured_at", "match_date", "home_team", "away_team",
                 "avg_home", "avg_draw", "avg_away", "best_home", "best_draw", "best_away"],
                snap_rows)
    if bet_rows:
        append_rows(bets_path,
                    ["captured_at", "match_date", "home_team", "away_team", "outcome",
                     "model_prob", "market_prob", "offered_odds", "edge", "stake", "status"],
                    bet_rows)
    print(f"snapshot: {len(snap_rows)} events -> data/odds_live.csv | "
          f"joined to predictions: {joined} | new value bets: {flagged} -> data/forward_bets.csv")


if __name__ == "__main__":
    main()
