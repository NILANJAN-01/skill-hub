#!/usr/bin/env python3
"""Repo architecture: walk a repository and draw its architecture as ARCHITECTURE.md and architecture.html.

    analyze   scan the repository, find components, imports between them, entry points, build commands
              and dependencies; write model.json, annotations.json, ARCHITECTURE.md, architecture.html
    render    rebuild ARCHITECTURE.md and architecture.html from model.json + annotations.json
              (run it after you wrote descriptions into annotations.json)
    check     report what annotations.json still lacks (exit 1 if anything is missing)

Python 3.8+, standard library only. It reads files as text and never runs code from the repository.
The diagram is inline SVG (no network, no scripts); the Markdown carries a Mermaid copy of it.

    python repo_architecture.py analyze path/to/repo
    python repo_architecture.py analyze https://github.com/owner/project.git
    python repo_architecture.py render repo-architecture/project
    python repo_architecture.py check repo-architecture/project
"""
from __future__ import annotations

import argparse
import fnmatch
import html
import json
import math
import os
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile

TODO = "TODO(architecture)"
MAX_READ = 1_000_000
CONTAINER_DIRS = {"src", "lib", "app", "apps", "packages", "services", "modules", "cmd", "internal", "pkg",
                  "crates", "libs", "projects", "components", "plugins", "backend", "frontend", "server",
                  "client", "source", "sources", "main", "skills", "extensions"}
HARD_SKIP = {".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv", ".tox", ".mypy_cache",
             ".pytest_cache", ".ruff_cache", ".gradle", ".idea", ".dart_tool", ".next", ".nuxt", "DerivedData",
             "bower_components", ".terraform", "dist", "build", "target", "out", "vendor", "Pods", "coverage"}
BINARY_EXT = set("""png jpg jpeg gif bmp ico icns webp tif tiff psd heic avif mp3 wav ogg flac m4a aac mp4 mov mkv
webm avi wmv zip gz tgz bz2 xz 7z rar tar jar war aar apk aab ipa dex class pyc pyo so dll dylib exe bin o a lib
obj pdb wasm pdf doc docx xls xlsx ppt pptx odt ttf otf woff woff2 eot db sqlite sqlite3 mdb dat pack idx keystore
jks p12 pfx der crt cer""".split())
LOCKFILES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "cargo.lock", "poetry.lock", "pipfile.lock",
             "gemfile.lock", "composer.lock", "go.sum", "uv.lock", "pubspec.lock", "podfile.lock", "bun.lockb"}
SENSITIVE_NAMES = {".env", ".npmrc", ".netrc", ".pypirc", "id_rsa", "id_ed25519", "credentials", "credentials.json",
                   "secrets.json", "secrets.yml", "secrets.yaml", "local.properties"}
SENSITIVE_GLOBS = ["*.pem", "*.key", "*.p12", "*.pfx", "*.jks", "*.keystore", ".env.*", "*.tfvars"]
SAFE_SUFFIX = (".example", ".sample", ".template", ".dist")

LANG = {"py": "Python", "js": "JavaScript", "jsx": "JavaScript", "mjs": "JavaScript", "cjs": "JavaScript",
        "ts": "TypeScript", "tsx": "TypeScript", "java": "Java", "kt": "Kotlin", "kts": "Kotlin", "scala": "Scala",
        "go": "Go", "rs": "Rust", "cs": "C#", "c": "C", "h": "C", "cpp": "C++", "cc": "C++", "cxx": "C++",
        "hpp": "C++", "rb": "Ruby", "php": "PHP", "swift": "Swift", "dart": "Dart", "sh": "Shell",
        "bash": "Shell", "ps1": "PowerShell", "lua": "Lua", "r": "R", "vue": "Vue", "svelte": "Svelte"}
OTHER = {"md": "docs", "rst": "docs", "txt": "docs", "json": "config", "yml": "config", "yaml": "config",
         "toml": "config", "ini": "config", "cfg": "config", "xml": "config", "html": "web", "css": "web",
         "scss": "web", "sql": "data", "csv": "data"}
TEST_PARTS = {"test", "tests", "__tests__", "spec", "specs", "e2e", "androidtest", "unittests", "testing"}
DOC_PARTS = {"docs", "doc", "documentation"}
TOOL_PARTS = {"scripts", "tools", "bin", "ci", "devtools", ".devcontainer", "script"}
EXAMPLE_PARTS = {"examples", "example", "samples", "sample", "demo", "demos"}
CI_PARTS = {".github", ".gitlab", ".circleci", ".azure-pipelines", ".buildkite"}
PY_STDLIB_FALLBACK = set("""os sys re json math time datetime pathlib typing collections itertools functools io
subprocess argparse unittest logging random string shutil tempfile urllib http socket threading asyncio abc enum
dataclasses copy glob hashlib base64 struct csv sqlite3 zipfile tarfile gzip pickle traceback inspect textwrap
fnmatch posixpath ntpath platform ast html xml email secrets uuid warnings contextlib operator queue signal
stat errno codecs locale decimal fractions statistics heapq bisect array weakref types builtins""".split())
NODE_BUILTINS = set("""fs path os http https url util events stream crypto child_process zlib net dns readline
assert buffer process querystring string_decoder timers tty vm worker_threads cluster""".split())
KIND_ORDER = ["source", "web", "tests", "docs", "tooling", "ci", "examples", "config", "data"]


# ------------------------------------------------------------------ file discovery
def is_sensitive(name: str) -> bool:
    low = name.lower()
    if low.endswith(SAFE_SUFFIX):
        return False
    return low in SENSITIVE_NAMES or any(fnmatch.fnmatch(low, g) for g in SENSITIVE_GLOBS)


def list_files(root: str) -> list:
    out = []
    try:
        r = subprocess.run(["git", "-C", root, "ls-files", "-co", "--exclude-standard", "-z"],
                           capture_output=True, timeout=60)
        if r.returncode == 0 and r.stdout:
            out = [p for p in r.stdout.decode("utf-8", "replace").split("\0") if p]
    except (OSError, subprocess.SubprocessError):
        out = []
    if not out:
        for dp, dns, fns in os.walk(root):
            dns[:] = sorted(d for d in dns if d not in HARD_SKIP)
            for f in sorted(fns):
                out.append(os.path.relpath(os.path.join(dp, f), root).replace(os.sep, "/"))
    keep = []
    for p in out:
        parts = p.split("/")
        name = parts[-1]
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        full = os.path.join(root, *parts)
        if any(x in HARD_SKIP for x in parts[:-1]) or ext in BINARY_EXT or name.lower() in LOCKFILES:
            continue
        if is_sensitive(name) or os.path.islink(full) or not os.path.isfile(full):
            continue
        keep.append(p)
    return sorted(set(keep))


