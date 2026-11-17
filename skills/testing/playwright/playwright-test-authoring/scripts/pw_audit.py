#!/usr/bin/env python3
"""Audit a Playwright test suite and its config for flaky or brittle patterns.

Usage:
    python pw_audit.py <project-dir> [--json] [--strict]

Reads playwright.config.{ts,js,mjs,cjs} (or pytest settings for pytest-playwright) and every test
file (*.spec.* / *.test.* for TS/JS, test_*.py / *_test.py for Python), then reports the config,
the locator mix and anti-patterns with file and line. Standard library only. Read-only.

Exit codes: 0 no errors, 1 errors (or warnings with --strict), 2 bad input.
"""
import argparse
import json
import os
import re
import sys
from collections import Counter

SKIP_DIRS = {"node_modules", ".git", "dist", "build", "playwright-report", "test-results", "blob-report",
             ".venv", "venv", "__pycache__", ".next", "coverage"}
JS_TEST = re.compile(r"\.(spec|test)\.(ts|tsx|js|jsx|mjs|cjs)$")
PY_TEST = re.compile(r"^(test_.*|.*_test)\.py$")
CONFIG_NAMES = ["playwright.config.ts", "playwright.config.js", "playwright.config.mjs", "playwright.config.cjs",
                "playwright.config.mts", "playwright.config.cts"]

WEB_FIRST = ("toBeVisible|toBeHidden|toBeEnabled|toBeDisabled|toBeChecked|toBeEditable|toBeFocused|toBeAttached|"
             "toBeEmpty|toBeInViewport|toHaveText|toContainText|toHaveValue|toHaveValues|toHaveAttribute|"
             "toHaveClass|toHaveCount|toHaveCSS|toHaveId|toHaveURL|toHaveTitle|toHaveScreenshot|"
             "toMatchAriaSnapshot|toHaveAccessibleName|toHaveRole")

