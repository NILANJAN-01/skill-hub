"""Tests for api_check.py. They start a local HTTP server, so no network access is needed."""
import contextlib
import io
import json
import os
import sys
import tempfile
import threading
import time
import unittest
import urllib.parse
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import api_check as ac  # noqa: E402

FIXTURES = HERE / "fixtures"
TOKEN = "secret-token-123"


def quiet_main(argv):
    """Run the CLI without printing to the test log."""
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return ac.main(argv)


class Api(BaseHTTPRequestHandler):
    orders = {}
    counters = {}
    lock = threading.Lock()

    def log_message(self, *args):
        pass

    def send(self, status, body=None, ctype="application/json", headers=None):
        data = b"" if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
        self.send_response(status)
        if body is not None:
            self.send_header("Content-Type", ctype)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def problem(self, status, title):
        self.send(status, {"type": "about:blank", "title": title, "status": status}, "application/problem+json")

    def authed(self):
        if self.headers.get("Authorization") != "Bearer " + TOKEN:
            self.problem(401, "Unauthorized")
            return False
        return True

    def count(self, key):
        with self.lock:
            self.counters[key] = self.counters.get(key, 0) + 1
            return self.counters[key]

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def route(self):
        url = urllib.parse.urlsplit(self.path)
        q = dict(urllib.parse.parse_qsl(url.query))
        path, m = url.path, self.command
        if path == "/health" and m == "GET":
            return self.send(200, {"status": "ok"})
        if path == "/orders" and m == "POST":
            if not self.authed():
                return
            data = json.loads(self.body() or b"{}")
            if not data.get("items"):
                return self.problem(422, "items must not be empty")
            oid = "ord-%d" % (len(self.orders) + 1)
            self.orders[oid] = {"id": oid, "status": "NEW", "customer": data.get("customer"),
                                "items": data["items"], "total": 19.5, "created": time.time()}
            return self.send(201, self.view(oid), headers={"Location": "/orders/" + oid})
        if path.startswith("/orders/"):
            oid = path.split("/")[2]
            if not self.authed():
                return
            if oid not in self.orders:
                return self.problem(404, "Not found")
            if m == "GET":
                return self.send(200, self.view(oid))
            if m == "DELETE":
                del self.orders[oid]
                return self.send(204)
        if path == "/flaky":  # 503 for the first `fail` calls per key
            if self.count("flaky-" + q.get("key", "")) <= int(q.get("fail", "1")):
                return self.send(503, {"error": "busy"}, headers={"Retry-After": "0"})
            return self.send(200, {"ok": True})
        if path == "/count":
            return self.send(200, {"n": self.counters.get(q.get("key", ""), 0)})
        if path == "/flaky-post" and m == "POST":
            self.count("post-" + q.get("key", ""))
            return self.send(503, {"error": "busy"})
        if path == "/redirect":
            return self.send(302, {"to": "/health"}, headers={"Location": "/health"})
        if path == "/login" and m == "POST":
            form = dict(urllib.parse.parse_qsl(self.body().decode()))
            if form.get("user") == "qa" and form.get("password") == "pw-1234":
                return self.send(200, {"ok": True}, headers={"Set-Cookie": "session=s3ss10n; Path=/; HttpOnly"})
            return self.problem(401, "bad login")
        if path == "/me":
            if "session=s3ss10n" not in (self.headers.get("Cookie") or ""):
                return self.problem(401, "no session")
            return self.send(200, {"user": "qa", "roles": ["tester", "viewer"], "active": True, "age": 1})
        if path == "/slow":
            time.sleep(int(q.get("ms", "200")) / 1000)
            return self.send(200, {"ok": True})
        if path == "/text":
            return self.send(200, b"hello world", "text/plain; charset=utf-8")
        if path == "/echo":
            return self.send(200, {"method": m, "query": q, "headers": dict(self.headers),
                                   "body": self.body().decode() or None})
        return self.problem(404, "no route")

    def view(self, oid):
        o = dict(self.orders[oid])
        if time.time() - o.pop("created") > 0.3:
            o["status"] = "CONFIRMED"
        return o

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = do_HEAD = route


class ServerCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Api)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = "http://127.0.0.1:%d" % cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def run_suite(self, suite, suite_path=None, **kw):
        out = io.StringIO()
        kw.setdefault("environ", {"BASE_URL": self.base, "API_TOKEN": TOKEN})
        runner = ac.Runner(suite, suite_path, out=out, **kw)
        results, seconds = runner.run()
        self.last_output = out.getvalue()
        return {r["name"]: r for r in results}, results, seconds

    def suite(self, *tests, **extra):
        s = {"name": "t", "base_url": "${BASE_URL}", "tests": list(tests)}
        s.update(extra)
        return s


