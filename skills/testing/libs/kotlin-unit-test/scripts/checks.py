#!/usr/bin/env python3
"""Project scan, test-to-code mapping (class-wise and method-wise) and test verification rules.
Python 3.8+, standard library only. The rules are documented in references/checks.md."""

import os
import re
from pathlib import Path

import kotlin_source as ks
import results as rs

SKIP_DIRS = rs.SKIP_DIRS | {"build", "out", "target", "buildSrc", "generated", "bin"}
TEST_DIR_NAMES = {"test", "tests", "testFixtures", "integrationTest", "unitTest", "jvmTest", "commonTest"}
INSTRUMENTED_DIR_NAMES = {"androidTest", "androidInstrumentedTest", "androidUnitTest"}
TEST_FILE_RE = re.compile(r"(Test|Tests|Spec|IT|TestCase)\.kts?$")
TEST_SUFFIXES = ("UnitTest", "Tests", "Test", "Spec", "IT", "TestCase", "Should")

ASSERT_RE = re.compile(
    r"\b(?:assert\w*|expect\w*|fail|verify\w*|coVerify\w*|confirmVerified|check|checkNotNull|assertk\w*)"
    r"\s*(?:<[^<>]*(?:<[^<>]*>)?[^<>]*>\s*)?[({]"
    r"|\bshould\w*\b"
    r"|\.\s*(?:check|andExpect|assert\w*|expect\w*)\s*\(")
MOCK_ONLY_RE = re.compile(r"\b(verify\w*|coVerify\w*|confirmVerified)\b")
MOCK_BLOCK_RE = re.compile(r"\b(every|coEvery|verify|coVerify|verifyOrder|verifySequence|verifyAll|coVerifyOrder|"
                           r"whenever|wheneverBlocking|given|doReturn|doThrow|justRun|coJustRun)\s*[({]|`when`\s*\(")
MOCKED_TYPE_RES = [re.compile(r"\b(?:mockk|mock|relaxedMockk|mockkClass)\s*<\s*([A-Z]\w*)"),
                   re.compile(r"\b(?:mockk|mock|mockkClass)\s*\(\s*([A-Z]\w*)::class"),
                   re.compile(r"@(?:MockK|RelaxedMockK|Mock|MockBean)\b[^:\n]*:\s*([A-Z]\w*)"),
                   re.compile(r"\bval\s+\w+\s*:\s*([A-Z]\w*)\s*=\s*(?:mockk|mock|relaxedMockk)\b")]
SLEEP_RE = re.compile(r"\b(Thread\.sleep|SystemClock\.sleep|TimeUnit\.\w+\.sleep)\s*\(")
DELAY_RE = re.compile(r"(?<![.\w])delay\s*\(")
NONDET_RE = re.compile(r"\b(LocalDate(?:Time)?\.now|Instant\.now|ZonedDateTime\.now|System\.currentTimeMillis|"
                       r"System\.nanoTime|UUID\.randomUUID|Random\.next\w*|Math\.random|Date\s*\(\s*\))\s*\(?")
REAL_IO_RE = re.compile(r"\b(URL\s*\(|HttpURLConnection|OkHttpClient\s*\(|HttpClient\.new|Socket\s*\(|"
                        r"DriverManager\.getConnection|FileWriter\s*\(|FileOutputStream\s*\()")
REAL_DRIVER_RE = re.compile(r"\b(AndroidDriver|IOSDriver|AppiumDriver|RemoteWebDriver|ChromeDriver|FirefoxDriver|"
                            r"EdgeDriver|SafariDriver|UiDevice\.getInstance)\s*[(<]")
TODO_RE = re.compile(r"\bTODO\s*\(|NotImplementedError|fail\s*\(\s*\"(?:not (?:yet )?implemented|todo)", re.I)
TRIVIAL_RES = [re.compile(r"\bassert(?:True|That)\s*\(\s*true\s*\)"), re.compile(r"\bassertFalse\s*\(\s*false\s*\)"),
               re.compile(r"\bassertNotNull\s*\(\s*(?:\"[^\"]*\"|\d+|true|false)\s*\)"),
               re.compile(r"\b(true|false|\d+)\s+shouldBe\s+\1\b")]
