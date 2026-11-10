---
name: android-uiautomator-locators
description: Convert an Android UIAutomator dump (window_dump.xml, .uix, Appium page source, or an HTML page that contains a dump) into a JSON locator file of keyword names mapped to resource-ids, with ready-made UiSelector, By, uiautomator2, Appium and XPath locators for UIAutomator-based tests. Works for any Android UI, including Android Automotive / OEM head units (multi-window dumps, Compose screens without ids, non-English text). Use when the user shares a uiautomator dump or HTML of one and wants keywords, resource ids, element locators, an object repository or page objects for Android UI tests, or mentions uiautomator dump, window_dump.xml, resource-id, UiSelector, uiautomator2, Appium locators.
license: Complete terms in the repository README
compatibility: Needs Python 3.8+ (standard library only). Capturing a fresh dump needs adb and a connected device or emulator.
metadata:
  title: "Android UIAutomator dump to locators"
  category: android-automation
---

# Android UIAutomator dump → locator JSON

`scripts/dump_to_locators.py` reads a UIAutomator dump and writes one JSON file per screen into a **separate output folder** (default `locators/`). Each file contains:

- `keywords`: `{"keyword_name": "package:id/resource_id"}`, the simple map most test suites need.
- `elements`: every usable element with its keyword, the strategy used, text, content-desc, class, package, bounds, center point, and ready-made locators (`uiselector`, `by`, `uiautomator2`, `appium`, `xpath`).
- `summary` and `warnings`, for example "this screen has no resource-ids".

The full field reference is in [references/output-format.md](references/output-format.md).

## When to use

- The user has a `uiautomator dump` XML, a uiautomatorviewer `.uix`, an Appium page source, or an **HTML page** showing a dump, and wants keyword names, resource ids or locators.
- The user is building an object repository, page objects, or a keyword library for UIAutomator, uiautomator2, Appium, or keyword-driven tests (such as Robot Framework) on Android.
- The screen is from any device: phone, tablet, TV, or an Android Automotive / OEM infotainment system.

## When NOT to use

- iOS, web (Selenium DOM) or desktop UIs. This skill only reads Android accessibility dumps.
- Screenshots only, with no dump. Capture a dump first (see below).

## Procedure

1. **Get the dump.** If the user already has the file, use it. Otherwise capture one with a device connected (more options in [references/capturing-dumps.md](references/capturing-dumps.md)):
   ```bash
   adb shell uiautomator dump /sdcard/window_dump.xml
   adb pull /sdcard/window_dump.xml
   ```
2. **Convert it.** The script's path is relative to this skill's folder:
   ```bash
   python scripts/dump_to_locators.py window_dump.xml              # -> locators/window_dump.locators.json
   python scripts/dump_to_locators.py dumps/ --out tests/locators  # every dump in a folder, one JSON each
   ```
   Useful options:
   - `--format keywords`: write only the `{keyword: resource-id}` map.
   - `--case upper|camel`: `BTN_PLAY` or `btnPlay` style keywords (default `snake`).
   - `--package com.oem.media`: keep only one app's elements. `--exclude-package com.android.systemui` drops the system bar. Repeat either option as needed.
   - `--include-layout`: also emit elements with no id, text or description. These locators are fragile and marked so.
   - `--stdout`: print the JSON instead of writing files.
3. **Read the console summary and the warnings, and pass them on to the user.** In particular:
   - *No resource-ids*: typical for Jetpack Compose and some OEM UIs. Locators fall back to content-desc, then text. Recommend that developers expose test tags as resource-ids.
   - *Text-based locators*: these break when the UI language changes. This matters on OEM head units that switch language by market or user.
   - *N elements share this id*: list rows. Use the per-item keywords (`title_bluetooth`) or the `instance`.
4. **Check the result.** Open the JSON and confirm that the keywords for the elements the user cares about exist. If a needed element is missing, it has no id, text or description: rerun with `--include-layout`, or recommend adding an id.
5. **Hand over.** Show the user the `keywords` map (or the relevant part of it) and the output path. If they want code, generate it from `elements[].locators` for their framework (see below). Don't retype selectors by hand.

