---
name: secrets-dependency-audit
description: "Find secrets committed to a repository (AWS, GitHub or API keys, tokens, private keys, passwords) and risky dependency pins with a bundled script, before a commit or release. Use when the user asks if a key was committed or leaked, to scan for secrets, add a pre-commit secret check, or audit dependency pinning."
license: MIT
metadata:
  title: "Secrets and dependency audit"
  category: security-tools
---

# Secrets and dependency audit

`scripts/audit.py` scans a repository for committed secrets and for dependency settings that let an attacker or a surprise release into the build. It needs only Python 3.8+ (git is optional) and prints a short report: one line per finding with a masked value, then one fix per finding type. Read the report, not the files.

## When to use

- "Did I commit a key?", "scan this repo for secrets", before making a repository public or cutting a release.
- Adding a pre-commit check that blocks secrets.
- A key was leaked earlier and the user wants to know if it is still in git history.
- Reviewing dependency hygiene: unpinned versions, missing lock files, http registries, unpinned GitHub Actions or Docker images.

## When NOT to use

- Known vulnerabilities (CVEs) in dependencies: use the ecosystem's tool (`pip-audit`, `npm audit`, `osv-scanner`, Dependabot). This skill checks how dependencies are pinned and fetched, not their CVEs.
- A full security review of code logic: this finds secrets and supply-chain settings only.
- Apps that call an LLM (prompt injection, prompt leaking, hallucinated packages in generated code): use `llm-app-security`.

## Safety rules for the agent

- Never print, copy or paste a full secret. Quote only the masked value from the report.
- A committed secret must be treated as leaked: tell the user to **revoke and replace it first**. Deleting the line or rewriting history does not make it safe, because clones, forks and caches keep it.
- Do not rewrite git history (`git filter-repo`, force-push) without the user's explicit go-ahead; it disrupts everyone who has cloned.
- `install-hook` and `baseline` write files: show the plan and ask before running them with `--yes` or committing the baseline.

## Procedures

Paths are relative to this skill's folder; run the script from the repository root.

1. **Scan the working tree** (tracked and untracked files; `.gitignore`, binaries and `node_modules`-style folders are skipped):
   ```bash
   python scripts/audit.py scan
   ```
   Exit code 0 means nothing found, 1 findings, 2 bad input. Add `--json` for machine output, `--fail-on high` to fail only on high severity.
2. **Check history** when a secret may have been committed and removed:
   ```bash
   python scripts/audit.py scan --history --max-commits 2000
   ```
   Findings show the commit. If any is real, rotate it (rule 2), then offer history rewriting.
3. **Audit dependencies** (requirements*.txt, package.json, Gradle, pom.xml, Dockerfiles, GitHub workflows):
   ```bash
   python scripts/audit.py deps
   ```
4. **Triage false positives.** Test fixtures and docs often hold fake keys. Mark one line with a comment containing `audit:ignore`, skip paths with `--exclude "tests/fixtures/*"`, or accept all current findings with `python scripts/audit.py baseline` (writes `.secrets-baseline.json`; new findings are still reported).
5. **Block new secrets** before each commit (ask first):
   ```bash
   python scripts/audit.py install-hook          # shows the plan
   python scripts/audit.py install-hook --yes    # writes .git/hooks/pre-commit
   ```
   In CI, run `python scripts/audit.py scan --fail-on medium`.

## What it detects

- **High:** private keys, AWS, GitHub, GitLab, Slack, Google, Stripe live, OpenAI, Anthropic, npm, PyPI, SendGrid and Azure storage keys; passwords inside URLs; http package indexes and repositories.
- **Medium:** `password`/`token`/`api_key`-style names assigned a random-looking value (placeholders like `changeme`, `${VAR}`, `your_key` are ignored), JWTs, Slack webhooks; unpinned or wildcard versions, git/URL dependencies, missing lock files, `--extra-index-url` (dependency confusion), unpinned Docker images, `curl | sh`, third-party actions not pinned to a commit SHA, `permissions: write-all`.
- **Low:** range-pinned Python packages, first-party actions on a tag, `mavenLocal()`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `error: --staged needs a git repository` | Run inside a git checkout, or scan paths instead |
| A test fixture with a fake key is reported | `audit:ignore` on that line, `--exclude`, or `baseline` |
| `... already exists and is not ours` from `install-hook` | Add the printed line to the existing hook (or to the pre-commit framework config) |
| A real secret type is not detected | Generic names are caught only with a random value of 8+ characters; check the exact format against the provider docs |
