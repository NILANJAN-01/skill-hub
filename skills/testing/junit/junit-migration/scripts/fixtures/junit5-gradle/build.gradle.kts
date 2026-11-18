plugins {
    java
    id("org.jetbrains.kotlin.jvm") version "2.0.21"
}

java {
    toolchain {
        languageVersion.set(JavaLanguageVersion.of(17))
    }
}

dependencies {
    testImplementation("org.junit.jupiter:junit-jupiter-api:6.1.3")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher:1.10.2")
    testRuntimeOnly("org.junit.jupiter:junit-jupiter-engine:6.1.3")
    testImplementation("org.junit.jupiter:junit-jupiter-migrationsupport:6.1.3")
}

tasks.test {
    useJUnitPlatform()
    systemProperty("junit.jupiter.tempdir.scope", "per_context")
}
