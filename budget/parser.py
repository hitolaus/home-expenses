"""Danske Bank transaction-list PDF -> Transaction objects.

Layout (verified against a real 2026 export, "TransactionListTemplate"):
one table per page with columns Dato | Tekst | Beløb | Saldo | Status | Afstemt,
newest first. Quirks handled here:
  * rows straddling a page break are rendered on both pages, each copy with a
    clipped description -> merged back into one row;
  * occasionally two rows are extracted as one row with newline-joined cells;
  * clipped fragments with no date appear at page bottoms -> ignored.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pdfplumber

log = logging.getLogger(__name__)

DATE_RE = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")
AMOUNT_RE = re.compile(r"^-?\d{1,3}(?:\.\d{3})*,\d{2}$")
SKIP_TEXT_RE = re.compile(r"saldo\s+(primo|ultimo)", re.IGNORECASE)
TEXT_LINE_RE = re.compile(
    r"^(\d{2}\.\d{2}\.\d{4})\s+(.*?)\s*(-?\d{1,3}(?:\.\d{3})*,\d{2})\s+(-?\d{1,3}(?:\.\d{3})*,\d{2})\b"
)


@dataclass(frozen=True)
class Transaction:
    account_id: str
    date: dt.date
    description: str
    amount: Decimal
    balance: Decimal | None
    source_file: str
    page: int = 0


@dataclass
class _Row:
    page: int
    date: dt.date
    lines: list[str]
    amount: Decimal
    balance: Decimal | None


@dataclass
class ParseResult:
    transactions: list[Transaction]
    warnings: list[str]


def parse_amount(text: str) -> Decimal:
    """Danish number format: '-1.234,56' -> Decimal('-1234.56')."""
    s = text.strip().replace(" ", "")
    if not AMOUNT_RE.match(s):
        raise ValueError(f"not a Danish amount: {text!r}")
    try:
        return Decimal(s.replace(".", "").replace(",", "."))
    except InvalidOperation:
        raise ValueError(f"not a Danish amount: {text!r}")


def parse_date(text: str) -> dt.date:
    return dt.datetime.strptime(text.strip(), "%d.%m.%Y").date()


def clean_description(lines: list[str]) -> str:
    """Join wrapped lines and drop Danske Bank's backslash field separators."""
    text = " ".join(line.replace("\\", " ") for line in lines)
    return " ".join(text.split())


def account_id_for(path: Path) -> str | None:
    """Danske Bank names exports '<account number>_<from>-<to>.pdf'."""
    m = re.match(r"^(\d{6,})_", path.name)
    return m.group(1) if m else None


def _column_map(header: list[str | None]) -> dict[str, int] | None:
    names = [(c or "").strip().lower() for c in header]
    if "dato" not in names or "beløb" not in names:
        return None
    cols = {"date": names.index("dato"), "amount": names.index("beløb")}
    cols["text"] = names.index("tekst") if "tekst" in names else cols["date"] + 1
    if "saldo" in names:
        cols["balance"] = names.index("saldo")
    return cols


DEFAULT_COLUMNS = {"date": 0, "text": 1, "amount": 2, "balance": 3}


def _cell(row: list[str | None], idx: int | None) -> str:
    if idx is None or idx >= len(row):
        return ""
    return row[idx] or ""


def table_rows_to_rows(pages: list[tuple[int, list[list[str | None]]]], warnings: list[str],
                       source: str) -> list[_Row]:
    """Turn raw extracted table rows (per page) into parsed rows, in document order."""
    cols = DEFAULT_COLUMNS
    out: list[_Row] = []
    for page_no, table in pages:
        for raw in table:
            if not raw:
                continue
            header = _column_map(raw)
            if header:
                cols = header
                continue
            date_cell = _cell(raw, cols["date"]).strip()
            if not date_cell:
                continue  # empty spacer or a clipped fragment of a row repeated on the next page
            dates = date_cell.split("\n")
            amounts = _cell(raw, cols["amount"]).split("\n")
            balances = _cell(raw, cols.get("balance")).split("\n") if "balance" in cols else [None] * len(dates)
            text_lines = _cell(raw, cols["text"]).split("\n")
            n = len(dates)
            if len(amounts) != n or len(balances) != n:
                warnings.append(f"{source} p.{page_no}: could not split merged row {raw!r}")
                continue
            if n == 1:
                per_row_lines = [text_lines]
            elif len(text_lines) == n:
                per_row_lines = [[line] for line in text_lines]
            else:
                warnings.append(f"{source} p.{page_no}: merged row with ambiguous description, "
                                f"using full text for each: {raw!r}")
                per_row_lines = [text_lines] * n
            for d, a, b, lines in zip(dates, amounts, balances, per_row_lines):
                if SKIP_TEXT_RE.search(" ".join(lines)):
                    continue
                if not DATE_RE.match(d.strip()):
                    warnings.append(f"{source} p.{page_no}: skipped unparseable row {raw!r}")
                    continue
                try:
                    out.append(_Row(
                        page=page_no,
                        date=parse_date(d),
                        lines=[line.strip() for line in lines if line.strip()],
                        amount=parse_amount(a),
                        balance=parse_amount(b) if b is not None and b.strip() else None,
                    ))
                except ValueError as e:
                    warnings.append(f"{source} p.{page_no}: skipped unparseable row {raw!r} ({e})")
    return out


