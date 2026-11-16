---
name: android-logcat-analyzer
description: "Analyse Android logcat output (a file, a bugreport zip, or a connected device over adb) with a ready-made Python script that reports fatal exceptions, native crashes, ANRs, service crashes, low-memory kills and other problems, with stacks and usual causes. Use when the user shares a logcat or bugreport, or asks why an Android app crashed, froze, restarted or was killed."
license: Complete terms in the repository README
compatibility: Needs Python 3.8+ (standard library only). Reading from a device needs adb (Android platform-tools) and a device or emulator with USB debugging enabled.
metadata:
  title: "Android logcat analyzer"
  category: android-automation
---

# Android logcat analyzer

`scripts/logcat_analyzer.py` reads logcat text and reports what went wrong. It uses only the Python standard library.

A logcat is often tens of thousands of lines. Run the script first and read its report, not the raw log: it finds the problems, groups repeats, and prints each one with its stack, the lines the same process logged just before, and the usual cause.

## When to use

- The user shares a logcat file, a bugreport zip, or pasted logcat lines and asks what went wrong.
- A device or emulator is connected and the user asks why an app crashed, froze, restarted or was killed.
- The user asks for the crashes, ANRs or exceptions of one app (package name) in a log.
- A test run failed on a device and the cause has to be found in the device log.
- A script or CI job must fail when a log contains a crash.

## When NOT to use

- The user needs element locators from a screen dump: use the `android-uiautomator-locators` skill.
- The log is not Android logcat (for example a Gradle build log or a server log).
- The user only wants the last few lines of a log. Reading them directly is faster.

## Safety rules for the agent

- The script only reads. With `--adb` it runs `adb logcat -d`, which dumps the buffers and does not clear them. Do not run `adb logcat -c` (it erases the evidence) unless the user asks.
- Logs can contain personal data, tokens and URLs. Quote only the lines needed to explain a problem, and do not send the log to an outside service.
- Report what the log shows. The "Usual cause" lines are hints for where to look, not a diagnosis. Say so when the log does not contain the cause.

## Procedures

Run the commands from the skill folder, or give the full path of the script.

### 1. Analyse a log file

```bash
python scripts/logcat_analyzer.py logcat.txt
```

Accepted inputs: plain text, `.gz`, an Android bugreport `.zip`, several files at once, or `-` for standard input. Accepted line formats: `adb logcat -v threadtime` (the default of adb), `-v time`, `-v brief`, and text copied from the Android Studio Logcat window.

The report has three parts:

1. A **Result** line with the count of each problem type.
2. A **Summary** table: id, severity, type, process, how often, first seen, one-line description.
3. **Details** for each problem: exception and root cause, top frame in the app's own code, thread, the log block, the last lines of the same process before it, the usual cause, and what happened after (process died, service restarted).

### 2. Analyse a connected device

```bash
python scripts/logcat_analyzer.py --adb --package com.example.app
```

- `--serial <id>` picks a device when several are connected (`adb devices` lists them).
- `--save device-log.txt` also keeps the raw log, so that the analysis can be repeated after the device buffer has rolled over.
- `--buffers main,system,crash,events` is the default. The `events` buffer is what explains process deaths and ANRs.
- `--adb-path <path>` is for an adb that is not on the PATH.

### 3. Narrow the report

| Goal | Option |
|---|---|
| Only one app | `--package com.example.app` |
| Only some problem types | `--only crash,anr` (see the type list below) |
| Hide minor findings | `--min-severity high` |
| Only a time window | `--since "11-12 10:00:00" --until "10:05:00"` |
| One problem in full, with the whole stack | `--show 3` (the id from the Summary table) |
| More or fewer lines before each problem | `--context 20` |
| Longer log blocks | `--max-stack 0` (0 means no limit) |

Start with the default report. If it is long, read the Summary table, then use `--show <id>` for the problems that matter.

### 4. Read the result and answer the user

