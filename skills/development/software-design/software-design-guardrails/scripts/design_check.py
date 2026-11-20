#!/usr/bin/env python3
"""Flag software-design red flags in source code.

The rules follow the red flags named in "A Philosophy of Software Design"
(John Ousterhout): pass-through methods and variables, shallow one-use
functions, overexposed interfaces, swallowed or repeated error handlers,
duplicated code, comments that repeat the code, missing or contaminated
interface comments, vague names, generic containers and kludge markers.

Python is parsed with `ast`. C-family languages (Java, Kotlin, C#, Go,
JavaScript/TypeScript, C/C++, Rust, Swift, Dart, Scala, PHP) use lighter
text heuristics, so treat their findings as prompts for review, not proof.

Usage:
  python design_check.py [PATH ...]            scan files or folders (default: .)
  python design_check.py --diff [REF]          report only lines changed since REF
                                               (default HEAD) plus untracked files
  python design_check.py --staged              report only staged lines (pre-commit)
  python design_check.py --list-rules          show every rule, its red flag and fix

Options:
  --format text|json      output format (default text)
  --fail-on warning|info|never
                          exit 1 when a finding has at least this severity
                          (default warning)
  --select R1,R2 / --ignore R1,R2
                          run only / skip these rule ids
  --baseline FILE         hide findings recorded in FILE
  --write-baseline FILE   record current findings in FILE (to adopt on old code)
  --include-tests         also apply interface and size rules to test files

Silence one finding with a comment on the same line or the line above:
  # design-check: ignore[rule-id] -- reason
Exit codes: 0 clean, 1 findings at or above --fail-on, 2 usage or git error.
Read-only except --write-baseline. Python 3.8+, standard library only.
"""
import argparse
import ast
import bisect
import io
import json
import os
import re
import subprocess
import sys
import tokenize
from collections import Counter, defaultdict, namedtuple

Rule = namedtuple("Rule", "red_flag severity chapter fix")

RULES = {
    "pass-through-method": Rule(
        "Pass-Through Method", "warning", "ch. 7.1",
        "Give this layer real work, let callers use the lower object directly, "
        "or merge the two classes so each has a distinct responsibility."),
    "pass-through-variable": Rule(
        "Pass-Through Variable", "warning", "ch. 7.5",
        "Stop threading the value through layers that never use it: put it in an "
        "object both ends already share, or in a context object."),
    "single-use-shallow": Rule(
        "Shallow Module", "info", "ch. 4.5, 9.6",
        "Inline it at its only call site, or give it enough work to hide something."),
    "trivial-accessor": Rule(
        "Shallow Module (getter/setter)", "info", "ch. 19.6",
        "Offer a higher-level operation instead of exposing the raw field."),
    "long-parameter-list": Rule(
        "Overexposure", "warning", "ch. 4.7, 5.7, 8.2",
        "Make the common case simple: give defaults, group related values into "
        "one type, or let the module decide instead of the caller."),
    "swallowed-error": Rule(
        "Exception masked too far", "warning", "ch. 10.10",
        "Handle it, let it reach one aggregate handler, or crash with a message. "
        "If ignoring it is correct, write a comment that says why."),
    "repeated-handler": Rule(
        "Repetition (error handlers)", "info", "ch. 10.7",
        "Aggregate: let the error propagate to one handler higher up."),
    "duplicate-code": Rule(
        "Repetition", "warning", "ch. 9.3",
        "Find the missing abstraction: move the shared code into one function "
        "with a simple signature, or restructure so it runs in one place."),
    "comment-repeats-code": Rule(
        "Comment Repeats Code", "info", "ch. 13.2",
        "Say what the code cannot: why, units, bounds, invariants or the intent "
        "of the block. Otherwise delete the comment."),
    "doc-repeats-name": Rule(
        "Comment Repeats Code", "info", "ch. 13.2",
        "Use different words from the name: meaning, units, edge cases, result, "
        "side effects, errors."),
    "missing-interface-doc": Rule(
        "Obscurity (no interface comment)", "info", "ch. 13.5, 15",
        "Write the interface comment: behaviour as callers see it, each argument, "
        "the result, side effects, errors and preconditions."),
    "impl-in-interface-doc": Rule(
        "Implementation Documentation Contaminates Interface", "info", "ch. 13.5",
        "Move how-it-works text into the body; keep the interface comment to "
        "what callers need."),
    "vague-name": Rule(
        "Vague Name", "info", "ch. 14.3",
        "Pick a precise name that tells a reader what the thing is (and is not)."),
    "non-predicate-boolean": Rule(
        "Vague Name (boolean)", "info", "ch. 14.3",
        "Name booleans as predicates, for example is_muted, has_paid, retry_allowed."),
    "generic-container": Rule(
        "Nonobvious Code (generic container)", "info", "ch. 18.2",
        "Return a small named type (dataclass, record, struct) whose fields say "
        "what each value means."),
    "tactical-marker": Rule(
        "Tactical programming (kludge marker)", "info", "ch. 3",
        "Fix the design problem now while the context is loaded, or file a "
        "tracked issue and reference it."),
}
SEVERITY_RANK = {"info": 1, "warning": 2}

PY_EXT = {".py"}
C_EXT = {
    ".js": "js", ".jsx": "js", ".mjs": "js", ".cjs": "js", ".ts": "ts", ".tsx": "ts",
    ".java": "java", ".kt": "kotlin", ".kts": "kotlin", ".cs": "csharp", ".go": "go",
    ".c": "c", ".h": "c", ".cc": "cpp", ".cpp": "cpp", ".cxx": "cpp", ".hpp": "cpp",
    ".hh": "cpp", ".rs": "rust", ".swift": "swift", ".dart": "dart", ".scala": "scala",
    ".php": "php",
}
SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "venv", ".venv", "env", "__pycache__",
    "build", "dist", "target", "out", "bin", "obj", "vendor", "third_party",
    ".tox", ".mypy_cache", ".pytest_cache", ".gradle", ".idea", ".next", "coverage",
}
MAX_FILE_BYTES = 1_000_000
TEST_FILE_RE = re.compile(
    r"(^test_.*\.py$|_test\.(py|go)$|(Test|Tests|Spec)\.(java|kt|cs|swift|scala)$|"
    r"\.(test|spec)\.[jt]sx?$|_spec\.rb$)")
TEST_DIRS = {"test", "tests", "__tests__", "spec", "testing", "androidTest"}
IGNORE_RE = re.compile(r"design-check:\s*ignore(?:\[([\w\-, ]+)\])?")

# ---------------------------------------------------------------- words ----

STOPWORDS = set(
    "a an the of to in on for and or is are be by with from this that it its as at "
    "if then else which into each all any we our not no".split())
GENERIC_DOC_WORDS = {
    "return", "get", "set", "method", "function", "class", "object", "given",
    "new", "create", "helper", "make", "param", "parameter", "argument",
    "specified", "current", "obtain", "provided", "instance", "call", "invoke"}
ABBREV = {
    "ptr": "pointer", "num": "number", "idx": "index", "cnt": "count", "str": "string",
    "msg": "message", "err": "error", "buf": "buffer", "len": "length", "val": "value",
    "var": "variable", "obj": "object", "arg": "argument", "param": "parameter",
    "init": "initialize", "initialise": "initialize", "calc": "calculate", "cfg": "config",
    "conf": "config", "db": "database", "req": "request", "resp": "response",
    "res": "response", "ctx": "context", "src": "source", "dst": "destination",
    "dest": "destination", "tmp": "temporary", "temp": "temporary", "attr": "attribute",
    "elem": "element", "btn": "button", "img": "image", "doc": "document",
    "pos": "position", "prev": "previous", "cur": "current", "curr": "current",
    "sel": "selection", "h": "horizontal", "v": "vertical", "inc": "increment",
    "dec": "decrement", "add": "add", "del": "delete", "rm": "remove"}
