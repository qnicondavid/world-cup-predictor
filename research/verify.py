"""
research/verify.py  -  Verification harness for the football-forecasting project.

Imports from goal_models.py without modifying it.
Run:  python3 research/verify.py            (uses data/results.csv by default)
      python3 research/verify.py <path>     (explicit CSV path)
"""

import sys, os, math
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from goal_models import load, DixonColes, EloDrawBaseline, mcb, outcome, Match

# ---------------------------------------------------------------------------
# 1. WINDOWS and collect_predictions
# ---------------------------------------------------------------------------
def enc(y, m, d):
    return y * 372 + m * 31 + d

WINDOWS = {
    "WC2006": (enc(2006, 6, 1), enc(2006, 7, 31)),
    "WC2010": (enc(2010, 6, 1), enc(2010, 7, 31)),
    "WC2014": (enc(2014, 6, 1), enc(2014, 7, 31)),
    "WC2018": (enc(2018, 6, 1), enc(2018, 7, 31)),
    "WC2022": (enc(2022, 11, 1), enc(2022, 12, 31)),
}


def _fit_window(args):
    """Picklable worker: fit one WC window and return records."""
    label, s, e, factory_name, factory_kwargs, train_matches, test_matches = args
    import math, sys, os
    _h = os.path.dirname(os.path.abspath(__file__))
    if _h not in sys.path:
        sys.path.insert(0, _h)
    from goal_models import DixonColes, EloDrawBaseline, outcome

    if factory_name == "DixonColes":
        mdl = DixonColes(**factory_kwargs)
        mdl.fit(train_matches, asof=s)
    elif factory_name == "EloDrawBaseline":
        mdl = EloDrawBaseline()
        mdl.fit(train_matches)
    else:
        raise ValueError(f"Unknown factory: {factory_name}")

    records = []
    for m in test_matches:
        p = list(mdl.wdl(m.home, m.away, m.neutral))
        s_p = sum(p)
        p = [v / s_p for v in p]
        assert all(math.isfinite(v) for v in p), f"Non-finite prob in {label}: {p}"
        assert abs(sum(p) - 1.0) < 1e-6, f"Probs don't sum to 1 in {label}: {sum(p)}"
        y = outcome(m)
        records.append(dict(tournament=label, home=m.home, away=m.away,
                            date=m.date, p=p, y=y))
    return label, records


def collect_predictions(factory, data, workers=2):
    """
    Collect per-match prediction records for all 5 WC windows.
    factory() -> fresh DixonColes or EloDrawBaseline instance.
    Returns list of record dicts in WINDOWS order.
    Each record: {tournament, home, away, date, p:[pH,pD,pA], y:int}
    p is normalised and validated (finite, sums to 1 within 1e-6).
    """
    probe = factory()
    if isinstance(probe, DixonColes):
        factory_name = "DixonColes"
        factory_kwargs = dict(
            half_life_years=math.log(2) / (probe.xi * 372),
            l2=probe.l2,
            bivariate=probe.bivariate,
        )
    elif isinstance(probe, EloDrawBaseline):
        factory_name = "EloDrawBaseline"
        factory_kwargs = {}
    else:
        factory_name = None
        factory_kwargs = {}

    tasks = []
    for label, (s, e) in WINDOWS.items():
        train = [m for m in data if m.date < s and m.date >= s - 12 * 372]
        test  = [m for m in data if s <= m.date <= e
                 and m.tournament.lower() == "fifa world cup"]
        if not test:
            print(f"  WARNING: no test matches for {label}", file=sys.stderr)
            continue
        if factory_name is None:
            # sequential fallback for unknown types
            mdl = factory()
            mdl.fit(train)
            recs = []
            for m in test:
                p = list(mdl.wdl(m.home, m.away, m.neutral))
                s_p = sum(p); p = [v / s_p for v in p]
                recs.append(dict(tournament=label, home=m.home, away=m.away,
                                 date=m.date, p=p, y=outcome(m)))
            tasks.append((label, recs))
            continue
        tasks.append((label, s, e, factory_name, factory_kwargs, train, test))

    if factory_name is None:
        records = []
        for label, recs in tasks:
            records.extend(recs)
        return records

    label_to_records = {}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_fit_window, t): t[0] for t in tasks}
        for fut in as_completed(futures):
            label, recs = fut.result()
            label_to_records[label] = recs

    records = []
    for label in WINDOWS:
        if label in label_to_records:
            records.extend(label_to_records[label])
    return records


# ---------------------------------------------------------------------------
# 2. brier / per_tournament_brier
# ---------------------------------------------------------------------------
def brier(records):
    if not records:
        return float("nan")
    return sum(mcb(r["p"], r["y"]) for r in records) / len(records)


