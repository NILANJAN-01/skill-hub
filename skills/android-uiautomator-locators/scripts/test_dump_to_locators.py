#!/usr/bin/env python3
"""Tests for dump_to_locators.py. Run: python test_dump_to_locators.py   (standard library only)."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import dump_to_locators as d2l  # noqa: E402

FIX = HERE / "fixtures"


class Opts:
    package = None
    exclude_package = None
    include_layout = False
    case = "snake"


def run(name, **kw):
    o = Opts()
    for k, v in kw.items():
        setattr(o, k, v)
    nodes, windows = d2l.parse_dump(d2l.read_text(FIX / name))
    return d2l.convert(nodes, windows, name, o)


def by_kw(result):
    return {e["keyword"]: e for e in result["elements"]}


class FormatTests(unittest.TestCase):
    def test_standard_dump(self):
        r = run("phone_settings.xml")
        self.assertEqual(r["summary"]["nodes"], 21)
        self.assertEqual(r["keywords"]["homepage_title"], "com.android.settings:id/homepage_title")
        self.assertEqual(r["keywords"]["search_action_bar"], "com.android.settings:id/search_action_bar")

    def test_html_escaped_with_highlight_spans_and_two_windows(self):
        r = run("automotive_media_escaped.html")
        self.assertEqual(r["summary"]["nodes"], 13)
        self.assertEqual(r["summary"]["windows"], 2)
        self.assertEqual(set(r["summary"]["packages"]), {"com.example.oem.media", "com.android.systemui"})
        e = by_kw(r)["source_chip"]
        self.assertEqual(e["text"], "Quelle: USB & Bluetooth")      # double-escaped &amp;amp; decoded once

    def test_appium_page_source(self):
        r = run("appium_navigation_source.xml")
        self.assertEqual(r["summary"]["nodes"], 8)
        e = by_kw(r)["destination_input"]
        self.assertEqual(e["class"], "android.widget.EditText")
        self.assertEqual(e["hint"], "Ziel eingeben")

    def test_browser_saved_dom_ignores_page_markup(self):
        r = run("compose_browser_saved.html")
        self.assertEqual(r["summary"]["nodes"], 7)                     # the <div class=header> is not a node
        self.assertTrue(all(e["package"] == "com.example.composeapp" for e in r["elements"]))

    def test_same_nodes_from_xml_and_escaped_html(self):
        xml = (FIX / "phone_settings.xml").read_text(encoding="utf-8")
        import html
        page = "<html><body><pre>" + html.escape(xml) + "</pre></body></html>"
        a, _ = d2l.parse_dump(xml)
        b, _ = d2l.parse_dump(page)
        self.assertEqual([n["resource_id"] for n in a], [n["resource_id"] for n in b])
        self.assertEqual([n["text"] for n in a], [n["text"] for n in b])

    def test_utf16_file(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "dump.xml"
            p.write_bytes((FIX / "phone_settings.xml").read_text(encoding="utf-8").encode("utf-16"))
            nodes, _ = d2l.parse_dump(d2l.read_text(p))
            self.assertEqual(len(nodes), 21)

    def test_no_nodes(self):
        nodes, _ = d2l.parse_dump("<html><body><p>nothing here</p></body></html>")
        self.assertEqual(nodes, [])


class KeywordTests(unittest.TestCase):
    def test_shared_id_gets_group_and_per_item_keywords(self):
        k = by_kw(run("phone_settings.xml"))
        self.assertEqual(k["title"]["occurrences"], 4)
        self.assertIn("title_network_internet", k)
        self.assertEqual(k["title_network_internet"]["locators"]["uiselector"],
                         'new UiSelector().resourceId("android:id/title").text("Network & internet")')

    def test_same_id_in_two_packages(self):
        r = run("automotive_media_escaped.html")
        self.assertEqual(r["keywords"]["back"], "com.example.oem.media:id/back")
        self.assertEqual(r["keywords"]["systemui_back"], "com.android.systemui:id/back")

    def test_shared_id_prefers_stable_description_over_live_text(self):
        k = by_kw(run("automotive_media_escaped.html"))
        self.assertIn("hvac_temperature_driver_temperature", k)      # not hvac_temperature_21_5
        self.assertEqual(k["hvac_temperature_driver_temperature"]["strategy"], "resource_id+content_desc")
        self.assertEqual(k["hvac_temperature_passenger_temperature"]["locators"]["uiselector"],
                         'new UiSelector().resourceId("com.android.systemui:id/hvac_temperature")'
                         '.description("Passenger temperature")')

    def test_compose_test_tag_without_id_prefix(self):
        self.assertEqual(run("automotive_media_escaped.html")["keywords"]["media_play_pause"], "media_play_pause")

    def test_non_english_labels(self):
        k = by_kw(run("automotive_media_escaped.html"))
        self.assertIn("nachster_titel_button", k)                     # German, accent removed
        chinese = [e for e in k.values() if e["text"] == "音乐"]
        self.assertEqual(len(chinese), 1)
        self.assertRegex(chinese[0]["keyword"], r"^[a-z]+_\d+$")       # safe ASCII fallback
        self.assertEqual(chinese[0]["locators"]["uiselector"], 'new UiSelector().text("音乐")')

    def test_id_starting_with_digit(self):
        self.assertIn("el_2fa_toggle", run("appium_navigation_source.xml")["keywords"])

    def test_duplicate_text_gets_instances(self):
        k = by_kw(run("appium_navigation_source.xml"))
        self.assertEqual(k["destination_name_home"]["instance"], 0)
        self.assertEqual(k["destination_name_home_2"]["instance"], 1)
        self.assertEqual(k["destination_name_home_2"]["locators"]["xpath"],
                         "(//*[@resource-id='com.example.oem2.navigation:id/destination_name' and @text='Home'])[2]")
        self.assertNotIn("instance", k["destination_name_work"])

    def test_keywords_are_unique(self):
        for f in FIX.iterdir():
            kws = [e["keyword"] for e in run(f.name)["elements"]]
            self.assertEqual(len(kws), len(set(kws)), f.name)

    def test_case_styles(self):
        self.assertIn("HOMEPAGE_TITLE", run("phone_settings.xml", case="upper")["keywords"])
        self.assertIn("homepageTitle", run("phone_settings.xml", case="camel")["keywords"])


class FallbackTests(unittest.TestCase):
    def test_no_resource_ids_warns_and_falls_back(self):
        r = run("compose_browser_saved.html")
        self.assertEqual(r["keywords"], {})
        self.assertTrue(any("No resource-ids" in w for w in r["warnings"]))
        k = by_kw(r)
        self.assertEqual(k["email_input"]["strategy"], "content_desc")
        self.assertEqual(k["email_input"]["locators"]["appium"], {"strategy": "accessibility id", "value": "Email"})
        self.assertEqual(k["sign_in_button"]["locators"]["uiselector"], 'new UiSelector().text("Sign in").instance(1)')

    def test_layout_nodes_only_on_request(self):
        plain = run("phone_settings.xml")
        self.assertFalse(any(e["strategy"] == "class_instance" for e in plain["elements"]))
        lay = run("phone_settings.xml", include_layout=True)
        fallback = [e for e in lay["elements"] if e["strategy"] == "class_instance"]
        self.assertTrue(fallback)
        self.assertTrue(all(e["fragile"] for e in fallback))
        xps = [e["locators"]["xpath"] for e in fallback]
        self.assertEqual(len(xps), len(set(xps)))                     # each points at exactly one node

    def test_package_filters_keep_device_instance_numbers(self):
        r = run("automotive_media_escaped.html", exclude_package=["com.android.systemui"])
        self.assertNotIn("systemui_back", r["keywords"])
        r = run("automotive_media_escaped.html", package=["com.android.systemui"])
        self.assertEqual(set(r["summary"]["packages"]), {"com.android.systemui"})


class CliTests(unittest.TestCase):
    def test_folder_input_writes_separate_output_folder(self):
        with tempfile.TemporaryDirectory() as t:
            out = Path(t) / "locators"
            p = subprocess.run([sys.executable, str(HERE / "dump_to_locators.py"), str(FIX), "--out", str(out)],
                               capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(p.returncode, 0, p.stderr)
            files = sorted(x.name for x in out.iterdir())
            self.assertEqual(len(files), len(list(FIX.iterdir())))
            for f in out.iterdir():
                data = json.loads(f.read_text(encoding="utf-8"))
                self.assertIn("keywords", data)
                self.assertIn("elements", data)

    def test_keywords_format_and_bad_input(self):
        with tempfile.TemporaryDirectory() as t:
            bad = Path(t) / "empty.html"
            bad.write_text("<html><body>no dump</body></html>", encoding="utf-8")
            p = subprocess.run([sys.executable, str(HERE / "dump_to_locators.py"), str(FIX / "phone_settings.xml"),
                                "--format", "keywords", "--stdout"], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(json.loads(p.stdout)["title"], "android:id/title")
            p = subprocess.run([sys.executable, str(HERE / "dump_to_locators.py"), str(bad), "--stdout"],
                               capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(p.returncode, 2)
            self.assertIn("no UIAutomator nodes", p.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=1)
