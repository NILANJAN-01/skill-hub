#!/usr/bin/env python3
"""Turn Android UIAutomator XML dumps into a JSON locator map (keyword names -> resource ids + selectors).

Input: the XML written by `uiautomator dump` (window_dump.xml), for any Android UI: phone, tablet,
TV, Android Automotive / OEM head units. Also reads the same hierarchy saved as .uix
(uiautomatorviewer) or Appium page-source XML.

Usage:
    python dump_to_locators.py window_dump.xml                  # -> locators/window_dump.locators.json
    python dump_to_locators.py dumps/ --out test/locators       # every .xml/.uix dump in a folder
    python dump_to_locators.py screen.xml --stdout              # print instead of writing
    python dump_to_locators.py screen.xml --format keywords     # only {"keyword": "resource-id"}
    python dump_to_locators.py screen.xml --case upper          # BTN_PLAY style keywords
    python dump_to_locators.py screen.xml --package com.example.media --exclude-package com.android.systemui

Standard library only (Python 3.8+). Exit code 0 = all files converted, 2 = a file could not be read.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

VERSION = "1.1"
INPUT_SUFFIXES = {".xml", ".uix"}
BOUNDS_RE = re.compile(r"\[\s*(-?\d+)\s*,\s*(-?\d+)\s*\]\s*\[\s*(-?\d+)\s*,\s*(-?\d+)\s*\]")
XML_DECL_RE = re.compile(r"<\?xml[^>]*\?>")
# Characters XML 1.0 forbids; some apps leak them into text and the dump then fails to parse.
BAD_XML_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
BAD_CHAR_REF_RE = re.compile(r"&#(?:[xX]0*(?:[0-8bBcCeEfF]|1[0-9a-fA-F])|0*(?:[0-8]|1[124-9]|2[0-9]|3[01]));")
BOOL_ATTRS = ("checkable", "checked", "clickable", "enabled", "focusable", "focused", "scrollable",
              "long-clickable", "password", "selected", "displayed")
# Short role names used to make readable keywords; first match wins (order matters).
ROLES = [("EditText", "input"), ("AutoCompleteTextView", "input"), ("SearchView", "search"),
         ("ImageButton", "button"), ("FloatingActionButton", "button"), ("RadioButton", "radio"),
         ("ToggleButton", "toggle"), ("CompoundButton", "toggle"), ("Button", "button"),
         ("CheckBox", "checkbox"), ("Switch", "switch"), ("SeekBar", "slider"), ("Slider", "slider"),
         ("RatingBar", "rating"), ("ProgressBar", "progress"), ("Spinner", "dropdown"),
         ("ImageView", "image"), ("TextView", "text"), ("RecyclerView", "list"), ("ListView", "list"),
         ("GridView", "grid"), ("ScrollView", "scroll"), ("ViewPager", "pager"), ("TabLayout", "tabs"),
         ("TabWidget", "tabs"), ("WebView", "webview"), ("Toolbar", "toolbar")]


class DumpError(ValueError):
    """The file is not a readable UIAutomator XML dump."""


# ================================================================================ reading
def read_text(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def _xml_root(text: str) -> ET.Element:
    """Parse the dump. Tolerates what real dumps contain: the XML declaration, the status line that
    `adb exec-out uiautomator dump /dev/tty` appends, several <hierarchy> blocks in one file, and
    control characters some apps leak into text."""
    if not re.search(r"<\s*(?:hierarchy|node)\b", text):
        raise DumpError("not a UIAutomator XML dump: no <hierarchy> or <node> elements found")
    if re.search(r"<!DOCTYPE|<html\b", text, re.I):
        raise DumpError("this looks like an HTML page or a document with a DOCTYPE; give the XML written by "
                        "`uiautomator dump` (window_dump.xml)")
    body = XML_DECL_RE.sub("", text)
    body = body[body.find("<"):body.rfind(">") + 1]          # drop text before/after the markup
    doc = "<dumps>" + body + "</dumps>"
    try:
        return ET.fromstring(doc)
    except ET.ParseError:
        pass
    try:
        return ET.fromstring(BAD_CHAR_REF_RE.sub("", BAD_XML_CHARS_RE.sub("", doc)))
    except ET.ParseError as e:
        line, col = e.position
        raise DumpError(f"invalid XML near line {line}, column {col}: {e}. The dump may be cut off; "
                        "capture it again") from None


def parse_dump(text: str):
    """Return (nodes in document order, number of windows). A window is a top-level node of the
    hierarchy: on Android Automotive the app, the system bars and overlays are separate windows."""
    root = _xml_root(text)
    nodes: list = []
    windows = 0
    stack = [(child, None, 0) for child in reversed(list(root))]
    while stack:
        el, parent, window = stack.pop()
        a = {k.lower(): v for k, v in el.attrib.items()}
        if el.tag == "node" or ("bounds" in a and ("class" in a or "resource-id" in a)):
            if parent is None:
                windows += 1
                window = windows
            idx = len(nodes)
            nodes.append(make_node(a, el.tag, idx, parent, window))
            parent = idx
        for child in reversed(list(el)):
            stack.append((child, parent, window))
    return nodes, windows


def make_node(a: dict, tag: str, order: int, parent, window: int) -> dict:
    cls = a.get("class") or ("" if tag == "node" else tag)
    m = BOUNDS_RE.search(a.get("bounds", ""))
    bounds = [int(x) for x in m.groups()] if m else None
    node = {
        "order": order, "parent": parent, "window": window,
        "resource_id": a.get("resource-id", "").strip(),
        "text": a.get("text", ""),
        "content_desc": a.get("content-desc", ""),
        "hint": a.get("hint", ""),
        "class": cls, "package": a.get("package", ""), "index": a.get("index", ""),
        "bounds": bounds,
    }
    for b in BOOL_ATTRS:
        if b in a:
            node[b.replace("-", "_")] = a[b].strip().lower() == "true"
    return node


# ================================================================================ keywords
def slug(s: str, limit: int = 40) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s[:limit].rstrip("_")


GENERIC_CLASSES = ("View", "ViewGroup", "FrameLayout", "LinearLayout", "RelativeLayout", "ConstraintLayout",
                   "CardView", "ComposeView", "AndroidComposeView")


def role(cls: str, clickable: bool = False) -> str:
    short = cls.rsplit(".", 1)[-1]
    for key, r in ROLES:
        if key.lower() in short.lower():
            return r
    if clickable and (short in GENERIC_CLASSES or not short):
        return "button"                       # clickable Compose/OEM containers act as buttons
    return slug(short) or "element"


def node_role(n: dict) -> str:
    return role(n["class"], n.get("clickable", False))


def id_entry(rid: str) -> str:
    """'com.app:id/btn_play' -> 'btn_play'; Compose test tags without ':id/' are used as they are."""
    if ":id/" in rid:
        return rid.split(":id/", 1)[1]
    return rid.rsplit("/", 1)[-1]


def label_keyword(label: str, n: dict) -> str:
    s, r = slug(label), node_role(n)
    if not s:
        return ""
    return s if s.endswith(r) or s.startswith(r + "_") else f"{s}_{r}"


def apply_case(kw: str, case: str) -> str:
    if case == "upper":
        return kw.upper()
    if case == "camel":
        parts = kw.split("_")
        return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])
    return kw


class KeywordPool:
    def __init__(self) -> None:
        self.owner: dict = {}

    def claim(self, base: str, package: str) -> str:
        if base and base[0].isdigit():
            base = "el_" + base
        if base not in self.owner:
            self.owner[base] = package
            return base
        pkg = slug(package.rsplit(".", 1)[-1]) if package else ""
        if pkg and self.owner[base] != package and f"{pkg}_{base}" not in self.owner:
            self.owner[f"{pkg}_{base}"] = package
            return f"{pkg}_{base}"
        n = 2
        while f"{base}_{n}" in self.owner:
            n += 1
        self.owner[f"{base}_{n}"] = package
        return f"{base}_{n}"


# ================================================================================ locators
def java_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def xpath_str(s: str) -> str:
    if "'" not in s:
        return f"'{s}'"
    if '"' not in s:
        return f'"{s}"'
    return "concat(" + ", \"'\", ".join(f"'{p}'" for p in s.split("'")) + ")"


def build_locators(sel: dict, instance) -> dict:
    """sel: ordered {"resourceId"|"text"|"description": value}. instance: 0-based or None."""
    ui = "new UiSelector()" + "".join(f".{k}({java_str(v)})" for k, v in sel.items())
    xp_attr = {"resourceId": "resource-id", "text": "text", "description": "content-desc", "className": "class"}
    cond = " and ".join(f"@{xp_attr[k]}={xpath_str(v)}" for k, v in sel.items())
    xpath = f"//*[{cond}]"
    by_name = {"resourceId": "res", "text": "text", "description": "desc", "className": "clazz"}
    by = ".".join(f"{by_name[k]}({java_str(v)})" for k, v in sel.items())
    u2 = dict(sel)
    if instance is not None:
        ui += f".instance({instance})"
        xpath = f"({xpath})[{instance + 1}]"
        u2["instance"] = instance
    loc = {"uiselector": ui, "uiautomator2": u2, "by": "By." + by, "xpath": xpath}
    if list(sel) == ["resourceId"]:
        loc["appium"] = {"strategy": "id", "value": sel["resourceId"]}
    elif list(sel) == ["description"]:
        loc["appium"] = {"strategy": "accessibility id", "value": sel["description"]}
    else:
        loc["appium"] = {"strategy": "xpath", "value": xpath}
    return loc


class SelectorIndex:
    """Answers 'which instance of this selector is node n?' in O(1) after one pass per selector shape.
    Instances are 0-based in document order, matching UiSelector.instance() semantics."""
    FIELDS = {"resourceId": "resource_id", "text": "text", "description": "content_desc", "className": "class"}

    def __init__(self, nodes: list) -> None:
        self.nodes = nodes
        self.cache: dict = {}

    def instance(self, n: dict, sel: dict):
        keys = tuple(sel)
        if keys not in self.cache:
            groups: dict = {}
            pos: dict = {}
            for m in self.nodes:
                bucket = groups.setdefault(tuple(m[self.FIELDS[k]] for k in keys), [])
                pos[m["order"]] = len(bucket)
                bucket.append(m["order"])
            self.cache[keys] = (groups, pos)
        groups, pos = self.cache[keys]
        same = groups[tuple(n[self.FIELDS[k]] for k in keys)]
        return None if len(same) <= 1 else pos[n["order"]]


# ================================================================================ building
def convert(nodes: list, windows: list, source: str, opts) -> dict:
    keep = [n for n in nodes
            if (not opts.package or n["package"] in opts.package)
            and n["package"] not in (opts.exclude_package or [])]
    pool, elements, warnings = KeywordPool(), [], []
    index = SelectorIndex(nodes)        # instances count every node on screen, like the device does
    by_id: dict = {}
    for n in keep:
        if n["resource_id"]:
            by_id.setdefault(n["resource_id"], []).append(n)

    def add(n, base, strategy, sel, instance, extra=None):
        kw = pool.claim(base, n["package"])
        el = {"keyword": apply_case(kw, opts.case), "strategy": strategy,
              "resource_id": n["resource_id"], "text": n["text"], "content_desc": n["content_desc"],
              "class": n["class"], "package": n["package"], "window": n["window"],
              "clickable": n.get("clickable", False), "enabled": n.get("enabled", True),
              "bounds": n["bounds"],
              "center": [(n["bounds"][0] + n["bounds"][2]) // 2, (n["bounds"][1] + n["bounds"][3]) // 2]
              if n["bounds"] else None,
              "locators": build_locators(sel, instance)}
        if instance is not None:
            el["instance"] = instance
        if n["hint"]:
            el["hint"] = n["hint"]
        if extra:
            el.update(extra)
        elements.append(el)

    seen_groups = set()
    for n in keep:
        rid, text, desc = n["resource_id"], n["text"].strip(), n["content_desc"].strip()
        if rid:
            group = by_id[rid]
            base = slug(id_entry(rid), 60) or node_role(n)
            if len(group) == 1:
                add(n, base, "resource_id", {"resourceId": rid}, None)
                continue
            if rid not in seen_groups:                    # one entry for the shared id itself
                seen_groups.add(rid)
                samples = [m["text"] or m["content_desc"] for m in group if m["text"] or m["content_desc"]]
                add(n, base, "resource_id", {"resourceId": rid}, None,
                    {"occurrences": len(group), "samples": samples[:10],
                     "note": f"{len(group)} elements share this id; add .instance(n) or use the "
                             "per-item keywords with text"})
            # content-desc is usually a fixed label; text often holds live values (temperature, track name)
            key = "description" if desc else ("text" if text else "")
            if key:
                raw = n["text"] if key == "text" else n["content_desc"]   # selectors match exactly
                sel = {"resourceId": rid, key: raw}
                lbl = slug(raw)
                add(n, f"{base}_{lbl}" if lbl else f"{base}_{n['order']}",
                    "resource_id+text" if key == "text" else "resource_id+content_desc",
                    sel, index.instance(n, sel))
            continue
        if desc:
            sel = {"description": n["content_desc"]}
            add(n, label_keyword(desc, n) or f"{node_role(n)}_{n['order']}",
                "content_desc", sel, index.instance(n, sel))
        elif text:
            sel = {"text": n["text"]}
            add(n, label_keyword(text, n) or f"{node_role(n)}_{n['order']}",
                "text", sel, index.instance(n, sel))
        elif opts.include_layout and n["class"]:
            sel = {"className": n["class"]}
            add(n, f"{node_role(n)}_{n['order']}", "class_instance", sel, index.instance(n, sel),
                {"fragile": True, "note": "no id, text or description: breaks when the layout changes; "
                                          "prefer asking for an id or test tag"})

    with_id = sum(1 for n in keep if n["resource_id"])
    labelled = sum(1 for n in keep if n["resource_id"] or n["text"].strip() or n["content_desc"].strip())
    if keep and with_id == 0:
        warnings.append("No resource-ids in this dump (common in Jetpack Compose and some OEM UIs). Locators "
                        "fall back to content-desc and text; ask developers for test tags exposed as "
                        "resource-ids (Compose: Modifier.semantics { testTagsAsResourceId = true }).")
    elif keep and with_id < labelled / 2:
        warnings.append(f"Only {with_id} of {labelled} labelled elements have a resource-id; text-based "
                        "locators break when the UI language changes.")
    if any(e["strategy"] == "text" for e in elements):
        warnings.append("Some locators use visible text: they depend on the UI language and wording.")

    packages: dict = {}
    for n in keep:
        packages[n["package"]] = packages.get(n["package"], 0) + 1
    keywords = {e["keyword"]: e["resource_id"] for e in elements if e["resource_id"] and
                e["strategy"] == "resource_id"}
    return {
        "generator": f"android-uiautomator-locators {VERSION}",
        "source": source,
        "summary": {"nodes": len(nodes), "nodes_kept": len(keep), "elements": len(elements),
                    "with_resource_id": with_id, "windows": windows,
                    "packages": packages},
        "warnings": warnings,
        "keywords": keywords,
        "elements": elements,
    }


# ================================================================================ CLI
def iter_inputs(paths: list):
    for p in paths:
        if p.is_dir():
            yield from sorted(f for f in p.rglob("*") if f.is_file() and f.suffix.lower() in INPUT_SUFFIXES)
        else:
            yield p


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Convert UIAutomator XML dumps into a JSON map of keyword names, "
                                             "resource ids and ready-made selectors.")
    ap.add_argument("inputs", nargs="+", type=Path, help="XML dump files, or folders of them (.xml / .uix)")
    ap.add_argument("--out", type=Path, default=Path("locators"), help="output folder (default: ./locators)")
    ap.add_argument("--stdout", action="store_true", help="print JSON instead of writing files")
    ap.add_argument("--format", choices=["full", "keywords"], default="full",
                    help="full = keywords + detailed elements (default); keywords = only {keyword: resource-id}")
    ap.add_argument("--case", choices=["snake", "upper", "camel"], default="snake", help="keyword style")
    ap.add_argument("--package", action="append", help="only keep nodes from this package (repeatable)")
    ap.add_argument("--exclude-package", action="append", help="drop nodes from this package (repeatable)")
    ap.add_argument("--include-layout", action="store_true",
                    help="also emit elements that have no id, text or description (fragile xpath)")
    opts = ap.parse_args(argv)

    files = list(iter_inputs(opts.inputs))
    if not files:
        print("No dump files found.", file=sys.stderr)
        return 2
    status = 0
    for f in files:
        if not f.is_file():
            print(f"ERROR {f}: not found", file=sys.stderr)
            status = 2
            continue
        try:
            nodes, windows = parse_dump(read_text(f))
            if not nodes:
                raise DumpError("the XML has a <hierarchy> but no <node> elements (was the screen blank or locked?)")
        except DumpError as e:
            print(f"ERROR {f}: {e}", file=sys.stderr)
            status = 2
            continue
        result = convert(nodes, windows, f.name, opts)
        payload = result["keywords"] if opts.format == "keywords" else result
        text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
        s = result["summary"]
        if opts.stdout:
            sys.stdout.write(text)
        else:
            opts.out.mkdir(parents=True, exist_ok=True)
            dest = opts.out / f"{f.stem}.locators.json"
            dest.write_text(text, encoding="utf-8")
            print(f"{f} -> {dest}")
        print(f"  {s['elements']} elements ({len(result['keywords'])} keyword->resource-id), "
              f"{s['nodes']} nodes, {s['windows']} window(s), packages: {', '.join(p or '?' for p in s['packages'])}",
              file=sys.stderr if opts.stdout else sys.stdout)
        for w in result["warnings"]:
            print(f"  WARN {w}", file=sys.stderr)
    return status


if __name__ == "__main__":
    sys.exit(main())
