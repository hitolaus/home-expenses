---
name: Household budget
description: A rolling-year household budget report drawn as a kitchen wall year planner.
colors:
  paper: "#ffffff"
  ink: "#1b1b19"
  muted: "#67675f"
  rule: "#cfcfc7"
  hair: "#e9e9e3"
  column: "#f6f6f2"
  green: "#2f7a52"
  green-tint: "#d3e7da"
  amber: "#c98a12"
  amber-tint: "#f5e2b8"
  red: "#c8402c"
  red-tint: "#f6d3cb"
typography:
  display:
    fontFamily: "Planner, Arial Narrow, sans-serif"
    fontSize: "clamp(40px, 6.4vw, 76px)"
    fontWeight: 700
    lineHeight: 0.95
    letterSpacing: "-0.01em"
  headline:
    fontFamily: "Planner, Arial Narrow, sans-serif"
    fontSize: "26px"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "0.04em"
  title:
    fontFamily: "Planner, Arial Narrow, sans-serif"
    fontSize: "15px"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "0.12em"
  figure:
    fontFamily: "Planner, Arial Narrow, sans-serif"
    fontSize: "22px"
    fontWeight: 500
    lineHeight: 1
    letterSpacing: "0"
  label:
    fontFamily: "Planner, Arial Narrow, sans-serif"
    fontSize: "13px"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "0.08em"
  lead:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, system-ui, sans-serif"
    fontSize: "19px"
    fontWeight: 400
    lineHeight: 1.45
    fontFeature: "tnum"
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "tnum"
  small:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, system-ui, sans-serif"
    fontSize: "12.5px"
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "tnum"
  mono:
    fontFamily: "ui-monospace, SF Mono, Menlo, monospace"
    fontSize: "12.5px"
    fontWeight: 400
    lineHeight: 1
rounded:
  none: "0"
  fill: "2px"
  mark: "3px"
  dot: "50%"
spacing:
  row: "11px"
  gutter: "16px"
  page-top: "32px"
  section: "64px"
  section-compact: "48px"
  footer: "72px"
components:
  section-heading:
    textColor: "{colors.ink}"
    typography: "{typography.title}"
    padding: "0 0 9px"
  rank-fill-green:
    backgroundColor: "{colors.green}"
    rounded: "{rounded.fill}"
    height: "14px"
  rank-fill-amber:
    backgroundColor: "{colors.amber}"
    rounded: "{rounded.fill}"
    height: "14px"
  rank-fill-red:
    backgroundColor: "{colors.red}"
    rounded: "{rounded.fill}"
    height: "14px"
  limit-tick:
    backgroundColor: "{colors.ink}"
    rounded: "{rounded.none}"
    width: "2px"
    height: "24px"
  planner-cell:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.small}"
    height: "40px"
  planner-ink-green:
    backgroundColor: "{colors.green-tint}"
    rounded: "{rounded.fill}"
  planner-ink-amber:
    backgroundColor: "{colors.amber-tint}"
    rounded: "{rounded.fill}"
  planner-ink-red:
    backgroundColor: "{colors.red-tint}"
    rounded: "{rounded.fill}"
  disclosure-row:
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    padding: "11px 0"
---

# Design System: Household budget

## Overview

**Creative North Star: "The Kitchen Wall Year Planner"**

The report is a paper year planner pinned to the kitchen wall: white planner paper, near-black ink rules, a heavier rule at every month, and each category marked in with a marker pen up to what was spent. Structure comes from ruled lines and columns, never from boxes. The reader gets the most important answer first: each category against its own limit, with its monthly budget. Then the year drawn against the budget, then month-by-month detail, then the transactions behind every number. There is no verdict headline; the ranked list's total row carries the overall figure.

Density is high but calm. Figures are tabular everywhere so columns of Danish-formatted amounts align. Colour is almost absent until it means something: three marker colours carry state and nothing else. Headings and chart labels are set in a condensed grotesk in caps, the hand-lettered register of a wall planner; reading text is the system sans.

The document is one self-contained HTML file: inline CSS, inline SVG drawn server-side, fonts embedded as data URIs, no script, no external URL. Every visual must be achievable under that constraint.

**Key Characteristics:**
- White planner paper, near-black ink, three marker colours mapped to state.
- Ruled structure: 3px ink rules bound the page, 1.5px ink rules open sections and close totals, 1px hairlines separate rows.
- Barlow Condensed (embedded as "Planner") in caps for headings, chart labels and headline figures; system sans for prose and tables.
- No cards, no elevation shadows, no containers with fills.
- Charts are planner drawings: a pace chart, limit bars crossing one ruled limit line, a month grid filled like marker ink.
- Self-contained: no script, no network, server-rendered SVG and CSS only.

## Colors

A white sheet with warm-neutral ink and greys, plus three marker colours that only ever report state.

### Primary
- **Planner Ink** (`ink`): all text, month rules, the today edge, axes, the limit tick, section and total rules, focus outlines. It is the line work of the planner.