def read_text(root: str, rel: str) -> str:
    full = os.path.join(root, *rel.split("/"))
    try:
        if os.path.getsize(full) > MAX_READ:
            return ""
        with open(full, "rb") as fh:
            data = fh.read()
    except OSError:
        return ""
    if b"\0" in data[:4096]:
        return ""
    return data.decode("utf-8", "replace")


# ------------------------------------------------------------------ components
def component_dirs(files: list, depth: int) -> list:
    """Directories that count as components: top-level dirs, descending into container dirs."""
    dirs = set()
    for p in files:
        parts = p.split("/")[:-1]
        if not parts:
            continue
        n = 1
        while n < depth + 1 and n <= len(parts) and parts[n - 1].lower() in CONTAINER_DIRS and n < len(parts):
            n += 1
        dirs.add("/".join(parts[:n]))
    # a container dir with files directly inside it is its own component as well
    return sorted(dirs)


def make_comp_of(cdirs: list):
    ordered = sorted(cdirs, key=len, reverse=True)

    def comp_of(path: str) -> str:
        for d in ordered:
            if path == d or path.startswith(d + "/"):
                return d
        return "(root)"
    return comp_of


def guess_kind(cdir: str, exts: dict) -> str:
    parts = {x.lower() for x in cdir.split("/")}
    if parts & TEST_PARTS:
        return "tests"
    if parts & DOC_PARTS:
        return "docs"
    if parts & CI_PARTS:
        return "ci"
    if parts & EXAMPLE_PARTS:
        return "examples"
    if parts & TOOL_PARTS:
        return "tooling"
    code = sum(c for e, c in exts.items() if e in LANG)
    other = {}
    for e, c in exts.items():
        if e in OTHER:
            other[OTHER[e]] = other.get(OTHER[e], 0) + c
    if code and code >= max(other.values() or [0]):
        return "source"
    if other:
        return max(other, key=other.get)
    return "source" if code else "config"


# ------------------------------------------------------------------ import extraction
RE_PY = re.compile(r"^[ \t]*(?:from[ \t]+(\.*)([\w.]*)[ \t]+import[ \t]+([^\n#]+)|import[ \t]+([\w., \t]+))", re.M)
RE_JS = re.compile(r"""(?:\bimport\s+(?:[\w*{}\s,$]+?\s+from\s+)?|\bexport\s+[\w*{}\s,$]+?\s+from\s+|\brequire\(\s*|\bimport\(\s*)['"]([^'"\n]+)['"]""")
RE_JAVA = re.compile(r"^[ \t]*import[ \t]+(?:static[ \t]+)?([\w.]+)", re.M)
RE_JAVA_PKG = re.compile(r"^[ \t]*package[ \t]+([\w.]+)", re.M)
RE_CS_USING = re.compile(r"^[ \t]*using[ \t]+(?:static[ \t]+)?([\w.]+)[ \t]*;", re.M)
RE_CS_NS = re.compile(r"^[ \t]*namespace[ \t]+([\w.]+)", re.M)
RE_GO = re.compile(r'^[ \t]*(?:import[ \t]+)?(?:[\w.]+[ \t]+)?"([\w./\-~]+)"[ \t]*$', re.M)
RE_RS = re.compile(r"^[ \t]*(?:pub[ \t]+)?use[ \t]+([\w]+)::", re.M)
RE_C = re.compile(r'^[ \t]*#[ \t]*include[ \t]+"([^"\n]+)"', re.M)
RE_RB = re.compile(r"""^[ \t]*require_relative[ \t]+['"]([^'"\n]+)['"]""", re.M)

JS_EXT = {"js", "jsx", "mjs", "cjs", "ts", "tsx", "vue", "svelte"}


def norm_name(s: str) -> str:
    return re.sub(r"[-_.\s]", "", s.lower())


