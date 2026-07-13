# Phase 2 results

Phase 2 of BRIER_PLAN.md is the team-strength work: Candidate 2 (confederation-aware strength in the fit) and Candidate 3 (make the squad-quality prior's data earn more, detailed in notes/model/EA_RATINGS_PLAN.md as EA Sports FC player ratings). This file records the Candidate 2 outcome and the existing-data part of Candidate 3. The remaining part of Candidate 3, EA Sports FC ratings as a new data source, is gated on acquiring those datasets.

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

## Candidate 3: squad-value data upgrades from existing data

Candidate 3 keeps the value-prior mechanism, the single biggest banked win, and asks whether the data feeding it can earn more. Two upgrades need no new data, only the Transfermarkt dumps already in the repo: an attack-versus-defence value split (the shipped prior maps one total-value number onto attack and defence symmetrically, so it cannot express that a team's money sits in its forwards or in its defenders), and a squad-age term (resale value undervalues aging cores). The project's real-squads experiment had already shown that any reasonable total-value construction correlates about 0.99 with any other after standardizing logs, so the cheap test asks first whether the split and age carry independent information, then whether that information predicts outcomes.

The aggregation mirrors build_market_values.py: per nationality and snapshot, players valued within 730 days, top 26 by value, split by Transfermarkt position (Attack and Midfield on the attack side, Defender and Goalkeeper on the defence side), plus mean squad age. Built for the 96 World Cup 2014, 2018, and 2022 squads.

Kill test A, the correlation wall, does not kill it. Attack-side value tracks total closely (correlation 0.99), but defence-side value is looser (0.93), the two sides correlate only 0.87, and the attack-minus-defence tilt has a real spread (standard deviation 0.51 in standardized log units): teams genuinely differ in where their money sits. Mean squad age is almost orthogonal to total value (correlation -0.08), so it is not the total in disguise at all. Unlike the real-squads experiment, this data is not redundant.

Kill test B, residual predictiveness, kills it anyway. Leave-one-tournament-out, neither the attack-minus-defence tilt differential nor the age differential predicts the production model's outcome residual. The pooled correlations are +0.012 and -0.028, indistinguishable from zero, and the per-tournament signs flip rather than holding steady (tilt +0.18, -0.05, -0.15 across 2014, 2018, 2022; age -0.19, +0.08, +0.05). The independent information exists but does not transfer to match outcomes.

Verdict: the existing-data upgrades do not ship, and no pipeline was built. A team's attack and defence value balance and its squad age carry information the total value misses, but that information does not predict results out of sample, so a prior built on it would add variance, not signal. One caveat kept honest: the goalkeeper-value term was folded into the defence side rather than isolated, because Transfermarkt systematically compresses goalkeeper values, which is precisely why the stronger version of this idea uses EA goalkeeper ratings instead. Reproduce with `python research/candidate3_value_split_diagnostic.py`.

That leaves the EA Sports FC ratings (notes/model/EA_RATINGS_PLAN.md), the other instance of Candidate 3 with a genuinely different signal, judged ability and real goalkeeper ratings rather than resale price, as the last open Brier lever, gated on acquiring the EA rating datasets.