WHY_WORDS = {"because", "so", "otherwise", "must", "never", "always", "note", "why",
             "unit", "units", "pixels", "seconds", "ms", "bytes", "inclusive", "exclusive",
             "invariant", "assume", "assumes", "ensure", "guarantee", "warning", "workaround"}
IDENT_RE = re.compile(r"[A-Za-z_$][\w$]*")
VAGUE_NAMES = {
    "data", "info", "tmp", "temp", "obj", "thing", "things", "stuff", "foo", "bar",
    "baz", "qux", "val", "var", "flag", "dummy", "whatever", "something", "mydata",
    "myvar", "the_data", "thedata"}
VAGUE_FUNCTIONS = {
    "process", "handle", "do", "doit", "do_it", "run_it", "helper", "util", "utils",
    "manage", "do_stuff", "dostuff", "do_work", "dowork", "process_data",
    "processdata", "handle_data", "handledata", "misc", "func", "foo", "bar"}
NUMBERED_RE = re.compile(r"^(?:data|tmp|temp|val|var|obj|item|arg|res|str|list|arr|x|y)\d+$", re.I)
BOOL_VAGUE = {"status", "flag", "state", "mode", "check", "switch", "toggle", "value",
              "val", "result", "bool", "boolean"}
TACTICAL_RE = re.compile(
    r"\b(HACK|XXX|KLUDGE|FIXME)\b|\b(kludge|quick fix|quick hack|temporary fix|"
    r"temporary hack|temp fix|for now)\b", re.I)
IMPL_DOC_RE = re.compile(
    r"\b(internally|implemented (?:with|using|by|as)|implementation detail|for[- ]loop|"
    r"while[- ]loop|we (?:loop|iterate)|loops? (?:over|through)|private (?:field|member|"
    r"variable|method|helper)|helper (?:method|function)|calls? the (?:private|internal)|"
    r"(?:hash ?map|dictionary|linked list|array list) (?:is used|to store))\b", re.I)


def split_words(identifier):
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", identifier)
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", s)
    return [w.lower() for w in re.split(r"[^A-Za-z0-9]+", s) if w]


def stem(word):
    word = ABBREV.get(word, word)
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def text_words(text):
    words = []
    for ident in IDENT_RE.findall(text):
        words.extend(split_words(ident))
    return {stem(w) for w in words if w not in STOPWORDS and len(w) > 1}


def comment_repeats(comment, code):
    """True when nearly every word of the comment already appears in the code."""
    raw = {w.lower() for w in IDENT_RE.findall(comment)}
    if raw & WHY_WORDS or "?" in comment and len(raw) > 4:
        return False
    cw = text_words(comment)
    if len(cw) < 2 or len(cw) > 10:
        return False
    hits = len(cw & text_words(code))
    return hits / len(cw) >= 0.75


def related_names(a, b):
    """True when two function names share a meaningful word (load / load_file)."""
    generic = {"get", "set", "do", "run", "impl", "internal", "inner", "helper", "the"}
    wa = {w for w in split_words(a) if len(w) > 2} - generic
    wb = {w for w in split_words(b) if len(w) > 2} - generic
    return bool(wa & wb)


def last_word(name):
    words = split_words(name)
    return words[-1] if words else ""


# --------------------------------------------------------------- results ----

class Finding(object):
    __slots__ = ("rule", "path", "line", "end_line", "message", "symbol", "related")

    def __init__(self, rule, path, line, message, end_line=None, symbol="", related=None):
        self.rule = rule
        self.path = path
        self.line = line
        self.end_line = end_line or line
        self.message = message
        self.symbol = symbol
        self.related = related  # (path, first_line, last_line) for duplicates

    @property
    def severity(self):
        return RULES[self.rule].severity

    def to_dict(self, rel):
        rule = RULES[self.rule]
        d = {"rule": self.rule, "severity": rule.severity, "red_flag": rule.red_flag,
             "chapter": rule.chapter, "path": rel(self.path), "line": self.line,
             "end_line": self.end_line, "message": self.message, "fix": rule.fix}
        if self.related:
            d["related"] = {"path": rel(self.related[0]), "line": self.related[1],
                            "end_line": self.related[2]}
        return d


# One comment: first and last line, text without markers, whether it stands on its own
# line (not after code), and its column.
Comment = namedtuple("Comment", "line end_line text own_line col")


class SourceFile(object):
    """One scanned file: original lines, comments and code lines without comments."""

    def __init__(self, path, text, lang):
        self.path = path
        self.text = text
        self.lang = lang
        self.lines = text.split("\n")
        self.comments = []
        self.code_lines = self.lines  # replaced by a comment-free version
        self.is_test = is_test_path(path)

    def ignored(self, line, rule):
        for ln in (line, line - 1):
            if 1 <= ln <= len(self.lines):
                m = IGNORE_RE.search(self.lines[ln - 1])
                if m and (not m.group(1) or rule in [r.strip() for r in m.group(1).split(",")]):
                    return True
        return False


class Context(object):
    """State shared across files for rules that need the whole code base."""

    def __init__(self, include_tests=False):
        self.include_tests = include_tests
        self.findings = []
        self.skipped = []
        self.files = []
        self.py_calls = Counter()
        self.c_calls = Counter()
        self.c_defs = Counter()
        self.shallow = []      # (lang_family, name, Finding)
        self.forwarders = {}   # (func, param) -> (src, line, callee names)
        self.py_defs = set()   # names of Python functions defined in the scanned code

    def add(self, src, rule, line, message, end_line=None, symbol="", related=None):
        if not src.ignored(line, rule):
            self.findings.append(Finding(rule, src.path, line, message, end_line,
                                         symbol, related))


def is_test_path(path):
    base = os.path.basename(path)
    if TEST_FILE_RE.search(base):
        return True
    parts = set(re.split(r"[\\/]", os.path.dirname(path)))
    return bool(parts & TEST_DIRS)


# ----------------------------------------------------------- shared rules ----

