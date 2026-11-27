#!/usr/bin/env python3
"""Find leaked secrets and risky dependency pins in a repository. Python 3.8+, standard library only.

    python audit.py scan [PATH ...]            # secrets in the files (tracked + untracked, .gitignore respected)
    python audit.py scan --staged              # only lines added in the staged changes (pre-commit)
    python audit.py scan --history [--max-commits 500]    # lines added in past commits (secrets stay in history)
    python audit.py deps [PATH]                # risky dependency pins, registries and install steps
    python audit.py baseline [PATH]            # accept today's findings: write .secrets-baseline.json
    python audit.py install-hook [--yes]       # add a git pre-commit hook that runs `scan --staged`

Secrets are never printed in full: findings show a masked value (first 4 and last 2 characters).
Options: --json, --fail-on {high,medium,low} (default low: any finding fails), --baseline FILE, --exclude GLOB.
Suppress one line with a comment containing `audit:ignore` or `pragma: allowlist secret`.
Exit codes: 0 nothing at or above --fail-on, 1 findings, 2 bad input.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

LEVELS = {"high": 3, "medium": 2, "low": 1}
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "env", "__pycache__", "dist", "build", ".tox", ".mypy_cache",
             ".pytest_cache", ".gradle", ".idea", "target", "vendor", ".next", "coverage"}
SKIP_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip", ".gz", ".jar", ".class", ".so", ".dll",
            ".exe", ".woff", ".woff2", ".ttf", ".mp4", ".mp3", ".lock"}
MAX_BYTES = 2_000_000
SUPPRESS = re.compile(r"audit:ignore|pragma: allowlist secret")
BASELINE = ".secrets-baseline.json"

# (rule id, severity, regex, group holding the secret, what to do). Provider formats first: exact and low-noise.
RULES = [
    ("private-key", "high", r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY(?: BLOCK)?-----", 0,
     "Replace the key pair (it must be treated as known), then remove the file and keep keys out of the repository."),
    ("aws-access-key-id", "high", r"\b((?:AKIA|ASIA|ABIA|ACCA)[A-Z0-9]{16})\b", 1,
     "Deactivate the key in AWS IAM and create a new one; load it from the environment or a secrets manager."),
    ("aws-secret-access-key", "high",
     r"(?i)aws_?secret_?access_?key\s*[\"']?\s*[:=]\s*[\"']?([A-Za-z0-9/+=]{40})(?![A-Za-z0-9/+=])", 1,
     "Rotate the AWS key pair in IAM."),
    ("github-token", "high", r"\b((?:gh[pousr]_[A-Za-z0-9]{36,255})|(?:github_pat_[A-Za-z0-9_]{60,255}))\b", 1,
     "Revoke the token in GitHub settings (Developer settings > tokens) and create a new one."),
    ("gitlab-token", "high", r"\b(glpat-[A-Za-z0-9_\-]{20,})", 1, "Revoke the token in GitLab and create a new one."),
    ("slack-token", "high", r"\b(xox[baprs]-[A-Za-z0-9-]{10,})", 1, "Revoke the token in the Slack app settings."),
    ("slack-webhook", "medium", r"(https://hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]{20,})", 1,
     "Delete the webhook in Slack and create a new one."),
    ("google-api-key", "high", r"\b(AIza[0-9A-Za-z\-_]{35})\b", 1, "Delete or restrict the key in Google Cloud console."),
    ("stripe-live-key", "high", r"\b((?:sk|rk)_live_[0-9a-zA-Z]{24,})", 1, "Roll the key in the Stripe dashboard."),
    ("openai-key", "high", r"\b(sk-(?:proj-|svcacct-|admin-)?[A-Za-z0-9_\-]{20,}T3BlbkFJ[A-Za-z0-9_\-]{20,})", 1,
     "Revoke the key in the OpenAI dashboard."),
    ("anthropic-key", "high", r"\b(sk-ant-(?:api|admin)\d{2}-[A-Za-z0-9_\-]{80,})", 1,
     "Revoke the key in the Anthropic console."),
    ("npm-token", "high", r"\b(npm_[A-Za-z0-9]{36})\b", 1, "Revoke the token with `npm token revoke` or on npmjs.com."),
    ("pypi-token", "high", r"\b(pypi-AgEIcHlwaS5vcmc[A-Za-z0-9_\-]{50,})", 1, "Remove the token in PyPI account settings."),
    ("sendgrid-key", "high", r"\b(SG\.[A-Za-z0-9_\-]{22}\.[A-Za-z0-9_\-]{43})\b", 1, "Delete the key in SendGrid."),
    ("azure-storage-key", "high", r"AccountKey=([A-Za-z0-9+/=]{80,})", 1,
     "Rotate the storage account key in Azure; prefer managed identities or SAS tokens."),
    ("jwt", "medium", r"\b(eyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,})", 1,
     "A signed token was committed; if it is a real session or API token, revoke it and shorten its lifetime."),
    ("url-credentials", "high", r"\b[a-z][a-z0-9+.\-]*://[^/\s:@\"']+:([^/\s:@\"']{3,})@[^\s\"']+", 1,
     "Change the password and take it out of the URL (use a credential helper or environment variable)."),
    ("secret-assignment", "medium",
     r"([A-Za-z_][\w.\-]*)[\"']?\s*(?::=|=>|[:=])\s*[\"']([^\"'\s]{8,})[\"']", 2,
     "Move the value to an environment variable or secrets manager, and rotate it if it is real."),
]
# Names whose words show a secret ("db_password", "apiKey", "AUTH_TOKEN"), but not "author" or "tokenizer".
SECRET_WORDS = {"password", "passwd", "pwd", "secret", "token", "auth", "credential", "credentials", "passphrase"}
SECRET_PAIRS = {("api", "key"), ("access", "key"), ("private", "key"), ("secret", "key"), ("client", "secret")}


def secret_name(name: str) -> bool:
    words = [w.lower() for w in re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+", name.replace("-", "_"))]
    return bool(SECRET_WORDS.intersection(words)) or any(p in SECRET_PAIRS for p in zip(words, words[1:])) \
        or "apikey" in words
COMPILED = [(rid, sev, re.compile(rx), grp, fix) for rid, sev, rx, grp, fix in RULES]
PLACEHOLDER = re.compile(
    r"(?i)^(?:x+|\*+|\.+|-+|0+|1234\w*|password\w*|secret\w*|changeme\w*|example\w*|sample\w*|dummy\w*|test\w*|"
    r"fake\w*|placeholder\w*|your[_\-]?\w*|replace[_\-]?\w*|todo\w*|none|null|undefined|redacted\w*|<.*>|\{\{.*\}\}|"
    r"\$\{.*\}|\$\w+|%\w+%|env\(.*|process\.env.*|os\.environ.*|getenv.*)$")


def entropy(s: str) -> float:
    if not s:
        return 0.0
    counts = {c: s.count(c) for c in set(s)}
    return -sum(n / len(s) * math.log2(n / len(s)) for n in counts.values())


def mask(secret: str) -> str:
    return (secret[:4] + "…" + secret[-2:]) if len(secret) > 8 else "…"


def fingerprint(rule: str, path: str, secret: str) -> str:
    return hashlib.sha256(f"{rule}\0{path}\0{secret}".encode("utf-8", "replace")).hexdigest()[:16]


def scan_line(line: str):
    """[(rule, severity, secret, fix)] for one line of text."""
    if SUPPRESS.search(line):
        return []
    out, seen = [], set()
    for rid, sev, rx, grp, fix in COMPILED:
        for m in rx.finditer(line):
            secret = m.group(grp)
            if not secret or secret in seen:
                continue
            if rid == "secret-assignment" and not secret_name(m.group(1)):
                continue
            if rid in ("secret-assignment", "url-credentials"):
                if PLACEHOLDER.match(secret) or entropy(secret) < (3.0 if rid == "url-credentials" else 3.5):
                    continue
                if rid == "secret-assignment" and any(secret in s for s in seen):
                    continue
            seen.add(secret)
            out.append((rid, sev, secret, fix))
    return out


# ------------------------------------------------------------------------------------------------ files
def git(args, cwd):
    try:
        r = subprocess.run(["git"] + args, cwd=cwd, capture_output=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.decode("utf-8", "replace") if r.returncode == 0 else None


def list_files(root: Path, excludes):
    listed = git(["ls-files", "-co", "--exclude-standard", "-z"], root)
    if listed is not None:
        rels = [p for p in listed.split("\0") if p]
    else:
        rels = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for f in filenames:
                rels.append(os.path.relpath(os.path.join(dirpath, f), root).replace(os.sep, "/"))
    out = []
    for rel in sorted(rels):
        parts = rel.split("/")
        if any(p in SKIP_DIRS for p in parts[:-1]) or Path(rel).suffix.lower() in SKIP_EXT:
            continue
        if any(fnmatch.fnmatch(rel, g) for g in excludes) or rel == BASELINE:
            continue
        out.append(rel)
    return out


def read_text(path: Path):
    try:
        if path.stat().st_size > MAX_BYTES:
            return None
        data = path.read_bytes()
    except OSError:
        return None
    if b"\0" in data[:8192]:
        return None                                                    # binary
    return data.decode("utf-8", "replace")


def added_lines(diff: str):
    """{path: [(line_no, text)]} for the '+' lines of a unified diff with -U0."""
    out, path, line_no = {}, None, 0
    for line in diff.splitlines():
        if line.startswith("+++ "):
            path = line[6:] if line.startswith("+++ b/") else None
        elif line.startswith("@@"):
            m = re.search(r"\+(\d+)", line)
            line_no = int(m.group(1)) if m else 0
        elif path and line.startswith("+") and not line.startswith("+++"):
            out.setdefault(path, []).append((line_no, line[1:]))
            line_no += 1
    return out


def findings_for(path: str, numbered_lines, where=""):
    out = []
    for no, text in numbered_lines:
        for rid, sev, secret, fix in scan_line(text):
            out.append({"rule": rid, "severity": sev, "path": path, "line": no, "where": where,
                        "masked": mask(secret), "fingerprint": fingerprint(rid, path, secret), "fix": fix})
    return out


def scan(root: Path, paths, staged=False, history=False, max_commits=500, excludes=()):
    results = []
    if staged:
        diff = git(["diff", "--cached", "-U0", "--no-color", "--diff-filter=ACMR"], root)
        if diff is None:
            raise SystemExit("error: --staged needs a git repository")
        for path, lines in added_lines(diff).items():
            if not any(fnmatch.fnmatch(path, g) for g in excludes):
                results += findings_for(path, lines)
        return results
    if history:
        log = git(["log", "-p", "-U0", "--no-color", f"--max-count={max_commits}", "--format=@@COMMIT %h"], root)
        if log is None:
            raise SystemExit("error: --history needs a git repository")
        for chunk in log.split("@@COMMIT ")[1:]:
            commit, _, diff = chunk.partition("\n")
            for path, lines in added_lines(diff).items():
                results += findings_for(path, lines, where="commit " + commit.strip())
        return results
    targets = []
    for p in paths or ["."]:
        p = Path(p)
        if p.is_dir():
            base = p.resolve()
            targets += [(base / rel, (Path(os.path.relpath(base / rel, root)).as_posix())) for rel in list_files(base, excludes)]
        elif p.is_file():
            targets.append((p, Path(os.path.relpath(p.resolve(), root)).as_posix()))
        else:
            raise SystemExit(f"error: no such file or folder: {p}")
    for full, rel in targets:
        text = read_text(full)
        if text is not None:
            results += findings_for(rel, enumerate(text.splitlines(), 1))
    return results


# ------------------------------------------------------------------------------------------- dependencies
def dep(sev, rule, path, line, text, fix):
    return {"rule": rule, "severity": sev, "path": path, "line": line, "where": "", "masked": text.strip()[:100],
            "fingerprint": fingerprint(rule, path, text.strip()), "fix": fix}


def deps_requirements(rel, text):
    out = []
    for no, raw in enumerate(text.splitlines(), 1):
        line = raw.split(" #")[0].strip()
        if not line or line.startswith("#") or SUPPRESS.search(raw):
            continue
        if re.match(r"(?:--index-url|-i)\s+http://", line):
            out.append(dep("high", "insecure-index", rel, no, line, "Use an https:// package index."))
        elif line.startswith("--extra-index-url"):
            out.append(dep("medium", "extra-index-url", rel, no, line,
                           "An extra index lets a public package with the same name win (dependency confusion); "
                           "use one index that proxies both, or pin with hashes (--require-hashes)."))
        elif line.startswith("--trusted-host"):
            out.append(dep("medium", "trusted-host", rel, no, line, "Remove --trusted-host and use https."))
        elif re.match(r"(?:-e\s+)?(?:git\+|hg\+|svn\+|https?://)", line):
            out.append(dep("medium", "vcs-or-url-dependency", rel, no, line,
                           "Pin the dependency to a release, or to an exact commit hash (@<40-hex>)."))
        elif line.startswith("-"):
            continue
        elif "==" not in line and "===" not in line and "@" not in line:
            sev = "low" if re.search(r">=|~=|<", line) else "medium"
            out.append(dep(sev, "unpinned-python-dependency", rel, no, line,
                           "Pin exact versions (==) in applications, ideally with a lock file or hashes."))
    return out


def deps_package_json(rel, text, folder: Path):
    out = []
    try:
        data = json.loads(text)
    except ValueError:
        return [dep("low", "unreadable-manifest", rel, 1, "package.json is not valid JSON", "Fix the JSON.")]
    lines = text.splitlines()

    def line_of(name):
        return next((i for i, l in enumerate(lines, 1) if f'"{name}"' in l), 1)
    for section in ("dependencies", "devDependencies", "optionalDependencies"):
        for name, spec in (data.get(section) or {}).items():
            spec = str(spec).strip()
            if spec in ("", "*", "latest", "x", "next"):
                out.append(dep("high", "wildcard-npm-version", rel, line_of(name), f"{name}: {spec or '(empty)'}",
                               "Use a version range from the registry (e.g. ^1.4.2) and commit the lock file."))
            elif re.match(r"(?:git\+|git:|github:|https?://|[\w.-]+/[\w.-]+(?:#|$))", spec):
                out.append(dep("medium", "git-or-url-dependency", rel, line_of(name), f"{name}: {spec}",
                               "Pin to a published version, or to an exact commit (#<sha>)."))
    has_deps = any(data.get(s) for s in ("dependencies", "devDependencies"))
    locks = ("package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb", "bun.lock")
    if has_deps and not any((folder / l).exists() for l in locks):
        out.append(dep("medium", "missing-lockfile", rel, 1, "no lock file next to package.json",
                       "Commit the lock file so every install gets the same versions (npm install writes it)."))
    return out


def deps_gradle(rel, text):
    out = []
    for no, line in enumerate(text.splitlines(), 1):
        if SUPPRESS.search(line):
            continue
        if re.search(r"[\"'][\w.\-]+:[\w.\-]+:[\w.\-]*\+[\"']|latest\.(?:release|integration)", line):
            out.append(dep("medium", "dynamic-gradle-version", rel, no, line,
                           "Use fixed versions (or a version catalog) and Gradle dependency locking."))
        if re.search(r"url\s*[=(]?\s*(?:uri\()?[\"']http://", line):
            out.append(dep("high", "insecure-repository", rel, no, line, "Use an https:// repository."))
        if "mavenLocal()" in line:
            out.append(dep("low", "maven-local", rel, no, line, "Builds should not depend on the local Maven cache."))
    return out


def deps_pom(rel, text):
    out = []
    for no, line in enumerate(text.splitlines(), 1):
        if re.search(r"<version>\s*(?:LATEST|RELEASE)\s*</version>", line):
            out.append(dep("medium", "floating-maven-version", rel, no, line, "Use a fixed version."))
        if re.search(r"<url>\s*http://", line):
            out.append(dep("high", "insecure-repository", rel, no, line, "Use an https:// repository."))
    return out


def deps_dockerfile(rel, text):
    out = []
    for no, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        m = re.match(r"(?i)FROM\s+(?:--platform=\S+\s+)?(\S+)", s)
        if m and m.group(1).lower() != "scratch" and not m.group(1).startswith("$"):
            image = m.group(1)
            if "@sha256:" not in image and (":" not in image.split("/")[-1] or image.endswith(":latest")):
                out.append(dep("medium", "unpinned-image", rel, no, s,
                               "Pin a version tag (better: a digest, image@sha256:...)."))
        if re.search(r"(?:curl|wget)\b[^|]*\|\s*(?:sudo\s+)?(?:ba|z)?sh\b", s):
            out.append(dep("medium", "pipe-to-shell", rel, no, s,
                           "Download, check a checksum or signature, then run; or install from a package manager."))
    return out


def deps_workflow(rel, text):
    out = []
    for no, line in enumerate(text.splitlines(), 1):
        m = re.search(r"uses:\s*[\"']?([\w.\-]+/[\w.\-/]+)@([\w.\-/]+)", line)
        if m and not re.fullmatch(r"[0-9a-f]{40}", m.group(2)) and not SUPPRESS.search(line):
            first_party = m.group(1).split("/")[0] in ("actions", "github")
            out.append(dep("low" if first_party else "medium", "unpinned-action", rel, no, line.strip(),
                           "Pin the action to a full commit SHA (uses: owner/action@<40-hex> # v1.2.3)."))
        if re.search(r"permissions:\s*write-all", line):
            out.append(dep("medium", "broad-permissions", rel, no, line.strip(),
                           "Grant only the permissions the job needs (e.g. contents: read)."))
        if re.search(r"(?:curl|wget)\b[^|]*\|\s*(?:sudo\s+)?(?:ba|z)?sh\b", line):
            out.append(dep("medium", "pipe-to-shell", rel, no, line.strip(),
                           "Download, check a checksum or signature, then run."))
    return out


def deps(root: Path, excludes=()):
    out = []
    for rel in list_files(root, excludes):
        name = rel.rsplit("/", 1)[-1]
        if not (re.match(r"requirements.*\.(?:txt|in)$", name) or name in ("package.json", "pom.xml")
                or name.startswith("Dockerfile") or name.endswith((".gradle", ".gradle.kts"))
                or re.match(r"\.github/workflows/.+\.ya?ml$", rel)):
            continue
        text = read_text(root / rel)
        if text is None:
            continue
        if name == "package.json":
            out += deps_package_json(rel, text, (root / rel).parent)
        elif name == "pom.xml":
            out += deps_pom(rel, text)
        elif name.startswith("Dockerfile"):
            out += deps_dockerfile(rel, text)
        elif name.endswith((".gradle", ".gradle.kts")):
            out += deps_gradle(rel, text)
        elif rel.startswith(".github/workflows/"):
            out += deps_workflow(rel, text)
        else:
            out += deps_requirements(rel, text)
    return out


# ------------------------------------------------------------------------------------------------ output
def load_baseline(path: Path):
    try:
        return set(json.loads(path.read_text(encoding="utf-8")).get("fingerprints", []))
    except (OSError, ValueError):
        return set()


def report(findings, what, as_json):
    findings = sorted(findings, key=lambda f: (-LEVELS[f["severity"]], f["path"], f["line"]))
    if as_json:
        return json.dumps({"kind": what, "count": len(findings), "findings": findings}, indent=2, ensure_ascii=False)
    if not findings:
        return f"{what}: no findings."
    counts = {s: sum(f["severity"] == s for f in findings) for s in LEVELS}
    lines = [f"{what}: {len(findings)} finding(s): " + ", ".join(f"{n} {s}" for s, n in counts.items() if n)]
    for f in findings:
        loc = f"{f['path']}:{f['line']}" + (f" ({f['where']})" if f["where"] else "")
        lines.append(f"  {f['severity'].upper():6} {f['rule']:28} {loc}  {f['masked']}")
    fixes = {}
    for f in findings:
        fixes.setdefault(f["rule"], f["fix"])
    lines.append("How to fix (once per type):")
    lines += [f"  {rule}: {fix}" for rule, fix in fixes.items()]
    return "\n".join(lines)


HOOK = """#!/bin/sh
# Added by secrets-dependency-audit: block commits that add secrets.
python3 "{script}" scan --staged || python "{script}" scan --staged
"""


def install_hook(root: Path, yes: bool) -> int:
    gitdir = git(["rev-parse", "--git-path", "hooks"], root)
    if gitdir is None:
        print("error: not a git repository", file=sys.stderr)
        return 2
    hook = (root / gitdir.strip() / "pre-commit").resolve()
    script = Path(__file__).resolve().as_posix()
    if hook.exists() and "secrets-dependency-audit" not in hook.read_text(encoding="utf-8", errors="replace"):
        print(f"{hook} already exists and is not ours: add this line to it instead:\n"
              f'  python "{script}" scan --staged')
        return 1
    print(f"Plan: write {hook} (runs `audit.py scan --staged` before each commit).")
    if not yes:
        print("Nothing written. Run again with --yes to write it.")
        return 0
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text(HOOK.format(script=script), encoding="utf-8")
    try:
        hook.chmod(0o755)
    except OSError:
        pass
    print(f"Wrote {hook}.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Find leaked secrets and risky dependency pins.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("scan", "deps", "baseline"):
        p = sub.add_parser(name)
        p.add_argument("paths", nargs="*", help="files or folders (default: the current folder)")
        p.add_argument("--json", action="store_true")
        p.add_argument("--fail-on", choices=list(LEVELS), default="low")
        p.add_argument("--baseline", type=Path, help=f"accepted findings (default: {BASELINE} if present)")
        p.add_argument("--exclude", action="append", default=[], metavar="GLOB")
        if name == "scan":
            p.add_argument("--staged", action="store_true", help="only lines added in the staged changes")
            p.add_argument("--history", action="store_true", help="lines added in past commits")
            p.add_argument("--max-commits", type=int, default=500)
    h = sub.add_parser("install-hook")
    h.add_argument("--yes", action="store_true", help="write the hook (default: show the plan only)")
    a = ap.parse_args(argv)
    root = Path.cwd()
    if a.cmd == "install-hook":
        return install_hook(root, a.yes)
    try:
        if a.cmd == "deps":
            where = Path(a.paths[0]) if a.paths else root
            if not where.is_dir():
                raise SystemExit(f"error: no such folder: {where}")
            findings, what = deps(where.resolve(), a.exclude), "dependency audit"
        else:
            findings = scan(root, a.paths, getattr(a, "staged", False), getattr(a, "history", False),
                            getattr(a, "max_commits", 500), a.exclude)
            what = "secret scan" + (" (staged)" if getattr(a, "staged", False) else
                                    " (history)" if getattr(a, "history", False) else "")
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 2
    if a.cmd == "baseline":
        out = root / BASELINE
        out.write_text(json.dumps({"tool": "secrets-dependency-audit", "fingerprints":
                                   sorted({f["fingerprint"] for f in findings})}, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {out} with {len(findings)} accepted finding(s). Commit it; new findings will still be reported.")
        return 0
    base = a.baseline or (root / BASELINE)
    accepted = load_baseline(base) if base.exists() else set()
    shown = [f for f in findings if f["fingerprint"] not in accepted]
    print(report(shown, what, a.json))
    if accepted and len(shown) < len(findings) and not a.json:
        print(f"({len(findings) - len(shown)} accepted finding(s) in {base.name} not shown)")
    return 1 if any(LEVELS[f["severity"]] >= LEVELS[a.fail_on] for f in shown) else 0


if __name__ == "__main__":
    sys.exit(main())
