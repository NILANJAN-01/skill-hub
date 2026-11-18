# Suite format for api_check.py

A suite is one JSON file. Tests run in file order, and values captured in one test are available to later tests. `python api_check.py example` prints a complete example, and `scripts/fixtures/orders_suite.json` is a suite that the skill's own tests run.

```json
{
  "name": "Orders API",
  "base_url": "${BASE_URL}",
  "allowed_hosts": ["localhost", "127.0.0.1", "*.staging.example.com"],
  "defaults": {
    "headers": {"Accept": "application/json"},
    "timeout": 10,
    "auth": {"bearer": "${API_TOKEN}"},
    "retry": {"attempts": 3, "backoff_ms": 250}
  },
  "variables": {"customer_email": "qa+${$run_id}@example.test"},
  "tests": [ { "name": "...", "request": {...}, "expect": {...} } ]
}
```

| Suite key | Meaning |
|---|---|
| `name`, `description` | Shown in output and reports |
| `base_url` | Prefix for every `path`. `--base-url` overrides it |
| `allowed_hosts` | Host names or globs (`*.test`). Requests to any other host are refused. Required by `lint` when the suite writes |
| `defaults` | `headers`, `query`, `timeout` (seconds, default 15), `follow_redirects` (default true), `retry`, `auth` for every test |
| `variables` | Default values. They may use other variables |
| `tests` | The list of tests |

## Variables

`${NAME}` works in every string of `request`, `expect` and `variables`. A variable is looked up in this order, first match wins:

1. values captured by earlier tests
2. `--var NAME=VALUE`
3. the process environment (CI secrets)
4. the `--env` file (`NAME=VALUE` lines, or a JSON object)
5. the suite's `variables`

If a string is exactly `"${count}"`, the value keeps its type, so a captured number stays a number in a JSON body. Built-ins: `${$run_id}` (one random id per run, for unique test data), `${$uuid}` (new on each use), `${$timestamp}` (Unix seconds), `${$now}` (UTC ISO time), `${$rand}` (6 digits). An undefined variable makes the test an **error** before anything is sent. An `always_run` test with an undefined variable is skipped instead, because there is nothing to clean up.

Values of variables whose names look secret (`token`, `secret`, `password`, `key`, `auth`, `cookie`, `session` ...) and every `Authorization`, `Cookie` and `X-Api-Key` value are masked as `***` in all output and reports.

## Test

| Key | Meaning |
|---|---|
| `name` | Unique. Used by `depends_on`, `--only` and reports |
| `tags` | For example `["smoke", "negative", "security", "write"]`; select with `--tag` and `--skip-tag` |
| `request` | See below |
| `expect` | See below. If `status` is left out, any 2xx passes (`lint` warns about it) |
| `capture` | `{"order_id": "$.id"}`, `{"url": {"header": "Location"}}`, `{"csrf": {"regex": "name=\"csrf\" value=\"([^\"]+)\""}}`, `{"code": {"status": true}}`. A capture that finds nothing fails the test |
| `depends_on` | Names of earlier tests. If one did not pass, this test is skipped with the reason |
| `always_run` | Runs even after `--fail-fast` stops the suite and with `--tag` filters. Use it for cleanup |
| `retry` | `attempts` (default 3), `backoff_ms` (250, doubled per attempt), `on_status` (`[429, 502, 503, 504]`), `unsafe` (allow retrying POST/PATCH; prefer an `Idempotency-Key` header) |
| `poll` | `{"timeout_ms": 10000, "interval_ms": 500}`: repeat the request until `expect` passes or time runs out (for asynchronous processing) |
| `skip` | `true` or a reason string |
| `read_only_safe` | Lets a write method run in `--read-only` mode (for example a POST search endpoint) |

Retries apply only to idempotent methods (GET, HEAD, OPTIONS, PUT, DELETE) or requests with an `Idempotency-Key` header. A status listed in `expect.status` is never retried. `Retry-After` is honoured, up to 30 s. Every retry is counted in the summary and in JUnit `system-out`, so a flaky endpoint stays visible.

### request

| Key | Meaning |
|---|---|
| `method` | Default `GET` |
| `path` | Appended to `base_url`. A captured absolute path (such as a `Location` value) works too |
| `url` | Absolute URL, for a different service (bypasses `base_url`) |
| `headers` | Merged over `defaults.headers`, case-insensitively; `null` removes a header (for example `"Authorization": null` for a no-token test) |
| `query` | `{"page": 2, "tag": ["a", "b"]}`; lists repeat the key |
| `json` / `form` / `body` | JSON body (sets `Content-Type: application/json`), URL-encoded form, or raw string. Use only one |
| `auth` | `{"bearer": "${TOKEN}"}`, `{"basic": ["${USER}", "${PASS}"]}`, `{"header": {"X-Api-Key": "${KEY}"}}`, or `null` to switch off the default auth |
| `timeout` | Seconds |
| `follow_redirects` | `false` to assert a 3xx and its `Location` |

