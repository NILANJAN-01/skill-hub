#!/usr/bin/env python3
"""adb_tool: one script for everything adb: diagnose, connect, control devices, debug, and look up any adb command.

Python 3.8+, standard library only. Needs adb (Android SDK Platform-Tools) for everything except
`catalog`, `find` and `classify`. Nothing destructive runs without --yes. --dry-run prints the adb
commands instead of running them (read-only queries used to pick a device still run).

  Diagnose   doctor | devices | info
  Connect    wifi pair|connect|disconnect|tcpip|status
  Apps       apps | app-info | install | uninstall | clear | grant | revoke | start | stop
  Files      push | pull | screenshot | record
  Screen     display size|density
  Debug      logcat | dumpsys | snapshot | bugreport
  Anything   run -- <adb args>   (risk-checked)     classify -- <adb args>
  Lookup     find WORDS | catalog [--area A] [--risk R] [--markdown|--json]

Exit codes: 0 ok, 1 a problem was found or the command failed, 2 bad usage, 3 needs --yes.
Official sources: references/sources.md.
"""
import argparse
import datetime
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from collections import namedtuple
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adb_catalog as cat  # noqa: E402

Result = namedtuple("Result", "rc out err cmd")


class Problem(Exception):
    def __init__(self, msg, code=1):
        super().__init__(msg)
        self.code = code


# ---------------------------------------------------------------- locating adb

def adb_candidates():
    exe = "adb.exe" if os.name == "nt" else "adb"
    home = Path.home()
    roots = [os.environ.get("ANDROID_HOME"), os.environ.get("ANDROID_SDK_ROOT"),
             os.path.join(os.environ.get("LOCALAPPDATA", ""), "Android", "Sdk") if os.environ.get("LOCALAPPDATA") else None,
             str(home / "Library" / "Android" / "sdk"), str(home / "Android" / "Sdk")]
    return [Path(r) / "platform-tools" / exe for r in roots if r]


def find_adb(explicit=None):
    """Return the adb path: --adb, $ADB, PATH, then the usual SDK folders; None if not found."""
    for c in (explicit, os.environ.get("ADB")):
        if c and (Path(c).is_file() or shutil.which(c)):
            return shutil.which(c) or str(c)
    found = shutil.which("adb")
    if found:
        return found
    for p in adb_candidates():
        if p.is_file():
            return str(p)
    return None


INSTALL_HELP = (
    "adb was not found. Install Android SDK Platform-Tools:\n"
    "  - Android Studio: SDK Manager > SDK Tools > Android SDK Platform-Tools, or\n"
    "  - command line: sdkmanager \"platform-tools\", or download the zip from\n"
    "    https://developer.android.com/tools/releases/platform-tools and unzip it.\n"
    "Then add the platform-tools folder to PATH (or set ANDROID_HOME), or pass --adb PATH."
)


# ---------------------------------------------------------------- running adb

class Adb:
    def __init__(self, path, serial=None, dry_run=False):
        self.path = path
        self.serial = serial or os.environ.get("ANDROID_SERIAL") or None
        self.dry_run = dry_run
        self._resolved = bool(self.serial)

    def base(self):
        return [self.path] + (["-s", self.serial] if self.serial else [])

    def run(self, args, timeout=60, out_file=None, allow_timeout=False, always=False, global_cmd=False):
        """Run `adb [-s SERIAL] ARGS`. global_cmd=True skips -s (devices, connect, pair...)."""
        cmd = ([self.path] if global_cmd else self.base()) + list(args)
        if self.dry_run and not always:
            print("[dry-run] " + " ".join(shlex.quote(c) for c in cmd))
            return Result(0, "", "", cmd)
        try:
            if out_file:
                with open(out_file, "wb") as fh:
                    p = subprocess.run(cmd, stdout=fh, stderr=subprocess.PIPE, timeout=timeout)
                return Result(p.returncode, "", p.stderr.decode("utf-8", "replace"), cmd)
            p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
            return Result(p.returncode, clean(p.stdout), clean(p.stderr), cmd)
        except subprocess.TimeoutExpired as e:
            if allow_timeout:
                return Result(0, clean(e.stdout or b""), clean(e.stderr or b""), cmd)
            raise Problem("timed out after %ss: %s" % (timeout, " ".join(cmd)))
        except OSError as e:
            raise Problem("could not run adb (%s): %s" % (self.path, e))

    def sh(self, *parts, **kw):
        """adb shell with each part quoted for the device shell (adb passes the string to the remote sh)."""
        return self.run(["shell", " ".join(shlex.quote(str(p)) for p in parts)], **kw)

    def sh_raw(self, command, **kw):
        return self.run(["shell", command], **kw)

    def target(self):
        """Pick the device: --serial, $ANDROID_SERIAL, or the only ready device. Raises if ambiguous."""
        if self._resolved:
            return self.serial
        devs = parse_devices(self.run(["devices", "-l"], always=True, global_cmd=True).out)
        ready = [d for d in devs if d["state"] == "device"]
        if len(ready) == 1:
            self.serial, self._resolved = ready[0]["serial"], True
            return self.serial
        if not devs:
            raise Problem("No device found. Run: adb_tool.py doctor")
        if not ready:
            raise Problem("No device is ready: " + "; ".join("%s is %s" % (d["serial"], d["state"]) for d in devs)
                          + ". Run: adb_tool.py doctor")
        raise Problem("More than one device. Pick one with --serial (or set ANDROID_SERIAL):\n  "
                      + "\n  ".join("%s  %s" % (d["serial"], d.get("model", "")) for d in ready))


def clean(b):
    return (b or b"").decode("utf-8", "replace").replace("\r\r\n", "\n").replace("\r\n", "\n")


# ---------------------------------------------------------------- parsing

STATES = ("device", "offline", "unauthorized", "recovery", "sideload", "bootloader", "rescue",
          "connecting", "authorizing", "host", "no permissions")


