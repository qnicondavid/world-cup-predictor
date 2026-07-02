# World Cup Predictor

A prediction model for FIFA World Cup matches, trained on 150+ years of
international football results (49,000+ matches, 1872 to today). Predictions are
served from a **Dixon-Coles goal model** with a squad market-value prior, locked
before kickoff, and scored against real results as the tournament unfolds. The
harder question behind the project was whether the probabilities are sharp enough
to beat a bookmaker's closing line. Tested against real closing odds from four
past World Cups, the model comes out level with the line: a small edge after
calibration, but well inside the margin of error, so not a demonstrated one. How
it gets there, and where it stops, is the rest of this README.

**Live demo: [qnicondavid.github.io/world-cup-predictor](https://qnicondavid.github.io/world-cup-predictor/)**

## Live results

A GitHub Action runs daily: it pulls fresh results, locks predictions for
upcoming fixtures with the production model, scores completed ones, and rewrites
the tables below automatically.

<!-- TRACKER:START -->
Δ is the total goal difference from the actual result (🎯 = exact), and Brier is multiclass.

**Record: 53/82 picks correct (64.6%), multiclass Brier 0.525, mean goal error 1.9** (uniform guess = 0.667)

| Date | Match | Winner | H/D/A % | Score (xG) | Result | Δ | Hit |
|---|---|---|---|---|---|---|---|
| Jul 1 | England vs DR Congo | England | 57/30/14% | 1-0 (1.3–0.5) | 2-1 | 2 | ✅ |
| Jul 1 | Belgium vs Senegal | Belgium | 43/29/28% | 1-1 (1.4–1.0) | 3-2 | 3 | ✅ |
| Jul 1 | United States vs Bosnia and Herzegovina | United States | 64/21/15% | 2-0 (2.1–0.9) | 2-0 | 0 🎯 | ✅ |
| Jun 30 | Ivory Coast vs Norway | Norway | 30/30/40% | 1-1 (1.0–1.2) | 1-2 | 1 | ✅ |
| Jun 30 | France vs Sweden | France | 62/22/16% | 2-0 (2.0–1.0) | 3-0 | 1 | ✅ |
| Jun 30 | Mexico vs Ecuador | Mexico | 35/34/31% | 0-0 (0.9–0.9) | 2-0 | 2 | ✅ |
| Jun 29 | Brazil vs Japan | Brazil | 45/29/26% | 1-0 (1.4–1.0) | 2-1 | 2 | ✅ |
| Jun 29 | Germany vs Paraguay | Germany | 53/27/21% | 1-0 (1.6–0.9) | 1-1 | 1 | ❌ |
| Jun 29 | Netherlands vs Morocco | Morocco | 33/32/35% | 1-1 (1.0–1.0) | 1-1 | 0 🎯 | ❌ |
| Jun 28 | South Africa vs Canada | Canada | 19/30/50% | 0-1 (0.7–1.3) | 0-1 | 0 🎯 | ✅ |
| Jun 27 | Algeria vs Austria | Austria | 33/30/37% | 1-1 (1.3–1.3) | 3-3 | 4 | ❌ |
| Jun 27 | Jordan vs Argentina | Argentina | 2/12/86% | 0-3 (0.5–3.7) | 1-3 | 1 | ✅ |
| Jun 27 | Colombia vs Portugal | Colombia | 36/30/35% | 1-1 (1.3–1.3) | 0-0 | 2 | ❌ |
| Jun 27 | DR Congo vs Uzbekistan | Uzbekistan | 26/28/46% | 1-1 (1.1–1.5) | 3-1 | 2 | ❌ |
| Jun 27 | Panama vs England | England | 8/19/73% | 0-2 (0.7–2.5) | 0-2 | 0 🎯 | ✅ |
| Jun 27 | Croatia vs Ghana | Croatia | 81/15/4% | 3-0 (3.1–0.5) | 2-1 | 2 | ✅ |
| Jun 26 | Egypt vs Iran | Iran | 22/27/51% | 1-1 (1.0–1.7) | 1-1 | 0 🎯 | ❌ |
| Jun 26 | New Zealand vs Belgium | Belgium | 6/18/76% | 0-2 (0.6–2.8) | 1-5 | 4 | ✅ |
| Jun 26 | Cape Verde vs Saudi Arabia | Saudi Arabia | 29/29/42% | 1-1 (1.2–1.5) | 0-0 | 2 | ❌ |
| Jun 26 | Uruguay vs Spain | Spain | 10/21/69% | 0-2 (0.7–2.3) | 0-1 | 1 | ✅ |
| Jun 26 | Norway vs France | France | 19/26/56% | 0-1 (0.9–1.8) | 1-4 | 4 | ✅ |
| Jun 26 | Senegal vs Iraq | Senegal | 61/25/15% | 1-0 (2.0–0.8) | 5-0 | 4 | ✅ |
| Jun 25 | United States vs Turkey | Turkey | 27/28/45% | 1-1 (1.1–1.5) | 2-3 | 3 | ✅ |
| Jun 25 | Paraguay vs Australia | Paraguay | 37/30/33% | 1-1 (1.3–1.3) | 0-0 | 2 | ❌ |
| Jun 25 | Curaçao vs Ivory Coast | Ivory Coast | 9/20/71% | 0-2 (0.7–2.5) | 0-2 | 0 🎯 | ✅ |
| Jun 25 | Ecuador vs Germany | Germany | 33/30/38% | 1-1 (1.2–1.4) | 2-1 | 1 | ❌ |
| Jun 25 | Japan vs Sweden | Japan | 67/22/11% | 2-0 (2.3–0.7) | 1-1 | 2 | ❌ |
| Jun 25 | Tunisia vs Netherlands | Netherlands | 8/19/73% | 0-2 (0.7–2.6) | 1-3 | 2 | ✅ |
| Jun 24 | Mexico vs Czech Republic | Mexico | 65/23/11% | 2-0 (2.2–0.8) | 3-0 | 1 | ✅ |
| Jun 24 | South Africa vs South Korea | South Korea | 9/20/70% | 0-2 (0.7–2.4) | 1-0 | 3 | ❌ |
| Jun 24 | Canada vs Switzerland | Switzerland | 34/30/36% | 1-1 (1.3–1.3) | 1-2 | 1 | ✅ |
| Jun 24 | Bosnia and Herzegovina vs Qatar | Bosnia and Herzegovina | 52/27/21% | 1-0 (1.7–1.0) | 3-1 | 3 | ✅ |
| Jun 24 | Scotland vs Brazil | Brazil | 11/23/66% | 0-2 (0.8–2.2) | 0-3 | 1 | ✅ |
| Jun 24 | Morocco vs Haiti | Morocco | 78/17/5% | 2-0 (2.9–0.6) | 4-2 | 4 | ✅ |
| Jun 23 | Portugal vs Uzbekistan | Portugal | 68/22/10% | 2-0 (2.3–0.7) | 5-0 | 3 | ✅ |
| Jun 23 | Colombia vs DR Congo | Colombia | 76/18/6% | 2-0 (2.8–0.6) | 1-0 | 1 | ✅ |
| Jun 23 | England vs Ghana | England | 88/10/2% | 4-0 (4.0–0.4) | 0-0 | 4 | ❌ |
| Jun 23 | Panama vs Croatia | Croatia | 15/25/60% | 0-1 (0.9–2.0) | 0-1 | 0 🎯 | ✅ |
| Jun 22 | France vs Iraq | France | 84/13/3% | 3-0 (3.4–0.5) | 3-0 | 0 🎯 | ✅ |
| Jun 22 | Norway vs Senegal | Norway | 48/28/24% | 1-1 (1.6–1.1) | 3-2 | 3 | ✅ |
| Jun 22 | Argentina vs Austria | Argentina | 71/20/9% | 2-0 (2.4–0.7) | 2-0 | 0 🎯 | ✅ |
| Jun 22 | Jordan vs Algeria | Algeria | 17/25/58% | 0-1 (0.9–1.9) | 1-2 | 2 | ✅ |
| Jun 21 | Belgium vs Iran | Belgium | 49/27/23% | 1-1 (1.6–1.0) | 0-0 | 2 | ❌ |
| Jun 21 | New Zealand vs Egypt | Egypt | 22/27/52% | 0-1 (1.0–1.7) | 1-3 | 3 | ✅ |
| Jun 21 | Spain vs Saudi Arabia | Spain | 91/8/2% | 4-0 (4.5–0.4) | 4-0 | 0 🎯 | ✅ |
| Jun 21 | Uruguay vs Cape Verde | Uruguay | 77/18/6% | 2-0 (2.8–0.6) | 2-2 | 2 | ❌ |
| Jun 20 | Germany vs Ivory Coast | Germany | 63/24/12% | 2-0 (2.1–0.8) | 2-1 | 1 | ✅ |
| Jun 20 | Ecuador vs Curaçao | Ecuador | 87/11/2% | 3-0 (3.9–0.4) | 0-0 | 3 | ❌ |
| Jun 20 | Netherlands vs Sweden | Netherlands | 68/22/10% | 2-0 (2.3–0.7) | 5-1 | 4 | ✅ |
| Jun 20 | Tunisia vs Japan | Japan | 8/19/73% | 0-2 (0.7–2.6) | 0-4 | 2 | ✅ |
| Jun 19 | Scotland vs Morocco | Morocco | 17/25/58% | 0-1 (0.9–1.9) | 0-1 | 0 🎯 | ✅ |
| Jun 19 | Brazil vs Haiti | Brazil | 84/13/3% | 3-0 (3.4–0.5) | 3-0 | 0 🎯 | ✅ |
| Jun 19 | United States vs Australia | United States | 38/30/32% | 1-1 (1.4–1.2) | 2-0 | 2 | ✅ |
| Jun 19 | Turkey vs Paraguay | Turkey | 46/28/26% | 1-1 (1.5–1.1) | 0-1 | 1 | ❌ |
| Jun 18 | Czech Republic vs South Africa | Czech Republic | 59/25/16% | 1-0 (1.9–0.9) | 1-1 | 1 | ❌ |
| Jun 18 | Mexico vs South Korea | Mexico | 54/26/20% | 1-0 (1.8–1.0) | 1-0 | 0 🎯 | ✅ |
| Jun 18 | Switzerland vs Bosnia and Herzegovina | Switzerland | 76/18/6% | 2-0 (2.8–0.6) | 4-1 | 3 | ✅ |
| Jun 18 | Canada vs Qatar | Canada | 85/12/3% | 3-0 (3.6–0.5) | 6-0 | 3 | ✅ |
| Jun 17 | Portugal vs DR Congo | Portugal | 76/18/6% | 2-0 (2.8–0.6) | 1-1 | 2 | ❌ |
| Jun 17 | Uzbekistan vs Colombia | Colombia | 10/21/69% | 0-2 (0.7–2.3) | 1-3 | 2 | ✅ |
| Jun 17 | England vs Croatia | England | 51/27/22% | 1-1 (1.7–1.0) | 4-2 | 4 | ✅ |
| Jun 17 | Ghana vs Panama | Panama | 13/25/62% | 0-2 (0.8–2.1) | 1-0 | 3 | ❌ |
| Jun 16 | France vs Senegal | France | 66/23/11% | 2-0 (2.2–0.8) | 3-1 | 2 | ✅ |
| Jun 16 | Iraq vs Norway | Norway | 9/20/71% | 0-2 (0.7–2.5) | 1-4 | 3 | ✅ |
| Jun 16 | Argentina vs Algeria | Argentina | 72/19/8% | 2-0 (2.5–0.7) | 3-0 | 1 | ✅ |
| Jun 16 | Austria vs Jordan | Austria | 60/25/15% | 1-0 (2.0–0.9) | 3-1 | 3 | ✅ |
| Jun 15 | Belgium vs Egypt | Belgium | 63/24/13% | 2-0 (2.1–0.8) | 1-1 | 2 | ❌ |
| Jun 15 | Iran vs New Zealand | Iran | 65/24/11% | 2-0 (2.2–0.8) | 2-2 | 2 | ❌ |
| Jun 15 | Spain vs Cape Verde | Spain | 93/5/2% | 5-0 (5.0–0.3) | 0-0 | 5 | ❌ |
| Jun 15 | Saudi Arabia vs Uruguay | Uruguay | 8/20/72% | 0-2 (0.7–2.5) | 1-1 | 2 | ❌ |
| Jun 14 | Germany vs Curaçao | Germany | 88/10/2% | 4-0 (4.0–0.4) | 7-1 | 4 | ✅ |
| Jun 14 | Ivory Coast vs Ecuador | Ecuador | 14/25/61% | 0-2 (0.8–2.0) | 1-0 | 3 | ❌ |
| Jun 14 | Netherlands vs Japan | Netherlands | 36/30/35% | 1-1 (1.3–1.3) | 2-2 | 2 | ❌ |
| Jun 14 | Sweden vs Tunisia | Sweden | 42/29/29% | 1-1 (1.5–1.2) | 5-1 | 4 | ✅ |
| Jun 13 | Qatar vs Switzerland | Switzerland | 3/12/85% | 0-3 (0.5–3.6) | 1-1 | 3 | ❌ |
| Jun 13 | Brazil vs Morocco | Brazil | 46/28/26% | 1-1 (1.5–1.1) | 1-1 | 0 🎯 | ❌ |
| Jun 13 | Haiti vs Scotland | Scotland | 15/25/60% | 0-1 (0.8–2.0) | 0-1 | 0 🎯 | ✅ |
| Jun 13 | Australia vs Turkey | Turkey | 25/28/48% | 1-1 (1.1–1.6) | 2-0 | 2 | ❌ |
| Jun 12 | Canada vs Bosnia and Herzegovina | Canada | 75/18/7% | 2-0 (2.7–0.6) | 1-1 | 2 | ❌ |
| Jun 12 | United States vs Paraguay | United States | 36/30/34% | 1-1 (1.3–1.3) | 4-1 | 3 | ✅ |
| Jun 11 | Mexico vs South Africa | Mexico | 75/16/9% | 2-0 (2.0–0.6) | 2-0 | 0 🎯 | ✅ |
| Jun 11 | South Korea vs Czech Republic | South Korea | 44/23/33% | 1-1 (1.2–1.2) | 2-1 | 1 | ✅ |

**Locked for upcoming matches:**

| Date | Match | Winner | H/D/A % | Score (xG) |
|---|---|---|---|---|
| Jul 2 | Spain vs Austria | Spain | 58/25/17% | 1-0 (1.7–0.8) |
| Jul 2 | Portugal vs Croatia | Portugal | 50/27/23% | 1-0 (1.5–0.9) |
| Jul 2 | Switzerland vs Algeria | Switzerland | 40/28/32% | 1-1 (1.4–1.2) |
| Jul 3 | Australia vs Egypt | Australia | 36/35/30% | 0-0 (0.9–0.8) |
| Jul 3 | Argentina vs Cape Verde | Argentina | 77/18/5% | 2-0 (2.1–0.4) |
| Jul 3 | Colombia vs Ghana | Colombia | 64/24/12% | 1-0 (1.8–0.6) |
| Jul 4 | Canada vs Morocco | Morocco | 22/34/45% | 0-1 (0.7–1.1) |
| Jul 4 | Paraguay vs France | France | 13/19/68% | 0-1 (0.6–1.7) |
| Jul 5 | Brazil vs Norway | Brazil | 62/19/19% | 1-1 (1.7–1.0) |
| Jul 5 | Mexico vs England | England | 22/22/55% | 0-1 (0.9–1.5) |
| Jul 6 | United States vs Belgium | Belgium | 30/21/49% | 1-1 (1.3–1.5) |

<!-- TRACKER:END -->

### Championship odds

<!-- TITLE:START -->
The model's championship odds from 10,000 Monte Carlo simulations, updated 2026-07-02. They inherit the simulator's simplifications (knockout bracket paired in schedule order, games as neutral with no draws), so read them as the model's view, not a hard forecast.

| # | Team | Title | Final | Semis |
|---|---|---|---|---|
| 1 | France | 22.8% | 39.3% | 55.9% |
| 2 | Argentina | 22.8% | 36.0% | 52.2% |
| 3 | Spain | 14.4% | 25.6% | 45.8% |
| 4 | Brazil | 8.6% | 17.7% | 29.3% |
| 5 | England | 7.6% | 17.3% | 38.1% |
| 6 | Colombia | 4.3% | 9.7% | 19.4% |
| 7 | Morocco | 4.2% | 10.2% | 22.5% |
| 8 | Mexico | 3.9% | 9.5% | 25.5% |
| 9 | Belgium | 2.9% | 8.0% | 24.8% |
| 10 | Portugal | 2.7% | 6.5% | 16.2% |
| 11 | Norway | 1.6% | 4.6% | 10.8% |
| 12 | Switzerland | 1.4% | 4.2% | 13.8% |
| 13 | Croatia | 0.6% | 2.0% | 6.3% |
| 14 | United States | 0.6% | 2.6% | 11.6% |
| 15 | Canada | 0.4% | 1.7% | 5.8% |
| 16 | Australia | 0.4% | 1.5% | 6.4% |

<!-- TITLE:END -->

## Track record on past World Cups

Before predicting 2026, the model is validated on five World Cups it never saw
during training. For each tournament it trains only on matches played before it,
then predicts every match in it, the same information regime as predicting live.

| Tournament | Tuned model | Baseline |
|---|---|---|
| World Cup 2022 | 32/64 (50.0%), Brier 0.183 | 34/64 (53.1%), Brier 0.181 |
| World Cup 2018 | 37/64 (57.8%), Brier 0.159 | 34/64 (53.1%), Brier 0.167 |
| World Cup 2014 | 39/64 (60.9%), Brier 0.135 | 39/64 (60.9%), Brier 0.150 |
| World Cup 2010 | 35/64 (54.7%), Brier 0.146 | 32/64 (50.0%), Brier 0.148 |
| World Cup 2006 | 41/64 (64.1%), Brier 0.119 | 42/64 (65.6%), Brier 0.129 |
| **Combined (320)** | **184/320 (57.5%), Brier 0.148** | 181/320 (56.6%), Brier 0.155 |
| Coin-flip reference | 50%, Brier 0.250 | n/a |

The tuned model beats both the baseline and a coin flip across the combined 320
matches. One pattern stands out: **World Cups are getting harder to predict.**
Brier rises almost monotonically from 0.119 (2006) to 0.183 (2022); the field
has genuinely tightened.

## How it works

The production model is **Dixon-Coles**: every team gets a separate **attack**
and **defence** rating, fit by weighted maximum likelihood on all of
international history, with a home-advantage term, the low-score correlation
correction (`rho`) that fixes Poisson's under-counting of 0-0 and 1-1,
exponential time decay (2-year half-life), and shrinkage toward the average for
rarely-seen teams. Squad market value is folded in as a **prior** on those
ratings. From the fitted attack/defence pair the model produces a full scoreline
distribution, and from that the win/draw/loss probabilities and most-likely
score you see above.

```
data/results.csv -> MatchCsvParser -> Dixon-Coles fit (+ value prior) -> scoreline distribution -> predictions
```

The original engine is an **Elo rating system**: every team starts at 1500, and
after each match ratings shift by `K * (actual - expected)` with K scaled by
match importance and a home boost at non-neutral venues. Elo still drives the
Monte Carlo title simulation and remains the baseline every goal model is
measured against.

## Why you can trust it

Every figure in the track record above comes from
World Cups the model never trained on, predicting each match before its result,
so nothing is fit to the games it is judged on. The live 2026 picks follow the
same discipline.

Live predictions are written to
`predictions/predictions.csv` before kickoff and never changed; the git history
is the audit trail. A prediction made under an older model is preserved as-is
and never re-locked.

Several intuitive ideas were tested
honestly and did not earn their place, and they stay documented because that is
why the rest can be believed:

- **Rest-days advantage**: no out-of-sample improvement (`--rest`).
- **Bivariate covariance term**: adds nothing over Dixon-Coles (Brier 0.573 vs
  0.574).
- **Temperature scaling**: sharpened in-sample but made held-out 2022 worse on
  every metric, so none is applied.
- **Annual regression toward the mean**: never helped at any strength;
  national-team strength is more persistent than folklore suggests.

What did survive: goal-margin scaling (combined Brier 0.148 vs 0.155) and a
small, tuned squad-value prior.

### More negative findings from goal-model research

Three more ideas were tested on the five held-out World Cups (320 matches, 2006-2022)
and did not clear the bar:

- **Elo + Dixon-Coles ensemble blend**: leave-one-tournament-out cross-validation
  drove the learned weight to near-pure Elo in every fold. The blend scored
  +0.0007 worse than plain Elo on the held-out set (95% CI [0.0000, +0.0019]);
  the confidence interval never favors the blend. Dead.
- **Symmetric draw scaling**: a single multiplicative factor k on the draw
  probability, tuned via LOTO-CV, reverted to k=1.0 (no-op) every time, and
  held-out Brier did not move. Scaling every draw up or down uniformly changes
  nothing, because the freed probability flows back to both sides in proportion.
  That reads like a dead end, and for the symmetric version it is. The mistake was
  assuming the fix had to be symmetric: the model does over-produce draws (mean
  predicted 0.283 vs a 0.225 base rate), but the surplus belongs on the favourite,
  not split evenly. The asymmetric version of this idea, the draw-transfer under
  Methodology, is the one calibration change that later cleared the gate.
- **Half-life retune**: longer decay half-lives (~3 years) lean slightly
  better; pooled held-out Brier improved by roughly -0.003 (0.595 vs 0.598).
  That delta is inside the approximately plus-or-minus 0.015 to 0.020 noise
  floor implied by block-bootstrap CIs over five tournaments, so the change
  is not adopted as a standalone improvement.

A fourth idea showed real structure but was absorbed by the value prior. A
cross-confederation strength correction estimates a per-confederation-pair
goal-difference residual from training data and applies it to
inter-confederation matchups. On the Python Dixon-Coles baseline (no value
prior) it improved combined Brier by roughly -0.016 (95% CI excludes zero, all
five World Cups negative, gain in resolution). But re-measured on the
production model through the export bridge (--verify-export, scored with
verify.py --score), the gain collapsed to about -0.005 with a 95% CI of
[-0.012, +0.005] that spans zero, and one tournament reversed sign. The
squad-value prior and confederation strength are partly redundant, since rich
squads cluster in the strong confederations, so the prior already absorbs
roughly two-thirds of the effect. Not adopted on the production model, where
the residual sits inside the noise. The export bridge and verification harness
(research/verify.py) built to settle this are kept, since every future idea is
judged the same way.

Three later ideas were tested the same way and also did not clear the gate.
**Favourite recalibration** (a leave-one-tournament-out map that sharpens the
favourite's probability) cut reliability but traded away resolution and reversed
sign on one tournament, leaving a 95% CI of [-0.013, +0.001] that grazes zero:
the temperature lesson a third time, not adopted. **Dynamic / state-space
ratings** (a two-timescale strength blend) gave at most a noise-floor Brier
change with no certifiable resolution lift. **Lineup-weighted squad value** (the
actual starting XI valued as-of the match date, sourced from StatsBomb open data
for 2018 and 2022) carried only a weak residual signal (correlation 0.06) that
did not transfer between tournaments and cost resolution out of sample, so the
harder 2006-2014 backfill was not pursued; the collectors live in
research/fetch_lineups.py and research/lineup_value.py as a record of the
attempt.

Across the campaign three changes survived this gate: the strengthened value
prior, the recent-form nudge, and a draw-transfer calibration, together moving the
held-out Brier from 0.5717 to 0.5441. The first two mostly bought resolution,
sharper separation between outcomes. The third went back for a calibration defect
the earlier symmetric tests had written off, once the decomposition made clear the
leftover error was draws landing on the wrong side rather than too much draw mass
overall. Everything else, the recalibration maps and the extra rating machinery,
kept washing out. Only changes that add real signal or fix a real bias held up out
of sample.

## Methodology in depth

### Draw modelling

The Elo expected score conflates winning and drawing (E = P(win) + P(draw)/2).
To split it, P(draw) is estimated empirically: replaying 37,314 internationals
since 1980 through the model shows the draw rate falling from ~30% between equal
teams to ~2% at a 600-point rating gap. `DrawModel` interpolates that observed
curve and splits E into explicit win/draw/loss probabilities. An honest
limitation: the model never makes "draw" its single most likely outcome (~30% is
the ceiling), so the draw model improves probabilities, not picks;
bookmakers share this property.

### Goal models

A goal model gives every team a separate attack and defence rating and predicts
the scoreline, yielding win/draw/loss probabilities from first principles
rather than from an empirical draw curve. Three live under
`com.david.worldcup.goals`, comparable head-to-head via `--goals`:

- **Dixon-Coles**: the production model (described above).
- **Bivariate Poisson**: the same attack/defence fit plus a shared component
  that makes the two scores positively correlated.
- **Elo-Poisson**: the lightweight option, reusing the Elo gap and mapping it to
  two Poisson rates by regression.

Scored on 320 World Cup matches (2006-2022), train-before-each-tournament:

| Model | Picks correct | Combined multiclass Brier |
|---|---|---|
| Dixon-Coles | 183/320 (57.2%) | 0.574 |
| Bivariate Poisson | 183/320 (57.2%) | 0.573 |
| Elo-Poisson | 178/320 (55.6%) | 0.575 |
| Elo + DrawModel (baseline) | 178/320 (55.6%) | 0.576 |
| Uniform reference | n/a | 0.667 |

The goal models edge the Elo baseline modestly. The edge is uneven across
tournaments, so an **Elo + Dixon-Coles ensemble** (averaging the two probability
vectors) is also wired into `--goals`. This fixed average is a different
construction from the learned blend banked as dead above, where
leave-one-tournament-out drove the weight toward near-pure Elo; the average lands
inside the noise floor of plain Dixon-Coles, so read it as a reference, not a win.
The fitter itself is validated against
`research/goal_models.py`: on data from a known Dixon-Coles process it recovers
team attack strengths at correlation 0.99.

### Squad market value

Elo and goal ratings are lagging: they learn strength from results. Squad
market value is a leading signal. The model folds it in as a **prior on the
Dixon-Coles attack/defence ratings**: a richer-than-average squad gets a higher
attack and lower (better) defence prior, and each team's fitted rating is shrunk
toward that prior. It reads `data/market_values.csv` (`team,as_of,value_eur`);
lookups always take the most recent value on or before the match date, so
nothing leaks from the future.

`--values-tune` grid-searches the weights on 2006-2018 and validates once on
held-out 2022. Held-out testing through the verification harness showed the
value prior was under-exploited, so a widened sweep was run; the tuned prior
(`globalWeight 0.40, sparseWeight 0, valueScale 0.60`, roughly double the
earlier setting) beats plain Dixon-Coles out of sample (multiclass Brier
**0.5907 vs 0.6123** on 2022) and is now the default. Scored across all five
held-out World Cups through the export bridge, it cuts the production model's
combined Brier from 0.5717 to 0.5566, with the gain split between better
calibration (reliability 0.0226 to 0.0136) and sharper separation (resolution
0.0914 to 0.0957). Caveats kept in view: four of five tournaments improve while
2010 is marginally worse, and the sparse-team lever still earns nothing. The
shipped `market_values.csv` is a small **illustrative** sample; replace it with
real data (see Data below).

### Recent form

Squad value and the fitted ratings move slowly; recent results do not. A
`FormAdjuster` nudges the win/draw/loss probabilities by each side's recent
defensive form, the mean goals conceded over its last 5 matches before kickoff
(leakage-safe, since only prior matches count). Measured on the production
model's held-out predictions through the export bridge, a conservative
coefficient cuts the combined Brier from 0.5566 to 0.5506, with the gain almost
entirely in resolution (sharper separation, the component the model was losing
to) and improving in all five tournaments. It is shipped and wired into the live
tracker, so daily predictions carry it. One caveat: the nudge moves the
probabilities, not the expected goals, so the most-likely-score column still
comes from the raw model.

### Draw-transfer calibration

The model over-produces draws. Averaged over the five held-out World Cups it puts
about 0.283 on the draw where the real rate is 0.225, a bias Dixon-Coles inherits
from its low-score correction. The obvious fix, scaling the draw probability down,
does nothing out of sample (see the symmetric-scaling note under negative
findings), so for a while this looked settled.

What the symmetric test missed showed up in the closing-line backtest. Split by
match type, the model lost most to the market on moderate favourites, matches
priced around 45 to 65 percent for one side. A Murphy decomposition put that loss
in reliability rather than resolution and traced it to the home and draw
probabilities. The draw mass was not simply too large; it was sitting between the
two teams when it belonged on the favourite.

The fix moves a fixed fraction of each match's draw probability onto whichever side
the model already favours, then renormalises. The fraction, about 0.21, is fit
leave-one-tournament-out and stays stable across folds. Scored the same way as
every other change, it cuts the held-out Brier from 0.5506 to 0.5441, improves
four of the five tournaments (2010 is flat), and the block-bootstrap interval on
the gain clears zero. The whole improvement is reliability, the exact component
the decomposition flagged. Direction is what makes it work: a band-restricted
version and a symmetric split both failed the gate, and only the global,
favourite-directed transfer passed it. It ships as `Calibration.transferDraw` and
is applied in the export and the live tracker, so daily predictions carry it.

### Calibration

`--calibrate` audits the production model on the held-out World Cups: reliability
bins, log-loss, multiclass Brier and expected calibration error (ECE), plus a
temperature fit. The finding: the model is mildly **under-confident** (ECE ≈
0.06), but the calibration direction is not stable across tournaments, so no
temperature is applied and the raw probabilities ship as-is. The practical
consequence for any betting layer is to demand a margin of safety and size
conservatively.

### Against the closing line

This is the question the project was built around, so it earns a real answer
rather than a mock one.

The value-betting loop is simple. `--bets` reads bookmaker odds, strips the
overround to fair probabilities, and compares them to the model for each fixture.
When an outcome's expected value clears a threshold it is flagged and sized by
fractional Kelly, on a conservative default policy (a 5% edge floor, quarter-Kelly,
capped at 5% of bankroll) because the calibration wobbles between tournaments.

The hard part was getting real closing odds to test against, which international
football mostly lacks. Two sources filled the gap: an OddsPortal aggregate for the
2006, 2010 and 2014 World Cups, and a scrape of 2018 and 2022. The model's held-out
predictions were then scored against the de-vigged closing line on the same
matches, which is the only fair comparison. Across 272 matches:

| World Cups | Matches | Model Brier | Market Brier | Difference |
|---|---|---|---|---|
| 2006, 2010, 2014 | 173 | 0.5291 | 0.5363 | -0.0072 |
| 2018, 2022 | 99 | 0.5643 | 0.5684 | -0.0042 |

The model edges the line on both sets, but each margin sits inside one standard
error and the block-bootstrap intervals over the tournaments span zero. The honest
read is parity: after the draw-transfer calibration the model is level with the
sharpest line available, leaning very slightly favourable, without a gap wide
enough to call an edge. For a model built on public data, reaching the closing
line is already near the ceiling.

The paper ROI made the same point from the other side. A naive run of the value
policy showed a positive return, but almost all of it came from a few longshots
that happened to land, and one of those was a data bug: neutral-venue matches label
home and away differently across sources, and a position-wise join once paid a
favourite's win at the underdog's price. Joining on the unordered team pair removed
the phantom, and what remains is what the Brier numbers imply, small disagreements
with the market that carry no reliable edge.

The live test runs forward. `research/fetch_odds_live.py` captures pre-kickoff
prices, flags value bets under the same policy, and appends them to a never-edited
ledger; `research/settle_bets.py` grades them and measures closing-line value. A
verdict there needs a few hundred settled bets, so it is a long-run instrument, not
a result yet. The early returns match the backtest: the first settled bets, all
contrarian draw-or-underdog flags, lost, while the model's straight match picks
came in.

### Rest-days differential (experimental)

`--rest` tests whether a team with more recovery than its opponent has an edge
the rating misses: it adds rating points per day of rest advantage (capped at 10
days) and measures held-out Brier against the unadjusted baseline. It needs no
new data, so it is fully reproducible. As noted above, the effect did not survive
out of sample.

## Run it

Requires JDK 17+ and Maven.

```bash
mvn test                            # run the unit test suite
mvn compile exec:java               # replay history, print Elo top 15 + sample predictions
mvn compile exec:java -Dexec.args="--backtest"   # evaluate on the held-out World Cups
mvn compile exec:java -Dexec.args="--tune"       # hyperparameter grid search
mvn compile exec:java -Dexec.args="--track"      # lock/score predictions, update README
mvn compile exec:java -Dexec.args="--simulate"   # Monte Carlo: 10,000 tournament sims
mvn compile exec:java -Dexec.args="--upcoming"   # every fixture with win/draw/loss probs
mvn compile exec:java -Dexec.args="--predict=France,Argentina"   # any matchup
mvn compile exec:java -Dexec.args="--goals"      # goal models vs Elo: held-out comparison
mvn compile exec:java -Dexec.args="--rest"       # does a rest-days edge improve the model?
mvn compile exec:java -Dexec.args="--values"     # does squad market value improve the model?
mvn compile exec:java -Dexec.args="--values-tune" # grid-search the market-value prior weights
mvn compile exec:java -Dexec.args="--calibrate"  # reliability / log-loss audit + temperature fit
mvn compile exec:java -Dexec.args="--bets"       # value bets vs bookmaker odds (mock odds)
mvn compile exec:java -Dexec.args="--verify-export" # write held-out predictions to research/export_predictions.csv
```

(PowerShell: quote the whole flag, e.g. `mvn compile exec:java "-Dexec.args=--simulate"`.)

## Data & credits

Match data from [martj42/international_results](https://github.com/martj42/international_results)
(includes scheduled 2026 fixtures, used as the prediction list). Refreshed daily
by the tracker Action.

Squad market values come from the Transfermarkt community datasets (no public
API exists, so download where you have network access, not from CI):

- [dcaribou/transfermarkt-datasets](https://github.com/dcaribou/transfermarkt-datasets):
  the best fit, a `player_valuations` table with dated market values plus
  national-team data, refreshed weekly. Aggregate player valuations to a squad
  total per national team per date to build `market_values.csv`.
- [salimt/football-datasets](https://github.com/salimt/football-datasets) and the
  Kaggle mirror [davidcariboo/player-scores](https://www.kaggle.com/datasets/davidcariboo/player-scores)
  are alternatives.
