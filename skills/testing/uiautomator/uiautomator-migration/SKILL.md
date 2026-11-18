---
name: uiautomator-migration
description: "Migrate and audit Android UI Automator tests in Kotlin and Java: UiSelector, UiObject, UiScrollable, UiCollection and the support library to By/UiObject2 (Java) or the 2.4 uiAutomator { } DSL (Kotlin), fix 2.4 alpha names, sleeps and other flaky code. A script reports each issue with file, line and fix. Use when the user wants to upgrade, modernise, review or de-flake UI Automator tests."
license: Complete terms in the repository README
compatibility: The audit script needs Python 3.8+ (standard library only) and only reads files. Verifying a migration needs the Android project, Gradle and a device or emulator. Part of the uiautomator-tools bundle with uiautomator-test-authoring and uiautomator-run-debug.
metadata:
  title: "UI Automator migration and audit (Kotlin and Java)"
  category: uiautomator-tools
---

# UI Automator migration and audit

Move UI Automator tests to the current API and remove what makes them flaky. Targets, by language:

| Language | Target API |
|---|---|
| Kotlin | the 2.4 DSL: `uiAutomator { }`, `onElement { }`, `watchFor`, `waitForStable` (androidx.test.uiautomator 2.4.1) |
| Java | `UiDevice` + `By`/`BySelector` + `Until` + `UiObject2` (the DSL is Kotlin-only in practice) |

`UiSelector`, `UiObject`, `UiScrollable` and `UiCollection` still compile but are being deprecated. `UiAutomatorTestCase`, `UiAutomatorInstrumentationTestRunner`, the support library (`android.support.test.uiautomator`) and UI Automator 1.0 (`com.android.uiautomator`, `uiautomator runtest`) are obsolete.

## When to use

- "Upgrade / migrate / modernise our UI Automator tests", "convert UiSelector to By", "move to uiAutomator { }".
- Code review of a UI Automator suite, or tests that flake (sleeps, coordinates, null `findObject`, stale objects).
- A build fails after bumping uiautomator to 2.4.x (code written against 2.4 alphas).

## When NOT to use

- Writing new tests from scratch: `uiautomator-test-authoring`.
- Diagnosing one failing run from its output: `uiautomator-run-debug`.
- Espresso, Compose test rule, Appium or Python uiautomator2 code.

## Procedure

`scripts/uia_audit.py` is in this skill's folder. It only reads files.

1. **Audit first.**
   ```bash
   python scripts/uia_audit.py <project-dir>              # text report, errors first
   python scripts/uia_audit.py <project-dir> --json       # machine-readable
   python scripts/uia_audit.py <project-dir> --strict     # warnings also fail (for CI)
   python scripts/uia_audit.py --rules                    # every rule id, level and fix
   python scripts/uia_audit.py <dir> --only ui-selector ui-scrollable sleep
   ```
   It scans `.kt` and `.java` test sources (androidTest, test and benchmark modules, or any file importing UI Automator) and the Gradle files, and prints the API mix (DSL vs `By` vs `UiSelector`), the uiautomator version found, and findings with file, line, code and fix. Exit 1 means errors.
2. **Fix the build first.** Set `androidx.test.uiautomator:uiautomator:2.4.1`, `testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"`, `androidx.test.ext:junit` and replace `androidx.test.runner.AndroidJUnit4` with `androidx.test.ext.junit.runners.AndroidJUnit4`. Errors such as `support-library`, `test-case`, `test-runner` and `old-version` come first.
3. **Migrate one test class at a time** using [references/migration-map.md](references/migration-map.md) (every `UiSelector`, `UiObject`, `UiScrollable`, `UiCollection` and `UiDevice` call with its Java and Kotlin replacement). Keep each class compiling and passing before the next. Don't mix a large rename with behaviour changes in one commit.
4. **Remove flakiness while you are there:** replace sleeps with condition waits, coordinates with element actions, `findObject(...).click()` with a wait plus assertion, held `UiObject2` references with fresh lookups, `text ==` with `textAsString() ==`, and short ids for Views with `simpleViewResourceName()`.
5. **Verify on a device.** Run the migrated class several times (`uiautomator-run-debug`: `uia_run.py run --class <Class> ...`), then the whole suite. Re-run the audit until it reports no ERROR and the WARN list is understood.
6. **Report** what changed per file, what remains (INFO items left on purpose), and the run results.

## Rule levels

| Level | Meaning | Examples |
|---|---|---|
| ERROR | Does not compile with 2.4.1, or uses removed/obsolete APIs | `onView { }` (renamed `onElement` in 2.4.0-alpha04), `uiautomator { }`, wrong `PermissionDialog` import, `UiAutomatorTestCase`, support library, DSL code with uiautomator < 2.4 |
| WARN | Deprecated or flaky; fix during migration | `UiSelector`/`UiObject`/`UiScrollable`, sleeps, coordinates, unchecked `findObject`, `text ==` in predicates, `clearAppData("pkg")`, `startIntent`, watchers or display ids never reset, pre-release 2.4.0 versions |
| INFO | Worth a look, sometimes fine | `waitForIdle()`, `executeShellCommand`, `UiObjectNotFoundException`, Configurator changes not restored, `contentDescription ==` |

## Safety rules

- The audit never edits files. Make changes with the user's agreement, in small reviewed steps, under version control.
- Behaviour must not change silently: a migrated test must assert the same things. If the old test relied on a quirk (for example `UiScrollable` searching a fixed number of swipes), say so and agree the new behaviour.
- Do not delete tests that fail after migration; report them with their failure.

## Troubleshooting

| Problem | Fix |
|---|---|
| `Unresolved reference: onElement` after migration | Add `import androidx.test.uiautomator.onElement` for chained calls on `UiObject2`; members of the scope need no import |
| Migrated `By.text(...)` test fails where `UiSelector.text(...)` passed | `findObject(By...)` does not wait: use `device.wait(Until.findObject(sel), t)`; `UiObject` waited `waitForSelectorTimeout` (10 s) on every action |
| `UiSelector.instance(n)` has no `By` equivalent | `device.findObjects(sel).get(n)`, or better a structural selector (`hasParent`, `hasAncestor`) or the row's text |
| Watcher stopped firing after moving to `UiObject2` | `findObject(BySelector)` never runs watchers: call `device.runWatchers()` at that step, or use `watchFor` in Kotlin |
| `scrollIntoView` replacement scrolls forever | `scrollUntil(Direction.DOWN, Until.findObject(sel))` stops at the end and returns null; assert the result |
| Audit flags short `viewIdResourceName` in a Compose app | Expected for test tags (INFO when the project uses `testTagsAsResourceId`) |

## References

- [references/migration-map.md](references/migration-map.md): legacy API to Java and Kotlin replacements, with before/after examples.
