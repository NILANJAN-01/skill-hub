# Diagnosing Gradle failures

Source: [sources.md](sources.md). Start with `python skills/gradle-android/scripts/gradle_doctor.py diagnose build.log`.

## Method

1. Re-run with `--stacktrace` (`-s`) and save the log. The first `* What went wrong:` block is the cause; later errors are usually fallout.
2. `./gradlew help`: fails = configuration problem (build scripts, plugins, settings); passes = a task problem.
3. More detail: `--info`; `--debug` is huge and may expose secrets. Why a task re-ran: `--info` or `--console=verbose`.
4. `--scan` publishes a Build Scan to scans.gradle.com; anyone with the link can see the console log and environment, so ask the user first.
5. Deprecations: `--warning-mode all`.
6. Daemon trouble before any task runs: read `~/.gradle/daemon/<version>/daemon-<pid>.out.log`; a NAT/VPN that masquerades local connections can make Gradle refuse its own daemon. `./gradlew --stop` clears stale daemons.
7. Persistent stack traces: `org.gradle.logging.stacktrace=all` in `gradle.properties`.

## Dependency problems

```bash
./gradlew :app:dependencies --configuration debugRuntimeClasspath
./gradlew :app:dependencyInsight --dependency okhttp --configuration debugRuntimeClasspath
./gradlew :app:buildEnvironment          # plugin classpath
./gradlew build --refresh-dependencies   # re-download metadata
```

Output markers: `(*)` repeated subtree, `(c)` constraint, `(n)` not resolvable, `a:b:1.6 -> 1.7` conflict where 1.7 won. In `dependencyInsight` read *Selection reasons* (conflict resolution, constraint, ancestor/strictly, forced, rule, rejection).

Fixes, in order: declare the wanted version directly; add a constraint or a BOM/platform; `strictly` only when you must; `exclude(group, module)` for duplicate classes.

## Catalogue (what `diagnose` knows)

| Failure | Typical cause | Fix |
|---|---|---|
| Unsupported class file major version N / Java not supported | JDK vs Gradle/AGP/Kotlin | Use JDK 17, or Gradle that supports the JDK ([compatibility.md](compatibility.md)) |
| Minimum supported Gradle version is X | Wrapper older than AGP needs | Bump wrapper |
| SDK location not found | No `sdk.dir` / `ANDROID_HOME` | `fix --sdk-dir` |
| Failed to install SDK packages / licenses | Licenses not accepted | `sdkmanager --licenses` |
| Could not resolve / Could not find group:name:version | Typo, missing repo, offline, proxy | Check coordinates, repos, `--refresh-dependencies` |
| Duplicate class X found in modules | Two artifacts ship the class | `dependencies`, then exclude or align versions |
| Manifest merger failed | minSdk or attribute conflict | Raise minSdk, `tools:replace`, `tools:overrideLibrary` |
| android:exported needs to be explicitly specified | targetSdk 31+ | Set `android:exported` |
| OutOfMemoryError / Metaspace | Heap too small | `org.gradle.jvmargs`, `kotlin.daemon.jvmargs`, `--stop` |
| Dex / R8 errors | Missing keep or dontwarn rule, too many methods | Use `missing_rules.txt`, multidex, desugaring |
| Plugin not found | Missing plugin repository or wrong id | `pluginManagement` repositories |
| Version catalog accessor unresolved | Alias typo, wrong file name or location | `gradle/libs.versions.toml`; `retrofit-core` is `libs.retrofit.core` |
| Network, proxy, TLS | VPN, firewall, intercepting proxy | Proxy properties in `~/.gradle`, CA into `cacerts` |
| Daemon or lock errors | Stale daemon, other Gradle running | `./gradlew --stop`, close other Gradle runs |
| Duplicate files while packaging | META-INF clashes | `packaging { resources { excludes += ... } }` |
| Unit tests failed | Real test failure | Open the HTML report, rerun one test |
| INSTALL_FAILED_* / no devices | Emulator or install conflict | `adb devices`, uninstall the old app |
| Lint failure | Lint errors fail the build | Fix, or use a baseline |

## Clean-ups, in order of risk

1. `./gradlew --stop`
2. `./gradlew clean` (deletes `build/` only)
3. `--refresh-dependencies`
4. Invalidate IDE caches
5. Delete `.gradle/` in the project (agree with the user first)
6. Delete `~/.gradle/caches` (slow re-download; agree first, and stop all Gradle processes)
