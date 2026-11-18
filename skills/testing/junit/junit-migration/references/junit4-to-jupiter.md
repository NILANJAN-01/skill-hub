# JUnit 3/4 to JUnit Jupiter

## Mapping

| JUnit 4 (`org.junit`) | JUnit Jupiter (`org.junit.jupiter.api`) |
|---|---|
| `@Test` | `@Test` (new package, no attributes) |
| `@Test(expected = X.class)` | `assertThrows(X.class, () -> ...)`, then assert on the exception |
| `@Test(timeout = 1000)` | `@Timeout(value = 1, unit = SECONDS)` or `assertTimeout(Duration.ofSeconds(1), ...)` |
| `@Before` / `@After` | `@BeforeEach` / `@AfterEach` |
| `@BeforeClass` / `@AfterClass` | `@BeforeAll` / `@AfterAll` (static, or `@TestInstance(PER_CLASS)`) |
| `@Ignore("reason")` | `@Disabled("reason")` |
| `@Category(Slow.class)` | `@Tag("slow")` (Vintage exposes categories as tags named by the class, e.g. `com.acme.Slow`) |
| `@FixMethodOrder(NAME_ASCENDING)` | `@TestMethodOrder(MethodOrderer.MethodName.class)` |
| `@RunWith(MockitoJUnitRunner.class)` | `@ExtendWith(MockitoExtension.class)` (`org.mockito:mockito-junit-jupiter`) |
| `@RunWith(SpringRunner.class)` | `@ExtendWith(SpringExtension.class)` (implied by `@SpringBootTest`, `@WebMvcTest`, ...) |
| `@RunWith(Enclosed.class)` | `@Nested` inner classes |
| `@RunWith(Parameterized.class)` | `@ParameterizedClass` + class-level source, or `@ParameterizedTest` per method |
| `@RunWith(Suite.class) @SuiteClasses` | `@Suite @SelectClasses` (`junit-platform-suite`) |
| `@RunWith(Theories.class)` | `@ParameterizedTest` with sources |
| `@Rule TemporaryFolder` | `@TempDir Path dir` |
| `@Rule ExpectedException` | `assertThrows` |
| `@Rule Timeout` | `@Timeout` on the class |
| `@Rule TestName` | `TestInfo` parameter |
| `@Rule ErrorCollector` | `assertAll(...)` |
| `@Rule TestWatcher` | an extension implementing `org.junit.jupiter.api.extension.TestWatcher` |
| `@Rule ExternalResource` / custom rules | an extension (`BeforeEachCallback`, `AfterEachCallback`), `@RegisterExtension`, or `@AutoClose` fields |
| `@ClassRule` | `static @RegisterExtension` field or class-level `@ExtendWith` |
| `org.junit.Assert.*` | `org.junit.jupiter.api.Assertions.*`, **message last** |
| `Assert.assertThat(x, matcher)` | Hamcrest `MatcherAssert.assertThat` or AssertJ `assertThat` |
| `org.junit.Assume.*` | `org.junit.jupiter.api.Assumptions.*` |
| JUnit 3 `extends TestCase`, `setUp()`, `testFoo()` | Plain class, `@BeforeEach void setUp()`, `@Test void foo()` |
| `public` classes and methods | Package-private is enough |

The failure message moved from first to last in `assertTrue`, `assertFalse`, `assertNull`, `assertNotNull`, `assertEquals`, `assertNotEquals`, `assertArrayEquals`, `assertSame`, `assertNotSame`, `assertThrows`, `assumeTrue`, `assumeFalse`. A call that still compiles after only changing the import (for example `assertEquals("total", expected, actual)` with Strings) now compares the message with the value: the audit reports it as `message-first`.

## Before and after (Java)

JUnit 4:

```java
@RunWith(Parameterized.class)
public class InvoiceTest {
    @Rule public TemporaryFolder folder = new TemporaryFolder();
    @Rule public ExpectedException thrown = ExpectedException.none();

    @Parameterized.Parameters(name = "{0} items")
    public static Collection<Object[]> data() {
        return Arrays.asList(new Object[][] {{1, 10}, {2, 20}});
    }

    private final int quantity;
    private final int expected;
    private Invoice invoice;

    public InvoiceTest(int quantity, int expected) {
        this.quantity = quantity;
        this.expected = expected;
    }

    @Before
    public void setUp() {
        invoice = new Invoice();
    }

    @Test
    public void total() {
        assertEquals("total", expected, invoice.total(quantity));
    }

    @Test
    public void negativeQuantity() {
        thrown.expect(IllegalArgumentException.class);
        thrown.expectMessage("negative");
        invoice.total(-1);
    }

    @Test
    public void export() throws IOException {
        File out = folder.newFile("invoice.csv");
        invoice.export(out);
        assertTrue(out.length() > 0);
    }
}
```

