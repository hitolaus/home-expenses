"""Deterministic transaction fingerprints and description normalization."""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from typing import Iterable

from .parser import Transaction


def normalize_description(description: str) -> str:
    """Merchant key: upper-case, drop reference-number-like tokens (3+ digits).

    'Asia House 91498' and 'Asia House 74975' both become 'ASIA HOUSE'.
    """
    tokens = description.upper().split()
    kept = [t for t in tokens if sum(ch.isdigit() for ch in t) < 3]
    return " ".join(kept) or " ".join(tokens)


def _sha(parts: Iterable[object]) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()


def fingerprint_all(transactions: list[Transaction]) -> list[str]:
    """Fingerprints for the transactions of one statement, in order.

    With a running balance, (account, date, amount, balance) identifies a row.
    The description is deliberately left out: Danske Bank PDFs repeat and clip
    rows that straddle a page break, so the same transaction can be extracted
    with different description text from two overlapping statements.

    Without a balance, fall back to (account, date, description, amount,
    occurrence_index among identical rows in this statement).
    """
    seen: Counter[tuple] = Counter()
    out = []
    for t in transactions:
        if t.balance is not None:
            out.append(_sha((t.account_id, t.date.isoformat(), t.amount, t.balance)))
        else:
            key = (t.account_id, t.date.isoformat(), normalize_description(t.description), t.amount)
            out.append(_sha((*key, seen[key])))
            seen[key] += 1
    return out
