---
name: junit-test-authoring
description: "Write JUnit 6 (Jupiter) tests in Java or Kotlin: Gradle/Maven setup, assertions, lifecycle, @Nested, @DisplayName, tags, @ParameterizedTest and @ParameterizedClass, dynamic tests, @TempDir, @Timeout, conditions, extensions and parallel runs. A script checks the build setup and generates a test class for a source file. Use when the user wants JUnit tests written or JUnit set up."
license: Complete terms in the repository README
compatibility: Scripts need Python 3.8+ (standard library only). The tests need JDK 17+ and Gradle or Maven with JUnit 6.1.3 (Kotlin 2.2+ for Kotlin tests). Works with junit-migration and junit-run-reports (the junit-tools bundle); kotlin-unit-test adds coverage and mutation checks for Kotlin.
metadata:
  title: "JUnit 6 test authoring (Java and Kotlin)"
  category: junit-tools
---

# JUnit 6 test authoring (Java and Kotlin)

JUnit 6 = **JUnit Platform** (launches tests, used by Gradle, Maven and IDEs) + **JUnit Jupiter** (the API you write tests with, `org.junit.jupiter.api`) + **JUnit Vintage** (deprecated runner for old JUnit 4 tests). Since 6.0 all three share one version: **6.1.3** (August 2026). JUnit 6 needs **Java 17+** at runtime and **Kotlin 2.2+**.

| Need | Skill |
|---|---|
| Set up JUnit, write tests, parameterized tests, extensions | this skill |
| Move JUnit 4 or JUnit 5 code to JUnit 6, audit a suite for weak or never-run tests | `junit-migration` |
| Run a subset, read Gradle/Maven/JUnit reports, explain failures, find flaky tests | `junit-run-reports` |
| Kotlin coverage, untested-method map, mutation check | `kotlin-unit-test` |

## When to use

- "Write JUnit tests for this class", "add JUnit 5/6 to the project", "make this a parameterized test".
- Java or Kotlin unit and integration tests on the JVM, including Android local unit tests (`src/test`).
- Choosing assertions, lifecycle, nesting, tags, timeouts, temporary folders or an extension.

## When NOT to use

- Android instrumented tests (`src/androidTest`, UI Automator, Espresso): use `uiautomator-test-authoring`.
- TestNG, Spock, Kotest specs, or non-JVM languages.
- The project still runs JUnit 4: migrate first (`junit-migration`), or write new tests in Jupiter beside them with the Vintage engine temporarily.

## Procedure

`scripts/junit_scaffold.py` is in this skill's folder. Run it from the project root.

1. **Learn the project first.** Find the build file, existing tests (`src/test/java`, `src/test/kotlin`), their naming (`FooTest`), assertion library (Jupiter `Assertions`, AssertJ, Hamcrest, kotlin.test), mocking (Mockito, MockK) and test data helpers. Follow what is there.
2. **Check the setup.**
   ```bash
   python scripts/junit_scaffold.py check .        # exit 1 = something is missing, with the snippet to add
   python scripts/junit_scaffold.py deps --build gradle-kts|gradle-groovy|toml|maven [--kotlin] [--vintage]
   ```
   The minimum for Gradle (Kotlin DSL):
   ```kotlin
   dependencies {
       testImplementation(platform("org.junit:junit-bom:6.1.3"))
       testImplementation("org.junit.jupiter:junit-jupiter")          // api + params + engine
       testRuntimeOnly("org.junit.platform:junit-platform-launcher")  // required by Gradle 9
   }
   tasks.test { useJUnitPlatform() }
   ```
   Maven: import `org.junit:junit-bom:6.1.3` in `dependencyManagement`, add `org.junit.jupiter:junit-jupiter` (test scope) and pin `maven-surefire-plugin` to 3.5.5 or newer (JUnit 6 needs 3.0.0+). Android local unit tests: `android { testOptions { unitTests.all { it.useJUnitPlatform() } } }`.
3. **Generate a starting point** (optional):
   ```bash
   python scripts/junit_scaffold.py new src/main/java/com/shop/PriceCalculator.java   # -> src/test/java/com/shop/PriceCalculatorTest.java
   python scripts/junit_scaffold.py new src/main/kotlin/com/shop/Basket.kt --stdout
   ```
   It writes one `@Nested` group per public method: a test that calls it and **fails with a TODO** until you assert something, an `assertThrows` test for each exception the method throws (Kotlin `require`/`check` included), and a `@Disabled` `@ParameterizedTest` `@CsvSource` template for methods with simple parameters. The output compiles; nothing passes by accident. Replace every TODO with real inputs and assertions.