def per_tournament_brier(records):
    groups = {}
    for r in records:
        groups.setdefault(r["tournament"], []).append(r)
    return {t: brier(recs) for t, recs in sorted(groups.items())}


# ---------------------------------------------------------------------------
# 3. Murphy decomposition
# ---------------------------------------------------------------------------
def murphy_decomposition(records, bins=10):
    """
    Summed-over-3-classes Murphy (REL/RES/UNC) decomposition.
    residual = (REL - RES + UNC) - brier; asserts |residual| < 0.03.
    Returns dict(reliability, resolution, uncertainty, brier, residual).
    """
    N = len(records)
    if N == 0:
        raise ValueError("Empty records")
    edges = np.linspace(0.0, 1.0, bins + 1)
    REL_total = RES_total = UNC_total = 0.0
    for c in range(3):
        preds = np.array([r["p"][c] for r in records])
        obs   = np.array([1.0 if r["y"] == c else 0.0 for r in records])
        obar  = obs.mean()
        UNC_total += obar * (1.0 - obar)
        REL_c = RES_c = 0.0
        for k in range(bins):
            lo_e, hi_e = edges[k], edges[k + 1]
            if k == bins - 1:
                mask = (preds >= lo_e) & (preds <= hi_e)
            else:
                mask = (preds >= lo_e) & (preds < hi_e)
            n_k = int(mask.sum())
            if n_k == 0:
                continue
            mean_pred_k = preds[mask].mean()
            mean_obs_k  = obs[mask].mean()
            REL_c += n_k * (mean_pred_k - mean_obs_k) ** 2
            RES_c += n_k * (mean_obs_k  - obar)       ** 2
        REL_total += REL_c / N
        RES_total += RES_c / N
    brier_val = brier(records)
    residual  = (REL_total - RES_total + UNC_total) - brier_val
    assert abs(residual) < 0.03, f"Murphy residual too large: {residual:.6f}"
    return dict(reliability=REL_total, resolution=RES_total,
                uncertainty=UNC_total, brier=brier_val, residual=residual)


# ---------------------------------------------------------------------------
# 4. block_bootstrap
# ---------------------------------------------------------------------------
def block_bootstrap(records, stat_fn, B=2000, seed=12345):
    """
    Resample distinct tournaments WITH replacement (5 draws of 5).
    Returns (point, lo, hi): point=stat_fn(records), lo/hi=2.5/97.5 pctiles.
    Uses a seeded numpy Generator for reproducibility.
    """
    point = stat_fn(records)
    tournament_groups = {}
    for r in records:
        tournament_groups.setdefault(r["tournament"], []).append(r)
    tournaments = sorted(tournament_groups.keys())
    T = len(tournaments)
    rng = np.random.default_rng(seed)
    boot_vals = []
    for _ in range(B):
        chosen = rng.choice(T, size=T, replace=True)
        pooled = []
        for idx in chosen:
            pooled.extend(tournament_groups[tournaments[idx]])
        if not pooled:
            continue
        boot_vals.append(stat_fn(pooled))
    boot_vals = np.array(boot_vals)
    lo = float(np.percentile(boot_vals, 2.5))
    hi = float(np.percentile(boot_vals, 97.5))
    return point, lo, hi


# ---------------------------------------------------------------------------
# 5. paired_delta
# ---------------------------------------------------------------------------
def _record_key(r):
    return (r["tournament"], r["home"], r["away"], r["date"])


def paired_delta(records_a, records_b):
    """
    Align A and B by (tournament, home, away, date).
    delta_i = mcb(A.p, A.y) - mcb(B.p, B.y).
    Asserts A and B cover identical match keys.
    Returns dict(mean_delta, ci_lo, ci_hi, per_tournament).
    """
    keys_a = {_record_key(r): r for r in records_a}
    keys_b = {_record_key(r): r for r in records_b}
    only_a = set(keys_a) - set(keys_b)
    only_b = set(keys_b) - set(keys_a)
    if only_a or only_b:
        raise AssertionError(
            f"Match key mismatch: only_in_A={len(only_a)}, only_in_B={len(only_b)}")
    paired = []
    for k in sorted(keys_a.keys()):
        ra, rb = keys_a[k], keys_b[k]
        d = mcb(ra["p"], ra["y"]) - mcb(rb["p"], rb["y"])
        paired.append(dict(tournament=ra["tournament"], home=ra["home"],
                           away=ra["away"], date=ra["date"],
                           p=[d], y=0, _delta=d))

    def mean_delta_fn(recs):
        return float(np.mean([r["_delta"] for r in recs]))

    point, lo, hi = block_bootstrap(paired, mean_delta_fn)
    per_tournament = {}
    for r in paired:
        per_tournament.setdefault(r["tournament"], []).append(r["_delta"])
    per_tournament = {t: float(np.mean(v)) for t, v in sorted(per_tournament.items())}
    return dict(mean_delta=point, ci_lo=lo, ci_hi=hi, per_tournament=per_tournament)


