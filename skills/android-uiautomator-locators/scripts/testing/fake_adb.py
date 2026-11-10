#!/usr/bin/env python3
"""A stand-in for `adb`, used only by test_capture_and_convert.py (no device needed).

Behaviour is controlled with environment variables:
  FAKE_ADB_STATE      folder for the fake device file system, the call log and counters (required)
  FAKE_ADB_DEVICES    comma list of serial:state, e.g. "emulator-5554:device,R58M:unauthorized"
  FAKE_ADB_DUMP       XML file that `uiautomator dump` "writes" on the device
  FAKE_ADB_IDLE_FAILS number of dump attempts that fail with "could not get idle state" (default 0)
  FAKE_ADB_FOCUS      value printed as mCurrentFocus by `dumpsys window`
"""

import os
import shutil
import sys
from pathlib import Path

state = Path(os.environ["FAKE_ADB_STATE"])
state.mkdir(parents=True, exist_ok=True)
args = sys.argv[1:]
with open(state / "calls.log", "a", encoding="utf-8") as log:
    log.write(" ".join(args) + "\n")

serial = ""
if args[:1] == ["-s"]:
    serial, args = args[1], args[2:]


def device_path(p: str) -> Path:
    return state / "device" / p.lstrip("/").replace("/", "_")


devices = [d.split(":") for d in os.environ.get("FAKE_ADB_DEVICES", "").split(",") if d]

if args == ["devices"]:
    print("List of devices attached")
    for s, st in devices:
        print(f"{s}\t{st}")
    print()
    sys.exit(0)

if serial and serial not in [s for s, st in devices if st == "device"]:
    print(f"adb: device '{serial}' not found", file=sys.stderr)
    sys.exit(1)

if args[:3] == ["shell", "uiautomator", "dump"]:
    target = args[-1]
    counter = state / "dump_attempts"
    n = int(counter.read_text()) + 1 if counter.exists() else 1
    counter.write_text(str(n))
    if n <= int(os.environ.get("FAKE_ADB_IDLE_FAILS", "0")):
        print("ERROR: could not get idle state.")
        sys.exit(0)                                   # real uiautomator often exits 0 on this error
    dst = device_path(target)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(os.environ["FAKE_ADB_DUMP"], dst)
    print(f"UI hierchary dumped to: {target}")
    sys.exit(0)

if args[:1] == ["pull"]:
    src, dest = device_path(args[1]), Path(args[2])
    if not src.exists():
        print(f"adb: error: failed to stat remote object '{args[1]}': No such file or directory", file=sys.stderr)
        sys.exit(1)
    shutil.copyfile(src, dest)
    print(f"{args[1]}: 1 file pulled.")
    sys.exit(0)

if args[:3] == ["shell", "rm", "-f"]:
    p = device_path(args[3])
    if p.exists():
        p.unlink()
    sys.exit(0)

if args[:3] == ["shell", "dumpsys", "window"]:
    focus = os.environ.get("FAKE_ADB_FOCUS", "")
    if focus:
        print(f"  mCurrentFocus=Window{{4f2a1c u0 {focus}}}")
    sys.exit(0)

print(f"fake adb: unsupported command {args}", file=sys.stderr)
sys.exit(1)