Cookies persist for the whole run, like a browser session: log in once with a `form` POST, and later tests send the session cookie.

### expect

| Key | Example | Checks |
|---|---|---|
| `status` | `201`, `[400, 422]`, `"2xx"` | Status code |
| `content_type` | `"application/json"` | Media type, ignoring `; charset=` |
| `headers` | `{"Location": {"regex": "^/orders/"}, "Cache-Control": {"contains": "no-store"}, "X-Request-Id": true, "Server": false}` | A value, a matcher, `true` = present, `false` = absent |
| `no_headers` | `["X-Powered-By", "X-Debug"]` | Headers that must not be sent (information leaks) |
| `max_ms` | `800` | Response time budget |
| `json` | `{"$.status": "NEW", "$.items.length": 2, "$.total": {"gte": 0}}` | JSON paths, see below |
| `schema` | `{"$ref": "openapi.json#/components/schemas/Order"}` or an inline schema | The whole body against a JSON Schema |
| `body_contains`, `body_not_contains` | `"Welcome"`, `["stack trace", "Exception"]` | Raw text |
| `body_regex` | `"order-\\d+"` | Raw text |

### JSON paths and matchers

Paths: `$` (the whole body), `$.a.b`, `$.items[0]`, `$.items[-1]`, `$['odd key']`, `$.items.length` (length of an array, string or object).

A plain value means "equal". JSON types are strict: `true` is not `1`, and `1` equals `1.0`. An object whose keys are all matcher names is treated as matchers:

| Matcher | Example |
|---|---|
| `eq`, `ne` | `{"eq": {"a": 1}}` (use `eq` to compare a whole object literally) |
| `type` | `"string"`, `"integer"`, `"number"`, `"boolean"`, `"array"`, `"object"`, `"null"`, or a list |
| `regex` | `{"regex": "^ord-\\d+$"}` |
| `gt`, `gte`, `lt`, `lte` | `{"gte": 0, "lt": 100}` |
| `len`, `min_len`, `max_len` | `{"min_len": 1}` |
| `in` | `{"in": ["NEW", "CONFIRMED"]}` |
| `contains`, `not_contains` | Substring of a string, element of an array, key of an object |
| `exists` | `{"exists": false}` (for example, `$.password` must never be returned) |
| `schema` | `{"schema": {"type": "array", "items": {"$ref": "openapi.json#/components/schemas/Item"}}}` |

### Schema support

The schema check supports `type` (and OpenAPI `nullable`), `enum`, `const`, `properties`, `required`, `additionalProperties`, `items`, `minItems`/`maxItems`/`uniqueItems`, `minLength`/`maxLength`/`pattern`, `format` (date-time, date, email, uuid, uri, ipv4), `minimum`/`maximum`/`exclusiveMinimum`/`exclusiveMaximum`/`multipleOf`, `allOf`/`anyOf`/`oneOf`/`not`, and `$ref` to the same document or to another file (`file.json#/pointer`, relative to the suite file). JSON Pointer escapes: `/` becomes `~1` and `~` becomes `~0` (`#/paths/~1orders/post/...`). YAML spec files need PyYAML. For full JSON Schema 2020-12 or property-based fuzzing, use Schemathesis (see [frameworks.md](frameworks.md)).

## CLI

```text
run SUITE [--env FILE] [--var K=V]... [--base-url URL] [--tag T]... [--skip-tag T]... [--only NAME]...
          [--read-only] [--fail-fast] [--no-retry] [--junit FILE] [--json FILE] [--report FILE] [--insecure] [-v]
lint SUITE [--strict]          # ERROR = must fix, WARN = flaky or unsafe pattern, INFO = needs a value at run time
plan OPENAPI [--out FILE]      # OpenAPI 3.x JSON (YAML with PyYAML); Swagger 2.0 must be converted first
example [--out FILE]
```

Exit codes: `0` all passed or no lint errors; `1` failures, errors or lint errors (`--strict`: warnings too); `2` invalid suite, file or option. Proxies come from `HTTP_PROXY`, `HTTPS_PROXY` and `NO_PROXY`. TLS certificates are checked against the OS trust store.
