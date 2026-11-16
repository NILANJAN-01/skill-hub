"""Static "what does this file do" analysis for py_tutor.py: public API, inputs and outputs, side effects,
call graph, command-line options, docstring examples, and a loose line-based fallback for files that do not
parse (Python 2, syntax errors). It never imports or runs the analysed code. Standard library only."""
from __future__ import annotations

import ast
import doctest
import re

NETWORK_PREFIX = ("requests.", "urllib.", "http.client.", "httpx.", "socket.", "aiohttp.", "urllib3.", "ftplib.", "smtplib.", "websocket.")
DB_PREFIX = ("sqlite3.", "psycopg2.", "pymysql.", "sqlalchemy.", "pymongo.", "redis.", "mysql.")
PROC_PREFIX = ("subprocess.", "os.system", "os.popen", "os.spawn", "os.exec")
FILE_DELETE = ("os.remove", "os.unlink", "os.rmdir", "os.removedirs", "shutil.rmtree", "os.rename", "shutil.move", "os.replace", "Path.unlink")
FILE_MAKE = ("os.makedirs", "os.mkdir", "shutil.copy", "shutil.copy2", "shutil.copytree")
PATH_READ = ("read_text", "read_bytes")
PATH_WRITE = ("write_text", "write_bytes")
EXIT_CALLS = ("sys.exit", "exit", "quit", "os._exit")
RANDOM_PREFIX = ("random.", "secrets.", "numpy.random.", "np.random.")
LOG_PREFIX = ("logging.", "logger.", "log.", "self.logger.", "self.log.")
THREAD_CALLS = ("threading.Thread", "multiprocessing.Process", "multiprocessing.Pool", "asyncio.run", "asyncio.create_task",
                "concurrent.futures.ThreadPoolExecutor", "ThreadPoolExecutor", "ProcessPoolExecutor", "loop.run_until_complete")


def dotted(node) -> str:
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    if isinstance(node, ast.Call):
        inner = dotted(node.func)
        return (inner + "()." + ".".join(reversed(parts))) if parts else inner
    return ".".join(reversed(parts)) if parts else ""


def seg(source: str, node) -> str:
    try:
        return ast.get_source_segment(source, node) or ""
    except Exception:  # noqa: BLE001 - positions can be missing on synthetic nodes
        return ""


def first_line(doc) -> str:
    if not doc:
        return ""
    return doc.strip().split("\n")[0].strip()


