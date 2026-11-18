# The same API tests in common frameworks

Use the framework the team already has. Every example tests the same three things: create an order and check the status, contract and fields; read it back; reject a request without a token. Each one cleans up afterwards. Base URL and token always come from the environment. Library versions are examples: use the versions the project already pins.

## REST Assured (Java, JUnit 5/6)

```java
// build.gradle.kts: testImplementation("io.rest-assured:rest-assured:<version>")
//                   testImplementation("io.rest-assured:json-schema-validator:<version>")
import static io.restassured.RestAssured.*;
import static org.hamcrest.Matchers.*;
import static io.restassured.module.jsv.JsonSchemaValidator.matchesJsonSchemaInClasspath;

class OrdersApiTest {
    static final String TOKEN = System.getenv("API_TOKEN");
    String orderId;

    @BeforeAll static void setUp() {
        baseURI = System.getenv().getOrDefault("BASE_URL", "http://localhost:8080");
        enableLoggingOfRequestAndResponseIfValidationFails();
    }

    @Test void createsAndReadsAnOrder() {
        orderId = given().auth().oauth2(TOKEN).contentType("application/json")
                .header("Idempotency-Key", UUID.randomUUID().toString())
                .body(Map.of("customer", "qa+" + UUID.randomUUID() + "@example.test",
                             "items", List.of(Map.of("sku", "SKU-1", "qty", 2))))
            .when().post("/orders")
            .then().statusCode(201).contentType("application/json")
                .header("Location", startsWith("/orders/"))
                .body("status", equalTo("NEW"), "items", hasSize(1))
                .body(matchesJsonSchemaInClasspath("schemas/order.json"))
                .time(lessThan(2000L))
            .extract().path("id");

        given().auth().oauth2(TOKEN).when().get("/orders/{id}", orderId)
            .then().statusCode(200).body("id", equalTo(orderId));
    }

    @Test void rejectsMissingToken() {
        when().get("/orders/any").then().statusCode(401);
    }

    @AfterEach void cleanUp() {
        if (orderId != null) given().auth().oauth2(TOKEN).delete("/orders/{id}", orderId)
            .then().statusCode(anyOf(is(204), is(404)));
    }
}
```

Set connection and socket timeouts through `RestAssuredConfig` (`HttpClientConfig`), so a hung server fails the test instead of blocking the build. Kotlin: the same API works with `Given { } When { } Then { }` from `io.rest-assured:kotlin-extensions`. Write the JUnit structure with `junit-test-authoring`.

## pytest + requests (or httpx)

```python
# pip install pytest requests jsonschema
import json, os, uuid
from pathlib import Path
import pytest, requests
from jsonschema import validate

BASE = os.environ.get("BASE_URL", "http://localhost:8080")
TIMEOUT = 10  # pass it on every call: requests has no default timeout

@pytest.fixture
def api():
    with requests.Session() as s:
        s.headers.update({"Authorization": f"Bearer {os.environ['API_TOKEN']}", "Accept": "application/json"})
        yield s

@pytest.fixture(scope="session")
def order_schema():
    return json.loads(Path(__file__).with_name("order.schema.json").read_text())

@pytest.fixture
def order(api):
    r = api.post(f"{BASE}/orders", timeout=TIMEOUT,
                 json={"customer": f"qa+{uuid.uuid4().hex[:8]}@example.test", "items": [{"sku": "SKU-1", "qty": 2}]},
                 headers={"Idempotency-Key": str(uuid.uuid4())})
    assert r.status_code == 201, r.text
    body = r.json()
    yield body
    api.delete(f"{BASE}/orders/{body['id']}", timeout=TIMEOUT)   # cleanup runs even if the test fails

def test_create_and_read(api, order, order_schema):
    assert order["status"] == "NEW" and len(order["items"]) == 1
    validate(order, order_schema)
    r = api.get(f"{BASE}/orders/{order['id']}", timeout=TIMEOUT)
    assert r.status_code == 200 and r.json()["id"] == order["id"]

def test_requires_token():
    assert requests.get(f"{BASE}/orders/any", timeout=TIMEOUT).status_code == 401
```

For polling, write one small `wait_until(fn, timeout)` helper instead of `time.sleep` loops spread through tests. Add `pytest-rerunfailures` only together with a report of what was rerun. `pytest --junitxml=build/api.xml` produces results for CI.

## Postman / Newman

```javascript
// Collection pre-request or a "setup" request stores the schema once:
//   pm.collectionVariables.set("orderSchema", JSON.stringify({ type: "object", required: ["id", "status"] }));
// Tests tab of "Create order":
pm.test("201 and contract", () => {
  pm.response.to.have.status(201);
  pm.expect(pm.response.headers.get("Location")).to.match(/^\/orders\//);
  pm.response.to.have.jsonSchema(JSON.parse(pm.collectionVariables.get("orderSchema")));
  const body = pm.response.json();
  pm.expect(body.status).to.eql("NEW");
  pm.collectionVariables.set("orderId", body.id);
});
```

