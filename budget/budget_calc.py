"""Rolling-window budget math."""

from __future__ import annotations

import calendar
import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal

from .config import Config
from .db import StoredTransaction

REVIEW_CONFIDENCE = 0.6


def subtract_months(d: dt.date, months: int) -> dt.date:
    total = d.year * 12 + (d.month - 1) - months
    year, month = divmod(total, 12)
    month += 1
    return dt.date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


@dataclass(frozen=True)
class Window:
    start: dt.date  # exclusive
    end: dt.date    # inclusive

    def __contains__(self, d: dt.date) -> bool:
        return self.start < d <= self.end

    @property
    def first_day(self) -> dt.date:
        return self.start + dt.timedelta(days=1)

    def months(self) -> list[tuple[int, int]]:
        out, y, m = [], self.first_day.year, self.first_day.month
        while (y, m) <= (self.end.year, self.end.month):
            out.append((y, m))
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        return out


def window_for(reference_date: dt.date, months: int) -> Window:
    return Window(subtract_months(reference_date, months), reference_date)


@dataclass
class CategoryLine:
    name: str
    limit: Decimal | None
    spent: Decimal
    transactions: list[StoredTransaction] = field(default_factory=list)

    @property
    def remaining(self) -> Decimal | None:
        return None if self.limit is None else self.limit - self.spent

    @property
    def used_pct(self) -> float | None:
        if not self.limit:
            return None
        return float(self.spent / self.limit * 100)


@dataclass
class Budget:
    window: Window
    lines: list[CategoryLine]          # budgeted categories
    non_budgeted: list[CategoryLine]   # spent = net money out (negative = net money in)
    needs_review: list[StoredTransaction]
    uncategorized_spent: Decimal
    months: list[tuple[int, int]]
    monthly: dict[str, list[Decimal]]  # category -> spent per month, aligned with `months`
    coverage_warnings: list[str]

    @property
    def total_limit(self) -> Decimal:
        return sum((ln.limit for ln in self.lines), Decimal(0))

    @property
    def total_spent(self) -> Decimal:
        return sum((ln.spent for ln in self.lines), Decimal(0))

    @property
    def total_remaining(self) -> Decimal:
        return self.total_limit - self.total_spent

    @property
    def total_used_pct(self) -> float | None:
        return float(self.total_spent / self.total_limit * 100) if self.total_limit else None


def needs_review(t: StoredTransaction) -> bool:
    return t.category is None or (t.source == "claude" and (t.confidence or 0) < REVIEW_CONFIDENCE)


def compute(transactions: list[StoredTransaction], config: Config) -> Budget:
    window = window_for(config.reference_date, config.window_months)
    in_window = [t for t in transactions if t.date in window]
    months = window.months()
    month_index = {ym: i for i, ym in enumerate(months)}

    def line(cat) -> CategoryLine:
        txs = [t for t in in_window if t.category == cat.name]
        return CategoryLine(cat.name, cat.yearly_limit, -sum((t.amount for t in txs), Decimal(0)), txs)

    lines = [line(c) for c in config.budgeted]
    monthly = {}
    for ln in lines:
        per_month = [Decimal(0)] * len(months)
        for t in ln.transactions:
            per_month[month_index[(t.date.year, t.date.month)]] -= t.amount
        monthly[ln.name] = per_month

    uncategorized = [t for t in in_window if t.category is None]

    coverage = []
    earliest: dict[str, dt.date] = {}
    for t in transactions:
        if t.account_id not in earliest or t.date < earliest[t.account_id]:
            earliest[t.account_id] = t.date
    for account, first in sorted(earliest.items()):
        if first > window.first_day:
            coverage.append(f"Account {account}: data starts {first:%d.%m.%Y}, after the window start "
                            f"{window.first_day:%d.%m.%Y} - spending is understated.")
    if not transactions:
        coverage.append("No transactions imported yet.")

    return Budget(
        window=window,
        lines=lines,
        non_budgeted=[line(c) for c in config.non_budgeted],
        needs_review=[t for t in in_window if needs_review(t)],
        uncategorized_spent=-sum((t.amount for t in uncategorized), Decimal(0)),
        months=months,
        monthly=monthly,
        coverage_warnings=coverage,
    )
