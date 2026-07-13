# Phase 3 Candidate 4 pre-registration

Opponent-adjusted recent-form residual. Candidate 4 in notes/model/BRIER_PLAN.md. Written and committed before the feature is built and before any expanded-surface result is seen, so the formulation, the grid, and the decision rule are frozen and the larger surface cannot be p-hacked. Any change after commit is recorded in the deviations log at the bottom.

## Why this candidate, and why now

The recent-form channel is the one place in the model with a positive that keeps showing up and never certifies. The shipped nudge (FormAdjuster, GA(5), lambda 0.20) averages the raw goals a team conceded over its last five matches. A leave-one-tournament-out sweep found an interior optimum near lambda 0.60 that lowered the World Cup 320 Brier from 0.5441 to 0.5393, but Phase 1 showed that optimum reverses on the 2,180-match expanded surface (lambda 0.60 worse by 0.0064, CI on the worse side), so the raw feature is finished.

This candidate tests the single mechanistic reason the raw feature might still be leaving signal on the table: it is confounded by schedule strength. Conceding three to Brazil and three to a minnow count the same, so a hard run of fixtures makes a good defence look bad. That is a plausible reason cranking lambda hurt 2022, whose compressed winter schedule put wildly varying opponents into each team's recent window. The fix is to measure recent defence against what the model expected, not against zero.

## The change, frozen

One change against the shipped feature, and nothing else. Replace the per-match quantity in the form average, from raw goals conceded to the opponent-adjusted residual

    residual = expectedConceded - actualConceded

where expectedConceded is the fitted model's expected goals against that specific opponent in that specific fixture, taken from the same per-window value-adjusted strength used for prediction. For a match the team played at home, expectedConceded = lambdaAway(team, opponent, neutral); for a match it played away, expectedConceded = lambdaHome(opponent, team, neutral). A positive residual means the team conceded fewer than its fixtures implied, that is, defended better than expected.

Everything else about the nudge is held identical to the shipped FormAdjuster: the window is the last WINDOW = 5 matches strictly before kickoff, the average is a simple mean (no decay reweighting, deliberately, so this test isolates the opponent-adjustment and nothing else), the guard returns the input probabilities unchanged if either side has fewer than five prior matches, and the shift is applied on the home-versus-away log-odds axis as shift = lambda * (homeResidual - awayResidual), with the draw probability left untouched and the three outcomes renormalised. The sign convention matches the shipped feature: a positive shift favours the home side. Decay weighting, longer windows, and goals-scored terms were tested in the plan session and are out of scope here; adding any of them would confound the one comparison this file commits to.

Leakage: the expected-conceded for each recent match comes from the per-window strength, which is fit only on matches before the tournament window, and the recent matches themselves are strictly before the prediction date. The fit never sees a test outcome. This is the same train-before, predict-after regime as every other gate in the project.

## Grid, frozen

A single coefficient grid: lambda in {0.00, 0.20, 0.40, 0.60, 0.80}. 0.00 is form off and serves as the identity check: it must reproduce research/expanded_predictions_l000.csv byte for byte, since at lambda 0 no nudge is applied regardless of the feature. 0.20 is the shipped operating point, the apples-to-apples comparison against the raw feature at the same strength. The residual feature is smaller in magnitude than raw goals conceded, because it is centred near zero, so the interesting region may sit at a higher lambda than the raw feature's; the grid covers that without extending indefinitely.

The draw-transfer alpha stays fixed at the shipped 0.21 throughout, so this test moves exactly one thing. A joint (lambda, alpha) grid is named as an optional secondary only, to be pre-registered and run separately if and only if the primary below shows life.

## The ship rule, frozen

Primary comparison: the opponent-adjusted residual feature at lambda 0.20 against the shipped raw feature at lambda 0.20 (research/expanded_predictions_l020.csv), on the primary expanded surface (five World Cups plus continental finals, friendlies excluded), paired per-match Brier delta with the tournament-block bootstrap.

A ship requires all of the following.

1. Expanded-surface improvement. The paired mean improvement is in the improving direction (the residual feature has the lower Brier) and its block-bootstrap 95 percent confidence interval excludes zero.

2. World Cup gate preserved. The World Cup 320 paired delta does not worsen, with no single held-out tournament regressing by more than the noise floor of about 0.005.

3. Grid consistency. Under leave-one-tournament-out selection over the frozen lambda grid on the expanded surface, the residual feature's honest pooled Brier is at least as good as the shipped feature, and the selected lambda's paired CI against the shipped feature also excludes zero.

If all three hold, the opponent-adjusted residual replaces the raw GA(5) feature at the leave-one-tournament-out-selected lambda, and the full World Cup 320 gate is re-run to bank the number and update the README and site. If any condition fails, the form channel is closed: the result is written to the negative-findings ledger with the measured numbers, and the raw GA(5) at lambda 0.20 stays shipped as the last word on recent form.

## Reproduction, once built

    mvn -q compile
    mvn -q exec:java "-Dexec.mainClass=com.david.worldcup.Main" "-Dexec.args=--expanded-export-formresid=0.00"
    mvn -q exec:java "-Dexec.mainClass=com.david.worldcup.Main" "-Dexec.args=--expanded-export-formresid=0.20"
    mvn -q exec:java "-Dexec.mainClass=com.david.worldcup.Main" "-Dexec.args=--expanded-export-formresid=0.40"
    mvn -q exec:java "-Dexec.mainClass=com.david.worldcup.Main" "-Dexec.args=--expanded-export-formresid=0.60"
    mvn -q exec:java "-Dexec.mainClass=com.david.worldcup.Main" "-Dexec.args=--expanded-export-formresid=0.80"

    cmp research/expanded_predictions_formresid_l000.csv research/expanded_predictions_l000.csv
    python research/verify.py --expanded-paired research/expanded_predictions_l020.csv research/expanded_predictions_formresid_l020.csv

The identity check must pass (empty cmp output) before any gate number is trusted. The bootstrap is seeded, so every interval reproduces exactly.

## Deviations log

(none yet)
