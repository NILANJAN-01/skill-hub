# Android tests with Gradle

Source: [sources.md](sources.md).

## Two kinds

| Kind | Runs on | Source set | Task | Reports |
|---|---|---|---|---|
| Local unit test | JVM, no device | `src/test` | `test` or `test<Variant>UnitTest` | `<module>/build/reports/tests/` (HTML), `<module>/build/test-results/` (XML) |
| Instrumented test | Device or emulator | `src/androidTest` | `connectedAndroidTest` or `connected<Variant>AndroidTest` | `<module>/build/reports/androidTests/connected/`, `<module>/build/outputs/androidTest-results/connected/` |

`check` and `connectedCheck` run the tests plus other checks (lint and so on). Task names can be abbreviated: `./gradlew cAT`.

## Commands

```bash
./gradlew test                                   # all modules, all variants
./gradlew :app:testDebugUnitTest                 # one module, one variant
./gradlew :app:testDebugUnitTest --tests 'com.example.CartTest'
./gradlew :app:testDebugUnitTest --tests 'com.example.CartTest.totalIsSummed'
./gradlew :app:testDebugUnitTest --tests '*.totalIsSummed'
./gradlew :app:connectedDebugAndroidTest
./gradlew :app:connectedDebugAndroidTest -Pandroid.testInstrumentationRunnerArguments.class=com.example.LoginUiTest#showsError
```

The `--tests` filter is for local tests. For instrumented tests filter with the runner argument above, or run through adb:

```bash
adb shell am instrument -w -e class com.example.LoginUiTest#showsError com.example.test/androidx.test.runner.AndroidJUnitRunner
```

`-e package`, `-e class a,b#m`, `-e size small|medium|large`, `-e log true` (list without running). A `package` argument wins over `class`.

`gradle_doctor.py test` builds these commands for you (`--dry-run` prints them and the report folders).

## Dependencies

```kotlin
dependencies {
    testImplementation(libs.junit)                     // local
    androidTestImplementation(libs.androidx.test.ext.junit)
    androidTestImplementation(libs.androidx.test.espresso.core)
}
android { defaultConfig { testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner" } }
```

Add them with `add-lib --config testImplementation` or `--config androidTestImplementation`. Android framework classes in local tests need Robolectric or `unitTests.isReturnDefaultValues = true`; prefer Robolectric or an instrumented test over returning defaults.

## Devices

- `adb devices` must show `device` (not `unauthorized` or `offline`).
- Gradle Managed Devices create and run emulators from the build, good for CI: define them under `android.testOptions.managedDevices` and run `./gradlew <deviceName>DebugAndroidTest`.
- `INSTALL_FAILED_UPDATE_INCOMPATIBLE`: uninstall the app (different signature). `INSTALL_FAILED_OLDER_SDK`: device API is below `minSdk`.

## Reports and coverage

- Open `index.html` in the report folder. For XML use `build/test-results/...`.
- Unified report (experimental, needs `android.experimental.reportAggregationSupport=true` and AGP 9.5.0-alpha05+): `./gradlew :app:testAllSuites --continue`.
- Coverage needs JaCoCo or Kover configured in the build; for Kotlin class/method level reports and quality checks use `kotlin-unit-test`.

## When a test fails

1. Rerun only that test with `--tests`.
2. Read `build/reports/tests/.../classes/<Class>.html` for the assertion message and stack.
3. If the build (not the test) fails, run `gradle_doctor.py diagnose` on the log.
4. Flaky: rerun with `--rerun-tasks` (forces tasks) or `cleanTest`; check for shared state and time or network dependence.
