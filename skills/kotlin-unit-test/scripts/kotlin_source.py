#!/usr/bin/env python3
"""Light-weight Kotlin source scanner (Python 3.8+, standard library only).

It finds packages, imports, classes/objects/interfaces, functions (members, companion members, top-level and
extension functions), their modifiers, annotations, line ranges and bodies, plus JUnit-style test functions and
Kotest test cases. It is not a compiler: it works on the text with comments and string contents masked out, which
is enough to map tests to classes and methods and to check test bodies.
"""

import bisect
import re
from pathlib import Path

CHAR_RE = re.compile(r"'(?:\\u[0-9a-fA-F]{4}|\\.|[^'\\\n])'")
MODIFIERS = {"public", "private", "internal", "protected", "open", "abstract", "sealed", "data", "enum", "annotation",
             "inner", "value", "inline", "expect", "actual", "final", "override", "suspend", "operator", "infix",
             "tailrec", "external", "companion", "lateinit", "const", "noinline", "crossinline", "reified"}
TEST_ANNOTATIONS = {"Test", "ParameterizedTest", "RepeatedTest", "TestFactory", "TestTemplate"}
DISABLED_ANNOTATIONS = {"Disabled", "Ignore", "Ignored"}
KOTEST_SPECS = {"StringSpec", "FunSpec", "ShouldSpec", "DescribeSpec", "BehaviorSpec", "WordSpec", "FreeSpec",
                "FeatureSpec", "ExpectSpec", "AnnotationSpec"}

CLASS_RE = re.compile(r"\b(?P<kind>class|interface|object)\b(?:\s+(?P<name>[A-Za-z_]\w*|`[^`]+`))?")
FUN_RE = re.compile(r"\bfun\b(?:\s*<(?:[^<>{}()=]|<[^<>{}()=]*>)*>)?\s*"
                    r"(?:(?P<recv>[\w.?*]+(?:<(?:[^<>{}()=]|<[^<>{}()=]*>)*>)?\??)\s*\.\s*)?"
                    r"(?P<name>[A-Za-z_]\w*|`[^`]+`)\s*\(")
ANNOTATION_RE = re.compile(r"@(?:\w+:)?([A-Za-z_][\w.]*)(\s*\((?:[^()]|\([^()]*\))*\))?")
KOTEST_CALL_RE = re.compile(r"\b(?P<fn>x?test|x?should|x?it|x?scenario|[Tt]hen|xthen)\s*\(\s*\"")
KOTEST_STRING_RE = re.compile(r"(?m)^[ \t]*(?P<x>!?)\"[^\"\n]*\"\s*(?:\.config\((?:[^()]|\([^()]*\))*\)\s*)?\{")


# ------------------------------------------------------------------------------------------------ masking

def _skip_string(src, i):
    """Index just after the string literal starting at src[i] ('"' or '\"\"\"')."""
    n = len(src)
    if src.startswith('"""', i):
        j = i + 3
        while j < n:
            if src.startswith('"""', j):
                j += 3
                while j < n and src[j] == '"':
                    j += 1
                return j
            if src.startswith("${", j):
                j = _skip_template(src, j)
                continue
            j += 1
        return n
    j = i + 1
    while j < n:
        c = src[j]
        if c == "\\":
            j += 2
            continue
        if c == '"':
            return j + 1
        if c == "\n":
            return j
        if src.startswith("${", j):
            j = _skip_template(src, j)
            continue
        j += 1
    return n


def _skip_template(src, j):
    """src[j:j+2] == '${'; index just after the matching '}'."""
    depth, k, n = 0, j + 1, len(src)
    while k < n:
        c = src[k]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return k + 1
        elif c == '"':
            k = _skip_string(src, k)
            continue
        elif c == "'":
            m = CHAR_RE.match(src, k)
            if m:
                k = m.end()
                continue
        elif src.startswith("//", k):
            e = src.find("\n", k)
            k = n if e < 0 else e
            continue
        elif src.startswith("/*", k):
            e = src.find("*/", k + 2)
            k = n if e < 0 else e + 2
            continue
        k += 1
    return n


def mask(src):
    """Same-length copy of src with comments and the contents of strings/char literals replaced by spaces
    (newlines and the quote characters are kept, so offsets and line numbers stay valid)."""
    out = list(src)
    n = len(src)

    def blank(a, b):
        for k in range(a, min(b, n)):
            if out[k] != "\n":
                out[k] = " "

    i = 0
    while i < n:
        c = src[i]
        if c == "/" and src.startswith("//", i):
            j = src.find("\n", i)
            j = n if j < 0 else j
            blank(i, j)
            i = j
        elif c == "/" and src.startswith("/*", i):
            depth, j = 1, i + 2
            while j < n and depth:
                if src.startswith("/*", j):
                    depth, j = depth + 1, j + 2
                elif src.startswith("*/", j):
                    depth, j = depth - 1, j + 2
                else:
                    j += 1
            blank(i, j)
            i = j
        elif c == '"':
            j = _skip_string(src, i)
            q = 3 if src.startswith('"""', i) else 1
            blank(i + q, j - q if j - q > i + q else j)
            i = j
        elif c == "'":
            m = CHAR_RE.match(src, i)
            if m:
                blank(m.start() + 1, m.end() - 1)
                i = m.end()
            else:
                i += 1
        else:
            i += 1
    return "".join(out)