class FixtureSuite(ServerCase):
    def test_orders_suite_passes_end_to_end(self):
        suite = ac.load_structured(FIXTURES / "orders_suite.json")
        self.assertEqual([f for f in ac.lint_suite(suite) if f[0] != "INFO"], [])
        by_name, results, _ = self.run_suite(suite, FIXTURES / "orders_suite.json")
        bad = {n: r["errors"] for n, r in by_name.items() if r["status"] != "passed"}
        self.assertEqual(bad, {}, self.last_output)
        self.assertGreaterEqual(by_name["order becomes confirmed"]["attempts"], 1)
        self.assertEqual(len(results), 8)

    def test_cli_run_writes_junit_and_markdown_and_masks_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            junit, md, js = Path(tmp, "r.xml"), Path(tmp, "r.md"), Path(tmp, "r.json")
            old = dict(os.environ)
            os.environ.update({"BASE_URL": self.base, "API_TOKEN": TOKEN})
            try:
                code = quiet_main(["run", str(FIXTURES / "orders_suite.json"), "--junit", str(junit),
                                "--report", str(md), "--json", str(js), "--verbose"])
            finally:
                os.environ.clear()
                os.environ.update(old)
            self.assertEqual(code, 0)
            root = ET.parse(str(junit)).getroot()
            self.assertEqual((root.get("tests"), root.get("failures"), root.get("errors")), ("8", "0", "0"))
            self.assertIn("| PASSED | create order |", md.read_text(encoding="utf-8"))
            for f in (junit, md, js):
                self.assertNotIn(TOKEN, f.read_text(encoding="utf-8"))


class Assertions(ServerCase):
    def test_failure_messages_are_specific(self):
        t = {"name": "me", "request": {"path": "/me"},
             "expect": {"status": 200, "json": {"$.user": "admin"}}}
        login = {"name": "login", "request": {"method": "POST", "path": "/login",
                                              "form": {"user": "qa", "password": "pw-1234"}},
                 "expect": {"status": 200}}
        by_name, _, _ = self.run_suite(self.suite(login, t))
        self.assertEqual(by_name["login"]["status"], "passed")  # cookie kept for the next request
        self.assertEqual(by_name["me"]["status"], "failed")
        self.assertEqual(by_name["me"]["errors"], ['$.user: expected "admin", got "qa"'])
        self.assertIn("GET %s/me -> 200" % self.base, self.last_output)

    def test_matchers(self):
        login = {"name": "login", "request": {"method": "POST", "path": "/login",
                                              "form": {"user": "qa", "password": "pw-1234"}}, "expect": {"status": 200}}
        good = {"name": "good", "request": {"path": "/me"}, "expect": {"status": "2xx", "json": {
            "$.roles": {"contains": "tester", "len": 2}, "$.roles[-1]": "viewer", "$.age": {"gte": 1, "lt": 2},
            "$.active": True, "$.missing": {"exists": False}, "$.user": {"in": ["qa", "dev"], "regex": "^q"},
            "$.roles.length": 2}}}
        bad = {"name": "bad", "request": {"path": "/me"}, "expect": {"status": 200, "json": {
            "$.active": 1, "$.age": {"type": "string"}, "$.roles": {"not_contains": "tester"}, "$.nope": 3}}}
        by_name, _, _ = self.run_suite(self.suite(login, good, bad))
        self.assertEqual(by_name["good"]["status"], "passed", by_name["good"]["errors"])
        errs = by_name["bad"]["errors"]
        self.assertEqual(len(errs), 4, errs)
        self.assertIn("$.active: expected 1, got true", errs)  # true is not 1

    def test_status_headers_body_and_time(self):
        t1 = {"name": "text", "request": {"path": "/text"}, "expect": {
            "status": 200, "content_type": "text/plain", "body_contains": ["hello"], "body_not_contains": "error",
            "body_regex": "w.rld", "headers": {"Content-Type": {"contains": "utf-8"}, "X-Nope": False}}}
        t2 = {"name": "slow", "request": {"path": "/slow", "query": {"ms": 300}}, "expect": {"status": 200, "max_ms": 50}}
        t3 = {"name": "not json", "request": {"path": "/text"}, "expect": {"status": 200, "json": {"$.a": 1}}}
        by_name, _, _ = self.run_suite(self.suite(t1, t2, t3))
        self.assertEqual(by_name["text"]["status"], "passed", by_name["text"]["errors"])
        self.assertTrue(by_name["slow"]["errors"][0].startswith("time:"))
        self.assertIn("not JSON", by_name["not json"]["errors"][0])

    def test_redirects_followed_or_not(self):
        follow = {"name": "follow", "request": {"path": "/redirect"}, "expect": {"status": 200, "json": {"$.status": "ok"}}}
        raw = {"name": "raw", "request": {"path": "/redirect", "follow_redirects": False},
               "expect": {"status": 302, "headers": {"Location": "/health"}}}
        by_name, _, _ = self.run_suite(self.suite(follow, raw))
        self.assertEqual([r["status"] for r in by_name.values()], ["passed", "passed"], self.last_output)

    def test_inline_schema(self):
        schema = {"type": "object", "required": ["user", "roles"], "additionalProperties": False,
                  "properties": {"user": {"type": "string"}, "roles": {"type": "array", "items": {"enum": ["tester"]}}}}
        login = {"name": "login", "request": {"method": "POST", "path": "/login",
                                              "form": {"user": "qa", "password": "pw-1234"}}, "expect": {"status": 200}}
        t = {"name": "schema", "request": {"path": "/me"}, "expect": {"status": 200, "schema": schema}}
        by_name, _, _ = self.run_suite(self.suite(login, t))
        errs = by_name["schema"]["errors"]
        self.assertTrue(any("$.roles[1]" in e and "viewer" in e for e in errs), errs)
        self.assertTrue(any("$.active: property not allowed" in e for e in errs), errs)

    def test_query_and_typed_variables_in_json_body(self):
        t = {"name": "echo", "request": {"method": "POST", "path": "/echo", "query": {"tag": ["a", "b"], "n": 2},
                                         "json": {"count": "${count}", "label": "n=${count}"}},
             "capture": {"sent": "$.body"}, "expect": {"status": 200, "json": {"$.query.n": "2"}}}
        runner_vars = {"count": 3}
        by_name, _, _ = self.run_suite(self.suite(t, variables=runner_vars))
        self.assertEqual(by_name["echo"]["status"], "passed", by_name["echo"]["errors"])
        self.assertIn("tag=a&tag=b", by_name["echo"]["url"])


