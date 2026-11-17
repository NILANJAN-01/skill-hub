---
name: robotframework-results
description: "Find why Robot Framework tests or tasks failed: read output.xml or output.json, log.html and the console, sort failures by cause (assertion, missing keyword, variable, timeout, setup, UI element, connection, import), show the failing keyword chain, spot flaky tests with --rerunfailed and compare runs. A script summarises results. Use when a Robot run failed, is flaky or got slow."
license: MIT
compatibility: The script needs Python 3.8+ (standard library only) and reads output.xml from RF 4-7 (RF 7 ISO timestamps and RF 6 start/end times) and output.json from RF 7.2+.
metadata:
  title: "Robot Framework results: failures, flaky tests and slow keywords"
  category: robotframework-tools
---

# Robot Framework results and debugging

Robot Framework writes everything to `output.xml` (or `output.json`), from which `log.html` and `report.html` are generated. Read that evidence to find the real cause before changing a test.

## When to use

- A run (local or CI) failed and the cause is not obvious from the report.
- Tests pass on rerun (flaky), fail only in CI, or the suite got slow.
- Comparing two runs: what newly fails after a change or an upgrade.

## When NOT to use

- Writing or modernising suites: use `robotframework-test-authoring`.
- Pipeline setup, parallel runs with pabot, rerun-and-merge in CI: use `robotframework-ci`.

## Procedure

1. **Summarise the run:**
   ```bash
   python scripts/rf_results.py results/output.xml
   python scripts/rf_results.py results/output.json                       # JSON results (RF 7.2+: robot --output output.json)
   python scripts/rf_results.py results/output.xml --rerun results/rerun.xml # flaky = failed, then passed on rerun
   python scripts/rf_results.py results/output.xml --baseline last-green/output.xml
   python scripts/rf_results.py results/output.xml --json
   ```
   It prints totals, execution errors (import failures, syntax problems, deprecation warnings: often the real root cause), every failed test with its cause category, the **failing keyword chain** (`Check Total > BuiltIn.Should Be Equal`) and the message, failures by cause and by tag, skipped tests with reasons, the slowest tests and keywords, and with `--rerun` / `--baseline` the flaky tests, new failures and fixes.
2. **Read the evidence for each failure** in `log.html` (expand the failing keyword: arguments, return values, screenshots, messages). Set `--loglevel DEBUG:INFO` (or `TRACE`) when arguments are missing from the log; errors and warnings can be collapsed in the log since 7.4.
3. **Reproduce one test:** `robot --test "Suite.Test Name" --loglevel TRACE tests/`; `robot --dryrun tests/` finds missing keywords, wrong argument counts and import errors without running anything.
4. **Fix by cause:**

   | Category | Typical message | Fix |
   |---|---|---|
   | `assertion` | `Total differs: 12 != 10`, `... should be ...` | Real bug, or wrong test data/expectation: check data setup |
   | `keyword-not-found` | `No keyword with name 'X' found.` | Missing `Library`/`Resource` import, a typo, or a library version change; `--dryrun` lists them |
   | `variable` | `Variable '${x}' not found.` | Scope (`VAR ... scope=SUITE`), a missing `--variable`/variable file, or an unset environment variable |
   | `timeout` | `Test timeout 2 minutes exceeded.` | Something never happened: find the last keyword in the chain; wait for a condition, do not raise the timeout blindly |
   | `setup` / `teardown` | `Parent suite setup failed:` | Fix the setup first: every test below it fails with the same message |
   | `import` | `Importing library 'X' failed` | Library not installed in this environment, wrong Python, or `rfbrowser init` not run |
   | `ui-element` | `Element ... not visible`, `TimeoutError: waiting for locator` | Locator out of date, page not ready, overlay in the way: use library wait keywords, update locators |
   | `connection` | `ConnectionError`, `Max retries exceeded`, `status code 503` | Environment down or wrong URL: check the environment before the tests |
5. **Flaky tests:** rerun only failures (`robot --rerunfailed output.xml --output rerun.xml tests/`), compare with `--rerun`, and merge results with `rebot --merge output.xml rerun.xml`. A test that passes on rerun needs a ticket: usual causes are shared test data between parallel runs (pabot), fixed `Sleep`s, and order dependence (find it with `robot --randomize tests`).
6. **Slow suites:** the slowest keywords list shows where time goes (often `Sleep`, `Wait Until Keyword Succeeds` with long retries, or browser start-up per test); move browser start-up to suite setup and run suites in parallel with pabot.

## Safety rules

- `output.xml` and `log.html` contain every non-secret keyword argument: share them only inside the team; use `Secret` variables (RF 7.4+) so credentials show as `<secret>`.
- Do not mark failing tests as skipped or remove assertions to make a run green; record why a test is quarantined (`[Tags]    quarantine` excluded with `--exclude quarantine`, plus a ticket).

## Troubleshooting

| Symptom | Fix |
|---|---|
| Script says it cannot read the output | The run was interrupted and the file is incomplete: rerun, or check disk space; JSON needs RF 7.2+ |
| Every test fails with the same message | Suite setup, library import or environment problem: read the execution errors first |
| `LookupError: unknown encoding: utf-8:surrogateescape`, then `RecursionError` | Seen with RF 7.5.1 when output is piped (CI): `PYTHONIOENCODING` contains an error handler that RF passes on as an encoding name. Set `PYTHONIOENCODING=utf-8` (or unset it) |
| Log too large to open | `--removekeywords passed` / `--flattenkeywords` with rebot, or `--splitlog` |
| Different results locally and in CI | Compare Python, RF and library versions (`pip freeze`) and environment variables |
