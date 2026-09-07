# AirStat India --- UI/UX Design Specification

**Design direction:** "Airspace Observatory"\
**Goal:** Create a unique government-grade analytical interface that
feels like a mission-control system for India's airfare economy---not
another travel booking dashboard.

------------------------------------------------------------------------

# 1. Design Concept

## Airspace Observatory

The interface should visually communicate:

``` text
AIR ROUTES
+
ECONOMIC SIGNALS
+
LIVE DATA
+
STATISTICAL CONFIDENCE
```

Instead of a conventional dashboard made from cards and generic charts,
AirStat India uses:

-   a geographic route canvas
-   a persistent "Index Pulse"
-   a vertical time rail
-   evidence drawers
-   confidence halos
-   route-flow visualizations
-   statistical story cards

The UI should feel analytical, calm and trustworthy.

------------------------------------------------------------------------

# 2. Visual Identity

## Primary visual metaphor

Think:

> "Air Traffic Control meets Economic Observatory."

Avoid:

-   airline-booking UI
-   excessive gradients
-   generic admin panels
-   dense spreadsheet-only layouts
-   fake "AI" visual effects

------------------------------------------------------------------------

# 3. Layout System

Desktop:

``` text
┌──────────────────────────────────────────────────────────────┐
│ AIRSTAT INDIA          INDEX PULSE 127.42     ● LIVE 08:42  │
├───────────┬──────────────────────────────────────────────────┤
│           │                                                  │
│ NAV       │              ROUTE OBSERVATORY                  │
│           │                                                  │
│ Overview  │      India route network / index signals        │
│ Index     │                                                  │
│ Routes    │                                                  │
│ Lead Time │                                                  │
│ Sources   │                                                  │
│ Quality   │                                                  │
│ Backtest  │                                                  │
│ Method    │                                                  │
│           │                                                  │
├───────────┴──────────────────────────────────────────────────┤
│ Evidence / data-quality / methodology strip                  │
└──────────────────────────────────────────────────────────────┘
```

------------------------------------------------------------------------

# 4. Unique Navigation

Use a **rail + command palette** rather than a normal top navigation.

Keyboard shortcut:

``` text
/
```

opens:

``` text
Search routes
Search airlines
Open index
Open backtest
Open methodology
```

------------------------------------------------------------------------

# 5. Global Header

Header contains:

### Left

`AIRSTAT / INDIA`

### Center

Current index pulse:

``` text
APIx 127.42
+4.8% MoM
```

### Right

``` text
● Data current
Last collection 08:42
```

Do not use flashing animations.

------------------------------------------------------------------------

# 6. Color System

Use a restrained statistical palette.

Suggested tokens:

``` text
--ink
--paper
--surface
--muted
--grid
--signal
--warning
--critical
--positive
```

Use color primarily for:

-   increase/decrease
-   warning
-   source health
-   confidence
-   anomaly

The default UI should remain mostly neutral.

------------------------------------------------------------------------

# 7. Typography

Use a modern readable sans-serif.

Suggested:

``` text
Inter
```

Use:

-   large numerical typography for APIx
-   compact labels
-   generous line height
-   tabular numerals for financial/statistical values

Example:

``` text
127.42
```

should use tabular numerals so values align in tables.

------------------------------------------------------------------------

# 8. Home / Overview

Hero section:

``` text
AIRFARE PRICE INDEX

127.42

+4.8% vs previous month
+11.2% vs base-year comparison

2,845 observations
10 routes
5 lead-time windows
```

Below:

``` text
┌─────────────────────────────┐
│ INDEX PULSE                 │
│ 30-day trend                │
└─────────────────────────────┘

┌─────────────────────────────┐
│ ROUTE PRESSURE              │
│ Top 5 increasing routes     │
└─────────────────────────────┘

┌─────────────────────────────┐
│ DATA CONFIDENCE             │
│ 98.1% usable observations   │
└─────────────────────────────┘
```

------------------------------------------------------------------------

# 9. Route Observatory

This is the signature screen.

Display a stylized India map.

Routes are represented as thin arcs between airports.

Each route has:

-   current index
-   percentage movement
-   confidence
-   observation count

Clicking a route opens a right-side evidence drawer.

------------------------------------------------------------------------

# 10. Route Evidence Drawer

Example:

``` text
DEL → BOM

APIx
124.8

+7.2% / 7D

LEAD TIME
T+45   ₹4,120
T+30   ₹4,450
T+15   ₹5,180
T+7    ₹6,020
T+1    ₹8,150

CONFIDENCE
██████████ 93%

EVIDENCE
4/5 sources agree
```

The user should be able to drill from index → route → quote.

------------------------------------------------------------------------

# 11. Index Trend Screen

Main chart:

``` text
140 ┤                         ╭──
130 ┤               ╭─────────╯
120 ┤      ╭────────╯
110 ┤──────╯
100 ┤
    └────────────────────────────
```

Interactions:

-   hover
-   date brush
-   route filter
-   source filter
-   lead-time filter

Do not overload one chart with every dimension.

------------------------------------------------------------------------

# 12. Lead-Time Screen

The core visual:

``` text
₹
│                         ● T+1
│
│                  ● T+7
│
│            ● T+15
│
│      ● T+30
│
│ ● T+45
└────────────────────────────
  45  30  15   7   1
       Days to departure
```