```bash
npx newman run orders.postman_collection.json -e staging.postman_environment.json \
  --env-var "API_TOKEN=$API_TOKEN" --timeout-request 10000 \
  --reporters cli,junit --reporter-junit-export build/newman.xml
```

Keep secrets out of exported environments: current values are not exported, so set them with `--env-var`. Put cleanup requests at the end of the folder. Use `pm.execution.setNextRequest` sparingly, because it hides the run order.

## Karate

```gherkin
Feature: orders
  Background:
    * url java.lang.System.getenv('BASE_URL')
    * header Authorization = 'Bearer ' + java.lang.System.getenv('API_TOKEN')
    * configure readTimeout = 10000

  Scenario: create, read, delete
    * def email = 'qa+' + java.util.UUID.randomUUID() + '@example.test'
    Given path 'orders'
    And request { customer: '#(email)', items: [{ sku: 'SKU-1', qty: 2 }] }
    When method post
    Then status 201
    And match response contains { id: '#string', status: 'NEW', items: '#[1]', total: '#number' }
    * def id = response.id
    Given path 'orders', id
    When method get
    Then status 200
    And match response.id == id
    Given path 'orders', id
    When method delete
    Then status 204
```

`retry until` handles polling (`* configure retry = { count: 20, interval: 500 }`).

## Playwright (TypeScript) `request` fixture

```typescript
import { test, expect } from '@playwright/test';

test.use({ baseURL: process.env.BASE_URL, extraHTTPHeaders: { Authorization: `Bearer ${process.env.API_TOKEN}` } });

test('creates and reads an order', async ({ request }) => {
  const created = await request.post('/orders', { data: { customer: `qa+${Date.now()}@example.test`, items: [{ sku: 'SKU-1', qty: 2 }] } });
  expect(created.status()).toBe(201);
  const order = await created.json();
  try {
    expect(order).toMatchObject({ status: 'NEW', items: [{ sku: 'SKU-1', qty: 2 }] });
    await expect.poll(async () => (await (await request.get(`/orders/${order.id}`)).json()).status,
                      { timeout: 10_000 }).toBe('CONFIRMED');
  } finally {
    await request.delete(`/orders/${order.id}`);
  }
});
```

This works well when UI tests need API setup in the same project (see `playwright-test-authoring`).

## SuperTest + Jest / Vitest (Node.js services)

```javascript
const request = require('supertest');
const api = request(process.env.BASE_URL);               // or request(app) for in-process tests
const auth = { Authorization: `Bearer ${process.env.API_TOKEN}` };

test('rejects an order without items', async () => {
  const res = await api.post('/orders').set(auth).send({ customer: 'qa@example.test', items: [] }).timeout(10000);
  expect(res.status).toBe(422);
  expect(res.headers['content-type']).toMatch(/application\/problem\+json/);
  expect(res.body).toHaveProperty('title');
});
```

## Other tools worth knowing

| Need | Tool |
|---|---|
| Consumer-driven contracts between microservices | Pact (pact-jvm, pact-js, pact-python) with a Pact Broker |
| Generate many inputs from the OpenAPI spec and find 500s | Schemathesis (`schemathesis run openapi.json --url "$BASE_URL"`) |
| Mock third-party APIs (slow, broken, error responses) | WireMock, MockServer, Prism (spec-based mock) |
| Real databases and brokers in tests | Testcontainers |
| Load and performance | k6 (JavaScript), Gatling (Scala/Java/Kotlin), JMeter, Locust (Python) |
| Lint the OpenAPI spec itself | Spectral |
| HTTP files in the repository, run from an editor or CLI | `.http` files, Bruno, Hurl |
| .NET services | xUnit/NUnit + `HttpClient` / `WebApplicationFactory`, RestSharp |

## Running in CI

Copy `api_check.py` into the project (for example `tools/api_check.py`) so CI does not depend on where the skill is installed.

```yaml
# GitHub Actions
- name: API tests
  env: { BASE_URL: "${{ vars.STAGING_URL }}", API_TOKEN: "${{ secrets.STAGING_API_TOKEN }}" }
  run: python tools/api_check.py run tests/api/orders.json --junit build/api-junit.xml --report build/api-report.md
- uses: actions/upload-artifact@v4
  if: always()
  with: { name: api-report, path: build/ }
```

```yaml
# GitLab CI (BASE_URL and API_TOKEN as masked CI/CD variables)
api-tests:
  stage: test
  script:
    - python tools/api_check.py lint tests/api/orders.json --strict
    - python tools/api_check.py run tests/api/orders.json --junit api-junit.xml --report api-report.md
  artifacts:
    when: always
    reports: { junit: api-junit.xml }
    paths: [api-report.md]
```

- Run `lint --strict` on every merge request. It is fast and needs no server.
- Run the `smoke` tag right after each deploy (with `--read-only` on production), and the full suite against staging.
- Keep the API under test reachable from the runner (VPN, allow-listed runner IPs), and set `HTTPS_PROXY` if a corporate proxy is required.
- Publish the JUnit file so the CI shows per-test results. Fail the pipeline on failures and keep the report as an artifact.
