# Source Compliance Research — AirStat India (SIH 26056)

**Date:** 2026-09-09 · **Status:** Frozen (decisions below are the current source-policy behavior)

This document records the compliance research behind every candidate fare/price data source
for the AirStat India APIx platform, and the collection policy we operate under. It exists so
that "why don't we just scrape X?" has a written, evidence-based answer.

---

## 1. Collection policy statement

1. **robots.txt and ToS first.** Before any fetch, the target's robots.txt is parsed and
   honored; terms of service are read and honored. A disallow or a ToS prohibition means we
   do not collect, full stop.
2. **Detection is never bypassed.** No CAPTCHA solving, no headless-browser stealth
   evasion, no JavaScript-obfuscation workarounds.
3. **No IP rotation.** We never rotate proxies/IPs/infra to evade a block or rate limit.
   Restriction signals (CAPTCHA, HTTP 403/429, robots disallow) raise a
   `SourcePolicyError` and the source is paused — never worked around.
4. **Bounded, polite collection.** Declared user agent, per-source rate limits,
   timeouts, bounded retries, politeness delays between requests.
5. **Data-provenance honesty.** Every source is labeled with a `policy_status`
   (`SYNTHETIC_DATA`, `SIMULATED`, `DEMO_SCRAPING_COMPLIANT`, `PUBLISHED_TARIFF_PDF`,
   `ROBOTS_ALLOWED_SEO`) so synthetic/simulated data is never presented as observed fares.

---

## 2. Source decision matrix

Decision values:
- **BUILT** — adapter implemented and active in this repository.
- **COMPLIANT-AVAILABLE** — collection is permitted (robots + ToS clean); adapter not yet prioritized.
- **RESTRICTED-DOCUMENTED** — robots.txt and/or ToS prohibit collection; documented, not collected.
- **REJECTED** — rejected on compliance or data-quality grounds; will not be collected.

| Source | robots.txt verdict | ToS verdict | Anti-bot stack | Decision | What we use it for |
|---|---|---|---|---|---|
| IndiGo | Not evaluated in detail; search/booking paths not open | ToS restricts automated access | Akamai CDN / bot manager | RESTRICTED-DOCUMENTED | Nothing (candidate only) |
| Air India | Permissive robots (no blocking of fare paths) | ToS prohibits automated scraping/data extraction | WAF + bot detection | RESTRICTED-DOCUMENTED | Nothing (robots-permissive but ToS prohibits — ToS wins) |
| Air India Express | Not open for fare search | ToS restricts automated access | Bot management | RESTRICTED-DOCUMENTED | Nothing (candidate only) |
| Akasa Air | **Zero `Disallow` lines**; fare-sheet PDF at plain HTTP 200 storyblok URL | Published fare sheet is public document, no anti-bot clause | None | **BUILT** | Published tariff PDF → `akasa-tariff` source (`PUBLISHED_TARIFF_PDF`) |
| SpiceJet | Search/booking paths not open | ToS restricts automated access | PerimeterX/bot manager | RESTRICTED-DOCUMENTED | Nothing (candidate only) |
| Alliance Air | robots.txt has no relevant disallow for published tariff PDFs; PDF is a public filed document | Public tariff document | None | **BUILT** | Published tariff PDF (15MAR23) → `alliance-tariff` source (`PUBLISHED_TARIFF_PDF`) |
| MakeMyTrip | **`Disallow: /flight/search*`** — fare search explicitly disallowed | ToS prohibits scraping | Akamai + device fingerprinting | REJECTED | Nothing — robots.txt disallow is decisive |
| Goibibo | Fare-search paths disallowed (MMT-family rules) | ToS prohibits scraping | Same family anti-bot as MMT | REJECTED | Nothing |
| Yatra | **`User-agent: * / Allow: /`** — explicitly allows all crawling; SEO route pages are sitemap-published | No anti-bot clause found | Light (server-rendered pages) | **BUILT** | SEO route pages (server-rendered cheapest-fare strip) → `yatra-ota` source (`ROBOTS_ALLOWED_SEO`) |
| EaseMyTrip | Fare-search/booking paths not permitted to bots | ToS restricts automated access | Bot management | RESTRICTED-DOCUMENTED | Nothing (candidate only) |
| Cleartrip | Fare-search paths disallowed | ToS prohibits scraping | Bot detection | REJECTED | Nothing |
| Ixigo | robots not blocking general pages, but | **ToS bans bots/automated access outright** | Aggregation + bot defense | REJECTED | Nothing — ToS bot ban is decisive |
| Amadeus (GDS API) | N/A — official API | API terms permit paid production use with credentials | N/A (auth-gated API) | COMPLIANT-AVAILABLE | Nothing yet (needs API key/budget; would be the strongest permitted source) |
| Travelpayouts (affiliate API) | N/A — official API | API terms permit use with affiliate credentials | N/A (auth-gated API) | COMPLIANT-AVAILABLE | Nothing yet (needs affiliate account) |
| MoSPI CPI | N/A — official open data API (eSankhyiki) | Public open-data API | N/A | **BUILT** | CPI "Airfare" sub-index (2024=100, item 294) as the official backtest reference series |
| DGCA datasets | N/A — public datasets (S3-hosted city-pair traffic data) | Public data | N/A | **BUILT** | City-pair passenger data → route weights (`WB-2026.09-DGCA`) |

Notes on verdicts:

- **Air India**: its robots.txt is permissive, but the terms of service prohibit automated
  data extraction. Our policy is robots *and* ToS must both permit — so ToS wins and the
  source is restricted.
- **Ixigo**: the ToS bot ban applies regardless of robots.txt generosity.
- **MakeMyTrip** `Disallow: /flight/search*` is a direct, unambiguous robots.txt
  prohibition of exactly the paths we would need; combined with Akamai anti-bot, the source
  is rejected rather than "worked around".

## 3. The DGCA fare-data finding

A key result of this research (frozen 2026-09-09, `memory.md` §9):

> **Route-wise monthly average fares were never published by DGCA.** The problem statement's
> expectation of "publicly available DGCA monthly average-fare data" does not exist as a
> public dataset.

What exists instead:

- **MoSPI CPI "Airfare" sub-index** (2024=100, All India, Combined, item code 294 /
  COICOP 07.3.3.1.2.01) — the official anchor. This is the exact CPI component that APIx
  augments, so it is used as the backtest reference series (via the eSankhyiki API).
- **DGCA domestic city-pair traffic data** (monthly, public S3) — provides *weights*:
  each basket route's share of directional passengers (see `WB-2026.09-DGCA`,
  `scripts/load_dgca_weights.py`). Passengers, not prices.

We never claim the CPI airfare sub-index and APIx are methodologically equivalent — the
backtest reports co-movement (correlation, trend-direction) only.

## 4. Compliance verification in code

- `collectors/sources/scrape_engine.py` — `RobotPolicy` gates every fetch against
  robots.txt (cached per host; unreachable/5xx → treated as fully disallowed, RFC 9309
  fail-closed); CAPTCHA/403/429 raise `SourcePolicyError` and pause the source.
- `backend/app/models.py` — every `Source` row carries `policy_status` + `robots_status`,
  surfaced through the `/api/v1/sources` endpoint and rendered as badges on the dashboard
  Sources screen.
