# 03 — Economic Model: Revenue, Costs, and Margin

**Project:** Belvo — Intelligent Collections Engine

**Stage:** Economic specification; formulas are proposed interpretations of the challenge

Implementation update: [frozen protocol](07_evaluation_protocol.md),
[economic policy ADR](adrs/0004_economic_policy.md) and [results](09_results.md)
document the instantiated conventions and their limits. Full-window profitability is
not inferred from the restricted one-step prototype.

**Diagram:** [`diagrams/economic_flow.mmd`](../diagrams/economic_flow.mmd)

## 1. Objective and accounting perspectives

Belvo earns a **DPD-dependent percentage of successfully recovered funds**, and it pays for payment attempts regardless of success. The stated objective is to maximize **absolute net margin**, not gross collections or a percentage margin. Each lender must be profitable, and the solution should estimate a realistic achievable ceiling relative to the legacy policy.

The [economic-flow diagram](../diagrams/economic_flow.mmd) intentionally distinguishes:

- **Expected decision economics:** value of a candidate daily collection plan before its outcomes are known.
- **Realized contract economics:** commissions actually earned and provider payments charged over the six-month contract window.

**Do not add an estimated opportunity cost to realized accounting costs.** It is a decision-support quantity, not an additional invoice.

### Supplied coverage and scale

The supplied [package README](provided/README.md) specifies **2026-01-01 through 2026-04-30**, a uniform **1-in-15 sample of loans**, and an A contract window of **2026-01-01 through 2026-06-30**. A's 10,000,000 transactions and upfront payment refer to the **full book**. The extract therefore cannot establish realized six-month margin, exact full-book A consumption, or remaining full-book capacity by itself. May-June activity is unobserved. These are supplied metadata; empirical coverage checks remain part of EDA.

## 2. Commission and transaction terms (specified in the challenge)

| Days past due (on attempt date) | Belvo commission rate |
|---|---:|
| 0–5 | 15% |
| 6–15 | 20% |
| 16–30 | 25% |
| 31–60 | 30% |
| 61–90 | 40% |
| 91+ | 50% |

| Term | Provider A | Provider B |
|---|---|---|
| Published price | 1.0 per transaction | 2.0 per transaction |
| Payment mode | **10,000,000 units prepaid** at the beginning of a **six-month** window | Charged for each attempt |
| Upfront cash commitment | **10,000,000 monetary units** | None |
| Unused allowance | Expires without refund or rollover | Not applicable |
| Failed transaction | Consumes one prepaid unit | Still costs 2.0 |
| Marginal cash cost within A allowance | **0** after prepayment | **2.0** per submitted attempt |

The brief does not describe A's terms **beyond** the prepaid allowance. For prototype feasibility, assume no additional A transactions can be submitted after the prepaid balance reaches zero, unless new contract terms are supplied.

## 3. Realized revenue and full-window margin

Let `a` be a **unique submitted installment** with amount `m_a`, lender `c(a)`, provider `g(a) ∈ {A, B}`, attempt-date DPD `d_a`, and outcome `y_a ∈ {0,1}` (1 = success). Let `r(d)` be the commission rate table above.

The data dictionary defines `amount` as collected on `success` and attempted on `failed`. Under this supplied binary-payment convention:

$$
R_a = y_a\,m_a\,r(d_a).
$$

These formulas use unrounded commission arithmetic. Implementation must disclose whether commission is rounded per attempt or after aggregation and apply the same rule to legacy and candidate calculations. The package documents two-decimal amounts but does not specify commission rounding.

For a completed six-month provider A contract window `W`, define `N_B(W)` as the number of **unique B attempts actually submitted**, including failures. The realized full-window margin is:

$$
M_W = \sum_{a\in W} R_a - 10{,}000{,}000 - 2\,N_B(W).
$$

Assign attempts to `W` by their submission date, even if the outcome is learned after the last day of the window. Finalize realized margin only once those outcomes are reconciled; pending outcomes are not failures. The upfront payment is subtracted **once per applicable prepaid contract window**. A attempts are not billed a second time within the prepaid allocation. All attempt counts should be deduplicated using stable transaction identities rather than callback counts. A genuinely new provider transaction consumes another unit or fee even if caused by an unintended retry.

> **Window-matching rule:** do not subtract the entire 10-million commitment from a one-day or incomplete-window sample and call the result the observed *full-window* margin. If the supplied historical data do not cover the entire contract window, report the missing coverage and clearly label any prorating, forecast, or hypothetical allocation.

### Observed extract, usage-priced diagnostic, and contract projection

Let `S` denote the sampled loans and `O` the observed January-April submission dates. Compute the following separately:

$$
R_{S,O}=\sum_{a\in(S,O)}R_a,\qquad
U_{S,O}=R_{S,O}-\sum_{a\in(S,O)}\mathrm{fee}_a.
$$

