# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
A couple running one shared household budget. One of them runs the tool; both read the report together, usually on a laptop or desktop. One reader does not speak Danish, so everything the tool writes must be in English. Only the bank's own transaction texts stay Danish.

## Product Purpose
A local command-line tool reads Danske Bank transaction PDFs, removes duplicates, categorizes transactions with Claude, and writes one HTML report. The report shows rolling 12-month spending against a yearly limit for each category. Success means the two of them can see at a glance whether they are on track and where the money goes, then drill into transactions and fix wrong categories.

## Operating Context
- The report is regenerated after new statements are imported (`uv run python -m budget run`) and opened locally from `output/report.html`.
- Wrong categories are fixed by adding a transaction's fingerprint prefix or a description rule to `overrides.toml`, then rerunning. The report has to show fingerprints so that is possible.
- Categories, yearly limits and the window length are set in `config.toml`, and the user can change them at any time.

## Capabilities and Constraints
- The report is one self-contained HTML file: inline CSS, no external assets, no `<script>`, no network URLs. Visuals must be inline SVG/CSS rendered by the Jinja2 template.
- Money is in DKK with Danish number formatting (1.234,50); dates are DD.MM.YYYY.
- Budgeted categories have a yearly limit. Income and Transfers are non-budgeted and must never distort the spending figures.
- "Needs review": uncategorized transactions, plus Claude results with confidence below 0.6.
- Data coverage warnings appear when an account's data starts after the window start.

## Evidence on Hand
Real data: one Danske Bank export covering 12.10.2025–12.10.2026 (`statements/`). The report shows only real computed figures. Never invent sample numbers.

## Product Principles
- Answer "are we on track?" and "where does the money go?" before anything else.
- Every number can be traced to its transactions.
- Make correction easy: anything that needs review is obvious, and its fingerprint is right there.
- Readable by a non-Danish speaker.