def _const_str(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def open_mode(call: ast.Call) -> str:
    node = call.args[1] if len(call.args) > 1 else next((k.value for k in call.keywords if k.arg == "mode"), None)
    if node is None:
        return "r"
    return _const_str(node) or "?"          # "?" = the mode is a variable, known only at run time


# ------------------------------------------------------------------ effects, returns, raises
def effects_in(node, within=None) -> dict:
    """Map side-effect description -> list of line numbers, for the subtree of node."""
    out: dict = {}

    def add(label, n):
        out.setdefault(label, []).append(getattr(n, "lineno", 0))

    for n in ast.walk(node):
        t = type(n).__name__
        if t == "Call":
            name = dotted(n.func)
            last = name.split(".")[-1]
            if name == "open" or name.endswith(".open") and name.split(".")[0] in ("io", "codecs", "gzip", "bz2"):
                mode = open_mode(n)
                add("opens files (read or write decided at run time)" if mode == "?"
                    else "writes files" if any(c in mode for c in "wax+") else "reads files", n)
            elif last in PATH_READ:
                add("reads files", n)
            elif last in PATH_WRITE:
                add("writes files", n)
            elif name in FILE_DELETE or last in ("unlink", "rmtree"):
                add("deletes, renames or moves files", n)
            elif name in FILE_MAKE or last in ("mkdir", "makedirs"):
                add("creates folders or copies files", n)
            elif name == "print":
                add("prints to the screen", n)
            elif name in ("input", "raw_input"):
                add("asks the user for input", n)
            elif name in ("sys.stdout.write", "sys.stderr.write"):
                add("prints to the screen", n)
            elif name in EXIT_CALLS:
                add("ends the program", n)
            elif name.startswith(NETWORK_PREFIX):
                add("uses the network", n)
            elif name.startswith(DB_PREFIX):
                add("uses a database", n)
            elif name.startswith(PROC_PREFIX):
                add("runs other programs", n)
            elif name in ("os.getenv", "os.environ.get", "os.environ.setdefault"):
                add("reads environment variables", n)
            elif name.startswith(RANDOM_PREFIX):
                add("uses randomness", n)
            elif name == "time.sleep" or name == "asyncio.sleep":
                add("waits (sleeps)", n)
            elif name in ("time.time", "time.monotonic", "datetime.now", "datetime.datetime.now", "datetime.utcnow", "time.perf_counter"):
                add("reads the clock", n)
            elif name.startswith(LOG_PREFIX) and last in ("debug", "info", "warning", "warn", "error", "critical", "exception", "log"):
                add("writes log messages", n)
            elif name in THREAD_CALLS:
                add("starts threads, processes or an event loop", n)
            elif name in ("eval", "exec", "compile", "__import__", "importlib.import_module"):
                add("runs or loads code dynamically", n)
            elif name in ("json.dump", "pickle.dump", "csv.writer", "yaml.dump", "shutil.make_archive"):
                add("writes data files", n)
            elif name in ("json.load", "pickle.load", "csv.reader", "csv.DictReader", "yaml.safe_load", "yaml.load"):
                add("reads data files", n)
        elif t in ("Global", "Nonlocal"):
            add("changes shared (global) state", n)
        elif t == "Attribute" and dotted(n) in ("os.environ", "sys.argv", "sys.stdin"):
            add({"os.environ": "reads environment variables", "sys.argv": "reads command-line arguments",
                 "sys.stdin": "reads standard input"}[dotted(n)], n)
        elif t == "Assign" and within is not None:
            for tg in n.targets:
                if isinstance(tg, ast.Attribute) and isinstance(tg.value, ast.Name) and tg.value.id in ("self", "cls"):
                    add("changes the object's own state", n)
    return {k: sorted(set(v)) for k, v in out.items()}


def returns_of(fn) -> list:
    """Describe what a function returns, from its return statements (not run)."""
    kinds = []
    has_yield = False
    stack = list(ast.iter_child_nodes(fn))
    while stack:
        n = stack.pop()
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(n, (ast.Yield, ast.YieldFrom)):
            has_yield = True
        if isinstance(n, ast.Return):
            v = n.value
            if v is None or (isinstance(v, ast.Constant) and v.value is None):
                kinds.append("None")
            elif isinstance(v, ast.Constant):
                kinds.append({bool: "a bool", int: "a number", float: "a number", str: "a string", bytes: "bytes"}.get(type(v.value), "a constant"))
            elif isinstance(v, (ast.List, ast.ListComp)):
                kinds.append("a list")
            elif isinstance(v, (ast.Dict, ast.DictComp)):
                kinds.append("a dict")
            elif isinstance(v, (ast.Set, ast.SetComp)):
                kinds.append("a set")
            elif isinstance(v, ast.Tuple):
                kinds.append(f"a tuple of {len(v.elts)} values")
            elif isinstance(v, ast.JoinedStr):
                kinds.append("a string")
            elif isinstance(v, (ast.Compare, ast.BoolOp)) or (isinstance(v, ast.UnaryOp) and isinstance(v.op, ast.Not)):
                kinds.append("a bool")
            elif isinstance(v, ast.Call):
                kinds.append(f"the result of `{dotted(v.func) or 'a call'}(...)`")
            elif isinstance(v, ast.Name):
                kinds.append(f"the variable `{v.id}`")
            elif isinstance(v, (ast.BinOp, ast.UnaryOp)):
                kinds.append("a computed value")
            elif isinstance(v, ast.IfExp):
                kinds.append("one of two values")
            else:
                kinds.append("an expression")
        stack.extend(ast.iter_child_nodes(n))
    if has_yield:
        return ["a generator (yields values one by one)"]
    out = []
    for k in kinds:
        if k not in out:
            out.append(k)
    return out[:6] or ["None (no return statement)"]


def raises_of(fn) -> list:
    out = []
    for n in ast.walk(fn):
        if isinstance(n, ast.Raise):
            if n.exc is None:
                name = "(re-raises the current error)"
            else:
                e = n.exc.func if isinstance(n.exc, ast.Call) else n.exc
                name = dotted(e) or "an exception"
            if name not in out:
                out.append(name)
    return out[:6]


def params_of(fn, source: str) -> list:
    a = fn.args
    pos = list(getattr(a, "posonlyargs", [])) + list(a.args)
    defaults = [None] * (len(pos) - len(a.defaults)) + list(a.defaults)
    rows = []
    for arg, d in zip(pos, defaults):
        rows.append({"name": arg.arg, "default": seg(source, d) if d is not None else None,
                     "type": seg(source, arg.annotation) if arg.annotation else ""})
    if a.vararg:
        rows.append({"name": "*" + a.vararg.arg, "default": None, "type": seg(source, a.vararg.annotation) if a.vararg.annotation else ""})
    for arg, d in zip(a.kwonlyargs, a.kw_defaults):
        rows.append({"name": arg.arg + " (keyword-only)", "default": seg(source, d) if d is not None else None,
                     "type": seg(source, arg.annotation) if arg.annotation else ""})
    if a.kwarg:
        rows.append({"name": "**" + a.kwarg.arg, "default": None, "type": ""})
    return [r for r in rows if r["name"] not in ("self", "cls")]


def api_entry(fn, source: str, owner: str = "") -> dict:
    name = (owner + "." if owner else "") + fn.name
    decs = [dotted(d.func if isinstance(d, ast.Call) else d) for d in fn.decorator_list]
    return {"name": name, "kind": "async function" if isinstance(fn, ast.AsyncFunctionDef) else ("method" if owner else "function"),
            "line": fn.lineno, "end": fn.end_lineno, "public": not fn.name.startswith("_") or (fn.name.startswith("__") and fn.name.endswith("__")),
            "decorators": decs, "doc": first_line(ast.get_docstring(fn)), "params": params_of(fn, source),
            "returns_type": seg(source, fn.returns) if fn.returns else "", "returns": returns_of(fn), "raises": raises_of(fn),
            "effects": sorted(effects_in(fn, within=fn)), "calls": sorted({dotted(c.func) for c in ast.walk(fn) if isinstance(c, ast.Call) and dotted(c.func)})[:15]}


# ------------------------------------------------------------------ whole-file functionality
def cli_of(tree, source: str) -> dict:
    args, subs, desc, click = [], [], "", []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            name = dotted(n.func)
            last = name.split(".")[-1]
            if last == "ArgumentParser":
                for k in n.keywords:
                    if k.arg == "description":
                        desc = _const_str(k.value) or ""
            elif last == "add_argument":
                flags = [s for s in (_const_str(a) for a in n.args) if s]
                kw = {k.arg: (seg(source, k.value)) for k in n.keywords if k.arg in ("help", "default", "type", "action", "required", "choices", "nargs")}
                args.append({"flags": flags, "help": (_const_str(next((k.value for k in n.keywords if k.arg == "help"), None)) or ""),
                             "details": {k: v for k, v in kw.items() if k != "help"}, "line": n.lineno})
            elif last == "add_parser":
                s = _const_str(n.args[0]) if n.args else None
                if s:
                    subs.append(s)
            elif last in ("option", "argument") and name.split(".")[0] in ("click", "typer", "cli", "app"):
                flags = [s for s in (_const_str(a) for a in n.args) if s]
                click.append({"flags": flags, "help": _const_str(next((k.value for k in n.keywords if k.arg == "help"), None)) or "",
                              "details": {}, "line": n.lineno})
    return {"description": desc, "arguments": args + click, "subcommands": subs}


def doctests_of(tree) -> list:
    out = []
    parser = doctest.DocTestParser()
    nodes = [tree] + [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    for n in nodes:
        doc = ast.get_docstring(n, clean=False)
        if not doc or ">>>" not in doc:
            continue
        owner = "module" if isinstance(n, ast.Module) else n.name
        try:
            for ex in parser.get_examples(doc):
                out.append({"in": owner, "source": ex.source.rstrip("\n"), "want": ex.want.rstrip("\n")})
        except ValueError:
            continue
        if len(out) >= 24:
            break
    return out[:24]


def functionality(tree, source: str, stdlib: set) -> dict:
    api = []
    top_funcs, methods_of = {}, {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            api.append(api_entry(node, source))
            top_funcs[node.name] = node
        elif isinstance(node, ast.ClassDef):
            entry = {"name": node.name, "kind": "class", "line": node.lineno, "end": node.end_lineno, "public": not node.name.startswith("_"),
                     "decorators": [dotted(d.func if isinstance(d, ast.Call) else d) for d in node.decorator_list],
                     "doc": first_line(ast.get_docstring(node)), "params": [], "returns_type": "", "returns": [],
                     "raises": [], "effects": [], "calls": [], "bases": [dotted(b) for b in node.bases]}
            api.append(entry)
            ms = [m for m in node.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))]
            methods_of[node.name] = {m.name: m for m in ms}
            for m in ms:
                api.append(api_entry(m, source, owner=node.name))
    defined = set(top_funcs) | {f"{c}.{m}" for c, ms in methods_of.items() for m in ms}

    def resolve(call_name: str, owner: str) -> str:
        if call_name in top_funcs:
            return call_name
        if owner and call_name.startswith(("self.", "cls.")):
            cand = f"{owner}.{call_name.split('.', 1)[1].split('.')[0]}"
            return cand if cand in defined else ""
        if call_name in defined:
            return call_name
        if call_name.split(".")[0] in methods_of and call_name in defined:
            return call_name
        return ""

    graph = {}
    for node in tree.body:
        pairs = []
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            pairs.append((node.name, node, ""))
        elif isinstance(node, ast.ClassDef):
            for m in node.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    pairs.append((f"{node.name}.{m.name}", m, node.name))
        for name, fn, owner in pairs:
            seen = []
            for c in ast.walk(fn):
                if isinstance(c, ast.Call):
                    r = resolve(dotted(c.func), owner)
                    if r and r != name and r not in seen:
                        seen.append(r)
            graph[name] = seen
    # class instantiation counts as a call to __init__ of that class in the module flow
    entry_calls, module_nodes = [], []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom)):
            continue
        module_nodes.append(node)
        for c in ast.walk(node):
            if isinstance(c, ast.Call):
                r = resolve(dotted(c.func), "")
                if not r and dotted(c.func) in methods_of:
                    r = dotted(c.func)
                if r and r not in entry_calls:
                    entry_calls.append(r)
    guard_calls = []
    for node in module_nodes:
        if isinstance(node, ast.If) and isinstance(node.test, ast.Compare) and isinstance(node.test.left, ast.Name) \
                and node.test.left.id == "__name__":
            for c in ast.walk(node):
                if isinstance(c, ast.Call):
                    r = resolve(dotted(c.func), "")
                    if not r and dotted(c.func) in methods_of:
                        r = dotted(c.func)
                    if r and r not in guard_calls:
                        guard_calls.append(r)
    effects = {}
    for node in tree.body:
        for k, v in effects_in(node, within=node if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else None).items():
            effects.setdefault(k, []).extend(v)
    effects = {k: sorted(set(v)) for k, v in sorted(effects.items())}
    env, files, urls = [], [], []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            name = dotted(n.func)
            if name in ("os.getenv", "os.environ.get", "os.environ.setdefault") and n.args and _const_str(n.args[0]):
                env.append(_const_str(n.args[0]))
            if name == "open" and n.args and _const_str(n.args[0]):
                files.append({"path": _const_str(n.args[0]), "mode": open_mode(n), "line": n.lineno})
        elif isinstance(n, ast.Subscript) and dotted(n.value) == "os.environ":
            s = _const_str(n.slice) or _const_str(getattr(n.slice, "value", None))
            if s:
                env.append(s)
        elif isinstance(n, ast.Constant) and isinstance(n.value, str) and re.match(r"https?://", n.value):
            urls.append(n.value[:120])
    third = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                third.add(a.name.split(".")[0])
        elif isinstance(n, ast.ImportFrom) and n.module and not n.level:
            third.add(n.module.split(".")[0])
    local = {n.split(".")[0] for n in top_funcs}
    third = sorted(m for m in third if m not in stdlib and m not in ("__future__",) and m not in local)
    return {"api": api, "cli": cli_of(tree, source), "effects": effects, "env": sorted(set(env))[:12], "files": files[:12],
            "urls": sorted(set(urls))[:8], "third_party": third, "call_graph": graph, "entry_calls": guard_calls or entry_calls,
            "runs_on_import": bool(module_nodes) and not guard_calls and bool(entry_calls), "has_main_guard": bool(guard_calls),
            "doctests": doctests_of(tree)}