class Reliability(ServerCase):
    def test_get_is_retried_on_503_and_reported(self):
        t = {"name": "flaky", "request": {"path": "/flaky", "query": {"key": "g1", "fail": 2}},
             "retry": {"backoff_ms": 1}, "expect": {"status": 200}}
        by_name, results, secs = self.run_suite(self.suite(t))
        self.assertEqual(by_name["flaky"]["status"], "passed")
        self.assertEqual(by_name["flaky"]["retries"], 2)
        self.assertIn("2 retries", ac.summarize(results, secs)[2])

    def test_no_retry_exposes_flakiness(self):
        t = {"name": "flaky", "request": {"path": "/flaky", "query": {"key": "g2"}}, "expect": {"status": 200}}
        by_name, _, _ = self.run_suite(self.suite(t), no_retry=True)
        self.assertEqual(by_name["flaky"]["status"], "failed")

    def test_post_is_not_retried_without_idempotency_key(self):
        plain = {"name": "plain", "request": {"method": "POST", "path": "/flaky-post", "query": {"key": "p1"}},
                 "retry": {"backoff_ms": 1}, "expect": {"status": 201}}
        keyed = {"name": "keyed", "request": {"method": "POST", "path": "/flaky-post", "query": {"key": "p2"},
                                              "headers": {"Idempotency-Key": "${$uuid}"}},
                 "retry": {"backoff_ms": 1}, "expect": {"status": 201}}
        self.run_suite(self.suite(plain, keyed))
        self.assertEqual(Api.counters["post-p1"], 1)
        self.assertEqual(Api.counters["post-p2"], 3)

    def test_expected_503_is_not_retried(self):
        t = {"name": "maint", "request": {"path": "/flaky", "query": {"key": "g3", "fail": 5}}, "expect": {"status": 503}}
        by_name, _, _ = self.run_suite(self.suite(t))
        self.assertEqual((by_name["maint"]["status"], by_name["maint"]["retries"]), ("passed", 0))

    def test_poll_gives_up_with_a_clear_message(self):
        t = {"name": "never", "request": {"path": "/health"}, "poll": {"timeout_ms": 300, "interval_ms": 100},
             "expect": {"status": 200, "json": {"$.status": "done"}}}
        by_name, _, _ = self.run_suite(self.suite(t))
        r = by_name["never"]
        self.assertEqual(r["status"], "failed")
        self.assertGreaterEqual(r["attempts"], 2)
        self.assertIn("still failing after", r["errors"][-1])

    def test_dependencies_and_cleanup(self):
        create = {"name": "create", "request": {"method": "POST", "path": "/orders",
                                                "headers": {"Authorization": "Bearer ${API_TOKEN}"},
                                                "json": {"items": []}},
                  "expect": {"status": 201}, "capture": {"order_id": "$.id"}}
        read = {"name": "read", "depends_on": ["create"], "request": {"path": "/orders/${order_id}"},
                "expect": {"status": 200}}
        cleanup = {"name": "cleanup", "always_run": True,
                   "request": {"method": "DELETE", "path": "/orders/${order_id}"}, "expect": {"status": 204}}
        missing = {"name": "missing", "request": {"path": "/x/${nope}"}, "expect": {"status": 200}}
        by_name, _, _ = self.run_suite(self.suite(create, read, cleanup, missing))
        self.assertEqual(by_name["create"]["status"], "failed")
        self.assertEqual(by_name["read"]["status"], "skipped")
        self.assertIn("depends on 'create'", by_name["read"]["reason"])
        self.assertEqual(by_name["cleanup"]["status"], "skipped")
        self.assertEqual(by_name["missing"]["status"], "error")
        self.assertIn("${nope} is not defined", by_name["missing"]["errors"][0])

    def test_fail_fast_still_runs_cleanup(self):
        a = {"name": "a", "request": {"path": "/health"}, "expect": {"status": 500}}
        b = {"name": "b", "request": {"path": "/health"}, "expect": {"status": 200}}
        c = {"name": "c", "always_run": True, "request": {"path": "/health"}, "expect": {"status": 200}}
        by_name, _, _ = self.run_suite(self.suite(a, b, c), fail_fast=True)
        self.assertEqual([by_name[n]["status"] for n in "abc"], ["failed", "skipped", "passed"])

    def test_read_only_and_allowed_hosts(self):
        post = {"name": "post", "request": {"method": "POST", "path": "/orders", "json": {}}, "expect": {"status": 201}}
        get = {"name": "get", "request": {"path": "/health"}, "expect": {"status": 200}}
        by_name, _, _ = self.run_suite(self.suite(post, get), read_only=True)
        self.assertEqual((by_name["post"]["status"], by_name["get"]["status"]), ("skipped", "passed"))
        by_name, _, _ = self.run_suite(self.suite(get, allowed_hosts=["api.staging.example.com"]))
        self.assertEqual(by_name["get"]["status"], "error")
        self.assertIn("not in allowed_hosts", by_name["get"]["errors"][0])

    def test_connection_refused_is_an_error_not_a_crash(self):
        t = {"name": "down", "request": {"url": "http://127.0.0.1:9/x", "timeout": 2},
             "retry": {"attempts": 1}, "expect": {"status": 200}}
        by_name, _, _ = self.run_suite(self.suite(t))
        self.assertEqual(by_name["down"]["status"], "error")
        self.assertIn("request failed", by_name["down"]["errors"][0])

    def test_secrets_are_masked(self):
        t = {"name": "echo", "request": {"path": "/echo", "auth": {"bearer": "${API_TOKEN}"}},
             "expect": {"status": 200, "json": {"$.method": "POST"}}}
        by_name, _, _ = self.run_suite(self.suite(t), verbose=True)
        self.assertEqual(by_name["echo"]["status"], "failed")
        self.assertNotIn(TOKEN, self.last_output)
        self.assertNotIn(TOKEN, json.dumps(by_name))
        self.assertIn("***", by_name["echo"]["response_excerpt"])


