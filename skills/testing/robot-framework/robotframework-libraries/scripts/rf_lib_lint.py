#!/usr/bin/env python3
"""Review a Robot Framework Python keyword library (static analysis, nothing is imported or run).

Usage:
    python rf_lib_lint.py <library.py or folder> [--json] [--strict]

Lists the keywords and flags: missing docstrings and type hints, secret-like arguments not typed
Secret (RF 7.4), print() instead of robot.api.logger, class libraries without an explicit scope,
BuiltIn().get_variable_value(..., default=...) (positional-only since 7.4), and deprecated
robot.utils helpers. Standard library only.

Exit codes: 0 no warnings/errors, 1 warnings (only with --strict) or errors, 2 bad input.
"""
import argparse
import ast
import json
import os
import re
import sys

SECRET_ARG = re.compile(r"(?i)(password|passwd|secret|token|api_?key|credential)")
DEPRECATED_UTILS = {
    "is_string": "7.3", "is_bytes": "7.3", "is_number": "7.3", "is_integer": "7.3", "is_pathlike": "7.3",
    "ET": "7.3", "read_rest_data": "7.5", "split_tags_from_doc": "7.5", "is_union": "7.5",
}
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", "results", "build", "dist"}


def _decorator_name(dec):
    target = dec.func if isinstance(dec, ast.Call) else dec
    if isinstance(target, ast.Attribute):
        return target.attr
    if isinstance(target, ast.Name):
        return target.id
    return ""


def _keyword_name(func):
    for dec in func.decorator_list:
        if _decorator_name(dec) == "keyword" and isinstance(dec, ast.Call):
            if dec.args and isinstance(dec.args[0], ast.Constant) and isinstance(dec.args[0].value, str):
                return dec.args[0].value
            for kw in dec.keywords:
                if kw.arg == "name" and isinstance(kw.value, ast.Constant):
                    return kw.value.value
    return func.name.replace("_", " ").title()


def _is_keyword(func, auto_keywords):
    if any(_decorator_name(d) == "not_keyword" for d in func.decorator_list):
        return False
    if any(_decorator_name(d) == "keyword" for d in func.decorator_list):
        return True
    return auto_keywords and not func.name.startswith("_")


def _annotation_text(node):
    try:
        return ast.unparse(node) if node is not None else None      # novermin (Python 3.9+, guarded)
    except AttributeError:
        return "?" if node is not None else None


def check_function(func, rel, owner, findings, keywords):
    name = _keyword_name(func)
    keywords.append({"keyword": name, "python": f"{owner + '.' if owner else ''}{func.name}", "file": rel,
                     "line": func.lineno, "async": isinstance(func, ast.AsyncFunctionDef)})

    def add(level, rule, msg, line=None):
        findings.append({"level": level, "rule": rule, "file": rel, "line": line or func.lineno,
                         "keyword": name, "message": msg})
    if not ast.get_docstring(func):
        add("WARN", "no-doc", f"'{name}' has no docstring: Libdoc and IDEs show nothing")
    args = func.args.posonlyargs + func.args.args + func.args.kwonlyargs
    args = [a for a in args if a.arg not in ("self", "cls")]
    untyped = [a.arg for a in args if a.annotation is None]
    if untyped:
        add("INFO", "no-types", f"'{name}': no type hints for {', '.join(untyped)} (values arrive as strings, Libdoc shows no types)")
    for a in args:
        ann = _annotation_text(a.annotation)
        if SECRET_ARG.search(a.arg) and (ann is None or ann.strip() in ("str", "Optional[str]", "str | None")):
            add("WARN", "secret-arg", f"'{name}': argument '{a.arg}' looks secret: type it Secret (or str | Secret) so it is never logged (RF 7.4+)")
    for node in ast.walk(func):
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name) and fn.id == "print":
                add("INFO", "print", f"'{name}' uses print(): use robot.api.logger (info/debug/console)", node.lineno)
            if isinstance(fn, ast.Attribute) and fn.attr == "get_variable_value" and any(k.arg == "default" for k in node.keywords):
                add("WARN", "positional-only", "BuiltIn().get_variable_value(default=...): BuiltIn arguments are positional-only since RF 7.4", node.lineno)
        if isinstance(node, ast.ExceptHandler) and isinstance(node.type, ast.Name) and node.type.id == "BaseException":
            add("WARN", "base-exception", f"'{name}' catches BaseException: it also swallows RF timeouts (TimeoutExceeded, RF 7.5)", node.lineno)


