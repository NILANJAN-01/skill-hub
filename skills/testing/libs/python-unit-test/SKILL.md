---
name: python-unit-test
description: "Unit test any Python (.py) file function by function and method by method, run the tests, and get a diagnosis with a suggested fix for each failure, plus static bug findings (mutable defaults, bare except, swallowed errors) and weak-test checks. Use when the user asks to unit test, add or run tests for a .py file, find why a Python test fails, fix a failing pytest/unittest test, find untested functions, or check Python code for bugs."
license: Complete terms in the repository README
compatibility: Needs Python 3.8+ (standard library only) to run the script. It uses pytest when installed and falls back to unittest. Line coverage needs the coverage package.
metadata:
  title: "Python unit tests: write, run, diagnose and suggest fixes"
  category: testing-tools
---

# Python unit tests

`scripts/pyunit.py` plans, runs and diagnoses unit tests for one Python file at a time.

| Command | What it does |
|---|---|
| `plan FILE` | Lists functions and methods (arguments, branches, exceptions raised), the tests linked to each (`[ ]` = untested), static bug findings in the source, and weak tests |
| `scaffold FILE` | Writes a `unittest` skeleton for the untested units. Never overwrites an existing file |
| `run FILE` | Runs the linked tests, then prints each failure with its location, the code around it, the likely cause (code, test or setup) and a suggested fix. Writes `pyunit-report/report.json` |
| `diagnose` | Prints the diagnosis from the last run again |

Tests are found as `test_<file>.py` or `<file>_test.py` next to the file, in its package root, or in `tests/`. A test is linked to a function when it calls it or has its name in the test name. Use `--test-file` to choose other test files.

## When to use

- "Unit test this .py file", "write tests for every function in utils.py", "run the tests for parser.py".
- "Why does this test fail and how do I fix it?", "suggest a fix for this failing test".
- "Which functions have no tests?", "are these tests any good?"

## When NOT to use

- Kotlin code (use the Kotlin unit-test skill), or UI/end-to-end suites that need a device or browser.
- Whole-project test orchestration, which is the project's own test runner's job.

## Procedure

`scripts/…` is the `scripts` folder inside this skill's folder. Run commands from the project root.

1. **Plan.** `python scripts/pyunit.py plan path/to/file.py`. Read the file itself too, so you know what each function is *supposed* to do.
2. **Write the tests.** If none exist, run `scaffold`, then replace every TODO. Per function: a normal case, edge cases (empty, `None`, zero, boundaries) and each exception it raises (`assertRaises`). Assert exact results. Follow [references/writing-tests.md](references/writing-tests.md). Tests describe the intended behaviour, not whatever the code returns now.
3. **Run.** `python scripts/pyunit.py run path/to/file.py` (add `-k name` for one test with pytest, `--coverage` for line coverage).
4. **Act on each failure using the diagnosis** ([references/diagnosis.md](references/diagnosis.md) lists the rules):
   - *likely cause: code* → the source is wrong. Propose the fix as a small diff and show the failing line. Ask the user before changing production code.
   - *likely cause: test* or *setup* → fix the test (mock the file system/network, fix the import, finish the TODO).
   - *test or code (decide)* → an assertion differs. Read the function's intent (docstring, callers, name) and decide which side is wrong. Say which and why.
5. **Resolve findings.** Fix the `PT…` test-quality findings (no assertion, empty, TODO, skipped, trivial) and consider each `PY…` source finding. Add tests for the untested functions.
6. **Re-run** until green, then summarize: tests passed and failed, bugs found with suggested fixes, units still untested, coverage if measured.

## Rules

- **Never weaken a test to make it pass:** no deleted assertions, loosened expected values, `skip`, or swallowed exceptions.
- **Don't edit production code without the user's agreement.** Suggest the fix; apply it only when asked.
- **Keep tests isolated.** Mock network, database, clock, randomness and real files (use `tempfile`).
- **Report honestly.** Say when a run could not happen (missing dependency, import error) and never claim a pass without a run that shows it.
- Running tests executes the project's code. Ask first for code with side effects.

## Troubleshooting

| Problem | Fix |
|---|---|
| `no tests found for FILE` | Run `scaffold FILE`, or pass `--test-file` |
| `The test run did not produce results` | Read the output shown: usually an import error or a syntax error in the code or tests |
| Plain `def test_x()` functions don't run | pytest isn't installed, and the fallback runs `unittest.TestCase` tests only. Install pytest or use TestCase classes |
| No coverage line | Install the `coverage` package and pass `--coverage` |
| `timed out` | The code has an infinite loop or waits on I/O; mock it, or raise `--timeout` |

## Run the tests

```bash
python -m unittest discover -s scripts -p "test_*.py"
```
