---
name: robotframework-ci
description: "Run Robot Framework in CI and from the command line: GitHub Actions, GitLab CI, Azure Pipelines or Jenkins, tag selection, typed and secret variables, rerun of failed tests with rebot merge, parallel runs with pabot, JUnit results, JSON output and Robocop checks. A script generates the pipeline. Use when the user wants Robot tests in CI, faster runs, or reliable reports."
license: MIT
compatibility: The generator needs Python 3.8+ (standard library only). Pipelines run Robot Framework 7.x on Python 3.8+; the Browser library also needs Node.js (or its Docker image).
metadata:
  title: "Robot Framework in CI: run, rerun, parallelise, report"
  category: robotframework-tools
---

# Robot Framework in CI

A good Robot pipeline installs pinned versions, selects tests by tag, feeds secrets from the CI store, reruns failed tests once and merges the result (so flaky tests show up as re-executed, not as red builds), runs in parallel when the suite is large, and publishes `xunit.xml`, `log.html` and `report.html`.

## When to use

- Add Robot Framework to GitHub Actions, GitLab CI, Azure Pipelines or Jenkins.
- Speed up a long suite (pabot), cut noise from flaky tests (rerun + merge), or fix missing reports.
- Look up the right `robot` / `rebot` / `pabot` options.

## When NOT to use

- A run failed and you need the cause: use `robotframework-results`.
- Writing tests: use `robotframework-test-authoring`.

## Procedure

1. **Check the project:** pinned versions in `requirements.txt` (`robotframework`, libraries, `robotframework-pabot`), the suite folder, tags in use, environment variable files, and the secrets the tests read with `%{NAME}`.
2. **Generate the pipeline** (prints unless `--out`; never overwrites without `--force`):
   ```bash
   python scripts/rf_ci.py --ci github --project-dir . --tests tests --env E2E_PASSWORD --include smoke
   python scripts/rf_ci.py --ci gitlab --pabot 4 --variablefile variables/staging.py --out .gitlab-ci.robot.yml
   python scripts/rf_ci.py --ci azure --env API_TOKEN
   python scripts/rf_ci.py --ci jenkins --no-rerun --out Jenkinsfile
   ```
   It detects the Browser library and pabot from requirements; installs Node.js and runs `rfbrowser init` (GitHub/Azure) or uses the `marketsquare/robotframework-browser:<version>` image (GitLab/Jenkins); runs `robot` or `pabot --processes N`; reruns only failed tests once and merges with `rebot --merge` (the step's exit code is the number of tests still failing); writes `results/xunit.xml` for the CI test view and keeps `results/` as an artifact; sets `PYTHONIOENCODING=utf-8` (see troubleshooting); and maps each `--env` name to the CI's secret mechanism.
3. **Store secrets** in the CI and read them in data as secret variables (RF 7.4+): `${PASSWORD: Secret}    %{E2E_PASSWORD}`.
4. **Add a lint job** if the team agrees: `pip install robotframework-robocop && robocop check tests/` (and `robocop format --check` style options per the Robocop docs).
5. **Review and run on a branch**, then read results with `robotframework-results`' `rf_results.py results/output.xml --rerun results/rerun.xml`.

## Command-line essentials (RF 7.x)

| Need | Option |
|---|---|
| Select tests | `--include smoke`, `--exclude "slow OR flaky"`, `--test "Suite.Name*"`, `--suite checkout` (full name since 7.0; `--test` and `--include` add up) |
| Variables | `--variable ENV:staging`, typed `--variable "RETRIES: int:3"` (7.3), secret `--variable "TOKEN: Secret:$TOKEN"` (7.4), `--variablefile variables/staging.py` |
| Argument files | `robot --argumentfile ci.args tests` (environment variables are expanded inside since 7.4) |
| Outputs | `--outputdir results`, `--output output.json` for JSON (7.2), `--xunit xunit.xml`, `--log NONE`, `--loglevel DEBUG:INFO` |
| Console | `--console dotted|quiet|verbose`; custom console loggers with `--console` (7.5, also for rebot) |
| Rerun failed | `--rerunfailed results/output.xml --output rerun.xml`, `--rerunfailedsuites`; merge with `rebot --merge output.xml rerun.xml` |
| Control | `--dryrun`, `--exitonfailure`, `--skiponfailure tag`, `--randomize all`, `--rpa` for tasks |
| Markdown tests | `*.robot.md` are run automatically (7.5); other `*.md` with `--parseinclude` / `--extension` |
| Smaller logs | `rebot --removekeywords passed --flattenkeywords name:Wait*` |
| Exit code | 0 all passed; 1–250 number of failed tests; 251+ errors (252 invalid data or options, 253 stopped by user) |

**pabot** (parallel): `pabot --processes 4 --outputdir results tests` splits by suite; `--testlevelsplit` splits by test (needs independent tests); `--pabotlib` with PabotLib locks and value sets keeps parallel tests from sharing accounts. Results are merged into one `output.xml`.

## Safety rules

- Secrets only via the CI secret store and `Secret` variables; never echo them in scripts.
- Run destructive RPA tasks only in approved environments; keep production runs explicit and separate.
- `results/` can contain personal data from the system under test: keep artifact retention short and access internal.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `LookupError: unknown encoding: utf-8:surrogateescape`, then `RecursionError` | Seen with RF 7.5.1 when output is piped: `PYTHONIOENCODING` contains an error handler and RF uses it as an encoding name. Set `PYTHONIOENCODING=utf-8` (the generated pipelines do) |
| Step stops right after the first run | The CI shell uses `set -e`; the generated block starts with `set +e` and exits with the final count |
| `Importing library 'Browser' failed` / no browsers | Run `rfbrowser init` after installing (Node.js needed), or use the Browser Docker image |
| `[ ERROR ] Collecting failed tests from 'output.xml' failed` | The first run produced no output (data error, 252): read its console log |
| Parallel runs fail randomly | Tests share accounts or data: use PabotLib locks / value sets, or `--testlevelsplit` only for independent tests |
| xunit shows no tests in the CI | Path: `--xunit` is relative to `--outputdir` (`results/xunit.xml`) |