def parse_devices(text):
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(("List of devices", "*")):
            continue
        parts = line.split(None, 1)
        if len(parts) < 2:
            continue
        serial, rest = parts
        state = next((s for s in STATES if rest.startswith(s)), None)
        if state is None:
            continue
        tail = rest[len(state):]
        info = dict(re.findall(r"(\w+):(\S+)", tail))
        d = {"serial": serial, "state": state, "detail": tail.strip()}
        d.update({k: v for k, v in info.items() if k in ("product", "model", "device", "transport_id", "usb")})
        out.append(d)
    return out


def parse_version(text):
    """(client protocol version, platform-tools version) from `adb version`."""
    proto = re.search(r"Android Debug Bridge version ([\d.]+)", text)
    tools = re.search(r"^Version (\d+(?:\.\d+)*)", text, re.M)
    return (proto.group(1) if proto else None), (tools.group(1) if tools else None)


def vtuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", v or "")[:3]) or (0,)


def parse_server_status(text):
    kv = {}
    for line in text.splitlines():
        m = re.match(r"\s*([\w]+):\s*\"?([^\"]*)\"?\s*$", line)
        if m:
            kv[m.group(1)] = m.group(2).strip()
    return kv


STATE_HELP = {
    "unauthorized": "Unlock the device and accept the \"Allow USB debugging?\" dialog (tick always allow). No dialog: Developer options > Revoke USB debugging authorizations, replug, then `adb kill-server`.",
    "offline": "Replug the cable (try another cable/port), toggle USB debugging, then `adb reconnect offline` or `adb kill-server`. Update platform-tools if it persists.",
    "no permissions": "Linux: add yourself to the plugdev group (sudo usermod -aG plugdev $LOGNAME, then log out and in) and install udev rules (apt-get install android-sdk-platform-tools-common).",
    "recovery": "Device is in recovery mode; reboot it normally (adb reboot) unless you meant to sideload.",
    "sideload": "Device is in sideload mode; use adb sideload or reboot it.",
    "bootloader": "Device is in the bootloader; adb cannot talk to it. Use fastboot or reboot.",
    "rescue": "Device is in rescue mode; follow the OEM or sideload steps.",
    "connecting": "Still connecting; wait a few seconds and run doctor again.",
    "authorizing": "Waiting for authorization; check the device screen.",
    "host": "Host-side entry; ignore.",
}


# ---------------------------------------------------------------- risk classification

TOP_READ = {"devices", "version", "help", "--help", "get-state", "get-serialno", "get-devpath", "bugreport",
            "jdwp", "server-status", "pull", "features", "host-features", "mdns"}
TOP_CHANGE = {"connect", "disconnect", "pair", "tcpip", "usb", "push", "install", "install-multiple",
              "install-multi-package", "start-server", "kill-server", "reconnect", "unroot", "keygen", "emu",
              "enable-verity", "attach", "detach", "forward", "reverse"}
TOP_DESTRUCTIVE = {"uninstall", "root", "remount", "disable-verity", "reboot", "sideload", "sync"}
SH_DESTRUCTIVE = {"rm", "dd", "mkfs", "wipe", "format", "su", "reboot", "shutdown", "factoryreset", "mv",
                  "fastboot", "umount", "mount", "flash", "recovery"}
SH_READ = {"dumpsys", "getprop", "ls", "cat", "ps", "top", "df", "du", "ip", "pidof", "id", "whoami", "date",
           "uname", "echo", "uptime", "stat", "wc", "grep", "head", "tail", "find", "which", "env", "free",
           "netstat", "ifconfig", "ping", "getevent", "logcat", "printenv", "cut", "sort", "sleep", "true", "pwd"}
SH_CHANGE = {"input", "svc", "monkey", "setprop", "bmgr", "mkdir", "touch", "cp", "chmod", "chown", "screenrecord",
             "start", "stop", "kill", "killall", "am", "ln", "rmdir"}
RANK = {"read": 0, "change": 1, "destructive": 2, "unknown": 2}
WORSE = lambda a, b: a if RANK[a] >= RANK[b] else b  # noqa: E731


def strip_globals(argv):
    argv = list(argv)
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("-s", "-t", "-H", "-P", "-L", "--one-device"):
            i += 2
        elif a in ("-a", "-d", "-e", "--exit-on-write-error"):
            i += 1
        else:
            break
    return argv[i:]


def classify_segment(tokens):
    if not tokens:
        return "read", "empty"
    first, rest = tokens[0], tokens[1:]
    sub = rest[0] if rest else ""
    if first in SH_DESTRUCTIVE:
        return "destructive", "%s can lose data or change the device state" % first
    if first == "sh" and "-c" in rest:
        inner = rest[rest.index("-c") + 1:]
        return classify_shell(inner) if inner else ("unknown", "sh -c without a command")
    if first == "pm":
        if sub in ("uninstall", "clear", "remove-user"):
            return "destructive", "pm %s deletes an app or its data" % sub
        if sub in ("list", "path", "get-install-location", "get-max-users", "get-app-links", "get-app-link-owners"):
            return "read", "pm query"
        return "change", "pm %s changes package state" % sub
    if first == "am":
        if sub in ("to-uri", "to-intent-uri", "dumpheap", "dumpbitmaps", "monitor"):
            return "read", "am query"
        return "change", "am %s changes app or display state" % sub
    if first == "dpm":
        if sub in ("set-device-owner", "remove-active-admin"):
            return "destructive", "dpm %s changes device ownership/admin" % sub
        return "change", "dpm %s" % sub
    if first == "cmd":
        if sub == "testharness":
            return "destructive", "cmd testharness factory-resets the device"
        if sub in ("-l", "") or (rest and rest[-1] in ("help", "--help", "dump-profiles")):
            return "read", "cmd query"
        if sub == "package" and rest[1:2] and rest[1] in ("resolve-activity", "list", "path", "dump-profiles", "query-activities", "dump"):
            return "read", "cmd package query"
        return "change", "cmd %s" % sub
    if first == "settings":
        return ("read", "settings read") if sub in ("get", "list") else ("change", "settings %s changes a setting" % sub)
    if first == "wm":
        return ("read", "wm query") if len(rest) <= 1 else ("change", "wm changes display size or density")
    if first == "content":
        return ("read", "content query") if sub == "query" else ("change", "content %s" % sub)
    if first == "uiautomator":
        return "change", "uiautomator dump writes a file on the device"
    if first == "screencap":
        return ("read", "screencap to stdout") if rest in (["-p"], []) else ("change", "screencap writes a file")
    if first == "logcat":
        return ("change", "logcat clears or resizes buffers") if any(a in ("-c", "-G", "--clear") for a in rest) else ("read", "logcat read")
    if first in SH_READ:
        return "read", "%s is read-only" % first
    if first in SH_CHANGE:
        return "change", "%s changes device state" % first
    return "unknown", "%s is not a known command; check it before running" % first