1. Start with the `critical` and `high` rows. A fatal exception, native crash or ANR is usually the cause, and the service crashes and process deaths after it are usually effects. The **Cause** and **After it** lines link them.
2. For a Java or Kotlin crash, read **Root cause** (the last `Caused by`) and **Top app frame**. That file and line is where to look in the user's code.
3. For a native crash, read the signal, the library and the top frame of the backtrace. "no tombstone in the log" means the log holds only the signal, so ask for the tombstone or a bugreport.
4. For an ANR, read the reason (input dispatch, broadcast, service timeout) and the lines before it. The main-thread stack is in the ANR traces file of a bugreport, not in logcat.
5. Tell the user: what failed, in which process and when, the root cause line, the place in their code, and the next step. Quote the few log lines that prove it, with their line numbers.

### 5. Use it in scripts and CI

```bash
python scripts/logcat_analyzer.py logcat.txt --json --out report.json
python scripts/logcat_analyzer.py logcat.txt --package com.example.app --fail-on high
```

- `--json` prints the same result as data: `counts`, `by_severity`, `groups` (one per problem, with `id`, `severity`, `type`, `process`, `count`, `title`, `fields`, `hint`, `stack`, `before`, `related`) and `timeline`.
- `--out FILE` writes the report to a file.
- Exit codes: `0` finished, `1` a problem at or above `--fail-on` was found, `2` the input could not be read or contained no logcat lines.

## Problem types

Use the names in the left column with `--only`.

| Type | Meaning | Severity |
|---|---|---|
| `java_crash` | Fatal exception in Java or Kotlin code (`FATAL EXCEPTION`) | critical |
| `native_crash` | Native crash: fatal signal, tombstone | critical |
| `anr` | Application Not Responding | critical |
| `watchdog` | System watchdog killed `system_server`; system restart | critical |
| `service_crash` | An app service lost its process or a native service died | high |
| `lmk` | Low-memory killer killed a process | high |
| `process_death` | A foreground or visible process died with no cause in the log | high |
| `kill` | Process killed by the system (normal ones are `info`) | varies |
| `exception` | Exception with a stack trace that did not kill the app | medium |
| `fatal_log` | Fatal-level log line (`Log.wtf`, assert) | medium |
| `binder` | Failed binder transaction (often a parcel that is too large) | medium |
| `service_blocked` | Background service start not allowed | low |
| `strictmode` | StrictMode violation | low |
| `jank` | Main thread skipped many frames (`--jank-frames` sets the limit, default 60) | low |
| `selinux` | SELinux denial (`avc: denied`) | low |
| `exception_mention` | A line names an exception but has no stack | low |

Group names for `--only`: `crash` (Java and native), `fatal` (crashes and fatal logs), `java`, `native`, `service` (service crashes, process deaths, kills, low-memory kills, blocked starts), `exceptions`, `memory`, `system`.

Normal system kills are hidden by default. Add `--min-severity info` to see them.

## Troubleshooting

| Symptom / error | Fix |
|---|---|
| `error: no logcat lines found in ...` | The file is not logcat text, or it uses a custom format. Capture again with `adb logcat -v threadtime -d > logcat.txt` |
| `error: give a logcat file, '-' for stdin, or --adb` | Pass a file path, pipe the log in, or add `--adb` |
| adb is not found, or no device | Install Android platform-tools, check `adb devices`, accept the USB debugging prompt on the device, or pass `--adb-path` and `--serial` |
| The crash the user saw is not in the report | The device buffer rolled over. Reproduce the problem and capture straight away, or ask for a bugreport zip |
| Process shown as `-` or only as a pid | The log has no line that names that pid. Include the `events` and `system` buffers |
| Nothing for the app with `--package` | Check the package name; run once without `--package` to see the process names in the log |
| Too many low-severity rows | Add `--min-severity high`, or `--only crash,anr` |
| A stack is cut off | Use `--show <id>` or `--max-stack 0` |

## Tests

`scripts/test_logcat_analyzer.py` runs the analyzer on the sample logs in `scripts/fixtures/`. Run it after changing the script:

```bash
python -m unittest discover -s scripts -p "test_*.py"
```
