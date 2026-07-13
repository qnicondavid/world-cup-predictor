"""
Residual probe for the production football outcome model.

Purpose: this is a DETECTOR, not a shipper. It asks: does the production
model (p_home, p_draw, p_away) leave any exploitable structure in the
remaining features, when evaluated honestly out of sample? It is not meant
to produce a model we would ever deploy.

Leakage discipline:
- Grouping / folding is done by tournament (leave-one-tournament-out, LOTO),
  so no match from a held-out tournament ever appears in that fold's
  training data. This matters because matches inside the same tournament
  share context (squads, form, host country) that would leak information
  across a naive random split.
- A label-shuffle canary is run through the exact same LOTO loop. If the
  canary (trained on shuffled labels) scores anywhere near the real probe,
  that is a strong signal of a leakage bug somewhere in the pipeline
  (e.g. training rows that are not actually independent of the test row).
- All randomness is seeded (random_state=0) so this script is deterministic
  and reproducible.
"""

import sys
import numpy as np
import pandas as pd

from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.preprocessing import OrdinalEncoder
from sklearn.inspection import permutation_importance

RANDOM_STATE = 0
CSV_PATH = "research/probe_features.csv"
OUT_PATH = "research/probe_results.txt"

CLASS_ORDER = ["home", "draw", "away"]  # k = 0, 1, 2 in this order
CLASS_TO_INT = {c: i for i, c in enumerate(CLASS_ORDER)}

NUMERIC_FEATURES = [
    "p_home", "p_draw", "p_away",
    "rate_gap", "total", "value_gap", "form_resid_gap",
    "is_inter", "rest_days_diff", "neutral",
]
CATEGORICAL_FEATURES = ["home_confed", "away_confed"]
ALL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

MODEL_PARAMS = dict(
    max_depth=3,
    max_iter=200,
    learning_rate=0.05,
    random_state=RANDOM_STATE,
)


def brier(P, y):
    """
    Multiclass Brier score.
    P: array (n_rows, 3) of predicted probabilities, columns ordered
       [home, draw, away] = [0, 1, 2].
    y: array (n_rows,) of integer labels in {0, 1, 2}.
    Returns the mean over rows of sum_k (P[row,k] - onehot(y)[k])^2.
    """
    P = np.asarray(P, dtype=float)
    y = np.asarray(y, dtype=int)
    n_rows, n_classes = P.shape
    onehot = np.zeros((n_rows, n_classes), dtype=float)
    onehot[np.arange(n_rows), y] = 1.0
    return float(np.mean(np.sum((P - onehot) ** 2, axis=1)))


def reindex_proba(proba, classes_, n_classes=3):
    """
    HistGradientBoostingClassifier.classes_ reflects whatever integer
    labels were present in the training fold, in sorted order, not
    necessarily [0, 1, 2] if a class was entirely absent from a fold.
    This reindexes predict_proba output into a fixed [0, 1, 2] column
    order, filling 0.0 for any class missing from that particular fold.
    """
    out = np.zeros((proba.shape[0], n_classes), dtype=float)
    for col_idx, cls in enumerate(classes_):
        out[:, int(cls)] = proba[:, col_idx]
    return out