def text_to_rows(pages: list[tuple[int, str]], warnings: list[str], source: str) -> list[_Row]:
    """Fallback for pages without an extractable table: one regex per date line.

    A description wrapped around the date line is taken from the preceding
    non-date lines when the date line itself has no text.
    """
    out: list[_Row] = []
    for page_no, text in pages:
        pending: list[str] = []
        for line in text.splitlines():
            m = TEXT_LINE_RE.match(line.strip())
            if not m:
                pending.append(line.strip())
                continue
            date_s, desc, amount_s, balance_s = m.groups()
            lines = [desc] if desc else pending
            pending = []
            if SKIP_TEXT_RE.search(" ".join(lines)):
                continue
            try:
                out.append(_Row(page_no, parse_date(date_s), lines,
                                parse_amount(amount_s), parse_amount(balance_s)))
            except ValueError as e:
                warnings.append(f"{source} p.{page_no}: skipped unparseable line {line!r} ({e})")
    return out


def merge_page_repeats(rows: list[_Row]) -> list[_Row]:
    """Collapse consecutive copies of the same row (same date, amount and balance).

    Two genuinely identical purchases have different running balances, so they
    are never merged. The copies' description lines are unioned in order.
    """
    out: list[_Row] = []
    for row in rows:
        prev = out[-1] if out else None
        if (prev and row.balance is not None and prev.date == row.date
                and prev.amount == row.amount and prev.balance == row.balance):
            for line in row.lines:
                if line not in prev.lines:
                    prev.lines.append(line)
            continue
        out.append(_Row(row.page, row.date, list(row.lines), row.amount, row.balance))
    return out


def balance_breaks(rows: list[_Row]) -> list[_Row]:
    """Rows after which the running balance does not continue (a missed or misread row).

    Statements are newest-first, so balance[i] - amount[i] == balance[i+1];
    an oldest-first statement is accepted too.
    """
    if any(r.balance is None for r in rows) or len(rows) < 2:
        return []
    newest_first = [a for a, b in zip(rows, rows[1:]) if a.balance - a.amount != b.balance]
    oldest_first = [a for a, b in zip(rows, rows[1:]) if b.balance - b.amount != a.balance]
    return min(newest_first, oldest_first, key=len)


def parse_pdf(path: Path) -> ParseResult:
    path = Path(path)
    source = path.name
    warnings: list[str] = []
    account_id = account_id_for(path)
    if account_id is None:
        account_id = path.stem
        warnings.append(f"{source}: no account number in file name, using {account_id!r} as account id "
                        f"(rename to '<account>_....pdf' so overlapping exports de-duplicate)")

    table_pages: list[tuple[int, list]] = []
    text_pages: list[tuple[int, str]] = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables()
            if tables:
                table_pages.append((i, [row for t in tables for row in t]))
            else:
                text_pages.append((i, page.extract_text() or ""))

    rows = table_rows_to_rows(table_pages, warnings, source)
    if text_pages:
        warnings.append(f"{source}: no table found on page(s) {[p for p, _ in text_pages]}, used text fallback")
        rows += text_to_rows(text_pages, warnings, source)
        rows.sort(key=lambda r: r.page)
    rows = merge_page_repeats(rows)

    for r in balance_breaks(rows):
        warnings.append(f"{source} p.{r.page}: running balance breaks after {r.date:%d.%m.%Y} "
                        f"{clean_description(r.lines)!r} {r.amount} - a row may be missing")
    if not rows:
        warnings.append(f"{source}: no transactions found")

    txs = [Transaction(account_id, r.date, clean_description(r.lines), r.amount, r.balance, source, r.page)
           for r in rows]
    return ParseResult(txs, warnings)
