---
version: 1
slug: "budget-templates-report-html-j2"
primary_target: "budget/templates/report.html.j2"
related_targets: ["budget/report.py","output/report.html"]
---

# Budget report (output/report.html)

Scope: the single self-contained HTML report rendered by budget/templates/report.html.j2 (+ budget/report.py view helpers). Mode: Operate. Desktop/laptop first, must still work on a phone.

Audience and task: a couple, one non-Danish speaker, reviewing the rolling 12 months together. Answer "are we on track?" and "where did the money go?" first, then let them drill into transactions and copy fingerprints to fix categories. All UI copy is in English; amounts and dates keep Danish formatting.

Constraints: no <script>, no external URLs, no remote fonts; visuals are inline SVG/CSS rendered server-side; fonts are embedded as data URIs. Only real computed figures are shown.

## Direction contract

THESIS: The budget year as a kitchen wall year planner. Ruled month columns, a today edge, and each category marked in with a marker pen, filled up to what was spent. This refuses the fintech-dashboard default of KPI tiles, a donut and floating cards.

OWN-WORLD: Planner paper (white) with black ruled hairlines and a heavier rule at every month. Ink is near-black. Three marker colours map to state: green under 75%, amber 75–100%, red over the limit. Red is reserved for over-limit and needs-review only (raise from gate board). Month and section headings are set in condensed grotesk caps (Barlow Condensed, embedded). Figures are tabular. No cards and no shadows: structure comes from rules and columns, not boxes.

STORY: They see the verdict for the year, then how the year unfolded against the budget, then where the money went by category, then month-by-month detail. They open a category to check transactions and copy a fingerprint from Needs review.

FIRST VIEWPORT: A masthead line (title, window, last import). Then a monumental verdict sentence across the width: "Under budget / Over budget", with spent of limit and what's left (raise from Isotype: one answer first). Below that, a full-width planner chart: month columns ruled like the wall planner, the budget accruing as a straight ruled line, cumulative spending as a marker stroke, and the gap at the right edge labelled.

FORM: Kitchen wall year planner. My #1 grounded candidate, chosen by the user as the pick card over the rolled Isotype direction. Seed key 7ac860b5. Raise from Isotype: categories rank as counted bars with the limit as a tick, so "where did the money go" is answered by length.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