class FileScan(object):
    """Reports findings for one file: the shared context, the file and the names seen.

    Rule helpers live here so the context, the file and the per-file state do not
    have to be passed through every analysis function.
    """

    def __init__(self, ctx, src):
        self.ctx = ctx
        self.src = src
        self.seen = set()  # (kind, name) pairs already reported, one finding per name

    def add(self, rule, line, message, **extra):
        """Record a finding for this file unless an inline ignore comment covers it."""
        self.ctx.add(self.src, rule, line, message, **extra)

    def comments(self):
        """comment-repeats-code and tactical-marker, for every language."""
        code = self.src.code_lines
        for c in self.src.comments:
            if TACTICAL_RE.search(c.text):
                self.add("tactical-marker", c.line,
                         "kludge marker in comment: %r" % c.text.strip()[:80])
            if c.line != c.end_line:
                continue
            if c.own_line:
                following = []
                ln = c.end_line
                while ln < len(code) and len(following) < 2:
                    ln += 1
                    stripped = code[ln - 1].strip()
                    if not stripped:
                        if following:
                            break
                        continue
                    following.append(stripped)
                snippet = " ".join(following)
            else:
                snippet = code[c.line - 1]
            if snippet and comment_repeats(c.text, snippet):
                self.add("comment-repeats-code", c.line,
                         "comment %r only restates the code next to it" % c.text.strip()[:70])

    def name(self, name, line, kind, returns_value=True):
        """vague-name: kind is "function", "parameter" or "variable"."""
        if (kind, name) in self.seen:
            return
        low = name.lower().lstrip("_$")
        vague = (low in VAGUE_NAMES or NUMBERED_RE.match(low)
                 or (kind == "function" and low in VAGUE_FUNCTIONS)
                 or (low == "result" and not returns_value))
        if vague:
            self.seen.add((kind, name))
            why = " in a function that returns nothing" if low == "result" else ""
            self.add("vague-name", line, "%s name %r is vague%s" % (kind, name, why),
                     symbol=name)

    def bool_name(self, name, line):
        """non-predicate-boolean for a name known to hold a boolean."""
        if ("bool", name) in self.seen or last_word(name) not in BOOL_VAGUE:
            return
        self.seen.add(("bool", name))
        self.add("non-predicate-boolean", line,
                 "boolean %r is not named as a predicate (true means what?)" % name,
                 symbol=name)

    def params(self, name, line, required, total):
        """long-parameter-list: more than 4 required or 8 total parameters."""
        if required > 4 or total > 8:
            self.add("long-parameter-list", line,
                     "%s takes %d parameters (%d required); callers must know too much"
                     % (name, total, required), symbol=name)

    def doc(self, name, line, doc, param_names):
        """impl-in-interface-doc and doc-repeats-name for one interface comment."""
        if not doc:
            return
        impl = IMPL_DOC_RE.search(doc)
        if impl:
            self.add("impl-in-interface-doc", line,
                     "interface comment of %s describes how it works: %r"
                     % (name, impl.group(0)), symbol=name)
        body = [ln for ln in doc.strip().splitlines() if ln.strip()]
        if len(body) != 1:
            return
        words = text_words(body[0]) - {stem(w) for w in GENERIC_DOC_WORDS}
        allowed = set()
        for ident in [name] + list(param_names):
            allowed |= {stem(w) for w in split_words(ident)}
        if words and words <= allowed:
            self.add("doc-repeats-name", line,
                     "interface comment of %s only repeats its name: %r" % (name, body[0][:70]),
                     symbol=name)

    def repeated_handlers(self, handlers):
        """repeated-handler: handlers maps a normalised handler body to its lines."""
        for key, lines in handlers.items():
            if len(lines) >= 3 and key.strip():
                self.add("repeated-handler", lines[0],
                         "the same error handler appears %d times (lines %s)"
                         % (len(lines), ", ".join(str(n) for n in lines[:6])))


# ------------------------------------------------------------------ Python ----

def py_comments(text):
    comments = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type == tokenize.COMMENT:
                line, col = tok.start
                own = not tok.line[:col].strip()
                comments.append(Comment(line, line, tok.string.lstrip("#").strip(), own, col))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass  # unfinished source: keep the comments found so far; ast reports the error
    return comments


def py_docstring_body(body):
    if (body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        return body[1:]
    return body


def py_name_of_call(call):
    f = call.func
    if isinstance(f, ast.Attribute):
        return f.attr
    if isinstance(f, ast.Name):
        return f.id
    return None


def py_is_abstract(stmt):
    if isinstance(stmt, ast.Pass):
        return True
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
        return True
    if isinstance(stmt, ast.Raise):
        return True
    return False


def py_decorators(node):
    names = []
    for d in node.decorator_list:
        while isinstance(d, ast.Call):
            d = d.func
        if isinstance(d, ast.Attribute):
            names.append(d.attr)
        elif isinstance(d, ast.Name):
            names.append(d.id)
    return names


def py_params(node, in_class):
    a = node.args
    positional = [x.arg for x in getattr(a, "posonlyargs", [])] + [x.arg for x in a.args]
    if in_class and positional and positional[0] in ("self", "cls") \
            and "staticmethod" not in py_decorators(node):
        positional = positional[1:]
    kwonly = [x.arg for x in a.kwonlyargs]
    required = max(0, len(positional) - len(a.defaults))
    required += sum(1 for d in a.kw_defaults if d is None)
    ordered = list(positional)
    if a.vararg:
        ordered.append(a.vararg.arg)
    ordered += kwonly
    if a.kwarg:
        ordered.append(a.kwarg.arg)
    return positional, kwonly, required, ordered


def py_pass_through(node, body, ordered):
    if len(body) != 1 or not isinstance(body[0], (ast.Return, ast.Expr)):
        return None
    val = body[0].value
    if isinstance(val, ast.Await):
        val = val.value
    if not isinstance(val, ast.Call):
        return None
    f = val.func
    recv = None
    if isinstance(f, ast.Attribute):
        callee, recv = f.attr, f.value
        if isinstance(recv, ast.Call) and isinstance(recv.func, ast.Name) and recv.func.id == "super":
            return None
    elif isinstance(f, ast.Name):
        callee = f.id
    else:
        return None
    names = []
    for arg in val.args:
        if isinstance(arg, ast.Starred):
            arg = arg.value
        if not isinstance(arg, ast.Name):
            return None
        names.append(arg.id)
    for kw in val.keywords:
        if not isinstance(kw.value, ast.Name) or (kw.arg is not None and kw.arg != kw.value.id):
            return None
        names.append(kw.value.id)
    if names != ordered:
        return None
    if recv is None and (callee == node.name or not related_names(callee, node.name)):
        return None  # recursion, or a shallow wrapper around another function
    if not ordered and (recv is None or callee != node.name):
        return None
    unparse = getattr(ast, "unparse", None)  # Python 3.9+
    return unparse(f) if unparse else callee


def py_accessor(node, body, positional):
    if not re.match(r"^(get|set)_?[A-Za-z]", node.name) or len(body) != 1:
        return False
    st = body[0]
    if not positional and isinstance(st, ast.Return):
        v = st.value
        return (isinstance(v, ast.Attribute) and isinstance(v.value, ast.Name)
                and v.value.id == "self")
    if len(positional) == 1 and isinstance(st, ast.Assign) and len(st.targets) == 1:
        t = st.targets[0]
        return (isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name)
                and t.value.id == "self" and isinstance(st.value, ast.Name)
                and st.value.id == positional[0])
    return False


def py_returns_value(node):
    for sub in ast.walk(node):
        if sub is not node and isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        if isinstance(sub, ast.Return) and sub.value is not None:
            return True
        if isinstance(sub, (ast.Yield, ast.YieldFrom)):
            return True
    return False


def py_tuple_size(annotation):
    if isinstance(annotation, ast.Subscript):
        base = annotation.value
        name = base.id if isinstance(base, ast.Name) else getattr(base, "attr", "")
        if name in ("Tuple", "tuple"):
            sl = annotation.slice
            if hasattr(ast, "Index") and isinstance(sl, getattr(ast, "Index")):
                sl = sl.value
            if isinstance(sl, ast.Tuple):
                return len(sl.elts)
    return 0


def own_nodes(func):
    """Walk a function body without descending into nested functions or classes."""
    stack = list(func.body)
    while stack:
        n = stack.pop()
        yield n
        for child in ast.iter_child_nodes(n):
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                                      ast.Lambda)):
                stack.append(child)


