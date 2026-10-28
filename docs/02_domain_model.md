# 02 — Domain Model and Data Relationships

**Project:** Belvo — Intelligent Collections Engine

**Stage:** Logical data model; schema assertions require CSV verification

**Diagram:** [`diagrams/entity_relationship.mmd`](../diagrams/entity_relationship.mmd)

## 1. Purpose and modeling scope

The challenge describes three supplied CSV datasets: `clients.csv`, `loan_snapshots.csv`, and `payment_attempts.csv`. Their purpose is to reconstruct lender policies, daily loan states, historical collection actions, and observed payment outcomes.

The [entity-relationship diagram](../diagrams/entity_relationship.mmd) also contains **`LOANS` as a conceptual entity**. It is a useful bridge between repeated snapshots and payment attempts, **not a fourth CSV** and not evidence that a physical loans table exists.

**Source status:** the [package README](provided/README.md), [data dictionary](provided/data_dictionary.md), and actual CSV headers were inspected in the provided archive (identified in [01](01_business_process.md)). The README reports 12 lenders, 561,659 snapshots, 10,714 loans, and 370,101 attempts; these are **publisher-reported counts**, not results independently recomputed here. EDA must verify keys, cardinalities, coverage, and values.

## 2. Entities and grain

| Entity | Source | Logical grain | Key / relationship |
|---|---|---|---|
| `CLIENTS` | `clients.csv` | One lender | `client_id` — expected primary key |
| `LOANS` | Derived logical entity | One distinct loan | `loan_id` — **provisional** identifier; references lender |
| `LOAN_SNAPSHOTS` | `loan_snapshots.csv` | One loan observed on one portfolio date | Candidate composite key `(loan_id, snapshot_date)` |
| `PAYMENT_ATTEMPTS` | `payment_attempts.csv` | One submitted installment transaction | `attempt_id` — expected primary key |

### Core attributes

**`CLIENTS`**
- `client_id`: lender identifier.
- `max_installment_amount`: maximum permitted amount of a single installment for that lender.

**`LOAN_SNAPSHOTS`**
- `snapshot_date`, `loan_id`, `client_id`.
- `outstanding_balance`: amount currently owed on that date, **after collections through the previous day**, according to the dictionary.
- `days_past_due`: DPD as observed in that snapshot.
- `original_amount`: amount originally lent.
- `payroll_cycle`: `weekly`, `biweekly`, or `monthly`.
- `debtor_bank`: anonymized bank category, `bank_1` through `bank_4`; this is **not a debtor or account identifier**.
- `customer_tenure_months`: months the debtor has been a lender customer.

These four additional attributes are documented in the supplied dictionary and present in the CSV header. Their distributions, stability over time, and predictive usefulness remain EDA questions.

**`PAYMENT_ATTEMPTS`**
- `attempt_id`, `loan_id`, `attempt_date`.
- `installment_index`, `installment_count`, `amount`.
- `provider` (`A`/`B`), `status` (`success`/`failed`), `fee`.
- The dictionary defines `amount` as collected on success and attempted on failure; therefore recovered amount is `amount` for `success` and zero for `failed` under the supplied convention. `status` becomes known the day after `attempt_date`.

Amounts are documented with two decimal places, although the dictionary calls their storage type `float`. Use decimal or integer minor-unit arithmetic for feasibility checks and monetary aggregation, with an explicit commission-rounding rule; do not silently round an over-cap plan into feasibility.

**`LOANS` (derived)**
- Conceptual `loan_id` and lender assignment from observed snapshots.
- Its primary key and ownership assumptions remain provisional until actual cardinalities are checked.

## 3. Relationships and cardinality

- One **client** can own many **loans**: `CLIENTS (1) → LOANS (0..N)`.
- One **loan** can appear in many **daily snapshots**: `LOANS (1) → LOAN_SNAPSHOTS (0..N)`.
- One **loan** can have many **payment attempts**: `LOANS (1) → PAYMENT_ATTEMPTS (0..N)`.
- The diagram also shows a direct client-to-snapshot association via `LOAN_SNAPSHOTS.client_id`. This is a recorded foreign-key relationship, whereas ownership through `LOANS` is an inferred, normalized view.

If loan ownership is stable, the snapshot's client must equal its derived loan owner. A failure of `loan_id -> client_id` could indicate ID collisions, data errors, or actual transfers; these require different resolutions. In particular, `payment_attempts.csv` has **no `client_id`**: changing a loan key to `(client_id, loan_id)` alone does not resolve ambiguous attempt ownership. Determine an unambiguous dated mapping, or quarantine and report those attempts. Genuine ownership changes require a temporal ownership model rather than assuming a permanently assigned client.

A single snapshot **must not** be treated as the parent of all loan attempts: a loan may have many attempts on different dates, and snapshots may be absent on some dates.

## 4. Temporal joins and leakage prevention

Use the **decision date** as the reference point for all features and constraints. A robust join design should distinguish:

