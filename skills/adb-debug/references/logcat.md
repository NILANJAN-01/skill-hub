# logcat

Source: [adb-tool/references/sources.md](../../adb-tool/references/sources.md) (logcat page). `adb logcat` is shorthand for `adb shell logcat`. General form: `[adb] shell logcat [option]... [filter-spec]...`. Options differ by Android version and many are root-only: run `adb logcat --help` on the device.

## The logging system

Logs live in fixed circular buffers kept by `logd`. Buffers: `main` (app logs), `system` (OS), `crash`; also `radio`, `events`. `default` is main + system + crash; `all` is everything. Entries carry a priority, a tag and the message.

Filtering happens at four levels: compile time (ProGuard can remove `Log.d`), system properties read by `liblog` (minimum severity per tag), application (`__android_log_set_minimum_priority`, default INFO), and display filtering by `adb logcat`.

## Priorities

`V` verbose (lowest), `D` debug, `I` info, `W` warning, `E` error, `F` fatal, `S` silent (nothing printed).

## Filter expressions

`tag:priority ...` shows messages for that tag at or above the priority; whitespace-separated.

```
adb logcat ActivityManager:I MyApp:D *:S      # allow-list: only these tags (*:S silences the rest)
adb logcat *:W                                # warnings and above for all tags
adb logcat "ActivityManager:I MyApp:D *:S"    # quote in shells that expand *
export ANDROID_LOG_TAGS="ActivityManager:I MyApp:D *:S"   # default filter for adb logcat on the host
```
`ANDROID_LOG_TAGS` is not exported to the device when you run `adb shell logcat`.

Common options (confirm with `--help`): `-b BUFFER` (repeat or comma list: `-b main,radio,events`), `-d` dump and exit, `-c` clear buffers, `-t N` last N lines, `-T TIME|N` start at time or last N, `-v FORMAT`, `-f FILE` (on the device), `-g` buffer sizes, `--pid=PID`, `-s` same as `*:S`, `-e REGEX` / `--regex`, `-m N` max lines.

## Formats (`-v`)

| Format | Shows |
|---|---|
| `brief` | priority, tag, PID |
| `long` | all metadata fields, messages separated by blank lines |
| `process` | PID only |
| `raw` | message only |
| `tag` | priority and tag only |
| `thread` | priority, PID, TID (legacy) |
| `threadtime` | date, time, priority, tag, PID, TID (default) |
| `time` | date, time, priority, tag, PID |

Modifiers combine with one format: `color`, `descriptive` (event-log descriptions), `epoch`, `monotonic`, `printable` (escape binary), `uid`, `usec`, `UTC`, `year`, `zone`. Example: `adb logcat -b all -v color -d`. `logcat -v --help` lists them.

## Script mapping

| Goal | `adb_tool.py logcat ...` | Runs |
|---|---|---|
| Last 500 lines | (default) | `logcat -v threadtime -d -t 500` |
| One app | `--package com.x` | adds `--pid PID` from `pidof` |
| Tags | `--tag A:D --tag B` | adds `A:D B:V *:S` |
| Level | `--level W` | adds `*:W` |
| Crash buffer | `--crash` | `-b crash` |
| Buffers | `--buffer all` | `-b all` |
| Since | `--since "11-15 09:30:00.000"` | `-T` |
| Follow | `--follow --seconds 30` | no `-d`, stops after 30 s |
| Host filter | `--grep "regex"` | filters on the computer, case-insensitive |
| Save | `--out file` | writes the file (feed it to `android-logcat-analyzer`) |
| Clear | `--clear` | `logcat -c` |

## Writing logs from code

`Log.v/d/i/w/e(tag, msg)`; output `I/MyActivity( 1557): message` in brief format. Use a stable tag per component so the allow-list filter works.