### Secondary (state markers)
- **Marker Green** (`green`): under 75% of a limit. Bar fills, the pace stroke when on track, the "to spare" gap label.
- **Marker Amber** (`amber`): 75 to 100% of a limit. Bar fills, the pace stroke when close, the dot beside coverage warnings. Graphic only; never sets text.
- **Marker Red** (`red`): over a limit, and needs review. Bar fills, the overspend hatch, the "over" amounts, the needs-review dot and low-confidence values, the top edge of an over-share month cell.

### Tertiary (marker tints)
- **Green Wash** (`green-tint`), **Amber Wash** (`amber-tint`), **Red Wash** (`red-tint`): the same three states laid down lightly, used where ink text sits on the colour: month-grid cells and the light half of the overspend hatch. Amber Wash doubles as the text-selection colour.

### Neutral
- **Planner Paper** (`paper`): the page and every surface. There is no second surface colour.
- **Pencil Grey** (`muted`): secondary text, ledes, column heads, sub-figures, axis values, fingerprints.
- **Ruled Line** (`rule`): list and table header rules, the dotted baseline of a bar track.
- **Hairline** (`hair`): row separators and chart gridlines.
- **Column Shade** (`column`): alternate month columns in the pace chart and alternate rows of the month grid, the faint banding of a printed planner.

### Named Rules
**The Red Means Trouble Rule.** Red and its wash are reserved for over-limit and needs-review. Nothing decorative, no headings, no links, no brand accents are red. If a red element on the page does not point at overspending or at a transaction to fix, it is wrong.

**The Three Markers Rule.** State is green under 75%, amber from 75 to 100%, red over 100%, computed by one function and applied identically to bars, pace stroke and month cells. No fourth state colour, and no state colour used for anything but state.

**The Amber Never Writes Rule.** Amber is a fill and stroke colour only; it is too light to carry text on paper. Text that must signal state uses ink on a wash, or red/green.

## Typography

**Display Font:** Barlow Condensed, weights 500 and 700, embedded as the family "Planner" (fallback Arial Narrow, sans-serif)
**Body Font:** the system sans stack (-apple-system, BlinkMacSystemFont, Segoe UI, system-ui)
**Label/Mono Font:** ui-monospace stack, for fingerprints only

**Character:** a tall, condensed grotesk in caps for everything that reads like lettering on a planner (masthead, section heads, month names, chart labels, headline figures), paired with a neutral system sans for sentences and tables so long reading stays comfortable.

### Hierarchy
- **Display** (`typography.display`): currently unused; reserved for a single headline sentence.
- **Headline** (`typography.headline`, uppercase): the masthead title.
- **Title** (`typography.title`, uppercase): section headings, sitting on a 1.5px ink rule.
- **Figure** (`typography.figure`): headline numbers inside and under the pace chart (spent, budget, over / to spare).
- **Label** (`typography.label`, uppercase): month column heads, the TODAY label, chart end labels; axis values use the 500 weight at 0.04em in Pencil Grey.
- **Lead** (`typography.lead`): currently unused.
- **Body** (`typography.body`): ledes (Pencil Grey, max 75ch), list rows, summaries. Category names in rows are 600.
- **Small** (`typography.small`): column heads, sub-figures, keys, footer, month-cell amounts. Transaction tables run at 14px.
- **Mono** (`typography.mono`): fingerprints, select-all on click.

### Named Rules
**The Tabular Figures Rule.** `font-variant-numeric: tabular-nums` is set on the body and inherited everywhere. Amounts are right-aligned, Danish-formatted (1.234 / 1.234,50), and never wrap.

**The Lettering Rule.** The condensed face is for planner lettering: short caps labels, headings and headline figures. It never sets a sentence, and never sets table body text.

## Layout

A single column, max 1180px, centred, with 16px side padding and a 32px top margin. The masthead is a flex row (title left, window and last import right) closed by a 3px ink rule; the footer opens with the same rule, 72px below the last section. Sections are 64px apart, each opened by its title on a 1.5px ink rule and a Pencil Grey lede.

Tables are grids of rules rather than boxes. The ranked list is a six-column grid (name, bar track, % of limit, per-month budget, spent, limit and left) with 16px gaps and 11px row padding. The month grid is a fixed-layout table with a 196px name column and one column per window month, each separated by a 1px ink rule like planner columns; it keeps a 980px minimum width and scrolls horizontally inside its wrapper rather than squeezing.

**Responsive (max-width 760px):**
- Page top padding drops to 20px; sections to 48px apart; the lead to 17px.
- Ranked rows collapse: name, "… per month" in Pencil Grey and % of limit on the first line, the bar track full-width beneath; spent, limit and the column-head row are hidden.
- The pace chart keeps its drawing but hides all SVG text; a three-up figure row (Spent, Budget, Over / To spare) below the chart carries the numbers, with the over figure in red.
- The month grid's name column narrows to 136px and wraps; the grid still scrolls sideways.
- Transaction summaries drop the count to a second line; the fingerprint column is hidden and the table loses its indent.

