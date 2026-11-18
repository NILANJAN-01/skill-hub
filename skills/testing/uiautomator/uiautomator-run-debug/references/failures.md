# Failure causes detected by uia_run.py

The script checks causes in this order and reports the first that matches the failure message and stack.

| Id | Matches | What happened | Fix |
|---|---|---|---|
| `element-not-found` | `ElementNotFoundException` | Kotlin `onElement { }` / `scrollToElement` found no node within its timeout (10 s default) | Compare the predicate with a dump of the real screen. For Views `viewIdResourceName` is `"pkg:id/name"` (use `simpleViewResourceName()` for `"name"`); text needs `textAsString()`; Compose tags need `testTagsAsResourceId`. Check the right screen is in front. Raise `timeoutMs` only for slow loads |
| `stale-object` | `StaleObjectException` | A `UiObject2` outlived its view (navigation, RecyclerView recycling, recomposition) | Find it again right before each use; page-object getters should look up every time |
| `legacy-not-found` | `UiObjectNotFoundException` | A legacy `UiSelector`/`UiObject` matched nothing within `waitForSelectorTimeout` | Migrate (`uiautomator-migration`) or fix the selector |
| `null-uiobject2` | NPE mentioning `UiObject2` | `findObject(By...)` returned null (element not there yet) and the test called a method on it | `UiObject2 o = device.wait(Until.findObject(sel), TIMEOUT); assertNotNull("sel", o);` |
| `intent-unresolved` | `does not resolve to an activity`, `ActivityNotFoundException` | `startActivity`/`startActivityIntent`/`startActivity(Intent)` had no matching activity | Check package and class names, `android:exported`, that the app is installed, and `<queries>` on Android 11+ |
| `no-launch-intent` | `getLaunchIntentForPackage`, `no launch intent for` | The test could not resolve the app's launcher activity | Install the app; add `<queries><package android:name="..."/></queries>` to `src/androidTest/AndroidManifest.xml` |
| `uiautomation-busy` | `UiAutomationService ... already registered`, `UiAutomation not connected` | Only one UiAutomation client can be connected: something else holds it | `adb shell am force-stop io.appium.uiautomator2.server` (and `.test`), stop other runs or accessibility test tools, retry |
| `no-root-window` | `Failed to get root in active window` | The active window could not be read: screen off, keyguard, secure (FLAG_SECURE) or system window, app still starting | Wake/unlock, keep the screen on, `waitForAppToBeVisible`, avoid secure screens in UI checks |
| `idle-timeout` | `could not get idle state` | `waitForIdle` (also used inside some actions) timed out on a screen that keeps changing | Wait for specific elements; lower `Configurator.setWaitForIdleTimeout` for such screens; disable animations |
| `inject-events` | `INJECT_EVENTS` | Input injected through `Instrumentation` (Espresso, `sendKeySync`, DSL `type()`) into another app's window | Use `UiObject2.setText`, `click`, `UiDevice.pressKeyCode` for other apps |
| `process-crashed` | `Process crashed` | The app or test process died; the remaining tests did not run | Read logcat (`--logcat`); fix the crash; the Orchestrator keeps one crash from ending the run |
| `instrumentation-missing` | `Unable to find instrumentation info`, `INSTRUMENTATION_FAILED` | Test APK not installed, wrong `<test.package>/<runner>`, or the target app missing | `./gradlew :app:installDebug :app:installDebugAndroidTest`; copy the name from `uia_run.py doctor` |
| `no-tests` | `No tests found`, `numtests=0`, `initializationError` | Filters matched nothing, or a class failed to initialise (bad `@Rule`, constructor, runner) | Fully qualified `--class`, `Class#method`; check annotations; read the initializationError stack |
| `incomplete-run` | `Test run failed to complete`, `Expected N tests, received M` | The run stopped part-way (crash, device disconnect, timeout) | Look at the last started test and logcat; check the cable or emulator |
| `assertion` | `AssertionError`, `expected:<` | The app showed something different from the expectation | Compare expected and actual; capture a screenshot and hierarchy at that step |
| `dependency-clash` | `NoSuchMethodError` / `NoClassDefFoundError` in `androidx.test` | Two versions of androidx.test or uiautomator on the test classpath | `./gradlew :app:dependencies --configuration debugAndroidTestRuntimeClasspath`; pin one version |
| `timeout` | `TimeoutException`, `timed out` | Something did not happen in time | Find the waiting step in the stack and wait for a specific condition |
| `other` | anything else | | Read the first stack frame in the test code (`at:` line in the summary) |

## Flaky tests: checklist

1. Run the test 5 to 10 times in a row; note which step fails and whether the message changes.
2. Look for sleeps, fixed coordinates, `findObject` without a wait, held `UiObject2` references, `waitForIdle` on animated screens (`uiautomator-migration`'s audit finds them).
3. Check test independence: does it pass alone and fail after another test? Use the Orchestrator with `clearPackageData`, reset watchers and `Configurator`.
4. Check the environment: animations, language, font scale, screen size, a dialog (update prompt, battery warning, permission) appearing only sometimes: add a watcher for it.
5. Capture the screen at the failure (screenshot + `dumpWindowHierarchy`) instead of guessing.
