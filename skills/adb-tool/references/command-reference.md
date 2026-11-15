# adb command reference

Generated from `scripts/adb_catalog.py` (`python scripts/adb_tool.py catalog --markdown`). Do not edit by hand.
139 commands. Risk: **read** only reads, **change** is reversible, **destructive** can lose data, reboot or weaken security (the script asks for --yes). Source: `doc` = official adb page / adb manual page, `notes` = platform-tools release notes, `device` = a device tool: confirm options with `adb shell <tool> --help`.

## Global options (before the command)

| Command | Syntax | What it does | Risk | Source |
|---|---|---|---|---|
| `-a` | `adb -a ...` | Listen on all network interfaces, not only localhost (the server accepts remote clients; unsafe on shared networks). | change | doc |
| `-d` | `adb -d COMMAND` | Use the USB device. Errors if more than one USB device is connected. | read | doc |
| `-e` | `adb -e COMMAND` | Use the TCP/IP device (emulator). Errors if more than one is available. | read | doc |
| `-s` | `adb -s SERIAL COMMAND` | Use the device with this serial. Overrides $ANDROID_SERIAL. | read | doc |
| `-t` | `adb -t ID COMMAND` | Use the device with this transport ID. | read | doc |
| `-H` | `adb -H HOST COMMAND` | adb server host (default localhost). | read | doc |
| `-P` | `adb -P PORT COMMAND` | adb server smart-socket port (default 5037). | read | doc |
| `-L` | `adb -L SOCKET COMMAND` | Socket the adb server listens on (default tcp:localhost:5037). | read | doc |
| `--one-device` | `adb --one-device SERIAL\|USB start-server` | Server connects to one USB device only (with start-server or server nodaemon). | change | doc |
| `--exit-on-write-error` | `adb --exit-on-write-error COMMAND` | Exit if stdout is closed. | read | doc |

## Server and general

| Command | Syntax | What it does | Risk | Source |
|---|---|---|---|---|
| `start-server` | `adb start-server` | Start the adb server (any adb command also starts it). Listens on TCP 5037. | change | doc |
| `kill-server` | `adb kill-server` | Stop the adb server. Use it when adb does not respond; any later command restarts it. | change | doc |
| `server-status` | `adb server-status` | Show server version, mDNS state/backend, and the log file path. | read | doc |
| `reconnect` | `adb reconnect [device\|offline]` | Reconnect the device (or all offline devices) from the host side. | change | doc |
| `version` | `adb version` | Print the adb client version. | read | doc |
| `help` | `adb help \| adb --help` | List all supported commands. | read | doc |
| `host-features` | `adb host-features` | List features the server supports. | read | doc |
| `features` | `adb features` | List features supported by the server and device. | read | doc |

## Query devices and wait for them

| Command | Syntax | What it does | Risk | Source |
|---|---|---|---|---|
| `devices` | `adb devices [-l]` | List devices with state (device, offline, unauthorized, ...). -l adds product, model, device, transport. | read | doc |
| `get-state` | `adb get-state` | Print device, offline or bootloader. | read | doc |
| `get-serialno` | `adb get-serialno` | Print the device serial number. | read | doc |
| `get-devpath` | `adb get-devpath` | Print the device path. | read | doc |
| `wait-for` | `adb wait-for[-TRANSPORT]-STATE` | Block until the device reaches STATE: device, recovery, rescue, sideload, bootloader, disconnect. TRANSPORT: usb, local, any. | read | doc |

## Wi-Fi, TCP/IP and mDNS

| Command | Syntax | What it does | Risk | Source |
|---|---|---|---|---|
| `pair` | `adb pair HOST[:PORT] [PAIRING_CODE]` | Pair with a device for wireless debugging (Android 11+). Needs the pairing IP:port and six-digit code from the device. | change | doc |
| `pair --qr` | `adb pair --qr` | Pair by showing a QR code in the terminal (platform-tools 37.0.3, canary at the time of checking). | change | notes |
| `connect` | `adb connect HOST[:PORT]` | Connect to a device by TCP/IP (default port 5555). | change | doc |
| `disconnect` | `adb disconnect [HOST[:PORT]]` | Disconnect one TCP/IP device, or all if no argument. | change | doc |
| `tcpip` | `adb tcpip PORT` | Restart adbd on the device listening for TCP/IP (for example 5555). The classic path for Android 10 and lower; needs USB first. Traffic is not encrypted. | change | doc |
| `usb` | `adb usb` | Restart adbd on the device listening on USB again. | change | doc |
| `mdns check` | `adb mdns check` | Check that mDNS discovery is available. | read | doc |
| `mdns services` | `adb mdns services` | List discovered mDNS services (devices ready to pair or connect). | read | doc |
| `mdns track-services` | `adb mdns track-services --proto-text` | Stream discovered services; an empty result means the network blocks mDNS. mdns_service_version 2.0 means ADB Wi-Fi 2.0 (Android 17+). | read | doc |