# ------------------------------------------------------------------------------------------------ helpers

def brace_pairs(m):
    pairs, stack = {}, []
    for i, c in enumerate(m):
        if c == "{":
            stack.append(i)
        elif c == "}" and stack:
            pairs[stack.pop()] = i
    return pairs


def match_paren(m, i, open_c="(", close_c=")"):
    depth = 0
    for j in range(i, len(m)):
        if m[j] == open_c:
            depth += 1
        elif m[j] == close_c:
            depth -= 1
            if depth == 0:
                return j
    return len(m) - 1


def _next_text(m, j):
    k = j
    while k < len(m) and m[k] in " \t\r\n":
        k += 1
    return m[k:k + 6]


CONTINUATION_START = (".", "?.", "?:", "&&", "||", "+", "-", "*", "/", "%", ":", "as ", "as?", "?", "=", ")", "]")


def expr_end(m, i):
    """End offset of an expression body starting at i (after '=')."""
    depth, n, j = 0, len(m), i
    while j < n:
        c = m[j]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            if depth == 0:
                return j
            depth -= 1
        elif c == ";" and depth == 0:
            return j
        elif c == "\n" and depth == 0:
            prev = m[i:j].rstrip()
            nxt = _next_text(m, j)
            if not prev or prev[-1] in "=+-*/%&|.,(?:<>!" or nxt.startswith(CONTINUATION_START):
                j += 1
                continue
            return j
        j += 1
    return n


def tokens(name):
    """'calculateTotal_whenEmpty returns 0' -> ['calculate', 'total', 'when', 'empty', 'returns', '0']"""
    name = name.strip("`")
    parts = re.findall(r"[A-Z]+(?=[A-Z][a-z]|\d|\b)|[A-Z]?[a-z]+|[A-Z]+|\d+", name)
    return [p.lower() for p in parts]


class Code:
    """Raw text, masked text and a line index for one file."""

    def __init__(self, text):
        self.raw = text
        self.m = mask(text)
        self.nl = [i for i, c in enumerate(text) if c == "\n"]
        self.pairs = brace_pairs(self.m)

    def line(self, pos):
        return bisect.bisect_left(self.nl, pos) + 1

    def line_start(self, pos):
        return self.m.rfind("\n", 0, pos) + 1


# ------------------------------------------------------------------------------------------------ parsing

def _prefix(code, pos):
    """Annotations (raw text) and modifier words written before a declaration starting at pos."""
    ls = code.line_start(pos)
    cut = max(code.m.rfind(ch, ls, pos) for ch in "{};")
    same_line_only = cut >= 0
    if same_line_only:
        ls = cut + 1
    raw_parts = [code.raw[ls:pos]]
    mods_text = code.m[ls:pos]
    balance = 0
    end = -1 if same_line_only else ls - 1
    while end > 0:
        start = code.m.rfind("\n", 0, end) + 1
        mline = code.m[start:end].strip()
        if not mline:
            break
        if mline.startswith("@") or balance < 0:
            balance += mline.count("(") - mline.count(")")
            raw_parts.insert(0, code.raw[start:end])
            end = start - 1
            continue
        break
    raw = "\n".join(raw_parts)
    annotations = []
    for a in ANNOTATION_RE.finditer(raw):
        annotations.append({"name": a.group(1).split(".")[-1], "args": (a.group(2) or "").strip()})
    words = set(re.findall(r"\b[a-z]+\b", ANNOTATION_RE.sub(" ", mods_text)))
    return annotations, words & MODIFIERS


def _class_header_end(code, start):
    """From the end of 'class Name', return (body_open or None, header_end)."""
    m, n = code.m, len(code.m)
    depth, angle, j = 0, 0, start
    while j < n:
        c = m[j]
        if c == "(":
            j = match_paren(m, j) + 1
            continue
        if c == "<" and depth == 0:
            angle += 1
        elif c == ">" and angle and m[j - 1] != "-":
            angle -= 1
        elif c == "{" and angle == 0:
            return j, j
        elif c in ";}" and angle == 0:
            return None, j
        elif c == "\n" and angle == 0:
            prev = m[start:j].rstrip()
            nxt = _next_text(m, j)
            if (prev and prev[-1] in ":,(") or nxt.startswith((":", ",", "(", "{", "where", "const", "@", "privat",
                                                                  "intern", "protec", "public")):
                j += 1
                continue
            return None, j
        j += 1
    return None, n


