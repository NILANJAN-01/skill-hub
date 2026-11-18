#!/usr/bin/env python3
"""Set up and scaffold Android UI Automator tests in Kotlin or Java.

Usage:
    python uia_scaffold.py check <project-dir> [--json]
    python uia_scaffold.py deps [--dsl kts|groovy|toml]
    python uia_scaffold.py new --name NAME --package PKG --app APP_PACKAGE
                               [--lang kotlin|java] [--kind test|page|benchmark|baseline-profile]
                               [--locators FILE.locators.json | --dump window_dump.xml]
                               [--clickable-only] [--out DIR] [--force]

check  reads settings.gradle(.kts), each module's build.gradle(.kts) and gradle/libs.versions.toml and
       reports what a UI Automator setup still needs (dependency, version, runner, androidTest folder,
       test module target, Compose testTagsAsResourceId), with the snippet to add.
deps   prints the dependency and runner snippet.
new    writes a test class, a page object (from a locator JSON made by android-uiautomator-locators, or
       straight from a uiautomator dump XML), a Macrobenchmark or a Baseline Profile generator.
       Kotlin uses the 2.4 uiAutomator { } DSL; Java uses UiDevice, By, Until and UiObject2.
       Without --out the code is printed. Existing files are never overwritten without --force.
Standard library only.

Exit codes: 0 ok, 1 check found missing setup, 2 bad usage or input.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

UIAUTOMATOR = "2.4.1"
EXT_JUNIT = "1.3.0"
RUNNER = "1.7.0"
RUNNER_CLASS = "androidx.test.runner.AndroidJUnitRunner"
SKIP_DIRS = {".git", ".gradle", ".idea", "build", "out", "node_modules", "__pycache__"}
LAYOUT_CLASSES = {"android.widget.FrameLayout", "android.widget.LinearLayout", "android.widget.RelativeLayout",
                  "android.view.ViewGroup", "android.view.View", "androidx.constraintlayout.widget.ConstraintLayout",
                  "androidx.recyclerview.widget.RecyclerView", "android.widget.ScrollView",
                  "androidx.drawerlayout.widget.DrawerLayout", "androidx.compose.ui.platform.ComposeView"}
KOTLIN_KEYWORDS = {"as", "break", "class", "continue", "do", "else", "false", "for", "fun", "if", "in", "interface",
                   "is", "null", "object", "package", "return", "super", "this", "throw", "true", "try", "typealias",
                   "val", "var", "when", "while"}
JAVA_KEYWORDS = {"abstract", "assert", "boolean", "break", "byte", "case", "catch", "char", "class", "const",
                 "continue", "default", "do", "double", "else", "enum", "extends", "final", "finally", "float", "for",
                 "goto", "if", "implements", "import", "instanceof", "int", "interface", "long", "native", "new",
                 "package", "private", "protected", "public", "return", "short", "static", "strictfp", "super",
                 "switch", "synchronized", "this", "throw", "throws", "transient", "try", "void", "volatile", "while"}


# ================================================================================ snippets
def deps_snippet(dsl: str) -> str:
    if dsl == "groovy":
        return ("android {\n    defaultConfig {\n        testInstrumentationRunner \"%s\"\n    }\n}\n\n"
                "dependencies {\n    androidTestImplementation \"androidx.test.ext:junit:%s\"\n"
                "    androidTestImplementation \"androidx.test:runner:%s\"\n"
                "    androidTestImplementation \"androidx.test.uiautomator:uiautomator:%s\"\n}\n"
                % (RUNNER_CLASS, EXT_JUNIT, RUNNER, UIAUTOMATOR))
    if dsl == "toml":
        return ("# gradle/libs.versions.toml\n[versions]\nuiautomator = \"%s\"\nandroidxJunit = \"%s\"\n"
                "androidxTestRunner = \"%s\"\n\n[libraries]\n"
                "androidx-test-uiautomator = { group = \"androidx.test.uiautomator\", name = \"uiautomator\", "
                "version.ref = \"uiautomator\" }\n"
                "androidx-test-ext-junit = { group = \"androidx.test.ext\", name = \"junit\", "
                "version.ref = \"androidxJunit\" }\n"
                "androidx-test-runner = { group = \"androidx.test\", name = \"runner\", "
                "version.ref = \"androidxTestRunner\" }\n\n"
                "# module build.gradle.kts\nandroid {\n    defaultConfig {\n"
                "        testInstrumentationRunner = \"%s\"\n    }\n}\n"
                "dependencies {\n    androidTestImplementation(libs.androidx.test.ext.junit)\n"
                "    androidTestImplementation(libs.androidx.test.runner)\n"
                "    androidTestImplementation(libs.androidx.test.uiautomator)\n}\n"
                % (UIAUTOMATOR, EXT_JUNIT, RUNNER, RUNNER_CLASS))
    return ("android {\n    defaultConfig {\n        testInstrumentationRunner = \"%s\"\n    }\n}\n\n"
            "dependencies {\n    androidTestImplementation(\"androidx.test.ext:junit:%s\")\n"
            "    androidTestImplementation(\"androidx.test:runner:%s\")\n"
            "    androidTestImplementation(\"androidx.test.uiautomator:uiautomator:%s\")\n}\n"
            % (RUNNER_CLASS, EXT_JUNIT, RUNNER, UIAUTOMATOR))


# ================================================================================ check
def read(path: str) -> str:
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        return fh.read()


def strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return "\n".join(re.sub(r"(^|[^:])//.*$", r"\1", line) for line in text.splitlines())


def find_modules(root: str) -> list:
    mods = []
    for name in ("settings.gradle.kts", "settings.gradle"):
        p = os.path.join(root, name)
        if os.path.isfile(p):
            text = strip_comments(read(p))
            for m in re.finditer(r"""["'](:[\w.:-]+)["']""", text):
                if re.search(r"include", text[max(0, m.start() - 200):m.start()]):
                    mods.append(m.group(1))
    seen, out = set(), []
    for m in mods:
        if m not in seen:
            seen.add(m)
            out.append(m)
    if not out:                                   # no settings file: every folder with a build file
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
            if dirpath != root and ("build.gradle" in filenames or "build.gradle.kts" in filenames):
                out.append(":" + os.path.relpath(dirpath, root).replace(os.sep, ":"))
    return out


def toml_catalog(root: str) -> tuple:
    p = os.path.join(root, "gradle", "libs.versions.toml")
    if not os.path.isfile(p):
        return {}, {}
    versions, libs, sect = {}, {}, None
    for raw in read(p).splitlines():
        s = raw.split("#", 1)[0].strip()
        if s.startswith("["):
            sect = s.strip("[]").strip()
            continue
        m = re.match(r"""([\w.-]+)\s*=\s*(.+)$""", s)
        if not m:
            continue
        key, val = m.group(1), m.group(2)
        if sect == "versions":
            versions[key] = val.strip().strip("\"'")
        elif sect == "libraries":
            coord = re.search(r"""module\s*=\s*["']([^"']+)["']""", val)
            g = re.search(r"""group\s*=\s*["']([^"']+)["']""", val)
            n = re.search(r"""name\s*=\s*["']([^"']+)["']""", val)
            if coord:
                coord = coord.group(1)
            elif g and n:
                coord = "%s:%s" % (g.group(1), n.group(1))
            elif re.match(r"""["'][^"']+:[^"']+:[^"']+["']""", val.strip()):
                parts = val.strip().strip("\"'").split(":")
                coord, versions["_inline_" + key] = ":".join(parts[:2]), parts[2]
                libs[key] = (coord, versions["_inline_" + key])
                continue
            else:
                continue
            vr = re.search(r"""version\.ref\s*=\s*["']([^"']+)["']""", val)
            vv = re.search(r"""version\s*=\s*["']([^"']+)["']""", val)
            libs[key] = (coord, versions.get(vr.group(1), "") if vr else (vv.group(1) if vv else ""))
    return versions, libs


def accessor(key: str) -> str:
    return "libs." + re.sub(r"[-_]", ".", key)


def check_module(root: str, mod: str, catalog_libs: dict) -> dict:
    d = os.path.join(root, *mod.strip(":").split(":"))
    build = None
    for name in ("build.gradle.kts", "build.gradle"):
        if os.path.isfile(os.path.join(d, name)):
            build = os.path.join(d, name)
            break
    info = {"module": mod, "path": os.path.relpath(d, root).replace(os.sep, "/"), "build_file": None,
            "type": "unknown", "dsl": None, "uiautomator": None, "runner": None, "ext_junit": False,
            "android_test_dir": False, "target_project": None, "compose": False, "test_tags_as_resource_id": False,
            "missing": [], "notes": []}
    if not build:
        info["missing"].append("no build.gradle(.kts) in %s" % info["path"])
        return info
    info["build_file"] = os.path.relpath(build, root).replace(os.sep, "/")
    info["dsl"] = "kts" if build.endswith(".kts") else "groovy"
    text = strip_comments(read(build))
    if re.search(r"com\.android\.application|android\.application\b|androidApplication", text):
        info["type"] = "application"
    elif re.search(r"com\.android\.test|android\.test\b|androidTest\)", text) and \
            re.search(r"targetProjectPath", text):
        info["type"] = "test"
    elif re.search(r"com\.android\.library|android\.library\b|androidLibrary", text):
        info["type"] = "library"
    elif re.search(r"com\.android\.test", text):
        info["type"] = "test"
    if info["type"] == "unknown":
        info["notes"].append("not an Android module (no com.android.* plugin found)")
        return info
    tp = re.search(r"""targetProjectPath\s*(?:=\s*)?["']([^"']+)["']""", text)
    info["target_project"] = tp.group(1) if tp else None
    m = re.search(r"""androidx\.test\.uiautomator:uiautomator:([^"'$\s)]+)""", text)
    if m:
        info["uiautomator"] = m.group(1)
    else:
        for key, (coord, ver) in catalog_libs.items():
            if coord == "androidx.test.uiautomator:uiautomator" and accessor(key) in text:
                info["uiautomator"] = ver or "?"
    if "uiautomator-v18" in text:
        info["uiautomator"] = "support-library"
    info["ext_junit"] = "androidx.test.ext:junit" in text or any(
        coord == "androidx.test.ext:junit" and accessor(k) in text for k, (coord, _v) in catalog_libs.items())
    r = re.search(r"""testInstrumentationRunner\s*(?:=\s*)?["']([^"']+)["']""", text)
    info["runner"] = r.group(1) if r else None
    info["compose"] = bool(re.search(r"compose\s*=\s*true|buildFeatures\s*\{[^}]*compose|kotlin\.plugin\.compose|"
                                     r"plugin\.compose|compose\.compiler", text, re.S))
    src = os.path.join(d, "src")
    info["android_test_dir"] = os.path.isdir(os.path.join(src, "androidTest")) or info["type"] == "test"
    if os.path.isdir(src):
        for dirpath, dirnames, filenames in os.walk(src):
            dirnames[:] = [x for x in dirnames if x not in SKIP_DIRS]
            for f in filenames:
                if f.endswith(".kt") and "testTagsAsResourceId" in read(os.path.join(dirpath, f)):
                    info["test_tags_as_resource_id"] = True
                    break
            if info["test_tags_as_resource_id"]:
                break

    if info["type"] in ("application", "library", "test"):
        if info["uiautomator"] is None:
            info["missing"].append("androidTestImplementation androidx.test.uiautomator:uiautomator:%s" % UIAUTOMATOR)
        elif info["uiautomator"] == "support-library":
            info["missing"].append("replace com.android.support.test.uiautomator with androidx.test.uiautomator:%s"
                                   % UIAUTOMATOR)
        elif info["uiautomator"] != UIAUTOMATOR and info["uiautomator"] != "?":
            info["notes"].append("uiautomator %s: the uiAutomator { } DSL needs 2.4.0+, latest stable is %s"
                                 % (info["uiautomator"], UIAUTOMATOR))
        if not info["runner"]:
            info["missing"].append('testInstrumentationRunner = "%s" in defaultConfig' % RUNNER_CLASS)
        if not info["ext_junit"]:
            info["missing"].append("androidTestImplementation androidx.test.ext:junit:%s (AndroidJUnit4)" % EXT_JUNIT)
        if not info["android_test_dir"] and info["type"] != "test":
            info["notes"].append("no src/androidTest folder yet: put tests in %s/src/androidTest/java/<package>/"
                                 % info["path"])
        if info["type"] == "test" and not info["target_project"]:
            info["missing"].append("targetProjectPath = \":app\" (com.android.test modules need a target)")
        if info["compose"] and not info["test_tags_as_resource_id"]:
            info["notes"].append("Compose is enabled but no testTagsAsResourceId found: set "
                                 "Modifier.semantics { testTagsAsResourceId = true } high in the tree so "
                                 "Modifier.testTag values are visible to UI Automator")
    return info


def check(root: str) -> dict:
    _versions, libs = toml_catalog(root)
    mods = find_modules(root)
    results = [check_module(root, m, libs) for m in mods]
    android = [r for r in results if r["type"] != "unknown"]
    with_ui = [r for r in android if r["uiautomator"] not in (None, "support-library")]
    return {"root": root, "modules": results, "catalog": bool(libs),
            "ok": bool(with_ui) and all(not r["missing"] for r in with_ui)}


def print_check(rep: dict) -> None:
    print("UI Automator setup check: %s" % rep["root"])
    if not rep["modules"]:
        print("  no Gradle modules found (is this the project root with settings.gradle?)")
    for r in rep["modules"]:
        if r["type"] == "unknown":
            continue
        print("\nmodule %s (%s, %s)" % (r["module"], r["type"], r["build_file"] or "no build file"))
        print("  uiautomator: %s   runner: %s   ext.junit: %s   androidTest folder: %s" %
              (r["uiautomator"] or "-", r["runner"] or "-", "yes" if r["ext_junit"] else "no",
               "yes" if r["android_test_dir"] else "no"))
        if r["target_project"]:
            print("  targetProjectPath: %s" % r["target_project"])
        for m in r["missing"]:
            print("  MISSING %s" % m)
        for n in r["notes"]:
            print("  NOTE    %s" % n)
    print()
    if rep["ok"]:
        print("Setup looks complete.")
    else:
        dsl = "toml" if rep["catalog"] else next((r["dsl"] for r in rep["modules"] if r["dsl"]), "kts")
        print("Add to the module that holds the UI tests (%s):\n" % dsl)
        print(deps_snippet(dsl))


# ================================================================================ elements
def keyword(raw: str, used: set, fallback: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", raw or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_").lower()
    s = s[:40].strip("_") or fallback
    if s[0].isdigit():
        s = "el_" + s
    base, i = s, 2
    while s in used:
        s = "%s_%d" % (base, i)
        i += 1
    used.add(s)
    return s


def camel(s: str, upper: bool = False) -> str:
    parts = [p for p in s.split("_") if p]
    out = parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:]) if parts else "element"
    if upper:
        out = out[:1].upper() + out[1:]
    return out


