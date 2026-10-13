"""Load and validate config.toml and overrides.toml."""

from __future__ import annotations

import datetime as dt
import re
import tomllib
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

FALLBACK_CATEGORY = "Miscellaneous"


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Category:
    name: str
    description: str
    budgeted: bool
    yearly_limit: Decimal | None


@dataclass(frozen=True)
class Config:
    currency: str
    window_months: int
    reference_date: dt.date
    model: str
    statements_dir: Path
    database: Path
    output: Path
    categories: list[Category]

    @property
    def category_names(self) -> list[str]:
        return [c.name for c in self.categories]

    @property
    def budgeted(self) -> list[Category]:
        return [c for c in self.categories if c.budgeted]

    @property
    def non_budgeted(self) -> list[Category]:
        return [c for c in self.categories if not c.budgeted]


@dataclass(frozen=True)
class Overrides:
    # description substring (upper-cased) -> category, in file order
    rules: dict[str, str] = field(default_factory=dict)
    # fingerprint or fingerprint prefix (lower-cased) -> category
    transactions: dict[str, str] = field(default_factory=dict)


def _resolve(base: Path, value: str) -> Path:
    p = Path(value)
    return p if p.is_absolute() else (base / p)


def load_config(path: Path, today: dt.date | None = None) -> Config:
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Config file not found: {path} (copy config.example.toml to get started)")
    with path.open("rb") as f:
        raw = tomllib.load(f)
    base = path.parent

    ref = raw.get("reference_date", "today")
    if ref == "today":
        reference_date = today or dt.date.today()
    else:
        try:
            reference_date = dt.date.fromisoformat(str(ref))
        except ValueError:
            raise ConfigError(f"reference_date must be 'today' or YYYY-MM-DD, got {ref!r}")

    window_months = raw.get("window_months", 12)
    if not isinstance(window_months, int) or window_months < 1:
        raise ConfigError("window_months must be a positive integer")

    categories = []
    seen = set()
    for c in raw.get("category", []):
        name = c.get("name")
        if not name:
            raise ConfigError("Every [[category]] needs a name")
        if name in seen:
            raise ConfigError(f"Duplicate category: {name}")
        seen.add(name)
        budgeted = c.get("budgeted", True)
        limit = c.get("yearly_limit")
        if budgeted and limit is None:
            raise ConfigError(f"Budgeted category {name!r} needs a yearly_limit")
        categories.append(Category(
            name=name,
            description=c.get("description", ""),
            budgeted=budgeted,
            yearly_limit=Decimal(str(limit)) if limit is not None else None,
        ))
    if FALLBACK_CATEGORY not in seen:
        raise ConfigError(f"Config must define a {FALLBACK_CATEGORY!r} category (used for unknown results)")

    return Config(
        currency=raw.get("currency", "DKK"),
        window_months=window_months,
        reference_date=reference_date,
        model=raw.get("model", "claude-opus-5-5"),
        statements_dir=_resolve(base, raw.get("statements_dir", "./statements")),
        database=_resolve(base, raw.get("database", "./data/budget.db")),
        output=_resolve(base, raw.get("output", "./output/report.html")),
        categories=categories,
    )


def load_overrides(path: Path, category_names: list[str]) -> Overrides:
    path = Path(path)
    if not path.exists():
        return Overrides()
    with path.open("rb") as f:
        raw = tomllib.load(f)
    valid = set(category_names)
    for key in raw.get("transactions", {}):
        if not re.fullmatch(r"[0-9a-fA-F]{8,64}\.*", key):
            raise ConfigError(f"{path}: [transactions] key {key!r} must be a fingerprint (at least 8 hex chars)")
    for section in ("rules", "transactions"):
        for key, cat in raw.get(section, {}).items():
            if cat not in valid:
                raise ConfigError(f"{path}: [{section}] {key!r} -> unknown category {cat!r}")
    return Overrides(
        rules={k.upper(): v for k, v in raw.get("rules", {}).items()},
        transactions={k.lower().rstrip("."): v for k, v in raw.get("transactions", {}).items()},
    )
