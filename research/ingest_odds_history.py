#!/usr/bin/env python3
"""
research/ingest_odds_history.py - merge WC odds from multiple sources into the
single data/odds_history.csv that odds_backtest.py consumes, then report how
many of the 128 WC2018+WC2022 matches are now covered.

Handles two input shapes automatically:
  * OddsHarvester CSV (columns incl. match_date + a 1x2_market blob of
    per-bookmaker {'1','X','2'} dicts) - the odds are averaged across books.
  * a flat CSV with match_date,home_team,away_team,home_odds,draw_odds,away_odds.

Pass files as arguments, or it defaults to the two scrape files:
    python3 research/ingest_odds_history.py [file1.csv file2.csv ...]

Team names are normalized to data/results.csv via the alias map; any match in
the held-out predictions that fails to join is listed so you can extend it.
Output schema: match_date,home_team,away_team,home_odds,draw_odds,away_odds
"""
import ast
import csv
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.join(_HERE, "..")
_DATA = os.path.join(_ROOT, "data")

if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from aliases import ALIASES, canon  # single source of truth for team-name canonicalization


def pick(cols, *, want, avoid=()):
    for c in cols:
        lc = c.lower()
        if all(w in lc for w in want) and not any(x in lc for x in avoid):
            return c
    return None


def detect(cols):
    date = (next((c for c in cols if c.lower() == "match_date"), None)
            or pick(cols, want=["date"], avoid=["scraped"]) or pick(cols, want=["date"]))
    home = pick(cols, want=["home", "team"]) or pick(cols, want=["home"], avoid=["odd", "score"])
    away = pick(cols, want=["away", "team"]) or pick(cols, want=["away"], avoid=["odd", "score"])
    market = pick(cols, want=["1x2"]) or pick(cols, want=["market"])  # OddsHarvester blob
    home_odds = pick(cols, want=["home", "odd"]) or pick(cols, want=["odds_1"])
    draw_odds = pick(cols, want=["draw", "odd"]) or pick(cols, want=["odds_x"])
    away_odds = pick(cols, want=["away", "odd"]) or pick(cols, want=["odds_2"])
    return {"date": date, "home": home, "away": away, "market": market,
            "home_odds": home_odds, "draw_odds": draw_odds, "away_odds": away_odds}


def odds_from_blob(blob):
    """Average 1/X/2 across the per-bookmaker dicts in a 1x2_market value."""
    try:
        books = ast.literal_eval(blob) if isinstance(blob, str) else blob
    except (ValueError, SyntaxError):
        return None
    h, d, a = [], [], []
    for bk in books or []:
        try:
            h.append(float(bk["1"])); d.append(float(bk["X"])); a.append(float(bk["2"]))
        except (KeyError, ValueError, TypeError):
            continue
    if h and d and a:
        return sum(h) / len(h), sum(d) / len(d), sum(a) / len(a)
    return None


def load_source(path):
    with open(path, encoding="utf-8") as f:
        r = csv.DictReader(f)
        m = detect(r.fieldnames)
        use_blob = bool(m["market"]) and not (m["home_odds"] and m["draw_odds"] and m["away_odds"])
        kind = "OddsHarvester blob" if use_blob else "flat odds"
        print(f"  {os.path.basename(path)} [{kind}]  date={m['date']} home={m['home']} "
              f"away={m['away']} odds={'1x2_market' if use_blob else (m['home_odds'],m['draw_odds'],m['away_odds'])}")
        if not (m["date"] and m["home"] and m["away"] and (use_blob or all(
                (m["home_odds"], m["draw_odds"], m["away_odds"])))):
            print(f"  !! could not detect required columns; headers were: {r.fieldnames}")
            return []
        rows = []
        for row in r:
            if use_blob:
                avg = odds_from_blob(row[m["market"]])
                if not avg:
                    continue
                oh, od, oa = avg
            else:
                try:
                    oh, od, oa = (float(row[m["home_odds"]]), float(row[m["draw_odds"]]),
                                  float(row[m["away_odds"]]))
                except (ValueError, KeyError):
                    continue
            rows.append((row[m["date"]][:10], canon(row[m["home"]]), canon(row[m["away"]]),
                         oh, od, oa))
        print(f"     parsed {len(rows)} rows")
        return rows


def main():
    args = sys.argv[1:]
    if not args:
        args = [os.path.join(_DATA, "wc2018_odds.csv"),
                os.path.join(_DATA, "wc2022_odds.csv"),
                os.path.join(_DATA, "odds_history_2022.csv")]
    print("Merging sources:")
    merged = {}
    for path in args:
        if not os.path.exists(path):
            print(f"  (skip, not found: {os.path.basename(path)})")
            continue
        for d, h, a, oh, od, oa in load_source(path):
            merged[(d, h, a)] = (oh, od, oa)

    out = os.path.join(_DATA, "odds_history.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["match_date", "home_team", "away_team",
                    "home_odds", "draw_odds", "away_odds"])
        for (d, h, a), (oh, od, oa) in sorted(merged.items()):
            w.writerow([d, h, a, f"{oh:.4f}", f"{od:.4f}", f"{oa:.4f}"])
    print(f"wrote {len(merged)} odds rows -> {out}")

    pred_path = os.path.join(_ROOT, "research", "export_predictions_form.csv")
    if not os.path.exists(pred_path):
        print("(no export_predictions_form.csv - skip coverage check)")
        return
    have = set(merged)
    miss = {"WC2018": [], "WC2022": []}
    tot = {"WC2018": 0, "WC2022": 0}
    for r in csv.DictReader(open(pred_path, encoding="utf-8")):
        if r["tournament"] not in tot:
            continue
        tot[r["tournament"]] += 1
        key = (r["date"][:10], canon(r["home"]), canon(r["away"]))
        if key not in have:
            miss[r["tournament"]].append(key)
    for t in ("WC2018", "WC2022"):
        cov = tot[t] - len(miss[t])
        print(f"{t}: {cov}/{tot[t]} matches covered")
        for k in miss[t][:20]:
            print(f"    miss: {k}")
    print("Extend ALIASES or check dates for misses, then re-run. "
          "When coverage is good: python3 research/odds_backtest.py")


if __name__ == "__main__":
    main()
