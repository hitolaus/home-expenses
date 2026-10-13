"""Categorization: overrides -> merchant cache -> Claude (batched, structured JSON)."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import sqlite3
import subprocess
from dataclasses import dataclass
from typing import Callable

from . import db
from .config import FALLBACK_CATEGORY, Config, Overrides
from .dedupe import normalize_description

log = logging.getLogger(__name__)

BATCH_SIZE = 50
CACHE_MIN_CONFIDENCE = 0.8
CLI_TIMEOUT_SECONDS = 300


class ApiUnavailable(Exception):
    """The API could not be reached even after retries; stop sending batches."""


class BadResponse(Exception):
    """One batch got an unusable response; other batches may still succeed."""


# A classifier takes [{"id", "date", "description", "amount"}] and returns
# [{"id", "category", "confidence"}]. Injected so tests run without the API.
Classifier = Callable[[list[dict]], list[dict]]


@dataclass
class CategorizeStats:
    overridden: int = 0
    from_cache: int = 0
    from_claude: int = 0
    api_calls: int = 0
    uncategorized: int = 0


def override_category(t: db.StoredTransaction, overrides: Overrides) -> tuple[str, str] | None:
    """(category, source) if an override applies. Pinned fingerprints beat description rules."""
    for prefix, category in overrides.transactions.items():
        if t.fingerprint.startswith(prefix):
            return category, "override"
    desc = t.description.upper()
    for needle, category in overrides.rules.items():
        if needle in desc:
            return category, "rule"
    return None


def apply_overrides(conn: sqlite3.Connection, overrides: Overrides) -> int:
    """Re-apply overrides from scratch, so edits and removals in overrides.toml take effect."""
    db.delete_categorizations(conn, ("override", "rule"))
    items = []
    for t in db.all_transactions(conn):
        match = override_category(t, overrides)
        if match:
            items.append((t.id, match[0], match[1], None, None))
    db.set_categorizations(conn, items)
    return len(items)


def mask_numbers(description: str) -> str:
    """Hide account/card-like numbers before sending text to the API."""
    return re.sub(r"\d{6,}", "######", description)


def categorize(conn: sqlite3.Connection, config: Config, overrides: Overrides,
               classify: Classifier | None) -> CategorizeStats:
    stats = CategorizeStats()
    stats.overridden = apply_overrides(conn, overrides)

    pending = [t for t in db.all_transactions(conn) if t.category is None]

    cache = db.merchant_cache(conn)
    valid = set(config.category_names)
    hits, misses = [], []
    for t in pending:
        cat = cache.get(normalize_description(t.description))
        if cat in valid:
            hits.append((t.id, cat, "cache", None, None))
        else:
            misses.append(t)
    db.set_categorizations(conn, hits)
    stats.from_cache = len(hits)

    # Recurring merchants are sent once: one representative per (merchant, in/out).
    groups: dict[tuple[str, bool], list[db.StoredTransaction]] = {}
    for t in misses:
        groups.setdefault((normalize_description(t.description), t.amount > 0), []).append(t)
    reps = [members[0] for members in groups.values()]

    if not reps:
        return stats
    if classify is None:
        log.warning("No Claude client available; %d transactions left uncategorized", len(misses))
        stats.uncategorized = len(misses)
        return stats

    for start in range(0, len(reps), BATCH_SIZE):
        batch = reps[start:start + BATCH_SIZE]
        items = [{"id": t.id, "date": t.date.isoformat(), "description": mask_numbers(t.description),
                  "amount": str(t.amount)} for t in batch]
        stats.api_calls += 1
        try:
            results = classify(items)
        except ApiUnavailable as e:
            log.warning("Claude API unavailable, leaving the rest uncategorized: %s", e)
            break
        except BadResponse as e:
            log.warning("Unusable response for a batch of %d, left uncategorized: %s", len(batch), e)
            continue

        by_id = {t.id: t for t in batch}
        rows, cache_updates = [], {}
        for r in results:
            rep = by_id.get(r.get("id"))
            if rep is None:
                continue
            category, confidence = r.get("category"), r.get("confidence")
            try:
                confidence = min(max(float(confidence), 0.0), 1.0)
            except (TypeError, ValueError):
                confidence = 0.0
            if category not in valid:
                category, confidence = FALLBACK_CATEGORY, 0.0
            key = (normalize_description(rep.description), rep.amount > 0)
            for t in groups[key]:
                rows.append((t.id, category, "claude", confidence, config.model))
            if confidence >= CACHE_MIN_CONFIDENCE:
                cache_updates[key[0]] = category
        db.set_categorizations(conn, rows)
        db.update_merchant_cache(conn, cache_updates)
        stats.from_claude += len(rows)

    stats.uncategorized = sum(1 for t in db.all_transactions(conn) if t.category is None)
    return stats


def reset_claude_results(conn: sqlite3.Connection) -> None:
    """For `recategorize --all`: forget Claude and cache results; overrides are kept."""
    db.delete_categorizations(conn, ("claude", "cache"))
    db.clear_merchant_cache(conn)


SYSTEM_PROMPT = """You categorize bank transactions for a Danish household budget.