class Lint(unittest.TestCase):
    def levels(self, suite):
        return [(lvl, msg) for lvl, _, msg in ac.lint_suite(suite)]

    def test_detects_common_mistakes(self):
        suite = {"name": "x", "base_url": "http://api.example.com", "tests": [
            {"name": "a", "request": {"method": "GET", "path": "/a/${later}", "headers": {"Authorization": "Bearer abc"}},
             "expect": {"stauts": 200}},
            {"name": "a", "request": {"method": "POST", "path": "/b"}, "retry": {"unsafe": True},
             "expect": {"status": 201}, "capture": {"later": "$.id"}, "depends_on": ["zzz"]},
            {"name": "c", "request": {"method": "FETCH"}},
        ]}
        text = "\n".join("%s %s" % f for f in self.levels(suite))
        for needle in ("unknown key 'stauts' (did you mean 'status'?)", "literal secret", "duplicate test name",
                       "captured by a later test", "Idempotency-Key", "depends_on 'zzz'", "unknown HTTP method",
                       "needs 'path'", "checks nothing", "plain http://", "allowed_hosts", "no DELETE test"):
            self.assertIn(needle, text)

    def test_example_and_fixture_are_clean(self):
        self.assertEqual([f for f in ac.lint_suite(ac.EXAMPLE) if f[0] != "INFO"], [])

    def test_run_refuses_a_broken_suite(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp, "s.json")
            p.write_text(json.dumps({"tests": [{"name": "a", "request": {"path": "/"}, "expect": {"stauts": 1}}]}))
            self.assertEqual(quiet_main(["run", str(p), "--base-url", "http://127.0.0.1:9"]), 2)
            self.assertEqual(quiet_main(["lint", str(p)]), 1)

    def test_bad_json_reports_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp, "s.json")
            p.write_text('{"tests": [\n  {"name": "a",}\n]}')
            with self.assertRaises(ac.SuiteError) as cm:
                ac.load_structured(p)
            self.assertIn("line 2", str(cm.exception))


