import dataclasses
import datetime as dt
from decimal import Decimal

from budget.budget_calc import compute
from budget.report import axis_label, bar_class, month_grid, money, pace_chart, ranked_lines, render
from tests.test_budget_calc import st


def test_money_uses_danish_separators():
    assert money(Decimal("1234567.891"), 2) == "1.234.567,89"
    assert money(Decimal("-1234.5")) == "-1.235"
    assert money(Decimal("-0.4")) == "0"
    assert money(None) == "–"


def test_progress_bar_thresholds():
    assert bar_class(74.9) == "green"
    assert bar_class(75) == "amber"
    assert bar_class(100) == "amber"
    assert bar_class(100.1) == "red"


def test_report_is_self_contained_and_shows_budget(config):
    config = dataclasses.replace(config, reference_date=dt.date(2026, 1, 31))
    over = st("2026-01-05", "-1500", "Groceries")
    review = st("2026-01-06", "-42", None)
    html = render(compute([over, review, st("2026-01-02", "25000", "Income")], config), config, "2026-01-31T10:00:00")

    assert "<script" not in html and "http" not in html.replace("http-equiv", "")
    assert "Groceries" in html and "1.500" in html
    assert "Within budget" in html
    assert "fill bg-red" in html
    assert over.fingerprint[:12] in html
    assert review.fingerprint[:12] in html and "Needs review" in html
    assert "Income" in html and "25.000" in html
    assert "31.01.2026 10:00" in html


def test_report_embeds_its_fonts_and_uses_english_month_labels(config):
    config = dataclasses.replace(config, reference_date=dt.date(2026, 5, 31))
    html = render(compute([st("2026-05-05", "-10", "Groceries")], config), config, None)
    assert "data:font/woff2;base64," in html
    assert "May 26" in html and "maj" not in html


def at(config, reference_date):
    return dataclasses.replace(config, reference_date=dt.date.fromisoformat(reference_date))


def test_pace_chart_ends_at_total_spent_and_full_budget(config):
    config = at(config, "2026-01-31")
    b = compute([st("2025-03-01", "-400", "Groceries"), st("2025-09-01", "-600", "Housing"),
                 st("2025-09-02", "100", "Housing"),        # refund lowers the curve
                 st("2025-10-01", "-5000", "Income")], config)  # non-budgeted: not in the curve
    pace = pace_chart(b)
    assert pace.spent == Decimal("900") and pace.limit == b.total_limit
    assert not pace.over
    x0, y0, x1, y1 = pace.budget_line
    assert pace.budget_end == (x1, y1) and y1 < y0  # budget accrues upward to the right edge
    assert pace.spent_end[0] == x1
    ys = [float(p.split(",")[1]) for p in pace.spent_points.split()]
    assert min(ys) < ys[-1]  # the refund brought the curve back down at the end
    assert len(pace.months) == len(b.months)


def test_ranked_lines_measure_each_category_against_its_own_limit(config):
    config = at(config, "2026-01-31")
    b = compute([st("2026-01-05", "-1500", "Groceries"),         # limit 1000: 150%
                 st("2026-01-05", "-60000", "Housing"),          # limit 120000: 50%, biggest amount
                 st("2026-01-05", "-100", "Transport"),          # limit 1000: 10%
                 st("2026-01-05", "-2000", "Miscellaneous")], config)  # limit 500: 400%
    ranked = {r.name: r for r in ranked_lines(b)}
    # Most over the limit first, regardless of the amount spent
    assert [r.name for r in ranked_lines(b)][:4] == ["Miscellaneous", "Groceries", "Housing", "Transport"]
    # The limit sits at the same place on every track, so bars compare as % of limit
    assert ranked["Housing"].bar_pct == 25 and ranked["Groceries"].bar_pct == 75
    assert ranked["Transport"].bar_pct == 5
    assert all(r.limit_pct == 50 for r in ranked.values())
    assert ranked["Groceries"].state == "red" and not ranked["Groceries"].capped
    # Beyond the end of the track the bar is cut off and marked as such
    assert ranked["Miscellaneous"].bar_pct == 100 and ranked["Miscellaneous"].capped


def test_month_grid_prorates_the_allowance_for_partial_months(config):
    config = at(config, "2026-01-15")  # window 16.01.2025 - 15.01.2026: Jan 25 and Jan 26 are partial
    b = compute([st("2025-06-10", "-200", "Groceries"), st("2026-01-10", "-10", "Groceries")], config)
    rows = dict(month_grid(b))
    groceries = rows["Groceries"]
    days = 365
    assert groceries[0].allowance == Decimal(1000) * 16 / days   # 16-31 Jan 2025
    assert groceries[5].allowance == Decimal(1000) * 30 / days   # June 2025
    assert groceries[-1].allowance == Decimal(1000) * 15 / days  # 1-15 Jan 2026
    june = groceries[5]
    assert june.fill_pct == 100 and june.state == "red"           # 200 against ~82: capped, flagged
    assert round(sum(c.allowance for c in groceries), 6) == 1000
    assert rows["Total"][5].spent == Decimal(200)


def test_axis_labels_are_short_and_unambiguous():
    assert axis_label(Decimal(0)) == "0"
    assert axis_label(Decimal(500000)) == "500k"
    assert axis_label(Decimal(1000000)) == "1 mio."
    assert axis_label(Decimal(1500000)) == "1,5 mio."


def test_overspending_reads_as_over_not_negative_left(config):
    config = at(config, "2026-01-31")
    html = render(compute([st("2026-01-05", "-1500", "Groceries")], config), config, None)
    assert "500 over" in html and "-500 left" not in html


def test_where_the_money_went_shows_use_of_limit_not_share_of_total(config):
    config = at(config, "2026-01-31")
    html = render(compute([st("2026-01-05", "-2000", "Miscellaneous"),    # limit 500: 400%
                           st("2026-01-05", "-60000", "Housing")], config), config, None)
    where = html[html.index('id="where-h"'):html.index('id="months-h"')]
    assert "Share" not in where
    assert ">400%<" in where and 'class="over capped"' in where