def elements_from_locators(path: str) -> list:
    data = json.loads(read(path))
    if not isinstance(data, dict) or "elements" not in data:
        raise ValueError("%s is not a locator file from android-uiautomator-locators (no 'elements')" % path)
    out = []
    for e in data["elements"]:
        if e.get("fragile") or e.get("strategy") == "class_instance":
            continue
        out.append({"keyword": e.get("keyword") or "", "resource_id": e.get("resource_id") or "",
                    "text": e.get("text") or "", "desc": e.get("content_desc") or "", "class": e.get("class") or "",
                    "clickable": bool(e.get("clickable")), "scrollable": bool(e.get("scrollable")),
                    "strategy": e.get("strategy") or "", "instance": e.get("instance"),
                    "occurrences": e.get("occurrences")})
    return out


def elements_from_dump(path: str) -> list:
    raw = read(path)
    start = raw.find("<")
    if start < 0 or "<node" not in raw:
        raise ValueError("%s is not a uiautomator dump (no <node> elements)" % path)
    try:
        root = ET.fromstring(raw[start:].split("UI hierchary dumped to")[0].strip())
    except ET.ParseError as e:
        raise ValueError("invalid XML in %s: %s" % (path, e))
    nodes = list(root.iter("node"))
    id_count, text_count = {}, {}
    for n in nodes:
        rid = n.get("resource-id", "")
        if rid:
            id_count[rid] = id_count.get(rid, 0) + 1
        t = n.get("text", "")
        if t:
            text_count[t] = text_count.get(t, 0) + 1
    out, text_seen = [], {}
    for n in nodes:
        rid, text, desc = n.get("resource-id", ""), n.get("text", ""), n.get("content-desc", "")
        cls = n.get("class", "")
        if not (rid or text or desc):
            continue
        e = {"keyword": "", "resource_id": rid, "text": text, "desc": desc, "class": cls,
             "clickable": n.get("clickable") == "true", "scrollable": n.get("scrollable") == "true",
             "strategy": "", "instance": None, "occurrences": None}
        if rid and id_count[rid] == 1:
            e["strategy"] = "resource_id"
        elif rid and desc:
            e["strategy"] = "resource_id+content_desc"
        elif rid and text:
            e["strategy"] = "resource_id+text"
        elif desc:
            e["strategy"] = "content_desc"
        elif text:
            e["strategy"] = "text"
            if text_count[text] > 1:
                e["instance"] = text_seen.get(text, 0)
                text_seen[text] = e["instance"] + 1
        else:                                     # repeated id with no text or description: list container
            e["strategy"] = "resource_id"
            e["occurrences"] = id_count[rid]
            if any(x["resource_id"] == rid and x["strategy"] == "resource_id" for x in out):
                continue
        out.append(e)
    return out


