#!/usr/bin/env python3
"""Python tutor: study notes for any .py file, from beginner to advanced, for interview preparation.

    analyze   parse a .py file (or every .py file in a folder) WITHOUT running it, find the Python concepts it uses,
              split it into blocks, and write <name>.model.json, <name>.notes.json and <name>.html
    render    rebuild the HTML after you wrote explanations into <name>.notes.json
    check     report which blocks still have no explanation (exit 1 if any)

Python 3.8+, standard library only. It reads the file as text with the ast module and never imports or executes it.

    python py_tutor.py analyze path/to/file.py
    python py_tutor.py analyze path/to/folder --out notes
    python py_tutor.py render python-tutor/file
    python py_tutor.py check  python-tutor/file
"""
from __future__ import annotations

import argparse
import ast
import builtins
import hashlib
import html
import io
import json
import os
import re
import sys
import tokenize

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from py_tutor_concepts import CONCEPTS, FUNDAMENTALS, LEVELS, ORDER  # noqa: E402
from py_tutor_behaviour import functionality, loose_concepts, loose_gotchas, loose_outline, loose_py2  # noqa: E402

TODO = "TODO(tutor)"
MAX_BYTES = 1_000_000
MAX_FILES = 200
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".tox", ".mypy_cache", ".pytest_cache",
             "build", "dist", ".idea", ".vscode", "site-packages"}
OPERATOR_DUNDERS = {"__add__", "__sub__", "__mul__", "__truediv__", "__floordiv__", "__mod__", "__pow__",
                    "__eq__", "__ne__", "__lt__", "__le__", "__gt__", "__ge__", "__radd__", "__rmul__",
                    "__neg__", "__getitem__", "__setitem__", "__contains__", "__and__", "__or__", "__iadd__"}
MODULE_CONCEPT = {"re": "regex", "json": "json-data", "os": "filesystem", "pathlib": "filesystem",
                  "shutil": "filesystem", "glob": "filesystem", "logging": "logging", "argparse": "cli-args",
                  "unittest": "testing", "pytest": "testing", "doctest": "testing", "enum": "enums",
                  "collections": "collections-module", "functools": "functools-itertools",
                  "itertools": "functools-itertools", "threading": "concurrency",
                  "multiprocessing": "concurrency", "concurrent": "concurrency", "asyncio": "async-await",
                  "dataclasses": "dataclasses", "abc": "abc",
                  "math": "time-random-math", "random": "time-random-math", "time": "time-random-math",
                  "datetime": "time-random-math", "secrets": "time-random-math", "typing": "type-hints"}
STD_DOC = {"os": "operating-system functions and environment variables", "sys": "interpreter details such as argv and exit",
           "re": "regular expressions", "json": "reading and writing JSON", "math": "mathematical functions",
           "random": "random numbers", "time": "time and sleeping", "datetime": "dates and times",
           "pathlib": "object-oriented file paths", "collections": "specialised containers (Counter, deque, defaultdict)",
           "itertools": "efficient iteration tools", "functools": "higher-order function tools (lru_cache, partial, wraps)",
           "typing": "type hints", "dataclasses": "auto-generated data classes", "abc": "abstract base classes",
           "enum": "enumerations", "logging": "logging", "argparse": "command-line parsing", "subprocess": "running other programs",
           "threading": "threads", "multiprocessing": "processes", "asyncio": "asynchronous I/O", "unittest": "unit tests",
           "csv": "CSV files", "sqlite3": "SQLite databases", "shutil": "file copying and removal", "glob": "file name patterns",
           "copy": "shallow and deep copies", "string": "string constants and helpers", "io": "in-memory streams",
           "heapq": "heaps and priority queues", "bisect": "binary search on sorted lists", "statistics": "basic statistics",
           "decimal": "exact decimal arithmetic", "fractions": "rational numbers", "hashlib": "hash functions",
           "uuid": "unique identifiers", "urllib": "URL handling and simple HTTP", "http": "HTTP clients and servers",
           "socket": "network sockets", "tempfile": "temporary files", "traceback": "stack traces", "contextlib": "context-manager helpers",
           "operator": "operators as functions", "pickle": "object serialisation (unsafe on untrusted data)",
           "textwrap": "wrapping text", "pprint": "pretty printing", "secrets": "secure random values",
           "concurrent": "thread and process pools", "queue": "thread-safe queues", "platform": "system information"}
SECRET_RE = re.compile(r"(password|passwd|secret|token|api[_-]?key|apikey|private[_-]?key|credential|auth[_-]?key)", re.I)
BUILTIN_NAMES = {n for n in dir(builtins) if n.islower() and not n.startswith("_")}
SHADOW = {"list", "dict", "set", "str", "int", "float", "id", "type", "input", "sum", "max", "min", "len", "object",
          "format", "filter", "map", "all", "any", "next", "iter", "hash", "bytes", "range", "zip", "sorted", "file",
          "open", "print", "tuple", "bool", "dir", "vars", "round", "abs", "chr", "ord"} & (BUILTIN_NAMES | {"file"})
STDLIB = set(getattr(sys, "stdlib_module_names", ())) | set(STD_DOC)


