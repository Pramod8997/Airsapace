# AirStat India --- Technical Requirements Document (TRD)

**Version:** 1.0\
**Purpose:** Technical blueprint for implementing the SIH 2026
prototype.

------------------------------------------------------------------------

# 1. Technical Objective

Build a modular, secure and reproducible data platform that can:

``` text
collect → store → validate → normalize → calculate → visualize → expose
```

airfare observations and index values.

The architecture must allow additional airline/OTA adapters without
modifying the statistical engine.

------------------------------------------------------------------------

# 2. Technology Stack

## 2.1 Backend

  Component         Technology
  ----------------- ---------------
  Language          Python 3.12+
  API               FastAPI
  Validation        Pydantic
  ORM               SQLAlchemy
  Migrations        Alembic
  Testing           Pytest
  HTTP client       httpx
  Data processing   Pandas, NumPy

## 2.2 Collection

  Need                                    Technology
  --------------------------------------- ----------------
  Browser automation                      Playwright
  Static/API-style collection             httpx
  Structured crawling where appropriate   Scrapy
  Scheduling MVP                          APScheduler
  Production workers                      Celery + Redis

## 2.3 Database

  Component              Technology
  ---------------------- -----------------------------------------
  Primary DB             PostgreSQL
  Cache/queue            Redis
  Raw artifact storage   Object storage / filesystem abstraction

## 2.4 Frontend

  Component     Technology
  ------------- -----------------
  Framework     React
  Language      TypeScript
  Build         Vite
  Styling       Tailwind CSS
  Charts        Apache ECharts
  State/query   TanStack Query
  Forms         React Hook Form
  Routing       React Router

## 2.5 DevOps

  Component             Technology
  --------------------- ----------------------
  Containers            Docker
  Local orchestration   Docker Compose
  Reverse proxy         Nginx
  CI                    GitHub Actions
  API documentation     OpenAPI/Swagger
  Logging               Structured JSON logs

## 2.6 Analytics

-   NumPy
-   Pandas
-   SciPy where needed
-   scikit-learn for anomaly detection/optional ML

> Source note: the supplied PPTX contains headings for "METHODOLOGIES /
> ARCHITECTURE / TECH STACK" but does not populate a concrete technology
> stack. Therefore this TRD explicitly defines the recommended
> implementation stack rather than claiming it came from the PPTX. The
> supplied PPTX shows those headings on its Technical Approach slide.
> fileciteturn0file0L88-L108

------------------------------------------------------------------------

# 3. Architecture

``` text
                        ┌──────────────────────┐
                        │ Airline / OTA Source │
                        └──────────┬───────────┘
                                   ↓
                        ┌──────────────────────┐
                        │ Source Adapter Layer │
                        │ Playwright / HTTP    │
                        └──────────┬───────────┘
                                   ↓
                        ┌──────────────────────┐
                        │ Collection Scheduler │
                        └──────────┬───────────┘
                                   ↓
                        ┌──────────────────────┐
                        │ Raw Observation Store│
                        └──────────┬───────────┘
                                   ↓
                        ┌──────────────────────┐
                        │ Validation Pipeline  │
                        └──────────┬───────────┘
                                   ↓
                        ┌──────────────────────┐
                        │ Normalization Engine │
                        └──────────┬───────────┘
                                   ↓
                        ┌──────────────────────┐
                        │ Quality Engine       │
                        └──────────┬───────────┘
                                   ↓
                        ┌──────────────────────┐
                        │ Statistical Engine   │
                        └──────────┬───────────┘
                                   ↓
                    ┌──────────────┼──────────────┐
                    ↓              ↓              ↓
                Dashboard         API          Exports
```

------------------------------------------------------------------------

# 4. Repository Architecture

