import dataclasses
import datetime as dt
from decimal import Decimal

from budget.budget_calc import compute, subtract_months, window_for
from budget.db import StoredTransaction

_ids = iter(range(1, 10_000))


def st(date, amount, category, source="claude", confidence=0.9, account="111111"):
    i = next(_ids)
    return StoredTransaction(i, f"{i:064x}", account, dt.date.fromisoformat(date), f"tx {i}",
                             Decimal(amount), None, "a.pdf", category,
                             source if category else None, confidence if category else None)


def at(config, reference_date):
    return dataclasses.replace(config, reference_date=dt.date.fromisoformat(reference_date))


def test_subtract_months_clamps_to_month_end():
    assert subtract_months(dt.date(2026, 3, 31), 1) == dt.date(2026, 2, 28)
    assert subtract_months(dt.date(2026, 9, 30), 12) == dt.date(2025, 9, 30)
    assert subtract_months(dt.date(2026, 1, 15), 13) == dt.date(2024, 12, 15)


def test_window_excludes_start_and_includes_reference_date(config):
    config = at(config, "2026-09-30")
    txs = [st("2025-09-30", "-100", "Groceries"),   # window start: excluded
           st("2025-10-01", "-10", "Groceries"),    # first day
           st("2026-09-30", "-1", "Groceries"),     # reference date: included
           st("2026-10-01", "-1000", "Groceries")]  # future: excluded
    b = compute(txs, config)
    assert b.lines[0].spent == Decimal("11")
    assert window_for(config.reference_date, 12).first_day == dt.date(2025, 10, 1)


def test_spent_remaining_and_used_pct_with_refunds_netting(config):
    config = at(config, "2026-01-31")
    txs = [st("2026-01-05", "-800.00", "Groceries"),
           st("2026-01-06", "-450.50", "Groceries"),
           st("2026-01-07", "50.50", "Groceries"),  # refund reduces spending
           st("2026-01-07", "-100", "Transport")]
    b = compute(txs, config)
    groceries = next(ln for ln in b.lines if ln.name == "Groceries")
    assert groceries.spent == Decimal("1200.00")
    assert groceries.remaining == Decimal("-200.00")
    assert groceries.used_pct == 120.0
    assert len(groceries.transactions) == 3


def test_totals_match_manual_sum_and_exclude_non_budgeted(config):
    config = at(config, "2026-01-31")
    txs = [st("2026-01-05", "-800", "Groceries"), st("2026-01-06", "-1500", "Housing"),
           st("2026-01-07", "-12.34", "Miscellaneous"),
           st("2026-01-02", "25000", "Income"), st("2026-01-03", "-5000", "Transfers"),
           st("2026-01-04", "-77", None)]
    b = compute(txs, config)

    manual = {}
    for t in txs:
        if t.category:
            manual[t.category] = manual.get(t.category, 0) - t.amount
    for ln in b.lines + b.non_budgeted:
        assert ln.spent == manual.get(ln.name, 0)
    assert b.total_spent == Decimal("2312.34")
    assert b.total_limit == sum(c.yearly_limit for c in config.budgeted)
    assert b.uncategorized_spent == Decimal("77")
    income = next(ln for ln in b.non_budgeted if ln.name == "Income")
    assert income.spent == Decimal("-25000")


def test_needs_review_holds_uncategorized_and_low_confidence_claude_results(config):
    config = at(config, "2026-01-31")
    uncategorized = st("2026-01-05", "-1", None)
    unsure = st("2026-01-05", "-1", "Miscellaneous", confidence=0.59)
    sure = st("2026-01-05", "-1", "Miscellaneous", confidence=0.6)
    rule = st("2026-01-05", "-1", "Miscellaneous", source="rule", confidence=None)
    b = compute([uncategorized, unsure, sure, rule], config)
    assert {t.id for t in b.needs_review} == {uncategorized.id, unsure.id}


def test_every_transaction_in_window_is_in_a_category_or_needs_review(config):
    config = at(config, "2026-01-31")
    txs = [st("2026-01-05", "-1", c) for c in config.category_names] + [st("2026-01-06", "-2", None)]
    b = compute(txs, config)
    listed = {t.id for ln in b.lines + b.non_budgeted for t in ln.transactions} | {t.id for t in b.needs_review}
    assert listed == {t.id for t in txs}


def test_monthly_spending_is_aligned_to_window_months(config):
    config = at(config, "2026-03-15")
    txs = [st("2025-03-16", "-10", "Transport"), st("2026-03-01", "-5", "Transport"),
           st("2026-03-02", "-5", "Transport")]
    b = compute(txs, config)
    assert b.months[0] == (2025, 3) and b.months[-1] == (2026, 3) and len(b.months) == 13
    assert b.monthly["Transport"][0] == Decimal("10")
    assert b.monthly["Transport"][-1] == Decimal("10")


def test_coverage_warning_when_data_starts_after_window_start(config):
    config = at(config, "2026-09-30")
    late = compute([st("2026-03-01", "-1", "Miscellaneous")], config)
    full = compute([st("2025-10-01", "-1", "Miscellaneous")], config)
    assert late.coverage_warnings and "understated" in late.coverage_warnings[0]
    assert full.coverage_warnings == []


def test_coverage_is_checked_per_account(config):
    config = at(config, "2026-09-30")
    b = compute([st("2025-10-01", "-1", "Miscellaneous", account="111111"),
                 st("2026-06-01", "-1", "Miscellaneous", account="222222")], config)
    assert len(b.coverage_warnings) == 1 and "222222" in b.coverage_warnings[0]
