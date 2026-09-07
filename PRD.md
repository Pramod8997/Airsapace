# AirStat India --- Product Requirements Document (PRD)

**Smart India Hackathon 2026 --- Problem Statement 26056**\
**Product:** AirStat India --- Real-Time Airfare Price Index &
Intelligence Platform\
**Theme:** Smart Automation\
**Category:** Software\
**Organization:** MoSPI / Data Informatics & Innovation Division (DIID)\
**Document version:** 1.0\
**Status:** Build-ready SIH prototype specification

------------------------------------------------------------------------

## 1. Executive Summary

AirStat India is an end-to-end statistical data platform that collects
domestic airfare observations from airline and OTA sources, normalizes
and validates them, constructs a transparent Airfare Price Index (APIx),
and exposes the results through a web dashboard and machine-readable
API.

The product is designed around five principles:

1.  **Consumer-representative:** measure payable airfare rather than
    only advertised base fare.
2.  **Dynamic-price aware:** preserve booking lead time, timestamp,
    availability, route, airline and fare attributes.
3.  **Statistically reproducible:** every index value must be traceable
    to observations, weights and a methodology version.
4.  **Ethical automation:** source policies, robots.txt, terms of
    service, rate limits and CAPTCHA detection are first-class controls.
5.  **Government-ready:** provide data-quality metrics, methodology,
    historical data, exports and APIs.

> AirStat India is an analytical augmentation platform. It must not
> claim to replace the official CPI methodology unless formally adopted
> by the competent authority.

------------------------------------------------------------------------

# 2. Problem Definition

Traditional airfare price collection can struggle to represent the
highly dynamic online airfare market. The target system therefore needs
to automate observation of online fares across representative Indian
domestic city-pairs and advance-purchase windows, then convert
observations into a statistically meaningful high-frequency index.

The system must support:

-   Airline and OTA source adapters.
-   JavaScript-rendered pages where permitted.
-   Scheduled daily extraction.
-   T+1, T+7, T+15, T+30 and T+45 booking windows.
-   Raw and normalized fare components.
-   Missing, sold-out and outlier handling.
-   Route and source metadata.
-   Daily, weekly and monthly index views.
-   Route heatmaps.
-   Lead-time elasticity curves.
-   Public/API consumption.
-   At least 30 days of back-tested results against an available public
    DGCA reference series.

------------------------------------------------------------------------

# 3. Product Vision

> **Turn fragmented, dynamic online airfare observations into a
> transparent, reproducible and auditable high-frequency price
> intelligence layer for India.**

------------------------------------------------------------------------

# 4. Product Mission

Build a reliable statistical pipeline:

``` text
Observe → Validate → Normalize → Quality-score → Aggregate → Explain → Backtest → Publish
```

------------------------------------------------------------------------

# 5. Goals

## P0 Goals

-   Automate airfare data collection through modular source adapters.
-   Maintain a canonical airfare observation schema.
-   Store immutable raw observations and versioned processed
    observations.
-   Calculate APIx using documented route weights and a defined base
    period.
-   Provide daily/weekly/monthly views.
-   Support the five required booking lead-time windows.
-   Provide interactive dashboard and REST API.
-   Provide 30-day backtesting capability.
-   Provide full auditability and data-quality reporting.
-   Make the scraper resilient without depending on bypassing anti-bot
    controls.

## P1 Goals

-   Intraday collection.
-   Anomaly detection.
-   Source comparison.
-   Fare decomposition.
-   Natural-language analytical explanations.
-   Additional routes and sources.

## P2 / Future

-   Forecasting.
-   Automated methodology experiments.
-   Larger national route basket.
-   Statistical quality adjustment research.
-   Integration with official statistical workflows subject to
    authorization.

------------------------------------------------------------------------

# 6. Non-Goals

The SIH prototype will not:

-   Sell or book flight tickets.
-   Circumvent CAPTCHA, authentication or access controls.
-   Scrape sources in violation of their policies.
-   Represent scraped observations as official CPI values.
-   Use an LLM as the core index-calculation engine.
-   Guarantee that every airline/OTA remains scrapeable indefinitely.
-   Treat a sold-out flight as a zero price.

------------------------------------------------------------------------

# 7. Target Users

## 7.1 MoSPI / NSO Analyst

Needs:

