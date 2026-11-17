#!/usr/bin/env python3
"""Lint LLM tool / function definitions.

Usage:
    python tool_lint.py <tools.json> [--json] [--strict]

Accepts one tool, a list of tools, or {"tools": [...]}, in MCP (inputSchema),
input_schema or OpenAI function ({"type": "function", "function": {...}}) form.
Standard library only.

Exit codes: 0 clean, 1 errors (or warnings with --strict), 2 unreadable input.
"""
import argparse
import json
import re
import sys

NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
WHEN_RE = re.compile(r"\b(use (this )?(when|to|for|if)|when the user|call (this )?when|only when|do not use|don't use)\b",
                     re.IGNORECASE)
JSON_TYPES = {"string", "number", "integer", "boolean", "object", "array", "null"}
STOPWORDS = set("a an the and or of to in for on by with from this that is are it its be as at use when user "
                "returns return tool given".split())
MAX_PARAMS = 10
MIN_DESC = 40


def normalize(tool):
    """Return (name, description, schema, format) for any supported tool shape."""
    if tool.get("type") == "function" and isinstance(tool.get("function"), dict):
        fn = tool["function"]
        return fn.get("name"), fn.get("description"), fn.get("parameters"), "openai"
    if "parameters" in tool and "inputSchema" not in tool and "input_schema" not in tool:
        return tool.get("name"), tool.get("description"), tool.get("parameters"), "function"
    if "input_schema" in tool:
        return tool.get("name"), tool.get("description"), tool.get("input_schema"), "input_schema"
    return tool.get("name"), tool.get("description"), tool.get("inputSchema"), "mcp"


def load_tools(data):
    if isinstance(data, dict) and isinstance(data.get("tools"), list):
        return data["tools"]
    if isinstance(data, dict) and isinstance(data.get("functions"), list):
        return data["functions"]
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data]
    raise ValueError("expected a tool object, a list of tools, or {\"tools\": [...]}")


def _words(text):
    return {w for w in re.findall(r"[a-z]+", (text or "").lower()) if len(w) > 2 and w not in STOPWORDS}


def _check_property(label, path, prop, findings):
    if not isinstance(prop, dict):
        findings.append(("ERROR", label, "%s: schema must be an object" % path))
        return
    ptype = prop.get("type")
    types = ptype if isinstance(ptype, list) else [ptype] if ptype else []
    for t in types:
        if t not in JSON_TYPES:
            findings.append(("ERROR", label, "%s: unknown JSON Schema type %r" % (path, t)))
    if not types and not any(k in prop for k in ("enum", "const", "anyOf", "oneOf", "allOf", "$ref")):
        findings.append(("WARN", label, "%s: no type given" % path))
    if not prop.get("description") and "enum" not in prop and "const" not in prop:
        findings.append(("WARN", label, "%s: no description" % path))
    if "enum" in prop:
        enum = prop["enum"]
        if not isinstance(enum, list) or not enum:
            findings.append(("ERROR", label, "%s: enum must be a non-empty list" % path))
        elif len(set(json.dumps(v, sort_keys=True) for v in enum)) != len(enum):
            findings.append(("WARN", label, "%s: enum has duplicate values" % path))
    if "array" in types:
        if "items" not in prop:
            findings.append(("WARN", label, "%s: array without items schema" % path))
        elif isinstance(prop["items"], dict) and prop["items"].get("type") == "object":
            _check_object(label, path + "[]", prop["items"], findings, nested=True)
    if "object" in types and "properties" in prop:
        _check_object(label, path, prop, findings, nested=True)


def _check_object(label, path, schema, findings, nested=False):
    props = schema.get("properties", {})
    if not isinstance(props, dict):
        findings.append(("ERROR", label, "%s.properties must be an object" % path))
        return 0
    required = schema.get("required", [])
    if not isinstance(required, list):
        findings.append(("ERROR", label, "%s.required must be a list" % path))
        required = []
    for req in required:
        if req not in props:
            findings.append(("ERROR", label, "%s: required %r is not in properties" % (path, req)))
    for pname, prop in props.items():
        _check_property(label, "%s.%s" % (path, pname) if nested else pname, prop, findings)
    return len(props)


