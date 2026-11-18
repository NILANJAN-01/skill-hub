# Parameterized tests and classes (junit-jupiter-params)

Included in the aggregate `org.junit.jupiter:junit-jupiter`; with separate artifacts add `org.junit.jupiter:junit-jupiter-params`. Annotations are in `org.junit.jupiter.params` and `org.junit.jupiter.params.provider`.

## @ParameterizedTest

```java
@ParameterizedTest
@ValueSource(strings = { "racecar", "radar", "able was I ere I saw elba" })
void palindromes(String candidate) {
    assertTrue(StringUtils.isPalindrome(candidate));
}

@ParameterizedTest(name = "{0} x {1} = {2}")
@CsvSource(textBlock = """
    2, 3, 6
    0, 9, 0
    -1, 4, -4
    """)
void multiplies(int a, int b, int expected) {
    assertEquals(expected, calculator.multiply(a, b));
}
```

```kotlin
@ParameterizedTest(name = "{0} x {1} = {2}")
@CsvSource("2, 3, 6", "0, 9, 0", "-1, 4, -4")
fun multiplies(a: Int, b: Int, expected: Int) = assertEquals(expected, calculator.multiply(a, b))

@ParameterizedTest
@MethodSource("invalidEmails")
fun `rejects invalid emails`(email: String) {
    assertThrows<IllegalArgumentException> { Email(email) }
}

companion object {
    @JvmStatic
    fun invalidEmails() = listOf("", "no-at-sign", "a@", "@b.com")
}
```

Parameter order: indexed (source) parameters first, then aggregators (`ArgumentsAccessor`, `@AggregateWith`), then injected ones (`TestInfo`, `@TempDir`).

## Argument sources

| Source | Use |
|---|---|
| `@ValueSource(ints = {...})` | One argument: `shorts, bytes, ints, longs, floats, doubles, chars, booleans, strings, classes` |
| `@NullSource`, `@EmptySource`, `@NullAndEmptySource` | `null` / empty String, collection, map, array (`@EmptySource(type = ...)` in 6.1) |
| `@EnumSource(Unit.class)` | All constants; `names = {"A","B"}`, `mode = EXCLUDE`, `mode = MATCH_ALL` (regex names), `from = "B", to = "D"` |
| `@CsvSource({"a, 1", "'b, c', 2"})` / `textBlock = """..."""` | Rows; `'` quotes; empty `''` = `""`, nothing = `null`; `nullValues = "N/A"`, `delimiter`, `useHeadersInDisplayName`, `#` comments in text blocks |
| `@CsvFileSource(resources = "/cases.csv", numLinesToSkip = 1)` | CSV from the classpath (`files =` for paths); `"` is the quote character |
| `@MethodSource("factory")` | `static` method returning `Stream`, `Iterable`, array, primitive stream; elements are values, `Object[]` or `Arguments`. Name omitted = same name as the test; external: `"com.x.Cases#emails"` |
| `@FieldSource("cases")` | `static` field (a `List`, array, or `Supplier<Stream<...>>`); external `"com.x.Cases#cases"` |
| `@ArgumentsSource(MyProvider.class)` | A class implementing `ArgumentsProvider` |

Sources are repeatable and can be combined; each adds invocations. Factory methods and fields need not be static with `@TestInstance(PER_CLASS)`.

```java
static Stream<Arguments> discounts() {
    return Stream.of(
        arguments(100, 0, 100),
        argumentSet("member discount", 100, 10, 90),       // named set: shown as the display name
        arguments(Named.of("big order", 1_000), 15, 850));
}

@ParameterizedTest
@MethodSource("discounts")
void appliesDiscount(int price, int percent, int expected) {
    assertEquals(expected, pricing.apply(price, percent));
}

public class EvenNumbers implements ArgumentsProvider {
    @Override
    public Stream<? extends Arguments> provideArguments(ParameterDeclarations parameters, ExtensionContext context) {
        return IntStream.rangeClosed(1, 5).map(i -> i * 2).mapToObj(Arguments::of);
    }
}
```

`ParameterDeclarations` is `org.junit.jupiter.params.support.ParameterDeclarations`. `arguments`/`argumentSet` are static methods of `org.junit.jupiter.params.provider.Arguments`; `Named.of` / `named` are in `org.junit.jupiter.api.Named`. JUnit 6.1 adds `Arguments.of(Iterable)` and `argumentSetFrom(name, Iterable)`.

