# 01 — Business Process and Operational Context

**Project:** Belvo — Intelligent Collections Engine

**Stage:** Domain discovery / proposed process (not a verified production architecture)

Implementation update: [architecture](05_architecture.md), [ADRs](adrs/README.md),
[protocol](07_evaluation_protocol.md) and [operational evidence](10_validation.md)
now instantiate a local prototype; this working business specification remains broader.

**Primary diagram:** [`diagrams/business_flow.mmd`](../diagrams/business_flow.mmd)

## 1. Purpose and business boundary

Belvo operates a debt-collection platform on behalf of **lenders**. Each lender submits its current portfolio of outstanding loans daily. For each loan appearing in that day's portfolio, the platform chooses whether to submit collection attempts; if it does, it chooses the number of installments, their amounts, and the payment provider for each installment.

All installments selected for the same loan are **submitted on the decision date**. Payment outcomes (success or failure) are reported **the following day**. The process repeats as portfolios and historical information change. The business objective is to maximize Belvo's **absolute net margin**, subject to loan-level, lender-level, and provider-level constraints.

**Scope:** the decision process, submission, feedback, financial accounting, and the data needed to explain these steps. This document describes an intended logical workflow, not a claim about Belvo's current implementation.

### Evidence boundary before EDA

This specification was checked against the PDF and the [challenge](provided/CHALLENGE.md), [package README](provided/README.md), and [data dictionary](provided/data_dictionary.md). These local reference copies match the corresponding text in `belvo-collections-engine-takehome-2026-10-07.zip`. The CSV headers were also inspected. Distributional properties, key uniqueness, historical constraint compliance, and model performance have **not** been established by this review; the data archive need not be committed to the repository.

The package README specifies an observation period of **2026-01-01 through 2026-04-30**, a uniform **1-in-15 sample of loans**, and an A contract window of **2026-01-01 through 2026-06-30**. The 10,000,000-unit allowance applies to the **full book**, not the extract. The observed four-month sample is neither the whole portfolio nor a completed contract window. These boundaries must remain explicit in all later capacity and profitability calculations.

## 2. Actors and responsibilities

| Actor / component | Responsibility | Boundary / information exchanged |
|---|---|---|
| Lender | Supplies the daily portfolio and a per-installment collection cap | Loan identifiers, balances, days past due (DPD), client identifier |
| Portfolio ingestion | Validates and versions the submitted daily state | One snapshot per observable loan-date, subject to data validation |
| Historical data layer | Provides prior attempts and outcomes known by decision time | Prevents using future payment results or later snapshots |
| Decision engine | Proposes and selects a feasible collection plan per loan | Attempt/no-attempt; installment amount(s) and assigned provider(s) |
| Payment providers A/B | Receive submitted debit attempts and return results | A uses prepaid capacity; B charges per attempt |
| Capacity ledger | Tracks allocation and consumption of provider A transactions | One unit per legitimately submitted A transaction; no double-counting |
| Financial evaluation | Computes realized commission, provider charges, and net margin | Window-level and lender-level reports |

## 3. Daily business flow

The canonical process is represented in the [business-flow Mermaid diagram](../diagrams/business_flow.mmd). It follows these steps:

1. **Receive the portfolio (day `t`).** Ingest each lender's list of loans currently in scope, including observed balance and DPD. The dictionary defines the balance as net of collections through the previous day; do not deduct those historical payments a second time.
2. **Validate and enrich.** Check identifiers, amounts, timestamps, lender caps and historical payment outcomes that were already available **before the decision cutoff**.
3. **Construct decisions.** Build feasible options for each loan, including **no attempt**, and account for provider choice, available prepaid capacity, and expected lender profitability.
4. **Select and persist a plan.** Record the decision even when no collection is attempted; record chosen installments and stable transaction identities when applicable.
5. **Submit attempts (day `t`).** Submit every selected installment for a loan that day to its assigned provider. Count prepaid A capacity on a unique submitted transaction, regardless of subsequent success or failure. Reserve capacity before concurrent submissions and reconcile provider acceptance; a timeout must not silently release uncertain consumption or trigger a fresh payment identity.
6. **Collect outcomes (day `t+1`).** Reconcile each provider response against its submitted transaction, deduplicate repeated delivery, and distinguish unsuccessful payments from missing or delayed outcomes.
7. **Evaluate realized economics.** Compute commissions using the **DPD on the attempt date** and actual outcomes; aggregate provider usage and lender-level results.
8. **Feed the next cycle.** Update available history and capacity; process the next daily portfolio rather than assuming the loan set remains static.

