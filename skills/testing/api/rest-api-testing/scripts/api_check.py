#!/usr/bin/env python3
"""Run, lint and generate REST API test suites for web applications (Python standard library only).

Usage:
  python api_check.py run SUITE.json [--env FILE] [--var NAME=VALUE] [--base-url URL] [--tag T] [--skip-tag T]
                      [--only NAME] [--read-only] [--fail-fast] [--no-retry] [--junit FILE] [--json FILE]
                      [--report FILE] [--insecure] [--verbose]
  python api_check.py lint SUITE.json [--strict]
  python api_check.py plan OPENAPI.json [--out SUITE.json]
  python api_check.py example [--out SUITE.json]

Exit codes: 0 = everything passed (or no lint errors), 1 = test failures or lint errors, 2 = bad input.
The suite format is described in references/suite-format.md.
"""
from __future__ import annotations

import argparse
import base64
import copy
import difflib
import fnmatch
import http.cookiejar
import json
import os
import random
import re
import socket
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yaml_lite  # noqa: E402  (bundled next to this script)

VERSION = "1.0"
METHODS = {"GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE", "TRACE"}
IDEMPOTENT = {"GET", "HEAD", "OPTIONS", "PUT", "DELETE", "TRACE"}
WRITES = {"POST", "PUT", "PATCH", "DELETE"}
DEFAULT_RETRY = {"attempts": 3, "backoff_ms": 250, "on_status": [429, 502, 503, 504], "unsafe": False}
DEFAULT_TIMEOUT = 15.0
MAX_WAIT_S = 30.0
SECRET_NAME = re.compile(r"token|secret|passw|pwd|api[_-]?key|auth|cookie|session|credential|private", re.I)
SECRET_HEADERS = {"authorization", "proxy-authorization", "cookie", "set-cookie", "x-api-key", "api-key"}
VAR = re.compile(r"\$\{(\$?[A-Za-z_][A-Za-z0-9_.\-]*)\}")
BUILTINS = {"$run_id", "$uuid", "$timestamp", "$now", "$rand"}

SUITE_KEYS = {"$schema", "name", "description", "base_url", "defaults", "variables", "allowed_hosts", "tests"}
DEFAULTS_KEYS = {"headers", "query", "timeout", "follow_redirects", "retry", "auth"}
TEST_KEYS = {"name", "description", "tags", "request", "expect", "capture", "depends_on", "retry", "poll",
             "always_run", "skip", "read_only_safe"}
REQUEST_KEYS = {"method", "path", "url", "headers", "query", "json", "form", "body", "timeout",
                "follow_redirects", "auth"}
EXPECT_KEYS = {"status", "headers", "content_type", "max_ms", "json", "schema", "body_contains",
               "body_not_contains", "body_regex", "no_headers"}
RETRY_KEYS = {"attempts", "backoff_ms", "on_status", "unsafe"}
POLL_KEYS = {"timeout_ms", "interval_ms"}
AUTH_KEYS = {"bearer", "basic", "header"}
MATCHERS = {"eq", "ne", "type", "regex", "gt", "gte", "lt", "lte", "len", "min_len", "max_len", "exists",
            "in", "contains", "not_contains", "schema"}
FORMATS = {
    "date-time": re.compile(r"^\d{4}-\d{2}-\d{2}[Tt ]\d{2}:\d{2}:\d{2}(\.\d+)?([Zz]|[+-]\d{2}:?\d{2})$"),
    "date": re.compile(r"^\d{4}-\d{2}-\d{2}$"),
    "email": re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$"),
    "uuid": re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"),
    "uri": re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:\S+$"),
    "ipv4": re.compile(r"^((25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(25[0-5]|2[0-4]\d|1?\d?\d)$"),
}


class SuiteError(Exception):
    """The suite, an input file or a CLI option is wrong (exit code 2)."""


class MissingVar(SuiteError):
    def __init__(self, name):
        super().__init__("variable ${%s} is not defined (set it in 'variables', --env, --var or the environment, "
                         "or capture it in an earlier test)" % name)
        self.name = name


class TransportError(Exception):
    """No HTTP response: DNS, connection, TLS or timeout problem."""


# ============================================================================ helpers
def load_structured(path):
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as e:
        raise SuiteError("cannot read %s: %s" % (path, e.strerror or e))
    if path.suffix.lower() in (".yaml", ".yml"):
        try:
            return yaml_lite.load(text)  # bundled reader: no PyYAML needed
        except yaml_lite.YamlError as e:
            raise SuiteError("%s: %s (or convert the file to JSON)" % (path, e))
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise SuiteError("%s: invalid JSON at line %d column %d: %s" % (path, e.lineno, e.colno, e.msg))


def load_env_file(path):
    path = Path(path)
    if path.suffix.lower() == ".json":
        data = load_structured(path)
        if not isinstance(data, dict):
            raise SuiteError("%s: an env JSON file must be an object" % path)
        return {str(k): v for k, v in data.items()}
    out = {}
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError as e:
        raise SuiteError("cannot read %s: %s" % (path, e.strerror or e))
    for n, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            raise SuiteError("%s:%d: expected NAME=VALUE" % (path, n))
        k, v = line.split("=", 1)
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        out[k.strip()] = v
    return out


def json_type(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, int):
        return "integer"
    if isinstance(v, float):
        return "number"
    if isinstance(v, str):
        return "string"
    if isinstance(v, list):
        return "array"
    if isinstance(v, dict):
        return "object"
    return type(v).__name__


def type_ok(v, t):
    actual = json_type(v)
    if t == "number":
        return actual in ("integer", "number")
    if t == "integer":
        return actual == "integer" or (actual == "number" and float(v).is_integer())
    return actual == t


