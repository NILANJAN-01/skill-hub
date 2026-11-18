# Extensions, configuration, parallel execution and suites

## Registering extensions

```java
@ExtendWith(MockitoExtension.class)                    // declarative: class, method, field or parameter
class OrderServiceTest {

    @RegisterExtension                                 // programmatic: configured instance
    static WireMockExtension api = WireMockExtension.newInstance().options(wireMockConfig().dynamicPort()).build();

    @Mock PaymentGateway gateway;
    @InjectMocks OrderService service;
}
```

- `@ExtendWith` is inherited and repeatable; order follows declaration order.
- A `static` `@RegisterExtension` field can do class-level work (`BeforeAllCallback`); an instance field only method-level work.
- Global registration: list the class in `META-INF/services/org.junit.jupiter.api.extension.Extension` and set `junit.jupiter.extensions.autodetection.enabled = true` (narrow with `...autodetection.include` / `...exclude`).
- Common ones: Mockito `MockitoExtension` (`mockito-junit-jupiter`), Spring `SpringExtension` (included in `@SpringBootTest`), Testcontainers `@Testcontainers`, WireMock `WireMockExtension`.

## Writing an extension

Extension points (`org.junit.jupiter.api.extension`): `BeforeAllCallback`, `BeforeEachCallback`, `BeforeTestExecutionCallback`, `AfterTestExecutionCallback`, `AfterEachCallback`, `AfterAllCallback`, `ParameterResolver`, `ExecutionCondition`, `TestInstancePostProcessor`, `TestInstanceFactory`, `TestInstancePreDestroyCallback`, `TestExecutionExceptionHandler`, `LifecycleMethodExecutionExceptionHandler`, `TestWatcher`, `InvocationInterceptor`, `TestTemplateInvocationContextProvider`, `PreInterruptCallback`.

```java
public class TimingExtension implements BeforeTestExecutionCallback, AfterTestExecutionCallback {

    private static final ExtensionContext.Namespace NS = ExtensionContext.Namespace.create(TimingExtension.class);

    @Override
    public void beforeTestExecution(ExtensionContext context) {
        context.getStore(NS).put(context.getRequiredTestMethod(), System.nanoTime());
    }

    @Override
    public void afterTestExecution(ExtensionContext context) {
        long start = context.getStore(NS).remove(context.getRequiredTestMethod(), long.class);
        context.publishReportEntry("ms", String.valueOf((System.nanoTime() - start) / 1_000_000));
    }
}

public class FixedClockResolver implements ParameterResolver {
    @Override
    public boolean supportsParameter(ParameterContext p, ExtensionContext c) {
        return p.getParameter().getType() == Clock.class;
    }

    @Override
    public Object resolveParameter(ParameterContext p, ExtensionContext c) {
        return Clock.fixed(Instant.parse("2026-01-01T00:00:00Z"), ZoneOffset.UTC);
    }
}
```

- Keep state in `ExtensionContext.Store` with your own `Namespace`, never in extension fields (one extension instance can serve parallel tests). In JUnit 6 use `store.computeIfAbsent(key, k -> create(), Type.class)`; `getOrComputeIfAbsent` is deprecated.
- Values in the store that implement `AutoCloseable` are closed when their context ends (`junit.jupiter.extensions.store.close.autocloseable.enabled`).
- `InvocationInterceptor.interceptDynamicTest(Invocation, ExtensionContext)` was removed in JUnit 6: override the variant that also takes a `DynamicTestInvocationContext`.
- Test an extension with the JUnit Platform Test Kit (`org.junit.platform:junit-platform-testkit`, `EngineTestKit.engine("junit-jupiter").selectors(selectClass(X.class)).execute()`).

## Configuration parameters

Put them in `src/test/resources/junit-platform.properties`, or pass them from the build (Gradle `systemProperty(...)` in `tasks.test`, Maven Surefire `<configurationParameters>`, ConsoleLauncher `--config key=value`). Build/launcher values win over system properties, which win over the properties file. The constants are in `org.junit.jupiter.api.Constants` (6.1).

