import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gradle_doctor as gd  # noqa: E402

FIX = Path(__file__).parent / "fixtures"


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = gd.main(list(argv))
    return rc, out.getvalue(), err.getvalue()


def make_project(root, gradle="8.7", agp="8.5.0", extra_build=""):
    root = Path(root)
    (root / "gradle" / "wrapper").mkdir(parents=True)
    (root / "gradle" / "wrapper" / "gradle-wrapper.properties").write_text(
        "distributionUrl=https\\://services.gradle.org/distributions/gradle-%s-bin.zip\n" % gradle)
    (root / "gradle" / "libs.versions.toml").write_text(
        '[versions]\nagp = "%s"\nkotlin = "2.0.21"\n\n[libraries]\n\n[plugins]\n'
        'android-application = { id = "com.android.application", version.ref = "agp" }\n' % agp)
    (root / "settings.gradle.kts").write_text(
        "pluginManagement { repositories { google(); mavenCentral() } }\n"
        "dependencyResolutionManagement { repositories { google(); mavenCentral() } }\n")
    (root / "app").mkdir()
    (root / "app" / "build.gradle.kts").write_text(
        "plugins { alias(libs.plugins.android.application) }\ndependencies {\n    implementation(libs.core)\n}\n" + extra_build)
    (root / "gradlew").write_text("#!/bin/sh\n")
    (root / "gradlew.bat").write_text("")
    return root


class Versions(unittest.TestCase):
    def test_vtuple(self):
        self.assertEqual(gd.vtuple("8.10.2"), (8, 10, 2))
        self.assertEqual(gd.vtuple("9.5.0-rc01"), (9, 5, 0))
        self.assertLess(gd.vtuple("8.9"), gd.vtuple("8.10"))

    def test_java_major(self):
        self.assertEqual(gd.java_major('openjdk version "17.0.9" 2023-10-17'), 17)
        self.assertEqual(gd.java_major('java version "1.8.0_391"'), 8)
        self.assertEqual(gd.java_major('openjdk version "21" 2023-09-19'), 21)

    def test_min_gradle(self):
        self.assertEqual(gd.min_gradle_for_agp("9.5.1"), ("9.6.0", True))
        self.assertEqual(gd.min_gradle_for_agp("8.5.2")[0], "8.7")
        need, exact = gd.min_gradle_for_agp("9.3.0")
        self.assertFalse(exact)
        self.assertEqual(need, "9.1.0")


class Diagnose(unittest.TestCase):
    def test_fixture(self):
        titles = [r["title"] for r in gd.diagnose_text((FIX / "failure_java_agp.log").read_text())]
        self.assertIn("Gradle is older than the Android Gradle Plugin needs", titles)
        self.assertIn("Dependency could not be resolved", titles)
        self.assertIn("Android SDK location not set", titles)

    def test_cli_exit_codes(self):
        rc, out, _ = run("diagnose", str(FIX / "failure_java_agp.log"))
        self.assertEqual(rc, 1)
        self.assertIn("fix:", out)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "ok.log"
            p.write_text("BUILD SUCCESSFUL in 3s\n")
            self.assertEqual(run("diagnose", str(p))[0], 0)
        self.assertEqual(run("diagnose", "no-such-file.log")[0], 2)

    def test_oom_and_dupes(self):
        t = "java.lang.OutOfMemoryError: Java heap space\nDuplicate class kotlin.collections.jdk8.X found in modules a and b"
        titles = [r["title"] for r in gd.diagnose_text(t)]
        self.assertIn("Out of memory in the Gradle or Kotlin daemon", titles)
        self.assertIn("Duplicate classes from two dependencies", titles)


class Check(unittest.TestCase):
    def test_agp_gradle_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            make_project(d, gradle="8.7", agp="9.5.0",
                         extra_build='dependencies { implementation("a.b:c:1.+") }\n')
            rc, out, _ = run("check", "--project", d, "--json")
            self.assertEqual(rc, 1)
            self.assertIn("agp-gradle", out)
            self.assertIn("dynamic-version", out)

    def test_not_a_project(self):
        with tempfile.TemporaryDirectory() as d:
            rc, out, _ = run("check", "--project", d)
            self.assertEqual(rc, 1)
            self.assertIn("no-settings", out)


