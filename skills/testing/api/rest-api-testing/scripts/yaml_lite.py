"""A small YAML reader for configuration and OpenAPI files (Python standard library only).

    from yaml_lite import load, YamlError
    data = load(text)          # dict / list / str / int / float / bool / None

It reads the YAML that OpenAPI, CI and config files use: block mappings and sequences, flow
collections ([a, b], {a: 1}, JSON), plain, single- and double-quoted scalars (also over several
lines), literal and folded block scalars (|, >, with -, + and an indent digit), comments, anchors
and aliases (&a, *a), merge keys (<<), the !!str/!!int/!!float/!!bool/!!null tags and a leading
'---'. Only the first document of a multi-document stream is returned.

Scalars follow the YAML 1.2 core schema: true/false, null/~, ints (also 0x and 0o) and floats
(also .inf and .nan). 'yes', 'no', 'on' and 'off' stay strings. Mapping keys are always strings,
so `200:` gives the key "200", as the same file written in JSON would.

Not supported (raises YamlError with the line number): '?' complex keys, tabs used as indentation,
and flow collections used as mapping keys.
"""
from __future__ import annotations

import re

__all__ = ["load", "YamlError"]


class YamlError(ValueError):
    """The text is not YAML this reader understands. The message starts with 'line N:'."""

    def __init__(self, msg, line=None):
        super().__init__(("line %d: %s" % (line, msg)) if line else msg)
        self.line = line


_INT10 = re.compile(r"[-+]?[0-9]+\Z")
_INT16 = re.compile(r"0x[0-9a-fA-F]+\Z")
_INT8 = re.compile(r"0o[0-7]+\Z")
_FLOAT = re.compile(r"[-+]?(\.[0-9]+|[0-9]+(\.[0-9]*)?)([eE][-+]?[0-9]+)?\Z")
_INF = re.compile(r"[-+]?\.(inf|Inf|INF)\Z")
_NAN = re.compile(r"\.(nan|NaN|NAN)\Z")
_ESCAPES = {"0": "\0", "a": "\a", "b": "\b", "t": "\t", "\t": "\t", "n": "\n", "v": "\v", "f": "\f",
            "r": "\r", "e": "\x1b", " ": " ", '"': '"', "/": "/", "\\": "\\", "N": "\x85",
            "_": "\xa0", "L": " ", "P": " "}
_HEX_LEN = {"x": 2, "u": 4, "U": 8}
_MISSING = object()


def load(text):
    """Parse the first YAML document in *text* and return plain Python values."""
    if isinstance(text, bytes):
        text = text.decode("utf-8-sig")
    return _Parser(text).document()


def _resolve(s):
    """Type a plain (unquoted) scalar by the YAML 1.2 core schema."""
    if s in ("", "~", "null", "Null", "NULL"):
        return None
    if s in ("true", "True", "TRUE"):
        return True
    if s in ("false", "False", "FALSE"):
        return False
    if _INT10.match(s):
        return int(s)
    if _INT16.match(s):
        return int(s[2:], 16)
    if _INT8.match(s):
        return int(s[2:], 8)
    if _FLOAT.match(s) and any(c.isdigit() for c in s):
        return float(s)
    if _INF.match(s):
        return float("-inf") if s.startswith("-") else float("inf")
    if _NAN.match(s):
        return float("nan")
    return s


def _key(value):
    """Mapping keys are strings, like the same document in JSON."""
    if isinstance(value, str):
        return value
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, dict)):
        raise YamlError("a list or mapping cannot be used as a mapping key")
    return str(value)


def _comment_at(s, start=0):
    """Index of a '#' comment in *s* (outside quotes), or len(s). '#' needs a space before it."""
    i, n = start, len(s)
    quote = None
    while i < n:
        c = s[i]
        if quote == "'":
            if c == "'":
                if i + 1 < n and s[i + 1] == "'":
                    i += 1
                else:
                    quote = None
        elif quote == '"':
            if c == "\\":
                i += 1
            elif c == '"':
                quote = None
        elif c in "'\"" and (i == start or s[i - 1] in " \t[{,:-?"):
            quote = c
        elif c == "#" and (i == 0 or s[i - 1] in " \t"):
            return i
        i += 1
    return n


