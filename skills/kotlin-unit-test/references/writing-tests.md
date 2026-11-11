# Writing good Kotlin unit tests

## Shape of a test

```kotlin
class PriceCalculatorTest {
    private val taxes = mockk<TaxTable>()
    private val calculator = PriceCalculator(taxes)

    @Test
    fun `total adds tax for a normal basket`() {
        every { taxes.rateFor("DE") } returns 0.19                 // Arrange
        val total = calculator.total(listOf(100.0, 50.0), "DE")    // Act
        assertEquals(178.5, total, 0.001)                          // Assert
    }

    @Test
    fun `total of an empty basket is zero`() {
        every { taxes.rateFor(any()) } returns 0.19
        assertEquals(0.0, calculator.total(emptyList(), "DE"), 0.0)
    }

    @Test
    fun `total rejects an unknown country`() {
        every { taxes.rateFor("XX") } throws IllegalArgumentException("unknown")
        assertFailsWith<IllegalArgumentException> { calculator.total(listOf(1.0), "XX") }
    }
}
```

- **One behaviour per test.** Name the test `<method> <does what> <when>`, so the report links it to the method.
- **Per method, cover:** the normal case, the boundaries (empty, 0, 1, max, null), invalid input (the exception), and every branch (`if`/`when`).
- **Expected values come from the specification**, not from running the code and copying its output. If the code's current behaviour looks wrong, say so; don't encode the bug.
- **Use exact assertions:** `assertEquals(expected, actual)`. For lists and objects, compare whole values (data classes compare by value). For doubles, use a delta.
- **Keep tests independent.** Create fresh objects for each test; JUnit 5 creates a new test-class instance for every test by default.

## Libraries

| Need | Use |
|---|---|
| Assertions | `kotlin.test` (`assertEquals`, `assertTrue`, `assertFailsWith`, `assertNull`), JUnit 5 `Assertions`, or AssertJ/Kotest matchers if the project already uses them |
| Mocks | MockK: `mockk<T>()`, `every { } returns`, `verify { }`, `relaxed = true`; `mockkObject(Singleton)` / `mockkStatic("pkg.FileKt")` for objects and top-level functions (call `unmockkAll()` in `@AfterEach`) |
| Coroutines | `kotlinx-coroutines-test`: `@Test fun x() = runTest { … }`; inject a `TestDispatcher`; `advanceUntilIdle()`; collect flows with `toList()` or Turbine |
| Parameterized | `@ParameterizedTest` with `@CsvSource` / `@ValueSource` / `@MethodSource` (`junit-jupiter-params`) |
| Time | Inject `java.time.Clock` and use `Clock.fixed(...)` in tests |

## Android (JVM unit tests in `src/test`)

- Test ViewModels, use cases, repositories, mappers and validators on the JVM. Don't touch Android framework classes, or use Robolectric when you must.
- **ViewModel:** call `Dispatchers.setMain(StandardTestDispatcher())` in `@BeforeEach` and `Dispatchers.resetMain()` in `@AfterEach`. Read `StateFlow.value`, or collect it in `runTest`. For LiveData, use `InstantTaskExecutorRule` (JUnit 4) or the `InstantTaskExecutorExtension` pattern (JUnit 5).
- Run with `ktest.py run --variant debug`, which runs `testDebugUnitTest` per module.

## Test-automation code (Appium, Selenium, Espresso helpers)

Unit-test the logic of page objects, locator builders, wait helpers, data builders and report parsers **without a device or browser.** Mock the driver and its elements:

```kotlin
class LoginPageTest {
    private val driver = mockk<AndroidDriver>()
    private val user = mockk<WebElement>(relaxed = true)
    private val pass = mockk<WebElement>(relaxed = true)
    private val submit = mockk<WebElement>(relaxed = true)

    @Test
    fun `login types the credentials and taps submit`() {
        every { driver.findElement(AppiumBy.id("com.app:id/user")) } returns user
        every { driver.findElement(AppiumBy.id("com.app:id/pass")) } returns pass
        every { driver.findElement(AppiumBy.id("com.app:id/login")) } returns submit

        LoginPage(driver).login("ann", "secret")

        verifyOrder {
            user.sendKeys("ann")
            pass.sendKeys("secret")
            submit.click()
        }
    }

    @Test
    fun `errorText is null when no error is shown`() {
        every { driver.findElements(AppiumBy.id("com.app:id/error")) } returns emptyList()
        assertNull(LoginPage(driver).errorText())
    }
}
```

- Put retry and wait logic behind an injectable clock or sleeper, so tests don't really wait.
- Test locator builders and parsers with plain inputs and outputs (strings, XML snippets).
- End-to-end tests that need a real device stay in the automation suite; they are not unit tests.

## Kotlin scripts (`.kts`) and loose files

Scripts can't be unit-tested directly. Move the logic into functions in a `.kt` file, keep the script as a thin `main` that calls them, and test those functions. For loose files without a build, see [setup.md](setup.md).

## What not to do

- Don't write tests without assertions, `assertTrue(true)`, or tests that only print.
- Don't catch exceptions in a test to make it pass, and don't add `@Disabled` to get a green build.
- Don't use `Thread.sleep`, real servers, real devices, shared mutable state between tests, or a dependency on test order.
- Don't change production code just to make a test pass, and don't make members public only for tests. Test through the public API; `internal` is visible to tests in the same module.