# ---------------------------------------------------------------------------
# 6. loto_cv_select
# ---------------------------------------------------------------------------
def loto_cv_select(config_records):
    """
    Leave-one-tournament-out model selection on precomputed prediction tables.

    config_records: dict { config_name -> list_of_records }
    For each held-out tournament t:
        choose the config with lowest pooled brier on the other 4 tournaments;
        report its brier on t.
    Returns (per_heldout, pooled_heldout_brier).
      per_heldout: { tournament -> (chosen_config, heldout_brier) }
    """
    tournaments = sorted({r["tournament"]
                          for recs in config_records.values()
                          for r in recs})
    by_ct = {}
    for cfg, recs in config_records.items():
        for r in recs:
            by_ct.setdefault((cfg, r["tournament"]), []).append(r)
    per_heldout = {}
    for held_t in tournaments:
        other_t = [t for t in tournaments if t != held_t]
        best_cfg, best_val = None, float("inf")
        for cfg in config_records:
            other_recs = []
            for t in other_t:
                other_recs.extend(by_ct.get((cfg, t), []))
            if not other_recs:
                continue
            b = brier(other_recs)
            if b < best_val:
                best_val = b; best_cfg = cfg
        held_recs = by_ct.get((best_cfg, held_t), [])
        per_heldout[held_t] = (best_cfg, brier(held_recs))
    pooled = float(np.mean([v for _, v in per_heldout.values()]))
    return per_heldout, pooled


# ---------------------------------------------------------------------------
# 7. draw_diagnostics
# ---------------------------------------------------------------------------
def draw_diagnostics(records):
    n = len(records)
    draw_count = sum(1 for r in records if r["y"] == 1)
    return dict(
        draw_base_rate=draw_count / n if n else float("nan"),
        mean_pred_draw=float(np.mean([r["p"][1] for r in records])) if n else float("nan"),
        n_draw_argmax=sum(1 for r in records if r["p"].index(max(r["p"])) == 1),
        n=n,
    )


# ---------------------------------------------------------------------------
# 8. run_self_tests
# ---------------------------------------------------------------------------
def run_self_tests(dc_records, data):
    """
    Five self-tests with PASS/FAIL output.
    (a) perfect-calibration synthetic set -> REL < 0.01
    (b) constant predictions = base rates -> RES < 0.01
    (c) Murphy residual < 0.03 on real DC predictions
    (d) determinism: collect twice yields identical results
    (e) bootstrap point estimate lies within [lo, hi]
    """
    all_pass = True

    def _check(name, cond, extra=""):
        nonlocal all_pass
        status = "PASS" if cond else "FAIL"
        if not cond:
            all_pass = False
        print(f"  {status}  {name}" + (f"  {extra}" if extra else ""))

    print("\n=== Self-tests ===")

    # (a) Perfect calibration -> REL < 0.01
    rng = np.random.default_rng(42)
    N_syn = 3000
    probs_syn = rng.dirichlet(np.ones(3), size=N_syn)
    outcomes_syn = np.array([rng.choice(3, p=p) for p in probs_syn])
    syn_records = [
        dict(tournament="SYN", home=f"H{i}", away=f"A{i}",
             date=i, p=list(probs_syn[i]), y=int(outcomes_syn[i]))
        for i in range(N_syn)
    ]
    dec_syn = murphy_decomposition(syn_records)
    _check("(a) perfect-calibration: REL < 0.01",
           dec_syn["reliability"] < 0.01,
           f"REL={dec_syn['reliability']:.4f}")

    # (b) Constant predictions -> RES < 0.01
    counts = np.zeros(3)
    for r in dc_records:
        counts[r["y"]] += 1
    base_rates = (counts / counts.sum()).tolist()
    const_records = [
        dict(tournament=r["tournament"], home=r["home"], away=r["away"],
             date=r["date"], p=base_rates[:], y=r["y"])
        for r in dc_records
    ]
    dec_const = murphy_decomposition(const_records)
    _check("(b) constant-pred: RES < 0.01",
           dec_const["resolution"] < 0.01,
           f"RES={dec_const['resolution']:.4f}")

    # (c) Reconstruction residual < 0.03
    dec_dc = murphy_decomposition(dc_records)
    _check("(c) DC decomposition residual < 0.03",
           abs(dec_dc["residual"]) < 0.03,
           f"residual={dec_dc['residual']:.6f}")

    # (d) Determinism: re-collect predictions and compare bit-for-bit
    dc_records_2 = collect_predictions(DixonColes, data, workers=2)
    b1 = brier(dc_records)
    b2 = brier(dc_records_2)
    length_ok = len(dc_records_2) == len(dc_records)
    brier_ok  = abs(b2 - b1) == 0.0
    keys_1 = {_record_key(r): r for r in dc_records}
    keys_2 = {_record_key(r): r for r in dc_records_2}
    probs_ok = (set(keys_1) == set(keys_2) and
                all(all(keys_1[k]["p"][c] == keys_2[k]["p"][c]
                        for c in range(3))
                    for k in keys_1))
    # Additional structural check: finite and sum to 1
    p_sum_ok = all(abs(sum(r["p"]) - 1.0) < 1e-6 for r in dc_records)
    nan_ok   = all(all(math.isfinite(v) for v in r["p"]) for r in dc_records)
    det_ok = length_ok and brier_ok and probs_ok and p_sum_ok and nan_ok
    _check("(d) determinism: collect twice identical",
           det_ok,
           f"b1={b1:.6f} b2={b2:.6f}")

    # (e) Bootstrap point in [lo, hi]
    pt, lo, hi = block_bootstrap(dc_records, brier)
    _check("(e) bootstrap: point lies in [lo, hi]",
           lo <= pt <= hi,
           f"lo={lo:.4f} pt={pt:.4f} hi={hi:.4f}")

    print(f"  [{'ALL PASS' if all_pass else 'SOME TESTS FAILED'}]")
    return all_pass


