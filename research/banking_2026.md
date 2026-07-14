# 2026 out-of-sample banking: pre-committed framing and checklist

Written before the 2026 World Cup final (scheduled around July 19, 2026), so the interpretation
is frozen before the outcome is known. This is how the 2026 live record gets banked once the final
is played. It commits the framing now so the post-final write-up reports the number rather than
spins it. 2026 is and remains a pure test set: nothing here tunes any model parameter, and no
locked prediction is ever re-locked.

## What 2026 is, and is not

The load-bearing out-of-sample figure for the project stays the WC-320 held-out multiclass Brier,
0.5441 over the 2006 to 2022 World Cups. The 2026 live record is a separate and smaller
out-of-sample sample (about 104 matches by the final, in the 48-team format), scored on predictions
git-locked before each kickoff. It corroborates the held-out result on genuinely unseen data, but it
does not replace it as the headline, because a hundred-odd matches is a thin sample and multiclass
and binary Brier sit on different scales.

Current standing before the final, for reference only (to be refreshed, not edited by hand): the
tracker has scored 100 of the 2026 matches at multiclass Brier about 0.502; on the 98 with a
captured market price the model is about 0.507 against the de-vigged consensus 0.459. These move as
the last matches resolve; the final banked numbers come from the commands below.

## What to compute after the final (mechanical, no choices)

1. Score the last results and refresh the site data and the README block:
   `mvn -q compile exec:java "-Dexec.args=--track"`
   Record the final matches scored, the correct percentage, and the multiclass Brier it prints.
2. Refresh the model-versus-market comparison:
   `python3 research/live_vs_market.py`
   Record the model and market multiclass Brier over the matches with captured odds, and the count
   of matches the model was sharper on. This writes docs/data/live_market.json, which the site reads.
3. Reference only, unchanged: the calibrated model-versus-market statement stays the 99-match 2018
   and 2022 single-book closing-line comparison (model 0.5643 versus market 0.5684, a parity of
   -0.0042), already in the README. 2026 does not overwrite it.

## The framing, pre-committed before the outcome

Whatever the numbers say, the write-up holds to these, decided now.

The 2026 model-versus-market gap is measured against a de-vigged cross-book consensus (measured
overround near 1.0, dipping below 1.0 on some matches), which is structurally sharper than any
single bookmaker's bettable line. So the 2026 gap is directional, not a clean model-versus-market
verdict, and the calibrated read stays the 2018 and 2022 single-book parity.

If the model's 2026 Brier beats or ties the consensus: report it as small-sample corroboration,
state the sharper-benchmark caveat in the same breath, and do not upgrade the headline claim beyond
"at parity with the closing line."

If the model's 2026 Brier loses to the consensus (the more likely case, since the consensus is
sharper than a single book): report it plainly, and attribute it to the already-documented
cross-confederation mid-tier mispricing (the model priced AFC and CONMEBOL sides above the market
and CAF and UEFA sides below, and the worst per-match losses were cross-confederation pairings of
mid-tier teams). That is a known, already-banked limitation, not a new surprise, and it is not
patched in response to 2026, because patching on the test set is the one thing the whole design
forbids.

The 2026 result confirms or refutes the shipped value-only model. It does not test the EA set-piece
hypothesis: the 2026 predictions carry no set-piece term, so that hypothesis still awaits a future
World Cup where a set-piece-augmented model is locked in advance (research/ea_subattr_setpiece_wc_
preregistration.md).

## What to update

README: flip the two "in progress" rows in the At-a-glance table (the Live 2026 record row and the
Model vs market consensus row) to a final status with the banked numbers, and update the one-line
summary beneath the table. Keep the honesty labels; the load-bearing figure stays the 0.5441.

Site: docs/data/tracker.json and docs/data/live_market.json refresh from the two commands above, and
the static page reads them, so the live table and the market panel update without hand-editing.

Optional: a short research/2026_out_of_sample.md with the final numbers and the framing above, for
the permanent record, mirroring the other results files.

## Non-negotiables, restated

2026 tunes nothing and selects nothing. No prediction is re-locked. The de-vigged-consensus caveat
is stated every time the 2026 market gap is mentioned. The headline out-of-sample number remains the
WC-320 0.5441; the 2026 record is corroboration, reported honestly whichever way it falls.