# ------------------------------------------------------------------ concept detection
def _names(node):
    """Dotted name of a Name/Attribute chain, else ''."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return ""


def _decor_names(node):
    out = []
    for d in getattr(node, "decorator_list", []):
        d = d.func if isinstance(d, ast.Call) else d
        out.append(_names(d))
    return out


def is_docstring_stmt(stmt) -> bool:
    return (isinstance(stmt, ast.Expr) and isinstance(getattr(stmt, "value", None), ast.Constant)
            and isinstance(stmt.value.value, str))


def is_main_guard(node) -> bool:
    if not isinstance(node, ast.If) or not isinstance(node.test, ast.Compare):
        return False
    t = node.test
    return (isinstance(t.left, ast.Name) and t.left.id == "__name__" and len(t.comparators) == 1
            and isinstance(t.comparators[0], ast.Constant) and t.comparators[0].value == "__main__")


def detect(root, skip_defs: bool = False, fn_name: str = "") -> dict:
    """Map concept id -> sorted list of line numbers, for the nodes under root."""
    out: dict = {}

    def add(cid, node):
        out.setdefault(cid, []).append(getattr(node, "lineno", 0))

    def visit(node, fn, depth, in_loop):
        t = type(node).__name__
        if t in ("Assign", "AugAssign", "AnnAssign"):
            add("variables", node)
            if t == "AnnAssign":
                add("type-hints", node)
            if t == "Assign" and any(isinstance(x, (ast.Tuple, ast.List)) for x in node.targets):
                add("unpacking", node)
            if t == "Assign" and any(isinstance(x, ast.Name) and x.id == "__slots__" for x in node.targets):
                add("slots", node)
        elif t == "BinOp":
            op = type(node.op).__name__
            if op in ("Add", "Sub", "Mult", "Div", "FloorDiv", "Mod", "Pow"):
                add("arithmetic", node)
            elif op in ("LShift", "RShift") or (op in ("BitAnd", "BitOr", "BitXor") and any(
                    isinstance(x, ast.Constant) and isinstance(x.value, int) and not isinstance(x.value, bool)
                    for x in (node.left, node.right))):
                add("bitwise", node)          # `a | b` on sets is not bit work: only count it next to an int literal
        elif t == "UnaryOp" and isinstance(node.op, ast.Invert):
            add("bitwise", node)
        elif t == "UnaryOp" and isinstance(node.op, ast.Not):
            add("boolean-logic", node)
        elif t == "BoolOp":
            add("boolean-logic", node)
        elif t == "Constant" and isinstance(node.value, str) and node.value:
            add("strings", node)
        elif t == "JoinedStr":
            add("f-strings", node)
        elif t == "Call":
            name = _names(node.func)
            if name in ("print", "input"):
                add("print-input", node)
            elif name == "range":
                add("range", node)
            elif name in ("enumerate", "zip"):
                add("enumerate-zip", node)
            elif name in ("sorted", "map", "filter", "sum", "min", "max", "any", "all", "reversed"):
                add("builtin-helpers", node)
            elif name == "open":
                add("file-io", node)
            elif name == "super":
                add("inheritance", node)
            if fn and (name == fn or name == "self." + fn or name == "cls." + fn):
                add("recursion", node)
        elif t == "If":
            add("conditionals", node)
            if is_main_guard(node):
                add("main-guard", node)
        elif t == "IfExp":
            add("ternary", node)
        elif t == "Compare":
            ops = [type(o).__name__ for o in node.ops]
            if "Is" in ops or "IsNot" in ops:
                add("is-vs-eq", node)
            if len(ops) > 1:
                add("chained-comparison", node)
        elif t in ("For", "AsyncFor"):
            add("for-loops", node)
            if node.orelse:
                add("break-continue", node)
            if t == "AsyncFor":
                add("async-await", node)
        elif t == "While":
            add("while-loops", node)
            if node.orelse:
                add("break-continue", node)
        elif t in ("Break", "Continue"):
            add("break-continue", node)
        elif t == "List":
            add("lists", node)
        elif t == "Tuple":
            add("tuples", node)
        elif t == "Dict":
            add("dicts", node)
        elif t == "Set":
            add("sets", node)
        elif t in ("ListComp", "DictComp", "SetComp"):
            add("comprehensions", node)
        elif t == "GeneratorExp":
            add("generator-expressions", node)
        elif t == "Subscript":
            st = type(node.slice).__name__
            add("slicing" if st in ("Slice", "ExtSlice") else "indexing", node)
        elif t == "Starred":
            add("unpacking", node)
        elif t == "NamedExpr":
            add("walrus", node)
        elif t == "Lambda":
            add("lambda", node)
        elif t in ("Yield", "YieldFrom"):
            add("generators", node)
        elif t == "Await":
            add("async-await", node)
        elif t in ("With", "AsyncWith"):
            add("with-statements", node)
            if t == "AsyncWith":
                add("async-await", node)
        elif t in ("Try", "TryStar"):
            add("exceptions", node)
        elif t == "Raise":
            add("raise", node)
        elif t == "Assert":
            add("assert", node)
        elif t in ("Global", "Nonlocal"):
            add("scope", node)
        elif t == "Delete":
            add("del", node)
        elif t == "Match":
            add("pattern-matching", node)
        elif t in ("Import", "ImportFrom"):
            add("imports", node)
            mods = [a.name for a in node.names] if t == "Import" else [node.module or ""]
            for m in mods:
                cid = MODULE_CONCEPT.get(m.split(".")[0])
                if cid:
                    add(cid, node)
        elif t == "Attribute" and _names(node) == "sys.argv":
            add("cli-args", node)
        elif t in ("FunctionDef", "AsyncFunctionDef"):
            add("functions", node)
            decs = _decor_names(node)
            if decs:
                add("decorators", node)
            for d in decs:
                last = d.split(".")[-1]
                if last in ("property", "setter", "getter", "deleter", "cached_property"):
                    add("property", node)
                if last in ("staticmethod", "classmethod"):
                    add("static-class-methods", node)
                if last in ("lru_cache", "cache", "cached_property"):
                    add("memoization", node)
                if last == "abstractmethod":
                    add("abc", node)
                if last == "wraps":
                    add("decorators", node)
            a = node.args
            if a.defaults or any(x is not None for x in a.kw_defaults) or a.kwonlyargs or getattr(a, "posonlyargs", []):
                add("default-args", node)
            if a.vararg or a.kwarg:
                add("args-kwargs", node)
            allargs = list(a.args) + list(a.kwonlyargs) + list(getattr(a, "posonlyargs", []))
            if node.returns or any(x.annotation for x in allargs):
                add("type-hints", node)
            if t == "AsyncFunctionDef":
                add("async-await", node)
            n = node.name
            if n in ("__enter__", "__exit__", "__aenter__", "__aexit__"):
                add("context-manager-class", node)
            elif n in ("__iter__", "__next__", "__aiter__", "__anext__"):
                add("iterators", node)
            elif n in ("__get__", "__set__", "__delete__", "__set_name__"):
                add("descriptors", node)
            elif n in OPERATOR_DUNDERS:
                add("operator-overloading", node)
            elif n.startswith("__") and n.endswith("__") and n not in ("__init__", "__new__"):
                add("dunder-methods", node)
            if depth > 0:
                add("closures", node)
            if node.body and is_docstring_stmt(node.body[0]):
                add("docstrings", node)
        elif t == "ClassDef":
            add("classes", node)
            bases = [_names(b) for b in node.bases]
            for b in bases:
                last = b.split(".")[-1]
                if last == "ABC":
                    add("abc", node)
                elif last in ("Protocol", "Generic"):
                    add("generics-protocols", node)
                elif last.endswith(("Error", "Exception")) or last in ("Warning",):
                    add("custom-exceptions", node)
                elif last not in ("object", ""):
                    add("inheritance", node)
                elif last == "":
                    add("inheritance", node)
            for k in node.keywords:
                if k.arg == "metaclass":
                    add("abc" if _names(k.value).endswith("ABCMeta") else "metaclasses", node)
            for d in _decor_names(node):
                if d.split(".")[-1] == "dataclass":
                    add("dataclasses", node)
            if node.body and is_docstring_stmt(node.body[0]):
                add("docstrings", node)
        elif t == "Module" and node.body and is_docstring_stmt(node.body[0]):
            add("docstrings", node.body[0])
        if t in ("For", "AsyncFor", "While") and in_loop:
            add("big-o", node)
        for child in ast.iter_child_nodes(node):
            if skip_defs and isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            nfn, ndepth = fn, depth
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                nfn = child.name
                ndepth = depth + 1 if t in ("FunctionDef", "AsyncFunctionDef") else depth
            nloop = in_loop or t in ("For", "AsyncFor", "While")
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                nloop = False
            visit(child, nfn, ndepth, nloop)

    visit(root, fn_name, 0, False)
    if fn_name and "recursion" in out and "big-o" not in out:
        out["big-o"] = out["recursion"][:1]
    return {k: sorted(set(v)) for k, v in out.items()}


def max_loop_depth(node, d=0) -> int:
    best = d
    for child in ast.iter_child_nodes(node):
        inc = 1 if isinstance(child, (ast.For, ast.AsyncFor, ast.While, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)) else 0
        if isinstance(child, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            inc = max(1, len(child.generators))
        best = max(best, max_loop_depth(child, d + inc))
    return best


def cyclomatic(node) -> int:
    n = 1
    for x in ast.walk(node):
        if isinstance(x, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler, ast.IfExp, ast.Assert)):
            n += 1
        elif isinstance(x, ast.BoolOp):
            n += len(x.values) - 1
        elif isinstance(x, ast.comprehension):
            n += 1 + len(x.ifs)
        elif type(x).__name__ == "match_case":
            n += 1
    return n


# ------------------------------------------------------------------ gotchas (things interviewers like to ask about)
def find_gotchas(tree) -> list:
    out = []

    def add(gid, title, node, text, advice):
        out.append({"id": gid, "title": title, "line": getattr(node, "lineno", 0), "text": text, "advice": advice})

    with_calls = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.With, ast.AsyncWith)):
            for it in node.items:
                with_calls.add(id(it.context_expr))
    parents = {}
    for node in ast.walk(tree):
        for ch in ast.iter_child_nodes(node):
            parents[id(ch)] = node

    def in_loop(node):
        p = parents.get(id(node))
        while p is not None:
            if isinstance(p, (ast.For, ast.AsyncFor, ast.While)):
                return True
            if isinstance(p, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                return False
            p = parents.get(id(p))
        return False

    for node in ast.walk(tree):
        t = type(node).__name__
        if t in ("FunctionDef", "AsyncFunctionDef"):
            a = node.args
            for d in list(a.defaults) + [x for x in a.kw_defaults if x is not None]:
                if isinstance(d, (ast.List, ast.Dict, ast.Set, ast.ListComp, ast.DictComp, ast.SetComp)) or (
                        isinstance(d, ast.Call) and _names(d.func) in ("list", "dict", "set")):
                    add("mutable-default", "Mutable default argument", node,
                        f"`{node.name}` uses a mutable object as a default value.",
                        "Defaults are created once; use `None` and create the object inside the function.")
            for arg in list(a.args) + list(a.kwonlyargs):
                if arg.arg in SHADOW:
                    add("shadow-builtin", "Name hides a built-in", node, f"Parameter `{arg.arg}` hides the built-in `{arg.arg}`.",
                        "Pick another name so the built-in stays usable.")
        elif t == "ExceptHandler":
            if node.type is None:
                add("bare-except", "Bare except", node, "`except:` catches everything, even Ctrl+C and `sys.exit()`.",
                    "Catch a specific exception type, or at least `Exception`.")
            if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                add("swallowed", "Exception ignored", node, "The error is caught and silently ignored.",
                    "Log it, handle it, or re-raise; silent failure hides bugs.")
        elif t == "Compare":
            for op, comp in zip(node.ops, node.comparators):
                if isinstance(op, (ast.Eq, ast.NotEq)) and isinstance(comp, ast.Constant) and comp.value is None:
                    add("eq-none", "Comparing to None with ==", node, "Uses `== None` / `!= None`.", "Use `is None` / `is not None`.")
                if isinstance(op, (ast.Is, ast.IsNot)) and isinstance(comp, ast.Constant) and comp.value not in (None, True, False) and not isinstance(comp.value, type(Ellipsis)):
                    add("is-literal", "`is` used with a literal", node, "`is` compares identity, not value, for numbers and strings.",
                        "Use `==` for values; keep `is` for None, True and False.")
        elif t == "Call":
            name = _names(node.func)
            if name in ("eval", "exec"):
                add("eval", f"Use of {name}()", node, f"`{name}` runs text as code.", "Dangerous with untrusted input; prefer `ast.literal_eval` or real parsing.")
            if name == "open" and id(node) not in with_calls:
                add("open-no-with", "File opened without `with`", node, "`open()` is used outside a `with` block.",
                    "Use `with open(...) as f:` so the file is closed even on errors.")
            if name.startswith("subprocess.") and any(k.arg == "shell" and isinstance(k.value, ast.Constant) and k.value.value is True for k in node.keywords):
                add("shell-true", "subprocess with shell=True", node, "The command goes through the shell.", "Pass a list of arguments and avoid `shell=True`, especially with user input (command injection).")
            if name in ("pickle.load", "pickle.loads", "yaml.load"):
                add("unsafe-load", f"{name} on possibly untrusted data", node, "Loading this format can run code.", "Only load data you trust; use `json` or `yaml.safe_load`.")
            if isinstance(node.func, ast.Attribute) and node.func.attr in ("append", "remove", "insert", "pop", "extend"):
                p = parents.get(id(node))
                while p is not None and not isinstance(p, (ast.For, ast.FunctionDef, ast.AsyncFunctionDef)):
                    p = parents.get(id(p))
                if isinstance(p, ast.For) and isinstance(p.iter, ast.Name) and isinstance(node.func.value, ast.Name) \
                        and node.func.value.id == p.iter.id and node.func.attr != "append":
                    add("mutate-while-iterating", "List changed while looping over it", node,
                        f"`{p.iter.id}.{node.func.attr}()` is called inside `for ... in {p.iter.id}`.",
                        "Loop over a copy (`list(x)`) or build a new list.")
        elif t == "ImportFrom" and any(a.name == "*" for a in node.names):
            add("import-star", "Wildcard import", node, f"`from {node.module} import *` hides where names come from.", "Import only what you need.")
        elif t == "Assign":
            for tg in node.targets:
                if isinstance(tg, ast.Name):
                    if tg.id in SHADOW:
                        add("shadow-builtin", "Name hides a built-in", node, f"`{tg.id}` hides the built-in `{tg.id}`.", "Pick another name.")
                    if SECRET_RE.search(tg.id) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str) and node.value.value:
                        add("hard-coded-secret", "Possible hard-coded secret", node, f"`{tg.id}` is set to a string literal (the value is hidden in these notes).",
                            "Read secrets from environment variables or a secret store, never from source code.")
        elif t == "AugAssign" and isinstance(node.op, ast.Add) and isinstance(node.target, ast.Name):
            if isinstance(node.value, (ast.JoinedStr,)) or (isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)):
                if in_loop(node):
                    add("string-concat-loop", "String built with += in a loop", node, "Repeated `+=` on a string copies it each time.", "Collect parts in a list and `''.join(parts)`.")
        elif t == "Global":
            add("global", "Global state", node, f"`global {', '.join(node.names)}` changes module-level state from a function.", "Prefer passing values in and returning results.")
        elif t == "Dict":
            for k, v in zip(node.keys, node.values):
                if isinstance(k, ast.Constant) and isinstance(k.value, str) and SECRET_RE.search(k.value) \
                        and isinstance(v, ast.Constant) and isinstance(v.value, str) and v.value:
                    add("hard-coded-secret", "Possible hard-coded secret", node, f"Key `{k.value}` holds a string literal (hidden in these notes).",
                        "Read secrets from the environment or a secret store.")
    seen, uniq = set(), []
    for g in sorted(out, key=lambda x: (x["line"], x["id"])):
        key = (g["id"], g["line"])
        if key not in seen:
            seen.add(key)
            uniq.append(g)
    return uniq


def mask_secret_lines(lines: list, gotchas: list) -> list:
    out = list(lines)
    for g in gotchas:
        if g["id"] == "hard-coded-secret" and 1 <= g["line"] <= len(out):
            out[g["line"] - 1] = re.sub(r"""((?:=|:)\s*)(['"]).*?\2""", r"\1\2…hidden…\2", out[g["line"] - 1])
    return out


# ------------------------------------------------------------------ blocks
GROUP_IMPORT, GROUP_ASSIGN = "imports", "assignments"


def start_line(node) -> int:
    ls = [node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])]
    return min(ls)