class Resolver:
    def __init__(self, files: list, root: str, comp_of, cdirs: list):
        self.files, self.fileset, self.root, self.comp_of = files, set(files), root, comp_of
        self.names = {}          # normalised component / package name -> component
        for d in cdirs:
            self.names.setdefault(norm_name(d.split("/")[-1]), d)
        self.pymods = {}         # dotted module -> component (None = ambiguous)
        self.packages = {}       # java/kotlin/c# package or namespace -> set(component)
        self.gomod = ""
        self.by_base = {}
        for p in files:
            self.by_base.setdefault(p.rsplit("/", 1)[-1], []).append(p)
        pydirs = {p.rsplit("/", 1)[0] for p in files if p.endswith("/__init__.py")}
        pydirs |= {"."} if "__init__.py" in self.fileset else set()
        for p in files:
            ext = p.rsplit(".", 1)[-1].lower() if "." in p else ""
            if ext == "py":
                self._index_py(p, pydirs)
            elif ext in ("java", "kt", "scala"):
                m = RE_JAVA_PKG.search(read_text(root, p))
                if m:
                    self.packages.setdefault(m.group(1), set()).add(comp_of(p))
            elif ext == "cs":
                for m in RE_CS_NS.finditer(read_text(root, p)):
                    self.packages.setdefault(m.group(1), set()).add(comp_of(p))
            elif p.endswith("package.json"):
                try:
                    name = json.loads(read_text(root, p)).get("name", "")
                except ValueError:
                    name = ""
                if name:
                    self.names[norm_name(name.split("/")[-1])] = comp_of(p)
                    self.names[norm_name(name)] = comp_of(p)
            elif p.endswith("go.mod") and p == "go.mod":
                m = re.search(r"^module[ \t]+(\S+)", read_text(root, p), re.M)
                self.gomod = m.group(1) if m else ""

    def _index_py(self, p: str, pydirs: set) -> None:
        segs = p[:-3].split("/")
        if segs[-1] == "__init__":
            segs = segs[:-1]
        if not segs:
            return
        comp = self.comp_of(p)
        for k in range(len(segs)):
            is_mod = k == len(segs) - 1
            is_pkg = "/".join(segs[:k + 1]) in pydirs or (k == 0 and "." in pydirs)
            if not (is_mod or is_pkg):
                continue
            name = ".".join(segs[k:])
            if self.pymods.get(name, comp) != comp:
                self.pymods[name] = None
            else:
                self.pymods[name] = comp

    def rel(self, file: str, spec: str):
        base = posixpath.normpath(posixpath.join(posixpath.dirname(file), spec))
        if base.startswith(".."):
            return None
        return self.comp_of(base + "/_")

    def imports(self, p: str, text: str):
        """Yield (component or None, external name or None) for each import in the file."""
        ext = p.rsplit(".", 1)[-1].lower() if "." in p else ""
        if ext == "py":
            yield from self._py(p, text)
        elif ext in JS_EXT:
            yield from self._js(p, text)
        elif ext in ("java", "kt", "scala"):
            for m in RE_JAVA.finditer(text):
                yield self._pkg(m.group(1), ("java.", "javax.", "kotlin.", "scala.", "android.", "androidx."))
        elif ext == "cs":
            for m in RE_CS_USING.finditer(text):
                yield self._pkg(m.group(1), ("System",))
        elif ext == "go":
            yield from self._go(text)
        elif ext == "rs":
            for m in RE_RS.finditer(text):
                n = m.group(1)
                if n in ("crate", "self", "super", "std", "core", "alloc"):
                    continue
                yield (self.names.get(norm_name(n)), None if norm_name(n) in self.names else n)
        elif ext in ("c", "h", "cpp", "cc", "cxx", "hpp"):
            for m in RE_C.finditer(text):
                yield self._c(p, m.group(1))
        elif ext == "rb":
            for m in RE_RB.finditer(text):
                yield (self.rel(p, m.group(1)), None)

    def _py(self, p, text):
        for m in RE_PY.finditer(text):
            dots, mod, names, plain = m.groups()
            if plain is not None:
                targets = [x.strip().split(" as ")[0].strip() for x in plain.split(",")]
                for t in targets:
                    if t:
                        yield self._pymod(t)
            elif dots:
                base = posixpath.dirname(p)
                for _ in range(len(dots) - 1):
                    base = posixpath.dirname(base)
                target = posixpath.join(base, mod.replace(".", "/")) if mod else base
                yield (self.comp_of(target + "/_"), None)
            else:
                yield self._pymod(mod)

    def _pymod(self, dotted: str):
        parts = dotted.split(".")
        for n in range(len(parts), 0, -1):
            name = ".".join(parts[:n])
            if name in self.pymods:
                return (self.pymods[name], None)
        top = parts[0]
        if top in getattr(sys, "stdlib_module_names", PY_STDLIB_FALLBACK) or top in PY_STDLIB_FALLBACK:
            return (None, None)
        if norm_name(top) in self.names:
            return (self.names[norm_name(top)], None)
        return (None, top)

    def _js(self, p, text):
        for m in RE_JS.finditer(text):
            spec = m.group(1)
            if spec.startswith("."):
                yield (self.rel(p, spec), None)
            elif spec.startswith(("@/", "~/")):
                rest = spec[2:]
                src_first = self.comp_of("src/" + rest + "/_")
                yield (src_first if src_first != "(root)" else self.comp_of(rest + "/_"), None)
            elif spec.startswith("node:") or spec in NODE_BUILTINS:
                continue
            else:
                segs = spec.split("/")
                name = "/".join(segs[:2]) if spec.startswith("@") and len(segs) > 1 else segs[0]
                key = norm_name(name.split("/")[-1])
                if norm_name(name) in self.names:
                    yield (self.names[norm_name(name)], None)
                elif key in self.names and spec.startswith("@"):
                    yield (self.names[key], None)
                else:
                    yield (None, name)

    def _pkg(self, name: str, skip: tuple):
        if name.startswith(skip):
            return (None, None)
        parts = name.split(".")
        for n in range(len(parts), 0, -1):
            comps = self.packages.get(".".join(parts[:n]))
            if comps:
                return (sorted(comps)[0], None)
        return (None, ".".join(parts[:2]))

    def _go(self, text):
        for m in RE_GO.finditer(text):
            path = m.group(1)
            if self.gomod and path.startswith(self.gomod):
                yield (self.comp_of(path[len(self.gomod):].lstrip("/") + "/_"), None)
            elif "." in path.split("/")[0]:
                yield (None, "/".join(path.split("/")[:3]))

    def _c(self, p, inc):
        cand = posixpath.normpath(posixpath.join(posixpath.dirname(p), inc))
        if cand in self.fileset:
            return (self.comp_of(cand), None)
        hits = self.by_base.get(inc.rsplit("/", 1)[-1], [])
        return (self.comp_of(hits[0]), None) if hits else (None, None)


# ------------------------------------------------------------------ facts: entry points, commands, dependencies
ENTRY_NAMES = {"main.py", "__main__.py", "app.py", "manage.py", "wsgi.py", "asgi.py", "server.py", "cli.py",
               "index.js", "index.ts", "main.js", "main.ts", "app.js", "app.ts", "server.js", "server.ts",
               "main.go", "main.rs", "lib.rs", "program.cs", "main.java", "main.kt", "mainactivity.kt",
               "mainactivity.java", "main.c", "main.cpp", "index.html", "dockerfile"}


def find_entry_points(files: list) -> list:
    out = []
    for p in files:
        low = p.rsplit("/", 1)[-1].lower()
        parts = p.split("/")
        if low in ENTRY_NAMES and len(parts) <= 4:
            out.append(p)
        elif len(parts) >= 2 and parts[0] in ("cmd", "bin") and len(parts) <= 3:
            out.append(p)
    return sorted(out)[:25]


