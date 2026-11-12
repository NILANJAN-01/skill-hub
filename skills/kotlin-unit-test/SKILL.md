---
name: kotlin-unit-test
description: "Write, run and verify unit tests for Kotlin code (apps, libraries, Android, Appium/Selenium page objects) with Gradle, Maven or kotlinc, then produce an HTML report of results, coverage and weak tests (no assertions, disabled, untested methods, mutation check). Use when the user asks to unit test Kotlin code, add or run Kotlin tests, get a test or coverage report, or check test quality."
license: Complete terms in the repository README
compatibility: Needs Python 3.8+ (standard library only) to run the scripts, and a JDK with the project's build tool (Gradle wrapper, Maven, or kotlinc plus the JUnit console launcher) to run the tests. Coverage needs JaCoCo or Kover configured in the build.
metadata:
  title: "Kotlin unit tests: class/method-wise testing, verification and HTML report"
  category: testing-tools
---

# Kotlin unit tests

`scripts/ktest.py` plans, runs and checks unit tests for Kotlin code, and writes `ktest-report/index.html` (one self-contained page) and `ktest-report/report.json`.

| Command | What it does |
|---|---|
| `plan` | Lists every class and its methods, and which tests are linked to each method. `[ ]` means untested |
| `scaffold --class X` | Writes a test-class skeleton with one TODO test per case for the untested methods of `X`. It never overwrites an existing file |
| `run` | Runs all tests, one class (`--class X`) or one method (`--class X --method m`), then verifies and writes the report |
| `verify` | Checks test quality and the latest results without running anything (exit code 1 on errors, so it works as a CI gate) |
| `mutate --class X` | Puts small bugs into `X` one at a time (`+`→`-`, `>`→`>=`, `true`→`false`, …), runs its tests, and restores the file. It shows which bugs no test catches |
| `report` | Rebuilds the HTML report from existing results |

How tests are linked: a test class `FooTest` (or `FooTests`, `FooSpec`, `FooIT`) belongs to class `Foo`. A test is linked to a method when its body calls that method, or when its name contains the method name (for example `` `add returns sum` `` is linked to `add`). Calls inside mock stubbing or verification (`every {}`, `verify {}`, `whenever()`) don't count. Top-level and extension functions are grouped by file (`Strings.kt` gives `StringsKt`).

## When to use

- "Write unit tests for this Kotlin class", "test every method of …", "generate tests for the untested methods".
- "Run the Kotlin tests", "run the tests for class X / method Y", "give me an HTML test report", "what is the coverage".
- "Are these tests any good?", "find tests that don't assert anything", "which methods have no tests".
- Kotlin test-automation code (page objects, helpers, utilities for Appium, Selenium or Espresso): unit-test its logic with a mocked driver.

## When NOT to use

- Running UI/instrumented tests on a device (`androidTest`, `connectedAndroidTest`) or end-to-end suites. The scripts list instrumented tests but don't run them.
- Java-only projects (the parser reads `.kt` files only).

## Procedure

`scripts/…` means the `scripts` folder inside this skill's folder. Run commands from the project root. `<project>` defaults to the current folder.

1. **Check the setup.** You need a JDK (`java -version`) and a build: a Gradle wrapper (`gradlew`), `pom.xml`, or loose `.kt` files with `kotlinc`. For loose files or scripts, see [references/setup.md](references/setup.md). Make sure the project's tests can run at all (`python scripts/ktest.py run --dry-run` shows the command). Ask before adding dependencies (JUnit 5, MockK, kotlinx-coroutines-test, JaCoCo) to the build.
2. **Plan, class by class:**
   ```bash
   python scripts/ktest.py plan
   python scripts/ktest.py plan --class OrderService
   ```
   Agree with the user which classes are in scope. Default order: business logic first, then helpers. Skip generated code, DI modules and plain data holders.
3. **Write the tests, one class at a time.**
   - Optionally create the skeleton first: `python scripts/ktest.py scaffold --class OrderService`.
   - Then replace every `TODO` with a real test. For each public/internal method, cover the normal case, edge cases (empty, zero, null, boundaries) and error cases (`assertFailsWith`/`assertThrows`). Assert exact results or state changes.
   - Follow [references/writing-tests.md](references/writing-tests.md): naming, MockK, coroutines, Android ViewModels, automation code with a mocked driver.
   - Read the method's code before writing its test. A test must describe the intended behaviour, not copy whatever the code does now.
