"""Catalog of adb commands: the single source of truth for references/command-reference.md.

Each entry: (area, command, syntax, description, risk, source)
  risk   : read        = only reads state
           change      = changes device/app/host state but is easy to undo
           destructive = can lose data, reboot, weaken security or is hard to undo
  source : doc    = official page developer.android.com/tools/adb or the adb manual page
           device = a tool on the device; confirm options with `adb shell <tool> --help`
           notes  = platform-tools release notes

Regenerate the markdown with:  python adb_tool.py catalog --markdown > ../references/command-reference.md
"""

AREAS = [
    ("options", "Global options (before the command)"),
    ("server", "Server and general"),
    ("devices", "Query devices and wait for them"),
    ("wireless", "Wi-Fi, TCP/IP and mDNS"),
    ("forward", "Port forwarding"),
    ("files", "Copy files"),
    ("shell", "Shell"),
    ("install", "Install and uninstall apps (adb level)"),
    ("debug", "Debugging"),
    ("system", "System, security and reboot"),
    ("usb", "USB backend"),
    ("am", "Activity manager: adb shell am"),
    ("pm", "Package manager: adb shell pm"),
    ("dpm", "Device policy manager: adb shell dpm"),
    ("screen", "Screenshots and screen recording"),
    ("other", "Other documented shell commands"),
    ("device-tools", "Common device tools (check --help on the device)"),
]

R, C, D = "read", "change", "destructive"