def classify_shell(tokens):
    tokens = list(tokens)
    while tokens and tokens[0].startswith("-") and tokens[0] != "--":
        tokens = tokens[2:] if tokens[0] == "-e" else tokens[1:]
    if not tokens:
        return "unknown", "an interactive shell can run anything"
    if len(tokens) == 1 and re.search(r"\s", tokens[0]):
        try:
            tokens = shlex.split(tokens[0])
        except ValueError:
            return "unknown", "could not parse the shell command"
    joined = " ".join(tokens)
    risk, why = "read", "read-only"
    segments = [s for s in re.split(r"\s*(?:;|&&|\|\||\|)\s*", joined) if s]
    for seg in segments:
        try:
            toks = shlex.split(seg)
        except ValueError:
            return "unknown", "could not parse: %s" % seg
        if ">" in seg and not re.search(r"2>\s*/dev/null", seg):
            risk, why = WORSE(risk, "change"), "redirects output to a file"
        r, w = classify_segment([t for t in toks if not t.startswith(">")])
        if RANK[r] > RANK[risk] or (risk == "read" and r != "read"):
            risk, why = r, w
    return risk, why


def classify(argv):
    """Risk of an adb command line (after the word `adb`): (risk, reason). risk: read|change|destructive|unknown."""
    a = strip_globals(argv)
    if not a:
        return "read", "no command"
    cmd, rest = a[0], a[1:]
    if cmd == "shell":
        return classify_shell(rest)
    if cmd == "exec-out":
        return classify_shell(rest)
    if cmd == "logcat":
        return ("change", "logcat clears or resizes buffers") if any(x in ("-c", "-G", "--clear") for x in rest) else ("read", "logcat read")
    if cmd in ("forward", "reverse") and "--list" in rest:
        return "read", "list rules"
    if cmd.startswith("wait-for"):
        return "read", "wait"
    if cmd == "mdns":
        return "read", "mDNS query"
    if cmd == "pair" and rest[:1] == ["--qr"]:
        return "change", "pairs a device"
    if cmd in TOP_DESTRUCTIVE:
        return "destructive", "%s can lose data, reboot the device or weaken security" % cmd
    if cmd in TOP_CHANGE:
        return "change", "%s changes device or server state" % cmd
    if cmd in TOP_READ:
        return "read", "%s only reads" % cmd
    return "unknown", "unknown adb command %s" % cmd


def need_yes(args, risk, why, what):
    if getattr(args, "yes", False) or getattr(args, "dry_run", False):
        return
    raise Problem("%s is %s (%s). Ask the user first, then re-run with --yes." % (what, risk, why), 3)


# ---------------------------------------------------------------- doctor / devices / info

def cmd_doctor(args, adb):
    problems = 0
    print("== adb ==")
    print("path: %s" % adb.path)
    v = adb.run(["version"], global_cmd=True, always=True)
    proto, tools = parse_version(v.out)
    print("client: %s, platform-tools: %s" % (proto or "?", tools or "?"))
    if tools and vtuple(tools) < (34,):
        print("[WARN] platform-tools %s is old; update (Wi-Fi pairing, mDNS and USB fixes need newer)." % tools)
    elif tools and vtuple(tools) < (37,):
        print("[INFO] platform-tools %s: 37.0.0 or newer is needed for ADB Wi-Fi 2.0 (also needs Android 17 on the device)." % tools)
    ss = adb.run(["server-status"], global_cmd=True, always=True)
    if ss.rc == 0 and ss.out.strip():
        kv = parse_server_status(ss.out)
        print("server: version=%s mdns_enabled=%s mdns_backend=%s" % (kv.get("version", "?"), kv.get("mdns_enabled", "?"), kv.get("mdns_backend", "?")))
        if kv.get("mdns_enabled") == "false":
            print("[WARN] mDNS is off: set ADB_MDNS=1, then adb kill-server && adb start-server (needed for wireless auto-connect).")
        if kv.get("log_absolute_path"):
            print("server log: %s" % kv["log_absolute_path"])
    else:
        print("server: (server-status not available in this adb; update platform-tools)")
    envs = {k: os.environ[k] for k in os.environ if k.startswith("ADB_") or k in ("ANDROID_SERIAL", "ANDROID_LOG_TAGS")}
    if envs:
        print("env: " + ", ".join("%s=%s" % kv for kv in sorted(envs.items())))
    print("\n== devices ==")
    devs = parse_devices(adb.run(["devices", "-l"], global_cmd=True, always=True).out)
    if not devs:
        problems += 1
        print("[FAIL] No devices listed. Checklist:")
        for step in ("Cable: use a data cable, another port, or another cable.",
                     "Device: enable Developer options > USB debugging; unlock the screen; set USB mode to File transfer.",
                     "Windows: install the OEM USB driver (developer.android.com/studio/run/oem-usb).",
                     "Linux: plugdev group + udev rules (see `doctor` message for 'no permissions').",
                     "Wireless: Android 11+ Wireless debugging, then `adb_tool.py wifi pair HOST:PORT`.",
                     "Reset: adb kill-server, then adb devices."):
            print("  - " + step)
    for d in devs:
        label = "%s  %s" % (d["serial"], d.get("model") or d.get("product") or "")
        if d["state"] == "device":
            boot = type(adb)(adb.path, d["serial"], adb.dry_run).sh("getprop", "sys.boot_completed", always=True)
            note = "" if boot.out.strip() == "1" else " (connected but the system is still booting)"
            print("[ OK ] %s  state=device%s" % (label.strip(), note))
        else:
            problems += 1
            print("[FAIL] %s  state=%s" % (label.strip(), d["state"]))
            print("       fix: " + STATE_HELP.get(d["state"], "see references/connection-troubleshooting.md"))
    if len([d for d in devs if d["state"] == "device"]) > 1 and not adb.serial:
        print("[INFO] More than one device: pass --serial SERIAL (or set ANDROID_SERIAL) or adb says 'more than one device/emulator'.")
    print("\n%s" % ("Problems found: %d" % problems if problems else "No problems found."))
    return 1 if problems else 0