def filter_elements(elems: list, clickable_only: bool) -> list:
    out = []
    for e in elems:
        if clickable_only and not (e["clickable"] or "EditText" in e["class"]):
            continue
        if e["class"] in LAYOUT_CLASSES and not (e["clickable"] or e["scrollable"] or e["text"] or e["desc"]) \
                and not clickable_only and e["strategy"] == "resource_id" and not e.get("occurrences"):
            continue                              # bare layout container
        out.append(e)
    return out


def disambiguate(elems: list) -> list:
    """Repeated text/description: add the class name when that makes each match unique (no instance needed)."""
    groups = {}
    for e in elems:
        if e.get("instance") is not None:
            groups.setdefault((e["strategy"], e["resource_id"], e["text"], e["desc"]), []).append(e)
    for members in groups.values():
        classes = [m["class"] for m in members]
        if len(members) > 1 and all(classes) and len(set(classes)) == len(classes):
            for m in members:
                m["use_class"], m["instance"] = True, None
    return elems


def name_elements(elems: list, lang: str) -> list:
    used = set()
    reserved = KOTLIN_KEYWORDS if lang == "kotlin" else JAVA_KEYWORDS
    for i, e in enumerate(elems):
        base = e["keyword"]
        if not base:
            short = e["resource_id"].split("/")[-1] if e["resource_id"] else ""
            label = e["desc"] or e["text"]
            if e["strategy"].startswith("resource_id+") and label:
                base = "%s_%s" % (short, label)
            else:
                base = short or label
        k = keyword(base, used, "element_%d" % (i + 1))
        member = camel(k)
        if member in reserved:
            member += "Element"
        e["member"] = member
        e["const"] = k.upper()
    return elems


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("\"", "\\\"").replace("$", "\\$").replace("\n", "\\n")