## Port forwarding

| Command | Syntax | What it does | Risk | Source |
|---|---|---|---|---|
| `forward` | `adb forward [--no-rebind] LOCAL REMOTE` | Forward host LOCAL to device REMOTE, for example tcp:6100 tcp:7100 or tcp:6100 local:logd. Specs: tcp:, localreserved:, localfilesystem:, jdwp:, vsock:, acceptfd:, dev:, dev-raw:. | change | doc |
| `forward --list` | `adb forward --list` | List forward rules. | read | doc |
| `forward --remove` | `adb forward --remove LOCAL` | Remove one forward rule. | change | doc |
| `forward --remove-all` | `adb forward --remove-all` | Remove all forward rules. | change | doc |
| `reverse` | `adb reverse [--no-rebind] REMOTE LOCAL` | Reverse-forward a device port to the host. Specs: tcp:, localabstract:, localreserved:, localfilesystem:. | change | doc |
| `reverse --list` | `adb reverse --list` | List reverse rules. | read | doc |
| `reverse --remove` | `adb reverse --remove REMOTE` | Remove one reverse rule. | change | doc |
| `reverse --remove-all` | `adb reverse --remove-all` | Remove all reverse rules. | change | doc |

## Copy files

| Command | Syntax | What it does | Risk | Source |
|---|---|---|---|---|
| `push` | `adb push [--sync] [-n] [-z ALGORITHM] [-Z] LOCAL... REMOTE` | Copy files or folders to the device. -n dry run; -z compression: any, none, brotli, lz4, zstd; -Z disable compression. Overwrites existing files. | change | doc |
| `pull` | `adb pull [-a] [-z ALGORITHM] [-Z] REMOTE... LOCAL` | Copy files or folders from the device. -a preserves timestamp and mode. | read | doc |
| `sync` | `adb sync [-n] [-l] [-z ALGORITHM] [-Z] [all\|data\|odm\|oem\|product\|system\|system_ext\|vendor]` | Push a build-output partition to the device (platform developers). -n dry run, -l list only. 37.0.3 adds system_dlkm, vendor_dlkm, odm_dlkm. | destructive | doc |

## Shell

| Command | Syntax | What it does | Risk | Source |
|---|---|---|---|---|
| `shell` | `adb shell [-e ESCAPE] [-n] [-Tt] [-x] [COMMAND...]` | Run a command, or open an interactive shell. -e escape char or none; -n no stdin; -T no pty; -t/-tt allocate pty; -x disable exit codes and stdout/stderr split. Quote twice for values with spaces (adb shell setprop key "'two words'"). | change | doc |
| `exec-out` | `adb exec-out COMMAND` | Run a command and return raw binary output with no pty translation, for example adb exec-out screencap -p > screen.png. | read | doc |
| `emu` | `adb emu COMMAND` | Send an emulator console command. | change | doc |

## Install and uninstall apps (adb level)

| Command | Syntax | What it does | Risk | Source |
|---|---|---|---|---|
| `install` | `adb install [-lrtsdg] [--instant] [--abi ABI] [--streaming\|--no-streaming] APK` | Install an APK. -r replace, keep data; -t allow test APKs; -d allow downgrade; -g grant all runtime permissions; -l forward lock; -s on SD card. --fastdeploy is deprecated in 37.0.3 in favour of the android install command. | change | doc |
| `install-multiple` | `adb install-multiple [-lrtsdpg] [--instant] APK...` | Install a split APK set (for example downloaded from Play Console). -p partial install. | change | doc |
| `install-multi-package` | `adb install-multi-package [-lrtsdpg] [--instant] APK...` | Install several packages atomically. | change | doc |
| `uninstall` | `adb uninstall [-k] PACKAGE` | Remove an app. -k keeps data and cache. Deletes the app's data otherwise. | destructive | doc |