# ------------------------------------------------------------------ loose mode (Python 2 and syntax errors)
LOOSE_CONCEPTS = [
    ("variables", r"^\s*[A-Za-z_][\w.\[\]'\"]*\s*(?:[-+*/%]?=)\s*[^=]"), ("for-loops", r"^\s*for\s.+\sin\s"),
    ("while-loops", r"^\s*while\s"), ("conditionals", r"^\s*(?:if|elif)\s"), ("functions", r"^\s*def\s"),
    ("classes", r"^\s*class\s"), ("imports", r"^\s*(?:import|from)\s"), ("exceptions", r"^\s*try\s*:"),
    ("with-statements", r"^\s*with\s"), ("lambda", r"\blambda\b"), ("comprehensions", r"\[[^\]]*\sfor\s[^\]]*\sin\s"),
    ("generators", r"\byield\b"), ("decorators", r"^\s*@\w"), ("print-input", r"\bprint\b|\binput\s*\(|\braw_input\b"),
    ("f-strings", r"\bf['\"]"), ("raise", r"^\s*raise\b"), ("assert", r"^\s*assert\b"), ("async-await", r"\basync\s+def\b|\bawait\b"),
    ("break-continue", r"^\s*(?:break|continue)\b"), ("recursion-hint", r"$^")]
