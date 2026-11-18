# Failure causes detected by junit_report.py

The script checks the exception type, message and stack in this order and reports the first cause that matches.

| Id | Matches | What happened | Fix |
|---|---|---|---|
| `version-mismatch` | `NoSuchMethodError` / `NoClassDefFoundError` / `ClassNotFoundException` / `AbstractMethodError` in `org.junit` or `opentest4j`; `OutputDirectoryProvider not available`; `TestEngine with ID ... failed to discover tests` | JUnit jars of different versions on the test class path (Platform 1.x next to Jupiter 6, an IDE's launcher, a library pulling an old engine) | Import `org.junit:junit-bom:6.1.3`, remove other JUnit versions, add `junit-platform-launcher` (Gradle), Surefire 3.5.5+ (Maven); check `./gradlew dependencies --configuration testRuntimeClasspath` or `mvn dependency:tree -Dincludes=org.junit*` |
| `lifecycle-config` | `@BeforeAll method ... must be static`, `must not be private`, `must not return a value` | A method breaks JUnit's rules | Static (Kotlin companion + `@JvmStatic`) or `@TestInstance(PER_CLASS)`; non-private, `void` |
| `parameter-resolution` | `ParameterResolutionException`, `No ParameterResolver registered` | A parameter nothing can supply | Add the extension (`@ExtendWith(MockitoExtension.class)`, Spring), turn the method into a `@ParameterizedTest` with a source, or remove the parameter |
| `parameterized-config` | `You must configure at least one set of arguments`, `ArgumentConversionException`, `Failed to convert`, `PreconditionViolationException` | Source and parameters do not fit | Check value types, column counts and quoting; `argumentCountValidation = STRICT` catches extra columns |
| `mockito` | `UnnecessaryStubbingException`, `WantedButNotInvoked`, `PotentialStubbingProblem`, `TooManyActualInvocations`, `ArgumentsAreDifferent`, `InvalidUseOfMatchersException`, `MockitoException` | A strict-stubbing or verification check | Remove unused `when(...)`, check the expected call's arguments, don't mix raw values and matchers; on Java 21+ configure Mockito's agent for inline mocks |
| `spring-context` | `Failed to load ApplicationContext`, `BeanCreationException`, `NoSuchBeanDefinitionException` | The Spring test context did not start | Fix the first `Caused by`; use a slice test (`@WebMvcTest`, `@DataJpaTest`) or `@MockitoBean` for missing beans |
| `timeout` | `TimeoutException`, `timed out after`, `execution exceeded timeout` | `@Timeout` or `assertTimeout` exceeded | Find the slow step; wait for conditions instead of sleeping; raise the limit only if the work is really slow |
| `multiple-failures` | `MultipleFailuresError` | Several `assertAll` checks failed | Fix each listed failure |
| `assertion` | `AssertionFailedError`, `AssertionError`, `ComparisonFailure`, `expected: <...> but was: <...>` | The result differs from the expectation | Compare expected and actual (the summary extracts both); decide whether the code or the test is wrong |
| `null-pointer` | `NullPointerException` | Something was never initialised | JUnit 4 `@Before` in a Jupiter class never runs; mocks need `MockitoExtension` or `MockitoAnnotations.openMocks(this)`; `@BeforeEach` must assign the field; Kotlin `lateinit` not set |
| `resource` | `OutOfMemoryError`, `StackOverflowError`, `Too many open files` | The test JVM ran out of something | Look for recursion and leaks (`@AutoClose`, try-with-resources); raise `maxHeapSize` (Gradle) or `argLine=-Xmx1g` (Surefire) |
| `exception` | anything else | An unexpected exception | Read the message and the first frame in your code |

Statuses: `failed` is an assertion failure, `error` an unexpected exception (legacy XML `<error>`, Open Test Reporting `ERRORED` or a non-assertion throwable). Aborted tests (assumptions) are reported as skipped with the reason.

## Flaky tests: checklist

1. Confirm it is flaky: rerun the single test 10 to 20 times (`for i in $(seq 20); do ./gradlew test --tests X --rerun || break; done`, or `@RepeatedTest(20)` temporarily).
2. **Order and shared state:** does it pass alone and fail in the suite? Look for static fields, singletons, caches, system properties, `Locale`/time zone changes, files in fixed paths. Use `@TempDir`, `@DefaultLocale`, `@SetSystemProperty`, fresh instances in `@BeforeEach`; try `MethodOrderer.Random` to expose order dependence.
3. **Time:** `Instant.now()`, `LocalDate.now()`, time-zone or DST boundaries, `Thread.sleep`. Inject a `Clock`; wait for conditions.
4. **Concurrency:** parallel execution sharing a resource (`@ResourceLock`, `@Isolated`), async code asserted too early (Awaitility), thread pools not shut down.
5. **Environment:** network, ports (use port 0 / dynamic ports), containers starting slowly, CI machines with fewer cores or different file systems and line endings.
6. **Randomness:** seed it and log the seed.
7. Fix the cause; quarantining with `@Tag("flaky")` (excluded from the main build) is a temporary measure with a ticket, not a fix.