class Fix(unittest.TestCase):
    def test_dry_run_then_apply(self):
        with tempfile.TemporaryDirectory() as d:
            make_project(d)
            rc, out, _ = run("fix", "--project", d, "--gradle-version", "9.6.0")
            self.assertEqual(rc, 0)
            self.assertIn("WOULD", out)
            self.assertFalse((Path(d) / "gradle.properties").exists())
            run("fix", "--project", d, "--gradle-version", "9.6.0", "--apply")
            wp = (Path(d) / "gradle/wrapper/gradle-wrapper.properties").read_text()
            self.assertIn("gradle-9.6.0-bin.zip", wp)
            self.assertTrue((Path(d) / "gradle/wrapper/gradle-wrapper.properties.bak").exists())
            self.assertIn("android.useAndroidX=true", (Path(d) / "gradle.properties").read_text())

    def test_sdk_dir(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as sdk:
            make_project(d)
            run("fix", "--project", d, "--sdk-dir", sdk, "--apply")
            self.assertIn("sdk.dir=", (Path(d) / "local.properties").read_text())
            self.assertEqual(run("fix", "--project", d, "--sdk-dir", os.path.join(sdk, "nope"))[0], 2)

    def test_bad_version(self):
        with tempfile.TemporaryDirectory() as d:
            make_project(d)
            self.assertEqual(run("fix", "--project", d, "--gradle-version", "latest")[0], 2)


class AddLib(unittest.TestCase):
    def test_add(self):
        with tempfile.TemporaryDirectory() as d:
            make_project(d)
            args = ["add-lib", "--project", d, "--coordinates", "com.squareup.retrofit2:retrofit:2.11.0",
                    "--alias", "retrofit-core"]
            rc, out, _ = run(*args)
            self.assertEqual(rc, 0)
            self.assertNotIn("retrofit", (Path(d) / "gradle/libs.versions.toml").read_text())
            self.assertEqual(run(*args, "--apply")[0], 0)
            toml = (Path(d) / "gradle/libs.versions.toml").read_text()
            self.assertIn('retrofit-core = "2.11.0"', toml)
            self.assertIn('retrofit-core = { group = "com.squareup.retrofit2", name = "retrofit", version.ref = "retrofit-core" }', toml)
            self.assertLess(toml.index("[libraries]"), toml.index("retrofit-core = {"))
            self.assertLess(toml.index("retrofit-core = {"), toml.index("[plugins]"))
            self.assertIn("implementation(libs.retrofit.core)", (Path(d) / "app/build.gradle.kts").read_text())
            self.assertEqual(run(*args, "--apply")[0], 1)  # duplicate alias refused

    def test_rejects(self):
        with tempfile.TemporaryDirectory() as d:
            make_project(d)
            base = ["add-lib", "--project", d, "--alias", "x"]
            self.assertEqual(run(*base, "--coordinates", "a:b:1.+")[0], 2)
            self.assertEqual(run(*base, "--coordinates", "a:b")[0], 2)
            self.assertEqual(run(*base, "--coordinates", "a:b:1", "--config", "compile")[0], 2)

    def test_creates_catalog_and_groovy(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "app").mkdir()
            (root / "app" / "build.gradle").write_text("dependencies {\n}\n")
            run("add-lib", "--project", d, "--coordinates", "junit:junit:4.13.2", "--alias", "junit",
                "--config", "testImplementation", "--apply")
            self.assertIn("testImplementation libs.junit", (root / "app/build.gradle").read_text())
            self.assertIn('junit = "4.13.2"', (root / "gradle/libs.versions.toml").read_text())


class TestCommand(unittest.TestCase):
    def test_commands(self):
        rc, out, _ = run("test", "--dry-run", "--class", "com.x.FooTest", "--method", "adds")
        self.assertEqual(rc, 0)
        self.assertIn(":app:testDebugUnitTest --tests com.x.FooTest.adds", out)
        self.assertIn("app/build/reports/tests/testDebugUnitTest/", out)
        _, out, _ = run("test", "--dry-run", "--instrumented", "--variant", "freeDebug", "--class", "com.x.UiTest")
        self.assertIn(":app:connectedFreeDebugAndroidTest", out)
        self.assertIn("android.testInstrumentationRunnerArguments.class=com.x.UiTest", out)
        self.assertEqual(run("test", "--dry-run", "--instrumented", "--method", "m")[0], 2)


if __name__ == "__main__":
    unittest.main()