def lint_file(path, rel):
    with open(path, encoding="utf-8-sig") as fh:
        source = fh.read()
    tree = ast.parse(source, filename=path)
    findings, keywords = [], []
    module_name = os.path.splitext(os.path.basename(path))[0]

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("robot.utils"):
            for alias in node.names:
                if alias.name in DEPRECATED_UTILS:
                    findings.append({"level": "WARN", "rule": "deprecated-utils", "file": rel, "line": node.lineno, "keyword": "",
                                     "message": f"robot.utils.{alias.name} is deprecated (RF {DEPRECATED_UTILS[alias.name]}): "
                                                + ("use xml.etree.ElementTree" if alias.name == "ET" else "use isinstance()/standard library")})
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "utils" and node.attr in DEPRECATED_UTILS:
            findings.append({"level": "WARN", "rule": "deprecated-utils", "file": rel, "line": node.lineno, "keyword": "",
                             "message": f"robot.utils.{node.attr} is deprecated (RF {DEPRECATED_UTILS[node.attr]})"})

    classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    lib_classes = []
    for cls in classes:
        decs = {_decorator_name(d): d for d in cls.decorator_list}
        if "library" in decs or cls.name == module_name:
            lib_classes.append((cls, decs.get("library")))
    if lib_classes:
        for cls, dec in lib_classes:
            auto = dec is None                     # @library defaults to auto_keywords=False
            scope = None
            if isinstance(dec, ast.Call):
                for kw in dec.keywords:
                    if kw.arg == "auto_keywords" and isinstance(kw.value, ast.Constant):
                        auto = bool(kw.value.value)
                    if kw.arg == "scope":
                        scope = _annotation_text(kw.value)
            for item in cls.body:
                if isinstance(item, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "ROBOT_LIBRARY_SCOPE" for t in item.targets):
                    scope = _annotation_text(item.value)
            if scope is None:
                findings.append({"level": "INFO", "rule": "scope", "file": rel, "line": cls.lineno, "keyword": "",
                                 "message": f"class {cls.name} has no explicit scope: default TEST creates a new instance per test; "
                                            "use scope='SUITE' or 'GLOBAL' for clients and connections"})
            if not ast.get_docstring(cls):
                findings.append({"level": "INFO", "rule": "no-intro", "file": rel, "line": cls.lineno, "keyword": "",
                                 "message": f"class {cls.name} has no docstring: it becomes the Libdoc introduction"})
            for item in cls.body:
                if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) or item.name == "__init__":
                    continue
                if _is_keyword(item, auto):
                    check_function(item, rel, cls.name, findings, keywords)
                elif (not item.name.startswith("_") and not any(_decorator_name(d) == "not_keyword" for d in item.decorator_list)
                      and not any(_decorator_name(d) in ("property", "staticmethod", "classmethod") for d in item.decorator_list)):
                    findings.append({"level": "INFO", "rule": "not-exposed", "file": rel, "line": item.lineno, "keyword": "",
                                     "message": f"public method {cls.name}.{item.name} is not a keyword: @library exposes only "
                                                "@keyword methods unless auto_keywords=True (mark helpers @not_keyword or _private)"})
    else:
        decorated = any(_decorator_name(d) == "keyword" for n in tree.body
                        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) for d in n.decorator_list)
        for item in tree.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_keyword(item, not decorated):
                check_function(item, rel, "", findings, keywords)
    return findings, keywords


def lint(path):
    files = []
    if os.path.isfile(path):
        files = [(path, os.path.basename(path))]
    else:
        for dirpath, dirs, names in os.walk(path):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
            for n in sorted(names):
                if n.endswith(".py") and not n.startswith("test_") and n != "__init__.py":
                    full = os.path.join(dirpath, n)
                    files.append((full, os.path.relpath(full, path).replace(os.sep, "/")))
    findings, keywords, errors = [], [], []
    for full, rel in files:
        try:
            f, k = lint_file(full, rel)
        except (SyntaxError, UnicodeDecodeError) as exc:
            errors.append(f"{rel}: cannot parse ({exc})")
            continue
        findings += f
        keywords += k
    return {"files": len(files), "keywords": keywords, "findings": findings, "errors": errors}


def format_text(r):
    out = [f"Files: {r['files']}   Keywords: {len(r['keywords'])}"]
    for k in r["keywords"]:
        out.append(f"  {k['keyword']:<45} {k['python']}{' (async)' if k['async'] else ''}  ({k['file']}:{k['line']})")
    for e in r["errors"]:
        out.append(f"  ERROR {e}")
    order = {"ERROR": 0, "WARN": 1, "INFO": 2}
    if r["findings"]:
        out.append("\nFindings:")
        for f in sorted(r["findings"], key=lambda f: (order[f["level"]], f["file"], f["line"])):
            out.append(f"  {f['level']:<5} {f['file']}:{f['line']}  {f['message']}")
    else:
        out.append("\nNo findings.")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("path", help="library .py file or a folder of libraries")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="fail on warnings too")
    opts = ap.parse_args(argv)
    if not os.path.exists(opts.path):
        print(f"not found: {opts.path}", file=sys.stderr)
        return 2
    r = lint(opts.path)
    print(json.dumps(r, indent=2) if opts.json else format_text(r))
    if r["errors"]:
        return 1
    return 1 if opts.strict and any(f["level"] == "WARN" for f in r["findings"]) else 0


if __name__ == "__main__":
    sys.exit(main())