## @ParameterizedClass (run the whole class per argument set)

```java
@ParameterizedClass
@ValueSource(strings = { "postgres", "mysql" })
class RepositoryTest {

    @Parameter
    String database;                                   // field injection

    Repository repository;

    @BeforeEach
    void connect() {
        repository = Repository.connect(database);
    }

    @Test
    void savesAndLoads() {
        repository.save(new Item("pen"));
        assertEquals(1, repository.count());
    }
}

@ParameterizedClass
@CsvSource({ "apple, 23", "banana, 42" })
record FruitTest(String fruit, int quantity) {         // constructor injection (also plain constructors)
    @Test
    void hasQuantity() {
        assertTrue(quantity > 0, fruit);
    }
}
```

`@Parameter(0)`, `@Parameter(1)` for several fields. `@BeforeParameterizedClassInvocation` / `@AfterParameterizedClassInvocation` (static unless `PER_CLASS`) run around each class invocation and can receive the arguments. `@Nested` classes run for each invocation too. Parameterized classes are marked experimental.

## Conversion

- **Implicit** from String: numbers (`"0xF"`, `"1_000"`), booleans, chars, enums by name, `Class`, `File`, `Path`, `URI`, `URL`, `Charset`, `Currency`, `Locale` (BCP 47 such as `"en-US"` since JUnit 6), `UUID`, `java.time` types (`"2026-01-31"`, `"PT5S"`).
- **Fallback:** a type with a single `String` or `CharSequence` factory method or constructor (`Money.of(String)`).
- **Explicit:** `@ConvertWith(MyConverter.class)` with `SimpleArgumentConverter` or `TypedArgumentConverter<S, T>`; `@JavaTimeConversionPattern("dd.MM.yyyy") LocalDate date`.
- Widening (`int` to `long`) works.

## Aggregation

```java
@ParameterizedTest
@CsvSource({ "Jane, Doe, 1990-05-20", "John, Roe, 1985-01-02" })
void people(ArgumentsAccessor row) {
    Person p = new Person(row.getString(0), row.getString(1), row.get(2, LocalDate.class));
    assertTrue(p.age() > 18);
}

@ParameterizedTest
@CsvSource({ "Jane, Doe, 1990-05-20" })
void aggregated(@AggregateWith(PersonAggregator.class) Person person) { }

static class PersonAggregator implements ArgumentsAggregator {
    @Override
    public Person aggregateArguments(ArgumentsAccessor a, ParameterContext context) {
        return new Person(a.getString(0), a.getString(1), a.get(2, LocalDate.class));
    }
}
```

## Display names

Default: `[{index}] {argumentSetNameOrArgumentsWithNames}`, e.g. `[1] a = 2, b = 3, expected = 6` when compiled with `-parameters` (Java) or `-java-parameters` (Kotlin), otherwise `arg0 = ...`. Since JUnit 6 text arguments are shown quoted (`"abc"`, `'c'`), turn off with `quoteTextArguments = false`.

| Placeholder | Meaning |
|---|---|
| `{displayName}` | The method's display name |
| `{index}` | 1-based invocation number |
| `{arguments}` / `{argumentsWithNames}` | All arguments, without / with names |
| `{argumentSetName}` / `{argumentSetNameOrArgumentsWithNames}` | Name from `argumentSet(...)` |
| `{0}`, `{1}` | One argument (`MessageFormat`, so `''` for a literal quote) |

Project default: `junit.jupiter.params.displayname.default = {index}` in `junit-platform.properties`; argument text is cut at `junit.jupiter.params.displayname.argument.maxlength` (512).

## Strictness and cleanup

- Extra CSV columns are ignored by default; `@ParameterizedTest(argumentCountValidation = ArgumentCountValidationMode.STRICT)` or `junit.jupiter.params.argumentCountValidation = strict` makes them an error.
- Arguments that are `AutoCloseable` are closed after each invocation (`autoCloseArguments = false` to keep them).
- JUnit 6 parses CSV with FastCSV: characters after a closing quote (`'a'b`) are now an error, and `@CsvFileSource(lineSeparator = ...)` is gone.