def find_commands(root: str, files: list) -> list:
    cmds = []
    fs = set(files)
    if "package.json" in fs:
        try:
            scripts = json.loads(read_text(root, "package.json")).get("scripts", {})
        except ValueError:
            scripts = {}
        for k, v in list(scripts.items())[:15]:
            cmds.append({"command": f"npm run {k}", "does": str(v)[:100], "source": "package.json"})
    for mk in ("Makefile", "makefile"):
        if mk in fs:
            for m in re.finditer(r"^([A-Za-z][\w.-]*)[ \t]*:(?!=)", read_text(root, mk), re.M):
                cmds.append({"command": f"make {m.group(1)}", "does": "", "source": mk})
            break
    if "pyproject.toml" in fs:
        t = read_text(root, "pyproject.toml")
        sec = re.search(r"\[project\.scripts\]\n(.*?)(?=\n\[|\Z)", t, re.S)
        for m in re.finditer(r'^([\w.-]+)[ \t]*=[ \t]*"([^"]+)"', sec.group(1) if sec else "", re.M):
            cmds.append({"command": m.group(1), "does": "entry point " + m.group(2), "source": "pyproject.toml"})
    for f in ("gradlew", "gradlew.bat"):
        if f in fs:
            cmds.append({"command": "./gradlew build", "does": "Gradle wrapper build", "source": f})
            break
    for f, c in (("go.mod", "go build ./..."), ("Cargo.toml", "cargo build"), ("pom.xml", "mvn package")):
        if f in fs:
            cmds.append({"command": c, "does": "", "source": f})
    if any(p.endswith(".csproj") or p.endswith(".sln") for p in fs):
        cmds.append({"command": "dotnet build", "does": "", "source": "*.sln / *.csproj"})
    if any(p.lower() == "dockerfile" for p in fs):
        cmds.append({"command": "docker build .", "does": "image build", "source": "Dockerfile"})
    return cmds[:30]


def find_dependencies(root: str, files: list) -> list:
    deps = []

    def add(src, kind, names):
        names = [n for n in dict.fromkeys(names) if n]
        if names:
            deps.append({"manifest": src, "ecosystem": kind, "packages": names[:60], "total": len(names)})
    for p in files:
        low = p.rsplit("/", 1)[-1].lower()
        if len(p.split("/")) > 3:
            continue
        if low == "package.json":
            try:
                d = json.loads(read_text(root, p))
            except ValueError:
                continue
            add(p, "npm", list(d.get("dependencies", {})) + list(d.get("devDependencies", {})))
        elif re.fullmatch(r"requirements[\w.-]*\.txt", low):
            add(p, "pip", [re.split(r"[<>=!~;\[ ]", ln.strip())[0] for ln in read_text(root, p).splitlines()
                           if ln.strip() and not ln.startswith(("#", "-"))])
        elif low == "pyproject.toml":
            t = read_text(root, p)
            m = re.search(r"^dependencies[ \t]*=[ \t]*\[(.*?)\]", t, re.S | re.M)
            add(p, "pip", [re.split(r"[<>=!~;\[ ]", x)[0] for x in re.findall(r'"([^"]+)"', m.group(1))] if m else [])
        elif low == "go.mod":
            add(p, "go", re.findall(r"^[ \t]*(?:require[ \t]+)?([\w.\-]+\.[\w.\-]+/[\w./\-]+)[ \t]+v", read_text(root, p), re.M))
        elif low == "cargo.toml":
            m = re.search(r"\[dependencies\]\n(.*?)(?=\n\[|\Z)", read_text(root, p), re.S)
            add(p, "cargo", re.findall(r"^([\w-]+)[ \t]*=", m.group(1), re.M) if m else [])
        elif low in ("build.gradle", "build.gradle.kts"):
            add(p, "gradle", re.findall(r"""(?:implementation|api|compileOnly|runtimeOnly|testImplementation|kapt|ksp)\s*\(?\s*["']([^"':]+:[^"':]+)""", read_text(root, p)))
        elif low == "pom.xml":
            add(p, "maven", re.findall(r"<artifactId>([^<]+)</artifactId>", read_text(root, p)))
        elif low.endswith(".csproj"):
            add(p, "nuget", re.findall(r'PackageReference\s+Include="([^"]+)"', read_text(root, p)))
        elif low == "gemfile":
            add(p, "gem", re.findall(r"^\s*gem\s+['\"]([^'\"]+)", read_text(root, p), re.M))
        elif low == "composer.json":
            try:
                add(p, "composer", list(json.loads(read_text(root, p)).get("require", {})))
            except ValueError:
                pass
    return deps


def find_ci(files: list) -> list:
    return sorted(p for p in files if p.startswith((".github/workflows/", ".circleci/", ".buildkite/"))
                  or p in (".gitlab-ci.yml", "azure-pipelines.yml", "Jenkinsfile", "bitbucket-pipelines.yml"))[:20]


# ------------------------------------------------------------------ analysis
def analyze_repo(root: str, depth: int = 2) -> dict:
    files = list_files(root)
    if not files:
        raise SystemExit("error: no readable files found")
    cdirs = component_dirs(files, depth)
    comp_of = make_comp_of(cdirs)
    res = Resolver(files, root, comp_of, cdirs)
    comps = {}
    texts = {}
    for p in files:
        c = comp_of(p)
        e = comps.setdefault(c, {"name": c, "files": 0, "lines": 0, "exts": {}, "langs": {}, "samples": []})
        ext = p.rsplit(".", 1)[-1].lower() if "." in p else ""
        e["files"] += 1
        e["exts"][ext] = e["exts"].get(ext, 0) + 1
        text = read_text(root, p) if (ext in LANG or ext in OTHER) else ""
        n = text.count("\n") + (1 if text else 0)
        e["lines"] += n
        if ext in LANG:
            e["langs"][LANG[ext]] = e["langs"].get(LANG[ext], 0) + n
            texts[p] = text
        e["samples"].append((p, n))
    edges, ext_use = {}, {}
    for p, text in texts.items():
        a = comp_of(p)
        for target, outside in res.imports(p, text):
            if target and target != a:
                edges[(a, target)] = edges.get((a, target), 0) + 1
            elif outside:
                ext_use.setdefault(outside, {})
                ext_use[outside][a] = ext_use[outside].get(a, 0) + 1
    components = []
    for name, e in sorted(comps.items()):
        key = [s for s, _ in e["samples"] if re.search(r"(^|/)(readme|index|main|__init__|app|mod|lib)\.[\w]+$", s.lower())]
        src = [(s, n) for s, n in e["samples"] if s.rsplit(".", 1)[-1].lower() in LANG]
        pick = (key or [s for s, _ in sorted(src, key=lambda x: -x[1])] or [s for s, _ in e["samples"]])[:3]
        langs = sorted(e["langs"].items(), key=lambda x: -x[1])
        components.append({"name": name, "kind": guess_kind(name, e["exts"]), "files": e["files"],
                           "lines": e["lines"], "language": langs[0][0] if langs else "",
                           "key_files": pick})
    names = {c["name"] for c in components}
    elist = sorted(({"from": a, "to": b, "count": n} for (a, b), n in edges.items()
                    if a in names and b in names), key=lambda x: (-x["count"], x["from"], x["to"]))
    externals = sorted(({"name": n, "count": sum(u.values()), "used_by": sorted(u, key=lambda k: -u[k])[:5]}
                        for n, u in ext_use.items()), key=lambda x: (-x["count"], x["name"]))[:40]
    langs_total = {}
    for c in comps.values():
        for k, v in c["langs"].items():
            langs_total[k] = langs_total.get(k, 0) + v
    model = {"name": os.path.basename(os.path.abspath(root)) or "repo", "files": len(files),
             "lines": sum(c["lines"] for c in comps.values()), "languages": dict(sorted(langs_total.items(), key=lambda x: -x[1])),
             "components": components, "edges": elist, "externals": externals,
             "entry_points": find_entry_points(files), "commands": find_commands(root, files),
             "dependencies": find_dependencies(root, files), "ci": find_ci(files),
             "docs": [p for p in files if "/" not in p and p.lower().rsplit(".", 1)[0] in
                      ("readme", "contributing", "architecture", "agents", "claude", "changelog", "guide", "security")]}
    model["layers"] = compute_layers(model)
    return model