EMPTY_CATCH_RE = re.compile(r"\bcatch\s*\([^)]*\)\s*\{(?P<body>[^{}]*)\}")
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


# ------------------------------------------------------------------------------------------------ scan

def classify(path, root):
    """'main', 'test', 'instrumented' or None (build scripts)."""
    rel = path.relative_to(root)
    parts = rel.parts
    if path.name.endswith((".gradle.kts", "settings.gradle.kts")):
        return None
    if any(p in INSTRUMENTED_DIR_NAMES for p in parts[:-1]):
        return "instrumented"
    if "src" in parts:
        i = parts.index("src")
        if i + 1 < len(parts) - 1:
            src_set = parts[i + 1]
            if src_set in TEST_DIR_NAMES or src_set.endswith("Test"):
                return "test"
            return "main"
    if any(p in TEST_DIR_NAMES for p in parts[:-1]) or TEST_FILE_RE.search(path.name):
        return "test"
    return "main"


def scan(root, include_private=False):
    root = Path(root).resolve()
    files = {"main": [], "test": [], "instrumented": []}
    errors = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        for fn in sorted(filenames):
            if not fn.endswith((".kt", ".kts")):
                continue
            p = Path(dirpath) / fn
            kind = classify(p, root)
            if kind is None:
                continue
            try:
                info = ks.parse_file(p)
            except (OSError, RecursionError, ValueError) as e:
                errors.append(f"{p}: could not be read ({e})")
                continue
            info["rel"] = p.relative_to(root).as_posix()
            info["kind"] = kind
            files[kind].append(info)
    return {"root": str(root), "files": files, "errors": errors, "include_private": include_private,
            "build": build_info(root)}


def build_info(root):
    root = Path(root)
    texts = []
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        if len(Path(dirpath).relative_to(root).parts) > 3:
            dirnames[:] = []
        for fn in filenames:
            if fn in ("build.gradle", "build.gradle.kts", "pom.xml", "libs.versions.toml"):
                p = Path(dirpath) / fn
                found.append(p.relative_to(root).as_posix())
                try:
                    texts.append(p.read_text(encoding="utf-8", errors="replace"))
                except OSError:
                    pass
    t = "\n".join(texts)
    return {"files": found,
            "junit_platform": bool(re.search(r"useJUnitPlatform|junit-jupiter|junit\.jupiter|kotest-runner", t)),
            "vintage": "vintage" in t,
            "junit4": bool(re.search(r"junit:junit|\"junit\"\s*,\s*\"junit\"|junit4", t)),
            "kotlin_test": bool(re.search(r"kotlin\(\s*\"test|kotlin-test", t)),
            "mockk": "mockk" in t, "mockito": "mockito" in t, "kotest": "kotest" in t,
            "jacoco": "jacoco" in t, "kover": "kover" in t,
            "android": bool(re.search(r"com\.android\.(application|library)|android\s*\{", t))}


# ------------------------------------------------------------------------------------------------ model

def _fq(pkg, name):
    return f"{pkg}.{name}" if pkg else name


def production_units(project):
    """Class-wise list of production units with their methods."""
    units = {}
    inc_private = project["include_private"]
    for f in project["files"]["main"]:
        pkg = f["package"]
        for c in f["classes"]:
            if c["kind"] in ("companion", "annotation"):
                continue
            fq = _fq(pkg, c["qualname"])
            units[fq] = {"id": fq, "name": c["qualname"], "simple": c["name"], "package": pkg, "kind": c["kind"],
                         "file": f["rel"], "line": c["line"], "private": c["private"], "methods": [],
                         "supertypes": c["supertypes"]}
        for fn in f["functions"]:
            if fn["owner"] is None:
                fq = _fq(pkg, f["facade"])
                units.setdefault(fq, {"id": fq, "name": f["facade"], "simple": f["facade"], "package": pkg,
                                      "kind": "file (top-level functions)", "file": f["rel"], "line": fn["line"],
                                      "private": False, "methods": [], "supertypes": []})
            else:
                fq = _fq(pkg, fn["owner"])
            u = units.get(fq)
            if u is None:
                continue
            mods = set(fn["modifiers"])
            skip = None
            if fn["body_kind"] is None:
                skip = "abstract (no body)"
            elif ("private" in mods or fn["class_private"]) and not inc_private:
                skip = "private"
            elif fn["name"] in ("toString", "hashCode", "equals") and "override" in mods:
                skip = "boilerplate override"
            u["methods"].append({"id": f"{fq}#{fn['name']}:{fn['line']}", "name": fn["name"], "line": fn["line"],
                                 "end_line": fn["end_line"], "signature": fn["signature"],
                                 "modifiers": fn["modifiers"], "companion": fn["companion"],
                                 "receiver": fn["receiver"], "skip": skip, "file": f["rel"],
                                 "jvm_class": fq + (".Companion" if fn["companion"] else "")})
    for u in units.values():
        u["testable"] = [m for m in u["methods"] if not m["skip"]]
    return units