PY2_HINTS = [
    (r"^\s*print\s+[^(\s=]", "print statement", "`print x` becomes `print(x)`"),
    (r"^\s*except\s+[\w.]+\s*,\s*\w+\s*:", "old except syntax", "`except E, e:` becomes `except E as e:`"),
    (r"\braw_input\s*\(", "raw_input", "use `input()`"),
    (r"\bxrange\s*\(", "xrange", "use `range()`"),
    (r"\bunicode\s*\(|\bbasestring\b", "unicode / basestring", "use `str`"),
    (r"\.(?:iteritems|itervalues|iterkeys)\s*\(", "dict.iteritems()", "use `.items()`, `.values()`, `.keys()`"),
    (r"\blong\s*\(", "long()", "`int` is unlimited in Python 3"),
    (r"<>", "`<>` operator", "use `!=`"),
    (r"^\s*exec\s+[\"']", "exec statement", "`exec(code)` is a function"),
    (r"\braise\s+\w+\s*,\s*", "old raise syntax", "`raise E, msg` becomes `raise E(msg)`"),
    (r"\b0[0-7]{3,}\b", "old octal literal", "write `0o777`"),
]
LOOSE_GOTCHAS = [
    ("bare-except", r"^\s*except\s*:", "Bare except", "`except:` also catches Ctrl+C and `sys.exit()`.", "Catch a specific exception type."),
    ("eq-none", r"[=!]=\s*None\b", "Comparing to None with ==", "Uses `== None` / `!= None`.", "Use `is None` / `is not None`."),
    ("eval", r"\b(?:eval|exec)\s*\(", "Use of eval/exec", "Runs text as code.", "Dangerous with untrusted input."),
    ("hard-coded-secret", r"""(?i)(password|passwd|secret|token|api[_-]?key|credential)\w*\s*=\s*['"][^'"]+['"]""", "Possible hard-coded secret",
     "A secret-looking name is set to a string literal (the value is hidden in these notes).", "Read secrets from the environment or a secret store."),
    ("shell-true", r"shell\s*=\s*True", "subprocess with shell=True", "The command goes through the shell.", "Pass an argument list instead."),
]


