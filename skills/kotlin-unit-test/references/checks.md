# Verification rules

`ktest.py verify`, `run` and `mutate` report these findings.
- **Errors** make the verdict FAILED and the exit code 1.
- **Warnings** fail the verdict only with `--strict`.

A filtered run (`--class`, `--method`, `--test`) only reports findings for the selected classes and tests.

| Rule | Severity | Finding | Why it matters / how to fix |
|---|---|---|---|
| KT001 | error | Test without assertions | The test passes even if the code is wrong. Assert the result, the state, or the expected exception. Helper functions in test sources that assert (for example `assertValidOrder(x)`) count. |
| KT002 | error | Empty test | It always passes. Write the test or delete it. |
| KT003 | error | Unfinished test (`TODO()`, `NotImplementedError`, `fail("not implemented")`) | Usually left from `scaffold`. Write the real test. |
| KT004 | warning | Assertion that can never fail (`assertTrue(true)`, `assertEquals(x, x)`, `true shouldBe true`) | It checks nothing. Compare the real result with an expected value. |
| KT005 | warning | Exception swallowed (empty `catch`, or a `catch` that only logs) | Failures are hidden. Use `assertFailsWith<…> { }` / `assertThrows`, or let the exception propagate. |
| KT006 | warning | `Thread.sleep` / `delay` outside `runTest` | Slow and flaky. Use `runTest` (virtual time), a fake clock, or wait for a condition. |
| KT007 | warning | Disabled test (`@Disabled`, `@Ignore`, `x`-prefixed Kotest) | Disabled tests hide regressions. Fix it or delete it, and track the reason. |
| KT008 | info | Uses the current time or randomness | Results change between runs. Inject a `Clock`, or seed the `Random`. |
| KT009 | warning/info | Real driver, network or file I/O in a unit test | A unit test must not start Appium/WebDriver/UiDevice (warning) or call the network or disk (info). Mock the driver, use MockWebServer, or a temp folder. |
| KT010 | error | JUnit 4 `@Test` on the JUnit 5 platform without `junit-vintage-engine` | Those tests are **silently not run**. Switch the import to `org.junit.jupiter.api.Test` / `kotlin.test.Test`, or add the vintage engine. |
| KT011 | warning | Method has no test | No test calls the method or is named after it. Write tests (`scaffold --class X --method m`). |
| KT012 | warning | Class has no tests | None of its methods is tested. |
| KT013 | error | Failing test | Read the message and stack trace in the report. Decide whether the code or the test is wrong. Never weaken the test to make it pass. |
| KT014 | warning | Declared test was not executed (full runs only) | The engine didn't discover it: wrong annotation, wrong source set, excluded by the build, or a JUnit 4/5 mix. |
| KT015 | error | No tests were executed | The engine isn't configured, the filter matched nothing, or the build stopped early. |
| KT016 | warning | Results older than the sources (`verify`/`report` only) | Run the tests again before trusting the report. |
| KT017 | warning | Linked tests never execute the method (0% coverage) | The test probably exercises a mock, a fake, or another overload instead of the real method. |
| KT018 | error | Line coverage below `--min-coverage` | Add tests for the uncovered lines of that class. |
| KT019 | warning | Survived mutant (`mutate`) | A small bug in that line wasn't noticed by any test. Add a case or an assertion that would fail for it. |
| KT020 | info | Test not linked to any production method | Call the method directly in the test, or put its name in the test name, so the report counts the test for that method. |
| KT021 | info | Only checks mock interactions (`verify {}`) | Fine for "was the event sent?" tests. If the method returns or changes something, assert that too. |
| KT022 | warning | Method only has tests that check nothing | Every linked test is empty, unfinished or assertion-free, so the method is effectively untested (status **weak**). Add real assertions. |
| KT024 | info | Skipped at run time (assumption failed) | Check that the assumption holds where the tests normally run. |
| KT025 | info | Slow unit test (`--slow`, default 2 s) | Unit tests should take milliseconds. Look for real I/O, sleeps or heavy setup. |
| KT027 | info | Test class without tests | Leftover file or missing annotations. |
| KT028 | info | Instrumented tests (`androidTest`) not run | They need a device: `./gradlew connectedAndroidTest`. |
| KT029 | error | Build or compilation failed | The finding shows the compiler errors; the full log is in `ktest-report/build.log`. |

## Method status in the report

| Status | Meaning |
|---|---|
| tested | At least one linked test with assertions ran and passed, and none failed |
| failing | At least one linked test failed |
| weak | Linked tests pass, but all of them are empty, unfinished or have no assertions (KT022) |
| untested | No test calls or names the method |
| not run | Linked tests exist but did not run (filtered out, disabled engine, build failure) |
| skipped | All linked tests were skipped |
| excluded | Not counted: private, abstract (no body), or `toString`/`equals`/`hashCode` overrides |

## Mutation check

`mutate` changes one operator at a time inside the class's methods, then runs only that class's tests. The mutations are:
- `==` ↔ `!=`;
- `<` → `<=`, `>` → `>=`, `<=` → `<`, `>=` → `>`;
- `&&` ↔ `||`;
- `+` ↔ `-`, `*` → `/`, `/` → `*`, `%` → `*`, `+=` ↔ `-=`;
- `true` ↔ `false`;
- removing `!`.

Each mutant gets one of these results:

| Result | Meaning |
|---|---|
| killed | A test failed. Good: the tests notice this bug |
| survived | All tests still passed. The tests miss this behaviour |
| timeout | The tests hung. Counted as killed |
| compile error | The change didn't compile. Not counted |

Score = killed / (killed + survived). Aim for 80% or more on business logic. The tool works through mutants evenly across methods, up to `--max-mutants`. It restores the original file after each mutant, then re-runs the tests on the restored code to confirm the restore.