def esc_java(s: str) -> str:
    return s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n")


def kotlin_predicate(e: dict) -> str:
    pred = _kotlin_predicate(e)
    if e.get("use_class"):
        pred += ' && className?.toString() == "%s"' % esc(e["class"])
    return pred


def _kotlin_predicate(e: dict) -> str:
    rid, text, desc = e["resource_id"], e["text"], e["desc"]
    id_part = 'viewIdResourceName == "%s"' % esc(rid) if rid else ""
    st = e["strategy"]
    if st == "resource_id" and rid:
        return id_part
    if st == "resource_id+content_desc":
        return '%s && contentDescription?.toString() == "%s"' % (id_part, esc(desc))
    if st == "resource_id+text":
        return '%s && textAsString() == "%s"' % (id_part, esc(text))
    if st == "content_desc" or (desc and not text):
        return 'contentDescription?.toString() == "%s"' % esc(desc)
    return 'textAsString() == "%s"' % esc(text)


def java_selector(e: dict) -> str:
    sel = _java_selector(e)
    if e.get("use_class"):
        sel += '.clazz("%s")' % esc_java(e["class"])
    return sel


def _java_selector(e: dict) -> str:
    rid, text, desc = e["resource_id"], e["text"], e["desc"]
    st = e["strategy"]
    if st == "resource_id" and rid:
        return 'By.res("%s")' % esc_java(rid)
    if st == "resource_id+content_desc":
        return 'By.res("%s").desc("%s")' % (esc_java(rid), esc_java(desc))
    if st == "resource_id+text":
        return 'By.res("%s").text("%s")' % (esc_java(rid), esc_java(text))
    if st == "content_desc" or (desc and not text):
        return 'By.desc("%s")' % esc_java(desc)
    return 'By.text("%s")' % esc_java(text)


