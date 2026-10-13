import datetime as dt
from decimal import Decimal

import pytest

from budget.parser import (
    balance_breaks, clean_description, merge_page_repeats, parse_amount, parse_pdf,
    table_rows_to_rows, text_to_rows,
)
from make_fixture import expected, write_pdf
from tests.conftest import SAMPLE_PDF

HEADER = ["Dato", "Tekst", "Beløb", "Saldo", "Status", "Afstemt"]
EMPTY = ["", None, None, None, None, None]


def rows_from(pages):
    warnings = []
    rows = merge_page_repeats(table_rows_to_rows(pages, warnings, "test.pdf"))
    return rows, warnings


@pytest.mark.parametrize("text, value", [
    ("1.234,56", "1234.56"),
    ("-1.234,56", "-1234.56"),
    ("-0,64", "-0.64"),
    ("87.255,00", "87255.00"),
    ("-10.267,04", "-10267.04"),
    ("1.000.000,00", "1000000.00"),
])
def test_parse_danish_amounts(text, value):
    assert parse_amount(text) == Decimal(value)


@pytest.mark.parametrize("text", ["-587.00", "12", "abc", "1,2"])
def test_rejects_non_danish_amounts(text):
    with pytest.raises(ValueError):
        parse_amount(text)


def test_sample_pdf_yields_every_row_with_correct_fields():
    result = parse_pdf(SAMPLE_PDF)

    assert result.warnings == []
    got = [(t.date, t.description, t.amount, t.balance) for t in result.transactions]
    want = [(dt.datetime.strptime(d, "%d.%m.%Y").date(), clean_description(lines), a, b)
            for d, lines, a, b in expected()]
    assert got == want
    assert {t.account_id for t in result.transactions} == {"1234567890"}
    assert {t.page for t in result.transactions} == {1, 2}  # spans a page break


def test_multiline_description_is_joined_without_separators():
    assert clean_description(["JOE THE JUICE A/S\\", "\\Kobenhavn\\"]) == "JOE THE JUICE A/S Kobenhavn"
    assert clean_description(["APPLE.COM/BILL\\ \\80249625\\"]) == "APPLE.COM/BILL 80249625"


def test_row_repeated_across_page_break_is_merged_with_full_description():
    # Danske Bank renders a row that straddles a page break on both pages, each clipped.
    pages = [
        (1, [HEADER,
             ["12.10.2026", "Wolt", "-550,00", "32.886,32", "Udført", "Nej"],
             ["11.10.2026", "Hotel at Booking.com\\", "-954,68", "33.436,32", "Udført", "Nej"],
             EMPTY]),
        (2, [EMPTY,
             ["11.10.2026", "Hotel at Booking.com\\\n\\Amsterdam\\", "-954,68", "33.436,32", "Udført", "Nej"],
             ["10.10.2026", "Rejsekort", "-22,00", "34.391,00", "Udført", "Nej"]]),
    ]
    rows, warnings = rows_from(pages)

    assert warnings == []
    assert [(r.date.day, clean_description(r.lines)) for r in rows] == [
        (12, "Wolt"), (11, "Hotel at Booking.com Amsterdam"), (10, "Rejsekort")]
    assert balance_breaks(rows) == []


def test_clipped_fragment_without_date_is_ignored():
    pages = [(1, [HEADER,
                  ["09.09.2026", "Matas", "-150,00", "42.292,52", "Udført", "Nej"],
                  ["", "JOE THE JUICE A/S\\", "", "", "", ""],
                  EMPTY])]
    rows, warnings = rows_from(pages)
    assert [clean_description(r.lines) for r in rows] == ["Matas"]
    assert warnings == []


def test_two_rows_extracted_as_one_are_split():
    pages = [(7, [HEADER, [
        "07.07.2026\n07.07.2026", "MONTA APP\\ \\KBH\\\nCEZ\\ \\Praha\\", "-6,24\n-362,55",
        "18.762,75\n18.768,99", "Udført\nUdført", "Nej\nNej"]])]
    rows, warnings = rows_from(pages)
    assert [(clean_description(r.lines), r.amount, r.balance) for r in rows] == [
        ("MONTA APP KBH", Decimal("-6.24"), Decimal("18762.75")),
        ("CEZ Praha", Decimal("-362.55"), Decimal("18768.99")),
    ]
    assert warnings == []


def test_identical_purchases_on_same_day_are_both_kept():
    pages = [(1, [HEADER,
                  ["03.01.2026", "Caffeine 63613", "-45,00", "100,00", "Udført", "Nej"],
                  ["03.01.2026", "Caffeine 63613", "-45,00", "145,00", "Udført", "Nej"]])]
    rows, _ = rows_from(pages)
    assert len(rows) == 2


def test_saldo_primo_and_ultimo_rows_are_ignored():
    pages = [(1, [HEADER,
                  ["31.01.2026", "Saldo ultimo", "0,00", "145,00", "", ""],
                  ["03.01.2026", "Caffeine", "-45,00", "145,00", "Udført", "Nej"],
                  ["01.01.2026", "Saldo primo", "0,00", "190,00", "", ""]])]
    rows, _ = rows_from(pages)
    assert [clean_description(r.lines) for r in rows] == ["Caffeine"]


def test_unparseable_row_is_skipped_with_warning_naming_file_and_page():
    pages = [(3, [HEADER,
                  ["03.01.2026", "Caffeine", "-45,00", "145,00", "Udført", "Nej"],
                  ["03.01.2026", "Broken", "n/a", "145,00", "Udført", "Nej"]])]
    rows, warnings = rows_from(pages)
    assert len(rows) == 1
    assert len(warnings) == 1 and "test.pdf p.3" in warnings[0]


def test_missing_row_is_reported_as_balance_break(tmp_path):
    rows = expected()
    del rows[3]
    path = tmp_path / "1234567890_x.pdf"
    write_pdf(path, rows)

    result = parse_pdf(path)
    assert len(result.transactions) == len(rows)
    assert len(result.warnings) == 1 and "running balance breaks" in result.warnings[0]


def test_pdf_without_transactions_warns_instead_of_failing(tmp_path):
    from reportlab.pdfgen import canvas
    path = tmp_path / "1234567890_empty.pdf"
    c = canvas.Canvas(str(path))
    c.drawString(100, 750, "Ingen transaktioner")
    c.save()

    result = parse_pdf(path)
    assert result.transactions == []
    assert any("no transactions found" in w for w in result.warnings)


def test_account_id_missing_from_file_name_falls_back_with_warning(tmp_path):
    path = tmp_path / "export.pdf"
    write_pdf(path, expected()[:3])
    result = parse_pdf(path)
    assert {t.account_id for t in result.transactions} == {"export"}
    assert any("no account number" in w for w in result.warnings)


def test_text_fallback_parses_single_and_wrapped_rows():
    text = "\n".join([
        "Dato Tekst Beløb Saldo Status Afstemt",
        "12.10.2026 Til food -3.000,00 29.258,32 Udført Nej",
        "TV2 PLAY 231440063\\ \\ODENSE",
        "09.10.2026 -99,00 32.258,32 Udført Nej",
        "C\\",
    ])
    warnings = []
    rows = text_to_rows([(1, text)], warnings, "x.pdf")
    assert [(clean_description(r.lines), r.amount, r.balance) for r in rows] == [
        ("Til food", Decimal("-3000.00"), Decimal("29258.32")),
        ("TV2 PLAY 231440063 ODENSE", Decimal("-99.00"), Decimal("32258.32")),
    ]