# ---------------------------------------------------------------------------
# 9. main
# ---------------------------------------------------------------------------
def main(csv_path=None):
    if csv_path is None:
        repo_root = os.path.dirname(_HERE)
        csv_path = os.path.join(repo_root, "data", "results.csv")

    print(f"Loading data from {csv_path} ...")
    data = load(csv_path)
    print(f"  {len(data):,} matches loaded  "
          f"(dates {data[0].date} .. {data[-1].date})")

    # DC predictions: 5 WC windows in parallel (2 workers)
    print("\nCollecting Dixon-Coles predictions ...")
    dc_records = collect_predictions(DixonColes, data, workers=2)
    print(f"  {len(dc_records)} test matches collected")

    print("\n--- Per-tournament Brier (Dixon-Coles) ---")
    ptb = per_tournament_brier(dc_records)
    for t, b in ptb.items():
        print(f"  {t}: {b:.4f}")
    combined = brier(dc_records)
    print(f"  COMBINED ({len(dc_records)} matches): {combined:.4f}  [expected ~0.598]")

    print("\n--- Murphy Decomposition (Dixon-Coles) ---")
    dec = murphy_decomposition(dc_records)
    print(f"  Reliability:   {dec['reliability']:.4f}")
    print(f"  Resolution:    {dec['resolution']:.4f}")
    print(f"  Uncertainty:   {dec['uncertainty']:.4f}")
    print(f"  Brier (check): {dec['brier']:.4f}")
    print(f"  Residual:      {dec['residual']:.6f}  (|res|<0.03 asserted)")

    print("\n--- Block-bootstrap 95% CI on combined Brier (Dixon-Coles) ---")
    pt, lo, hi = block_bootstrap(dc_records, brier)
    print(f"  Point: {pt:.4f}  95% CI: [{lo:.4f}, {hi:.4f}]")

    # Elo predictions: EloDrawBaseline is fast (running_gaps, no optimizer)
    print("\nCollecting EloDrawBaseline predictions ...")
    elo_records = collect_predictions(EloDrawBaseline, data, workers=2)
    print(f"  {len(elo_records)} test matches collected")

    print("\n--- DC vs EloDrawBaseline paired delta ---")
    pd_result = paired_delta(dc_records, elo_records)
    print(f"  Mean delta (DC - Elo): {pd_result['mean_delta']:+.4f}  (negative = DC is better)")
    print(f"  95% CI: [{pd_result['ci_lo']:+.4f}, {pd_result['ci_hi']:+.4f}]")
    print("  Per-tournament signs:")
    for t, d in pd_result["per_tournament"].items():
        direction = "DC better" if d < 0 else "Elo better"
        print(f"    {t}: {d:+.4f}  ({direction})")

    print("\n--- Draw Diagnostics (Dixon-Coles) ---")
    dd = draw_diagnostics(dc_records)
    print(f"  Draw base rate:           {dd['draw_base_rate']:.3f}")
    print(f"  Mean predicted draw prob: {dd['mean_pred_draw']:.3f}")
    print(f"  Matches where draw is argmax: {dd['n_draw_argmax']} / {dd['n']}")

    # LOTO demo: reuse hl=2.0 (dc_records), add hl=1.5 and hl=3.0.
    # Use workers=1 to avoid memory pressure from nested subprocess pools.
    print("\n--- LOTO CV select demo (half_life_years in [1.5, 2.0, 3.0]) ---")
    config_recs = {"hl2.0": dc_records}
    for name, hl in [("hl1.5", 1.5), ("hl3.0", 3.0)]:
        print(f"  Fitting DixonColes(half_life_years={hl}) ...")
        config_recs[name] = collect_predictions(
            lambda hl=hl: DixonColes(half_life_years=hl), data, workers=1
        )

    per_heldout, pooled_heldout = loto_cv_select(config_recs)
    print("\n  LOTO results:")
    for t, (chosen, hb) in sorted(per_heldout.items()):
        print(f"    held-out {t}: chosen={chosen}  heldout_brier={hb:.4f}")
    print(f"  Pooled held-out Brier: {pooled_heldout:.4f}")

    run_self_tests(dc_records, data)