def lint(tools):
    """Return a list of (level, tool_label, message)."""
    findings = []
    seen = {}
    summaries = []
    for i, raw in enumerate(tools):
        if not isinstance(raw, dict):
            findings.append(("ERROR", "#%d" % i, "tool is not an object"))
            continue
        name, desc, schema, _fmt = normalize(raw)
        label = name if isinstance(name, str) and name else "#%d" % i
        if not isinstance(name, str) or not name:
            findings.append(("ERROR", label, "missing name"))
        else:
            if not NAME_RE.match(name):
                findings.append(("ERROR", label, "name must be 1-64 chars of A-Z a-z 0-9 _ -"))
            elif not re.match(r"^[a-z][a-z0-9]*([_-][a-z0-9]+)+$", name):
                findings.append(("WARN", label, "prefer a verb_noun snake_case name (e.g. search_issues)"))
            key = name.lower()
            if key in seen:
                findings.append(("ERROR", label, "duplicate name (also tool #%d)" % seen[key]))
            seen[key] = i
        if not isinstance(desc, str) or not desc.strip():
            findings.append(("ERROR", label, "missing description"))
            desc = ""
        else:
            if len(desc.strip()) < MIN_DESC:
                findings.append(("WARN", label, "description under %d chars; say what it does, when to use it "
                                 "and what it returns" % MIN_DESC))
            if not WHEN_RE.search(desc):
                findings.append(("WARN", label, "description does not say when to use it ('Use when ...')"))
        if schema is None:
            findings.append(("ERROR", label, "missing parameter schema"))
        elif not isinstance(schema, dict):
            findings.append(("ERROR", label, "parameter schema must be an object"))
        else:
            if schema.get("type") != "object":
                findings.append(("ERROR", label, 'schema root type must be "object"'))
            count = _check_object(label, "params", schema, findings)
            if count > MAX_PARAMS:
                findings.append(("WARN", label, "%d parameters; consider splitting the tool or using enums" % count))
        summaries.append((label, _words(desc)))
    for a in range(len(summaries)):
        for b in range(a + 1, len(summaries)):
            wa, wb = summaries[a][1], summaries[b][1]
            if len(wa) >= 5 and len(wb) >= 5:
                overlap = len(wa & wb) / float(min(len(wa), len(wb)))
                if overlap >= 0.8:
                    findings.append(("WARN", summaries[a][0], "description overlaps %d%% with %s; say when to "
                                     "use each" % (overlap * 100, summaries[b][0])))
    if len(tools) > 20:
        findings.append(("WARN", "(set)", "%d tools; selection gets less reliable above ~20" % len(tools)))
    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("file", help="JSON file with tool definitions ('-' for stdin)")
    parser.add_argument("--json", action="store_true", help="print findings as JSON")
    parser.add_argument("--strict", action="store_true", help="treat warnings as failures")
    opts = parser.parse_args(argv)
    try:
        if opts.file == "-":
            data = json.load(sys.stdin)
        else:
            with open(opts.file, encoding="utf-8-sig") as fh:
                data = json.load(fh)
        tools = load_tools(data)
    except (OSError, ValueError) as exc:
        print("cannot read tools: %s" % exc, file=sys.stderr)
        return 2
    findings = lint(tools)
    errors = sum(1 for f in findings if f[0] == "ERROR")
    warns = len(findings) - errors
    if opts.json:
        print(json.dumps({"tools": len(tools), "errors": errors, "warnings": warns,
                          "findings": [{"level": l, "tool": t, "message": m} for l, t, m in findings]}, indent=2))
    else:
        for level, tool, msg in findings:
            print("%-5s %s: %s" % (level, tool, msg))
        print("%d tool(s), %d error(s), %d warning(s)" % (len(tools), errors, warns))
    if errors or (opts.strict and warns):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
