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
SCRIPT = str(HERE / "dump_to_locators.py")


class Opts:
    package = None
    exclude_package = None
    include_layout = False
    case = "snake"


def convert_text(text, name="dump.xml", **kw):
    o = Opts()
    for k, v in kw.items():
        setattr(o, k, v)
    nodes, windows = d2l.parse_dump(text)
    return d2l.convert(nodes, windows, name, o)


def run(name, **kw):
    return convert_text(d2l.read_text(FIX / name), name, **kw)


def by_kw(result):
    return {e["keyword"]: e for e in result["elements"]}


def fixture_text(name):
    return (FIX / name).read_text(encoding="utf-8")


class ReadingTests(unittest.TestCase):
    def test_standard_dump(self):
        r = run("phone_settings.xml")
        self.assertEqual(r["summary"]["nodes"], 21)
        self.assertEqual(r["summary"]["windows"], 1)
        self.assertEqual(r["keywords"]["homepage_title"], "com.android.settings:id/homepage_title")

    def test_automotive_app_and_system_bar_are_two_windows(self):
        r = run("automotive_media.xml")
        self.assertEqual(r["summary"]["nodes"], 13)
        self.assertEqual(r["summary"]["windows"], 2)
        self.assertEqual(set(r["summary"]["packages"]), {"com.example.oem.media", "com.android.systemui"})
        k = by_kw(r)
        self.assertEqual(k["back"]["window"], 1)
        self.assertEqual(k["systemui_back"]["window"], 2)
        self.assertEqual(k["source_chip"]["text"], "Quelle: USB & Bluetooth")   # &amp; decoded

    def test_appium_page_source_xml(self):
        r = run("appium_navigation_source.xml")
        self.assertEqual(r["summary"]["nodes"], 8)
        e = by_kw(r)["destination_input"]
        self.assertEqual(e["class"], "android.widget.EditText")
        self.assertEqual(e["hint"], "Ziel eingeben")

    def test_exec_out_status_line_is_ignored(self):
        text = fixture_text("phone_settings.xml") + "UI hierchary dumped to: /dev/tty\n"
        self.assertEqual(len(d2l.parse_dump(text)[0]), 21)

    def test_several_hierarchy_blocks_in_one_file(self):
        text = fixture_text("phone_settings.xml") + fixture_text("compose_login.xml")
        nodes, windows = d2l.parse_dump(text)
        self.assertEqual(len(nodes), 21 + 7)
        self.assertEqual(windows, 2)

    def test_control_characters_from_apps_are_tolerated(self):
        text = fixture_text("compose_login.xml").replace('text="Sign in" resource-id="" class="android.widget.Button"',
                                                         'text="Sign&#1; in\x07" resource-id="" class="android.widget.Button"')
        nodes, _ = d2l.parse_dump(text)
        self.assertIn("Sign in", [n["text"] for n in nodes])

    def test_utf16_file(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "dump.xml"
            p.write_bytes(fixture_text("phone_settings.xml").encode("utf-16"))
            self.assertEqual(len(d2l.parse_dump(d2l.read_text(p))[0]), 21)

    def test_truncated_dump_reports_position(self):
        text = fixture_text("phone_settings.xml")
        with self.assertRaises(d2l.DumpError) as cm:
            d2l.parse_dump(text[: len(text) // 2])
        self.assertIn("invalid XML near line", str(cm.exception))

    def test_html_is_rejected(self):
        with self.assertRaises(d2l.DumpError) as cm:
            d2l.parse_dump("<!DOCTYPE html><html><body><pre>&lt;hierarchy&gt;</pre><node/></body></html>")
        self.assertIn("HTML", str(cm.exception))

    def test_not_a_dump(self):
        with self.assertRaises(d2l.DumpError):
            d2l.parse_dump("<config><item>1</item></config>")


class KeywordTests(unittest.TestCase):
    def test_shared_id_gets_group_and_per_item_keywords(self):
        k = by_kw(run("phone_settings.xml"))
        self.assertEqual(k["title"]["occurrences"], 4)
        self.assertEqual(k["title_network_internet"]["locators"]["uiselector"],
                         'new UiSelector().resourceId("android:id/title").text("Network & internet")')

    def test_shared_id_prefers_stable_description_over_live_text(self):
        k = by_kw(run("automotive_media.xml"))
        self.assertIn("hvac_temperature_driver_temperature", k)        # not hvac_temperature_21_5
        self.assertEqual(k["hvac_temperature_passenger_temperature"]["locators"]["uiselector"],
                         'new UiSelector().resourceId("com.android.systemui:id/hvac_temperature")'
                         '.description("Passenger temperature")')

    def test_same_id_in_two_packages(self):
        r = run("automotive_media.xml")
        self.assertEqual(r["keywords"]["back"], "com.example.oem.media:id/back")
        self.assertEqual(r["keywords"]["systemui_back"], "com.android.systemui:id/back")

    def test_compose_test_tag_without_id_prefix(self):
        self.assertEqual(run("automotive_media.xml")["keywords"]["media_play_pause"], "media_play_pause")

    def test_non_english_labels(self):
        k = by_kw(run("automotive_media.xml"))
        self.assertIn("nachster_titel_button", k)                       # German, accent removed
        chinese = [e for e in k.values() if e["text"] == "音乐"]
        self.assertEqual(len(chinese), 1)
        self.assertRegex(chinese[0]["keyword"], r"^[a-z]+_\d+$")         # safe ASCII fallback
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
        r = run("compose_login.xml")
        self.assertEqual(r["keywords"], {})
        self.assertTrue(any("No resource-ids" in w for w in r["warnings"]))
        k = by_kw(r)
        self.assertEqual(k["email_input"]["strategy"], "content_desc")
        self.assertEqual(k["email_input"]["locators"]["appium"], {"strategy": "accessibility id", "value": "Email"})
        self.assertEqual(k["sign_in_button"]["locators"]["uiselector"], 'new UiSelector().text("Sign in").instance(1)')

    def test_layout_nodes_only_on_request(self):
        self.assertFalse(any(e["strategy"] == "class_instance" for e in run("phone_settings.xml")["elements"]))
        fallback = [e for e in run("phone_settings.xml", include_layout=True)["elements"]
                    if e["strategy"] == "class_instance"]
        self.assertTrue(fallback and all(e["fragile"] for e in fallback))
        xps = [e["locators"]["xpath"] for e in fallback]
        self.assertEqual(len(xps), len(set(xps)))                       # each points at exactly one node

    def test_package_filters(self):
        r = run("automotive_media.xml", exclude_package=["com.android.systemui"])
        self.assertNotIn("systemui_back", r["keywords"])
        r = run("automotive_media.xml", package=["com.android.systemui"])
        self.assertEqual(set(r["summary"]["packages"]), {"com.android.systemui"})


class CliTests(unittest.TestCase):
    def cli(self, *args):
        return subprocess.run([sys.executable, SCRIPT, *map(str, args)],
                              capture_output=True, text=True, encoding="utf-8")

    def test_folder_input_writes_separate_output_folder(self):
        with tempfile.TemporaryDirectory() as t:
            out = Path(t) / "locators"
            p = self.cli(FIX, "--out", out)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(sorted(x.name for x in out.iterdir()),
                             sorted(f"{f.stem}.locators.json" for f in FIX.iterdir()))
            for f in out.iterdir():
                data = json.loads(f.read_text(encoding="utf-8"))
                self.assertIn("keywords", data)
                self.assertIn("elements", data)

    def test_keywords_format(self):
        p = self.cli(FIX / "phone_settings.xml", "--format", "keywords", "--stdout")
        self.assertEqual(json.loads(p.stdout)["title"], "android:id/title")

    def test_bad_inputs_fail_clearly(self):
        with tempfile.TemporaryDirectory() as t:
            page = Path(t) / "page.xml"
            page.write_text("<!DOCTYPE html><html><body><node bounds='[0,0][1,1]' class='x'/></body></html>",
                            encoding="utf-8")
            empty = Path(t) / "empty.xml"
            empty.write_text("<?xml version='1.0'?><hierarchy rotation='0'></hierarchy>", encoding="utf-8")
            p = self.cli(page, empty, "--stdout")
            self.assertEqual(p.returncode, 2)
            self.assertIn("looks like an HTML page", p.stderr)
            self.assertIn("no <node> elements", p.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=1)