## Debugging

| Command | Syntax | What it does | Risk | Source |
|---|---|---|---|---|
| `logcat` | `adb logcat [OPTIONS] [TAG:PRIORITY ...]` | Show the system log. Shorthand for adb shell logcat. See references/logcat.md. | read | doc |
| `bugreport` | `adb bugreport [PATH]` | Create a bug report zip (default bugreport.zip) with dumpsys, dumpstate and logcat. Contains personal data: share with care. | read | doc |
| `jdwp` | `adb jdwp` | List process IDs of debuggable VMs (JDWP). | read | doc |
| `server-status` | `adb server-status` | Server state and log path; set ADB_TRACE=all and restart the server to get a detailed log. | read | doc |

## System, security and reboot

| Command | Syntax | What it does | Risk | Source |
|---|---|---|---|---|
| `root` | `adb root` | Restart adbd as root (userdebug/eng builds and emulators only). | destructive | doc |
| `unroot` | `adb unroot` | Restart adbd without root. | change | doc |
| `remount` | `adb remount [-R]` | Remount partitions read-write (-R reboots if needed). Needs root and a disabled verity. | destructive | doc |
| `disable-verity` | `adb disable-verity` | Disable dm-verity checking. Weakens device integrity. | destructive | doc |
| `enable-verity` | `adb enable-verity` | Re-enable dm-verity checking. | change | doc |
| `keygen` | `adb keygen FILE` | Generate an adb authentication key pair file. | change | doc |
| `reboot` | `adb reboot [bootloader\|recovery\|sideload\|sideload-auto-reboot]` | Reboot the device, optionally into another mode. Unsaved data on the device is lost. | destructive | doc |
| `sideload` | `adb sideload OTAPACKAGE` | Flash an OTA package while the device is in sideload mode. Can brick a device with the wrong package. | destructive | doc |

## USB backend

| Command | Syntax | What it does | Risk | Source |
|---|---|---|---|---|
| `attach` | `adb attach SERIAL` | Attach a USB device to the server (libusb backend only). | change | doc |
| `detach` | `adb detach SERIAL` | Detach a USB device from the server (libusb backend only). | change | doc |

## Activity manager: adb shell am

| Command | Syntax | What it does | Risk | Source |
|---|---|---|---|---|
| `am start` | `adb shell am start [-D] [-W] [-S] [-R COUNT] [--user ID\|current] [--debug-link] INTENT` | Start an activity. -D debug, -W wait for launch, -S force-stop first, -R repeat, --start-profiler FILE, -P FILE, --opengl-trace. --debug-link (Android 17+) explains app-link resolution. | change | doc |
| `am startservice` | `adb shell am startservice [--user ID\|current] INTENT` | Start a service. | change | doc |
| `am force-stop` | `adb shell am force-stop PACKAGE` | Force-stop everything of the package. | change | doc |
| `am kill` | `adb shell am kill [--user ID\|all\|current] PACKAGE` | Kill only processes that are safe to kill. | change | doc |
| `am kill-all` | `adb shell am kill-all` | Kill all background processes. | change | doc |
| `am broadcast` | `adb shell am broadcast [--user ID\|all\|current] INTENT` | Send a broadcast intent. | change | doc |
| `am instrument` | `adb shell am instrument [-r] [-e NAME VALUE] [-p FILE] [-w] [--no-window-animation] [--user ID\|current] TEST_PACKAGE/RUNNER` | Run instrumented tests. -w is required to see results. Runner options (class, package, size, log) via -e; see references/activity-manager.md. | change | doc |
| `am profile` | `adb shell am profile start PROCESS FILE \| profile stop PROCESS` | Start or stop the profiler on a process. | change | doc |
| `am dumpheap` | `adb shell am dumpheap [--user ID\|current] [-b [png\|jpg\|webp]] [-n] PROCESS FILE` | Dump a heap. -n native heap, -b bitmaps (API 35+). | read | doc |
| `am dumpbitmaps` | `adb shell am dumpbitmaps [-d\|--dump [png\|jpg\|webp]] [-p PROCESS]...` | Dump bitmap info/contents into dumpbitmaps-<time>.zip (API 36+). | read | doc |
| `am set-debug-app` | `adb shell am set-debug-app [-w] [--persistent] PACKAGE` | Mark an app to debug; -w waits for the debugger. | change | doc |
| `am clear-debug-app` | `adb shell am clear-debug-app` | Clear the debug app. | change | doc |
| `am monitor` | `adb shell am monitor [--gdb]` | Watch for crashes and ANRs. | read | doc |
| `am screen-compat` | `adb shell am screen-compat {on\|off} PACKAGE` | Control screen compatibility mode of a package. | change | doc |
| `am display-size` | `adb shell am display-size [reset\|WIDTHxHEIGHT]` | Override display size (example 1280x800). Reset afterwards. | change | doc |
| `am display-density` | `adb shell am display-density DPI` | Override display density (example 480). Reset afterwards. | change | doc |
| `am to-uri` | `adb shell am to-uri INTENT` | Print the intent as a URI. | read | doc |
| `am to-intent-uri` | `adb shell am to-intent-uri INTENT` | Print the intent as an intent: URI. | read | doc |
| `am memory-limiter` | `adb shell am memory-limiter ignore UID\|none\|all \| manual PID LIMIT\|max\|none \| status` | Adjust or disable app memory limits on Android 17+. | change | doc |