1. **Current state:** the loan snapshot selected for decision date `t`, normally `snapshot_date = t`.
2. **Prior attempts:** submitted attempts occurring before the decision cutoff for `t`.
3. **Known outcomes:** results whose **availability time** is earlier than the decision cutoff. The PDF only specifies next-day results, not an explicit outcome-arrival timestamp; derive an admissible availability rule or request clarification.
4. **Commission DPD:** the DPD on the **attempt date**, not a later updated snapshot value.
5. **Lender attributes:** the relevant lender cap for the decision date; `clients.csv` has no historical effective-date field, so treating it as time-invariant is an assumption.

Join an attempt to **exactly one same-day snapshot** to recover DPD, dated balance and lender ownership. Assert that the join does not multiply attempt rows or drop them silently. If a same-day snapshot is missing, report it; neither a future snapshot nor unrestricted forward-filling across portfolio absence is an admissible default.

### Coverage, truncation and sample design

- The README specifies **2026-01-01 to 2026-04-30** and a uniform **1-in-15 loan sample** of the full book. Sampling is by loan, not by snapshot or attempt; retain complete trajectories when estimating totals or uncertainty.
- The observation start is **left-truncated history**. No earlier observed attempt does not mean the loan was never attempted. Mark prior-history features as observation-window summaries.
- Outcomes for attempts on **2026-04-30** are available on **2026-05-01** under the next-day convention. They may be used as subsequently observed labels if provided, but not as April 30 decision features. The package does not establish May-June portfolio states or collections.
- Current snapshots already incorporate legacy collections through the previous day. A new policy changes future balances; replaying unchanged future snapshots cannot establish a valid multi-day counterfactual.

**Historical no-attempt decisions:** `payment_attempts.csv` contains only executed attempts. A loan present in a snapshot without a same-day attempt may imply "no observed attempt," but its precise business reason is unknown. Avoid inventing a historical decision label or policy rationale.

## 5. Data validation plan

| Check | Expected interpretation / action |
|---|---|
| `clients.client_id` uniqueness | Fail or quarantine duplicates; document conflicts |
| `(loan_id, snapshot_date)` uniqueness | Verify; if false, establish a defensible composite key and deduplication rule |
| `attempt_id` uniqueness | Distinguish duplicate rows from genuine repeated submissions |
| `loan_id → client_id` stability | Separate ownership changes, collisions and errors; establish dated attempt attribution before revising the model |
| Snapshot-to-client referential integrity | Find orphan lender IDs |
| Attempt-to-loan referential integrity | Identify attempts with no known snapshot/owner; determine if history is truncated |
| `amount > 0`, `outstanding_balance >= 0`, `max_installment_amount > 0` | Validate numeric integrity and handling of zero/negative values |
| `days_past_due` | Nonnegative integer with a defined commission band; quarantine invalid or missing values rather than assigning an arbitrary rate |
| `installment_index` / `installment_count` | Positive integers; index within count; validate count consistency, unique indices and completeness per loan/date before assuming one plan per day |
| `provider`, `status`, `fee` | Confirm supported categories and fee mapping (A=1.0, B=2.0 in the brief) |
| Date consistency | Flag future data, duplicate snapshot dates, attempts outside observable loan history |
| Attempt limits | Compare individual amount against lender cap and total attempted amount against dated balance |
| Documented extra attributes | Validate categories, nonnegative tenure, original amount, missingness and within-loan changes without assuming each attribute is static |
| Package metadata | Recompute file counts, date ranges, loan/lender counts and join coverage; reconcile discrepancies with README claims |

Data quality failures must be **reported**, not silently corrected to make the model fit the assumed schema.

## 6. Analytical tables and derived features (proposed)

For notebook/prototype work, build an analysis-ready **loan-day** table with:

- Snapshot attributes available on day `t`.
- Prior-attempt counts and time since last attempt.
- Prior successful/failed attempt summaries (strictly as-of `t`).
- Historical provider usage, attempted amounts, and installment patterns.
- Observed `no_attempt` indicator derived from snapshot/attempt coverage, marked as observational rather than a ground-truth decision label.
- Decision outcomes for supervised training **only where a historical attempt was actually observed**, with explicit treatment of selection bias.

Aggregate attempt rows into their complete observed loan-day plan before learning plan effects. Keep the label and feature timestamps separate, and split evaluation chronologically. Confidence intervals must respect repeated observations within loans; shared calendar effects may require time blocks as well. The 15x sampling weight can estimate additive full-book totals, but it does not create missing outcomes or identify the best counterfactual policy.

## 7. Future production entities (not in the supplied data)

The proposed solution will likely need a durable `DECISIONS` log, an `ATTEMPT_SUBMISSIONS` ledger, an `OUTCOME_EVENTS` table and a `PROVIDER_A_CONTRACT_WINDOWS` ledger. These are **architecture proposals**; their schema and identifiers are not demonstrated by the provided CSV description.

**Related documents:** [Business process](01_business_process.md) · [Economic model](03_economic_model.md) · [Problem framing](04_problem_framing.md).