COMMANDS = [
    # ---- global options
    ("options", "-a", "adb -a ...", "Listen on all network interfaces, not only localhost (the server accepts remote clients; unsafe on shared networks).", C, "doc"),
    ("options", "-d", "adb -d COMMAND", "Use the USB device. Errors if more than one USB device is connected.", R, "doc"),
    ("options", "-e", "adb -e COMMAND", "Use the TCP/IP device (emulator). Errors if more than one is available.", R, "doc"),
    ("options", "-s", "adb -s SERIAL COMMAND", "Use the device with this serial. Overrides $ANDROID_SERIAL.", R, "doc"),
    ("options", "-t", "adb -t ID COMMAND", "Use the device with this transport ID.", R, "doc"),
    ("options", "-H", "adb -H HOST COMMAND", "adb server host (default localhost).", R, "doc"),
    ("options", "-P", "adb -P PORT COMMAND", "adb server smart-socket port (default 5037).", R, "doc"),
    ("options", "-L", "adb -L SOCKET COMMAND", "Socket the adb server listens on (default tcp:localhost:5037).", R, "doc"),
    ("options", "--one-device", "adb --one-device SERIAL|USB start-server", "Server connects to one USB device only (with start-server or server nodaemon).", C, "doc"),
    ("options", "--exit-on-write-error", "adb --exit-on-write-error COMMAND", "Exit if stdout is closed.", R, "doc"),
    # ---- server and general
    ("server", "start-server", "adb start-server", "Start the adb server (any adb command also starts it). Listens on TCP 5037.", C, "doc"),
    ("server", "kill-server", "adb kill-server", "Stop the adb server. Use it when adb does not respond; any later command restarts it.", C, "doc"),
    ("server", "server-status", "adb server-status", "Show server version, mDNS state/backend, and the log file path.", R, "doc"),
    ("server", "reconnect", "adb reconnect [device|offline]", "Reconnect the device (or all offline devices) from the host side.", C, "doc"),
    ("server", "version", "adb version", "Print the adb client version.", R, "doc"),
    ("server", "help", "adb help | adb --help", "List all supported commands.", R, "doc"),
    ("server", "host-features", "adb host-features", "List features the server supports.", R, "doc"),
    ("server", "features", "adb features", "List features supported by the server and device.", R, "doc"),
    # ---- devices
    ("devices", "devices", "adb devices [-l]", "List devices with state (device, offline, unauthorized, ...). -l adds product, model, device, transport.", R, "doc"),
    ("devices", "get-state", "adb get-state", "Print device, offline or bootloader.", R, "doc"),
    ("devices", "get-serialno", "adb get-serialno", "Print the device serial number.", R, "doc"),
    ("devices", "get-devpath", "adb get-devpath", "Print the device path.", R, "doc"),
    ("devices", "wait-for", "adb wait-for[-TRANSPORT]-STATE", "Block until the device reaches STATE: device, recovery, rescue, sideload, bootloader, disconnect. TRANSPORT: usb, local, any.", R, "doc"),
    # ---- wireless
    ("wireless", "pair", "adb pair HOST[:PORT] [PAIRING_CODE]", "Pair with a device for wireless debugging (Android 11+). Needs the pairing IP:port and six-digit code from the device.", C, "doc"),
    ("wireless", "pair --qr", "adb pair --qr", "Pair by showing a QR code in the terminal (platform-tools 37.0.3, canary at the time of checking).", C, "notes"),
    ("wireless", "connect", "adb connect HOST[:PORT]", "Connect to a device by TCP/IP (default port 5555).", C, "doc"),
    ("wireless", "disconnect", "adb disconnect [HOST[:PORT]]", "Disconnect one TCP/IP device, or all if no argument.", C, "doc"),
    ("wireless", "tcpip", "adb tcpip PORT", "Restart adbd on the device listening for TCP/IP (for example 5555). The classic path for Android 10 and lower; needs USB first. Traffic is not encrypted.", C, "doc"),
    ("wireless", "usb", "adb usb", "Restart adbd on the device listening on USB again.", C, "doc"),
    ("wireless", "mdns check", "adb mdns check", "Check that mDNS discovery is available.", R, "doc"),
    ("wireless", "mdns services", "adb mdns services", "List discovered mDNS services (devices ready to pair or connect).", R, "doc"),
    ("wireless", "mdns track-services", "adb mdns track-services --proto-text", "Stream discovered services; an empty result means the network blocks mDNS. mdns_service_version 2.0 means ADB Wi-Fi 2.0 (Android 17+).", R, "doc"),
    # ---- forward / reverse
    ("forward", "forward", "adb forward [--no-rebind] LOCAL REMOTE", "Forward host LOCAL to device REMOTE, for example tcp:6100 tcp:7100 or tcp:6100 local:logd. Specs: tcp:, localreserved:, localfilesystem:, jdwp:, vsock:, acceptfd:, dev:, dev-raw:.", C, "doc"),
    ("forward", "forward --list", "adb forward --list", "List forward rules.", R, "doc"),
    ("forward", "forward --remove", "adb forward --remove LOCAL", "Remove one forward rule.", C, "doc"),
    ("forward", "forward --remove-all", "adb forward --remove-all", "Remove all forward rules.", C, "doc"),
    ("forward", "reverse", "adb reverse [--no-rebind] REMOTE LOCAL", "Reverse-forward a device port to the host. Specs: tcp:, localabstract:, localreserved:, localfilesystem:.", C, "doc"),
    ("forward", "reverse --list", "adb reverse --list", "List reverse rules.", R, "doc"),
    ("forward", "reverse --remove", "adb reverse --remove REMOTE", "Remove one reverse rule.", C, "doc"),
    ("forward", "reverse --remove-all", "adb reverse --remove-all", "Remove all reverse rules.", C, "doc"),
    # ---- files
    ("files", "push", "adb push [--sync] [-n] [-z ALGORITHM] [-Z] LOCAL... REMOTE", "Copy files or folders to the device. -n dry run; -z compression: any, none, brotli, lz4, zstd; -Z disable compression. Overwrites existing files.", C, "doc"),
    ("files", "pull", "adb pull [-a] [-z ALGORITHM] [-Z] REMOTE... LOCAL", "Copy files or folders from the device. -a preserves timestamp and mode.", R, "doc"),
    ("files", "sync", "adb sync [-n] [-l] [-z ALGORITHM] [-Z] [all|data|odm|oem|product|system|system_ext|vendor]", "Push a build-output partition to the device (platform developers). -n dry run, -l list only. 37.0.3 adds system_dlkm, vendor_dlkm, odm_dlkm.", D, "doc"),
    # ---- shell
    ("shell", "shell", "adb shell [-e ESCAPE] [-n] [-Tt] [-x] [COMMAND...]", "Run a command, or open an interactive shell. -e escape char or none; -n no stdin; -T no pty; -t/-tt allocate pty; -x disable exit codes and stdout/stderr split. Quote twice for values with spaces (adb shell setprop key \"'two words'\").", C, "doc"),
    ("shell", "exec-out", "adb exec-out COMMAND", "Run a command and return raw binary output with no pty translation, for example adb exec-out screencap -p > screen.png.", R, "doc"),
    ("shell", "emu", "adb emu COMMAND", "Send an emulator console command.", C, "doc"),
    # ---- install
    ("install", "install", "adb install [-lrtsdg] [--instant] [--abi ABI] [--streaming|--no-streaming] APK", "Install an APK. -r replace, keep data; -t allow test APKs; -d allow downgrade; -g grant all runtime permissions; -l forward lock; -s on SD card. --fastdeploy is deprecated in 37.0.3 in favour of the android install command.", C, "doc"),
    ("install", "install-multiple", "adb install-multiple [-lrtsdpg] [--instant] APK...", "Install a split APK set (for example downloaded from Play Console). -p partial install.", C, "doc"),
    ("install", "install-multi-package", "adb install-multi-package [-lrtsdpg] [--instant] APK...", "Install several packages atomically.", C, "doc"),
    ("install", "uninstall", "adb uninstall [-k] PACKAGE", "Remove an app. -k keeps data and cache. Deletes the app's data otherwise.", D, "doc"),
    # ---- debugging
    ("debug", "logcat", "adb logcat [OPTIONS] [TAG:PRIORITY ...]", "Show the system log. Shorthand for adb shell logcat. See references/logcat.md.", R, "doc"),
    ("debug", "bugreport", "adb bugreport [PATH]", "Create a bug report zip (default bugreport.zip) with dumpsys, dumpstate and logcat. Contains personal data: share with care.", R, "doc"),
    ("debug", "jdwp", "adb jdwp", "List process IDs of debuggable VMs (JDWP).", R, "doc"),
    ("debug", "server-status", "adb server-status", "Server state and log path; set ADB_TRACE=all and restart the server to get a detailed log.", R, "doc"),
    # ---- system
    ("system", "root", "adb root", "Restart adbd as root (userdebug/eng builds and emulators only).", D, "doc"),
    ("system", "unroot", "adb unroot", "Restart adbd without root.", C, "doc"),
    ("system", "remount", "adb remount [-R]", "Remount partitions read-write (-R reboots if needed). Needs root and a disabled verity.", D, "doc"),
    ("system", "disable-verity", "adb disable-verity", "Disable dm-verity checking. Weakens device integrity.", D, "doc"),
    ("system", "enable-verity", "adb enable-verity", "Re-enable dm-verity checking.", C, "doc"),
    ("system", "keygen", "adb keygen FILE", "Generate an adb authentication key pair file.", C, "doc"),
    ("system", "reboot", "adb reboot [bootloader|recovery|sideload|sideload-auto-reboot]", "Reboot the device, optionally into another mode. Unsaved data on the device is lost.", D, "doc"),
    ("system", "sideload", "adb sideload OTAPACKAGE", "Flash an OTA package while the device is in sideload mode. Can brick a device with the wrong package.", D, "doc"),
    # ---- usb
    ("usb", "attach", "adb attach SERIAL", "Attach a USB device to the server (libusb backend only).", C, "doc"),
    ("usb", "detach", "adb detach SERIAL", "Detach a USB device from the server (libusb backend only).", C, "doc"),
    # ---- am
    ("am", "am start", "adb shell am start [-D] [-W] [-S] [-R COUNT] [--user ID|current] [--debug-link] INTENT", "Start an activity. -D debug, -W wait for launch, -S force-stop first, -R repeat, --start-profiler FILE, -P FILE, --opengl-trace. --debug-link (Android 17+) explains app-link resolution.", C, "doc"),
    ("am", "am startservice", "adb shell am startservice [--user ID|current] INTENT", "Start a service.", C, "doc"),
    ("am", "am force-stop", "adb shell am force-stop PACKAGE", "Force-stop everything of the package.", C, "doc"),
    ("am", "am kill", "adb shell am kill [--user ID|all|current] PACKAGE", "Kill only processes that are safe to kill.", C, "doc"),
    ("am", "am kill-all", "adb shell am kill-all", "Kill all background processes.", C, "doc"),
    ("am", "am broadcast", "adb shell am broadcast [--user ID|all|current] INTENT", "Send a broadcast intent.", C, "doc"),
    ("am", "am instrument", "adb shell am instrument [-r] [-e NAME VALUE] [-p FILE] [-w] [--no-window-animation] [--user ID|current] TEST_PACKAGE/RUNNER", "Run instrumented tests. -w is required to see results. Runner options (class, package, size, log) via -e; see references/activity-manager.md.", C, "doc"),
    ("am", "am profile", "adb shell am profile start PROCESS FILE | profile stop PROCESS", "Start or stop the profiler on a process.", C, "doc"),
    ("am", "am dumpheap", "adb shell am dumpheap [--user ID|current] [-b [png|jpg|webp]] [-n] PROCESS FILE", "Dump a heap. -n native heap, -b bitmaps (API 35+).", R, "doc"),
    ("am", "am dumpbitmaps", "adb shell am dumpbitmaps [-d|--dump [png|jpg|webp]] [-p PROCESS]...", "Dump bitmap info/contents into dumpbitmaps-<time>.zip (API 36+).", R, "doc"),
    ("am", "am set-debug-app", "adb shell am set-debug-app [-w] [--persistent] PACKAGE", "Mark an app to debug; -w waits for the debugger.", C, "doc"),
    ("am", "am clear-debug-app", "adb shell am clear-debug-app", "Clear the debug app.", C, "doc"),
    ("am", "am monitor", "adb shell am monitor [--gdb]", "Watch for crashes and ANRs.", R, "doc"),
    ("am", "am screen-compat", "adb shell am screen-compat {on|off} PACKAGE", "Control screen compatibility mode of a package.", C, "doc"),
    ("am", "am display-size", "adb shell am display-size [reset|WIDTHxHEIGHT]", "Override display size (example 1280x800). Reset afterwards.", C, "doc"),
    ("am", "am display-density", "adb shell am display-density DPI", "Override display density (example 480). Reset afterwards.", C, "doc"),
    ("am", "am to-uri", "adb shell am to-uri INTENT", "Print the intent as a URI.", R, "doc"),
    ("am", "am to-intent-uri", "adb shell am to-intent-uri INTENT", "Print the intent as an intent: URI.", R, "doc"),
    ("am", "am memory-limiter", "adb shell am memory-limiter ignore UID|none|all | manual PID LIMIT|max|none | status", "Adjust or disable app memory limits on Android 17+.", C, "doc"),
    # ---- pm
    ("pm", "pm list packages", "adb shell pm list packages [-f] [-d] [-e] [-s] [-3] [-i] [-u] [--user ID] [FILTER]", "List packages. -f file, -d disabled, -e enabled, -s system, -3 third-party, -i installer, -u include uninstalled.", R, "doc"),
    ("pm", "pm list permission-groups", "adb shell pm list permission-groups", "List permission groups.", R, "doc"),
    ("pm", "pm list permissions", "adb shell pm list permissions [-g] [-f] [-s] [-d] [-u] [GROUP]", "List permissions. -d dangerous only.", R, "doc"),
    ("pm", "pm list instrumentation", "adb shell pm list instrumentation [-f] [TARGET_PACKAGE]", "List test packages.", R, "doc"),
    ("pm", "pm list features", "adb shell pm list features", "List system features.", R, "doc"),
    ("pm", "pm list libraries", "adb shell pm list libraries", "List supported libraries.", R, "doc"),
    ("pm", "pm list users", "adb shell pm list users", "List users.", R, "doc"),
    ("pm", "pm path", "adb shell pm path PACKAGE", "Print the APK path(s) of a package.", R, "doc"),
    ("pm", "pm install", "adb shell pm install [-r] [-t] [-i INSTALLER] [--user ID] [--install-location 0|1|2] [-f] [-d] [-g] [--fastdeploy] [--incremental] PATH", "Install a package already on the device.", C, "doc"),
    ("pm", "pm uninstall", "adb shell pm uninstall [-k] [--user ID] [--versionCode CODE] PACKAGE", "Remove a package.", D, "doc"),
    ("pm", "pm clear", "adb shell pm clear PACKAGE", "Delete all data of a package.", D, "doc"),
    ("pm", "pm enable", "adb shell pm enable PACKAGE_OR_COMPONENT", "Enable a package or component (package/class).", C, "doc"),
    ("pm", "pm disable", "adb shell pm disable PACKAGE_OR_COMPONENT", "Disable a package or component.", C, "doc"),
    ("pm", "pm disable-user", "adb shell pm disable-user [--user ID] PACKAGE_OR_COMPONENT", "Disable for one user.", C, "doc"),
    ("pm", "pm grant", "adb shell pm grant PACKAGE PERMISSION", "Grant a permission declared in the manifest (Android 6+).", C, "doc"),
    ("pm", "pm revoke", "adb shell pm revoke PACKAGE PERMISSION", "Revoke a permission.", C, "doc"),
    ("pm", "pm set-install-location", "adb shell pm set-install-location 0|1|2", "Change the default install location (debug only; can break apps).", C, "doc"),
    ("pm", "pm get-install-location", "adb shell pm get-install-location", "Show the install location: 0 auto, 1 internal, 2 external.", R, "doc"),
    ("pm", "pm set-permission-enforced", "adb shell pm set-permission-enforced PERMISSION true|false", "Enforce or relax a permission.", C, "doc"),
    ("pm", "pm trim-caches", "adb shell pm trim-caches DESIRED_FREE_SPACE", "Trim caches to reach free space.", C, "doc"),
    ("pm", "pm create-user", "adb shell pm create-user NAME", "Create a user; prints its id.", C, "doc"),
    ("pm", "pm remove-user", "adb shell pm remove-user USER_ID", "Remove a user and all its data.", D, "doc"),
    ("pm", "pm get-max-users", "adb shell pm get-max-users", "Print the maximum number of users.", R, "doc"),
    ("pm", "pm get-app-links", "adb shell pm get-app-links [--user ID] [PACKAGE]", "Show domain verification state (none, verified, approved, denied, migrated, restored, legacy_failure, system_configured, >=1024 custom error).", R, "doc"),
    ("pm", "pm reset-app-links", "adb shell pm reset-app-links [--user ID] [PACKAGE|all]", "Reset domain verification state.", C, "doc"),
    ("pm", "pm verify-app-links", "adb shell pm verify-app-links [--re-verify] [PACKAGE]", "Broadcast a verification request.", C, "doc"),
    ("pm", "pm set-app-links", "adb shell pm set-app-links [--package PACKAGE|all] STATE DOMAINS|all", "Set domain state: 0 no response, 1 success, 2 approved, 3 denied.", C, "doc"),
    ("pm", "pm set-app-links-user-selection", "adb shell pm set-app-links-user-selection --user ID [--package PACKAGE] ENABLED DOMAINS|all", "Set a user's link-handling selection.", C, "doc"),
    ("pm", "pm set-app-links-allowed", "adb shell pm set-app-links-allowed --user ID [--package PACKAGE|all] true|false", "Toggle auto-verified link handling.", C, "doc"),
    ("pm", "pm get-app-link-owners", "adb shell pm get-app-link-owners --user ID [--package PACKAGE|all] DOMAINS", "Show owners of a domain, low to high priority.", R, "doc"),
    # ---- dpm
    ("dpm", "dpm set-active-admin", "adb shell dpm set-active-admin [--user ID|current] COMPONENT", "Set a component as active admin.", C, "doc"),
    ("dpm", "dpm set-profile-owner", "adb shell dpm set-profile-owner [--user ID|current] [--name NAME] COMPONENT", "Set profile owner.", C, "doc"),
    ("dpm", "dpm set-device-owner", "adb shell dpm set-device-owner [--user ID|current] [--name NAME] COMPONENT", "Set device owner.", D, "doc"),
    ("dpm", "dpm remove-active-admin", "adb shell dpm remove-active-admin [--user ID|current] COMPONENT", "Remove an active admin (app must be testOnly); also removes device and profile owners.", D, "doc"),
    ("dpm", "dpm clear-freeze-period-record", "adb shell dpm clear-freeze-period-record", "Clear recorded OTA freeze periods (Android 9+).", C, "doc"),
    ("dpm", "dpm force-network-logs", "adb shell dpm force-network-logs", "Make network logs available to the DPC (rate limited, Android 9+).", C, "doc"),
    ("dpm", "dpm force-security-logs", "adb shell dpm force-security-logs", "Make security logs available to the DPC (rate limited, Android 9+).", C, "doc"),
    # ---- screen
    ("screen", "screencap", "adb exec-out screencap -p > screen.png", "Screenshot as PNG streamed to the host. Or adb shell screencap /sdcard/screen.png then adb pull.", R, "doc"),
    ("screen", "screenrecord", "adb shell screenrecord [--size WxH] [--bit-rate BPS] [--time-limit SEC] [--rotate] [--verbose] /sdcard/demo.mp4", "Record the screen (Android 4.4+): max 180 s, no audio, no rotation. Pull the file afterwards.", C, "doc"),
    # ---- other documented
    ("other", "cmd package dump-profiles", "adb shell cmd package dump-profiles PACKAGE", "Dump ART profiles as text (root needed to pull /data/misc/profman/PACKAGE.prof.txt).", R, "doc"),
    ("other", "cmd testharness", "adb shell cmd testharness enable", "Factory-reset a test device (Android 10+) into test-harness state. Erases all data.", D, "doc"),
    ("other", "sqlite3", "adb shell sqlite3 /data/data/PACKAGE/databases/NAME.db", "Inspect an app database (root or emulator only).", R, "doc"),
    # ---- common device tools (not on the adb page)
    ("device-tools", "dumpsys", "adb shell dumpsys [-l | SERVICE [ARGS]]", "Dump a system service: package, activity, meminfo, batterystats, gfxinfo, window, display, wifi, connectivity... -l lists services.", R, "device"),
    ("device-tools", "getprop", "adb shell getprop [KEY]", "Read system properties (ro.product.model, ro.build.version.release, ro.build.version.sdk, ro.product.cpu.abi).", R, "device"),
    ("device-tools", "setprop", "adb shell setprop KEY VALUE", "Set a system property (many need root).", C, "device"),
    ("device-tools", "settings", "adb shell settings get|put|list|delete NAMESPACE [KEY [VALUE]]", "Read or change settings (namespaces system, secure, global).", C, "device"),
    ("device-tools", "wm", "adb shell wm size [WxH|reset] | wm density [DPI|reset]", "Show or override screen size and density.", C, "device"),
    ("device-tools", "input", "adb shell input tap X Y | swipe X1 Y1 X2 Y2 [MS] | text STR | keyevent CODE", "Send touch, text or key events (KEYCODE_HOME=3, BACK=4, POWER=26).", C, "device"),
    ("device-tools", "svc", "adb shell svc wifi|data|power|usb enable|disable", "Toggle Wi-Fi, mobile data and similar.", C, "device"),
    ("device-tools", "monkey", "adb shell monkey -p PACKAGE [-v] COUNT", "Send pseudo-random UI events to an app (stress test).", C, "device"),
    ("device-tools", "content", "adb shell content query --uri URI", "Query a content provider.", R, "device"),
    ("device-tools", "uiautomator", "adb shell uiautomator dump [FILE]", "Dump the UI hierarchy as XML (see the android-uiautomator-locators skill).", R, "device"),
    ("device-tools", "ps / top / df / ip / pidof", "adb shell ps -A | top -n 1 | df -h | ip addr | pidof PACKAGE", "Processes, CPU, storage, network addresses, process id of an app.", R, "device"),
    ("device-tools", "rm / mv / cp / mkdir / cat / ls", "adb shell rm -r PATH ...", "Unix file tools from toybox. rm and mv can lose data.", D, "device"),
    ("device-tools", "cmd", "adb shell cmd -l | cmd SERVICE help", "Talk to system services (cmd package, cmd jobscheduler, cmd wifi, cmd statusbar ...).", R, "device"),
    ("device-tools", "bmgr", "adb shell bmgr backupnow PACKAGE", "Back up and restore app data (backup manager).", C, "device"),
]

