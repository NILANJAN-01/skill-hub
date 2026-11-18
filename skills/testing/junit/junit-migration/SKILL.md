---
name: junit-migration
description: "Migrate Java and Kotlin tests from JUnit 3/4 or JUnit 5 to JUnit 6 (Jupiter) and audit a suite: imports, @Test(expected), rules, runners, Parameterized, categories, message order, removed JUnit 6 APIs, tests that never run (private, static, non-void, static @Nested), weak tests and build setup. A script reports each issue with file, line and fix. Use when the user wants to upgrade or review JUnit tests."
license: Complete terms in the repository README
compatibility: The audit script needs Python 3.8+ (standard library only) and only reads files. Verifying a migration needs JDK 17+ and the project's Gradle or Maven build. Part of the junit-tools bundle with junit-test-authoring and junit-run-reports.
metadata:
  title: "JUnit migration and audit (JUnit 4/5 to 6, Java and Kotlin)"
  category: junit-tools
---

# JUnit migration and audit

Move tests to **JUnit 6.1.3 (Jupiter)** and find tests that are wrong in ways the build does not report. Covers Java and Kotlin.

| From | To | Main changes |
|---|---|---|
| JUnit 3 (`TestCase`) / JUnit 4 (`org.junit.*`) | Jupiter (`org.junit.jupiter.api.*`) | Annotations, assertions (message moves last), rules to extensions, runners to `@ExtendWith`/`@Nested`/`@ParameterizedClass`/`@Suite`, categories to tags |
| JUnit 5.x | JUnit 6.x | Java 17, Kotlin 2.2, one version for all artifacts, Surefire 3, removed APIs (`MethodOrderer.Alphanumeric`, `JUnitPlatform` runner, ...), deprecated Vintage and migrationsupport |

## When to use

- "Migrate our JUnit 4 tests", "upgrade to JUnit 6", "convert `@Rule TemporaryFolder` / `@RunWith(Parameterized.class)`".
- "Why don't these tests run?", "review our test suite", "find tests without assertions".
- The build fails after bumping JUnit (`NoSuchMethodError`, `OutputDirectoryProvider not available`, `MethodOrderer$Alphanumeric` not found).

## When NOT to use

- Writing new tests: `junit-test-authoring`. Explaining a failing run: `junit-run-reports`.
- TestNG, Spock or Kotest migrations, or Android instrumented tests (`uiautomator-migration` covers UI Automator).

## Procedure

`scripts/junit_audit.py` is in this skill's folder and only reads files.

1. **Audit.**
   ```bash
   python scripts/junit_audit.py <project-dir>              # errors first, with file:line, code and fix
   python scripts/junit_audit.py <project-dir> --json
   python scripts/junit_audit.py <project-dir> --strict     # warnings fail too (CI gate)
   python scripts/junit_audit.py --rules                    # every rule
   python scripts/junit_audit.py <dir> --only junit4-import junit4-expected
   ```
   It reads `.java`/`.kt` test sources, `junit-platform.properties`, Gradle files, the version catalog and `pom.xml`, and prints the JUnit 3/4 vs Jupiter mix, the JUnit dependencies with versions, and findings.