def analyze_python(ctx, src):
    try:
        tree = ast.parse(src.text)
    except (SyntaxError, ValueError):
        ctx.skipped.append(src.path)
        return
    src.comments = py_comments(src.text)
    code_lines = list(src.lines)
    for c in src.comments:
        if c.line <= len(code_lines):
            code_lines[c.line - 1] = code_lines[c.line - 1][:c.col]
    src.code_lines = code_lines
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            child._dc_parent = node
        if isinstance(node, ast.Call):
            name = py_name_of_call(node)
            if name:
                ctx.py_calls[name] += 1
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            ctx.py_defs.add(node.name)

    scan = FileScan(ctx, src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            py_function(scan, node)
        elif isinstance(node, ast.ClassDef):
            parent = getattr(node, "_dc_parent", None)
            doc = ast.get_docstring(node)
            public = not node.name.startswith("_") and isinstance(parent, ast.Module)
            if (public and not doc and not src.is_test
                    and (node.end_lineno or node.lineno) - node.lineno >= 3):
                scan.add("missing-interface-doc", node.lineno,
                        "class %s has no interface comment" % node.name, symbol=node.name)
            scan.doc(node.name, node.lineno, doc, [])
        elif isinstance(node, ast.ExceptHandler):
            py_handler(scan, node)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            is_bool = (isinstance(node.value, ast.Constant) and isinstance(node.value.value, bool)) \
                or (isinstance(node, ast.AnnAssign) and isinstance(node.annotation, ast.Name)
                    and node.annotation.id == "bool")
            for t in targets:
                name = t.id if isinstance(t, ast.Name) else (
                    t.attr if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name)
                    and t.value.id == "self" else None)
                if not name:
                    continue
                if is_bool:
                    scan.bool_name(name, node.lineno)
                if isinstance(t, ast.Name) and name.lower() != "result":
                    scan.name(name, node.lineno, "variable")

    handlers = defaultdict(list)
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            body = node.body
            if len(body) == 1 and (py_is_abstract(body[0]) or isinstance(body[0], ast.Raise)):
                continue
            key = "".join(ast.dump(b, annotate_fields=False) for b in body)
            handlers[key].append(node.lineno)
    scan.repeated_handlers(handlers)
    scan.comments()


def py_handler(scan, node):
    src = scan.src
    body = node.body
    if len(body) != 1 or not (isinstance(body[0], ast.Pass) or (
            isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)
            and body[0].value.value is Ellipsis)):
        return
    last = body[0].end_lineno or body[0].lineno
    if any(node.lineno <= c.line <= last for c in src.comments):
        return
    unparse = getattr(ast, "unparse", None)  # Python 3.9+
    kind = "except" if node.type is None else "except %s" % (
        unparse(node.type) if unparse else "...")
    scan.add("swallowed-error", node.lineno,
            "%s discards the error silently, with no comment saying why" % kind)


def py_function(scan, node):
    ctx, src = scan.ctx, scan.src
    parent = getattr(node, "_dc_parent", None)
    in_class = isinstance(parent, ast.ClassDef)
    positional, kwonly, required, ordered = py_params(node, in_class)
    body = py_docstring_body(node.body)
    decorators = py_decorators(node)
    dunder = node.name.startswith("__") and node.name.endswith("__")
    is_test_fn = node.name.startswith("test") or src.is_test
    returns_value = py_returns_value(node)

    if not is_test_fn or ctx.include_tests:
        scan.params(node.name, node.lineno, required, len(positional) + len(kwonly))

    shallow_done = False
    if not dunder:
        target = py_pass_through(node, body, ordered)
        if target and not is_test_fn:
            scan.add("pass-through-method", node.lineno,
                    "%s only forwards its arguments to %s(...)" % (node.name, target),
                    symbol=node.name)
            shallow_done = True
        elif in_class and py_accessor(node, body, positional):
            scan.add("trivial-accessor", node.lineno,
                    "%s is a plain getter/setter for one field" % node.name, symbol=node.name)
            shallow_done = True
    if (not shallow_done and not dunder and not decorators and not is_test_fn
            and len(body) == 1 and not py_is_abstract(body[0])
            and not isinstance(body[0], (ast.If, ast.For, ast.While, ast.Try, ast.With))):
        seg = ast.get_source_segment(src.text, body[0]) or ""
        if len(seg) <= 100 and "\n" not in seg:
            ctx.shallow.append(("py", node.name, Finding(
                "single-use-shallow", src.path, node.lineno,
                "%s has a one-line body and only one call site" % node.name,
                symbol=node.name)))

    # interface comments
    doc = ast.get_docstring(node)
    module_level = isinstance(parent, ast.Module)
    public_method = in_class and not parent.name.startswith("_") \
        and isinstance(getattr(parent, "_dc_parent", None), ast.Module)
    if (not doc and not node.name.startswith("_") and (module_level or public_method)
            and not is_test_fn and node.name != "main"
            and not {"override", "overload", "setter"} & set(decorators)
            and (node.end_lineno or node.lineno) - node.lineno >= 4):
        scan.add("missing-interface-doc", node.lineno,
                "public function %s has no interface comment" % node.name, symbol=node.name)
    scan.doc(node.name, node.lineno, doc, ordered)

    # names
    scan.name(node.name, node.lineno, "function")
    for a in node.args.args + node.args.kwonlyargs:
        scan.name(a.arg, node.lineno, "parameter")
        if isinstance(a.annotation, ast.Name) and a.annotation.id == "bool":
            scan.bool_name(a.arg, node.lineno)
    for sub in own_nodes(node):
        if isinstance(sub, (ast.Assign, ast.AnnAssign)):
            targets = sub.targets if isinstance(sub, ast.Assign) else [sub.target]
            for t in targets:
                if isinstance(t, ast.Name) and t.id.lower() == "result":
                    scan.name(t.id, sub.lineno, "variable", returns_value)

    # generic containers
    size = py_tuple_size(node.returns) if node.returns is not None else 0
    if size < 3:
        for sub in own_nodes(node):
            if isinstance(sub, ast.Return) and isinstance(sub.value, ast.Tuple) \
                    and len(sub.value.elts) >= 3:
                size = len(sub.value.elts)
                break
    if size >= 3:
        scan.add("generic-container", node.lineno,
                "%s returns a %d-tuple; callers must remember what each position means"
                % (node.name, size), symbol=node.name)

    # pass-through variables (resolved across files later)
    if dunder or is_test_fn or shallow_done:
        return
    for p in ordered:
        loads = [n for n in own_nodes(node) if isinstance(n, ast.Name) and n.id == p]
        if not loads:
            continue
        callees = set()
        for n in loads:
            par = getattr(n, "_dc_parent", None)
            if isinstance(par, ast.Starred):
                par = getattr(par, "_dc_parent", None)
            if isinstance(par, ast.keyword):
                par = getattr(par, "_dc_parent", None)
            if isinstance(par, ast.Call) and par.func is not n and py_name_of_call(par):
                callees.add(py_name_of_call(par))
            else:
                callees = None
                break
        if callees:
            ctx.forwarders[(node.name, p)] = (src, node.lineno, callees)



# ----------------------------------------------------------- C family ----

CHAR_LIT_RE = re.compile(r"'(?:\\.[^'\n]{0,8}|[^'\\\n])'")


