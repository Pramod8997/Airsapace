# AirStat India --- Security Requirements

**Version:** 1.0\
**Scope:** Web application, API, collectors, database, dashboard, CI/CD
and operational data.

------------------------------------------------------------------------

# 1. Security Objective

Protect:

-   application availability
-   source credentials/configuration
-   user accounts
-   administrative functions
-   database integrity
-   raw/processed datasets
-   API endpoints
-   audit logs
-   methodology/index integrity

The system must also protect the integrity of the statistical pipeline.

------------------------------------------------------------------------

# 2. Security Principles

1.  Least privilege.
2.  Secure by default.
3.  Defense in depth.
4.  Never trust client input.
5.  Secrets never enter source control.
6.  Immutable/auditable statistical results.
7.  Separate collection permissions from administration.
8.  Fail safely when a source becomes unsafe.
9.  Do not bypass source security controls.

------------------------------------------------------------------------

# 3. Threat Model

## T1 --- Unauthorized API access

Mitigation:

-   authentication
-   authorization
-   rate limits
-   token expiration
-   audit logs

## T2 --- Admin privilege escalation

Mitigation:

-   RBAC
-   server-side authorization
-   separate admin endpoints
-   audit all configuration changes

## T3 --- SQL injection

Mitigation:

-   SQLAlchemy parameterization
-   Pydantic validation
-   no string-built SQL from user input

## T4 --- XSS

Mitigation:

-   React escaping
-   sanitize any rendered rich text
-   strict Content Security Policy

## T5 --- CSRF

For cookie-authenticated workflows:

-   SameSite cookies
-   CSRF token where required
-   origin validation

For bearer-token APIs:

-   avoid storing long-lived tokens in insecure browser storage

## T6 --- Credential leakage

Mitigation:

-   environment variables
-   secret manager in production
-   Git secret scanning
-   `.env` ignored

## T7 --- Scraper abuse

Mitigation:

-   source-specific rate limit
-   circuit breaker
-   job budgets
-   robots/policy gate
-   CAPTCHA detection
-   no access-control bypass

## T8 --- Data poisoning

Mitigation:

-   schema validation
-   source identity
-   range checks
-   anomaly checks
-   provenance
-   quality score

## T9 --- Index manipulation

Mitigation:

-   immutable calculation inputs
-   methodology versioning
-   weight versioning
-   signed/audited releases where feasible
-   restricted publication permissions

## T10 --- Denial of service

Mitigation:

-   API rate limits
-   reverse proxy
-   request size limits
-   pagination
-   database query limits
-   worker concurrency limits

------------------------------------------------------------------------

# 4. Authentication

Use:

-   short-lived access tokens
-   refresh token rotation where refresh tokens are implemented
-   strong password hashing (Argon2id preferred)
-   optional MFA for admin users

Do not store plaintext passwords.

------------------------------------------------------------------------

# 5. Authorization

Roles:

``` text
VIEWER
ANALYST
OPERATOR
ADMIN
```

Example:

  Action                    Viewer   Analyst   Operator   Admin
  ----------------------- -------- --------- ---------- -------
  View dashboard                 ✓         ✓          ✓       ✓
  Export data                              ✓          ✓       ✓
  View raw observations                    ✓          ✓       ✓
  Retry scraper                                       ✓       ✓
  Change source policy                                        ✓
  Change weights                                              ✓
  Publish methodology                                         ✓
  Manage users                                                ✓

Authorization must always be enforced server-side.

------------------------------------------------------------------------

# 6. Password Policy

If local authentication is used:

-   minimum 12 characters
-   Argon2id
-   password reset tokens expire
-   rate-limit login attempts
-   account lockout/risk-based throttling after repeated failures

------------------------------------------------------------------------

# 7. API Security

Implement:

``` text
HTTPS
authentication
RBAC
rate limiting
request validation
response filtering
pagination
maximum page size
```

Example:

``` text
GET /api/v1/fares?page=1&page_size=100
```

Never allow unlimited result sets.

------------------------------------------------------------------------

# 8. Input Validation

Validate:

-   IATA codes
-   dates
-   numeric fare values
-   route IDs
-   source IDs
-   enum values
-   query lengths
-   pagination

Reject malformed data early.

------------------------------------------------------------------------

# 9. Database Security

-   Separate application DB user from migration/admin user.
-   Minimum privileges.
-   No public database exposure.
-   TLS for remote database connections.
-   Backups encrypted.
-   Sensitive operational fields encrypted where necessary.

------------------------------------------------------------------------

# 10. Secrets Management

Never commit:

``` text
JWT_SECRET
DATABASE_PASSWORD
API_KEYS
SOURCE_CREDENTIALS
COOKIE_VALUES
```

Use:

``` text
.env
```

only for local development.

Production:

-   cloud secret manager
-   Docker/Kubernetes secrets
-   CI secret store

------------------------------------------------------------------------

# 11. Web Security Headers

Configure:

``` text
Content-Security-Policy
Strict-Transport-Security
X-Content-Type-Options
Referrer-Policy
Permissions-Policy
```

Use `frame-ancestors` or equivalent clickjacking protection.

------------------------------------------------------------------------