2. **Fix the build first** (ERRORs such as `junit4-not-run`, `no-use-junit-platform`, `no-engine`, `platform-version-mix`, `surefire-too-old`, `java-too-old`). Use the BOM `org.junit:junit-bom:6.1.3` so every JUnit artifact has one version. To keep old tests running while you migrate, add the deprecated Vintage engine temporarily (`testRuntimeOnly("org.junit.vintage:junit-vintage-engine")` with `junit:junit:4.13.2`).
3. **Fix tests that never run** (`private-method`, `static-test`, `non-void-test`, `beforeall-not-static`, `beforeall-kotlin`, `nested-static`, `nested-not-inner`, `mixed-junit4-jupiter`). They pass silently today, so fixing them can reveal real failures: report those, don't hide them.
4. **Migrate class by class** with [references/junit4-to-jupiter.md](references/junit4-to-jupiter.md) (JUnit 3/4) and [references/junit5-to-6.md](references/junit5-to-6.md) (5 to 6). Change imports, annotations and assertions together; move every message argument from first to last; replace `@Test(expected)`, `ExpectedException`, `TemporaryFolder`, `@RunWith(Parameterized.class)` and `@Category`. Keep each class compiling and green before the next. OpenRewrite recipes (`org.openrewrite.java.testing.junit5.JUnit4to5Migration`) can do the mechanical part; review their diff and still run the audit.
5. **Improve weak tests while there** (`no-assertion`, `message-first`, `sleep`, `disabled-no-reason`, `try-fail-catch`, `assert-true-equals`).
6. **Verify:** run the whole suite and compare the test count with the count before the migration (a drop means tests stopped running). Re-run the audit until there are no ERRORs, then remove the Vintage engine and `junit:junit`.
7. **Report** per file what changed, tests that newly fail, and INFO items left on purpose.

## Rule groups

| Level | Examples |
|---|---|
| ERROR | Never runs or does not compile on JUnit 6: `junit4-not-run`, `mixed-junit4-jupiter`, `private-method`, `static-test`, `non-void-test`, `beforeall-not-static`, `nested-static`, `nested-not-inner`, `removed-alphanumeric`, `removed-platform-runner`, `removed-config`, `no-engine`, `no-params`, `no-use-junit-platform`, `platform-version-mix`, `junit-version-mix`, `surefire-too-old`, `java-too-old` |
| WARN | Migrate or fix: `junit4-import`, `junit4-expected`, `junit4-timeout`, `junit3-testcase`, `message-first`, `deprecated-jre-constant`, `deprecated-jre-other`, `deprecated-migrationsupport`, `vintage-engine`, `no-launcher`, `kotlin-too-old`, `no-assertion`, `sleep`, `disabled-no-reason` |
| INFO | Worth a look: `junit5-version`, `try-fail-catch`, `assert-true-equals`, `assert-true-null`, `assert-equals-boolean`, `wall-clock`, `random`, `print`, `java-target-old`, `surefire-unpinned` |

The audit reads source text, not compiled code: it can miss unusual formatting and can flag a helper method that asserts indirectly. Confirm each ERROR before changing code.

## Safety rules

- The audit never edits files. Change code with the user's agreement, in small commits, under version control.
- A migrated test must check the same things. Never drop an assertion, expected exception or timeout during the rewrite; if a JUnit 4 rule had behaviour Jupiter lacks, say so.
- Tests that start running after a fix (they were silently skipped) may fail: report them with the reason instead of disabling them.

## Troubleshooting

| Problem | Fix |
|---|---|
| Fewer tests after migration | JUnit 4 classes without Vintage, a static/`private` method, or a `@Nested` class that is static / not `inner` |
| `assertEquals("msg", expected, actual)` now fails or compares the wrong thing | Jupiter takes the message **last**: `assertEquals(expected, actual, "msg")` |
| `@Before` method does not run in a Jupiter class | Use `@BeforeEach`; JUnit 4 annotations are ignored by the Jupiter engine |
| `MockitoJUnitRunner` / `SpringRunner` | `@ExtendWith(MockitoExtension.class)` (`mockito-junit-jupiter`) / `@ExtendWith(SpringExtension.class)` or `@SpringBootTest` |
| `NoSuchMethodError` in `org.junit.platform...` after upgrading | A JUnit 5 Platform jar (1.x) is still on the path: remove its explicit version, use the BOM |
| Surefire runs no tests after moving to JUnit 6 | Surefire 2.x: upgrade to 3.5.5+ |

## References

- [references/junit4-to-jupiter.md](references/junit4-to-jupiter.md): JUnit 3/4 to Jupiter mapping with before/after Java and Kotlin code, rules, runners, Parameterized, suites, categories.
- [references/junit5-to-6.md](references/junit5-to-6.md): everything that changed from JUnit 5 to 6 and how to update.