## Elevation & Depth

Flat. Nothing floats. There are no cards, no panels and no elevation shadows; hierarchy comes from rule weight (3px page bounds, 1.5px section and total rules, 1px row hairlines), the alternating column shade, and the weight of the condensed caps. The one `box-shadow` in the build is an inset 3px red bar on the month-grid key swatch, which draws the over-share top edge in miniature; it is a stroke, not depth.

### Named Rules
**The Rules Not Boxes Rule.** Group things with ruled lines and columns. If a new element needs a border on all four sides, a fill behind a block, or a shadow to read as a group, it is outside this world.

## Shapes

Square by default. Rules and columns are straight lines. The only softening is marker-tip rounding: 2px on bar fills, month-cell ink and key swatches, and round 9px dots for notes. The limit tick is a hard 2px ink bar, square. Overspend is a -45 degree hatch (3px red, 3px red wash). The disclosure chevron is drawn from two 1.5px ink borders rotated, not a glyph.

## Components

### Notes list
Sits directly under the masthead, before the first section. Ruled list between hairlines (`rule`), each item led by a 9px round dot: amber for coverage and data notes, red only for the needs-review link.

### Section heading
Condensed caps title with 0.12em tracking on a 1.5px ink rule, followed by a Pencil Grey lede that says how to read the chart below.

### Pace chart (signature)
Server-rendered SVG, 1000 by 300 user units, full width. Month columns ruled in ink with alternate columns shaded, labelled in caps above the plot; light horizontal gridlines with short axis labels (500k, 1 mio.). The budget accrues as a straight dashed ink line (1.5px, 6/5 dash) ending in an open circle; cumulative spending is a 4px stepped marker stroke in the year's state colour ending in a filled dot. A 2.5px ink "today" edge closes the plot. At the right edge, a bracket and label in red (OVER) or green (TO SPARE) state the gap, with SPENT and BUDGET values beside their line ends. With motion allowed, the stroke draws in over 1.4s (cubic-bezier(.16, 1, .3, 1)) and the dot appears after.

### Limit bars (signature)
Each category measured against its own yearly limit, never against the total or the other categories: share of the total is deliberately not shown. Every track runs from 0 to 200% of that category's limit, so the limit sits at the same place on every row and is drawn as one continuous 2px ink line down the list, labelled LIMIT in the column head. Rows are sorted by % of limit, most over first. A dotted baseline marks the track; the fill is the state colour up to the limit, and spending beyond it continues past the line as the red hatch. Past 200% the hatch is cut off with a notched end. Right-hand columns give % of limit as a headline figure (red when over), the monthly budget (yearly limit / 12), spent, and limit (with left, or over in red). A total row sits on a 1.5px ink rule. A key below spells out every mark.

### Month grid (signature)
The planner itself: categories down, months across, each cell filled from the bottom with a marker wash against that month's prorated share of the yearly limit (partial first and last months get a partial share). Fill height caps at full; green, amber or red wash by state, and an over-share cell gets a 3px red top edge. The amount sits top-right in small text; empty months stay blank. Alternate rows carry the column shade. A total row closes the grid on a 1.5px ink rule.

### Disclosure rows
Native `details`/`summary` rows separated by hairlines: an ink chevron (rotates on open, 0.2s), category name in 600, count in Pencil Grey, amount right-aligned. Hover underlines the name; focus shows a 2px ink outline offset 3px. Inside, a transaction table with Pencil Grey column heads, dates in grey, Danish amounts right-aligned, and select-all fingerprints in mono. The needs-review table adds category and a red low-confidence value.

## Do's and Don'ts

### Do:
- **Do** map state through the one threshold function: green under 75%, amber 75 to 100%, red over 100%.
- **Do** keep red for over-limit and needs-review only.
- **Do** put ink text on a wash, never on a full-strength marker colour.
- **Do** separate and group with rules: 3px ink for page bounds, 1.5px ink for section heads and totals, 1px hairlines for rows.
- **Do** set headings, month names and chart labels in the embedded condensed face in caps, and prose and tables in the system sans with tabular figures.
- **Do** draw charts as server-rendered inline SVG or CSS from computed figures, with a text equivalent (SVG `desc`, ARIA labels, the mobile figure row).
- **Do** measure each category against its own limit, with the limit as one ink line at the same place on every row.
- **Do** let wide grids scroll horizontally below 760px instead of shrinking them, and swap chart labels for a figure row when the chart gets too small to label.
- **Do** gate motion behind `prefers-reduced-motion: no-preference`.

### Don't:
- **Don't** use cards, filled panels or elevation shadows.
- **Don't** use red, or its wash, for anything that is not overspending or a transaction needing review.
- **Don't** set text in amber.
- **Don't** add script, external URLs, remote fonts or linked images; the report is one self-contained file.
- **Don't** use KPI tiles or donut charts, and don't show a category's share of the total; what matters is whether it crossed its limit.
- **Don't** show invented or sample figures; every number is computed from the data.
