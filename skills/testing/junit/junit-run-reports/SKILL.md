---
name: junit-run-reports
description: "Run JUnit tests (Java or Kotlin) with Gradle, Maven or the ConsoleLauncher, select by class, method, package or tag, rerun failures, and explain results from JUnit XML or Open Test Reporting files: each failure with cause and fix, flaky tests, skipped tests without a reason, slowest tests, a Markdown CI summary. Use when JUnit tests must be run, fail, flake or need a report."
license: Complete terms in the repository README
compatibility: Needs Python 3.8+ (standard library only). Running tests needs JDK 17+ and the project's Gradle wrapper or Maven (or the JUnit ConsoleLauncher jar); reading reports needs nothing else. Part of the junit-tools bundle with junit-test-authoring and junit-migration.
metadata:
  title: "JUnit: run tests and explain the results"
  category: junit-tools
---

# JUnit: run tests and explain the results

Gradle, Maven and IDEs all run JUnit through the **JUnit Platform**, and all write the same legacy JUnit XML (`TEST-<class>.xml`). JUnit 6 can also write the richer **Open Test Reporting** XML (`open-test-report.xml`). `scripts/junit_report.py` builds the right command for a selection, runs it, and turns those reports into a summary that names a likely cause and fix for every failure.

## When to use

- "Run only `OrderServiceTest`", "run the tests tagged `fast`", "rerun the failures", "stop at the first failure".
- A build reports failing tests: "why does this fail?", "summarise the test results", "which tests are flaky or slow?".
- A CI job needs a short Markdown summary of the JUnit results.

## When NOT to use

- Writing tests or setting up JUnit: `junit-test-authoring`. Tests silently not running, or a JUnit 4/5 upgrade: `junit-migration`.
- Android instrumented tests on a device: `uiautomator-run-debug`.
- Kotlin coverage and mutation checks: `kotlin-unit-test`.

## Procedure

`scripts/junit_report.py` is in this skill's folder. Run it from the project root (or pass `--project`). `cmd`, `parse` and `results` only read files.

1. **Build the command for the selection.**
   ```bash
   python scripts/junit_report.py cmd --class com.shop.OrderServiceTest#placesOrder          # tool auto-detected
   python scripts/junit_report.py cmd --tool maven --module billing --tag fast --exclude-tag slow --rerun 2
   python scripts/junit_report.py cmd --tool console --package com.shop --class-path build/classes/java/test:build/classes/java/main
   ```
   Gradle: `./gradlew :app:test --tests 'com.shop.OrderServiceTest.placesOrder'` (`--fail-fast` supported). Gradle has no command-line tag filter, so the script prints a `tasks.test` snippet that reads `-PincludeTags` / `-PexcludeTags`; reruns need the `org.gradle.test-retry` plugin. Maven: `-Dtest='OrderServiceTest#placesOrder'`, `-Dgroups=fast -DexcludedGroups=slow`, `-Dsurefire.rerunFailingTestsCount=2`, `-Dsurefire.skipAfterFailureCount=1`. More in [references/running.md](references/running.md).
2. **Run and summarise in one step.**
   ```bash
   python scripts/junit_report.py run --class com.shop.OrderServiceTest           # Gradle wrapper or mvn, then the summary
   python scripts/junit_report.py run --tool maven --tag fast --json
   python scripts/junit_report.py run ... --dry-run                               # only print the command
   ```
   It only summarises reports written during this run, so stale results from an earlier build are not mixed in.
3. **Or summarise existing results** (from CI artifacts, a teammate, an IDE export):
   ```bash
   python scripts/junit_report.py results .                                       # build/test-results, surefire/failsafe-reports, open-test-report.xml
   python scripts/junit_report.py parse target/surefire-reports build/reports/junit/open-test-report.xml
   python scripts/junit_report.py results . --markdown >> "$GITHUB_STEP_SUMMARY"
   ```
4. **Read the summary.** For each failure: the exception type, message, expected and actual values when present, the first stack frame in the test class, the cause and the fix ([references/failures.md](references/failures.md) lists every cause). It also lists flaky tests (failed, then passed on a rerun: Surefire `flakyFailure`, Gradle test-retry), skipped tests with their reasons, and the slowest tests. Exit code 1 means failures.
5. **Fix and prove it.** Fix the cause, rerun only that test, then rerun it several times before calling a flaky test fixed (Maven `-Dsurefire.rerunFailingTestsCount`, or a loop). Finish with the full suite.
6. **Report** the command, the counts, each failure with its cause, and what changed.

## Failure causes (short)

| Id | Typical message | Usual fix |
|---|---|---|
| `assertion` | `AssertionFailedError: expected: <30> but was: <27>` | Decide whether the code or the expectation is wrong |
| `multiple-failures` | `MultipleFailuresError` | Every `assertAll` failure is listed; fix each |
| `null-pointer` | `NullPointerException` | Setup did not run: JUnit 4 `@Before` in a Jupiter class, mocks without `MockitoExtension`, a field never assigned |
| `parameter-resolution` | `No ParameterResolver registered for parameter` | Missing `@ExtendWith`, or a parameter on a plain `@Test` |
| `parameterized-config` | `Failed to convert`, `at least one set of arguments` | Source values vs parameter types and count |
| `timeout` | `timed out after`, `execution exceeded timeout` | Find the slow step; wait for conditions |
| `version-mismatch` | `NoSuchMethodError ... org.junit`, `OutputDirectoryProvider not available` | BOM, launcher dependency, Surefire 3 |
| `lifecycle-config` | `@BeforeAll method ... must be static` | Static / companion `@JvmStatic`, or `PER_CLASS` |
| `mockito`, `spring-context` | `UnnecessaryStubbingException`, `Failed to load ApplicationContext` | See the reference |

## Safety rules

- Running tests executes project code: tests may write files, call services or use databases. Run them against test environments only, and check what an unfamiliar suite does first.
- `run` uses the project's own wrapper (`gradlew`, `mvnw`) or the installed `mvn`/`gradle`; it does not download build tools or change build files.
- Reports and logs can contain data from the tests (names, tokens printed by mistake). Share them only with people who need them; don't commit them.
- Never "fix" a failing test by deleting or `@Disabled`-ing it without the user's agreement.

## Troubleshooting

| Problem | Fix |
|---|---|
| `no new test reports were written` | The build failed before tests ran (compile error: read the build output), or the selection matched nothing |
| Maven multi-module: `No tests matching pattern` | `-pl <module> -am -Dsurefire.failIfNoSpecifiedTests=false` (the script adds it with `--module`) |
| Gradle `--tests` matches nothing | Use the fully qualified class, `Class.method`, or wildcards (`'*OrderServiceTest'`); nested classes are `Outer$Inner` |
| Parameterized names are hard to match | Select the method (`Class.method`), not one invocation |
| Report XML `not valid XML` | The JVM was killed mid-write (timeout, OOM): rerun; check memory settings |
| Flaky test passes locally, fails in CI | Order dependence, shared state, time zone or locale, parallelism: see the checklist in `failures.md` |

## References

- [references/running.md](references/running.md): Gradle, Maven (Surefire and Failsafe), ConsoleLauncher and IDE options, selection syntax, tags, reruns, parallel forks, report locations, enabling Open Test Reporting.
- [references/failures.md](references/failures.md): every failure cause with explanation and fix, plus a flaky-test checklist.
