#!/usr/bin/env python3
"""Tests for junit_scaffold.py. Standard library only.
Run: python -m unittest discover -s . -p "test_*.py"
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import junit_scaffold as js  # noqa: E402

JAVA_SRC = HERE / "fixtures" / "shop" / "src" / "main" / "java" / "com" / "example" / "shop" / "PriceCalculator.java"
KT_SRC = HERE / "fixtures" / "shop" / "src" / "main" / "kotlin" / "com" / "example" / "shop" / "Basket.kt"
SCRIPT = str(HERE / "junit_scaffold.py")


def cli(*argv):
    return subprocess.run([sys.executable, SCRIPT, *argv], capture_output=True, text=True, encoding="utf-8")


def project(files):
    d = tempfile.mkdtemp()
    for rel, text in files.items():
        p = Path(d) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return d


class ParseTests(unittest.TestCase):
    def test_java(self):
        info = js.parse_java(JAVA_SRC.read_text(encoding="utf-8"))
        self.assertEqual(info["package"], "com.example.shop")
        names = [m["name"] for m in info["methods"]]
        self.assertEqual(names, ["price", "discount", "gross", "items", "round"])   # no ctor, no private log()
        price = info["methods"][0]
        self.assertEqual(price["params"], [("String", "item"), ("int", "quantity")])
        self.assertEqual(price["throws"], ["IllegalArgumentException", "PriceCalculator.UnknownItemException"])
        self.assertTrue(info["methods"][-1]["static"])
        self.assertEqual(info["ctor"], [("Map<String, Integer>", "prices")])

    def test_kotlin(self):
        info = js.parse_kotlin(KT_SRC.read_text(encoding="utf-8"))
        names = [m["name"] for m in info["methods"]]
        self.assertEqual(names, ["add", "total", "priceOf", "checkout", "empty"])   # private clear() skipped
        add = info["methods"][0]
        self.assertEqual(add["throws"], ["IllegalArgumentException", "IllegalStateException"])  # require / check
        self.assertTrue(info["methods"][3]["suspend"])
        self.assertTrue(info["methods"][4]["static"])                                # companion object
        self.assertEqual(info["ctor"], [("Map<String, Int>", "catalog")])             # defaulted param omitted

    def test_record_and_no_constructor(self):
        info = js.parse_java("package a;\npublic record Money(long cents, String currency) {\n"
                             "  public Money plus(Money o) { return new Money(cents + o.cents, currency); }\n}")
        self.assertEqual(info["ctor"], [("long", "cents"), ("String", "currency")])
        info = js.parse_java("package a;\npublic class Util { public static int twice(int x) { return 2 * x; } }")
        self.assertEqual(info["ctor"], [])

    def test_bad_source(self):
        with self.assertRaises(ValueError):
            js.parse_java("package a;\n// nothing here\n")


class GenerateTests(unittest.TestCase):
    def test_java_output(self):
        code = js.gen_java(js.parse_java(JAVA_SRC.read_text(encoding="utf-8")), "PriceCalculatorTest", True)
        self.assertIn("class PriceCalculatorTest {", code)
        self.assertIn("priceCalculator = new PriceCalculator(null);", code)
        self.assertIn("assertThrows(PriceCalculator.UnknownItemException.class, () -> priceCalculator.price(\"\", 0))",
                      code)
        self.assertIn("var result = PriceCalculator.round(0.0);", code)
        self.assertIn('@Disabled("TODO: replace the sample row with real cases, then remove @Disabled")', code)
        self.assertIn('"text, 0, 0",', code)
        self.assertEqual(code.count("fail(\"TODO"), 7)          # 5 method tests + 2 exception tests
        self.assertNotIn("org.junit.Test", code)

    def test_kotlin_output(self):
        code = js.gen_kotlin(js.parse_kotlin(KT_SRC.read_text(encoding="utf-8")), "BasketTest", True)
        self.assertIn('basket = Basket(TODO("Map<String, Int>"))', code)
        self.assertIn("inner class PriceOf {", code)
        self.assertIn("assertThrows<IllegalStateException> { basket.add(\"\") }", code)
        self.assertIn("suspend fun `returns the expected result`()", code)
        self.assertIn("val result = Basket.empty()", code)
        self.assertIn('@CsvSource("text, 0, 0")', code)
        self.assertIn("import org.junit.jupiter.api.fail", code)

    def test_no_parameterized(self):
        code = js.gen_java(js.parse_java(JAVA_SRC.read_text(encoding="utf-8")), "T", False)
        self.assertNotIn("ParameterizedTest", code)

    def test_writes_to_matching_test_folder_and_refuses_overwrite(self):
        d = project({"src/main/java/com/x/Calc.java": "package com.x;\npublic class Calc {\n"
                                                    "  public int add(int a, int b) { return a + b; }\n}"})
        src = str(Path(d) / "src/main/java/com/x/Calc.java")
        p = cli("new", src)
        self.assertEqual(p.returncode, 0, p.stderr)
        target = Path(d) / "src/test/java/com/x/CalcTest.java"
        self.assertTrue(target.is_file())
        self.assertEqual(cli("new", src).returncode, 2)
        self.assertEqual(cli("new", src, "--force").returncode, 0)

    def test_needs_out_outside_src_main(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "Calc.java"
            f.write_text("public class Calc { public int one() { return 1; } }", encoding="utf-8")
            self.assertEqual(cli("new", str(f)).returncode, 2)
            self.assertIn("class CalcTest", cli("new", str(f), "--stdout").stdout)


class CheckTests(unittest.TestCase):
    def test_gradle_missing_pieces(self):
        d = project({"build.gradle.kts": 'plugins { java }\ndependencies { '
                                         'testImplementation("org.junit.jupiter:junit-jupiter:5.10.0") }\n'
                                         "kotlin { jvmToolchain(11) }"})
        rep = js.check(d)
        m = rep["modules"][0]
        self.assertFalse(rep["ok"])
        joined = " ".join(m["missing"])
        self.assertIn("junit-platform-launcher", joined)
        self.assertIn("useJUnitPlatform", joined)
        self.assertIn("Java 17+", joined)
        self.assertTrue(any("5.10.0" in n for n in m["notes"]))
        p = cli("check", d)
        self.assertEqual(p.returncode, 1)
        self.assertIn('testImplementation(platform("org.junit:junit-bom:6.1.3"))', p.stdout)

    def test_gradle_complete_with_catalog(self):
        d = project({"gradle/libs.versions.toml": '[versions]\njunit = "6.1.3"\n[libraries]\n'
                                                  'junit-bom = { module = "org.junit:junit-bom", version.ref = "junit" }\n'
                                                  'junit-jupiter = { module = "org.junit.jupiter:junit-jupiter" }\n'
                                                  'junit-launcher = { module = "org.junit.platform:junit-platform-launcher" }\n',
                     "build.gradle.kts": "dependencies {\n testImplementation(platform(libs.junit.bom))\n"
                                         " testImplementation(libs.junit.jupiter)\n testRuntimeOnly(libs.junit.launcher)\n}\n"
                                         "tasks.test { useJUnitPlatform() }"})
        rep = js.check(d)
        self.assertTrue(rep["ok"], rep)
        self.assertEqual(rep["modules"][0]["version"], "6.1.3")

    def test_maven(self):
        d = project({"pom.xml": "<project><dependencies><dependency><groupId>org.junit.jupiter</groupId>"
                                "<artifactId>junit-jupiter</artifactId><version>6.1.3</version></dependency>"
                                "</dependencies><build><plugins><plugin><artifactId>maven-surefire-plugin</artifactId>"
                                "<version>2.22.2</version></plugin></plugins></build></project>"})
        m = js.check(d)["modules"][0]
        self.assertTrue(any("3.5.5" in x for x in m["missing"]))

    def test_android_hint(self):
        d = project({"app/build.gradle.kts": 'plugins { id("com.android.application") }\n'
                                             'dependencies { testImplementation(platform("org.junit:junit-bom:6.1.3"))\n'
                                             ' testImplementation("org.junit.jupiter:junit-jupiter")\n'
                                             ' testRuntimeOnly("org.junit.platform:junit-platform-launcher") }'})
        m = js.check(d)["modules"][0]
        self.assertTrue(any("unitTests.all" in x for x in m["missing"]))

    def test_deps_variants(self):
        for build in ("gradle-kts", "gradle-groovy", "toml", "maven"):
            out = cli("deps", "--build", build, "--vintage").stdout
            self.assertIn("6.1.3", out)
            self.assertIn("vintage", out)


if __name__ == "__main__":
    unittest.main()
