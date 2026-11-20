plugins {
    java
    checkstyle
    kotlin("jvm") version "2.1.0"
    id("io.gitlab.arturbosch.detekt") version "1.23.7"
    alias(libs.plugins.ktlint)
}

repositories {
    mavenCentral()
}