def compute_layers(model: dict) -> dict:
    """Layer 0 = nothing depends on it (apps, entry points); deeper layers are what others build on."""
    names = [c["name"] for c in model["components"]]
    level = {n: 0 for n in names}
    for _ in range(len(names) + 1):
        changed = False
        for e in model["edges"]:
            if level[e["to"]] < level[e["from"]] + 1 and level[e["from"]] + 1 < len(names):
                level[e["to"]] = level[e["from"]] + 1
                changed = True
        if not changed:
            break
    return level


# ------------------------------------------------------------------ annotations
def new_annotations(model: dict) -> dict:
    return {"summary": TODO + ": one paragraph: what this repository is, who uses it, how it is built",
            "components": {c["name"]: {"title": "", "description": TODO + ": what this component does and why it exists"}
                           for c in model["components"]},
            "flows": [{"title": TODO + ": name of a main flow, e.g. a request, a build, a command",
                       "steps": [TODO + ": step 1 (component, file, function)"]}],
            "notes": []}


def load_annotations(out: str, model: dict) -> dict:
    path = os.path.join(out, "annotations.json")
    ann = new_annotations(model)
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as fh:
                have = json.load(fh)
        except ValueError as e:
            raise SystemExit(f"error: annotations.json is not valid JSON: {e}")
        ann["summary"] = have.get("summary", ann["summary"])
        ann["flows"] = have.get("flows", ann["flows"])
        ann["notes"] = have.get("notes", [])
        for k, v in (have.get("components") or {}).items():
            if k in ann["components"] and isinstance(v, dict):
                ann["components"][k].update(v)
    return ann


def missing(model: dict, ann: dict) -> list:
    out = []
    if not ann["summary"].strip() or TODO in ann["summary"]:
        out.append("summary")
    for c in model["components"]:
        d = ann["components"].get(c["name"], {}).get("description", "")
        if not d.strip() or TODO in d:
            out.append("component " + c["name"])
    flows = [f for f in ann["flows"] if TODO not in json.dumps(f) and f.get("steps")]
    if not flows:
        out.append("at least one flow")
    return out


# ------------------------------------------------------------------ rendering
def esc(s) -> str:
    return html.escape(str(s), quote=True)


def mm(s: str) -> str:
    return re.sub(r'["\[\]{}()<>|]', "'", str(s))


def md_cell(s) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def tour_order(model: dict) -> list:
    return sorted(model["components"], key=lambda c: (model["layers"].get(c["name"], 0), c["name"]))


MAX_NODES = 30


def shown(model: dict, limit: int = MAX_NODES) -> list:
    """The components worth drawing: code first, then the most connected, then the biggest."""
    comps = model["components"]
    if len(comps) <= limit:
        return comps
    deg = {}
    for e in model["edges"]:
        deg[e["from"]] = deg.get(e["from"], 0) + 1
        deg[e["to"]] = deg.get(e["to"], 0) + 1

    def score(c):
        return ((10 ** 7 if c["kind"] in ("source", "web") else 0) + deg.get(c["name"], 0) * 10 ** 4 + c["lines"], c["name"])
    keep = {c["name"] for c in sorted(comps, key=score, reverse=True)[:limit]}
    return [c for c in comps if c["name"] in keep]


def mermaid(model: dict, max_edges: int = 40) -> str:
    comps = shown(model)
    idx = {c["name"]: f"n{i}" for i, c in enumerate(comps)}
    lines = ["flowchart TD"]
    for c in comps:
        lines.append(f'    {idx[c["name"]]}["{mm(c["name"])}<br/>{c["files"]} files, {c["lines"]} lines"]')
    for e in [e for e in model["edges"] if e["from"] in idx and e["to"] in idx][:max_edges]:
        lines.append(f'    {idx[e["from"]]} -->|{e["count"]}| {idx[e["to"]]}')
    ext = [x for x in model["externals"] if x["count"] >= 2][:8]
    if ext:
        lines.append('    subgraph EXT["External packages"]')
        for i, x in enumerate(ext):
            lines.append(f'        x{i}["{mm(x["name"])}"]')
        lines.append("    end")
        for i, x in enumerate(ext):
            for u in x["used_by"][:2]:
                if u in idx:
                    lines.append(f"    {idx[u]} -.-> x{i}")
    return "\n".join(lines)


KIND_CLASS = {"source": "k-src", "web": "k-web", "tests": "k-test", "docs": "k-doc", "tooling": "k-tool",
              "ci": "k-tool", "examples": "k-doc", "config": "k-cfg", "data": "k-cfg"}


