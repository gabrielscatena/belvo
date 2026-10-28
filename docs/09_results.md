# Results and trust assessment

Frozen [protocol](07_evaluation_protocol.md), [outputs](../reports/evaluation/frozen_v1/results.md),
[lender table](../reports/evaluation/frozen_v1/per_client.csv),
[diagnostics / uncertainty](../reports/evaluation/frozen_v1/summary.json),
[sensitivity](../reports/evaluation/frozen_v1/sensitivities.csv).

April has 140,710 observed loan-days across 6,233 loans. The final probability baseline
uses labels through March 30 only. Each evaluated candidate action is feasible in cents
and the sampled A capacity scenario, including prior observed consumption. Evaluation
conditions on legacy portfolio states; it does not produce new observed outcomes.

| April net margin, sample currency | Result |
|---|---:|
| Observed legacy | 80,758.24 |
| Model-estimated legacy | 107,146.78 |
| Model-estimated candidate | 1,228,967.16 |
| Conservative candidate stress score, accounting convention unchanged | 713,158.07 |
| Relaxed supported-plan model ceiling | 1,257,322.98 |

All rows allocate 30/181 of the same upfront cost and use identical lender weights.
Multiply by 15 only for a full-book point extrapolation; this is not full-book optimization.
Lender margins reconcile with totals. All lenders have positive estimated April margins;
**C11 remains negative in Jan–Apr coverage when the entire contract cost is charged**.
Therefore the six-month profitability requirement has not been demonstrated.

The candidate's conditional estimate is the best feasible policy found, not a proven
optimum. Its gap to a relaxed model upper bound is 28,355.82. The upper bound ignores
quota coupling and lender constraints, retains restricted plans and fitted mean response,
and is **not** an achievable six-month ceiling. An intervention ceiling is not identifiable
from these data without additional assumptions or experimentation.

The large apparent uplift is especially uncertain: only 5.59% of candidate loan-day
actions exactly match legacy. Cell counts establish coarse historical coverage, not
causal overlap. Estimated legacy margin already overstates observed margin by 26,388.54.
Loan bootstrap intervals are conditional on the fitted model and legacy states; they
exclude response-model bias and changes in future balances. A lower stress score does
not fix those limitations or guarantee recovery. Provider rates are observational.

The candidate uses 275,962 A units and 42,153 B attempts in April, leaving 157,146 A units
after prior usage. All tested May–June continuations at 0.5/1/1.5 times April demand exceed
that remainder. Their margins are deliberately null rather than pretending that the
same plan can run after quota exhaustion. Live selection does enforce quota and falls
back to feasible B/no-attempt alternatives; future economic allocation needs refinement.

**Decision: do not recommend live deployment on these estimates.** Next evidence should
come from shadow operation, better action/amount support, lender-level calibration and
a capped randomized provider/plan pilot. A negative or uncertain conclusion is preferable
to presenting these estimates as verified gains. The prototype demonstrates the required
decision, accounting and operational slice; causal uplift and contract profitability remain open.
