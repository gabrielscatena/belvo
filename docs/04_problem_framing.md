# 04 — Problem Framing and Optimization Specification

**Project:** Belvo — Intelligent Collections Engine

**Stage:** Business specification; see implemented [ADRs](adrs/README.md) and [protocol](07_evaluation_protocol.md).

**Inputs:** [Business process](01_business_process.md) · [Domain model](02_domain_model.md) · [Economic model](03_economic_model.md)

## 1. Decision problem in one paragraph

Each day, lenders submit their current outstanding loan portfolios. For **each observed loan on that date**, Belvo must choose **no attempt** or a feasible plan with one or more payment installments, each with an amount and a provider assignment. The business objective is the highest **expected full-window absolute net margin** while respecting the outstanding balance, per-installment lender cap, the remaining six-month prepaid capacity of provider A, and a requirement to plan for positive expected margin **for each lender**. A daily incremental score is a tractable approximation to this dynamic objective, not its definition. Results from submitted transactions arrive the next day and inform future decisions. **Full-window realized margin**, after the prepaid A commitment and B per-attempt fees, is the ultimate business metric.

### Supplied facts and current evidence

The [package README](provided/README.md) specifies **2026-01-01 to 2026-04-30**, a uniform **1-in-15 loan sample**, and an A window of **2026-01-01 to 2026-06-30**. The 10,000,000-unit commitment refers to the **full book**. Cross-table EDA and operational tests pass; causal uplift remains unverified. May-June collections are not observed. The [protocol](07_evaluation_protocol.md) instantiates a sample scenario and [results](09_results.md) separate observed, estimated and projected money. The full mathematical specification below exceeds the prototype's restricted heuristic; it is not a claim that a global stochastic optimizer was implemented.

## 2. Explicit objective / decision / constraint separation

| Category | Definition |
|---|---|
| Business objective | Maximize **absolute net margin** for Belvo, not successful-payment count, gross collections, or margin percentage |
| Atomic decision grain | `loan_id + decision_date`; include `client_id` if loan IDs are not global |
| Candidate actions | No attempt, or a plan containing installment count, amounts, and provider choice **per installment** |
| Local feasibility | Positive installment amounts; each `<= max_installment_amount`; their total `<= outstanding_balance` |
| Shared resource | Provider A: prepaid allowance of 10,000,000 units over six months, net of used units |
| Business-level restriction | Forecast positive full-window margin for **every lender**, using an explicit allocation of A's upfront cost |
| Feedback | Submitted attempts today; outcomes reported the following day |
| Global planning horizon | Six-month A contract window; daily decisions are revised with new portfolio snapshots and payment history |
| Evaluation target | Baseline vs candidate **net margin**, by lender and overall, and a defensible attainable-margin estimate |

The challenge examples mention one, two, or three installments; they do **not explicitly establish three as a maximum**. Treat the maximum installment count as a configurable modeling bound, documented as an assumption.

## 3. Notation

| Symbol | Meaning |
|---|---|
| `t` | Decision / portfolio date |
| `c ∈ C` | Lender |
| `l ∈ L_t` | Loan appearing in the portfolio at time `t` |
| `P_{l,t}` | Generated feasible plan alternatives for loan `l` at `t`, including no attempt |
| `J(p)` | Set of installments in plan `p` |
| `m_j`, `g_j` | Amount and provider (`A`/`B`) of installment `j` |
| `r(d_{l,t})` | Commission fraction determined by loan's DPD on attempt date |
| `\hat p_{l,t,p,j}` | Predicted success probability for installment `j` conditional on the full plan |
| `n_A(p)`, `n_B(p)` | Count of installments assigned to each provider |
| `Q_t` | Available unconsumed prepaid A units immediately before day `t` submissions |
| `x_{l,t,p}` | Binary variable: plan `p` is selected for loan `l` on date `t` |
| `\widehat{OC}_{A,t}(p)` | Estimated future opportunity cost of using A units for plan `p` |
| `W`, `F_A`, `Q_0` | January-June contract window, upfront cost 10,000,000, initial allowance 10,000,000 (full-book scale) |
| `\mathcal F_t`, `S_t` | Information available before the decision and the corresponding portfolio, payment-history and capacity state |
| `\pi` | A policy selecting plans using only currently available information |
| `w_{c,W}`, `\varepsilon_c` | Disclosed lender fixed-cost weight and strictly positive monetary profitability threshold |