`U` is a **historical usage-priced margin diagnostic**, using recorded per-attempt fees. It is not the full-window prepaid-contract margin: assigning A's nominal 1.0 fee to each used unit omits the cost of unused prepaid capacity. Verify the recorded fee mapping before reconciling it. At full-book, full-window scope, if recorded fees match A=1 and B=2:

$$
M_W=U_W-\bigl(10{,}000{,}000-N_A(W)\bigr).
$$

This is a reconciliation between two views, **not** an instruction to subtract both the A upfront payment and all A usage fees from the same revenue total.

Under the documented inclusion probability `1/15`, `15 R_{S,O}`, `15 N_{A,S}(O)`, and `15 N_{B,S}(O)` are sampling-weighted estimates of additive full-book totals **for the observed period**. Apply the weight to loan trajectories; do not multiply individual payment amounts, success probabilities or commission rates, and do not treat repeated snapshots as independent samples. Sampling and calendar uncertainty must be reported. Raw nonlinear policy optimization or its apparent ceiling does not become an unbiased full-book estimate merely by multiplying by 15.

For capacity planning, explicitly choose either full-book weighted demand against the actual 10,000,000-unit allowance, or a labeled sample-scale scenario with allowance `10,000,000 / 15` and matching fixed cost. The latter is an approximation, not a contractual allocation to the sampled loans; installment counts remain integers. Neither approach reveals actual full-book consumption or removes sampling uncertainty.

A January-June projection must add an explicit forecast/scenario for May-June and subtract the full upfront payment once at the corresponding scale. Report the observed-period results separately. Calendar-based cost accrual or other prorating is an optional reporting convention, not evidence of the missing collections or an observed completed contract. Use the **same horizon, scale and accounting convention** for legacy, candidate and ceiling comparisons.

### Lender-level cost allocation

The problem requires lender-level profitability, but the prepaid A payment is **shared** across lenders. Choose and disclose an allocation rule `w_{c,W}`, where each weight is nonnegative and `Σ_c w_{c,W}=1` across lenders included in the contract accounting scope. Then:

$$
M_{c,W} = \sum_{a\in W:\,c(a)=c} R_a
          - 2\,N_{B,c}(W)
          - 10{,}000{,}000\,w_{c,W}.
$$

This ensures `Σ_c M_{c,W}=M_W`, provided **all** relevant revenues and B attempts are attributed to exactly one lender. A possible descriptive allocation is the fraction of total A attempts attributable to each lender, with an explicit fallback when no A attempts exist. This is a **suggested accounting policy**, not a contractual fact, and an allocation driven by each evaluated policy's own usage can change apparent lender profitability. For the primary policy comparison and prospective feasibility constraint, use a disclosed rule fixed from decision-time information and held constant across policies; show alternative allocations as sensitivity analyses. Define the lender accounting scope in advance, including any lender with allocated costs but no selected attempts.

The stated requirement is `M_{c,W} > 0` for every lender. An ex-ante optimizer cannot guarantee that **realized** condition in stochastic payments: it can enforce a risk-aware **expected** counterpart and later flag realized violations. If strict profitability is mathematically infeasible, report infeasibility rather than misrepresenting it as satisfied.

The brief does not specify the lender-profitability reporting horizon. Using the A contract window is an explicit modeling choice. A no-attempt plan avoids new transaction costs but does not erase allocated fixed costs, recover past losses, or make a lender profitable by definition.

## 4. Expected economics of a candidate collection plan

At decision date `t`, a plan `p` for loan `l` consists of `k` installments `(m_j, g_j)` (or the **no-attempt** plan). For each installment, estimate:

$$
p_{l,t,p,j}=P(\text{successful installment }j\mid
\text{loan history available at }t,\,p).
$$

The expected commission of the **full plan** is:

$$
\widehat R(l,t,p) = r(d_{l,t})\sum_{j=1}^{k} m_j\,p_{l,t,p,j}.
$$

**Linearity of expectation means that summing these terms does not assume independent installment outcomes.** The estimated probabilities must nevertheless account for the full plan (for example, multiple debits on the same day may compete for the same debtor funds). The no-attempt plan has zero immediate revenue and zero submitted attempts.

The CSV schema does not identify debtors across loans. Treating loan-level predictions as sufficient for joint portfolio selection is a modeling approximation; account-level interactions across loans cannot be established from `debtor_bank`, which only identifies a bank category.

Let `n_B(p)` and `n_A(p)` denote the number of installments assigned to B and A. A conceptual **incremental decision score** is:

$$
\widehat V(l,t,p) = \widehat R(l,t,p)
- 2\,n_B(p)
- \widehat{OC}_{A,t}(p),
$$

where `\widehat{OC}_{A,t}(p)` estimates the future value of the A capacity consumed. Within the prepaid balance, A's **additional cash payment** is zero. This score is for comparing current actions, **not** the full-window realized margin. It is a daily approximation: it omits other continuation effects such as a lower future loan balance, changing DPD commission bands, and future disappearance/reappearance. It must not be described as the exact dynamic optimum.

