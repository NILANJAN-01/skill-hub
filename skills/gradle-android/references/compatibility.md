# Version compatibility

Source: [sources.md](sources.md). Four versions must agree: **JDK running Gradle**, **Gradle**, **AGP**, **Kotlin plugin**. `gradle_doctor.py check` tests these.

## JDK to minimum Gradle (Gradle can run on this JDK)

| JDK | Gradle | JDK | Gradle |
|---|---|---|---|
| 8 | 2.0 | 21 | 8.5 |
| 11 | 5.0 | 22 | 8.8 |
| 16 | 7.0 | 23 | 8.10 |
| 17 | 7.3 | 24 | 8.14 |
| 19 | 7.6 | 25 | 9.1.0 |
| 20 | 8.3 | 26 / 27 | 9.4.0 / 9.8.0 |

Gradle 9.9.1 does not support JVM 28 or later.

## AGP to Gradle, JDK, Build Tools

| AGP | Min Gradle | JDK | Build Tools |
|---|---|---|---|
| 9.5 | 9.6.0 (default 9.6.0) | 17 | 36.0.0 (verified) |
| 9.0 | 9.1.0 | 17 | see release page |
| 8.13 / 8.12 / 8.11 | 8.13 | 17 | see release page |
| 8.10 / 8.9 | 8.11.1 | 17 | see release page |
| 8.8 | 8.10.2 | 17 | see release page |
| 8.7 | 8.9 | 17 | see release page |
| 8.6 / 8.5 | 8.7 | 17 | see release page |
| 8.4 | 8.6 | 17 | see release page |
| 8.3 | 8.4 | 17 | see release page |
| 8.2 | 8.2 | 17 | see release page |

Only the 9.5 row was re-read on the date in sources.md. Confirm other rows on the AGP release page. AGP 9.5 supports up to API level 37.

## Kotlin plugin to minimum Gradle

| Kotlin | Gradle | Kotlin | Gradle |
|---|---|---|---|
| 1.8.10 | 8.0 | 2.2.0 | 9.0.0 |
| 1.9.0 | 8.3 | 2.3.0 | 9.4.0 |
| 1.9.20 | 8.5 | 2.4.0 | 9.7.0 |
| 2.0.21 | 8.12 | 2.4.21 | 9.9.0 |

(Gradle's embedded Kotlin table; it is a floor for the Gradle side, the Kotlin Gradle plugin and Compose compiler have their own pairing rules on kotlinlang.org.)

## Upgrade order (one step at a time, build between steps)

1. Commit or stash. Run `./gradlew assembleDebug testDebugUnitTest` to get a green baseline.
2. JDK first if needed (17+), set `JAVA_HOME` and the IDE's Gradle JDK.
3. Gradle: `./gradlew wrapper --gradle-version X.Y.Z`, run it again to refresh scripts and jar, `./gradlew --version`. Since Gradle 9 the properties file needs full `X.Y.Z`.
4. AGP, then Kotlin, then libraries. Read the release notes' breaking changes (for AGP 9 check built-in Kotlin and DSL changes).
5. `./gradlew build --warning-mode all` and fix deprecations before the next major.
6. If `distributionSha256Sum` is set, the wrapper task fails unless you pass the new sum: add the published checksum for the new release.
