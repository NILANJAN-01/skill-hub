#!/usr/bin/env python3
"""Set up JUnit 6 (Jupiter) and scaffold test classes for Java and Kotlin code.

Usage:
    python junit_scaffold.py check <project-dir> [--json]
    python junit_scaffold.py deps [--build gradle-kts|gradle-groovy|toml|maven] [--kotlin] [--vintage]
    python junit_scaffold.py new <Source.java|Source.kt> [--out DIR] [--stdout] [--force]
                                 [--no-parameterized] [--test-suffix Test]

check  reads settings.gradle(.kts), build.gradle(.kts), gradle/libs.versions.toml and pom.xml files and
       says what a JUnit 6 setup still needs (BOM/version, junit-jupiter, junit-platform-launcher,
       useJUnitPlatform(), Surefire 3.x, Java 17 toolchain, Kotlin 2.2), with the snippet to add.
deps   prints the dependency and test-task snippet.
new    reads one class (Java or Kotlin) and writes <Class>Test with one @Nested group per public method:
       a @Test that calls the method and fails with a TODO until real assertions are written, an
       assertThrows test for each exception the method throws, and (for methods with simple
       parameters and a result) a @ParameterizedTest @CsvSource template that stays @Disabled until
       real rows are added. The output compiles; nothing passes by accident.
       Default output: the matching src/test/java or src/test/kotlin folder. Never overwrites without --force.
Standard library only.

Exit codes: 0 ok, 1 check found missing setup, 2 bad usage or input.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

JUNIT = "6.1.3"
SUREFIRE = "3.5.5"
SKIP_DIRS = {".git", ".gradle", ".idea", "build", "out", "target", "node_modules", "__pycache__"}

SIMPLE_JAVA = {"int": "0", "long": "0", "short": "0", "byte": "0", "double": "0.0", "float": "0.0",
               "boolean": "false", "char": "a", "String": "text", "Integer": "0", "Long": "0", "Double": "0.0",
               "Float": "0.0", "Boolean": "false", "Character": "a", "Short": "0", "Byte": "0"}
SIMPLE_KT = {"Int": "0", "Long": "0", "Short": "0", "Byte": "0", "Double": "0.0", "Float": "0.0",
             "Boolean": "false", "Char": "a", "String": "text"}
JAVA_LITERAL = {"int": "0", "long": "0L", "short": "(short) 0", "byte": "(byte) 0", "double": "0.0",
                "float": "0.0f", "boolean": "false", "char": "'a'", "String": "\"\"", "Integer": "0", "Long": "0L",
                "Double": "0.0", "Float": "0.0f", "Boolean": "false", "Character": "'a'", "Short": "(short) 0",
                "Byte": "(byte) 0"}
KT_LITERAL = {"Int": "0", "Long": "0L", "Short": "0", "Byte": "0", "Double": "0.0", "Float": "0.0f",
              "Boolean": "false", "Char": "'a'", "String": "\"\""}
JAVA_KEYWORDS = {"if", "for", "while", "switch", "catch", "return", "new", "throw", "else", "synchronized", "try",
                 "do", "super", "this"}


# ================================================================================ snippets
def deps_snippet(build: str, kotlin: bool = False, vintage: bool = False) -> str:
    if build == "maven":
        extra = ""
        if vintage:
            extra = ("\n  <!-- temporary, while JUnit 4 tests are migrated (Vintage is deprecated) -->\n"
                     "  <dependency>\n    <groupId>org.junit.vintage</groupId>\n"
                     "    <artifactId>junit-vintage-engine</artifactId>\n    <scope>test</scope>\n  </dependency>")
        return ("<dependencyManagement>\n  <dependencies>\n    <dependency>\n      <groupId>org.junit</groupId>\n"
                "      <artifactId>junit-bom</artifactId>\n      <version>%s</version>\n      <type>pom</type>\n"
                "      <scope>import</scope>\n    </dependency>\n  </dependencies>\n</dependencyManagement>\n\n"
                "<dependencies>\n  <dependency>\n    <groupId>org.junit.jupiter</groupId>\n"
                "    <artifactId>junit-jupiter</artifactId>\n    <scope>test</scope>\n  </dependency>%s\n"
                "</dependencies>\n\n<build>\n  <plugins>\n    <plugin>\n"
                "      <artifactId>maven-surefire-plugin</artifactId>\n      <version>%s</version>\n"
                "    </plugin>\n  </plugins>\n</build>\n<!-- run Maven on JDK 17 or newer -->\n"
                % (JUNIT, extra, SUREFIRE))
    if build == "toml":
        return ("# gradle/libs.versions.toml\n[versions]\njunit = \"%s\"\n\n[libraries]\n"
                "junit-bom = { module = \"org.junit:junit-bom\", version.ref = \"junit\" }\n"
                "junit-jupiter = { module = \"org.junit.jupiter:junit-jupiter\" }\n"
                "junit-platform-launcher = { module = \"org.junit.platform:junit-platform-launcher\" }\n"
                "%s\n# build.gradle.kts\ndependencies {\n    testImplementation(platform(libs.junit.bom))\n"
                "    testImplementation(libs.junit.jupiter)\n    testRuntimeOnly(libs.junit.platform.launcher)\n"
                "%s}\n\ntasks.test {\n    useJUnitPlatform()\n}\n"
                % (JUNIT, "junit-vintage-engine = { module = \"org.junit.vintage:junit-vintage-engine\" }\n"
                   if vintage else "", "    testRuntimeOnly(libs.junit.vintage.engine) // temporary\n"
                   if vintage else ""))
    q, call = ("'", "%s %s") if build == "gradle-groovy" else ('"', "%s(%s)")

    def dep(conf, coord, plat=False):
        c = "%s%s%s" % (q, coord, q)
        if plat:
            c = "platform(%s)" % c
        return "    " + call % (conf, c)
    lines = [dep("testImplementation", "org.junit:junit-bom:" + JUNIT, True),
             dep("testImplementation", "org.junit.jupiter:junit-jupiter"),
             dep("testRuntimeOnly", "org.junit.platform:junit-platform-launcher")]
    if kotlin:
        lines.append("    // assertThrows<T> { }, assertAll and fail are in junit-jupiter-api for Kotlin;")
        lines.append("    // add kotlinx-coroutines-core (and kotlin-reflect) to write suspend test functions")
    if vintage:
        lines.append(dep("testRuntimeOnly", "org.junit.vintage:junit-vintage-engine") + "  // temporary")
    task = "test {\n    useJUnitPlatform()\n}" if build == "gradle-groovy" else "tasks.test {\n    useJUnitPlatform()\n}"
    toolchain = ("java {\n    toolchain {\n        languageVersion = JavaLanguageVersion.of(17)\n    }\n}\n\n"
                 if build == "gradle-groovy" else
                 "java {\n    toolchain {\n        languageVersion.set(JavaLanguageVersion.of(17))\n    }\n}\n\n")
    return toolchain + "dependencies {\n" + "\n".join(lines) + "\n}\n\n" + task + "\n"


# ================================================================================ check
def read(path: str) -> str:
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        return fh.read()


def vtuple(v: str):
    m = re.match(r"(\d+)\.(\d+)(?:\.(\d+))?", v or "")
    return (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)) if m else None


def find_build_files(root: str) -> list:
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        for f in ("build.gradle.kts", "build.gradle", "pom.xml"):
            if f in filenames:
                out.append(os.path.join(dirpath, f))
    return out


def toml_info(root: str) -> dict:
    p = os.path.join(root, "gradle", "libs.versions.toml")
    if not os.path.isfile(p):
        return {}
    text = read(p)
    versions = dict(re.findall(r"""^\s*([\w.-]+)\s*=\s*["']([^"']+)["']""",
                               (re.search(r"\[versions\](.*?)(\n\[|\Z)", text, re.S) or [None, ""])[1]
                               if re.search(r"\[versions\]", text) else "", re.M))
    libs = {}
    for m in re.finditer(r"""^\s*([\w.-]+)\s*=\s*\{([^}]*)\}""", text, re.M):
        body = m.group(2)
        mod = re.search(r"""module\s*=\s*["']([^"']+)["']""", body)
        g = re.search(r"""group\s*=\s*["']([^"']+)["']""", body)
        n = re.search(r"""name\s*=\s*["']([^"']+)["']""", body)
        coord = mod.group(1) if mod else ("%s:%s" % (g.group(1), n.group(1)) if g and n else "")
        vr = re.search(r"""version\.ref\s*=\s*["']([^"']+)["']""", body)
        vv = re.search(r"""version\s*=\s*["']([^"']+)["']""", body)
        libs["libs." + re.sub(r"[-_]", ".", m.group(1))] = (coord, versions.get(vr.group(1), "") if vr else
                                                             (vv.group(1) if vv else ""))
    return libs


def check_gradle(path: str, root: str, libs: dict) -> dict:
    text = re.sub(r"//.*", "", read(path))
    info = {"file": os.path.relpath(path, root).replace(os.sep, "/"), "tool": "gradle",
            "dsl": "gradle-kts" if path.endswith(".kts") else "gradle-groovy", "missing": [], "notes": []}
    coords = {}
    for m in re.finditer(r"""["']([\w.-]+:[\w.-]+)(?::([^"'@\s)]+))?["']""", text):
        coords[m.group(1)] = m.group(2) or ""
    for acc, (coord, ver) in libs.items():
        if re.search(re.escape(acc) + r"\b", text) and coord:
            coords[coord] = ver
    junit = {c: v for c, v in coords.items() if c.startswith(("org.junit", "junit:junit"))}
    if not junit and not re.search(r"\b(test|androidTest)Implementation\b|useJUnit", text):
        return {}
    info["junit"] = junit
    versions = [vtuple(v) for c, v in junit.items() if c.startswith(("org.junit:junit-bom", "org.junit.jupiter")) and vtuple(v)]
    info["version"] = ".".join(map(str, max(versions))) if versions else None
    has_jupiter = any(c.startswith("org.junit.jupiter:junit-jupiter") for c in junit)
    android = bool(re.search(r"com\.android\.(application|library)|androidApplication|androidLibrary", text))
    if not has_jupiter:
        info["missing"].append('testImplementation("org.junit.jupiter:junit-jupiter") with the BOM %s' % JUNIT)
    elif "org.junit.jupiter:junit-jupiter" not in junit and "org.junit.jupiter:junit-jupiter-engine" not in junit:
        info["missing"].append("an engine: use the aggregate org.junit.jupiter:junit-jupiter (api + params + engine)")
    if "org.junit:junit-bom" not in junit and not any(v for c, v in junit.items() if c == "org.junit.jupiter:junit-jupiter"):
        info["notes"].append("no JUnit BOM: import platform(\"org.junit:junit-bom:%s\") so all JUnit artifacts "
                             "share one version" % JUNIT)
    if has_jupiter and "org.junit.platform:junit-platform-launcher" not in junit:
        info["missing"].append('testRuntimeOnly("org.junit.platform:junit-platform-launcher") (required by Gradle 9)')
    if has_jupiter and not re.search(r"useJUnitPlatform|useJUnitJupiter", text):
        info["missing"].append("unitTests.all { it.useJUnitPlatform() } in android.testOptions" if android else
                               "tasks.test { useJUnitPlatform() }")
    if info["version"] and vtuple(info["version"]) < (6, 0, 0):
        info["notes"].append("JUnit %s: %s is current (needs Java 17+); see junit-migration" % (info["version"], JUNIT))
    tc = re.search(r"(jvmToolchain\s*\(\s*|JavaLanguageVersion\.of\s*\(\s*)(\d+)", text)
    if tc and int(tc.group(2)) < 17:
        info["missing"].append("a Java 17+ toolchain for the tests (found %s)" % tc.group(2))
    kv = re.search(r"""kotlin[\w.()"']*\s*version\s*["'](\d+\.\d+)""", text)
    if kv and vtuple(kv.group(1)) < (2, 2, 0):
        info["notes"].append("Kotlin %s: JUnit 6 needs Kotlin 2.2+" % kv.group(1))
    if "junit:junit" in junit and "org.junit.vintage:junit-vintage-engine" not in junit and has_jupiter:
        info["notes"].append("junit:junit is on the classpath without junit-vintage-engine: JUnit 4 tests do not run")
    info["kotlin"] = bool(re.search(r"kotlin", text))
    return info


def check_maven(path: str, root: str) -> dict:
    text = re.sub(r"<!--.*?-->", "", read(path), flags=re.S)
    if "junit" not in text and "<packaging>jar" not in text:
        return {}
    info = {"file": os.path.relpath(path, root).replace(os.sep, "/"), "tool": "maven", "dsl": "maven",
            "missing": [], "notes": []}
    props = dict(re.findall(r"<([\w.-]+)>([^<]+)</\1>", (re.search(r"<properties>(.*?)</properties>", text, re.S)
                                                          or re.match("()", "")).group(1)))
    junit = {}
    plugins = {}
    for m in re.finditer(r"<(dependency|plugin)>(.*?)</\1>", text, re.S):
        g = re.search(r"<groupId>\s*([^<\s]+)", m.group(2))
        a = re.search(r"<artifactId>\s*([^<\s]+)", m.group(2))
        v = re.search(r"<version>\s*([^<\s]+)", m.group(2))
        if not a:
            continue
        ver = v.group(1) if v else ""
        pv = re.match(r"\$\{([^}]+)\}", ver)
        ver = props.get(pv.group(1), ver) if pv else ver
        if m.group(1) == "plugin":
            plugins[a.group(1)] = ver
        elif g and g.group(1).startswith(("org.junit", "junit")):
            junit["%s:%s" % (g.group(1), a.group(1))] = ver
    info["junit"] = junit
    versions = [vtuple(v) for v in junit.values() if vtuple(v)]
    info["version"] = ".".join(map(str, max(versions))) if versions else None
    if not any(c.startswith("org.junit.jupiter:junit-jupiter") for c in junit):
        info["missing"].append("org.junit.jupiter:junit-jupiter (test scope) with the junit-bom %s import" % JUNIT)
    sf = plugins.get("maven-surefire-plugin")
    if sf is None or not sf:
        info["missing"].append("maven-surefire-plugin %s (JUnit 6 needs 3.0.0+; the default depends on Maven)" % SUREFIRE)
    elif vtuple(sf) and vtuple(sf) < (3, 0, 0):
        info["missing"].append("maven-surefire-plugin %s or newer (found %s)" % (SUREFIRE, sf))
    rel = re.search(r"<(maven\.compiler\.release|maven\.compiler\.source|java\.version)>\s*(\d+)", text)
    if rel and int(rel.group(2)) < 17:
        info["notes"].append("compiling for Java %s is fine, but run the tests on JDK 17+" % rel.group(2))
    if "junit:junit" in junit and "org.junit.vintage:junit-vintage-engine" not in junit and \
            any(c.startswith("org.junit.jupiter") for c in junit):
        info["notes"].append("junit:junit without junit-vintage-engine: Surefire runs only the Jupiter tests")
    info["kotlin"] = "kotlin-maven-plugin" in plugins
    return info


def check(root: str) -> dict:
    libs = toml_info(root)
    mods = []
    for f in find_build_files(root):
        info = check_maven(f, root) if f.endswith("pom.xml") else check_gradle(f, root, libs)
        if info:
            mods.append(info)
    ok = bool(mods) and all(not m["missing"] for m in mods)
    return {"root": root, "modules": mods, "catalog": bool(libs), "ok": ok}


def print_check(rep: dict) -> None:
    print("JUnit setup check: %s" % rep["root"])
    if not rep["modules"]:
        print("  no Gradle or Maven module with tests found")
    for m in rep["modules"]:
        print("\n%s (%s)" % (m["file"], m["tool"]))
        print("  JUnit: %s" % (", ".join("%s%s" % (c, (":" + v) if v else "") for c, v in m["junit"].items()) or "none"))
        for x in m["missing"]:
            print("  MISSING %s" % x)
        for x in m["notes"]:
            print("  NOTE    %s" % x)
    print()
    if rep["ok"]:
        print("Setup looks complete.")
    else:
        build = "toml" if rep["catalog"] else (rep["modules"][0]["dsl"] if rep["modules"] else "gradle-kts")
        kotlin = any(m.get("kotlin") for m in rep["modules"])
        print("Snippet (%s):\n" % build)
        print(deps_snippet(build, kotlin))


# ================================================================================ source parsing
def strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    return "\n".join(re.sub(r"//.*$", "", l) for l in text.splitlines())


def split_params(s: str) -> list:
    out, depth, cur = [], 0, ""
    for c in s:
        if c in "<([{":
            depth += 1
        elif c in ">)]}":
            depth -= 1
        if c == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += c
    if cur.strip():
        out.append(cur.strip())
    return out


def body_of(text: str, start: int) -> str:
    i = text.find("{", start)
    if i < 0:
        return ""
    depth = 0
    for j in range(i, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return text[i + 1:j]
    return text[i + 1:]


def parse_java(text: str) -> dict:
    src = strip_comments(text)
    strings_free = re.sub(r'"(?:\\.|[^"\\])*"', '""', src)
    pkg = re.search(r"^\s*package\s+([\w.]+)\s*;", strings_free, re.M)
    cm = re.search(r"^\s*(?:public\s+)?(?:final\s+|abstract\s+|sealed\s+|non-sealed\s+)*(class|record|interface|enum)\s+"
                   r"(\w+)(\s*<[^>{]*>)?(\s*\(([^)]*)\))?", strings_free, re.M)
    if not cm:
        raise ValueError("no top-level class, record, interface or enum found")
    kind, name = cm.group(1), cm.group(2)
    abstract = bool(re.search(r"\babstract\s+class\s+" + name + r"\b", strings_free)) or kind == "interface"
    body = body_of(strings_free, cm.end())
    # only members at depth 0 of the class body
    top, depth = [], 0
    for c in body:
        if c == "{":
            depth += 1
            if depth == 1:
                top.append("{")
            continue
        if c == "}":
            depth -= 1
            if depth == 0:
                top.append("}")
            continue
        if depth == 0:
            top.append(c)
    flat = "".join(top)
    nested_types = set(re.findall(r"\b(?:class|record|enum|interface)\s+(\w+)", body))
    methods = []
    for m in re.finditer(r"(?:^|[;}\n])\s*((?:@\w+(?:\([^)]*\))?\s+)*)((?:(?:public|protected|private|static|final|"
                         r"abstract|synchronized|default|native)\s+)*)(<[^>]+>\s+)?([\w$][\w$<>\[\],.?]*(?:\s*<[^;{}()]*>)?"
                         r"(?:\[\])*)\s+(\w+)\s*\(([^)]*)\)\s*(?:throws\s+([\w.,\s]+))?\s*[{;]", flat):
        mods, ret, mname, params, throws = m.group(2).split(), m.group(4), m.group(5), m.group(6), m.group(7)
        if "private" in mods or mname in JAVA_KEYWORDS or ret in JAVA_KEYWORDS or ret == "new" or mname == name \
                or ret in ("public", "protected", "private"):
            continue
        if kind != "interface" and not ("public" in mods or "protected" in mods or not mods or
                                        set(mods) <= {"static", "final", "synchronized"}):
            continue
        ps = []
        for p in split_params(params):
            p = re.sub(r"@\w+(\([^)]*\))?\s*", "", p).replace("final ", "").strip()
            pm = re.match(r"(.+?)\s+(\w+)$", p)
            if pm:
                ps.append((pm.group(1).replace("...", "[]").strip(), pm.group(2)))
        mbody = ""
        idx = re.search(r"\b%s\s*\(%s\)" % (re.escape(mname), re.escape(params)), strings_free)
        if idx:
            mbody = body_of(strings_free, idx.end())
        exc = set(re.findall(r"\bthrow\s+new\s+([\w.]+)\s*\(", mbody))
        exc = {"%s.%s" % (name, e) if e in nested_types else e for e in exc}
        if throws:
            exc |= {t.strip() for t in throws.split(",") if t.strip() and t.strip() not in ("Exception", "Throwable")}
        methods.append({"name": mname, "ret": ret.strip(), "params": ps, "static": "static" in mods,
                        "throws": sorted(exc)})
    ctors = []
    for m in re.finditer(r"(?:^|[;}\n])\s*((?:public|protected|private)\s+)?%s\s*\(([^)]*)\)\s*(?:throws[^{]*)?\{"
                         % re.escape(name), flat):
        if (m.group(1) or "").strip() == "private":
            continue
        ps = []
        for p in split_params(m.group(2)):
            pm = re.match(r"(?:final\s+)?(.+?)\s+(\w+)$", re.sub(r"@\w+\s*", "", p).strip())
            if pm:
                ps.append((pm.group(1), pm.group(2)))
        ctors.append(ps)
    if kind == "record":
        ctors.append([tuple(re.match(r"(.+?)\s+(\w+)$", p.strip()).groups())
                      for p in split_params(cm.group(5) or "") if re.match(r"(.+?)\s+(\w+)$", p.strip())])
    has_explicit = bool(re.search(r"(?:^|[;}\n])\s*((?:public|protected|private)\s+)?%s\s*\(" % re.escape(name), flat))
    if not ctors and not has_explicit:
        ctors = [[]]
    return {"lang": "java", "package": pkg.group(1) if pkg else "", "name": name, "kind": kind,
            "abstract": abstract, "methods": methods, "ctor": min(ctors, key=len) if ctors else None}


def parse_kotlin(text: str) -> dict:
    src = strip_comments(text)
    sf = re.sub(r'"(?:\\.|[^"\\])*"', '""', src)
    pkg = re.search(r"^\s*package\s+([\w.]+)", sf, re.M)
    cm = re.search(r"^\s*((?:public\s+|internal\s+|open\s+|abstract\s+|data\s+|sealed\s+|final\s+)*)(class|object|"
                   r"interface)\s+(\w+)(\s*<[^>]*>)?\s*(?:(?:public|internal|private|protected)?\s*constructor\s*)?"
                   r"(\(([^)]*(?:\([^)]*\)[^)]*)*)\))?", sf, re.M)
    if not cm:
        raise ValueError("no top-level class or object found")
    mods, kind, name = cm.group(1).split(), cm.group(2), cm.group(3)
    abstract = "abstract" in mods or kind == "interface" or "sealed" in mods
    body = body_of(sf, cm.end())
    methods = []
    depth, i, companion_depth = 0, 0, None
    lines = body.splitlines()
    for line in lines:
        stripped = line.strip()
        if depth == 0 or (companion_depth is not None and depth == companion_depth):
            fm = re.match(r"((?:(?:public|internal|protected|private|override|open|suspend|inline|operator|infix|"
                          r"final|abstract)\s+)*)fun\s+(?:<[^>]+>\s*)?(`[^`]+`|\w+)\s*\(([^)]*)\)\s*(?::\s*([^={]+?))?"
                          r"\s*(?:=|\{|$)", stripped)
            if fm and "private" not in fm.group(1).split() and "protected" not in fm.group(1).split():
                ps = []
                for p in split_params(fm.group(3)):
                    p = re.sub(r"@\w+(\([^)]*\))?\s*", "", p)
                    pm = re.match(r"(?:vararg\s+)?(\w+)\s*:\s*([^=]+?)(\s*=.*)?$", p.strip())
                    if pm:
                        ps.append((pm.group(2).strip(), pm.group(1)))
                start = sf.find(stripped)
                mbody = body_of(sf, start) if "{" in stripped else stripped
                exc = sorted(set(re.findall(r"\bthrow\s+([\w.]+)\s*\(", mbody)) |
                             ({"IllegalArgumentException"} if re.search(r"\brequire(NotNull)?\s*\(", mbody) else set()) |
                             ({"IllegalStateException"} if re.search(r"\b(check|checkNotNull|error)\s*\(", mbody) else set()))
                methods.append({"name": fm.group(2), "ret": (fm.group(4) or "Unit").strip(), "params": ps,
                                "static": kind == "object" or companion_depth is not None,
                                "suspend": "suspend" in fm.group(1).split(), "throws": exc})
        if re.match(r"companion\s+object\b", stripped) and depth == 0:
            companion_depth = 1
        depth += stripped.count("{") - stripped.count("}")
        if companion_depth is not None and depth < companion_depth:
            companion_depth = None
    ctor = []
    if cm.group(6):
        for p in split_params(cm.group(6)):
            p = re.sub(r"@\w+(\([^)]*\))?\s*", "", p).strip()
            pm = re.match(r"(?:(?:private|public|internal|protected|override)\s+)*(?:val\s+|var\s+)?(\w+)\s*:\s*"
                          r"([^=]+?)(\s*=.*)?$", p)
            if pm and not pm.group(3):
                ctor.append((pm.group(2).strip(), pm.group(1)))
    return {"lang": "kotlin", "package": pkg.group(1) if pkg else "", "name": name, "kind": kind,
            "abstract": abstract, "methods": methods, "ctor": None if kind == "object" else ctor}


# ================================================================================ generation
def nested_name(method: str, used: set) -> str:
    words = re.split(r"[^A-Za-z0-9]+", method.strip("`"))
    base = "".join(w[:1].upper() + w[1:] for w in words if w) or "Method"
    if base[0].isdigit():
        base = "M" + base
    n, i = base, 2
    while n in used:
        n, i = "%s%d" % (base, i), i + 1
    used.add(n)
    return n


def simple_name(t: str) -> str:
    return t.split(".")[-1]


def java_arg(t: str) -> str:
    return JAVA_LITERAL.get(t, "null")


def kt_arg(t: str) -> str:
    t = t.strip()
    if t.endswith("?"):
        return "null"
    return KT_LITERAL.get(t, 'TODO("%s")' % t.replace('"', "'"))


def gen_java(info: dict, test_name: str, parameterized: bool) -> str:
    n, var = info["name"], info["name"][0].lower() + info["name"][1:]
    imports = {"org.junit.jupiter.api.DisplayName", "org.junit.jupiter.api.Nested", "org.junit.jupiter.api.Test"}
    static = {"fail"}
    lines = []
    instance = any(not m["static"] for m in info["methods"])
    if instance and info["ctor"] is not None and not info["abstract"]:
        imports.add("org.junit.jupiter.api.BeforeEach")
        args = ", ".join(java_arg(t) for t, _ in info["ctor"])
        lines += ["    private %s %s;" % (n, var), "",
                  "    @BeforeEach", "    void setUp() {",
                  "        // TODO: pass real collaborators (fakes or mocks) for the constructor arguments" if args else
                  "        // a fresh instance for every test",
                  "        %s = new %s(%s);" % (var, n, args), "    }", ""]
    used = set()
    for m in info["methods"]:
        group = nested_name(m["name"], used)
        target = n if m["static"] else var
        args = ", ".join(java_arg(t) for t, _ in m["params"])
        sig = "%s(%s)" % (m["name"], ", ".join(simple_name(t) for t, _ in m["params"]))
        call = "%s.%s(%s)" % (target, m["name"], args)
        lines += ["    @Nested", '    @DisplayName("%s")' % sig, "    class %s {" % group, ""]
        lines += ["        @Test", "        void returnsExpectedResult() throws Exception {"]
        if m["ret"] != "void":
            lines.append("            var result = %s;" % call)
            lines.append('            fail("TODO: assert on result, e.g. assertEquals(expected, result); was " + result);')
        else:
            lines.append("            %s;" % call)
            lines.append('            fail("TODO: assert the effect of %s (state, return of a getter, a mock call)");'
                         % m["name"])
        lines += ["        }", ""]
        for exc in m["throws"]:
            static.add("assertThrows")
            lines += ["        @Test", "        void throws%s() {" % simple_name(exc),
                      "            // TODO: use the input that makes %s throw" % m["name"],
                      "            var e = assertThrows(%s.class, () -> %s);" % (exc, call),
                      '            fail("TODO: check the message: " + e.getMessage());', "        }", ""]
        simple = m["params"] and all(t in SIMPLE_JAVA for t, _ in m["params"])
        if parameterized and simple and m["ret"] != "void" and m["ret"] in SIMPLE_JAVA:
            imports |= {"org.junit.jupiter.api.Disabled", "org.junit.jupiter.params.ParameterizedTest",
                        "org.junit.jupiter.params.provider.CsvSource"}
            static.add("assertEquals")
            params = ", ".join("%s %s" % (t, p) for t, p in m["params"])
            row = ", ".join(SIMPLE_JAVA[t] for t, _ in m["params"]) + ", " + SIMPLE_JAVA[m["ret"]]
            placeholders = ", ".join("{%d}" % i for i in range(len(m["params"])))
            call_p = "%s.%s(%s)" % (target, m["name"], ", ".join(p for _, p in m["params"]))
            lines += ['        @Disabled("TODO: replace the sample row with real cases, then remove @Disabled")',
                      '        @ParameterizedTest(name = "%s(%s) = {%d}")' % (m["name"], placeholders, len(m["params"])),
                      "        @CsvSource({", '            "%s",' % row, "        })",
                      "        void cases(%s, %s expected) {" % (params, m["ret"]),
                      "            assertEquals(expected, %s);" % call_p, "        }", ""]
        lines[-1:] = ["    }", ""]
    if not info["methods"]:
        lines += ["    @Test", "    void todo() {", '        fail("TODO: no public methods found in %s");' % n, "    }"]
    head = ["package %s;" % info["package"], ""] if info["package"] else []
    for s in sorted(static):
        head.append("import static org.junit.jupiter.api.Assertions.%s;" % s)
    head.append("")
    for i in sorted(imports):
        head.append("import %s;" % i)
    head += ["", '@DisplayName("%s")' % n, "class %s {" % test_name, ""]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(head + lines + ["}", ""])


def gen_kotlin(info: dict, test_name: str, parameterized: bool) -> str:
    n, var = info["name"], info["name"][0].lower() + info["name"][1:]
    imports = {"org.junit.jupiter.api.DisplayName", "org.junit.jupiter.api.Nested", "org.junit.jupiter.api.Test",
               "org.junit.jupiter.api.fail"}
    lines = []
    instance = any(not m["static"] for m in info["methods"])
    if instance and info["ctor"] is not None and not info["abstract"]:
        imports.add("org.junit.jupiter.api.BeforeEach")
        args = ", ".join(kt_arg(t) for t, _ in info["ctor"])
        lines += ["    private lateinit var %s: %s" % (var, n), "",
                  "    @BeforeEach", "    fun setUp() {"]
        if args:
            lines.append("        // TODO: pass real collaborators (fakes or mocks); TODO(...) throws until replaced")
        lines += ["        %s = %s(%s)" % (var, n, args), "    }", ""]
    used = set()
    any_suspend = False
    for m in info["methods"]:
        group = nested_name(m["name"], used)
        target = n if m["static"] else var
        mname = m["name"]
        args = ", ".join(kt_arg(t) for t, _ in m["params"])
        call = "%s.%s(%s)" % (target, mname, args)
        sig = "%s(%s)" % (mname.strip("`"), ", ".join(t for t, _ in m["params"]))
        lines += ["    @Nested", '    @DisplayName("%s")' % sig.replace("$", "\\$"), "    inner class %s {" % group, ""]
        susp = m.get("suspend")
        any_suspend = any_suspend or susp
        lines += ["        @Test", "        %sfun `returns the expected result`() {" % ("suspend " if susp else "")]
        if m["ret"] not in ("Unit", ""):
            lines += ["            val result = %s" % call,
                      '            fail("TODO: assert on result, e.g. assertEquals(expected, result); was $result")']
        else:
            lines += ["            %s" % call,
                      '            fail("TODO: assert the effect of %s")' % mname.strip("`")]
        lines += ["        }", ""]
        for exc in m["throws"]:
            imports.add("org.junit.jupiter.api.assertThrows")
            lines += ["        @Test", "        %sfun `throws %s`() {" % ("suspend " if susp else "", simple_name(exc)),
                      "            // TODO: use the input that makes %s throw" % mname.strip("`"),
                      "            val e = assertThrows<%s> { %s }" % (exc, call),
                      '            fail("TODO: check the message: ${e.message}")', "        }", ""]
        simple = m["params"] and all(t in SIMPLE_KT for t, _ in m["params"])
        if parameterized and simple and m["ret"] in SIMPLE_KT and not susp:
            imports |= {"org.junit.jupiter.api.Disabled", "org.junit.jupiter.params.ParameterizedTest",
                        "org.junit.jupiter.params.provider.CsvSource", "org.junit.jupiter.api.Assertions.assertEquals"}
            params = ", ".join("%s: %s" % (p, t) for t, p in m["params"])
            row = ", ".join(SIMPLE_KT[t] for t, _ in m["params"]) + ", " + SIMPLE_KT[m["ret"]]
            placeholders = ", ".join("{%d}" % i for i in range(len(m["params"])))
            call_p = "%s.%s(%s)" % (target, mname, ", ".join(p for _, p in m["params"]))
            lines += ['        @Disabled("TODO: replace the sample row with real cases, then remove @Disabled")',
                      '        @ParameterizedTest(name = "%s(%s) = {%d}")' % (mname.strip("`"), placeholders,
                                                                            len(m["params"])),
                      '        @CsvSource("%s")' % row,
                      "        fun cases(%s, expected: %s) {" % (params, m["ret"]),
                      "            assertEquals(expected, %s)" % call_p, "        }", ""]
        lines[-1:] = ["    }", ""]
    if not info["methods"]:
        lines += ["    @Test", "    fun todo() {", '        fail("TODO: no public functions found in %s")' % n, "    }"]
    head = ["package %s" % info["package"], ""] if info["package"] else []
    head += ["import %s" % i for i in sorted(imports)]
    if any_suspend:
        head.append("// suspend tests need kotlinx-coroutines-core (and kotlin-reflect) on the test classpath")
    head += ["", '@DisplayName("%s")' % n, "class %s {" % test_name, ""]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(head + lines + ["}", ""])


def default_out(source: str, lang: str) -> str:
    p = os.path.abspath(source).replace("\\", "/")
    for main, test in (("/src/main/java/", "/src/test/java/"), ("/src/main/kotlin/", "/src/test/kotlin/"),
                       ("/src/commonMain/kotlin/", "/src/commonTest/kotlin/"), ("/src/jvmMain/kotlin/", "/src/jvmTest/kotlin/")):
        if main in p:
            return p.split(main)[0] + test
    return ""


def cmd_new(a) -> int:
    if not os.path.isfile(a.source):
        print("error: %s not found" % a.source, file=sys.stderr)
        return 2
    lang = "kotlin" if a.source.endswith(".kt") else "java" if a.source.endswith(".java") else None
    if not lang:
        print("error: give a .java or .kt file", file=sys.stderr)
        return 2
    try:
        info = (parse_kotlin if lang == "kotlin" else parse_java)(read(a.source))
    except ValueError as e:
        print("error: %s: %s" % (a.source, e), file=sys.stderr)
        return 2
    if info["kind"] in ("interface",) or (info["abstract"] and all(not m["static"] for m in info["methods"])):
        print("note: %s is %s; test a concrete implementation instead (or a test interface with default methods)"
              % (info["name"], "an interface" if info["kind"] == "interface" else "abstract"), file=sys.stderr)
    test_name = info["name"] + a.test_suffix
    code = (gen_kotlin if lang == "kotlin" else gen_java)(info, test_name, not a.no_parameterized)
    print("%s: %d method(s): %s" % (info["name"], len(info["methods"]),
                                    ", ".join(m["name"] for m in info["methods"]) or "none"), file=sys.stderr)
    if a.stdout:
        print(code)
        return 0
    out = a.out or default_out(a.source, lang)
    if not out:
        print("error: cannot tell the test folder (source is not under src/main/...); pass --out or --stdout",
              file=sys.stderr)
        return 2
    folder = os.path.join(out, *info["package"].split(".")) if info["package"] else out
    target = os.path.join(folder, test_name + (".kt" if lang == "kotlin" else ".java"))
    if os.path.exists(target) and not a.force:
        print("error: %s exists (pass --force to overwrite, or add the missing tests by hand)" % target, file=sys.stderr)
        return 2
    os.makedirs(folder, exist_ok=True)
    with open(target, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(code)
    print("wrote %s" % target)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Set up JUnit 6 and scaffold Java/Kotlin test classes.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("project")
    c.add_argument("--json", action="store_true")
    d = sub.add_parser("deps")
    d.add_argument("--build", choices=["gradle-kts", "gradle-groovy", "toml", "maven"], default="gradle-kts")
    d.add_argument("--kotlin", action="store_true")
    d.add_argument("--vintage", action="store_true", help="also run JUnit 4 tests (temporary, deprecated engine)")
    n = sub.add_parser("new")
    n.add_argument("source", help="the .java or .kt file to test")
    n.add_argument("--out", help="test source root, e.g. src/test/java (package folders are added)")
    n.add_argument("--stdout", action="store_true", help="print instead of writing")
    n.add_argument("--force", action="store_true")
    n.add_argument("--no-parameterized", action="store_true", help="no @ParameterizedTest templates")
    n.add_argument("--test-suffix", default="Test")
    a = ap.parse_args(argv)
    if a.cmd == "deps":
        print(deps_snippet(a.build, a.kotlin, a.vintage))
        return 0
    if a.cmd == "check":
        if not os.path.isdir(a.project):
            print("error: %s is not a folder" % a.project, file=sys.stderr)
            return 2
        rep = check(a.project)
        print(json.dumps(rep, indent=2)) if a.json else print_check(rep)
        return 0 if rep["ok"] else 1
    return cmd_new(a)


if __name__ == "__main__":
    sys.exit(main())
