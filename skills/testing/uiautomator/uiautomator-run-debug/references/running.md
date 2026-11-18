# Running UI Automator tests

## Gradle

| Goal | Command |
|---|---|
| All instrumented tests of all modules | `./gradlew connectedAndroidTest` (`./gradlew cAT`) |
| One module | `./gradlew :app:connectedAndroidTest` |
| One variant | `./gradlew :app:connectedFreeDebugAndroidTest` |
| One class / method | `./gradlew :app:connectedDebugAndroidTest -Pandroid.testInstrumentationRunnerArguments.class=com.example.LoginTest#signIn` |
| By annotation / size / package | `-Pandroid.testInstrumentationRunnerArguments.annotation=com.example.Smoke`, `...size=large`, `...package=com.example.login` |
| Install only (for fast adb reruns) | `./gradlew :app:installDebug :app:installDebugAndroidTest` |
| Benchmarks | `./gradlew :macrobenchmark:connectedCheck` |

Reports:

- HTML: `<module>/build/reports/androidTests/connected/`
- JUnit XML: `<module>/build/outputs/androidTest-results/connected/` (one folder per device or variant); `uia_run.py results <project>` reads them.
- Extra files (screenshots, benchmark JSON, traces): `<module>/build/outputs/connected_android_test_additional_output/`.
- Unified unit + instrumented report (experimental, AGP 9.5.0-alpha05+, `android.experimental.reportAggregationSupport=true` in `gradle.properties`): `./gradlew :app:testAllSuites --continue`, report in `build/reports/testAllSuites/test-report/`.

## adb and am instrument

```bash
adb shell am instrument -w -r [-e KEY VALUE ...] <test.package>/androidx.test.runner.AndroidJUnitRunner
```

| Flag | Meaning |
|---|---|
| `-w` | Wait for the run to finish (needed to see results) |
| `-r` | Raw key-value output (what `uia_run.py` parses) |
| `-e KEY VALUE` | Runner argument (repeatable) |
| `--no-hidden-api-checks` | Allow hidden APIs |
| `--user <id>` | Run for another user (multi-user devices, automotive) |

`adb shell am help` lists every flag on that device.

| Runner argument (`-e`) | Value |
|---|---|
| `class` | `com.example.LoginTest`, `com.example.LoginTest#signIn`, comma list |
| `notClass` | Exclude classes or methods |
| `package` / `notPackage` | Java package (wins over `class` when both are given) |
| `size` | `small`, `medium`, `large` (`@SmallTest` ...) |
| `annotation` / `notAnnotation` | Fully qualified annotation |
| `numShards` + `shardIndex` | Split the suite; run index 0..N-1 on N devices |
| `log` | `true`: list tests, do not run |
| `debug` | `true`: wait for a debugger |
| `timeout_msec` | Per-test timeout |
| `listener` | Extra `RunListener` class |
| `clearPackageData` | `true`: clear app data between tests (Test Orchestrator only) |
| anything else | Read it in the test with `InstrumentationRegistry.getArguments().getString("key")` |

Result codes in raw output: `1` start, `0` pass, `-2` failure, `-1` error, `-3` ignored, `-4` assumption failure. A run that ends with `INSTRUMENTATION_RESULT: shortMsg=Process crashed.` stopped early.

## Test Orchestrator (isolate tests, clear state)

Each test runs in its own instrumentation instance, so one crash does not end the run and state does not leak.

```kotlin
android {
    defaultConfig {
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        testInstrumentationRunnerArguments["clearPackageData"] = "true"   // wipes app data before each test
    }
    testOptions { execution = "ANDROIDX_TEST_ORCHESTRATOR" }
}
dependencies { androidTestUtil("androidx.test:orchestrator:1.6.1") }
```

`clearPackageData` deletes the app's data before every test: confirm that is wanted on the device used.

## Gradle Managed Devices (emulators Gradle creates)

```kotlin
android {
    testOptions {
        managedDevices {
            localDevices {                      // `devices` in older AGP versions
                create("pixel8api34") {
                    device = "Pixel 8"
                    apiLevel = 34
                    systemImageSource = "aosp-atd"   // ATD images are slimmer and faster for tests
                }
            }
        }
    }
}
```

Run with `./gradlew pixel8api34DebugAndroidTest`. Good for CI: the same emulator every time. Baseline Profile generation needs `systemImageSource = "aosp"` (root).

## Device preparation for stable runs

Ask before changing settings on a device the user did not dedicate to testing.

- Unlock the screen and keep it on (`adb shell svc power stayon usb`), dismiss the keyguard (`adb shell wm dismiss-keyguard`).
- Turn animations off in Developer options, or `adb shell settings put global window_animation_scale 0`, `transition_animation_scale 0`, `animator_duration_scale 0` (restore with `1`).
- Fix the language and font size the tests expect; text locators depend on them.
- Stop other UiAutomation clients (Appium's uiautomator2 server, a second test run).

## Artifacts worth collecting on failure

- Raw output (`uia_run.py run --out run.txt`) and JUnit XML.
- Logcat (`--logcat logcat.txt`; analyse with `android-logcat-analyzer`).
- A screenshot and hierarchy at the failing step from the test itself: `device.takeScreenshot(File)`, `device.dumpWindowHierarchy(File)`, or Kotlin `ResultsReporter` so Android Studio shows them.
- A screen recording of a flaky run: `adb shell screenrecord /sdcard/run.mp4` (see `adb-device-control`).