-   Index trend.
-   Route contribution.
-   Data-quality status.
-   Methodology.
-   Historical series.
-   Export/API access.

## 7.2 RBI / Economic Analyst

Needs:

-   Airfare inflation.
-   MoM/YoY changes.
-   Route-level contribution.
-   Lead-time effects.
-   Shock detection.

## 7.3 Statistical Researcher

Needs:

-   Raw/clean observations.
-   Weights.
-   Calculation metadata.
-   Revision history.
-   Reproducibility.

## 7.4 System Administrator

Needs:

-   Scraper health.
-   Job history.
-   Source failures.
-   Data-quality alerts.
-   API/system health.

------------------------------------------------------------------------

# 8. Core User Journeys

## Journey A --- Analyst checks current airfare inflation

1.  Open dashboard.
2.  View current APIx.
3.  See daily/weekly/monthly changes.
4.  Open route contribution.
5.  Drill into route observations.
6.  Inspect lead-time effect.
7.  Download data.

## Journey B --- Analyst investigates a price shock

1.  Open Shock Monitor.
2.  Select route.
3.  See deviation from route baseline.
4.  Compare airlines/sources.
5.  Inspect lead-time and availability.
6.  Review evidence behind the anomaly.

## Journey C --- Researcher reproduces an index

1.  Select index date.
2.  Open methodology version.
3.  Open route basket/weight version.
4.  Retrieve contributing observations.
5.  Re-run calculation through the backtest/calculation endpoint.

## Journey D --- Administrator handles scraper failure

1.  Open Source Health.
2.  Identify failed source.
3.  View error class.
4.  Check robots/policy status.
5.  Pause source if required.
6.  Continue with other sources/fallback data.

------------------------------------------------------------------------

# 9. Functional Requirements

## FR-01 Source Registry

The system shall maintain:

-   source ID
-   source name
-   source type
-   source URL
-   adapter name/version
-   policy status
-   robots status
-   rate limit
-   active/inactive status
-   last successful run
-   last failed run

## FR-02 Route Registry

Each route shall contain:

-   route ID
-   origin IATA
-   destination IATA
-   city names
-   state/country
-   route weight
-   weight source
-   weight version
-   active status

## FR-03 Airline Registry

Store:

-   airline ID
-   IATA code
-   airline name
-   active status
-   source mapping

## FR-04 Search Configuration

A search configuration shall define:

-   origin
-   destination
-   departure date
-   advance-purchase window
-   airline/source
-   cabin
-   passenger count
-   trip type
-   nonstop/stops policy

Default prototype specification:

-   one-way
-   one adult
-   economy
-   representative nonstop service where available

## FR-05 Automated Collection

The scheduler shall create collection jobs for:

-   T+1
-   T+7
-   T+15
-   T+30
-   T+45

Every job shall have:

-   job ID
-   source
-   route
-   target date
-   lead time
-   start/end timestamp
-   result count
-   status
-   error classification

## FR-06 Raw Data Preservation

Raw source observations shall be stored or archived before
transformation, subject to source-policy and storage constraints.

Raw records shall include:

-   collection timestamp
-   source
-   request/search metadata
-   parser version
-   raw fare payload/reference
-   job ID

## FR-07 Canonical Fare Schema

Every normalized quote should contain:

-   origin
-   destination
-   departure date
-   departure time
-   airline
-   flight number where available
-   cabin
-   fare class where available
-   lead time
-   base fare
-   taxes
-   UDF/airport charges where identifiable
-   convenience fee
-   other mandatory fees
-   total payable fare
-   currency
-   stops
-   availability
-   source
-   timestamp
-   quality score

## FR-08 Cleaning

The pipeline shall:

-   validate schema
-   validate dates
-   validate fare relationships
-   detect duplicates
-   identify missing values
-   identify invalid prices
-   classify sold-out results
-   detect statistical anomalies
-   flag imputed observations
-   produce a clean dataset

## FR-09 Price Normalization

Primary comparison metric:

``` text
consumer_payable_fare =
base_fare
+ taxes
+ mandatory_fees
+ mandatory_charges
```

The individual components must remain separately stored.

## FR-10 Data Quality Score

Each observation shall receive a quality score based on:

-   completeness
-   consistency
-   source reliability
-   timestamp validity
-   duplication
-   field-level validity

