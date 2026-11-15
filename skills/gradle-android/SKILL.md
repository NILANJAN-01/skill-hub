---
name: gradle-android
description: "Set up Gradle for Android apps and fix Gradle problems: wrapper, JDK, Android Gradle Plugin (AGP) and Kotlin compatibility, SDK path, version catalogs, adding libraries, running unit and instrumented tests, and diagnosing build failures with a bundled script. Use when a Gradle or Android build fails or will not sync, the user asks how to set up, upgrade or speed up Gradle, add a dependency, or run Android tests."
license: Complete terms in the repository README
compatibility: Needs Python 3.8+ (standard library only) for the scripts. Running builds needs a JDK 17+ and the Android SDK; the project's own Gradle wrapper is used.
metadata:
  title: "Gradle for Android: setup, diagnosis, libraries and testing"
  category: gradle-tools
---

# Gradle for Android

`scripts/gradle_doctor.py` checks a project, explains failure logs, applies safe fixes, adds libraries and runs tests. Facts come from the official Gradle and Android docs (see [references/sources.md](references/sources.md)). Never trust version numbers from memory: Gradle, AGP and Kotlin move fast, so verify against the sources before recommending an upgrade.

| Command | What it does |
|---|---|
| `check [--project DIR]` | Finds setup problems: JDK, wrapper files, Gradle vs JDK vs AGP vs Kotlin versions, SDK path, `gradle.properties`, dynamic versions, `jcenter()`, removed `compile` configurations. Exit 1 on errors |
| `diagnose LOG` | Matches a build log (file or `-` for stdin) against ~20 known failures and prints evidence, cause and fix |
| `fix [--apply] [--gradle-version X] [--sdk-dir P]` | Dry run by default. Adds recommended `gradle.properties` keys, bumps the wrapper version, writes `sdk.dir`, ignores `local.properties` |
| `add-lib --coordinates G:A:V --alias a-b [--module app] [--config implementation] [--apply]` | Adds the library to `gradle/libs.versions.toml` and the module's build file (Kotlin or Groovy DSL) |
| `test [--module app] [--variant debug] [--class C] [--method m] [--instrumented] [--dry-run]` | Builds and runs the right Gradle test task, then prints the report folders |

Run it as `python skills/gradle-android/scripts/gradle_doctor.py <command>` (use the path where the skill is installed). Every file it edits is first copied to `<file>.bak`.

## When to use

- "Gradle sync failed", "build fails", a pasted Gradle error, "Unsupported class file major version", "SDK location not found", "Could not resolve …", "Duplicate class …", "Manifest merger failed", OutOfMemoryError in a build.
- "Set up Gradle for my Android project", "upgrade Gradle or AGP", "which Gradle does AGP X need", "which JDK".
- "Add library X", "migrate to a version catalog", "why is this dependency version chosen".
- "Run the unit tests / one test / the instrumented tests", "where is the test report".
- "Make the build faster".

## When NOT to use

- Writing the test code itself for Kotlin: use `kotlin-unit-test`. Crashes of a running app: use `android-logcat-analyzer`. Gradle in a GitLab pipeline: use `gitlab-ci-debugging`.

## Safety rules for the agent

- Start read-only: run `check` and `diagnose` first. Run `fix` and `add-lib` without `--apply`, show the plan, and apply only after the user agrees.
- Do not delete `~/.gradle`, `.gradle/` or `build/` folders, and do not remove lock files, unless the user agrees and no Gradle process is running. Prefer `./gradlew --stop`.
- Never put proxy passwords, keystore passwords or tokens in the project's `gradle.properties`; use `~/.gradle/gradle.properties`.
- Never use `+` or `latest` versions. Look up the exact current version on the library's official page (Maven Central, Google Maven) and state where it came from.
- Do not upgrade Gradle, AGP, Kotlin or the JDK together in one step; change one, build, then the next. Use the compatibility tables in [references/compatibility.md](references/compatibility.md).
- Use the project's wrapper (`./gradlew`, `gradlew.bat` on Windows), not a system Gradle.

## Procedures

1. **Diagnose a failing build.**
   ```bash
   ./gradlew assembleDebug --stacktrace > build.log 2>&1
   python skills/gradle-android/scripts/gradle_doctor.py diagnose build.log
   python skills/gradle-android/scripts/gradle_doctor.py check
   ```
   Read the first `What went wrong:` block, not the last error. If nothing matches, run `./gradlew help`: if it fails the problem is in configuration, otherwise in a task. Then use `--info`, `--scan` (check what a build scan publishes first) or `--warning-mode all`. See [references/diagnosis.md](references/diagnosis.md).
2. **Set up a project.** Run `check`, then `fix` (dry run), then `fix --apply`. Use JDK 17+, a wrapper that matches the AGP, a valid SDK path and a version catalog. Steps: [references/setup.md](references/setup.md).
3. **Add a library.** Find the exact coordinates and version in the library's official docs, then:
   ```bash
   python skills/gradle-android/scripts/gradle_doctor.py add-lib --coordinates com.squareup.retrofit2:retrofit:2.11.0 --alias retrofit
   python skills/gradle-android/scripts/gradle_doctor.py add-lib --coordinates ... --alias retrofit --apply
   ./gradlew :app:dependencies --configuration debugRuntimeClasspath
   ```
   Choose the configuration (`implementation`, `api`, `ksp`, `testImplementation`, `androidTestImplementation`, `debugImplementation`) with [references/dependencies.md](references/dependencies.md). For conflicts use `dependencyInsight`.
4. **Run tests.** Local unit tests need no device; instrumented tests need a device, emulator or Gradle Managed Device.
   ```bash
   python skills/gradle-android/scripts/gradle_doctor.py test --class com.example.CartTest --method totalIsSummed
   python skills/gradle-android/scripts/gradle_doctor.py test --instrumented --class com.example.LoginUiTest
   ```
   Report folders and the adb alternative: [references/android-testing.md](references/android-testing.md).
5. **Finish.** Re-run `./gradlew assembleDebug` and the tests; report what failed before, what changed (files and `.bak` copies) and what is verified.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Unsupported class file major version 65` / Java not supported | JDK and Gradle mismatch: `check`, then use JDK 17 or a Gradle that supports the JDK |
| `Minimum supported Gradle version is X` | `fix --gradle-version X --apply`, then `./gradlew wrapper` twice |
| `SDK location not found` | `fix --sdk-dir <path> --apply` |
| Sync works in the IDE but not on the command line (or the reverse) | The IDE's Gradle JDK differs from `JAVA_HOME`; align both (see setup reference) |
| `diagnose` finds nothing | Re-run with `--stacktrace --info`, paste the first `What went wrong:` block |

## References

- [references/setup.md](references/setup.md): JDK, wrapper, SDK, `gradle.properties`, proxy, speed
- [references/compatibility.md](references/compatibility.md): JDK, Gradle, AGP and Kotlin version tables and how to upgrade safely
- [references/diagnosis.md](references/diagnosis.md): failure catalogue, commands, how to read output
- [references/dependencies.md](references/dependencies.md): version catalogs, configurations, conflicts, BOMs
- [references/android-testing.md](references/android-testing.md): unit and instrumented tests, filters, reports, managed devices
- [references/sources.md](references/sources.md): the official pages this skill is based on and how to refresh it
