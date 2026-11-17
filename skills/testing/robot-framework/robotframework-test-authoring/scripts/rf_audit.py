#!/usr/bin/env python3
"""Audit Robot Framework suites for outdated, deprecated or risky syntax (checked against RF 7.5).

Usage:
    python rf_audit.py <dir-or-file> [--json] [--strict] [--max-steps 30]

Reads *.robot, *.resource and *.robot.md (robotframework code blocks) plus argument files and CI
scripts, and reports: modern features in use, features newer than the pinned Robot Framework version,
removed/deprecated syntax, hard sleeps, literal secrets, long tests and undocumented keywords.
Read-only; standard library only. For full linting and formatting use Robocop.

Exit codes: 0 no errors, 1 errors (or warnings with --strict), 2 bad input.
"""
import argparse
import json
import os
import re
import sys
from collections import Counter

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "results", "output", "reports", "dist", "build"}
SEP = re.compile(r"\s{2,}|\t| \| ")
SECRET_NAME = re.compile(r"(?i)(password|passwd|pwd|secret|token|api_?key|credential)")
ARG_FILES = re.compile(r"(\.args|\.sh|\.bat|\.ps1|\.ya?ml|\.toml|\.cfg|\.ini)$|^(Jenkinsfile|Makefile)$", re.I)

# feature -> (min version, regex on a step/setting line)
FEATURES = {
    "VAR": ((7, 0), re.compile(r"^VAR$")),
    "keyword [Setup]": ((7, 0), None),
    "GROUP": ((7, 2), re.compile(r"^GROUP$")),
    "typed variables ${x: type}": ((7, 3), re.compile(r"[$@&]\{[^}:]+: [^}]+\}")),
    "Secret variables": ((7, 4), re.compile(r"[$@&]\{[^}:]+: *Secret\}")),
    "[Metadata] in tests": ((7, 5), re.compile(r"^\[Metadata\]$")),
    "Markdown tests (*.robot.md)": ((7, 5), None),
    "TRY/EXCEPT": ((5, 0), re.compile(r"^TRY$")),
    "WHILE": ((5, 0), re.compile(r"^WHILE$")),
    "RETURN": ((5, 0), re.compile(r"^RETURN$")),
    "BREAK/CONTINUE": ((5, 0), re.compile(r"^(BREAK|CONTINUE)$")),
    "IF/ELSE": ((4, 0), re.compile(r"^IF$")),
}

# (rule, level, regex on the first keyword/setting token, message)
STEP_RULES = [
    ("old-for", "ERROR", re.compile(r"^:FOR$", re.I), "old ':FOR' syntax was removed: use FOR ... END"),
    ("return-setting", "WARN", re.compile(r"^\[Return\]$"), "[Return] is deprecated (RF 7.0): use RETURN"),
    ("loop-keywords", "WARN", re.compile(r"^(Exit For Loop|Exit For Loop If|Continue For Loop|Continue For Loop If)$", re.I),
     "loop control keywords are superseded: use BREAK / CONTINUE (with inline IF)"),
    ("run-keyword-if", "WARN", re.compile(r"^(Run Keyword If|Run Keyword Unless)$", re.I),
     "Run Keyword If/Unless is superseded: use IF / ELSE IF / ELSE / END or inline IF"),
    ("return-keywords", "WARN", re.compile(r"^(Return From Keyword|Return From Keyword If|Run Keyword And Return If)$", re.I),
     "use RETURN (with inline IF) instead of the Return From Keyword family"),
    ("set-variable", "INFO", re.compile(r"^(Set Test Variable|Set Task Variable|Set Suite Variable|Set Global Variable|Set Local Variable)$", re.I),
     "prefer VAR with scope=TEST|SUITE|GLOBAL (RF 7.0+)"),
    ("os-run", "WARN", re.compile(r"^(OperatingSystem\.)?(Run|Run And Return Rc|Run And Return Rc And Output)$", re.I),
     "OperatingSystem Run* keywords are deprecated (more visibly since RF 7.4): use Process.Run Process"),
    ("sleep", "WARN", re.compile(r"^(BuiltIn\.)?Sleep$", re.I),
     "hard Sleep: wait for a condition (library wait keywords, Wait Until Keyword Succeeds)"),
]
SETTING_RULES = [
    ("force-tags", "WARN", re.compile(r"^(Force Tags|Default Tags)$", re.I), "Force Tags / Default Tags are deprecated: use Test Tags (and [Tags] with -tag to remove)"),
    ("telnet", "WARN", re.compile(r"^Library$", re.I), None),   # value checked below
]


def tokens(line):
    return [t for t in SEP.split(line.strip()) if t != ""]


def rf_lines(path):
    """Robot data lines (number, text). For *.md only lines inside robotframework code blocks."""
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        lines = fh.read().splitlines()
    if not path.lower().endswith(".md"):
        return list(enumerate(lines, 1))
    out, inside = [], False
    for n, line in enumerate(lines, 1):
        s = line.strip()
        if s.startswith("```"):
            inside = s[3:].strip().lower().startswith("robotframework") if not inside else False
            continue
        if inside:
            out.append((n, line))
    return out