Add:

``` text
Lead-time premium:
T+1 vs T+45 = +97%
```

This is one of the most distinctive analytical screens.

------------------------------------------------------------------------

# 13. Route Heatmap

Use an airport matrix.

Cells contain:

``` text
124.3
+6.4%
```

Hover shows:

-   route
-   current index
-   observation count
-   confidence
-   lead-time driver

------------------------------------------------------------------------

# 14. Price Decomposition

Use a stacked visual:

``` text
TOTAL ₹6,450

BASE FARE
₹5,100

TAXES
₹920

MANDATORY FEES
₹180

CONVENIENCE
₹250
```

Allow toggle:

``` text
₹
%
```

------------------------------------------------------------------------

# 15. Source Comparison

Do not show source logos as the main visual.

Instead:

``` text
SOURCE CONSENSUS

DEL → BOM

████████  Airline
███████   OTA
████████  Airline
██████    OTA
```

Then:

``` text
Median spread: ₹180
Cross-source agreement: 87%
```

------------------------------------------------------------------------

# 16. Data Quality Screen

Create a "quality cockpit".

``` text
DATA HEALTH

98.1% usable
2,845 observations

Completeness     ██████████ 98%
Duplicates       ██         1.2%
Rejected         █          3.4%
Imputed          █          1.8%
```

Below:

``` text
SOURCE HEALTH
● IndiGo       Healthy
● Air India    Healthy
● Source X     Degraded
○ Source Y     Paused
```

------------------------------------------------------------------------

# 17. Backtesting Screen

Split screen:

``` text
AIRSTAT INDEX          REFERENCE SERIES
     ╭───╮                    ╭───╮
─────╯   ╰────             ───╯   ╰──

MAPE       2.3%
RMSE       2.7
Correlation 0.94
```

Add a methodology disclaimer:

> Comparison indicates statistical consistency with the selected
> reference series; it does not imply methodological equivalence.

------------------------------------------------------------------------

# 18. Methodology Screen

Make this unusually good.

Use an "index recipe":

``` text
01 OBSERVE
02 STANDARDIZE
03 CLEAN
04 WEIGHT
05 AGGREGATE
06 VALIDATE
```

Clicking each stage opens:

-   rules
-   formula
-   version
-   example

------------------------------------------------------------------------

# 19. Confidence Visualization

Every analytical result should have an optional confidence indicator:

``` text
Confidence 93%
█████████░
```

Do not imply formal statistical confidence intervals unless they have
actually been calculated.

Call it:

> **Data Confidence Score**

not:

> Confidence Interval.

------------------------------------------------------------------------

# 20. Anomaly Screen

Signature visual:

``` text
PRICE SHOCK DETECTED

DEL → BOM

₹11,800
+96% vs 30-day route median

WHY?

T+1 booking window
Reduced availability
4/5 source confirmation
```

The explanation must be evidence-based.

------------------------------------------------------------------------

# 21. Empty States

Never show blank charts.

Example:

``` text
NO VALID OBSERVATIONS

The selected route has no usable
T+30 observations for this period.

Try:
• another lead time
• another date
• replay mode
```

------------------------------------------------------------------------

# 22. Error States

Example:

``` text
SOURCE TEMPORARILY UNAVAILABLE

The source adapter is paused after
a policy/access failure.

Last valid observation:
08:12 IST

Other sources remain active.
```

Avoid technical stack traces in user-facing UI.

------------------------------------------------------------------------

# 23. Responsive Design

Desktop-first because primary users are analysts.

Tablet:

-   collapsible rail
-   2-column cards

Mobile:

-   summary first
-   route drawer becomes bottom sheet
-   charts become scrollable
-   tables become cards

------------------------------------------------------------------------

# 24. Accessibility

Target WCAG 2.1 AA where practical.

Requirements:

-   keyboard navigation
-   visible focus
-   semantic HTML
-   accessible chart summaries
-   non-color-only status
-   readable contrast
-   reduced-motion preference

------------------------------------------------------------------------

# 25. Micro-interactions

Use subtle transitions:

-   route hover
-   chart crosshair
-   drawer transition
-   status changes

Avoid:

-   bouncing cards
-   flashing alerts
-   excessive particle effects
-   decorative animations that obscure data

------------------------------------------------------------------------

# 26. Design System Components

Build reusable:

``` text
IndexPulse
MetricTile
RouteNode
RouteArc
EvidenceDrawer
ConfidenceBar
TrendChart
LeadTimeCurve
SourceStatus
QualityMeter
MethodologyStep
DataTable
FilterBar
DateRangePicker
CommandPalette
Toast
EmptyState
ErrorState
```

------------------------------------------------------------------------

# 27. Design Principle

The interface should answer three questions immediately:

1.  **What is airfare inflation doing?**
2.  **Where is it changing?**
3.  **Why should I trust this number?**

That third question is the main differentiator from consumer travel
websites.

------------------------------------------------------------------------

# 28. UI Success Criteria

-   A first-time analyst understands the current APIx within 10 seconds.
-   A route can be investigated in under 3 clicks.
-   A price shock can be traced to evidence.
-   Data quality is visible without opening an admin panel.
-   Methodology is accessible from every index screen.