Jupiter (the parameterized part becomes a `@ParameterizedTest`, so the non-parameterized tests run once):

```java
class InvoiceTest {
    Invoice invoice;

    @BeforeEach
    void setUp() {
        invoice = new Invoice();
    }

    @ParameterizedTest(name = "{0} items")
    @CsvSource({ "1, 10", "2, 20" })
    void total(int quantity, int expected) {
        assertEquals(expected, invoice.total(quantity), "total");
    }

    @Test
    void negativeQuantity() {
        var e = assertThrows(IllegalArgumentException.class, () -> invoice.total(-1));
        assertTrue(e.getMessage().contains("negative"));
    }

    @Test
    void export(@TempDir Path dir) throws IOException {
        File out = dir.resolve("invoice.csv").toFile();
        invoice.export(out);
        assertTrue(out.length() > 0);
    }
}
```

To keep the class-wide parameterization instead (every test runs per row), follow the JUnit guide's recipe: replace `@RunWith(Parameterized.class)` with `@ParameterizedClass`, add a class-level `@MethodSource("data")` pointing to the old `@Parameters` method (and remove `@Parameters`), turn `@Parameter` fields into `org.junit.jupiter.params.Parameter` fields or keep the constructor, and replace `@BeforeParam`/`@AfterParam` with `@BeforeParameterizedClassInvocation`/`@AfterParameterizedClassInvocation`.

## Before and after (Kotlin)

```kotlin
// JUnit 4
class CartTest {
    @get:Rule val folder = TemporaryFolder()
    private lateinit var cart: Cart

    @Before fun setUp() { cart = Cart() }

    @Test(expected = IllegalArgumentException::class)
    fun rejectsBlank() { cart.add(" ") }

    companion object {
        @BeforeClass @JvmStatic fun loadCatalog() { }
    }
}

// Jupiter
class CartTest {
    @TempDir lateinit var folder: Path
    private lateinit var cart: Cart

    @BeforeEach fun setUp() { cart = Cart() }

    @Test
    fun `rejects blank items`() {
        assertThrows<IllegalArgumentException> { cart.add(" ") }
    }

    companion object {
        @BeforeAll @JvmStatic fun loadCatalog() { }
    }
}
```

Kotlin specifics: `@get:Rule` disappears; `@Nested` classes must be `inner class`; `kotlin.test` assertions keep working (add `kotlin-test-junit5` instead of `kotlin-test-junit`).

## Writing a replacement for a custom rule

```java
// JUnit 4: public class DatabaseRule extends ExternalResource { before() / after() }
public class DatabaseExtension implements BeforeEachCallback, AfterEachCallback {
    @Override public void beforeEach(ExtensionContext c) { Database.start(); }
    @Override public void afterEach(ExtensionContext c) { Database.stop(); }
}

@ExtendWith(DatabaseExtension.class)
class RepositoryTest { }
```

## Running JUnit 4 and Jupiter side by side

During a gradual migration:

```kotlin
dependencies {
    testImplementation(platform("org.junit:junit-bom:6.1.3"))
    testImplementation("org.junit.jupiter:junit-jupiter")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
    testImplementation("junit:junit:4.13.2")                          // temporary
    testRuntimeOnly("org.junit.vintage:junit-vintage-engine")         // temporary, deprecated in JUnit 6
}
tasks.test { useJUnitPlatform() }
```

- One class uses one framework: mixing `org.junit.Test` with `org.junit.jupiter.api.BeforeEach` means each engine ignores the other's annotations.
- The Vintage engine logs an INFO discovery issue in JUnit 6 when it finds JUnit 4 classes (`junit.vintage.discovery.issue.reporting.enabled = false` silences it).
- `junit-jupiter-migrationsupport` (`@EnableRuleMigrationSupport` for `ExternalResource`, `Verifier`, `ExpectedException`; `@EnableJUnit4MigrationSupport` adds `@Ignore`) is deprecated and will be removed: use it only as a short bridge.
- Without `junit-vintage-engine`, Gradle's `useJUnitPlatform()` and Surefire with `junit-jupiter` on the classpath run **no** JUnit 4 tests and report no error. Compare test counts before and after.
