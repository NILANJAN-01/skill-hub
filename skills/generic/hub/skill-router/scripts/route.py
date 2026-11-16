#!/usr/bin/env python3
"""Route a user request to the right skills: split it into parts, grade each part, match installed skills.

    python route.py "request text" [--root DIR]... [--catalog catalog.json] [--json] [--top 3]
    python route.py --file request.txt

For every part of the request it prints a level (basic / advanced), the best matching installed skills with the
words that matched, missing inputs the skill will need (a file, a link, an image ...), missing tools, and a final
list of skills to load in order. Skills that are not installed but exist in a hub catalog are listed separately.

Standard library only (Python 3.8+). Read-only: it never installs, runs or writes anything.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HINTS_FILE = HERE.parent / "references" / "routing-hints.json"

PROJECT_DIRS = [".claude/skills", ".agents/skills", ".agent/skills", ".github/skills", ".cursor/skills",
                ".devin/skills", ".windsurf/skills", ".codex/skills", ".gemini/skills"]
USER_DIRS = ["~/.claude/skills", "~/.agents/skills", "~/.gemini/config/skills", "~/.gemini/skills",
             "~/.copilot/skills", "~/.cursor/skills", "~/.config/devin/skills", "~/.codex/skills"]

STOP = set("""a an and are as at be by can do for from has have how i in is it its me my of on or our so that the
their them then this to use used using want was we what when where which who will with you your please help make
need needs get give show tell about into out up""".split())

ACTIONS = set("""analyse analyze check write create build make fix find explain review generate run test convert
tailor read summarise summarize compare improve optimise optimize debug add update refactor draft inspect extract
install plan report document translate""".split())

ADVANCED_WORDS = set("""end-to-end pipeline across multiple compare optimise optimize refactor migrate automate
architecture architectures coverage mutation benchmark regression integration whole entire every all""".split())

REQUIREMENTS = {
    "python": ("python", None), "adb": ("cmd", "adb"), "java": ("cmd", "java"), "jdk": ("cmd", "javac"),
    "gradle": ("cmd", "gradle"), "maven": ("cmd", "mvn"), "kotlinc": ("cmd", "kotlinc"),
    "ffmpeg": ("cmd", "ffmpeg"), "ffprobe": ("cmd", "ffprobe"), "docker": ("cmd", "docker"),
    "node": ("cmd", "node"), "npm": ("cmd", "npm"), "git": ("cmd", "git"), "tesseract": ("cmd", "tesseract"),
    "opencv": ("py", "cv2"), "pillow": ("py", "PIL"), "numpy": ("py", "numpy"),
}

# What the prompt must contain for an input kind to count as "given".
INPUT_PATTERNS = {
    "url": (r"https?://\S+", "a link (http/https URL)"),
    "file": (r"[\w./\\:-]+\.[A-Za-z0-9]{1,6}\b|\battach|\bfile\b|\bpaste", "a file path, an attachment or pasted text"),
    "image": (r"\.(png|jpe?g|webp|gif|bmp|tiff?)\b|\bscreenshot|\bimage|\bphoto", "an image or screenshot"),
    "video": (r"\.(mp4|mov|mkv|webm|avi)\b|\bvideo|\brecording", "a video or screen recording"),
    "python-file": (r"\.py\b|\bpython\b", "a .py file"),
    "repo": (r"https?://\S+|\brepo|\brepository|\bproject|\bcodebase|\bfolder", "a repository path or URL"),
    "device": (r"\bdevice|\bphone|\bemulator|\badb\b|\bandroid", "a connected device or emulator"),
}


# ----------------------------------------------------------------------------- registry
def parse_frontmatter(text: str) -> dict:
    m = re.match(r"^---\s*\r?\n(.*?)\r?\n---\s*(?:\r?\n|$)", text, re.S)
    if not m:
        return {}
    out, parent = {}, None
    for line in m.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        kv = re.match(r"^\s*([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not kv:
            continue
        key, val = kv.group(1), kv.group(2).strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        if indent == 0:
            out[key], parent = ({}, key) if val == "" else (val, None)
        elif parent and isinstance(out.get(parent), dict):
            out[parent][key] = val
    return out


def roots_to_scan(extra: list, defaults: bool = True) -> list:
    roots = [Path(r).expanduser() for r in extra]
    if defaults:
        roots += [Path.cwd() / d for d in PROJECT_DIRS] + [Path(d).expanduser() for d in USER_DIRS]
        if (Path.cwd() / ".claude-plugin").is_dir():
            roots.append(Path.cwd() / "skills")
    return roots


def skill_folders(root: Path, depth: int = 3) -> list:
    """Folders under `root` that hold a SKILL.md: directly (an agent's skills folder) or nested up to
    `depth` levels (a hub clone: skills/<area>/<group>/<name>/)."""
    found = []
    try:
        children = sorted(p for p in root.iterdir() if p.is_dir())
    except OSError:
        return found
    for d in children:
        if d.name.startswith(".") or d.name == "__pycache__":
            continue
        if (d / "SKILL.md").is_file():
            found.append(d)
        elif depth > 1:
            found += skill_folders(d, depth - 1)
    return found


def scan(extra: list = (), defaults: bool = True) -> dict:
    reg = {}
    for root in roots_to_scan(list(extra), defaults):
        if not root.is_dir():
            continue
        for d in skill_folders(root):
            md = d / "SKILL.md"
            try:
                fm = parse_frontmatter(md.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
            name = fm.get("name") or d.name
            if name not in reg:
                reg[name] = {"name": name, "description": fm.get("description", ""),
                             "compatibility": fm.get("compatibility", ""), "installed": True}
    return reg


def load_catalog(path: Path, installed: dict) -> dict:
    """Skills listed in a hub catalog.json that are not installed (so they can be suggested)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {s["name"]: {"name": s["name"], "description": s.get("description", ""),
                        "compatibility": s.get("compatibility", ""), "installed": False}
            for s in data.get("skills", []) if s.get("name") and s["name"] not in installed}


def load_hints(path: Path = HINTS_FILE) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("skills", {})
    except (OSError, ValueError):
        return {}


# ----------------------------------------------------------------------------- understanding the request
def tokens(text: str) -> list:
    return [t for t in re.findall(r"[a-z][a-z0-9+#-]*", text.lower()) if t not in STOP and len(t) > 1]


def stem(t: str) -> str:
    for suf in ("ing", "es", "s", "ed"):
        if t.endswith(suf) and len(t) - len(suf) >= 3:
            return t[: -len(suf)]
    return t


def split_request(text: str) -> list:
    """Split a prompt into separate asks: lines, bullets, sentences, 'then', ';' and 'and <action>'."""
    text = re.sub(r"https?://\S+", lambda m: m.group(0).replace(".", "․"), text)   # keep URLs whole
    parts = re.split(r"\n+|(?<=[.!?])\s+|;\s*|\s+(?:and then|and also|after that|afterwards|then|also|plus)\s+", text)
    out = []
    for p in parts:
        p = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", p).strip(" ,")
        if not p:
            continue
        sub = re.split(r"\s+and\s+(?=(?:" + "|".join(sorted(ACTIONS)) + r")\b)", p, flags=re.I)
        out += [s.strip(" ,") for s in sub if s.strip(" ,")]
    return [p.replace("․", ".") for p in out]


def level_of(part: str, n_matches: int = 1) -> str:
    words = re.findall(r"[a-z-]+", part.lower())
    if len(words) > 25 or any(w in ADVANCED_WORDS for w in words) or n_matches > 1:
        return "advanced"
    return "basic"


def missing_inputs(part: str, whole: str, needs: list) -> list:
    out = []
    for kind in needs:
        pat = INPUT_PATTERNS.get(kind)
        if pat and not re.search(pat[0], part + " " + whole, re.I):
            out.append(pat[1])
    return out


# ----------------------------------------------------------------------------- matching
def match(part: str, reg: dict, hints: dict, top: int = 3, context: str = "") -> list:
    """Rank skills: term overlap with name (x3), description (x1) and routing hints (x2); rare terms count more.
    Words that appear only in the surrounding request (context) count at 30%, so 'write tests for it' follows
    'this python file'."""
    q = list(dict.fromkeys(stem(t) for t in tokens(part)))
    ctx = [t for t in dict.fromkeys(stem(t) for t in tokens(context)) if t not in q]
    low = part.lower()
    if not q or not reg:
        return []
    docs = {}
    for name, s in reg.items():
        hint_words = " ".join(hints.get(name, {}).get("keywords", []))
        docs[name] = ({stem(t) for t in tokens(name.replace("-", " "))},
                      {stem(t) for t in tokens(s["description"])}, {stem(t) for t in tokens(hint_words)})
    n = len(docs)
    scored = []
    for name, (nt, dt, ht) in docs.items():
        score, why = 0.0, []
        for t in q:
            df = sum(1 for a, b, c in docs.values() if t in a or t in b or t in c)
            idf = math.log((n + 1) / (df + 0.5)) if df else 0
            w = (3.0 if t in nt else 0) + (1.0 if t in dt else 0) + (2.0 if t in ht else 0)
            if w:
                score += w * idf
                why.append(t)
        for t in ctx:
            df = sum(1 for a, b, c in docs.values() if t in a or t in b or t in c)
            w = (3.0 if t in nt else 0) + (1.0 if t in dt else 0) + (2.0 if t in ht else 0)
            if w and df:
                score += 0.3 * w * math.log((n + 1) / (df + 0.5))
        for phrase in hints.get(name, {}).get("phrases", []):
            if phrase.lower() in low:
                score += 6.0
                why.append(f'"{phrase}"')
        if score > 0:
            scored.append({"skill": name, "score": round(score, 2), "matched": why,
                           "installed": reg[name]["installed"]})
    scored.sort(key=lambda r: (-r["score"], r["skill"]))
    if scored:
        best = scored[0]["score"]
        for r in scored:
            strong = len(r["matched"]) >= 2 or any(m.startswith('"') for m in r["matched"])   # one bare word is weak
            if r["score"] >= max(8.0, 0.7 * best) and r is scored[0]:
                r["confidence"] = "high" if strong else "low"
            else:
                r["confidence"] = "medium" if r["score"] >= 0.5 * best and strong else "low"
    return scored[:top]


def requirements_of(compat: str) -> list:
    low = compat.lower()
    found = [k for k in REQUIREMENTS if re.search(r"(?<![a-z])" + re.escape(k) + r"(?![a-z])", low)]
    if re.search(r"python\s*3", low) and "python" not in found:
        found.append("python")
    return found


def have(req: str) -> bool:
    kind, target = REQUIREMENTS[req]
    if kind == "python":
        return sys.version_info >= (3, 8)
    if kind == "cmd":
        return shutil.which(target) is not None
    try:
        return importlib.util.find_spec(target) is not None
    except (ImportError, ValueError):
        return False


# ----------------------------------------------------------------------------- routing
def route(text: str, reg: dict, hints: dict, top: int = 3) -> dict:
    installed = {k: v for k, v in reg.items() if v["installed"]}
    parts = []
    for p in split_request(text):
        cands = match(p, reg, hints, top, text)
        inst = [c for c in cands if c["installed"]]
        pick = inst[0] if inst and inst[0]["score"] >= 0.5 * cands[0]["score"] else None
        suggest = [c for c in cands if not c["installed"]][:1]
        needs = hints.get(pick["skill"], {}).get("needs", []) if pick else []
        tools = []
        if pick:
            tools = [r for r in requirements_of(installed[pick["skill"]]["compatibility"]) if not have(r)]
        parts.append({"part": p, "level": level_of(p, len(inst) if len(inst) > 1 and inst[1]["score"] > 0.8 * inst[0]["score"] else 1),
                      "skill": pick["skill"] if pick else None, "confidence": pick["confidence"] if pick else None,
                      "matched": pick["matched"] if pick else [], "alternatives": [c["skill"] for c in inst[1:] if c["confidence"] != "low"],
                      "not_installed_suggestion": suggest[0]["skill"] if suggest else None,
                      "missing_inputs": missing_inputs(p, text, needs) if pick else [], "missing_tools": tools})
    order = list(dict.fromkeys(p["skill"] for p in parts if p["skill"]))
    return {"request": text, "parts": parts, "load": order,
            "chain": len(order) > 1, "unmatched": [p["part"] for p in parts if not p["skill"]]}


def render(r: dict) -> str:
    lines = [f"Request: {r['request']}", f"Parts: {len(r['parts'])}", ""]
    for i, p in enumerate(r["parts"], 1):
        lines.append(f"{i}. [{p['level']}] {p['part']}")
        if p["skill"]:
            lines.append(f"     skill: {p['skill']} ({p['confidence']} confidence; matched: {', '.join(p['matched'])})")
            if p["confidence"] == "low":
                lines.append("     LOW CONFIDENCE: read the skill's description and confirm with the user before loading")
            if p["alternatives"]:
                lines.append(f"     also consider: {', '.join(p['alternatives'])}")
            if p["missing_inputs"]:
                lines.append("     ASK THE USER FOR: " + "; ".join(p["missing_inputs"]))
            if p["missing_tools"]:
                lines.append("     missing tools: " + ", ".join(p["missing_tools"]))
        else:
            lines.append("     skill: none installed matches")
            if p["not_installed_suggestion"]:
                lines.append(f"     in the hub but not installed: {p['not_installed_suggestion']} (offer to install)")
    lines.append("")
    if r["load"]:
        lines.append("Load, in order: " + " -> ".join(r["load"]))
        if r["chain"]:
            lines.append("Several skills are needed: plan the hand-offs with the skill-orchestrator skill if installed.")
    else:
        lines.append("No installed skill fits. Answer directly, or use find-skills to search the hub.")
    if r["unmatched"]:
        lines.append("Handle directly (no skill): " + "; ".join(r["unmatched"]))
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("request", nargs="?", help="the user's request text")
    ap.add_argument("--file", type=Path, help="read the request from a file instead")
    ap.add_argument("--root", action="append", default=[], help="extra skills folder to scan (repeatable)")
    ap.add_argument("--no-default-roots", action="store_true", help="scan only the --root folders")
    ap.add_argument("--catalog", type=Path, help="hub catalog.json: also suggest skills that are not installed")
    ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    text = args.file.read_text(encoding="utf-8") if args.file else (args.request or "")
    if not text.strip():
        sys.exit("Give the request text, or --file FILE")
    reg = scan(args.root, not args.no_default_roots)
    catalog = args.catalog or (Path.cwd() / "catalog.json" if (Path.cwd() / "catalog.json").is_file() else None)
    if catalog:
        reg.update(load_catalog(catalog, reg))
    result = route(text, reg, load_hints(), args.top)
    print(json.dumps(result, indent=2) if args.json else render(result))


if __name__ == "__main__":
    main()