# ---------------------------------------------------------------------------
# 10. score_export  (bridge consumer for Java --verify-export CSV)
# ---------------------------------------------------------------------------
def expected_calibration_error(records, bins=10):
    """Count-weighted gap between predicted probability and observed frequency,
    pooling all three outcomes one-vs-rest into ``bins`` equal-width buckets.
    Same definition as the Java Calibration.expectedCalibrationError, applied to
    the final (form + draw-transfer) predictions in the export."""
    sum_pred = [0.0] * bins
    sum_hit = [0.0] * bins
    count = [0] * bins
    for r in records:
        for i, p in enumerate(r["p"]):
            b = min(bins - 1, int(p * bins))
            sum_pred[b] += p
            sum_hit[b] += 1.0 if i == r["y"] else 0.0
            count[b] += 1
    total = sum(count)
    if total == 0:
        return 0.0
    ece = 0.0
    for b in range(bins):
        if count[b] == 0:
            continue
        ece += count[b] / total * abs(sum_pred[b] / count[b] - sum_hit[b] / count[b])
    return ece


def score_export(csv_path):
    """
    Load a CSV written by the Java --verify-export bridge and print Brier metrics.

    Expected columns: tournament,home,away,date,p_home,p_draw,p_away,actual
    actual in {home, draw, away}  ->  mapped to y in {0, 1, 2}.
    """
    import csv as csv_mod
    actual_map = {"home": 0, "draw": 1, "away": 2}
    records = []
    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv_mod.DictReader(fh)
        for row in reader:
            y_str = row["actual"].strip()
            if y_str not in actual_map:
                raise ValueError(f"Unknown actual value: {y_str!r}")
            records.append(dict(
                tournament=row["tournament"].strip(),
                home=row["home"].strip(),
                away=row["away"].strip(),
                date=row["date"].strip(),
                p=[float(row["p_home"]), float(row["p_draw"]), float(row["p_away"])],
                y=actual_map[y_str],
            ))
    print(f"Loaded {len(records)} records from {csv_path}")
    if not records:
        print("No records; nothing to score.")
        return

    print(f"\n--- Combined Brier ---")
    combined = brier(records)
    print(f"  Combined ({len(records)} matches): {combined:.4f}")

    print("\n--- Per-tournament Brier ---")
    ptb = per_tournament_brier(records)
    for t, b in ptb.items():
        print(f"  {t}: {b:.4f}")

    print("\n--- Murphy Decomposition ---")
    dec = murphy_decomposition(records)
    print(f"  Reliability:   {dec['reliability']:.4f}")
    print(f"  Resolution:    {dec['resolution']:.4f}")
    print(f"  Uncertainty:   {dec['uncertainty']:.4f}")
    print(f"  Brier (check): {dec['brier']:.4f}")
    print(f"  Residual:      {dec['residual']:.6f}")

    print("\n--- Block-bootstrap 95% CI on combined Brier ---")
    pt, lo, hi = block_bootstrap(records, brier)
    print(f"  Point: {pt:.4f}  95% CI: [{lo:.4f}, {hi:.4f}]")

    print("\n--- Expected calibration error (10 bins, one-vs-rest) ---")
    print(f"  ECE: {expected_calibration_error(records, 10):.4f}")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--score":
        score_export(sys.argv[2])
    else:
        path = sys.argv[1] if len(sys.argv) > 1 else None
        main(path)
