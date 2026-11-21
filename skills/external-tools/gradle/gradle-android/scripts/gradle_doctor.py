#!/usr/bin/env python3
"""Gradle doctor for Android projects: check setup, diagnose failures, apply safe fixes, add libraries, run tests.

Python 3.8+, standard library only. Nothing is changed unless --apply is given
(the `test` command only runs Gradle). Every file it edits is first copied to <file>.bak.

  gradle_doctor.py check    [--project DIR] [--json]
  gradle_doctor.py diagnose LOGFILE|-  [--json]
  gradle_doctor.py fix      [--project DIR] [--apply] [--gradle-version X.Y.Z] [--sdk-dir PATH]
  gradle_doctor.py add-lib  --coordinates G:A:V --alias NAME [--module app] [--config implementation] [--project DIR] [--apply]
  gradle_doctor.py test     [--project DIR] [--module app] [--variant debug] [--class C] [--method m] [--instrumented] [--dry-run]

Exit code: 0 = no errors, 1 = errors found (check/diagnose), 2 = bad usage.
Compatibility data comes from the official docs listed in references/sources.md; see that file to re-verify.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------- compatibility data
# AGP major.minor -> minimum Gradle. 9.5 -> 9.6.0 and JDK 17 were read from
# developer.android.com/build/releases/gradle-plugin; older rows follow the same page's
# history table. Re-verify with references/sources.md before relying on a row.
AGP_MIN_GRADLE = {
    "8.0": "8.0", "8.1": "8.0", "8.2": "8.2", "8.3": "8.4", "8.4": "8.6", "8.5": "8.7",
    "8.6": "8.7", "8.7": "8.9", "8.8": "8.10.2", "8.9": "8.11.1", "8.10": "8.11.1",
    "8.11": "8.13", "8.12": "8.13", "8.13": "8.13", "9.0": "9.1.0", "9.5": "9.6.0",
}
AGP_MIN_JDK = {"8": 17, "9": 17}  # AGP 8.x and 9.x need JDK 17 to run
# Java version -> minimum Gradle that can run on it (docs.gradle.org/current/userguide/compatibility.html)
JAVA_MIN_GRADLE = {8: "2.0", 9: "4.3", 10: "4.7", 11: "5.0", 12: "5.4", 13: "6.0", 14: "6.3", 15: "6.7",
                   16: "7.0", 17: "7.3", 18: "7.5", 19: "7.6", 20: "8.3", 21: "8.5", 22: "8.8",
                   23: "8.10", 24: "8.14", 25: "9.1.0", 26: "9.4.0", 27: "9.8.0"}
# Kotlin Gradle plugin -> minimum Gradle (same page, embedded Kotlin table; used as a floor hint)
KOTLIN_MIN_GRADLE = {"1.8": "8.0", "1.9": "8.3", "2.0": "8.11", "2.1": "8.12", "2.2": "9.0.0",
                     "2.3": "9.4.0", "2.4": "9.7.0"}

RECOMMENDED_PROPS = {
    "org.gradle.jvmargs": "-Xmx2048m -Dfile.encoding=UTF-8",
    "org.gradle.parallel": "true",
    "org.gradle.caching": "true",
    "android.useAndroidX": "true",
}

# ---------------------------------------------------------------- helpers


def vtuple(v):
    """'8.10.2' -> (8, 10, 2); non-numeric tails are ignored ('9.5.0-rc01' -> (9, 5, 0))."""
    out = []
    for p in re.split(r"[.\-]", str(v)):
        m = re.match(r"\d+", p)
        if not m:
            break
        out.append(int(m.group()))
    return tuple(out) or (0,)


def read(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def backup_write(path, text):
    p = Path(path)
    if p.exists():
        shutil.copy2(p, str(p) + ".bak")
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:  # Path.write_text(newline=) needs Python 3.10
        f.write(text)


def parse_props(text):
    props = {}
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "!")) or "=" not in line:
            continue
        k, v = line.split("=", 1)
        props[k.strip()] = v.strip()
    return props


def java_major(text):
    """Major Java version from `java -version` output or a JAVA_VERSION string."""
    m = re.search(r'version "?(\d+)(?:\.(\d+))?', text) or re.search(r"^(\d+)(?:\.(\d+))?", text.strip())
    if not m:
        return None
    major = int(m.group(1))
    return int(m.group(2) or 0) if major == 1 else major


def find_java():
    """(major, source) of the JVM Gradle would use via JAVA_HOME or PATH, or (None, reason)."""
    home = os.environ.get("JAVA_HOME")
    exe = None
    if home:
        cand = Path(home) / "bin" / ("java.exe" if os.name == "nt" else "java")
        if cand.exists():
            exe = str(cand)
        else:
            return None, f"JAVA_HOME={home} has no bin/java"
    exe = exe or shutil.which("java")
    if not exe:
        return None, "no java on PATH and JAVA_HOME is not set"
    try:
        r = subprocess.run([exe, "-version"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as e:
        return None, f"could not run {exe}: {e}"
    return java_major(r.stderr + r.stdout), exe


class Findings:
    def __init__(self):
        self.items = []

    def add(self, level, code, msg, fix=""):
        self.items.append({"level": level, "code": code, "message": msg, "fix": fix})

    @property
    def errors(self):
        return sum(1 for i in self.items if i["level"] == "ERROR")


# ---------------------------------------------------------------- project model


def project_files(root):
    root = Path(root)
    skip = {"build", ".gradle", ".git", ".idea", "node_modules"}
    out = []
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in skip]
        for f in fns:
            if f in ("build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts"):
                out.append(Path(dp) / f)
    return out


def wrapper_version(root):
    text = read(Path(root) / "gradle" / "wrapper" / "gradle-wrapper.properties")
    if text is None:
        return None, None
    props = parse_props(text.replace("\\:", ":"))
    m = re.search(r"gradle-([0-9][^/]*?)-(?:bin|all)\.zip", props.get("distributionUrl", ""))
    return (m.group(1) if m else None), props


def find_agp(root):
    """AGP version from the version catalog or plugin blocks."""
    cat = read(Path(root) / "gradle" / "libs.versions.toml") or ""
    versions = dict(re.findall(r'^\s*([\w.\-]+)\s*=\s*"([^"]+)"', cat.split("[libraries]")[0], re.M))
    for m in re.finditer(r'com\.android\.(?:application|library)"?[^\n]*?version(?:\.ref)?\s*=\s*"([^"]+)"', cat):
        return versions.get(m.group(1), m.group(1))
    for k in ("agp", "androidGradlePlugin", "android-gradle-plugin", "androidGradle"):
        if k in versions:
            return versions[k]
    for f in project_files(root):
        t = read(f) or ""
        m = re.search(r'com\.android\.(?:application|library)["\']\)?\s*version\s*["\']([^"\']+)', t) or \
            re.search(r'com\.android\.tools\.build:gradle:([\d.][^"\')\s]*)', t)
        if m:
            return m.group(1)
    return None


def find_kotlin(root):
    cat = read(Path(root) / "gradle" / "libs.versions.toml") or ""
    m = re.search(r'^\s*kotlin\s*=\s*"([^"]+)"', cat, re.M)
    if m:
        return m.group(1)
    for f in project_files(root):
        m = re.search(r'org\.jetbrains\.kotlin\.[\w.]+["\']\)?\s*version\s*["\']([^"\']+)', read(f) or "")
        if m:
            return m.group(1)
    return None


def agp_key(v):
    t = vtuple(v)
    return f"{t[0]}.{t[1] if len(t) > 1 else 0}"


def min_gradle_for_agp(v):
    """Minimum Gradle for an AGP version: exact row, else the nearest lower known row (marked approximate)."""
    k = agp_key(v)
    if k in AGP_MIN_GRADLE:
        return AGP_MIN_GRADLE[k], True
    lower = [x for x in AGP_MIN_GRADLE if vtuple(x) <= vtuple(k)]
    if lower:
        return AGP_MIN_GRADLE[max(lower, key=vtuple)], False
    return None, False


# ---------------------------------------------------------------- check


def cmd_check(args):
    root = Path(args.project).resolve()
    f = Findings()
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2
    if not any((root / n).exists() for n in ("settings.gradle", "settings.gradle.kts")):
        f.add("ERROR", "no-settings", "No settings.gradle(.kts) here: this is not a Gradle project root.",
              "Run from the project root, or pass --project DIR.")

    # JDK
    major, src = find_java()
    if major is None:
        f.add("ERROR", "no-java", f"Java not usable: {src}.", "Install JDK 17+ and set JAVA_HOME to it.")
    elif major < 17:
        f.add("ERROR", "old-java", f"Java {major} found ({src}); AGP 8.x and 9.x need JDK 17+.",
              "Install JDK 17 (or newer supported one) and set JAVA_HOME, or set org.gradle.java.home in gradle.properties.")

    # wrapper
    gv, wprops = wrapper_version(root)
    if wprops is None:
        f.add("ERROR", "no-wrapper", "gradle/wrapper/gradle-wrapper.properties is missing.",
              "Run `gradle wrapper --gradle-version <X.Y.Z>` once with a Gradle install, then commit gradlew, gradlew.bat and gradle/wrapper/.")
    else:
        if gv is None:
            f.add("ERROR", "wrapper-url", "distributionUrl in gradle-wrapper.properties is unreadable.",
                  "Use https://services.gradle.org/distributions/gradle-X.Y.Z-bin.zip")
        elif not wprops.get("distributionUrl", "").startswith("https://"):
            f.add("WARN", "wrapper-http", "distributionUrl is not https.", "Switch to an https URL.")
        if not (root / "gradle" / "wrapper" / "gradle-wrapper.jar").exists():
            f.add("ERROR", "wrapper-jar", "gradle/wrapper/gradle-wrapper.jar is missing.",
                  "Re-run `./gradlew wrapper` twice (properties first, then scripts+jar) or restore it from git.")
        if "distributionSha256Sum" not in wprops:
            f.add("INFO", "wrapper-sha", "No distributionSha256Sum in the wrapper properties.",
                  "Optional hardening: add the SHA-256 published for your Gradle release.")
    if not (root / "gradlew").exists() or not (root / "gradlew.bat").exists():
        f.add("ERROR", "no-gradlew", "gradlew and/or gradlew.bat missing.", "Regenerate with `gradle wrapper`.")

    # JDK vs Gradle
    if gv and major:
        need = JAVA_MIN_GRADLE.get(major)
        if need and vtuple(gv) < vtuple(need):
            f.add("ERROR", "java-gradle", f"Gradle {gv} cannot run on Java {major} (needs Gradle {need}+).",
                  f"Upgrade the wrapper to Gradle {need}+ or run Gradle on an older JDK.")

    # AGP vs Gradle/JDK
    agp = find_agp(root)
    if agp and gv:
        need, exact = min_gradle_for_agp(agp)
        if need and vtuple(gv) < vtuple(need):
            f.add("ERROR", "agp-gradle",
                  f"AGP {agp} needs Gradle {need}+ ({'documented' if exact else 'nearest documented row'}), wrapper has {gv}.",
                  f"`python gradle_doctor.py fix --gradle-version {need} --apply` or lower the AGP version.")
    if agp and major and vtuple(agp)[0] >= 8 and major < 17:
        f.add("ERROR", "agp-jdk", f"AGP {agp} requires JDK 17+ but Java {major} is in use.", "Use JDK 17+.")
    kot = find_kotlin(root)
    if kot and gv:
        floor = KOTLIN_MIN_GRADLE.get(agp_key(kot))
        if floor and vtuple(gv) < vtuple(floor):
            f.add("WARN", "kotlin-gradle", f"Kotlin {kot} is documented with Gradle {floor}+, wrapper has {gv}.",
                  "Upgrade Gradle or lower the Kotlin plugin version.")

    # gradle.properties
    gp = read(root / "gradle.properties")
    props = parse_props(gp)
    if gp is None:
        f.add("WARN", "no-gradle-properties", "No gradle.properties.", "`fix --apply` creates one with recommended settings.")
    for k, v in RECOMMENDED_PROPS.items():
        if k not in props:
            f.add("WARN" if k == "android.useAndroidX" else "INFO", "prop-missing", f"{k} is not set (recommended: {v}).",
                  "`fix --apply` adds it.")
    m = re.search(r"-Xmx(\d+)([mMgG])", props.get("org.gradle.jvmargs", ""))
    if m and (int(m.group(1)) * (1024 if m.group(2) in "gG" else 1)) < 1024:
        f.add("WARN", "low-heap", f"org.gradle.jvmargs heap is small ({m.group(0)}); large apps hit OutOfMemoryError.",
              "Use -Xmx2048m or more.")
    if any(k.endswith("proxyPassword") for k in props):
        f.add("WARN", "proxy-secret", "A proxy password is stored in project gradle.properties.",
              "Move credentials to ~/.gradle/gradle.properties (never commit them).")
    if props.get("android.enableJetifier", "").lower() == "true":
        f.add("INFO", "jetifier", "android.enableJetifier=true slows builds.", "Disable it once no dependency uses the old support libraries.")

    # SDK location
    sdk = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    lp = parse_props(read(root / "local.properties"))
    sdk_dir = lp.get("sdk.dir", "").replace("\\:", ":").replace("\\\\", "\\")
    if sdk_dir and not Path(sdk_dir).is_dir():
        f.add("ERROR", "bad-sdk-dir", f"local.properties sdk.dir does not exist: {sdk_dir}",
              "`fix --apply --sdk-dir <path>` or open the project in Android Studio.")
    elif not sdk_dir and not (sdk and Path(sdk).is_dir()):
        f.add("ERROR", "no-sdk", "Android SDK not found: no valid sdk.dir in local.properties and no ANDROID_HOME.",
              "`fix --apply --sdk-dir <SDK path>` (Windows default: %LOCALAPPDATA%\\Android\\Sdk).")
    if (root / "local.properties").exists() and (root / ".gitignore").exists() \
            and "local.properties" not in (read(root / ".gitignore") or ""):
        f.add("WARN", "ignore-local", "local.properties is not in .gitignore.", "Add it: it holds a machine-specific path.")

    # build scripts
    repos_text = ""
    for bf in project_files(root):
        t = read(bf) or ""
        rel = bf.relative_to(root)
        if re.search(r"""['"][\w.\-]+:[\w.\-]+:[^'"]*\+['"]""", t):
            f.add("WARN", "dynamic-version", f"{rel}: dynamic version ('+') dependency.",
                  "Pin an exact version (the Android docs advise against dynamic versions).")
        if re.search(r"\bjcenter\(\)", t):
            f.add("ERROR", "jcenter", f"{rel}: jcenter() is shut down.", "Use mavenCentral() and google().")
        if re.search(r"^\s*(compile|testCompile|androidTestCompile)\s*[\s(]", t, re.M):
            f.add("ERROR", "old-config", f"{rel}: removed configuration compile/testCompile.",
                  "Use implementation/api and testImplementation/androidTestImplementation.")
        if re.search(r"\bkapt\b", t):
            f.add("INFO", "kapt", f"{rel}: uses kapt.", "Prefer ksp when the library supports it (slower builds otherwise).")
        if bf.name.startswith("settings"):
            repos_text += t
    if (root / "settings.gradle").exists() or (root / "settings.gradle.kts").exists():
        if "google()" not in repos_text and "google {" not in repos_text and "dev.google" not in repos_text:
            f.add("WARN", "no-google-repo", "google() repository not found in settings.",
                  "Add google() to pluginManagement and dependencyResolutionManagement repositories.")
        if "mavenCentral()" not in repos_text:
            f.add("WARN", "no-maven-central", "mavenCentral() not found in settings.", "Add mavenCentral().")
    if not (root / "gradle" / "libs.versions.toml").exists():
        f.add("INFO", "no-catalog", "No gradle/libs.versions.toml version catalog.",
              "New Android projects use one; `add-lib` creates it on first use.")

    return emit_findings(f, args, header={"gradle": gv, "agp": agp, "kotlin": kot, "java": major})


def emit_findings(f, args, header=None):
    if getattr(args, "json", False):
        print(json.dumps({"summary": header or {}, "findings": f.items}, indent=2))
    else:
        if header:
            print("Detected: " + ", ".join(f"{k}={v or '?'}" for k, v in header.items()))
        order = {"ERROR": 0, "WARN": 1, "INFO": 2}
        for i in sorted(f.items, key=lambda x: order[x["level"]]):
            print(f"[{i['level']}] {i['code']}: {i['message']}")
            if i["fix"]:
                print(f"        fix: {i['fix']}")
        print(f"\n{f.errors} error(s), {sum(1 for i in f.items if i['level'] == 'WARN')} warning(s)")
    return 1 if f.errors else 0


# ---------------------------------------------------------------- diagnose

# (regex, title, cause, fix)
PATTERNS = [
    (r"Unsupported class file major version (\d+)|Unsupported Java\. Your build is currently configured to use Java|"
     r"Could not (?:determine java version|create service of type)|Gradle does not support (?:Java|JVM)|JVM \d+ (?:is not supported|does not support)",
     "Java and Gradle versions do not match",
     "The JDK running Gradle is newer or older than the Gradle/AGP/Kotlin in use (class major 61=Java 17, 65=21, 69=25).",
     "Run `gradle_doctor.py check`. Use JDK 17 for AGP 8/9, or upgrade the wrapper to a Gradle that supports your JDK (docs.gradle.org compatibility table). Set JAVA_HOME or Android Studio > Settings > Build Tools > Gradle > Gradle JDK."),
    (r"Minimum supported Gradle version is ([\d.]+)|requires Gradle ([\d.]+)|requires (?:at least )?Gradle ([\d.]+)",
     "Gradle is older than the Android Gradle Plugin needs",
     "The wrapper Gradle is below the minimum for this AGP.",
     "`gradle_doctor.py fix --gradle-version <version from the message> --apply`, then `./gradlew --version`. Or lower the AGP version."),
    (r"SDK location not found|Define a valid SDK location|sdk\.dir",
     "Android SDK location not set",
     "Neither local.properties sdk.dir nor ANDROID_HOME points to an SDK.",
     "`gradle_doctor.py fix --sdk-dir <path> --apply` (Windows: %LOCALAPPDATA%\\Android\\Sdk, macOS: ~/Library/Android/sdk, Linux: ~/Android/Sdk)."),
    (r"Failed to install the following Android SDK packages|licenses? (?:have not been|not) accepted|You have not accepted the license",
     "Android SDK licenses not accepted",
     "A required SDK package (build-tools, platform) cannot be installed until licenses are accepted.",
     "Run `sdkmanager --licenses` from the SDK cmdline-tools and accept, or install the missing package in the SDK Manager."),
    (r"Could not resolve ([\w.\-]+:[\w.\-]+:[^\s']+)|Could not find ([\w.\-]+:[\w.\-]+:[^\s]+)|Could not GET '([^']+)'|Could not resolve all (?:files|dependencies)",
     "Dependency could not be resolved",
     "Wrong coordinates/version, missing repository, offline mode, proxy/TLS problem, or a flaky network.",
     "1) Check group:artifact:version on the library's page. 2) Make sure google() and mavenCentral() are in dependencyResolutionManagement. 3) `./gradlew :app:dependencyInsight --dependency <name> --configuration debugRuntimeClasspath`. 4) Retry with `--refresh-dependencies`. 5) Behind a proxy set systemProp.https.proxyHost/Port in ~/.gradle/gradle.properties."),
    (r"Duplicate class ([\w.$]+) found in modules",
     "Duplicate classes from two dependencies",
     "The same class ships in two artifacts (e.g. old support libs and AndroidX, or a library and its -ktx/-jdk7/-jdk8 stub).",
     "`./gradlew :app:dependencies` and exclude one module: `implementation(libs.x) { exclude(group = \"...\", module = \"...\") }`, or align versions with a BOM/constraint."),
    (r"Manifest merger failed|uses-sdk:minSdkVersion .* cannot be smaller than version",
     "Manifest merge failed",
     "A library needs a higher minSdk, or attributes conflict (android:exported, allowBackup, label...).",
     "Raise minSdk if acceptable, or add tools:overrideLibrary / tools:replace in the manifest. The error names the exact attribute and library."),
    (r"android:exported needs to be explicitly specified|targeting Android 12",
     "android:exported is missing",
     "Targeting API 31+ requires android:exported on every activity, service and receiver with an intent-filter.",
     "Add android:exported=\"true\" or \"false\" to the element named in the message."),
    (r"OutOfMemoryError|Java heap space|GC overhead limit exceeded|Metaspace|Expiring Daemon because JVM heap space is exhausted",
     "Out of memory in the Gradle or Kotlin daemon",
     "The default heap is too small for the project.",
     "In gradle.properties: `org.gradle.jvmargs=-Xmx4g -XX:MaxMetaspaceSize=1g -Dfile.encoding=UTF-8` and `kotlin.daemon.jvmargs=-Xmx2g`, then `./gradlew --stop`. Lower values on low-RAM machines."),
    (r"Execution failed for task ':[\w:]*(?:dex|Dex|mergeDex|minify|r8|R8)\w*'|Cannot fit requested classes in a single dex file|R8:",
     "Dex or R8/ProGuard failure",
     "Too many methods without multidex, a missing -dontwarn/-keep rule, or a library needing desugaring.",
     "Read the first `R8:` line. Add the suggested rule from build/outputs/mapping/<variant>/missing_rules.txt, enable multidex for minSdk < 21, or coreLibraryDesugaring for Java 8+ APIs."),
    (r"Unresolved reference|Cannot access class|Type mismatch|Kotlin: |e: file:///",
     "Kotlin compile error",
     "Source error, or a library/Kotlin version mismatch (metadata version, API removed).",
     "Fix the first `e:` line. For 'incompatible version of Kotlin' align Kotlin plugin and library versions. Run `./gradlew :app:compileDebugKotlin --stacktrace`."),
    (r"Plugin \[id: '([^']+)'\] was not found|Plugin with id '([^']+)' not found|plugin .* was not found in any of the following sources",
     "Gradle plugin not found",
     "pluginManagement repositories lack google()/gradlePluginPortal(), or the plugin id/version is wrong.",
     "In settings.gradle(.kts) pluginManagement { repositories { google(); mavenCentral(); gradlePluginPortal() } } and check the plugin id and version."),
    (r"Unresolved reference: libs|Unresolved reference: (?:alias|versionCatalogs)|Could not find method \w+\(\) for arguments \[libs|Unable to find method .*libs|Cannot resolve external dependency .* because no repositories are defined|libs\.versions\.toml",
     "Version catalog problem",
     "libs.versions.toml missing/misnamed, alias typo, or '-' vs '.' in the accessor (`retrofit-core` is `libs.retrofit.core`).",
     "File must be gradle/libs.versions.toml with [versions]/[libraries]/[plugins]. Sync after edits. Use `gradle_doctor.py add-lib` to add entries safely."),
    (r"A problem occurred configuring (?:root )?project|Build file '([^']+)' line: (\d+)|Script compilation error",
     "Build script error",
     "Syntax or API error in a build script (the file and line are in the message).",
     "Open the file and line shown. Run `./gradlew help --stacktrace`: if `help` fails the problem is in configuration, not in a task."),
    (r"Timeout of \d+ ms|Connection timed out|Read timed out|UnknownHostException|PKIX path building failed|SSLHandshakeException|Connect to [\w.\-]+:\d+ .* failed",
     "Network, proxy or TLS failure",
     "Gradle cannot reach a repository or the Gradle distribution.",
     "Check connectivity/VPN. Set systemProp.http(s).proxyHost/proxyPort in ~/.gradle/gradle.properties. For corporate TLS interception add the CA to the JDK cacerts. Retry with `--offline` only if everything is cached."),
    (r"Could not (?:connect to|create|find) .*daemon|Daemon (?:will be stopped|disappeared)|Timeout waiting to lock|currently in use by another Gradle instance|lock (?:on|for) .* held",
     "Gradle daemon or lock problem",
     "A stale/crashed daemon, or another Gradle process holds a lock on ~/.gradle.",
     "`./gradlew --stop`, close other IDE/Gradle runs, delete stale `*.lock` files under ~/.gradle only when no Gradle process is running. See daemon-<pid>.out.log in ~/.gradle/daemon/<version>/."),
    (r"Entry .* is a duplicate but no duplicate handling strategy|More than one file was found with OS independent path|2 files found with path 'META-INF",
     "Duplicate files when packaging",
     "Two libraries ship the same resource (often META-INF/*).",
     "android { packaging { resources { excludes += \"/META-INF/{AL2.0,LGPL2.1}\" } } } (or pickFirsts for the exact path in the message)."),
    (r"Test (?:.*) FAILED|There were failing tests|Execution failed for task ':[\w:]*(?:test|Test)\w*'",
     "Unit tests failed",
     "One or more tests failed; the build output only summarises them.",
     "Open build/reports/tests/test<Variant>UnitTest/index.html or run `gradle_doctor.py test --class <C> --method <m>` to rerun just that test."),
    (r"INSTALL_FAILED_\w+|No connected devices|DeviceException|Unable to determine .* device|ShellCommandUnresponsiveException",
     "Instrumented test device problem",
     "No device/emulator, wrong ABI/API, or install conflict.",
     "`adb devices` must list a device in `device` state. For INSTALL_FAILED_UPDATE_INCOMPATIBLE uninstall the app first. Or use Gradle Managed Devices."),
    (r"lint found|Lint found errors|Execution failed for task ':[\w:]*lint\w*'",
     "Lint failure",
     "Lint reported errors that fail the build.",
     "Read build/reports/lint-results-<variant>.html; fix the issue, or record a baseline with `lint { baseline = file(\"lint-baseline.xml\") }`."),
    (r"Deprecated Gradle features were used|has been deprecated and is scheduled to be removed in Gradle \d+",
     "Deprecation warning (not a failure)",
     "Build logic uses an API removed in a future Gradle.",
     "Run `./gradlew build --warning-mode all` to list each one, and update the plugin or script named."),
]


def diagnose_text(text):
    results = []
    seen = set()
    for rx, title, cause, fix in PATTERNS:
        m = re.search(rx, text, re.I | re.M)
        if m and title not in seen:
            seen.add(title)
            line = text[max(0, text.rfind("\n", 0, m.start()) + 1):]
            line = line.split("\n", 1)[0].strip()[:300]
            results.append({"title": title, "evidence": line, "cause": cause, "fix": fix})
    return results


def cmd_diagnose(args):
    text = sys.stdin.read() if args.log == "-" else read(args.log)
    if text is None:
        print(f"cannot read {args.log}", file=sys.stderr)
        return 2
    res = diagnose_text(text)
    real = [r for r in res if not r["title"].startswith("Deprecation")]
    if args.json:
        print(json.dumps(res, indent=2))
    elif not res:
        print("No known problem matched. Re-run with `./gradlew <task> --stacktrace --info` and look for the first 'What went wrong:' block.")
    else:
        for n, r in enumerate(res, 1):
            print(f"{n}. {r['title']}\n   evidence: {r['evidence']}\n   cause:    {r['cause']}\n   fix:      {r['fix']}\n")
    return 1 if real else 0


# ---------------------------------------------------------------- fix


def cmd_fix(args):
    root = Path(args.project).resolve()
    plan = []

    gp = root / "gradle.properties"
    text = read(gp) or ""
    props = parse_props(text)
    add = [f"{k}={v}" for k, v in RECOMMENDED_PROPS.items() if k not in props]
    if add:
        new = text + ("" if not text or text.endswith("\n") else "\n") + "\n".join(add) + "\n"
        plan.append((f"add to gradle.properties: {', '.join(add)}", gp, new))

    if args.gradle_version:
        wp = root / "gradle" / "wrapper" / "gradle-wrapper.properties"
        t = read(wp)
        if t is None:
            print("no gradle-wrapper.properties; run `gradle wrapper --gradle-version X` instead", file=sys.stderr)
        elif not re.fullmatch(r"\d+\.\d+(\.\d+)?", args.gradle_version):
            print("--gradle-version must look like 8.13 or 9.6.0", file=sys.stderr)
            return 2
        else:
            new = re.sub(r"gradle-[0-9][^/\s]*?-(bin|all)\.zip", f"gradle-{args.gradle_version}-\\1.zip", t)
            if "distributionSha256Sum" in new:
                new = re.sub(r"^distributionSha256Sum=.*\n?", "", new, flags=re.M)
                print("note: removed the old distributionSha256Sum; add the new release checksum from gradle.org.")
            plan.append((f"wrapper distributionUrl -> Gradle {args.gradle_version} "
                         "(run `./gradlew wrapper` twice afterwards to refresh scripts and jar)", wp, new))

    if args.sdk_dir:
        sdk = Path(args.sdk_dir).expanduser()
        if not sdk.is_dir():
            print(f"--sdk-dir is not a directory: {sdk}", file=sys.stderr)
            return 2
        lp = root / "local.properties"
        t = read(lp) or ""
        val = str(sdk).replace("\\", "\\\\").replace(":", "\\:")
        new = re.sub(r"^sdk\.dir=.*$", lambda _m: f"sdk.dir={val}", t, flags=re.M) if re.search(r"^sdk\.dir=", t, re.M) \
            else t + ("" if not t or t.endswith("\n") else "\n") + f"sdk.dir={val}\n"
        plan.append((f"set sdk.dir in local.properties to {sdk}", lp, new))

    gi = root / ".gitignore"
    if gi.exists() and (root / "local.properties").exists() and "local.properties" not in (read(gi) or ""):
        t = read(gi)
        plan.append(("add local.properties to .gitignore", gi, t + ("" if t.endswith("\n") else "\n") + "local.properties\n"))

    if not plan:
        print("Nothing to fix.")
        return 0
    for desc, path, new in plan:
        print(("APPLY  " if args.apply else "WOULD  ") + desc)
        if args.apply:
            backup_write(path, new)
    if not args.apply:
        print("\nDry run. Re-run with --apply to write (originals are saved as .bak).")
    return 0


# ---------------------------------------------------------------- add-lib

ALIAS_RE = re.compile(r"^[a-z][a-z0-9]*(?:[-_.][a-z0-9]+)*$", re.I)
CONFIGS = {"implementation", "api", "compileOnly", "runtimeOnly", "ksp", "kapt", "annotationProcessor",
           "testImplementation", "androidTestImplementation", "debugImplementation", "lintChecks", "lintPublish"}


def toml_add(text, alias, group, name, version):
    """Insert a version + library into libs.versions.toml text; returns (new_text, version_key)."""
    if not text.strip():
        text = "[versions]\n\n[libraries]\n"
    for sec in ("[versions]", "[libraries]"):
        if sec not in text:
            text = text.rstrip("\n") + f"\n\n{sec}\n"
    if re.search(rf"^{re.escape(alias)}\s*=", text.split("[libraries]", 1)[1], re.M):
        raise ValueError(f"alias {alias!r} already exists in [libraries]")
    vkey = alias
    lib = f'{alias} = {{ group = "{group}", name = "{name}", version.ref = "{vkey}" }}\n'
    head, rest = text.split("[libraries]", 1)
    head = head.rstrip("\n") + f'\n{vkey} = "{version}"\n\n'
    # keep any sections that follow [libraries] intact
    m = re.search(r"^\[(?!libraries)", rest, re.M)
    body, tail = (rest[:m.start()], rest[m.start():]) if m else (rest, "")
    body = body.rstrip("\n") + "\n" + lib + ("\n" if tail else "")
    return head + "[libraries]" + body + tail, vkey


def cmd_add_lib(args):
    parts = args.coordinates.split(":")
    if len(parts) != 3 or not all(parts):
        print("--coordinates must be group:artifact:version", file=sys.stderr)
        return 2
    group, name, version = parts
    if "+" in version or version.lower() in ("latest", "latest.release", "release"):
        print("dynamic versions are not allowed; give an exact version (check Maven Central / Google Maven)", file=sys.stderr)
        return 2
    if not ALIAS_RE.match(args.alias):
        print("alias must be lowercase letters/digits separated by - (e.g. retrofit-core)", file=sys.stderr)
        return 2
    if args.config not in CONFIGS:
        print(f"unknown configuration {args.config}; choose one of {', '.join(sorted(CONFIGS))}", file=sys.stderr)
        return 2
    root = Path(args.project).resolve()
    toml = root / "gradle" / "libs.versions.toml"
    try:
        new_toml, _ = toml_add(read(toml) or "", args.alias, group, name, version)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1
    accessor = "libs." + re.sub(r"[-_]", ".", args.alias)

    mod = root / args.module
    bf = mod / "build.gradle.kts"
    kts = bf.exists()
    if not kts:
        bf = mod / "build.gradle"
    if not bf.exists():
        print(f"no build.gradle(.kts) in {mod}", file=sys.stderr)
        return 1
    btxt = read(bf)
    line = f"    {args.config}({accessor})\n" if kts else f"    {args.config} {accessor}\n"
    m = re.search(r"^dependencies\s*\{[ \t]*\n", btxt, re.M)
    if not m:
        new_b = btxt.rstrip("\n") + f"\n\ndependencies {{\n{line}}}\n"
    else:
        new_b = btxt[:m.end()] + line + btxt[m.end():]
    print(f"{toml.relative_to(root)}: + [versions] {args.alias} = \"{version}\"; [libraries] {args.alias} = {group}:{name}")
    print(f"{bf.relative_to(root)}: + {line.strip()}")
    if args.apply:
        backup_write(toml, new_toml)
        backup_write(bf, new_b)
        print("Written (originals saved as .bak). Now run `./gradlew :%s:dependencies --configuration debugRuntimeClasspath` or sync." % args.module)
    else:
        print("Dry run. Re-run with --apply to write.")
    return 0


# ---------------------------------------------------------------- test


def cap(s):
    return s[:1].upper() + s[1:]


def build_test_command(args):
    mod = args.module.strip(":")
    prefix = f":{mod}:" if mod else ""
    var = cap(args.variant)
    task = f"{prefix}connected{var}AndroidTest" if args.instrumented else f"{prefix}test{var}UnitTest"
    cmd = [task]
    if args.cls:
        if args.instrumented:
            filt = args.cls + (f"#{args.method}" if args.method else "")
            cmd += [f"-Pandroid.testInstrumentationRunnerArguments.class={filt}"]
        else:
            cmd += ["--tests", args.cls + (f".{args.method}" if args.method else "")]
    elif args.method:
        if args.instrumented:
            raise ValueError("--method needs --class for instrumented tests")
        cmd += ["--tests", f"*.{args.method}"]
    return cmd


def report_dirs(args):
    mod = args.module.strip(":") or "."
    var = args.variant
    if args.instrumented:
        return [f"{mod}/build/reports/androidTests/connected/", f"{mod}/build/outputs/androidTest-results/connected/"]
    return [f"{mod}/build/reports/tests/test{cap(var)}UnitTest/", f"{mod}/build/test-results/test{cap(var)}UnitTest/"]


def cmd_test(args):
    root = Path(args.project).resolve()
    try:
        gargs = build_test_command(args)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    wrapper = root / ("gradlew.bat" if os.name == "nt" else "gradlew")
    exe = str(wrapper) if wrapper.exists() else (shutil.which("gradle") or "gradle")
    full = [exe] + gargs + ["--console=plain"]
    print("$ " + " ".join(full))
    print("reports: " + ", ".join(report_dirs(args)))
    if args.dry_run:
        return 0
    if args.instrumented:
        print("note: instrumented tests need a device or emulator (`adb devices`) or Gradle Managed Devices.")
    try:
        rc = subprocess.run(full, cwd=str(root)).returncode
    except OSError as e:
        print(f"could not start Gradle: {e}", file=sys.stderr)
        return 2
    if rc != 0:
        print("\nBuild failed. Save the output to a file and run: gradle_doctor.py diagnose <file>")
    return rc


# ---------------------------------------------------------------- main


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("check", help="inspect a project for setup and compatibility problems")
    p.add_argument("--project", default=".")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_check)

    p = sub.add_parser("diagnose", help="explain a Gradle failure log")
    p.add_argument("log", help="log file, or - for stdin")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_diagnose)

    p = sub.add_parser("fix", help="apply safe fixes (dry run unless --apply)")
    p.add_argument("--project", default=".")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--gradle-version")
    p.add_argument("--sdk-dir")
    p.set_defaults(fn=cmd_fix)

    p = sub.add_parser("add-lib", help="add a library to the version catalog and a module")
    p.add_argument("--coordinates", required=True, help="group:artifact:version")
    p.add_argument("--alias", required=True)
    p.add_argument("--module", default="app")
    p.add_argument("--config", default="implementation")
    p.add_argument("--project", default=".")
    p.add_argument("--apply", action="store_true")
    p.set_defaults(fn=cmd_add_lib)

    p = sub.add_parser("test", help="run Android unit or instrumented tests")
    p.add_argument("--project", default=".")
    p.add_argument("--module", default="app")
    p.add_argument("--variant", default="debug")
    p.add_argument("--class", dest="cls")
    p.add_argument("--method")
    p.add_argument("--instrumented", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(fn=cmd_test)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