def cmd_devices(args, adb):
    devs = parse_devices(adb.run(["devices", "-l"], global_cmd=True, always=True).out)
    if args.json:
        print(json.dumps(devs, indent=2))
    elif not devs:
        print("No devices. Run: adb_tool.py doctor")
    else:
        for d in devs:
            print("%-24s %-14s %s" % (d["serial"], d["state"], d.get("model", "")))
    return 0 if any(d["state"] == "device" for d in devs) else 1


PROPS = [("manufacturer", "ro.product.manufacturer"), ("model", "ro.product.model"), ("android", "ro.build.version.release"),
         ("sdk", "ro.build.version.sdk"), ("abi", "ro.product.cpu.abi"), ("build_type", "ro.build.type"),
         ("debuggable", "ro.debuggable"), ("fingerprint", "ro.build.fingerprint"), ("boot_completed", "sys.boot_completed")]


def cmd_info(args, adb):
    adb.target()
    info = {"serial": adb.serial}
    for name, key in PROPS:
        info[name] = adb.sh("getprop", key).out.strip()
    info["screen_size"] = adb.sh("wm", "size").out.strip().replace("Physical size: ", "")
    info["screen_density"] = adb.sh("wm", "density").out.strip().replace("Physical density: ", "")
    batt = adb.sh("dumpsys", "battery").out
    m = re.search(r"level:\s*(\d+)", batt)
    info["battery_percent"] = m.group(1) if m else ""
    df = [ln for ln in adb.sh("df", "-h", "/data").out.splitlines() if "/data" in ln]
    info["storage_data"] = " ".join(df[-1].split()) if df else ""
    ip = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", adb.sh_raw("ip -o -4 addr show wlan0").out)
    info["wifi_ip"] = ip.group(1) if ip else ""
    if args.json:
        print(json.dumps(info, indent=2))
    else:
        for k, v in info.items():
            print("%-16s %s" % (k, v))
    return 0


# ---------------------------------------------------------------- wireless

def cmd_wifi(args, adb):
    a = args.action
    if a == "pair":
        if not args.host:
            raise Problem("usage: wifi pair HOST:PORT [--code 123456] (IP, port and code are on the device: Wireless debugging > Pair device with pairing code)", 2)
        cmd = ["pair", args.host] + ([args.code] if args.code else [])
        r = adb.run(cmd, global_cmd=True, timeout=60)
    elif a == "connect":
        if not args.host:
            raise Problem("usage: wifi connect HOST[:PORT] (port is on the Wireless debugging screen, not the pairing port)", 2)
        r = adb.run(["connect", args.host], global_cmd=True, timeout=30)
    elif a == "disconnect":
        r = adb.run(["disconnect"] + ([args.host] if args.host else []), global_cmd=True)
    elif a == "status":
        out = []
        for c in (["mdns", "check"], ["mdns", "services"]):
            x = adb.run(c, global_cmd=True, always=True)
            out.append("$ adb %s\n%s%s" % (" ".join(c), x.out, x.err))
        print("\n".join(out))
        print("If `mdns services` is empty, the network blocks mDNS: connect with `wifi connect IP:PORT` instead.")
        return 0
    elif a == "tcpip":
        adb.target()
        ip = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", adb.sh_raw("ip -o -4 addr show wlan0", always=True).out)
        if not ip and not adb.dry_run:
            raise Problem("Could not read the device Wi-Fi IP (is Wi-Fi on and connected to the same network?).")
        host = ip.group(1) if ip else "DEVICE_IP"
        r = adb.run(["tcpip", str(args.port)])
        if r.rc == 0:
            time.sleep(0 if adb.dry_run else 2)
            r = type(adb)(adb.path, None, adb.dry_run).run(["connect", "%s:%s" % (host, args.port)], global_cmd=True)
            print("Note: adb over tcpip is not encrypted; use it on networks you trust. Return to USB with: adb usb")
    else:
        raise Problem("unknown wifi action", 2)
    print((r.out + r.err).strip())
    if a in ("pair", "connect") and ("failed" in (r.out + r.err).lower() or "unable" in (r.out + r.err).lower() or r.rc != 0):
        print("\nHints: same Wi-Fi network; Android 11+; pairing uses the PAIRING port and code, connect uses the port on the main Wireless debugging screen; "
              "if nothing is discovered run `wifi status` (mDNS) and `doctor`.")
        return 1
    return r.rc


# ---------------------------------------------------------------- apps

def pkg_arg(p):
    if not re.fullmatch(r"[A-Za-z][\w]*(\.[A-Za-z_][\w]*)+", p):
        raise Problem("not a valid package name: %s (example com.example.app)" % p, 2)
    return p


def cmd_apps(args, adb):
    adb.target()
    cmd = ["pm", "list", "packages"]
    if args.system:
        cmd.append("-s")
    elif not args.all:
        cmd.append("-3")
    if args.disabled:
        cmd.append("-d")
    if args.installer:
        cmd.append("-i")
    if args.versions:
        cmd.append("--show-versioncode")
    if args.filter:
        cmd.append(args.filter)
    r = adb.sh(*cmd)
    lines = sorted(ln.replace("package:", "", 1).strip() for ln in r.out.splitlines() if ln.startswith("package:"))
    print("\n".join(lines) if lines else "(no packages)")
    print("%d package(s)" % len(lines), file=sys.stderr)
    return 0 if r.rc == 0 else 1