### Avoid double-counting scarce capacity

Two valid conceptual strategies are:

1. **Explicit multi-period optimization:** represent future demand/decisions and the prepaid capacity constraint directly; the optimizer internalizes scarcity.
2. **Rolling daily optimization:** use a calibrated capacity opportunity-cost estimate (e.g., a marginal value of retaining one A unit) alongside the actual hard limit on available units.

Do not apply a second scarcity penalty if that same marginal cost is already embedded in the plan valuation. The demand forecast and shadow-price method, if used, must be described as **model estimates**, not observed facts.

## 5. Economic constraints and interpretation

- **Amount feasibility:** every installment `m_j` must be positive and at most the lender's cap; the sum of all chosen amounts cannot exceed that day's outstanding balance.
- **Prepaid capacity:** full-window A usage must be at most 10,000,000. New submissions must fit the remaining allowance after prior consumption and outstanding reservations; do not subtract prior consumption twice. After expiry, unused units are unavailable and no renewal is assumed.
- **Daily submission:** all installments chosen for a loan-date are submitted on that date.
- **Per-lender profitability:** forecast the expected **full-window**, allocated margin for each lender rather than treating each individual transaction as necessarily profitable.
- **Time consistency:** decisions may use only information available as of the decision cutoff. Outcomes are expected on the next day.

## 6. How to evaluate the economics offline

1. **Reconstruct the legacy baseline** from observed payment attempts, DPD on their attempt dates, recovered amounts, and recorded provider usage. Publish the observed extract's revenue, recorded fees and usage-priced diagnostic. Separately show any weighted full-book estimates and full-window projections, with **commission revenue, B usage fees, A upfront payment, and projected net margin separately**.
2. **Evaluate the candidate policy** on time-based holdout data. Estimate counterfactual success for proposed actions using supported historical action regions; do not label unobserved outcomes as known.
3. **Quantify model and selection uncertainty.** Legacy actions were generated by rules. Differences between A/B outcomes may reflect selection, amounts, DPD, loan composition, or timing; naive provider averages are not causal estimates.
   - A sequence of untouched legacy snapshots is not a valid new-policy simulation: alternative collections change future balances and may change later eligibility/history. Use an explicit state-transition model for multi-day scenarios or label the evaluation as a restricted one-step comparison on legacy states. Missing pre-January history and right-edge outcome availability must also be respected.
4. **Report lender-level results** with the prepaid-cost allocation policy, coverage of the contract window, and a reconciliation to the total margin.
5. **Estimate an achievable ceiling** using feasible decisions and calibrated outcome estimates, ideally under optimistic/base/conservative assumptions. Report candidate-set and solver limitations. A feasible candidate policy is not an upper bound on all possible policies, and a maximum under an estimated model is not a proven bound on real-world earnings. A perfect-information relaxation can serve as an optimistic bound only if its horizon, balance evolution and constraints are defined consistently; do not count the same debt as fully recovered on every historical snapshot.
6. **Stress-test assumptions:** provider success-rate changes, expiry proximity, unmet or excess A demand, missing loans, delayed results, and high-variance lender portfolios.

### Suggested results table (fill only after computing actual data)

| Metric (monetary units unless stated) | Legacy observed | Candidate estimated | Uncertainty / notes |
|---|---:|---:|---|
| Commission revenue | TBD | TBD | Outcomes vs predictions |
| Provider A units used | TBD | TBD | Window coverage |
| Provider B attempts | TBD | TBD | Including failed attempts |
| Provider A prepaid charge | TBD | TBD | Once per full window |
| Provider B fees | TBD | TBD | 2.0 per submitted attempt |
| Total net margin | TBD | TBD | Same cost boundary required |
| Number of non-positive-margin lenders | TBD | TBD | Apply the same allocation policy |
| Attainable-margin estimate | — | TBD | Scenario/model uncertainty |

Produce separate table panels for **observed sample January-April**, **sampling-weighted full-book January-April**, and **projected full-book January-June** when used. Mark unavailable realized full-window values as **not observed**, rather than filling them with sample-period results or forecasts. The counterfactual candidate remains estimated in every panel.

## 7. Open economic questions

- The supplied dictionary supports binary full-payment accounting; would a production extension need partial-settlement events?
- The January-June contract dates are supplied. Where would exact full-book consumed/reserved capacity be obtained? It cannot be read directly from this loan sample.
- How should unobserved May-June demand and collections be forecast, and how sensitive are profitability and expiry utilization to that forecast?
- What cost-allocation rule does the business accept for cross-lender profitability?
- Does a provider have an operational limit or an extra-fee option outside A's allowance?
- Is lender profitability assessed per six-month contract window, a reporting period, or the lifetime of the client relationship? **Six months is a modeling assumption**, aligned with A's commitment, until confirmed.

**Related documents:** [Business process](01_business_process.md) · [Domain model](02_domain_model.md) · [Problem framing](04_problem_framing.md).