### Full-horizon reference problem

At the start of the contract, the conceptual policy objective is:

$$
\max_{\pi}\;\mathbb E_{\pi}\left[
\sum_{a:\,\operatorname{attempt\_date}(a)\in W}
\left(y_a m_a r(d_a)-2\,\mathbf 1\{g(a)=B\}\right)
\right]-F_A.
$$

Only the selected, actually submitted installments contribute. The policy is **non-anticipating**: current plans may depend on `\mathcal F_t`, never future snapshots or outcomes. Along every execution path, local amount constraints and total A usage `<= Q_0` apply. For each lender, impose the prospective expected full-window counterpart:

$$
\mathbb E_{\pi}\left[
\sum_{a:\,\operatorname{attempt\_date}(a)\in W,\ c(a)=c}
\left(y_a m_a r(d_a)-2\,\mathbf 1\{g(a)=B\}\right)
\right]-F_A w_{c,W}\ge\varepsilon_c>0.
$$

Weights are nonnegative and sum to one over the declared lender scope. This expected constraint is a planning approximation to the brief's realized-profitability requirement, not a guarantee that realized margins will be positive. The six-month lender reporting horizon and fixed-cost allocation are modeling choices. `F_A` is constant after purchase and therefore does not change the unconstrained ranking of policies, but it remains essential to total margin and lender feasibility.

The stochastic state transition includes policy-driven collections and changes in balance/history, together with uncertain portfolio disappearance, reappearance and future demand. No transition law is supplied. This is a **reference specification**, not a claim that a dynamic program has been implemented or identified from the CSVs. The daily formulation below is a restricted approximation.

## 4. Feasible plan construction

For each loan-day, generate a finite and **documented** candidate set, including the null plan `p=∅`. Every positive-collection plan must satisfy:

$$
0 < m_j \le \operatorname{cap}_{c(l)},\quad \forall j\in J(p),
$$

$$
\sum_{j\in J(p)} m_j \le \operatorname{outstanding\_balance}_{l,t},
$$

$$
g_j \in \{A,B\}.
$$

The installments for a selected plan must all be **submitted on day `t`**. For `p=∅`, define `J(p)=∅`, no additional provider charge, and no submitted attempt; previously committed costs remain applicable. Amounts must respect the documented two-decimal currency precision. Use integer minor units or decimal arithmetic, and define commission rounding separately. Do not hardcode equal installment values unless modeling assumptions justify doing so. For tractability, start with a small set of candidate amounts/counts/provider assignments; describe its coverage and any resulting approximation gap. A zero-balance loan admits only no-attempt; invalid balances or caps must be flagged rather than converted into collection plans.

## 5. Expected plan value

For a binary full-payment outcome per installment, expected commission from candidate plan `p` is:

$$
\widehat{R}_{l,t,p} = r(d_{l,t})
\sum_{j\in J(p)} m_j\,\widehat p_{l,t,p,j}.
$$

The sum uses **marginal probabilities conditional on the complete plan**, so it does **not require installment independence**. These probabilities are not available for arbitrary counterfactual actions directly from the legacy data; estimating them requires care about historical action coverage and selection bias.

The supplied dictionary defines successful `amount` as collected and failed `amount` as attempted. `debtor_bank` does not identify a debtor or account, so cross-loan shared-funds effects cannot be verified from the supplied schema. Ignoring them is a documented portfolio-model approximation, not established independence.

An incremental score consistent with the supplied economic-flow diagram is:

$$
\widehat{V}_{l,t,p} =
\widehat R_{l,t,p} - 2\,n_B(p)
- \widehat{OC}_{A,t}(p).
$$

Within the prepaid allowance, A's **incremental cash payment** is zero because its 10-million monetary-unit commitment has already been paid. Its **opportunity cost may be nonzero** if available capacity is scarce relative to future demand. Do not include the fixed upfront commitment again in the daily incremental score.

