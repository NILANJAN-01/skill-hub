---
name: adb-debug
description: "Debug Android apps and devices with adb: read and filter logcat (by app, tag, level, buffer, time), capture crashes and ANRs, run dumpsys for memory, graphics, battery and activities, collect a snapshot or a bug report, take heap dumps, and run instrumented tests with am instrument. Use when the user asks why an app crashed or is slow, wants logs from a device, needs a bug report, or wants memory, frame or battery data."
license: Complete terms in the repository README
compatibility: Needs Python 3.8+ and the script from the adb-tool skill (install the adb-tools bundle), adb on PATH, and one connected device or emulator (see adb-connect). Analysing a saved log file is done by android-logcat-analyzer.
metadata:
  title: "adb debugging: logcat, dumpsys, bug reports, snapshots"
  category: adb-tools
---

# adb: logs, dumps and bug reports

Uses `skills/adb-tool/scripts/adb_tool.py`. If no device is listed use `adb-connect`; with several devices add `--serial SERIAL`. Everything in this skill is read-only except clearing log buffers (`logcat --clear`), heap dumps (write a file on the device) and instrumented tests.

## When to use

- "Show the logs", "why did my app crash/freeze (ANR)", "filter logcat for my app/tag/errors", "save the log".
- "Get a bug report", "collect device info for a ticket", "how much memory does the app use", "why is it janky (gfxinfo)", "battery usage".
- "Run the instrumented tests on the device and read the results".

## When NOT to use

- Analysing an existing logcat file or bugreport zip for crashes: use `android-logcat-analyzer` (this skill captures, that one analyses).
- Gradle build or Gradle test failures: `gradle-android`. Connection problems: `adb-connect`.

## Safety rules for the agent

- Logs and bug reports contain personal data (accounts, installed apps, network names, sometimes message text and tokens). Save locally, do not paste whole files into chats, and share only with people who need them.
- `logcat --clear` erases evidence: do not clear before the user has captured the problem.
- Do not use `adb root` or `setprop log.tag.*` to get more logs unless the user asked; many options are root-only.
- Heap dumps and bitmap dumps may contain secrets from app memory; delete the device copy after pulling (`adb shell rm /data/local/tmp/x.hprof`, after the user agrees).

## Procedures

1. **Quick log of the problem.**
   ```bash
   python skills/adb-tool/scripts/adb_tool.py logcat --lines 500 --level W --out log.txt
   python skills/adb-tool/scripts/adb_tool.py logcat --package com.example.app --out app.log     # only that running app (by pid)
   python skills/adb-tool/scripts/adb_tool.py logcat --tag MyApp:D --tag OkHttp:I              # allow-list tags, hide the rest
   python skills/adb-tool/scripts/adb_tool.py logcat --crash --out crash.txt                     # crash buffer
   python skills/adb-tool/scripts/adb_tool.py logcat --follow --seconds 30 --grep "Exception|ANR"
   ```
   Priorities `V D I W E F S`. Formats (`--format`): brief, long, process, raw, tag, thread, threadtime (default), time; modifiers such as `color`, `epoch`, `usec`, `UTC`, `year`, `zone`, `uid`. Details: [references/logcat.md](references/logcat.md).
2. **Reproduce, then capture.** Ask the user to reproduce the problem, then run the commands above. For a crash right at launch the pid disappears, so use `--crash` or `--since` instead of `--package`, or run `logcat --follow --seconds 30` in one terminal and `adb_tool.py start PKG -S` in another.
3. **Analyse.** Hand the saved file to the `android-logcat-analyzer` skill (fatal exceptions, native crashes, ANRs, low-memory kills with stacks and usual causes).
4. **Snapshot for a bug report.**
   ```bash
   python skills/adb-tool/scripts/adb_tool.py snapshot --package com.example.app --out snap/
   ```
   Writes properties, battery, top activity, processes, storage, display, meminfo, gfxinfo, package info and the last 2000 log lines into one folder. Read-only.
5. **Full bug report.** `adb_tool.py bugreport ./reports/` (zip with dumpsys, dumpstate and logcat; takes minutes). Older reports: `adb shell ls /bugreports/` then `adb pull`. Open `bugreport-*.txt` inside the zip first. See [references/dumpsys-and-bugreport.md](references/dumpsys-and-bugreport.md).
6. **Targeted dumps.**
   ```bash
   python skills/adb-tool/scripts/adb_tool.py dumpsys                      # list services
   python skills/adb-tool/scripts/adb_tool.py dumpsys meminfo com.example.app --out mem.txt
   python skills/adb-tool/scripts/adb_tool.py dumpsys gfxinfo com.example.app
   python skills/adb-tool/scripts/adb_tool.py dumpsys batterystats --out battery.txt
   ```
7. **App-level debugging helpers.** `am monitor` (crash/ANR watcher), `am dumpheap PROCESS FILE`, `am set-debug-app -w PKG` (wait for a debugger), `adb jdwp` (debuggable process ids), `adb forward jdwp:PID tcp:8700`. See [references/debugging-workflows.md](references/debugging-workflows.md).
8. **Instrumented tests.** `adb_tool.py run -- shell am instrument -w -e class com.example.CartTest#totalIsSummed com.example.test/androidx.test.runner.AndroidJUnitRunner` (results go to stdout; `-w` is required). Through Gradle use the `gradle-android` skill.
9. **Report** the evidence (the lines that show the problem, with timestamps and pid), not just the conclusion, and say what could not be captured.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Log is empty or short | Buffers are circular and small: reproduce again right before capturing; add `--buffer all` |
| App logs missing | Filtered by `*:S` or the wrong tag; try `--package` or `--level D`. System property filtering can hide logs below a level |
| `--package` says not running | The app is not running (no pid). Start it, then retry |
| `logcat: Permission denied` for some buffers | Some options and buffers are root-only |
| bugreport hangs | It can take several minutes; keep the device unlocked and connected |
| Output has `\r\r\n` / garbled lines on Windows | The script normalises line endings; use `--out` to write a clean file |
| Different options on your device | Run `adb logcat --help` or `adb shell dumpsys -l` for what this device supports |

## References

- [references/logcat.md](references/logcat.md): options, filter expressions, formats, buffers
- [references/dumpsys-and-bugreport.md](references/dumpsys-and-bugreport.md): dumpsys services, bug report contents and capture
- [references/debugging-workflows.md](references/debugging-workflows.md): crash, ANR, memory, jank, battery, JDWP, profiling