def _fun_body(code, close_paren):
    """After the parameter list: (body_kind, body_start, body_end) with kind 'block', 'expr' or None."""
    m, n = code.m, len(code.m)
    j = close_paren + 1
    depth = 0
    while j < n:
        c = m[j]
        if c == "(":
            j = match_paren(m, j) + 1
            continue
        if c == "{" and depth == 0:
            return "block", j, code.pairs.get(j, n - 1)
        if c == "=" and m[j + 1:j + 2] != "=" and m[j - 1:j] not in ("!", "<", ">", "="):
            return "expr", j + 1, expr_end(m, j + 1)
        if c in ";}":
            return None, j, j
        if c == "\n":
            prev = m[close_paren + 1:j].rstrip()
            nxt = _next_text(m, j)
            if (prev.endswith((":", ",", "->")) or nxt.startswith(("=", "{", ":", "where", "->", "."))):
                j += 1
                continue
            return None, j, j
        j += 1
    return None, n, n


def parse(text, path="<text>"):
    """Parse Kotlin source text. Returns a dict with package, imports, classes, functions."""
    code = Code(text)
    m = code.m
    pkg = re.search(r"(?m)^\s*package\s+([\w.]+)", m)
    package = pkg.group(1) if pkg else ""
    imports = re.findall(r"(?m)^\s*import\s+([\w.*`]+)(?:\s+as\s+(\w+))?", m)
    jvm_name = re.search(r"@file\s*:\s*JvmName\s*\(\s*\"([^\"]+)\"", text)
    stem = Path(path).stem
    facade = jvm_name.group(1) if jvm_name else (stem[:1].upper() + stem[1:] + "Kt")

    # classes
    classes = []
    for cm in CLASS_RE.finditer(m):
        pos = cm.start()
        if m[max(0, pos - 2):pos] == "::" or m[max(0, pos - 1):pos] in (".", "@"):
            continue
        kind, name = cm.group("kind"), cm.group("name")
        annotations, mods = _prefix(code, pos)
        before = m[code.line_start(pos):pos]
        if kind == "interface" and re.search(r"\bfun\s*$", before):
            mods.add("fun")
        if kind == "object" and not name:
            if "companion" not in mods:
                continue                                    # anonymous object expression
            name = "Companion"
        if kind == "class" and not name:
            continue
        if kind == "object" and "companion" in mods and name:
            kind = "companion"
        name = name.strip("`")
        body_open, header_end = _class_header_end(code, cm.end())
        header = m[cm.end():header_end]
        st = re.search(r"(?s)^(?:\s*<[^{]*?>)?\s*(?:@\w+\s*)*(?:(?:private|internal|protected|public)\s+)?"
                       r"(?:constructor\s*)?(?:\((?:.|\n)*?\))?\s*:\s*(.+)$", header)
        supertypes = re.findall(r"\b([A-Z]\w*)\s*[({<,]?", st.group(1)) if st else []
        body_close = code.pairs.get(body_open) if body_open is not None else None
        span_end = body_close if body_close is not None else header_end
        kind_label = "enum" if "enum" in mods else "annotation" if "annotation" in mods else \
                     "data class" if "data" in mods and kind == "class" else kind
        classes.append({"name": name, "kind": kind_label, "modifiers": sorted(mods), "line": code.line(pos),
                        "start": pos, "body": (body_open, body_close) if body_close is not None else None,
                        "span": (pos, span_end), "end_line": code.line(span_end), "supertypes": supertypes,
                        "annotations": annotations})
    # nesting: the innermost class whose body contains this class
    for c in classes:
        outer = [o for o in classes if o is not c and o["body"] and o["body"][0] < c["start"] < o["body"][1]]
        c["outer"] = min(outer, key=lambda o: o["body"][1] - o["body"][0]) if outer else None
    for c in classes:
        chain, o = [c["name"]], c["outer"]
        while o:
            chain.insert(0, o["name"])
            o = o["outer"]
        c["qualname"] = ".".join(chain)
        c["private"] = any("private" in x["modifiers"] for x in _chain(c))

    class_bodies = {c["body"][0]: c for c in classes if c["body"]}

    # functions
    functions = []
    fun_bodies = []
    for fm in FUN_RE.finditer(m):
        pos = fm.start()
        name = fm.group("name").strip("`")
        open_paren = fm.end() - 1
        close_paren = match_paren(m, open_paren)
        kind, b0, b1 = _fun_body(code, close_paren)
        fun_bodies.append((pos, b0, b1, kind))
        annotations, mods = _prefix(code, pos)
        functions.append({"name": name, "receiver": fm.group("recv"), "pos": pos, "line": code.line(pos),
                          "params": " ".join(text[open_paren + 1:close_paren].split()),
                          "signature": " ".join(text[pos:(b0 if kind else close_paren + 1)].split()).rstrip("={ "),
                          "modifiers": sorted(mods), "annotations": annotations, "body_kind": kind,
                          "body_range": (b0, b1), "end_line": code.line(b1)})

    def enclosing(pos):
        """Innermost brace pair around pos -> ('class', cls) | ('block', None) | ('top', None)."""
        best = None
        for o, c in code.pairs.items():
            if o < pos < c and (best is None or o > best[0]):
                best = (o, c)
        if best is None:
            return "top", None
        if best[0] in class_bodies:
            return "class", class_bodies[best[0]]
        return "block", None

    out_funs = []
    for f in functions:
        where, cls = enclosing(f["pos"])
        if where == "block":
            continue                                        # local function or inside a lambda/anonymous object
        b0, b1 = f["body_range"]
        f["body"] = text[b0:b1 + 1] if f["body_kind"] == "block" else text[b0:b1]
        f["body_masked"] = m[b0:b1 + 1] if f["body_kind"] == "block" else m[b0:b1]
        if cls is not None:
            owner = cls["outer"]["qualname"] if cls["kind"] == "companion" and cls["outer"] else cls["qualname"]
            f.update(owner=owner, companion=cls["kind"] == "companion", owner_kind=cls["kind"],
                     class_private=cls["private"])
        else:
            f.update(owner=None, companion=False, owner_kind="file", class_private=False)
        names = {a["name"] for a in f["annotations"]}
        f["is_test"] = bool(names & TEST_ANNOTATIONS)
        dis = [a for a in f["annotations"] if a["name"] in DISABLED_ANNOTATIONS]
        f["disabled"] = (dis[0]["args"].strip("()").strip().strip('"') or "no reason given") if dis else None
        f["expected_exception"] = any(a["name"] == "Test" and "expected" in a["args"] for a in f["annotations"])
        f["kotest"] = False
        out_funs.append(f)

    # Kotest test cases (leaf blocks such as test("...") { } and "..." { })
    kotest_classes = [c for c in classes if set(c["supertypes"]) & KOTEST_SPECS]
    for c in kotest_classes:
        c["kotest"] = True
        s0, s1 = c["span"]
        if c["body"] is None:                        # class FooSpec : StringSpec({ ... }) - tests in the lambda
            p = m.find("(", c["start"])
            s1 = match_paren(m, p) if p >= 0 else s1
        cases = []
        for km in KOTEST_CALL_RE.finditer(m, s0, s1):
            q = km.end() - 1
            qe = _skip_string(text, q)
            close = match_paren(m, q - 1 if m[q - 1] == "(" else m.rfind("(", 0, q))
            ob = m.find("{", close)
            if ob < 0 or ob not in code.pairs or m[close + 1:ob].strip():
                continue
            cases.append((km.start(), text[q + 1:qe - 1], km.group("fn").startswith("x"), ob))
        if "StringSpec" in c["supertypes"]:
            for km in KOTEST_STRING_RE.finditer(m, s0, s1):
                q = m.find('"', km.start())
                qe = _skip_string(text, q)
                ob = km.end() - 1
                cases.append((q, text[q + 1:qe - 1], bool(km.group("x")), ob))
        for pos, title, off, ob in cases:
            cb = code.pairs[ob]
            out_funs.append({"name": title, "receiver": None, "pos": pos, "line": code.line(pos), "params": "",
                             "signature": title, "modifiers": [], "annotations": [], "body_kind": "block",
                             "body_range": (ob, cb), "end_line": code.line(cb), "body": text[ob:cb + 1],
                             "body_masked": m[ob:cb + 1], "owner": c["qualname"], "companion": False,
                             "owner_kind": "class", "class_private": False, "is_test": True,
                             "disabled": "x-prefixed (disabled) Kotest case" if off else None,
                             "expected_exception": False, "kotest": True})
    for c in classes:
        c.setdefault("kotest", False)
        c.pop("outer", None)
    for f in out_funs:
        f.pop("pos", None)
    return {"path": str(path), "package": package, "imports": [i[0] for i in imports], "facade": facade,
            "classes": classes, "functions": out_funs}


def _chain(c):
    out = []
    while c:
        out.append(c)
        c = c.get("outer")
    return out


def parse_file(path):
    p = Path(path)
    data = p.read_bytes()
    text = data.decode("utf-8-sig", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
    return parse(text, p)


if __name__ == "__main__":
    import json
    import sys
    for a in sys.argv[1:]:
        r = parse_file(a)
        for f in r["functions"]:
            f.pop("body", None)
            f.pop("body_masked", None)
        print(json.dumps(r, indent=2, default=str))
