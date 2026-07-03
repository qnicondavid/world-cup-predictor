#!/usr/bin/env python3
"""A4 feasibility probe: does leakage-clean availability carry signal the value prior misses?

Finding "A4" asks whether knowing which key players are injured/suspended at kickoff (a
pre-match-KNOWN, leakage-clean signal) improves the forecast beyond the squad market-value
prior. This is the cheap GO/NO-GO probe run before committing to the full multi-day scrape.

Logic: for each team depleted by a pre-match-known absence (pre-tournament rule-out, or a
specific-match absence) in WC2018/WC2022, look at the model's held-out predictions on that
team's affected matches and ask:
  (A) Are those matches unusually badly predicted? (if not, there is nothing to fix)
  (B) When wrong, did the value prior OVERRATE the depleted team (expected pts > actual)?
      An availability down-adjustment can only help if the model overrated them.
If the biggest, cleanest absences show the model UNDER-rating depleted teams (they
overperformed anyway), an availability cut would HURT -> NO-GO.

Reads only committed files (research/export_predictions_form.csv, data/market_values.csv);
absent-player values are annotated approximations used only to size each depletion.
"""
import csv, os

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_HERE, ".."))
PRED = os.path.join(ROOT, "research", "export_predictions_form.csv")
MV   = os.path.join(ROOT, "data", "market_values.csv")

# Leakage-clean pre-match-known absences (verified via ESPN/Al Jazeera/Yahoo pre-tournament
# injury reports). value_eur_approx = player's market value at the time (Transfermarkt-era
# figure, used only to size the depletion; approximate).
ABSENCES = {
    ("WC2022","France"):   {"players":[("Benzema",25e6),("Pogba",25e6),("Kante",20e6),
                                        ("Nkunku",60e6),("Kimpembe",45e6)], "matches":None},
    ("WC2022","Senegal"):  {"players":[("Mane",65e6)], "matches":None},
    ("WC2022","Portugal"): {"players":[("Jota",60e6)], "matches":None},
    ("WC2018","Egypt"):    {"players":[("Salah",130e6)], "matches":{"Uruguay"}},  # out match 1 only
    ("WC2018","Argentina"):{"players":[("Romero",7e6)], "matches":None},          # backup-tier GK
}

def load_team_values():
    v = {}
    for r in csv.DictReader(open(MV, encoding="utf-8")):
        v.setdefault(r["team"], {})[r["as_of"][:4]] = float(r["value_eur"])
    return v

def result_points(actual, is_home):
    if actual == "draw": return 1
    if (actual == "home") == is_home: return 3
    return 0

def brier(r):
    oh = {"home":(1,0,0),"draw":(0,1,0),"away":(0,0,1)}[r["actual"]]
    p = (float(r["p_home"]),float(r["p_draw"]),float(r["p_away"]))
    return sum((pi-oi)**2 for pi,oi in zip(p,oh))

def main():
    rows = [r for r in csv.DictReader(open(PRED, encoding="utf-8"))
            if r["tournament"] in ("WC2018","WC2022")]
    tvals = load_team_values()

    overall = {}
    for t in ("WC2018","WC2022"):
        b = [brier(r) for r in rows if r["tournament"]==t]
        overall[t] = sum(b)/len(b)

    print("=== A4 feasibility probe: availability vs the value prior (WC2018 + WC2022) ===\n")
    print(f"Overall mean multiclass Brier:  WC2018 {overall['WC2018']:.4f}   WC2022 {overall['WC2022']:.4f}")
    print("(depleted-team matches are 'unusually bad' only if their Brier exceeds this)\n")

    yr = {"WC2018":"2018","WC2022":"2022"}
    grand_over = 0.0; grand_matches = 0
    for (tour, team), info in ABSENCES.items():
        miss = sum(v for _,v in info["players"])
        sq = tvals.get(team,{}).get(yr[tour])
        frac = miss/sq if sq else float("nan")
        tm = [r for r in rows if r["tournament"]==tour and (r["home"]==team or r["away"]==team)]
        if info["matches"] is not None:
            tm = [r for r in tm if (r["away"] if r["home"]==team else r["home"]) in info["matches"]]
        exp_pts=act_pts=bsum=0.0
        detail=[]
        for r in tm:
            is_home = r["home"]==team
            pw = float(r["p_home"]) if is_home else float(r["p_away"])
            pd = float(r["p_draw"])
            ep = 3*pw + 1*pd
            ap = result_points(r["actual"], is_home)
            opp = r["away"] if is_home else r["home"]
            exp_pts+=ep; act_pts+=ap; bsum+=brier(r)
            detail.append(f"{opp:<14} exp{ep:.2f} act{ap} {'W' if ap==3 else 'D' if ap==1 else 'L'}")
        n=len(tm)
        over = exp_pts-act_pts
        mb = bsum/n if n else 0.0
        players = ", ".join(p for p,_ in info["players"])
        print(f"--- {tour} {team}  (out: {players})")
        print(f"    missing value ~EUR{miss/1e6:.0f}M / squad ~EUR{(sq or 0)/1e6:.0f}M = {frac*100:.0f}% of squad")
        print(f"    matches {n} | model expected pts {exp_pts:.2f} vs actual {act_pts:.0f} "
              f"| overrating {over:+.2f} | mean Brier {mb:.4f} vs tour {overall[tour]:.4f}")
        for d in detail: print(f"      {d}")
        print()
        grand_over += over; grand_matches += n

    print("=== verdict inputs ===")
    print(f"total depleted-team matches: {grand_matches}")
    print(f"net overrating (sum of expected-minus-actual pts across depleted teams): {grand_over:+.2f}")
    print("  >0  => model overrated depleted teams on net (availability cut MIGHT help)")
    print("  <0  => model UNDERrated depleted teams (they overperformed; availability cut would HURT)")

if __name__ == "__main__":
    main()