def test_units(project):
    """Test classes with their test functions and the helper functions defined in test sources."""
    classes, helpers = {}, {}
    for f in project["files"]["test"]:
        pkg = f["package"]
        imports = f["imports"]
        for fn in f["functions"]:
            if not fn["is_test"]:
                if fn["body_kind"]:
                    helpers[fn["name"]] = fn
                continue
            owner = fn["owner"] or f["facade"]
            fq = _fq(pkg, owner)
            tc = classes.setdefault(fq, {"id": fq, "name": owner, "package": pkg, "file": f["rel"], "tests": [],
                                         "imports": imports, "kotest": fn["kotest"], "file_masked": "",
                                         "mocked": set()})
            tc["tests"].append({"id": f"{fq}#{fn['name']}", "name": fn["name"], "line": fn["line"],
                                "end_line": fn["end_line"], "file": f["rel"], "class": fq,
                                "body": fn["body"], "body_masked": fn["body_masked"],
                                "disabled": fn["disabled"], "expected_exception": fn["expected_exception"],
                                "kotest": fn["kotest"], "annotations": [a["name"] for a in fn["annotations"]],
                                "targets": [], "results": []})
        raw = Path(project["root"], f["rel"]).read_text(encoding="utf-8", errors="replace")
        masked = ks.mask(raw)
        for fq, tc in classes.items():
            if tc["file"] == f["rel"]:
                tc["file_masked"] = masked
                for rx in MOCKED_TYPE_RES:
                    tc["mocked"].update(rx.findall(raw))
    # test classes that declare no tests (e.g. all tests removed) are reported by verify()
    empty = []
    for f in project["files"]["test"]:
        for c in f["classes"]:
            fq = _fq(f["package"], c["qualname"])
            if fq not in classes and (c["name"].endswith(TEST_SUFFIXES) or c["kotest"]) and c["kind"] == "class":
                empty.append({"id": fq, "file": f["rel"], "line": c["line"]})
    return classes, helpers, empty


def strip_suffix(name):
    for s in TEST_SUFFIXES:
        if name.endswith(s) and len(name) > len(s):
            return name[:-len(s)]
    if name.startswith("Test") and len(name) > 4 and name[4].isupper():
        return name[4:]
    return None


def _demock(body):
    """Blank out mock stubbing/verification blocks so calls inside them don't count as 'tested'."""
    out = body
    for mm in MOCK_BLOCK_RE.finditer(body):
        j = mm.end() - 1
        if body[j] not in "({":
            continue
        close = ks.match_paren(body, j, body[j], ")" if body[j] == "(" else "}")
        out = out[:mm.start()] + " " * (close + 1 - mm.start()) + out[close + 1:]
    return out


def contains_seq(hay, needle):
    n = len(needle)
    return n > 0 and any(hay[i:i + n] == needle for i in range(len(hay) - n + 1))