def find_files(root):
    if os.path.isfile(root):
        return [root], []
    data, other = [], []
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and (not d.startswith(".") or d == ".github"))
        for name in sorted(files):
            path = os.path.join(dirpath, name)
            low = name.lower()
            if low.endswith((".robot", ".resource", ".robot.md")):
                data.append(path)
            elif ARG_FILES.search(name):
                other.append(path)
    return data, other


def rf_version(root):
    base = root if os.path.isdir(root) else os.path.dirname(os.path.abspath(root))
    for cand in (base, os.path.dirname(os.path.abspath(base))):
        for name in ("requirements.txt", "requirements-dev.txt", "pyproject.toml", "setup.cfg", "Pipfile"):
            path = os.path.join(cand, name)
            if os.path.isfile(path):
                with open(path, encoding="utf-8-sig", errors="replace") as fh:
                    m = re.search(r"""(?<![\w-])robotframework\s*["']?\s*(?:==|>=|~=|=)\s*["']?(\d+)\.(\d+)""", fh.read(), re.I)
                if m:
                    return (int(m.group(1)), int(m.group(2))), os.path.relpath(path, base) if cand == base else path
    return None, None


def audit_file(path, rel, findings, features, stats, max_steps):
    section, item, item_steps, item_line, item_doc, item_kind = None, None, 0, 0, False, None

    def close_item():
        if item is None:
            return
        if item_kind == "test" and item_steps > max_steps:
            add("INFO", "long-test", item_line, f"'{item}' has {item_steps} steps: split it or move steps into keywords", "")
        if item_kind == "keyword" and not item_doc:
            stats["undocumented_keywords"].append(f"{rel}:{item_line} {item}")

    def add(level, rule, line, message, code):
        findings.append({"level": level, "rule": rule, "file": rel, "line": line, "message": message, "code": code.strip()[:140]})

    if path.lower().endswith(".md"):
        features["Markdown tests (*.robot.md)"] += 1
    for n, raw in rf_lines(path):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.startswith("*"):
            close_item()
            item = None
            low = raw.strip("* \t").lower()
            section = ("settings" if low.startswith("setting") else "variables" if low.startswith("variable") else
                       "tests" if low.startswith(("test case", "task")) else "keywords" if low.startswith("keyword") else "other")
            continue
        toks = tokens(raw)
        if not toks:
            continue
        if section in ("tests", "keywords") and not raw[0].isspace():
            close_item()
            item, item_steps, item_line, item_doc = toks[0], 0, n, False
            item_kind = "test" if section == "tests" else "keyword"
            toks = toks[1:]
            if not toks:
                continue
        # feature usage
        for name, (_, rx) in FEATURES.items():
            if rx is not None and any(rx.search(t) for t in toks):
                features[name] += 1
        if section == "settings":
            first = toks[0]
            if re.match(r"^(Force Tags|Default Tags)$", first, re.I):
                add("INFO", "force-tags", n, "Force Tags / Default Tags are superseded by Test Tags (RF 6.0+); use [Tags] with -tag to remove", raw)
            if re.match(r"^Library$", first, re.I) and len(toks) > 1 and toks[1].lower() == "telnet":
                add("WARN", "telnet", n, "built-in Telnet library: deprecated (RF 7.5) and fails to import on Python 3.13+ "
                                         "(telnetlib was removed): install the external TelnetLibrary", raw)
            continue
        if section == "variables":
            name = toks[0]
            value = toks[1] if len(toks) > 1 else ""
            typed_secret = re.search(r":\s*Secret\}", name)
            literal = value and not value.startswith(("%{", "${", "@{", "&{")) and value not in ("${EMPTY}", "${NONE}")
            if typed_secret and literal and "${" not in value and "%{" not in value:
                add("ERROR", "secret-literal", n, "a Secret variable cannot have a literal value (RF 7.4): use %{ENV_VAR}", raw)
            elif SECRET_NAME.search(name) and literal and not typed_secret:
                add("WARN", "literal-secret", n, f"{name} holds a literal value: use ${{NAME: Secret}}    %{{ENV_VAR}} (RF 7.4+) and the CI secret store", raw)
            continue
        if section in ("tests", "keywords"):
            first = toks[0]
            if first.lower() == "[documentation]":
                item_doc = True
            if first == "[Setup]" and item_kind == "keyword":
                features["keyword [Setup]"] += 1
            if not first.startswith("["):
                item_steps += 1
            kw_tokens = [t for t in toks if not re.match(r"^[$@&]\{.*\}=?$", t)]
            kw = kw_tokens[0] if kw_tokens else ""
            for rule, level, rx, message in STEP_RULES:
                if rx.match(kw) or (rule in ("old-for", "return-setting") and rx.match(first)):
                    add(level, rule, n, message, raw)
            if first == "VAR" and len(toks) == 3 and re.match(r"(?i)^scope=(?!local)", toks[2]):
                add("WARN", "var-no-value", n, "VAR without a value in a non-local scope is deprecated (RF 7.4): give ${EMPTY} explicitly", raw)
            if "NO VALUES" in toks:
                add("WARN", "no-values", n, "NO VALUES is deprecated (RF 7.4): use values=False", raw)
    close_item()