def signature(node) -> str:
    a = node.args
    parts = [x.arg for x in getattr(a, "posonlyargs", [])] + [x.arg for x in a.args]
    if a.vararg:
        parts.append("*" + a.vararg.arg)
    parts += [x.arg for x in a.kwonlyargs]
    if a.kwarg:
        parts.append("**" + a.kwarg.arg)
    return "(" + ", ".join(parts) + ")"


def make_blocks(body, lines, parent=""):
    blocks, group = [], []

    def flush():
        nonlocal group
        if not group:
            return
        kind = GROUP_IMPORT if isinstance(group[0], (ast.Import, ast.ImportFrom)) else GROUP_ASSIGN
        blocks.append(_block(kind, "", group, group[0].lineno, group[-1].end_lineno, parent))
        group = []

    for node in body:
        if is_docstring_stmt(node):
            flush()
            blocks.append(_block("docstring", "", [node], node.lineno, node.end_lineno, parent))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            if group and not isinstance(group[0], (ast.Import, ast.ImportFrom)):
                flush()
            group.append(node)
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            if group and isinstance(group[0], (ast.Import, ast.ImportFrom)):
                flush()
            group.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            flush()
            kind = "method" if parent else "function"
            b = _block(kind, node.name, [node], start_line(node), node.end_lineno, parent, node)
            b["signature"] = signature(node)
            b["is_async"] = isinstance(node, ast.AsyncFunctionDef)
            blocks.append(b)
        elif isinstance(node, ast.ClassDef):
            flush()
            members = [x for x in node.body if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
            end = (min(start_line(m) for m in members) - 1) if members else node.end_lineno
            b = _block("class", node.name, [node], start_line(node), max(end, node.lineno), parent, node, skip_defs=True)
            b["bases"] = [_names(x) for x in node.bases]
            blocks.append(b)
            blocks.extend(make_blocks(node.body, lines, parent=(parent + "." if parent else "") + node.name)[0:])
        elif is_main_guard(node):
            flush()
            blocks.append(_block("main-guard", "", [node], start_line(node), node.end_lineno, parent, node))
        else:
            flush()
            kinds = {"For": "loop", "AsyncFor": "loop", "While": "loop", "If": "conditional", "With": "with block",
                     "AsyncWith": "with block", "Try": "try block", "Expr": "statement", "Return": "statement"}
            blocks.append(_block(kinds.get(type(node).__name__, "statement"), "", [node], start_line(node), node.end_lineno, parent, node))
    flush()
    return blocks


def _block(kind, name, nodes, start, end, parent, owner=None, skip_defs=False):
    concepts: dict = {}
    for n in nodes:
        fn = name if kind in ("function", "method") else ""
        for k, v in detect(n, skip_defs=skip_defs, fn_name=fn).items():
            concepts.setdefault(k, []).extend(v)
    # class blocks: skip the body statements that belong to methods (done by skip_defs); module groups keep all
    concepts = {k: sorted(set(v)) for k, v in concepts.items()}
    b = {"kind": kind, "name": name, "parent": parent, "start": start, "end": end,
         "concepts": concepts, "level": max([CONCEPTS[c]["level"] for c in concepts if c in CONCEPTS] or [1])}
    if owner is not None and kind in ("function", "method"):
        b["complexity"] = cyclomatic(owner)
        b["loop_depth"] = max_loop_depth(owner)
        b["calls"] = sorted({_names(x.func) for x in ast.walk(owner) if isinstance(x, ast.Call) and _names(x.func)})[:12]
    if kind == GROUP_IMPORT:
        mods = []
        for n in nodes:
            if isinstance(n, ast.Import):
                mods += [a.name for a in n.names]
            else:
                mods.append(("." * n.level) + (n.module or ""))
        b["modules"] = mods
    return b


def assign_ids(blocks):
    seen = {}
    for b in blocks:
        base = (b["kind"] + ":" + ((b["parent"] + ".") if b["parent"] else "") + b["name"]) if b["name"] else f"{b['kind']}@{b['start']}"
        n = seen.get(base, 0)
        seen[base] = n + 1
        b["id"] = base if n == 0 else f"{base}#{n + 1}"


def auto_text(b) -> str:
    if b["kind"] == GROUP_IMPORT:
        bits = []
        for m in b["modules"]:
            top = m.split(".")[0]
            if m.startswith("."):
                bits.append(f"`{m}` (a module from this project)")
            elif top in STD_DOC:
                bits.append(f"`{m}` ({STD_DOC[top]})")
            elif top in STDLIB:
                bits.append(f"`{m}` (standard library)")
            else:
                bits.append(f"`{m}` (third-party or project module)")
        return "Imports other modules so their code can be used here: " + "; ".join(bits[:12]) + "."
    if b["kind"] == "docstring":
        return "A docstring: text that documents what the surrounding module, class or function is for. It is stored in `__doc__`."
    return ""


# ------------------------------------------------------------------ analysis
def read_py(path):
    with open(path, "rb") as fh:
        raw = fh.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise SystemExit(f"error: {path} is larger than {MAX_BYTES} bytes")
    enc = tokenize.detect_encoding(io.BytesIO(raw).readline)[0]
    return raw.decode(enc, "replace").replace("\r\n", "\n").replace("\r", "\n")


def level_name(concepts: dict) -> str:
    c = {1: 0, 2: 0, 3: 0}
    for cid in concepts:
        if cid in CONCEPTS:
            c[CONCEPTS[cid]["level"]] += 1
    if c[3] >= 3:
        return "Advanced"
    if c[3] >= 1 or c[2] >= 5:
        return "Intermediate"
    return "Beginner"


def block_hash(lines: list, b: dict) -> str:
    text = "\n".join(x.rstrip() for x in lines[b["start"] - 1:b["end"]] if x.strip())
    return hashlib.sha1(text.encode("utf-8", "replace")).hexdigest()[:12]


def _loose(model: dict, lines: list) -> None:
    """Line-pattern analysis for files that do not parse (Python 2, syntax errors)."""
    outline = loose_outline(lines)
    if not outline:
        return
    blocks = []
    for kind, name, parent, s, e in outline:
        c = {k: v for k, v in loose_concepts(lines, s, e).items() if k in CONCEPTS}
        m = re.search(r"def\s+\w+\s*(\([^)]*\))", lines[s - 1])
        blocks.append({"kind": kind, "name": name, "parent": parent, "start": s, "end": e, "concepts": c,
                       "level": max([CONCEPTS[x]["level"] for x in c] or [1]), "signature": m.group(1) if m else ""})
    assign_ids(blocks)
    for b in blocks:
        b["hash"] = block_hash(lines, b)
    total = {k: v for k, v in loose_concepts(lines).items() if k in CONCEPTS}
    model.update(fallback=True, blocks=blocks, concepts=total, level=level_name(total), gotchas=loose_gotchas(lines),
                 py2=loose_py2(lines))
    model["source_lines"] = mask_secret_lines(lines, model["gotchas"])
    model["functions"] = sum(1 for b in blocks if b["kind"] in ("function", "method"))
    model["classes"] = sum(1 for b in blocks if b["kind"] == "class")


def full_name(b: dict) -> str:
    return (b["parent"] + "." if b["parent"] else "") + b["name"]


def apply_selection(model: dict, only: list) -> None:
    """Keep only the selected functions/classes (and what they call in this file)."""
    names = {x.strip() for x in only if x.strip()}
    graph = (model.get("functionality") or {}).get("call_graph", {})
    sel = [b for b in model["blocks"] if b["kind"] in ("function", "method", "class")
           and (b["name"] in names or full_name(b) in names or b["parent"].split(".")[0] in names)]
    if not sel:
        raise SystemExit(f"error: none of {sorted(names)} found in {model['file']} "
                         "(use a function name, Class.method or a class name)")
    keep = {full_name(b) for b in sel}
    stack = list(keep)
    while stack:
        for callee in graph.get(stack.pop(), []):
            if callee not in keep:
                keep.add(callee)
                stack.append(callee)
    owners = {k.split(".")[0] for k in keep if "." in k}
    kept = [b for b in model["blocks"] if b["kind"] in ("imports", "docstring") or full_name(b) in keep
            or (b["kind"] == "class" and b["name"] in owners and not b["parent"])]
    model["omitted"] = len(model["blocks"]) - len(kept)
    model["selected"] = sorted(names)
    model["blocks"] = kept
    total: dict = {}
    for b in kept:
        for cid, ln in b["concepts"].items():
            total.setdefault(cid, []).extend(ln)
    model["concepts"] = {k: sorted(set(v)) for k, v in total.items()}
    model["level"] = level_name(model["concepts"])
    spans = [(b["start"], b["end"]) for b in kept]
    inside = lambda n: any(s <= n <= e for s, e in spans)  # noqa: E731
    model["gotchas"] = [g for g in model["gotchas"] if inside(g["line"])]
    f = model.get("functionality")
    if f:
        f["api"] = [x for x in f["api"] if x["name"] in keep or x["name"] in owners]
        f["effects"] = {k: [n for n in v if inside(n)] for k, v in f["effects"].items()}
        f["effects"] = {k: v for k, v in f["effects"].items() if v}
        f["doctests"] = [d for d in f["doctests"] if d["in"] in keep or d["in"] in owners or d["in"] in names]
        f["files"] = [x for x in f["files"] if inside(x["line"])]
        f["cli"]["arguments"] = [x for x in f["cli"]["arguments"] if inside(x["line"])]
    model["functions"] = sum(1 for b in kept if b["kind"] in ("function", "method"))
    model["classes"] = sum(1 for b in kept if b["kind"] == "class")


def analyze_source(rel: str, source: str, only=None) -> dict:
    lines = source.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    model = {"file": rel, "line_count": len(lines), "source_lines": lines, "error": None, "blocks": [], "concepts": {},
             "gotchas": [], "level": "Beginner", "comments": 0, "functions": 0, "classes": 0, "fallback": False}
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.COMMENT:
                model["comments"] += 1
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass
    try:
        tree = ast.parse(source, filename=rel)
    except SyntaxError as e:
        hint = ""
        if re.search(r"^\s*print\s+[^(\s=]", source, re.M):
            hint = "This looks like Python 2 code (print statement)."
        elif "match" in source and sys.version_info < (3, 10):
            hint = "The file may use features newer than this Python version."
        model["error"] = {"message": e.msg, "line": e.lineno or 0, "hint": hint}
        _loose(model, lines)
        return model
    except (ValueError, RecursionError) as e:
        model["error"] = {"message": str(e), "line": 0, "hint": ""}
        _loose(model, lines)
        return model
    model["gotchas"] = find_gotchas(tree)
    model["source_lines"] = mask_secret_lines(lines, model["gotchas"])
    blocks = make_blocks(tree.body, lines)
    assign_ids(blocks)
    for b in blocks:
        b["hash"] = block_hash(lines, b)
    total = detect(tree)
    if model["comments"]:
        total["docstrings"] = sorted(set(total.get("docstrings", []) + [0]))
    model.update(blocks=blocks, concepts=total, level=level_name(total))
    model["functions"] = sum(1 for b in blocks if b["kind"] in ("function", "method"))
    model["classes"] = sum(1 for b in blocks if b["kind"] == "class")
    model["functionality"] = functionality(tree, source, STDLIB)
    if only:
        apply_selection(model, only)
    return model


def new_notes(model: dict) -> dict:
    blocks = {}
    for b in model["blocks"]:
        auto = auto_text(b)
        blocks[b["id"]] = {"explanation": auto or f"{TODO}: explain this block in plain words for a beginner", "deeper": "",
                           "lines": {}, "hash": b.get("hash", "")}
    return {"summary": f"{TODO}: what this file does, in two or three sentences",
            "functionality": f"{TODO}: what the file does when it runs or is imported: inputs, processing, outputs, side effects",
            "how_to_run": "", "example_run": {"command": "", "output": "", "note": ""}, "blocks": blocks,
            "interview_questions": [], "exercises": [], "notes": []}


def _is_default(entry: dict) -> bool:
    e = entry.get("explanation", "")
    return not e.strip() or TODO in e


def load_notes(path: str, model: dict) -> dict:
    notes = new_notes(model)
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as fh:
                have = json.load(fh)
        except ValueError as e:
            raise SystemExit(f"error: {path} is not valid JSON: {e}")
        for k in ("summary", "functionality", "how_to_run", "example_run", "interview_questions", "exercises", "notes"):
            if k in have:
                notes[k] = have[k]
        old = have.get("blocks") or {}
        by_hash = {b.get("hash"): b["id"] for b in model["blocks"] if b.get("hash")}
        for bid, v in old.items():
            if not isinstance(v, dict):
                continue
            if bid in notes["blocks"]:
                keep_hash = notes["blocks"][bid]["hash"]
                notes["blocks"][bid].update(v)
                notes["blocks"][bid]["hash"] = keep_hash
            else:                       # the block moved or was renamed: find it again by its code
                tid = by_hash.get(v.get("hash"))
                if tid and tid not in old and _is_default(notes["blocks"][tid]):
                    keep_hash = notes["blocks"][tid]["hash"]
                    notes["blocks"][tid].update(v)
                    notes["blocks"][tid]["hash"] = keep_hash
    return notes


def missing(model: dict, notes: dict) -> list:
    out = []
    if model.get("error") and not model.get("fallback"):
        return out
    if TODO in notes["summary"] or not notes["summary"].strip():
        out.append("summary")
    if model.get("functionality") and (TODO in notes.get("functionality", "") or not notes.get("functionality", "").strip()):
        out.append("functionality")
    for b in model["blocks"]:
        e = notes["blocks"].get(b["id"], {}).get("explanation", "")
        if not e.strip() or TODO in e:
            out.append("block " + b["id"])
    return out


TICKED = re.compile(r"`([A-Za-z_][\w]*(?:\.[\w]+)*)(?:\(\))?`")


def warnings(model: dict, notes: dict) -> list:
    """Cheap sanity checks on the written explanations (they never block, unless --strict)."""
    out = []
    src = "\n".join(model.get("source_lines", []))
    known = set(re.findall(r"[A-Za-z_]\w*", src)) | BUILTIN_NAMES | set(STDLIB) | {"self", "cls", "True", "False", "None"} | \
        set(__import__("keyword").kwlist)
    seen = {}
    texts = [("summary", notes.get("summary", "")), ("functionality", notes.get("functionality", ""))]
    for b in model["blocks"]:
        nb = notes["blocks"].get(b["id"], {})
        texts.append((b["id"], nb.get("explanation", "") + "\n" + nb.get("deeper", "")))
        e = nb.get("explanation", "").strip()
        if e and TODO not in e and not auto_text(b):
            if len(e) < 25:
                out.append(f"{b['id']}: explanation is very short ({len(e)} characters)")
            if e in seen:
                out.append(f"{b['id']}: same explanation as {seen[e]}")
            seen.setdefault(e, b["id"])
        for k in (nb.get("lines") or {}):
            try:
                if not b["start"] <= int(k) <= b["end"]:
                    out.append(f"{b['id']}: line note {k} is outside the block (lines {b['start']}-{b['end']})")
            except ValueError:
                out.append(f"{b['id']}: line note key {k!r} is not a line number")
    for where, text in texts:
        for m in TICKED.finditer(text):
            first = m.group(1).split(".")[0]
            if first not in known and len(first) > 1:
                out.append(f"{where}: mentions `{m.group(1)}`, which does not appear in the file (check for a mistake)")
    return sorted(set(out))


# ------------------------------------------------------------------ HTML
def esc(s) -> str:
    return html.escape(str(s), quote=True)


def md_inline(s: str) -> str:
    """Escape, then turn `code` and **bold** into HTML."""
    s = esc(s)
    s = re.sub(r"`([^`\n]+)`", r"<code>\1</code>", s)
    return re.sub(r"\*\*([^*\n]+)\*\*", r"<b>\1</b>", s)


def paragraphs(s: str) -> str:
    parts = [p.strip() for p in re.split(r"\n\s*\n", s or "") if p.strip()]
    return "".join(f"<p>{md_inline(p)}</p>" for p in parts)


CSS = """
:root{--bg:#fff;--fg:#1d2430;--mut:#5d6b7c;--line:#dbe1e8;--card:#f5f7fa;--code:#f0f3f7;--b1:#1a7f4b;--b2:#b36a00;--b3:#b3261e;--acc:#2456c9}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#0e131a;--fg:#e4e9f0;--mut:#98a5b5;--line:#2a3441;--card:#161d27;--code:#1b2431;--b1:#4cc38a;--b2:#f0a73c;--b3:#ff7b72;--acc:#7aa2ff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 system-ui,Segoe UI,sans-serif}
main{max-width:1000px;margin:0 auto;padding:24px 16px 80px}h1{margin:.2em 0;font-size:1.8rem}h2{margin:2em 0 .5em;border-bottom:2px solid var(--line);padding-bottom:.2em}h3{margin:1.4em 0 .3em}
a{color:var(--acc)}.mut{color:var(--mut)}code{background:var(--code);padding:1px 5px;border-radius:4px;font-size:.9em}
.badge{display:inline-block;font-size:.75rem;font-weight:600;border-radius:99px;padding:1px 9px;border:1px solid currentColor;white-space:nowrap}.l1{color:var(--b1)}.l2{color:var(--b2)}.l3{color:var(--b3)}
.bar{position:sticky;top:0;background:var(--bg);padding:8px 0;border-bottom:1px solid var(--line);z-index:5;display:none;gap:8px;flex-wrap:wrap;align-items:center}.js .bar{display:flex}
.bar button{font:inherit;border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:8px;padding:4px 12px;cursor:pointer}.bar button[aria-pressed=true]{border-color:var(--acc);color:var(--acc);font-weight:600}
nav a{margin-right:12px;white-space:nowrap}.stats{display:flex;gap:10px;flex-wrap:wrap;margin:12px 0}.stat{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:6px 14px}.stat b{display:block;font-size:1.2rem}
.block{border:1px solid var(--line);border-radius:10px;margin:18px 0;overflow:hidden}.block>header{background:var(--card);padding:8px 12px;display:flex;gap:10px;flex-wrap:wrap;align-items:center}.block>header h3{margin:0;font-size:1rem}
.block .body{padding:0 12px 10px}pre.code{margin:0;overflow:auto;background:var(--code);font:13.5px/1.5 ui-monospace,Consolas,monospace}
table.src{border-collapse:collapse;width:100%}table.src td{padding:0 10px;vertical-align:top}td.n{color:var(--mut);text-align:right;user-select:none;width:1%;border-right:1px solid var(--line)}td.t{white-space:pre}
tr.ann td{background:color-mix(in srgb,var(--acc) 10%,transparent);font:14px/1.45 system-ui,sans-serif;white-space:normal;padding:4px 10px;border-left:3px solid var(--acc)}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0}.chip{font-size:.78rem;border:1px solid var(--line);border-radius:6px;padding:0 7px;background:var(--bg)}
.card{border:1px solid var(--line);border-radius:10px;padding:10px 14px;margin:12px 0;background:var(--bg)}.card h3{margin:.1em 0}.card .k{font-weight:600;color:var(--mut)}
.warn{border-left:4px solid var(--b2);background:var(--card);padding:8px 12px;border-radius:6px;margin:8px 0}.err{border-left:4px solid var(--b3);background:var(--card);padding:10px 14px;border-radius:6px}
details{margin:6px 0}summary{cursor:pointer;font-weight:600}.deeper{border-left:3px solid var(--b3);padding-left:10px;margin:8px 0}
.hide{display:none!important}ul.check li{list-style:'☐  '}table.idx{border-collapse:collapse;width:100%}table.idx td,table.idx th{border:1px solid var(--line);padding:6px 10px;text-align:left}
@media print{.bar{display:none!important}details{display:block}details>*{display:block}.block{break-inside:avoid}}
"""

JS = """
(function(){var d=document;d.documentElement.classList.add('js');var btns=d.querySelectorAll('.bar button');
function set(n){d.querySelectorAll('[data-level]').forEach(function(e){e.classList.toggle('hide',parseInt(e.getAttribute('data-level'),10)>n)});
btns.forEach(function(b){b.setAttribute('aria-pressed',b.getAttribute('data-n')==String(n))})}
btns.forEach(function(b){b.addEventListener('click',function(){set(parseInt(b.getAttribute('data-n'),10))})});set(3)})();
"""


def badge(level: int) -> str:
    return f'<span class="badge l{level}">{LEVELS[level]}</span>'


def render_code(model: dict, b: dict, ann: dict) -> str:
    rows = []
    for n in range(b["start"], min(b["end"], len(model["source_lines"])) + 1):
        text = model["source_lines"][n - 1] if n - 1 < len(model["source_lines"]) else ""
        rows.append(f'<tr><td class="n">{n}</td><td class="t">{esc(text)}</td></tr>')
        note = ann.get(str(n))
        if note:
            rows.append(f'<tr class="ann"><td class="n"></td><td>↳ {md_inline(note)}</td></tr>')
    return '<pre class="code"><table class="src">' + "".join(rows) + "</table></pre>"


def complexity_note(b: dict) -> str:
    bits = []
    if "complexity" in b:
        c = b["complexity"]
        bits.append(f"cyclomatic complexity {c} ({'simple' if c <= 5 else 'moderate' if c <= 10 else 'complex: consider splitting'})")
        d = b.get("loop_depth", 0)
        if d >= 2:
            bits.append(f"loops nested {d} deep, so time is likely O(n^{d}) in the input size")
        elif d == 1:
            bits.append("one loop level, so time is likely O(n)")
        if "recursion" in b["concepts"]:
            bits.append("recursive: check the base case and the recursion depth")
    return "; ".join(bits)


def render_banners(model: dict) -> str:
    out = []
    if model.get("selected"):
        out.append('<div class="warn"><b>Selected parts only:</b> ' + ", ".join(f"<code>{esc(x)}</code>" for x in model["selected"])
                   + f" and the functions in this file that they call. {model.get('omitted', 0)} other block(s) are left out.</div>")
    if model.get("fallback"):
        e = model["error"]
        out.append(f'<div class="err"><b>Loose mode.</b> This file could not be parsed as Python 3 (line {e["line"]}: {esc(e["message"])}). '
                   + (esc(e["hint"]) + " " if e["hint"] else "")
                   + "The outline, concepts and gotchas below come from line patterns, so they can be incomplete.</div>")
        if model.get("py2"):
            rows = "".join(f'<tr><td>{x["line"]}</td><td>{esc(x["what"])}</td><td>{md_inline(x["fix"])}</td></tr>' for x in model["py2"][:25])
            out.append('<h3>Python 2 idioms found</h3><table class="idx"><tr><th>Line</th><th>Found</th><th>Python 3</th></tr>' + rows + "</table>")
    return "".join(out)


def sig_text(entry: dict) -> str:
    ps = []
    for p in entry["params"]:
        s = p["name"].replace(" (keyword-only)", "")
        if p["type"]:
            s += ": " + p["type"]
        if p["default"] is not None:
            s += " = " + p["default"]
        ps.append(s)
    return f'{entry["name"]}({", ".join(ps)})' + (f' -> {entry["returns_type"]}' if entry["returns_type"] else "")


INPUT_EFFECTS = {"reads command-line arguments", "asks the user for input", "reads environment variables", "reads files",
                 "reads data files", "reads standard input"}
OUTPUT_EFFECTS = {"prints to the screen", "writes files", "writes data files", "uses the network", "writes log messages",
                  "ends the program", "creates folders or copies files", "deletes, renames or moves files"}


def render_functionality(model: dict, notes: dict) -> str:
    f = model.get("functionality")
    if not f:
        return ""
    out = ['<h2 id="functionality">Functionality: what this file does</h2>']
    out.append(paragraphs(notes.get("functionality", "")))
    docs = {x["name"]: x["doc"] for x in f["api"]}
    # when it runs
    out.append("<h3>When the file runs</h3>")
    if f["entry_calls"]:
        shown = set()

        def tree(name, depth, trail):
            d = f' <span class="mut">{esc(docs[name])}</span>' if docs.get(name) else ""
            if name in shown:                    # each function is expanded once; later mentions point back
                return f'<li><code>{esc(name)}()</code> <span class="mut">(see above)</span></li>'
            shown.add(name)
            kids = [] if depth >= 4 or name in trail else [c for c in f["call_graph"].get(name, []) if c not in trail]
            inner = "<ul>" + "".join(tree(c, depth + 1, trail + [name]) for c in kids[:8]) + "</ul>" if kids else ""
            return f"<li><code>{esc(name)}()</code>{d}{inner}</li>"
        why = "Starting at the main guard" if f["has_main_guard"] else "Importing or running the file executes top-level code that calls"
        out.append(f"<p>{why}, the program goes through:</p><ul>" + "".join(tree(c, 0, []) for c in f["entry_calls"][:6]) + "</ul>")
        if f["runs_on_import"]:
            out.append('<p class="warn">Code at the top level runs as soon as the file is imported, not only when it is run directly.</p>')
    else:
        out.append("<p>Nothing runs automatically. The file is a module of functions and classes meant to be imported and called.</p>")
    # inputs / outputs
    rows = []
    cli = f["cli"]
    if cli["arguments"] or cli["subcommands"]:
        flags = "; ".join("<code>" + esc(" ".join(a["flags"]) or "argument") + "</code>" + (f" {esc(a['help'])}" if a["help"] else "") for a in cli["arguments"][:12])
        rows.append(("Input", "command-line options" + (f" (subcommands: {', '.join(cli['subcommands'])})" if cli["subcommands"] else ""), flags, ""))
    for label, lines_ in f["effects"].items():
        kind = "Input" if label in INPUT_EFFECTS else "Output" if label in OUTPUT_EFFECTS else "Other effect"
        extra = ""
        if label == "reads environment variables" and f["env"]:
            extra = "variables: " + ", ".join(f"<code>{esc(v)}</code>" for v in f["env"])
        elif label in ("reads files", "writes files") and f["files"]:
            mode = (lambda m: any(c in m for c in "wax+"))
            extra = "files: " + ", ".join(f"<code>{esc(x['path'])}</code>" for x in f["files"] if mode(x["mode"]) == (label == "writes files"))[:300]
        elif label == "uses the network" and f["urls"]:
            extra = "URLs: " + ", ".join(f"<code>{esc(u)}</code>" for u in f["urls"][:4])
        rows.append((kind, esc(label), extra, "line" + ("s " if len(lines_) > 1 else " ") + ", ".join(map(str, lines_[:8]))))
    out.append("<h3>Inputs, outputs and side effects</h3>")
    if rows:
        out.append('<table class="idx"><tr><th></th><th>What</th><th>Details</th><th>Where</th></tr>'
                   + "".join(f"<tr><td>{a}</td><td>{b}</td><td>{c}</td><td>{d}</td></tr>" for a, b, c, d in rows) + "</table>")
    else:
        out.append("<p>No input, output or side effects were detected: the code only computes values. (Static analysis can miss effects hidden behind other libraries.)</p>")
    if f["third_party"]:
        out.append("<p><b>Needs these non-standard-library packages:</b> " + ", ".join(f"<code>{esc(x)}</code>" for x in f["third_party"]) + "</p>")
    # API
    pub = [x for x in f["api"] if x["public"]]
    if pub:
        out.append("<h3>What you can call (public API)</h3>")
        rows = []
        for x in pub:
            if x["kind"] == "class":
                sig = "class " + x["name"] + (f"({', '.join(x['bases'])})" if x.get("bases") else "")
            else:
                sig = sig_text(x)
            ret = "; ".join(x["returns"]) if x["kind"] != "class" else ""
            rows.append(f"<tr><td><code>{esc(sig)}</code><br><span class=mut>line {x['line']}</span></td><td>{esc(x['doc'])}</td>"
                        f"<td>{esc(ret)}</td><td>{esc(', '.join(x['raises']))}</td><td>{esc(', '.join(x['effects']))}</td></tr>")
        out.append('<div style="overflow-x:auto"><table class="idx"><tr><th>Signature</th><th>Docstring</th><th>Returns</th><th>Can raise</th><th>Side effects</th></tr>'
                   + "".join(rows) + "</table></div>")
    if f["doctests"]:
        out.append("<h3>Examples from the docstrings</h3><p class=mut>Written by the code's author; not run here.</p>")
        for d in f["doctests"][:10]:
            out.append(f'<pre class="code" style="padding:8px 12px">&gt;&gt;&gt; {esc(d["source"])}\n{esc(d["want"])}</pre>')
    er = notes.get("example_run") or {}
    if isinstance(er, dict) and (er.get("command") or er.get("output")):
        out.append('<h3>Example run</h3><p class="mut">Recorded by the reader with the owner\'s permission; the script itself never runs the file.</p>'
                   f'<pre class="code" style="padding:8px 12px">$ {esc(er.get("command", ""))}\n{esc(er.get("output", ""))}</pre>'
                   + (f'<p>{md_inline(er["note"])}</p>' if er.get("note") else ""))
    return "".join(out)


def render_html(model: dict, notes: dict) -> str:
    name = model["file"]
    if model.get("error") and not model.get("fallback"):
        e = model["error"]
        src = "".join(f'<tr><td class="n">{i}</td><td class="t">{esc(t)}</td></tr>' for i, t in enumerate(model["source_lines"][:200], 1))
        body = (f'<div class="err"><b>Could not parse {esc(name)}</b><br>Line {e["line"]}: {esc(e["message"])}'
                + (f"<br>{esc(e['hint'])}" if e["hint"] else "") + '</div><h2>Source</h2><pre class="code"><table class="src">' + src + "</table></pre>")
        return _page(name, body, "", model)
    counts = {1: 0, 2: 0, 3: 0}
    for cid in model["concepts"]:
        if cid in CONCEPTS:
            counts[CONCEPTS[cid]["level"]] += 1
    found = [c for c in ORDER if c in model["concepts"]]
    out = []
    out.append(f'<h1>Notes: <code>{esc(name)}</code> {badge({"Beginner": 1, "Intermediate": 2, "Advanced": 3}[model["level"]])}</h1>')
    out.append('<div class="bar" role="group" aria-label="Choose your level"><b>Show up to:</b>'
               '<button data-n="1">Beginner</button><button data-n="2">Intermediate</button><button data-n="3" aria-pressed="true">Advanced</button></div>')
    out.append('<nav><a href="#overview">Overview</a>' + ('<a href="#functionality">Functionality</a>' if model.get("functionality") else "")
               + '<a href="#walkthrough">Walkthrough</a><a href="#concepts">Concepts</a>'
               '<a href="#gotchas">Gotchas</a><a href="#interview">Interview</a><a href="#revise">Revise</a></nav>')
    out.append(render_banners(model))
    out.append('<h2 id="overview">Overview</h2>' + paragraphs(notes["summary"]))
    if notes.get("how_to_run"):
        out.append("<p><b>How to run:</b> " + md_inline(notes["how_to_run"]) + "</p>")
    elif any(b["kind"] == "main-guard" for b in model["blocks"]):
        out.append(f"<p><b>How to run:</b> <code>python {esc(os.path.basename(name))}</code> (the file has a main guard, so it is meant to be run).</p>")
    out.append('<div class="stats">' + "".join(f'<div class="stat"><b>{v}</b>{k}</div>' for k, v in (
        ("lines", model["line_count"]), ("functions / methods", model["functions"]), ("classes", model["classes"]),
        ("comments", model["comments"]), ("concepts used", len(found)))) + "</div>")
    out.append(f'<p class="mut">Concepts by level: {badge(1)} {counts[1]} &nbsp; {badge(2)} {counts[2]} &nbsp; {badge(3)} {counts[3]}. '
               "Read the walkthrough top to bottom; use the buttons above to hide concepts beyond your level.</p>")
    out.append(render_functionality(model, notes))
    # walkthrough
    out.append('<h2 id="walkthrough">Walkthrough</h2>')
    for b in model["blocks"]:
        nb = notes["blocks"].get(b["id"], {})
        title = {"imports": "Imports", "assignments": "Module-level values", "docstring": "Docstring", "main-guard": "Entry point (main guard)"}.get(b["kind"])
        if title is None:
            title = f'{b["kind"].capitalize()} <code>{esc((b["parent"] + "." if b["parent"] else "") + b["name"])}{esc(b.get("signature", ""))}</code>' if b["name"] else b["kind"].capitalize()
        chips = "".join(f'<span class="chip lv l{CONCEPTS[c]["level"]}" data-level="{CONCEPTS[c]["level"]}" title="line {b["concepts"][c][0]}">{esc(CONCEPTS[c]["title"])}</span>'
                        for c in ORDER if c in b["concepts"] and c in CONCEPTS)
        cx = complexity_note(b)
        lines_html = f'<span class="mut">lines {b["start"]}-{b["end"]}</span>'
        out.append(f'<section class="block" id="{esc(b["id"])}"><header><h3>{title}</h3>{lines_html}{badge(b["level"])}</header>'
                   + render_code(model, b, {str(k): v for k, v in nb.get("lines", {}).items()}) + '<div class="body">'
                   + paragraphs(nb.get("explanation", ""))
                   + (f'<div class="deeper lv" data-level="3"><b>Going deeper:</b>{paragraphs(nb["deeper"])}</div>' if nb.get("deeper") else "")
                   + (f'<p class="mut">{esc(cx)}</p>' if cx else "") + f'<div class="chips">{chips}</div></div></section>')
    # concepts
    out.append('<h2 id="concepts">Concepts used in this file</h2>')
    for lv in (1, 2, 3):
        items = [c for c in found if CONCEPTS[c]["level"] == lv]
        if not items:
            continue
        out.append(f'<div class="lv" data-level="{lv}"><h3>{LEVELS[lv]} ({len(items)})</h3>')
        for cid in items:
            c = CONCEPTS[cid]
            ln = [n for n in model["concepts"][cid] if n][:8]
            out.append(f'<div class="card"><h3>{esc(c["title"])} {badge(lv)}</h3>'
                       f'<p><span class="k">What:</span> {md_inline(c["what"])}</p><p><span class="k">Why it matters:</span> {md_inline(c["why"])}</p>'
                       f'<p><span class="k">Watch out:</span> {md_inline(c["pitfall"])}</p><pre class="code" style="padding:8px 12px">{esc(c["example"])}</pre>'
                       + (f'<p class="mut">In this file: line{"s" if len(ln) > 1 else ""} {", ".join(map(str, ln))}</p>' if ln else "")
                       + f'<details><summary>Interview question</summary><p><b>{md_inline(c["q"])}</b></p><p>{md_inline(c["a"])}</p></details></div>')
        out.append("</div>")
    # gotchas
    out.append('<h2 id="gotchas">Gotchas and review notes</h2>')
    if model["gotchas"]:
        out.append("<p class=mut>Things a reviewer or interviewer would point at in this file.</p>")
        for g in model["gotchas"]:
            out.append(f'<div class="warn"><b>Line {g["line"]}: {esc(g["title"])}.</b> {md_inline(g["text"])} <i>{md_inline(g["advice"])}</i></div>')
    else:
        out.append("<p>No common pitfalls were detected automatically. That does not prove the code is free of bugs.</p>")
    for n in notes.get("notes", []):
        out.append(f'<div class="warn">{md_inline(n)}</div>')
    # interview
    out.append('<h2 id="interview">Interview questions</h2><p class="mut">Click a question to reveal a model answer. Try answering aloud first.</p>')
    custom = [q for q in notes.get("interview_questions", []) if isinstance(q, dict) and q.get("q")]
    for q in custom:
        lv = q.get("level", 2) if q.get("level") in (1, 2, 3) else 2
        out.append(f'<details class="lv" data-level="{lv}"><summary>{badge(lv)} {md_inline(q["q"])}</summary>{paragraphs(q.get("a", ""))}</details>')
    for cid in found:
        c = CONCEPTS[cid]
        out.append(f'<details class="lv" data-level="{c["level"]}"><summary>{badge(c["level"])} {md_inline(c["q"])}</summary>{paragraphs(c["a"])}</details>')
    # revise
    out.append('<h2 id="revise">Also revise for interviews</h2><p class="mut">Topics this file does not use, but interviews often cover.</p>')
    for lv in (1, 2, 3):
        rest = [c for c in ORDER if CONCEPTS[c]["level"] == lv and c not in model["concepts"]]
        if rest:
            out.append(f'<div class="lv" data-level="{lv}"><h3>{LEVELS[lv]}</h3><ul class="check">'
                       + "".join(f'<li><details><summary>{esc(CONCEPTS[c]["title"])}</summary><p>{md_inline(CONCEPTS[c]["what"])}</p><p><b>{md_inline(CONCEPTS[c]["q"])}</b><br>{md_inline(CONCEPTS[c]["a"])}</p></details></li>' for c in rest)
                       + "</ul></div>")
    out.append("<h3>Fundamentals checklist</h3><ul class=check>" + "".join(f"<li><b>{esc(a)}:</b> {md_inline(b)}</li>" for a, b in FUNDAMENTALS) + "</ul>")
    ex = [e for e in notes.get("exercises", []) if str(e).strip()]
    if ex:
        out.append("<h2>Practice</h2><ol>" + "".join(f"<li>{md_inline(e)}</li>" for e in ex) + "</ol>")
    return _page(name, "\n".join(out), JS, model)


def _page(name, body, script, model) -> str:
    return ('<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>Python notes: {esc(name)}</title><style>{CSS}</style></head><body><main>{body}"
            '<p class="mut" style="margin-top:3em">Generated by py_tutor.py from the file\'s syntax tree; the file was never run. '
            "Explanations were written by a reader and may contain mistakes: check them against the code.</p></main>"
            + (f"<script>{script}</script>" if script else "") + "</body></html>\n")


def render_index(models: list) -> str:
    rows = "".join(f'<tr><td><a href="{esc(m["slug"])}.html">{esc(m["file"])}</a></td><td>{m["line_count"]}</td><td>{esc(m["level"])}</td>'
                   f'<td>{len(m["concepts"])}</td><td>{len(m["gotchas"])}</td></tr>' for m in models)
    return ('<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>Python notes index</title><style>{CSS}</style></head><body><main><h1>Python notes</h1>"
            '<p class="mut">Start with the Beginner files and work up.</p><table class="idx"><tr><th>File</th><th>Lines</th><th>Level</th><th>Concepts</th><th>Gotchas</th></tr>'
            f"{rows}</table></main></body></html>\n")


# ------------------------------------------------------------------ commands
def write(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def slugify(rel: str) -> str:
    s = re.sub(r"\.py$", "", rel.replace("\\", "/"))
    return re.sub(r"[^\w.-]+", "__", s).strip("_") or "file"


def collect(paths) -> list:
    files = []
    for p in paths:
        if os.path.isfile(p):
            files.append((os.path.basename(p), p))
        elif os.path.isdir(p):
            base = os.path.abspath(p)
            for dp, dns, fns in os.walk(base):
                dns[:] = sorted(d for d in dns if d not in SKIP_DIRS)
                for f in sorted(fns):
                    if f.endswith(".py"):
                        full = os.path.join(dp, f)
                        files.append((os.path.relpath(full, base).replace(os.sep, "/"), full))
        else:
            raise SystemExit(f"error: {p} is not a file or a folder")
    files = [(r, f) for r, f in files if f.endswith(".py") or len(paths) == 1]
    if not files:
        raise SystemExit("error: no .py files found")
    if len(files) > MAX_FILES:
        print(f"note: {len(files)} files found, using the first {MAX_FILES}; pass a sub-folder for the rest")
        files = files[:MAX_FILES]
    return files


def cmd_analyze(a) -> int:
    only = [x for x in (a.only or '').split(',') if x.strip()]
    files = collect(a.paths)
    first = a.paths[0].rstrip("/\\")
    name = os.path.splitext(os.path.basename(first))[0] if os.path.isfile(first) else os.path.basename(os.path.abspath(first))
    out = a.out or os.path.join("python-tutor", name)
    os.makedirs(out, exist_ok=True)
    models = []
    for rel, full in files:
        model = analyze_source(rel, read_py(full), only)
        model["slug"] = slugify(rel)
        write(os.path.join(out, model["slug"] + ".model.json"), json.dumps(model, indent=2, ensure_ascii=False) + "\n")
        models.append(model)
    print(f"analysed {len(models)} file(s) into {out}")
    for m in models:
        render_one(out, m)
    if len(models) > 1:
        write(os.path.join(out, "index.html"), render_index(models))
    return 0


def render_one(out: str, model: dict) -> None:
    npath = os.path.join(out, model["slug"] + ".notes.json")
    notes = load_notes(npath, model)
    write(npath, json.dumps(notes, indent=2, ensure_ascii=False) + "\n")
    write(os.path.join(out, model["slug"] + ".html"), render_html(model, notes))
    if model.get("error") and not model.get("fallback"):
        print(f"  {model['file']}: could not parse (line {model['error']['line']}: {model['error']['message']}); a page with the error was written")
        return
    if model.get("fallback"):
        print(f"  {model['file']}: could not parse (line {model['error']['line']}: {model['error']['message']}); using loose mode")
    todo = missing(model, notes)
    print(f"  {model['file']}: {model['level']}, {len(model['concepts'])} concepts, {len(model['blocks'])} blocks, "
          f"{len(model['gotchas'])} gotchas; {len(todo)} still to explain")


def load_models(out: str) -> list:
    ms = []
    for f in sorted(os.listdir(out)) if os.path.isdir(out) else []:
        if f.endswith(".model.json"):
            with open(os.path.join(out, f), encoding="utf-8") as fh:
                ms.append(json.load(fh))
    if not ms:
        raise SystemExit(f"error: no *.model.json in {out}; run analyze first")
    return ms


def cmd_render(a) -> int:
    ms = load_models(a.folder)
    for m in ms:
        render_one(a.folder, m)
    if len(ms) > 1:
        write(os.path.join(a.folder, "index.html"), render_index(ms))
    return 0


def cmd_check(a) -> int:
    bad = warned = 0
    for m in load_models(a.folder):
        notes = load_notes(os.path.join(a.folder, m["slug"] + ".notes.json"), m)
        todo = missing(m, notes)
        if todo:
            bad += 1
            print(f"{m['file']}: not complete, still to explain:")
            for x in todo[:40]:
                print("  -", x)
        warn = warnings(m, notes) if not m.get("error") or m.get("fallback") else []
        if warn:
            warned += 1
            print(f"{m['file']}: {len(warn)} warning(s) about the explanations:")
            for x in warn[:30]:
                print("  ?", x)
    print("Result: " + ("not complete" if bad else "complete") + (f" ({warned} file(s) with warnings)" if warned else ""))
    return 1 if bad or (a.strict and warned) else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("analyze", help="parse files and write the first draft of the notes")
    p.add_argument("paths", nargs="+", help=".py files or folders")
    p.add_argument("--out", help="output folder (default python-tutor/<name>)")
    p.add_argument("--only", help="comma-separated functions, Class.method or classes to explain; the functions they call in the same file come along")
    p.set_defaults(fn=cmd_analyze)
    p = sub.add_parser("render", help="rebuild the HTML after editing *.notes.json")
    p.add_argument("folder")
    p.set_defaults(fn=cmd_render)
    p = sub.add_parser("check", help="list blocks that still have no explanation, and suspicious explanations")
    p.add_argument("folder")
    p.add_argument("--strict", action="store_true", help="also fail on warnings")
    p.set_defaults(fn=cmd_check)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