def json_equal(a, b):
    """Equality that keeps true != 1 and 1 == 1.0, like JSON."""
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(json_equal(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(json_equal(x, y) for x, y in zip(a, b))
    return type(a) is type(b) and a == b


def short(v, limit=200):
    s = json.dumps(v, ensure_ascii=False, default=str)
    return s if len(s) <= limit else s[:limit] + "...(%d chars)" % len(s)


PATH_TOKEN = re.compile(r"\.([A-Za-z_$][\w$\-]*)|\[(-?\d+)\]|\[['\"]([^'\"]+)['\"]\]")


def resolve_path(doc, path):
    """Resolve a small JSONPath ($.a.b[0]['c d'], .length on arrays/strings/objects). Returns (found, value)."""
    if not isinstance(path, str) or not path.startswith("$"):
        raise SuiteError("JSON path %r must start with '$'" % (path,))
    cur, pos, rest = doc, 0, path[1:]
    while pos < len(rest):
        m = PATH_TOKEN.match(rest, pos)
        if not m:
            raise SuiteError("bad JSON path %r near %r" % (path, rest[pos:]))
        pos = m.end()
        key, idx, qkey = m.groups()
        if idx is not None:
            i = int(idx)
            if not isinstance(cur, list) or not -len(cur) <= i < len(cur):
                return False, None
            cur = cur[i]
            continue
        k = key if key is not None else qkey
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        elif key == "length" and isinstance(cur, (list, str, dict)):
            cur = len(cur)
        else:
            return False, None
    return True, cur


def json_pointer(doc, pointer, where=""):
    p = pointer[1:] if pointer.startswith("#") else pointer
    if p == "":
        return doc
    if not p.startswith("/"):
        raise SuiteError("bad JSON pointer %r%s" % (pointer, where))
    for part in p[1:].split("/"):
        part = urllib.parse.unquote(part).replace("~1", "/").replace("~0", "~")
        if isinstance(doc, list) and part.lstrip("-").isdigit() and int(part) < len(doc):
            doc = doc[int(part)]
        elif isinstance(doc, dict) and part in doc:
            doc = doc[part]
        else:
            raise SuiteError("$ref %r not found%s" % (pointer, where))
    return doc


def pointer_escape(part):
    return str(part).replace("~", "~0").replace("/", "~1")


# ============================================================================ JSON Schema (subset)
class SchemaChecker:
    """Validates JSON against a practical JSON Schema / OpenAPI 3.x subset, with local and file $refs."""

    def __init__(self, base_dir):
        self.base_dir = Path(base_dir)
        self.cache = {}

    def load(self, path):
        path = Path(path).resolve()
        if path not in self.cache:
            self.cache[path] = load_structured(path)
        return self.cache[path]

    def resolve(self, ref, root, root_dir):
        file, _, frag = ref.partition("#")
        if file:
            doc_path = (root_dir / file)
            root, root_dir = self.load(doc_path), doc_path.resolve().parent
        return json_pointer(root, "#" + frag, " (in %s)" % (file or "the same document")), root, root_dir

    def check(self, value, schema, root=None, root_dir=None):
        errors = []
        self._v(value, schema, schema if root is None else root, root_dir or self.base_dir, "$", errors, 0)
        return errors

    def _v(self, value, schema, root, root_dir, path, errors, depth):
        if depth > 64:
            errors.append("%s: schema nesting too deep (recursive $ref?)" % path)
            return
        if schema is True or not isinstance(schema, dict):
            return
        if schema is False:
            errors.append("%s: no value allowed here" % path)
            return
        if "$ref" in schema:
            sub, r, d = self.resolve(schema["$ref"], root, root_dir)
            self._v(value, sub, r, d, path, errors, depth + 1)
            return
        if value is None and schema.get("nullable"):
            return
        t = schema.get("type")
        if t is not None:
            types = t if isinstance(t, list) else [t]
            if not any(type_ok(value, x) for x in types):
                errors.append("%s: expected %s, got %s %s" % (path, "/".join(types), json_type(value), short(value, 80)))
                return
        if "enum" in schema and not any(json_equal(value, e) for e in schema["enum"]):
            errors.append("%s: %s is not one of %s" % (path, short(value, 80), short(schema["enum"], 120)))
        if "const" in schema and not json_equal(value, schema["const"]):
            errors.append("%s: expected constant %s, got %s" % (path, short(schema["const"]), short(value, 80)))
        if isinstance(value, dict):
            for req in schema.get("required", []):
                if req not in value:
                    errors.append("%s: required property '%s' is missing" % (path, req))
            props = schema.get("properties", {})
            for k, v in value.items():
                child = "%s.%s" % (path, k)
                if k in props:
                    self._v(v, props[k], root, root_dir, child, errors, depth + 1)
                else:
                    extra = schema.get("additionalProperties", True)
                    if extra is False:
                        errors.append("%s: property not allowed by the schema" % child)
                    elif isinstance(extra, dict):
                        self._v(v, extra, root, root_dir, child, errors, depth + 1)
            if "minProperties" in schema and len(value) < schema["minProperties"]:
                errors.append("%s: fewer than %d properties" % (path, schema["minProperties"]))
        if isinstance(value, list):
            if "minItems" in schema and len(value) < schema["minItems"]:
                errors.append("%s: %d items, at least %d expected" % (path, len(value), schema["minItems"]))
            if "maxItems" in schema and len(value) > schema["maxItems"]:
                errors.append("%s: %d items, at most %d expected" % (path, len(value), schema["maxItems"]))
            if schema.get("uniqueItems"):
                seen = []
                for item in value:
                    if any(json_equal(item, s) for s in seen):
                        errors.append("%s: items are not unique (%s repeats)" % (path, short(item, 60)))
                        break
                    seen.append(item)
            if isinstance(schema.get("items"), dict):
                for i, item in enumerate(value):
                    self._v(item, schema["items"], root, root_dir, "%s[%d]" % (path, i), errors, depth + 1)
        if isinstance(value, str):
            if "minLength" in schema and len(value) < schema["minLength"]:
                errors.append("%s: shorter than %d characters" % (path, schema["minLength"]))
            if "maxLength" in schema and len(value) > schema["maxLength"]:
                errors.append("%s: longer than %d characters" % (path, schema["maxLength"]))
            if "pattern" in schema and not re.search(schema["pattern"], value):
                errors.append("%s: %s does not match pattern %s" % (path, short(value, 80), schema["pattern"]))
            fmt = FORMATS.get(schema.get("format", ""))
            if fmt and not fmt.match(value):
                errors.append("%s: %s is not a valid %s" % (path, short(value, 80), schema["format"]))
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if "minimum" in schema:
                excl = schema.get("exclusiveMinimum") is True
                if value < schema["minimum"] or (excl and value == schema["minimum"]):
                    errors.append("%s: %s is below the minimum %s" % (path, value, schema["minimum"]))
            if "maximum" in schema:
                excl = schema.get("exclusiveMaximum") is True
                if value > schema["maximum"] or (excl and value == schema["maximum"]):
                    errors.append("%s: %s is above the maximum %s" % (path, value, schema["maximum"]))
            for key, bad in (("exclusiveMinimum", lambda a, b: a <= b), ("exclusiveMaximum", lambda a, b: a >= b)):
                lim = schema.get(key)
                if isinstance(lim, (int, float)) and not isinstance(lim, bool) and bad(value, lim):
                    errors.append("%s: %s violates %s %s" % (path, value, key, lim))
            mult = schema.get("multipleOf")
            if mult and abs(value / mult - round(value / mult)) > 1e-9:
                errors.append("%s: %s is not a multiple of %s" % (path, value, mult))
        for sub in schema.get("allOf", []):
            self._v(value, sub, root, root_dir, path, errors, depth + 1)
        for key in ("anyOf", "oneOf"):
            if key in schema:
                ok = 0
                for sub in schema[key]:
                    e = []
                    self._v(value, sub, root, root_dir, path, e, depth + 1)
                    ok += not e
                if (key == "anyOf" and ok == 0) or (key == "oneOf" and ok != 1):
                    errors.append("%s: matches %d of the %s schemas" % (path, ok, key))
        if "not" in schema:
            e = []
            self._v(value, schema["not"], root, root_dir, path, e, depth + 1)
            if not e:
                errors.append("%s: must not match the 'not' schema" % path)


# ============================================================================ matchers
def check_value(found, value, expected, where, schemas):
    """Compare one resolved value with an expectation (literal or matcher object). Returns a list of errors."""
    if isinstance(expected, dict) and expected and set(expected) <= MATCHERS:
        errors = []
        if "exists" in expected:
            if bool(expected["exists"]) != found:
                return ["%s: expected %s" % (where, "to exist" if expected["exists"] else "to be absent")]
            if not found:
                return []
        if not found:
            return ["%s: not found in the response" % where]
        for op, arg in expected.items():
            err = None
            num = isinstance(value, (int, float)) and not isinstance(value, bool)
            if op == "eq" and not json_equal(value, arg):
                err = "expected %s, got %s" % (short(arg), short(value))
            elif op == "ne" and json_equal(value, arg):
                err = "expected anything but %s" % short(arg)
            elif op == "type":
                types = arg if isinstance(arg, list) else [arg]
                if not any(type_ok(value, t) for t in types):
                    err = "expected type %s, got %s %s" % ("/".join(types), json_type(value), short(value, 80))
            elif op == "regex" and not (isinstance(value, str) and re.search(arg, value)):
                err = "%s does not match /%s/" % (short(value), arg)
            elif op in ("gt", "gte", "lt", "lte"):
                okfn = {"gt": lambda a, b: a > b, "gte": lambda a, b: a >= b,
                        "lt": lambda a, b: a < b, "lte": lambda a, b: a <= b}[op]
                if not num or not okfn(value, arg):
                    err = "expected %s %s, got %s" % (op, arg, short(value))
            elif op in ("len", "min_len", "max_len"):
                if not isinstance(value, (list, str, dict)):
                    err = "%s needs an array, string or object, got %s" % (op, json_type(value))
                elif (op == "len" and len(value) != arg) or (op == "min_len" and len(value) < arg) or \
                        (op == "max_len" and len(value) > arg):
                    err = "length %d, expected %s %s" % (len(value), op, arg)
            elif op == "in" and not any(json_equal(value, a) for a in arg):
                err = "%s is not one of %s" % (short(value), short(arg))
            elif op in ("contains", "not_contains"):
                if isinstance(value, str):
                    has = isinstance(arg, str) and arg in value
                elif isinstance(value, list):
                    has = any(json_equal(x, arg) for x in value)
                elif isinstance(value, dict):
                    has = arg in value
                else:
                    has = False
                if has != (op == "contains"):
                    err = "%s %s %s" % (short(value), "does not contain" if op == "contains" else "contains", short(arg))
            elif op == "schema":
                errs = schemas.check(value, arg)
                errors.extend("%s%s" % (where, e[1:]) for e in errs)
            if err:
                errors.append("%s: %s" % (where, err))
        return errors
    if not found:
        return ["%s: not found in the response (expected %s)" % (where, short(expected))]
    if not json_equal(value, expected):
        return ["%s: expected %s, got %s" % (where, short(expected), short(value))]
    return []


def status_ok(actual, expected):
    for e in expected if isinstance(expected, list) else [expected]:
        if isinstance(e, int) and not isinstance(e, bool) and actual == e:
            return True
        if isinstance(e, str):
            e = e.strip().lower()
            if re.fullmatch(r"[1-5]xx", e) and actual // 100 == int(e[0]):
                return True
            if e.isdigit() and actual == int(e):
                return True
    return False


def media_type(value):
    return (value or "").split(";", 1)[0].strip().lower()


# ============================================================================ HTTP
class Response:
    def __init__(self, status, headers, body, ms, url):
        self.status, self.headers, self.body, self.ms, self.url = status, headers, body, ms, url
        self._json, self._json_error, self._parsed = None, None, False

    @property
    def text(self):
        charset = "utf-8"
        m = re.search(r"charset=([\w\-]+)", self.header("content-type") or "", re.I)
        if m:
            charset = m.group(1)
        try:
            return self.body.decode(charset, errors="replace")
        except LookupError:
            return self.body.decode("utf-8", errors="replace")

    def header(self, name):
        return self.headers.get(name) if self.headers is not None else None

    def json(self):
        if not self._parsed:
            self._parsed = True
            try:
                self._json = json.loads(self.text) if self.body else None
                if not self.body:
                    self._json_error = "the body is empty"
            except ValueError as e:
                self._json_error = "the body is not JSON (%s): %s" % (e, short(self.text, 120))
        return self._json


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Http:
    def __init__(self, insecure=False):
        self.cookies = http.cookiejar.CookieJar()
        ctx = ssl.create_default_context()
        if insecure:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        common = [urllib.request.HTTPCookieProcessor(self.cookies), urllib.request.HTTPSHandler(context=ctx)]
        self.follow = urllib.request.build_opener(*common)
        self.nofollow = urllib.request.build_opener(*(common + [_NoRedirect()]))

    def send(self, method, url, headers, data, timeout, follow):
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        opener = self.follow if follow else self.nofollow
        start = time.perf_counter()
        try:
            resp = opener.open(req, timeout=timeout)
            with resp:
                body = resp.read()
                return Response(resp.status, resp.headers, body, (time.perf_counter() - start) * 1000, resp.geturl())
        except urllib.error.HTTPError as e:
            try:
                body = e.read()
            except Exception:  # body may be unreadable after a reset
                body = b""
            finally:
                e.close()
            return Response(e.code, e.headers, body, (time.perf_counter() - start) * 1000, url)
        except urllib.error.URLError as e:
            raise TransportError(str(e.reason))
        except (socket.timeout, TimeoutError):
            raise TransportError("timed out after %.0f s" % timeout)
        except (ConnectionError, ssl.SSLError, OSError) as e:
            raise TransportError("%s: %s" % (type(e).__name__, e))


# ============================================================================ runner
class Runner:
    def __init__(self, suite, suite_path=None, env_file=None, cli_vars=None, base_url=None, read_only=False,
                 fail_fast=False, no_retry=False, insecure=False, verbose=False, out=None, environ=None):
        if not isinstance(suite, dict) or not isinstance(suite.get("tests"), list):
            raise SuiteError("the suite must be a JSON object with a 'tests' list")
        self.suite = suite
        self.base_dir = Path(suite_path).resolve().parent if suite_path else Path.cwd()
        self.defaults = suite.get("defaults") or {}
        self.layers = [{}, cli_vars or {}, dict(os.environ if environ is None else environ), env_file or {},
                       suite.get("variables") or {}]
        self.captured = self.layers[0]
        self.base_url_override = base_url
        self.read_only, self.fail_fast, self.no_retry, self.verbose = read_only, fail_fast, no_retry, verbose
        self.http = Http(insecure)
        self.schemas = SchemaChecker(self.base_dir)
        self.out = out or sys.stdout
        self.secrets = set()
        self.run_id = uuid.uuid4().hex[:8]
        self.allowed = [h.lower() for h in suite.get("allowed_hosts") or []]

    # ---------------------------------------------------------------- variables
    def lookup(self, name, depth):
        if name.startswith("$"):
            if name == "$run_id":
                return self.run_id
            if name == "$uuid":
                return str(uuid.uuid4())
            if name == "$timestamp":
                return int(time.time())
            if name == "$now":
                return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            if name == "$rand":
                return random.randint(100000, 999999)
            raise SuiteError("unknown built-in variable ${%s} (known: %s)" % (name, ", ".join(sorted(BUILTINS))))
        for i, layer in enumerate(self.layers):
            if name in layer:
                value = layer[name]
                if i == 4 and isinstance(value, str) and depth < 10:  # suite variables may use other variables
                    value = self.sub(value, depth + 1)
                if SECRET_NAME.search(name) and isinstance(value, str) and len(value) >= 4:
                    self.secrets.add(value)
                return value
        raise MissingVar(name)

    def sub(self, obj, depth=0):
        if isinstance(obj, str):
            m = VAR.fullmatch(obj)
            if m:  # keep the type of a whole-string variable (numbers, booleans, objects in JSON bodies)
                return self.lookup(m.group(1), depth)
            return VAR.sub(lambda mm: self.text_of(self.lookup(mm.group(1), depth)), obj)
        if isinstance(obj, list):
            return [self.sub(x, depth) for x in obj]
        if isinstance(obj, dict):
            return {k: self.sub(v, depth) for k, v in obj.items()}
        return obj

    @staticmethod
    def text_of(v):
        return v if isinstance(v, str) else json.dumps(v)

    def mask(self, text):
        if not isinstance(text, str):
            return text
        for s in sorted(self.secrets, key=len, reverse=True):
            text = text.replace(s, "***")
        return text

    # ---------------------------------------------------------------- request building
    def prepare(self, test):
        req = test.get("request") or {}
        if not isinstance(req, dict):
            raise SuiteError("'request' must be an object")
        method = str(req.get("method", "GET")).upper()
        if method not in METHODS:
            raise SuiteError("unknown HTTP method %r" % method)
        headers = {}
        auth = self.sub(req.get("auth", self.defaults.get("auth")))  # "auth": null turns default auth off
        if auth:
            if "bearer" in auth:
                headers["Authorization"] = "Bearer %s" % auth["bearer"]
            elif "basic" in auth:
                user, pwd = auth["basic"]
                token = base64.b64encode(("%s:%s" % (user, pwd)).encode()).decode()
                headers["Authorization"] = "Basic " + token
                self.secrets.add(str(pwd))
            elif "header" in auth:
                for k, v in auth["header"].items():
                    headers[k] = self.text_of(v)
        for src in (self.defaults.get("headers") or {}, req.get("headers") or {}):
            for k, v in self.sub(src).items():  # later wins, case-insensitive; null removes the header
                for old in [h for h in headers if h.lower() == k.lower()]:
                    del headers[old]
                if v is not None:
                    headers[k] = self.text_of(v)
        for k, v in headers.items():
            if k.lower() in SECRET_HEADERS and len(v) >= 4:
                self.secrets.add(v)
                if " " in v:
                    self.secrets.add(v.split(" ", 1)[1])
        headers.setdefault("User-Agent", "api-check/%s" % VERSION)
        url = self.sub(req.get("url") or req.get("path") or "")
        if not re.match(r"^https?://", url, re.I):
            base = self.base_url_override or self.sub(self.suite.get("base_url") or "")
            if not base:
                raise SuiteError("no base_url: set it in the suite or pass --base-url")
            url = base.rstrip("/") + "/" + url.lstrip("/") if url else base
        query = {}
        query.update(self.sub(self.defaults.get("query") or {}))
        query.update(self.sub(req.get("query") or {}))
        if query:
            pairs = []
            for k, v in query.items():
                for item in (v if isinstance(v, list) else [v]):
                    pairs.append((k, self.text_of(item) if not isinstance(item, str) else item))
            url += ("&" if urllib.parse.urlsplit(url).query else "?") + urllib.parse.urlencode(pairs)
        bodies = [k for k in ("json", "form", "body") if k in req]
        if len(bodies) > 1:
            raise SuiteError("use only one of json, form or body (found %s)" % ", ".join(bodies))
        data, lower = None, {k.lower() for k in headers}
        if "json" in req:
            data = json.dumps(self.sub(req["json"]), ensure_ascii=False).encode("utf-8")
            if "content-type" not in lower:
                headers["Content-Type"] = "application/json"
        elif "form" in req:
            data = urllib.parse.urlencode(self.sub(req["form"]), doseq=True).encode("utf-8")
            if "content-type" not in lower:
                headers["Content-Type"] = "application/x-www-form-urlencoded"
        elif "body" in req:
            b = self.sub(req["body"])
            data = (b if isinstance(b, str) else json.dumps(b)).encode("utf-8")
        timeout = float(req.get("timeout", self.defaults.get("timeout", DEFAULT_TIMEOUT)))
        follow = bool(req.get("follow_redirects", self.defaults.get("follow_redirects", True)))
        expect = self.sub(test.get("expect") or {})
        return {"method": method, "url": url, "headers": headers, "data": data, "timeout": timeout,
                "follow": follow, "expect": expect}

    def host_allowed(self, url):
        host = (urllib.parse.urlsplit(url).hostname or "").lower()
        return not self.allowed or any(fnmatch.fnmatch(host, pat) for pat in self.allowed), host

    # ---------------------------------------------------------------- sending
    def retry_policy(self, test, p):
        pol = dict(DEFAULT_RETRY)
        pol.update(self.defaults.get("retry") or {})
        pol.update(test.get("retry") or {})
        safe = p["method"] in IDEMPOTENT or any(k.lower() == "idempotency-key" for k in p["headers"]) or pol["unsafe"]
        attempts = 1 if (self.no_retry or not safe) else max(1, int(pol["attempts"]))
        expected = p["expect"].get("status")
        on_status = [s for s in pol["on_status"] if expected is None or not status_ok(s, expected)]
        return attempts, int(pol["backoff_ms"]), on_status

    def send_with_retry(self, test, p):
        attempts, backoff, on_status = self.retry_policy(test, p)
        last_exc, resp, used = None, None, 0
        for i in range(attempts):
            used = i + 1
            try:
                resp = self.http.send(p["method"], p["url"], p["headers"], p["data"], p["timeout"], p["follow"])
                last_exc = None
                if resp.status not in on_status or i == attempts - 1:
                    break
                wait = backoff * (2 ** i) / 1000.0
                ra = resp.header("Retry-After")
                if ra and ra.strip().isdigit():
                    wait = max(wait, float(ra))
            except TransportError as e:
                last_exc, resp = e, None
                if i == attempts - 1:
                    break
                wait = backoff * (2 ** i) / 1000.0
            time.sleep(min(wait, MAX_WAIT_S))
        return resp, used - 1, last_exc

    # ---------------------------------------------------------------- checking
    def check(self, resp, expect):
        errors = []
        status = expect.get("status", "2xx")
        if not status_ok(resp.status, status):
            errors.append("status: expected %s, got %d" % (short(status), resp.status))
        for name, want in (expect.get("headers") or {}).items():
            got = resp.header(name)
            if want is True or want is False:
                if (got is not None) != want:
                    errors.append("header %s: expected %s" % (name, "to be present" if want else "to be absent"))
            else:
                errors += check_value(got is not None, got, want, "header %s" % name, self.schemas)
        for name in expect.get("no_headers") or []:
            if resp.header(name) is not None:
                errors.append("header %s: must not be sent (got %s)" % (name, short(resp.header(name), 80)))
        if "content_type" in expect:
            got = media_type(resp.header("content-type"))
            if got != media_type(expect["content_type"]):
                errors.append("content type: expected %s, got %s" % (expect["content_type"], got or "none"))
        if "max_ms" in expect and resp.ms > float(expect["max_ms"]):
            errors.append("time: %.0f ms, limit %s ms" % (resp.ms, expect["max_ms"]))
        text = None
        for key in ("body_contains", "body_not_contains"):
            if key in expect:
                text = resp.text if text is None else text
                for needle in expect[key] if isinstance(expect[key], list) else [expect[key]]:
                    if (needle in text) != (key == "body_contains"):
                        errors.append("body: %s %s" % ("does not contain" if key == "body_contains" else "contains",
                                                        short(needle)))
        if "body_regex" in expect:
            text = resp.text if text is None else text
            if not re.search(expect["body_regex"], text):
                errors.append("body: does not match /%s/" % expect["body_regex"])
        if "json" in expect or "schema" in expect:
            doc = resp.json()
            if resp._json_error:
                errors.append("json: " + resp._json_error)
            else:
                for path, want in (expect.get("json") or {}).items():
                    found, value = resolve_path(doc, path)
                    errors += check_value(found, value, want, path, self.schemas)
                if "schema" in expect:
                    errors += ["schema " + e for e in self.schemas.check(doc, expect["schema"])]
        return errors

    def capture(self, test, resp):
        errors = []
        for var, spec in (test.get("capture") or {}).items():
            found, value = False, None
            if isinstance(spec, str):
                spec = {"json": spec}
            if "json" in spec:
                doc = resp.json()
                if not resp._json_error:
                    found, value = resolve_path(doc, spec["json"])
            elif "header" in spec:
                value = resp.header(spec["header"])
                found = value is not None
            elif "regex" in spec:
                m = re.search(spec["regex"], resp.text)
                if m:
                    found, value = True, m.group(spec.get("group", 1) if m.groups() else 0)
            elif spec.get("status"):
                found, value = True, resp.status
            else:
                raise SuiteError("capture %s: use a JSON path string or one of json, header, regex, status" % var)
            if not found:
                errors.append("capture %s: %s not found in the response" % (var, short(spec)))
                continue
            self.captured[var] = value
            if SECRET_NAME.search(var) and isinstance(value, str) and len(value) >= 4:
                self.secrets.add(value)
        return errors

    # ---------------------------------------------------------------- one test
    def run_test(self, test, results):
        name = test.get("name") or "(unnamed)"
        res = {"name": name, "status": "passed", "errors": [], "ms": 0.0, "retries": 0, "attempts": 0,
               "method": "", "url": "", "response_status": None, "response_excerpt": "", "reason": ""}
        if test.get("skip"):
            res.update(status="skipped", reason=test["skip"] if isinstance(test["skip"], str) else "skip: true")
            return res
        for dep in test.get("depends_on") or []:
            st = results.get(dep, {}).get("status")
            if st != "passed":
                res.update(status="skipped", reason="depends on '%s', which %s" % (dep, st or "did not run"))
                return res
        try:
            p = self.prepare(test)
        except MissingVar as e:
            if test.get("always_run"):
                res.update(status="skipped", reason="%s; nothing to clean up" % e)
            else:
                res.update(status="error", errors=[str(e)])
            return res
        except SuiteError as e:
            res.update(status="error", errors=[str(e)])
            return res
        res["method"], res["url"] = p["method"], self.mask(p["url"])
        if self.read_only and p["method"] in WRITES and not test.get("read_only_safe"):
            res.update(status="skipped", reason="read-only mode: %s not sent" % p["method"])
            return res
        ok, host = self.host_allowed(p["url"])
        if not ok:
            res.update(status="error", errors=["host %s is not in allowed_hosts %s; request not sent"
                                                % (host, self.allowed)])
            return res
        poll = test.get("poll")
        deadline = time.monotonic() + float(poll.get("timeout_ms", 10000)) / 1000 if poll else None
        interval = float(poll.get("interval_ms", 500)) / 1000 if poll else 0
        started = time.perf_counter()
        while True:
            res["attempts"] += 1
            resp, retries, exc = self.send_with_retry(test, p)
            res["retries"] += retries
            if exc is not None:
                errors = ["request failed: %s (%s %s)" % (exc, p["method"], self.mask(p["url"]))]
            else:
                try:
                    errors = self.check(resp, p["expect"])
                except SuiteError as e:
                    errors = [str(e)]
            if not errors or deadline is None or time.monotonic() + interval > deadline:
                break
            time.sleep(interval)
        res["ms"] = resp.ms if resp is not None else (time.perf_counter() - started) * 1000
        if resp is not None:
            res["response_status"] = resp.status
            res["response_excerpt"] = self.mask(resp.text[:800])
            if not errors:
                try:
                    errors = self.capture(test, resp)
                except SuiteError as e:
                    errors = [str(e)]
        if poll and errors:
            errors.append("still failing after %d polls over %.1f s" % (res["attempts"], float(poll.get("timeout_ms", 10000)) / 1000))
        if errors:
            res.update(status="failed" if resp is not None else "error", errors=[self.mask(e) for e in errors])
        return res

    # ---------------------------------------------------------------- whole suite
    def run(self, select=None):
        results, ordered, failed = {}, [], False
        t0 = time.perf_counter()
        for test in self.suite["tests"]:
            if select is not None and not select(test):
                continue
            if failed and self.fail_fast and not test.get("always_run"):
                res = {"name": test.get("name", "(unnamed)"), "status": "skipped", "reason": "--fail-fast",
                       "errors": [], "ms": 0.0, "retries": 0, "attempts": 0, "method": "", "url": "",
                       "response_status": None, "response_excerpt": ""}
            else:
                res = self.run_test(test, results)
            failed = failed or res["status"] in ("failed", "error")
            results[res["name"]] = res
            ordered.append(res)
            self.print_result(res)
        return ordered, time.perf_counter() - t0

    def print_result(self, r):
        label = {"passed": "PASS", "failed": "FAIL", "error": "ERROR", "skipped": "SKIP"}[r["status"]]
        extra = ""
        if r["status"] in ("passed", "failed"):
            retries = ", %d %s" % (r["retries"], "retry" if r["retries"] == 1 else "retries") if r["retries"] else ""
            extra = " (%.0f ms%s)" % (r["ms"], retries)
        print("%-5s %s%s" % (label, r["name"], extra), file=self.out)
        if r["reason"]:
            print("      %s" % r["reason"], file=self.out)
        for e in r["errors"]:
            print("      - %s" % e, file=self.out)
        if (r["status"] == "failed" or self.verbose) and r["method"]:
            print("      %s %s -> %s" % (r["method"], r["url"], r["response_status"]), file=self.out)
            if r["response_excerpt"] and (r["status"] == "failed" or self.verbose):
                body = " ".join(r["response_excerpt"].split())
                print("      body: %s" % (body if len(body) <= 300 else body[:300] + "..."), file=self.out)


# ============================================================================ reports
def summarize(results, seconds):
    counts = {k: sum(1 for r in results if r["status"] == k) for k in ("passed", "failed", "error", "skipped")}
    retries = sum(r["retries"] for r in results)
    return counts, retries, "%d passed, %d failed, %d errors, %d skipped%s in %.1f s" % (
        counts["passed"], counts["failed"], counts["error"], counts["skipped"],
        " (%d retries: check for flaky endpoints)" % retries if retries else "", seconds)


def write_junit(path, suite_name, results, seconds):
    counts, _, _ = summarize(results, seconds)
    ts = ET.Element("testsuite", name=suite_name, tests=str(len(results)), failures=str(counts["failed"]),
                    errors=str(counts["error"]), skipped=str(counts["skipped"]), time="%.3f" % seconds)
    for r in results:
        tc = ET.SubElement(ts, "testcase", classname=suite_name, name=r["name"], time="%.3f" % (r["ms"] / 1000))
        if r["status"] == "failed":
            el = ET.SubElement(tc, "failure", message=r["errors"][0] if r["errors"] else "failed")
            el.text = "\n".join(r["errors"]) + "\n\n%s %s -> %s\n%s" % (r["method"], r["url"], r["response_status"],
                                                                         r["response_excerpt"])
        elif r["status"] == "error":
            ET.SubElement(tc, "error", message=r["errors"][0] if r["errors"] else "error").text = "\n".join(r["errors"])
        elif r["status"] == "skipped":
            ET.SubElement(tc, "skipped", message=r["reason"])
        if r["retries"]:
            ET.SubElement(tc, "system-out").text = "retries: %d" % r["retries"]
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(ts).write(str(path), encoding="utf-8", xml_declaration=True)


def write_markdown(path, suite_name, results, seconds):
    _, _, line = summarize(results, seconds)
    rows = ["# API test report: %s" % suite_name, "", line, "", "| Result | Test | Request | Status | Time |",
            "|---|---|---|---|---|"]
    for r in results:
        req = ("`%s %s`" % (r["method"], r["url"])).replace("|", "\\|") if r["method"] else ""
        rows.append("| %s | %s | %s | %s | %s |" % (r["status"].upper(), r["name"].replace("|", "\\|"), req,
                                                    r["response_status"] or "", "%.0f ms" % r["ms"] if r["ms"] else ""))
    bad = [r for r in results if r["status"] in ("failed", "error")]
    if bad:
        rows += ["", "## Failures", ""]
        for r in bad:
            rows.append("### %s" % r["name"])
            rows += ["- %s" % e for e in r["errors"]]
            if r["response_excerpt"]:
                rows += ["", "```", r["response_excerpt"][:800], "```"]
            rows.append("")
    slow = sorted((r for r in results if r["ms"]), key=lambda r: -r["ms"])[:5]
    if slow:
        rows += ["", "## Slowest", ""] + ["- %s: %.0f ms" % (r["name"], r["ms"]) for r in slow]
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(rows) + "\n", encoding="utf-8")


# ============================================================================ lint
def _unknown(keys, allowed, where, add):
    for k in keys:
        if k not in allowed:
            close = difflib.get_close_matches(k, allowed, n=1)
            add("ERROR", where, "unknown key '%s'%s" % (k, " (did you mean '%s'?)" % close[0] if close else ""))


def _vars_in(obj):
    if isinstance(obj, str):
        return set(VAR.findall(obj))
    if isinstance(obj, list):
        return set().union(*[_vars_in(x) for x in obj]) if obj else set()
    if isinstance(obj, dict):
        return set().union(*[_vars_in(v) for v in obj.values()]) if obj else set()
    return set()


def _local(host):
    return host in ("localhost", "127.0.0.1", "::1", "0.0.0.0") or host.endswith((".local", ".test", ".localhost"))


def lint_suite(suite):
    findings = []

    def add(level, where, msg):
        findings.append((level, where, msg))

    if not isinstance(suite, dict):
        add("ERROR", "suite", "the suite must be a JSON object")
        return findings
    _unknown(suite, SUITE_KEYS, "suite", add)
    tests = suite.get("tests")
    if not isinstance(tests, list) or not tests:
        add("ERROR", "suite", "'tests' must be a non-empty list")
        return findings
    defaults = suite.get("defaults") or {}
    _unknown(defaults, DEFAULTS_KEYS, "defaults", add)
    _unknown(defaults.get("retry") or {}, RETRY_KEYS, "defaults.retry", add)
    base = str(suite.get("base_url") or "")
    if base.lower().startswith("http://") and not _local(urllib.parse.urlsplit(base).hostname or ""):
        add("WARN", "suite", "base_url uses plain http:// for a non-local host; use https://")
    if not base:
        add("WARN", "suite", "no base_url: every run needs --base-url (or absolute URLs)")
    known = set(suite.get("variables") or {}) | BUILTINS
    later_captures, names = {}, []
    for i, t in enumerate(tests):
        for var in (t.get("capture") or {}) if isinstance(t, dict) else {}:
            later_captures.setdefault(var, i)
    captured, has_writes, creates, cleanup = set(), False, False, False
    for i, t in enumerate(tests):
        where = "test %d" % (i + 1)
        if not isinstance(t, dict):
            add("ERROR", where, "each test must be an object")
            continue
        name = t.get("name")
        if not name:
            add("ERROR", where, "test has no 'name'")
        else:
            where = "'%s'" % name
            if name in names:
                add("ERROR", where, "duplicate test name (names must be unique for depends_on and reports)")
            names.append(name)
        _unknown(t, TEST_KEYS, where, add)
        req = t.get("request")
        if not isinstance(req, dict):
            add("ERROR", where, "missing 'request' object")
            req = {}
        _unknown(req, REQUEST_KEYS, where + ".request", add)
        method = str(req.get("method", "GET")).upper()
        if method not in METHODS:
            add("ERROR", where, "unknown HTTP method '%s'" % method)
        if not (req.get("path") or req.get("url")):
            add("ERROR", where, "request needs 'path' (relative to base_url) or 'url'")
        if len([k for k in ("json", "form", "body") if k in req]) > 1:
            add("ERROR", where, "use only one of json, form or body")
        if method in ("GET", "HEAD") and any(k in req for k in ("json", "form", "body")):
            add("WARN", where, "%s with a body: many servers and proxies drop it" % method)
        url = str(req.get("url") or req.get("path") or "")
        if url.lower().startswith("http://") and not _local(urllib.parse.urlsplit(url).hostname or ""):
            add("WARN", where, "plain http:// URL for a non-local host")
        if re.match(r"^https?://", url, re.I) and base:
            add("WARN", where, "absolute URL bypasses base_url and --base-url; use 'path' unless it is a different service")
        exp = t.get("expect")
        if not isinstance(exp, dict) or not exp:
            add("ERROR", where, "no 'expect': the test checks nothing (at least set 'status')")
            exp = {}
        _unknown(exp, EXPECT_KEYS, where + ".expect", add)
        if exp and "status" not in exp:
            add("WARN", where, "no expected 'status' (defaults to any 2xx); state the exact code")
        st = exp.get("status")
        checks_body = any(k in exp for k in ("json", "schema", "body_contains", "body_regex"))
        if st is not None and status_ok(200, st) and method == "GET" and not checks_body:
            add("WARN", where, "only the status is checked; add json, schema or body checks")
        if st is not None and any(status_ok(c, st) for c in (500, 502, 503)):
            add("WARN", where, "expects a 5xx status: a server error is usually a bug, not a contract")
        for path in (exp.get("json") or {}):
            try:
                resolve_path({}, path)
            except SuiteError as e:
                add("ERROR", where, str(e))
        retry = t.get("retry") or {}
        _unknown(retry, RETRY_KEYS, where + ".retry", add)
        idem_key = any(k.lower() == "idempotency-key" for k in (req.get("headers") or {}))
        if retry.get("unsafe") and method not in IDEMPOTENT and not idem_key:
            add("WARN", where, "retrying %s without an Idempotency-Key header can create duplicates" % method)
        poll = t.get("poll")
        if poll is not None:
            _unknown(poll, POLL_KEYS, where + ".poll", add)
            if float(poll.get("interval_ms", 500)) < 100:
                add("WARN", where, "poll interval below 100 ms hammers the server")
            if float(poll.get("timeout_ms", 10000)) > 120000:
                add("WARN", where, "poll timeout above 2 minutes; is this an API test?")
        timeout = req.get("timeout", defaults.get("timeout"))
        if timeout is not None and (float(timeout) <= 0 or float(timeout) > 60):
            add("WARN", where, "timeout %s s: use a value between 1 and 60" % timeout)
        for dep in t.get("depends_on") or []:
            earlier = names[:-1] if name else names
            if dep not in earlier:
                add("ERROR", where, "depends_on '%s' is not an earlier test" % dep)
        # secrets
        hdrs = dict(defaults.get("headers") or {}, **(req.get("headers") or {}))
        for k, v in hdrs.items():
            if (k.lower() in SECRET_HEADERS or SECRET_NAME.search(k)) and isinstance(v, str) and "${" not in v and v.strip():
                add("ERROR", where, "header %s holds a literal secret; use ${VARIABLE} from --env or the environment" % k)
        auth = req.get("auth") or {}
        for v in ([auth.get("bearer")] + list(auth.get("basic") or [])[1:2] + list((auth.get("header") or {}).values())):
            if isinstance(v, str) and v and "${" not in v:
                add("ERROR", where, "auth holds a literal secret; use ${VARIABLE}")
        for key in ("json", "form"):
            body = req.get(key)
            if isinstance(body, dict):
                for k, v in body.items():
                    if SECRET_NAME.search(k) and isinstance(v, str) and v and "${" not in v:
                        add("WARN", where, "%s.%s looks like a literal secret; use ${VARIABLE}" % (key, k))
        # variables
        used = _vars_in(req) | _vars_in(exp)
        for v in sorted(used):
            if v in captured or v in known:
                continue
            if v in later_captures and later_captures[v] > i:
                add("ERROR", where, "${%s} is captured by a later test (test %d)" % (v, later_captures[v] + 1))
            elif v.startswith("$"):
                add("ERROR", where, "unknown built-in ${%s}" % v)
            else:
                add("INFO", where, "${%s} must come from --env, --var or the environment" % v)
        captured |= set(t.get("capture") or {})
        if method in WRITES:
            has_writes = True
        if method == "POST" and status_ok(201, st or 0):
            creates = True
        if method == "DELETE" and t.get("always_run"):
            cleanup = True
    if has_writes and not suite.get("allowed_hosts"):
        add("WARN", "suite", "the suite writes data but has no allowed_hosts; add them so it cannot hit production by mistake")
    if creates and not cleanup:
        add("WARN", "suite", "creates data (POST -> 201) but has no DELETE test with always_run: true for cleanup")
    return findings


# ============================================================================ plan from OpenAPI
def _example(schema, spec, depth=0, name=""):
    if depth > 8 or not isinstance(schema, dict):
        return None
    if "$ref" in schema:
        return _example(json_pointer(spec, schema["$ref"]) if schema["$ref"].startswith("#") else {}, spec, depth + 1, name)
    for key in ("example", "default", "const"):
        if key in schema:
            return schema[key]
    if schema.get("examples"):
        ex = schema["examples"]
        return ex[0] if isinstance(ex, list) else None
    if schema.get("enum"):
        return schema["enum"][0]
    if "allOf" in schema:
        merged = {}
        for sub in schema["allOf"]:
            v = _example(sub, spec, depth + 1, name)
            if isinstance(v, dict):
                merged.update(v)
        return merged
    for key in ("oneOf", "anyOf"):
        if schema.get(key):
            return _example(schema[key][0], spec, depth + 1, name)
    t = schema.get("type")
    t = next((x for x in t if x != "null"), "string") if isinstance(t, list) else t
    if t == "object" or "properties" in schema:
        props = schema.get("properties", {})
        req = set(schema.get("required", []))
        return {k: _example(v, spec, depth + 1, k) for k, v in props.items()
                if k in req or not (isinstance(v, dict) and v.get("readOnly"))}
    if t == "array":
        item = _example(schema.get("items", {}), spec, depth + 1, name)
        return [item] if item is not None else []
    if t == "integer":
        return int(schema.get("minimum", 1))
    if t == "number":
        return float(schema.get("minimum", 1.5))
    if t == "boolean":
        return True
    fmt = schema.get("format", "")
    if fmt == "email":
        return "qa+${$run_id}@example.test"
    if fmt == "uuid":
        return "00000000-0000-4000-8000-000000000000"
    if fmt == "date-time":
        return "2026-01-01T00:00:00Z"
    if fmt == "date":
        return "2026-01-01"
    if fmt in ("uri", "url"):
        return "https://example.test/item"
    base = "test-%s-${$run_id}" % (name or "value")
    n = schema.get("minLength", 0)
    return base if len(base) >= n else base + "x" * (n - len(base))


def _deref(obj, spec):
    seen = 0
    while isinstance(obj, dict) and "$ref" in obj and obj["$ref"].startswith("#") and seen < 10:
        obj, seen = json_pointer(spec, obj["$ref"]), seen + 1
    return obj


def plan_from_openapi(spec, spec_ref):
    if not isinstance(spec, dict) or not ("openapi" in spec or "swagger" in spec):
        raise SuiteError("not an OpenAPI document (no 'openapi' field)")
    if "swagger" in spec:
        raise SuiteError("Swagger 2.0 is not supported; convert it to OpenAPI 3 first (e.g. swagger2openapi)")
    title = (spec.get("info") or {}).get("title", "API")
    servers = spec.get("servers") or []
    schemes = (spec.get("components") or {}).get("securitySchemes") or {}
    suite = {"name": "%s (generated)" % title,
             "description": "Generated from %s. Review every TODO, replace example values, then run lint." % spec_ref,
             "base_url": "${BASE_URL}",
             "allowed_hosts": ["localhost", "127.0.0.1", "*.test"],
             "defaults": {"headers": {"Accept": "application/json"}, "timeout": 15},
             "variables": {}, "tests": []}
    if servers and isinstance(servers[0], dict) and servers[0].get("url"):
        suite["description"] += " Server in the spec: %s" % servers[0]["url"]
    rank = {"post": 0, "get": 1, "put": 2, "patch": 3, "delete": 4}
    for raw_path, item in (spec.get("paths") or {}).items():
        item = _deref(item, spec)
        shared = item.get("parameters", [])
        for method in sorted((m for m in item if m in rank), key=lambda m: rank[m]):
            op = item[method]
            op_id = op.get("operationId") or "%s %s" % (method.upper(), raw_path)
            params = [_deref(p, spec) for p in shared + op.get("parameters", [])]
            path = raw_path
            for p in params:
                if p.get("in") == "path":
                    var = re.sub(r"\W", "_", p["name"])
                    path = path.replace("{%s}" % p["name"], "${%s}" % var)
                    suite["variables"].setdefault(var, _example(p.get("schema", {}), spec, 0, p["name"])
                                                  if p.get("schema") else "TODO")
            query = {p["name"]: _example(p.get("schema", {}), spec, 0, p["name"]) for p in params
                     if p.get("in") == "query" and p.get("required")}
            responses = op.get("responses") or {}
            ok = sorted(c for c in responses if re.fullmatch(r"2\d\d", str(c)))
            code = int(ok[0]) if ok else 200
            test = {"name": op_id, "tags": ["generated"] + list(op.get("tags", [])),
                    "request": {"method": method.upper(), "path": path}, "expect": {"status": code}}
            if query:
                test["request"]["query"] = query
            security = op.get("security", spec.get("security")) or []
            headers = {}
            for req_sec in security:
                for sname in req_sec:
                    sch = schemes.get(sname, {})
                    if sch.get("type") == "http" and sch.get("scheme", "").lower() == "bearer":
                        headers["Authorization"] = "Bearer ${API_TOKEN}"
                    elif sch.get("type") == "http" and sch.get("scheme", "").lower() == "basic":
                        test["request"]["auth"] = {"basic": ["${API_USER}", "${API_PASSWORD}"]}
                    elif sch.get("type") == "apiKey" and sch.get("in") == "header":
                        headers[sch["name"]] = "${API_KEY}"
                    elif sch.get("type") in ("oauth2", "openIdConnect"):
                        headers["Authorization"] = "Bearer ${API_TOKEN}"
                break  # the first security alternative is enough
            if headers:
                test["request"]["headers"] = headers
            body = _deref(op.get("requestBody") or {}, spec)
            body_schema = None
            content = body.get("content") or {}
            jtype = next((c for c in content if "json" in c), None)
            if jtype:
                body_schema = content[jtype].get("schema", {})
                ex = content[jtype].get("example")
                test["request"]["json"] = ex if ex is not None else _example(body_schema, spec)
            resp = _deref(responses.get(str(code)) or responses.get(code) or {}, spec)
            rjson = next((c for c in (resp.get("content") or {}) if "json" in c), None)
            if rjson and resp["content"][rjson].get("schema"):
                ptr = "#/paths/%s/%s/responses/%s/content/%s/schema" % (
                    pointer_escape(raw_path), method, code, pointer_escape(rjson))
                test["expect"]["content_type"] = "application/json"
                test["expect"]["schema"] = {"$ref": "%s%s" % (spec_ref, ptr)}
            if method == "post" and code == 201 and rjson:
                test["capture"] = {"created_id": "$.id"}
                test["description"] = "TODO: check that the response has an id at $.id, or change the capture path"
            suite["tests"].append(test)
            if headers or test["request"].get("auth"):
                neg = copy.deepcopy(test)
                neg.pop("capture", None)
                neg.pop("description", None)
                neg["name"] = "%s without credentials" % op_id
                neg["tags"] = ["generated", "negative", "security"]
                neg["request"].pop("auth", None)
                neg["request"]["headers"] = {k: None for k in headers}
                neg["expect"] = {"status": [401, 403]}
                suite["tests"].append(neg)
            if body_schema is not None and (_deref(body_schema, spec) or {}).get("required") and method in ("post", "put", "patch"):
                neg = copy.deepcopy(test)
                neg.pop("capture", None)
                neg.pop("description", None)
                neg["name"] = "%s rejects an empty body" % op_id
                neg["tags"] = ["generated", "negative", "validation"]
                neg["request"]["json"] = {}
                neg["expect"] = {"status": [400, 422]}
                suite["tests"].append(neg)
            path_vars = [p for p in params if p.get("in") == "path"]
            if path_vars and method in ("get", "put", "patch", "delete") and "404" in {str(c) for c in responses}:
                neg = copy.deepcopy(test)
                neg.pop("capture", None)
                neg["name"] = "%s returns 404 for an unknown id" % op_id
                neg["tags"] = ["generated", "negative"]
                last = re.sub(r"\W", "_", path_vars[-1]["name"])
                neg["request"]["path"] = path.replace("${%s}" % last, "does-not-exist-${$run_id}")
                neg["expect"] = {"status": 404}
                suite["tests"].append(neg)
    if not suite["variables"]:
        del suite["variables"]
    return suite


EXAMPLE = {
    "name": "Orders API smoke",
    "base_url": "${BASE_URL}",
    "allowed_hosts": ["localhost", "127.0.0.1", "*.test", "api.staging.example.com"],
    "defaults": {"headers": {"Accept": "application/json"}, "timeout": 10, "auth": {"bearer": "${API_TOKEN}"}},
    "variables": {"customer_email": "qa+${$run_id}@example.test"},
    "tests": [
        {"name": "health check", "tags": ["smoke"], "request": {"method": "GET", "path": "/health"},
         "expect": {"status": 200, "json": {"$.status": "ok"}, "max_ms": 1000}},
        {"name": "create order", "tags": ["smoke", "write"],
         "request": {"method": "POST", "path": "/orders", "headers": {"Idempotency-Key": "${$uuid}"},
                     "json": {"customer": "${customer_email}", "items": [{"sku": "SKU-1", "qty": 2}]}},
         "expect": {"status": 201, "content_type": "application/json", "headers": {"Location": {"regex": "/orders/"}},
                    "json": {"$.id": {"type": "string"}, "$.status": "NEW", "$.items.length": 1}},
         "capture": {"order_id": "$.id"}},
        {"name": "read the order", "depends_on": ["create order"],
         "request": {"method": "GET", "path": "/orders/${order_id}"},
         "expect": {"status": 200, "json": {"$.id": "${order_id}", "$.items[0].qty": 2, "$.total": {"gte": 0}}}},
        {"name": "order becomes confirmed", "depends_on": ["create order"],
         "request": {"method": "GET", "path": "/orders/${order_id}"}, "poll": {"timeout_ms": 10000, "interval_ms": 500},
         "expect": {"status": 200, "json": {"$.status": "CONFIRMED"}}},
        {"name": "rejects an order without items", "tags": ["negative"],
         "request": {"method": "POST", "path": "/orders", "json": {"customer": "${customer_email}", "items": []}},
         "expect": {"status": [400, 422], "json": {"$.title": {"exists": True}}}},
        {"name": "requires a token", "tags": ["negative", "security"],
         "request": {"method": "GET", "path": "/orders/${order_id}", "headers": {"Authorization": None}},
         "depends_on": ["create order"], "expect": {"status": 401}},
        {"name": "delete the order (cleanup)", "always_run": True,
         "request": {"method": "DELETE", "path": "/orders/${order_id}"}, "expect": {"status": [204, 404]}},
    ],
}


# ============================================================================ CLI
def parse_vars(items):
    out = {}
    for item in items or []:
        if "=" not in item:
            raise SuiteError("--var expects NAME=VALUE, got %r" % item)
        k, v = item.split("=", 1)
        out[k] = v
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Run, lint and generate REST API test suites (stdlib only).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run a suite against a server")
    r.add_argument("suite")
    r.add_argument("--env", help="NAME=VALUE file (.env) or JSON object with variables")
    r.add_argument("--var", action="append", help="NAME=VALUE, may repeat; wins over --env and the environment")
    r.add_argument("--base-url", help="override base_url (e.g. a staging or local server)")
    r.add_argument("--tag", action="append", help="run only tests with this tag (may repeat)")
    r.add_argument("--skip-tag", action="append", help="skip tests with this tag (may repeat)")
    r.add_argument("--only", action="append", help="run only the test with this name (may repeat)")
    r.add_argument("--read-only", action="store_true", help="do not send POST/PUT/PATCH/DELETE (production smoke)")
    r.add_argument("--fail-fast", action="store_true", help="stop after the first failure (always_run tests still run)")
    r.add_argument("--no-retry", action="store_true", help="never retry, to expose flaky endpoints")
    r.add_argument("--junit", help="write JUnit XML here (for CI)")
    r.add_argument("--json", dest="json_out", help="write results as JSON here")
    r.add_argument("--report", help="write a Markdown report here")
    r.add_argument("--insecure", action="store_true", help="skip TLS verification (self-signed test servers only)")
    r.add_argument("--verbose", "-v", action="store_true", help="print request and response for every test")
    li = sub.add_parser("lint", help="check a suite for mistakes and flaky or unsafe patterns")
    li.add_argument("suite")
    li.add_argument("--strict", action="store_true", help="treat warnings as errors")
    pl = sub.add_parser("plan", help="generate a starter suite from an OpenAPI 3 file")
    pl.add_argument("openapi")
    pl.add_argument("--out", help="write the suite here (default: print)")
    ex = sub.add_parser("example", help="print or write an example suite")
    ex.add_argument("--out")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "run":
            suite = load_structured(args.suite)
            errors = [f for f in lint_suite(suite) if f[0] == "ERROR"]
            if errors:
                for _, where, msg in errors:
                    print("ERROR %s: %s" % (where, msg), file=sys.stderr)
                print("fix the suite first (python api_check.py lint %s)" % args.suite, file=sys.stderr)
                return 2
            env = load_env_file(args.env) if args.env else {}
            runner = Runner(suite, args.suite, env, parse_vars(args.var), args.base_url, args.read_only,
                            args.fail_fast, args.no_retry, args.insecure, args.verbose)
            if args.insecure:
                print("WARNING: TLS verification is off (--insecure)", file=sys.stderr)

            def select(t):
                tags = set(t.get("tags") or [])
                if args.only and t.get("name") not in args.only:
                    return False
                if args.tag and not (tags & set(args.tag)) and not t.get("always_run"):
                    return False
                return not (args.skip_tag and tags & set(args.skip_tag))

            print("Suite: %s" % suite.get("name", args.suite))
            results, seconds = runner.run(select)
            counts, _, line = summarize(results, seconds)
            print("\n" + line)
            name = suite.get("name") or Path(args.suite).stem
            if args.junit:
                write_junit(args.junit, name, results, seconds)
            if args.report:
                write_markdown(args.report, name, results, seconds)
            if args.json_out:
                Path(args.json_out).write_text(json.dumps({"suite": name, "seconds": seconds, "summary": counts,
                                                           "results": results}, indent=2), encoding="utf-8")
            if not results:
                print("no tests selected", file=sys.stderr)
                return 2
            return 1 if counts["failed"] or counts["error"] else 0
        if args.cmd == "lint":
            findings = lint_suite(load_structured(args.suite))
            for level, where, msg in findings:
                print("%-5s %s: %s" % (level, where, msg))
            n_err = sum(1 for f in findings if f[0] == "ERROR")
            n_warn = sum(1 for f in findings if f[0] == "WARN")
            print("%d errors, %d warnings" % (n_err, n_warn))
            return 1 if n_err or (args.strict and n_warn) else 0
        if args.cmd == "plan":
            spec_path = Path(args.openapi)
            out = Path(args.out) if args.out else None
            try:
                ref = os.path.relpath(spec_path.resolve(), out.resolve().parent if out else Path.cwd())
            except ValueError:  # different drives on Windows
                ref = str(spec_path.resolve())
            ref = ref.replace("\\", "/")
            suite = plan_from_openapi(load_structured(spec_path), ref)
            text = json.dumps(suite, indent=2, ensure_ascii=False) + "\n"
            if out:
                out.write_text(text, encoding="utf-8")
                print("wrote %s with %d tests; review the TODOs, then: python api_check.py lint %s"
                      % (out, len(suite["tests"]), out))
            else:
                sys.stdout.write(text)
            return 0
        if args.cmd == "example":
            text = json.dumps(EXAMPLE, indent=2) + "\n"
            if args.out:
                if Path(args.out).exists():
                    raise SuiteError("%s already exists; not overwriting" % args.out)
                Path(args.out).write_text(text, encoding="utf-8")
                print("wrote %s" % args.out)
            else:
                sys.stdout.write(text)
            return 0
    except SuiteError as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
