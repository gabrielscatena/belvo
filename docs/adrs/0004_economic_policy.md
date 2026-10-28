# ADR 0004: Transparent empirical plan scoring

Status: Accepted for prototype only. Date: 2026-10-28.

Context: Legacy assignments are observational and loan outcomes are rare. An unvalidated
complex model would obscure support and causal limitations. Deterministic feasibility
alone cannot compare expected commission with provider costs.

Decision: Empirical success frequencies conditioned on lender, provider, installment count,
DPD commission band and total-plan amount fraction. Smooth toward provider/count/DPD
frequency with 100 pseudo-observations; back off to global frequency when absent. Default
selector admits only pure-provider cells with at least 100 historical attempts. Mixed
plans remain explicitly unsupported. Marginal expectations add without assuming installment
independence; this does not identify interference or causal provider response.

Conservative score: mean minus one approximate standard error, clipped to zero. This is a
stress score, **not** a calibrated confidence guarantee (repeated loans/debits are dependent).
No robust minimax optimality is claimed. Full-plan fractions are coarse support checks;
amounts inside a bin can still extrapolate. Validation and loan bootstrap must expose risk.

Selection: start from best B/no-attempt plans, then allocate shared A by contribution gain
per unit, first toward lender deficits and then by economic score. Deterministic tie order
and persisted model hash permit reproduction. The heuristic is not an exact optimizer;
unmet requirements are reported without asserting infeasibility. Default opportunity cost
is zero because the sampled observed volume leaves substantial quota; sensitivity varies it.
No separate shadow-price penalty is added. Future online allocation can still be suboptimal.

Lender requirement: `past_known_contribution + today_conservative_contribution +
pending_expected + future_expected - fixed_A_share > 0`. The initial CLI check sets pending
and future contribution to zero as an explicit stringent scenario, not as a forecast.
Known fees of pending B submissions are charged even when pending recovery is assumed zero.
It reports unmet constraints rather than claiming all lenders profitable or concealing fixed
cost. A production recommendation requires a supported horizon forecast and positive lender
results under its uncertainty criteria. No-attempt cannot cure an already negative contract.

Alternatives: Rules alone cannot estimate economic outcomes; flexible supervised models
need stronger validation; exact integer optimization cannot fix causal identification.
More features, mixed-provider plans and calibrated sequential models are future work.

Evaluation update: candidate volume would exhaust A under the tested May-June continuation
scenarios. Legacy underuse does not establish ample capacity under a new policy. Zero
opportunity cost remains a disclosed prototype baseline; future pacing is not validated.
