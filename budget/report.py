"""Render the budget as a single self-contained HTML file."""

from __future__ import annotations

import base64
import datetime as dt
import math
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from importlib import resources
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from .budget_calc import Budget
from .config import Config

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
FINGERPRINT_PREFIX = 12


def money(value: Decimal | None, decimals: int = 0) -> str:
    """Danish formatting: 1234.5 -> '1.235' (or '1.234,50' with decimals=2)."""
    if value is None:
        return "–"
    q = Decimal(1).scaleb(-decimals)
    s = f"{abs(value.quantize(q, rounding=ROUND_HALF_UP)):,.{decimals}f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return ("-" if value < 0 and s.strip("0,.") else "") + s


def bar_class(pct: float | None) -> str:
    if pct is None:
        return ""
    if pct > 100:
        return "red"
    if pct >= 75:
        return "amber"
    return "green"


# Pace chart drawing area, in SVG user units.
CHART_W, CHART_H = 1000, 300
CHART_LEFT, CHART_RIGHT, CHART_TOP, CHART_BOTTOM = 64, 150, 34, 26


def nice_step(span: float, ticks: int = 4) -> float:
    """A round 1/2/5 x 10^k step that splits `span` into about `ticks` parts."""
    raw = span / ticks
    mag = 10 ** math.floor(math.log10(raw))
    return next(m * mag for m in (1, 2, 5, 10) if m * mag >= raw)


