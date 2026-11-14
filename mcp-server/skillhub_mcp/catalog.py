"""Read-only access to the skill-hub catalog: sources (local clone or GitHub), search, files, install commands.

Standard library only (Python 3.8+).
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
CACHE_SECONDS = 900
STOP = {"a", "an", "the", "to", "of", "in", "on", "for", "and", "or", "my", "i", "me", "how", "do", "is", "it", "with",
        "can", "you", "please", "want", "need", "that", "this", "what", "when", "use", "using", "from", "be"}
TEXT_SUFFIXES = {".md", ".txt", ".py", ".json", ".yml", ".yaml", ".toml", ".html", ".css", ".js", ".sh", ".csv", ".ini", ""}


class CatalogError(Exception):
    """A problem the caller can understand and fix (unknown skill, bad path, no network)."""


# ------------------------------------------------------------------ sources
class LocalSource:
    kind = "local"

    def __init__(self, root):
        self.root = Path(root).resolve()
        if not (self.root / "catalog.json").is_file():
            raise CatalogError(f"no catalog.json in {self.root}")

    def describe(self):
        return f"local clone at {self.root}"

    def catalog(self):
        return json.loads((self.root / "catalog.json").read_text(encoding="utf-8"))

    def read(self, rel):
        path = (self.root / rel).resolve()
        skills = (self.root / "skills").resolve()
        if skills not in path.parents or not path.is_file():
            raise CatalogError(f"file not found: {rel}")
        if path.is_symlink() or path.stat().st_size > 5_000_000:
            raise CatalogError(f"file not readable: {rel}")
        return path.read_bytes()

    def list_files(self, skill_path):
        base = (self.root / skill_path).resolve()
        return sorted(p.relative_to(base).as_posix() for p in base.rglob("*")
                      if p.is_file() and not p.is_symlink() and "__pycache__" not in p.parts)


class RemoteSource:
    kind = "remote"

    def __init__(self, repo=REPO, ref="main", timeout=20):
        self.repo, self.ref, self.timeout = repo, ref, timeout
        self._cache = {}

    def describe(self):
        return f"GitHub {self.repo}@{self.ref}"

    def _get(self, url):
        hit = self._cache.get(url)
        if hit and time.time() - hit[0] < CACHE_SECONDS:
            return hit[1]
        req = urllib.request.Request(url, headers={"User-Agent": "skillhub-mcp"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = resp.read(5_000_001)
        except (urllib.error.URLError, OSError) as exc:
            raise CatalogError(f"could not fetch {url}: {exc}") from exc
        self._cache[url] = (time.time(), data)
        return data

    def catalog(self):
        return json.loads(self._get(f"https://raw.githubusercontent.com/{self.repo}/{self.ref}/catalog.json"))

    def read(self, rel):
        if not rel.startswith("skills/") or ".." in rel.split("/"):
            raise CatalogError(f"file not found: {rel}")
        return self._get(f"https://raw.githubusercontent.com/{self.repo}/{self.ref}/{rel}")

    def list_files(self, skill_path):
        tree = json.loads(self._get(f"https://api.github.com/repos/{self.repo}/git/trees/{self.ref}?recursive=1"))
        prefix = skill_path.rstrip("/") + "/"
        return sorted(t["path"][len(prefix):] for t in tree.get("tree", [])
                      if t.get("type") == "blob" and t["path"].startswith(prefix))


def find_local_root(explicit=None):
    """--root (must be valid), else SKILLHUB_ROOT, else the clone this file lives in."""
    if explicit:
        return Path(explicit) if (Path(explicit) / "catalog.json").is_file() else None
    for cand in (os.environ.get("SKILLHUB_ROOT"), Path(__file__).resolve().parents[2]):
        if cand and (Path(cand) / "catalog.json").is_file():
            return Path(cand)
    return None


def make_source(root=None, remote=False, ref="main"):
    if not remote:
        found = find_local_root(root)
        if found:
            return LocalSource(found)
        if root:
            raise CatalogError(f"no catalog.json in {root}")
    return RemoteSource(ref=ref)


# ------------------------------------------------------------------ catalog
def _stem(w):
    for suf in ("ing", "ed", "es", "s"):
        if w.endswith(suf) and len(w) > len(suf) + 2 and not w.endswith("ss"):
            w = w[:-len(suf)]
            break
    if len(w) > 3 and w.endswith("e"):
        w = w[:-1]
    if len(w) > 3 and w[-1] == w[-2] and w[-1] not in "sl":
        w = w[:-1]
    return w


def _words(text):
    return [_stem(w) for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP]


def split_frontmatter(text):
    m = re.match(r"\A---\r?\n.*?\r?\n---\r?\n", text, re.DOTALL)
    return text[m.end():] if m else text


class Catalog:
    def __init__(self, source):
        self.source = source
        self._data = None
        self._loaded_at = 0.0

    @property
    def data(self):
        if self._data is None or time.time() - self._loaded_at > CACHE_SECONDS:
            self._data = self.source.catalog()
            self._loaded_at = time.time()
            self._index = {s["name"]: s for s in self._data["skills"]}
        return self._data

    @property
    def skills(self):
        return self.data["skills"]

    def get(self, name):
        self.data
        key = name.strip().lower()
        if key in self._index:
            return self._index[key]
        close = [n for n in self._index if key in n][:5]
        raise CatalogError(f"unknown skill '{name}'" + (f". Did you mean: {', '.join(close)}?" if close else
                                                          ". Use search_skills to find one."))

    # ---- search
    def search(self, query, category=None, limit=8):
        tokens = _words(query)
        if not tokens:
            raise CatalogError("query has no searchable words")
        results = []
        fields = {s["name"]: (set(_words(s["name"].replace("-", " "))), set(_words(s.get("title", ""))),
                              set(_words(s["category"].replace("-", " "))), set(_words(s.get("description", ""))),
                              set(_words(" ".join(s.get("examples", []))))) for s in self.skills}
        n = len(self.skills)
        weight = {}
        for t in tokens:
            df = sum(1 for f in fields.values() if t in f[0] or t in f[1] or t in f[3])
            weight[t] = math.log(1 + n / max(df, 1))
        for s in self.skills:
            if category and s["category"] != category and category not in s.get("plugins", []):
                continue
            name_w, title_w, cat_w, desc_w, ex_w = fields[s["name"]]
            score, matched = 0.0, []
            for t in tokens:
                pts = 6 if t in name_w else 3 if any(w.startswith(t) for w in name_w) else 0
                pts += 4 if t in title_w else 0
                pts += 2 if t in cat_w else 0
                pts += 1.5 if t in desc_w else 0.5 if any(t in w for w in desc_w) else 0
                pts += 1 if t in ex_w else 0
                if pts:
                    score += pts * weight[t]
                    matched.append(t)
            if len(tokens) > 1 and " ".join(query.lower().split()) in s.get("description", "").lower():
                score += 3
            if score > 0:
                results.append((score, s, matched))
        results.sort(key=lambda r: (-r[0], r[1]["name"]))
        return [{"name": s["name"], "title": s.get("title", ""), "category": s["category"],
                 "description": s["description"], "score": round(sc, 1), "matched": m}
                for sc, s, m in results[:limit]]

    # ---- reading skills
    def skill_text(self, name):
        s = self.get(name)
        return self.source.read(f"{s['path']}/SKILL.md").decode("utf-8", "replace")

    def files(self, name):
        s = self.get(name)
        return self.source.list_files(s["path"])

    def read_file(self, name, rel):
        s = self.get(name)
        if not rel or rel.startswith(("/", "\\")) or ".." in re.split(r"[\\/]", rel) or ":" in rel:
            raise CatalogError("path must be relative to the skill folder, e.g. references/checks.md")
        if Path(rel).suffix.lower() not in TEXT_SUFFIXES:
            raise CatalogError(f"'{rel}' is not a text file")
        raw = self.source.read(f"{s['path']}/{rel.replace(chr(92), '/')}")
        truncated = len(raw) > MAX_FILE_BYTES
        text = raw[:MAX_FILE_BYTES].decode("utf-8", "replace")
        return text + (f"\n\n[truncated at {MAX_FILE_BYTES} bytes]" if truncated else "")

    # ---- groupings
    def categories(self):
        return [{"name": c["name"], "title": c.get("title", c["name"]), "count": c.get("count", 0)}
                for c in self.data.get("categories", [])]

    def plugins(self, category=None):
        return [{"name": p["name"], "category": p.get("category", ""), "description": p.get("description", ""),
                 "skills": p.get("skills", [])} for p in self.data.get("plugins", [])
                if not category or p.get("category") == category or p["name"] == category]

    def agents(self):
        return [{k: a.get(k) for k in ("id", "name", "project", "global", "native", "docs")} for a in self.data.get("agents", [])]

    # ---- install help (read-only: returns commands, never runs them)
    def install_commands(self, target, agent=None, use_global=False):
        names = {s["name"] for s in self.skills}
        plugin = next((p for p in self.data.get("plugins", []) if p["name"] == target), None)
        if target in names:
            kind, flag = "skill", "--skill"
        elif plugin:
            kind, flag = "plugin", "--plugin"
        else:
            self.get(target)  # raises with suggestions
            raise CatalogError(f"unknown skill or plugin '{target}'")
        repo = self.data.get("repository", f"https://github.com/{REPO}")
        slug = repo.split("github.com/")[-1]
        ag = None
        if agent:
            ag = next((a for a in self.data.get("agents", []) if a["id"] == agent or a["name"].lower() == agent.lower()), None)
            if not ag:
                raise CatalogError(f"unknown agent '{agent}'. Known: {', '.join(a['id'] for a in self.data.get('agents', []))}")
        cmds = [{"method": "installer (asks before writing)",
                 "command": f"python tools/install.py {flag} {target}" + (f" --agent {ag['id']}" if ag else "") +
                            (" --global" if use_global else "") + "   # run inside a clone of " + repo},
                {"method": "npx skills", "command": f"npx skills add {slug} --{kind} {target}"}]
        if ag and ag.get("native"):
            cmds.append({"method": f"{ag['name']} native", "command": ag["native"]})
        folder = None
        if ag:
            folder = ag.get("global") if use_global else ag.get("project")
        return {"target": target, "kind": kind, "agent": ag["name"] if ag else None, "skill_folder": folder, "commands": cmds}
