"""Deterministic quota-constrained heuristic; failure is not proof of infeasibility."""

from collections import defaultdict

from belvo.domain import Loan, plans


def no_history_decisions(loans, quota, protocol):
    """No unsupported fallback debits when all available training data is quarantined."""
    return [
        {
            "loan_id": loan.loan_id,
            "client_id": loan.client_id,
            "day": loan.day,
            "version": loan.version,
            "plan": {"amounts": [], "providers": []},
            "status": "no_attempt",
            "reason": "no_available_training_history",
            "lender_constraint": {"status": "not_evaluated"},
        }
        for loan in loans
    ], quota


class EconomicSelector:
    version = "economic_heuristic_v2"

    def __init__(self, model, required_today=None, supported_only=True):
        self.model = model
        self.required = required_today
        self.supported_only = supported_only
        self.report = {}
        self._options = {}

    def prepare(self, loans, protocol):
        """Score before locking state; allocate against locked quota in __call__."""
        for loan in loans:
            if loan in self._options:
                continue
            candidates = []
            for plan in plans(
                loan, protocol.values["amount_fractions"], protocol.values["max_installments"]
            ):
                if plan.a_units and not protocol.a_available(loan.day):
                    continue
                value = self.model.evaluate(loan, plan)
                if self.supported_only and plan.amounts and not value["supported"]:
                    continue
                candidates.append((plan, value))
            self._options[loan] = candidates

    @staticmethod
    def _score_key(item):
        plan, value = item
        return value["score"], -plan.a_units, -len(plan.amounts)

    def _improve(self, options, selected, loan_map, totals, remaining):
        """Improve current choices without reversing a satisfied lender requirement.

        Replacements use incremental capacity, including for loans already using A.
        Under scarcity this is a local heuristic, not an optimality certificate.
        """
        changed = True
        while changed:
            changed = False
            for key in sorted(selected):
                current, current_value = selected[key]
                client = loan_map[key].client_id
                floor = (
                    min(totals[client], self.required[client])
                    if self.required is not None and client in self.required
                    else float("-inf")
                )
                feasible = [
                    item
                    for item in options[key]
                    if item[0].a_units - current.a_units <= remaining
                    and totals[client]
                    + (
                        item[1]["conservative_contribution"]
                        - current_value["conservative_contribution"]
                    )
                    >= floor
                ]
                replacement = max(feasible, key=self._score_key)
                plan, value = replacement
                # Strict score improvement or equal score with less capacity ensures termination.
                if (value["score"], -plan.a_units) <= (
                    current_value["score"], -current.a_units
                ):
                    continue
                totals[client] += (
                    value["conservative_contribution"]
                    - current_value["conservative_contribution"]
                )
                remaining -= plan.a_units - current.a_units
                selected[key] = replacement
                changed = True
        return remaining

    def __call__(self, loans: list[Loan], quota: int, protocol):
        self.prepare(loans, protocol)
        options, selected, loan_map = {}, {}, {loan.loan_id: loan for loan in loans}
        for loan in sorted(loans, key=lambda x: x.loan_id):
            candidates = self._options[loan]
            options[loan.loan_id] = candidates
            selected[loan.loan_id] = max(
                (item for item in candidates if not item[0].a_units),
                key=lambda item: (item[1]["score"], -len(item[0].amounts)),
            )
        totals = defaultdict(float)
        for key, (_, value) in selected.items():
            totals[loan_map[key].client_id] += value["conservative_contribution"]
        remaining = quota
        # Prioritize lender deficits before unconstrained total-value upgrades.
        # Positive contribution gains can satisfy a lender requirement despite an OC penalty.
        for constraint_phase in (True, False):
            upgrades = []
            for key, candidates in options.items():
                current, current_value = selected[key]
                if current.a_units:
                    continue
                for plan, value in candidates:
                    if not plan.a_units:
                        continue
                    metric = "conservative_contribution" if constraint_phase else "score"
                    gain = value[metric] - current_value[metric]
                    if gain > 0:
                        upgrades.append((gain / plan.a_units, key, plan, value))
            upgrades.sort(key=lambda x: (-x[0], x[1], x[2].amounts))
            for _, key, plan, value in upgrades:
                client = loan_map[key].client_id
                if constraint_phase and (
                    self.required is None or totals[client] >= self.required.get(client, 0)
                ):
                    continue
                if selected[key][0].a_units or plan.a_units > remaining:
                    continue
                totals[client] += (
                    value["conservative_contribution"]
                    - selected[key][1]["conservative_contribution"]
                )
                remaining -= plan.a_units
                selected[key] = plan, value
        # Independent score maxima are globally optimal when all shared constraints permit them.
        independent = {
            key: max(candidates, key=self._score_key) for key, candidates in options.items()
        }
        independent_units = sum(plan.a_units for plan, _ in independent.values())
        independent_totals = defaultdict(float)
        for key, (_, value) in independent.items():
            independent_totals[loan_map[key].client_id] += value["conservative_contribution"]
        requirements_met = self.required is None or all(
            client in self.required and total >= self.required[client]
            for client, total in independent_totals.items()
        )
        if independent_units <= quota and requirements_met:
            selected, totals, remaining = independent, independent_totals, quota - independent_units
        else:
            remaining = self._improve(options, selected, loan_map, totals, remaining)
        self.report = {
            client: {
                "conservative_today_contribution": totals[client],
                "required_today": None if self.required is None else self.required.get(client, 0),
                "status": "not_evaluated"
                if self.required is None
                else "missing_lender_budget"
                if client not in self.required
                else "satisfied_expected"
                if totals[client] >= self.required.get(client, 0)
                else "unmet_heuristic_constraint",
            }
            for client in sorted({loan.client_id for loan in loans})
        }
        decisions = []
        for key in sorted(selected):
            loan, (plan, value) = loan_map[key], selected[key]
            decisions.append(
                {
                    "loan_id": key,
                    "client_id": loan.client_id,
                    "day": loan.day,
                    "version": loan.version,
                    "plan": plan.payload(),
                    "status": "attempt" if plan.amounts else "no_attempt",
                    "reason": self.version
                    if plan.amounts
                    else "no_supported_positive_plan",
                    "economics": value,
                    "lender_constraint": self.report[loan.client_id],
                }
            )
        return decisions, remaining


def zero_future_budget(frame, day, protocol, clients=None):
    """Full-contract check under explicitly zero future contribution, not a forecast."""
    clients = sorted(frame.client_id.unique() if clients is None else clients)
    known = frame.loc[frame.attempt_date.le(protocol.known_attempt_through(day))].copy()
    known["realized_contribution"] = known.amount_cents / 100 * known.band / 100 * known.status.eq(
        "success"
    ) - known.provider.eq("B") * float(protocol.values["b_fee"])
    past = known.groupby("client_id").realized_contribution.sum().to_dict()
    pending = frame.loc[
        frame.attempt_date.lt(day) & frame.attempt_date.gt(protocol.known_attempt_through(day))
    ]
    pending_b_cost = (
        (pending.provider.eq("B").astype(int) * float(protocol.values["b_fee"]))
        .groupby(pending.client_id)
        .sum()
        .to_dict()
    )
    fixed = float(protocol.sample_upfront) / len(clients)
    # Pending and future contribution assumed zero: stringent sensitivity, not six-month prediction.
    return {
        client: fixed - past.get(client, 0) + pending_b_cost.get(client, 0) + 0.0001
        for client in clients
    }