**Avoid double counting:** if a multi-period optimization already models the value of future capacity explicitly, omit any separately derived shadow-price penalty for the same scarcity effect. A hard feasibility limit is still necessary.

This score omits non-capacity continuation effects, including lower future balances, changes in DPD commission rates, and alternative future collection dates. The null plan has zero **immediate** score but may retain future value. A policy maximizing the displayed daily score is therefore a myopic approximation with a capacity-value adjustment; it is not proven to maximize the reference full-horizon objective.

## 6. Portfolio-level optimization (daily approximation)

Select exactly one feasible plan per loan:

$$
\max_{x}\; \sum_{l\in L_t}\sum_{p\in P_{l,t}}
\widehat V_{l,t,p}\,x_{l,t,p}
$$

subject to:

$$
\sum_{p\in P_{l,t}}x_{l,t,p}=1
\quad\forall l\in L_t,
$$

$$
\sum_{l\in L_t}\sum_{p\in P_{l,t}}
 n_A(p)\,x_{l,t,p}\le Q_t,
$$

$$
x_{l,t,p}\in\{0,1\}.
$$

Local amount/provider constraints are already enforced when constructing `P_{l,t}`. Within the window and under a single-batch assumption, update prepaid capacity as `Q_{t+1} = Q_t - actual_unique_A_submissions_t`, reconciling any discrepancies between planned and actually submitted transactions. For concurrent batches, subtract outstanding reservations from usable capacity before further selections. The ledger counts each real provider transaction once and does not change on duplicate callbacks or idempotent re-delivery; a genuinely new transaction consumes another unit. Uncertain submission outcomes require reconciliation rather than automatic release and resubmission under a new identity. At expiry, unused units are unavailable and no renewed pool is assumed.

The formula above is at **full-book scale**. For this loan extract, do not place raw sample demand against all 10,000,000 units and claim a full-book optimum. A weighted scenario can constrain `15 * sample_A_usage <= estimated_full_book_remaining_capacity`; alternatively declare a sample-scale quota/cost scenario. Both are approximations requiring sensitivity analysis, consistent scaling of the ledger and fixed cost, and an explicit treatment of unobserved full-book usage. Inclusion weights do not make the nonlinear policy optimum or its uncertainty known.

### Expected full-window profitability by lender

The challenge explicitly requires each lender to remain profitable. A **proposed forward-looking operational constraint** is:

$$
\widehat M^{\mathrm{window}}_{c,t}(x) \ge \varepsilon_c > 0
\quad \forall c\in C,
$$

One explicit decomposition, conditioned on information available at `t`, is:

$$
\widehat M^{\mathrm{window}}_{c,t}(x)=
R^{\mathrm{known}}_{c,<t}
+\widehat R^{\mathrm{pending}}_{c,<t}
+\sum_{l\in L_t:\,c(l)=c}\sum_{p\in P_{l,t}}
\widehat R_{l,t,p}x_{l,t,p}
+\widehat R^{\mathrm{future}}_{c,>t}(x)
-2\left[
N_{B,c,<t}
+\sum_{l\in L_t:\,c(l)=c}\sum_{p\in P_{l,t}}n_B(p)x_{l,t,p}
+\widehat N^{\mathrm{future}}_{B,c,>t}(x)
\right]-F_Aw_{c,W}.
$$

Here, prior submitted attempts have known B costs even if their payment outcomes are pending. Prior realized revenue and expected pending revenue are disjoint. Current plans and future forecasts must likewise be disjoint, and all terms must share the same horizon and sample/full-book scale. Future forecasts depend on the state resulting from today's plans; freezing them is an additional approximation that can misstate the lender constraint. Capacity opportunity costs do **not** enter this financial margin. This prospective definition is **not specified directly in the brief** and must be validated with the business.

A lender's realized margin can still be non-positive despite a positive expected margin. If the constraint makes the feasible set empty (including the no-attempt choices), **report infeasibility** rather than claiming a guarantee. Alternative policies, such as thresholded risk of loss or conditional participation, require stakeholder approval.

