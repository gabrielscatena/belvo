# Horizon and recent-calendar sensitivities

Post-inspection April conditional quota/admission sensitivities; not a contract forecast. The original observed benchmark is preserved in every row.

See scenarios.csv, daily.csv and per_client.csv. Both policies receive the same cumulative release and calendar admission. Filtered legacy money is a retained-log accounting diagnostic, not measured counterfactual improvement.

- Same fixed cumulative release schedule for both policies; independent consumption ledgers and unspent carryover.
- Opening capacity and schedule fixed at test start, not dynamically renormalized from later use.
- 0.75 reserves a quarter through expiry; 1.25 releases earlier and still clips at total capacity.
- Logged plans admitted whole by hash(seed, day, loan_id), never observed outcomes or revenue.
- Retained logged observed margin is accounting for a selected subset, not its counterfactual policy value.
- Calendar sensitivity gates both policies using only pretest pure-plan exposure; causal support remains unproved.
- All variants use the original daily lender budgets from supplied legacy history, not simulated candidate feedback.
- Legacy future snapshots are held fixed; changes to future balances or portfolio exits are not simulated.
- Identical monthly prepaid allocation cancels in differences; pacing is not an extra accounting cost.
- No causal decomposition attributes the original gap to front-loading, targeting or response-model bias.
- May-June demand and outcomes are absent; no optimal pacing or six-month profit is established.
