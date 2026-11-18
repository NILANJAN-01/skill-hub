---
name: uiautomator-test-authoring
description: "Write Android UI Automator tests in Kotlin (2.4 uiAutomator { } DSL: onElement, watchFor, waitForStable) or Java (UiDevice, By, Until, UiObject2): project setup, selectors, waits, permission dialogs, system UI, multi-window, screenshots, Compose test tags, Macrobenchmark and Baseline Profiles. A script checks the Gradle setup and generates tests and page objects. Use when the user wants UI Automator tests written or set up."
license: Complete terms in the repository README
compatibility: Scripts need Python 3.8+ (standard library only). The generated tests need an Android Gradle project, androidx.test.uiautomator 2.4.1 (Kotlin DSL; Java works from 2.3.0), and a device or emulator to run on. Works with the uiautomator-migration, uiautomator-run-debug and android-uiautomator-locators skills (the uiautomator-tools bundle).
metadata:
  title: "UI Automator test authoring (Kotlin and Java)"
  category: uiautomator-tools
---

# UI Automator test authoring (Kotlin and Java)

UI Automator drives the UI **from outside the app's process**, through accessibility: it can tap your app, other apps, the launcher, Settings, notifications and system dialogs, and it tests release builds with minification. Tests are instrumented JUnit4 tests run by `AndroidJUnitRunner`. This skill covers Kotlin and Java only.

| Language | API to write | Entry point |
|---|---|---|
| **Kotlin** | Modern 2.4 DSL (recommended by Google for new tests) | `@Test fun t() = uiAutomator { ... }` |
| **Java** | `UiDevice` + `By`/`BySelector` + `Until` + `UiObject2` (the DSL is Kotlin lambdas with receivers, so it is not practical from Java) | `UiDevice.getInstance(InstrumentationRegistry.getInstrumentation())` |

Do not write new code with `UiSelector`, `UiObject`, `UiScrollable` or `UiCollection`: they are being deprecated (see `uiautomator-migration`).

| Need | Skill |
|---|---|
| Write tests, set up the project, page objects, benchmarks | this skill |
| Get resource-ids and locators from the real screen | `android-uiautomator-locators` |
| Migrate old tests, audit a suite for flaky or deprecated code | `uiautomator-migration` |
| Run tests, read results, fix failures | `uiautomator-run-debug` |

## When to use

- Add UI Automator to an Android project, or write a test for a user flow (Kotlin or Java).
- Tests that cross app boundaries: launcher, Settings, notification shade, permission dialogs, share sheets, another app.
- Opaque-box tests of a release/minified build, Macrobenchmark journeys, Baseline Profile generators.

## When NOT to use

- In-app UI tests with no cross-app step: Espresso (Views) or the Compose testing APIs synchronise better with the app.
- Cross-platform or Python/JS automation (Appium, uiautomator2 Python): only Kotlin and Java are covered here.
- A test already fails and the reason is unknown: use `uiautomator-run-debug`.

## Procedure

`scripts/uia_scaffold.py` is in this skill's folder; run it with the user's project as the working directory.

1. **Check the setup.**
   ```bash
   python scripts/uia_scaffold.py check <project-dir>       # exit 1 = something is missing
   python scripts/uia_scaffold.py deps --dsl kts|groovy|toml  # just print the snippet
   ```
   It reads `settings.gradle(.kts)`, each module's build file and `gradle/libs.versions.toml`, and reports the uiautomator version, `testInstrumentationRunner`, `androidx.test.ext:junit`, the `src/androidTest` folder, `targetProjectPath` for `com.android.test` modules, and Compose without `testTagsAsResourceId`. The minimum is:
   ```kotlin
   android { defaultConfig { testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner" } }
   dependencies {
       androidTestImplementation("androidx.test.ext:junit:1.3.0")
       androidTestImplementation("androidx.test.uiautomator:uiautomator:2.4.1")
   }
   ```
   Tests go in `<module>/src/androidTest/java/<package>/` (Kotlin files can live there too), or in a separate `com.android.test` module with `targetProjectPath = ":app"`.
2. **Get real locators, don't guess them.** Open the screen on a device and run `android-uiautomator-locators` (it writes `locators/<screen>.locators.json`), or `adb shell uiautomator dump` and pull the XML. In Compose apps, ask for `Modifier.semantics { testTagsAsResourceId = true }` once near the root and `Modifier.testTag("...")` on elements; then the tag is the whole resource name.
3. **Generate a starting point.**
   ```bash
   python scripts/uia_scaffold.py new --name LoginTest --package com.example.app.test --app com.example.app \
       --lang kotlin --locators locators/login.locators.json --out app/src/androidTest/java
   python scripts/uia_scaffold.py new --name LoginTest --lang java ... --dump window_dump.xml --clickable-only
   python scripts/uia_scaffold.py new --name StartupBenchmark --kind benchmark ...         # Kotlin only
   python scripts/uia_scaffold.py new --name BaselineProfileGenerator --kind baseline-profile ...
   ```
   It writes a test class plus a page object (`LoginScreen`) whose members re-find the element every time (no stale objects). Kotlin page objects wrap `UiAutomatorTestScope`; Java ones wait with `device.wait(Until.findObject(sel), TIMEOUT_MS)` and fail with the selector if it is missing. Without `--out` it prints; it never overwrites without `--force`.