def month_spans(budget: Budget) -> list[tuple[dt.date, dt.date]]:
    """First and last day of each window month, clipped to the window."""
    first, end = budget.window.first_day, budget.window.end
    spans = []
    for yr, mo in budget.months:
        next_month = dt.date(yr + mo // 12, mo % 12 + 1, 1)
        spans.append((max(dt.date(yr, mo, 1), first), min(next_month - dt.timedelta(days=1), end)))
    return spans


def axis_label(value: Decimal) -> str:
    """Short y-axis label: 500k, 1 mio., 1,5 mio."""
    if value >= 1_000_000:
        return money(value / 1_000_000, 1).removesuffix(",0") + " mio."
    return f"{money(value / 1000)}k" if value else "0"


@dataclass
class PaceChart:
    months: list[tuple[float, float, str]]  # x, width, label
    y_ticks: list[tuple[float, str]]         # y, label
    spent_points: str                        # SVG polyline points
    budget_line: tuple[float, float, float, float]
    spent_end: tuple[float, float]
    budget_end: tuple[float, float]
    spent: Decimal
    limit: Decimal
    over: bool


def pace_chart(budget: Budget) -> PaceChart:
    """Cumulative budgeted spending through the window against the budget accruing evenly."""
    first, end = budget.window.first_day, budget.window.end
    days = (end - first).days + 1
    plot_w = CHART_W - CHART_LEFT - CHART_RIGHT
    plot_h = CHART_H - CHART_TOP - CHART_BOTTOM

    by_day: dict[dt.date, Decimal] = {}
    for ln in budget.lines:
        for t in ln.transactions:
            by_day[t.date] = by_day.get(t.date, Decimal(0)) - t.amount
    cumulative, running = [], Decimal(0)
    for d in sorted(by_day):
        running += by_day[d]
        cumulative.append(((d - first).days + 1, running))

    top_value = max([budget.total_limit, Decimal(1)] + [v for _, v in cumulative])
    step = nice_step(float(top_value))
    y_max = math.ceil(float(top_value) / step) * step

    def x(day: float) -> float:
        return round(CHART_LEFT + plot_w * day / days, 1)

    def y(value) -> float:
        return round(CHART_TOP + plot_h * (1 - float(value) / y_max), 1)

    points = [(x(0), y(0))]
    for day, value in cumulative:
        points.append((x(day - 1), points[-1][1]))  # flat until the day's spending lands
        points.append((x(day), y(value)))
    points.append((x(days), points[-1][1]))

    months = []
    for start, stop in month_spans(budget):
        x0, x1 = x((start - first).days), x((stop - first).days + 1)
        name = MONTH_NAMES[start.month - 1]
        months.append((x0, round(x1 - x0, 1), f"{name} {start.year % 100:02d}" if x1 - x0 > 40 else name))

    ticks, v = [], 0.0
    while v <= y_max + step / 2:
        ticks.append((y(v), axis_label(Decimal(str(v)))))
        v += step

    return PaceChart(
        months=months,
        y_ticks=ticks,
        spent_points=" ".join(f"{px},{py}" for px, py in points),
        budget_line=(x(0), y(0), x(days), y(budget.total_limit)),
        spent_end=points[-1],
        budget_end=(x(days), y(budget.total_limit)),
        spent=budget.total_spent,
        limit=budget.total_limit,
        over=budget.total_spent > budget.total_limit,
    )


RANK_SCALE = 200  # a track runs from 0 to 200% of the category's own limit


@dataclass
class RankedLine:
    name: str
    spent: Decimal
    limit: Decimal | None
    used_pct: float | None
    bar_pct: float    # used % of limit, as % of the track
    limit_pct: float  # the limit's position on the track, the same for every category
    capped: bool      # used more than the track shows
    state: str


def ranked_lines(budget: Budget) -> list[RankedLine]:
    """Budgeted categories, most used of their own limit first, so over-limit ones lead."""
    out = []
    for ln in sorted(budget.lines, key=lambda ln: ln.used_pct or 0.0, reverse=True):
        used = max(ln.used_pct or 0.0, 0.0)
        out.append(RankedLine(
            name=ln.name, spent=ln.spent, limit=ln.limit, used_pct=ln.used_pct,
            bar_pct=min(used, RANK_SCALE) / RANK_SCALE * 100,
            limit_pct=100 / RANK_SCALE * 100,
            capped=used > RANK_SCALE,
            state=bar_class(ln.used_pct),
        ))
    return out


@dataclass
class MonthCell:
    spent: Decimal
    allowance: Decimal
    fill_pct: float  # spending as % of the allowance, capped at 100
    state: str


def month_grid(budget: Budget) -> list[tuple[str, list[MonthCell]]]:
    """Per category and month: spending against that month's share of the yearly limit.

    The share is prorated by how many of the window's days fall in the month, so the
    partial first and last months are not judged against a full month's allowance.
    """
    days = (budget.window.end - budget.window.first_day).days + 1
    month_days = [(stop - start).days + 1 for start, stop in month_spans(budget)]

    def cell(spent: Decimal, limit: Decimal, n_days: int) -> MonthCell:
        allowance = limit * n_days / days
        pct = float(spent / allowance * 100) if allowance else 0.0
        return MonthCell(spent, allowance, max(0.0, min(pct, 100.0)), bar_class(pct) if allowance else "")

    rows = [(ln.name, [cell(v, ln.limit or Decimal(0), n) for v, n in zip(budget.monthly[ln.name], month_days)])
            for ln in budget.lines]
    totals = [sum((budget.monthly[ln.name][i] for ln in budget.lines), Decimal(0)) for i in range(len(month_days))]
    rows.append(("Total", [cell(v, budget.total_limit, n) for v, n in zip(totals, month_days)]))
    return rows


def font_data_uri(weight: int) -> str:
    data = resources.files("budget").joinpath(f"assets/barlow-condensed-latin-{weight}-normal.woff2").read_bytes()
    return "data:font/woff2;base64," + base64.b64encode(data).decode("ascii")


def render(budget: Budget, config: Config, last_import: str | None) -> str:
    env = Environment(loader=PackageLoader("budget", "templates"), autoescape=select_autoescape())
    env.filters["money"] = money
    env.filters["bar_class"] = bar_class
    template = env.get_template("report.html.j2")
    return template.render(
        b=budget,
        currency=config.currency,
        generated=dt.datetime.now().strftime("%d.%m.%Y %H:%M"),
        last_import=dt.datetime.fromisoformat(last_import).strftime("%d.%m.%Y %H:%M") if last_import else None,
        month_labels=[f"{MONTH_NAMES[m - 1]} {y % 100:02d}" for y, m in budget.months],
        fp_len=FINGERPRINT_PREFIX,
        pace=pace_chart(budget),
        chart=dict(w=CHART_W, h=CHART_H, left=CHART_LEFT, top=CHART_TOP, bottom=CHART_H - CHART_BOTTOM),
        ranked=ranked_lines(budget),
        rank_scale=RANK_SCALE,
        grid=month_grid(budget),
        over_count=sum(1 for ln in budget.lines if ln.used_pct is not None and ln.used_pct > 100),
        fonts={w: font_data_uri(w) for w in (500, 700)},
    )


def write_report(budget: Budget, config: Config, last_import: str | None) -> Path:
    config.output.parent.mkdir(parents=True, exist_ok=True)
    config.output.write_text(render(budget, config, last_import), encoding="utf-8")
    return config.output
