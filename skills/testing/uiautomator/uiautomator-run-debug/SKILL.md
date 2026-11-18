---
name: uiautomator-run-debug
description: "Run Android UI Automator tests (Kotlin or Java) with Gradle or adb am instrument, filter by class, method, annotation or shard, and explain failures from raw instrumentation output or JUnit XML: ElementNotFoundException, StaleObjectException, null UiObject2, process crashes, missing instrumentation, UiAutomation already registered. Use when UI Automator tests must be run or fail, flake or hang."
license: Complete terms in the repository README
compatibility: Needs Python 3.8+ (standard library only). Running tests needs adb (Android SDK Platform-Tools), the app and test APKs and a device or emulator; parsing saved output needs nothing else. Part of the uiautomator-tools bundle; uses adb-connect for connection problems and android-logcat-analyzer for crashes when installed.
metadata:
  title: "UI Automator: run tests and debug failures"
  category: uiautomator-tools
---

# UI Automator: run tests and debug failures

UI Automator tests are instrumented tests: Gradle builds and installs two APKs (the app and the test APK) and `AndroidJUnitRunner` runs them on the device. `scripts/uia_run.py` builds the right command, runs it, and turns the output into a summary in which every failure has a likely cause and a fix.

## When to use

- "Run the UI Automator tests", "run only this class / method / smoke tests", "shard the suite".
- A run failed, hung, crashed or reported fewer tests than expected; the user pastes `am instrument` output or a Gradle report.
- Flaky UI Automator tests that pass and fail on the same code.

## When NOT to use

- adb cannot see the device (`unauthorized`, `offline`, no devices): `adb-connect` first.
- The app itself crashes and you need the crash analysed: `android-logcat-analyzer` (this skill saves the logcat).
- Writing or migrating tests: `uiautomator-test-authoring`, `uiautomator-migration`.

## Procedure

`scripts/uia_run.py` is in this skill's folder. `doctor`, `cmd`, `parse` and `results` never change the device.

1. **Check the device and the installed test APK.**
   ```bash
   python scripts/uia_run.py doctor [--serial emulator-5554]
   ```
   It finds adb (PATH, `$ADB`, the SDK), lists devices, shows `pm list instrumentation` (the `<test.package>/<runner>` names) and warns when animations are on.
2. **Pick how to run.**
   - Whole module, builds and installs for you (reports in `build/reports/androidTests/connected/`):
     ```bash
     ./gradlew :app:connectedDebugAndroidTest
     python scripts/uia_run.py cmd --gradle app --class com.example.app.test.LoginTest        # prints the command
     python scripts/uia_run.py cmd --gradle app --variant freeDebug --annotation com.example.Smoke
     ```
   - Fast reruns of APKs already installed (`./gradlew :app:installDebug :app:installDebugAndroidTest`):
     ```bash
     python scripts/uia_run.py run --test-package com.example.app.test --class 'com.example.app.test.LoginTest#signIn' --out run.txt --logcat logcat.txt
     python scripts/uia_run.py run --runner com.example.app.test/com.example.CustomRunner --size large
     python scripts/uia_run.py run --test-package com.example.app.test --shards 4 --shard-index 0
     python scripts/uia_run.py run ... --dry-run      # show the adb command only
     ```
     Filters map to `AndroidJUnitRunner` arguments: `--class` (comma list, `Class#method`), `--package-filter`, `--size`, `--annotation`, `--not-annotation`, `--shards`/`--shard-index`, `--log-only` (list tests without running), `--debug` (wait for a debugger), `--arg KEY=VALUE` (anything else, for example credentials your test reads with `InstrumentationRegistry.getArguments()`).
3. **Read the summary.** For each failed, errored or interrupted test it prints the first message line, the first stack frame in your code, the cause and the fix. Run-level problems (crash, missing instrumentation, no tests) are listed separately. Exit code 1 means failures.
4. **Summarise saved results** (from CI, a teammate, or Gradle):
   ```bash
   python scripts/uia_run.py parse run.txt                       # am instrument -r output, plain output or JUnit XML
   python scripts/uia_run.py results <project-dir>               # every build/outputs/androidTest-results/**/TEST-*.xml
   python scripts/uia_run.py parse run.txt --json
   ```
5. **Fix, then prove it.** Apply the fix for the reported cause ([references/failures.md](references/failures.md) has the full table), rerun only the failing test, then rerun it several times (`for i in 1 2 3 4 5; do ...; done`) before calling a flaky test fixed. Finish with the whole suite.
6. **Report** the command used, the counts, each failure with its cause, and what was changed.

## Failure causes (short)

| Id | Typical message | Usual fix |
|---|---|---|
| `element-not-found` | `ElementNotFoundException` | Predicate wrong (full vs short id, `textAsString()`), wrong screen, raise `timeoutMs` |
| `null-uiobject2` | NPE `... UiObject2.click() on a null object reference` | `device.wait(Until.findObject(sel), t)` + `assertNotNull` instead of `findObject(...).click()` |
| `stale-object` | `StaleObjectException` | Look the element up again after the screen changes |
| `process-crashed` | `INSTRUMENTATION_RESULT: shortMsg=Process crashed.` | Read the saved logcat; fix the crash; consider Test Orchestrator |
| `instrumentation-missing` | `Unable to find instrumentation info`, `INSTRUMENTATION_FAILED` | Install both APKs, use the name from `doctor` |
| `uiautomation-busy` | `UiAutomationService ... already registered` | Stop Appium's uiautomator2 server or the other run |
| `no-root-window` | `Failed to get root in active window` | Wake and unlock the screen; wait for the app |
| `idle-timeout` | `could not get idle state` | Wait for elements instead of idle; turn animations off |
| `no-tests` / `incomplete-run` | `No tests found`, `Expected 10 tests, received 4` | Fix filters; find the crash that stopped the run |

## Safety rules

- Running tests taps, types and changes data on the device. Use a test device or emulator unless the user says the device is fine to use.
- Ask before commands that wipe or change settings: `pm clear`, `clearPackageData` (orchestrator), uninstalling, `settings put global *_animation_scale 0`. Say what each one changes and how to undo it.
- When several devices are attached, always pass `--serial`; never guess.
- Raw output, logcat and screenshots can contain personal data. Keep them local and share them only with the people who need them.

## Troubleshooting

| Problem | Fix |
|---|---|
| `adb not found` | Install Platform-Tools, pass `--adb`, or set `ADB` |
| `several devices are connected` | `--serial <id>` (from `doctor`), or set `ANDROID_SERIAL` |
| Gradle passes `-Pandroid.testInstrumentationRunnerArguments.class=...` but all tests run | The key is case-sensitive and the class must be fully qualified; for several use a comma list |
| Tests pass alone, fail together | Shared state: use the Android Test Orchestrator with `clearPackageData` (see the reference), reset watchers and `Configurator` in `@After` |
| Passes locally, fails in CI | Different screen size, language, animations or speed; screenshots and `device.dumpWindowHierarchy(file)` at the failing step show the real screen |
| Run hangs | A test waits on something that never comes, or `--debug` is waiting for a debugger; `--timeout` stops the script, `adb shell am force-stop <test.package>` stops the run |

## References

- [references/failures.md](references/failures.md): every cause the script detects, with explanation and fix.
- [references/running.md](references/running.md): Gradle tasks and report folders, `am instrument` flags and runner arguments, sharding, Test Orchestrator, Gradle Managed Devices, artifacts to collect.
