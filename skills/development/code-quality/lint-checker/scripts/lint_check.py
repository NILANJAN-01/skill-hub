#!/usr/bin/env python3
"""Find, run and summarise linters for a project in any programming language.

Detects the languages in a project, the linters it already configures and the
ones installed on this machine, runs the right ones and reports their exit
codes and output together. Java and Kotlin projects are linted through the
lint plugins their Gradle or Maven build applies (Checkstyle, PMD, SpotBugs,
ktlint, kotlinter, detekt, Spotless, Android Lint), run with the project's
wrapper. Built-in checks work on every text file with no tools installed:
merge conflict markers, syntax errors in Python, JSON and TOML, leftover
debugger calls and printStackTrace(), trailing whitespace, mixed line
endings, mixed tab/space indentation, missing final newline, overlong lines.

Usage:
  python lint_check.py detect [PATH]       languages, configured and installed linters, the plan
  python lint_check.py run [PATH]          run the planned linters plus the built-in checks
  python lint_check.py basic [PATH ...]    built-in checks only (files or folders, default .)
  python lint_check.py list                every linter this script knows

Options for detect and run:
  --only ID,ID          use only these linters (ids from `list`)
  --all                 use every installed linter for the detected languages
Options for run:
  --changed [REF]       lint only files changed since REF (default HEAD) plus untracked files
  --fix                 run each linter's fix command instead; without --yes only prints the plan
  --yes                 confirm --fix (it rewrites files)
  --no-basic            skip the built-in checks
  --timeout SECONDS     limit per linter command (default 600)
  --max-output LINES    output lines kept per linter (default 200, 0 = all)
Options for run and basic:
  --max-line N          flag lines longer than N characters (default 120, 0 = off)
  --fail-on error|warning|info|never
                        exit 1 when a built-in finding has at least this severity (default error)
Common:
  --format text|json    output format (default text)

Exit codes: 0 clean, 1 a linter failed or a built-in finding reached --fail-on,
2 usage error, 3 (run only) nothing failed but a planned linter is not installed, or some files were
not passed to it (on Windows, names cmd.exe would interpret are never given to a .cmd/.bat tool).
Read-only unless --fix --yes. Python 3.8+, standard library only.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import warnings

# ---------------------------------------------------------------- languages
LANG_EXT = {
    "python": [".py", ".pyi"],
    "javascript": [".js", ".jsx", ".mjs", ".cjs", ".vue", ".svelte", ".astro"],   # components: ESLint/Biome
    "typescript": [".ts", ".tsx", ".mts", ".cts"],
    "go": [".go"],
    "rust": [".rs"],
    "java": [".java"],
    "kotlin": [".kt", ".kts"],
    "c-cpp": [".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hh", ".hxx"],
    "csharp": [".cs"],
    "ruby": [".rb", ".rake"],
    "php": [".php"],
    "shell": [".sh", ".bash"],
    "powershell": [".ps1", ".psm1", ".psd1"],
    "swift": [".swift"],
    "dart": [".dart"],
    "lua": [".lua"],
    "css": [".css", ".scss", ".sass", ".less"],
    "yaml": [".yml", ".yaml"],
    "markdown": [".md", ".markdown"],
    "terraform": [".tf"],
    "sql": [".sql"],
    "haskell": [".hs"],
    "elixir": [".ex", ".exs"],
    "dockerfile": [".dockerfile"],
}
EXT_LANG = {ext: lang for lang, exts in LANG_EXT.items() for ext in exts}
NAME_LANG = {"Dockerfile": "dockerfile", "Gemfile": "ruby", "Rakefile": "ruby"}

SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "venv", ".venv", "env", "__pycache__", ".tox", ".nox",
    ".mypy_cache", ".ruff_cache", ".pytest_cache", "dist", "build", "target", "vendor", ".gradle",
    ".idea", "out", "bin", "obj", "coverage", ".next", ".nuxt", ".dart_tool", ".terraform", "Pods",
}
GENERATED = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "Pipfile.lock", "uv.lock",
    "Cargo.lock", "go.sum", "composer.lock", "Gemfile.lock", "pubspec.lock", "mix.lock",
}
MAX_FILE_BYTES = 1_000_000


def lang_of(path: str) -> str | None:
    name = os.path.basename(path)
    if name in NAME_LANG or name.startswith("Dockerfile."):
        return NAME_LANG.get(name, "dockerfile")
    return EXT_LANG.get(os.path.splitext(name)[1].lower())


def _git(root: str, *args: str) -> str | None:
    try:
        res = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return res.stdout if res.returncode == 0 else None


def _skipped(rel: str) -> bool:
    return any(part in SKIP_DIRS for part in rel.replace("\\", "/").split("/")[:-1])


def list_files(root: str) -> list[str]:
    """Files under root (relative, '/'-separated). Honours .gitignore inside a git work tree."""
    out = _git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    if out is not None:
        rels = [p for p in out.split("\0") if p]
        files = [p for p in rels if os.path.isfile(os.path.join(root, p))]
    else:
        files = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
            for f in sorted(filenames):
                files.append(os.path.relpath(os.path.join(dirpath, f), root).replace(os.sep, "/"))
    return sorted(f for f in files if not _skipped(f))


def changed_files(root: str, ref: str) -> list[str] | None:
    """Files changed since ref plus untracked files, relative to root; None outside git or for a bad ref."""
    diff = _git(root, "diff", "--name-only", "--relative", "--diff-filter=ACMR", ref)
    if diff is None:
        return None
    untracked = _git(root, "ls-files", "--others", "--exclude-standard") or ""
    names = {p for p in (diff + "\n" + untracked).splitlines() if p.strip()}
    return sorted(p for p in names if os.path.isfile(os.path.join(root, p)) and not _skipped(p))


def count_languages(files: list[str]) -> dict[str, int]:
    """Source files per language. Gradle's Kotlin DSL scripts (build.gradle.kts, settings.gradle.kts) are build
    configuration, not Kotlin sources, so a Java project built with them is not reported as Kotlin."""
    counts: dict[str, int] = {}
    for f in files:
        lang = lang_of(f)
        if lang and not f.endswith(".gradle.kts"):
            counts[lang] = counts.get(lang, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


# ------------------------------------------------------------------ linters
class Linter:
    """One external linter.

    target: "dir" appends "." (or the changed files when takes_files), "files" appends every
    matching file, "root" appends nothing and lets the tool find the project itself.
    configs: files at the project root that mean the project uses this linter; "file::text"
    means the file exists and contains text. markers: globs at the root the tool needs to run.
    needs_config / kind "types": chosen by default only when the project configures them.
    config_flag: when a (plain) config file exists, it replaces the argument after this flag.
    build: "gradle" or "maven". The linter runs the lint tasks of the plugins the build applies
    (see BUILD_PLUGINS) through the project's wrapper, and counts as configured when any are found.
    """

    def __init__(self, id, langs, cmd, fix=None, configs=(), target="dir", takes_files=True,
                 node=False, needs_config=False, kind="lint", markers=(), install="", config_flag=None,
                 build=None):
        self.id, self.langs, self.cmd, self.fix = id, langs, cmd, fix
        self.configs, self.target, self.takes_files, self.node = list(configs), target, takes_files, node
        self.needs_config, self.kind, self.markers, self.install = needs_config, kind, list(markers), install
        self.config_flag, self.build = config_flag, build


# Lint plugins found in build files: (plugin, pattern, check tasks or goals, fix tasks or goals).
def _core_gradle_plugin(name: str) -> str:
    return (rf"""(?m)\bid\s*\(?\s*["']{name}["']|apply\s*\(?\s*plugin\s*[:=]\s*["']{name}["']"""
            rf"""|^\s*`?{name}`?\s*$""")


BUILD_PLUGINS = {
    "gradle": [
        ("checkstyle", _core_gradle_plugin("checkstyle"), ["checkstyleMain"], []),
        ("pmd", _core_gradle_plugin("pmd"), ["pmdMain"], []),
        ("spotbugs", r"com\.github\.spotbugs", ["spotbugsMain"], []),
        ("ktlint", r"org\.jlleitschuh\.gradle\.ktlint", ["ktlintCheck"], ["ktlintFormat"]),
        ("kotlinter", r"org\.jmailen\.kotlinter", ["lintKotlin"], ["formatKotlin"]),
        ("detekt", r"io\.gitlab\.arturbosch\.detekt|\bdev\.detekt\b", ["detekt"], []),
        ("spotless", r"com\.diffplug\.spotless", ["spotlessCheck"], ["spotlessApply"]),
        ("android-lint", r"com\.android\.(?:application|library|dynamic-feature)\b", ["lint"], ["lintFix"]),
    ],
    "maven": [
        ("spotbugs", r"spotbugs-maven-plugin", ["compile", "spotbugs:check"], []),
        ("checkstyle", r"maven-checkstyle-plugin", ["checkstyle:check"], []),
        ("pmd", r"maven-pmd-plugin", ["pmd:check"], []),
        ("ktlint", r"ktlint-maven-plugin", ["ktlint:check"], ["ktlint:format"]),
        ("detekt", r"detekt-maven-plugin", ["detekt:check"], []),
        ("spotless", r"spotless-maven-plugin", ["spotless:check"], ["spotless:apply"]),
    ],
}
BUILD_WRAPPERS = {"gradle": ("gradlew", "gradle"), "maven": ("mvnw", "mvn")}


def _is_build_file(rel: str, build: str) -> bool:
    name = os.path.basename(rel)
    if build == "maven":
        return name == "pom.xml"
    return name.endswith((".gradle", ".gradle.kts", ".versions.toml"))


L = Linter
ESLINT_CONFIGS = ["eslint.config.js", "eslint.config.mjs", "eslint.config.cjs", "eslint.config.ts",
                  ".eslintrc", ".eslintrc.js", ".eslintrc.cjs", ".eslintrc.json", ".eslintrc.yml",
                  ".eslintrc.yaml", 'package.json::"eslintConfig"']
LINTERS = [
    L("ruff", ["python"], ["ruff", "check"], ["ruff", "check", "--fix"],
      ["ruff.toml", ".ruff.toml", "pyproject.toml::[tool.ruff"], install="pip install ruff"),
    L("flake8", ["python"], ["flake8"], None, [".flake8", "setup.cfg::[flake8]", "tox.ini::[flake8]"],
      install="pip install flake8"),
    L("pylint", ["python"], ["pylint"], None, [".pylintrc", "pylintrc", "pyproject.toml::[tool.pylint"],
      target="files", install="pip install pylint"),
    L("mypy", ["python"], ["mypy"], None, ["mypy.ini", ".mypy.ini", "pyproject.toml::[tool.mypy",
                                            "setup.cfg::[mypy"], kind="types", install="pip install mypy"),
    L("eslint", ["javascript", "typescript"], ["eslint"], ["eslint", "--fix"], ESLINT_CONFIGS, node=True,
      needs_config=True, install="npm install --save-dev eslint, then npm init @eslint/config@latest"),
    L("biome", ["javascript", "typescript", "css"], ["biome", "lint"], ["biome", "lint", "--write"],
      ["biome.json", "biome.jsonc"], node=True, install="npm install --save-dev --save-exact @biomejs/biome"),
    L("tsc", ["typescript"], ["tsc", "--noEmit", "-p", "."], None, ["tsconfig.json"], target="root", takes_files=False,
      node=True, kind="types", install="npm install --save-dev typescript"),
    L("golangci-lint", ["go"], ["golangci-lint", "run", "./..."], ["golangci-lint", "run", "--fix", "./..."],
      [".golangci.yml", ".golangci.yaml", ".golangci.toml", ".golangci.json"], target="root", takes_files=False,
      markers=["go.mod"], install="see https://golangci-lint.run/welcome/install/"),
    L("go-vet", ["go"], ["go", "vet", "./..."], None, target="root", takes_files=False, markers=["go.mod"],
      install="included with Go"),
    L("clippy", ["rust"], ["cargo", "clippy", "--all-targets", "--", "-D", "warnings"],
      ["cargo", "clippy", "--fix", "--allow-dirty", "--allow-staged"], ["clippy.toml", ".clippy.toml"],
      target="root", takes_files=False, markers=["Cargo.toml"], install="rustup component add clippy"),
    L("gradle-lint", ["java", "kotlin"], ["gradlew", "--console=plain", "--continue"],
      ["gradlew", "--console=plain", "--continue"], target="root", takes_files=False, needs_config=True,
      build="gradle", markers=["build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts"],
      install="apply a lint plugin in the Gradle build (checkstyle, pmd, spotbugs, ktlint, detekt, "
              "spotless); see references/linters.md"),
    L("maven-lint", ["java", "kotlin"], ["mvnw", "-B", "-fae"], ["mvnw", "-B", "-fae"], target="root",
      takes_files=False, needs_config=True, build="maven", markers=["pom.xml"],
      install="add a lint plugin to pom.xml (maven-checkstyle-plugin, maven-pmd-plugin, spotbugs-maven-plugin, "
              "ktlint-maven-plugin, detekt-maven-plugin); see references/linters.md"),
    L("pmd", ["java"], ["pmd", "check", "--no-progress", "-R", "rulesets/java/quickstart.xml", "-d"],
      None, ["pmd-ruleset.xml", "ruleset.xml"], takes_files=False,
      install="see https://pmd.github.io (or use the build's checkstyle/spotbugs/pmd task)"),
    L("checkstyle", ["java"], ["checkstyle", "-c", "/google_checks.xml"], None,
      ["checkstyle.xml", "config/checkstyle/checkstyle.xml"], target="files", config_flag="-c",
      install="see https://checkstyle.org (brew install checkstyle, or java -jar checkstyle-all.jar)"),
    L("ktlint", ["kotlin"], ["ktlint"], ["ktlint", "--format"], [".editorconfig::ktlint"], target="root",
      install="see https://pinterest.github.io/ktlint/ (or the build's ktlintCheck task)"),
    L("detekt", ["kotlin"], ["detekt", "--input"], None, ["detekt.yml", "config/detekt/detekt.yml"],
      takes_files=False, install="see https://detekt.dev (or the build's detekt task)"),
    L("cppcheck", ["c-cpp"], ["cppcheck", "--enable=warning,style,performance,portability", "--quiet",
                              "--error-exitcode=1"], None, [".cppcheck"], install="see https://cppcheck.sourceforge.io"),
    L("clang-tidy", ["c-cpp"], ["clang-tidy"], ["clang-tidy", "--fix"], [".clang-tidy"], target="files",
      needs_config=True, install="install LLVM/clang tools; needs compile_commands.json"),
    L("dotnet-format", ["csharp"], ["dotnet", "format", "--verify-no-changes"], ["dotnet", "format"],
      [".editorconfig"], target="root", takes_files=False, markers=["*.sln", "*.slnx", "*.csproj"], install="included with the .NET SDK"),
    L("rubocop", ["ruby"], ["rubocop"], ["rubocop", "-a"], [".rubocop.yml"], install="gem install rubocop"),
    L("phpstan", ["php"], ["phpstan", "analyse", "--no-progress"], None, ["phpstan.neon", "phpstan.neon.dist"],
      target="root", needs_config=True, install="composer require --dev phpstan/phpstan"),
    L("phpcs", ["php"], ["phpcs"], ["phpcbf"], ["phpcs.xml", "phpcs.xml.dist", ".phpcs.xml"], target="root",
      needs_config=True, install="composer require --dev squizlabs/php_codesniffer"),
    L("shellcheck", ["shell"], ["shellcheck"], None, [".shellcheckrc"], target="files",
      install="see https://www.shellcheck.net (apt/brew/choco/scoop install shellcheck)"),
    L("psscriptanalyzer", ["powershell"],
      ["pwsh", "-NoProfile", "-Command", "Invoke-ScriptAnalyzer -Path . -Recurse -EnableExit"], None,
      ["PSScriptAnalyzerSettings.psd1"], target="root", takes_files=False,
      install="Install-Module PSScriptAnalyzer -Scope CurrentUser (needs pwsh)"),
    L("swiftlint", ["swift"], ["swiftlint", "lint"], ["swiftlint", "--fix"], [".swiftlint.yml"], target="root",
      install="brew install swiftlint"),
    L("dart-analyze", ["dart"], ["dart", "analyze"], ["dart", "fix", "--apply"], ["analysis_options.yaml"],
      target="root", markers=["pubspec.yaml"], install="included with the Dart/Flutter SDK"),
    L("luacheck", ["lua"], ["luacheck"], None, [".luacheckrc"], install="luarocks install luacheck"),
    L("stylelint", ["css"], ["stylelint"], ["stylelint", "--fix"],
      [".stylelintrc", ".stylelintrc.json", ".stylelintrc.yml", ".stylelintrc.yaml", "stylelint.config.js",
       "stylelint.config.mjs", "stylelint.config.cjs", 'package.json::"stylelint"'], target="files", node=True,
      needs_config=True, install="npm install --save-dev stylelint stylelint-config-standard"),
    L("yamllint", ["yaml"], ["yamllint"], None, [".yamllint", ".yamllint.yml", ".yamllint.yaml"],
      install="pip install yamllint"),
    L("markdownlint", ["markdown"], ["markdownlint-cli2"], ["markdownlint-cli2", "--fix"],
      [".markdownlint.json", ".markdownlint.jsonc", ".markdownlint.yaml", ".markdownlint.yml",
       ".markdownlint-cli2.jsonc", ".markdownlint-cli2.yaml"], target="files", node=True,
      install="npm install --save-dev markdownlint-cli2"),
    L("hadolint", ["dockerfile"], ["hadolint"], None, [".hadolint.yaml", ".hadolint.yml"], target="files",
      install="see https://github.com/hadolint/hadolint"),
    L("tflint", ["terraform"], ["tflint", "--recursive"], ["tflint", "--recursive", "--fix"], [".tflint.hcl"],
      target="root", takes_files=False, install="see https://github.com/terraform-linters/tflint"),
    L("sqlfluff", ["sql"], ["sqlfluff", "lint"], ["sqlfluff", "fix", "-f"],
      [".sqlfluff", "pyproject.toml::[tool.sqlfluff"], needs_config=True, install="pip install sqlfluff"),
    L("hlint", ["haskell"], ["hlint"], None, [".hlint.yaml"], install="cabal install hlint"),
    L("credo", ["elixir"], ["mix", "credo"], None, ["mix.exs::credo"], target="root", needs_config=True,
      install="add {:credo, only: [:dev, :test]} to mix.exs deps"),
]
BY_ID = {l.id: l for l in LINTERS}


def _read(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


_BUILD_TEXT: dict = {}     # (root, build) -> the text of its build files; make_plan() clears it for each run


def _build_text(root: str, build: str) -> str:
    """All build files of one kind under root, read once per plan (planning and commands ask several times)."""
    key = (os.path.abspath(root), build)
    if key not in _BUILD_TEXT:
        _BUILD_TEXT[key] = "\n".join(_read(os.path.join(root, f)) for f in list_files(root)
                                     if _is_build_file(f, build))
    return _BUILD_TEXT[key]


def build_tasks(linter: Linter, root: str) -> tuple[list[str], list[str], list[str]]:
    """For a build linter: (plugins found, check tasks, fix tasks) from the project's build files."""
    plugins, check, fix = [], [], []
    if not linter.build:
        return plugins, check, fix
    text = _build_text(root, linter.build)
    for name, pattern, tasks, fixes in BUILD_PLUGINS[linter.build]:
        if re.search(pattern, text):
            plugins.append(name)
            check += [t for t in tasks if t not in check]
            fix += [t for t in fixes if t not in fix]
    return plugins, check, fix


def resolve_build(linter: Linter, root: str) -> list[str] | None:
    """Command prefix for a build linter: the project's wrapper if present, else the tool on PATH."""
    wrapper, tool = BUILD_WRAPPERS[linter.build]
    found = shutil.which(wrapper, path=root)
    if found:
        return [found]
    if os.name != "nt" and os.path.isfile(os.path.join(root, wrapper)):
        return ["sh", os.path.join(root, wrapper)]  # wrapper committed without the executable bit
    found = shutil.which(tool)
    return [found] if found else None


def fix_available(linter: Linter, root: str) -> bool:
    return bool(build_tasks(linter, root)[2]) if linter.build else bool(linter.fix)


def is_configured(linter: Linter, root: str) -> bool:
    if linter.build:
        return bool(build_tasks(linter, root)[1])
    for entry in linter.configs:
        name, _, needle = entry.partition("::")
        path = os.path.join(root, name)
        if os.path.isfile(path) and (not needle or needle in _read(path)):
            return True
    return False


def has_markers(linter: Linter, root: str) -> bool:
    return not linter.markers or any(glob.glob(os.path.join(glob.escape(root), m)) for m in linter.markers)


def resolve_exe(exe: str, node: bool, root: str) -> str | None:
    if node:
        local = os.path.join(root, "node_modules", ".bin")
        if os.path.isdir(local):
            found = shutil.which(exe, path=local)
            if found:
                return found
    return shutil.which(exe)


def make_plan(root: str, files: list[str], only: list[str] | None = None, use_all: bool = False) -> dict:
    """Decide which linters to run. Returns languages, per-linter rows, the selection and notes."""
    _BUILD_TEXT.clear()                 # build files may have changed since an earlier plan
    langs = count_languages(files)
    rows, notes = {}, []

    def row(l: Linter) -> dict:
        if l.id not in rows:
            if l.build:
                prefix = resolve_build(l, root)
                installed = " ".join(prefix) if prefix else None
            else:
                installed = resolve_exe(l.cmd[0], l.node, root)
            rows[l.id] = {"id": l.id, "languages": l.langs, "configured": is_configured(l, root),
                          "installed": installed, "markers_ok": has_markers(l, root),
                          "install": l.install, "selected": False, "reason": ""}
            if l.build:
                rows[l.id]["plugins"] = build_tasks(l, root)[0]
                if rows[l.id]["configured"]:
                    wrapper, tool = BUILD_WRAPPERS[l.build]
                    rows[l.id]["install"] = (f"no {wrapper} wrapper in the project and no {tool} on PATH; "
                                             f"install {tool} or add the wrapper, and a JDK")
        return rows[l.id]

    selected: list[str] = []

    def pick(l: Linter, reason: str) -> None:
        r = row(l)
        if l.id not in selected:
            selected.append(l.id)
            r["selected"], r["reason"] = True, reason

    if only:
        for lid in only:
            pick(BY_ID[lid], "asked for")
    for lang in langs:
        cands = [l for l in LINTERS if lang in l.langs]
        for l in cands:
            row(l)
        if only:
            continue
        configured = [l for l in cands if rows[l.id]["configured"]]
        if use_all:
            chosen = [l for l in cands if rows[l.id]["installed"] and rows[l.id]["markers_ok"]
                      and (rows[l.id]["configured"] or not l.needs_config)]
            for l in chosen:
                pick(l, "configured" if rows[l.id]["configured"] else "installed (--all)")
        elif configured:
            # Lint plugins in the build are what CI runs; don't run standalone copies next to them.
            builds = [l for l in configured if l.build]
            for l in builds or configured:
                pick(l, "configured: " + ", ".join(rows[l.id]["plugins"]) if l.build else "configured")
        else:
            default = next((l for l in cands if rows[l.id]["installed"] and rows[l.id]["markers_ok"]
                            and not l.needs_config and l.kind == "lint"), None)
            if default:
                pick(default, "installed (no linter configured)")
        if not any(rows[l.id]["selected"] for l in cands):  # selected but missing is reported per linter
            hint = (next((l for l in cands if l.build and rows[l.id]["markers_ok"]), None)
                    or next((l for l in cands if not l.needs_config), cands[0] if cands else None))
            tip = f"; to add one: {hint.id} ({hint.install})" if hint else ""
            notes.append(f"{lang}: no linter will run{tip}. The built-in checks still apply.")
    for lid in selected:
        r = rows[lid]
        if not r["installed"]:
            r["reason"] += "; NOT INSTALLED"
        elif not r["markers_ok"]:
            r["reason"] += f"; needs {' or '.join(BY_ID[lid].markers)} at the project root"
    return {"root": os.path.abspath(root), "languages": langs, "linters": list(rows.values()),
            "selected": selected, "notes": notes}


def _chunks(items: list[str], max_chars: int = 7000, max_items: int = 200):
    batch, size = [], 0
    for item in items:
        if batch and (size + len(item) + 1 > max_chars or len(batch) >= max_items):
            yield batch
            batch, size = [], 0
        batch.append(item)
        size += len(item) + 1
    if batch:
        yield batch


# cmd.exe interprets these even inside the arguments of a .cmd/.bat file (npm's node_modules/.bin shims are .cmd
# files on Windows), so a file named "a&calc&.md" would run calc. Such names are never passed to a batch shim.
BATCH_META = set('&|<>^%!"()')


def _batch_shim(exe: str) -> bool:
    return os.name == "nt" and exe.lower().endswith((".cmd", ".bat"))


def build_commands(linter: Linter, root: str, files: list[str], changed: bool, fix: bool,
                   skipped: list | None = None) -> list[list[str]]:
    """Commands to run for one linter. files are the project (or changed) files, relative to root.
    File names unsafe to pass to a Windows batch shim are left out and appended to `skipped`."""
    base = list(linter.fix if fix else linter.cmd)
    mine = [f for f in files if lang_of(f) in linter.langs]
    if changed and not mine:
        return []
    if linter.build:
        _, check, fixes = build_tasks(linter, root)
        tasks = fixes if fix else check
        return [(resolve_build(linter, root) or base[:1]) + base[1:] + tasks] if tasks else []
    exe = resolve_exe(base[0], linter.node, root)
    if exe:
        base[0] = exe
    if _batch_shim(base[0]):
        unsafe = [f for f in mine if BATCH_META & set(f)]
        if unsafe:
            mine = [f for f in mine if f not in unsafe]
            if skipped is not None:
                skipped.extend(unsafe)
            if not mine and (linter.target == "files" or (changed and linter.takes_files)):
                return []                       # every file it would have been given was unsafe
    if linter.config_flag and linter.config_flag in base:
        config = next((c for c in linter.configs if "::" not in c and os.path.isfile(os.path.join(root, c))), None)
        if config:
            base[base.index(linter.config_flag) + 1] = config
    if linter.target == "root":
        if changed and linter.takes_files:
            return [base + batch for batch in _chunks(mine)]
        return [base]
    if linter.target == "files" or (changed and linter.takes_files):
        return [base + batch for batch in _chunks(mine)]
    return [base + ["."]]


def run_command(cmd: list[str], root: str, timeout: int) -> tuple[int, str]:
    try:
        res = subprocess.run(cmd, cwd=root, capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=timeout)
    except FileNotFoundError:
        return 127, f"command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout}s"
    except OSError as e:
        return 126, f"could not run {cmd[0]}: {e}"
    return res.returncode, (res.stdout + ("\n" if res.stdout and res.stderr else "") + res.stderr).strip()


def _trim(text: str, max_lines: int) -> str:
    lines = text.splitlines()
    if max_lines and len(lines) > max_lines:
        return "\n".join(lines[:max_lines] + [f"... {len(lines) - max_lines} more lines"])
    return text


# ----------------------------------------------------------- built-in checks
SEVERITY = {"info": 1, "warning": 2, "error": 3}
DEBUG_PATTERNS = {
    "python": [r"^\s*breakpoint\(\)", r"^\s*import i?pdb\b", r"\bi?pdb\.set_trace\("],
    "javascript": [r"^\s*debugger\s*;?\s*$"],
    "typescript": [r"^\s*debugger\s*;?\s*$"],
    "ruby": [r"\bbinding\.(pry|irb)\b", r"^\s*byebug\b"],
    "php": [r"\bvar_dump\s*\(", r"^\s*dd\s*\("],
    "rust": [r"\bdbg!\s*\("],
    "java": [r"\.printStackTrace\(\s*\)"],
    "kotlin": [r"\.printStackTrace\(\s*\)"],
}
DEBUG_RE = {lang: re.compile("|".join(p)) for lang, p in DEBUG_PATTERNS.items()}
JSONC_NAMES = {".eslintrc.json", "biome.json", "devcontainer.json", ".markdownlint.json", "turbo.json",
               ".babelrc", "deno.json", "launch.json", "tasks.json", "settings.json", "extensions.json"}
NO_WHITESPACE_EXT = {".diff", ".patch"}
NO_LONG_LINE_EXT = {".md", ".markdown", ".json", ".svg", ".csv", ".tsv", ".txt", ".lock", ".map", ".html",
                    ".xml", ".rst"}
NO_INDENT_NAMES = {"Makefile", "makefile", "GNUmakefile"}


def _finding(path, line, sev, rule, msg, col=1) -> dict:
    return {"path": path, "line": line, "col": col, "severity": sev, "rule": rule, "message": msg}


def check_text(rel: str, raw: bytes, max_line: int = 120) -> list[dict]:
    """Built-in checks for one file's bytes. rel is only used for the file type and the report."""
    name = os.path.basename(rel)
    ext = os.path.splitext(name)[1].lower()
    if b"\0" in raw[:8192] or name in GENERATED or ".min." in name:
        return []
    out: list[dict] = []
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
        out.append(_finding(rel, 1, "info", "encoding", "not valid UTF-8; checked as Latin-1"))
    lines = text.splitlines()
    lang = lang_of(rel)

    # Merge conflict markers (a lone ======= counts only next to a <<<<<<< line). In Markdown,
    # markers inside fenced code blocks are examples, not conflicts.
    fenced = _fenced_lines(lines) if lang == "markdown" else set()
    if ext not in NO_WHITESPACE_EXT and any((l.startswith("<<<<<<< ") or l == "<<<<<<<") and i not in fenced
                                            for i, l in enumerate(lines, 1)):
        for i, l in enumerate(lines, 1):
            if i not in fenced and (l.startswith(("<<<<<<<", ">>>>>>>", "|||||||")) or l == "======="):
                out.append(_finding(rel, i, "error", "conflict-marker", "unresolved merge conflict marker"))

    # Syntax of formats the standard library can parse.
    if lang == "python":
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                compile(text, rel, "exec", dont_inherit=True)
        except SyntaxError as e:
            v = sys.version_info
            out.append(_finding(rel, e.lineno or 1, "error", "syntax",
                                f"{e.msg} (checked with Python {v[0]}.{v[1]})", e.offset or 1))
        except ValueError as e:
            out.append(_finding(rel, 1, "error", "syntax", str(e)))
    elif ext == ".json" and not _is_jsonc(rel):
        try:
            json.loads(text)
        except json.JSONDecodeError as e:
            out.append(_finding(rel, e.lineno, "error", "syntax", f"invalid JSON: {e.msg}", e.colno))
    elif ext == ".toml":
        try:
            import tomllib  # novermin (Python 3.11+, guarded)
        except ImportError:
            tomllib = None
        if tomllib:
            try:
                tomllib.loads(text)
            except tomllib.TOMLDecodeError as e:
                m = re.search(r"line (\d+), column (\d+)", str(e))
                out.append(_finding(rel, int(m.group(1)) if m else 1, "error", "syntax", f"invalid TOML: {e}",
                                    int(m.group(2)) if m else 1))

    # Leftover debugger calls.
    if lang in DEBUG_RE:
        for i, l in enumerate(lines, 1):
            if DEBUG_RE[lang].search(l):
                out.append(_finding(rel, i, "warning", "debugger", f"leftover debug code: {l.strip()[:60]}"))

    if ext in NO_WHITESPACE_EXT or not text:
        return out

    # Whitespace rules: one finding per file with the count and the first line.
    def summary(rule, sev, hits, what):
        if hits:
            more = f" ({len(hits)} lines, first shown)" if len(hits) > 1 else ""
            out.append(_finding(rel, hits[0], sev, rule, what + more))

    if lang != "markdown":
        summary("trailing-whitespace", "warning",
                [i for i, l in enumerate(lines, 1) if l != l.rstrip(" \t")], "trailing whitespace")
    if not text.endswith(("\n", "\r")):
        out.append(_finding(rel, len(lines), "warning", "final-newline", "no newline at end of file"))
    crlf = text.count("\r\n")
    if crlf and text.count("\n") - crlf:
        out.append(_finding(rel, 1, "warning", "line-endings",
                            f"mixed line endings ({crlf} CRLF, {text.count(chr(10)) - crlf} LF)"))
    if name not in NO_INDENT_NAMES and ext not in (".mk", ".tsv") and lang != "markdown":
        text_lines = _block_lines(lines, lang)          # comment and docstring bodies: not indentation
        tabs = [i for i, l in enumerate(lines, 1) if l.startswith("\t") and i not in text_lines]
        spaces = [i for i, l in enumerate(lines, 1) if l.startswith(" ") and l.strip()
                  and not l.lstrip().startswith("*") and i not in text_lines]
        if tabs and spaces:
            first = min(tabs[0], spaces[0])
            out.append(_finding(rel, first, "warning", "mixed-indent",
                                f"indentation mixes tabs ({len(tabs)} lines) and spaces ({len(spaces)} lines)"))
    if max_line and ext not in NO_LONG_LINE_EXT:
        summary("line-length", "info", [i for i, l in enumerate(lines, 1) if len(l) > max_line],
                f"line longer than {max_line} characters")
    return out


BLOCK_COMMENT_LANGS = {"javascript", "typescript", "go", "rust", "java", "kotlin", "c-cpp", "csharp", "swift",
                       "dart", "php", "css"}


def _in_quotes(prefix: str) -> bool:
    """Rough test: is the end of this text inside a string literal (an odd number of one kind of quote)?"""
    return any(prefix.count(q) % 2 for q in ('"', "'", "`"))


def _block_lines(lines: list[str], lang: str | None) -> set:
    """1-based numbers of the lines that continue a /* block comment */ (C-family languages) or a Python
    triple-quoted string. Their leading whitespace is text, not indentation. Openers inside string literals
    ("src/**/*.js") and after // are ignored."""
    if lang == "python":
        openers = ('"""', "'''")
    elif lang in BLOCK_COMMENT_LANGS:
        openers = ("/*",)
    else:
        return set()
    out, inside, close = set(), False, ""
    for i, line in enumerate(lines, 1):
        if inside:
            out.add(i)
        pos = 0
        while True:
            if inside:
                j = line.find(close, pos)
                if j < 0:
                    break
                inside, pos = False, j + len(close)
                continue
            hits = [(line.find(o, pos), o) for o in openers]
            hits = [(j, o) for j, o in hits if j >= 0 and (lang == "python" or not _in_quotes(line[:j]))]
            line_comment = line.find("//", pos) if lang != "python" else -1
            if not hits or (0 <= line_comment < min(hits)[0]):
                break
            j, o = min(hits)
            inside, close, pos = True, "*/" if o == "/*" else o, j + len(o)
    return out


def _fenced_lines(lines: list[str]) -> set:
    """1-based numbers of the lines inside Markdown ``` or ~~~ fences, fence lines included."""
    inside, fence, out = False, "", set()
    for i, l in enumerate(lines, 1):
        s = l.lstrip()
        if not inside and s.startswith(("```", "~~~")):
            inside, fence = True, s[:3]
            out.add(i)
        elif inside:
            out.add(i)
            if s.startswith(fence):
                inside = False
    return out


def _is_jsonc(rel: str) -> bool:
    parts = rel.replace("\\", "/").split("/")
    name = parts[-1]
    return (name in JSONC_NAMES or ".vscode" in parts or ".devcontainer" in parts
            or re.match(r"^(ts|js)config.*\.json$", name) is not None)


def basic_check(root: str, files: list[str], max_line: int) -> list[dict]:
    findings = []
    for rel in files:
        path = os.path.join(root, rel)
        try:
            if os.path.getsize(path) > MAX_FILE_BYTES:
                continue
            with open(path, "rb") as fh:
                raw = fh.read()
        except OSError:
            continue
        findings.extend(check_text(rel, raw, max_line))
    return findings


def _expand(paths: list[str]) -> tuple[str, list[str]]:
    """Turn basic's PATH arguments into (root, files relative to root)."""
    if len(paths) == 1 and os.path.isdir(paths[0]):
        return paths[0], list_files(paths[0])
    files = []
    for p in paths:
        if os.path.isdir(p):
            files.extend(os.path.join(p, f).replace(os.sep, "/") for f in list_files(p))
        elif os.path.isfile(p):
            files.append(p.replace(os.sep, "/"))
        else:
            raise SystemExit(f"error: no such file or folder: {p}")
    return ".", files


def fails(findings: list[dict], fail_on: str) -> bool:
    return fail_on != "never" and any(SEVERITY[f["severity"]] >= SEVERITY[fail_on] for f in findings)


def format_findings(findings: list[dict]) -> str:
    lines = [f"{f['path']}:{f['line']}:{f['col']}: {f['severity']} [{f['rule']}] {f['message']}"
             for f in sorted(findings, key=lambda f: (f["path"], f["line"]))]
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in ("error", "warning", "info")}
    nfiles = len({f["path"] for f in findings})
    lines.append(f"built-in checks: {counts['error']} errors, {counts['warning']} warnings, "
                 f"{counts['info']} info in {nfiles} files")
    return "\n".join(lines)


# ---------------------------------------------------------------------- CLI
def cmd_list(args) -> int:
    if args.format == "json":
        print(json.dumps([{"id": l.id, "languages": l.langs, "command": l.cmd, "fix": l.fix,
                           "configs": l.configs, "install": l.install} for l in LINTERS], indent=2))
        return 0
    for l in LINTERS:
        tasks = " <lint tasks of the plugins in the build>" if l.build else ""
        fix = " (fix: " + " ".join(l.fix) + tasks + ")" if l.fix else ""
        print(f"{l.id:17} {','.join(l.langs):30} {' '.join(l.cmd)}{tasks}{fix}")
    return 0


def _plan_for(args) -> tuple[dict, list[str]]:
    if not os.path.isdir(args.path):
        raise SystemExit(f"error: not a folder: {args.path}")
    files = list_files(args.path)
    plan = make_plan(args.path, files, args.only, args.all)
    return plan, files


def cmd_detect(args) -> int:
    plan, _ = _plan_for(args)
    if args.format == "json":
        print(json.dumps(plan, indent=2))
        return 0
    print(f"Project: {plan['root']}")
    langs = ", ".join(f"{k} ({v})" for k, v in plan["languages"].items()) or "none recognised"
    print(f"Languages: {langs}\n")
    print(f"{'linter':17} {'languages':28} {'configured':11} {'installed':10} plan")
    for r in plan["linters"]:
        plan_text = "RUN - " + r["reason"] if r["selected"] else "-"
        print(f"{r['id']:17} {','.join(r['languages']):28} {('yes' if r['configured'] else 'no'):11} "
              f"{('yes' if r['installed'] else 'no'):10} {plan_text}")
        if r["selected"] and not r["installed"]:
            print(f"{'':17} install: {r['install']}")
    for n in plan["notes"]:
        print("note: " + n)
    print("Built-in checks run on every text file in `run` and `basic`.")
    return 0


def cmd_run(args) -> int:
    plan, files = _plan_for(args)
    root = args.path
    changed = args.changed is not None
    if changed:
        files = changed_files(root, args.changed)
        if files is None:
            raise SystemExit(f"error: --changed needs a git work tree and a valid ref ({args.changed})")
    results = []
    for lid in plan["selected"]:
        linter, row = BY_ID[lid], next(r for r in plan["linters"] if r["id"] == lid)
        if args.fix and not fix_available(linter, root):
            results.append({"id": lid, "status": "skipped", "detail": "has no fix command", "commands": []})
            continue
        if not row["installed"]:
            results.append({"id": lid, "status": "missing", "detail": "install: " + row["install"], "commands": []})
            continue
        if not row["markers_ok"]:
            results.append({"id": lid, "status": "skipped", "commands": [],
                            "detail": f"needs {' or '.join(linter.markers)} at the project root"})
            continue
        unsafe: list = []
        cmds = build_commands(linter, root, files, changed, args.fix, unsafe)
        note = (f"left out {len(unsafe)} file(s) whose names cmd.exe would interpret (& | < > ^ % ! \" ( )), "
                f"e.g. {unsafe[0]}; rename them or lint them by hand") if unsafe else ""
        if not cmds:
            results.append({"id": lid, "status": "skipped", "commands": [],
                            "detail": note or "no matching files", **({"unlinted_files": unsafe} if unsafe else {})})
            continue
        if args.fix and not args.yes:
            results.append({"id": lid, "status": "planned", "detail": "; ".join(x for x in ("dry run", note) if x),
                            "commands": cmds})
            continue
        code, outputs = 0, []
        for c in cmds:
            rc, out = run_command(c, root, args.timeout)
            code = code or rc
            if out:
                outputs.append(out)
        result = {"id": lid, "status": "passed" if code == 0 else "failed", "exit": code,
                  "commands": cmds, "output": _trim("\n".join(outputs), args.max_output)}
        if note:
            result["detail"], result["unlinted_files"] = note, unsafe
        results.append(result)

    findings = [] if (args.no_basic or args.fix) else basic_check(root, files, args.max_line)
    failed = any(r["status"] == "failed" for r in results) or fails(findings, args.fail_on)
    missing = [r["id"] for r in results if r["status"] == "missing"]
    partial = [r["id"] for r in results if r.get("unlinted_files")]
    verdict = "FAIL" if failed else "INCOMPLETE" if missing or partial else "OK"
    code = 1 if failed else 3 if missing or partial else 0

    if args.format == "json":
        print(json.dumps({"root": plan["root"], "languages": plan["languages"], "changed_only": changed,
                          "linters": results, "builtin": findings, "notes": plan["notes"],
                          "result": verdict}, indent=2))
        return code
    for r in results:
        print(f"== {r['id']}: {r['status']}" + (f" (exit {r['exit']})" if r.get("exit") else "")
              + (f" - {r['detail']}" if r.get("detail") else ""))
        for c in r["commands"]:
            print("$ " + " ".join(_short(c)))
        if r.get("output"):
            print(r["output"])
        print()
    if args.fix and not args.yes:
        print("Dry run: these fix commands rewrite files. Commit or stash first, then add --yes to apply.")
    for n in plan["notes"]:
        print("note: " + n)
    if not (args.no_basic or args.fix):
        print(format_findings(findings))
    summary = ", ".join(f"{r['id']} {r['status']}" for r in results) or "no external linters ran"
    print(f"\nsummary: {summary}; result: {verdict}")
    if missing:
        print(f"not installed: {', '.join(missing)}. Install them, or report that they did not run.")
    if partial:
        print(f"some files not linted by: {', '.join(partial)} (names unsafe for a Windows batch shim; see above).")
    return code


def _short(cmd: list[str]) -> list[str]:
    """Show the bare tool name instead of its absolute path, and abbreviate long file lists."""
    head = [os.path.splitext(os.path.basename(cmd[0]))[0]] + cmd[1:]
    return head if len(head) <= 12 else head[:10] + [f"... (+{len(head) - 10} args)"]


def cmd_basic(args) -> int:
    root, files = _expand(args.paths or ["."])
    findings = basic_check(root, files, args.max_line)
    if args.format == "json":
        print(json.dumps(findings, indent=2))
    else:
        print(format_findings(findings))
    return 1 if fails(findings, args.fail_on) else 0


def _ids(value: str) -> list[str]:
    ids = [v.strip() for v in value.split(",") if v.strip()]
    unknown = [i for i in ids if i not in BY_ID]
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown linter id(s): {', '.join(unknown)} (see `list`)")
    return ids


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="command", required=True)

    def common(p):
        p.add_argument("--format", choices=["text", "json"], default="text")

    def checks(p):
        p.add_argument("--max-line", type=int, default=120)
        p.add_argument("--fail-on", choices=["error", "warning", "info", "never"], default="error")

    p = sub.add_parser("list", help="every linter this script knows")
    common(p)
    for name in ("detect", "run"):
        p = sub.add_parser(name)
        p.add_argument("path", nargs="?", default=".")
        p.add_argument("--only", type=_ids)
        p.add_argument("--all", action="store_true")
        common(p)
        if name == "run":
            p.add_argument("--changed", nargs="?", const="HEAD", default=None, metavar="REF")
            p.add_argument("--fix", action="store_true")
            p.add_argument("--yes", action="store_true")
            p.add_argument("--no-basic", action="store_true")
            p.add_argument("--timeout", type=int, default=600)
            p.add_argument("--max-output", type=int, default=200)
            checks(p)
    p = sub.add_parser("basic")
    p.add_argument("paths", nargs="*")
    common(p)
    checks(p)
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return {"list": cmd_list, "detect": cmd_detect, "run": cmd_run, "basic": cmd_basic}[args.command](args)
    except SystemExit as e:
        if isinstance(e.code, str):
            print(e.code, file=sys.stderr)
            return 2
        raise


if __name__ == "__main__":
    sys.exit(main())