def parse_dumpsys_package(text):
    def g(rx):
        m = re.search(rx, text)
        return m.group(1) if m else ""
    perms = re.findall(r"^\s+(android\.permission\.[\w.]+|[\w.]+\.permission\.[\w.]+): granted=(true|false)", text, re.M)
    return {"versionName": g(r"versionName=(\S+)"), "versionCode": g(r"versionCode=(\d+)"),
            "minSdk": g(r"minSdk=(\d+)"), "targetSdk": g(r"targetSdk=(\d+)"),
            "installer": g(r"installerPackageName=(\S+)"), "firstInstall": g(r"firstInstallTime=([^\n]+)"),
            "lastUpdate": g(r"lastUpdateTime=([^\n]+)"), "debuggable": "DEBUGGABLE" in text,
            "granted": sorted({p for p, ok in perms if ok == "true"}),
            "denied": sorted({p for p, ok in perms if ok == "false"})}


def cmd_app_info(args, adb):
    adb.target()
    pkg = pkg_arg(args.package)
    path = adb.sh("pm", "path", pkg).out.strip()
    if not path:
        raise Problem("%s is not installed on %s" % (pkg, adb.serial))
    info = parse_dumpsys_package(adb.sh("dumpsys", "package", pkg).out)
    pid = adb.sh("pidof", pkg).out.strip()
    info.update({"package": pkg, "apk": [p.replace("package:", "") for p in path.splitlines()], "running_pid": pid or None})
    if args.json:
        print(json.dumps(info, indent=2))
    else:
        for k in ("package", "versionName", "versionCode", "minSdk", "targetSdk", "installer", "debuggable", "running_pid", "firstInstall", "lastUpdate"):
            print("%-14s %s" % (k, info.get(k)))
        print("apk            " + ", ".join(info["apk"]))
        print("granted        %d  denied %d (use --json for the lists)" % (len(info["granted"]), len(info["denied"])))
    return 0


def cmd_install(args, adb):
    adb.target()
    apks = [Path(p) for p in args.apk]
    for p in apks:
        if not p.is_file():
            raise Problem("file not found: %s" % p, 2)
        if p.suffix.lower() in (".aab", ".apks"):
            raise Problem("%s is not installable with adb install. Use bundletool to build/install from an .aab/.apks, or give the split .apk files." % p, 2)
    flags = [f for f, on in (("-r", args.replace), ("-t", args.test), ("-d", args.downgrade), ("-g", args.grant)) if on]
    cmd = (["install-multiple"] if len(apks) > 1 else ["install"]) + flags + [str(p) for p in apks]
    r = adb.run(cmd, timeout=600)
    print((r.out + r.err).strip())
    if r.rc != 0 or "Failure" in r.out:
        m = re.search(r"INSTALL_\w+", r.out + r.err)
        if m:
            print("Hint: " + INSTALL_FAIL.get(m.group(0), "see references/apps-and-packages.md (install errors)"))
        return 1
    return 0


INSTALL_FAIL = {
    "INSTALL_FAILED_UPDATE_INCOMPATIBLE": "signature differs from the installed app: uninstall the old one first (that deletes its data) after the user agrees.",
    "INSTALL_FAILED_VERSION_DOWNGRADE": "installed version is newer: use -d (debuggable apps) or uninstall first.",
    "INSTALL_FAILED_OLDER_SDK": "the device API level is below the app's minSdk.",
    "INSTALL_FAILED_INSUFFICIENT_STORAGE": "free up space on the device.",
    "INSTALL_FAILED_ALREADY_EXISTS": "use -r to replace the existing app.",
    "INSTALL_FAILED_TEST_ONLY": "this is a test APK: add -t.",
    "INSTALL_FAILED_NO_MATCHING_ABIS": "the app has no native libraries for this device ABI.",
    "INSTALL_PARSE_FAILED_NO_CERTIFICATES": "the APK is not signed.",
    "INSTALL_FAILED_USER_RESTRICTED": "the device blocks USB installs: allow Install via USB in Developer options.",
}


def cmd_uninstall(args, adb):
    adb.target()
    pkg = pkg_arg(args.package)
    need_yes(args, "destructive", "removes the app" + ("" if args.keep_data else " and deletes its data"), "uninstall %s" % pkg)
    r = adb.run(["uninstall"] + (["-k"] if args.keep_data else []) + [pkg])
    print((r.out + r.err).strip())
    return 0 if r.rc == 0 and "Success" in r.out or adb.dry_run else 1


def cmd_clear(args, adb):
    adb.target()
    pkg = pkg_arg(args.package)
    need_yes(args, "destructive", "deletes all data of the app", "clear %s" % pkg)
    r = adb.sh("pm", "clear", pkg)
    print((r.out + r.err).strip())
    return 0 if adb.dry_run or "Success" in r.out else 1


def cmd_perm(args, adb):
    adb.target()
    pkg = pkg_arg(args.package)
    perm = args.permission if "." in args.permission else "android.permission." + args.permission
    r = adb.sh("pm", args.cmd, pkg, perm)
    print((r.out + r.err).strip() or "ok")
    return r.rc


def resolve_launcher(adb, pkg):
    r = adb.sh("cmd", "package", "resolve-activity", "--brief", pkg)
    comps = [ln.strip() for ln in r.out.splitlines() if "/" in ln and " " not in ln.strip()]
    return comps[-1] if comps else None


def cmd_start(args, adb):
    adb.target()
    target = args.target
    cmd = ["am", "start"] + (["-W"] if args.wait else []) + (["-S"] if args.stop_first else [])
    if "/" in target:
        cmd += ["-n", target]
    else:
        pkg = pkg_arg(target)
        comp = resolve_launcher(adb, pkg)
        if comp:
            cmd += ["-n", comp]
        else:
            r = adb.sh("monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1")
            print(r.out.strip())
            return r.rc
    r = adb.sh(*cmd)
    print((r.out + r.err).strip())
    return 0 if r.rc == 0 and "Error" not in r.out else 1


