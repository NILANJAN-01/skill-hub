# Running JUnit tests

## Gradle

| Goal | Command |
|---|---|
| All tests of all projects | `./gradlew test` |
| One project | `./gradlew :app:test` |
| One class / method | `./gradlew test --tests 'com.shop.OrderServiceTest'`, `--tests 'com.shop.OrderServiceTest.placesOrder'` |
| Patterns | `--tests '*ServiceTest'`, `--tests 'com.shop.*'`, nested: `--tests 'com.shop.OrderServiceTest$WhenEmpty'` |
| Stop at first failure | `./gradlew test --fail-fast` |
| Rerun even if up to date | `./gradlew test --rerun` (or `--rerun-tasks` for everything) |
| Continue other projects after failures | `./gradlew test --continue` |

Tag filters live in the build file. To choose them on the command line:

```kotlin
tasks.test {
    useJUnitPlatform {
        (findProperty("includeTags") as String?)?.let { includeTags(*it.split(",").toTypedArray()) }
        (findProperty("excludeTags") as String?)?.let { excludeTags(*it.split(",").toTypedArray()) }
    }
}
// ./gradlew test -PincludeTags=fast -PexcludeTags=slow
```

A separate task for integration tests:

```kotlin
val integrationTest by tasks.registering(Test::class) {
    useJUnitPlatform { includeTags("integration") }
    testClassesDirs = sourceSets.test.get().output.classesDirs
    classpath = sourceSets.test.get().runtimeClasspath
}
tasks.test { useJUnitPlatform { excludeTags("integration") } }
```

Other `tasks.test` settings: `maxParallelForks = (Runtime.getRuntime().availableProcessors() / 2).coerceAtLeast(1)`, `maxHeapSize = "1g"`, `systemProperty("junit.jupiter.execution.parallel.enabled", "true")`, `testLogging { events("failed"); exceptionFormat = TestExceptionFormat.FULL }`, `failOnNoDiscoveredTests` (Gradle 9 fails a test task that finds no tests).

Retries: the Gradle plugin `org.gradle.test-retry` (`tasks.test { retry { maxRetries.set(2); maxFailures.set(10); failOnPassedAfterRetry.set(false) } }`) reruns failed tests; the XML then lists the test twice (failed, then passed), which `junit_report.py` reports as flaky.

Reports: XML `build/test-results/<task>/TEST-*.xml`, HTML `build/reports/tests/<task>/index.html`.

## Maven (Surefire for unit tests, Failsafe for `*IT`)

| Goal | Command |
|---|---|
| Unit tests | `mvn test` |
| Unit + integration tests (`*IT`, `*ITCase`, `IT*`) | `mvn verify` |
| One class / method | `mvn test -Dtest=OrderServiceTest`, `-Dtest='OrderServiceTest#placesOrder'`, `-Dtest='OrderServiceTest#places*'` |
| Several | `-Dtest='OrderServiceTest,Invoice*Test'`, exclude with `!`: `-Dtest='!SlowTest'` |
| Integration test selection | `mvn verify -Dit.test=CheckoutIT` |
| One module | `mvn test -pl billing -am -Dsurefire.failIfNoSpecifiedTests=false` |
| Tags | `-Dgroups='fast & !slow'`, `-DexcludedGroups=integration` |
| Rerun failures | `-Dsurefire.rerunFailingTestsCount=2` (`failsafe.rerunFailingTestsCount` for ITs) |
| Stop after N failures | `-Dsurefire.skipAfterFailureCount=1` |
| Parallel JVMs | `-DforkCount=1C` (one per core), `-DreuseForks=true` |
| Skip tests | `-DskipTests` (compile them), `-Dmaven.test.skip=true` (don't compile) |

Configuration parameters for JUnit go in the plugin configuration:

```xml
<plugin>
  <artifactId>maven-surefire-plugin</artifactId>
  <version>3.5.5</version>
  <configuration>
    <properties>
      <configurationParameters>
        junit.jupiter.execution.parallel.enabled = true
        junit.jupiter.execution.parallel.mode.default = concurrent
      </configurationParameters>
    </properties>
  </configuration>
</plugin>
```

Surefire's default includes are `**/Test*.java`, `**/*Test.java`, `**/*Tests.java`, `**/*TestCase.java`; nested classes are excluded from scanning but `@Nested` classes still run with their outer class. Reports: `target/surefire-reports/TEST-*.xml` and `target/failsafe-reports/`. With reruns, a test that passed on a retry gets `<flakyFailure>` entries; one that never passed gets `<rerunFailure>` entries.

## ConsoleLauncher (no build tool)

```bash
java -jar junit-platform-console-standalone-6.1.3.jar execute \
  --class-path build/classes/java/test:build/classes/java/main:libs/* \
  --select-class com.shop.OrderServiceTest \
  --include-tag fast --exclude-tag slow \
  --reports-dir build/junit-reports --details tree --fail-fast
```

- A subcommand is required in JUnit 6: `execute`, `discover` (list tests) or `engines`.
- Selectors: `--scan-classpath`, `-c/--select-class`, `-m/--select-method Class#method`, `-p/--select-package`, `--select-file`, `--uid`. Filters: `-t/--include-tag`, `-T/--exclude-tag`, `-n/--include-classname` (regex), `--include-methodname`, `-e/--include-engine`.
- `--config key=value` sets configuration parameters; `@args.txt` reads options from a file (Windows: use `;` in class paths).
- `--reports-dir` writes the legacy XML report (`TEST-junit-jupiter.xml`, one per engine); with `--config=junit.platform.reporting.open.xml.enabled=true` (and `junit-platform-reporting` on the class path) also `open-test-report.xml`.
- Exit codes: 0 success, 1 failures, 2 no tests found with `--fail-if-no-tests`, 3 invalid input, -1 other error.
- The standalone jar is on Maven Central: `org.junit.platform:junit-platform-console-standalone:6.1.3`.

## Open Test Reporting XML (richer report, JUnit 6)

Gradle:

```kotlin
dependencies { testRuntimeOnly("org.junit.platform:junit-platform-reporting") }
tasks.withType<Test>().configureEach {
    val outputDir = reports.junitXml.outputLocation
    jvmArgumentProviders += CommandLineArgumentProvider {
        listOf("-Djunit.platform.reporting.open.xml.enabled=true",
               "-Djunit.platform.reporting.output.dir=${outputDir.get().asFile.absolutePath}")
    }
}
```

Maven: add `org.junit.platform:junit-platform-reporting` (test scope) and the configuration parameters `junit.platform.reporting.open.xml.enabled = true`, `junit.platform.reporting.output.dir = target/surefire-reports`.

The file is `open-test-report.xml` in the output directory (`{uniqueNumber}` in the directory name gives one folder per run). It keeps display names, the test hierarchy, tags, skip reasons and stack traces; `junit.platform.reporting.open.xml.git.enabled = true` adds Git information.

## Capturing output

`junit.platform.output.capture.stdout = true` / `.stderr = true` attaches `System.out` / `System.err` per test to the reports (and to Open Test Reporting). With parallel execution, capture must be enabled to keep output separated per test.

## IDEs

IntelliJ IDEA, Eclipse, VS Code (Java extension pack) and NetBeans run Jupiter natively. If the IDE reports `OutputDirectoryProvider not available` or an engine discovery error, it bundles a different launcher version: add `junit-platform-launcher` from the BOM to the test runtime class path.
