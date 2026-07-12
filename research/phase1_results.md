# Phase 1 results

Outcome of the pre-registered re-gate in phase1_preregistration.md. Both candidates were tested on the expanded surface exactly as frozen, and neither ships. The production model is unchanged: Dixon-Coles fit, squad market-value prior, recent-form nudge at lambda 0.20, draw transfer at alpha 0.21, held-out multiclass Brier 0.5441 over the 320 World Cup matches.

This file records what was measured, so the rejection is on the record with numbers, not just a verdict.

## What was tested, and against what

The surface is the one frozen in the pre-registration: a rolling walk-forward over 2,180 matches, every match predicted by a model trained only on matches strictly before it. That is 320 matches from the five backtested World Cups (2006 to 2022) plus 1,860 matches from 65 continental-final editions since 2000 (UEFA Euro, Copa America, Africa Cup of Nations, AFC Asian Cup, Gold Cup, Oceania Nations Cup, and the Confederations Cup). Friendlies and qualifiers are excluded from this primary surface, for the reasons in the pre-registration.

Everything ran through the real Java production chain, not the Python replica. The exports come straight from Main and are scored by research/verify.py, so the numbers reflect the model that actually ships.

Two conventions for reading the numbers below. Brier is a loss, so lower is better. Where a delta is quoted against the shipped model, positive means the variant raised Brier (worse) and negative means it lowered Brier (better). The paired 95 percent intervals are tournament-block bootstraps (each edition is one block, B = 2000, seeded), so they are deterministic and reproduce exactly.

## Candidate A: recent-form nudge lambda

The shipped nudge is lambda 0.20. Fable's earlier World Cup 320 sweep found a clean interior optimum near 0.60 that lowered pooled Brier from 0.5441 to 0.5393, with a paired interval that only grazed zero. The pre-registration asked whether that optimum survives on the larger surface.

It does not, and the failure is sharp: the World Cup optimum is close to the worst point on the expanded surface.

| lambda | expanded Brier (2,180) | World Cup Brier (320) |
|---|---|---|
| 0.00 (form off) | 0.5624 | 0.5498 |
| 0.20 (shipped) | 0.5623 | 0.5441 |
| 0.40 | 0.5646 | 0.5411 |
| 0.60 | 0.5687 | 0.5393 |
| 0.80 | 0.5751 | 0.5416 |

Read the two columns against each other. On the 320 World Cup matches, Brier falls the whole way to lambda 0.60, which is exactly what made 0.60 look adoptable. On the 2,180-match surface, Brier is lowest at the shipped 0.20 and climbs monotonically after it, so lambda 0.60 is worse than shipped by 0.0064. The paired gate agrees: shipped against 0.60 is +0.0064 worse on the expanded surface, 95 percent interval [+0.0026, +0.0103], entirely on the worse side, while the same comparison on the World Cup subset alone is 0.0048 better, reproducing Fable. The World Cup gain was a 320-match overfit that the 6.8 times larger surface removes.

Form off (lambda 0.00) lands at 0.5624 on the expanded surface against the shipped 0.5623, a paired delta of about +0.0001 with an interval that straddles zero. So on continental finals the nudge neither helps nor hurts, while on the World Cups it is worth about 0.006 (0.5498 down to 0.5441). The nudge earns its place on World Cup matches and is harmless elsewhere, and 0.20 sits at the joint optimum. Candidate A does not ship. The shipped value is kept and is now better evidenced than before.

## Candidate B: cross-confederation correction

The correction estimates a decay-weighted goal-difference residual per ordered confederation pair from training data only, then applies it symmetrically in log-rate space to inter-confederation matchups at prediction time. The pre-registered grid is scale 0.0, 0.5, 1.0, with min_n 15 and half-life 6 years.

Scale 0 is the identity: with the offset switched off the export reproduces the shipped form-0.20 export byte for byte (confirmed with cmp), which proves the pipeline changes nothing except through the offset. The correction touches 494 inter-confederation test matches out of the 2,180.

| scale | expanded Brier (2,180) | World Cup Brier (320) |
|---|---|---|
| 0.0 (off) | 0.5623 | 0.5441 |
| 0.5 | 0.5643 | 0.5501 |
| 1.0 | 0.5670 | 0.5599 |

