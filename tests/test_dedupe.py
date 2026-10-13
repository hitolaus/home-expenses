import datetime as dt
from decimal import Decimal

from budget.dedupe import fingerprint_all, normalize_description
from budget.parser import Transaction


def tx(desc="Wolt", amount="-50.00", balance="100.00", day=1, account="111111", source="a.pdf"):
    return Transaction(account, dt.date(2026, 1, day), desc, Decimal(amount),
                       Decimal(balance) if balance is not None else None, source)


def test_same_transaction_from_two_statements_has_same_fingerprint():
    a = fingerprint_all([tx(source="jan.pdf")])
    b = fingerprint_all([tx(source="jan-feb.pdf")])
    assert a == b


def test_description_clipped_differently_by_page_break_still_matches():
    a = fingerprint_all([tx(desc="Hotel at Booking.com Amsterdam")])
    b = fingerprint_all([tx(desc="Amsterdam")])
    assert a == b


def test_identical_purchases_same_day_differ_by_running_balance():
    fps = fingerprint_all([tx(balance="100.00"), tx(balance="150.00")])
    assert len(set(fps)) == 2


def test_different_accounts_never_collide():
    assert fingerprint_all([tx(account="111111")]) != fingerprint_all([tx(account="222222")])


def test_without_balance_occurrence_index_keeps_duplicates_and_is_stable():
    rows = [tx(balance=None), tx(balance=None), tx(desc="Other", balance=None)]
    first = fingerprint_all(rows)
    assert len(set(first)) == 3
    assert fingerprint_all(rows) == first
    # The same statement imported again (or a later one containing it) gives the same keys.
    assert fingerprint_all(rows[:2]) == first[:2]


def test_normalize_description_drops_reference_numbers():
    assert normalize_description("Asia House 91498") == normalize_description("asia house 74975") == "ASIA HOUSE"
    assert normalize_description("Spotify P47209F501 Stockholm") == "SPOTIFY STOCKHOLM"
    assert normalize_description("3.dk") == "3.DK"
    assert normalize_description("12345") == "12345"
