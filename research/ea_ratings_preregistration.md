# EA Sports FC ratings pre-registration

Adding EA Sports FC player ratings as a second squad-quality signal alongside market value in the Dixon-Coles prior. Companion to notes/model/EA_RATINGS_PLAN.md and the kill-test result in research/phase2_results.md, where both cheap tests passed: the EA overall aggregate correlates 0.905 with standardized log market value (below the 0.97 wall), the goalkeeper aggregate only 0.668, and the rating-minus-value differential correlates +0.114 with the production model's held-out outcome residual, positive in both 2018 and 2022.

Written and committed before the committed aggregate is built and before any gate number is seen, so the surface, the aggregate, the ladder, the grids, and the decision rule are frozen. Any later change is recorded in the deviations log at the bottom, as a deviation, not a silent edit.

## Standing constraints

2026 is a pure test set. No 2026 data, EA ratings or otherwise, touches any fit, weight, threshold, or selection at any point.

All gating runs the real Java production chain: Dixon-Coles fit, market-value prior, form nudge at 0.20, draw transfer at 0.21. The EA signal enters only through the squad-quality prior, added to the existing market-value adjustment. The fit, the form nudge, and the draw transfer are untouched. The build is additive and default-off: at EA weight zero the model is byte-identical to today.

Leakage rules, hard requirements. For a tournament starting on date D, the EA edition used is the one whose release date is the latest on or before D, mirroring the market-value as-of rule; a post-tournament edition is never used. The editions in the committed raw dump are FIFA 15 (released September 2014) through FIFA 23 (September 2022); the aggregate is built from these strictly pre-tournament snapshots only. The raw player dump stays out of the repository (data/ea_raw/ is gitignored); only the derived per-team aggregate is committed.

## The validation surface, frozen

EA coverage is the binding constraint. The gate runs on the subset of the Phase 1 expanded surface for which a pre-tournament FIFA edition exists in the dump: the World Cups of 2018 and 2022, plus the continental championship finals from 2015 through 2023 (editions FIFA 15 through 23 cover the autumn before each). That is roughly twenty one tournament editions. Tournaments before 2015 (no edition in the dump) and from 2024 on (would need FC 24 and later) are excluded from the EA gate; on them the EA-blended model falls back to value-only and equals production exactly, so including them would only dilute the paired delta with zeros.

The World Cup 320 leave-one-tournament-out gate stays the project's headline honesty metric, but EA covers only two of its five tournaments (2018 and 2022), so the World Cup check here is the 2018-plus-2022 subset (128 matches), reported as a non-worsening guard rather than as the headline.

Coverage shrinkage, frozen: a team's EA weight scales with its rated-player count in that edition, full weight at 15 or more rated players, shrinking linearly to zero at 5, and value-only below 5. The rated count and the applied shrinkage are reported per team per edition.

## The aggregate, frozen

research/build_ea_ratings.py writes data/ea_ratings.csv, one row per team per edition snapshot, columns: team, as_of, n_rated, ovr_top26, atk_top, def_top, gk_top, age_mean. Aggregation mirrors the market-value proxy: the top 26 players by overall rating for that nationality in that edition. ovr_top26 is their mean overall; atk_top is the mean overall of the attack-side players among them (forwards and midfielders); def_top is the mean overall of the defence-side players (defenders and goalkeepers); gk_top is the best goalkeeper overall; age_mean is their mean age. Team names map to the results.csv names through the existing alias machinery, and the join rate is a reported audit number.

## The feature ladder, frozen

The EA signal is added to the existing, unchanged market-value adjustment as one or more standardized terms. Three rungs, run in order, stopping at the first that fails to beat the rung below it. One grid per rung, no post-hoc extension.

Rung 1, single rating blend. Attack and defence ratings receive their current market-value adjustment plus w_r times z(ovr_top26), applied symmetrically, exactly where the value prior acts today. Grid: w_r in {0.0, 0.1, 0.2, 0.3}; w_r = 0 reproduces the shipped value-only prior byte for byte.

Rung 2, positional decomposition. On top of the value adjustment, the attack prior additionally receives w_a times z(atk_top) and the defence prior w_d times z(def_top). This breaks the symmetry the value prior structurally cannot express. Grid: w_a and w_d each in {0.0, 0.1, 0.2}. Rung 2 must beat rung 1's selected point to proceed.

Rung 3, goalkeeper term. On top of the better of rungs 1 and 2, the defence prior additionally receives w_g times z(gk_top), the cleanest signal with no analog in market value. Grid: w_g in {0.0, 0.1, 0.2}. Rung 3 must beat rung 2.

An age term is not in the ladder. Kill test 1 showed age is nearly orthogonal to value, but the plan ranks it below the positional and goalkeeper signals and adding it would spend gate power this surface does not have; age is admitted to the Candidate 5 residual probe only, never to the prior.

## The ship rule, frozen

The rung's grid point is chosen by leave-one-tournament-out selection on the EA-covered surface, nested so a test tournament never selects its own point. A rung ships only if all of the following hold.

1. EA-covered surface. The paired mean improvement over the shipped value-only prior is negative (Brier goes down) and its tournament-block bootstrap 95 percent interval excludes zero.

2. World Cup guard. On the 2018-plus-2022 World Cup subset the paired delta does not worsen, with no single tournament regressing by more than the noise floor of about 0.005.

3. Direction consistency. The improvement holds the same sign across the confederation and favourite-band strata it claims to help, and does not come from a single tournament.

A rung that clears all three becomes the new prior, and the full World Cup 320 gate is re-run to bank the number (it moves on 2018 and 2022, stays put on 2006 to 2014) and update the README and site. A rung that fails is written to the negative-findings ledger with the measured numbers, and the shipped value-only prior stays. Because the whole idea passed the cheap tests on a modest signal, the honest prior is that it may clear or may just miss on the available power; either outcome is a result.

## Bootstrap and selection discipline

Tournament-block bootstrap, B equals 2000, the tournament edition as the resampling block, via the existing verify.py machinery extended to the EA-covered surface. One grid per rung, exactly as above, evaluated in order and stopping at the first failure. No feature enters the prior that is not in this ladder; anything else (age, pace, height, potential, international reputation, body type) is admitted only to the Candidate 5 residual probe and, if flagged, promoted to its own pre-registered rung.

## Deviations log

(none yet)