# (id, level, languages, regex, message)
RULES = [
    ("only", "ERROR", "js", re.compile(r"\b(test|describe|it)(\.describe)?\.only\s*\("),
     "test.only left in: other tests are skipped (set forbidOnly in CI)"),
    ("hard-wait", "WARN", "js", re.compile(r"\.waitForTimeout\s*\("),
     "hard wait: wait for a condition instead (web-first assertion, waitForResponse, toHaveURL)"),
    ("hard-wait", "WARN", "py", re.compile(r"\.wait_for_timeout\s*\(|\btime\.sleep\s*\("),
     "hard wait: wait for a condition instead (expect(...), expect_response, to_have_url)"),
    ("missing-await", "ERROR", "js", re.compile(r"^(?!.*\bawait\b)(?!.*\breturn\b).*\bexpect(\.soft|\.poll)?\s*\((?!\s*await).*\.(not\.)?(" + WEB_FIRST + r")\s*\("),
     "web-first assertion without await: it never runs or fails late"),
    ("non-retrying", "WARN", "js", re.compile(r"expect\s*\(\s*await\s+[^;]*\.(isVisible|isHidden|isEnabled|isChecked|textContent|innerText|inputValue|getAttribute|count)\s*\("),
     "non-retrying assertion: use await expect(locator).toBeVisible()/toHaveText()/toHaveCount() instead"),
    ("non-retrying", "WARN", "py", re.compile(r"\bassert\s+[^#\n]*\.(is_visible|is_hidden|is_enabled|is_checked|text_content|inner_text|input_value|get_attribute|count)\s*\("),
     "non-retrying assertion: use expect(locator).to_be_visible()/to_have_text()/to_have_count() instead"),
    ("force", "WARN", "js", re.compile(r"\bforce\s*:\s*true\b"),
     "force: true skips actionability checks and hides real UI problems"),
    ("force", "WARN", "py", re.compile(r"\bforce\s*=\s*True\b"),
     "force=True skips actionability checks and hides real UI problems"),
    ("networkidle", "WARN", "any", re.compile(r"networkidle"),
     "networkidle is discouraged and slow: assert on the content you need instead"),
    ("legacy-handle", "WARN", "js", re.compile(r"\bpage\.\$\$?\s*\(|\.\$eval\s*\(|\.\$\$eval\s*\(|\.waitForSelector\s*\("),
     "legacy ElementHandle / waitForSelector API: use locators (page.getByRole(...), page.locator(...))"),
    ("legacy-handle", "WARN", "py", re.compile(r"\.query_selector(_all)?\s*\(|\.wait_for_selector\s*\("),
     "legacy ElementHandle / wait_for_selector API: use locators (page.get_by_role(...), page.locator(...))"),
    ("xpath", "WARN", "any", re.compile(r"""(locator|\$)\s*\(\s*['"`](xpath=|//|\(//)"""),
     "XPath selector: brittle; prefer getByRole/getByLabel/getByTestId"),
    ("brittle-css", "WARN", "any", re.compile(r"""locator\s*\(\s*['"`][^'"`]*(:nth-child|:nth-of-type|\.css-[a-z0-9]{5,}|\[class\*=|(\s*>\s*[^'"`>]+){3,})"""),
     "brittle CSS (position, generated class or deep chain): prefer user-facing locators or a test id"),
    ("hardcoded-url", "WARN", "any", re.compile(r"""\.goto\s*\(\s*['"`]https?://"""),
     "hard-coded URL: set baseURL (or --base-url) and goto a path, so tests run on every environment"),
    ("credential", "WARN", "any", re.compile(r"""(?i)(password|passwd|secret|token)[^\n]*\.fill\s*\(\s*(['"`][^'"`$]{4,}['"`]\s*\)|[^)]*,\s*['"`][^'"`$]{4,}['"`])|\.fill\s*\([^,]*(password|passwd)[^,]*,\s*['"`][^'"`$]{4,}['"`]"""),
     "credential literal: read it from an environment variable / CI secret"),
    ("pause", "ERROR", "any", re.compile(r"\bpage\.pause\s*\("),
     "page.pause() left in: the test hangs in CI"),
    ("removed-api", "ERROR", "any", re.compile(r"""['"`](_react|_vue)="""),
     "_react= / _vue= selectors were removed in Playwright 1.58: use getByRole/getByTestId"),
    ("removed-api", "ERROR", "any", re.compile(r"\.accessibility\.snapshot\s*\("),
     "page.accessibility was removed in Playwright 1.57: use toMatchAriaSnapshot() / page.ariaSnapshot() or @axe-core/playwright"),
    ("removed-api", "ERROR", "any", re.compile(r"\.ariaRef\s*\(|\bvideosPath\b|\bvideoSize\b|\bvideos_path\b|\bvideo_size\b"),
     "removed in Playwright 1.60 (ariaRef, videosPath/videoSize): use recordVideo / record_video_dir"),
    ("visible-pseudo", "WARN", "any", re.compile(r"""locator\s*\(\s*['"`][^'"`]*:visible"""),
     "':visible' CSS suffix: use locator.visible() (1.63+) or filter({ visible: true })"),
]
LOCATOR_KINDS = [
    ("role", re.compile(r"\.(getByRole|get_by_role)\s*\(")),
    ("label", re.compile(r"\.(getByLabel|get_by_label|getByPlaceholder|get_by_placeholder|getByAltText|get_by_alt_text|getByTitle|get_by_title)\s*\(")),
    ("text", re.compile(r"\.(getByText|get_by_text)\s*\(")),
    ("test-id", re.compile(r"\.(getByTestId|get_by_test_id)\s*\(")),
    ("css/xpath", re.compile(r"\.locator\s*\(\s*['\"`]")),
]
CUSTOM_TESTID = re.compile(r"""\[(data-(?:qa|cy|test|test-id|automation-id|e2e|qa-id|testing))[=\]]""")
SKIP_MARK = re.compile(r"\b(test|describe)(\.describe)?\.(skip|fixme)\s*\(|@pytest\.mark\.skip")


