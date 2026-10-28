# Data package

This folder holds the data for the challenge described in `CHALLENGE.md`.

| File | What it is |
|---|---|
| `CHALLENGE.md` | The challenge description. |
| `clients.csv` | One row per lender: 12 lenders. |
| `loan_snapshots.csv` | One row per loan per day it appeared in a portfolio: 561,659 rows, 10,714 loans. |
| `payment_attempts.csv` | One row per transaction attempt: 370,101 rows. |
| `data_dictionary.md` | Every column in the three files. |

## Things to know

- **Period.** The files cover 2026-01-01 to 2026-04-30.
- **Sample.** This extract is a uniform random sample of **1 in 15 loans** of the full book. Volumes in
  the challenge description, such as the Provider A allocation of 10,000,000 transactions, refer to the full book.
- **Provider A window.** The 6-month Provider A window runs from 2026-01-01 to 2026-06-30.
- **Units.** All amounts are in abstract currency units, with two decimals.
- **History.** The first day of the data is not the first day of every loan's history. Loans that were already
  open on 2026-01-01 may have been attempted before it.