# 12. CORS

Only allow known frontend origins.

Bad:

``` text
*
```

Preferred:

``` text
https://dashboard.example
```

Use separate development and production origins.

------------------------------------------------------------------------

# 13. Scraper Security

Collectors are untrusted-network clients.

Controls:

-   isolate collector workers
-   strict outbound network policy where possible
-   request timeouts
-   response-size limits
-   no arbitrary URL fetching
-   allowlist source domains
-   sanitize parsed content
-   store source payload safely
-   never execute downloaded scripts outside browser sandbox

------------------------------------------------------------------------

# 14. SSRF Protection

The application must not allow arbitrary user-supplied URLs to be
fetched.

For source configuration:

``` text
source domain
→ allowlist
→ policy check
→ fetch
```

Reject:

``` text
localhost
127.0.0.1
private IP ranges
metadata endpoints
internal hostnames
```

unless explicitly required in a controlled internal operation.

------------------------------------------------------------------------

# 15. CAPTCHA and Anti-Bot Policy

The system shall:

``` text
detect CAPTCHA
→ classify source state
→ stop automated attempt
→ log event
→ retry only according to source policy
```

It must not:

-   bypass CAPTCHA
-   purchase solving services
-   evade authentication
-   circumvent access controls
-   rotate infrastructure solely to defeat restrictions

------------------------------------------------------------------------

# 16. Data Integrity

Each processing run should generate:

``` text
run_id
input_snapshot/reference
processor_version
methodology_version
weight_version
output_timestamp
```

Optional enhancement:

``` text
SHA-256 hash of normalized calculation input
```

This provides a reproducibility fingerprint.

------------------------------------------------------------------------

# 17. Audit Logging

Audit events:

``` text
LOGIN_SUCCESS
LOGIN_FAILURE
ROLE_CHANGED
SOURCE_ENABLED
SOURCE_DISABLED
WEIGHT_CHANGED
METHODOLOGY_PUBLISHED
INDEX_PUBLISHED
EXPORT_CREATED
SCRAPER_FAILED
SCRAPER_PAUSED
```

Audit fields:

``` text
timestamp
actor_id
action
resource
resource_id
before
after
request_id
IP metadata where policy permits
```

Never log passwords or secrets.

------------------------------------------------------------------------

# 18. Data Retention

Define separate retention periods for:

-   raw observations
-   normalized observations
-   index values
-   audit logs
-   application logs
-   temporary scraper artifacts

Retention should be configurable and aligned with source policy and
institutional requirements.

------------------------------------------------------------------------

# 19. Backups

Minimum:

-   daily PostgreSQL backup
-   backup encryption
-   restore test
-   retention policy

Production target:

``` text
RPO: 24 hours or better
RTO: 4 hours or better
```

Targets may be tightened after infrastructure sizing.

------------------------------------------------------------------------

# 20. CI/CD Security

Pipeline checks:

``` text
pytest
ruff
mypy where adopted
dependency audit
secret scan
container scan
SAST
```

Block deployment on critical security findings.

------------------------------------------------------------------------

# 21. Dependency Security

-   Pin production dependencies.
-   Update regularly.
-   Review critical CVEs.
-   Avoid abandoned packages.
-   Use lockfiles.

------------------------------------------------------------------------

# 22. Container Security

-   Minimal base images.
-   Non-root runtime user.
-   Read-only filesystem where practical.
-   Drop unnecessary Linux capabilities.
-   No privileged containers.
-   Scan images before release.

------------------------------------------------------------------------

# 23. Frontend Security

-   No secrets in frontend bundle.
-   Sanitize rich text.
-   Avoid unsafe HTML injection.
-   Use CSP.
-   Do not trust route/query parameters.
-   Do not expose admin APIs through hidden UI alone.

------------------------------------------------------------------------

# 24. Statistical Integrity Security

This is unique to AirStat India.

Protect:

``` text
route weights
base-period prices
methodology versions
index outputs
revision history
```

Only authorized roles may change them.

Every change creates a new version rather than overwriting historical
calculations.

------------------------------------------------------------------------

# 25. Security Incident Response

Severity:

``` text
P0 Critical
P1 High
P2 Medium
P3 Low
```

Process:

``` text
Detect
 ↓
Contain
 ↓
Preserve evidence
 ↓
Assess
 ↓
Remediate
 ↓
Verify
 ↓
Document
```

------------------------------------------------------------------------

# 26. Security Checklist

-   [ ] HTTPS enabled.
-   [ ] RBAC implemented.
-   [ ] Admin APIs protected.
-   [ ] Secrets removed from repository.
-   [ ] Rate limits enabled.
-   [ ] CORS restricted.
-   [ ] Security headers configured.
-   [ ] SQL injection tests pass.
-   [ ] XSS protections pass.
-   [ ] SSRF protections pass.
-   [ ] Dependency scan enabled.
-   [ ] Container scan enabled.
-   [ ] Audit logging enabled.
-   [ ] Backup tested.
-   [ ] Scraper policy gate enabled.
-   [ ] CAPTCHA detection implemented.
-   [ ] No access-control bypass logic.
-   [ ] Methodology/weight changes versioned.
