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

That leaves the EA Sports FC ratings (notes/model/EA_RATINGS_PLAN.md), the other instance of Candidate 3 with a genuinely different signal, judged ability and real goalkeeper ratings rather than resale price.

## Candidate 3, continued: EA Sports FC ratings kill tests

The EA ratings are the other instance of Candidate 3: a squad-quality signal that is judged ability rather than resale price, with real goalkeeper ratings and coverage of domestic-league cores. The plan gated it behind two cheap kill tests before any pipeline. With the FIFA 18 launch roster (2017-09-18, for the 2018 World Cup) and the FIFA 23 launch roster (2022-09-26, for the 2022 World Cup), both safely pre-tournament, the top-26 overall aggregate was built per nation, and for the first time in the campaign both kill tests pass.

Kill test 1, the correlation wall. Across the 64 World Cup 2018 and 2022 squads (all 64 matched), the EA overall aggregate correlates 0.905 with standardized log market value, below the 0.97 kill threshold, so it is not the value prior in disguise. The position-specific parts are more independent still: the goalkeeper aggregate correlates only 0.668 with value, and mean squad age only 0.227. This is exactly the profile the plan predicted, because transfer values compress goalkeeper prices and ignore age, so EA ratings see squad quality the value column cannot.

Kill test 2, residual predictiveness. Teams EA rates above their market value do systematically beat the production model's expectation. The rating-minus-value differential correlates +0.114 with the model's held-out outcome residual pooled over 128 matches, and positive in both tournaments (0.16 in 2018, 0.05 in 2022). The correlation is modest and, on 128 matches, not significant on its own, but the sign is stable, which is the plan's pass criterion, deliberately a direction check rather than a significance test at this sample size.

Verdict: pass, both tests, the first idea in the campaign to clear the cheap gate. This is a green light to build, not a ship decision. The signal is real and independent of value, the goalkeeper channel most of all, and points the right way out of sample in both folds, but it is small and uncertified. The next step is the pipeline the plan describes: build the committed per-team aggregate (data/ea_ratings.csv), generalise the value prior to a multi-signal blend in ValueAdjuster, and run the pre-registered feature ladder on the real leave-one-tournament-out gate, where a modest true effect either certifies or joins the negative-findings ledger. Reproduce the kill tests with `python research/ea_ratings_kill_tests.py` (needs the raw dump in data/ea_raw/, which stays out of the repo).

## Candidate 3, EA ratings: the ladder gate

The kill tests were a green light to build. Following research/ea_ratings_preregistration.md, the EA prior was built into ValueAdjuster as an additive, default-off multi-signal blend, and confirmed byte-identical to the shipped value prior at zero EA weight: the zero-weight export reproduces the value-only predictions to 0.00e+00. The gate ran leave-one-tournament-out on the 768-match EA-covered surface (World Cups 2018 and 2022 plus continental finals 2015 to 2023).

Rung 1, the single EA-overall term applied symmetrically, failed. Against the value-only baseline on the EA surface (deltas as EA minus baseline Brier, so positive is worse):

| EA-overall weight | EA surface delta (95% CI) | World Cup 2018+2022 delta |
|---|---|---|
| 0.1 | +0.0019 worse [+0.0001, +0.0040] | -0.0012 better |
| 0.2 | +0.0043 worse [+0.0011, +0.0080] | -0.0007 better |
| 0.3 | +0.0076 worse [+0.0028, +0.0131] | +0.0012 worse |

Every weight worsens the pre-registered surface, monotonically, with the interval excluding zero on the worse side. The overall term helps the World Cups slightly, matching the kill test, but hurts the continental finals enough that the net is a significant worsening. Condition 1 of the ship rule, an improvement on the EA surface with the interval clear of zero, fails. Per the frozen rule (run in order, stop at the first rung that fails to beat the one below), the ladder stops at rung 1 and the EA overall prior does not ship. The World Cup subset improvement is not a ship signal; the pre-registered metric is the full EA surface, which worsened, and reading the flattering 128-match stratum as a success would be exactly the goalpost-moving the pre-registration exists to prevent.

One honest caveat on the ladder design, recorded because it shaped the outcome. The rungs were ordered overall, positional, goalkeeper, which is most-correlated-with-value first: kill test 1 measured the overall aggregate at 0.905 correlation with market value and the goalkeeper aggregate at only 0.668. So the ladder gated the one genuinely value-independent channel last, behind two near-duplicates of the prior already shipped, and the stop rule halted on the weakest rung before reaching the strongest. Rung 1 failing is therefore weak evidence about the goalkeeper channel, which is tested next under its own separate pre-registration (research/ea_gk_preregistration.md), justified by the kill test rather than by this result and reported whatever it shows.

Reproduce: mvn -q compile, then the --ea-export runs, then python research/verify.py --expanded-paired research/ea_predictions_zero.csv research/ea_predictions_r1wNN.csv.
