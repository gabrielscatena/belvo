# Offline results

April conditional one-step replay on legacy states, sample scale

| April margin, currency units | Sample | Full-book ×15 point estimate |
|---|---:|---:|
| Observed legacy | 80,758.24 | 1,211,373.64 |
| Estimated legacy | 107,146.78 | 1,607,201.75 |
| Estimated candidate | 1,228,967.16 | 18,434,507.40 |
| Conservative candidate stress | 713,158.07 | 10,697,370.99 |
| Relaxed model ceiling | 1,257,322.98 | 18,859,844.69 |

The month allocates 30/181 of the fixed prepaid commitment equally by lender.
This is a monthly reporting convention, not final contract profitability.

Nonpositive candidate lenders (April): [].
Nonpositive lenders with full fixed cost in Jan–Apr coverage: ['C11'].
See per_client.csv; all lender amounts sum to their reported total.

The candidate is estimated, not observed. Provider selection is confounded;
coarse support bins and repeated snapshots cannot identify intervention effects.
The ceiling relaxes constraints under the fitted model and restricted plans;
it is not a certified achievable sequential/contract ceiling.
Loan bootstrap intervals capture sampling variation conditional on the model;
they exclude causal/model uncertainty. May–June is absent; projections that
exceed quota have no reported margin and require reoptimization.

Do not deploy solely from these results. Lender constraint warnings and
out-of-policy action mismatch are production blockers, not hidden exceptions.

## Rollout decision

**Not approved for live use.**

Exact action match is 5.59%; historical bin support is substantially weaker than intervention identification.
Legacy monetary margin error is 26,388.54. The very large projected uplift is not established business value.
Same-model candidate minus legacy estimate: 1,121,820.38. This is a conditional model-based difference, not measured causal uplift.
Candidate attempts: 318,115; legacy attempts: 93,772. Volume ratio: 3.39x.
Prepaid capacity is enforced; opportunity cost is configurable but zero in the frozen run.
Nonpositive full-upfront coverage lenders: ['C11'].
May-June continuation scenarios that exceed quota are explicitly marked infeasible;
they cannot justify a constant-composition contract projection.
The best feasible restricted one-step policy is only a model-based achievable estimate;
the true sequential six-month ceiling cannot be identified from this legacy dataset.
