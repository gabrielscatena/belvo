# Review findings and correction decisions

Baseline for the second review: `ad9ad1e` (29 October 2026). Original evaluations remain
preserved. All new April analyses are post-inspection diagnostics; they do not restore an
untouched holdout. No response-model probabilities were retuned.

| Finding | Judgment | Correction / evidence |
|---|---|---|
| Calendar support concealed January-only coverage. | Confirmed. Ordinary-day B has 36,568 candidate attempts supported by 665 January observations; 28,002 lack expanded joint-cell history. | [Revised diagnostics](../reports/evaluation/calibration_v2/candidate_support.csv) expose counts, recent qualifying months and weak coverage; a conservative gate is evaluated separately. |
| April anticipates use of A. | Confirmed: 67.35% of remaining units in 30/91 days. This makes a monthly gain insufficient evidence of contract value. | [Horizon sensitivities](../reports/evaluation/horizon_v1/summary.json) apply identical cumulative release schedules to both policies, with independent consumption ledgers. |
| Front-loading explains most of the estimated gain. | Not established. Same fixed expense cancels in the difference; future opportunity value is unobserved. | Pacing alone reduces the model difference by 27.2% while shifting into unsupported B days. Combined pacing/admission reduces it by 75.9%; these interacting sensitivities are not causal attribution. |
| Contract capacity is protected only within a day. | Incorrect: the transactional ledger enforces cumulative consumed + reserved capacity across days. | Distinguish the hard invariant from unimplemented optimal intertemporal allocation. |
| Tariff residual -181,200.76 measures bias or unused capacity. | Incorrect. It is the monthly cost minus nominal usage charges, an accounting bridge. | Keep [economic views](../reports/evaluation/economic_views_v1/README.md) separate from selection and physical capacity. |
| Candidate/bound/refit ranges anchor the primary narrative. | Fair communication criticism. | README and three-page design now lead with observed legacy, missing proof, capacity anticipation and weak support. Model numbers remain in the [results audit appendix](09_results.md). |
| Amount/calendar/history model is insufficiently validated. | Confirmed limitation, not a solved issue. | Keep calibration and [known-truth stress](../reports/validation/synthetic_stress_v1.json); synthetic optimism is 2.43x, not Belvo's identified bias factor. Feature development requires pre-test validation and new prospective evidence. |
| Runtime does not learn from persisted outcomes. | Confirmed prototype boundary. | Explicit in architecture/risks; production needs operational history, cost feedback and a separate runtime refit policy. No feedback loop is claimed. |

## Interpretation rules

- Daily release is a sensitivity assumption, not a correction to the contract. Unspent
  allowance carries forward; consumption need not follow a line or finish at zero.
- Filtering logged legacy plans creates a hypothetical subset replay. Rank without
  outcomes, keep plans whole, and retain the original **80,758.24** observed benchmark.
- The recent-calendar gate requires at least 100 pure attempts in a qualifying recent
  month for a provider/date type. Nonzero all-history counts remain descriptive; passing
  the gate does not establish exchangeability or provider effects.
- Historical unused-capacity revenue at a constant average is an illustrative scenario,
  not a credible ceiling. It mixes lenders, dates, DPD and uncertain future demand.
- Training-cluster refits rescore fixed actions. Twenty repetitions give coarse parameter
  percentiles, excluding model misspecification, causal confounding and future states.

Earlier confirmed engineering fixes remain: locked Makefile setup, slack-capacity selector,
versioned state, exact-money tests and idempotent recovery. Source/probability provenance,
AI assistance and elapsed checkpoints remain disclosed. Historical docs support audit;
the entry points are README, three-page design and results.

Recommendation remains **shadow only**. Six-month lender profitability, a realistic
sequential ceiling and positive causal uplift are not established. The scenario gate is
not silently promoted to the runtime default. See [ADR 0006](adrs/0006_review_corrections.md)
and the [evaluation protocol](07_evaluation_protocol.md).