def mask_c_like(text, lang):
    """Blank out comments and string contents (newlines kept) and collect comments."""
    out = list(text)
    comments = []
    n = len(text)
    starts = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            starts.append(i + 1)

    def line_of(pos):
        return bisect.bisect_right(starts, pos)

    def blank(a, b):
        for k in range(a, b):
            if out[k] != "\n":
                out[k] = " "

    sq_string = lang in ("js", "ts", "php", "dart")
    triple = lang in ("kotlin", "swift", "java", "scala", "dart", "csharp")
    i = 0
    while i < n:
        c = text[i]
        if text.startswith("//", i) or (lang == "php" and c == "#"):
            j = text.find("\n", i)
            j = n if j < 0 else j
            ln = line_of(i)
            own = not text[starts[ln - 1]:i].strip()
            raw = text[i:j].lstrip("/#!").strip()
            comments.append(Comment(ln, ln, raw, own, i - starts[ln - 1]))
            blank(i, j)
            i = j
            continue
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            ln = line_of(i)
            own = not text[starts[ln - 1]:i].strip()
            body = text[i + 2:j - 2] if j - 2 > i + 2 else ""
            lines = [re.sub(r"^\s*\*+ ?", "", x).strip() for x in body.split("\n")]
            raw = "\n".join(x for x in lines if x)
            comments.append(Comment(ln, line_of(max(i, j - 1)), raw.lstrip("*").strip(),
                                    own, i - starts[ln - 1]))
            blank(i, j)
            i = j
            continue
        if triple and text.startswith('"""', i):
            j = text.find('"""', i + 3)
            j = n if j < 0 else j + 3
            blank(i + 3, max(i + 3, j - 3))
            i = j
            continue
        if c == "`" and lang in ("js", "ts", "go"):
            j = i + 1
            while j < n and text[j] != "`":
                j += 2 if text[j] == "\\" and lang != "go" else 1
            blank(i + 1, min(j, n))
            i = j + 1
            continue
        if c == '"' or (c == "'" and sq_string):
            j = i + 1
            while j < n and text[j] != c and text[j] != "\n":
                j += 2 if text[j] == "\\" else 1
            blank(i + 1, min(j, n))
            i = j + 1
            continue
        if c == "'":
            m = CHAR_LIT_RE.match(text, i)
            if m:
                blank(i + 1, m.end() - 1)
                i = m.end()
                continue
        i += 1
    return "".join(out), comments, starts


KEYWORDS = {
    "if", "for", "while", "switch", "catch", "return", "new", "sizeof", "else", "do",
    "try", "synchronized", "using", "lock", "foreach", "when", "guard", "match", "typeof",
    "function", "super", "this", "elif", "throw", "case", "await", "yield", "delete",
    "assert", "echo", "print", "goto", "defer", "go", "select", "with", "fixed", "unsafe",
    "checked", "unchecked", "nameof", "default", "static_assert", "decltype", "alignof"}
PREFIX_STOP = {"return", "new", "else", "throw", "case", "await", "yield", "goto",
               "delete", "typeof", "sizeof", "echo", "print", "not", "and", "or", "in"}

FUNC_PATTERNS = {
    "kotlin": [r"\bfun\s+(?:<[^>]*>\s*)?(?:[\w.]+\.)?(?P<name>\w+)\s*\("],
    "swift": [r"\bfunc\s+(?P<name>\w+)\s*(?:<[^>]*>)?\s*\("],
    "go": [r"\bfunc\s+(?:\([^)]*\)\s*)?(?P<name>\w+)\s*(?:\[[^\]]*\])?\s*\("],
    "rust": [r"\bfn\s+(?P<name>\w+)\s*(?:<[^>]*>)?\s*\("],
    "scala": [r"\bdef\s+(?P<name>\w+)\s*(?:\[[^\]]*\])?\s*\("],
    "php": [r"\bfunction\s+&?(?P<name>\w+)\s*\("],
    "js": [r"\bfunction\s*\*?\s*(?P<name>[\w$]+)\s*(?:<[^<>()]*>)?\s*\(",
           r"^[ \t]*(?:(?:public|private|protected|static|async|override|readonly|abstract|"
           r"get|set)\s+)*\*?\s*(?P<name>[A-Za-z_$][\w$]*)\s*(?:<[^<>()]*>)?\s*\(",
           r"\b(?:const|let|var)\s+(?P<name>[\w$]+)\s*(?::[^=;]+)?=\s*(?:async\s*)?\("],
    "java": [r"^[ \t]*(?P<prefix>(?:[\w$<>\[\],.?*&:@~]+[ \t]+)+)(?:[\w]+::)*"
             r"(?P<name>[A-Za-z_$~][\w$]*)\s*\("],
}
FUNC_PATTERNS["ts"] = FUNC_PATTERNS["js"]
for _lang in ("csharp", "c", "cpp", "dart"):
    FUNC_PATTERNS[_lang] = FUNC_PATTERNS["java"]
FUNC_RES = {k: [re.compile(p, re.M) for p in v] for k, v in FUNC_PATTERNS.items()}

TYPE_DECL_RE = {
    "default": re.compile(
        r"^[ \t]*(?P<mods>(?:(?:public|export|abstract|final|sealed|open|data|internal|static|"
        r"partial|default|private|protected|pub(?:\([^)]*\))?|inline|value|enum)\s+)*)"
        r"(?:class|interface|struct|enum|record|trait|object|protocol)\s+(?P<name>\w+)", re.M),
    "go": re.compile(r"^type\s+(?P<name>\w+)\s+(?:struct|interface)\b", re.M),
}


def match_close(masked, open_idx, op, cl):
    depth = 0
    for k in range(open_idx, len(masked)):
        ch = masked[k]
        if ch == op:
            depth += 1
        elif ch == cl:
            depth -= 1
            if depth == 0:
                return k
    return -1


def split_top(s, seps=","):
    parts, depth, cur = [], 0, []
    for ch in s:
        if ch in "([{<":
            depth += 1
        elif ch in ")]}>":
            depth = max(0, depth - 1)
        if ch in seps and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return [p.strip() for p in parts if p.strip()]


def c_param_name(p, lang):
    p = re.sub(r"@\w+(?:\([^)]*\))?\s*", "", p).strip()
    has_default = False
    depth = 0
    for k, ch in enumerate(p):
        if ch in "([{<":
            depth += 1
        elif ch in ")]}>":
            depth -= 1
        elif ch == "=" and depth == 0 and p[k:k + 2] != "=>":
            p, has_default = p[:k].strip(), True
            break
    if lang in ("ts", "js") and "?" in p.split(":")[0]:
        has_default = True
    if lang == "php":
        m = re.findall(r"\$(\w+)", p)
        return (m[-1] if m else None), has_default
    if ":" in p and lang not in ("c", "cpp", "java", "csharp", "go"):
        toks = IDENT_RE.findall(p.split(":")[0])
        name = toks[-1] if toks else None
    elif lang == "go":
        toks = IDENT_RE.findall(p)
        name = toks[0] if toks else None
    else:
        toks = IDENT_RE.findall(p)
        name = toks[-1] if toks else None
    if name in ("self", "this", "void", "mut"):
        return None, has_default
    return name, has_default


def c_functions(masked, starts, lang):
    seen = set()
    for rx in FUNC_RES.get(lang, []):
        for m in rx.finditer(masked):
            name = m.group("name")
            if name in KEYWORDS:
                continue
            prefix = m.groupdict().get("prefix") or ""
            if set(prefix.split()) & PREFIX_STOP:
                continue
            open_idx = m.end() - 1
            if open_idx in seen:
                continue
            close = match_close(masked, open_idx, "(", ")")
            if close < 0:
                continue
            k, depth = close + 1, 0
            body_open = -1
            while k < len(masked) and k - close < 300:
                ch = masked[k]
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                elif depth == 0 and ch == "{":
                    body_open = k
                    break
                elif depth == 0 and (ch in ";}" or (ch == "=" and masked[k:k + 2] != "=>")):
                    break
                k += 1
            if body_open < 0:
                continue
            tail = masked[close + 1:body_open]
            body_close = match_close(masked, body_open, "{", "}")
            if body_close < 0:
                continue
            seen.add(open_idx)
            line_start = starts[bisect.bisect_right(starts, m.start()) - 1]
            yield {
                "name": name,
                "params": masked[open_idx + 1:close],
                "sig": masked[line_start:body_open],
                "line": bisect.bisect_right(starts, m.start("name")),
                "body": masked[body_open + 1:body_close],
                "end_line": bisect.bisect_right(starts, body_close),
                "tail": tail,
            }


