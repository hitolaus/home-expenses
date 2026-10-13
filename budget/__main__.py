"""CLI: python -m budget [run|import|categorize|report|recategorize --all]"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path


from . import budget_calc, db, report
from .categorizer import CategorizeStats, ClaudeClassifier, categorize, reset_claude_results
from .config import Config, ConfigError, load_config, load_overrides
from .dedupe import fingerprint_all
from .parser import parse_pdf

log = logging.getLogger("budget")


@dataclass
class ImportStats:
    files: int = 0
    found: int = 0
    new: int = 0

    @property
    def duplicates(self) -> int:
        return self.found - self.new


def import_statements(conn: sqlite3.Connection, statements_dir: Path) -> ImportStats:
    stats = ImportStats()
    files = sorted(statements_dir.glob("*.pdf")) + sorted(statements_dir.glob("*.PDF"))
    if not files:
        log.warning("No PDFs found in %s", statements_dir)
    for path in files:
        try:
            result = parse_pdf(path)
        except Exception as e:  # a corrupt PDF must not abort the run
            log.warning("%s: could not read PDF: %s", path.name, e)
            continue
        for w in result.warnings:
            log.warning(w)
        stats.files += 1
        stats.found += len(result.transactions)
        stats.new += db.insert_transactions(conn, result.transactions, fingerprint_all(result.transactions))
    return stats


def make_classifier(config: Config):
    try:
        return ClaudeClassifier(config)
    except Exception as e:
        log.warning("Could not use Claude (%s); install Claude Code and run `claude` once to log in", e)
        return None


def run_categorize(conn: sqlite3.Connection, config: Config, overrides_path: Path) -> CategorizeStats:
    overrides = load_overrides(overrides_path, config.category_names)
    return categorize(conn, config, overrides, make_classifier(config))


def run_report(conn: sqlite3.Connection, config: Config) -> Path:
    budget = budget_calc.compute(db.all_transactions(conn), config)
    return report.write_report(budget, config, db.last_import_time(conn))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m budget", description="Household budget tracker")
    parser.add_argument("--config", type=Path, default=Path("config.toml"))
    parser.add_argument("--overrides", type=Path, default=Path("overrides.toml"))
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("run", help="import + categorize + report (default)")
    sub.add_parser("import", help="parse PDFs only")
    sub.add_parser("categorize", help="categorize pending transactions only")
    sub.add_parser("report", help="regenerate the report from the database")
    recat = sub.add_parser("recategorize", help="clear Claude results (keeps overrides) and redo")
    recat.add_argument("--all", action="store_true", required=True)
    args = parser.parse_args(argv)
    command = args.command or "run"

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        config = load_config(args.config)
        conn = db.connect(config.database)
        summary = []

        if command in ("run", "import"):
            s = import_statements(conn, config.statements_dir)
            summary += [f"files read: {s.files}", f"transactions found: {s.found}",
                        f"new: {s.new}", f"duplicates skipped: {s.duplicates}"]

        if command == "recategorize":
            reset_claude_results(conn)
        if command in ("run", "categorize", "recategorize"):
            c = run_categorize(conn, config, args.overrides)
            summary += [f"categorized: {c.overridden} by overrides, {c.from_cache} from cache, "
                        f"{c.from_claude} by Claude", f"Claude calls: {c.api_calls}",
                        f"uncategorized: {c.uncategorized}"]

        if command in ("run", "report"):
            summary.append(f"report: {run_report(conn, config)}")
    except ConfigError as e:
        log.error(str(e))
        return 2

    print("\n".join(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