``` text
airstat-india/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── api/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── repositories/
│   │   ├── services/
│   │   ├── db/
│   │   └── middleware/
│   └── tests/
│
├── collectors/
│   ├── core/
│   │   ├── base_source.py
│   │   ├── models.py
│   │   ├── rate_limiter.py
│   │   ├── policy.py
│   │   └── runner.py
│   ├── airline/
│   ├── ota/
│   └── fixtures/
│
├── statistical_engine/
│   ├── basket.py
│   ├── weights.py
│   ├── normalization.py
│   ├── outliers.py
│   ├── aggregation.py
│   ├── index.py
│   └── backtest.py
│
├── frontend/
│   └── src/
│       ├── pages/
│       ├── components/
│       ├── charts/
│       ├── api/
│       ├── hooks/
│       └── types/
│
├── scripts/
├── docs/
├── data/
│   ├── fixtures/
│   └── reference/
├── docker-compose.yml
└── README.md
```

------------------------------------------------------------------------

# 5. Source Adapter Contract

Every source must implement the same conceptual interface:

``` python
class FlightSource:
    source_id: str

    async def search(self, query: FlightSearchQuery) -> list[FlightQuote]:
        ...

    async def health_check(self) -> SourceHealth:
        ...
```

The adapter must not calculate the index.

Responsibilities:

-   source interaction
-   parsing
-   canonical mapping
-   source-specific errors

Non-responsibilities:

-   route weighting
-   index calculation
-   statistical outlier deletion

------------------------------------------------------------------------

# 6. Canonical Data Contract

``` json
{
  "source_id": "example",
  "origin": "DEL",
  "destination": "BOM",
  "departure_date": "2026-10-07",
  "departure_time": "18:20",
  "airline": "XX",
  "flight_number": "XX123",
  "cabin": "economy",
  "fare_class": "Y",
  "advance_days": 30,
  "base_fare": 4200,
  "taxes": 756,
  "mandatory_fees": 100,
  "convenience_fee": 0,
  "other_fee": 0,
  "total_fare": 5056,
  "currency": "INR",
  "availability": "AVAILABLE",
  "stops": 0,
  "collected_at": "2026-09-07T08:00:00+05:30"
}
```

------------------------------------------------------------------------

# 7. Database Requirements

PostgreSQL must support:

-   relational integrity
-   timestamped records
-   indexes for route/date/source queries
-   versioned methodology
-   audit records
-   unique constraints where appropriate

Recommended indexes:

``` text
fare_quotes(origin, destination, departure_date)
fare_quotes(collected_at)
fare_quotes(source_id)
fare_quotes(advance_days)
index_values(index_date)
index_values(route_id, index_date)
scrape_jobs(status, started_at)
```

------------------------------------------------------------------------

# 8. API Requirements

## GET /api/v1/index/latest

Returns:

``` json
{
  "index": 127.42,
  "base": 100,
  "daily_change_pct": 1.2,
  "weekly_change_pct": 3.7,
  "monthly_change_pct": 4.8,
  "methodology_version": "APIX-v1.0"
}
```

## GET /api/v1/index/history

Query parameters:

``` text
from
to
frequency
route_id
lead_time
```

## GET /api/v1/fares

Query:

``` text
origin
destination
date
source
airline
lead_time
availability
```

## GET /api/v1/quality

Return:

-   observation count
-   completeness
-   duplicate rate
-   rejection rate
-   imputation rate
-   source health

## GET /api/v1/methodology

Return:

-   current methodology version
-   base period
-   basket
-   weight version
-   outlier policy
-   missing-data policy

------------------------------------------------------------------------

# 9. Index Engine

## 9.1 Base period

Prototype base:

``` text
First approved 30-day observation period
Index = 100
```

The base must be configurable.

## 9.2 Formula

``` text
I_t = [ Σ(w_i × P_i,t / P_i,0) / Σw_i ] × 100
```

## 9.3 Determinism

Same:

``` text
input snapshot
+
methodology version
+
weights
```

must produce the same result.

## 9.4 Versioning

Every calculated index must store:

``` text
methodology_version
basket_version
weight_version
calculation_run_id
```

------------------------------------------------------------------------

# 10. Backtesting Engine

Inputs:

-   historical airfare dataset
-   reference series
-   selected dates
-   basket version
-   methodology version

Outputs:

``` text
MAE
RMSE
MAPE
Correlation
Trend-direction accuracy
```

Example result:

``` json
{
  "period": "2026-01-01/2026-01-30",
  "mae": 2.1,
  "rmse": 2.7,
  "mape": 2.3,
  "correlation": 0.94
}
```