def link(project):
    """Map test classes to production classes and test functions to production methods."""
    units = production_units(project)
    tclasses, helpers, empty = test_units(project)
    by_simple = {}
    for u in units.values():
        for key in {u["simple"], u["name"]}:
            by_simple.setdefault(key, []).append(u)
    for u in units.values():
        u["test_classes"] = []
        for m in u["methods"]:
            m["tests"] = []

    for tc in tclasses.values():
        base = strip_suffix(tc["name"].split(".")[-1])
        primary = []
        if base:
            cands = by_simple.get(base, [])
            same_pkg = [u for u in cands if u["package"] == tc["package"]]
            primary = same_pkg or cands
        referenced = set()
        text = tc["file_masked"]
        for simple, us in by_simple.items():
            if simple in tc["mocked"] or not re.search(r"\b" + re.escape(simple) + r"\s*[.(:{]|::" +
                                                         re.escape(simple) + r"\b|\b" + re.escape(simple) +
                                                         r"\s*\.\s*\w+\s*\(", text):
                continue
            for u in us:
                referenced.add(u["id"])
        for u in units.values():                                 # top-level / extension functions
            if not u["kind"].startswith("file"):
                continue
            stem = u["simple"][:-2] if u["simple"].endswith("Kt") else u["simple"]
            if base and base == stem and u not in primary:
                primary.append(u)
            elif u["package"] == tc["package"] or any(
                    i in (u["package"] + ".*", *(u["package"] + "." + m["name"] for m in u["methods"]))
                    for i in tc["imports"]):
                if any(re.search(r"(?<![\w])" + re.escape(m["name"]) + r"\s*[({]", text) for m in u["methods"]):
                    referenced.add(u["id"])
        tc["primary"] = [u["id"] for u in primary]
        tc["referenced"] = sorted(referenced - set(tc["primary"]))
        cand_units = [units[i] for i in tc["primary"] + tc["referenced"]]
        for u in primary:
            u["test_classes"].append(tc["id"])
        for t in tc["tests"]:
            body = _demock(t["body_masked"])
            ttoks = ks.tokens(t["name"])
            for u in cand_units:
                is_primary = u["id"] in tc["primary"]
                facade = u["kind"].startswith("file")
                for m in u["methods"]:
                    name = re.escape(m["name"])
                    if facade:
                        call = re.search(r"(?<![\w.])" + name + r"\s*(?:\(|\{)|::" + name + r"\b|\.\s*" + name +
                                         r"\s*\(", body)
                    else:
                        call = re.search(r"\.\s*" + name + r"\s*(?:\(|\{|<)|::" + name + r"\b", body)
                        if not call and is_primary and u["kind"] == "object":
                            call = re.search(r"(?<![\w.])" + name + r"\s*\(", body)
                    named = is_primary and contains_seq(ttoks, ks.tokens(m["name"]))
                    if call or named:
                        ev = "calls it" if call else "test name"
                        m["tests"].append({"test": t["id"], "evidence": ev})
                        t["targets"].append({"unit": u["id"], "method": m["name"], "method_id": m["id"],
                                             "evidence": ev})
                        if u["id"] not in tc["primary"] and tc["id"] not in u["test_classes"]:
                            u["test_classes"].append(tc["id"])
    return {"units": units, "test_classes": tclasses, "helpers": helpers, "empty_test_classes": empty}


# ------------------------------------------------------------------------------------------------ results

def attach_results(model, cases):
    """Attach JUnit results to declared tests. Returns (unmatched_cases)."""
    index = {}
    for tc in model["test_classes"].values():
        for t in tc["tests"]:
            index.setdefault((tc["id"], t["name"]), t)
            index.setdefault((tc["id"], t["name"].replace(" ", "_")), t)
    unmatched = []
    for c in cases:
        cls = c["classname"].replace("$", ".")
        key = rs.test_key(c["name"])
        t = index.get((cls, key)) if key is not None else None
        if t is None and key is None:                         # '[1] a, b' - attach to the only parameterized test
            cands = [x for x in model["test_classes"].get(cls, {}).get("tests", [])
                     if "ParameterizedTest" in x["annotations"]]
            t = cands[0] if len(cands) == 1 else None
        if t is None:
            parent = model["test_classes"].get(cls)
            if parent:
                cands = [x for x in parent["tests"] if key and x["name"].lower() == key.lower()] or                         [x for x in parent["tests"] if key and x["kotest"] and key.endswith(x["name"])]
                t = cands[0] if cands else None
        if t is None:
            unmatched.append(c)
            continue
        t["results"].append(c)
    return unmatched


def test_status(t):
    if not t["results"]:
        return "not run"
    st = [r["status"] for r in t["results"]]
    if "error" in st or "failed" in st:
        return "failed"
    if all(s == "skipped" for s in st):
        return "skipped"
    return "passed"