def cmd_stop(args, adb):
    adb.target()
    r = adb.sh("am", "force-stop", pkg_arg(args.package))
    print((r.out + r.err).strip() or "stopped")
    return r.rc


# ---------------------------------------------------------------- files and screen

def stamp():
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def cmd_push(args, adb):
    adb.target()
    for p in args.local:
        if not Path(p).exists():
            raise Problem("local path not found: %s" % p, 2)
    r = adb.run(["push"] + list(args.local) + [args.remote], timeout=1800)
    print((r.out + r.err).strip())
    return r.rc


def cmd_pull(args, adb):
    adb.target()
    r = adb.run(["pull"] + list(args.remote) + [args.local], timeout=1800)
    print((r.out + r.err).strip())
    return r.rc


def cmd_screenshot(args, adb):
    adb.target()
    out = Path(args.out or "screenshot-%s.png" % stamp())
    r = adb.run(["exec-out", "screencap", "-p"], out_file=str(out), timeout=60)
    ok = adb.dry_run or (r.rc == 0 and out.exists() and out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n")
    if not ok:
        # some devices/old adb corrupt binary stdout: use a file on the device
        remote = "/sdcard/_adb_tool_%s.png" % stamp()
        adb.sh("screencap", "-p", remote)
        r = adb.run(["pull", remote, str(out)])
        adb.sh("rm", remote)
        ok = r.rc == 0 and out.exists()
    print("saved %s" % out if ok else "screenshot failed: %s" % r.err.strip())
    return 0 if ok else 1


def cmd_record(args, adb):
    adb.target()
    secs = max(1, min(args.time, 180))
    out = Path(args.out or "screenrecord-%s.mp4" % stamp())
    remote = "/sdcard/_adb_tool_%s.mp4" % stamp()
    cmd = ["screenrecord", "--time-limit", str(secs)]
    if args.size:
        cmd += ["--size", args.size]
    if args.bit_rate:
        cmd += ["--bit-rate", str(args.bit_rate)]
    r = adb.sh(*(cmd + [remote]), timeout=secs + 30)
    if r.rc != 0 and not adb.dry_run:
        print("screenrecord failed: %s" % (r.out + r.err).strip())
        return 1
    p = adb.run(["pull", remote, str(out)], timeout=300)
    if p.rc == 0:
        adb.sh("rm", remote)  # our own temp file
        print("saved %s (no audio, max 180 s)" % out)
    return p.rc


def cmd_display(args, adb):
    adb.target()
    what = args.what
    if args.value is None:
        print(adb.sh("wm", what).out.strip())
        return 0
    if args.value != "reset" and not re.fullmatch(r"\d+x\d+" if what == "size" else r"\d+", args.value):
        raise Problem("value must be %s or reset" % ("WIDTHxHEIGHT" if what == "size" else "a dpi number"), 2)
    r = adb.sh("wm", what, args.value)
    print((r.out + r.err).strip() or "ok (undo with: display %s reset)" % what)
    return r.rc


# ---------------------------------------------------------------- debug

def build_logcat(args, pid=None):
    cmd = ["logcat"]
    if args.clear:
        return ["logcat", "-c"]
    if args.crash:
        cmd += ["-b", "crash"]
    elif args.buffer:
        cmd += ["-b", args.buffer]
    cmd += ["-v", args.format]
    if args.since:
        cmd += ["-T", args.since]
    if not args.follow:
        cmd += ["-d"]
        if args.lines and not args.since:
            cmd += ["-t", str(args.lines)]
    if pid:
        cmd += ["--pid", str(pid)]
    filters = []
    for t in args.tag or []:
        filters.append(t if ":" in t else t + ":V")
    if filters:
        cmd += filters + ["*:S"]
    elif args.level:
        cmd += ["*:" + args.level.upper()]
    return cmd


def cmd_logcat(args, adb):
    adb.target()
    pid = None
    if args.package:
        pid = adb.sh("pidof", pkg_arg(args.package)).out.split()
        if not pid:
            print("%s is not running; showing no process filter. Start the app and retry." % args.package, file=sys.stderr)
        else:
            pid = pid[0]
    cmd = build_logcat(args, pid or None)
    if args.clear:
        r = adb.run(cmd)
        print("log buffers cleared" if r.rc == 0 else r.err)
        return r.rc
    r = adb.run(cmd, timeout=(args.seconds + 5) if args.follow else 120, allow_timeout=args.follow)
    text = r.out
    if args.grep:
        try:
            rx = re.compile(args.grep, re.I)
        except re.error as e:
            raise Problem("bad --grep regex: %s" % e, 2)
        text = "\n".join(ln for ln in text.splitlines() if rx.search(ln)) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print("wrote %s (%d lines). Analyse it with the android-logcat-analyzer skill." % (args.out, text.count("\n")))
    else:
        sys.stdout.write(text)
    return 0 if r.rc == 0 else 1


def cmd_dumpsys(args, adb):
    adb.target()
    r = adb.sh("dumpsys", *(["-l"] if not args.service else [args.service] + list(args.extra or [])), timeout=120)
    if args.out and args.service:
        Path(args.out).write_text(r.out, encoding="utf-8")
        print("wrote %s (%d lines)" % (args.out, r.out.count("\n")))
    else:
        sys.stdout.write(r.out)
    return 0 if r.rc == 0 else 1


def cmd_snapshot(args, adb):
    adb.target()
    d = Path(args.out or "adb-snapshot-%s" % stamp())
    d.mkdir(parents=True, exist_ok=True)
    pkg = pkg_arg(args.package) if args.package else None
    jobs = [("properties.txt", ["getprop"]), ("battery.txt", ["dumpsys", "battery"]),
            ("activity-top.txt", ["dumpsys", "activity", "top"]), ("processes.txt", ["ps", "-A"]),
            ("storage.txt", ["df", "-h"]), ("display.txt", ["wm", "size"]),
            ("meminfo.txt", ["dumpsys", "meminfo"] + ([pkg] if pkg else []))]
    if pkg:
        jobs += [("gfxinfo.txt", ["dumpsys", "gfxinfo", pkg]), ("package.txt", ["dumpsys", "package", pkg])]
    wrote = []
    for name, c in jobs:
        r = adb.sh(*c, timeout=120)
        (d / name).write_text(r.out + (("\n[stderr]\n" + r.err) if r.err.strip() else ""), encoding="utf-8")
        wrote.append(name)
    lg = adb.run(["logcat", "-b", "all", "-d", "-t", "2000", "-v", "threadtime"], timeout=120)
    (d / "logcat-last-2000.txt").write_text(lg.out, encoding="utf-8")
    wrote.append("logcat-last-2000.txt")
    print("snapshot in %s: %s" % (d, ", ".join(wrote)))
    return 0


def cmd_bugreport(args, adb):
    adb.target()
    out = args.out or "."
    r = adb.run(["bugreport", out], timeout=900)
    print((r.out + r.err).strip())
    print("A bug report holds personal data (accounts, app lists, logs): share it only with people who need it.")
    return r.rc


# ---------------------------------------------------------------- run / classify / catalog / find

SERVER_LEVEL = {"start-server", "kill-server", "version", "help", "--help", "devices", "connect", "disconnect",
                "pair", "mdns", "server-status", "reconnect", "keygen"}


def cmd_run(args, adb):
    argv = [a for a in args.adb_args if a != "--"]
    if not argv:
        raise Problem("usage: run [--yes] -- ADB_ARGS (example: run -- shell getprop ro.product.model)", 2)
    risk, why = classify(argv)
    print("[risk: %s] %s" % (risk, why), file=sys.stderr)
    if risk in ("destructive", "unknown"):
        need_yes(args, risk, why, "adb " + " ".join(argv))
    stripped = strip_globals(argv)
    own_globals = len(stripped) != len(argv)  # the user passed -s/-d/-e/...: leave them as given
    server_level = bool(stripped) and stripped[0] in SERVER_LEVEL
    if not server_level and not own_globals:
        adb.target()
    glob = server_level or own_globals
    r = adb.run(argv, timeout=args.timeout, global_cmd=glob)
    sys.stdout.write(r.out)
    sys.stderr.write(r.err)
    return r.rc


def cmd_classify(args, adb):
    argv = [a for a in args.adb_args if a != "--"]
    risk, why = classify(argv)
    print("%s: %s" % (risk, why))
    return 0


def markdown():
    n = len(cat.COMMANDS)
    lines = ["# adb command reference", "",
             "Generated from `scripts/adb_catalog.py` (`python scripts/adb_tool.py catalog --markdown`). Do not edit by hand.",
             "%d commands. Risk: **read** only reads, **change** is reversible, **destructive** can lose data, reboot or weaken security (the script asks for --yes). "
             "Source: `doc` = official adb page / adb manual page, `notes` = platform-tools release notes, `device` = a device tool: confirm options with `adb shell <tool> --help`." % n, ""]
    for key, title in cat.AREAS:
        rows = [c for c in cat.COMMANDS if c[0] == key]
        if not rows:
            continue
        lines += ["## %s" % title, "", "| Command | Syntax | What it does | Risk | Source |", "|---|---|---|---|---|"]
        for _, name, syn, desc, risk, src in rows:
            lines.append("| `%s` | `%s` | %s | %s | %s |" % (name, syn.replace("|", "\\|"), desc.replace("|", "\\|"), risk, src))
        lines.append("")
    lines += ["## Environment variables", "", "| Variable | Meaning | Source |", "|---|---|---|"]
    for name, desc, src in cat.ENV_VARS:
        lines.append("| `%s` | %s | %s |" % (name, desc.replace("|", "\\|"), src))
    return "\n".join(lines) + "\n"


def cmd_catalog(args, adb):
    if args.markdown:
        sys.stdout.write(markdown())
        return 0
    rows = [c for c in cat.COMMANDS if (not args.area or c[0] == args.area) and (not args.risk or c[4] == args.risk)]
    if args.json:
        print(json.dumps([dict(zip(("area", "command", "syntax", "description", "risk", "source"), c)) for c in rows], indent=2))
        return 0
    if args.area is None and not args.risk:
        print("Areas: " + ", ".join("%s (%d)" % (k, sum(1 for c in cat.COMMANDS if c[0] == k)) for k, _ in cat.AREAS))
    for c in rows:
        print("[%s] %s\n    %s\n    %s" % (c[4], c[2], c[3], "(source: %s)" % c[5]))
    return 0


def cmd_find(args, adb):
    words = [w.lower() for w in args.words]

    def score(c, need_all):
        hay = " ".join((c[0], c[1], c[2], c[3])).lower()
        hits = [w for w in words if w in hay]
        if (need_all and len(hits) != len(words)) or not hits:
            return 0
        return sum(hay.count(w) + (3 if w in c[1].lower() else 0) for w in hits)

    for need_all in (True, False):
        scored = sorted(((score(c, need_all), c) for c in cat.COMMANDS), key=lambda x: -x[0])
        scored = [x for x in scored if x[0]]
        if scored:
            break
    if not scored:
        print("No match. Try other words, `catalog`, or `adb help`.")
        return 1
    for _, c in scored[:args.limit]:
        print("[%s] %s\n    %s" % (c[4], c[2], c[3]))
    return 0


# ---------------------------------------------------------------- main

def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-s", "--serial", help="target device serial (or set ANDROID_SERIAL)")
    common.add_argument("--adb", help="path to the adb executable (or set ADB)")
    common.add_argument("--dry-run", action="store_true", help="print adb commands instead of running them")
    common.add_argument("--yes", action="store_true", help="confirm a destructive step (only after the user agreed)")

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, fn, help_):
        p = sub.add_parser(name, parents=[common], help=help_)
        p.set_defaults(fn=fn)
        return p

    add("doctor", cmd_doctor, "check adb, server and devices; explain problems")
    add("devices", cmd_devices, "list devices").add_argument("--json", action="store_true")
    add("info", cmd_info, "device snapshot: model, Android, ABI, screen, battery, storage, IP").add_argument("--json", action="store_true")

    p = add("wifi", cmd_wifi, "wireless adb: pair, connect, disconnect, tcpip, status")
    p.add_argument("action", choices=["pair", "connect", "disconnect", "tcpip", "status"])
    p.add_argument("host", nargs="?")
    p.add_argument("--code")
    p.add_argument("--port", type=int, default=5555)

    p = add("apps", cmd_apps, "list packages (third-party by default)")
    p.add_argument("--system", action="store_true")
    p.add_argument("--all", action="store_true")
    p.add_argument("--disabled", action="store_true")
    p.add_argument("--installer", action="store_true")
    p.add_argument("--versions", action="store_true")
    p.add_argument("--filter")
    p = add("app-info", cmd_app_info, "version, SDKs, permissions, APK path, running pid of a package")
    p.add_argument("package")
    p.add_argument("--json", action="store_true")
    p = add("install", cmd_install, "install one APK, or a split set with several")
    p.add_argument("apk", nargs="+")
    p.add_argument("-r", "--replace", action="store_true")
    p.add_argument("-t", "--test", action="store_true")
    p.add_argument("-d", "--downgrade", action="store_true")
    p.add_argument("-g", "--grant", action="store_true")
    p = add("uninstall", cmd_uninstall, "uninstall an app (needs --yes)")
    p.add_argument("package")
    p.add_argument("-k", "--keep-data", action="store_true")
    p = add("clear", cmd_clear, "delete all data of an app (needs --yes)")
    p.add_argument("package")
    for nm in ("grant", "revoke"):
        p = add(nm, cmd_perm, "%s a runtime permission" % nm)
        p.add_argument("package")
        p.add_argument("permission")
        p.set_defaults(cmd=nm)
    p = add("start", cmd_start, "start an app by package or package/.Activity")
    p.add_argument("target")
    p.add_argument("-W", "--wait", action="store_true")
    p.add_argument("-S", "--stop-first", action="store_true")
    add("stop", cmd_stop, "force-stop an app").add_argument("package")

    p = add("push", cmd_push, "copy local files to the device")
    p.add_argument("local", nargs="+")
    p.add_argument("remote")
    p = add("pull", cmd_pull, "copy device files to the host")
    p.add_argument("remote", nargs="+")
    p.add_argument("local")
    add("screenshot", cmd_screenshot, "PNG screenshot to a file").add_argument("out", nargs="?")
    p = add("record", cmd_record, "record the screen (max 180 s, no audio) and pull the video")
    p.add_argument("out", nargs="?")
    p.add_argument("--time", type=int, default=30)
    p.add_argument("--size")
    p.add_argument("--bit-rate", type=int)
    p = add("display", cmd_display, "show or override screen size/density (reset to undo)")
    p.add_argument("what", choices=["size", "density"])
    p.add_argument("value", nargs="?")

    p = add("logcat", cmd_logcat, "dump or follow the log with filters")
    p.add_argument("--lines", type=int, default=500)
    p.add_argument("--follow", action="store_true")
    p.add_argument("--seconds", type=int, default=15, help="with --follow: stop after N seconds")
    p.add_argument("--level", choices=list("VDIWEFSvdiwefs"), help="minimum priority for all tags")
    p.add_argument("--tag", action="append", help="TAG or TAG:PRIORITY (repeatable); hides other tags")
    p.add_argument("--package", help="only this running app (by pid)")
    p.add_argument("--crash", action="store_true", help="crash buffer only")
    p.add_argument("--buffer", help="main,system,crash,radio,events,all")
    p.add_argument("--format", default="threadtime")
    p.add_argument("--since", help="start time, e.g. '11-15 09:30:00.000'")
    p.add_argument("--grep", help="host-side regex filter")
    p.add_argument("--out")
    p.add_argument("--clear", action="store_true", help="clear the log buffers")
    p = add("dumpsys", cmd_dumpsys, "list services, or dump one")
    p.add_argument("service", nargs="?")
    p.add_argument("extra", nargs="*")
    p.add_argument("--out")
    p = add("snapshot", cmd_snapshot, "collect props, battery, memory, top activity, processes, storage, recent log into a folder")
    p.add_argument("--package")
    p.add_argument("--out")
    add("bugreport", cmd_bugreport, "create a bug report zip").add_argument("out", nargs="?")

    p = add("run", cmd_run, "run any adb command, risk-checked")
    p.add_argument("--timeout", type=int, default=120)
    p.add_argument("adb_args", nargs=argparse.REMAINDER)
    p = add("classify", cmd_classify, "show the risk of an adb command without running it")
    p.add_argument("adb_args", nargs=argparse.REMAINDER)

    p = add("catalog", cmd_catalog, "print the adb command catalog")
    p.add_argument("--area", choices=[k for k, _ in cat.AREAS])
    p.add_argument("--risk", choices=cat.RISKS)
    p.add_argument("--markdown", action="store_true")
    p.add_argument("--json", action="store_true")
    p = add("find", cmd_find, "find adb commands by keyword")
    p.add_argument("words", nargs="+")
    p.add_argument("--limit", type=int, default=12)
    return ap


NO_ADB = {"catalog", "find", "classify"}


def main(argv=None, adb_factory=None):
    args = build_parser().parse_args(argv)
    try:
        if args.cmd in NO_ADB:
            return args.fn(args, None)
        path = find_adb(args.adb)
        if not path:
            print(INSTALL_HELP, file=sys.stderr)
            return 1
        adb = (adb_factory or Adb)(path, args.serial, args.dry_run)
        return args.fn(args, adb)
    except Problem as e:
        print(str(e), file=sys.stderr)
        return e.code
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
