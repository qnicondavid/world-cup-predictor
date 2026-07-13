# Phase 3 results

Outcome of the pre-registered research bets in notes/model/BRIER_PLAN.md, gated on the expanded surface built in Phase 1. This file records what was measured, so each result is on the record with numbers.

Deltas below are paired per-match Brier against the shipped model. Where a delta is quoted as an improvement it means the variant has the lower Brier; the 95 percent intervals are tournament-block bootstraps (each edition one block, B = 2000, seeded), so they reproduce exactly.

## Candidate 4: opponent-adjusted recent-form residual

Pre-registered in research/phase3_candidate4_preregistration.md before any result was seen.

The shipped form nudge (FormAdjuster, GA(5), lambda 0.20) averages the raw goals a team conceded over its last five matches. That figure is confounded by schedule strength: conceding to a strong side and a weak side count the same. Candidate 4 changes one thing, the per-match quantity in the average, from raw goals conceded to the opponent-adjusted residual (what the fitted model expected the team to concede against that specific opponent, minus what it actually conceded), from the same per-window value-adjusted strength used for prediction. Everything else about the nudge is held identical to the shipped feature. The draw-transfer alpha stays fixed at 0.21.

Wiring check: at lambda 0 the export reproduces expanded_predictions_l000.csv byte for byte (confirmed with cmp), so the pipeline changes nothing except through the feature.

### The feature is genuinely better than the raw one

| variant | expanded Brier (2,180) | World Cup Brier (320) |
|---|---|---|
| shipped raw, lambda 0.20 | 0.5623 | 0.5441 |
| residual, lambda 0.20 | 0.5606 | 0.5448 |
| residual, lambda 0.40 | 0.5603 | 0.5429 |
| residual, lambda 0.60 | 0.5621 | 0.5414 |
| residual, lambda 0.80 | 0.5657 | 0.5424 |

The residual feature beats the shipped raw feature on the expanded surface at every operating point from 0.20 to 0.60, with the expanded optimum at lambda 0.40 (0.5603 against 0.5623). It also removed the cross-surface divergence that killed the raw feature in Phase 1: the raw feature's World Cup optimum (lambda 0.60) was near the expanded surface's worst point, while the residual feature's expanded and World Cup optima both sit in the 0.40 to 0.60 range. That is exactly what removing the schedule confound was meant to do.

### The pre-registered primary comparison clears the expanded gate

Residual at lambda 0.20 against the shipped raw feature at lambda 0.20, on the primary expanded surface: paired mean improvement +0.0017, block-bootstrap 95 percent interval [+0.0004, +0.0030], which excludes zero. This is the first candidate in the campaign to clear the primary expanded gate. The improvement concentrates in intra-confederation matches (+0.0024) where recent form is comparable, and is roughly neutral on inter-confederation matches (-0.0005), a sensible and interpretable locus.

### It still does not ship

The frozen ship rule requires all three conditions, evaluated at the leave-one-tournament-out-selected lambda.

Leave-one-tournament-out selection over the residual grid on the expanded surface picks lambda 0.40 in 69 of 70 folds, with an honest pooled Brier of 0.5617 against the shipped 0.5623. So the honest out-of-sample improvement of sweeping the residual lambda is real but small, about 0.0006.

At that selected lambda 0.40 the ship rule fails:

1. Expanded improvement, interval excludes zero. Fails. The paired improvement is +0.0020, but its interval is [-0.0001, +0.0042], which grazes zero. The interval only excludes zero at lambda 0.20, which the selection does not pick.

2. World Cup gate preserved, no tournament past the noise floor. Fails. At lambda 0.40 the 2022 World Cup regresses by 0.0085, well past the 0.005 floor; at lambda 0.20 the pooled World Cup delta is a touch negative (-0.0007) and 2006 regresses by 0.0054, just past the floor.

3. Grid consistency. Partly. The honest pooled Brier (0.5617) does beat the shipped feature (0.5623), but the selected lambda's paired interval does not exclude zero, so the second half of the condition fails.

### Verdict

