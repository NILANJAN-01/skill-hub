---
name: robotframework-test-authoring
description: "Write, review and modernise Robot Framework tests and tasks with the current 7.x syntax: VAR, typed variables, GROUP, secret variables, IF/TRY/WHILE, RETURN, keyword setup, test metadata and Markdown test files, plus Browser, SeleniumLibrary and RequestsLibrary. A script audits suites for outdated or deprecated syntax. Use when the user writes, reviews or upgrades .robot files."
license: MIT
compatibility: The audit script needs Python 3.8+ (standard library only). Tests need Robot Framework 7.x (latest 7.5.x, Python 3.8+); some features need newer versions (noted inline).
metadata:
  title: "Robot Framework authoring: modern 7.x syntax and an audit"
  category: robotframework-tools
---

# Robot Framework test authoring

Robot Framework (RF) changed a lot in 7.0–7.5: native `VAR`, typed variables, `GROUP`, secret variables, test metadata and tests inside Markdown. Write new suites with this syntax and move old suites onto it, following the conventions the project already has.

## When to use

- Write new test or RPA task suites, resource files or user keywords.
- Review a suite, or modernise one written for RF 3–6 (`Run Keyword If`, `[Return]`, `Set Test Variable`, `Force Tags`, ...).
- Choose libraries: web UI, API, mobile, database.

## When NOT to use

- Writing Python keyword libraries: use `robotframework-libraries`.
- A run failed and you need the cause: use `robotframework-results`.
- Running in CI or in parallel: use `robotframework-ci`.

## Procedure

1. **Read the project first:** RF version (`robot --version`), libraries in `requirements.txt`, folder layout (`tests/`, `resources/`, `libraries/`, `variables/`), naming and tag conventions, and existing resource files to reuse.
2. **Audit the existing suites** (read-only):
   ```bash
   python scripts/rf_audit.py <tests-dir>
   python scripts/rf_audit.py <tests-dir> --json
   python scripts/rf_audit.py <tests-dir> --strict        # warnings fail too (CI)
   ```
   It reports the RF version found in requirements, which modern features are used, and with file and line: removed, deprecated or superseded syntax (`[Return]` and `VAR` without a value in a non-local scope, which RF 7.5 warns about; tag patterns `XORY` and `&`; `NO VALUES`; OperatingSystem `Run`; the Telnet library, which no longer imports on Python 3.13+; old `:FOR`; and superseded `Force Tags`/`Default Tags`, `Exit For Loop`, `Run Keyword If`, `Set Test/Suite/Global Variable`), hard `Sleep`s, literal passwords that should be secret variables, very long tests, and keywords without documentation. For a full lint and formatter run Robocop (step 6).
3. **Write tests that read like specifications** ([references/syntax.md](references/syntax.md) has every construct with examples):
   - One behaviour per test, named for it; steps are user-level keywords from resource files, not raw library calls.
   - `*** Settings ***`: `Test Tags` (not `Force Tags`), `Resource`, `Library    Browser    timeout=10s`, `Suite Setup`/`Test Teardown`.
   - Variables: `VAR    ${name}    value    scope=TEST|SUITE|GLOBAL` instead of `Set ... Variable`; typed `${count: int}` (7.3+); secrets from the environment `${PASSWORD: Secret}    %{E2E_PASSWORD}` (7.4+).
   - Control flow: `IF / ELSE IF / ELSE / END`, inline `IF`, `TRY / EXCEPT / FINALLY`, `WHILE ... limit=`, `FOR ... IN RANGE | IN ENUMERATE | IN ZIP`, `BREAK`, `CONTINUE`, `RETURN`; `GROUP    name` (7.2+) to structure long flows in the log.
   - Data-driven tests with `[Template]` or `Test Template`; `[Metadata]` on tests (7.5+) for issue keys and owners.
   - Waiting: library waits (`Wait For Elements State`, `Wait Until Element Is Visible`) or `Wait Until Keyword Succeeds`, never bare `Sleep`.
4. **Pick libraries** (install with pip; versions pinned in `requirements.txt`):
   | Need | Library |
   |---|---|
   | Web UI (recommended for new work) | `robotframework-browser` (Browser, Playwright-based): `pip install robotframework-browser && rfbrowser init` |
   | Web UI (existing Selenium estates, Grid) | `robotframework-seleniumlibrary` |
   | REST APIs | `robotframework-requests` (RequestsLibrary) |
   | Mobile | `robotframework-appiumlibrary` |
   | Databases | `robotframework-databaselibrary` |
   | Files, processes, strings, dates, XML | standard libraries (OperatingSystem, Process, String, DateTime, Collections, XML) |
5. **Tests in Markdown (7.5+):** put RF data in ```` ```robotframework ```` blocks inside `*.robot.md` files to keep specs and executable examples together; plain `*.md` files are ignored unless `--parseinclude` / `--extension` say otherwise.
6. **Lint and format** with Robocop (Robotidy is now part of it):
   ```bash
   pip install robotframework-robocop
   robocop check tests/          # lint
   robocop format tests/         # format (configure in pyproject.toml [tool.robocop.format])
   ```
7. **Validate before running:** `robot --dryrun tests/` checks syntax, keyword names and argument counts without executing. Then run a single test with `robot --test "Name" tests/`.

## Safety rules

- Never put real passwords or tokens in `.robot` or variable files: use `Secret` variables fed from environment variables or the CI secret store. Secrets show as `<secret>` in logs; `${secret.value}` reveals them, so use it only when a keyword needs the raw value.
- Do not run destructive tasks (RPA bots, data deletion) against production without explicit approval.
- Keep `log.html` / `output.xml` private: they record every keyword argument that is not a secret.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `No keyword with name 'X' found` | Missing `Library`/`Resource` import or a typo; `robot --dryrun` lists them all |
| `Variable '${x}' not found` | Scope: use `VAR ... scope=SUITE` or pass it as an argument |
| Literal value rejected for a `Secret` variable | By design (7.4): take it from `%{ENV}` or `--variable "NAME: Secret:$ENV_VAR"` |
| `${x: int}` breaks an old variable named with `: ` | Since 7.3 a space after the colon means a type; rename the variable |
| Tag pattern warning `XORY` | Write `X OR Y` (7.5 deprecates the old forms and `&`) |

## References

- [references/syntax.md](references/syntax.md): every modern construct with examples, project layout, and what changed in 7.0–7.5.