def svg_diagram(model: dict, ann: dict, per_row: int = 5, max_edges: int = 45) -> str:
    drawn = {c["name"] for c in shown(model)}
    comps = [c for c in tour_order(model) if c["name"] in drawn]
    bw, bh, gx, gy, pad = 200, 62, 36, 92, 30
    rows = []
    by_layer = {}
    for c in comps:
        by_layer.setdefault(model["layers"].get(c["name"], 0), []).append(c)
    for layer in sorted(by_layer):
        items = by_layer[layer]
        for i in range(0, len(items), per_row):
            rows.append((layer, items[i:i + per_row]))
    width = pad * 2 + per_row * bw + (per_row - 1) * gx
    pos = {}
    for r, (_, items) in enumerate(rows):
        rw = len(items) * bw + (len(items) - 1) * gx
        x0 = (width - rw) / 2
        for i, c in enumerate(items):
            pos[c["name"]] = (x0 + i * (bw + gx), pad + 20 + r * (bh + gy))
    ext = [x for x in model["externals"] if x["count"] >= 2][:10]
    y_ext = pad + 20 + len(rows) * (bh + gy)
    height = y_ext + (70 if ext else 0) + pad
    out = [f'<svg viewBox="0 0 {int(width)} {int(height)}" role="img" aria-label="Architecture diagram of {esc(model["name"])}" '
           f'xmlns="http://www.w3.org/2000/svg"><defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" '
           f'markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" class="arrow"/></marker></defs>']
    more = len(model["components"]) - len(comps)
    out.append('<text x="12" y="18" class="cap">top: entry points and apps; lower: code the others build on'
               + (f" · {more} smaller components are not drawn (see the table)" if more else "") + "</text>")
    for e in model["edges"][:max_edges]:
        if e["from"] not in pos or e["to"] not in pos:
            continue
        (x1, y1), (x2, y2) = pos[e["from"]], pos[e["to"]]
        sw = round(1 + math.log(e["count"], 2) * 0.6, 2)
        tip = f'{esc(e["from"])} imports {esc(e["to"])} ({e["count"]}x)'
        if abs(y1 - y2) < 1:
            ax, bx = x1 + bw / 2, x2 + bw / 2
            d = f"M{ax:.0f} {y1:.0f} C{ax:.0f} {y1 - 46:.0f} {bx:.0f} {y1 - 46:.0f} {bx:.0f} {y1:.0f}"
        elif y2 > y1:
            ax, ay, bx, by = x1 + bw / 2, y1 + bh, x2 + bw / 2, y2
            d = f"M{ax:.0f} {ay:.0f} C{ax:.0f} {(ay + by) / 2:.0f} {bx:.0f} {(ay + by) / 2:.0f} {bx:.0f} {by:.0f}"
        else:
            ax, ay, bx, by = x1 + bw / 2, y1, x2 + bw / 2, y2 + bh
            d = f"M{ax:.0f} {ay:.0f} C{ax - 60:.0f} {ay - 50:.0f} {bx - 60:.0f} {by + 50:.0f} {bx:.0f} {by:.0f}"
        out.append(f'<path d="{d}" class="edge" stroke-width="{sw}" marker-end="url(#arr)"><title>{tip}</title></path>')
    for c in comps:
        x, y = pos[c["name"]]
        a = ann["components"].get(c["name"], {})
        desc = a.get("description", "")
        title = a.get("title") or c["name"]
        tip = f'{c["name"]}: {c["files"]} files, {c["lines"]} lines' + ("" if not desc or TODO in desc else ". " + desc)
        label = c["name"] if len(c["name"]) <= 26 else "…" + c["name"][-25:]
        sub = f'{c["files"]} files · {c["lines"]} lines' + (f' · {c["language"]}' if c["language"] else "")
        out.append(f'<g class="node {KIND_CLASS.get(c["kind"], "k-src")}"><title>{esc(tip)}</title>'
                   f'<rect x="{x:.0f}" y="{y:.0f}" width="{bw}" height="{bh}" rx="8"/>'
                   f'<text x="{x + bw / 2:.0f}" y="{y + 26:.0f}" class="nm" text-anchor="middle">{esc(label)}</text>'
                   f'<text x="{x + bw / 2:.0f}" y="{y + 46:.0f}" class="sb" text-anchor="middle">{esc(sub if title == c["name"] else title)}</text></g>')
    if ext:
        n = len(ext)
        ew, eg = 130, 16
        x0 = max(pad, (width - (n * ew + (n - 1) * eg)) / 2)
        out.append(f'<text x="12" y="{y_ext - 8:.0f}" class="cap">external packages (dashed = used by)</text>')
        for i, x in enumerate(ext):
            ex = x0 + i * (ew + eg)
            for u in x["used_by"][:2]:
                if u in pos:
                    ux, uy = pos[u]
                    out.append(f'<path d="M{ux + bw / 2:.0f} {uy + bh:.0f} L{ex + ew / 2:.0f} {y_ext:.0f}" class="ext-edge"/>')
            lab = x["name"] if len(x["name"]) <= 17 else x["name"][:16] + "…"
            out.append(f'<g class="node k-ext"><title>{esc(x["name"])}: {x["count"]} imports</title>'
                       f'<rect x="{ex:.0f}" y="{y_ext:.0f}" width="{ew}" height="34" rx="17"/>'
                       f'<text x="{ex + ew / 2:.0f}" y="{y_ext + 21:.0f}" class="sb" text-anchor="middle">{esc(lab)}</text></g>')
    out.append("</svg>")
    return "".join(out)


def depends_maps(model: dict):
    out, inn = {}, {}
    for e in model["edges"]:
        out.setdefault(e["from"], []).append(e["to"])
        inn.setdefault(e["to"], []).append(e["from"])
    return out, inn