| Key | Effect |
|---|---|
| `junit.jupiter.testinstance.lifecycle.default` | `per_method` (default) or `per_class` |
| `junit.jupiter.displayname.generator.default` | Class name of a `DisplayNameGenerator` |
| `junit.jupiter.testmethod.order.default` / `junit.jupiter.testclass.order.default` | Default `MethodOrderer` / `ClassOrderer` |
| `junit.jupiter.execution.order.random.seed` | Seed for `MethodOrderer.Random` |
| `junit.jupiter.execution.timeout.default` (and `...test.method.default`, `...lifecycle.method.default`, ...) | Default timeouts, e.g. `5 s`, `500 ms` |
| `junit.jupiter.execution.timeout.mode` | `enabled`, `disabled`, `disabled_on_debug` |
| `junit.jupiter.tempdir.cleanup.mode.default` / `...factory.default` / `...deletion.strategy.default` | `@TempDir` defaults |
| `junit.jupiter.conditions.deactivate` | Pattern of conditions to ignore (`*` runs `@Disabled` tests too) |
| `junit.jupiter.extensions.autodetection.enabled` | Load extensions through ServiceLoader |
| `junit.jupiter.params.argumentCountValidation` | `strict` / `lenient` / `none` |
| `junit.platform.output.capture.stdout` / `.stderr` | Capture `System.out` / `System.err` into reports |
| `junit.platform.reporting.open.xml.enabled` | Write the Open Test Reporting XML (needs `junit-platform-reporting`) |

An invalid value for an enum-type parameter (for example a typo in `junit.jupiter.testinstance.lifecycle.default`) fails discovery in JUnit 6 instead of being ignored.

## Parallel execution (opt-in)

```properties
junit.jupiter.execution.parallel.enabled = true
junit.jupiter.execution.parallel.mode.default = concurrent           # methods in parallel
junit.jupiter.execution.parallel.mode.classes.default = concurrent   # classes in parallel
junit.jupiter.execution.parallel.config.strategy = dynamic           # or fixed (+ fixed.parallelism = 4) or custom
junit.jupiter.execution.parallel.config.dynamic.factor = 1
```

- `enabled = true` alone still runs everything in one thread until a mode is `concurrent`.
- Per class or method: `@Execution(ExecutionMode.SAME_THREAD)` / `CONCURRENT`. Classes with `PER_CLASS` lifecycle or a `MethodOrderer` run their methods concurrently only with an explicit `@Execution(CONCURRENT)`.
- Shared resources: `@ResourceLock("database")` (`mode = READ` for readers), predefined `Resources.SYSTEM_PROPERTIES`, `SYSTEM_OUT`, `SYSTEM_ERR`, `LOCALE`, `TIME_ZONE`; `@Isolated` runs a class with nothing else in parallel.
- `junit.jupiter.execution.parallel.config.executor-service = worker_thread_pool` (6.1, experimental) avoids extra threads when tests use `ForkJoinPool` or blocking calls; the default is `fork_join_pool`.
- Gradle and Maven can also fork several JVMs (`maxParallelForks`, Surefire `forkCount`); that isolates static state better than threads.

## Suites (junit-platform-suite)

```java
@Suite
@SuiteDisplayName("Smoke tests")
@SelectPackages("com.example.shop")
@IncludeTags("smoke")
class SmokeSuite { }
```

Add `testImplementation("org.junit.platform:junit-platform-suite")` (the BOM supplies the version). Other selectors: `@SelectClasses`, `@SelectMethod`, `@SelectClasspathResource`; filters: `@IncludeClassNamePatterns`, `@ExcludeTags`, `@IncludeEngines`; `@ConfigurationParameter(key = ..., value = ...)` per suite. This replaces JUnit 4's `@RunWith(Suite.class)` and the removed `@RunWith(JUnitPlatform.class)`; `junit-platform-suite-commons` was merged into `junit-platform-suite` in JUnit 6.
