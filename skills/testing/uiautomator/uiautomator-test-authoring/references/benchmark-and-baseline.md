# Macrobenchmark and Baseline Profiles with UI Automator

Jetpack Macrobenchmark drives the app with UI Automator to measure startup, scrolling and animations, and the same journeys generate Baseline Profiles. In Macrobenchmark 1.5.0 (stable; checked 2026-11-18) `MacrobenchmarkScope`, the receiver of the measure and setup blocks, extends `UiAutomatorTestScope` and depends on uiautomator 2.4.0, so `startActivityAndWait()`, `pressHome()`, `device` and the DSL are all available; the official samples also wrap steps in `uiAutomator { }`.

## Module setup (Kotlin DSL)

A benchmark or profile generator lives in its own `com.android.test` module, separate from the app:

```kotlin
// macrobenchmark/build.gradle.kts
plugins {
    id("com.android.test")
    id("org.jetbrains.kotlin.android")
    id("androidx.baselineprofile")          // only for Baseline Profile generation
}
android {
    namespace = "com.example.macrobenchmark"
    targetProjectPath = ":app"
    defaultConfig { testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner" }
}
dependencies {
    implementation("androidx.benchmark:benchmark-macro-junit4:1.5.0")
    implementation("androidx.test.ext:junit:1.3.0")
    implementation("androidx.test.uiautomator:uiautomator:2.4.1")
}
```

In a `com.android.test` module the test code is in `src/main` (generate into `macrobenchmark/src/main/java`), so dependencies use `implementation`. Declaring uiautomator 2.4.1 explicitly keeps one version on the classpath. The app module needs:

- a `benchmark` build type: `initWith(getByName("release"))`, `signingConfig = signingConfigs.getByName("debug")`, `matchingFallbacks += listOf("release")` in multi-module projects;
- `<profileable android:shell="true"/>` in the manifest (the Studio template adds it) and `androidx.profileinstaller` 1.3+;
- for profiles: `plugins { id("androidx.baselineprofile") }` and `dependencies { baselineProfile(project(":baselineprofile")) }`.

Use Android Studio's **Benchmark** or **Baseline Profile Generator** module templates when possible; the generator template can create Java or Kotlin. `uia_scaffold.py --kind benchmark|baseline-profile` writes Kotlin classes that match the official samples.

## Startup and scroll benchmarks

```kotlin
@RunWith(AndroidJUnit4::class)
class StartupBenchmark {
    @get:Rule val benchmarkRule = MacrobenchmarkRule()

    @Test
    fun startup() = benchmarkRule.measureRepeated(
        packageName = TARGET,
        metrics = listOf(StartupTimingMetric()),
        iterations = 5,
        startupMode = StartupMode.COLD,
    ) {
        uiAutomator { startApp(TARGET) }
    }

    @Test
    fun scroll() = benchmarkRule.measureRepeated(
        packageName = TARGET,
        metrics = listOf(FrameTimingMetric()),
        iterations = 5,
        startupMode = StartupMode.WARM,
        setupBlock = { pressHome() },
    ) {
        startActivityAndWait()
        uiAutomator {
            val list = onElement { viewIdResourceName == "feed" }   // Compose testTag with testTagsAsResourceId
            list.setGestureMargin(device.displayWidth / 5)
            list.fling(Direction.DOWN)
        }
    }
}
```

- Time to full display: after `startApp`, wait for the content that loads last with `onElement { ... }` and have the app call `reportFullyDrawn()` (Compose: `ReportDrawnWhen`).
- `StartupMode.COLD` kills the process between `setupBlock` and the measure block; use `WARM` or `startupMode = null` when the process must stay alive.
- `CompilationMode.DEFAULT` installs the Baseline Profile on Android 7+; `None`, `Partial`, `Full`, `Ignore` compare compilation states. On Android 13 and lower each compile reset needs a reinstall; Android 14+ keeps state.

Run on a physical device (emulators are refused or misleading):

```bash
./gradlew :macrobenchmark:connectedCheck
./gradlew :macrobenchmark:connectedCheck -P android.testInstrumentationRunnerArguments.class=com.example.macrobenchmark.StartupBenchmark#startup
```

Results and Perfetto traces are copied to `macrobenchmark/build/outputs/connected_android_test_additional_output/<variant>AndroidTest/connected/<device>/`. Misconfiguration (debuggable app, emulator, low battery) fails the run with an error; `androidx.benchmark.suppressErrors` silences it only when you understand the cost.

## Baseline Profile generator

```kotlin
@RunWith(AndroidJUnit4::class)
class BaselineProfileGenerator {
    @get:Rule val baselineProfileRule = BaselineProfileRule()

    @Test
    fun startup() = baselineProfileRule.collect(
        packageName = TARGET,
        includeInStartupProfile = true,
        profileBlock = { uiAutomator { startApp(TARGET) } },
    )

    @Test
    fun browseCatalog() = baselineProfileRule.collect(
        packageName = TARGET,
        profileBlock = {
            uiAutomator {
                startApp(TARGET)
                onElement { textAsString() == "Catalog" }.click()
                onElement { isScrollable }.fling(Direction.DOWN)
            }
        },
    )
}
```

- Put only startup journeys in blocks with `includeInStartupProfile = true`; other journeys go in plain `collect` calls.
- Generate with `./gradlew :app:generateBaselineProfile` (or `:app:generate<Variant>BaselineProfile`). The profile is copied to `app/src/<variant>/generated/baselineProfiles/`.
- Devices: rooted device, emulator, a Gradle Managed Device with `systemImageSource = "aosp"`, or any device on Android 13+ (Macrobenchmark 1.2.0-alpha06+).
- Keep journeys deterministic: `onElement` waits, so avoid sleeps; share journey functions between the generator and the benchmarks.