def render_md(model: dict, ann: dict) -> str:
    out_, in_ = depends_maps(model)
    L = [f"# Architecture of {model['name']}", "",
         "> Generated by `repo_architecture.py` from the code, then described by a reader. Edges count imports between components; "
         "they show what the code references, not run-time behaviour.", "",
         "## Overview", "", ann["summary"], "",
         "## At a glance", "",
         f"- **Files / lines scanned:** {model['files']} / {model['lines']}",
         "- **Languages:** " + (", ".join(f"{k} ({v} lines)" for k, v in list(model["languages"].items())[:6]) or "none detected"),
         f"- **Components:** {len(model['components'])}  ·  **Dependencies between them:** {len(model['edges'])}",
         "- **Entry points:** " + (", ".join(f"`{p}`" for p in model["entry_points"][:8]) or "none found"),
         "- **CI:** " + (", ".join(f"`{p}`" for p in model["ci"][:6]) or "none found"), "",
         "## Diagram", "",
         "Boxes are components (folders); an arrow means *imports*. The layered picture is in `architecture.html`.", "",
         "```mermaid", mermaid(model), "```", "",
         "## Components", "",
         "| Component | Kind | Files | Lines | What it is | Depends on | Used by |", "|---|---|---|---|---|---|---|"]
    for c in tour_order(model):
        a = ann["components"].get(c["name"], {})
        L.append("| `{}` | {} | {} | {} | {} | {} | {} |".format(
            c["name"], c["kind"], c["files"], c["lines"], md_cell(a.get("description", "")),
            ", ".join(f"`{x}`" for x in out_.get(c["name"], [])) or "–",
            ", ".join(f"`{x}`" for x in in_.get(c["name"], [])) or "–"))
    L += ["", "## Walkthrough: where to read first", ""]
    n = 1
    for d in model["docs"][:3]:
        L.append(f"{n}. `{d}`: project documents."); n += 1
    if model["entry_points"]:
        L.append(f"{n}. Entry points: " + ", ".join(f"`{p}`" for p in model["entry_points"][:5]) + "."); n += 1
    for c in tour_order(model):
        if c["kind"] in ("source", "web", "tooling"):
            a = ann["components"].get(c["name"], {})
            kf = ", ".join(f"`{k}`" for k in c["key_files"][:2])
            L.append(f"{n}. `{c['name']}`: start with {kf}. {a.get('title', '')}".rstrip()); n += 1
    L += ["", "## Main flows", ""]
    for f in ann["flows"]:
        L.append(f"### {f.get('title', '')}")
        L.append("")
        for i, s in enumerate(f.get("steps", []), 1):
            L.append(f"{i}. {s}")
        L.append("")
    L += ["## Build, run and test", ""]
    if model["commands"]:
        L += ["| Command | Notes | Found in |", "|---|---|---|"]
        for c in model["commands"]:
            L.append(f"| `{md_cell(c['command'])}` | {md_cell(c['does'])} | `{c['source']}` |")
    else:
        L.append("No build commands were found automatically.")
    L += ["", "## External dependencies", ""]
    if model["dependencies"]:
        for d in model["dependencies"]:
            more = "" if d["total"] <= len(d["packages"]) else f" (+{d['total'] - len(d['packages'])} more)"
            L.append(f"- `{d['manifest']}` ({d['ecosystem']}): " + ", ".join(d["packages"][:25]) + more)
    else:
        L.append("No manifests found.")
    if model["externals"]:
        L += ["", "Most imported outside packages: " + ", ".join(f"`{x['name']}` ({x['count']})" for x in model["externals"][:12]) + "."]
    if ann["notes"]:
        L += ["", "## Notes and risks", ""] + [f"- {x}" for x in ann["notes"]]
    return "\n".join(L).rstrip() + "\n"


CSS = """
:root{--bg:#fff;--fg:#1c2128;--mut:#59636e;--line:#d1d9e0;--card:#f6f8fa;--edge:#6e7781;--src:#dbeafe;--web:#ccfbf1;--test:#e5e7eb;--doc:#dcfce7;--tool:#ffedd5;--cfg:#ede9fe;--ext:#fef9c3;--stroke:#57606a}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#0d1117;--fg:#e6edf3;--mut:#9198a1;--line:#30363d;--card:#161b22;--edge:#8b949e;--src:#1e3a5f;--web:#134e4a;--test:#2d333b;--doc:#14532d;--tool:#5a3510;--cfg:#3b2a63;--ext:#4a4210;--stroke:#8b949e}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 system-ui,Segoe UI,sans-serif}
main{max-width:1180px;margin:0 auto;padding:24px 16px 64px}h1{font-size:1.7rem;margin:.2em 0}h2{margin:1.8em 0 .5em;font-size:1.2rem;border-bottom:1px solid var(--line);padding-bottom:.25em}
.mut{color:var(--mut)}.stats{display:flex;flex-wrap:wrap;gap:10px;margin:14px 0}.stat{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px 14px}.stat b{display:block;font-size:1.3rem}
.diagram{overflow-x:auto;border:1px solid var(--line);border-radius:10px;background:var(--card);padding:8px}svg{width:100%;min-width:640px;height:auto;display:block}
.node rect{stroke:var(--stroke);stroke-width:1.2}.k-src rect{fill:var(--src)}.k-web rect{fill:var(--web)}.k-test rect{fill:var(--test)}.k-doc rect{fill:var(--doc)}.k-tool rect{fill:var(--tool)}.k-cfg rect{fill:var(--cfg)}.k-ext rect{fill:var(--ext);stroke-dasharray:4 3}
.nm{font:600 13px system-ui,sans-serif;fill:var(--fg)}.sb{font:11.5px system-ui,sans-serif;fill:var(--mut)}.cap{font:11px system-ui,sans-serif;fill:var(--mut)}
.edge{fill:none;stroke:var(--edge);opacity:.55}.edge:hover{opacity:1;stroke:#d1242f}.ext-edge{stroke:var(--edge);stroke-dasharray:3 4;opacity:.45;fill:none}.arrow{fill:var(--edge)}
.legend{display:flex;flex-wrap:wrap;gap:14px;font-size:.85rem;margin:10px 0}.legend i{display:inline-block;width:14px;height:14px;border-radius:3px;border:1px solid var(--stroke);vertical-align:-2px;margin-right:5px}
table{border-collapse:collapse;width:100%;font-size:.9rem}th,td{border:1px solid var(--line);padding:6px 9px;text-align:left;vertical-align:top}th{background:var(--card)}
code{background:var(--card);padding:1px 5px;border-radius:4px;font-size:.88em}pre{background:var(--card);border:1px solid var(--line);padding:12px;border-radius:8px;overflow:auto}
.tablewrap{overflow-x:auto}details{margin:10px 0}summary{cursor:pointer}ol li,ul li{margin:.2em 0}
"""


