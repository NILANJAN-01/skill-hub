# Capturing UIAutomator dumps

Put the screen you want in front first. The dump only contains what is visible at that moment.

## Standard capture (any Android device or emulator)

```bash
adb devices                                         # find the serial if several are connected
adb -s <serial> shell uiautomator dump /sdcard/window_dump.xml
adb -s <serial> pull /sdcard/window_dump.xml media_screen.xml
```

Give each dump a screen name (`media_screen.xml`, `nav_search.xml`). The output files are named after the input files: `locators/media_screen.locators.json`.

Print a dump straight to your computer, without a file on the device:

```bash
adb exec-out uiautomator dump /dev/tty > media_screen.xml
```

This prints a final status line after the XML ("UI hierchary dumped to: /dev/tty"; the misspelling is Android's own). The converter ignores it.

## Other sources the converter accepts

| Source | How to get it |
|---|---|
| uiautomatorviewer | *Save* → `.uix` file (XML) |
| Appium Inspector / Appium | Copy the page source, or `driver.page_source` → save as `.xml` |
| A web page or report showing the dump | Save the page as `.html`. Escaped text in `<pre>`, syntax-highlighted text and real `<node>` elements all work |
| Several screens | Put the files in a folder and pass the folder: one JSON per dump |

## Android Automotive / OEM head units

- **Several windows:** the media app, the system bar (HVAC, navigation buttons) and overlays can all appear in one dump. Each `<hierarchy>` is counted as a window (`window` field). To keep only the app, use `--package <app package>` or `--exclude-package com.android.systemui`.
- **Several displays** (driver, passenger, cluster): `uiautomator dump` usually captures the main display. Run `adb shell uiautomator` with no arguments to see what your build's `dump` command supports. If it can't target another display, use an Appium session on that display and save its page source.
- **Animated screens** (maps, media visualisers) can fail with `could not get idle state`. Pause the animation, or use Appium's page source.
- **Language:** OEM units often change UI language by market or user profile. Prefer `resource_id` keywords, and capture dumps in the language your tests run in if you must use text locators.
- **Restricted builds:** some production units disable `adb` or UIAutomator. Use an engineering or development build for test automation.