def c_statements(body):
    return [s.strip() for s in split_top(body, ";\n") if s.strip()]


CALL_STMT_RE = re.compile(
    r"^(?:return\s+)?(?:await\s+)?(?:try\s+)?(?P<recv>(?:[\w$]+(?:\(\))?\s*(?:\.|->|::|\?\.)\s*)*)"
    r"(?P<callee>[\w$]+)\s*\((?P<args>.*)\)\s*;?$", re.S)


def c_pass_through(fn, pnames):
    stmts = c_statements(fn["body"])
    if len(stmts) != 1:
        return None
    m = CALL_STMT_RE.match(stmts[0])
    if not m:
        return None
    recv, callee = m.group("recv").strip(), m.group("callee")
    if re.match(r"^(super|base|parent)\b", recv):
        return None
    if callee in KEYWORDS:
        return None
    args = []
    for a in split_top(m.group("args")):
        a = re.sub(r"^(?:\.\.\.|\*\*?|&|ref\s+|out\s+|in\s+)", "", a).strip()
        a = re.sub(r"\.\.\.$", "", a)
        if ":" in a:
            a = a.split(":", 1)[1].strip()
        elif re.match(r"^\w+\s*=\s*\w+$", a):
            a = a.split("=", 1)[1].strip()
        a = a.lstrip("$")
        if not re.match(r"^[A-Za-z_]\w*$", a):
            return None
        args.append(a)
    if args != pnames:
        return None
    if not recv and (callee == fn["name"] or not related_names(callee, fn["name"])):
        return None
    if not pnames and (not recv or callee != fn["name"]):
        return None
    return recv + callee


def c_is_private(fn, lang):
    sig = fn["sig"]
    if lang == "go":
        return fn["name"][:1].islower()
    if lang == "rust":
        return not re.search(r"\bpub\b", sig)
    if lang in ("c", "cpp"):
        return bool(re.search(r"\bstatic\b", sig))
    if lang == "dart":
        return fn["name"].startswith("_")
    return bool(re.search(r"\bprivate\b", sig)) or fn["name"].startswith("#")


def c_is_public(name, sig, lang, path):
    if lang in ("java", "csharp", "swift", "php"):
        return bool(re.search(r"\b(public|open)\b", sig)) or (
            lang == "php" and not re.search(r"\b(private|protected)\b", sig))
    if lang in ("kotlin", "scala"):
        return not re.search(r"\b(private|protected|internal|override)\b", sig)
    if lang in ("js", "ts"):
        return bool(re.search(r"\bexport\b", sig))
    if lang == "go":
        return name[:1].isupper()
    if lang == "rust":
        return bool(re.search(r"\bpub\b", sig))
    if lang == "dart":
        return not name.startswith("_")
    return path.endswith((".h", ".hpp", ".hh")) and not re.search(r"\bstatic\b", sig)


def doc_before(src, line, comment_by_end):
    ln = line - 1
    while ln >= 1 and re.match(r"^\s*(@|\[|#\[)", src.lines[ln - 1]):
        ln -= 1
    c = comment_by_end.get(ln)
    return c.text if c else None


def clean_doc(text):
    keep = [ln for ln in text.splitlines() if not re.match(r"^\s*[@\\]\w+", ln)]
    return "\n".join(keep).strip()


DECL_RES = {
    "js": re.compile(r"\b(?:let|const|var)\s+([A-Za-z_$][\w$]*)\s*(?::\s*(\w+))?\s*(=\s*(\w+))?"),
    "kotlin": re.compile(r"\b(?:val|var)\s+(\w+)\s*(?::\s*(\w+))?\s*(=\s*(\w+))?"),
    "swift": re.compile(r"\b(?:let|var)\s+(\w+)\s*(?::\s*(\w+))?\s*(=\s*(\w+))?"),
    "rust": re.compile(r"\blet\s+(?:mut\s+)?(\w+)\s*(?::\s*(\w+))?\s*(=\s*(\w+))?"),
    "go": re.compile(r"\b(\w+)\s*(?::=|\bvar\b)()\s*((\w+))?"),
    "java": re.compile(
        r"\b(int|long|short|byte|char|float|double|bool|boolean|Boolean|String|string|var|"
        r"auto|Object|object|dynamic|final)\s+([A-Za-z_]\w*)\s*(=\s*(\w+)|;)"),
}
DECL_RES["ts"] = DECL_RES["js"]
DECL_RES["scala"] = DECL_RES["kotlin"]
for _lang in ("csharp", "c", "cpp", "dart", "php"):
    DECL_RES[_lang] = DECL_RES["java"]
BOOL_TYPES = {"bool", "boolean", "Boolean", "Bool"}


