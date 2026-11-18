# JUnit 5 to JUnit 6

JUnit 6.0.0 was released on 2025-09-30; 6.1.3 (2026-08-07) is current. Most JUnit 5 tests compile and run unchanged; the work is mostly in the build and in a few removed APIs.

## Build

| Change | Action |
|---|---|
| Java 17 minimum at runtime | Run tests on JDK 17+ (Gradle toolchain, Maven on JDK 17+); code compiled for older targets can still be tested |
| Kotlin 2.2 minimum | Upgrade the Kotlin plugin |
| One version for Platform, Jupiter and Vintage | Platform 1.x is gone: `junit-platform-launcher:1.10.2` next to Jupiter 6 fails with `NoSuchMethodError`. Import `org.junit:junit-bom:6.1.3` and drop the other versions |
| Maven Surefire / Failsafe 3.0.0+ | Pin 3.5.5 or newer |
| `junit-platform-runner` removed | Replace `@RunWith(JUnitPlatform.class)` with `@Suite` (`junit-platform-suite`) |
| `junit-platform-jfr` removed | JFR events are part of `junit-platform-launcher` now |
| `junit-platform-suite-commons` removed | Use `junit-platform-suite` |
| Vintage engine deprecated | Finish migrating JUnit 4 tests |
| `junit-jupiter-migrationsupport` deprecated | Replace rule support with extensions |

## Code

| JUnit 5 | JUnit 6 |
|---|---|
| `MethodOrderer.Alphanumeric` | `MethodOrderer.MethodName` |
| `@UseTechnicalNames` (suites) | Remove |
| `JRE.JAVA_8` .. `JAVA_16` (deprecated) | `JRE.JAVA_17`+ or `versions` / `minVersion` / `maxVersion` ints |
| `JRE.OTHER` (deprecated in 6.1) | `@EnabledOnJre(versions = 30)`, `@EnabledForJreRange(minVersion = 30)` |
| `@EnabledForJreRange` default `min` | Now `JAVA_17` |
| `store.getOrComputeIfAbsent(...)` (deprecated) | `store.computeIfAbsent(...)` |
| `InvocationInterceptor.interceptDynamicTest(Invocation, ExtensionContext)` | The overload with `DynamicTestInvocationContext` |
| `TestTemplateInvocationContextProvider.provideTestTemplateInvocationContexts` returns `Stream<TestTemplateInvocationContext>` | `Stream<? extends TestTemplateInvocationContext>` |
| `org.junit.jupiter.engine.Constants` (deprecated in 6.1) | `org.junit.jupiter.api.Constants` |
| `ReflectionSupport.loadClass(String)` | `ReflectionSupport.tryToLoadClass(String)` |
| `org.junit.platform.commons.util.PreconditionViolationException` | `org.junit.platform.commons.PreconditionViolationException` |
| Kotlin `assertTimeout` contract `EXACTLY_ONCE` | `AT_MOST_ONCE`: code relying on definite assignment inside the block may not compile |

## Configuration and behaviour

| Change | Effect |
|---|---|
| `junit.jupiter.tempdir.scope` removed | Delete the setting |
| `junit.jupiter.params.arguments.conversion.locale.format` removed | `Locale` from String always uses BCP 47 (`"en-US"`, not `"en_US"`) |
| `junit.platform.reflection.search.useLegacySemantics` removed | Standard Java visibility and overriding rules always apply |
| Invalid enum configuration values now fail discovery | A typo such as `junit.jupiter.testinstance.lifecycle.default = perclass` is an error instead of being ignored |
| CSV parsing moved to FastCSV | Characters after a closing quote are an error; `@CsvFileSource(lineSeparator)` removed; `nullValues` and whitespace trimming apply to headers too; error messages for malformed CSV differ |
| Parameterized display names | `name = value` pairs, text arguments quoted (`quoteTextArguments = false` to turn off) |
| `@Nested` order | Deterministic (but not alphabetical); `@TestMethodOrder`/`@TestClassOrder` are inherited by nested classes |
| Display names | Control characters shown as `<LF>`, `<TAB>` ... |
| ConsoleLauncher | A subcommand (`execute`, `discover`, `engines`) is required; `--fail-fast` added; unusual option spellings (`--h`, `-help`) removed |
| Stack traces | Pruned to the test or lifecycle method |

## New features worth adopting after the upgrade

- Kotlin `suspend` test functions.
- `CancellationToken` and ConsoleLauncher `--fail-fast`.
- 6.1: `@DefaultLocale`, `@DefaultTimeZone`, `@SetSystemProperty`, `@ClearSystemProperty`, `@RestoreSystemProperties` built in (replacing JUnit Pioneer's versions), `@TempDir(deletionStrategy = ...)`, `worker_thread_pool` parallel executor, `Arguments.of(Iterable)`, Kotlin `assertThrowsExactly<T>`, a `junit.platform.reporting.open.xml.socket` option for live Open Test Reporting events.

## Upgrade checklist

1. Bump the BOM to 6.1.3, remove explicit versions on other `org.junit.*` artifacts.
2. JDK 17+ for tests, Kotlin 2.2+, Surefire/Failsafe 3.5.5+, Gradle launcher dependency.
3. Run `junit_audit.py` and fix every ERROR (removed APIs and settings).
4. Run the suite; compare the test count and display names in reports (parameterized names changed format, which can break report post-processing that matched names).
5. Replace deprecated APIs (WARN) in a follow-up change.
