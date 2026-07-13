# Contributing

Thanks for taking an interest. This project has one unusual rule that shapes
everything else: a change ships only if it clears an out-of-sample gate, and most
proposed changes do not. Sixteen ideas are documented as rejected in the README;
three survived. A carefully measured failure, with its confidence interval, is a
genuinely useful contribution here, not a wasted pull request.

## The gate

Every candidate change is scored the same way the headline numbers are:
leave-one-tournament-out over the five held-out World Cups (2006 to 2022, 320
matches). Train only on matches before each tournament, predict all of it, and
compare against the current production model with a paired block-bootstrap
confidence interval on the change in combined multiclass Brier.

A change is adopted only if the whole 95% interval clears zero on the better side.
A point estimate that looks good but whose interval grazes zero is a near miss, and
near misses stay documented as rejected rather than merged. This is deliberate:
with only 320 held-out matches, the interval is the honest unit, not the point
estimate.

## Proposing an idea

Open an **Idea to test** issue before writing code. Describe the hypothesis in one
sentence, what information the signal adds beyond what the model already uses (squad
market value, recent form, and the fitted ratings), and how it can be computed using
only information available before kickoff. Ideas that only re-express existing signal
tend to be absorbed by the value prior; the issue form walks through this.

## Submitting a change

1. Reproduce the current baseline first:

   ```
   mvn -q compile exec:java -Dexec.args="--verify-export"
   python research/verify.py --score research/export_predictions_form.csv
   ```

2. Implement your change behind its own flag or config so it can be toggled.
3. Export your variant's held-out predictions and run the paired gate:

   ```
   python research/verify.py --paired export_predictions_form.csv export_predictions_yourchange.csv
   ```

4. In the pull request, report the mean delta Brier and its 95% CI, the per-tournament
   direction, and whether the interval clears zero. Say plainly if it does not; a
   rejected idea with a clean measurement is welcome and will be added to the
   documented ledger.

## Leakage rules (non-negotiable)

- Training for a held-out tournament uses only matches dated before it.
- Feature lookups (market value, form) take the most recent value on or before the
  match date, never after.
- Live 2026 predictions are locked in git before kickoff and never edited.

## Development

- JDK 17+ and Maven. `mvn test` runs the unit suite.
- The research and evaluation harness lives in `research/` (Python 3).
- Do not commit large data dumps. `data/market_values.csv` rebuilds byte-for-byte
  from `research/build_market_values.py`; raw dumps stay out of the repo (see
  `.gitignore`).

## Reporting problems with the live tracker

If a score, championship number, or the live site looks wrong during the tournament,
open a **Tracker / data bug** issue with the date, match, and what you expected.
A locked prediction that looks wrong is expected (they are never edited after
kickoff); this is for scoring, data, or display problems.
