# Phase 3 Candidate 5 pre-registration

Learned residual probe, used as a detector. Candidate 5 in notes/model/BRIER_PLAN.md. Committed before the probe is built and before any attribution is seen, so the feature set, the method, and the interpretation rule are frozen. Any change after commit is recorded in the deviations log at the bottom.

## Purpose and non-goal

Candidate 4 closed the form channel and the Phase 1 re-gates closed the confederation and form-lambda directions. The honest open question is whether any systematic structure remains that the production model does not already capture. A constrained learner over tens of thousands of training matches is the cheapest way to search interactions no human pre-registered.

Non-goal, frozen: the gradient-boosted model is not a shipping candidate. The project ships only changes with a mechanism and a decomposition story, and neither the 320-match World Cup gate nor the 2,180-match expanded surface can justify a black box. The probe's only output is a ranked, attributed map of what it learned beyond the production model. Each interpretable finding becomes a new, separately pre-registered, single-formulation candidate, gated the normal way. Nothing the probe surfaces ships without that second step.

## Features, frozen

Per match, on the expanded-surface windows under the train-before, predict-after regime, the probe sees only these inputs:

1. The production model's own outputs: p_home, p_draw, p_away, plus the derived rate gap (lambda_home minus lambda_away) and total (lambda_home plus lambda_away) from the per-window fit.
2. The value gap: home minus away standardised log squad value, as-of or before the match date.
3. The opponent-adjusted recent-form residual for each side, from FormResidualAdjuster (the Candidate 4 feature), computed from the per-window fit.
4. The confederation pair: home confederation and away confederation.
5. Rest-days differential, tournament stage, and the neutral-venue flag.

Target: the three-class outcome (home win, draw, away win).

Explicitly excluded, to keep the search clean and leakage-free: any odds or market price, squad identities, anything dated at or after kickoff, and the result of the match being predicted.

## Leakage audit, frozen (runs before any fit)

Before any model trains, every feature is audited to be computable strictly from information available before kickoff, from a fit trained only on earlier matches. Rest days and stage are safe (the schedule is known in advance). The form residual and the model outputs use only prior matches and the pre-tournament fit. Confederation pair and neutrality are static. The value gap uses the latest value on or before the match date. Any feature that fails this audit is dropped before the probe runs and the drop is recorded in the deviations log. The audit result is printed and saved with the run.

## Method, frozen

Per leave-one-tournament-out fold on the expanded surface: train a small gradient-boosted classifier (shallow trees, strong regularisation, early stopping on an inner split) on that fold's training matches only, predict the held-out edition, and attribute the held-out predictions. Attributions use SHAP where available, and fall back to sklearn permutation importance on the held-out set if SHAP cannot be installed; the choice is recorded with the run. Pool the held-out predictions across folds.

Report two things: whether the probe's pooled held-out multiclass Brier beats the production model at all, and the pooled feature attributions read as a map of where any residual structure sits.

## Interpretation rule, frozen

If the probe does not beat the production model out of sample, the finding is "no residual structure detectable beyond the production model," written to the negative-findings ledger, and the search closes. If it does beat the model, only the named, interpretable drivers by attribution are carried forward, each as its own pre-registered candidate gated the normal way.

Stated in advance so a null result is not spun as a failure and a lucky one is not overread: the expected outcome, given everything already closed, is that the probe rediscovers the confederation axis (already known, already shown not to help post-hoc) and little else. A null result is the modal prediction and is a clean, publishable close of the search.

## Reproduction

Scripts land under research/ when built (a Java per-match feature export plus a Python probe), odds-free by construction. The feature export reproduces the expanded-surface match set as a special case, and the probe is seeded.

## Deviations log

(none yet)