# Environment variables: (name, description, source)
ENV_VARS = [
    ("ANDROID_SERIAL", "Default device serial (same as -s; -s wins).", "doc"),
    ("ANDROID_LOG_TAGS", "Default logcat filter expression when running adb logcat from the host (not exported by adb shell logcat).", "doc"),
    ("ADB_VENDOR_KEYS", "Colon-separated key files or directories used for authentication.", "doc"),
    ("ADB_TRACE", "Debug log categories: all, adb, sockets, packets, rwx, usb, sync, sysdeps, transport, jdwp, services, auth, fdevent, shell, incremental, mdns. Since 37.0.1 accepts a level, for example usb:v,services:w.", "doc"),
    ("ADB_LOCAL_TRANSPORT_MAX_PORT", "Highest emulator port the server scans (default 5585).", "doc"),
    ("ADB_MDNS", "Set to 1 to enable mDNS discovery if server-status shows mdns_enabled false (then kill-server, start-server).", "doc"),
    ("ADB_MDNS_AUTO_CONNECT", "mDNS services allowed to auto-connect (default adb-tls-connect).", "doc"),
    ("ADB_MDNS_OPENSCREEN", "Chooses the openscreen mDNS backend. No effect since platform-tools 37.0.1 (the only backend is libadbmdns).", "notes"),
    ("ADB_LIBUSB", "1 uses the libusb backend, 0 the native OS backend. Default: libusb except on Windows (and macOS from 37.0.1).", "doc"),
    ("ADB_USB_LEGACY", "Set to 1 to use the legacy USB backend instead of libadbusb (37.0.1 and later).", "notes"),
    ("ADB_USB_LINUX_POLL_INTERVAL_MS", "libadbusb polling interval on Linux (default 1000).", "notes"),
    ("ADB_BURST_MODE", "Set to 1 to enable experimental burst mode (adb 36.0.0 and later): faster large transfers.", "doc"),
]

RISKS = (R, C, D)
