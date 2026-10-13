# PRD: Household Budget Tracker (local script)

## 1. Summary

A local Python command-line script for two people (a household) that reads Danske Bank transaction PDFs from a folder, extracts and de-duplicates transactions, categorizes them with Claude (via the Claude Code CLI on the household's Claude subscription) into ~10 spending categories, stores them in a local SQLite database, and generates an HTML report showing spending over the last 12 months against yearly limits per category.

## 2. Goals and non-goals

**Goals**
- One command produces an up-to-date budget report.
- Dropping overlapping or previously processed PDFs into the folder never creates duplicate transactions.
- Categorization is automatic, consistent across runs, and cheap (each transaction is sent to Claude at most once).
- The user can correct a category and have that correction stick.
- Simple to set up: Python, a config file, and Claude Code logged in with a Claude subscription. No API key.

**Non-goals**
- No web app, hosting, multi-user login, or sync between machines.
- No direct bank API integration (PDF input only).
- No support for banks other than Danske Bank in v1.
- No forecasting, savings goals, or investment tracking.

## 3. User flow

1. User downloads one or more account statements ("kontoudtog" / transaction lists) from Danske Bank as PDF and places them in `./statements/`.
2. User runs `python -m budget run`.
3. Script parses all PDFs, inserts new transactions into the database, skips ones already stored, categorizes uncategorized transactions with Claude, and writes `./output/report.html`.
4. User opens the report in a browser.
5. If a transaction is miscategorized, the user adds an override (see §7.4) and re-runs.

## 4. Functional requirements

### 4.1 Configuration (`config.toml`)

```toml
currency = "DKK"
window_months = 12            # rolling window for the report
reference_date = "today"      # or a fixed date, e.g. "2026-09-30"
model = "claude-opus-5-5"
statements_dir = "./statements"
database = "./data/budget.db"
output = "./output/report.html"

[[category]]
name = "Groceries"
description = "Supermarkets, bakeries, groceries"
yearly_limit = 60000

[[category]]
name = "Housing"
description = "Rent, mortgage, utilities, home insurance, repairs"
yearly_limit = 120000

# ... ~10 spending categories total

[[category]]
name = "Income"
description = "Salary, refunds from public authorities, other income"
budgeted = false              # excluded from budget totals

[[category]]
name = "Transfers"
description = "Transfers between our own accounts"
budgeted = false
```

Suggested default spending categories: Groceries, Housing, Transport, Restaurants & takeaway, Shopping & clothes, Subscriptions, Leisure, Vacation, Health, Children, Miscellaneous. Plus the two non-budgeted categories above, so internal transfers and income never distort spending figures.

Claude is reached through the Claude Code CLI (`claude`), which must be installed and logged in with a Claude subscription. No API key is used: `ANTHROPIC_API_KEY` and `ANTHROPIC_AUTH_TOKEN` are removed from the environment passed to `claude`, so the subscription login is always used.

### 4.2 PDF parsing

- Read every `*.pdf` in `statements_dir`.
- Extract transaction rows using `pdfplumber` (table extraction, falling back to text-line parsing with regex).
- Expected fields per row (Danske Bank layout; verify against real PDFs during milestone 1): date (`dd.mm.yyyy`), description/text, amount, balance (`saldo`).
- Parse Danish number format: `1.234,56` → `1234.56`, negative amounts as `-1.234,56`.
- Record the account number/name if present in the PDF header, so multiple accounts can be handled.
- Ignore header, footer, page totals and "Saldo primo/ultimo" rows.
- If a PDF yields zero transactions or rows fail to parse, log a clear warning with file name and page; do not abort the run.

### 4.3 De-duplication

Each transaction gets a deterministic fingerprint:

```
sha256(account_id | date | normalized_description | amount | balance_after)
```

Including the running balance distinguishes genuinely identical purchases on the same day (e.g. two coffees for the same price), which would otherwise collide. If a statement lacks a balance column, fall back to `(account_id, date, description, amount, occurrence_index)` where `occurrence_index` is the position among identical rows within that statement.

The fingerprint is a unique key in the database; inserts use `INSERT OR IGNORE`. Re-running with the same or overlapping PDFs must produce identical totals.

### 4.4 Storage (SQLite)

Tables:

- `transactions(id, fingerprint UNIQUE, account_id, date, description, amount, balance, source_file, imported_at)`
- `categorizations(transaction_id, category, source, confidence, model, categorized_at)` where `source` is `claude`, `override`, or `rule`
- `merchant_cache(normalized_description, category, updated_at)` to reuse categories for recurring merchants without calling Claude

Transactions older than 24 months may be pruned (keeps the DB small while allowing a year-over-year comparison later).

### 4.5 Categorization with Claude

- Only uncategorized transactions are sent.
- Before calling Claude, check (in order): user overrides (§4.6), then `merchant_cache`. Only cache misses go to Claude.
- Send in batches of ~50 transactions, one `claude -p` invocation per batch (transactions as JSON on stdin). The system prompt includes the category list with descriptions from config, and `--json-schema` constrains the output to `{"results": [{"id": ..., "category": ..., "confidence": 0-1}]}` with `category` limited to the configured names.
- The CLI runs isolated from the user's Claude Code setup: `--safe-mode` (no CLAUDE.md, hooks, plugins or MCP servers), no tools, and no session persistence.
- Validate the response: every category must exist in config; unknown values become `Miscellaneous` with confidence 0.
- Store results and update `merchant_cache` for confidence ≥ 0.8.
- If `claude` is not installed, fails, or times out, stop sending batches, leave the remaining transactions uncategorized, and still generate the report (marking them clearly). A single batch with an unusable response is skipped and the other batches continue.
- Positive amounts (refunds) are categorized like expenses and net against their category; salary etc. should land in `Income`.

### 4.6 Manual overrides (`overrides.toml`)

```toml
# Match by description substring (case-insensitive) → category
[rules]
"NETTO" = "Groceries"
"MOBILEPAY ANNA" = "Transfers"

# Or pin a single transaction by fingerprint (shown in the report)
[transactions]
"a3f9c1..." = "Vacation"
```

Overrides always win over Claude and are re-applied on every run, so editing this file and re-running fixes past categorizations.

### 4.7 Budget calculation

- Window: from `reference_date - window_months` (exclusive) to `reference_date` (inclusive).
- For each budgeted category: `spent = -sum(amount)` over transactions in the window (expenses are negative in the bank data; refunds reduce spending).
- `remaining = yearly_limit - spent`; `used_pct = spent / yearly_limit`.
- Totals row across all budgeted categories.
- Warn in the report if the data does not cover the full window (earliest transaction is newer than the window start), since spending will then be understated.

### 4.8 HTML report

A single self-contained HTML file (inline CSS, no external assets), generated with Jinja2:

- Header: report date, window covered, data coverage warning if applicable, last import time.
- Summary table per category: limit, spent, remaining, a progress bar (green < 75%, amber 75–100%, red > 100%).
- Monthly spending per category for the window (a simple table or inline SVG bar chart).
- Expandable per-category transaction lists (date, description, amount, fingerprint prefix for overrides).
- "Needs review" section: uncategorized transactions and those with confidence < 0.6.
- Non-budgeted categories (Income, Transfers) shown separately for transparency.

### 4.9 CLI

```
python -m budget run            # import + categorize + report (default)
python -m budget import         # parse PDFs only
python -m budget categorize     # categorize pending only
python -m budget report         # regenerate report from DB
python -m budget recategorize --all   # clear Claude results (keeps overrides) and redo
```

Output a short run summary: files read, transactions found, new, duplicates skipped, categorized, Claude calls made.

## 5. Non-functional requirements

- Python 3.11+. Dependencies: `pdfplumber`, `jinja2`; `tomllib` from stdlib. External: the Claude Code CLI (`claude`) on `PATH`, logged in with a Claude subscription.
- Runs on macOS/Linux/Windows.
- Typical run (a year of data, ~1,500 transactions) completes in under 2 minutes on first run and seconds afterwards.
- No per-call cost: usage counts against the Claude subscription's usage limits. A first full run with a Haiku-class model uses little of that; subsequent runs only send new transactions.
- Privacy: data stays local except transaction descriptions and amounts sent to Claude via the CLI. Account numbers are not sent. `data/`, `statements/` and `output/` are git-ignored.

## 6. Project structure

```
budget/
  __init__.py
  __main__.py        # CLI entry (argparse)
  config.py          # load + validate config.toml / overrides.toml
  parser.py          # Danske Bank PDF → Transaction objects
  dedupe.py          # fingerprinting
  db.py              # SQLite schema + queries
  categorizer.py     # overrides, cache, Claude batching
  budget_calc.py     # window + per-category math
  report.py          # Jinja2 rendering
  templates/report.html.j2
tests/
  fixtures/          # anonymized sample PDF + expected rows
  test_parser.py
  test_dedupe.py
  test_budget_calc.py
config.example.toml
overrides.example.toml
pyproject.toml       # dependencies (managed with uv; uv.lock pins versions)
README.md
```

## 7. Milestones

1. **Parsing**: parse a real Danske Bank PDF into correct rows, with tests against an anonymized fixture. This is the riskiest part; validate the PDF layout first.
2. **Storage and de-duplication**: SQLite schema, fingerprinting, re-import of overlapping PDFs yields no duplicates.
3. **Categorization**: overrides, merchant cache, Claude batching with JSON validation.
4. **Budget and report**: calculation and HTML report.
5. **Polish**: CLI subcommands, run summary, README with setup steps.

## 8. Acceptance criteria

- Importing the same PDF twice leaves the transaction count unchanged.
- Importing two PDFs with overlapping date ranges yields each transaction exactly once.
- Two identical purchases on the same day are both kept.
- Every transaction in the window ends up in a configured category or in "Needs review".
- An override in `overrides.toml` changes the category on the next run without a Claude call.
- A second run with no new PDFs makes zero Claude calls.
- Report totals match a manual sum of the window's transactions per category.

## 9. Open questions

- Exact Danske Bank PDF layout (column order, whether balance is always present, how multi-line descriptions wrap). Resolve in milestone 1 using a real export.
- How shared vs. personal accounts should be treated if both of you export from separate accounts (one combined budget is assumed).
- Whether MobilePay transfers between you two should be auto-detected as `Transfers` (e.g. by listing your names in config).
