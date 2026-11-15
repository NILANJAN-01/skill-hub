# Connection troubleshooting

Source: [adb-tool/references/sources.md](../../adb-tool/references/sources.md).

## Device states in `adb devices`

| State | Meaning | Fix |
|---|---|---|
| `device` | Connected to the server. Does not prove Android finished booting: check `adb shell getprop sys.boot_completed` is `1` | Normal state |
| `offline` | Not connected or not responding | Replug, toggle USB debugging, `adb reconnect offline`, `adb kill-server`, update Platform-Tools |
| `unauthorized` | The device has not accepted this computer's key | Unlock, accept the dialog; or revoke authorizations and replug |
| `no permissions (...)` | Linux udev/plugdev | plugdev group + udev rules |
| `recovery`, `sideload`, `rescue` | Device is in that mode | Reboot normally (`adb reboot`) unless you meant to use it |
| `bootloader` | adb cannot talk to a bootloader | `fastboot` or reboot |
| `connecting`, `authorizing` | In progress | Wait; check the device screen |
| (not listed) | No link at all | Cable, driver, USB debugging, unlock, another port |

## Decision tree

1. `adb version` fails: install/PATH ([install-and-usb.md](install-and-usb.md)).
2. `adb devices` empty: cable, USB debugging, driver, unlock, USB mode; `adb kill-server`.
3. Wrong state: table above.
4. More than one device: `-s SERIAL`, `-d`, `-e`, or `ANDROID_SERIAL` (`-s` beats the variable).
5. Works over USB but not Wi-Fi: [wireless-debugging.md](wireless-debugging.md).
6. Server problems: `adb kill-server`; check nothing else listens on 5037; one adb copy on PATH; `adb -P PORT` runs against a server on another port when 5037 is taken.
7. Still stuck: `ADB_TRACE=all`, restart the server, reproduce, read the log from `adb server-status`.

## How adb finds devices (useful for odd cases)

The server listens on TCP 5037. It finds emulators by scanning odd ports 5555 to 5585 (each emulator uses an even console port and the next odd adb port: 5554/5555, 5556/5557, ...). `ADB_LOCAL_TRANSPORT_MAX_PORT` raises the limit. If an emulator started with `-port` is missing, stop the server, start the server, then list devices (`adb kill-server`, `adb start-server`, `adb devices`).

## USB backends

adb talks to USB through the OS backend or libusb. Platform-Tools 37.0.1 and later ship `libadbusb` (Windows, macOS, Linux) and `ADB_USB_LEGACY=1` selects the legacy one; `ADB_LIBUSB=1/0` still selects libusb or native where supported. If devices disappear after an update, try the other backend with these variables, then restart the server.

## Environment variables that change behaviour

`ANDROID_SERIAL`, `ADB_VENDOR_KEYS`, `ADB_TRACE`, `ADB_MDNS`, `ADB_MDNS_AUTO_CONNECT`, `ADB_LIBUSB`, `ADB_USB_LEGACY`, `ADB_BURST_MODE`. The doctor prints any that are set: a stale `ANDROID_SERIAL` pointing at an unplugged device is a classic cause of "device not found".
