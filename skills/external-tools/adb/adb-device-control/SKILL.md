---
name: adb-device-control
description: "Control an Android device or emulator with adb: install, uninstall, start and stop apps, list packages and app info, grant permissions, clear data, send intents with am, copy files with push and pull, take screenshots, record the screen, override display size or density, and read or change settings. Use when the user wants to install an APK, push or pull a file, capture the screen, reset an app, or script device actions."
license: Complete terms in the repository README
compatibility: Needs Python 3.8+ and the script from the adb-tool skill (install the adb-tools bundle), adb on PATH, and one connected device or emulator with USB or wireless debugging on (see adb-connect).
metadata:
  title: "adb device control: apps, files, screen, settings"
  category: adb-tools
  requires: adb-tool
---

# adb: apps, files, screen and settings

Everything here uses `skills/adb-tool/scripts/adb_tool.py`. If no device is listed first use `adb-connect`. With more than one device add `--serial SERIAL`.

## When to use

- "Install this APK", "uninstall/clear/force-stop the app", "start the app", "which apps are installed", "app version/permissions".
- "Pull/push a file", "copy the database", "take a screenshot", "record the screen".
- "Grant the camera permission", "open this deep link", "change screen size/density", "toggle airplane mode".

## When NOT to use

- Logs, crashes, dumpsys, bug reports: `adb-debug`. Connection problems: `adb-connect`. Building the APK: `gradle-android`. Writing UI tests / locators: `android-uiautomator-locators`.

## Safety rules for the agent

- **Ask before** `uninstall`, `clear`, `rm`, overwriting files with `push`, `pm disable`, `settings put`, `svc`, and display overrides on a device the user depends on. The script refuses `uninstall` and `clear` without `--yes`.
- `uninstall` and `pm clear` delete the app's data. Never use them to work around an install error without the user's agreement. Prefer `-r` (replace, keeps data) or `uninstall -k` (keeps data and cache).
- `push` overwrites existing files silently. Check the target first (`run -- shell ls -l PATH`).
- Reset display overrides afterwards: `display size reset`, `display density reset`.
- Do not grant or revoke permissions, or change `settings`, on the user's personal phone without being asked; prefer an emulator or test device.
- Do not paste secrets into `input text`: the text is visible in logs.

## Procedures

1. **Check the device.** `python skills/adb-tool/scripts/adb_tool.py info` (model, Android version, ABI, screen, battery, storage).
2. **Install an app.**
   ```bash
   python skills/adb-tool/scripts/adb_tool.py install app-debug.apk -r        # -r replace keeping data, -t test APK, -d downgrade, -g grant permissions
   python skills/adb-tool/scripts/adb_tool.py install base.apk split_a.apk    # several APKs use install-multiple
   ```
   `.aab` and `.apks` files cannot be installed by `adb install` (use bundletool). Install errors are explained by the script and in [references/apps-and-packages.md](references/apps-and-packages.md).
3. **Inspect apps.**
   ```bash
   python skills/adb-tool/scripts/adb_tool.py apps --filter example         # third-party; --system, --all, --disabled
   python skills/adb-tool/scripts/adb_tool.py app-info com.example.app      # version, SDKs, installer, permissions, APK path, pid
   ```
4. **Run and stop.**
   ```bash
   python skills/adb-tool/scripts/adb_tool.py start com.example.app -W     # resolves the launcher activity; or package/.Activity
   python skills/adb-tool/scripts/adb_tool.py stop com.example.app
   python skills/adb-tool/scripts/adb_tool.py run -- shell am start -a android.intent.action.VIEW -d "https://example.com"
   ```
   Intent options: [references/activity-manager.md](references/activity-manager.md).
5. **Permissions and reset.** `grant com.example.app CAMERA` (or the full permission name), `revoke ...`. To reset an app: `clear com.example.app --yes` (after the user agrees).
6. **Files.**
   ```bash
   python skills/adb-tool/scripts/adb_tool.py push build/data.json /sdcard/Download/
   python skills/adb-tool/scripts/adb_tool.py pull /sdcard/Download/report.pdf ./out/
   ```
   App-private files in `/data/data/<package>` need a debuggable app (`adb shell run-as <package>`), root, or an emulator. See [references/files-screen-input.md](references/files-screen-input.md).
7. **Screen.**
   ```bash
   python skills/adb-tool/scripts/adb_tool.py screenshot shot.png
   python skills/adb-tool/scripts/adb_tool.py record demo.mp4 --time 30    # max 180 s, no audio
   python skills/adb-tool/scripts/adb_tool.py display size 1280x800        # reset: display size reset
   ```
8. **Anything else:** `adb_tool.py find <words>`, then `adb_tool.py run -- <adb args>` (risk-checked). Examples: `run -- shell settings get global airplane_mode_on`, `run -- shell input keyevent 3` (Home), `run -- forward tcp:6100 tcp:7100`.
9. **Report** what ran and what changed. Undo temporary changes (display overrides, forwards, pushed temp files).

## Troubleshooting

| Symptom | Fix |
|---|---|
| `INSTALL_FAILED_UPDATE_INCOMPATIBLE` | Different signature: the old app must be uninstalled first (deletes its data; ask) |
| `INSTALL_FAILED_VERSION_DOWNGRADE` | Use `-d` for debuggable apps, or uninstall |
| `INSTALL_FAILED_USER_RESTRICTED` | Allow "Install via USB" in Developer options (some OEMs) |
| `INSTALL_FAILED_OLDER_SDK` / `NO_MATCHING_ABIS` | Device too old / wrong CPU ABI for the app's native libraries |
| `Permission denied` on pull/push | Path not accessible to the shell user; use `/sdcard/...` or `run-as` for debuggable apps |
| `screencap` file is corrupt | The script falls back to screencap + pull automatically |
| `Security exception` on `pm grant` | Permission is not grantable (not declared, or a signature/privileged permission) |
| Quoting errors in `shell` | Quote twice for values with spaces: `"'two words'"` (adb treats arguments like ssh) |

## References

- [references/apps-and-packages.md](references/apps-and-packages.md): `pm` commands, install options and errors, app links
- [references/activity-manager.md](references/activity-manager.md): `am` commands and the intent specification
- [references/files-screen-input.md](references/files-screen-input.md): push/pull, screencap, screenrecord, input, settings, display
- Full command list: `skills/adb-tool/references/command-reference.md`