The correction makes the model worse on both surfaces, at every scale, and worse the harder it is applied. At scale 0.5 the expanded surface is +0.0020 worse, paired interval [+0.0005, +0.0037]; at scale 1.0 it is +0.0047 worse, interval [+0.0017, +0.0081]. Both intervals exclude zero on the worse side.

The stratum it was built to fix moves the wrong way most of all. On the 494 inter-confederation matches, scale 0.5 is +0.0089 worse and scale 1.0 is +0.0209 worse. On the World Cup subset it is +0.0060 worse at 0.5 and +0.0158 worse at 1.0, with 2010 (+0.036) and 2022 (+0.027) regressing well past the 0.005 per-tournament noise floor at scale 1.0.

That fails pre-registration conditions 1, 2, and 3. Condition 1 wanted an improvement on the primary surface and found a significant worsening. Condition 2 required the World Cup gate not to worsen, and it does. Condition 3 required the effect to be an improvement on the inter-confederation stratum, and it is a worsening there. Condition 4, the friendlies sensitivity, is moot once 1 through 3 fail, so it was not run.

The reason is the one the README already gives for the World Cup 320 result, now confirmed on more data. The squad market-value prior already carries most of the inter-confederation strength signal, because strong squads cluster in the strong confederations. The residual the offset fits on top is mostly training-window noise that does not persist out of sample, so applying it double-counts what the prior already did and injects variance, worst on the very matches it targets. Candidate B does not ship.

## Reproduction

From the repo root, with Maven on the path.

Build once:

    mvn -q compile

Candidate A exports, one per lambda:

    mvn -q exec:java "-Dexec.mainClass=com.david.worldcup.Main" "-Dexec.args=--expanded-export=0.00"
    mvn -q exec:java "-Dexec.mainClass=com.david.worldcup.Main" "-Dexec.args=--expanded-export=0.20"
    mvn -q exec:java "-Dexec.mainClass=com.david.worldcup.Main" "-Dexec.args=--expanded-export=0.40"
    mvn -q exec:java "-Dexec.mainClass=com.david.worldcup.Main" "-Dexec.args=--expanded-export=0.60"
    mvn -q exec:java "-Dexec.mainClass=com.david.worldcup.Main" "-Dexec.args=--expanded-export=0.80"

Candidate B exports, one per scale:

    mvn -q exec:java "-Dexec.mainClass=com.david.worldcup.Main" "-Dexec.args=--expanded-export-confed=0.0"
    mvn -q exec:java "-Dexec.mainClass=com.david.worldcup.Main" "-Dexec.args=--expanded-export-confed=0.5"
    mvn -q exec:java "-Dexec.mainClass=com.david.worldcup.Main" "-Dexec.args=--expanded-export-confed=1.0"

Identity check and gates:

    cmp research/expanded_predictions_confed_s000.csv research/expanded_predictions_l020.csv
    python research/verify.py --expanded-paired research/expanded_predictions_l020.csv research/expanded_predictions_l060.csv
    python research/verify.py --expanded-paired research/expanded_predictions_l020.csv research/expanded_predictions_confed_s050.csv
    python research/verify.py --expanded-paired research/expanded_predictions_l020.csv research/expanded_predictions_confed_s100.csv

The bootstrap is seeded, so the intervals above reproduce exactly. The paired deltas were confirmed in a second environment against the same CSV files.

## Distribution shift and the 2026 caveat

2026 is a pure test set and is never fit, tuned, or selected on. It also differs from the training surface: a 48-team field, more entrants from weaker confederations, and so more inter-confederation matchups than any past World Cup. That is precisely the regime Candidate B aimed at, which is why it earned a careful gate rather than a quick dismissal.

The continental-final surface is the closest available proxy for out-of-sample tournament conditions, and it is where the correction did the most damage. Nothing here proves what happens in 2026, but the strongest evidence available says both candidates fail to generalise, so neither is a safe change to carry into a tournament that is itself out of sample.

## Exit verdict

Neither pre-registered candidate clears the expanded gate. Production stays exactly as shipped. Phase 1 closes having turned two soft leftovers, a form near-miss and a confederation correction thought merely redundant, into firmly evidenced rejections, and having built an expanded harness and paired gate that every future idea can be judged against the same way. The negative-findings ledger in the README and the site's rejected-ideas panel are updated with these numbers.
