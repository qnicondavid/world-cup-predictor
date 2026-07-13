# atk_pen gate pre-registration (promotion from the stage-1 screen)

SEALED 2026-07-13, before any gate number. Its sha256 is recorded in
notes/model/ea_subattr_freeze.txt; if this document changes after that, the hash will not match.
The additive Java wiring (EaWeights.wAtkPen, EaRatingsTable.atkPenAsOf, the
ValueAdjuster.adjustWithEa attack term, and the Main --ea-export token) is built. The gate is
pending the human mvn runs, and running it spends one of the two remaining budget slots, leaving one.

A single-candidate follow-on to the closed EA sub-attribute ladder
(research/ea_subattr_results.md). That ladder's two pre-registered candidates, gk_stop and the
set-piece pair, were killed on the 768-match surface at decision point 1. This document promotes
one probe composite, atk_pen, to a gate under the plan's promotion rule
(notes/model/EA_SUBATTRIBUTES_PLAN.md section 6).

Honesty note, stated up front: atk_pen was observed in the stage-1 screen before this
pre-registration was written (pooled +0.083, World Cup +0.096, continental +0.080, both strata
positive, research/ea_subattr_results.md). The plan's promotion rule explicitly allows a probe
to be argued from the published screen, so this is a permitted promotion, not a hidden peek. The
screen was a residualized correlation; the gate below is a distinct and more stringent test (the
Brier delta of the actual attack-prior term, with leave-one-tournament-out grid selection and a
tournament-block bootstrap on the 768-match surface). The screen does not predetermine the gate,
and a correlation of +0.083 routinely fails to convert into a certified Brier improvement.

## Mechanism, a priori

atk_pen scores a team's penetration from the top four attackers (pool: top 4 by overall among
ST, CF, LW, RW, LM, RM; floor 3; player score = 0.30 skill_dribbling + 0.25
movement_sprint_speed + 0.20 movement_acceleration + 0.25 skill_ball_control; frozen in the plan
section 4 and already built into data/ea_ratings.csv, column 14). Beating a marker and running
in behind is a scoring channel distinct from combination play and from squad market value, and
it bites hardest against the deep, compact blocks that mid-tier teams set against favourites.
That is the stratum the plan named as mispriced in 2026. A fitted historical goal rate sees
realized scorelines, not the latent ability to break a low block, so a fast, direct forward line
can move outcomes before the fitted rate catches up. The market prices transferable technique
and youth, so this is not simply value in disguise: in the screen 39 percent of atk_pen's
variance was independent of value and overall.

## The hypothesis, frozen

One term. The attack prior additionally receives w_ap times z(atk_pen), the standardized team
penetration score (standardized across teamsWithRatingAsOf at the as-of date), scaled by the
same EA coverage shrinkage as every other EA term (zero at 5 rated players, full at 15, linear
between). A higher penetration score raises the team's attack rate, so it scores more. The
defence prior is untouched; no other composite enters. In the export this is w_ap on a new
wAtkPen weight with all other EA weights zero.

## Grid, frozen

A single grid: w_ap in {0.0, 0.1, 0.2, 0.3}, with 0.0 reproducing the value-only prior byte for
byte (the identity check). One grid, no post-hoc extension.

## Surface and ship rule, frozen

Identical to research/ea_ratings_preregistration.md and the closed ladder: the 768-match EA
surface (World Cups 2018 and 2022 plus continental finals 2015 to 2023), leave-one-tournament-out
grid selection nested so a test tournament never selects its own point, tournament-block
bootstrap with B = 2000. A ship requires all of the following.

1. The paired mean improvement over the value-only prior on the 768 surface is in the improving
direction and its 95 percent interval excludes zero.
2. The World Cup 2018 plus 2022 subset does not worsen, with no single tournament regressing past
the noise floor of about 0.005.
3. The improvement is not driven by a single tournament and holds direction across the
confederation and favourite-band strata.

The leave-one-tournament-out-selected grid point ships if it clears, and the full World Cup 320
gate is re-run to bank the headline (only the 2018 and 2022 legs can move). This is the single
allowed test of the penetration channel. Whatever it shows, the result is reported and this
promotion is closed, with no further rungs, grids, or re-formulations. It spends one of the two
remaining budget slots; one slot remains after it.

## Expectation, stated before running

Modest. atk_pen was the cleanest cross-strata probe in the screen, but the screen is a
correlation and the gate is a Brier delta against a value model that already prices much of a
team's attack, so most of that correlation will not convert. Expected 768-surface delta between
+0.0010 (worse) and -0.0020 (better) at the selected weight, against measured half-widths of
about 0.001 to 0.003 for terms of this size, so the modal outcome is an interval spanning zero (a
near-miss) and the good tail is a certified 0.001 to 0.002. The whole EA arc has produced nulls
on this surface, so a third clean rejection is a likely and acceptable outcome. Any measured
improvement above roughly 0.005 should be treated first as a bug or a leak and audited before it
is believed.

## Java wiring (built only after this is sealed)

Mirrors the existing EA terms line for line, additive, adjust() untouched. EaRatingsTable gains
an atk_pen accessor (the 14th CSV field); EaWeights gains wAtkPen (ZERO gains one zero, coverage
unchanged); ValueAdjuster.adjustWithEa gains one standardiseEa call and one term on the attack
prior (priorAttack += cov times wAtkPen times zAtkPen); Main.java --ea-export token grows to
tag:wOverall:wAtk:wDef:wGk:wAtkPen with missing tokens defaulting to zero. The zero-weight export
must reproduce the previous zero export byte for byte before any weighted run. Two
ValueAdjusterTest cases: the zero-weight identity, and a positive wAtkPen raising only the
better-penetration team's attack prior. atk_pen is already in data/ea_ratings.csv, so no rebuild
is needed; only the Java wiring and the gate runs remain.

## Deviations log

(none yet)
