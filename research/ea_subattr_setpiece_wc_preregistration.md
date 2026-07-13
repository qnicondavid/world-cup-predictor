# Set-piece pair on the World Cup surface: gate pre-registration (budget slot 2 of 2)

SEALED 2026-07-13, before any gate number. Its sha256 is recorded in
notes/model/ea_subattr_freeze.txt. This spends the second and last EA sub-attribute budget slot;
none remain after it.

A single-candidate promotion under the plan's goalpost clause (EA_SUBATTRIBUTES_PLAN.md section 6),
which pre-authorizes exactly one such move: "If a World Cup-only prior is ever believed on
mechanism (tournament compression favouring set pieces is a candidate argument), that is a separate
future pre-registration naming the World Cup surface in advance." This is that document.

## Honesty notes, stated up front

First, this composite was already killed once. The set-piece pair (sp_threat, sp_vuln) was a named
candidate in the stage-1 kill test and was killed on the full 768-match surface
(research/ea_subattr_results.md): it improved the World Cup stratum (+0.128 residualized
correlation, the strongest of any composite) while going flat on the continental surface.
Re-testing a killed candidate on the stratum where it looked good is a goalpost move unless it is
justified by an a-priori mechanism that names the new surface in advance. The plan pre-authorized
exactly that for set pieces, on the tournament-compression argument below. That authorization, not
the +0.128, is what licenses this test.

Second, and more important: this cannot certify a ship, and does not claim to. The EA-covered World
Cup surface is two tournament blocks, WC2018 and WC2022, 128 matches. The project's gate
(leave-one-tournament-out selection plus tournament-block bootstrap) needs several blocks; on two it
is degenerate, because each LOTO fold would select on a single tournament and a two-block bootstrap
has no usable sampling distribution. So this pre-registration is characterization, not
certification. It measures the World Cup set-piece effect, freezes the hypothesis with a date and a
hash, and leaves the actual confirmation to World Cups still to come. It is the honest close of the
"do set pieces help at World Cups" question, not a claim that they do.

## Mechanism, a priori

Set pieces are rehearsed, and tournaments compress preparation time and add cautious,
stoppage-heavy knockout football, both of which favour rehearsed dead-ball routines over emergent
open play. Public tournament analyses consistently put the set-piece share of World Cup goals
materially above club-league shares. The market prices transferable skill (pace, technique, youth),
so aerial dead-ball specialists (tall centre-backs, target forwards, aging free-kick takers) are
systematically cheap relative to their set-piece contribution, and the overall rating dilutes
fk_accuracy and jumping among thirty-plus inputs. This is the plan's own named argument for a
World-Cup-specific effect that continental football, with its different stakes and preparation,
would wash out. The stage-1 pattern (World Cup positive, continental flat to negative) is consistent
with it.

## The hypothesis, frozen

One shared weight w_sp. The attack prior receives cov times w_sp times z(sp_threat); the defence
prior receives minus cov times w_sp times z(sp_vuln), in the concede-less direction; cov is the same
coverage shrinkage as every EA term. sp_threat and sp_vuln are already built into data/ea_ratings.csv
(columns 10 and 11) and frozen in the plan section 4. Threat and vulnerability are the two ends of
the same aerial dead-ball contest, so they share one weight; a two-weight version would spend more
budget than the mechanism warrants.

## Grid, frozen

w_sp in {0.0, 0.1, 0.2}. The 0.2 ceiling is the plan's set-piece grid ceiling: the mechanism prices
a share of goals, not all of them, so a 0.3-sized pull would be larger than the story. 0.0
reproduces value-only byte for byte.

## Surface named in advance, and the degraded methodology

The certifying surface is the EA-covered World Cup surface: WC2018 plus WC2022, 128 matches, two
tournament blocks. Because two blocks cannot support the standard gate, the following is frozen in
its place.

1. Report every grid point's WC-128 paired Brier delta against the value-only baseline
(delta = mcb(zero) minus mcb(sp); positive improves). No LOTO selection: with two folds it is
degenerate, so the whole grid is reported.
2. Report the per-tournament split, WC2018 and WC2022 separately. With only two blocks, the one
honest robustness check is whether both World Cups move the same way; a result driven by one of the
two is not credible.
3. Report a match-level paired bootstrap band (resampling the 128 matches, B = 2000) as a rough
uncertainty, explicitly noted as the weaker guard that trades the tournament-block leakage
protection for a computable interval.

There is no ship rule in the usual sense, because two blocks cannot certify. The pre-committed
interpretation: if both World Cups improve and the match-bootstrap band is clear of zero, the result
is recorded as a provisional, unconfirmed World Cup set-piece effect (the "validated on two cycles,
not five" status the README already uses for the xG idea), never as a headline ship, and its
confirmation is future out-of-sample World Cups. If either World Cup fails to improve, the effect is
a two-tournament coincidence and the question is closed negative. Either way the numbers are
published and this is the last word on the set-piece channel until the EA World Cup surface grows.

## 2026 and confirmation

2026 is never selected on. The remaining 2026 matches were locked with the shipped value-only model
and cannot be retro-fitted with a set-piece term. Confirmation of this hypothesis therefore comes
from World Cups after this seal (2030, or the FC24 to FC26 editions extending historical World Cup
coverage), evaluated out of sample against this frozen definition. That is the point of freezing it
now rather than leaving it vaguely parked.

## Budget

This spends the second of the two budget slots. Zero remain. Whatever this shows, the EA
sub-attribute campaign is closed after it.

## Java wiring (built at seal time)

Additive, mirrors the existing EA terms, adjust() untouched. EaWeights gains wSp (ZERO gains a
zero); EaRatingsTable gains spThreatAsOf and spVulnAsOf (CSV fields 10 and 11); ValueAdjuster.
adjustWithEa gains two standardiseEa calls and two coupled terms (attack += cov times wSp times
z(sp_threat); defence += minus cov times wSp times z(sp_vuln)); Main --ea-export token grows to
tag:wOverall:wAtk:wDef:wGk:wAtkPen:wSp. The zero-weight export must reproduce the previous zero
export byte for byte.

## Expectation, stated before running

Directional and uncertifiable. The stage-1 World Cup correlation was +0.128, the strongest of any
composite, so both World Cups improving is plausible, and a WC-128 Brier gain of roughly 0.002 to
0.004 at the selected weight would not surprise. But 128 matches over two blocks cannot certify it,
and the continental surface already said the effect does not generalize, so the honest status even
in the good case is provisional. A both-World-Cups-agree positive is the good outcome, and it is
still not a ship.

## Deviations log

(none yet)
