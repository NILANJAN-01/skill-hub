# JUnit Jupiter API (JUnit 6.1.3), Java and Kotlin

Package `org.junit.jupiter.api` unless noted. Annotations work as meta-annotations, so you can compose your own (see Tags).

## A complete test class

Java:

```java
import static org.junit.jupiter.api.Assertions.*;

import org.junit.jupiter.api.*;

@DisplayName("Calculator")
class CalculatorTest {

    Calculator calculator;

    @BeforeEach
    void setUp() {
        calculator = new Calculator();          // a new test instance (and field) for every test
    }

    @Test
    @DisplayName("adds two numbers")
    void adds() {
        assertEquals(5, calculator.add(2, 3), "2 + 3");
    }

    @Test
    void rejectsDivisionByZero() {
        var e = assertThrows(ArithmeticException.class, () -> calculator.divide(1, 0));
        assertEquals("/ by zero", e.getMessage());
    }

    @Nested
    @DisplayName("when memory holds a value")
    class WithMemory {
        @BeforeEach
        void store() {
            calculator.store(10);
        }

        @Test
        void recallsIt() {
            assertEquals(10, calculator.recall());
        }
    }
}
```

Kotlin:

```kotlin
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.BeforeAll
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Nested
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows

class CalculatorTest {
    private lateinit var calculator: Calculator

    companion object {
        @JvmStatic
        @BeforeAll
        fun loadNativeLib() { /* once per class */ }
    }

    @BeforeEach
    fun setUp() {
        calculator = Calculator()
    }

    @Test
    fun `adds two numbers`() = assertEquals(5, calculator.add(2, 3))

    @Test
    fun `rejects division by zero`() {
        val e = assertThrows<ArithmeticException> { calculator.divide(1, 0) }
        assertEquals("/ by zero", e.message)
    }

    @Nested
    inner class `when memory holds a value` {          // `inner` is required for @Nested in Kotlin
        @BeforeEach
        fun store() = calculator.store(10)

        @Test
        fun `recalls it`() = assertEquals(10, calculator.recall())
    }
}
```

Kotlin test and lifecycle functions may be `suspend` (JUnit 6; needs `kotlinx-coroutines-core` and `kotlin-reflect`). JUnit runs them with `runBlocking`; for virtual time use a plain `@Test` with `runTest { }` from `kotlinx-coroutines-test`.

## Rules for test classes and methods

- Classes, test methods and lifecycle methods may be package-private or public, never `private`; methods must not be `abstract` and must not return a value (`@TestFactory` returns its dynamic tests). Records can be test classes.
- `@BeforeAll` / `@AfterAll` are `static` unless the class uses `@TestInstance(TestInstance.Lifecycle.PER_CLASS)` (or the configuration parameter `junit.jupiter.testinstance.lifecycle.default = per_class`). With `PER_CLASS` one instance serves all tests, so reset state in `@BeforeEach`.
- `@Nested` classes are non-static inner classes; each gets its own instance with access to the outer fields. Since JUnit 6 they run in a deterministic order, and `@TestMethodOrder` / `@TestClassOrder` are inherited by enclosed `@Nested` classes (`MethodOrderer.Default`, `ClassOrderer.Default` reset it).
- Test and lifecycle methods are inherited from superclasses and interfaces (see "Test interfaces").

## Annotations

| Annotation | Purpose |
|---|---|
| `@Test` | A test method |
| `@ParameterizedTest`, `@ParameterizedClass` | Data-driven tests (`org.junit.jupiter.params`), see [parameterized.md](parameterized.md) |
| `@RepeatedTest(n)` | Run n times; inject `RepetitionInfo` |
| `@TestFactory` | Returns dynamic tests |
| `@TestTemplate`, `@ClassTemplate` | Run once per invocation context from a provider extension |
| `@BeforeEach`, `@AfterEach`, `@BeforeAll`, `@AfterAll` | Lifecycle (JUnit 4: `@Before`, `@After`, `@BeforeClass`, `@AfterClass`) |
| `@Nested` | Inner test class |
| `@DisplayName("...")`, `@DisplayNameGeneration(...)` | Readable names in reports and IDEs |
| `@Tag("fast")` | Filtering in the build |
| `@Disabled("reason")` | Skip a class or method |
| `@Timeout(5)` | Fail when slower than the limit |
| `@TempDir` (`org.junit.jupiter.api.io`) | Temporary folder, deleted afterwards |
| `@AutoClose` | Close the field after the tests (`close()` or the named method) |
| `@TestInstance(PER_CLASS)` | One instance for the whole class |
| `@TestMethodOrder`, `@TestClassOrder`, `@Order(n)` | Explicit ordering |
| `@ExtendWith`, `@RegisterExtension` | Register extensions |

## Assertions (`org.junit.jupiter.api.Assertions`)