## Package manager: adb shell pm

| Command | Syntax | What it does | Risk | Source |
|---|---|---|---|---|
| `pm list packages` | `adb shell pm list packages [-f] [-d] [-e] [-s] [-3] [-i] [-u] [--user ID] [FILTER]` | List packages. -f file, -d disabled, -e enabled, -s system, -3 third-party, -i installer, -u include uninstalled. | read | doc |
| `pm list permission-groups` | `adb shell pm list permission-groups` | List permission groups. | read | doc |
| `pm list permissions` | `adb shell pm list permissions [-g] [-f] [-s] [-d] [-u] [GROUP]` | List permissions. -d dangerous only. | read | doc |
| `pm list instrumentation` | `adb shell pm list instrumentation [-f] [TARGET_PACKAGE]` | List test packages. | read | doc |
| `pm list features` | `adb shell pm list features` | List system features. | read | doc |
| `pm list libraries` | `adb shell pm list libraries` | List supported libraries. | read | doc |
| `pm list users` | `adb shell pm list users` | List users. | read | doc |
| `pm path` | `adb shell pm path PACKAGE` | Print the APK path(s) of a package. | read | doc |
| `pm install` | `adb shell pm install [-r] [-t] [-i INSTALLER] [--user ID] [--install-location 0\|1\|2] [-f] [-d] [-g] [--fastdeploy] [--incremental] PATH` | Install a package already on the device. | change | doc |
| `pm uninstall` | `adb shell pm uninstall [-k] [--user ID] [--versionCode CODE] PACKAGE` | Remove a package. | destructive | doc |
| `pm clear` | `adb shell pm clear PACKAGE` | Delete all data of a package. | destructive | doc |
| `pm enable` | `adb shell pm enable PACKAGE_OR_COMPONENT` | Enable a package or component (package/class). | change | doc |
| `pm disable` | `adb shell pm disable PACKAGE_OR_COMPONENT` | Disable a package or component. | change | doc |
| `pm disable-user` | `adb shell pm disable-user [--user ID] PACKAGE_OR_COMPONENT` | Disable for one user. | change | doc |
| `pm grant` | `adb shell pm grant PACKAGE PERMISSION` | Grant a permission declared in the manifest (Android 6+). | change | doc |
| `pm revoke` | `adb shell pm revoke PACKAGE PERMISSION` | Revoke a permission. | change | doc |
| `pm set-install-location` | `adb shell pm set-install-location 0\|1\|2` | Change the default install location (debug only; can break apps). | change | doc |
| `pm get-install-location` | `adb shell pm get-install-location` | Show the install location: 0 auto, 1 internal, 2 external. | read | doc |
| `pm set-permission-enforced` | `adb shell pm set-permission-enforced PERMISSION true\|false` | Enforce or relax a permission. | change | doc |
| `pm trim-caches` | `adb shell pm trim-caches DESIRED_FREE_SPACE` | Trim caches to reach free space. | change | doc |
| `pm create-user` | `adb shell pm create-user NAME` | Create a user; prints its id. | change | doc |
| `pm remove-user` | `adb shell pm remove-user USER_ID` | Remove a user and all its data. | destructive | doc |
| `pm get-max-users` | `adb shell pm get-max-users` | Print the maximum number of users. | read | doc |
| `pm get-app-links` | `adb shell pm get-app-links [--user ID] [PACKAGE]` | Show domain verification state (none, verified, approved, denied, migrated, restored, legacy_failure, system_configured, >=1024 custom error). | read | doc |
| `pm reset-app-links` | `adb shell pm reset-app-links [--user ID] [PACKAGE\|all]` | Reset domain verification state. | change | doc |
| `pm verify-app-links` | `adb shell pm verify-app-links [--re-verify] [PACKAGE]` | Broadcast a verification request. | change | doc |
| `pm set-app-links` | `adb shell pm set-app-links [--package PACKAGE\|all] STATE DOMAINS\|all` | Set domain state: 0 no response, 1 success, 2 approved, 3 denied. | change | doc |
| `pm set-app-links-user-selection` | `adb shell pm set-app-links-user-selection --user ID [--package PACKAGE] ENABLED DOMAINS\|all` | Set a user's link-handling selection. | change | doc |
| `pm set-app-links-allowed` | `adb shell pm set-app-links-allowed --user ID [--package PACKAGE\|all] true\|false` | Toggle auto-verified link handling. | change | doc |
| `pm get-app-link-owners` | `adb shell pm get-app-link-owners --user ID [--package PACKAGE\|all] DOMAINS` | Show owners of a domain, low to high priority. | read | doc |

