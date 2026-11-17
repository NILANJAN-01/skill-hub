#!/usr/bin/env python3
"""Plan a Playwright upgrade: breaking changes between two versions, and where the project is affected.

Usage:
    python pw_upgrade.py <project-dir> [--from 1.48] [--to 1.65] [--json]

Detects the current version (package-lock.json / package.json / requirements / pyproject), lists the
breaking changes and removals in every release after it up to --to, scans code, config, CI files and
Docker image tags for each one, and prints the upgrade steps. Read-only; standard library only.

Release data: Playwright release notes 1.50 - 1.65 (https://playwright.dev/docs/release-notes).
Exit codes: 0 nothing affected, 1 affected places found, 2 bad input.
"""
import argparse
import json
import os
import re
import sys

LATEST_KNOWN = (1, 65)
SKIP_DIRS = {"node_modules", ".git", "dist", "build", "playwright-report", "test-results", "blob-report",
             ".venv", "venv", "__pycache__", "coverage", ".next"}
CODE_EXT = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts", ".py")
CI_NAMES = ("Jenkinsfile", ".gitlab-ci.yml", "azure-pipelines.yml", "Dockerfile", "package.json")
CI_DIRS = (".github",)

# (version, title, what to do, regex or None, where: code|ci|config|any)
CHANGES = [
    ((1, 50), "toBeEditable()/isEditable() now throw on elements that cannot be edited",
     "Assert only on inputs, textareas, selects or contenteditable elements",
     r"\b(toBeEditable|isEditable|to_be_editable|is_editable)\s*\(", "code"),
    ((1, 50), "updateSnapshots: 'all' now updates all snapshots (use 'changed' for only changed ones)",
     "Check CI does not rewrite baselines unexpectedly", r"updateSnapshots\s*:\s*['\"]all['\"]|--update-snapshots(=|\s+)all", "any"),
    ((1, 52), "Glob patterns no longer support ? and [] (route, waitForURL, testMatch, ...)",
     "Use a RegExp or a predicate function for those URLs/paths",
     r"""(route|unroute|waitForURL|wait_for_url|toHaveURL|testMatch|testIgnore)\s*[:(]\s*\(?\s*['"`][^'"`]*\*[^'"`]*[?\[][^'"`]*['"`]""", "any"),
    ((1, 52), "route.continue() ignores the Cookie header", "Set cookies with context.addCookies() instead",
     r"\.(continue|continue_)\s*\([^)]*[Cc]ookie", "code"),
    ((1, 54), "Node.js 16 removed (Node 18 deprecated)", "Upgrade Node.js (1.65 needs Node 22+)", None, "ci"),
    ((1, 54), "The -gv CLI shorthand was removed", "Use --grep-invert", r"\s-gv\b", "ci"),
    ((1, 54), "`playwright open` no longer opens the recorder", "Use `playwright codegen`", r"playwright\s+open\b", "any"),
    ((1, 55), "Chromium extension manifest v2 support dropped", "Migrate test extensions to manifest v3",
     r"""["']manifest_version["']\s*:\s*2\b""", "any"),
    ((1, 56), "browserContext.on('backgroundpage') is deprecated", "Use service workers (context.serviceWorkers())",
     r"""['"]backgroundpage['"]""", "code"),
    ((1, 57), "page.accessibility was removed", "Use toMatchAriaSnapshot()/page.ariaSnapshot() or @axe-core/playwright",
     r"\.accessibility\.snapshot\s*\(|page\.accessibility\b", "code"),
    ((1, 57), "Chromium tests now use Chrome for Testing builds (headless: chrome-headless-shell)",
     "Expect small rendering differences: re-check screenshot baselines", r"toHaveScreenshot|to_have_screenshot|toMatchSnapshot", "code"),
    ((1, 57), "Official Docker images use Node.js 24", "Rebuild custom images from the new tag", None, "ci"),
    ((1, 58), "_react and _vue selector engines removed", "Use getByRole/getByTestId",
     r"""['"`](_react|_vue)=""", "code"),
    ((1, 58), "The :light selector suffix was removed", "Remove the suffix (shadow DOM is pierced by default)",
     r""":light\b""", "code"),
    ((1, 58), "The devtools launch option was removed", "Use args: ['--auto-open-devtools-for-tabs']",
     r"\bdevtools\s*[:=]\s*(true|True)\b", "any"),
    ((1, 59), "The junit reporter reports some failures as <error> instead of <failure>",
     "Check CI dashboards that count only failures", r"""['"]junit['"]|--reporter[= ][^\n]*junit""", "any"),
    ((1, 59), "experimental-ct-svelte package removed", "Move Svelte component tests to E2E or another runner",
     r"experimental-ct-svelte", "any"),
    ((1, 60), "Locator.ariaRef(), exposeBinding's handle option, connect's logger option, videosPath/videoSize removed",
     "Use recordVideo: { dir, size } and remove the dropped options",
     r"\.ariaRef\s*\(|\bvideosPath\b|\bvideoSize\b|\bvideos_path\b|\bvideo_size\b|exposeBinding\s*\([^)]*handle\s*:", "any"),
    ((1, 62), "Clipboard is isolated in headless mode", "Grant clipboard permissions and read it within the same context",
     r"clipboard", "code"),
    ((1, 62), "Debian 11 is no longer supported", "Move CI images to Debian 12/13 or Ubuntu 22.04+", r"bullseye|debian:11", "ci"),
    ((1, 63), "Experimental component testing packages are no longer updated", "Plan a move to E2E or the new component model",
     r"@playwright/experimental-ct-", "any"),
    ((1, 63), "Ubuntu 20.04 is no longer supported", "Use ubuntu-22.04 or newer runners/images", r"ubuntu-20\.04|ubuntu:20\.04|focal", "ci"),
    ((1, 64), "Viewport `screen` now comes from device descriptors", "Re-check tests that read window.screen sizes",
     r"window\.screen|\bscreen\s*:\s*\{", "code"),
    ((1, 64), "--update-snapshots=missing now passes instead of failing", "Do not rely on it to fail CI for missing baselines",
     r"update-snapshots=missing", "any"),
    ((1, 64), "Elements inside hidden iframes count as hidden", "Assertions on them now see them as hidden", None, "code"),
    ((1, 64), "Video fontSize option deprecated in favour of style", "Move fontSize into the style option", r"\bfontSize\b", "config"),
    ((1, 65), "Node.js 20 is no longer supported", "Use Node.js 22 or newer locally, in CI and in custom images",
     r"""node-version:\s*['"]?(1[0-9]|20)(\.|['"\s]|$)|versionSpec:\s*['"]?(1[0-9]|20)\.|\bnode:(1[0-9]|20)\b|"node"\s*:\s*"[^"]*\b(1[0-9]|20)\b""", "ci"),
    ((1, 65), "A sharded run with no matching tests fails unless --pass-with-no-tests is given",
     "Add --pass-with-no-tests to sharded runs that use --grep/tags", r"--shard[^\n]*--grep|--grep[^\n]*--shard", "ci"),
    ((1, 65), "TypeScript useDefineForClassFields is followed", "Check classes with field declarations (page objects) still initialise as expected",
     r"useDefineForClassFields", "any"),
    ((1, 65), "Actions wait for elements to be not inert", "Tests clicking behind modals now wait; close the modal first", None, "code"),
    ((1, 65), "Cookie matching follows RFC 6265; proxy credentials are no longer sent to websites",
     "Re-check tests that set cookies for parent domains or rely on proxy auth reaching the site", r"addCookies|add_cookies|proxy\s*[:=]", "code"),
]