| Method | Notes |
|---|---|
| `assertEquals(expected, actual[, message])`, `assertNotEquals` | Overloads for primitives; `assertEquals(1.0, x, 0.001)` with a delta |
| `assertTrue(cond[, message])`, `assertFalse` | Message may be a `Supplier<String>` (built only on failure) |
| `assertNull`, `assertNotNull`, `assertSame`, `assertNotSame` | |
| `assertArrayEquals`, `assertIterableEquals` | Element by element, deep |
| `assertLinesMatch(expectedLines, actualLines)` | Lines with regexes and `>> skip >>` markers |
| `assertInstanceOf(Type.class, obj)` | Returns the cast value |
| `assertThrows(Type.class, executable)` | Type or subtype; returns the exception |
| `assertThrowsExactly(Type.class, executable)` | Exactly that type |
| `assertDoesNotThrow(executable)` | Returns the supplier's result |
| `assertAll([heading,] executables...)` | Runs all, reports every failure (`MultipleFailuresError`) |
| `assertTimeout(Duration, executable)` | Runs in the same thread, fails after it finishes late |
| `assertTimeoutPreemptively(Duration, executable)` | Aborts in another thread: `ThreadLocal` state (e.g. Spring transactions) is not visible |
| `fail([message])` | |

```java
assertAll("address",
    () -> assertEquals("Berlin", address.city()),
    () -> assertEquals("10115", address.zip()));

String greeting = assertTimeout(Duration.ofMillis(200), () -> service.greet("Ada"));

var e = assertThrows(IllegalArgumentException.class, () -> new Money(-1, "EUR"));
assertTrue(e.getMessage().contains("negative"), () -> "message was: " + e.getMessage());
```

Kotlin top-level functions in `org.junit.jupiter.api`: `assertThrows<T> { }`, `assertThrowsExactly<T> { }` (6.1), `assertDoesNotThrow { }`, `assertAll("heading", { ... }, { ... })`, `assertInstanceOf<T>(x)`, `assertNotNull(x)` (smart-casts), `assertTimeout(Duration) { }`, `fail("...")`. The Java methods work from Kotlin too (`Assertions.assertEquals`).

Third-party assertion libraries (AssertJ `assertThat(x).isEqualTo(y)`, Hamcrest, Truth, kotlin.test) work with any JUnit version; keep to the one the project uses.

## Assumptions (`org.junit.jupiter.api.Assumptions`)

```java
assumeTrue(System.getenv("CI") != null, "only on CI");     // aborted (skipped) if false
assumingThat(os.isWindows(), () -> assertEquals("\\", separator));   // runs the block only if true
Assumptions.abort("feature flag off");
```

An aborted test is reported as skipped with the message, not as a failure.

## Display names

- `@DisplayName` on classes and methods (emoji and spaces allowed).
- `@DisplayNameGeneration(DisplayNameGenerator.ReplaceUnderscores.class)` turns `adds_two_numbers` into "adds two numbers"; `@IndicativeSentencesGeneration(separator = ", ", generator = ReplaceUnderscores.class)` builds "Calculator, adds two numbers".
- Default for all classes: `junit.jupiter.displayname.generator.default = org.junit.jupiter.api.DisplayNameGenerator$ReplaceUnderscores` in `junit-platform.properties`.
- JUnit 6 shows control characters as `<LF>` etc. in names.

## Tags and composed annotations

```java
@Target({ElementType.TYPE, ElementType.METHOD})
@Retention(RetentionPolicy.RUNTIME)
@Tag("integration")
@Test
public @interface IntegrationTest { }          // use instead of @Test
```

```kotlin
@Target(AnnotationTarget.CLASS, AnnotationTarget.FUNCTION)
@Retention(AnnotationRetention.RUNTIME)
@Tag("integration")
@Test
annotation class IntegrationTest
```

Tag expressions in builds: `fast & !slow`, `(smoke | critical) & !flaky`, `any()`, `none()`. Tags must not contain spaces, `,`, `(`, `)`, `&`, `|` or `!`.

## Conditional execution (`org.junit.jupiter.api.condition`)

| Annotation | Example |
|---|---|
| `@EnabledOnOs` / `@DisabledOnOs` | `@EnabledOnOs(value = OS.LINUX, architectures = "aarch64")` |
| `@EnabledOnJre` / `@DisabledOnJre` | `@EnabledOnJre(JRE.JAVA_21)`, or `versions = 26` for versions without a constant |
| `@EnabledForJreRange` / `@DisabledForJreRange` | `@EnabledForJreRange(min = JRE.JAVA_21)`, `minVersion = 25`; default min is Java 17 in JUnit 6 |
| `@EnabledIfSystemProperty` / `@EnabledIfEnvironmentVariable` (and `Disabled...`) | `@EnabledIfEnvironmentVariable(named = "CI", matches = "true")`, repeatable |
| `@EnabledIf("methodName")` / `@DisabledIf` | Boolean method in the class, or `"com.x.Conditions#isOnline"` |
| `@EnabledInNativeImage` / `@DisabledInNativeImage` | GraalVM native image |

