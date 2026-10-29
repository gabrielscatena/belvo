# ADR 0006: Versioned selection correction and economic diagnostics

Status: Accepted for the local prototype. Date: 2026-10-29.

Context: External review reproduced a selector defect: choosing an A plan by gain per
unit and then refusing further replacements can leave a higher-value plan unselected
even when capacity is spare. The review also requested stronger money-path tests and
diagnostics. Its proposed scarcity charges must not become additional cash expenses.

Decision: Supersede the selection algorithm in [ADR 0004](0004_economic_policy.md)
with `economic_heuristic_v2`, retaining its empirical response model and declared
prototype limitations. Begin with B/no-attempt baselines and lender-priority capacity
allocation. If every loan's independently best score fits the shared quota and satisfies
all evaluated lender requirements, use those joint choices: they maximize the separable
score over the admitted finite plans under those conditions.

Otherwise retain capacity-aware allocation and apply deterministic replacements using
**incremental** A units, including for loans already assigned A. Each replacement must
strictly improve score or retain equal score while freeing capacity. It must not reduce
a satisfied lender below its requirement or worsen an existing unmet contribution.
The finite candidate set and monotone replacements terminate. This is a local
improvement heuristic under scarcity, not a certificate of optimality or infeasibility.

Runtime policy identity includes the selector version; decision basis also includes
selector/model/budget identity. Existing policy-version stores fail closed on mismatch.
Use a new simulation store and preserve old evidence rather than silently replanning
already submitted effects. Source revisions and unknown-submission protection remain
unchanged; the selector correction does not authorize duplicate external attempts.

Preserve `frozen_v1` and `verified_v2`. Publish corrected actions separately in
`selector_v3` and label them post-review engineering evidence. The probability model,
feature cells and price configuration are unchanged. April diagnostic inspection is
disclosed; revised policy results are not new untouched-test evidence.

Add four complementary diagnostic views:

1. Amount/calendar/lender/history calibration and finer historical-support slices,
   with training-fixed amount boundaries and information-available history.
2. Seeded known-response synthetic stress and an independent end-to-end money oracle.
3. Cash allocation sensitivities with equal primary weights, fixed pretest A-use weights
   identical across policies, and own-policy A-use weights marked diagnostic. Keep nominal
   tariff usage pricing separate, reconciling its residual to the one fixed cash payment.
4. Training-loan cluster refits of fixed actions. Report finite replication count,
   support changes and exclusions; parameter variation does not identify causal response.

An opportunity price changes a decision score, not realized accounting. Fixed-action
lambda tables neither select a price nor reoptimize the policy. No second A invoice,
forced end-of-June depletion target, or six-month forecast is introduced. Historical
observed-action hindsight cannot bound all counterfactual actions. Incomplete C11
coverage cannot establish final contract infeasibility.

Alternatives: Replacing all ratio ordering with absolute gain can make scarce allocation
worse. A full optimizer cannot repair misspecified or confounded probabilities. Adding
response features after seeing April would be statistical redesign requiring separate
development/validation disclosure. Subtracting shadow prices from accounting would
mix objectives and expenses.

Consequences: The concrete slack-capacity error is corrected and regression-tested.
Money reconciliation and synthetic failure modes become reproducible. Conditional model
estimates change, while observed legacy accounting and the response model remain fixed.
Future demand pacing, sequential state transitions, operational feedback, causal gains
and six-month lender profitability remain unvalidated; live rollout is not approved.

Evidence: [review appendix](../11_external_review.md),
[selector tests](../../tests/test_selector_frontier.py),
[money tests](../../tests/test_synthetic_evaluation.py),
[accounting views](../../reports/evaluation/economic_views_v1/README.md),
[refit summary](../../reports/evaluation/refit_v1/summary.json).