# ================================================================================ generators
def gen_kotlin_test(name: str, pkg: str, app: str, page: str | None) -> str:
    page_lines = ""
    if page:
        page_lines = ("\n        val screen = %s(this)\n"
                      "        // Example: screen.<element>.click()\n" % page)
    return '''package %(pkg)s

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.uiautomator.uiAutomator
import androidx.test.uiautomator.watcher.PermissionDialog
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

/** UI Automator test for %(app)s (modern 2.4 API). */
@RunWith(AndroidJUnit4::class)
class %(name)s {

    @Test
    fun appStartsAndShowsItsUi() = uiAutomator {
        // Accept a runtime permission dialog if one appears; unregistered when the block ends.
        watchFor(PermissionDialog) { clickAllow() }

        startApp(APP_PACKAGE) // blocks until a view of the package is visible
        assertTrue(waitForAppToBeVisible(APP_PACKAGE))
%(page)s
        // Find elements with a predicate on AccessibilityNodeInfo; onElement waits up to 10 s, then throws
        // ElementNotFoundException. Views: viewIdResourceName == "%(app)s:id/<name>" or
        // simpleViewResourceName() == "<name>". Compose: the testTag (needs testTagsAsResourceId).
        // Text: textAsString() == "..." (text is a CharSequence).
        // onElement { textAsString() == "Sign in" }.click()
        // onElement { simpleViewResourceName() == "email" }.setText("user@example.com")
        // onElementOrNull(timeoutMs = 2_000) { textAsString() == "Skip" }?.click()
    }

    private companion object {
        const val APP_PACKAGE = "%(app)s"
    }
}
''' % {"pkg": pkg, "name": name, "app": app, "page": page_lines}


def gen_java_test(name: str, pkg: str, app: str, page: str | None) -> str:
    page_lines = ""
    if page:
        page_lines = ("\n        %s screen = new %s(device);\n"
                      "        // Example: screen.<element>().click();\n" % (page, page))
    return '''package %(pkg)s;

import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

import android.content.Context;
import android.content.Intent;

import androidx.test.core.app.ApplicationProvider;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import androidx.test.uiautomator.By;
import androidx.test.uiautomator.UiDevice;
import androidx.test.uiautomator.UiObject2;
import androidx.test.uiautomator.Until;

import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;

/** UI Automator test for %(app)s (UiDevice, By, Until, UiObject2). */
@RunWith(AndroidJUnit4.class)
public class %(name)s {

    private static final String APP_PACKAGE = "%(app)s";
    private static final long TIMEOUT_MS = 10_000;

    private UiDevice device;

    @Before
    public void startAppFromHomeScreen() {
        device = UiDevice.getInstance(InstrumentationRegistry.getInstrumentation());
        device.pressHome();
        String launcher = device.getLauncherPackageName();
        assertNotNull("no launcher package", launcher);
        device.wait(Until.hasObject(By.pkg(launcher).depth(0)), TIMEOUT_MS);

        Context context = ApplicationProvider.getApplicationContext();
        Intent intent = context.getPackageManager().getLaunchIntentForPackage(APP_PACKAGE);
        // null on Android 11+ when the test APK cannot see the app: add <queries> to the androidTest manifest
        assertNotNull("no launch intent for " + APP_PACKAGE, intent);
        intent.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TASK);
        context.startActivity(intent);
        assertTrue("app did not appear",
                device.wait(Until.hasObject(By.pkg(APP_PACKAGE).depth(0)), TIMEOUT_MS));
    }

    @Test
    public void appStartsAndShowsItsUi() {
        assertTrue(device.hasObject(By.pkg(APP_PACKAGE)));
%(page)s
        // Wait for an element instead of sleeping; findObject returns null when it is not there yet.
        // UiObject2 signIn = device.wait(Until.findObject(By.res(APP_PACKAGE, "sign_in")), TIMEOUT_MS);
        // assertNotNull("sign in button", signIn);
        // signIn.clickAndWait(Until.newWindow(), TIMEOUT_MS);
    }

    @SuppressWarnings("unused")
    private UiObject2 waitFor(androidx.test.uiautomator.BySelector selector) {
        UiObject2 found = device.wait(Until.findObject(selector), TIMEOUT_MS);
        assertNotNull("not found within " + TIMEOUT_MS + " ms: " + selector, found);
        return found;
    }
}
''' % {"pkg": pkg, "name": name, "app": app, "page": page_lines}