def method_status(model, m):
    tests = [find_test(model, x["test"]) for x in m["tests"]]
    if m["skip"]:
        return "excluded"
    if not tests:
        return "untested"
    st = [test_status(t) for t in tests if t]
    if "failed" in st:
        return "failing"
    if any(test_status(t) == "passed" and not t.get("hollow") for t in tests if t):
        return "tested"
    if "passed" in st:
        return "weak"                                     # only passing tests that check nothing
    if st and all(s == "skipped" for s in st):
        return "skipped"
    return "not run"


def find_test(model, test_id):
    cls = test_id.split("#")[0]
    for t in model["test_classes"].get(cls, {}).get("tests", []):
        if t["id"] == test_id:
            return t
    return None


# ------------------------------------------------------------------------------------------------ verify

def _finding(rule, severity, title, detail, file=None, line=None, **kw):
    d = {"rule": rule, "severity": severity, "title": title, "detail": detail, "file": file, "line": line}
    d.update(kw)
    return d


def assertion_helpers(helpers):
    """Names of helper functions in test sources that (transitively) contain assertions."""
    names = {n for n, f in helpers.items() if ASSERT_RE.search(f.get("body_masked", ""))}
    for _ in range(3):
        added = False
        for n, f in helpers.items():
            if n in names:
                continue
            body = f.get("body_masked", "")
            if any(re.search(r"(?<![\w])" + re.escape(h) + r"\s*[({]", body) for h in names):
                names.add(n)
                added = True
        if not added:
            break
    return names