------------------------------------------------------------------------

# 11. Scheduler

MVP:

``` text
APScheduler
```

Production evolution:

``` text
APScheduler
   ↓
Celery
   ↓
Redis broker
   ↓
Workers
```

Jobs should be idempotent.

Job key:

``` text
source + route + departure_date + lead_time + collection_date
```

------------------------------------------------------------------------

# 12. Collection Resilience

Required controls:

-   per-source rate limiting
-   randomized but bounded scheduling where policy permits
-   exponential backoff
-   timeout
-   circuit breaker
-   retry budget
-   source health state
-   CAPTCHA detection
-   explicit failure classification

Failure states:

``` text
TIMEOUT
BLOCKED
CAPTCHA
ROBOTS_DENIED
PARSER_ERROR
SCHEMA_ERROR
SOURCE_DOWN
UNKNOWN
```

No control should be implemented to bypass a CAPTCHA or access
restriction.

------------------------------------------------------------------------

# 13. Frontend Requirements

Pages:

``` text
/overview
/index
/routes
/lead-time
/fare-decomposition
/sources
/quality
/backtesting
/methodology
/admin
```

Frontend must:

-   show loading states
-   show empty states
-   show stale-data warnings
-   show error states
-   be keyboard navigable
-   be responsive
-   support desktop-first analyst workflow

------------------------------------------------------------------------

# 14. Performance Requirements

Targets for prototype:

-   API p95 under 500 ms for common indexed queries.
-   Dashboard initial meaningful render under 3 seconds on normal
    broadband.
-   Collection jobs must have configurable timeouts.
-   Database queries must use appropriate indexes.
-   Large tables must use pagination.

------------------------------------------------------------------------

# 15. Testing

## Unit

-   normalization
-   fare arithmetic
-   index formula
-   weight validation
-   outlier logic
-   quality score

## Integration

``` text
collector → parser → DB
DB → cleaning → index
API → DB
```

## End-to-End

``` text
scheduled job
→ observation
→ processing
→ index
→ dashboard
```

## Security

-   authentication tests
-   authorization tests
-   input validation
-   injection tests
-   rate-limit tests
-   secret scanning

------------------------------------------------------------------------

# 16. Deployment

Prototype:

``` text
Docker Compose
├── frontend
├── backend
├── postgres
└── redis
```

Production-oriented:

``` text
Reverse Proxy
      ↓
Frontend/CDN
      ↓
API
      ↓
Workers
      ↓
PostgreSQL
Redis
Object Storage
Monitoring
```

------------------------------------------------------------------------

# 17. Environment Variables

Example:

``` text
APP_ENV
DATABASE_URL
REDIS_URL
JWT_SECRET
JWT_EXPIRY
CORS_ORIGINS
LOG_LEVEL
RAW_STORAGE_PATH
API_RATE_LIMIT
```

Never commit real secrets.

------------------------------------------------------------------------

# 18. Observability

Every important event should have:

``` text
timestamp
request/job ID
source
route
status
duration
error class
```

Use JSON logs.

------------------------------------------------------------------------

# 19. Technical Trade-offs

### Playwright vs Selenium

Choose Playwright for modern JS-heavy collection because of its browser
automation ergonomics and explicit waiting/network controls.

### APScheduler vs Celery

Choose APScheduler for SIH MVP simplicity. Move to Celery + Redis if
collection volume requires distributed workers.

### PostgreSQL vs NoSQL

Choose PostgreSQL because the core data is relational, analytical
metadata needs referential integrity, and index/audit/version
relationships benefit from SQL.

### React vs server-rendered UI

Choose React because the dashboard is highly interactive and
chart-heavy.

------------------------------------------------------------------------

# 20. Technical Definition of Done

-   Docker setup works from clean checkout.
-   Database migrations work.
-   Backend tests pass.
-   Frontend builds without errors.
-   At least one source adapter works in a controlled test.
-   Replay dataset can produce APIx.
-   API returns documented schemas.
-   Dashboard consumes the API.
-   Security checks pass.
-   Documentation is updated.
-   `memory.md` and `log.md` are updated.