## Device policy manager: adb shell dpm

| Command | Syntax | What it does | Risk | Source |
|---|---|---|---|---|
| `dpm set-active-admin` | `adb shell dpm set-active-admin [--user ID\|current] COMPONENT` | Set a component as active admin. | change | doc |
| `dpm set-profile-owner` | `adb shell dpm set-profile-owner [--user ID\|current] [--name NAME] COMPONENT` | Set profile owner. | change | doc |
| `dpm set-device-owner` | `adb shell dpm set-device-owner [--user ID\|current] [--name NAME] COMPONENT` | Set device owner. | destructive | doc |
| `dpm remove-active-admin` | `adb shell dpm remove-active-admin [--user ID\|current] COMPONENT` | Remove an active admin (app must be testOnly); also removes device and profile owners. | destructive | doc |
| `dpm clear-freeze-period-record` | `adb shell dpm clear-freeze-period-record` | Clear recorded OTA freeze periods (Android 9+). | change | doc |
| `dpm force-network-logs` | `adb shell dpm force-network-logs` | Make network logs available to the DPC (rate limited, Android 9+). | change | doc |
| `dpm force-security-logs` | `adb shell dpm force-security-logs` | Make security logs available to the DPC (rate limited, Android 9+). | change | doc |

## Screenshots and screen recording

| Command | Syntax | What it does | Risk | Source |
|---|---|---|---|---|
| `screencap` | `adb exec-out screencap -p > screen.png` | Screenshot as PNG streamed to the host. Or adb shell screencap /sdcard/screen.png then adb pull. | read | doc |
| `screenrecord` | `adb shell screenrecord [--size WxH] [--bit-rate BPS] [--time-limit SEC] [--rotate] [--verbose] /sdcard/demo.mp4` | Record the screen (Android 4.4+): max 180 s, no audio, no rotation. Pull the file afterwards. | change | doc |

## Other documented shell commands

| Command | Syntax | What it does | Risk | Source |
|---|---|---|---|---|
| `cmd package dump-profiles` | `adb shell cmd package dump-profiles PACKAGE` | Dump ART profiles as text (root needed to pull /data/misc/profman/PACKAGE.prof.txt). | read | doc |
| `cmd testharness` | `adb shell cmd testharness enable` | Factory-reset a test device (Android 10+) into test-harness state. Erases all data. | destructive | doc |
| `sqlite3` | `adb shell sqlite3 /data/data/PACKAGE/databases/NAME.db` | Inspect an app database (root or emulator only). | read | doc |