Each has `disabledReason`. `JRE.JAVA_8` to `JAVA_16` and `JRE.OTHER` are deprecated in JUnit 6; use the int attributes.

## Ordering

```java
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
class CheckoutFlowTest {
    @Test @Order(1) void addToCart() { }
    @Test @Order(2) void pay() { }
}
```

Method orderers: `MethodName` (replaces `Alphanumeric`, removed in JUnit 6), `DisplayName`, `OrderAnnotation`, `Random` (seed in `junit.jupiter.execution.order.random.seed`), `Default`. Class orderers for `@Nested`/top-level: `ClassName`, `DisplayName`, `OrderAnnotation`, `Random`, `Default`. Prefer independent tests; ordering is for flows where it is the point.

## Injected parameters

| Type | Gives |
|---|---|
| `TestInfo` | `getDisplayName()`, `getTags()`, `getTestMethod()`, `getTestClass()` |
| `TestReporter` | `publishEntry("key", "value")`, `publishFile(...)`: shown in reports |
| `RepetitionInfo` | `getCurrentRepetition()`, `getTotalRepetitions()` in `@RepeatedTest` |
| `@TempDir Path` | Temporary folder (field or parameter) |

```java
@RepeatedTest(value = 5, name = "{displayName} {currentRepetition}/{totalRepetitions}", failureThreshold = 2)
void staysStable(RepetitionInfo info, TestReporter reporter) {
    reporter.publishEntry("run", String.valueOf(info.getCurrentRepetition()));
    assertTrue(cache.isConsistent());
}
```

## Dynamic tests

```java
@TestFactory
Stream<DynamicTest> palindromes() {
    return Stream.of("racecar", "radar", "level")
        .map(word -> DynamicTest.dynamicTest(word, () -> assertTrue(isPalindrome(word))));
}

@TestFactory
Collection<DynamicNode> grouped() {
    return List.of(DynamicContainer.dynamicContainer("valid", Stream.of(
        DynamicTest.dynamicTest("one", () -> assertEquals(1, parse("1"))))));
}
```

Dynamic tests have no per-test `@BeforeEach`/`@AfterEach`; lifecycle runs once around the factory. Prefer `@ParameterizedTest` when the cases are data.

## Timeouts

- `@Timeout(5)` (seconds), `@Timeout(value = 500, unit = TimeUnit.MILLISECONDS)`, on methods, classes or lifecycle methods. `threadMode = Timeout.ThreadMode.SEPARATE_THREAD` runs the code in another thread so a hang can be interrupted.
- Defaults for all tests: `junit.jupiter.execution.timeout.default = 10 s`, `...timeout.testable.method.default`, `...lifecycle.method.default`.
- `junit.jupiter.execution.timeout.mode = disabled_on_debug` turns timeouts off while debugging.

## Built-in extensions

```java
@TempDir Path workDir;                                          // per test; static field = per class

@Test
void writes(@TempDir(cleanup = CleanupMode.ON_SUCCESS) Path dir) throws IOException {
    Path file = Files.writeString(dir.resolve("out.txt"), "hello");
    assertEquals("hello", Files.readString(file));
}

@AutoClose
HttpClient client = HttpClient.newHttpClient();                 // closed after each test (instance field)

@Test
@DefaultLocale("de-DE")                                         // org.junit.jupiter.api.util, JUnit 6.1
@DefaultTimeZone("Europe/Berlin")
@SetSystemProperty(key = "feature.x", value = "on")
void formatsGermanDates() { }
```

`@TempDir` also takes `factory` (a `TempDirFactory`) and `deletionStrategy` (`TempDirDeletionStrategy.Standard` fails the test if deletion fails, `IgnoreFailures` only warns; 6.1). `@ClearSystemProperty(key = ...)` and `@RestoreSystemProperties` restore system properties after the test. Mark tests that touch the same global state with `@ResourceLock(Resources.SYSTEM_PROPERTIES)` or `@WritesSystemProperty` when running in parallel.

## Test interfaces and default methods

```java
interface ContractTests<T extends Comparable<T>> {
    T smaller();
    T larger();

    @Test
    default void smallerIsLess() {
        assertTrue(smaller().compareTo(larger()) < 0);
    }
}

class MoneyTest implements ContractTests<Money> {
    public Money smaller() { return Money.of(1); }
    public Money larger() { return Money.of(2); }
}
```

Interfaces can also carry `@BeforeEach`, `@Tag`, `@ExtendWith` and (with `@TestInstance(PER_CLASS)`) `@BeforeAll` for shared contracts.
