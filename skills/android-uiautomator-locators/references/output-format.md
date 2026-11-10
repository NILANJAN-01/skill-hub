# Locator JSON format

One file per input dump: `<output folder>/<dump name>.locators.json`.

```json
{
  "generator": "android-uiautomator-locators 1.0",
  "source": "media.html",
  "summary": {
    "nodes": 13,                 // UI nodes found in the dump
    "nodes_kept": 13,            // after --package / --exclude-package
    "elements": 13,              // entries in "elements"
    "with_resource_id": 9,
    "windows": 2,                // <hierarchy> blocks (multi-window / multi-display dumps)
    "packages": {"com.example.oem.media": 9, "com.android.systemui": 4}
  },
  "warnings": ["..."],
  "keywords": {                  // keyword -> resource-id (only elements located by resource-id alone)
    "back": "com.example.oem.media:id/back",
    "systemui_back": "com.android.systemui:id/back"
  },
  "elements": [
    {
      "keyword": "hvac_temperature_21_5",
      "strategy": "resource_id+text",
      "resource_id": "com.android.systemui:id/hvac_temperature",
      "text": "21.5°",
      "content_desc": "Driver temperature",
      "class": "android.widget.TextView",
      "package": "com.android.systemui",
      "window": 2,
      "clickable": true,
      "enabled": true,
      "bounds": [200, 730, 320, 790],      // left, top, right, bottom (px)
      "center": [260, 760],                // tap point if nothing else works
      "locators": {
        "uiselector": "new UiSelector().resourceId(\"com.android.systemui:id/hvac_temperature\").text(\"21.5°\")",
        "uiautomator2": {"resourceId": "com.android.systemui:id/hvac_temperature", "text": "21.5°"},
        "by": "By.res(\"com.android.systemui:id/hvac_temperature\").text(\"21.5°\")",
        "xpath": "//*[@resource-id='com.android.systemui:id/hvac_temperature' and @text='21.5°']",
        "appium": {"strategy": "xpath", "value": "//*[...]"}
      }
    }
  ]
}
```
(The `//` comments are explanations here. The real file is plain JSON.)

## `strategy` values

| Strategy | Meaning | Robustness |
|---|---|---|
| `resource_id` | Located by resource-id alone. Group entries for shared ids carry `occurrences`, `samples` and a `note` | Best |
| `resource_id+text` / `resource_id+content_desc` | A shared id narrowed down by its text or description (list rows) | Good; text depends on language |
| `content_desc` | No id; located by accessibility description (Appium "accessibility id") | Good; may be localised |
| `text` | No id or description; located by visible text | Weak: changes with language and wording |
| `class_instance` | Nothing to identify it (`--include-layout` only); class name + position. Has `fragile: true` | Fragile |

## Optional fields

- `instance` (0-based): present when the selector matches more than one node in the dump. It is already applied in every locator: `.instance(n)` for UiSelector, `[n+1]` in XPath, and `instance` in uiautomator2.
- `occurrences`, `samples`, `note`: on group entries for ids shared by several elements.
- `hint`: the input hint (Appium page source).
- `fragile`, `note`: on `class_instance` elements.

## `--format keywords`

Writes only the `keywords` object:

```json
{"homepage_title": "com.android.settings:id/homepage_title", "title": "android:id/title"}
```