def loose_outline(lines: list) -> list:
    """Blocks for def/class lines using indentation only: [(kind, name, parent, start, end)]."""
    items = []
    stack = []   # (indent, class name)
    n = len(lines)
    for i, raw in enumerate(lines):
        m = re.match(r"^(\s*)(?:async\s+)?(def|class)\s+(\w+)", raw)
        if not m:
            continue
        indent = len(m.group(1).expandtabs(4))
        while stack and stack[-1][0] >= indent:
            stack.pop()
        parent = ".".join(x[1] for x in stack)
        end = i + 1
        for j in range(i + 1, n):
            s = lines[j]
            if s.strip() == "" or s.lstrip().startswith("#"):
                continue
            if len(s) - len(s.lstrip()) <= len(m.group(1)):
                break
            end = j + 1
        kind = "class" if m.group(2) == "class" else ("method" if stack else "function")
        items.append((kind, m.group(3), parent, i + 1, end))
        if m.group(2) == "class":
            stack.append((indent, m.group(3)))
    return items


def loose_concepts(lines: list, start: int = 1, end: int = None) -> dict:
    out: dict = {}
    end = end or len(lines)
    for ln in range(start, end + 1):
        text = lines[ln - 1]
        if text.lstrip().startswith("#"):
            continue
        for cid, rx in LOOSE_CONCEPTS:
            if rx != "$^" and re.search(rx, text):
                out.setdefault(cid, []).append(ln)
    return out


def loose_py2(lines: list) -> list:
    out = []
    for ln, text in enumerate(lines, 1):
        for rx, title, fix in PY2_HINTS:
            if re.search(rx, text):
                out.append({"line": ln, "what": title, "fix": fix})
    return out[:60]


def loose_gotchas(lines: list) -> list:
    out = []
    for ln, text in enumerate(lines, 1):
        if text.lstrip().startswith("#"):
            continue
        for gid, rx, title, what, advice in LOOSE_GOTCHAS:
            if re.search(rx, text):
                out.append({"id": gid, "title": title, "line": ln, "text": what, "advice": advice})
    return out