Categories:
{categories}

Each transaction has an id, date, description (Danish bank text, often a merchant name \
followed by a terminal or reference number) and amount in {currency}. Negative amounts are \
money out, positive amounts are money in. A positive amount from a merchant is a refund: give \
it that merchant's spending category. Choose the category whose description fits best; use \
"{fallback}" when nothing fits.

Return one result per transaction id with a confidence between 0 and 1 reflecting how sure \
you are."""


class ClaudeClassifier:
    """Runs the `claude` CLI in print mode, so it uses the Claude subscription it is logged in with."""

    def __init__(self, config: Config, run=subprocess.run, executable: str | None = None):
        executable = executable or shutil.which("claude")
        if executable is None:
            raise ApiUnavailable("`claude` CLI not found on PATH")
        self.executable = executable
        self.run = run
        self.model = config.model
        self.names = config.category_names
        self.system = SYSTEM_PROMPT.format(
            categories="\n".join(f"- {c.name}: {c.description}" for c in config.categories),
            currency=config.currency,
            fallback=FALLBACK_CATEGORY,
        )
        self.schema = {
            "type": "object",
            "properties": {
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "category": {"type": "string", "enum": self.names},
                            "confidence": {"type": "number"},
                        },
                        "required": ["id", "category", "confidence"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["results"],
            "additionalProperties": False,
        }

    def __call__(self, items: list[dict]) -> list[dict]:
        argv = [
            self.executable, "-p", "--safe-mode", "--no-session-persistence", "--tools", "",
            "--model", self.model, "--effort", "low", "--system-prompt", self.system,
            "--json-schema", json.dumps(self.schema, ensure_ascii=False), "--output-format", "json",
        ]
        # An API key in the environment would take precedence over the subscription login.
        env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
        try:
            proc = self.run(argv, input=json.dumps(items, ensure_ascii=False), capture_output=True,
                            text=True, env=env, timeout=CLI_TIMEOUT_SECONDS)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise ApiUnavailable(str(e)) from e
        try:
            out = json.loads(proc.stdout)
        except ValueError as e:
            if proc.returncode != 0:
                raise ApiUnavailable(f"claude exited {proc.returncode}: {proc.stderr.strip()}") from e
            raise BadResponse(f"invalid JSON from claude: {e}") from e
        if proc.returncode != 0 or out.get("is_error"):
            raise ApiUnavailable(f"claude failed: {out.get('result')}")
        results = (out.get("structured_output") or {}).get("results")
        if not isinstance(results, list):
            raise BadResponse("structured output has no results list")
        return [r for r in results if isinstance(r, dict)]