def audit_other(path, rel, findings):
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        for n, line in enumerate(fh, 1):
            if not re.search(r"\b(robot|pabot|rebot|testdoc)\b|--(include|exclude)|^\s*-[ie]\s", line):
                continue
            for m in re.finditer(r"(?:--include|--exclude|-i|-e)[ =]+['\"]?([^\s'\"]+)", line):
                pattern = m.group(1)
                # Deprecated in 7.5: operators glued to UPPERCASE operands (XORY) and '&'. 'xORy' stays valid.
                if re.search(r"[A-Z0-9](AND|OR|NOT)|(AND|OR|NOT)[A-Z0-9]", pattern.replace(" AND ", " ").replace(" OR ", " ").replace(" NOT ", " ")) or "&" in pattern:
                    findings.append({"level": "WARN", "rule": "tag-pattern", "file": rel, "line": n, "code": line.strip()[:140],
                                     "message": f"tag pattern '{pattern}' uses a form deprecated in RF 7.5 ('XORY' or '&'): write 'X OR Y' with spaces and AND instead of &"})
            if re.search(r"\btestdoc\b", line):
                findings.append({"level": "INFO", "rule": "testdoc", "file": rel, "line": n, "code": line.strip()[:140],
                                 "message": "built-in testdoc is deprecated (RF 7.4.2+): use the external Testdoc tool"})


def audit(root, max_steps=30):
    data, other = find_files(root)
    base = root if os.path.isdir(root) else os.path.dirname(os.path.abspath(root))
    findings, features = [], Counter()
    stats = {"undocumented_keywords": []}
    for path in data:
        audit_file(path, os.path.relpath(path, base).replace(os.sep, "/"), findings, features, stats, max_steps)
    for path in other:
        audit_other(path, os.path.relpath(path, base).replace(os.sep, "/"), findings)
    version, version_file = rf_version(root)
    if version:
        for name, count in features.items():
            need = FEATURES[name][0]
            if count and version < need:
                findings.append({"level": "ERROR", "rule": "version", "file": version_file, "line": 0, "code": "",
                                 "message": f"suites use {name} ({count}x) which needs Robot Framework {need[0]}.{need[1]}+, "
                                            f"but {version[0]}.{version[1]} is pinned"})
    undocumented = stats["undocumented_keywords"]
    if undocumented:
        findings.append({"level": "INFO", "rule": "undocumented", "file": "", "line": 0, "code": "",
                         "message": f"{len(undocumented)} user keyword(s) without [Documentation], e.g. " + "; ".join(undocumented[:3])})
    return {"root": os.path.abspath(root), "files": len(data), "robot_framework": "%d.%d" % version if version else None,
            "features": dict(features), "findings": findings}


def format_text(s):
    out = [f"Robot Framework audit: {s['root']}", f"Suite/resource files: {s['files']}",
           f"Pinned Robot Framework: {s['robot_framework'] or 'not found in requirements'}"]
    used = [f"{k} {v}" for k, v in sorted(s["features"].items(), key=lambda kv: -kv[1]) if v]
    out.append("Modern features in use: " + (", ".join(used) if used else "none"))
    missing = [k for k in ("VAR", "typed variables ${x: type}", "Secret variables", "GROUP") if not s["features"].get(k)]
    if missing:
        out.append("Not used yet: " + ", ".join(missing))
    counts = Counter(f["level"] for f in s["findings"])
    out.append(f"\nFindings: {counts.get('ERROR', 0)} error(s), {counts.get('WARN', 0)} warning(s), {counts.get('INFO', 0)} note(s)")
    order = {"ERROR": 0, "WARN": 1, "INFO": 2}
    for f in sorted(s["findings"], key=lambda f: (order[f["level"]], f["file"] or "", f["line"])):
        where = f"{f['file']}:{f['line']}" if f["line"] else (f["file"] or "(project)")
        out.append(f"  {f['level']:<5} {where}  {f['message']}")
        if f["code"]:
            out.append(f"        {f['code']}")
    by_rule = Counter(f["rule"] for f in s["findings"] if f["line"])
    if by_rule:
        out.append("\nMost common: " + ", ".join(f"{r} x{n}" for r, n in by_rule.most_common(6)))
    out.append("For a full lint and auto-format: pip install robotframework-robocop; robocop check; robocop format")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("path", help="folder with suites (or one .robot / .resource / .robot.md file)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="fail on warnings too")
    ap.add_argument("--max-steps", type=int, default=30, help="flag tests with more steps than this (default 30)")
    opts = ap.parse_args(argv)
    if not os.path.exists(opts.path):
        print(f"not found: {opts.path}", file=sys.stderr)
        return 2
    s = audit(opts.path, opts.max_steps)
    print(json.dumps(s, indent=2) if opts.json else format_text(s))
    levels = {f["level"] for f in s["findings"]}
    return 1 if "ERROR" in levels or (opts.strict and "WARN" in levels) else 0


if __name__ == "__main__":
    sys.exit(main())
