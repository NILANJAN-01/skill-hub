# Setup: test dependencies, coverage, loose files

Ask the user before changing their build files. Use the versions the project already uses where possible. The versions below are examples; check for current releases.

## Gradle (Kotlin DSL), JVM module

```kotlin
plugins {
    kotlin("jvm") version "2.0.21"
    jacoco                                   // coverage: ktest.py run --coverage runs jacocoTestReport
}

dependencies {
    testImplementation(kotlin("test"))       // kotlin.test assertions on JUnit 5
    testImplementation("org.junit.jupiter:junit-jupiter-params:5.11.3")
    testImplementation("io.mockk:mockk:1.13.13")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.9.0")
}

tasks.test {
    useJUnitPlatform()
    finalizedBy(tasks.jacocoTestReport)
}

tasks.jacocoTestReport {
    reports { xml.required.set(true); html.required.set(true) }
}
```

JUnit 4 tests on this setup also need `testRuntimeOnly("org.junit.vintage:junit-vintage-engine:5.11.3")`, otherwise they are silently skipped (rule KT010).

**Kover** (alternative coverage for Kotlin): add `id("org.jetbrains.kotlinx.kover") version "0.8.3"`. `ktest.py run --coverage` then runs `koverXmlReport`.

## Android module

Unit tests live in `src/test`. Add `testImplementation` dependencies as above. JUnit 5 on Android needs the `de.mannodermaus.android-junit5` plugin; otherwise use JUnit 4 (`junit:junit:4.13.2`) with `kotlin("test-junit")`.

`ktest.py` runs `test<Variant>UnitTest` (default `testDebugUnitTest`). JaCoCo for Android unit tests needs a custom report task. Pass its name with `--coverage-task jacocoDebugUnitTestReport` (or whatever the project calls it).

## Maven

You need `kotlin-maven-plugin`, `maven-surefire-plugin` 3.x, `junit-jupiter` and `kotlin-test-junit5` as test dependencies. Add `jacoco-maven-plugin` with the `prepare-agent` goal for coverage. `ktest.py run --tool maven --coverage` adds `jacoco:report`.

## Loose `.kt` files (no build)

**Option A: a small Gradle build around the files (recommended).** Create `build.gradle.kts` and `settings.gradle.kts` next to the code, put the code in `src/main/kotlin` and the tests in `src/test/kotlin`, and use the Gradle block above. Run it with an installed `gradle`, or create a wrapper once with `gradle wrapper`.

**Option B: kotlinc and the JUnit console launcher.**
- Needs a JDK, `kotlinc` on PATH, and `junit-platform-console-standalone-<version>.jar` from Maven Central.
- The compiler gets every `.kt` file found. Tests must use JUnit 5 or kotlin.test annotations.
- Extra libraries (MockK and its dependencies) go in `--classpath`.

```bash
python scripts/ktest.py run --tool kotlinc --junit-jar /path/junit-platform-console-standalone-1.11.3.jar
```

There is no coverage in this mode.

## Folder conventions the scripts understand

| Path | Treated as |
|---|---|
| `src/main/…`, other source sets (`src/jvmMain/…`) | Production code |
| `src/test/…`, `src/*Test/…` (`jvmTest`, `integrationTest`) | Unit tests |
| `src/androidTest/…` | Instrumented tests: listed, not run |
| Files without `src/`: names ending in `Test.kt`, `Tests.kt`, `Spec.kt`, `IT.kt`, or inside a `test`/`tests` folder | Tests; everything else is production code |
| `build/`, `out/`, `target/`, `buildSrc/`, `generated/`, hidden folders, `*.gradle.kts` | Ignored |