def gen_kotlin_page(name: str, pkg: str, app: str, elems: list, source: str) -> str:
    lines = []
    for e in elems:
        doc = describe(e)
        pred = kotlin_predicate(e)
        if e.get("instance") is not None:
            lines.append("    /** %s (match %d of several) */\n    val %s: UiObject2\n        get() = ui.onElements { %s }[%d]\n"
                         % (doc, e["instance"], e["member"], pred, e["instance"]))
        elif e.get("occurrences"):
            lines.append("    /** %s (%d on screen, one per row) */\n    val %s: List<UiObject2>\n"
                         "        get() = ui.onElements { %s }\n" % (doc, e["occurrences"], e["member"], pred))
        else:
            lines.append("    /** %s */\n    val %s: UiObject2\n        get() = ui.onElement { %s }\n"
                         % (doc, e["member"], pred))
    needs_text = any("textAsString()" in kotlin_predicate(e) for e in elems)
    imports = ["androidx.test.uiautomator.UiAutomatorTestScope", "androidx.test.uiautomator.UiObject2"]
    if needs_text:
        imports.append("androidx.test.uiautomator.textAsString")
    body = "\n".join(lines) if lines else "    // No elements with an id, text or description were found.\n"
    return '''package %(pkg)s

%(imports)s

/**
 * Page object for a screen of %(app)s, generated from %(source)s.
 * Use inside uiAutomator { }: `val screen = %(name)s(this)`. Every property looks the element up again
 * (onElement waits up to 10 s), so it never holds a stale UiObject2. Rename members to match the screen.
 */
class %(name)s(private val ui: UiAutomatorTestScope) {

%(body)s
    /** True when the screen is showing. Replace with an element unique to this screen. */
    fun isShown(timeoutMs: Long = 10_000): Boolean = ui.waitForAppToBeVisible("%(app)s", timeoutMs)
}
''' % {"pkg": pkg, "imports": "\n".join("import " + i for i in imports), "app": app, "source": source,
       "name": name, "body": body}


def gen_java_page(name: str, pkg: str, app: str, elems: list, source: str) -> str:
    consts, methods = [], []
    for e in elems:
        consts.append("    /** %s */\n    public static final BySelector %s = %s;" % (describe(e), e["const"],
                                                                                   java_selector(e)))
        if e.get("instance") is not None:
            methods.append("    public UiObject2 %s() {\n        return nth(%s, %d);\n    }" %
                           (e["member"], e["const"], e["instance"]))
        elif e.get("occurrences"):
            methods.append("    public List<UiObject2> %s() {\n        return all(%s);\n    }" %
                           (e["member"], e["const"]))
        else:
            methods.append("    public UiObject2 %s() {\n        return find(%s);\n    }" % (e["member"], e["const"]))
    return '''package %(pkg)s;

import static org.junit.Assert.assertNotNull;

import androidx.test.uiautomator.By;
import androidx.test.uiautomator.BySelector;
import androidx.test.uiautomator.UiDevice;
import androidx.test.uiautomator.UiObject2;
import androidx.test.uiautomator.Until;

import java.util.List;

/**
 * Page object for a screen of %(app)s, generated from %(source)s.
 * Every method waits for the element (up to TIMEOUT_MS) and fails with the selector if it is missing,
 * so a test never gets a null UiObject2. Rename members to match the screen.
 */
public final class %(name)s {

    public static final long TIMEOUT_MS = 10_000;

%(consts)s

    private final UiDevice device;

    public %(name)s(UiDevice device) {
        this.device = device;
    }

    /** True when the screen is showing. Replace with an element unique to this screen. */
    public boolean isShown() {
        return device.wait(Until.hasObject(By.pkg("%(app)s").depth(0)), TIMEOUT_MS);
    }

%(methods)s

    private UiObject2 find(BySelector selector) {
        UiObject2 found = device.wait(Until.findObject(selector), TIMEOUT_MS);
        assertNotNull("not found within " + TIMEOUT_MS + " ms: " + selector, found);
        return found;
    }

    private List<UiObject2> all(BySelector selector) {
        List<UiObject2> found = device.wait(Until.findObjects(selector), TIMEOUT_MS);
        assertNotNull("not found within " + TIMEOUT_MS + " ms: " + selector, found);
        return found;
    }

    private UiObject2 nth(BySelector selector, int index) {
        List<UiObject2> found = all(selector);
        if (index >= found.size()) {
            throw new AssertionError("only " + found.size() + " matches for " + selector);
        }
        return found.get(index);
    }
}
''' % {"pkg": pkg, "app": app, "source": source, "name": name,
       "consts": "\n".join(consts) if consts else "    // No elements with an id, text or description were found.",
       "methods": "\n\n".join(methods)}