The exact scoring model shall be versioned.

## FR-11 Index Construction

The system shall support a Laspeyres-style prototype index:

``` text
I_t = [ Σ(w_i × P_i,t / P_i,0) / Σw_i ] × 100
```

Where:

-   `w_i` = route/specification weight
-   `P_i,t` = current normalized price
-   `P_i,0` = base-period normalized price

The implementation shall be deterministic.

## FR-12 Lead-Time Indices

Calculate:

-   APIx-T1
-   APIx-T7
-   APIx-T15
-   APIx-T30
-   APIx-T45

And a documented combined index.

## FR-13 Aggregation

Support:

-   daily
-   weekly
-   monthly
-   route-level
-   lead-time-level
-   airline/source analytical breakdown

## FR-14 Backtesting

Support:

-   historical data replay
-   reference-series ingestion
-   APIx recomputation
-   MAE
-   RMSE
-   MAPE
-   correlation
-   trend-direction accuracy

The dashboard shall clearly distinguish correlation/validation from
methodological equivalence.

## FR-15 Dashboard

Required screens:

1.  Executive Overview
2.  Index Trends
3.  Route Heatmap
4.  Lead-Time Analytics
5.  Fare Decomposition
6.  Source/Airline Comparison
7.  Data Quality
8.  Source Health
9.  Backtesting
10. Methodology

## FR-16 API

Minimum endpoints:

``` text
GET /api/v1/index/latest
GET /api/v1/index/history
GET /api/v1/index/route/{route_id}
GET /api/v1/fares
GET /api/v1/routes
GET /api/v1/airlines
GET /api/v1/quality
GET /api/v1/sources
GET /api/v1/methodology
GET /api/v1/backtests
```

## FR-17 Export

Support:

-   CSV
-   JSON
-   XLSX

## FR-18 Auditability

Every index value must be traceable to:

-   calculation timestamp
-   methodology version
-   basket version
-   weight version
-   source observations
-   processing version

## FR-19 Source Resilience

The platform shall:

-   apply per-source rate limits
-   use exponential backoff
-   detect CAPTCHA
-   classify blocks
-   pause unsafe source jobs
-   support fallback sources
-   avoid bypassing access controls

## FR-20 Admin Controls

Admin can:

-   activate/deactivate source
-   activate/deactivate route
-   modify weights through versioned configuration
-   trigger/retry jobs
-   inspect failures
-   manage users/roles
-   publish/unpublish methodology versions

------------------------------------------------------------------------

# 10. Data Model

Core entities:

``` text
Source
Airport
Route
Airline
ScrapeJob
RawObservation
FareQuote
QualityAssessment
IndexBasket
IndexWeight
IndexValue
MethodologyVersion
BacktestRun
AuditLog
User
```

Relationship:

``` text
Source ──< ScrapeJob ──< RawObservation
Route ──< FareQuote >── Airline
FareQuote ──< QualityAssessment
IndexBasket ──< IndexWeight
IndexWeight + FareQuote ──> IndexValue
MethodologyVersion ──< IndexValue
BacktestRun ──< BacktestMetric
User ──< AuditLog
```

------------------------------------------------------------------------

# 11. Data Lifecycle

``` text
COLLECT
  ↓
RAW
  ↓
VALIDATE
  ↓
NORMALIZE
  ↓
DEDUPLICATE
  ↓
QUALITY SCORE
  ↓
CLEAN
  ↓
AGGREGATE
  ↓
INDEX
  ↓
ANALYTICS
  ↓
API / DASHBOARD / EXPORT
```

------------------------------------------------------------------------

# 12. Missing Data Policy

Never convert missing or sold-out observations to zero.

Classification:

``` text
AVAILABLE
SOLD_OUT
MISSING
INVALID
IMPUTED
REJECTED
```

Any imputation must be:

-   documented
-   flagged
-   reproducible
-   included in quality reporting

------------------------------------------------------------------------

# 13. Outlier Policy

A valid expensive flight is not automatically an invalid observation.

Use:

1.  Business-rule validation.
2.  Route/lead-time distribution checks.
3.  Robust statistics such as median/MAD.
4.  Source consistency checks.
5.  Manual review sample.

Store:

``` text
outlier_flag
outlier_reason
outlier_method_version
```