def analyze_c_like(ctx, src):
    masked, comments, starts = mask_c_like(src.text, src.lang)
    src.comments = comments
    src.code_lines = masked.split("\n")
    lang = src.lang
    for m in re.finditer(r"\b([A-Za-z_]\w*)\s*\(", masked):
        ctx.c_calls[m.group(1)] += 1
    comment_by_end = {c.end_line: c for c in comments if c.own_line}
    scan = FileScan(ctx, src)

    for fn in c_functions(masked, starts, lang):
        ctx.c_defs[fn["name"]] += 1
        params = []
        required = 0
        for p in split_top(fn["params"]):
            name, has_default = c_param_name(p, lang)
            if name:
                params.append(name)
                required += 0 if has_default else 1
        is_test_fn = src.is_test or fn["name"].lower().startswith("test")
        if not is_test_fn or ctx.include_tests:
            scan.params(fn["name"], fn["line"], required, len(params))
        target = None if is_test_fn else c_pass_through(fn, params)
        stmts = c_statements(fn["body"])
        accessor = False
        if target:
            scan.add("pass-through-method", fn["line"],
                    "%s only forwards its arguments to %s(...)" % (fn["name"], target),
                    symbol=fn["name"])
        elif re.match(r"^(get|set)[A-Z_]", fn["name"]) and len(stmts) == 1:
            s = stmts[0].rstrip(";").strip()
            getter = not params and re.match(r"^return\s+(?:this\.|self\.|\$this->)?[\w$]+$", s)
            setter = len(params) == 1 and re.match(
                r"^(?:this\.|self\.|\$this->)?[\w$]+\s*=\s*\$?%s$" % re.escape(params[0]), s)
            if getter or setter:
                accessor = True
                scan.add("trivial-accessor", fn["line"],
                        "%s is a plain getter/setter for one field" % fn["name"],
                        symbol=fn["name"])
        if (not target and not accessor and not is_test_fn and len(stmts) == 1
                and len(stmts[0]) <= 100 and c_is_private(fn, lang)
                and not re.search(r"@Override|\boverride\b", fn["sig"])
                and not re.match(r"^(if|for|while|switch|try|throw|return\s*;?$)\b", stmts[0])):
            ctx.shallow.append(("c", fn["name"], Finding(
                "single-use-shallow", src.path, fn["line"],
                "%s has a one-line body and only one call site" % fn["name"],
                symbol=fn["name"])))

        doc = doc_before(src, fn["line"], comment_by_end)
        if (doc is None and not is_test_fn and fn["end_line"] - fn["line"] >= 4
                and fn["name"] != "main" and c_is_public(fn["name"], fn["sig"], lang, src.path)):
            scan.add("missing-interface-doc", fn["line"],
                    "public function %s has no interface comment" % fn["name"],
                    symbol=fn["name"])
        if doc:
            scan.doc(fn["name"], fn["line"], clean_doc(doc), params)
        scan.name(fn["name"], fn["line"], "function")
        for p in params:
            scan.name(p, fn["line"], "parameter")
        ret_sig = fn["sig"] + " " + fn["tail"]
        if (re.search(r"\b(?:Pair|Triple|Tuple|Map\.Entry|SimpleEntry|std::pair|std::tuple)\s*<", ret_sig)
                or re.search(r"->\s*\((?:[^(),]+,){2,}[^()]*\)", fn["tail"])
                or re.search(r"\)\s*:\s*\[(?:[^\[\],]+,){2,}[^\[\]]*\]\s*$", "(" + fn["tail"].strip())
                or re.search(r"\breturn\s+(?:new\s+)?(?:Pair|Triple|Tuple|AbstractMap\.SimpleEntry)\b"
                             r"|\breturn\s+(?:std::)?make_(?:pair|tuple)\b|\breturn\s+Tuple\.Create\b",
                             fn["body"])):
            scan.add("generic-container", fn["line"],
                    "%s returns a generic pair/tuple; callers must remember what each part means"
                    % fn["name"], symbol=fn["name"])

    for rx in (TYPE_DECL_RE["go"] if lang == "go" else TYPE_DECL_RE["default"],):
        for m in rx.finditer(masked):
            line = bisect.bisect_right(starts, m.start("name"))
            sig = src.code_lines[line - 1]
            if src.is_test or not c_is_public(m.group("name"), sig, lang, src.path):
                continue
            doc = doc_before(src, line, comment_by_end)
            if doc is None:
                scan.add("missing-interface-doc", line,
                        "public type %s has no interface comment" % m.group("name"),
                        symbol=m.group("name"))
            else:
                scan.doc(m.group("name"), line, clean_doc(doc), [])

    decl = DECL_RES.get(lang)
    if decl:
        for m in decl.finditer(masked):
            if lang in ("java", "csharp", "c", "cpp", "dart", "php"):
                typ, name, init = m.group(1), m.group(2), m.group(4) or ""
            else:
                name, typ, init = m.group(1), m.group(2) or "", m.group(4) or ""
            line = bisect.bisect_right(starts, m.start())
            if name in KEYWORDS:
                continue
            scan.name(name, line, "variable")
            if typ in BOOL_TYPES or init in ("true", "false"):
                scan.bool_name(name, line)

    c_handlers(scan, masked, starts)
    scan.comments()


HANDLER_RES = [
    re.compile(r"\bcatch\b\s*(?:\((?:[^()]|\([^()]*\))*\))?\s*\{"),
    re.compile(r"\bif\s+err\s*!=\s*nil\s*\{"),
    re.compile(r"\.catch\(\s*(?:\(\s*[\w$]*\s*(?::\s*\w+)?\s*\)|[\w$]+)?\s*=>\s*\{"),
]


def c_handlers(scan, masked, starts):
    src = scan.src
    bodies = defaultdict(list)
    for rx in HANDLER_RES:
        for m in rx.finditer(masked):
            open_idx = m.end() - 1
            close = match_close(masked, open_idx, "{", "}")
            if close < 0:
                continue
            line = bisect.bisect_right(starts, m.start())
            end_line = bisect.bisect_right(starts, close)
            body = " ".join(masked[open_idx + 1:close].split())
            if not body:
                if not any(line <= c.line <= end_line for c in src.comments):
                    scan.add("swallowed-error", line,
                            "error handler is empty and has no comment saying why")
            elif not re.match(r"^(throw|return err|panic)\b[^;]*;?$", body):
                bodies[body].append(line)
    scan.repeated_handlers(bodies)


# ------------------------------------------------------ duplicate code ----

DUP_SKIP_RE = re.compile(
    r"^(?:[{}()\[\];,]+|else:?|try:?|finally:?|\}\s*else\s*\{|end|pass|break;?|continue;?|"
    r"return;?|import\b.*|from\s+\S+\s+import\b.*|package\b.*|using\b.*|#include\b.*|"
    r"@\w+.*|\"\"\"|'''|\*/|/\*\*?)$")
DUP_WINDOW = 6
DUP_MIN_CHARS = 140


def find_duplicates(ctx):
    seen = {}
    marks = defaultdict(dict)  # path -> {window_index: (first_path, first_line, last_line)}
    meaningful = {}
    for src in ctx.files:
        if src.is_test and not ctx.include_tests:
            continue
        rows = []
        for i, line in enumerate(src.code_lines):
            norm = " ".join(line.split())
            if norm and not DUP_SKIP_RE.match(norm):
                rows.append((i + 1, norm))
        meaningful[src.path] = rows
        for w in range(len(rows) - DUP_WINDOW + 1):
            chunk = rows[w:w + DUP_WINDOW]
            text = "\n".join(r[1] for r in chunk)
            if len(text) < DUP_MIN_CHARS:
                continue
            first = seen.get(text)
            if first is None:
                seen[text] = (src.path, w, chunk[0][0], chunk[-1][0])
            elif first[0] != src.path or w - first[1] >= DUP_WINDOW:
                marks[src.path][w] = (first[0], first[2], first[3])
    by_path = {s.path: s for s in ctx.files}
    for path, windows in marks.items():
        rows = meaningful[path]
        idx = sorted(windows)
        region = [idx[0], idx[0]]
        regions = []
        for w in idx[1:]:
            if w <= region[1] + DUP_WINDOW:
                region[1] = w
            else:
                regions.append(tuple(region))
                region = [w, w]
        regions.append(tuple(region))
        for a, b in regions:
            first_line = rows[a][0]
            last_line = rows[min(b + DUP_WINDOW - 1, len(rows) - 1)][0]
            rel = windows[a]
            rel_end = windows[b][2]
            src = by_path[path]
            ctx.add(src, "duplicate-code", first_line,
                    "lines %d-%d repeat code at %s:%d" % (first_line, last_line,
                                                         display(rel[0]), rel[1]),
                    end_line=last_line, symbol="dup:%d" % (last_line - first_line),
                    related=(rel[0], rel[1], rel_end))


# ---------------------------------------------------------------- driver ----

def display(path):
    try:
        rel = os.path.relpath(path)
    except ValueError:
        rel = path
    return rel.replace(os.sep, "/")


def discover(paths):
    files = []
    for p in paths:
        if os.path.isfile(p):
            files.append(os.path.abspath(p))
            continue
        for root, dirs, names in os.walk(p):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
            for name in sorted(names):
                ext = os.path.splitext(name)[1].lower()
                if ext in PY_EXT or ext in C_EXT:
                    if name.endswith((".min.js", ".d.ts", ".pb.go", "_pb2.py", ".g.dart")):
                        continue
                    files.append(os.path.abspath(os.path.join(root, name)))
    return files


def load(path):
    ext = os.path.splitext(path)[1].lower()
    lang = "python" if ext in PY_EXT else C_EXT.get(ext)
    if not lang:
        return None
    try:
        if os.path.getsize(path) > MAX_FILE_BYTES:
            return None
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return None
    return SourceFile(path, text.replace("\r\n", "\n"), lang)