class Plan(unittest.TestCase):
    def test_plan_from_openapi(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp, "suite.json")
            self.assertEqual(quiet_main(["plan", str(FIXTURES / "openapi.json"), "--out", str(out)]), 0)
            suite = json.loads(out.read_text(encoding="utf-8"))
        names = [t["name"] for t in suite["tests"]]
        self.assertEqual(names[:4], ["getHealth", "createOrder", "createOrder without credentials",
                                     "createOrder rejects an empty body"])
        self.assertIn("getOrder returns 404 for an unknown id", names)
        create = suite["tests"][1]
        self.assertEqual(create["expect"]["status"], 201)
        self.assertEqual(create["request"]["headers"], {"Authorization": "Bearer ${API_TOKEN}"})
        self.assertEqual(create["request"]["json"]["items"], [{"sku": "SKU-1", "qty": 1}])
        self.assertTrue(create["expect"]["schema"]["$ref"].endswith(
            "openapi.json#/paths/~1orders/post/responses/201/content/application~1json/schema"))
        self.assertNotIn("Authorization", suite["tests"][0]["request"].get("headers", {}))  # security: []
        self.assertEqual([f for f in ac.lint_suite(suite) if f[0] == "ERROR"], [])

    def test_rejects_swagger2(self):
        with self.assertRaises(ac.SuiteError):
            ac.plan_from_openapi({"swagger": "2.0"}, "x.json")


class Helpers(unittest.TestCase):
    def test_resolve_path(self):
        doc = {"a": {"b": [1, {"c d": 2}]}, "s": "abc"}
        self.assertEqual(ac.resolve_path(doc, "$.a.b[1]['c d']"), (True, 2))
        self.assertEqual(ac.resolve_path(doc, "$.a.b[-2]"), (True, 1))
        self.assertEqual(ac.resolve_path(doc, "$.a.b.length"), (True, 2))
        self.assertEqual(ac.resolve_path(doc, "$.a.x"), (False, None))
        self.assertEqual(ac.resolve_path(doc, "$.a.b[5]"), (False, None))
        with self.assertRaises(ac.SuiteError):
            ac.resolve_path(doc, "a.b")

    def test_json_equal_and_status(self):
        self.assertFalse(ac.json_equal(True, 1))
        self.assertTrue(ac.json_equal(1, 1.0))
        self.assertTrue(ac.json_equal({"a": [1]}, {"a": [1.0]}))
        self.assertTrue(ac.status_ok(204, "2xx") and ac.status_ok(404, [400, 404]) and not ac.status_ok(200, 201))

    def test_schema_formats_and_combinators(self):
        sc = ac.SchemaChecker(FIXTURES)
        s = {"type": "object", "properties": {"when": {"type": "string", "format": "date-time"},
                                              "n": {"oneOf": [{"type": "integer"}, {"type": "string"}]},
                                              "x": {"type": "string", "nullable": True}}}
        self.assertEqual(sc.check({"when": "2026-01-01T10:00:00Z", "n": 1, "x": None}, s), [])
        self.assertEqual(len(sc.check({"when": "yesterday", "n": 1.5}, s)), 2)
        errs = sc.check({"id": "1", "status": "LOST", "items": [], "total": -1},
                        {"$ref": "openapi.json#/components/schemas/Order"})
        self.assertEqual(len(errs), 2, errs)

    def test_env_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp, ".env")
            p.write_text("# c\nexport BASE_URL=http://x\nAPI_TOKEN='a b'\n\n")
            self.assertEqual(ac.load_env_file(p), {"BASE_URL": "http://x", "API_TOKEN": "a b"})


if __name__ == "__main__":
    unittest.main()
