# Technical Challenge: Smart Collections Engine

## Overview

You are joining a team that runs a debt-collections platform. Customers (lenders) send us their loan portfolios every day, and we try to collect the money through direct debits on their behalf.

Your task is to **design and prototype the decision engine** that decides, every day, how each loan gets collected. We care about how you frame the problem, the architecture you choose, and how you convince us it works. We care less about polish.

**Suggested time budget:** 6-8 hours. Please don't go beyond that. A clear design with a small, working prototype beats a half-finished big one.

**AI tools:** You can use them, as you would on the job. Be ready to explain every decision in your submission.

## The business problem

### What the platform does

Each day, a lender sends us their full list of open loans. For every loan we decide:

1. **Whether to attempt collection** today
2. **How many installments** to split the attempt into (for example, collect the balance in 1, 2 or 3 separate debits)
3. **The amount of each installment**
4. **Which provider** processes each installment

All installments chosen for a loan are submitted **on the same day**. We see their outcomes (success or failure) the **next day**.

### Money in and money out

- **Revenue:** we keep a share of every amount we successfully collect. The share depends on how overdue the loan is (its **days past due**, DPD, on the day of the attempt). The older the debt, the harder it is to collect, and the more we keep:

| Days past due | Share we keep |
| --- | --- |
| 0-5 | 15% |
| 6-15 | 20% |
| 16-30 | 25% |
| 31-60 | 30% |
| 61-90 | 40% |
| 91+ | 50% |

- **Cost:** we pay a fee **per transaction attempt, whether it succeeds or fails**. Failures happen, mostly because the debtor's account lacks funds.
- **Client cap:** each lender sets a **maximum amount we may debit in a single installment** for their loans. We can never exceed it.

### Objective

**Our objective is to maximize Belvo's total net margin**: the share we keep on collected amounts, minus the transaction fees we pay. We measure it as an **absolute amount in currency units, not as a percentage**. The question we care about is how much money we can really make.

Two things follow from this:

- **Every client must be profitable.** For each client, the margin earned on its loans (what we keep, minus the fees we pay to collect them) has to be positive. Making money overall by losing money on some clients does not count.
- **We want to know the ceiling.** Beyond beating our current approach, we want your best estimate of the most we could realistically earn on the data you are given, and how far today's behavior is from it.

### The two providers

All amounts are in abstract currency units. Treat the numbers as the real ones.

| | Provider A | Provider B |
| --- | --- | --- |
| Fee per transaction attempt | **1.0** | **2.0** |
| Commitment | **Prepaid: 10,000,000 transactions to be used within a 6-month window** | None, pay as you go |

Important details about Provider A:

- The 10,000,000 transactions are **paid for upfront** at the start of the 6-month window.
- Any part of the allocation **unused at the end of the window is lost**. There is no refund and no rollover.
- Assume the whole allocation is reserved for this product.
- Our current volume is in the same ballpark as the allocation, so whether we use all of it is genuinely uncertain.

### The portfolio is alive

The list of loans is **not static**:

- A loan can **disappear** from one day's portfolio to the next (for example, the debtor paid the lender through another channel).
- A loan can later **reappear**, sometimes with a different outstanding balance.
- Loans we have already tried to collect will carry a payment history that changes what we know about them.

So this is a **repeated daily decision**, not a one-time assignment.

## What we give you

Mocked datasets (CSV), generated to look like our real data. Row counts are in the hundreds of thousands, so everything runs on a laptop.

**`clients.csv`**

| column | description |
| --- | --- |
| client_id | Lender identifier |
| max_installment_amount | Cap per single installment for this lender |

**`loan_snapshots.csv`** (one row per loan per day it appeared in a portfolio)

| column | description |
| --- | --- |
| snapshot_date | Day of the portfolio |
| loan_id | Loan identifier |
| client_id | Lender identifier |
| outstanding_balance | Amount still owed that day |
| days_past_due | Days since the loan became delinquent |
| *additional loan attributes* | Mocked features, documented in the data dictionary |

**`payment_attempts.csv`** (one row per transaction attempt)

| column | description |
| --- | --- |
| attempt_id | Unique id |
| loan_id | Loan identifier |
| attempt_date | Day the attempt was submitted |
| installment_index / installment_count | Position within that day's split, and total installments that day |
| amount | Amount debited |
| provider | `A` or `B` |
| status | `success` or `failed` |
| fee | Fee paid for this attempt |

Please note:

- The historical attempts were produced by our **legacy rule-based system**, not by an ideal policy.
- The data is mocked. Patterns in it are plausible but not real, so don't over-index on exact numbers.
- A data dictionary and a small README come with the files.

## What we ask you to do

### 1. Design document (required)

A short document (2-4 pages) that covers:

- How you **frame the problem**. What is being decided, and with what information? (The objective is given above.)
- Your proposed **architecture**: components, data flow, and where each piece would run in production.
- How you handle the **constraints** (client caps, the prepaid Provider A allocation and its deadline).
- How you would **decide whether it works** before it touches real customers, and how you would roll it out safely.
- **Risks, limits and assumptions**. What could go wrong, and what would you check first?

### 2. Working prototype (required)

Implement a meaningful slice of your design using the mocked data, in the language of your choice. At minimum:

- A pipeline that takes a day's portfolio and produces a decision for each loan (attempt or not, installments, amounts, provider).
- Some form of **offline evaluation** that lets you compare your approach against the legacy behavior in the data. Report **total net margin in currency units** and the **margin per client**, so we can see whether every client is profitable.
- Clear instructions to run everything (`README`).

You don't need a production service, a UI, or infrastructure code.

### 3. Short write-up of results (required)

What did you build, what did you find, and how much do you trust it? Include the total net margin you estimate for your approach versus the legacy behavior, in currency units, and your estimate of the achievable ceiling. Plots and tables are welcome. A negative or uncertain result, honestly explained, is a perfectly good outcome.

## Things we deliberately leave open

- Which modeling approach and tooling you use
- How you represent the problem
- How you trade off simplicity against sophistication
- What you choose to build versus describe

If something is ambiguous, state your assumption and move on. You can also email us questions, and we'll answer within one business day.

## How we will review

We will look at:

- **Problem framing:** do you understand what is actually being decided, and what the data can and cannot tell you?
- **Architecture quality:** is the design sensible, scalable and realistic to operate?
- **Constraint handling:** are the client caps, the prepaid allocation and the per-client profitability requirement treated correctly?
- **Evaluation rigor:** how convincingly do you show it would beat the status quo in absolute margin, and how honest are you about uncertainty and about the ceiling you claim?
- **Engineering quality:** readable, tested where it matters, reproducible.
- **Communication:** a reader who wasn't in the room should follow your reasoning.

## Submission

Send us a repository link or a zip containing the design document, the prototype code with its README, and the results write-up. We'll schedule a 60-minute follow-up where you walk us through your decisions and we discuss extensions.

Good luck, and have fun with it.