## How keywords are named

| Element | Strategy | Keyword | Locator |
|---|---|---|---|
| Unique resource-id `com.app:id/btn_play` | `resource_id` | `btn_play` | `resourceId` |
| Id shared by list rows (`android:id/title` ×4) | `resource_id` (group, `occurrences: 4`) + `resource_id+text` per row | `title`, `title_bluetooth` | `resourceId` + `text` |
| Shared id with a content-desc (`hvac_temperature`, "Driver temperature") | `resource_id+content_desc`; the desc is preferred because text often holds live values (21.5°) | `hvac_temperature_driver_temperature` | `resourceId` + `description` |
| Same id in two apps (`…media:id/back`, `…systemui:id/back`) | `resource_id` | `back`, `systemui_back` | `resourceId` |
| Compose test tag without `:id/` (`media_play_pause`) | `resource_id` | `media_play_pause` | `resourceId` |
| No id, has content-desc "Nächster Titel" | `content_desc` | `nachster_titel_button` | `description` / Appium accessibility id |
| No id, only text "Sign in" | `text` | `sign_in_button` | `text` (+ `instance` when repeated) |
| Non-Latin text with no id ("音乐") | `text` | `text_7` (role + position in the dump) | `text("音乐")` |
| Nothing at all (`--include-layout` only) | `class_instance` | `button_5` | `className` + `instance`, `fragile: true` |

Keywords are lowercase ASCII (accents removed), unique within the file, and an `el_` prefix is added if a keyword would start with a digit. When the same text appears more than once, the element gets a 0-based `instance` that matches `UiSelector.instance()`, counted over the whole dump.

## Using the output in tests

```python
# uiautomator2 (Python)
import json, uiautomator2 as u2
loc = {e["keyword"]: e["locators"]["uiautomator2"] for e in json.load(open("locators/media.locators.json"))["elements"]}
d = u2.connect()
d(**loc["back"]).click()
```
```java
// UiAutomator (Java/Kotlin): paste locators.uiselector or locators.by
device.findObject(new UiSelector().resourceId("com.example.oem.media:id/back")).click();
device.findObject(By.res("com.example.oem.media:id/back")).click();
```
```python
# Appium (Python): the strategy names match AppiumBy values ("id", "accessibility id", "xpath")
import json
elements = {e["keyword"]: e for e in json.load(open("locators/media.locators.json"))["elements"]}
el = elements["back"]["locators"]["appium"]
driver.find_element(el["strategy"], el["value"]).click()
```

## Safety and quality rules

- The script only reads dumps and writes JSON into the output folder. It never touches the device.
- Never invent resource-ids. Every id in the output comes from the dump.
- Generated keywords are a starting point. Review the names of important elements with the user before building a large suite on them.
- Dumps can contain personal data, such as contact names and destinations. Don't publish dumps or locator files from real vehicles without the user's agreement.

## Troubleshooting

| Problem | Fix |
|---|---|
| `no UIAutomator nodes found` | The file holds no dump. For an HTML page, check that it contains the dump text or `<node …>` elements, not only a screenshot |
| `ERROR: could not get idle state` while dumping | The screen is animating (media players, maps). Pause the animation or retry. Some apps never become idle; use Appium's page source instead |
| Dump shows only the system bar or the wrong screen | Dump again with the app in front. On multi-display units, see [references/capturing-dumps.md](references/capturing-dumps.md) |
| Keywords like `text_7` | The label has no Latin characters. Rename the keyword in your suite, or ask for a resource-id |
| Locator works on one unit but not another | Text-based locators differ between languages and OEM builds. Prefer `resource_id` keywords |

## Run the tests

```bash
python scripts/test_dump_to_locators.py
```

The fixtures in `scripts/fixtures/` cover a standard dump, an HTML page with an escaped multi-window automotive dump, Appium page source, and a browser-saved Compose screen with no ids.
