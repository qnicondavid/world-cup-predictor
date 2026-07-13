# Phase 2 results

Phase 2 of BRIER_PLAN.md is the team-strength work: Candidate 2 (confederation-aware strength in the fit) and Candidate 3 (make the squad-quality prior's data earn more, detailed in notes/model/EA_RATINGS_PLAN.md as EA Sports FC player ratings). This file records the Candidate 2 outcome. Candidate 3 is gated on acquiring the EA rating datasets and is not yet run.

## Candidate 2: confederation-aware strength in the fit

Candidate 2 proposed estimating inter-confederation attack and defence offsets jointly with the team ratings, so cross-confederation matchups stop leaning on sparse direct evidence and a value prior that might double-count wealth. The plan named the main risk up front: the value prior may already absorb the confederation effect, in which case the in-fit version lands at the same uncertifiable place as the post-hoc one. It also prescribed a cheap kill test before any fitter surgery, a nested check of whether confederation structure adds anything beyond the value prior out of sample.

Two results were already in from earlier phases. Phase 1's post-hoc cross-confederation correction, applied on top of the value model, was not merely redundant but actively harmful on the expanded surface: 0.0020 worse at scale 0.5, rising to 0.0047 at scale 1.0, worst on the very inter-confederation matches it targeted. Candidate 5's learned probe, handed the production predictions plus the confederation features, found no out-of-sample gain from them. Both point the same way.

The Candidate 2 diagnostic settles it as an upper bound. On the 2,180-match surface it takes the production model's own predictions and applies a leave-one-tournament-out, per-ordered-confederation-pair residual correction: for each held-out tournament, the mean (outcome minus predicted probability) per confederation pair is estimated from the other tournaments (leakage-safe, minimum 15 matches per pair) and added to the held-out predictions. A free per-pair probability offset is strictly more expressive than the in-fit rating offsets Candidate 2 would estimate, which can only move two parameters per team, so it bounds from above what any confederation-aware method could extract.

| scale | pooled Brier (2,180) | delta | inter-confed Brier (494) | delta |
|---|---|---|---|---|
| production (no correction) | 0.5623 | baseline | 0.5294 | baseline |
| 0.25 | 0.5625 | +0.0002 | 0.5304 | +0.0010 |
| 0.50 | 0.5631 | +0.0008 | 0.5327 | +0.0034 |
| 1.00 | 0.5650 | +0.0027 | 0.5413 | +0.0119 |

The correction only makes things worse, at every scale, monotonically, and most on the inter-confederation stratum it was built for. Two things are worth reading off the table. First, the production model is already sharper on inter-confederation matches (0.5294) than overall (0.5623): those matchups tend to have a clearer favourite, so the model is more confident and more often right, and there is no systematic confederation bias in the backtest for a correction to fix. Second, whatever per-pair residual survives in the training window does not persist out of sample, the same pattern Phase 1 found with the goal-difference version.

Verdict: Candidate 2 does not ship, and is not built. The value prior has already absorbed the confederation signal, and since the free per-pair offset (an upper bound on the in-fit version) only worsens Brier out of sample, the in-fit confederation fit cannot beat production. This is the quick, cheap kill the plan hoped for, reached with no change to PoissonRatingsFitter. Reproduce with `python research/candidate2_confed_diagnostic.py` after regenerating research/probe_features.csv via the Java `--probe-export`.
