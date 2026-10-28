# Data dictionary

Three CSV files. Dates are `YYYY-MM-DD`. Amounts are in abstract currency units.

## `clients.csv`

| Column | Type | Description |
|---|---|---|
| `client_id` | string | Lender identifier. |
| `max_installment_amount` | float | Cap per single installment for this lender. |

## `loan_snapshots.csv`

One row per loan per day it appeared in a portfolio.

| Column | Type | Description |
|---|---|---|
| `snapshot_date` | date | Day of the portfolio. |
| `loan_id` | string | Loan identifier. |
| `client_id` | string | Lender identifier. |
| `outstanding_balance` | float | Amount still owed that day, after collections up to the previous day. |
| `days_past_due` | integer | Days since the loan became delinquent. |
| `original_amount` | float | Mocked loan attribute: the amount originally lent. |
| `payroll_cycle` | string | Mocked loan attribute: how often the debtor is paid, one of `weekly`, `biweekly`, `monthly`. |
| `debtor_bank` | string | Mocked loan attribute: the debtor's bank, anonymised as `bank_1` to `bank_4`. |
| `customer_tenure_months` | integer | Mocked loan attribute: months the debtor has been a customer of the lender. |

## `payment_attempts.csv`

One row per transaction attempt.

| Column | Type | Description |
|---|---|---|
| `attempt_id` | string | Unique id. |
| `loan_id` | string | Loan identifier. |
| `attempt_date` | date | Day the attempt was submitted. |
| `installment_index` | integer | Position within that day's split. |
| `installment_count` | integer | Total installments that day. |
| `amount` | float | Amount debited (the amount attempted, when the attempt failed). |
| `provider` | string | `A` or `B`. |
| `status` | string | `success` or `failed`, known the day after `attempt_date`. |
| `fee` | float | Fee paid for this attempt. |