def _uncomment(s):
    return s[:_comment_at(s)].rstrip()


class _Parser:
    def __init__(self, text):
        self.lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        if self.lines and self.lines[0].startswith("﻿"):
            self.lines[0] = self.lines[0][1:]
        self.i = 0
        self.anchors = {}

    # ------------------------------------------------------------------ line helpers
    def err(self, msg, i=None):
        return YamlError(msg, (self.i if i is None else i) + 1)

    @staticmethod
    def indent_of(line):
        return len(line) - len(line.lstrip(" "))

    def is_blank(self, i):
        s = self.lines[i].strip()
        return not s or s.startswith("#")

    def next_content(self):
        """Index of the next line with content (not blank, not a comment), or None at the end."""
        i = self.i
        while i < len(self.lines):
            line = self.lines[i]
            if line.startswith(("---", "...")) and (len(line) == 3 or line[3] in " \t"):
                return None if i > self.doc_start else i
            if not self.is_blank(i):
                stripped = line.lstrip(" ")
                if stripped.startswith("\t") or (line[:1] == "\t"):
                    raise self.err("tabs cannot be used for indentation", i)
                return i
            i += 1
        return None

    # ------------------------------------------------------------------ document
    def document(self):
        self.doc_start = -1
        while self.i < len(self.lines):
            s = self.lines[self.i].strip()
            if not s or s.startswith("#") or s.startswith("%"):
                self.i += 1
                continue
            break
        if self.i < len(self.lines) and self.lines[self.i].startswith("---"):
            rest = self.lines[self.i][3:]
            if rest == "" or rest[0] in " \t":
                self.doc_start = self.i
                rest = rest.strip()
                if rest and not rest.startswith("#"):
                    self.lines[self.i] = rest        # '--- value' on the marker line
                else:
                    self.i += 1
        self.doc_start = self.i
        if self.next_content() is None:
            return None
        value = self.block(-1)
        j = self.next_content()
        if j is not None:
            raise self.err("unexpected content (check the indentation)", j)
        return value

    # ------------------------------------------------------------------ block nodes
    def block(self, parent):
        """Parse the node whose lines are indented more than *parent*."""
        j = self.next_content()
        if j is None:
            return None
        line = self.lines[j]
        ind = self.indent_of(line)
        if ind <= parent:
            return None
        self.i = j
        body = line[ind:]
        if body == "-" or body.startswith(("- ", "-\t")):
            return self.sequence(ind)
        if body.startswith("? "):
            raise self.err("'?' complex mapping keys are not supported")
        if self.map_colon(body) >= 0:
            return self.mapping(ind)
        return self.inline_value(body, ind, parent)

    def sequence(self, ind):
        out = []
        while True:
            j = self.next_content()
            if j is None:
                break
            line = self.lines[j]
            if self.indent_of(line) != ind:
                if self.indent_of(line) > ind:
                    raise self.err("bad indentation in a list", j)
                break
            body = line[ind:]
            if not (body == "-" or body.startswith(("- ", "-\t"))):
                break
            self.i = j
            rest = body[1:]
            if not _uncomment(rest).strip():
                self.i += 1
                out.append(self.block(ind))
                continue
            pad = len(rest) - len(rest.lstrip(" \t"))
            # Rewrite '- item' as an indented line, so '- a: 1' continues as a mapping.
            self.lines[j] = " " * (ind + 1 + pad) + rest.lstrip(" \t")
            out.append(self.block(ind))
        return out

    def map_colon(self, body):
        """Index of the ':' that ends a mapping key on this line, or -1 if it is not a key."""
        if body[:1] in ("[", "{"):
            return -1
        if body[:1] in ("'", '"'):
            end = self.quote_end(body, 0)
            if end < 0:
                return -1
            k = end + 1
            while k < len(body) and body[k] == " ":
                k += 1
            if k < len(body) and body[k] == ":" and (k + 1 == len(body) or body[k + 1] in " \t"):
                return k
            return -1
        stop = _comment_at(body)
        k = 0
        while True:
            k = body.find(":", k, stop)
            if k < 0:
                return -1
            if k + 1 == len(body) or body[k + 1] in " \t" or k + 1 == stop:
                return k
            k += 1

    @staticmethod
    def quote_end(s, start):
        """Index of the quote closing the string that opens at s[start], or -1."""
        q = s[start]
        k = start + 1
        while k < len(s):
            c = s[k]
            if q == '"' and c == "\\":
                k += 2
                continue
            if c == q:
                if q == "'" and k + 1 < len(s) and s[k + 1] == "'":
                    k += 2
                    continue
                return k
            k += 1
        return -1

    def mapping(self, ind):
        out = {}
        merges = []
        while True:
            j = self.next_content()
            if j is None:
                break
            line = self.lines[j]
            cur = self.indent_of(line)
            if cur != ind:
                if cur > ind:
                    raise self.err("bad indentation in a mapping", j)
                break
            body = line[ind:]
            if body == "-" or body.startswith(("- ", "-\t")):
                break
            self.i = j
            colon = self.map_colon(body)
            if colon < 0:
                raise self.err("expected 'key: value'")
            raw_key = body[:colon].strip()
            if raw_key[:1] in ("'", '"'):
                key = self.quoted(raw_key, 0)[0]
            else:
                if raw_key.startswith(("&", "*", "!")):
                    raise self.err("anchors, aliases and tags on keys are not supported")
                key = raw_key                        # as written, like a JSON key
            rest = body[colon + 1:]
            value = self.value_after_key(rest, ind)
            if key == "<<" and raw_key == "<<":
                merges.extend(value if isinstance(value, list) else [value])
            else:
                out[key] = value
        if merges:
            merged = {}
            for m in merges:
                if not isinstance(m, dict):
                    raise self.err("'<<' needs a mapping or a list of mappings")
                for k, v in m.items():
                    merged.setdefault(k, v)
            merged.update(out)
            out = merged
        return out

    def value_after_key(self, rest, ind):
        """The value of a key whose text after the ':' is *rest* (on line self.i)."""
        text = _uncomment(rest).strip()
        alone = re.match(r"&(\S+)\Z", text)          # 'key: &name' with the value on the next lines
        anchor = alone.group(1) if alone else None
        if not text or alone:
            self.i += 1
            j = self.next_content()
            value = None
            if j is not None:
                line = self.lines[j]
                cur = self.indent_of(line)
                body = line[cur:]
                if cur > ind:
                    value = self.block(ind)
                elif cur == ind and (body == "-" or body.startswith(("- ", "-\t"))):
                    value = self.sequence(ind)      # a list may sit at its key's indent
        else:
            value = self.inline_value(text, ind, ind, raw=rest.strip())
        if anchor:
            self.anchors[anchor] = value
        return value

    # ------------------------------------------------------------------ scalars on a line
    def inline_value(self, text, ind, parent, raw=None):
        """A value that starts on line self.i with *text*. Consumes its lines."""
        raw = text if raw is None else raw
        text = _uncomment(text).strip() if raw is text else text
        anchor = None
        if text.startswith("&"):
            parts = text.split(None, 1)
            anchor = parts[0][1:]
            text = parts[1] if len(parts) > 1 else ""
            raw = raw.split(None, 1)[1] if len(raw.split(None, 1)) > 1 else ""
        tag = None
        if text.startswith("!"):
            parts = text.split(None, 1)
            tag = parts[0]
            text = parts[1] if len(parts) > 1 else ""
            raw = raw.split(None, 1)[1] if len(raw.split(None, 1)) > 1 else ""
        if not text:
            self.i += 1
            value = self.block(parent)
        elif text.startswith("*"):
            name = text[1:].strip()
            if name not in self.anchors:
                raise self.err("unknown alias *%s" % name)
            self.i += 1
            value = self.anchors[name]
        elif text[0] in "|>":
            value = self.block_scalar(text, parent)
        elif text[0] in "[{":
            value = self.flow(raw.strip())
        elif text[0] in "'\"":
            value = self.multiline_quoted(raw.strip(), parent)
        else:
            value = self.plain(text, parent)
        if tag:
            value = self.apply_tag(tag, value)
        if anchor:
            self.anchors[anchor] = value
        return value

    def apply_tag(self, tag, value):
        try:
            if tag == "!!str":
                if value is None:
                    return ""
                if isinstance(value, bool):
                    return "true" if value else "false"
                return value if isinstance(value, str) else str(value)
            if tag == "!!int":
                return int(value)
            if tag == "!!float":
                return float(value)
            if tag == "!!bool":
                return value if isinstance(value, bool) else str(value).lower() == "true"
            if tag == "!!null":
                return None
        except (TypeError, ValueError):
            raise self.err("cannot apply %s to %r" % (tag, value))
        return value                                 # !!map, !!seq and local tags: keep the value

    def plain(self, text, parent):
        """A plain scalar, which may continue on more-indented lines."""
        parts = [text]
        self.i += 1
        while True:
            j = self.next_content_or_blank()
            if j is None:
                break
            line = self.lines[j]
            if not line.strip():
                parts.append("")
                self.i = j + 1
                continue
            if self.indent_of(line) <= parent or line.lstrip().startswith("#"):
                break
            body = line.strip()
            if self.map_colon(body) >= 0 or body.startswith(("- ", "-\t")) and self.indent_of(line) <= parent + 1:
                break
            parts.append(_uncomment(body))
            self.i = j + 1
        while parts and parts[-1] == "":
            parts.pop()
        if len(parts) == 1:
            return _resolve(text)
        return self.fold(parts)

    def next_content_or_blank(self):
        if self.i >= len(self.lines):
            return None
        line = self.lines[self.i]
        if line.startswith(("---", "...")) and (len(line) == 3 or line[3] in " \t"):
            return None
        return self.i

    @staticmethod
    def fold(parts):
        """Join flow-scalar lines: a line break becomes a space, an empty line becomes a newline."""
        out = ""
        pending_space = False
        for p in parts:
            if p == "":
                out += "\n"
                pending_space = False
            else:
                if pending_space:
                    out += " "
                out += p
                pending_space = True
        return out

    def multiline_quoted(self, raw, parent):
        """A quoted scalar starting on line self.i; it may run on to later lines."""
        start = self.i
        buf = raw
        while self.quote_end(buf, 0) < 0:
            self.i += 1
            if self.i >= len(self.lines):
                raise self.err("unterminated quoted string", start)
            buf += "\n" + self.lines[self.i]
        value, end = self.quoted(buf, 0)
        tail = _uncomment(buf[end:]).strip()
        if tail:
            raise self.err("unexpected text after a quoted string: %r" % tail)
        self.i += 1
        return value

    def quoted(self, s, start):
        """Decode the quoted string at s[start]; return (value, index after the closing quote)."""
        q = s[start]
        end = self.quote_end(s, start)
        if end < 0:
            raise self.err("unterminated quoted string")
        inner = s[start + 1:end]
        if "\n" in inner:
            inner = self.fold_quoted_lines(inner, q)
        if q == "'":
            return inner.replace("''", "'"), end + 1
        out = []
        k = 0
        while k < len(inner):
            c = inner[k]
            if c != "\\":
                out.append(c)
                k += 1
                continue
            k += 1
            if k >= len(inner):
                raise self.err("bad escape at the end of a string")
            e = inner[k]
            if e in _HEX_LEN:
                n = _HEX_LEN[e]
                digits = inner[k + 1:k + 1 + n]
                if len(digits) != n or not all(ch in "0123456789abcdefABCDEF" for ch in digits):
                    raise self.err("bad \\%s escape" % e)
                out.append(chr(int(digits, 16)))
                k += 1 + n
            elif e in _ESCAPES:
                out.append(_ESCAPES[e])
                k += 1
            else:
                raise self.err("unknown escape \\%s" % e)
        return "".join(out), end + 1

    @staticmethod
    def fold_quoted_lines(inner, q):
        """Fold a quoted scalar written over several lines (before escapes are decoded)."""
        lines = inner.split("\n")
        last = len(lines) - 1
        res, prev_esc, breaks = "", False, 0
        for idx, ln in enumerate(lines):
            if idx:
                ln = ln.lstrip(" \t")
            esc = q == '"' and (len(ln) - len(ln.rstrip("\\"))) % 2 == 1   # '\' escapes the break
            if idx < last and not esc:
                ln = ln.rstrip(" \t")
            if esc:
                ln = ln[:-1]
            if idx == 0:
                res, prev_esc = ln, esc
                continue
            if ln == "" and idx < last and not esc:
                breaks += 1
                continue
            if breaks:
                res += "\n" * breaks
            elif not prev_esc:
                res += " "
            res += ln
            prev_esc, breaks = esc, 0
        return res

    def block_scalar(self, header, parent):
        m = re.match(r"([|>])([+-]?)([1-9]?)([+-]?)\s*\Z", header)
        if not m:
            raise self.err("bad block scalar header %r" % header)
        style, chomp, digit = m.group(1), m.group(2) or m.group(4), m.group(3)
        self.i += 1
        content_indent = (max(parent, 0) + int(digit)) if digit else None
        lines = []
        while self.i < len(self.lines):
            line = self.lines[self.i]
            if not line.strip():
                lines.append(line)
                self.i += 1
                continue
            cur = self.indent_of(line)
            if content_indent is None:
                if cur <= parent:
                    break
                content_indent = cur
            if cur < content_indent:
                break
            lines.append(line)
            self.i += 1
        if content_indent is None:
            content_indent = parent + 1
        body = [ln[content_indent:] if len(ln) >= content_indent else "" for ln in lines]
        trailing = 0
        while body and body[-1].strip() == "":
            body.pop()
            trailing += 1
        text = "\n".join(body) if style == "|" else self.fold_block(body)
        if not body:
            return "\n" * trailing if chomp == "+" else ""
        if chomp == "-":
            return text
        if chomp == "+":
            return text + "\n" + "\n" * trailing
        return text + "\n"

    @staticmethod
    def fold_block(body):
        """Folded style: join normal lines with spaces; blank lines and indented lines keep breaks."""
        out = []
        i = 0
        n = len(body)
        while i < n:
            ln = body[i]
            out.append(ln)
            if i + 1 >= n:
                break
            # count blank lines after this one
            j = i + 1
            blanks = 0
            while j < n and body[j] == "":
                blanks += 1
                j += 1
            if j >= n:
                break
            nxt = body[j]
            more = ln[:1] in " \t" or nxt[:1] in " \t" or ln == ""
            if blanks == 0:
                out.append("\n" if more else " ")
            else:
                out.append("\n" * (blanks + (1 if more else 0)))
            i = j
        return "".join(out)

    # ------------------------------------------------------------------ flow collections
    def flow(self, raw):
        """A [..] or {..} collection starting on line self.i, possibly over several lines."""
        start = self.i
        text = raw
        while True:
            try:
                value, end = _Flow(text, self).parse()
            except _Incomplete:
                self.i += 1
                if self.i >= len(self.lines):
                    raise self.err("unclosed [ or {", start)
                text += "\n" + self.lines[self.i]
                continue
            tail = _uncomment(text[end:]).strip()
            if tail:
                raise self.err("unexpected text after a flow collection: %r" % tail)
            self.i += 1
            return value


