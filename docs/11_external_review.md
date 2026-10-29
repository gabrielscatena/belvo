# External review: verified corrections and remaining limitations

Review baseline: `c862b5a`. The original [verified evaluation](../reports/evaluation/verified_v2/summary.json)
is preserved. The [revised selector checkpoint](../reports/evaluation/selector_v3/summary.json)
is a **post-review engineering correction**, not a second untouched April test.
No response features, fitted probability parameters or opportunity price were retuned.

The review correctly identifies weaknesses in the economic evidence. Operational and
selection fixes do not establish causal uplift or six-month lender profitability.
The appropriate recommendation remains **shadow evaluation, not live deployment**.

| Review claim | Verdict and evidence | Action taken | Residual limitation |
|---|---|---|---|
| Coarse response cells miss amount, calendar and history effects. | Confirmed limitation. April estimated/observed commission ratios vary from 0.83 to 1.54 across amount buckets and 0.81 to 1.28 across calendar groups. | Published [calibration slices](../reports/evaluation/calibration_v1/calibration_slices.csv), including lender, recency and known prior-failure groups; amount boundaries use training data. | These exploratory slices diagnose miscalibration; they do not identify action effects or quantify candidate bias. |
| A cell with 100 attempts establishes sufficient support. | Rejected as a causal interpretation. The revised candidate has 91,149 attempts in previously empty joint cells after adding amount/calendar dimensions; 150,640 have fewer than 100 joint observations. | Added [candidate support diagnostics](../reports/evaluation/calibration_v1/candidate_support.csv). | Original coarse cell support remains the admission rule. No stronger response model or supported causal policy is claimed. |
| Provider B only operates on first/15th/16th/month-end dates. | Partly correct: B occurs on 19 dates, but January 3, 6 and 9 are exceptions. | Published [provider-by-date evidence](../reports/evaluation/calibration_v1/provider_by_date.csv). | Calendar groups are observable date types, **not verified individual paydays**. A higher success rate on these dates is observational. |
| Synthetic ground truth exposes optimistic candidate estimates. | Confirmed failure mode. The current selector estimates 2,653,794.82 commission against 1,091,705.23 true expected commission: 2.43x. | Added a [seeded synthetic stress](../reports/validation/synthetic_stress_v1.json) and independent money tests. | This does not estimate bias on Belvo data. In this generator the candidate still beats legacy in true expected margin: 741,549.99 versus 108,220.30. |
| Ratio ordering wastes value even with spare capacity. | Confirmed defect and corrected. The supplied 5.4-versus-7.2 example now selects 7.2. | [Selector regressions](../tests/test_selector_frontier.py) cover slack capacity, incremental replacements, scarcity and lender priority. | Under scarcity the selector remains a local heuristic; it cannot certify global optimality or infeasibility. |
| The easy setup path omits pandas. | Confirmed defect and corrected. | [Makefile](../Makefile) now installs the MVP lock plus the MVP package extra. | Raw challenge data remain separately supplied; their expected location is documented. |
| A is incorrectly free and April cost allocation rewards front-loading. | Mixed. Incremental A **cash** cost is correctly zero after prepayment. The symmetric 30/181 fixed-cost allocation is a disclosed monthly convention. Missing future scarcity valuation is real. | Added [economic views](../reports/evaluation/economic_views_v1/README.md) and explicit fixed-action opportunity-price scores. | No opportunity price was selected or policy reoptimized for future demand. April accounting cannot establish contract profitability. |
| C11 is unprofitable under any reasonable cost treatment. | Not established. Nominal usage pricing gives -7,432.48, but allocating the same monthly cash commitment by current A use gives +10,968.50. Equal fixed allocation gives +12,981.42. | Published separate [cash allocations](../reports/evaluation/economic_views_v1/allocation_views.csv) and [usage-tariff diagnostics](../reports/evaluation/economic_views_v1/tariff_diagnostic.csv). | C11's Jan-Apr full-upfront coverage is -31,060.11. Missing May-Jun outcomes prevent proving either final profitability or final infeasibility. |
| Existing uncertainty excludes fitting variability. | Correct. Original loan resampling conditions on the fitted model and chosen actions. | Added [training-loan cluster refits](../reports/evaluation/refit_v1/summary.json). | Twenty refits yield unstable percentile estimates and do not cover confounding, model misspecification, action reselection or future-state effects. |
| The model ceiling is a realistic six-month ceiling. | Rejected. It is a restricted same-state fitted-mean relaxation; capacity and lender coupling are removed. | Retained its explicit scope and separate interpretation in [results](09_results.md). | A genuinely achievable sequential contract ceiling remains unidentified. |
| The runtime closes its learning and accounting loop. | Not implemented. Model fitting and lender budgets still use supplied CSV history. | The [feedback boundary](adrs/0005_source_order_and_model_evidence.md) remains explicit. | Production needs reconciled store outcomes, submitted costs and an independently specified online fitting policy. |

## Revised selector evidence

The [selector checkpoint](../reports/evaluation/selector_v3/summary.json) changes the
conditional candidate margin from **1,228,967.16 to 1,233,760.38**, with the response
model unchanged. A use rises from 275,962 to **291,698**; remaining sample capacity
falls to **141,410**. Exact legacy action match is **5.96%**, and the gap to the same
relaxed model bound is 23,562.60. These are model-conditioned results, not measured gains.

Repeating the revised April A pace would require about 593,119 units in May-Jun,
exceeding the remaining 141,410. Even half that continuation exceeds capacity.
The published continuation margins therefore remain unavailable. The live selector
respects capacity and can choose B/no-attempt; its future response and arrival mix have
not been forecast. A full contract projection cannot be created by continuing an
infeasible fixed action mix.

## Corrections to the proposed remedies

- **Keep cash margin separate from opportunity value.** In the
  [lambda table](../reports/evaluation/economic_views_v1/fixed_action_lambda.csv),
  prices 0/0.25/0.5/1/2 change fixed-action scores while accounting margin stays
  1,233,760.38. Subtracting that shadow penalty as an additional provider invoice would
  change the accounting definition and potentially count scarcity twice.
- **Distinguish allocation from tariffs.** Fixed pretest A-use weights remain identical
  across policies. Own-policy weights are sensitivity diagnostics. Subtracting 1 per A
  attempt is a usage-priced view, not allocation of the same fixed payment: its residual
  must reconcile back to cash cost. No-attempt does not erase allocated fixed cost.
- **Do not force capacity to zero on June 30.** Optimal use depends on future quality,
  demand and feasible positive-value actions. Leftover or early depletion is not by
  itself proof of an economic error; the missing forecast prevents such a conclusion.
- **Do not require incompatible bounds to bracket estimates.** An observed-action
  hindsight calculation cannot bound outcomes for unseen actions. A consistent-model
  relaxation bounds that model's feasible choices, not real-world or causal earnings.
- **Do not prescribe interval width.** Training-cluster refits add parameter variation;
  they do not repair structural bias. Here candidate-margin 2.5/97.5 percentiles are
  1,059,899.44/1,517,899.70 over 20 refits, with actions held fixed. They are not a
  complete confidence guarantee or an uncertainty range for true business uplift.

Next statistical work should compare amount/calendar/history specifications using
pre-test development data, evaluate operational feedback and demand pacing, then obtain
new prospective evidence. April-based diagnostics cannot restore untouched-test status.

Decision record: [ADR 0006](adrs/0006_review_corrections.md).