def describe(e: dict) -> str:
    bits = []
    if e["resource_id"]:
        bits.append("id " + e["resource_id"])
    if e["desc"] and not e.get("occurrences"):
        bits.append('desc "%s"' % e["desc"])
    if e["text"] and not e.get("occurrences"):
        bits.append('text "%s"' % e["text"])
    if e["class"]:
        bits.append(e["class"].rsplit(".", 1)[-1])
    return ", ".join(bits).replace("*/", "* /")


def gen_kotlin_benchmark(name: str, pkg: str, app: str) -> str:
    return '''package %(pkg)s

import androidx.benchmark.macro.FrameTimingMetric
import androidx.benchmark.macro.StartupMode
import androidx.benchmark.macro.StartupTimingMetric
import androidx.benchmark.macro.junit4.MacrobenchmarkRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.uiautomator.Direction
import androidx.test.uiautomator.uiAutomator
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Macrobenchmark for %(app)s driven by UI Automator. Lives in a com.android.test module whose
 * targetProjectPath points at the app; benchmark a non-debuggable, profileable build on a real device.
 */
@RunWith(AndroidJUnit4::class)
class %(name)s {

    @get:Rule
    val benchmarkRule = MacrobenchmarkRule()

    @Test
    fun startup() = benchmarkRule.measureRepeated(
        packageName = TARGET_PACKAGE,
        metrics = listOf(StartupTimingMetric()),
        iterations = 5,
        startupMode = StartupMode.COLD,
    ) {
        uiAutomator {
            startApp(TARGET_PACKAGE)
            // For time to full display, wait for content that loads last, e.g.:
            // onElement { viewIdResourceName == "%(app)s:id/feed" }
        }
    }

    @Test
    fun scrollMainList() = benchmarkRule.measureRepeated(
        packageName = TARGET_PACKAGE,
        metrics = listOf(FrameTimingMetric()),
        iterations = 5,
        startupMode = StartupMode.WARM,
        setupBlock = { pressHome() },
    ) {
        startActivityAndWait()
        uiAutomator {
            val list = onElement { isScrollable }
            list.setGestureMargin(device.displayWidth / 5) // keep away from the system gesture area
            list.fling(Direction.DOWN)
            list.fling(Direction.UP)
        }
    }

    private companion object {
        const val TARGET_PACKAGE = "%(app)s"
    }
}
''' % {"pkg": pkg, "name": name, "app": app}


def gen_kotlin_baseline(name: str, pkg: str, app: str) -> str:
    return '''package %(pkg)s

import androidx.benchmark.macro.junit4.BaselineProfileRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.uiautomator.Direction
import androidx.test.uiautomator.uiAutomator
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Baseline Profile generator for %(app)s. Run with ./gradlew :app:generateBaselineProfile
 * (rooted device, emulator, Gradle Managed Device with systemImageSource = "aosp", or Android 13+).
 */
@RunWith(AndroidJUnit4::class)
class %(name)s {

    @get:Rule
    val baselineProfileRule = BaselineProfileRule()

    @Test
    fun startup() = baselineProfileRule.collect(
        packageName = TARGET_PACKAGE,
        includeInStartupProfile = true,
        profileBlock = { uiAutomator { startApp(TARGET_PACKAGE) } },
    )

    @Test
    fun criticalUserJourney() = baselineProfileRule.collect(
        packageName = TARGET_PACKAGE,
        includeInStartupProfile = false,
        profileBlock = {
            uiAutomator {
                startApp(TARGET_PACKAGE)
                // Drive the journey you want pre-compiled; onElement waits, so the run is deterministic.
                onElementOrNull { isScrollable }?.fling(Direction.DOWN)
            }
        },
    )

    private companion object {
        const val TARGET_PACKAGE = "%(app)s"
    }
}
''' % {"pkg": pkg, "name": name, "app": app}


# ================================================================================ main
PKG_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")
CLASS_RE = re.compile(r"^[A-Z][A-Za-z0-9_]*$")


