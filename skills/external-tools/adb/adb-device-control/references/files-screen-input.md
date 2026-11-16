# Files, screen, input, settings

Source: [adb-tool/references/sources.md](../../adb-tool/references/sources.md). Items marked (device) come from device tools: confirm options with `adb shell <tool> --help`.

## Files

```
adb push [--sync] [-n] [-z ALGORITHM] [-Z] LOCAL... REMOTE     # -n dry run; -z any|none|brotli|lz4|zstd; -Z no compression
adb pull [-a] [-z ALGORITHM] [-Z] REMOTE... LOCAL              # -a keep time and mode
adb sync [-n] [-l] [all|data|odm|oem|product|system|system_ext|vendor]   # platform developers: build output to device
```

- Shared storage is `/sdcard/` (an alias of the user's storage). `/sdcard/Download`, `/sdcard/DCIM`, `/sdcard/Android/data/<package>` (app-specific external files; access rules differ by Android version, so test with `ls` first).
- App-private data `/data/data/<package>` needs a **debuggable** build (device tool: `adb exec-out run-as <package> cat files/x > out`), root, or an emulator.
- `adb exec-out` returns raw bytes (no pty line-ending translation): use it for binary output.
- Burst Mode (adb 36+, experimental): `ADB_BURST_MODE=1` speeds up large transfers.
- Listing: `adb shell ls -l /sdcard/Download`. Disk: `adb shell df -h /data`.

## Screenshots

```
adb exec-out screencap -p > screen.png          # streams PNG to the host
adb shell screencap /sdcard/screen.png && adb pull /sdcard/screen.png    # fallback
```
Without a filename, `screencap` writes to stdout (`-p` selects PNG). The script verifies the PNG signature and falls back automatically.

## Screen recording

```
adb shell screenrecord [--size WxH] [--bit-rate BPS] [--time-limit SEC] [--rotate] [--verbose] /sdcard/demo.mp4
adb pull /sdcard/demo.mp4
```
Android 4.4+; default max 180 s (also the limit); default bit rate 20 Mbps (`--bit-rate 6000000` for 6 Mbps); no audio; not on Wear OS; screen rotation during recording is not supported; some devices cannot record at native resolution (use `--size 1280x720`). Stop with Ctrl+C. `--rotate` is experimental.

## Display

```
adb shell wm size                  # Physical size: 1080x2400 (and Override size if set)   (device)
adb shell wm size 1280x800         # override
adb shell wm size reset
adb shell wm density 480
adb shell wm density reset
```
The adb page lists the older `am display-size` and `am display-density` for the same purpose. Always reset afterwards.

## Input and keys (device)

```
adb shell input tap X Y
adb shell input swipe X1 Y1 X2 Y2 [DURATION_MS]
adb shell input text hello%sworld        # %s is a space; avoid secrets
adb shell input keyevent 3               # HOME; 4 BACK; 26 POWER; 66 ENTER; 82 MENU; or KEYCODE_HOME
```
For stable UI automation prefer UI Automator / Espresso (see `android-uiautomator-locators`); coordinates break across screen sizes.

## Settings and services (device)

```
adb shell settings get|put|list|delete  system|secure|global  KEY [VALUE]
adb shell settings get global airplane_mode_on
adb shell svc wifi enable|disable       # also: data, power, usb
adb shell getprop ro.build.version.release
adb shell dumpsys battery set level 15 ; adb shell dumpsys battery reset      # simulate battery (reset afterwards)
```
Changing secure/global settings can lock you out of features (for example turning off adb). Write down the old value first.

## Port forwarding

```
adb forward tcp:6100 tcp:7100          # host 6100 -> device 7100
adb forward tcp:6100 local:logd
adb forward --list ; adb forward --remove tcp:6100 ; adb forward --remove-all
adb reverse tcp:8081 tcp:8081          # device 8081 -> host 8081 (for dev servers such as Metro)
adb reverse --list ; adb reverse --remove-all
```

## Reading ART profiles and databases

`adb shell cmd package dump-profiles PACKAGE` then `adb pull /data/misc/profman/PACKAGE.prof.txt` (root or emulator). `adb shell sqlite3 /data/data/PACKAGE/databases/NAME.db` needs root or an emulator.