def main():
    log_lines = []

    def log(msg=""):
        print(msg)
        log_lines.append(str(msg))

    # ---------------------------------------------------------------
    # 1. Load and prepare data
    # ---------------------------------------------------------------
    df = pd.read_csv(CSV_PATH, keep_default_na=True, na_values=[""])
    n_rows = len(df)
    log("=== Residual Probe over production football model ===")
    log(f"Loaded {n_rows} rows from {CSV_PATH}")

    missing_outcome = df["outcome"].isna().sum()
    if missing_outcome:
        log(f"WARNING: {missing_outcome} rows have missing outcome, dropping them.")
        df = df.dropna(subset=["outcome"]).reset_index(drop=True)
        n_rows = len(df)

    y = df["outcome"].map(CLASS_TO_INT).values
    if np.any(pd.isna(df["outcome"].map(CLASS_TO_INT))):
        bad = df.loc[df["outcome"].map(lambda v: v not in CLASS_TO_INT), "outcome"].unique()
        raise ValueError(f"Unexpected outcome values not in {CLASS_ORDER}: {bad}")
    y = y.astype(int)

    # numeric features: empty string -> NaN already via na_values=[""]
    for col in NUMERIC_FEATURES:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # categorical features: empty -> "UNK", then ordinal-encode to integers
    for col in CATEGORICAL_FEATURES:
        df[col] = df[col].fillna("UNK").astype(str)
        df.loc[df[col].str.strip() == "", col] = "UNK"

    ordinal_encoder = OrdinalEncoder(dtype=np.float64)
    cat_encoded = ordinal_encoder.fit_transform(df[CATEGORICAL_FEATURES])
    for i, col in enumerate(CATEGORICAL_FEATURES):
        df[col] = cat_encoded[:, i]

    X = df[ALL_FEATURES].values
    cat_col_indices = [ALL_FEATURES.index(c) for c in CATEGORICAL_FEATURES]

    tournaments = df["tournament"].values
    unique_tournaments = pd.unique(tournaments)
    n_tournaments = len(unique_tournaments)
    log(f"Found {n_tournaments} distinct tournaments (fold groups).")

    # production baseline probabilities, columns already [home, draw, away]
    P_prod = df[["p_home", "p_draw", "p_away"]].values.astype(float)
    n_missing_prod = np.isnan(P_prod).sum()
    if n_missing_prod:
        log(f"WARNING: {n_missing_prod} NaN values found in production probability columns.")

    # ---------------------------------------------------------------
    # 2. Production baseline Brier
    # ---------------------------------------------------------------
    prod_brier = brier(P_prod, y)
    log("")
    log(f"Production model Brier score: {prod_brier:.4f}")

    # ---------------------------------------------------------------
    # 3. Base-rate (no-skill) Brier
    # ---------------------------------------------------------------
    class_counts = np.bincount(y, minlength=3)
    class_freq = class_counts / class_counts.sum()
    P_base = np.tile(class_freq, (n_rows, 1))
    base_brier = brier(P_base, y)
    log(f"Base-rate (global class frequency) Brier score: {base_brier:.4f}")
    log(f"  Global class frequencies (home, draw, away): "
        f"{class_freq[0]:.4f}, {class_freq[1]:.4f}, {class_freq[2]:.4f}")

    # ---------------------------------------------------------------
    # 4. Probe held-out Brier via leave-one-tournament-out (LOTO)
    # ---------------------------------------------------------------
    def try_hgb(**overrides):
        params = dict(MODEL_PARAMS)
        params.update(overrides)
        return params

    def make_model(categorical_features=None):
        params = try_hgb()
        if categorical_features is not None:
            try:
                return HistGradientBoostingClassifier(
                    categorical_features=categorical_features, **params
                )
            except TypeError:
                # older sklearn without categorical_features support
                return HistGradientBoostingClassifier(**params)
        return HistGradientBoostingClassifier(**params)

    # detect whether categorical_features kwarg is supported at all
    supports_categorical = True
    try:
        HistGradientBoostingClassifier(categorical_features=cat_col_indices, **MODEL_PARAMS)
    except TypeError:
        supports_categorical = False
        log("NOTE: installed sklearn version rejects categorical_features kwarg; "
            "falling back to plain integer-coded categoricals as numeric features.")

    P_probe_holdout = np.zeros((n_rows, 3), dtype=float)
    P_canary_holdout = np.zeros((n_rows, 3), dtype=float)
    filled_mask = np.zeros(n_rows, dtype=bool)

    isolation_ok_all_folds = True
    fold_sizes = []

    rng_canary = np.random.RandomState(RANDOM_STATE)

    for fold_i, T in enumerate(unique_tournaments):
        test_mask = tournaments == T
        train_mask = ~test_mask

        # explicit per-fold isolation check: T must not appear in training slice
        if T in set(tournaments[train_mask]):
            isolation_ok_all_folds = False
            log(f"ISOLATION FAILURE on fold {T}: tournament leaked into training slice.")

        X_train, y_train = X[train_mask], y[train_mask]
        X_test = X[test_mask]
        fold_sizes.append(int(test_mask.sum()))

        if X_train.shape[0] == 0 or X_test.shape[0] == 0:
            log(f"WARNING: fold {T} has empty train or test slice, skipping.")
            continue

        # --- real probe model ---
        model = make_model(categorical_features=cat_col_indices if supports_categorical else None)
        model.fit(X_train, y_train)
        proba = model.predict_proba(X_test)
        proba = reindex_proba(proba, model.classes_)
        P_probe_holdout[test_mask] = proba

        # --- leakage canary: same fold, shuffled TRAIN labels only ---
        y_train_shuffled = y_train.copy()
        perm = rng_canary.permutation(len(y_train_shuffled))
        y_train_shuffled = y_train_shuffled[perm]

        canary_model = make_model(categorical_features=cat_col_indices if supports_categorical else None)
        canary_model.fit(X_train, y_train_shuffled)
        canary_proba = canary_model.predict_proba(X_test)
        canary_proba = reindex_proba(canary_proba, canary_model.classes_)
        P_canary_holdout[test_mask] = canary_proba

        filled_mask[test_mask] = True

    if not np.all(filled_mask):
        n_unfilled = np.sum(~filled_mask)
        log(f"WARNING: {n_unfilled} rows never received a held-out prediction "
            f"(likely from a skipped empty fold). Excluding them from pooled Brier.")

    pooled_idx = np.where(filled_mask)[0]
    probe_brier = brier(P_probe_holdout[pooled_idx], y[pooled_idx])
    canary_brier = brier(P_canary_holdout[pooled_idx], y[pooled_idx])

    delta = prod_brier - probe_brier

    log("")
    log(f"Min / max fold size across {n_tournaments} tournaments: "
        f"{min(fold_sizes)} / {max(fold_sizes)}")
    small_folds = [(t, s) for t, s in zip(unique_tournaments, fold_sizes) if s < 5]
    if small_folds:
        log(f"NOTE: {len(small_folds)} folds have fewer than 5 rows "
            f"(smallest test slices, may be noisy): {small_folds[:10]}")

    log("")
    log(f"Probe LOTO held-out Brier score: {probe_brier:.4f}")
    log(f"Delta (production - probe): {delta:+.4f}  "
        f"({'probe better' if delta > 0 else 'production better or tied'})")

    # ---------------------------------------------------------------
    # 5. Leakage canary result and PASS/FAIL
    # ---------------------------------------------------------------
    log("")
    log(f"Leakage canary Brier score (shuffled train labels): {canary_brier:.4f}")
    canary_pass = canary_brier > probe_brier + 0.01
    log(f"Canary check: {'PASS' if canary_pass else 'FAIL'} "
        f"(expect canary_brier > probe_brier + 0.01; "
        f"canary={canary_brier:.4f}, probe={probe_brier:.4f}, "
        f"threshold={probe_brier + 0.01:.4f})")
    if not canary_pass:
        log("WARNING: canary did not clear the threshold. This suggests possible "
            "leakage or a bug in the fold construction, and the probe LOTO Brier "
            "above should not be trusted until investigated.")
    log(f"For reference, a leakage-free canary is expected to land near the "
        f"base-rate Brier of about {base_brier:.4f} (typical healthy range "
        f"roughly 0.62 to 0.667).")

    # ---------------------------------------------------------------
    # 6. Per-fold sanity assertion
    # ---------------------------------------------------------------
    log("")
    assert isolation_ok_all_folds, "Per-fold tournament isolation check failed, see log above."
    log(f"Per-fold isolation check: PASSED for all {n_tournaments} folds "
        f"(held-out tournament never appeared in its own training slice).")

    # ---------------------------------------------------------------
    # 7. SHAP attribution (or permutation importance fallback)
    # ---------------------------------------------------------------
    log("")
    log("=== Feature attribution (fit on ALL rows, for interpretation only) ===")

    shap_lines = []
    full_model = make_model(categorical_features=cat_col_indices if supports_categorical else None)
    full_model.fit(X, y)

    shap_available = True
    try:
        import shap  # noqa: F401
    except ImportError:
        shap_available = False

    ranking = None
    method_used = None

    if shap_available:
        try:
            import shap
            try:
                explainer = shap.TreeExplainer(full_model)
                shap_values = explainer.shap_values(X)
            except Exception:
                explainer = shap.Explainer(full_model, X)
                shap_out = explainer(X)
                # shap_out.values shape may be (n, n_features, n_classes) or list
                shap_values = shap_out.values

            # normalize shap_values into a list of per-class (n, n_features) arrays
            if isinstance(shap_values, list):
                class_arrays = shap_values
            elif isinstance(shap_values, np.ndarray) and shap_values.ndim == 3:
                # could be (n, n_features, n_classes) or (n_classes, n, n_features)
                if shap_values.shape[-1] == 3:
                    class_arrays = [shap_values[:, :, k] for k in range(3)]
                elif shap_values.shape[0] == 3:
                    class_arrays = [shap_values[k] for k in range(3)]
                else:
                    class_arrays = [shap_values]
            else:
                class_arrays = [shap_values]

            mean_abs_total = np.zeros(len(ALL_FEATURES), dtype=float)
            for arr in class_arrays:
                mean_abs_total += np.mean(np.abs(arr), axis=0)

            ranking = sorted(
                zip(ALL_FEATURES, mean_abs_total), key=lambda p: p[1], reverse=True
            )
            method_used = "SHAP (mean |value| summed across classes)"
        except Exception as e:
            log(f"SHAP computation failed ({type(e).__name__}: {e}); "
                f"falling back to permutation importance.")
            shap_available = False

    if not shap_available or ranking is None:
        log("SHAP unavailable" if not shap_available else "SHAP failed, using fallback")
        perm_result = permutation_importance(
            full_model, X, y, n_repeats=10, random_state=RANDOM_STATE, scoring="neg_brier_score"
        ) if False else permutation_importance(
            full_model, X, y, n_repeats=10, random_state=RANDOM_STATE
        )
        ranking = sorted(
            zip(ALL_FEATURES, perm_result.importances_mean), key=lambda p: p[1], reverse=True
        )
        method_used = "permutation_importance (mean decrease in accuracy, n_repeats=10)"

    log(f"Attribution method: {method_used}")
    log("Top 12 features:")
    for rank_i, (feat, val) in enumerate(ranking[:12], start=1):
        line = f"  {rank_i:2d}. {feat:<18s} {val:.6f}"
        log(line)
        shap_lines.append(line)

    # ---------------------------------------------------------------
    # 8. Write plaintext summary
    # ---------------------------------------------------------------
    summary = []
    summary.append("Residual Probe Results Summary")
    summary.append("===============================")
    summary.append(f"Rows used: {n_rows}, tournaments (fold groups): {n_tournaments}")
    summary.append("")
    summary.append(f"Production model Brier: {prod_brier:.4f}")
    summary.append(f"Base-rate Brier: {base_brier:.4f}")
    summary.append(f"Probe LOTO Brier: {probe_brier:.4f}")
    summary.append(f"Delta (production - probe): {delta:+.4f}")
    summary.append("")
    summary.append(f"Leakage canary Brier: {canary_brier:.4f}")
    summary.append(f"Canary check: {'PASS' if canary_pass else 'FAIL'} "
                    f"(threshold: probe_brier + 0.01 = {probe_brier + 0.01:.4f})")
    summary.append("")
    summary.append(f"Per-fold isolation check: PASSED for all {n_tournaments} folds")
    summary.append("")
    summary.append(f"Attribution method: {method_used}")
    summary.append("Top 12 features:")
    summary.extend(shap_lines)
    summary.append("")
    summary.append("Read: " + (
        "the probe finds exploitable structure beyond production probabilities."
        if delta > 0.005 and canary_pass
        else "no material exploitable structure detected beyond production probabilities."
    ))

    with open(OUT_PATH, "w") as f:
        f.write("\n".join(summary) + "\n")

    log("")
    log(f"Summary written to {OUT_PATH}")


if __name__ == "__main__":
    main()