def find_files(root):
    tests, configs, py_settings = [], [], []
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
        for name in sorted(files):
            path = os.path.join(dirpath, name)
            if name in CONFIG_NAMES:
                configs.append(path)
            elif JS_TEST.search(name):
                tests.append((path, "js"))
            elif PY_TEST.match(name):
                tests.append((path, "py"))
            elif name in ("pytest.ini", "pyproject.toml", "setup.cfg", "conftest.py"):
                py_settings.append(path)
    return tests, configs, py_settings


def _read(path):
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        return fh.read()


def _strip_comment(line, lang):
    stripped = line.strip()
    if lang == "py":
        return "" if stripped.startswith("#") else line
    return "" if stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/*") else line


def audit_tests(root, tests):
    findings, locators, testids, skipped = [], Counter(), Counter(), 0
    uses_playwright = 0
    for path, lang in tests:
        text = _read(path)
        if "playwright" not in text and "page" not in text:
            continue
        uses_playwright += 1
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        for n, raw in enumerate(text.splitlines(), 1):
            line = _strip_comment(raw, lang)
            if not line.strip():
                continue
            for rid, level, langs, rx, msg in RULES:
                if langs in ("any", lang) and rx.search(line):
                    findings.append({"level": level, "rule": rid, "file": rel, "line": n, "message": msg,
                                     "code": raw.strip()[:140]})
            for kind, rx in LOCATOR_KINDS:
                locators[kind] += len(rx.findall(line))
            for attr in CUSTOM_TESTID.findall(line):
                testids[attr] += 1
            skipped += len(SKIP_MARK.findall(line))
    return findings, locators, testids, skipped, uses_playwright


def _config_value(text, key):
    m = re.search(r"\b" + key + r"""\s*:\s*([^,\n}]+)""", text)
    return m.group(1).strip() if m else None


def audit_config(root, configs, py_settings, has_js, has_py, testids):
    info, findings = {}, []
    if configs:
        path = configs[0]
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        text = _read(path)
        info["config"] = rel
        for key in ("baseURL", "retries", "trace", "forbidOnly", "fullyParallel", "workers", "testIdAttribute",
                    "screenshot", "video", "timeout"):
            info[key] = _config_value(text, key)
        info["projects"] = re.findall(r"""name\s*:\s*['"`]([^'"`]+)['"`]""", text)
        info["webServer"] = bool(re.search(r"\bwebServer\s*:", text))
        info["reporter"] = _config_value(text, "reporter")

        def add(level, msg):
            findings.append({"level": level, "rule": "config", "file": rel, "line": 0, "message": msg, "code": ""})
        if not info["baseURL"]:
            add("WARN", "no baseURL: tests need full URLs and cannot switch environment (use process.env.BASE_URL)")
        if not info["forbidOnly"]:
            add("WARN", "no forbidOnly: a stray test.only can silently skip the suite in CI (forbidOnly: !!process.env.CI)")
        if not info["retries"]:
            add("INFO", "no retries: retries on CI (retries: process.env.CI ? 2 : 0) separate flaky from broken tests")
        if not info["trace"]:
            add("WARN", "no trace setting: set trace: 'on-first-retry' so CI failures can be debugged")
        elif "'on'" in info["trace"] or '"on"' in info["trace"]:
            add("INFO", "trace: 'on' records every test (slow, large); 'on-first-retry' or 'retain-on-failure' is usual")
    elif has_js:
        findings.append({"level": "WARN", "rule": "config", "file": "", "line": 0, "code": "",
                         "message": "no playwright.config.* found: run `npm init playwright@latest` or add one"})
    if has_py:
        settings = "\n".join(_read(p) for p in py_settings)
        info["pytest_base_url"] = bool(re.search(r"base[_-]url", settings))
        if not info["pytest_base_url"]:
            findings.append({"level": "INFO", "rule": "config", "file": "", "line": 0, "code": "",
                             "message": "no base_url for pytest-playwright: add --base-url to pytest addopts"})
    if testids:
        attr, _ = testids.most_common(1)[0]
        configured = (info.get("testIdAttribute") or "").strip("'\"` ")
        if configured != attr:
            findings.append({"level": "INFO", "rule": "test-id", "file": info.get("config", ""), "line": 0, "code": "",
                             "message": f"selectors use [{attr}=...] {testids[attr]} time(s): set testIdAttribute: "
                                        f"'{attr}' (Python: selectors.set_test_id_attribute) and use getByTestId"})
    return info, findings


def audit(root):
    tests, configs, py_settings = find_files(root)
    findings, locators, testids, skipped, used = audit_tests(root, tests)
    has_js = any(l == "js" for _, l in tests)
    has_py = any(l == "py" for _, l in tests)
    info, cfg_findings = audit_config(root, configs, py_settings, has_js, has_py, testids)
    total = sum(locators.values())
    good = locators["role"] + locators["label"] + locators["test-id"] + locators["text"]
    summary = {"root": os.path.abspath(root), "test_files": used, "config": info,
               "locators": dict(locators), "user_facing_locator_share": round(good / total, 2) if total else None,
               "skipped_or_fixme": skipped, "findings": cfg_findings + findings}
    if total and good / total < 0.5:
        summary["findings"].insert(0, {"level": "WARN", "rule": "locators", "file": "", "line": 0, "code": "",
                                       "message": f"only {good}/{total} locators are user-facing (role/label/text/test id); "
                                                  "CSS/XPath-heavy suites break on every redesign"})
    return summary


def format_text(s):
    out = [f"Playwright audit: {s['root']}", f"Test files: {s['test_files']}"]
    cfg = s["config"]
    if cfg.get("config"):
        out.append(f"Config: {cfg['config']}")
        for key in ("baseURL", "retries", "trace", "forbidOnly", "fullyParallel", "workers", "testIdAttribute", "reporter"):
            out.append(f"  {key:<16} {cfg.get(key) or '-'}")
        out.append(f"  {'projects':<16} {', '.join(cfg.get('projects') or []) or '-'}")
        out.append(f"  {'webServer':<16} {'yes' if cfg.get('webServer') else 'no'}")
    loc = s["locators"]
    if loc:
        out.append("Locators: " + ", ".join(f"{k} {v}" for k, v in sorted(loc.items(), key=lambda kv: -kv[1]))
                   + (f"   (user-facing share {s['user_facing_locator_share']:.0%})" if s["user_facing_locator_share"] is not None else ""))
    if s["skipped_or_fixme"]:
        out.append(f"Skipped / fixme: {s['skipped_or_fixme']}  (each should link to a ticket)")
    counts = Counter(f["level"] for f in s["findings"])
    out.append(f"\nFindings: {counts.get('ERROR', 0)} error(s), {counts.get('WARN', 0)} warning(s), {counts.get('INFO', 0)} note(s)")
    order = {"ERROR": 0, "WARN": 1, "INFO": 2}
    for f in sorted(s["findings"], key=lambda f: (order[f["level"]], f["file"], f["line"])):
        where = f"{f['file']}:{f['line']}" if f["line"] else (f["file"] or "(project)")
        out.append(f"  {f['level']:<5} {where}  {f['message']}")
        if f["code"]:
            out.append(f"        {f['code']}")
    by_rule = Counter(f["rule"] for f in s["findings"] if f["line"])
    if by_rule:
        out.append("\nMost common: " + ", ".join(f"{r} x{n}" for r, n in by_rule.most_common(5)))
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project", help="project folder (the one with playwright.config.* or the tests)")
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    ap.add_argument("--strict", action="store_true", help="fail on warnings too")
    opts = ap.parse_args(argv)
    if not os.path.isdir(opts.project):
        print(f"not a folder: {opts.project}", file=sys.stderr)
        return 2
    s = audit(opts.project)
    print(json.dumps(s, indent=2) if opts.json else format_text(s))
    levels = {f["level"] for f in s["findings"]}
    return 1 if "ERROR" in levels or (opts.strict and "WARN" in levels) else 0


if __name__ == "__main__":
    sys.exit(main())