def split_args(s):
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch in "([{<":
            depth += 1
        elif ch in ")]}>":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def static_checks(model, project):
    """Rules that only need the source code."""
    fs = []
    helper_names = assertion_helpers(model["helpers"])
    helper_re = re.compile(r"(?<![\w])(" + "|".join(re.escape(h) for h in sorted(helper_names)) + r")\s*[({]") \
        if helper_names else None
    build = project["build"]
    for tc in model["test_classes"].values():
        junit4 = any(i in ("org.junit.Test", "org.junit.*") for i in tc["imports"])
        if junit4 and build["junit_platform"] and not build["vintage"] and not build["android"]:
            fs.append(_finding("KT010", "error", "JUnit 4 tests on the JUnit 5 platform without the vintage engine",
                               f"{tc['name']} uses org.junit.Test, but the build runs the JUnit Platform and has no "
                               "junit-vintage-engine. These tests are silently not run. Switch to "
                               "org.junit.jupiter.api.Test (or kotlin.test.Test), or add the vintage engine.",
                               tc["file"], tc["tests"][0]["line"] if tc["tests"] else None, test_class=tc["id"]))
        for t in tc["tests"]:
            body = t["body_masked"]
            inner = body.strip()
            inner = inner[1:-1].strip() if inner.startswith("{") and inner.endswith("}") else inner
            loc = dict(file=t["file"], line=t["line"], test=t["id"])
            if t["disabled"]:
                fs.append(_finding("KT007", "warning", "Disabled test", f"{t['name']}: {t['disabled']}", **loc))
            if not inner:
                fs.append(_finding("KT002", "error", "Empty test", f"{t['name']} has no code, so it always passes.",
                                   **loc))
                t["hollow"] = "empty"
                continue
            if TODO_RE.search(t["body"]):
                t["hollow"] = "unfinished (TODO)"
                fs.append(_finding("KT003", "error", "Unfinished test (TODO)",
                                   f"{t['name']} still contains TODO()/NotImplementedError; write the real test.",
                                   **loc))
            has_assert = bool(ASSERT_RE.search(body)) or t["expected_exception"] or \
                bool(helper_re and helper_re.search(body))
            if not has_assert and not TODO_RE.search(t["body"]):
                t["hollow"] = "no assertions"
                fs.append(_finding("KT001", "error", "Test without assertions",
                                   f"{t['name']} runs code but checks nothing, so it passes even when the code is "
                                   "wrong. Add assertions on the result or state.", **loc))
            elif has_assert and MOCK_ONLY_RE.search(body):
                rest = MOCK_ONLY_RE.sub(" ", body)
                if not ASSERT_RE.search(rest) and not (helper_re and helper_re.search(rest)):
                    fs.append(_finding("KT021", "info", "Only checks mock interactions",
                                       f"{t['name']} only verifies calls on mocks. Also assert the result or state "
                                       "if the method returns or changes something.", **loc))
            for rx in TRIVIAL_RES:
                if rx.search(t["body"]):
                    fs.append(_finding("KT004", "warning", "Assertion that can never fail",
                                       f"{t['name']}: '{rx.search(t['body']).group(0)}' always passes.", **loc))
                    break
            for am in re.finditer(r"\bassert(?:Equals|Same|NotEquals)\s*\(", body):
                close = ks.match_paren(t["body"], am.end() - 1)
                args = split_args(t["body"][am.end():close])
                if len(args) >= 2 and args[0] == args[1] and args[0]:
                    fs.append(_finding("KT004", "warning", "Assertion compares a value with itself",
                                       f"{t['name']}: both sides are '{args[0]}'.", **loc))
                    break
            for cm in EMPTY_CATCH_RE.finditer(body):
                cb = cm.group("body").strip()
                if not cb or re.fullmatch(r"(?s)\s*(println|print|log\w*|Log\.\w|e\.printStackTrace)[^;]*", cb):
                    fs.append(_finding("KT005", "warning", "Exception swallowed in a test",
                                       f"{t['name']} catches an exception and ignores it, which can hide failures. "
                                       "Use assertFailsWith/assertThrows, or let it propagate.", **loc))
                    break
            if SLEEP_RE.search(body) or (DELAY_RE.search(body) and "runTest" not in body):
                fs.append(_finding("KT006", "warning", "Test waits with sleep/delay",
                                   f"{t['name']} sleeps. This makes tests slow and flaky; use runTest with virtual "
                                   "time, a fake clock, or await a condition.", **loc))
            nd = NONDET_RE.search(body)
            if nd:
                fs.append(_finding("KT008", "info", "Depends on the current time or randomness",
                                   f"{t['name']} uses {nd.group(1)}; inject a fixed Clock or seeded Random so the "
                                   "result is repeatable.", **loc))
            drv = REAL_DRIVER_RE.search(body)
            if drv:
                fs.append(_finding("KT009", "warning", "Unit test starts a real driver/device",
                                   f"{t['name']} creates {drv.group(1)}. A unit test of automation code should mock "
                                   "the driver; real devices belong in integration/UI tests.", **loc))
            elif REAL_IO_RE.search(body):
                fs.append(_finding("KT009", "info", "Unit test uses real network/file I/O",
                                   f"{t['name']} uses {REAL_IO_RE.search(body).group(1).strip('( ')}; fake it "
                                   "(MockWebServer, temp folder) to keep the test fast and isolated.", **loc))
            if not t["targets"]:
                fs.append(_finding("KT020", "info", "Test not linked to a production method",
                                   f"{t['name']} does not call (or name) a method of the class it tests, so it is not "
                                   "counted for any method. Name the test after the method or call it directly.",
                                   **loc))
    for e in model["empty_test_classes"]:
        fs.append(_finding("KT027", "info", "Test class without tests",
                           f"{e['id']} has no @Test functions.", e["file"], e["line"]))
    if project["files"]["instrumented"]:
        n = len(project["files"]["instrumented"])
        fs.append(_finding("KT028", "info", "Instrumented tests not run",
                           f"{n} file(s) under androidTest need a device/emulator (connectedAndroidTest) and are "
                           "not part of this unit-test run."))
    for u in model["units"].values():
        if u["private"] and not project["include_private"]:
            continue
        untested = [m for m in u["testable"] if not m["tests"]]
        if u["testable"] and len(untested) == len(u["testable"]):
            fs.append(_finding("KT012", "warning", "Class has no tests",
                               f"None of the {len(u['testable'])} method(s) of {u['name']} is tested.",
                               u["file"], u["line"], unit=u["id"]))
        else:
            for m in untested:
                fs.append(_finding("KT011", "warning", "Method has no test",
                                   f"{u['name']}.{m['name']} ({m['signature']}) is not called or named by any test.",
                                   m["file"], m["line"], unit=u["id"], method=m["name"]))
        for m in u["testable"]:
            linked = [find_test(model, x["test"]) for x in m["tests"]]
            linked = [t for t in linked if t]
            if linked and all(t.get("hollow") for t in linked):
                fs.append(_finding("KT022", "warning", "Method only has tests that check nothing",
                                   f"{u['name']}.{m['name']} is linked only to empty, unfinished or assertion-free "
                                   f"tests ({', '.join(t['name'] for t in linked)}), so it is effectively untested.",
                                   m["file"], m["line"], unit=u["id"], method=m["name"]))
    return fs


