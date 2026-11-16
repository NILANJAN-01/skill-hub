#!/usr/bin/env python3
"""Capture the current screen of a connected Android device with `uiautomator dump`, pull the XML
over adb, and generate the locator JSON (keyword names -> resource ids + selectors) in one step.

    python capture_and_convert.py                               # current screen -> dumps/<screen>.xml + locators/<screen>.locators.json
    python capture_and_convert.py --name media_home             # choose the screen name
    python capture_and_convert.py --serial emulator-5554        # pick a device when several are connected
    python capture_and_convert.py --interactive                 # capture screen after screen: Enter = capture, q = quit
    python capture_and_convert.py --exclude-package com.android.systemui --case upper

Needs adb (Android platform-tools) on PATH, or pass --adb / set ADB. Standard library only (Python 3.8+).
The JSON is produced by dump_to_locators.py from the same folder, so it is identical to converting a
dump file by hand.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import dump_to_locators as d2l  # noqa: E402

DEVICE_TMP = "/sdcard/skillhub_window_dump.xml"
RETRYABLE = ("could not get idle state", "null root node", "ERROR: could not")


class CaptureError(RuntimeError):
    """Something went wrong talking to the device; the message says what to do."""


class Adb:
    """Thin wrapper around the adb executable. `exe` may also be a .py file (used by the tests)."""

    def __init__(self, exe: str, serial: str = "", timeout: int = 60):
        self.base = [sys.executable, exe] if exe.endswith(".py") else [exe]
        self.serial = serial
        self.timeout = timeout

    def run(self, *args: str, device: bool = True) -> str:
        cmd = list(self.base)
        if device and self.serial:
            cmd += ["-s", self.serial]
        cmd += list(args)
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=self.timeout)
        except FileNotFoundError:
            raise CaptureError(f"adb not found ({self.base[-1]}). Install Android platform-tools and add adb to "
                               "PATH, or pass --adb <path to adb>.") from None
        except subprocess.TimeoutExpired:
            raise CaptureError(f"adb {' '.join(args)} timed out after {self.timeout}s. Is the device responsive?") from None
        out = (p.stdout or "") + (p.stderr or "")
        if p.returncode != 0:
            raise CaptureError(f"adb {' '.join(args)} failed: {out.strip() or 'exit code ' + str(p.returncode)}")
        return out


def find_adb(explicit: str = "") -> str:
    for cand in (explicit, os.environ.get("ADB", "")):
        if cand:
            return cand
    found = shutil.which("adb")
    if found:
        return found
    for sdk in (os.environ.get("ANDROID_HOME", ""), os.environ.get("ANDROID_SDK_ROOT", ""),
                os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk"), os.path.expanduser("~/Library/Android/sdk"),
                os.path.expanduser("~/Android/Sdk")):
        exe = Path(sdk) / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb")
        if sdk and exe.is_file():
            return str(exe)
    return "adb"                                    # let the first call report a clear "not found"


def pick_device(adb: Adb) -> str:
    """Return the serial to use. Fails clearly with none, unauthorized/offline, or several devices."""
    if adb.serial:
        return adb.serial
    lines = adb.run("devices", device=False).splitlines()
    devices, problems = [], []
    for line in lines[1:]:
        parts = line.split()
        if len(parts) >= 2:
            (devices if parts[1] == "device" else problems).append((parts[0], parts[1]))
    if not devices:
        hint = "; ".join(f"{s} is {st}" for s, st in problems)
        if any(st == "unauthorized" for _, st in problems):
            hint += ". Accept the 'Allow USB debugging' prompt on the device"
        raise CaptureError("No device ready. Connect one with USB debugging enabled (check `adb devices`)"
                           + (f": {hint}" if hint else "") + ".")
    if len(devices) > 1:
        raise CaptureError("Several devices are connected: " + ", ".join(s for s, _ in devices)
                           + ". Choose one with --serial.")
    return devices[0][0]


def foreground_name(adb: Adb) -> str:
    """Best-effort screen name from the focused window, e.g. 'media_mainactivity'."""
    try:
        out = adb.run("shell", "dumpsys", "window")
    except CaptureError:
        return ""
    m = re.search(r"mCurrentFocus=Window\{[^}]*?\s([\w.]+)/([\w.$]+)\}", out) or \
        re.search(r"mFocusedApp=.*?\s([\w.]+)/([\w.$]+)", out)
    if not m:
        return ""
    pkg, act = m.group(1), m.group(2)
    return d2l.slug(pkg.rsplit(".", 1)[-1] + "_" + act.rsplit(".", 1)[-1].lstrip("."), 60)


def dump_screen(adb: Adb, dest: Path, retries: int = 3, delay: float = 1.5, dump_args=()) -> Path:
    """Run `uiautomator dump` on the device, pull the XML to `dest`, remove the device copy."""
    last = ""
    for attempt in range(1, retries + 1):
        try:
            out = adb.run("shell", "uiautomator", "dump", *dump_args, DEVICE_TMP)
        except CaptureError as e:
            out = str(e)
        if "dumped to" in out.lower():
            break
        last = out.strip()
        if attempt < retries and any(k.lower() in out.lower() for k in RETRYABLE):
            print(f"  dump attempt {attempt} failed ({last.splitlines()[-1] if last else 'no output'}); retrying...")
            time.sleep(delay)
            continue
        raise CaptureError(f"uiautomator dump failed: {last or 'no output'}. If the screen is animating "
                           "(maps, media), pause it and try again.")
    dest.parent.mkdir(parents=True, exist_ok=True)
    adb.run("pull", DEVICE_TMP, str(dest))
    try:
        adb.run("shell", "rm", "-f", DEVICE_TMP)
    except CaptureError:
        pass                                          # leaving a temp file on the device is harmless
    if not dest.is_file() or dest.stat().st_size == 0:
        raise CaptureError(f"adb pull did not produce {dest}")
    return dest


def capture_once(adb: Adb, name: str, opts) -> Path:
    name = d2l.slug(name, 60) if name else (foreground_name(adb) or "screen")
    exists = (Path(opts.dumps) / f"{name}.xml").exists()
    if opts.timestamp or (exists and not opts.overwrite):      # never silently replace an earlier capture
        name = f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    xml_path = dump_screen(adb, Path(opts.dumps) / f"{name}.xml", opts.retries, opts.retry_delay,
                           opts.dump_arg or ())
    print(f"Pulled  {xml_path}")
    argv = [str(xml_path), "--out", str(opts.out), "--format", opts.format, "--case", opts.case]
    for p in opts.package or []:
        argv += ["--package", p]
    for p in opts.exclude_package or []:
        argv += ["--exclude-package", p]
    if opts.include_layout:
        argv.append("--include-layout")
    if d2l.main(argv) != 0:
        raise CaptureError(f"could not convert {xml_path} (see the error above)")
    return Path(opts.out) / f"{xml_path.stem}.locators.json"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Dump the current screen over adb, pull the XML and generate locator JSON.")
    ap.add_argument("--name", help="screen name for the files (default: foreground app/activity, else 'screen')")
    ap.add_argument("--serial", "-s", default=os.environ.get("ANDROID_SERIAL", ""),
                    help="device serial (default: the only connected device, or $ANDROID_SERIAL)")
    ap.add_argument("--adb", default="", help="path to adb (default: $ADB, PATH, then the Android SDK)")
    ap.add_argument("--dumps", type=Path, default=Path("dumps"), help="folder for the pulled XML (default: ./dumps)")
    ap.add_argument("--out", type=Path, default=Path("locators"), help="folder for the JSON (default: ./locators)")
    ap.add_argument("--interactive", "-i", action="store_true",
                    help="capture several screens: navigate on the device, then press Enter (or type a name)")
    ap.add_argument("--overwrite", action="store_true", help="replace an existing dump with the same name")
    ap.add_argument("--timestamp", action="store_true", help="always add a timestamp to file names")
    ap.add_argument("--retries", type=int, default=3, help="dump attempts when the UI is not idle (default 3)")
    ap.add_argument("--retry-delay", type=float, default=1.5, help="seconds between attempts (default 1.5)")
    ap.add_argument("--dump-arg", action="append",
                    help="extra argument for `uiautomator dump`, e.g. --dump-arg=--compressed (repeatable)")
    ap.add_argument("--timeout", type=int, default=60, help="seconds before an adb call is abandoned")
    # converter options, passed through
    ap.add_argument("--format", choices=["full", "keywords"], default="full")
    ap.add_argument("--case", choices=["snake", "upper", "camel"], default="snake")
    ap.add_argument("--package", action="append")
    ap.add_argument("--exclude-package", action="append")
    ap.add_argument("--include-layout", action="store_true")
    opts = ap.parse_args(argv)

    adb = Adb(find_adb(opts.adb), opts.serial, opts.timeout)
    try:
        adb.serial = pick_device(adb)
        print(f"Device  {adb.serial}")
        if not opts.interactive:
            out = capture_once(adb, opts.name or "", opts)
            print(f"Done    {out}")
            return 0
        print("Interactive mode: open a screen on the device, then press Enter to capture it "
              "(or type a name first). Type q to finish.")
        done = []
        while True:
            try:
                answer = input("screen name [auto] / q: ").strip()
            except EOFError:
                break
            if answer.lower() in ("q", "quit", "exit"):
                break
            try:
                done.append(capture_once(adb, answer, opts))
            except CaptureError as e:
                print(f"ERROR {e}", file=sys.stderr)
        print(f"Captured {len(done)} screen(s): " + ", ".join(str(p) for p in done) if done else "Nothing captured.")
        return 0
    except CaptureError as e:
        print(f"ERROR {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