4. **Write the tests** with the rules below and the API in [references/jupiter-api.md](references/jupiter-api.md), [references/parameterized.md](references/parameterized.md) and [references/extensions-and-parallel.md](references/extensions-and-parallel.md).
5. **Run and verify:** `./gradlew test --tests 'com.shop.PriceCalculatorTest'` or `mvn test -Dtest=PriceCalculatorTest` (see `junit-run-reports`). Make each new test fail once on purpose (break the code or the expectation) to prove it can fail. If `junit-migration` is installed, run its audit and fix every ERROR.

## Rules for good JUnit tests

1. **One behaviour per test**, named for it: `@DisplayName("adds VAT to the net price")` (Java) or a backtick name `` fun `adds VAT to the net price`() `` (Kotlin). Arrange, act, assert.
2. **Test classes and methods are package-private** (no `public` needed), never `private` or `static`, and return `void` (`@TestFactory` excepted). A private or static `@Test` is silently skipped.
3. **Lifecycle:** `@BeforeEach`/`@AfterEach` per test; `@BeforeAll`/`@AfterAll` must be `static` (Kotlin: in a `companion object` with `@JvmStatic`) unless the class has `@TestInstance(Lifecycle.PER_CLASS)`. JUnit creates a new instance per test method, so instance fields are fresh.
4. **Assert precisely:** `assertEquals(expected, actual, "message")` (the message is the **last** argument), `assertThrows(Type.class, () -> ...)` and then assert on the exception, `assertAll` to report several related checks together. Kotlin: `assertThrows<Type> { }`, `assertAll(...)`, `assertInstanceOf<T>(x)` from `org.junit.jupiter.api`. Use AssertJ or Hamcrest if the project already does.
5. **Group with `@Nested`** inner classes (Kotlin: `inner class`) for "when ..." contexts; each nested class can have its own `@BeforeEach`.
6. **Data-driven tests:** `@ParameterizedTest` with `@ValueSource`, `@CsvSource` (text blocks), `@MethodSource`/`@FieldSource` or `@EnumSource`; `@ParameterizedClass` to run a whole class per argument set.
7. **No hidden dependencies:** no test order (`@TestMethodOrder` only when order is the point), no shared mutable statics, no real clock, network or random without a seed. Use `@TempDir` for files, `@DefaultLocale`/`@DefaultTimeZone`/`@SetSystemProperty` (6.1, `org.junit.jupiter.api.util`) for global state, `@AutoClose` for resources.
8. **No sleeps.** Wait for a condition (Awaitility, latches) or inject a fake clock/executor. `@Timeout` guards against hangs.
9. **Skip with reasons:** `@Disabled("why, ticket")`, `assumeTrue(cond, "why")` for environment-dependent tests, or `@EnabledOnOs`, `@EnabledIfEnvironmentVariable`, `@EnabledForJreRange(min = JAVA_21)`.
10. **Tag** slow or integration tests (`@Tag("integration")`, or a composed `@IntegrationTest` annotation) and filter them in the build.

## Safety rules

- Tests must not touch production systems, real customer data or the user's home folder: use `@TempDir`, fakes, test containers or test accounts.
- Never put secrets in test code; read them from environment variables or CI secrets, and skip with an assumption when they are missing.
- Don't weaken or delete an existing assertion to make a test pass; report the failure instead.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `No tests found` / 0 tests run on Gradle | `useJUnitPlatform()` missing, or only `junit-jupiter-api` without the engine: depend on `org.junit.jupiter:junit-jupiter` |
| A test never runs, no error | It is `private`, `static`, returns a value, is in a static (Java) or non-`inner` (Kotlin) `@Nested` class, or uses `org.junit.Test` (JUnit 4) |
| `@BeforeAll method ... must be static` | Make it static (Kotlin: companion + `@JvmStatic`) or use `@TestInstance(PER_CLASS)` |
| `ParameterResolutionException: No ParameterResolver registered` | A parameter on a plain `@Test`, or a missing `@ExtendWith` (Mockito, Spring) |
| `NoSuchMethodError` / `OutputDirectoryProvider not available` | Mixed JUnit versions: use the BOM and the launcher dependency |
| Parameterized display names show `arg0` | Compile with `-parameters` (Java) / `-java-parameters` (Kotlin), or use `name = "{0} ..."` |

## References

- [references/jupiter-api.md](references/jupiter-api.md): annotations, assertions, assumptions, lifecycle, nested, display names, tags, conditions, ordering, repeated and dynamic tests, timeouts, built-in extensions, Java and Kotlin examples.
- [references/parameterized.md](references/parameterized.md): `@ParameterizedTest`, `@ParameterizedClass`, every argument source, conversion, aggregation, display names.
- [references/extensions-and-parallel.md](references/extensions-and-parallel.md): registering and writing extensions, configuration parameters, parallel execution, suites.
- [references/sources.md](references/sources.md): the official pages and versions this skill set follows.
