import shutil

from budget import db
from budget.__main__ import import_statements
from make_fixture import expected, write_pdf
from tests.conftest import SAMPLE_PDF


def count(conn):
    return conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]


def test_importing_same_pdf_twice_leaves_count_unchanged(tmp_path):
    shutil.copy(SAMPLE_PDF, tmp_path)
    conn = db.connect(":memory:")

    first = import_statements(conn, tmp_path)
    second = import_statements(conn, tmp_path)

    assert first.new == len(expected()) and count(conn) == len(expected())
    assert second.new == 0 and second.duplicates == len(expected())


def test_overlapping_statements_yield_each_transaction_once(tmp_path):
    rows = expected()  # newest first
    write_pdf(tmp_path / "1234567890_early.pdf", rows[20:])
    write_pdf(tmp_path / "1234567890_late.pdf", rows[:40])  # overlaps rows 20..39
    conn = db.connect(":memory:")

    stats = import_statements(conn, tmp_path)

    assert stats.found == len(rows) + 20
    assert stats.new == len(rows) == count(conn)
    balances = sorted(t.balance for t in db.all_transactions(conn))
    assert balances == sorted(b for *_, b in rows)


def test_identical_purchases_on_same_day_are_both_stored(tmp_path):
    shutil.copy(SAMPLE_PDF, tmp_path)
    conn = db.connect(":memory:")
    import_statements(conn, tmp_path)
    caffeine = [t for t in db.all_transactions(conn) if t.description == "Caffeine 63613"]
    assert len(caffeine) == 2


def test_corrupt_pdf_does_not_abort_import(tmp_path, caplog):
    shutil.copy(SAMPLE_PDF, tmp_path)
    (tmp_path / "broken.pdf").write_bytes(b"not a pdf")
    conn = db.connect(":memory:")
    stats = import_statements(conn, tmp_path)
    assert stats.new == len(expected())
    assert "broken.pdf" in caplog.text


def test_money_is_stored_exactly():
    from decimal import Decimal
    assert db.to_ore(Decimal("-12062.98")) == -1206298
    assert db.from_ore(-1206298) == Decimal("-12062.98")