def parse_version(text):
    m = re.search(r"(\d+)\.(\d+)", text or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def fmt(v):
    return "%d.%d" % v


def _read(path):
    try:
        with open(path, encoding="utf-8-sig", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def detect_version(root):
    """(version tuple or None, exact string, language)."""
    lock = os.path.join(root, "package-lock.json")
    if os.path.isfile(lock):
        try:
            data = json.loads(_read(lock))
            for key in ("node_modules/@playwright/test", "node_modules/playwright"):
                v = ((data.get("packages") or {}).get(key) or {}).get("version")
                if v:
                    return parse_version(v), v, "node"
        except ValueError:
            pass
    pkg = os.path.join(root, "package.json")
    if os.path.isfile(pkg):
        try:
            data = json.loads(_read(pkg))
            deps = {}
            deps.update(data.get("dependencies") or {})
            deps.update(data.get("devDependencies") or {})
            for key in ("@playwright/test", "playwright"):
                if key in deps:
                    return parse_version(deps[key]), deps[key], "node"
        except ValueError:
            pass
    for name in ("requirements.txt", "requirements-dev.txt", "pyproject.toml", "setup.cfg"):
        m = re.search(r"""(?<![\w-])playwright\s*(?:==|>=|~=)\s*["']?([0-9]+\.[0-9]+(?:\.[0-9]+)?)""", _read(os.path.join(root, name)))
        if m:
            return parse_version(m.group(1)), m.group(1), "python"
    return None, None, None


def iter_files(root):
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and (not d.startswith(".") or d in CI_DIRS))
        for name in sorted(files):
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            if name.startswith("playwright.config") or name in ("conftest.py", "pytest.ini"):
                yield path, rel, "config"
            elif name in CI_NAMES or rel.startswith(".github/") or name.endswith((".yml", ".yaml")) and "ci" in name.lower():
                yield path, rel, "ci"
            elif name.endswith(CODE_EXT):
                yield path, rel, "code"


def scan(root, changes):
    files = [(rel, kind, _read(path).splitlines()) for path, rel, kind in iter_files(root)]
    results = []
    for version, title, action, pattern, where in changes:
        hits = []
        if pattern:
            rx = re.compile(pattern)
            for rel, kind, lines in files:
                if where != "any" and not (kind == where or (where == "code" and kind == "config")):
                    continue
                for n, line in enumerate(lines, 1):
                    if rx.search(line):
                        hits.append({"file": rel, "line": n, "code": line.strip()[:140]})
        results.append({"version": fmt(version), "change": title, "action": action, "places": hits[:20],
                        "more": max(0, len(hits) - 20), "checkable": bool(pattern)})
    images = []
    for rel, kind, lines in files:
        for n, line in enumerate(lines, 1):
            for m in re.finditer(r"mcr\.microsoft\.com/playwright(/python)?:v(\d+\.\d+\.\d+)(-\w+)?", line):
                images.append({"file": rel, "line": n, "tag": m.group(0)})
    return results, images


def plan(root, from_v=None, to_v=LATEST_KNOWN):
    detected, exact, lang = detect_version(root)
    current = from_v or detected
    if current is None:
        raise ValueError("could not find the Playwright version; pass --from (e.g. --from 1.48)")
    changes = [c for c in CHANGES if current < c[0] <= to_v]
    results, images = scan(root, changes)
    notes = []
    if to_v > LATEST_KNOWN:
        notes.append(f"release data covers up to {fmt(LATEST_KNOWN)}: read the release notes for later versions")
    if current >= to_v:
        notes.append(f"already on {fmt(current)}: nothing to upgrade to {fmt(to_v)}")
    return {"root": os.path.abspath(root), "language": lang or "node", "current": fmt(current), "current_spec": exact,
            "target": fmt(to_v), "changes": results, "docker_images": images, "notes": notes,
            "affected": sum(1 for r in results if r["places"])}


def steps(p):
    t = p["target"]
    if p["language"] == "python":
        return [f"pip install -U \"playwright=={t}.*\" pytest-playwright   (update requirements / pyproject too)",
                "python -m playwright install --with-deps",
                f"Docker: mcr.microsoft.com/playwright/python:v<exact {t}.x version>-noble",
                "Run the suite on every browser project; fix the affected places below"]
    return [f"npm install -D @playwright/test@~{t}.0   (yarn add -D / pnpm add -D; keep any 'playwright' package on the same version)",
            "npx playwright install --with-deps",
            f"Docker/CI images: mcr.microsoft.com/playwright:v<exact installed {t}.x version>-noble (must match the package)",
            "CI and local Node.js: 22 or newer for 1.65",
            "npx playwright test --project=<each project>; then update screenshot baselines only after reviewing diffs",
            "If you use Playwright test agents: npx playwright init-agents --loop=<your agent> again to refresh them"]


def format_text(p):
    out = [f"Playwright upgrade plan for {p['root']}",
           f"  current: {p['current']}" + (f"  ({p['current_spec']})" if p["current_spec"] else "") + f"   target: {p['target']}"]
    out.extend(f"  note: {n}" for n in p["notes"])
    if p["changes"]:
        out.append(f"\nBreaking changes and removals after {p['current']} (affected places first):")
        for r in sorted(p["changes"], key=lambda r: (not r["places"], r["version"])):
            mark = "AFFECTED" if r["places"] else ("check   " if not r["checkable"] else "ok      ")
            out.append(f"  [{mark}] {r['version']}  {r['change']}")
            out.append(f"             -> {r['action']}")
            for h in r["places"][:8]:
                out.append(f"             {h['file']}:{h['line']}  {h['code']}")
            if len(r["places"]) > 8 or r["more"]:
                out.append(f"             ... and {len(r['places']) - 8 + r['more']} more")
    if p["docker_images"]:
        out.append("\nDocker image tags to update:")
        out.extend(f"  {i['file']}:{i['line']}  {i['tag']}" for i in p["docker_images"])
    out.append("\nSteps:")
    out.extend(f"  {n}. {s}" for n, s in enumerate(steps(p), 1))
    out.append(f"\n{p['affected']} change(s) affect this project. 'check' = cannot be found by text search; review by hand.")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project", help="project folder")
    ap.add_argument("--from", dest="from_v", help="current version, if it cannot be detected (e.g. 1.48)")
    ap.add_argument("--to", default=fmt(LATEST_KNOWN), help=f"target version (default {fmt(LATEST_KNOWN)})")
    ap.add_argument("--json", action="store_true")
    opts = ap.parse_args(argv)
    if not os.path.isdir(opts.project):
        print(f"not a folder: {opts.project}", file=sys.stderr)
        return 2
    to_v = parse_version(opts.to)
    from_v = parse_version(opts.from_v) if opts.from_v else None
    if to_v is None or (opts.from_v and from_v is None):
        print("versions look like 1.48 or 1.65.0", file=sys.stderr)
        return 2
    try:
        p = plan(opts.project, from_v, to_v)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(p, indent=2) if opts.json else format_text(p))
    return 1 if p["affected"] else 0


if __name__ == "__main__":
    sys.exit(main())
