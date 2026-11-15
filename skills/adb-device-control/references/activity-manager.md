# Activity manager (`am`) and intents

Source: [adb-tool/references/sources.md](../../adb-tool/references/sources.md) (adb page, Call activity manager). Run as `adb shell am <command>`.

## Commands

| Command | Use |
|---|---|
| `am start [options] INTENT` | Start an activity. `-D` debug, `-W` wait for launch, `-S` force-stop first, `-R N` repeat, `--start-profiler FILE`, `-P FILE`, `--opengl-trace`, `--user ID|current`, `--debug-link` (Android 17+: explains why a URL did or did not match app links) |
| `am startservice [--user ID|current] INTENT` | Start a service |
| `am broadcast [--user ID|all|current] INTENT` | Send a broadcast |
| `am force-stop PACKAGE` | Stop everything of the app |
| `am kill [--user ID|all|current] PACKAGE` | Kill only processes safe to kill |
| `am kill-all` | Kill all background processes |
| `am instrument [-r] [-e NAME VALUE] [-p FILE] [-w] [--no-window-animation] [--user ID] PKG/RUNNER` | Run instrumented tests; `-w` needed to see results |
| `am profile start PROCESS FILE` / `am profile stop PROCESS` | CPU profiler |
| `am dumpheap [--user ID] [-b [png|jpg|webp]] [-n] PROCESS FILE` | Heap dump; `-n` native heap, `-b` bitmaps (API 35+) |
| `am dumpbitmaps [-d|--dump [fmt]] [-p PROCESS]...` | Bitmap info (API 36+), zip `dumpbitmaps-<time>.zip` |
| `am set-debug-app [-w] [--persistent] PACKAGE` / `am clear-debug-app` | Wait for a debugger at start |
| `am monitor [--gdb]` | Watch crashes and ANRs |
| `am screen-compat {on|off} PACKAGE` | Screen compatibility mode |
| `am display-size [reset|WxH]`, `am display-density DPI` | Display overrides (also `wm size` / `wm density`) |
| `am to-uri INTENT`, `am to-intent-uri INTENT` | Print the intent as a URI |
| `am memory-limiter ignore UID|none|all`, `manual PID LIMIT|max|none`, `status` | Android 17+ memory limits |

## Intent specification

| Option | Meaning |
|---|---|
| `-a ACTION` | Action, for example `android.intent.action.VIEW` (once) |
| `-d DATA_URI` | Data URI (once) |
| `-t MIME` | MIME type (once) |
| `-c CATEGORY` | Category (repeatable) |
| `-n COMPONENT` | Explicit component `com.example.app/.MainActivity` |
| `-f FLAGS` | Raw intent flags |
| `-e|--es KEY VALUE` | String extra |
| `--ez KEY true|false`, `--ei KEY INT`, `--el KEY LONG`, `--ef KEY FLOAT`, `--eu KEY URI`, `--ecn KEY COMPONENT`, `--esn KEY` (null) | Typed extras |
| `--eia|--ela|--efa KEY v1,v2,...` | Int, long, float arrays |
| `--grant-read-uri-permission`, `--grant-write-uri-permission` | URI permission flags |
| `--activity-clear-top`, `--activity-clear-task`, `--activity-new-task`-style flags | Activity flags: `--activity-brought-to-front`, `-clear-top`, `-clear-when-task-reset`, `-exclude-from-recents`, `-launched-from-history`, `-multiple-task`, `-no-animation`, `-no-history`, `-no-user-action`, `-previous-is-top`, `-reorder-to-front`, `-reset-task-if-needed`, `-single-top`, `-clear-task`, `-task-on-home` |
| `--receiver-registered-only`, `--receiver-replace-pending`, `--include-stopped-packages`, `--exclude-stopped-packages`, `--debug-log-resolution` | Broadcast and resolution flags |
| `--selector` | Needs `-d` and `-t` |
| bare `URI` / `COMPONENT` / `PACKAGE` | With ":" it is a URI, with "/" a component, otherwise a package |

## Examples

```bash
adb shell am start -a android.intent.action.VIEW -d "https://example.com/item/42"     # deep link
adb shell am start -W -n com.example.app/.MainActivity                                 # cold start time in the output
adb shell am start -S -n com.example.app/.MainActivity                                 # restart from scratch
adb shell am broadcast -a com.example.ACTION_SYNC --es reason manual
adb shell am force-stop com.example.app
adb shell am instrument -w -e class com.example.CartTest#totalIsSummed com.example.test/androidx.test.runner.AndroidJUnitRunner
```

Instrumentation runner arguments (`AndroidJUnitRunner`): `class` (`Class` or `Class#method`, comma separated), `package`, `size small|medium|large`, `log true` (list tests without running), `debug true`. `package` wins over `class`. To run a filtered instrumented test from Gradle see the `gradle-android` skill.

## Quoting

Use `adb_tool.py run -- shell am start ...` or quote like ssh: a `&` or `?` in a URL must be quoted for the device shell too: `adb shell am start -d "'https://x.com/a?b=1&c=2'"`.
