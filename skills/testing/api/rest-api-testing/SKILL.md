---
name: rest-api-testing
description: "Test the REST APIs of web applications reliably, in any field (banking, healthcare, e-commerce, telecom, SaaS): plan cases from an OpenAPI spec, write functional, negative, auth and contract tests, and run them with a script that retries only safe requests, polls instead of sleeping, masks secrets and writes JUnit reports. Use when the user wants API tests written, run or reviewed, or says API tests are flaky."
license: Complete terms in the repository README
compatibility: The script needs Python 3.8+ and nothing else (standard library only; YAML specs are read by the bundled yaml_lite.py). It sends real HTTP requests, so it needs network access to the API under test. Framework examples need their own toolchains (JDK for REST Assured and Karate, Node.js for Newman, SuperTest and Playwright).
metadata:
  title: "REST API testing for web applications"
  category: api-testing-tools
---

# REST API testing for web applications

Most web applications are a front end over REST APIs, and most of their bugs, security holes and outages show up in those APIs first. This skill tests that layer the same way in any field (banking, healthcare, retail, insurance, telecom, government, SaaS). It works in three steps: **plan** what to test, **write** tests that give the same result on every run, and **run and report** them in CI.

The bundled `scripts/api_check.py` runs JSON test suites with nothing to install. If the team already uses a framework (REST Assured, pytest, Postman, Karate, Playwright, SuperTest), write the tests there and follow the same rules: [references/frameworks.md](references/frameworks.md).

## When to use

- "Write API tests for our orders endpoints", "test this REST API", "generate tests from our OpenAPI/Swagger file".
- Review or harden an existing API suite: flaky tests, tests that only check the status, hard-coded tokens, tests that depend on order.
- Add contract checks (response matches the schema), auth/permission tests, negative and edge cases.
- Run API smoke tests after a deploy (read-only), or wire API tests into CI with JUnit results.

## When NOT to use

- Browser UI flows: use `playwright-test-authoring` (it can call the API for setup).
- Load and stress tests: use k6, Gatling, JMeter or Locust (see [references/frameworks.md](references/frameworks.md)). This skill only checks response times per request.
- GraphQL, gRPC, SOAP or WebSocket APIs: the ideas carry over, but the script speaks REST/HTTP JSON only.
- Penetration testing. The security checks here are the ones a test team should automate. They do not replace a security assessment.

## Safety rules (read first)

1. **Never test against production with write requests** unless the user says so explicitly for that run. Use a test or staging environment. For production smoke checks run `--read-only`. It skips POST, PUT, PATCH and DELETE.
2. Every suite that writes data has `allowed_hosts`. The script refuses to send a request to any other host.
3. **No secrets in suite files or test code.** Use `${API_TOKEN}` and pass values with `--env .env.test` (git-ignored), `--var` or CI secrets. `lint` fails on literal tokens. Output masks tokens, passwords and cookies.
4. Use synthetic test data only: no real customer, patient or card data (for test cards see [references/industry-checklists.md](references/industry-checklists.md)). Make data unique per run (`${$run_id}`) and delete what you create.
5. Don't weaken an assertion to make a test pass. If the API is wrong, report it as a bug.

## Procedure

`scripts/api_check.py` is in this skill's folder. Run it from anywhere. `python api_check.py <command> --help` lists the options.

