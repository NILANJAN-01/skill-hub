# Adding and managing libraries

Source: [sources.md](sources.md).

## Version catalog (`gradle/libs.versions.toml`)

Gradle imports `gradle/libs.versions.toml` as `libs` automatically.

```toml
[versions]
agp = "9.5.1"
retrofit = "2.11.0"

[libraries]
retrofit = { group = "com.squareup.retrofit2", name = "retrofit", version.ref = "retrofit" }
androidx-core-ktx = { module = "androidx.core:core-ktx", version = "1.13.1" }

[bundles]
networking = ["retrofit"]

[plugins]
android-application = { id = "com.android.application", version.ref = "agp" }
```

Use: `implementation(libs.retrofit)`, `implementation(libs.bundles.networking)`, `alias(libs.plugins.android.application)`. Dashes and underscores become dots (`androidx-core-ktx` is `libs.androidx.core.ktx`). Plugin aliases cannot be used in `settings` files. Version references are `libs.versions.retrofit.get()`. Rich versions (`strictly`, `prefer`, `reject`) work for libraries; they are deprecated for plugins.

`gradle_doctor.py add-lib` writes a `[versions]` key and a `[libraries]` entry with the alias as the key, then the dependency line in the module. Edit the file by hand for bundles or shared version keys.

Without a catalog: `implementation("group:name:1.2.3")` and `implementation(project(":lib"))`.

## Which configuration

| Configuration | Use for |
|---|---|
| `implementation` | Default. Not exposed to modules that depend on yours (faster builds) |
| `api` | Library modules whose public API exposes the dependency's types |
| `compileOnly` | Needed to compile, not at runtime (not for AARs) |
| `runtimeOnly` | Needed at runtime only (for example a logging backend) |
| `ksp` / `kapt` / `annotationProcessor` | Annotation processors: `ksp` if the library supports it, `kapt` for Kotlin otherwise, `annotationProcessor` for Java-only |
| `testImplementation` | Local JVM unit tests (JUnit, MockK, Mockito, Robolectric) |
| `androidTestImplementation` | Instrumented tests (AndroidX Test, Espresso) |
| `debugImplementation` | Debug builds only (LeakCanary, Compose UI tooling) |
| `lintChecks` / `lintPublish` | Lint rules to run / to publish inside an AAR |
| `freeImplementation` etc. | Per flavor or variant (a flavor+type pair needs the configuration created first) |

Annotation processors on the compile classpath turn off compile avoidance and AGP reports an error: use the processor configurations.

## Rules

- Exact versions only. Dynamic versions (`1.+`, `latest.release`) cause surprise updates and slow builds.
- Get coordinates from the library's official page, Maven Central or Google Maven, not from memory. Use the library's BOM when one exists (for example the Compose BOM): `implementation(platform(libs.compose.bom))`, then add members without versions.
- Repositories: `google()` and `mavenCentral()` (JCenter is shut down).
- Enable dependency verification when supply-chain safety matters (see the Android page in sources).
- After adding: sync, run `./gradlew :app:dependencies --configuration debugRuntimeClasspath`, then build and run the tests.
- Check the Play SDK Index warnings Android Studio shows for outdated or vulnerable SDKs.

## Conflicts and duplicates

`dependencyInsight` first ([diagnosis.md](diagnosis.md)). Then: declare the version you want; constraints block:

```kotlin
dependencies {
    constraints {
        implementation("com.squareup.okhttp3:okhttp:4.12.0") { because("align transitive versions") }
    }
    implementation(libs.retrofit) { exclude(group = "com.squareup.okio", module = "okio-jvm") }
}
```