## Common device tools (check --help on the device)

| Command | Syntax | What it does | Risk | Source |
|---|---|---|---|---|
| `dumpsys` | `adb shell dumpsys [-l \| SERVICE [ARGS]]` | Dump a system service: package, activity, meminfo, batterystats, gfxinfo, window, display, wifi, connectivity... -l lists services. | read | device |
| `getprop` | `adb shell getprop [KEY]` | Read system properties (ro.product.model, ro.build.version.release, ro.build.version.sdk, ro.product.cpu.abi). | read | device |
| `setprop` | `adb shell setprop KEY VALUE` | Set a system property (many need root). | change | device |
| `settings` | `adb shell settings get\|put\|list\|delete NAMESPACE [KEY [VALUE]]` | Read or change settings (namespaces system, secure, global). | change | device |
| `wm` | `adb shell wm size [WxH\|reset] \| wm density [DPI\|reset]` | Show or override screen size and density. | change | device |
| `input` | `adb shell input tap X Y \| swipe X1 Y1 X2 Y2 [MS] \| text STR \| keyevent CODE` | Send touch, text or key events (KEYCODE_HOME=3, BACK=4, POWER=26). | change | device |
| `svc` | `adb shell svc wifi\|data\|power\|usb enable\|disable` | Toggle Wi-Fi, mobile data and similar. | change | device |
| `monkey` | `adb shell monkey -p PACKAGE [-v] COUNT` | Send pseudo-random UI events to an app (stress test). | change | device |
| `content` | `adb shell content query --uri URI` | Query a content provider. | read | device |
| `uiautomator` | `adb shell uiautomator dump [FILE]` | Dump the UI hierarchy as XML (see the android-uiautomator-locators skill). | read | device |
| `ps / top / df / ip / pidof` | `adb shell ps -A \| top -n 1 \| df -h \| ip addr \| pidof PACKAGE` | Processes, CPU, storage, network addresses, process id of an app. | read | device |
| `rm / mv / cp / mkdir / cat / ls` | `adb shell rm -r PATH ...` | Unix file tools from toybox. rm and mv can lose data. | destructive | device |
| `cmd` | `adb shell cmd -l \| cmd SERVICE help` | Talk to system services (cmd package, cmd jobscheduler, cmd wifi, cmd statusbar ...). | read | device |
| `bmgr` | `adb shell bmgr backupnow PACKAGE` | Back up and restore app data (backup manager). | change | device |

## Environment variables

| Variable | Meaning | Source |
|---|---|---|
| `ANDROID_SERIAL` | Default device serial (same as -s; -s wins). | doc |
| `ANDROID_LOG_TAGS` | Default logcat filter expression when running adb logcat from the host (not exported by adb shell logcat). | doc |
| `ADB_VENDOR_KEYS` | Colon-separated key files or directories used for authentication. | doc |
| `ADB_TRACE` | Debug log categories: all, adb, sockets, packets, rwx, usb, sync, sysdeps, transport, jdwp, services, auth, fdevent, shell, incremental, mdns. Since 37.0.1 accepts a level, for example usb:v,services:w. | doc |
| `ADB_LOCAL_TRANSPORT_MAX_PORT` | Highest emulator port the server scans (default 5585). | doc |
| `ADB_MDNS` | Set to 1 to enable mDNS discovery if server-status shows mdns_enabled false (then kill-server, start-server). | doc |
| `ADB_MDNS_AUTO_CONNECT` | mDNS services allowed to auto-connect (default adb-tls-connect). | doc |
| `ADB_MDNS_OPENSCREEN` | Chooses the openscreen mDNS backend. No effect since platform-tools 37.0.1 (the only backend is libadbmdns). | notes |
| `ADB_LIBUSB` | 1 uses the libusb backend, 0 the native OS backend. Default: libusb except on Windows (and macOS from 37.0.1). | doc |
| `ADB_USB_LEGACY` | Set to 1 to use the legacy USB backend instead of libadbusb (37.0.1 and later). | notes |
| `ADB_USB_LINUX_POLL_INTERVAL_MS` | libadbusb polling interval on Linux (default 1000). | notes |
| `ADB_BURST_MODE` | Set to 1 to enable experimental burst mode (adb 36.0.0 and later): faster large transfers. | doc |