1. **Learn the API.** Find the OpenAPI/Swagger file (`openapi.json|yaml`, `/v3/api-docs`, `/swagger.json`), the auth method (bearer/OAuth2, API key, session cookie, basic), the environments and base URLs, how test data is created, and any existing API tests and their framework. Ask the user for the test environment URL and how to get a test token if they are not in the repository.
2. **Plan coverage** with [references/test-design.md](references/test-design.md). For each endpoint, cover the happy path, validation (400/422), auth (401) and permissions (403/404 on someone else's object), not found (404), conflicts and idempotency (409, retries), pagination/filter/sort, and the error format. Add the field's risks from [references/industry-checklists.md](references/industry-checklists.md). List the cases before writing them and order them by risk.
3. **Start a suite.** From a spec:
   ```bash
   python scripts/api_check.py plan openapi.json --out tests/api/orders.json
   ```
   It writes one positive test per operation with example bodies, a contract (schema `$ref`) check on the success response, and negative tests for missing credentials, empty bodies and unknown ids. Without a spec, use `python scripts/api_check.py example --out tests/api/smoke.json` and edit it. The format is in [references/suite-format.md](references/suite-format.md).
4. **Make every test meaningful.** Assert the exact status, the content type, the important fields (`json` matchers) and the schema. A test that only checks `200` is not enough. Chain CRUD with `capture` and `depends_on`, and end with an `always_run` cleanup.
5. **Lint, then run**:
   ```bash
   python scripts/api_check.py lint tests/api/orders.json            # unknown keys, secrets, order bugs, unsafe retries
   python scripts/api_check.py run tests/api/orders.json --env .env.test --junit build/api-junit.xml --report build/api-report.md
   python scripts/api_check.py run tests/api/orders.json --tag smoke --read-only --base-url https://app.example.com
   ```
   Exit code 0 means everything passed, 1 means a test failed or errored, 2 means the suite or input is invalid (`run` refuses a suite with lint errors).
6. **Prove the tests can fail.** Break one expectation (or point at a build with a known bug) and confirm the test goes red with a clear message. Run the suite twice in a row: it must pass both times, which shows the data is isolated and cleanup works. Run once with `--no-retry` to see which endpoints are flaky.
7. **Report.** Summarise passed/failed, each failure (request, expected, actual), retries (each one is a flaky endpoint), the slowest calls and bugs found. Add the run to CI using the JUnit file (see the CI section of [references/frameworks.md](references/frameworks.md)).

## Rules for reliable API tests

1. **Independent tests.** Each test (or each `depends_on` chain) creates its own data with unique values (`${$run_id}`, `${$uuid}`) and never relies on leftovers or on another chain running first.
2. **Clean up always.** Delete what you create in an `always_run` test (accept `[204, 404]`), or in a teardown/fixture `finally` in code.
3. **No fixed sleeps.** For asynchronous work (jobs, events, eventual consistency) poll until a condition is met, with a timeout (`poll`; Awaitility, `expect.poll`, `retry` loops in code).
4. **Retries are not a fix.** Retry only transport errors and 429/502/503/504, and only for idempotent methods (GET, PUT, DELETE) or a POST with an `Idempotency-Key`. Report every retry, and treat a flaky endpoint as a defect.
5. **Assert on stable facts.** Don't assert exact timestamps, generated ids, ordering the API doesn't promise, or the full body when only some fields matter. Use types, formats, ranges and `exists`.
6. **Exact status codes.** Expect `201`, not "2xx". Use a list only when the API really allows several codes (`[400, 422]` for validation, `[204, 404]` for idempotent delete).
7. **Contract plus behaviour.** Validate the schema (from the OpenAPI spec) and also check the values that matter for the business rule.
8. **Timeouts everywhere.** Give every request a timeout (the default is 15 s) and set a `max_ms` budget for key endpoints, so a slow dependency shows up as a failure and never as a hang.
9. **Configuration from outside.** Base URL, credentials and tenant come from the environment. The same suite runs locally, in CI and against staging.
10. **Name tests for behaviour**: "rejects an order without items", not "test 7". Tag them (`smoke`, `negative`, `security`, `write`) so CI can run subsets.

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| `variable ${X} is not defined` | Set it in `variables`, `--env`, `--var` or the environment, or the test that captures it failed. `lint` shows where it comes from |
| `request failed: [SSL: CERTIFICATE_VERIFY_FAILED]` | Corporate proxy or self-signed test certificate: install the CA in the OS store. `--insecure` is only for throwaway test servers |
| `request failed: timed out` / connection refused | Wrong `--base-url`, VPN/proxy needed (`HTTPS_PROXY` is honoured), or the service is down. Check with one `curl -i` |
| 401 on everything | Token missing, expired or for another environment; the `Authorization` header was overridden with `null`; the cookie-based login test failed earlier |
| 403/404 only in CI | The CI test user lacks a role or tenant, or the data the test reads only exists locally. Create it in the test |
| Test passes alone, fails in the suite | Shared data or order dependence: give it its own data and cleanup |
| Passes on retry only | A flaky endpoint (summary shows retries). Run with `--no-retry`, collect timings, report it |
| `the body is not JSON` | Error page from a gateway or proxy (HTML 502/504) or the wrong `Accept` header. The excerpt in the output shows the real body |
| Schema error `property not allowed` | The API added a field and the spec says `additionalProperties: false`. Update the spec or report contract drift |

## References

- [references/suite-format.md](references/suite-format.md): the full JSON suite format (requests, matchers, schema refs, capture, retry, poll, variables) and CLI options.
- [references/test-design.md](references/test-design.md): what to test per endpoint, negative and boundary cases, auth and permissions, pagination, idempotency, concurrency, caching, CORS, error format (RFC 9457), versioning, OWASP API Security Top 10 (2023), and the causes of flaky tests.
- [references/frameworks.md](references/frameworks.md): the same tests in REST Assured (Java/Kotlin), pytest + requests/httpx, Postman/Newman, Karate, Playwright `request`, SuperTest; contract testing (Pact, Schemathesis), mocking (WireMock), load tools; running in CI.
- [references/industry-checklists.md](references/industry-checklists.md): API risks and test cases by field: banking and payments, healthcare (FHIR, HIPAA), e-commerce and retail, insurance, telecom, travel, logistics, government, SaaS and multi-tenant, media.