**Formalization caveat:** if the lender's cost allocation or future forecast depends nonlinearly on current decisions, the profitability expression may not be linear. The resulting model should not be described as a linear or mixed-integer linear program without establishing linearity or applying a justified approximation.

For a fixed finite candidate set, additive fixed plan scores, fixed lender weights and a justified affine future-value/profit approximation, the daily selection can be expressed as a binary linear optimization. No solver family, solution quality or runtime is established before implementation. Declare the monetary `\varepsilon_c` and solver tolerance; this is not the same as choosing an arbitrary large profitability target.

## 7. Why decisions are dynamic

This is not a static allocation problem: a loan can disappear and reappear with a different outstanding balance; the DPD changes; prior payment outcomes update the probability model; and the prepaid A allowance declines toward expiry. Accordingly:

- Execute the decision policy **once per daily portfolio**.
- Use an as-of feature cutoff so payment outcomes from `t+1` cannot leak into a decision at `t`.
- The package's history starts on January 1 after some loans were already active: observed zero prior attempts does not mean no lifetime attempts. For `t-1` outcomes, explicitly assume arrival before today's cutoff or apply a conservative extra lag.
- Recompute expected values with current state, remaining A units, and a rolling demand forecast.
- Persist each plan, decision timestamp, model/configuration version, and submission identity for auditability.

An initial prototype can implement a **one-day optimization with a capacity-value heuristic**. A longer-term extension could model the six-month horizon via rolling-horizon stochastic optimization. Neither approach is assumed to have already been validated.

## 8. Modeling, baseline, and offline evaluation

### Minimum prototype pipeline

```text
Daily loan snapshots + lender caps + known prior outcomes
    -> data validation / as-of features
    -> feasible plan generation (including no attempt)
    -> installment success probabilities / expected commissions
    -> plan valuation and shared-resource optimization
    -> one decision per loan-date, installments and providers
    -> offline economic evaluation and lender-level reporting
```

**Baseline:** reconstruct the **observed** legacy policy's revenue and fees using historical payment attempts and commission by attempt-date DPD. Avoid treating all loans without a recorded attempt as if the historical system had deliberately rejected them for economic reasons.

**Temporal evaluation:** use chronological development/validation/test periods. For each evaluated day, ensure feature availability matches the decision cutoff. Compare both total margin and the complete lender distribution of margins.

The package covers only January-April, and April 30 outcomes are available on May 1 under the stated convention. Label any completed historical outcomes used for evaluation separately from decision-time features. Distinguish (i) observed sample results, (ii) 15x-weighted observed-period full-book estimates, and (iii) projected January-June full-book results. May-June cannot be presented as observed data, and an A cost prorating rule does not replace a forecast of missing activity. Keep the same accounting scope and fixed-cost allocation across legacy, candidate and ceiling estimates. Also report the recorded-fee usage-priced diagnostic defined in [03](03_economic_model.md), separately from prepaid-contract economics.

**Counterfactual limitation:** recorded outcomes are available for **executed historical actions**, not every new amount, plan, or provider the candidate policy could have chosen. A simple replay or accuracy metric is therefore insufficient to establish a policy improvement. Inspect action overlap and consider conservative scenario evaluation, uncertainty bounds, and—when assumptions/propensities allow—off-policy estimation. Do not invent propensity scores for a deterministic legacy policy.

In particular, future historical snapshots already reflect the legacy policy's collections. Reusing them unchanged after a candidate takes different actions can deduct collections twice or resurrect debt already collected in the simulated policy. A one-step evaluation on legacy states must be labeled as such; a multi-day comparison needs explicit state transitions and assumptions about external payments, loan exits/re-entry, and unobserved future demand. These transitions are not identified merely by fitting a success classifier. Repeated observations and correlated installments also require loan-aware and, where appropriate, calendar-block uncertainty estimates.

**Estimated attainable ceiling:** report an explicitly *model-dependent* expected maximum under the same constraints, together with uncertainty/sensitivity ranges and candidate-set/solver gaps. A feasible policy provides an achievable value only within its assumed model; it is not a certified upper bound on all policies or on real earnings. An oracle relaxation can be an optimistic bound only with a coherent horizon and balance evolution: assuming success separately on every historical snapshot can collect the same debt repeatedly and is not a valid bound on attainable policy performance. Distinguish real observed revenue, predicted counterfactuals, model optima and hypothetical upper bounds throughout.

