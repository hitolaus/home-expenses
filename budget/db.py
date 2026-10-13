"""SQLite schema and queries. Money is stored as integer øre so sums are exact."""

from __future__ import annotations

import datetime as dt
import sqlite3
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from .parser import Transaction

SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id            INTEGER PRIMARY KEY,
    fingerprint   TEXT NOT NULL UNIQUE,
    account_id    TEXT NOT NULL,
    date          TEXT NOT NULL,
    description   TEXT NOT NULL,
    amount_ore    INTEGER NOT NULL,
    balance_ore   INTEGER,
    source_file   TEXT NOT NULL,
    imported_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS transactions_date ON transactions(date);

CREATE TABLE IF NOT EXISTS categorizations (
    transaction_id INTEGER PRIMARY KEY REFERENCES transactions(id) ON DELETE CASCADE,
    category       TEXT NOT NULL,
    source         TEXT NOT NULL CHECK (source IN ('claude', 'cache', 'override', 'rule')),
    confidence     REAL,
    model          TEXT,
    categorized_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS merchant_cache (
    normalized_description TEXT PRIMARY KEY,
    category               TEXT NOT NULL,
    updated_at             TEXT NOT NULL
);
"""


def to_ore(d: Decimal) -> int:
    return int((d * 100).to_integral_value())


def from_ore(o: int | None) -> Decimal | None:
    return None if o is None else Decimal(o) / 100


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


@dataclass(frozen=True)
class StoredTransaction:
    id: int
    fingerprint: str
    account_id: str
    date: dt.date
    description: str
    amount: Decimal
    balance: Decimal | None
    source_file: str
    category: str | None
    source: str | None
    confidence: float | None


def connect(path: Path | str) -> sqlite3.Connection:
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def insert_transactions(conn: sqlite3.Connection, txs: list[Transaction], fingerprints: list[str]) -> int:
    """INSERT OR IGNORE by fingerprint; returns the number of new rows."""
    now = _now()
    before = conn.total_changes
    conn.executemany(
        "INSERT OR IGNORE INTO transactions "
        "(fingerprint, account_id, date, description, amount_ore, balance_ore, source_file, imported_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [(fp, t.account_id, t.date.isoformat(), t.description, to_ore(t.amount),
          to_ore(t.balance) if t.balance is not None else None, t.source_file, now)
         for t, fp in zip(txs, fingerprints)],
    )
    conn.commit()
    return conn.total_changes - before


def all_transactions(conn: sqlite3.Connection) -> list[StoredTransaction]:
    rows = conn.execute(
        "SELECT t.*, c.category, c.source, c.confidence FROM transactions t "
        "LEFT JOIN categorizations c ON c.transaction_id = t.id ORDER BY t.date, t.id"
    ).fetchall()
    return [StoredTransaction(
        id=r["id"], fingerprint=r["fingerprint"], account_id=r["account_id"],
        date=dt.date.fromisoformat(r["date"]), description=r["description"],
        amount=from_ore(r["amount_ore"]), balance=from_ore(r["balance_ore"]),
        source_file=r["source_file"], category=r["category"], source=r["source"],
        confidence=r["confidence"],
    ) for r in rows]


def set_categorizations(conn: sqlite3.Connection, items: list[tuple[int, str, str, float | None, str | None]]) -> None:
    """Upsert (transaction_id, category, source, confidence, model) rows."""
    now = _now()
    conn.executemany(
        "INSERT INTO categorizations (transaction_id, category, source, confidence, model, categorized_at) "
        "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(transaction_id) DO UPDATE SET "
        "category=excluded.category, source=excluded.source, confidence=excluded.confidence, "
        "model=excluded.model, categorized_at=excluded.categorized_at",
        [(*item, now) for item in items],
    )
    conn.commit()


def delete_categorizations(conn: sqlite3.Connection, sources: tuple[str, ...]) -> None:
    marks = ",".join("?" * len(sources))
    conn.execute(f"DELETE FROM categorizations WHERE source IN ({marks})", sources)
    conn.commit()


def merchant_cache(conn: sqlite3.Connection) -> dict[str, str]:
    return {r[0]: r[1] for r in conn.execute("SELECT normalized_description, category FROM merchant_cache")}


def update_merchant_cache(conn: sqlite3.Connection, items: dict[str, str]) -> None:
    now = _now()
    conn.executemany(
        "INSERT INTO merchant_cache (normalized_description, category, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(normalized_description) DO UPDATE SET category=excluded.category, updated_at=excluded.updated_at",
        [(k, v, now) for k, v in items.items()],
    )
    conn.commit()


def clear_merchant_cache(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM merchant_cache")
    conn.commit()


def last_import_time(conn: sqlite3.Connection) -> str | None:
    return conn.execute("SELECT MAX(imported_at) FROM transactions").fetchone()[0]
