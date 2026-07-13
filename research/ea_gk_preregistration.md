# EA goalkeeper term pre-registration

A single-hypothesis follow-on to research/ea_ratings_preregistration.md. The EA ladder there stopped at rung 1: the overall EA term, applied symmetrically, worsened the pre-registered EA surface (research/phase2_results.md). This test isolates the one EA channel the kill tests found genuinely independent of market value, the goalkeeper rating, which the overall-first ladder gated last and never reached.

Justification, predating this test's results: kill test 1 (research/phase2_results.md, run before any gate) measured the EA overall aggregate at 0.905 correlation with standardized log market value, the attack-side at 0.905, the defence-side at 0.890, and the goalkeeper aggregate at only 0.668. Transfer values compress goalkeeper prices, so the keeper rating is the EA signal with the least overlap with the value prior already shipped. That measurement, not the rung-1 result, motivates isolating it.

Written and committed before the goalkeeper gate is run. Frozen. Any later change is recorded in the deviations log.

## The hypothesis, frozen

One term. The defence prior additionally receives w_g times z(gk_top), the standardized best-goalkeeper overall, scaled by the same EA coverage shrinkage as the rest of the EA prior (full at 15 rated players, zero at 5). No overall term, no attack-side term, no outfield-defence term. A better goalkeeper lowers the team's defence rating, so the team concedes less; the attack prior is untouched. In the export this is w_g on the gk weight with all other EA weights zero.

## Grid, frozen

A single grid: w_g in {0.0, 0.1, 0.2, 0.3}, with 0.0 reproducing the value-only prior byte for byte (the identity check). One grid, no post-hoc extension.

## Surface and ship rule, frozen

Identical to research/ea_ratings_preregistration.md: the EA-covered surface (World Cups 2018 and 2022 plus continental finals 2015 to 2023, 768 matches), leave-one-tournament-out, tournament-block bootstrap with B = 2000, the tournament edition as the resampling block. A ship requires all of the following.

1. The paired mean improvement over the value-only prior on the EA surface is in the improving direction and its 95 percent interval excludes zero.

2. The World Cup 2018 plus 2022 subset does not worsen, with no single tournament regressing past the noise floor of about 0.005.

3. The improvement is not driven by a single tournament.

The leave-one-tournament-out-selected grid point is the shipped one if it clears, and the full World Cup 320 gate is re-run to bank the number. This is the single allowed test of the goalkeeper channel. Whatever it shows, the result is reported and the EA idea is closed, with no further rungs, grids, or re-formulations.

## Expectation, stated before running

Low. Rung 1 failed on the continental-final surface, not at the World Cups, and the goalkeeper term inherits that same surface. gk_top is also the noisiest aggregate built, one keeper standing in for a squad, thinnest exactly where coverage is thin. A second clean rejection is the likely and acceptable outcome. If it clears, it is the one EA channel that carried information beyond value, and it ships as a goalkeeper-only defence prior.

## Deviations log

(none yet)
