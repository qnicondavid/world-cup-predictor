# Phase 1 pre-registration

Re-gating the form nudge and the cross-confederation correction on an expanded validation surface.

This document is written and committed before the expanded harness is built and before any expanded-surface result is seen. Its purpose is to freeze what will be tested, how, and what counts as a ship, so the larger surface cannot be p-hacked. Once committed, the scope, the candidate formulations, the grids, and the decision rule are fixed. Any later change is recorded in the deviations log at the bottom, as a deviation, not a silent edit.

## Standing constraints

2026 is a pure test set. Nothing is fit, tuned, or selected on 2026 at any point.

The World Cup 320-match leave-one-tournament-out gate stays the headline metric, at the committed production value of 0.5441. The expanded surface is a power multiplier and a pre-gate, not a replacement for it.

All gating runs through the real Java production chain: Dixon-Coles fit, squad market-value prior, form nudge at lambda 0.20, draw transfer at alpha 0.21. The Python model in goal_models.py is not used for gating, because it diverges from the Java base (0.5976 against the Java base 0.5566) and is a simplified replica, not the shipped model.

## The expanded validation surface

Regime: a rolling walk-forward. Every match is predicted by a model trained only on matches strictly before it, the same train-before, predict-after information regime as the World Cup gate.

Scope, frozen: continental championship finals from 2000 onward (UEFA European Championship, Copa America, Africa Cup of Nations, AFC Asian Cup, CONCACAF Gold Cup, OFC Nations Cup), plus the Confederations Cup (2001 to 2017), plus the five backtested World Cups. Continental qualifiers and friendlies are excluded from the primary surface. Qualifiers are structurally different from tournament play, and friendlies are low-stakes and noisy, and the step 3 inventory showed the inter-confederation pool is 76 percent friendlies (2,611 of 3,449), which is exactly the material we do not want silently driving a verdict.

The World Cup 320 gate is a strict subset of this surface. The harness must reproduce it as a special case (see step 6 in the plan).

Stratification: report the paired delta overall, and split by confederation pairing (intra-confederation, inter-confederation, and per-confederation-pair where the count allows) and by favourite band, using the model's maximum win probability in bands under 40, 40 to 55, 55 to 70, and over 70 percent.

## Candidate A: form nudge lambda

Formulation, frozen: the shipped FormAdjuster and its shipped feature (decay-weighted mean goals conceded over the last five matches, GA(5)), with only the nudge strength lambda varied over a single grid: {0.00, 0.20, 0.40, 0.60, 0.80}. The value 0.20 is the current ship, 0.00 is form off. The form feature itself is not changed.

Hypothesis: lambda near 0.60 lowers pooled held-out Brier. Fable's World Cup 320 measurement was 0.5441 down to 0.5393 with a paired CI that grazed zero.

Locus: general, all matches, not a specific stratum.

## Candidate B: cross-confederation correction

Formulation, frozen: the offset from research/confederation.py, estimate_confed_offsets, which is the time-decayed mean of actual minus expected goal difference per inter-confederation pairing, estimated from training data only and applied to test inter-confederation matchups, layered on top of the production model. A single scale grid is tested: {0.0 (off), 0.5, 1.0}. min_n stays 15 and half_life stays 6 years, the committed defaults.

Hypothesis: it lowers Brier on inter-confederation matches. Fable measured minus 0.016 on the Python baseline and minus 0.005 on production, the value prior absorbing most of it.

Locus: inter-confederation matches. Primary evaluation uses the primary surface, so friendlies are excluded. A friendlies-included run is reported as a sensitivity check only.

## The ship rule, frozen

A candidate ships only if all of the following hold.

1. Expanded-surface primary gate. On the primary surface (friendlies excluded), the paired-delta mean improvement is negative (Brier goes down) and its block-bootstrap 95 percent confidence interval excludes zero.

2. World Cup gate preserved. The World Cup 320 paired delta is at most zero (non-worsening), with no single held-out tournament regressing by more than the noise floor, about 0.005 per tournament.

3. Direction consistency. The effect has the same sign across the strata it claims to fix. For Candidate B specifically, it must be negative on the inter-confederation stratum.

4. Candidate B friendlies stability. When friendlies are added back as a sensitivity check, the sign of the effect does not flip. Passing on friendlies is not required and is not by itself sufficient.

A candidate that clears 1 through 3, and 4 for Candidate B, ships: it becomes the new production default, and we then re-run the full World Cup 320 gate to bank the number and update the README and site. A candidate that fails any condition does not ship, and the result is written to the negative-findings ledger with the measured numbers.

## Bootstrap and selection discipline

Paired block bootstrap over tournaments, using the existing verify.py block_bootstrap, B equals 2000 resamples, with the tournament as the resampling block.

One grid per candidate, exactly the grids above. The reported verdict uses the single grid point chosen by leave-one-tournament-out selection on the expanded surface, nested so that a test tournament never selects its own grid point. No post-hoc grid extension and no re-formulation after seeing any result.

Candidates are evaluated one at a time, in the order A then B.

## Deviations log

Any change to the scope, a formulation, a grid, or the rule after this file is committed is recorded here with the date and the reason.

(none yet)
