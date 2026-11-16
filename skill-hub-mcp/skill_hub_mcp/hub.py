"""The skill-hub catalog: where it is read from (a local clone or GitHub), search, routing and file access.

Read-only. Standard library only (Python 3.8+).
"""
from __future__ import annotations

import json
import math
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = os.environ.get("SKILLHUB_REPO") or "NILANJAN-01/skill-hub"
MAX_FILE_BYTES = 200_000
MAX_FETCH_BYTES = 5_000_000
CACHE_SECONDS = 900
TEXT_SUFFIXES = {".md", ".txt", ".py", ".json", ".yml", ".yaml", ".toml", ".html", ".css", ".js", ".sh", ".csv",
                 ".ini", ".xml", ".kts", ".gradle", ""}
STOP = set("a an the to of in on for and or my i me how do does is it with can you please want need that this what "
           "when use using from be am are we our your so just get make have has".split())
# How much a word counts in each field of a skill.
FIELD_WEIGHTS = {"name": 4.0, "title": 3.0, "category": 1.5, "description": 1.0, "examples": 0.8}
SPLIT = re.compile(r"\s*(?:;|\n+|\b(?:and then|after that|and also|then|also)\b)\s*", re.I)


class HubError(Exception):
    """A problem the caller can understand and fix (unknown skill, bad path, no network)."""


# ------------------------------------------------------------------ sources
class LocalSource:
    kind = "local"

    def __init__(self, root):
        self.root = Path(root).resolve()
        if not (self.root / "catalog.json").is_file():
            raise HubError(f"no catalog.json in {self.root}")

    def describe(self):
        return f"local clone at {self.root}"

    def catalog(self):
        return json.loads((self.root / "catalog.json").read_text(encoding="utf-8"))

    def read(self, rel):
        skills = (self.root / "skills").resolve()
        path = (self.root / rel).resolve()
        if skills not in path.parents or not path.is_file():
            raise HubError(f"file not found: {rel}")
        if path.stat().st_size > MAX_FETCH_BYTES:
            raise HubError(f"file too large: {rel}")
        return path.read_bytes()

    def files(self, skill_path):
        base = (self.root / skill_path).resolve()
        return sorted(p.relative_to(base).as_posix() for p in base.rglob("*")
                      if p.is_file() and not p.is_symlink() and "__pycache__" not in p.parts)


