"""Recent-calendar admission sensitivity, not a response model or causal guarantee."""

from datetime import date, timedelta


def calendar_type(value):
    """Calendar proxy; these categories do not establish a borrower's actual payday."""
    day = date.fromisoformat(value)
    if day.day == 1:
        return "month_start"
    if day.day in (15, 16):
        return "midmonth"
    return "month_end" if (day + timedelta(days=1)).month != day.month else "other"


class CalendarSupport:
    """Count pure-plan exposure before a frozen cutoff, without reading outcomes.

    The last calendar month can be partial because only labels available through
    ``through`` are counted. One recent month must contain at least 100
    exposures by default, as well as 100 total exposures. This is an action
    admission sensitivity, not evidence that admitted actions are causally identified.
    """

    def __init__(self, history, through, *, months=2, minimum_attempts=100, minimum_months=1):
        if months < 1 or minimum_attempts < 1 or not 1 <= minimum_months <= months:
            raise ValueError("Invalid calendar-support thresholds")
        cutoff = date.fromisoformat(through)
        last_month = cutoff.year * 12 + cutoff.month - 1
        self.recent_months = tuple(
            f"{month // 12:04d}-{month % 12 + 1:02d}"
            for month in range(last_month - months + 1, last_month + 1)
        )
        self.through = through
        self.minimum_attempts = minimum_attempts
        self.minimum_months = minimum_months
        sample = history.loc[history.attempt_date.le(through) & history.pure].copy()
        sample["calendar"] = sample.attempt_date.map(calendar_type)
        sample["month"] = sample.attempt_date.str[:7]
        self._history_counts = sample.groupby(["provider", "calendar"]).size().to_dict()
        recent = sample.loc[sample.month.isin(self.recent_months)]
        self._recent_counts = recent.groupby(["provider", "calendar"]).size().to_dict()
        self._recent_month_counts = (
            recent.groupby(["provider", "calendar"]).month.nunique().to_dict()
        )
        monthly = recent.groupby(["provider", "calendar", "month"]).size()
        self._qualifying_month_counts = (
            monthly.ge(minimum_attempts).groupby(level=["provider", "calendar"]).sum().to_dict()
        )

    def check(self, provider, day):
        key = provider, calendar_type(day)
        count = int(self._recent_counts.get(key, 0))
        month_count = int(self._recent_month_counts.get(key, 0))
        qualifying_months = int(self._qualifying_month_counts.get(key, 0))
        admitted = count >= self.minimum_attempts and qualifying_months >= self.minimum_months
        return {
            "provider": provider,
            "calendar": key[1],
            "any_history_attempts": int(self._history_counts.get(key, 0)),
            "recent_attempts": count,
            "recent_months_observed": month_count,
            "recent_qualifying_months": qualifying_months,
            "recent_months": list(self.recent_months),
            "through": self.through,
            "minimum_attempts": self.minimum_attempts,
            "minimum_months": self.minimum_months,
            "admitted": admitted,
            "reason": "recent_calendar_support"
            if admitted
            else "insufficient_recent_calendar_support",
        }


class CalendarSupportedModel:
    """Decorate scoring with an explicit admission gate; preserve all money estimates."""

    def __init__(self, model, support):
        if model.fitted_through != support.through:
            raise ValueError("Calendar support and model must share the same label cutoff")
        self.model = model
        self.support = support

    def __getattr__(self, name):
        return getattr(self.model, name)

    def evaluate(self, loan, plan):
        if self.model.fitted_through != self.support.through:
            raise ValueError("Calendar support and model must share the same label cutoff")
        value = self.model.evaluate(loan, plan)
        support = {
            provider: self.support.check(provider, loan.day)
            for provider in sorted(set(plan.providers))
        }
        admitted = all(item["admitted"] for item in support.values())
        return value | {
            "observational_cell_supported": value["supported"],
            "calendar_supported": admitted,
            "calendar_support": support,
            "calendar_support_reason": "no_attempt"
            if not plan.amounts
            else "recent_calendar_support"
            if admitted
            else "insufficient_recent_calendar_support",
            "supported": bool(value["supported"] and admitted),
        }
