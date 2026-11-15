# Sources

Checked against the official pages on 2026-11-15 (Gradle 9.9.1 docs, AGP 9.5.x). Re-read the page before advising on any version number; `url-to-skill` can refresh a page into notes.

| Topic | Official page |
|---|---|
| JDK / Kotlin / AGP vs Gradle | https://docs.gradle.org/current/userguide/compatibility.html |
| AGP release notes, min Gradle / JDK / Build Tools | https://developer.android.com/build/releases/gradle-plugin |
| Version catalogs | https://docs.gradle.org/current/userguide/version_catalogs.html |
| Troubleshooting builds | https://docs.gradle.org/current/userguide/troubleshooting.html |
| Inspecting dependencies | https://docs.gradle.org/current/userguide/viewing_debugging_dependencies.html |
| Wrapper | https://docs.gradle.org/current/userguide/gradle_wrapper.html |
| Performance settings | https://docs.gradle.org/current/userguide/performance.html |
| Android dependencies and configurations | https://developer.android.com/build/dependencies |
| Android tests from the command line | https://developer.android.com/studio/test/command-line |
| Gradle Managed Devices | https://developer.android.com/studio/test/gradle-managed-devices |
| Java versions in Android builds | https://developer.android.com/build/jdks |
| Studio configuration, proxy, antivirus | https://developer.android.com/studio/intro/studio-config |
| Dependency verification | https://developer.android.com/build/dependency-verification |
| Migrate to version catalogs / KSP | https://developer.android.com/build/migrate-to-catalogs , https://developer.android.com/build/migrate-to-ksp |

Data in `scripts/gradle_doctor.py` and the tables here: the AGP 9.5 row (Gradle 9.6.0, JDK 17, Build Tools 36.0.0) and the Java and Kotlin tables were read from the pages above. Older AGP rows follow the AGP release-notes history and were not re-read in this pass: confirm them on the release page before relying on one.

The Gradle compatibility page does not publish an AGP-to-Gradle table; it only says which AGP range Gradle is tested with (9.0 up to 9.5.0-alpha at the time of checking). Use the Android page for AGP minimums.