### Decision branch

- **Attempt:** generate one or more installments, constrained by the outstanding balance and lender cap; submit them on the same day.
- **No attempt:** preserve a decision record; no new transaction charge or A unit consumption is incurred. The allocated A upfront cost remains applicable to lender profitability. The loan can be reconsidered on a later day **if it is present in the portfolio**, whether continuously or after an absence.

## 4. Business invariants and time semantics

| Invariant | Interpretation |
|---|---|
| Decision key | `(loan_id, decision_date)` is the intended logical grain; verify global `loan_id` uniqueness and add `client_id` if necessary |
| Installment limit | Each submitted amount must be no greater than the lender's `max_installment_amount` |
| Balance limit | The sum of installments submitted for a loan-date must not exceed its observed outstanding balance |
| Same-day execution | All selected installments for one loan are submitted on the same day |
| Outcome availability | Outcomes from attempts at `t` are not used for the decision at `t`; they are expected at `t+1` |
| Provider A | Prepaid units are finite and expire at the end of the six-month contract window |
| Lender profitability | Evaluate expected full-window profitability before selection and monitor **realized** profitability afterward; an expected-positive policy cannot guarantee every realized outcome |

The exact within-day arrival/cutoff ordering is not supplied. Treat an attempt on `t-1` as having an available outcome at the decision on `t` only under an explicit before-cutoff arrival assumption; otherwise lag it further. An outcome present in an offline CSV is not automatically available to the historical decision.

## 5. Data and event contracts (proposed)

| Logical artifact | Minimum attributes | Purpose |
|---|---|---|
| Daily snapshot | `client_id`, `loan_id`, `snapshot_date`, `outstanding_balance`, `days_past_due` | Decision-time loan state |
| Decision record | `decision_date`, `loan_id`, `client_id`, plan version, action, reason, model/config version | Audit trail and no-attempt visibility; **not supplied as a historical CSV** |
| Submission record | Stable attempt identifier, installment index/count, amount, provider, submission state | Reconciliation and idempotency |
| Outcome record | Attempt identifier, result, outcome availability timestamp | Realized revenue and historical features |
| A capacity record | Contract-window ID, reserved units, consumed units, remaining units, expiry | Prevent overspending prepaid capacity |

These are **logical contracts for the proposed solution**, not additional files claimed to be present in the dataset.

## 6. Operational exceptions and recovery

- **Missing or invalid portfolio:** quarantine affected records, log the issue, and do not silently infer a payable balance.
- **Loan disappears and reappears:** retain its attempt history; only create a new decision when it is present in a later snapshot.
- **Duplicate submission or callback:** match by stable payment identity and make ledger updates idempotent; provider-side idempotency support must be checked. A genuinely new provider transaction consumes another unit or fee even if a retry caused it accidentally.
- **Delayed or absent outcomes:** maintain a pending state instead of treating silence as payment failure.
- **Insufficient A capacity:** exclude infeasible A assignments; consider provider B only if its expected economics are acceptable.
- **Unprofitable or infeasible lender:** report the infeasibility explicitly. A no-attempt decision can prevent further costs but does not satisfy positive lender profitability by itself or remove allocated prepaid costs.

## 7. Questions to verify before implementation

1. What is the daily decision/submission cutoff, and when are provider outcomes actually available?
2. Is `loan_id` globally unique or only unique within a lender?
3. The dictionary maps `amount` to the collected amount on success and the attempted amount on failure. Are partial settlements possible outside this supplied binary-outcome convention?
4. Is there an upper limit on installment count beyond the examples of 1–3?
5. Are there additional submission limits, provider rate limits, or lender-specific collection policies?
6. The package supplies the January-June contract boundaries. How would the full-book consumed/reserved A balance be obtained in production? The loan sample cannot establish that exact balance.

## 8. Refinement after EDA

Validate the supplied coverage, identifiers, daily portfolio churn, attempt grouping and documented amount/fee semantics. Preserve complete loan histories when applying the 15x sampling weight; do not treat loan-day rows as independent draws. Establish sample-vs-full-book and observed-period-vs-full-window reporting before evaluating a policy. Later snapshots reflect legacy collections and cannot be reused unchanged as a validated trajectory under a different policy.

These files are working specifications. The challenge still asks for a concise **2-4 page final design document**, a functioning prototype, and a results report; these discovery notes should inform that deliverable rather than replace its length limit.

**Related documents:** [Domain model](02_domain_model.md) · [Economic model](03_economic_model.md) · [Problem framing](04_problem_framing.md).