class RemoteSource:
    kind = "remote"

    def __init__(self, repo=None, ref="main", timeout=20):
        self.repo, self.ref, self.timeout = repo or REPO, ref, timeout
        self._cache = {}

    def describe(self):
        return f"GitHub {self.repo}@{self.ref}"

    def fetch(self, url):
        hit = self._cache.get(url)
        if hit and time.time() - hit[0] < CACHE_SECONDS:
            return hit[1]
        req = urllib.request.Request(url, headers={"User-Agent": "skill-hub-mcp"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = resp.read(MAX_FETCH_BYTES + 1)
        except (urllib.error.URLError, OSError) as exc:
            raise HubError(f"could not fetch {url}: {exc}") from exc
        self._cache[url] = (time.time(), data)
        return data

    def raw(self, rel):
        return self.fetch(f"https://raw.githubusercontent.com/{self.repo}/{self.ref}/{rel}")

    def catalog(self):
        return json.loads(self.raw("catalog.json"))

    def read(self, rel):
        if not rel.startswith("skills/") or ".." in rel.split("/"):
            raise HubError(f"file not found: {rel}")
        return self.raw(rel)

    def files(self, skill_path):
        tree = json.loads(self.fetch(f"https://api.github.com/repos/{self.repo}/git/trees/{self.ref}?recursive=1"))
        prefix = skill_path.rstrip("/") + "/"
        return sorted(t["path"][len(prefix):] for t in tree.get("tree", [])
                      if t.get("type") == "blob" and t["path"].startswith(prefix))


def find_local_root(explicit=None):
    """--root if given, else SKILLHUB_ROOT, else the clone this file lives in. None if there is none."""
    candidates = [explicit] if explicit else [os.environ.get("SKILLHUB_ROOT"), Path(__file__).resolve().parents[2]]
    for cand in candidates:
        if cand and (Path(cand) / "catalog.json").is_file() and (Path(cand) / "skills").is_dir():
            return Path(cand)
    return None


def make_source(root=None, remote=False, ref="main"):
    if not remote:
        found = find_local_root(root)
        if found:
            return LocalSource(found)
        if root:
            raise HubError(f"{root} is not a skill-hub clone (no catalog.json and skills/)")
    return RemoteSource(ref=ref)


# ------------------------------------------------------------------ text
def stem(word):
    for suffix in ("ing", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) > len(suffix) + 2 and not word.endswith("ss"):
            word = word[:-len(suffix)]
            break
    if len(word) > 3 and word.endswith("e"):
        word = word[:-1]
    if len(word) > 3 and word[-1] == word[-2] and word[-1] not in "sl":
        word = word[:-1]
    return word


def words(text):
    return [stem(w) for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP]


def strip_frontmatter(text):
    m = re.match(r"\A---\r?\n.*?\r?\n---\r?\n", text, re.DOTALL)
    return text[m.end():] if m else text


# ------------------------------------------------------------------ catalog
class Hub:
    def __init__(self, source):
        self.source = source
        self._data, self._loaded = None, 0.0

    @property
    def data(self):
        if self._data is None or time.time() - self._loaded > CACHE_SECONDS:
            self._data, self._loaded = self.source.catalog(), time.time()
            self._by_name = {s["name"]: s for s in self._data["skills"]}
            self._index = self._build_index(self._data["skills"])
        return self._data

    @property
    def skills(self):
        return self.data["skills"]

    @property
    def version(self):
        return self.data.get("version", "")

    def get(self, name):
        self.data
        key = str(name).strip().lower()
        if key in self._by_name:
            return self._by_name[key]
        close = sorted(n for n in self._by_name if key and (key in n or n in key))[:5]
        raise HubError(f"unknown skill '{name}'." + (f" Did you mean: {', '.join(close)}?" if close
                                                      else " Use search_skills to find one."))

    # ---- search: BM25 over weighted fields
    @staticmethod
    def _build_index(skills):
        docs = {}
        for s in skills:
            fields = {"name": s["name"].replace("-", " "), "title": s.get("title", ""),
                      "category": s.get("category", "").replace("-", " "), "description": s.get("description", ""),
                      "examples": " ".join(s.get("examples", []))}
            freq = {}
            for field, text in fields.items():
                for w in words(text):
                    freq[w] = freq.get(w, 0.0) + FIELD_WEIGHTS[field]
            docs[s["name"]] = (freq, sum(freq.values()), set(words(fields["name"])))
        avg = sum(d[1] for d in docs.values()) / max(len(docs), 1)
        df = {}
        for freq, _, _ in docs.values():
            for w in freq:
                df[w] = df.get(w, 0) + 1
        return {"docs": docs, "avg": avg or 1.0, "df": df, "n": len(docs)}

    def search(self, query, category=None, limit=8):
        tokens = list(dict.fromkeys(words(query)))
        if not tokens:
            raise HubError("the query has no searchable words")
        self.data
        ix, k1, b = self._index, 1.4, 0.6
        hits = []
        for s in self.skills:
            if category and s.get("category") != category and category not in s.get("plugins", []):
                continue
            freq, length, name_words = ix["docs"][s["name"]]
            score, matched = 0.0, []
            for t in tokens:
                tf = freq.get(t, 0.0)
                if not tf:                                   # 'rebas' should still find 'rebasing'
                    tf = 0.5 * max((f for w, f in freq.items() if len(t) >= 4 and w.startswith(t)), default=0.0)
                if not tf:
                    continue
                idf = math.log(1 + (ix["n"] - ix["df"].get(t, 0) + 0.5) / (ix["df"].get(t, 0) + 0.5))
                score += idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * length / ix["avg"]))
                if t in name_words:
                    score += idf                             # a word in the skill's own name is a strong signal
                matched.append(t)
            if matched:
                score *= len(matched) / len(tokens) ** 0.5   # prefer skills that match more of the query
                hits.append((score, s, matched))
        hits.sort(key=lambda h: (-h[0], h[1]["name"]))
        return [{"name": s["name"], "title": s.get("title", ""), "category": s.get("category", ""),
                 "description": s.get("description", ""), "score": round(score, 2), "matched": matched}
                for score, s, matched in hits[:max(1, limit)]]

    def route(self, request, per_part=2):
        """Split a request into parts and pick skills for each one, in order."""
        parts = [p.strip(" .,") for p in SPLIT.split(request) if p and len(words(p)) >= 1]
        if not parts:
            raise HubError("the request has no searchable words")
        plan, order = [], []
        for i, part in enumerate(parts, 1):
            hits = self.search(part, limit=per_part)
            plan.append({"step": i, "part": part,
                         "skills": [{"name": h["name"], "title": h["title"], "score": h["score"]} for h in hits],
                         "note": "" if hits else "no skill matches this part; handle it without one"})
            if hits and hits[0]["name"] not in order:
                order.append(hits[0]["name"])
        return {"request": request, "parts": plan, "load_in_order": order,
                "next": "Read each skill with get_skill, in this order, and follow it for its part."
                        if order else "No skill matches; continue without one."}

    # ---- reading
    def skill_text(self, name):
        return self.source.read(f"{self.get(name)['path']}/SKILL.md").decode("utf-8", "replace")

    def files(self, name):
        return self.source.files(self.get(name)["path"])

    def read_file(self, name, rel):
        skill = self.get(name)
        if not isinstance(rel, str) or not rel or rel.startswith(("/", "\\")) or ":" in rel \
                or ".." in re.split(r"[\\/]", rel):
            raise HubError("path must be relative to the skill folder, for example references/checks.md")
        if Path(rel).suffix.lower() not in TEXT_SUFFIXES:
            raise HubError(f"'{rel}' is not a text file")
        raw = self.source.read(f"{skill['path']}/{rel.replace(chr(92), '/')}")
        text = raw[:MAX_FILE_BYTES].decode("utf-8", "replace")
        return text + (f"\n\n[truncated at {MAX_FILE_BYTES} bytes]" if len(raw) > MAX_FILE_BYTES else "")

    # ---- groupings
    def categories(self):
        return [{"name": c["name"], "title": c.get("title", c["name"]), "skills": c.get("count", 0)}
                for c in self.data.get("categories", [])]

    def plugins(self):
        return [{"name": p["name"], "category": p.get("category", ""), "description": p.get("description", ""),
                 "skills": p.get("skills", [])} for p in self.data.get("plugins", [])]

    def agents(self):
        return [{k: a.get(k) for k in ("id", "name", "project", "global", "docs")} for a in self.data.get("agents", [])]

    def targets(self, target):
        """Split 'a,b' into (plugin names, skill names); every name must exist."""
        skills, plugins = {s["name"] for s in self.skills}, {p["name"] for p in self.data.get("plugins", [])}
        chosen_plugins, chosen_skills = [], []
        for name in [t.strip() for t in str(target).split(",") if t.strip()]:
            if name in skills:
                chosen_skills.append(name)
            elif name in plugins:
                chosen_plugins.append(name)
            else:
                self.get(name)                 # raises with suggestions
        if not chosen_plugins and not chosen_skills:
            raise HubError("target is empty: give a skill or plugin name")
        return chosen_plugins, chosen_skills