class _Incomplete(Exception):
    pass


class _Flow:
    """Parser for one flow collection held in a string (newlines allowed)."""

    def __init__(self, s, owner):
        self.s = s
        self.k = 0
        self.owner = owner

    def skip(self):
        s = self.s
        while self.k < len(s):
            c = s[self.k]
            if c in " \t\n":
                self.k += 1
            elif c == "#" and (self.k == 0 or s[self.k - 1] in " \t\n"):
                nl = s.find("\n", self.k)
                if nl < 0:
                    raise _Incomplete()
                self.k = nl
            else:
                break
        if self.k >= len(s):
            raise _Incomplete()

    def parse(self):
        value = self.node()
        return value, self.k

    def node(self):
        self.skip()
        c = self.s[self.k]
        anchor = None
        if c == "&":
            m = re.match(r"&([^\s,\[\]{}]+)", self.s[self.k:])
            anchor = m.group(1)
            self.k += m.end()
            self.skip()
            c = self.s[self.k]
        tag = None
        if c == "!":
            m = re.match(r"!\S*", self.s[self.k:])
            tag = m.group(0)
            self.k += m.end()
            self.skip()
            c = self.s[self.k]
        if c == "[":
            value = self.seq()
        elif c == "{":
            value = self.map()
        elif c in "'\"":
            if self.owner.quote_end(self.s, self.k) < 0:
                raise _Incomplete()
            value, self.k = self.owner.quoted(self.s, self.k)
        elif c == "*":
            m = re.match(r"\*([^\s,\[\]{}]+)", self.s[self.k:])
            self.k += m.end()
            if m.group(1) not in self.owner.anchors:
                raise self.owner.err("unknown alias *%s" % m.group(1))
            value = self.owner.anchors[m.group(1)]
        else:
            value = self.plain()
        if tag:
            value = self.owner.apply_tag(tag, value)
        if anchor:
            self.owner.anchors[anchor] = value
        return value

    def plain(self, as_text=False):
        s = self.s
        start = self.k
        while self.k < len(s):
            c = s[self.k]
            if c in ",[]{}":
                break
            if c == ":" and (self.k + 1 >= len(s) or s[self.k + 1] in " \t\n,[]{}"):
                break
            if c == "#" and self.k > 0 and s[self.k - 1] in " \t\n":
                break
            self.k += 1
        text = " ".join(s[start:self.k].split())
        return text if as_text else _resolve(text)

    def seq(self):
        self.k += 1
        out = []
        while True:
            self.skip()
            if self.s[self.k] == "]":
                self.k += 1
                return out
            item = self.node()
            self.skip()
            if self.s[self.k] == ":":                # [a: 1] is a list holding a one-key mapping
                self.k += 1
                item = {_key(item): self.node()}
                self.skip()
            out.append(item)
            c = self.s[self.k]
            if c == ",":
                self.k += 1
            elif c != "]":
                raise self.owner.err("expected ',' or ']' in a flow list")

    def map(self):
        self.k += 1
        out = {}
        while True:
            self.skip()
            if self.s[self.k] == "}":
                self.k += 1
                return out
            if self.s[self.k] in "'\"[{*&!":
                key = _key(self.node())
            else:
                key = self.plain(as_text=True)       # as written, like a JSON key
            self.skip()
            value = None
            if self.s[self.k] == ":":
                self.k += 1
                self.skip()
                if self.s[self.k] not in ",}":
                    value = self.node()
                    self.skip()
            out[key] = value
            c = self.s[self.k]
            if c == ",":
                self.k += 1
            elif c != "}":
                raise self.owner.err("expected ',' or '}' in a flow mapping")
