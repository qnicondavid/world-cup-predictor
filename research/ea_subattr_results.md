# EA sub-attributes: stage-1 kill test results

Outcome of the EA sub-attribute campaign's stage-1 incremental-value kill test, run
July 13, 2026 against the frozen plan (kept private at notes/model/EA_SUBATTRIBUTES_PLAN.md,
sealed sha256 595f920e42e2d5ff11583ff9a706ba4508f665c4ce3f71f19396e9503915776e in
notes/model/ea_subattr_freeze.txt). The plan stays private; this record and its numbers are
the bank of the finding. Every number below was produced after the seal, never before.

Headline: both pre-registered candidates, gk_stop and the coupled set-piece pair, fail on the
certifying 768-match surface. Under the frozen thresholds this is a double kill. No Java change
is made and the shipped model is untouched. The two pre-registered candidates are closed. Two
gate attempts remain unspent but are reachable only through a fresh promotion pre-registration
(see the last section). Total cost was a few hours, entirely in-sandbox, no gate.

## Setup, frozen before the run

Surface: 768 matches in 21 tournament-edition blocks (World Cups 2018 and 2022, 128 matches;
continental finals 2015 to 2023, 640). Baseline: the value-only model in
research/ea_predictions_zero.csv. Composites read as-of from data/ea_ratings.csv (the
17-column aggregate this campaign added). Anchors: z(log market value) and z(ovr_top26).
Method: leave-one-tournament-out residualization of each composite jointly on both anchors,
then the residual differential per match correlated with the value-only outcome residual,
1/0.5/0 minus (p_home + 0.5 p_draw). Thresholds: pass at pooled +0.07 with both macro strata
positive; kill at pooled +0.03 or below, or the two strata opposite in sign; near zone
between. Only gk_stop and the set-piece pair carry decision authority. The null standard error
of a pooled correlation at n around 768 is about 0.036, so +0.07 is roughly two standard errors.

## Measured

Columns: pooled correlation, then the World Cup (128) and continental (640) strata, matched n,
blocks positive over blocks negative, then the anchor-overlap panel (correlation with value,
correlation with overall, joint R squared, and the leftover fraction independent of both).

| composite | pooled | WC | cont | n | blk +/- | vs value | vs ovr | joint R2 | leftover |
|-----------|-------:|---:|-----:|--:|:-------:|--------:|-------:|---------:|---------:|
| gk_stop     | -0.011 | +0.061 | -0.036 | 471 | 9/10  | +0.67 | +0.73 | 0.54 | 0.46 |
| sp_threat   | +0.020 | +0.013 | +0.019 | 547 | 10/10 | +0.79 | +0.84 | 0.72 | 0.28 |
| sp_vuln     | +0.059 | +0.157 | +0.017 | 499 | 12/8  | +0.71 | +0.76 | 0.58 | 0.42 |
| atk_fin     | -0.019 | +0.025 | -0.041 | 449 | 9/10  | +0.83 | +0.91 | 0.83 | 0.17 |
| atk_create  | +0.085 | +0.019 | +0.105 | 524 | 11/9  | +0.84 | +0.93 | 0.86 | 0.14 |
| atk_pen     | +0.083 | +0.096 | +0.080 | 545 | 11/9  | +0.76 | +0.76 | 0.61 | 0.39 |
| def_win     | -0.021 | +0.080 | -0.056 | 499 | 9/11  | +0.84 | +0.94 | 0.88 | 0.12 |
| ctrl        | +0.033 | +0.012 | +0.037 | 547 | 10/10 | +0.87 | +0.92 | 0.87 | 0.13 |
| pace_trans  | +0.061 | +0.103 | +0.052 | 545 | 10/10 | +0.53 | +0.48 | 0.28 | 0.72 |
| sp_pair     | +0.034 | +0.128 | -0.005 | 496 | 11/9  | coupled threat plus vuln, the gated form |

## The two verdicts

gk_stop: pooled -0.011, WC +0.061, continental -0.036. KILL. Pooled sits below +0.03 and the
strata are opposite in sign. The one channel the closed OVR campaign found most independent of
market value (the goalkeeper) does not survive once its overlap with value and overall is
removed and it is measured across the whole surface instead of the World Cups alone. The World
Cup stratum stays mildly positive, matching the earlier gk_top pattern, but the surface is flat
to slightly negative.

set-piece pair: pooled +0.034, WC +0.128, continental -0.005. KILL. The strata are opposite in
sign with pooled below +0.07. The set-piece signal lives almost entirely in the 128-match
World Cup stratum and disappears on the 640-match continental surface.

## The reading, honestly

This is the pattern the goalpost rule was written for, and the same one the closed OVR campaign
hit twice: a flattering World Cup subset (gk_stop +0.061, the pair +0.128, sp_vuln +0.157,
pace_trans +0.103) on top of a flat or negative continental surface. The frozen metric is the
768-match surface, and on it neither candidate clears the bar. Reading the World Cup stratum as
success is the move the pre-registration forbids, so the result is negative and is recorded as
such. The 128-match World Cup surface is too thin to certify effects of this size on its own,
which is why the plan parked that route as structurally underpowered until more covered World
Cups accumulate.

A note on why the null is trustworthy rather than a plumbing artifact: the anchor panel shows
value and overall explain 54 to 88 percent of each composite's variance, so the residuals that
were correlated are real and non-degenerate; the outcome residual is itself net of the value
model, so the test asks the correct question (does the part of the composite that value and
overall miss predict the part of the outcome the value model misses); and gk_stop's World Cup
figure of +0.061 lands inside the plan's pre-stated expectation of +0.02 to +0.08 for that
channel, so the machinery is behaving as anticipated. The signal simply is not there on the
surface that can certify it.