4. **Run class-wise, then method-wise when fixing:**
   ```bash
   python scripts/ktest.py run --class OrderService                    # all tests linked to the class
   python scripts/ktest.py run --class OrderService --method total     # only tests linked to total()
   python scripts/ktest.py run --test com.acme.OrderServiceTest#"total adds tax"
   ```
   A filtered run judges only the selected class and tests.
   - **If a test fails, decide whether the test or the code is wrong.** If the code is wrong, report the bug to the user. Don't change production code to make a test pass unless the user agrees.
   - **Never weaken a test to make it pass:** don't delete assertions, loosen expected values, add `@Disabled`, or catch the exception.
5. **Verify the tests themselves:**
   ```bash
   python scripts/ktest.py verify
   ```
   Fix every error, then the warnings:
   - assertion-free, empty, TODO or trivial tests;
   - JUnit 4 tests that never run;
   - failing tests;
   - untested methods.

   The rules and fixes are in [references/checks.md](references/checks.md).
6. **Prove the tests catch bugs** (for important classes, or when the user asks how good the tests are):
   ```bash
   python scripts/ktest.py mutate --class OrderService --max-mutants 12
   ```
   - Each **survived** mutant is a change to the code that no test noticed. Add a test or a stronger assertion for that line, then run `mutate` again.
   - The source file is restored after every mutant. A backup (`*.ktest-orig`) is restored automatically if a run is interrupted.
   - Run it with a clean working tree (commit or stash first).
7. **Full run and report:**
   ```bash
   python scripts/ktest.py run --coverage                  # all modules; add --min-coverage 80 to enforce a minimum
   ```
   Open `ktest-report/index.html`. It shows:
   - the verdict, tiles, findings;
   - classes → methods with status, linked tests and coverage;
   - test results with failure messages and stack traces;
   - the mutation results and the build command.

   Summarize for the user: how many tests passed and failed, the methods still untested, remaining findings, coverage, and the mutation score.

Other options:
- `--tool gradle|maven|kotlinc`: choose the build tool.
- `--variant release`: Android unit-test variant (default debug).
- `--coverage-task NAME`: a custom coverage task.
- `--build-arg ARG`: an extra argument passed to the build tool.
- `--timeout`: seconds before the build is stopped.
- `--verbose`: show the build output as it runs.
- `--strict`: warnings fail the verdict too.
- `--include-private`: also plan and check private methods.
- `--json`: JSON output for `plan` and `verify`.

## Rules

- **Tests must check behaviour.** Every test needs at least one assertion on a result, a state, or an expected exception. Calling the code without checking it is not a test.
- **Keep unit tests isolated.** Replace network, database, clock, randomness, Android framework and WebDriver/Appium drivers with fakes or mocks. Don't use `Thread.sleep`.
- **Don't edit generated files:** reports, build outputs, and code-generated sources.
- **Report honestly.** Say which tests fail and why, which methods are still untested, and when a run could not happen (no JDK, build error). Never claim tests pass without a run that shows it.

## Troubleshooting

| Problem | Fix |
|---|---|
| `no build found` | Install a JDK and use the project's Gradle wrapper, or set up a small build for loose files ([references/setup.md](references/setup.md)) |
| `KT029 Build or compilation failed` | Read the error lines in the finding and in `ktest-report/build.log`; fix the compile error first |
| `KT015 No tests were executed` | The test engine isn't configured (`useJUnitPlatform()`), the filter matched nothing, or the module has no test dependencies |
| `KT010` / `KT014` JUnit 4 tests not run | Use `org.junit.jupiter.api.Test` / `kotlin.test.Test`, or add `junit-vintage-engine` |
| `no tests found for class X` | No test is linked yet: `scaffold --class X`, or name the test class `XTest` |
| A test isn't linked to the method it tests | Call the method directly in the test or put the method name in the test name (KT020) |
| No coverage in the report | Configure JaCoCo or Kover ([references/setup.md](references/setup.md)); coverage tasks usually only run when all tests pass |
| Windows: test names with `&`, `|`, `%`, `^`, `!` | They are replaced with `*` in the Gradle filter, which may select a few extra tests |
| `the tests must pass before a mutation check` | Fix the failing tests first; mutation needs a green baseline |

## Run the tests

```bash
python -m unittest discover -s scripts -p "test_*.py"
```

The tests need no JDK. A fake Gradle wrapper writes real JUnit and JaCoCo XML, so these all run against a sample project:
- the Kotlin parser;
- the class/method linking;
- every verification rule;
- class-wise and method-wise runs;
- build-failure reporting;
- scaffolding;
- the mutation check, including restoring the source.