Candidate 4 does not ship, and the form channel is closed as the plan pre-committed. The result is the strongest of the campaign and worth stating plainly: the opponent-adjustment is the correct idea. The residual feature beats the raw feature, it clears the primary expanded gate at the shipped nudge strength, and it fixed the cross-surface divergence. What defeats it is size, not direction. The honest improvement (0.0006 to 0.0017 depending on how it is measured) sits right at the edge of what even the 2,180-match surface can certify, and the leave-one-tournament-out selection reaches for the larger nudge where the interval touches zero and the World Cup variance grows. This is the plan's own thesis confirmed: the binding constraint is statistical power, not idea supply. The shipped raw GA(5) at lambda 0.20 stays as the last word on recent form.

## Reproduction

    mvn -q compile
    mvn -q exec:java "-Dexec.mainClass=com.david.worldcup.Main" "-Dexec.args=--expanded-export-formresid=0.00"
    (repeat for 0.20, 0.40, 0.60, 0.80)
    cmp research/expanded_predictions_formresid_l000.csv research/expanded_predictions_l000.csv
    python research/verify.py --expanded-paired research/expanded_predictions_l020.csv research/expanded_predictions_formresid_l020.csv

The identity check must pass before any gate number is trusted. The bootstrap is seeded, so every interval reproduces exactly, and the paired deltas were confirmed in a second environment against the same CSV files.

## Candidate 5: learned residual probe

Candidate 5 is a detector, not a shippable change. It asks one question: after the value prior, the form nudge, and the draw transfer, does any structure remain that a flexible learner could exploit? If the answer is no, the model class is exhausted and further feature work is not worth the risk.

Method: for each of the seventy surface tournaments, a small gradient-boosted classifier (sklearn HistGradientBoostingClassifier, depth 3) is trained leave-one-tournament-out on every other tournament's matches and scored on the held-out one. Its inputs are the production model's own locked predictions (p_home, p_draw, p_away) plus twelve pre-kickoff features: the expected-goal rate gap and total, the squad value gap, the opponent-adjusted form residual from Candidate 4, the confederation pairing, the rest-days difference, and neutrality. Because the probe is handed the production probabilities themselves, any improvement it finds is by construction structure the production model missed.

Leakage discipline: folding is by tournament, so no match from a held-out tournament appears in its own training slice (confirmed on all seventy folds). A label-shuffle canary runs the identical loop with the training labels permuted; a leakage-free pipeline makes the canary collapse toward the base rate, far worse than the real probe. Every feature is computed from the per-window fit or from strictly-prior history, never from the match's own result.

| Measure | Multiclass Brier |
|---|---|
| Production model | 0.5623 |
| Base rate (global class frequencies) | 0.6433 |
| Probe, leave-one-tournament-out | 0.5880 |
| Leakage canary (shuffled labels) | 0.6829 |

The probe does not beat production. It does not even match it: 0.5880 against 0.5623, worse by 0.0258. Given the production model's own predictions as inputs, a flexible learner with twelve extra features and thousands of training matches per fold adds noise, not signal, out of sample. The canary lands at 0.6829, above the base rate and well clear of the probe, and per-tournament isolation held everywhere, so the null is clean rather than a fold-construction artifact.

The feature attribution (SHAP, fit on all rows, for interpretation only) leans on the rate gap, total, and value gap, which are the production model's own core signals. The confederation features it was handed, is_inter and home_confed, rank in the middle but yield no out-of-sample gain, the same verdict Phase 1 reached by a different route: the value prior already absorbs the confederation signal.

Verdict: no exploitable residual structure. The probe is not shipped, both because its held-out Brier is worse than production and because the project does not ship a black box a tournament-scale evaluation cannot justify. Its value was the search, and the search came back empty, which is the strongest available evidence that this model class is squeezed dry.

Reproduction:

    mvn -q compile
    mvn -q exec:java "-Dexec.mainClass=com.david.worldcup.Main" "-Dexec.args=--probe-export"
    pip install --break-system-packages scikit-learn shap pandas
    python research/probe.py

The probe is seeded, so the numbers reproduce exactly, and the headline Brier figures were confirmed in a second environment.