## Probe observations, no authority

The seven non-authority panels are prioritization input only. Their apparent passes are not
adjusted for having screened nine composites, so none can be gated on the strength of this run.

atk_pen (penetration: dribbling, sprint speed, acceleration, ball control over the top four
attackers) is the one exploratory positive that holds across strata: pooled +0.083, WC +0.096,
continental +0.080, 11 of 20 blocks positive, on a field where 39 percent of its variance is
independent of value and overall. Had it been pre-registered as a candidate it would have
cleared the pass bar. It was not, so it carries no authority here, and at roughly 2.3 standard
errors after screening nine composites it is exactly the kind of unadjusted positive the method
distrusts.

atk_create (+0.085) is continental-driven (WC +0.019) and less consistent across strata;
pace_trans (+0.061) is World Cup-driven. Neither is as clean as atk_pen.

## atk_pen promotion gate (budget slot 1 of 2, spent)

After the double kill, atk_pen was promoted under the plan's rule via a fresh sealed
pre-registration (research/ea_subattr_atkpen_preregistration.md, sha256 dedd98b3...9557). The term
was wired additively into the attack prior (priorAttack += cov times wAtkPen times z(atk_pen)),
confirmed byte-identical to value-only at zero weight, and gated on the 768 surface. Measured with
verify.py and a per-stratum recomputation (delta = mcb(zero) minus mcb(ap); positive improves):

| w_ap | pooled | 95% CI | WC-128 | continental-640 |
|-----:|-------:|:------:|-------:|----------------:|
| 0.1 | -0.00030 | [-0.00137, +0.00063] | +0.00135 | -0.00063 |
| 0.2 | -0.00211 | [-0.00442, -0.00010] | +0.00197 | -0.00292 |
| 0.3 | -0.00377 | [-0.00747, -0.00065] | +0.00361 | -0.00525 |

Verdict: FAIL. atk_pen worsens the certifying 768-match surface monotonically with weight, and the
95 percent interval excludes zero on the worse side at 0.2 and 0.3. Leave-one-tournament-out
selection over the grid picks 0.0, so nothing ships. The screen's +0.083 correlation did not
convert into a Brier improvement, exactly as the sealed expectation warned it usually will not.

The pattern, stated plainly: atk_pen improves the 128-match World Cup subset (up to +0.0036 at
w = 0.3) while worsening the 640-match continental surface. This is the third EA composite, after
gk_stop and the set-piece pair, to show the same World-Cup-positive and continental-negative shape,
which is also the shape the whole OVR campaign took. The certifying metric is the surface; the
World Cup subset is too thin to certify (its noise floor dwarfs +0.0036); the goalpost rule forbids
reading it as success. It is recorded as an observation, not a result.

## Set-piece pair on the World Cup surface (budget slot 2 of 2, spent): the campaign close

Per the sealed pre-registration (research/ea_subattr_setpiece_wc_preregistration.md, sha256
4bd088d7...6ad6f7), the set-piece pair was wired additively (sp_threat on attack, sp_vuln on
defence, shared weight w_sp), confirmed byte-identical to value-only at zero weight, and measured on
the World Cup surface (WC2018 plus WC2022, 128 matches, two tournament blocks). Because two blocks
cannot support the standard gate, the full grid is reported with the per-tournament split and a
match-level paired bootstrap band (delta = mcb(zero) minus mcb(sp); positive improves):

| w_sp | WC-128 delta | match-boot 95% | WC2018 | WC2022 |
|-----:|-------------:|:--------------:|-------:|-------:|
| 0.1 | +0.00374 | [-0.00291, +0.01012] | +0.00560 | +0.00189 |
| 0.2 | +0.00444 | [-0.00913, +0.01788] | +0.00941 | -0.00053 |

Verdict: directional positive, uncertifiable. At w_sp = 0.1 both World Cups improve, the only EA
composite to show both World Cups agreeing in the improving direction, and the pooled World Cup gain
(+0.0037) is the largest any composite has posted on this surface. But the match-bootstrap band
spans zero at both weights, and at w_sp = 0.2 the effect breaks down (WC2022 turns slightly
negative), so it is weight-fragile as well as uncertain. The pre-registered reading required both
World Cups positive and the band clear of zero for even a provisional effect; the second condition
is not met, so this does not clear the degraded bar.

The honest status: the tournament-compression mechanism is directionally consistent with the data
(both World Cups nudged the right way at the low weight), but 128 matches over two blocks cannot
certify a 0.004 effect, exactly as the pre-registration expected. The hypothesis is now frozen,
dated, and hashed; its confirmation or refutation waits for out-of-sample World Cups (2030, or the
FC24 to FC26 editions extending historical World Cup coverage). 2026 is never selected on. This is
the strongest single hint the EA sub-attribute data produced, and it is still not bankable today.

## Status and what remains

Kept: the 17-column data/ea_ratings.csv, the extended research/build_ea_ratings.py, and
research/ea_subattr_kill_test.py. Not built: any Java change. The shipped model is unchanged
and better evidenced for it.

Budget: both slots are spent. Slot 1 (atk_pen) failed its gate; slot 2 (the set-piece pair on the
World Cup surface, above) returned a directional but uncertifiable positive, both World Cups agreeing
at the low weight while the bootstrap band spanned zero. Zero slots remain and the EA sub-attribute
campaign is closed: nothing shipped, the model unchanged, and the full arc (double-kill ladder,
atk_pen gate failure, set-piece World Cup characterization) banked with numbers. Only future
out-of-sample World Cups can confirm the frozen set-piece hypothesis.

2026 remains untouched. No odds data entered this campaign.
