# API test design

Use this file to decide **what** to test. Rank the cases by risk: money, personal data, permissions and irreversible actions come first.

## Per-endpoint checklist

| Area | Cases |
|---|---|
| Happy path | Valid request gives the exact success code (`200` read, `201` + `Location` create, `202` async accepted, `204` delete/no body), correct content type, body fields and schema |
| Persistence | After a create or update, a GET returns the new state. After a delete, a GET returns 404 or 410 |
| Validation | Missing required field, wrong type, empty string, too long, out of range, bad format (email, date, enum), extra unknown field, empty body, malformed JSON give `400`/`422` with a useful error (which field, why) and no partial write |
| Boundaries | min, min-1, max, max+1 for numbers and lengths; zero, negative, decimals and rounding for amounts; Unicode, emoji and right-to-left text; leading and trailing spaces |
| Authentication | No token, expired token, malformed token, token for another environment give `401` (with `WWW-Authenticate`). Logout or revoke really invalidates the session |
| Authorization | User A reads, updates or deletes user B's object by id gives `403` or `404` (BOLA, the most common API bug); role without permission on an admin route gives `403`; tenant A cannot reach tenant B |
| Not found | Unknown id gives `404` with the error format, and not `500` or `200 null` |
| Methods | An unsupported method gives `405` with `Allow`; HEAD and OPTIONS behave; method-override headers are ignored unless intended |
| Content negotiation | Wrong `Content-Type` gives `415`; an `Accept` the API cannot serve gives `406`; charset handling |
| Conflicts | Duplicate create (unique key) gives `409`; stale update with `If-Match`/ETag gives `412`; state-machine violations (cancel a shipped order) give `409`/`422` |
| Idempotency | PUT/DELETE twice ends in the same state; POST with the same `Idempotency-Key` creates one resource and replays the first response |
| Lists | Pagination (first, middle, last, beyond last, size 0/1/max/max+1, stable order between pages), filter combinations, sort asc/desc and on invalid fields, empty result is `200 []` and not `404` |
| Errors | One error format everywhere, ideally RFC 9457 problem details (`application/problem+json` with `type`, `title`, `status`, `detail`, `instance`); no stack traces, SQL, internal hostnames or versions |
| Headers | `Cache-Control: no-store` on personal data, security headers where the API serves browsers, a correlation id (`X-Request-Id`/`traceparent`), no `X-Powered-By` |
| Rate limits | Above the limit you get `429` with `Retry-After`/`RateLimit-*`, and it recovers afterwards. Run this only on an environment where that is allowed |
| CORS | Allowed origin gets the right `Access-Control-Allow-*` headers; disallowed origin gets none; no `*` together with credentials |
| Versioning | Old version still works or returns a documented deprecation (`Deprecation`, `Sunset` headers); unknown version is rejected |
| Async | `202` + status URL; poll it until done or failed, with a timeout; the final state is correct; failed jobs report why |
| Files | Upload size limit (`413`), type checks, download `Content-Disposition` and `Content-Type` |
| Performance (smoke) | `max_ms` budget on key endpoints; no N+1 slowdown as lists grow. Real load testing belongs in a load tool |

## OWASP API Security Top 10 (2023) as tests

| Risk | Automate |
|---|---|
| API1 Broken Object Level Authorization | Two users: every id-based route with the other user's id gives 403/404. Includes nested routes and ids in the body |
| API2 Broken Authentication | 401 without, with expired and with tampered tokens (change one character, `alg: none`); login brute force is throttled; no tokens in URLs |
| API3 Broken Object Property Level Authorization | Responses never contain sensitive fields (`$.password`, `$.ssn` `exists: false`); mass assignment (`"role": "admin"`, `"price": 0` in the body) is ignored or rejected |
| API4 Unrestricted Resource Consumption | `page_size=100000`, huge bodies and deep JSON are rejected or capped; rate limits are present |
| API5 Broken Function Level Authorization | A normal user on admin routes or admin methods gives 403 |
| API6 Unrestricted Access to Sensitive Business Flows | Bulk purchase, sign-up or voucher abuse is limited (rate, CAPTCHA, per-account caps) |
| API7 Server Side Request Forgery | URL inputs (webhooks, avatars by URL) refuse `http://169.254.169.254/`, `localhost` and private ranges |
| API8 Security Misconfiguration | No stack traces, TLS only, CORS correct, no debug endpoints, `OPTIONS`/`TRACE` locked down |
| API9 Improper Inventory Management | Old versions (`/v1`) and undocumented routes found in the spec diff are either secured like current ones or removed |
| API10 Unsafe Consumption of APIs | Upstream timeouts and bad upstream data are handled: mock the third party (WireMock) and return garbage or slow responses |

Injection (SQL, NoSQL, command, header CRLF) still matters. Send typical payloads in strings and expect a `400` or a harmless echo, never a `500`. Deeper security testing (ZAP, Burp, a dedicated pentest) is out of scope here. Mention it to the user when the API handles money or personal data.

## Test data strategy

- **Create what you need** through the API (or a seeding endpoint or fixture) with unique values (`${$run_id}`) and delete it afterwards. Don't depend on shared seed data that other teams change.
- **Two users minimum** (owner and stranger) for authorization tests, plus an admin if roles exist. Keep their credentials in CI secrets.
- **Synthetic data only**: example.test e-mail domains, the field's official test numbers (cards, IBANs, patient ids), never production copies.
- **Clean up in reverse order** of creation. Make cleanup tolerant (`[204, 404]`) so a rerun after a crash still passes.
- **Time**: freeze or control it where the API allows (a test clock header or endpoint), or assert ranges instead of exact times. Watch time zones and DST.

## Why API tests become flaky, and the fix

| Cause | Fix |
|---|---|
| Order dependence and shared data | Each chain creates its own data; `depends_on` only inside a chain |
| Fixed sleeps for async work | Poll with a timeout |
| Eventual consistency (search index, read replica, cache) | Poll the read side; assert "eventually" with a bound |
| Asserting volatile values (time, ids, order of an unordered list) | Assert types, formats, ranges or sorted copies |
| Environment drift (expired token, data reset, feature flag) | Fetch tokens at run start; seed data in the run; pin flags per test environment |
| Rate limiting the test runner | Lower parallelism, use a test tenant with higher limits, honour `Retry-After` |
| Timeouts on slow shared environments | Realistic timeouts plus `max_ms` budgets; report slow endpoints separately |
| Hidden retries in the client masking failures | Count and report retries; run with retries off regularly (`--no-retry`) |
| Parallel tests touching the same record | Unique data per test, or run that group serially |

## Choosing the layer

| Layer | What it proves | Tool |
|---|---|---|
| Contract (consumer-driven) | Provider still satisfies what each consumer uses | Pact |
| Schema/spec conformance | Responses match the OpenAPI spec for many generated inputs | Schemathesis, `api_check.py` schema checks |
| Functional API tests | Business rules, permissions, errors, chained flows | `api_check.py`, REST Assured, pytest, Karate, Postman |
| Component tests with mocks | The service handles a bad or slow upstream | WireMock, MockServer, Testcontainers |
| End-to-end UI | Users can complete the journey | Playwright (see `playwright-test-authoring`) |
| Load | Throughput, latency percentiles, saturation | k6, Gatling, JMeter, Locust |

Put most cases in fast functional API tests, keep a few UI journeys, and run contract and schema checks on every merge request.