def result_checks(model, run, cov, opts):
    """Rules that need the test results (and coverage)."""
    fs = []
    total = sum(len(t["results"]) for tc in model["test_classes"].values() for t in tc["tests"]) + \
        len(run.get("unmatched", []))
    if run.get("build_failed"):
        fs.append(_finding("KT029", "error", "Build or compilation failed",
                           run.get("build_error") or "The build tool exited with an error before tests ran; see the "
                           "build log.", log=run.get("log")))
    if total == 0:
        fs.append(_finding("KT015", "error", "No tests were executed",
                           "The run produced no test results. Check the build log, the test filter and that the test "
                           "engine (JUnit 5 / Kotest) is configured."))
    filtered = bool(run.get("filters"))
    for tc in model["test_classes"].values():
        for t in tc["tests"]:
            loc = dict(file=t["file"], line=t["line"], test=t["id"])
            st = test_status(t)
            if st == "failed":
                r = next(r for r in t["results"] if r["status"] in ("failed", "error"))
                fs.append(_finding("KT013", "error", "Failing test",
                                   f"{t['name']}: {r['type'] or r['status']}: {r['message'][:300]}", **loc))
            elif st == "skipped" and not t["disabled"]:
                fs.append(_finding("KT024", "info", "Test skipped at run time",
                                   f"{t['name']} was skipped (assumption failed or disabled by the engine).", **loc))
            elif st == "not run" and total and not t["disabled"] and not filtered:
                fs.append(_finding("KT014", "warning", "Declared test was not executed",
                                   f"{t['name']} is in the source but not in the results (not discovered, wrong "
                                   "annotation/engine, or excluded by the build).", **loc))
            slow = max((r["time"] for r in t["results"]), default=0)
            if slow >= opts.get("slow", 2.0):
                fs.append(_finding("KT025", "info", "Slow unit test", f"{t['name']} took {slow:.2f} s.", **loc))
    if run.get("stale"):
        fs.append(_finding("KT016", "warning", "Results may be out of date", run["stale"]))
    if cov:
        min_cov = opts.get("min_coverage")
        for u in model["units"].values():
            for m in u["testable"]:
                c = rs.coverage_for(cov, m["jvm_class"], m["name"], m["line"], m["end_line"])
                m["coverage"] = {k: list(v) for k, v in c.items()} if c else None
                if c and m["tests"] and c.get("INSTRUCTION", (0, 0))[1] == 0 and \
                        any(test_status(find_test(model, x["test"]) or {"results": []}) == "passed"
                            for x in m["tests"]):
                    fs.append(_finding("KT017", "warning", "Linked tests never execute the method",
                                       f"{u['name']}.{m['name']} has linked passing tests but 0% coverage. The tests "
                                       "probably test a mock or another overload.", m["file"], m["line"],
                                       unit=u["id"], method=m["name"]))
            ccov = next((cov["classes"][c] for c in rs.class_candidates(u["id"]) if c in cov["classes"]), None)
            u["coverage"] = {k: list(v) for k, v in ccov["counters"].items()} if ccov else None
            if min_cov is not None and ccov and u["testable"]:
                lp = rs.pct(ccov["counters"].get("LINE"))
                if lp is not None and lp < min_cov:
                    fs.append(_finding("KT018", "error", "Line coverage below the minimum",
                                       f"{u['name']}: {lp}% < {min_cov}%.", u["file"], u["line"], unit=u["id"]))
    return fs


def sort_findings(fs):
    return sorted(fs, key=lambda f: (SEVERITY_ORDER[f["severity"]], f["rule"], f.get("file") or "",
                                     f.get("line") or 0))