def git(args, cwd):
    proc = subprocess.run(["git"] + args, cwd=cwd, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, universal_newlines=True,
                          encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "git %s failed" % " ".join(args))
    return proc.stdout


def changed_lines(ref, staged):
    """Map of absolute path -> set of added/changed line numbers (None = whole file)."""
    top = git(["rev-parse", "--show-toplevel"], os.getcwd()).strip()
    args = ["diff", "-U0", "--no-color", "--no-ext-diff", "--diff-filter=AMR"]
    args += ["--cached"] if staged else [ref]
    out = git(args + ["--"], top)
    result = {}
    current = None
    for line in out.splitlines():
        if line.startswith("+++ "):
            name = line[4:].strip()
            current = None if name == "/dev/null" else os.path.normcase(
                os.path.abspath(os.path.join(top, name[2:] if name.startswith("b/") else name)))
            if current:
                result.setdefault(current, set())
        elif line.startswith("@@") and current:
            m = re.search(r"\+(\d+)(?:,(\d+))?", line)
            start, count = int(m.group(1)), int(m.group(2) or 1)
            result[current].update(range(start, start + count))
    if not staged:
        for name in git(["ls-files", "--others", "--exclude-standard"], top).splitlines():
            result[os.path.normcase(os.path.abspath(os.path.join(top, name)))] = None
    return result


def touches(changed, path, first, last):
    key = os.path.normcase(path)
    if key not in changed:
        return False
    lines = changed[key]
    return lines is None or any(first <= n <= last for n in lines)


def fingerprint(f, lines_of):
    symbol = f.symbol
    if not symbol:
        lines = lines_of.get(f.path) or []
        symbol = " ".join(lines[f.line - 1].split()) if 0 < f.line <= len(lines) else ""
    return "%s|%s|%s" % (f.rule, display(f.path), symbol)


def run(paths, include_tests=False):
    ctx = Context(include_tests)
    for path in discover(paths):
        src = load(path)
        if src is None:
            continue
        ctx.files.append(src)
        if src.lang == "python":
            analyze_python(ctx, src)
        else:
            analyze_c_like(ctx, src)
    by_path = {s.path: s for s in ctx.files}
    for family, name, finding in ctx.shallow:
        calls = ctx.py_calls[name] if family == "py" else ctx.c_calls[name] - ctx.c_defs[name]
        src = by_path[finding.path]
        if calls == 1 and not src.ignored(finding.line, finding.rule):
            ctx.findings.append(finding)
    # A parameter is passed through when a function only hands it to other
    # functions of this code base, and at least two such layers are chained.
    layers = {key: val for key, val in ctx.forwarders.items()
              if val[2] <= ctx.py_defs and key[0] not in val[2]}
    for (func, p), (src, line, callees) in sorted(layers.items(), key=lambda kv: kv[1][1]):
        down = sorted(g for g in callees if (g, p) in layers)
        up = sorted(h for (h, q), v in layers.items() if q == p and func in v[2])
        if down or up:
            chain = " -> ".join(up[:1] + [func] + (down[:1] or sorted(callees)[:1]))
            ctx.add(src, "pass-through-variable", line,
                    "%s never uses %r; it only passes it on (%s)" % (func, p, chain),
                    symbol="%s:%s" % (func, p))
    find_duplicates(ctx)
    ctx.findings.sort(key=lambda f: (display(f.path), f.line, f.rule))
    return ctx


def list_rules():
    width = max(len(k) for k in RULES)
    for rule_id, r in RULES.items():
        print("%-*s  %-7s  %s (%s)" % (width, rule_id, r.severity, r.red_flag, r.chapter))
        print("%-*s           fix: %s" % (width, "", r.fix))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="Rules: run with --list-rules.")
    ap.add_argument("paths", nargs="*", default=None)
    ap.add_argument("--diff", nargs="?", const="HEAD", default=None, metavar="REF")
    ap.add_argument("--staged", action="store_true")
    ap.add_argument("--format", choices=("text", "json"), default="text")
    ap.add_argument("--fail-on", choices=("warning", "info", "never"), default="warning")
    ap.add_argument("--select", default="")
    ap.add_argument("--ignore", default="")
    ap.add_argument("--baseline")
    ap.add_argument("--write-baseline")
    ap.add_argument("--include-tests", action="store_true")
    ap.add_argument("--list-rules", action="store_true")
    args = ap.parse_args(argv)

    if args.list_rules:
        list_rules()
        return 0
    select = {r.strip() for r in args.select.split(",") if r.strip()}
    ignore = {r.strip() for r in args.ignore.split(",") if r.strip()}
    unknown = (select | ignore) - set(RULES)
    if unknown:
        print("unknown rule id(s): %s (see --list-rules)" % ", ".join(sorted(unknown)),
              file=sys.stderr)
        return 2

    changed = None
    paths = args.paths or ["."]
    if args.diff is not None or args.staged:
        try:
            changed = changed_lines(args.diff or "HEAD", args.staged)
        except (RuntimeError, OSError) as exc:
            print("design_check: git error: %s" % exc, file=sys.stderr)
            return 2
        if not args.paths:
            paths = [git(["rev-parse", "--show-toplevel"], os.getcwd()).strip()]

    ctx = run(paths, args.include_tests)
    findings = [f for f in ctx.findings
                if (not select or f.rule in select) and f.rule not in ignore]
    if changed is not None:
        findings = [f for f in findings
                    if touches(changed, f.path, f.line, f.end_line)
                    or (f.related and touches(changed, f.related[0], f.related[1], f.related[2]))]
    lines_of = {s.path: s.lines for s in ctx.files}

    if args.write_baseline:
        prints = sorted({fingerprint(f, lines_of) for f in findings})
        with open(args.write_baseline, "w", encoding="utf-8") as fh:
            json.dump({"version": 1, "fingerprints": prints}, fh, indent=1)
            fh.write("\n")
        print("wrote %d fingerprints to %s" % (len(prints), args.write_baseline))
        return 0
    if args.baseline:
        try:
            with open(args.baseline, encoding="utf-8") as fh:
                known = set(json.load(fh).get("fingerprints", []))
        except (OSError, ValueError) as exc:
            print("design_check: cannot read baseline: %s" % exc, file=sys.stderr)
            return 2
        findings = [f for f in findings if fingerprint(f, lines_of) not in known]

    counts = Counter(f.severity for f in findings)
    if args.format == "json":
        print(json.dumps({
            "findings": [f.to_dict(display) for f in findings],
            "summary": {"files": len(ctx.files), "warning": counts["warning"],
                        "info": counts["info"], "skipped": [display(p) for p in ctx.skipped]},
        }, indent=2))
    else:
        for f in findings:
            r = RULES[f.rule]
            print("%s:%d: %s %s [%s, %s]" % (display(f.path), f.line, f.severity, f.rule,
                                             r.red_flag, r.chapter))
            print("    %s" % f.message)
            print("    fix: %s" % r.fix)
        scope = " in changed lines" if changed is not None else ""
        print("\n%d warning(s), %d info%s; %d file(s) scanned." % (
            counts["warning"], counts["info"], scope, len(ctx.files)))
        if ctx.skipped:
            print("skipped (could not parse): %s" % ", ".join(display(p) for p in ctx.skipped))
        if findings:
            print("Fix each finding, or justify it with a comment: "
                  "design-check: ignore[<rule>] -- <reason>")
    if args.fail_on == "never":
        return 0
    threshold = SEVERITY_RANK[args.fail_on]
    return 1 if any(SEVERITY_RANK[f.severity] >= threshold for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