## 9. Proposed evaluation and deployment gates

| Gate | Evidence required |
|---|---|
| Input integrity | Keys, dates, balance/amount constraints, lender mapping, missingness |
| Modeling validity | Time-consistent features, calibration by lender/DPD/provider/amount, supported action coverage |
| Financial correctness | Consistent A prepayment, B costs, per-client A cost allocation, margin reconciliation |
| Policy feasibility | One plan per loan-date; no over-limit installment; no overspending A quota; explicit infeasibility handling |
| Offline improvement | Like-for-like margin in monetary units vs historical baseline, with uncertainty and honest caveats |
| Safe rollout (future) | Shadow decisions, small monitored canary, idempotent submissions, accounting alerts, rollback criteria |

The challenge requests a **design document, a small functioning prototype, and a short results report**; it does **not** require implementing production infrastructure or an API. The proposed deployment gates belong in the design narrative only.

## 10. Assumptions and open decisions

| Item | Current working assumption / question |
|---|---|
| A usage outside prepaid pool | Not allowed in the prototype; additional pricing is unspecified |
| Contract horizon and coverage | A: January 1-June 30, 2026; observed sample: January 1-April 30. Dates are supplied, empirical coverage requires EDA |
| Sampling scale | Uniform 1-in-15 loan sample; A commitment is full-book. Weighted totals and sample-scale capacity scenarios require explicit assumptions |
| Payment outcome | Supplied dictionary supports binary collected/failed accounting; production partial recoveries would need an extension |
| Installment count | Bound used for plan enumeration must be justified; 1–3 are examples, not a declared hard maximum |
| Lender-level profit | Expected positive full-window margin before execution; realized results monitored afterward |
| A fixed-cost allocation | Must be defined, applied consistently, and sum to the full upfront payment |
| Probabilities and provider effects | Estimates from legacy policy may be confounded; do not infer causal provider superiority from raw rates |
| Real-time requirements | Unknown; a daily batch prototype matches the described workflow unless other constraints emerge |
| Dynamic state transitions | Legacy snapshots cannot be reused as unchanged candidate-policy trajectories; transition/scenario assumptions remain unvalidated |

## 11. EDA handoff and refinement checklist

The archive already contains the CSVs, README, and dictionary. The next step is empirical validation, not obtaining unspecified files. Record evidence and revise these working documents as needed:

1. **Keys and joins:** uniqueness, dated lender attribution, duplicate attempts, join completeness and row-count preservation.
2. **Time and coverage:** actual date ranges, left-truncated histories, portfolio gaps/re-entry, outcome availability and complete loan-day installment groups.
3. **Amounts and fees:** two-decimal precision, installment caps, attempted sums vs dated balance, fee mapping, and documented status semantics.
4. **Economic reconstruction:** observed commission and recorded-fee diagnostic by lender; keep A consumption, prepaid fixed cost, accounting horizon and sample weights separate.
5. **Legacy support:** distributions of amounts, installment counts, providers, DPD and no-observed-attempt patterns; distinguish supported comparisons from extrapolation.
6. **Model feasibility:** label prevalence, temporal stability, calibration opportunities, cross-installment effects and sample size within action/lender strata. Do not infer causal effects from raw differences.
7. **Dynamic and horizon uncertainty:** inspect balance changes without declaring all changes to be collections; document unresolved external payments and May-June scenarios.
8. **Specification decisions:** choose the candidate-plan grid, capacity scenario, lender fixed-cost weights, profitability threshold and comparison horizon; report sensitivity rather than selecting assumptions solely to produce favorable margins.

**Current status:** cross-table checks and local operational tests pass. The [final design](design_document.md) condenses the implemented slice; [results](09_results.md) provide a restricted-model estimate and upper bound. Causal improvement, universal lender profitability and an achievable sequential six-month ceiling remain unestablished. The full specification here is not a claim of a global optimizer.
