# API test checklists by field

Every field needs the general checklist in [test-design.md](test-design.md). The tables below add what is specific to each field and usually costs the most when it fails. These are testing prompts, not legal advice. The user's compliance team decides what a regulation actually requires.

Rules for every field:
- **Synthetic data only.** Use the official test numbers that providers publish (payment gateways, banks, FHIR sandboxes), `example.test` e-mails and made-up names. Never use copies of production records.
- **Never send real personal data to a test environment**, and never send test data to production.
- Check that sensitive values never appear in responses that don't need them, and never in error messages, URLs or logs you can access.

## Banking, payments and fintech

| Risk | Tests |
|---|---|
| Money arithmetic | Amounts as decimal strings or minor units (cents) and never as floats; rounding rules (half-even vs half-up) at boundaries; currency with 0 and 3 decimals (JPY, KWD); negative, zero and maximum amounts |
| Double payment | Same `Idempotency-Key` gives one charge and the same response; a retry after a timeout does not double-charge; concurrent identical requests |
| Balances and ledgers | Transfer A to B: both balances change atomically; failure mid-way rolls back; the sum of ledger entries equals the balance; overdraft limits |
| State machine | authorize, capture, refund, void in valid and invalid orders; partial capture and partial refund up to the total and not beyond |
| Card data (PCI DSS) | Full card numbers (PAN) never returned (masked to first 6 and last 4 at most); CVV never stored or echoed; test cards only (for example the gateway's `4242 4242 4242 4242` or `4111 1111 1111 1111` in its sandbox) |
| Strong customer authentication, open banking | Consent required, scoped and expiring; payment above a threshold asks for a challenge; revoked consent gives 401/403 |
| Fraud and limits | Daily or velocity limits enforced; sanctioned or blocked accounts rejected; rate limits on OTP and login |
| Audit | Every money movement has an audit entry with actor, time and correlation id |
| Time | Cut-off times, business days, holidays and time zones for value dates |

## Healthcare (FHIR, HIPAA, GDPR health data)

| Risk | Tests |
|---|---|
| FHIR conformance | Resources validate against the FHIR version (R4/R5) and profiles; `CapabilityStatement` at `/metadata` matches what is served; errors return `OperationOutcome` |
| Search | FHIR search parameters (`patient=`, `date=ge2026-01-01`, `_count`, `_include`) and paging via `Bundle.link[next]` |
| Access control | SMART on FHIR scopes (`patient/*.read` vs `user/*.write`); a clinician only sees their patients; break-glass access is logged |
| Minimum necessary | Responses and list endpoints don't over-share identifiers (SSN, MRN) unless the scope requires it |
| Versioning | `If-Match` with `ETag`/`meta.versionId` prevents lost updates; history (`_history`) is kept |
| Audit | Every read of patient data produces an audit event (FHIR `AuditEvent` or the system's log) |
| Consent | Withdrawn consent blocks sharing; data-export and erasure requests are honoured where the law requires |
| Units and codes | LOINC, SNOMED CT and UCUM codes valid; units consistent; dates partial (`2026-05`) handled |

## E-commerce and retail

| Risk | Tests |
|---|---|
| Price and tax | Price, discount, tax and shipping totals agree with the line items; coupons stack only as allowed; expired, used and foreign-currency coupons |
| Inventory | Overselling the last item under concurrent checkout; reservations expire; stock updates after cancel or return |
| Cart and checkout | Guest and logged-in carts merge; price changes during checkout are detected; the order total is computed by the server, so a client-sent price is ignored (mass assignment) |
| Payments and webhooks | Webhook signatures are verified; duplicate webhooks are idempotent; out-of-order events (refund before capture notice) |
| Catalog | Search, filter, facet and sort; pagination stability; localisation (currency, language, units) |
| Promotions at scale | Rate limits and caching on peak endpoints; `max_ms` budgets on product and cart APIs |
| Privacy | Customers cannot see each other's orders or addresses (BOLA); account deletion or export (GDPR/CCPA) |

## Insurance

| Risk | Tests |
|---|---|
| Rating | Premium calculation for boundary ages, dates, regions and coverage limits; rounding; versioned rate tables by effective date |
| Policy lifecycle | Quote, bind, issue, endorse, renew, cancel; backdated and future-dated changes; changes that overlap |
| Claims | First notice of loss, documents upload (size and type), status transitions, payout limits and deductibles |
| Standards | ACORD or partner data formats map correctly; required fields per product line |
| Access | Agents, brokers and customers see only their policies; underwriter-only actions |

## Telecom

| Risk | Tests |
|---|---|
| Standard APIs | TM Forum Open API shapes (for example product catalog, product ordering, service inventory), `@type`/`href` fields, the event hub (`/hub`) subscriptions |
| Numbers | E.164 phone numbers, porting states, number reservation expiry |
| Provisioning | Long-running orders (`202` + poll); partial failures and rollback; idempotent retries from OSS/BSS systems |
| Usage and billing | Rating of usage records, time zones, roaming, proration on plan change mid-cycle |
| Scale | Bulk endpoints, pagination over millions of records, rate limits per partner |

## Travel and hospitality

| Risk | Tests |
|---|---|
| Availability | Double booking of the last seat or room under concurrency; holds expire; overbooking rules |
| Time | Time zones of origin and destination, DST transitions, dates across midnight, date-only vs date-time |
| Pricing | Fare rules, taxes and fees, currency conversion, price changes between search and booking |
| Changes | Modify, cancel and refund policies by fare class; partial cancellations of multi-segment bookings |
| Partners | Supplier timeouts and errors are mapped to clear responses (mock them) |

## Logistics and supply chain

| Risk | Tests |
|---|---|
| Shipment states | Only valid transitions (created, picked, in transit, delivered, returned); events arriving late or twice |
| Addresses and geo | International address formats, postcode validation, latitude and longitude bounds |
| Labels and documents | Generated PDFs and labels have the right `Content-Type`, size and content |
| Integrations | EDI/partner webhooks: signatures, retries, idempotency, backpressure |

## Government and public sector

| Risk | Tests |
|---|---|
| Identity | Citizen identity provider flows (OIDC); assurance levels; delegated access (acting for someone) |
| Data protection | Data minimisation, retention, audit of every access, data residency (the region the data must stay in) |
| Forms and rules | Eligibility rules at boundaries (age, income thresholds, dates); multilingual fields and character sets |
| Openness | Open data APIs: stable versioning, documented rate limits, consistent error format |
| Resilience | Peak load around deadlines; graceful `503` with `Retry-After` |

## SaaS, multi-tenant and B2B platforms

| Risk | Tests |
|---|---|
| Tenant isolation | Every endpoint with tenant B's ids under tenant A's token gives 403/404, including search, export, files and webhooks |
| Plans and limits | Plan quotas (seats, API calls, storage) enforced; upgrade or downgrade takes effect; `429` vs `402`/`403` semantics are documented |
| API keys and OAuth | Key scopes, rotation (old key stops working), revocation; OAuth client credentials and refresh tokens |
| Webhooks | HMAC signature header verified; timestamp tolerance against replay; retries with backoff; delivery is idempotent |
| Admin and roles | Role matrix tests (owner, admin, member, read-only) per endpoint |
| Bulk and export | Async export jobs, large files, CSV injection in exported fields |

## Media, streaming and content

| Risk | Tests |
|---|---|
| Delivery | Range requests (`206`, `Content-Range`), signed URL expiry, CDN cache headers (`ETag`, `Cache-Control`, `304` on `If-None-Match`) |
| Entitlements | Region, subscription tier and age-rating restrictions; concurrent stream limits |
| Uploads | Large and resumable uploads, type and size validation, transcoding job status by polling |

## Education and HR

| Risk | Tests |
|---|---|
| Roles | Student, teacher, parent, admin (or employee, manager, HR) role matrix, so nobody sees another person's grades or salary |
| Personal data | Minors' data protections, retention, export and erasure |
| Calendars | Terms, time zones, recurring events, payroll cut-off dates |
