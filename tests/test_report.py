import dataclasses
import datetime as dt
from decimal import Decimal

from budget.budget_calc import compute
from budget.report import (axis_label, bar_class, month_bars, month_grid, month_groups, money, ranked_lines,
                           render, slug)
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
    assert "Within budget" not in html and "Over budget" not in html  # no verdict headline
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


def test_month_bars_show_budgeted_spending_per_month_against_its_share(config):
    config = at(config, "2026-01-31")  # window 01.02.2025 - 31.01.2026: twelve full months
    b = compute([st("2025-03-01", "-400", "Groceries"), st("2025-03-20", "-600", "Housing"),
                 st("2025-03-21", "100", "Housing"),                  # refund lowers the month
                 st("2025-03-05", "-5000", "Income"),                 # non-budgeted: not in the bars
                 st("2025-09-01", "-30000", "Housing")], config)
    bars = month_bars(b).bars
    assert [m.label for m in bars] == [f"{m} {y}" for m, y in zip(
        ["Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan"], ["25"] * 11 + ["26"])]
    march, september, may = bars[1], bars[7], bars[3]
    assert march.spent == Decimal("900") and march.state == "green"
    assert march.over_y == march.bar_top > march.share_y  # under its share: the share line sits above the bar
    assert september.spent == Decimal("30000") and september.state == "red"
    assert september.bar_top < september.over_y == september.share_y  # the part above the share is the overspend
    assert september.bar_top < march.bar_top                          # the expensive month is the tall bar
    assert may.spent == 0 and all(m.days is None for m in bars)


def test_month_bars_judge_partial_months_against_a_partial_share(config):
    config = at(config, "2026-01-15")  # window 16.01.2025 - 15.01.2026
    b = compute([st("2025-01-20", "-20", "Groceries")], config)
    bars = month_bars(b).bars
    first, last = bars[0], bars[-1]
    assert (first.days, last.days) == ("16-31", "1-15") and bars[5].days is None
    assert first.allowance == b.total_limit * 16 / 365
    assert first.share_y > bars[5].share_y  # a shorter share than a full month


def test_month_bars_label_each_month_with_its_amount(config):
    config = at(config, "2026-01-31")
    html = render(compute([st("2025-09-01", "-30000", "Housing")], config), config, None)
    section = html[html.index('id="bars-h"'):html.index('id="months-h"')]
    assert ">30.000<" in section and 'class="amount fill-red"' in section
    assert "url(#over-hatch)" in section


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


def test_where_the_money_went_shows_each_category_monthly_budget(config):
    config = at(config, "2026-01-31")
    b = compute([st("2026-01-05", "-60000", "Housing")], config)
    assert {r.name: r.month_limit for r in ranked_lines(b)}["Housing"] == Decimal("10000")
    html = render(b, config, None)
    where = html[html.index('id="where-h"'):html.index("</section>", html.index('id="where-h"'))]
    assert "Per month" in where
    housing = where[where.index(">Housing<"):]
    assert ">10.000<" in housing[:housing.index('class="rank-row')]
    total = where[where.index(">Total<"):]
    assert f">{money(b.total_limit / 12)}<" in total


def test_where_the_money_went_comes_before_the_charts(config):
    config = at(config, "2026-01-31")
    html = render(compute([st("2026-01-05", "-100", "Groceries")], config), config, None)
    assert html.index('id="where-h"') < html.index('id="bars-h"') < html.index('id="months-h"')


def test_month_bars_for_one_category_use_its_spending_and_its_own_limit(config):
    config = at(config, "2026-01-31")  # twelve full months
    b = compute([st("2025-03-01", "-400", "Groceries"), st("2025-03-20", "-600", "Housing")], config)
    groceries = month_bars(b, "Groceries").bars
    total = month_bars(b).bars
    assert groceries[1].spent == Decimal("400") and total[1].spent == Decimal("1000")
    assert groceries[1].allowance == Decimal(1000) * 31 / 365  # March's share of Groceries' 1.000 limit
    assert groceries[1].state == "red"                          # 400 against ~85: over its own share


def test_slug_makes_a_url_fragment_from_a_category_name():
    assert slug("Restaurants & takeaway") == "restaurants-takeaway"
    assert slug("Groceries") == "groceries"


def section(html, start_id):
    start = html.index(start_id)
    return html[start:html.index("</section>", start)]


def test_categories_in_where_the_money_went_drill_down_to_their_months_and_transactions(config):
    config = at(config, "2026-01-31")
    groceries = st("2026-01-05", "-1500", "Groceries")
    housing = st("2026-01-06", "-60000", "Housing")
    html = render(compute([groceries, housing], config), config, None)

    where = section(html, 'id="where-h"')
    assert 'href="#c-groceries"' in where and 'href="#c-housing"' in where

    spending = section(html, 'id="bars-h"')
    panel = spending[spending.index('id="c-groceries"'):spending.index('id="c-housing"')]
    assert "<svg" in panel and ">1.500<" in panel             # its own month chart
    assert f">{groceries.description}<" in panel             # and its transactions
    assert f">{housing.description}<" not in panel


def test_spending_per_month_defaults_to_the_total_and_has_no_separate_transactions_section(config):
    config = at(config, "2026-01-31")
    html = render(compute([st("2026-01-05", "-1500", "Groceries"), st("2026-01-06", "-600", "Housing")], config), config, None)
    spending = section(html, 'id="bars-h"')
    total = spending[spending.index('class="drill all"'):]
    assert ">2.100<" in total                                  # the total chart, shown without a selection
    assert ".bars .drill:is(:target, :has(:target)) ~ .drill.all { display: none; }" in html
    assert "Transactions by category" not in html


def test_month_groups_split_a_category_by_window_month_newest_first(config):
    config = at(config, "2026-01-31")  # window 01.02.2025 - 31.01.2026
    b = compute([st("2025-03-01", "-400", "Groceries"), st("2025-03-20", "-100", "Groceries"),
                 st("2025-04-02", "-50", "Groceries"), st("2025-03-05", "-999", "Housing")], config)
    groups = month_groups(b, "Groceries")
    assert [(g.key, g.label, g.spent, len(g.transactions)) for g in groups] == [
        ("2025-04", "Apr 25", Decimal("50"), 1),
        ("2025-03", "Mar 25", Decimal("500"), 2),           # Housing's March spending is not in it
    ]
    assert [t.date for t in groups[1].transactions] == [dt.date(2025, 3, 20), dt.date(2025, 3, 1)]
    # shaded like the same month's column in the month bars: every second window month, from Mar
    assert groups[1].shaded and not groups[0].shaded


def test_category_month_bars_link_to_that_month_in_its_transactions(config):
    config = at(config, "2026-01-31")
    html = render(compute([st("2025-03-01", "-400", "Groceries"), st("2025-04-02", "-50", "Housing")], config),
                  config, None)
    spending = section(html, 'id="bars-h"')
    panel = spending[spending.index('id="c-groceries"'):spending.index('id="c-housing"')]
    assert 'href="#c-groceries-2025-03"' in panel and 'id="c-groceries-2025-03"' in panel
    assert 'href="#c-groceries-2025-04"' not in panel          # no transactions that month: nothing to go to
    total = spending[spending.index('class="drill all"'):]
    assert "<a " not in total                                  # all categories: bars do nothing
    # a month inside a panel keeps the panel open
    assert ".bars .drill:target, .bars .drill:has(:target), .bars .drill.all { display: block; }" in html
