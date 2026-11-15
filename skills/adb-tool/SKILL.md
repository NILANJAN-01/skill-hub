---
name: adb-tool
description: "Central skill for adb (Android Debug Bridge): every adb, am, pm, dpm and shell command with syntax and risk level, plus one Python script that diagnoses adb, lists devices, runs any adb command with a safety check, and looks up commands by keyword. Use when the user mentions adb, an Android device or emulator command, asks which adb command does X, or needs a safe way to run adb."
license: Complete terms in the repository README
compatibility: Needs Python 3.8+ (standard library only). Running device commands needs adb (Android SDK Platform-Tools) and a device or emulator with USB debugging or wireless debugging enabled. The related skills adb-connect, adb-device-control and adb-debug use this skill's script, so install them together (the adb-tools bundle).
metadata:
  title: "adb: command reference, safety check and central script"
  category: adb-tools
---

# adb (Android Debug Bridge)

`adb` is a client-server tool: a **client** on your computer, a **server** on your computer (TCP port 5037), and a **daemon (adbd)** on each device. This skill is the entry point of the adb skill set: it holds the full command catalog, the safety rules, and `scripts/adb_tool.py`, the one script all four adb skills share.

| Need | Skill |
|---|---|
| adb missing, no device listed, `unauthorized`, `offline`, wireless pairing, drivers | `adb-connect` |
| Install/uninstall/start apps, permissions, files, screenshots, screen recording, display size, settings | `adb-device-control` |
| logcat, crashes, ANRs, dumpsys, bug reports, memory/graphics snapshots, instrumented tests | `adb-debug` |
| "Which adb command does X?", run any other adb command safely | this skill |

## The script

Run `python skills/adb-tool/scripts/adb_tool.py <command>` (use the folder where the skill is installed). Add `--dry-run` to print the adb commands without running them, `--serial S` to pick a device, `--adb PATH` if adb is not on PATH. Exit codes: 0 ok, 1 problem or failure, 2 bad usage, 3 needs `--yes`.

| Command | What it does |
|---|---|
| `doctor` | Finds adb, shows version and server status (mDNS), lists devices with a fix for each bad state |
| `devices`, `info` | Parsed device list; model, Android version, ABI, screen, battery, storage, Wi-Fi IP |
| `find WORDS` | Searches the command catalog: `find screenshot`, `find wireless pair` |
| `catalog [--area A] [--risk R] [--markdown]` | Prints the catalog (139 commands in 17 areas) |
| `classify -- ADB_ARGS` | Says whether a command is read, change, destructive or unknown, without running it |
| `run [--yes] -- ADB_ARGS` | Runs any adb command after the risk check; destructive and unknown commands need `--yes` |
| `wifi`, `apps`, `app-info`, `install`, `uninstall`, `clear`, `grant`, `revoke`, `start`, `stop`, `push`, `pull`, `screenshot`, `record`, `display`, `logcat`, `dumpsys`, `snapshot`, `bugreport` | Task commands, described in the three other skills |

The full list of commands, flags, risk levels and sources is in [references/command-reference.md](references/command-reference.md) (generated from `scripts/adb_catalog.py`; do not edit by hand).

## When to use

- The user types or asks about any `adb ...` command, or wants to do something to an Android device or emulator from a computer.
- "Is there an adb command for ...", "what does `adb ...` do", "run this adb command".
- Any adb task that the three focused skills do not cover (`forward`, `reverse`, `sync`, `emu`, `am`, `pm`, `dpm`, `settings`, `input`).

## When NOT to use

- Android Studio-only tasks, Gradle builds (use `gradle-android`), analysing a saved logcat file (use `android-logcat-analyzer`), UI locators (use `android-uiautomator-locators`).

## Safety rules for the agent

1. Run read-only commands freely. For `change` commands say what will change. For **destructive** or **unknown** commands (uninstall, `pm clear`, `rm`, `reboot`, `root`, `remount`, `disable-verity`, `sideload`, `sync`, `cmd testharness`, factory reset, interactive `shell`) ask the user first, and add `--yes` only after they agree.
2. Always target one device explicitly when more than one is attached (`--serial`); never guess. adb itself errors with "more than one device/emulator".
3. Do not run `adb root`, `remount`, `disable-verity`, `sideload` or `reboot bootloader/recovery` unless the user asked for exactly that and understands the risk. Production devices refuse root.
4. Wipe nothing to "fix" a problem: do not uninstall an app or clear its data to get past an error unless the user agrees (it deletes their data).
5. A bug report and logcat contain personal data (accounts, app list, messages). Save them locally and share only with people who need them.
6. `adb tcpip` and `adb -a` expose the device or server without encryption. Use trusted networks, and return to USB with `adb usb`.
7. Quote values for the device shell: since Platform-Tools 23 adb treats arguments like `ssh`, so `adb shell setprop key 'two words'` fails; use `adb shell setprop key "'two words'"`. The script quotes for you.
8. Never claim a command works on this device without running it (or its `--help`): options depend on the Android version. The catalog marks device tools with source `device`.

## Procedures

1. **Check the setup first.**
   ```bash
   python skills/adb-tool/scripts/adb_tool.py doctor
   ```
   Fix what it reports (see `adb-connect`), then continue.
2. **Find the command.** `adb_tool.py find <words>`, or open the area in [references/command-reference.md](references/command-reference.md).
3. **Check the risk, then run.**
   ```bash
   python skills/adb-tool/scripts/adb_tool.py classify -- shell pm clear com.example.app
   python skills/adb-tool/scripts/adb_tool.py run -- shell getprop ro.build.version.release
   python skills/adb-tool/scripts/adb_tool.py run --yes -- shell pm clear com.example.app   # only after the user agrees
   ```
4. **Report** the exact command run, its output, and anything that changed on the device.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `adb: command not found` | Install Platform-Tools; `doctor` prints the steps and searches the usual SDK folders |
| `more than one device/emulator` | Use `--serial` (or `-s`), `-d` for the one USB device, `-e` for the one emulator |
| No device or `unauthorized`/`offline` | Use the `adb-connect` skill |
| `error: closed` / adb hangs | `adb kill-server`, then any adb command restarts the server |
| Command differs on your device | Run `adb shell <tool> --help`; options vary by Android version |

## References

- [references/command-reference.md](references/command-reference.md): all commands, flags, risk, source
- [references/sources.md](references/sources.md): the official pages this skill set is built from and when they were checked