def cmd_new(a) -> int:
    for label, val, rx in (("--name", a.name, CLASS_RE), ("--package", a.package, PKG_RE), ("--app", a.app, PKG_RE)):
        if not rx.match(val or ""):
            print("error: %s %r is not valid (%s)" % (label, val, "UpperCamelCase class name" if rx is CLASS_RE
                                                   else "dotted package name"), file=sys.stderr)
            return 2
    if a.kind in ("benchmark", "baseline-profile") and a.lang == "java":
        print("error: --kind %s is generated in Kotlin only (the official Macrobenchmark and Baseline Profile "
              "samples are Kotlin; Android Studio's Baseline Profile Generator template can create Java)" % a.kind,
              file=sys.stderr)
        return 2
    page_name, page_src = None, None
    files = []
    ext = ".kt" if a.lang == "kotlin" else ".java"
    if a.locators or a.dump or a.kind == "page":
        if not (a.locators or a.dump):
            print("error: --kind page needs --locators FILE or --dump FILE", file=sys.stderr)
            return 2
        src = a.locators or a.dump
        try:
            elems = elements_from_locators(src) if a.locators else elements_from_dump(src)
        except (OSError, ValueError, json.JSONDecodeError) as e:
            print("error: %s" % e, file=sys.stderr)
            return 2
        elems = name_elements(disambiguate(filter_elements(elems, a.clickable_only)), a.lang)
        if elems and not any(e["resource_id"] for e in elems):
            print("note: the screen has no resource-ids, so the page object matches text and descriptions, which "
                  "change with the language. For Compose, set Modifier.semantics { testTagsAsResourceId = true } and "
                  "give elements Modifier.testTag(...).", file=sys.stderr)
        page_name = a.name if a.kind == "page" else (re.sub(r"Test$", "", a.name) or a.name) + "Screen"
        page_src = os.path.basename(src)
        code = (gen_kotlin_page if a.lang == "kotlin" else gen_java_page)(page_name, a.package, a.app, elems, page_src)
        files.append((page_name + ext, code))
        print("page object %s: %d element(s) from %s" % (page_name, len(elems), page_src), file=sys.stderr)
    if a.kind == "test":
        code = (gen_kotlin_test if a.lang == "kotlin" else gen_java_test)(a.name, a.package, a.app, page_name)
        files.insert(0, (a.name + ext, code))
    elif a.kind == "benchmark":
        files.insert(0, (a.name + ".kt", gen_kotlin_benchmark(a.name, a.package, a.app)))
    elif a.kind == "baseline-profile":
        files.insert(0, (a.name + ".kt", gen_kotlin_baseline(a.name, a.package, a.app)))

    if not a.out:
        for fname, code in files:
            print("// ===== %s =====" % fname)
            print(code)
        return 0
    out_dir = os.path.join(a.out, *a.package.split(".")) if not a.flat else a.out
    for fname, _code in files:
        target = os.path.join(out_dir, fname)
        if os.path.exists(target) and not a.force:
            print("error: %s exists (pass --force to overwrite)" % target, file=sys.stderr)
            return 2
    os.makedirs(out_dir, exist_ok=True)
    for fname, code in files:
        target = os.path.join(out_dir, fname)
        with open(target, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(code)
        print("wrote %s" % target)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Set up and scaffold UI Automator tests (Kotlin/Java).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="check a project's UI Automator setup")
    c.add_argument("project")
    c.add_argument("--json", action="store_true")
    d = sub.add_parser("deps", help="print the dependency snippet")
    d.add_argument("--dsl", choices=["kts", "groovy", "toml"], default="kts")
    n = sub.add_parser("new", help="generate a test, page object, benchmark or baseline profile generator")
    n.add_argument("--name", required=True, help="class name, e.g. LoginTest")
    n.add_argument("--package", required=True, help="package of the test class, e.g. com.example.app.test")
    n.add_argument("--app", required=True, help="package of the app under test, e.g. com.example.app")
    n.add_argument("--lang", choices=["kotlin", "java"], default="kotlin")
    n.add_argument("--kind", choices=["test", "page", "benchmark", "baseline-profile"], default="test")
    g = n.add_mutually_exclusive_group()
    g.add_argument("--locators", help="locator JSON written by android-uiautomator-locators")
    g.add_argument("--dump", help="uiautomator dump XML (window_dump.xml)")
    n.add_argument("--clickable-only", action="store_true", help="page object: only clickable elements and inputs")
    n.add_argument("--out", help="source root, e.g. app/src/androidTest/java (package folders are added)")
    n.add_argument("--flat", action="store_true", help="write straight into --out without package folders")
    n.add_argument("--force", action="store_true", help="overwrite existing files")
    a = ap.parse_args(argv)
    if a.cmd == "deps":
        print(deps_snippet(a.dsl))
        return 0
    if a.cmd == "check":
        if not os.path.isdir(a.project):
            print("error: %s is not a folder" % a.project, file=sys.stderr)
            return 2
        rep = check(a.project)
        if a.json:
            print(json.dumps(rep, indent=2))
        else:
            print_check(rep)
        return 0 if rep["ok"] else 1
    return cmd_new(a)


if __name__ == "__main__":
    sys.exit(main())
