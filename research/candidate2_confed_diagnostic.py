#!/usr/bin/env python3
"""research/candidate2_confed_diagnostic.py - the cheap kill test for BRIER_PLAN
Candidate 2 (confederation-aware strength in the fit).

Candidate 2 proposes estimating inter-confederation attack/defence offsets jointly
with the team ratings, so cross-confederation matchups stop leaning on sparse direct
evidence. Before building that into PoissonRatingsFitter, the plan (section 7) calls
for a cheap nested check: does confederation structure add anything beyond the value
prior, out of sample?

This script answers it with an UPPER BOUND. On the 2,180-match expanded surface it
takes the production model's own predictions (from research/probe_features.csv) and
applies a leave-one-tournament-out, per-ordered-confederation-pair residual correction:
for each held-out tournament, estimate mean(onehot(outcome) - production_prob) per
confederation pair from the OTHER tournaments (leakage-safe, min 15 matches per pair),
then add scale * that residual to the held-out predictions and renormalise. A free
per-pair probability offset is strictly more expressive than in-fit rating offsets
(which can only shift two parameters per team), so if this cannot beat production out
of sample, the in-fit version cannot either.

Prerequisite: research/probe_features.csv (regenerate with the Java --probe-export).
Run: python3 research/candidate2_confed_diagnostic.py
"""
import csv
import numpy as np
from collections import defaultdict

MIN_N = 15
CSV = "research/probe_features.csv"
CLS = {"home": 0, "draw": 1, "away": 2}


def brier(p, y):
    oh = np.zeros(3)
    oh[y] = 1.0
    return float(((p - oh) ** 2).sum())


def main():
    rows = list(csv.DictReader(open(CSV, encoding="utf-8")))
    for r in rows:
        r["y"] = CLS[r["outcome"]]
        r["P"] = np.array([float(r["p_home"]), float(r["p_draw"]), float(r["p_away"])])
        r["pair"] = (r["home_confed"], r["away_confed"])
        r["inter"] = (r["home_confed"] != r["away_confed"]
                      and bool(r["home_confed"]) and bool(r["away_confed"]))
    tours = sorted({r["tournament"] for r in rows})

    def run(scale):
        prod, adj, iprod, iadj = [], [], [], []
        for T in tours:
            tr = [r for r in rows if r["tournament"] != T]
            te = [r for r in rows if r["tournament"] == T]
            acc = defaultdict(lambda: [np.zeros(3), 0])
            for r in tr:
                if not r["inter"]:
                    continue
                oh = np.zeros(3)
                oh[r["y"]] = 1.0
                acc[r["pair"]][0] += oh - r["P"]
                acc[r["pair"]][1] += 1
            res = {k: v[0] / v[1] for k, v in acc.items() if v[1] >= MIN_N}
            for r in te:
                p = r["P"]
                a = p.copy()
                if r["inter"] and r["pair"] in res:
                    a = p + scale * res[r["pair"]]
                    a = np.clip(a, 1e-6, None)
                    a = a / a.sum()
                prod.append(brier(p, r["y"]))
                adj.append(brier(a, r["y"]))
                if r["inter"]:
                    iprod.append(brier(p, r["y"]))
                    iadj.append(brier(a, r["y"]))
        return np.mean(prod), np.mean(adj), np.mean(iprod), np.mean(iadj), len(iprod)

    print("=== Candidate 2 upper bound: LOTO per-confederation-pair residual correction ===")
    print(f"{'scale':>6} {'prod(all)':>10} {'adj(all)':>10} {'dAll':>8} | "
          f"{'prod(int)':>10} {'adj(int)':>10} {'dInter':>8}")
    for s in (0.25, 0.5, 1.0):
        pa, aa, pi, ai, ni = run(s)
        print(f"{s:>6} {pa:>10.4f} {aa:>10.4f} {aa - pa:>+8.4f} | "
              f"{pi:>10.4f} {ai:>10.4f} {ai - pi:>+8.4f}   (n_inter={ni})")
    print("(positive delta means the confederation correction made Brier worse out of sample)")


if __name__ == "__main__":
    main()