def render_html(model: dict, ann: dict) -> str:
    out_, in_ = depends_maps(model)
    rows = []
    for c in tour_order(model):
        a = ann["components"].get(c["name"], {})
        rows.append("<tr><td><code>{}</code></td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            esc(c["name"]), esc(c["kind"]), c["files"], c["lines"], esc(a.get("description", "")),
            ", ".join(f"<code>{esc(x)}</code>" for x in out_.get(c["name"], [])) or "–",
            ", ".join(f"<code>{esc(x)}</code>" for x in in_.get(c["name"], [])) or "–"))
    tour = []
    for d in model["docs"][:3]:
        tour.append(f"<li><code>{esc(d)}</code>: project documents.</li>")
    if model["entry_points"]:
        tour.append("<li>Entry points: " + ", ".join(f"<code>{esc(p)}</code>" for p in model["entry_points"][:5]) + ".</li>")
    for c in tour_order(model):
        if c["kind"] in ("source", "web", "tooling"):
            a = ann["components"].get(c["name"], {})
            tour.append(f"<li><code>{esc(c['name'])}</code>: start with " +
                        ", ".join(f"<code>{esc(k)}</code>" for k in c["key_files"][:2]) + f". {esc(a.get('title', ''))}</li>")
    flows = "".join(f"<h3>{esc(f.get('title', ''))}</h3><ol>" + "".join(f"<li>{esc(s)}</li>" for s in f.get("steps", [])) + "</ol>"
                    for f in ann["flows"])
    cmds = ("<div class=tablewrap><table><tr><th>Command</th><th>Notes</th><th>Found in</th></tr>" +
            "".join(f"<tr><td><code>{esc(c['command'])}</code></td><td>{esc(c['does'])}</td><td><code>{esc(c['source'])}</code></td></tr>"
                    for c in model["commands"]) + "</table></div>") if model["commands"] else "<p class=mut>None found automatically.</p>"
    deps = "".join(f"<li><code>{esc(d['manifest'])}</code> ({esc(d['ecosystem'])}): {esc(', '.join(d['packages'][:25]))}"
                   + (f" (+{d['total'] - len(d['packages'])} more)" if d["total"] > len(d["packages"]) else "") + "</li>"
                   for d in model["dependencies"]) or "<li class=mut>No manifests found.</li>"
    notes = ("<h2>Notes and risks</h2><ul>" + "".join(f"<li>{esc(n)}</li>" for n in ann["notes"]) + "</ul>") if ann["notes"] else ""
    langs = ", ".join(f"{esc(k)} ({v})" for k, v in list(model["languages"].items())[:6])
    legend = "".join(f'<span><i style="background:var(--{v})"></i>{k}</span>' for k, v in
                     (("source", "src"), ("web", "web"), ("tests", "test"), ("docs / examples", "doc"),
                      ("tooling / CI", "tool"), ("config / data", "cfg"), ("external package", "ext")))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Architecture of {esc(model['name'])}</title><style>{CSS}</style></head>
<body><main>
<h1>Architecture of {esc(model['name'])}</h1>
<p class="mut">Generated from the code by <code>repo_architecture.py</code>. Arrows mean "imports"; they show what the code references, not run-time behaviour.</p>
<p>{esc(ann['summary'])}</p>
<div class="stats"><div class="stat"><b>{model['files']}</b>files</div><div class="stat"><b>{model['lines']}</b>lines</div>
<div class="stat"><b>{len(model['components'])}</b>components</div><div class="stat"><b>{len(model['edges'])}</b>dependencies</div></div>
<p class="mut">Languages: {langs or 'none detected'}</p>
<h2>Diagram</h2><div class="legend">{legend}</div>
<div class="diagram">{svg_diagram(model, ann)}</div>
<details><summary>Mermaid source (paste into any Mermaid renderer)</summary><pre>{esc(mermaid(model))}</pre></details>
<h2>Components</h2><div class="tablewrap"><table><tr><th>Component</th><th>Kind</th><th>Files</th><th>Lines</th><th>What it is</th><th>Depends on</th><th>Used by</th></tr>{''.join(rows)}</table></div>
<h2>Walkthrough: where to read first</h2><ol>{''.join(tour)}</ol>
<h2>Main flows</h2>{flows}
<h2>Build, run and test</h2>{cmds}
<h2>External dependencies</h2><ul>{deps}</ul>{notes}
</main></body></html>
"""


# ------------------------------------------------------------------ commands
def write(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def load_model(out: str) -> dict:
    path = os.path.join(out, "model.json")
    if not os.path.isfile(path):
        raise SystemExit(f"error: {path} not found; run analyze first")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def do_render(out: str, model: dict) -> None:
    ann = load_annotations(out, model)
    write(os.path.join(out, "annotations.json"), json.dumps(ann, indent=2, ensure_ascii=False) + "\n")
    write(os.path.join(out, "ARCHITECTURE.md"), render_md(model, ann))
    write(os.path.join(out, "architecture.html"), render_html(model, ann))
    todo = missing(model, ann)
    print(f"wrote {out}/ARCHITECTURE.md and {out}/architecture.html")
    print(f"still to describe: {len(todo)} item(s)" if todo else "all components and flows are described")


def cmd_analyze(a) -> int:
    src = a.source
    cleanup = None
    if re.match(r"^(https?://|ssh://|git@|git://)", src):
        cleanup = tempfile.mkdtemp(prefix="repo-arch-")
        print(f"cloning {src} ...")
        r = subprocess.run(["git", "clone", "--depth", "1", src, cleanup], capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit("error: git clone failed: " + r.stderr.strip()[-300:])
        root = cleanup
        name = re.sub(r"\.git$", "", src.rstrip("/").rsplit("/", 1)[-1])
    else:
        root = os.path.abspath(src)
        if not os.path.isdir(root):
            raise SystemExit(f"error: {src} is not a folder or a git URL")
        name = os.path.basename(root)
    try:
        model = analyze_repo(root, a.depth)
    finally:
        if cleanup:
            shutil.rmtree(cleanup, ignore_errors=True)
    model["name"] = name or model["name"]
    out = a.out or os.path.join("repo-architecture", name)
    os.makedirs(out, exist_ok=True)
    write(os.path.join(out, "model.json"), json.dumps(model, indent=2, ensure_ascii=False) + "\n")
    print(f"{model['files']} files, {model['lines']} lines, {len(model['components'])} components, "
          f"{len(model['edges'])} dependencies, {len(model['entry_points'])} entry points")
    do_render(out, model)
    return 0


def cmd_render(a) -> int:
    do_render(a.folder, load_model(a.folder))
    return 0


def cmd_check(a) -> int:
    model = load_model(a.folder)
    todo = missing(model, load_annotations(a.folder, model))
    if todo:
        print("Result: not complete. Still to describe in annotations.json:")
        for t in todo:
            print("  -", t)
        return 1
    print("Result: complete")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("analyze", help="scan a repository and write the first draft")
    p.add_argument("source", help="folder or git URL")
    p.add_argument("--out", help="output folder (default repo-architecture/<name>)")
    p.add_argument("--depth", type=int, default=2, help="how many container folders (src, packages, ...) to look into (default 2)")
    p.set_defaults(fn=cmd_analyze)
    p = sub.add_parser("render", help="rebuild the documents after editing annotations.json")
    p.add_argument("folder")
    p.set_defaults(fn=cmd_render)
    p = sub.add_parser("check", help="list what is still undescribed")
    p.add_argument("folder")
    p.set_defaults(fn=cmd_check)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