Do not silently delete observations.

------------------------------------------------------------------------

# 14. Route Basket

Initial SIH basket:

-   DEL-BOM
-   DEL-BLR
-   BOM-BLR
-   DEL-CCU
-   BLR-HYD
-   MAA-DEL
-   BOM-DEL
-   BLR-DEL
-   HYD-DEL
-   CCU-DEL

The production methodology should derive the final basket and weights
from authoritative passenger-traffic/reference data and preserve the
evidence/version used.

------------------------------------------------------------------------

# 15. Acceptance Criteria

The SIH prototype passes if:

-   [ ] At least 5 source/airline adapters are demonstrated or
    architecturally supported.
-   [ ] At least 10 representative routes are configured.
-   [ ] All five lead-time windows work.
-   [ ] Raw and normalized observations are stored.
-   [ ] Data cleaning is automated.
-   [ ] APIx is generated deterministically.
-   [ ] Dashboard exposes index and route trends.
-   [ ] Lead-time curve is visible.
-   [ ] Data quality is visible.
-   [ ] REST API works.
-   [ ] 30-day backtest workflow works.
-   [ ] MAE/RMSE/MAPE/correlation are calculated.
-   [ ] Methodology is documented.
-   [ ] Source failures do not destroy the dashboard.
-   [ ] Security controls are implemented.
-   [ ] Automated tests exist.

------------------------------------------------------------------------

# 16. Definition of Done

A feature is Done only when:

-   implementation exists
-   unit/integration tests exist
-   logging exists where applicable
-   API/schema is documented
-   UI state is handled
-   error states are handled
-   security implications are reviewed
-   `memory.md` is updated
-   `log.md` is updated

------------------------------------------------------------------------

# 17. SIH Demo Mode

The platform must support three modes:

``` text
LIVE
  ↓
Accessible live sources

DEMO
  ↓
Preloaded verified dataset

REPLAY
  ↓
Historical observation replay
```

The demo must not fail if a live source becomes unavailable.

------------------------------------------------------------------------

# 18. KPIs

### Collection

-   observations/day
-   collection success rate
-   source coverage
-   route coverage

### Quality

-   completeness
-   duplicate rate
-   rejection rate
-   imputation rate
-   outlier rate

### Statistics

-   MAE
-   RMSE
-   MAPE
-   correlation
-   trend-direction accuracy

### Platform

-   API p95 latency
-   scheduled-job success rate
-   scraper failure recovery time
-   dashboard load time

------------------------------------------------------------------------

# 19. Risks

  -----------------------------------------------------------------------
  Risk                    Severity                Mitigation
  ----------------------- ----------------------- -----------------------
  CAPTCHA/anti-bot        High                    Detection, rate limits,
                                                  source fallback

  Website changes         High                    Adapter interface +
                                                  contract tests

  Terms/robots            High                    Policy registry and
  restrictions                                    source controls

  Missing observations    Medium                  Explicit
                                                  missing/imputation
                                                  policy

  Statistical outliers    High                    Robust detection +
                                                  review

  Insufficient historical High                    Controlled replay
  data                                            dataset + public
                                                  reference data

  Demo source outage      High                    Demo/replay mode

  Methodology criticism   High                    Transparent versioned
                                                  methodology

  Data leakage            High                    Access control,
                                                  encryption, secret
                                                  management

  Index reproducibility   High                    Immutable versions and
  failure                                         deterministic
                                                  calculations
  -----------------------------------------------------------------------

------------------------------------------------------------------------

# 20. SIH Deliverables

1.  Working web application.
2.  Source adapter framework.
3.  Clean airfare database.
4.  APIx calculation engine.
5.  Interactive dashboard.
6.  REST API.
7.  30-day backtest.
8.  Automated tests.
9.  Documentation.
10. Security controls.
11. UI/UX specification.
12. TRD.
13. `memory.md`.
14. `log.md`.
15. Demo dataset and replay mode.
16. SIH presentation/demo narrative.

------------------------------------------------------------------------

# 21. Future Extensions

-   More routes.
-   More sources.
-   Intraday index.
-   Forecasting.
-   Shock detection.
-   Event/holiday effects.
-   Advanced quality adjustment.
-   Statistical experimental frameworks.
-   Official-system integration subject to authorization.