4. **Write the steps** with the rules below and the API in [references/kotlin-api.md](references/kotlin-api.md) / [references/java-api.md](references/java-api.md).
5. **Run and verify** with `uiautomator-run-debug` (`./gradlew :app:connectedDebugAndroidTest`, or one class with `-Pandroid.testInstrumentationRunnerArguments.class=...`). Run new tests several times before trusting them. If `uiautomator-migration` is installed, run its `uia_audit.py` on the test folder and fix every ERROR.

## Rules for reliable tests

1. **Selectors, best first:** resource-id (View id or Compose test tag) → content description → text (breaks when the language changes) → class plus structure (`hasParent`, `hasDescendant`, chained `onElement`). Never fixed coordinates.
2. **Kotlin predicates run on `AccessibilityNodeInfo`:**
   - `viewIdResourceName` is the **full** id for Views (`"com.example.app:id/sign_in"`); use `simpleViewResourceName() == "sign_in"` for the short form. A Compose test tag has no `:id/` part.
   - Compare text with `textAsString() == "..."`, not `text == "..."` (`text` is a `CharSequence`, maybe a `SpannableString`); the library ships a lint check for this. Use `contentDescription?.toString()` for descriptions.
   - `isClass(Button::class.java)`, `isClickable`, `isScrollable`, `isChecked`, `packageName == "..."` also work.
3. **Wait for conditions, never sleep.** Kotlin: `onElement` waits up to 10 s (`onElement(timeoutMs = 30_000) { }`), `onElementOrNull` for optional UI, `onElements` waits for at least one. Java: `device.wait(Until.findObject(sel), t)`, `Until.hasObject/gone`, `obj.wait(Until.textEquals("5"), t)`, `obj.clickAndWait(Until.newWindow(), t)`, `device.performActionAndWait(action, Until.newWindow(), t)`. `findObject(By...)` returns `null` immediately if the element is not there yet.
4. **Look elements up again after the screen changes.** A `UiObject2` is bound to one view and throws `StaleObjectException` after navigation, recycling or recomposition.
5. **Start from a known state.** Kotlin: `startApp(pkg)` / `startActivity(MyActivity::class.java)` / `startActivityIntent(intent)` block until the app or a new window shows; `clearAppData()` clears the instrumentation target app. Java: `pressHome()`, wait for the launcher, start the launch intent with `FLAG_ACTIVITY_CLEAR_TASK`, wait for `By.pkg(app).depth(0)`.
6. **Unexpected dialogs:** Kotlin `watchFor(PermissionDialog) { clickAllow() }` (import `androidx.test.uiautomator.watcher.PermissionDialog`); watchers run on each `onElement` poll and are removed when `uiAutomator { }` ends. For expected dialogs just use `onElement`. Java: `device.registerWatcher(name, watcher)` runs only when a legacy `UiSelector` lookup fails or when you call `device.runWatchers()`; `findObject(BySelector)` never runs it. Remove watchers in `@After`.
7. **`waitForStable()`** (window or element) waits until the accessibility tree (and by default the pixels) stop changing. Use it before screenshots or with `onElements` on a settling list, not as a general wait; it never settles on video.
8. **Restore global state.** `Configurator` is process-wide: save and restore values you change; call `resetDefaultDisplayId()` after `setDefaultDisplayId()`.
9. **One behaviour per test, independent tests.** No order dependence; put shared navigation in page objects.

## Safety rules

- `clearAppData()`, `pm clear`, `executeShellCommand` and Settings changes delete data or change the device. Run tests on test devices or emulators, not on a phone with the user's personal data, unless the user agrees.
- Never put real credentials in tests; read them from instrumentation arguments (`InstrumentationRegistry.getArguments()`) or CI secrets.
- Screenshots and hierarchy dumps can contain personal data; keep them out of version control.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ElementNotFoundException` / `findObject` returns null | Predicate or selector wrong (full vs short id, `textAsString()`), wrong screen, or slower UI: dump the screen and compare; raise the timeout |
| Compose elements have no resource-id | Set `testTagsAsResourceId = true` high in the tree; then `By.res("tag")` (not `By.res(pkg, "tag")`, which builds `pkg:id/tag`) or `viewIdResourceName == "tag"` |
| `getLaunchIntentForPackage` returns null (Android 11+) | Add `<queries><package android:name="..."/></queries>` to the androidTest manifest |
| Unresolved `uiAutomator`, `onElement`, `textAsString` | uiautomator older than 2.4.0, or missing imports `androidx.test.uiautomator.onElement` / `textAsString` (extension functions) |
| `clearAppData("pkg")` or `startIntent(...)` does not compile | 2.4.1 has `clearAppData()` and `startActivityIntent(intent)`; the guide shows pre-release names |
| Taps land in the gesture area on edge-to-edge screens | `obj.setGestureMargin(px)` / `setGestureMarginPercentage(0.1f)` before scroll, swipe or fling |
| Typing into another app throws `INJECT_EVENTS` | `type()` uses Instrumentation key events; use `UiObject2.setText()` for other apps |

## References

- [references/kotlin-api.md](references/kotlin-api.md): the 2.4 DSL (scope, finders, node extensions, scrolling, windows, screenshots, `ResultsReporter`, custom watchers, `uiautomator-shell`) with Kotlin examples.
- [references/java-api.md](references/java-api.md): `UiDevice`, `By`/`BySelector`, `Until`, `UiObject2`, `Configurator`, multi-display, watchers, system UI, with Java examples.
- [references/benchmark-and-baseline.md](references/benchmark-and-baseline.md): Macrobenchmark and Baseline Profile modules driven by UI Automator.
- [references/sources.md](references/sources.md): official pages used, versions, and where the guide and the API reference disagree.
