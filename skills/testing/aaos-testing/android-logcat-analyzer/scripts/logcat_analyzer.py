#!/usr/bin/env python3
"""Android logcat analyzer.

Reads logcat text (a file, a .gz, a bugreport .zip, stdin, or a live capture
over adb) and reports what went wrong: fatal exceptions, native crashes, ANRs,
service crashes and process deaths, low-memory kills, non-fatal exceptions,
watchdog resets, StrictMode violations, jank, SELinux denials and binder
failures. Repeated problems are grouped, and every group carries the stack,
the lines the process logged just before, and a hint about the usual cause.

Python 3.8+, standard library only.

    python logcat_analyzer.py logcat.txt
    python logcat_analyzer.py --adb --package com.example.app
    python logcat_analyzer.py bugreport.zip --only crash,anr --json
"""
from __future__ import annotations

import argparse
import bisect
import gzip
import io
import json
import os
import re
import subprocess
import sys
import zipfile
from collections import OrderedDict

# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------

RE_THREADTIME = re.compile(
    r"^(?:(\d{4})-)?(\d\d-\d\d)\s+(\d\d:\d\d:\d\d(?:\.\d+)?)\s+(?:(\S+)\s+)?(\d+)\s+(\d+)\s+"
    r"([VDIWEFA])\s(.*?)\s*:(?: (.*))?$")
RE_TIME = re.compile(
    r"^(\d\d-\d\d)\s+(\d\d:\d\d:\d\d(?:\.\d+)?)\s+([VDIWEFA])/(.*?)\(\s*(\d+)\):(?: (.*))?$")
RE_STUDIO = re.compile(
    r"^(\d{4})-(\d\d-\d\d) (\d\d:\d\d:\d\d(?:\.\d+)?)\s+(\d+)-(\d+)\s+(\S+)\s+(\S+)\s+"
    r"([VDIWEFA])\s{2}(.*)$")
RE_BRIEF = re.compile(r"^([VDIWEFA])/(.*?)\(\s*(\d+)\):(?: (.*))?$")


class Entry(object):
    __slots__ = ("n", "src", "date", "time", "pid", "tid", "level", "tag", "msg")

    def __init__(self, n, src, date, time, pid, tid, level, tag, msg):
        self.n = n
        self.src = src
        self.date = date
        self.time = time
        self.pid = pid
        self.tid = tid
        self.level = level
        self.tag = tag
        self.msg = msg or ""

    def stamp(self):
        return ((self.date + " ") if self.date else "") + (self.time or "")

    def text(self, width=400):
        s = "%s %s %s: %s" % (self.stamp(), self.level, self.tag, self.msg.rstrip())
        s = s.strip().replace("\t", "    ")
        return s if len(s) <= width else s[: width - 3] + "..."


def _p_threadtime(line, n, src):
    m = RE_THREADTIME.match(line)
    if not m:
        return None
    return Entry(n, src, m.group(2), m.group(3), int(m.group(5)), int(m.group(6)),
                 m.group(7), m.group(8), m.group(9))


def _p_time(line, n, src):
    m = RE_TIME.match(line)
    if not m:
        return None
    return Entry(n, src, m.group(1), m.group(2), int(m.group(5)), None,
                 m.group(3), m.group(4).strip(), m.group(6))


def _p_studio(line, n, src):
    m = RE_STUDIO.match(line)
    if not m:
        return None
    return Entry(n, src, m.group(2), m.group(3), int(m.group(4)), int(m.group(5)),
                 m.group(8), m.group(6), m.group(9))


def _p_brief(line, n, src):
    m = RE_BRIEF.match(line)
    if not m:
        return None
    return Entry(n, src, None, None, int(m.group(3)), None, m.group(1), m.group(2).strip(), m.group(4))


PARSERS = [("threadtime", _p_threadtime), ("time", _p_time), ("studio", _p_studio), ("brief", _p_brief)]


def parse_lines(lines, src=0):
    """Returns (entries, stats). Lines that are not logcat lines are skipped."""
    entries = []
    formats = {}
    skipped = 0
    order = list(PARSERS)
    last_studio = None
    for n, line in enumerate(lines, 1):
        line = line.rstrip("\r\n")
        if not line or line.startswith("--------- "):
            continue
        entry = None
        for k, (name, fn) in enumerate(order):
            entry = fn(line, n, src)
            if entry is not None:
                formats[name] = formats.get(name, 0) + 1
                if k:
                    order.insert(0, order.pop(k))
                last_studio = entry if name == "studio" else None
                break
        if entry is None:
            # The Android Studio format prints the next lines of a message without a prefix.
            if last_studio is not None and line[:1] in (" ", "\t") and line.strip():
                p = last_studio
                entry = Entry(n, src, p.date, p.time, p.pid, p.tid, p.level, p.tag, line.strip())
            else:
                skipped += 1
                continue
        entries.append(entry)
    return entries, {"lines": n if lines else 0, "parsed": len(entries), "skipped": skipped, "formats": formats}


def decode(data):
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16", "replace")
    if data[:3] == b"\xef\xbb\xbf":
        data = data[3:]
    head = data[:2000]
    if head and head.count(b"\x00") > len(head) // 4:
        # UTF-16 without a byte-order mark (a shell redirect on Windows can write this).
        return data.decode("utf-16-le" if head[1:2] == b"\x00" else "utf-16-be", "replace")
    return data.decode("utf-8", "replace")


def read_source(path):
    """Returns a list of (name, text). Supports plain text, .gz and .zip (bug reports)."""
    if path == "-":
        data = sys.stdin.buffer.read() if hasattr(sys.stdin, "buffer") else sys.stdin.read().encode("utf-8")
        return [("stdin", decode(data))]
    if not os.path.isfile(path):
        raise IOError("file not found: %s" % path)
    with open(path, "rb") as f:
        magic = f.read(4)
    if magic[:2] == b"PK":
        out = []
        with zipfile.ZipFile(path) as z:
            names = [i.filename for i in z.infolist() if not i.filename.endswith("/")]
            main = [x for x in names if re.search(r"(^|/)bugreport[^/]*\.txt$", x)]
            picked = main or [x for x in names if x.lower().endswith((".txt", ".log", ".logcat"))]
            for name in picked:
                out.append(("%s!%s" % (os.path.basename(path), name), decode(z.read(name))))
        if not out:
            raise IOError("no .txt or .log file inside %s" % path)
        return out
    if magic[:2] == b"\x1f\x8b":
        with gzip.open(path, "rb") as f:
            return [(os.path.basename(path), decode(f.read()))]
    with open(path, "rb") as f:
        return [(os.path.basename(path), decode(f.read()))]


def capture_adb(serial=None, buffers="main,system,crash,events", timeout=120, adb="adb"):
    """Dumps the device log buffers (never clears them). Returns the text."""
    cmd = [adb]
    if serial:
        cmd += ["-s", serial]
    cmd += ["logcat", "-d", "-v", "threadtime"]
    for b in [x.strip() for x in buffers.split(",") if x.strip()]:
        cmd += ["-b", b]
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    except FileNotFoundError:
        raise IOError("adb not found. Install Android platform-tools and put adb on PATH, or pass --adb-path")
    except subprocess.TimeoutExpired:
        raise IOError("adb logcat did not finish in %d s. Is the device connected and authorised?" % timeout)
    if p.returncode != 0:
        err = decode(p.stderr).strip() or decode(p.stdout).strip()
        raise IOError("adb failed: %s" % (err or "exit code %d" % p.returncode))
    return decode(p.stdout)


# --------------------------------------------------------------------------
# Knowledge
# --------------------------------------------------------------------------

SEVERITIES = ["critical", "high", "medium", "low", "info"]
SEV_RANK = dict((s, i) for i, s in enumerate(SEVERITIES))

KIND_LABEL = OrderedDict([
    ("java_crash", "Fatal exception (Java/Kotlin crash)"),
    ("native_crash", "Native crash (signal / tombstone)"),
    ("anr", "ANR (not responding)"),
    ("watchdog", "System watchdog / system restart"),
    ("service_crash", "Service crash / restart"),
    ("lmk", "Low-memory kill"),
    ("process_death", "Process died"),
    ("kill", "Process killed by the system"),
    ("exception", "Exception with stack trace (not fatal)"),
    ("fatal_log", "Fatal-level log (Log.wtf / assert)"),
    ("binder", "Binder transaction failure"),
    ("service_blocked", "Service start blocked"),
    ("strictmode", "StrictMode violation"),
    ("jank", "Jank (skipped frames)"),
    ("selinux", "SELinux denial"),
    ("exception_mention", "Exception mentioned (no stack)"),
])

KIND_ALIASES = {
    "crash": ["java_crash", "native_crash"],
    "fatal": ["java_crash", "native_crash", "fatal_log"],
    "native": ["native_crash"],
    "java": ["java_crash"],
    "service": ["service_crash", "process_death", "kill", "lmk", "service_blocked"],
    "exceptions": ["exception", "exception_mention"],
    "memory": ["lmk"],
    "system": ["watchdog"],
}

# Types for which the lines logged just before the problem help to explain it.
CONTEXT_KINDS = ("java_crash", "native_crash", "anr", "exception", "fatal_log", "process_death", "lmk", "binder")

SIGNALS = {4: "SIGILL", 5: "SIGTRAP", 6: "SIGABRT", 7: "SIGBUS", 8: "SIGFPE", 9: "SIGKILL",
           11: "SIGSEGV", 13: "SIGPIPE", 15: "SIGTERM", 31: "SIGSYS", 35: "SIGSTKFLT"}

FRAMEWORK_PREFIXES = ("java.", "javax.", "kotlin.", "kotlinx.", "android.", "androidx.", "com.android.",
                      "dalvik.", "libcore.", "sun.", "jdk.", "org.json.")

HINTS = [
    (r"ForegroundServiceDidNotStartInTime|did not then call Service\.startForeground",
     "A service started with startForegroundService() did not call startForeground() in time (about 5-10 s). "
     "Call startForeground() first thing in onCreate/onStartCommand, on every path, also when stopping at once."),
    (r"ForegroundServiceStartNotAllowed|startForegroundService\(\) not allowed",
     "The app tried to start a foreground service from the background (Android 12+). Start it while the app is "
     "visible, or use WorkManager / an exempted case."),
    (r"Bad notification|CannotPostForegroundServiceNotification|invalid channel for service notification",
     "The foreground-service notification is invalid: create the notification channel before startForeground() "
     "and give the notification a small icon."),
    (r"CannotDeliverBroadcast|can't deliver broadcast",
     "The system could not deliver a broadcast: the process was frozen or flooded with broadcasts. Check for "
     "receivers that register many times or broadcasts sent in a loop."),
    (r"lateinit property|UninitializedPropertyAccess",
     "A lateinit property was read before it was set. Check the order of initialisation (lifecycle callbacks, "
     "injection) on the path in the top app frame."),
    (r"NullPointerException|null object reference|NullPointer",
     "A null value was used. Read the top app frame: find which object is null there and why (not initialised "
     "yet, already cleared in onDestroy, missing extra/argument, failed lookup)."),
    (r"OutOfMemoryError",
     "The Java heap ran out. Look for large bitmaps, unbounded caches or lists, and leaks (activities kept "
     "alive). The crashing frame is often only the victim; take a heap dump."),
    (r"StackOverflowError", "Infinite or very deep recursion. The repeating frames in the stack show the cycle."),
    (r"TransactionTooLarge|FAILED BINDER TRANSACTION",
     "Too much data was sent through Binder (limit about 1 MB per process, shared). Shrink Intent extras, "
     "saved instance state and Bundles; pass an id or a file/URI instead of the data."),
    (r"DeadObjectException|DeadSystemException",
     "The remote process on the other side of a Binder call died. Find which process died just before "
     "(see process deaths in this report) and why; handle the disconnect and rebind."),
    (r"NetworkOnMainThread", "Network I/O on the main thread. Move it to a background thread or coroutine dispatcher."),
    (r"CalledFromWrongThread|Only the original thread that created a view hierarchy",
     "A view was touched from a background thread. Post the UI update to the main thread."),
    (r"BadTokenException|is your activity running|not attached to window manager",
     "A dialog or window was shown or dismissed after its activity was finished. Check lifecycle state before "
     "showing, and dismiss in onDestroy."),
    (r"IllegalStateException.*(Fragment|onSaveInstanceState|not attached)",
     "A fragment transaction or context access happened in the wrong lifecycle state (after onSaveInstanceState, "
     "or the fragment is detached)."),
    (r"ActivityNotFoundException", "No activity can handle the Intent. Check the action/component and the manifest; "
     "on Android 11+ also the <queries> element."),
    (r"SecurityException|Permission Denial",
     "A permission is missing or the component is not exported. The message names the permission or component."),
    (r"Resources\$NotFoundException|InflateException",
     "A resource is missing or invalid for this configuration (density, locale, night mode, API level), or "
     "setText was given an int. The 'Caused by' line names the resource or view."),
    (r"ClassNotFoundException|NoClassDefFoundError|NoSuchMethodError|NoSuchFieldError",
     "A class or member is missing at run time: code shrinking (R8/ProGuard) rules, a missing dependency, "
     "multidex, or a library version mismatch."),
    (r"UnsatisfiedLinkError",
     "A native library or JNI method was not found: wrong ABI in the APK, library not packaged, or the JNI "
     "function name does not match."),
    (r"ConcurrentModificationException",
     "A collection was changed while it was iterated, often from two threads. Iterate over a copy or synchronise."),
    (r"IndexOutOfBounds|ArrayIndexOutOfBounds|NoSuchElementException",
     "An index or element does not exist. Check sizes on the path in the top app frame, mainly empty lists and "
     "lists changed by another thread."),
    (r"ClassCastException", "An object has a different type than expected. Check casts of extras, views and parsed data."),
    (r"NumberFormatException", "Text could not be parsed as a number. Validate the input (empty string, locale, units)."),
    (r"SQLite\w*Exception|CursorWindow|no such (table|column)",
     "A database error: schema and code disagree (missing migration), the database is locked or full, or a row "
     "is too large for the cursor window."),
    (r"RemoteServiceException", "The system rejected something the app asked for; the message says what."),
    (r"SIGABRT",
     "The process aborted itself: a failed assert/CHECK, a JNI error detected by the runtime, a C++ exception "
     "not caught, or heap corruption found by the allocator. The abort message says which."),
    (r"SIGSEGV|SIGBUS",
     "Invalid memory access in native code. A fault address near 0x0 is a null pointer; other addresses point "
     "to use-after-free or a buffer overrun. Symbolise the backtrace (ndk-stack) with the unstripped libraries."),
    (r"SIGILL|SIGFPE|SIGSYS|SIGTRAP",
     "Native code hit an illegal instruction, arithmetic error, blocked system call or trap. Symbolise the "
     "backtrace (ndk-stack) with the unstripped libraries."),
]

ANR_HINTS = [
    (r"Input dispatching timed out|not responding\. Waited",
     "The main thread did not handle an input event within 5 s. It is blocked or busy: I/O, a lock, a slow "
     "Binder call, or heavy work. The main thread stack in the ANR trace file shows where."),
    (r"executing service", "A Service callback (onCreate/onStartCommand/onBind) did not finish in time (20 s in the "
     "foreground, 200 s in the background). Those callbacks run on the main thread; move the work off it."),
    (r"Broadcast of Intent|broadcast", "A BroadcastReceiver.onReceive() did not finish in time (10 s in the foreground). "
     "Use goAsync() or hand the work to a worker."),
    (r"ContentProvider", "A ContentProvider did not answer in time. Check slow queries and work in the provider's onCreate()."),
    (r"startForegroundService\(\) did not then call",
     "A service started with startForegroundService() did not call startForeground() in time."),
    (r"onStartJob|onStopJob|JobService", "A JobService callback did not return in time. It runs on the main thread."),
]


def hint_for(text, table=HINTS):
    for pattern, hint in table:
        if re.search(pattern, text):
            return hint
    return None


def norm(s, limit=160):
    """Removes the parts of a message that change between occurrences."""
    s = re.sub(r"0x[0-9a-fA-F]+|@[0-9a-f]{5,}|\b[0-9a-f]{6,}\b|\d+", "#", s or "")
    return " ".join(s.split())[:limit]


def frame_key(frame):
    return re.sub(r"\(.*$", "", frame or "").strip()


def is_app_frame(frame, package=None):
    if package and frame.startswith(package):
        return True
    return not frame.startswith(FRAMEWORK_PREFIXES)


def parse_stack(msgs, package=None):
    """Parses a Java stack trace given as message lines (headline first)."""
    sections = []  # [headline, [frames]]
    for m in msgs:
        s = m.strip()
        if not s:
            continue
        if s.startswith("at "):
            if sections:
                sections[-1][1].append(s[3:])
        elif s.startswith("Caused by: "):
            sections.append([s[11:], []])
        elif s.startswith("... ") or s.startswith("Suppressed: "):
            continue
        elif not sections:
            sections.append([s, []])
    if not sections:
        return None
    head, root = sections[0], sections[-1]

    def split(line):
        m = re.match(r"([\w.$]+)(?::\s*(.*))?$", line, re.S)
        return (m.group(1), m.group(2) or "") if m else (line, "")

    app = None
    for sec in reversed(sections):
        cands = [f for f in sec[1] if is_app_frame(f, package)]
        if package:
            cands = [f for f in cands if f.startswith(package)] or cands
        if cands:
            app = cands[0]
            break
    frames = sum(len(s[1]) for s in sections)
    first = root[1][0] if root[1] else (head[1][0] if head[1] else None)
    cls, msg = split(head[0])
    rcls, rmsg = split(root[0])
    return {"headline": head[0], "class": cls, "message": msg, "root": root[0], "root_class": rcls,
            "root_message": rmsg, "caused_by": len(sections) - 1, "frames": frames,
            "app_frame": app, "first_frame": first}


RE_EXC = re.compile(r"((?:[a-zA-Z_][\w$]*\.)+[A-Z][\w$]*(?:Exception|Error|Throwable|Failure))\b")
RE_STACK_CONT = re.compile(r"^\s*(?:at |Caused by: |\.\.\. \d+ more|Suppressed: )")
RE_NATIVE_FRAME = re.compile(r"#(\d+)\s+pc\s+([0-9a-fA-F]+)\s+(\S+)\s*(.*)$")


class Issue(object):
    def __init__(self, kind, severity, entry, title, signature, process=None, pid=None):
        self.kind = kind
        self.severity = severity
        self.entry = entry
        self.title = " ".join((title or "").split())
        self.signature = signature
        self.process = process
        self.pid = pid if pid is not None else entry.pid
        self.fields = OrderedDict()
        self.block = []          # entries of the stack / detail block
        self.related = []
        self.hint = None
        self.metric = None
        self.index = 0           # index of the first entry in the entry list


# --------------------------------------------------------------------------
# Analysis
# --------------------------------------------------------------------------

AM_TAGS = ("ActivityManager", "ActivityTaskManager")


class Analyzer(object):
    def __init__(self, entries, package=None, jank_frames=60):
        self.entries = entries
        self.package = package
        self.jank_frames = jank_frames
        self.issues = []
        self.procs = {}           # pid -> process name
        self.last_by_pid = {}     # pid -> Issue that explains a coming death
        self.explained = set()    # pids whose death has a known cause
        self.dead_by_proc = {}    # process name -> Issue (cause of the last death)
        self.libc_fatal = []      # (index, entry, match)
        self.event_anr = []
        self.event_crash = []
        self.last_native = None
        self.last_anr = None
        self.foreground = None
        self.seen_am = set()      # sources in which the activity manager already logged
        n = len(entries)
        self.consumed = bytearray(n)
        self.nxt = [None] * n
        self.prv = [None] * n
        self.by_pid = {}
        last = {}
        for i, e in enumerate(entries):
            k = (e.src, e.pid, e.tid)
            p = last.get(k)
            if p is not None:
                self.nxt[p] = i
                self.prv[i] = p
            last[k] = i
            self.by_pid.setdefault((e.src, e.pid), []).append(i)

    # -- helpers -----------------------------------------------------------

    def block(self, i, cont=None, limit=400):
        """Entry i plus the next entries the same thread logged with the same tag."""
        e0 = self.entries[i]
        out = [i]
        j = self.nxt[i]
        while j is not None and len(out) < limit:
            e = self.entries[j]
            if e.tag != e0.tag or self.consumed[j] or (cont is not None and not cont(e)):
                break
            out.append(j)
            j = self.nxt[j]
        for k in out:
            self.consumed[k] = 1
        return out

    def add(self, issue, i, block=None):
        issue.index = i
        if block:
            issue.block = [self.entries[k] for k in block]
        if issue.process is None:
            issue.process = self.procs.get(issue.pid)
        if self.foreground and "Last activity shown" not in issue.fields and issue.kind in (
                "java_crash", "native_crash", "anr", "watchdog"):
            issue.fields["Last activity shown"] = self.foreground
        self.issues.append(issue)
        return issue

    def proc_issue(self, name):
        """The last death cause known for a package (any of its processes)."""
        best = None
        for store in (self.dead_by_proc, dict((v.process, v) for v in self.last_by_pid.values() if v.process)):
            for proc, issue in store.items():
                if proc == name or proc.startswith(name + ":"):
                    if best is None or issue.index > best.index:
                        best = issue
        return best

    # -- block detectors ---------------------------------------------------

    def java_crash(self, i, e):
        idx = self.block(i, cont=lambda x: "FATAL EXCEPTION" not in x.msg)
        m = re.search(r"FATAL EXCEPTION(?: IN SYSTEM PROCESS)?: ?(.*)", e.msg)
        thread = m.group(1).strip() if m else ""
        process = "system_server" if "SYSTEM PROCESS" in e.msg else None
        pid = e.pid
        msgs = []
        for k in idx[1:]:
            s = self.entries[k].msg
            pm = re.match(r"\s*Process: (\S+?),? PID: (\d+)", s)
            if pm:
                process, pid = pm.group(1), int(pm.group(2))
                continue
            msgs.append(s)
        st = parse_stack(msgs, self.package) or {
            "headline": "(no exception line in the log)", "class": "unknown", "message": "", "root": "",
            "root_class": "unknown", "root_message": "", "caused_by": 0, "frames": 0, "app_frame": None,
            "first_frame": None}
        if process:
            self.procs[pid] = process
        top = st["app_frame"] or st["first_frame"]
        title = st["root"] or st["headline"]
        issue = Issue("java_crash", "critical", e, title,
                      "%s|%s" % (st["root_class"], frame_key(top)), process, pid)
        issue.fields["Thread"] = thread
        issue.fields["Exception"] = st["headline"]
        if st["caused_by"]:
            issue.fields["Root cause"] = st["root"]
        if st["app_frame"]:
            issue.fields["Top app frame"] = st["app_frame"]
        elif st["first_frame"]:
            issue.fields["Top frame"] = st["first_frame"] + "  (no app frame in the stack)"
        issue.hint = hint_for(st["root"] + " " + st["headline"])
        self.add(issue, i, idx)
        self.last_by_pid[pid] = issue
        self.explained.add(pid)

    def native_crash(self, i, e):
        idx = self.block(i, cont=lambda x: not x.msg.startswith("*** ***"), limit=800)
        f = OrderedDict()
        pid, process, thread, signame, frames = None, None, "", "", []
        code = fault = abort = cause = None
        in_bt = False
        for k in idx[1:]:
            s = self.entries[k].msg.strip()
            m = re.match(r"pid: (\d+), tid: (\d+), name: (.*?)\s+>>> (.*?) <<<", s)
            if m and pid is None:
                pid, thread, process = int(m.group(1)), "%s (tid %s)" % (m.group(3), m.group(2)), m.group(4)
                continue
            m = re.match(r"signal (\d+) \((\w+)\), code (-?\d+) \((\w+)\)(?:, fault addr (\S+))?", s)
            if m and not signame:
                signame, code, fault = m.group(2), m.group(4), m.group(5)
                continue
            m = re.match(r"Abort message: '?(.*?)'?$", s)
            if m:
                abort = m.group(1)
                continue
            m = re.match(r"Cause: (.*)", s)
            if m:
                cause = m.group(1)
                continue
            m = RE_NATIVE_FRAME.match(s)
            if m:
                if in_bt or not frames:
                    in_bt = True
                    rest = re.sub(r"\s*\(BuildId: [^)]*\)\s*$", "", m.group(4)).strip()
                    func = rest[1:-1] if rest.startswith("(") and rest.endswith(")") else rest
                    frames.append((m.group(3), func))
            elif frames:
                in_bt = False
        if pid is None:
            pid = e.pid
        self.procs.setdefault(pid, process)

        def lib(path):
            return path.rsplit("/", 1)[-1]

        top = None
        for path, func in frames:
            if lib(path) not in ("libc.so", "libc++.so", "[vdso]", "libc++abi.so"):
                top = (path, func)
                break
        top = top or (frames[0] if frames else None)
        app = None
        for path, func in frames:
            if "/data/app/" in path or "/data/data/" in path or (self.package and self.package in path):
                app = (path, func)
                break

        def show(fr):
            return "%s (%s)" % (lib(fr[0]), fr[1]) if fr[1] else lib(fr[0])

        title = signame or "native crash"
        if code:
            title += " (%s)" % code
        if abort:
            title += ": " + abort
        elif top:
            title += " in " + show(top)
        sig = "%s|%s|%s" % (signame, show(top) if top else "", norm(abort or "", 60))
        sig = re.sub(r"\+\d+\)", ")", sig)
        issue = Issue("native_crash", "critical", e, title, sig, process, pid)
        f["Thread"] = thread
        f["Signal"] = "%s%s%s" % (signame, " (%s)" % code if code else "", ", fault addr %s" % fault if fault else "")
        if abort:
            f["Abort message"] = abort
        if cause:
            f["Cause"] = cause
        if top:
            f["Top frame"] = show(top)
        if app and app != top:
            f["Top app frame"] = show(app)
        issue.fields = f
        issue.hint = hint_for(signame or "")
        self.add(issue, i, idx)
        self.last_by_pid[pid] = issue
        self.explained.add(pid)
        self.last_native = issue

    def anr(self, i, e):
        idx = self.block(i, cont=lambda x: not x.msg.startswith("ANR in "), limit=250)
        m = re.match(r"ANR in (\S+)(?: \((.*?)\))?", e.msg)
        process, component = m.group(1), m.group(2)
        pid, reason, load, cpu, total = None, "", None, [], None
        in_cpu = 0
        for k in idx[1:]:
            s = self.entries[k].msg.strip()
            if s.startswith("PID: "):
                pid = int(re.sub(r"\D.*", "", s[5:]) or 0) or None
            elif s.startswith("Reason: "):
                reason = s[8:]
            elif s.startswith("Load: "):
                load = s[6:]
            elif s.startswith("CPU usage from"):
                in_cpu += 1
            elif in_cpu == 1:
                if re.match(r"[\d.]+% TOTAL", s):
                    total = s
                elif re.match(r"[\d.]+% \d+/", s) and len(cpu) < 6:
                    cpu.append(s)
        if pid:
            self.procs[pid] = process
        issue = Issue("anr", "critical", e, "ANR in %s: %s" % (process, reason or "(no reason line)"),
                      norm(re.sub(r"\(.*", "", reason), 80), process, pid if pid else -1)
        if component:
            issue.fields["Component"] = component
        issue.fields["Reason"] = reason
        if load:
            issue.fields["Load"] = load
        if cpu:
            issue.fields["Top CPU"] = "; ".join(re.sub(r"\s*/ faults.*", "", c) for c in cpu[:4])
        if total:
            issue.fields["CPU total"] = total
        notes = []
        own = [c for c in cpu if pid and c.split("%", 1)[1].strip().startswith("%d/" % pid)]
        if own:
            pct = float(own[0].split("%", 1)[0])
            notes.append("the process used %g%% CPU, so it was %s" % (
                pct, "busy computing (look for a hot loop or heavy work)" if pct >= 60 else
                "mostly waiting (look for a lock, a Binder call or I/O in the main thread stack)"))
        io_m = re.search(r"([\d.]+)% iowait", total or "")
        if io_m and float(io_m.group(1)) >= 15:
            notes.append("iowait was %s%%: the device was stuck on disk I/O" % io_m.group(1))
        if notes:
            issue.fields["CPU reading"] = "; ".join(notes)
        issue.hint = hint_for(reason, ANR_HINTS) or ANR_HINTS[0][1]
        self.add(issue, i, idx)
        if pid:
            self.last_by_pid[pid] = issue
            self.explained.add(pid)
        self.last_anr = issue

    def strictmode(self, i, e):
        idx = self.block(i, cont=lambda x: RE_STACK_CONT.match(x.msg) is not None, limit=80)
        m = re.search(r"(\w+Violation)", e.msg)
        what = m.group(1) if m else norm(e.msg, 60)
        st = parse_stack(["x"] + [self.entries[k].msg for k in idx[1:]], self.package)
        app = st and st["app_frame"]
        issue = Issue("strictmode", "low", e, "StrictMode %s%s" % (what, " at " + app if app else ""),
                      "%s|%s" % (what, frame_key(app)))
        if app:
            issue.fields["Top app frame"] = app
        self.add(issue, i, idx)

    def fatal_log(self, i, e):
        idx = self.block(i, cont=lambda x: x.level in "FA", limit=60)
        issue = Issue("fatal_log", "medium", e, "%s: %s" % (e.tag, e.msg.strip()), "%s|%s" % (e.tag, norm(e.msg, 80)))
        self.add(issue, i, idx)

    def exception(self, i, e, m):
        s = e.msg.strip()
        if RE_STACK_CONT.match(s) and not s.startswith("Caused by: "):
            return
        idx = self.block(i, cont=lambda x: RE_STACK_CONT.match(x.msg) is not None, limit=300)
        st = parse_stack([s[11:] if s.startswith("Caused by: ") else s] + [self.entries[k].msg for k in idx[1:]],
                         self.package)
        cls = m.group(1)
        if not st or not st["frames"]:
            if e.level not in "WEF":
                self.consumed[i] = 0
                return
            issue = Issue("exception_mention", "low", e, "%s: %s" % (e.tag, s), "%s|%s" % (e.tag, cls))
            self.add(issue, i, idx)
            return
        root = st["root_class"]
        top = st["app_frame"] or st["first_frame"]
        sev = "high" if re.search(r"OutOfMemoryError|StackOverflowError", st["root"] + st["headline"]) else "medium"
        issue = Issue("exception", sev, e, st["root"] if st["caused_by"] else s,
                      "%s|%s|%s" % (root, frame_key(top), e.tag))
        issue.fields["Logged by"] = "%s (level %s)" % (e.tag, e.level)
        p = self.prv[i]
        if p is not None and self.entries[p].tag == e.tag and i - p <= 3 and not self.consumed[p]:
            issue.fields["Log message"] = self.entries[p].msg.strip()
        if st["caused_by"]:
            issue.fields["Exception"] = st["headline"]
            issue.fields["Root cause"] = st["root"]
        if st["app_frame"]:
            issue.fields["Top app frame"] = st["app_frame"]
        issue.hint = hint_for(st["root"] + " " + st["headline"])
        self.add(issue, i, idx)

    # -- single-line events ------------------------------------------------

    def am_line(self, i, e):
        msg = e.msg
        self.seen_am.add(e.src)
        m = re.search(r"Start proc (\d+):([^/\s]+)/", msg)
        if m:
            self.procs[int(m.group(1))] = m.group(2)
            return True
        m = re.search(r"Start proc (\S+) for .*?pid=(\d+)", msg)
        if m:
            self.procs[int(m.group(2))] = m.group(1)
            return True
        m = re.match(r"\s*(?:Displayed |START u\d+ \{.*?cmp=)([\w.$]+/[\w.$]+)", msg)
        if m:
            self.foreground = m.group(1)
            return True
        m = re.search(r"Process (\S+) \(pid (\d+)\) has died(?::\s*(.*))?", msg)
        if m:
            proc, pid, state = m.group(1), int(m.group(2)), (m.group(3) or "").strip()
            cause = self.last_by_pid.pop(pid, None)
            if cause is not None:
                cause.related.append("%s process died%s" % (e.stamp(), " (state: %s)" % state if state else ""))
                self.dead_by_proc[proc] = cause
                return True
            token = state.split()[0].lower() if state else ""
            if re.match(r"(fore|fg|vis|perc|prcp|pers|sys|psvc|bfgs|top)", token):
                sev, what = "high", "died while in the foreground or visible"
            elif re.match(r"(svc|home|hvy|bkup|prev)", token):
                sev, what = "medium", "died while running a service or as the previous app"
            else:
                sev, what = "low", "died while cached"
            issue = Issue("process_death", sev, e, "%s %s, no cause in the log (state: %s)" % (proc, what, state or "?"),
                          "died|" + token, proc, pid)
            issue.hint = ("No crash, ANR or kill line explains this death. Look at the kernel log (lmkd / OOM "
                          "killer), a native crash without a tombstone, or a kill from another tool (adb, a test "
                          "runner).") if sev != "low" else None
            self.add(issue, i)
            self.dead_by_proc[proc] = issue
            self.procs.pop(pid, None)
            return True
        m = re.search(r"Killing (\d+):([^/\s]+)/\S+ \(adj (-?\d+)\): (.*)", msg)
        if m:
            pid, proc, adj, reason = int(m.group(1)), m.group(2), m.group(3), m.group(4).strip()
            self.procs[pid] = proc
            self.explained.add(pid)
            prev = self.last_by_pid.get(pid)
            if prev is not None:
                prev.related.append("%s killed by the system: %s" % (e.stamp(), reason))
                return True
            bad = re.search(r"excessive|too many|error|crash|anr|not responding|oom|memory|bad |died|freez", reason, re.I)
            issue = Issue("kill", "medium" if bad else "info", e,
                          "%s killed: %s (adj %s)" % (proc, reason, adj), norm(reason, 60), proc, pid)
            self.add(issue, i)
            self.last_by_pid[pid] = issue
            return True
        m = re.search(r"Scheduling restart of crashed service (\S+) in (\d+)ms", msg)
        if m:
            comp = m.group(1)
            pkg = comp.split("/")[0]
            cause = self.proc_issue(pkg)
            if cause is None:
                sev, why = "medium", "the process died; the log does not show why"
            elif cause.kind in ("java_crash", "native_crash", "anr"):
                sev, why = "high", "%s: %s" % (KIND_LABEL[cause.kind], cause.title)
            else:
                sev = cause.severity if cause.severity != "info" else "low"
                why = "%s: %s" % (KIND_LABEL[cause.kind], cause.title)
            issue = Issue("service_crash", sev, e, "Service %s lost its process; restart in %s ms" % (comp, m.group(2)),
                          "restart|" + comp, cause.process if cause is not None and cause.process else pkg,
                          cause.pid if cause is not None else -1)
            issue.fields["Service"] = comp
            issue.fields["Cause"] = why + (" (line %d)" % cause.entry.n if cause is not None else "")
            if cause is not None:
                cause.related.append("%s service %s restart scheduled" % (e.stamp(), comp))
            self.add(issue, i)
            return True
        m = re.search(r"Service crashed (\d+) times, stopping: (.*)", msg)
        if m:
            cm = re.search(r"([\w.]+/[\w.$]+)", m.group(2))
            comp = cm.group(1) if cm else m.group(2)
            issue = Issue("service_crash", "high", e,
                          "Service %s crashed %s times; the system stopped restarting it" % (comp, m.group(1)),
                          "loop|" + comp, comp.split("/")[0], -1)
            issue.fields["Service"] = comp
            issue.hint = "The service crashes every time it starts. Fix the crash reported for this process above."
            self.add(issue, i)
            return True
        m = re.search(r"Process (\S+) has crashed too many times", msg)
        if m:
            issue = Issue("service_crash", "high", e, "%s crashed too many times; the system killed it" % m.group(1),
                          "toomany|" + m.group(1), m.group(1), -1)
            self.add(issue, i)
            return True
        m = re.search(r"Background start not allowed: service (.*?)(?: from pid=(\d+).*?pkg=(\S+))?(?: startFg.*)?$", msg)
        if not m:
            m2 = re.search(r"Unable to start service (Intent \{.*?\}).*?: not found", msg)
            if m2:
                issue = Issue("service_blocked", "low", e, "Service not found: " + m2.group(1), norm(m2.group(1), 80))
                issue.hint = "No service matches the Intent: check the component name, the manifest and package visibility."
                self.add(issue, i)
                return True
            return False
        cm = re.search(r"cmp=([\w.]+/[\w.$]+)", m.group(1))
        comp = cm.group(1) if cm else norm(m.group(1), 80)
        issue = Issue("service_blocked", "low", e, "Background start not allowed for service " + comp,
                      "bgstart|" + comp, m.group(3) or comp.split("/")[0], int(m.group(2)) if m.group(2) else -1)
        issue.hint = ("The app called startService() while in the background (Android 8+). Use "
                      "startForegroundService() with a notification, or WorkManager.")
        self.add(issue, i)
        return True

    def tag_line(self, i, e):
        tag, msg = e.tag, e.msg
        if tag in AM_TAGS:
            return self.am_line(i, e)
        if tag in ("lowmemorykiller", "lmkd"):
            m = re.search(r"Kill '([^']+)' \((\d+)\)(?:, uid \d+, oom_(?:score_)?adj (-?\d+))?(.*)", msg)
            if not m:
                return False
            proc, pid = m.group(1), int(m.group(2))
            adj = int(m.group(3)) if m.group(3) else None
            sev = "medium" if adj is None else ("high" if adj <= 250 else "medium" if adj <= 700 else "low")
            rm = re.search(r"reason:? (.*)", m.group(4) or "")
            issue = Issue("lmk", sev, e, "Low-memory killer killed %s%s" % (
                proc, " (oom_score_adj %d)" % adj if adj is not None else ""), "lmk", proc, pid)
            if rm:
                issue.fields["Reason"] = rm.group(1)
            issue.hint = ("The device ran out of memory. A low oom_score_adj (0-250) means a foreground or "
                          "perceptible process was killed: find what uses the memory (dumpsys meminfo).")
            self.add(issue, i)
            self.procs[pid] = proc
            self.last_by_pid[pid] = issue
            self.explained.add(pid)
            return True
        if tag == "init":
            m = re.search(r"Service '([^']+)' \(pid (\d+)\) (?:exited with status (-?\d+)|(?:received|killed by) signal (\d+))", msg)
            if m:
                if m.group(3) == "0":
                    return True
                if m.group(4):
                    num = int(m.group(4))
                    how = "received signal %d (%s)" % (num, SIGNALS.get(num, "?"))
                else:
                    how = "exited with status %s" % m.group(3)
                issue = Issue("service_crash", "high", e, "Native service '%s' %s" % (m.group(1), how),
                              "init|" + re.sub(r"\d+", "#", how), m.group(1), int(m.group(2)))
                issue.hint = ("A native daemon or HAL started by init stopped. Look for its tombstone or its last "
                              "log lines; init restarts it unless it is a oneshot service.")
                self.add(issue, i)
                self.explained.add(int(m.group(2)))
                return True
            m = re.search(r"critical process '([^']+)' exited (\d+) times", msg)
            if m:
                issue = Issue("watchdog", "critical", e,
                              "Critical process '%s' exited %s times; the device reboots" % (m.group(1), m.group(2)),
                              "critical|" + m.group(1), m.group(1), -1)
                self.add(issue, i)
                return True
            return False
        if tag == "Zygote":
            m = re.search(r"Process (\d+) exited due to signal (\d+)", msg)
            if not m:
                return False
            pid, num = int(m.group(1)), int(m.group(2))
            if pid in self.explained or pid in self.last_by_pid:
                return True
            name = SIGNALS.get(num, "signal %d" % num)
            sev = "low" if num in (9, 15) else "high"
            issue = Issue("process_death", sev, e, "%s exited due to signal %d (%s), no other cause in the log" % (
                self.procs.get(pid) or "pid %d" % pid, num, name), "zygote|%d" % num, self.procs.get(pid), pid)
            if sev == "high":
                issue.hint = hint_for(name)
            self.add(issue, i)
            self.explained.add(pid)
            return True
        if tag == "Watchdog":
            m = re.search(r"WATCHDOG KILLING SYSTEM PROCESS: (.*)", msg)
            if not m:
                return False
            issue = Issue("watchdog", "critical", e, "Watchdog killed system_server: " + m.group(1),
                          "watchdog|" + norm(m.group(1), 80), "system_server")
            issue.hint = ("A system_server thread was blocked for about 60 s, so the whole framework restarts "
                          "(soft reboot). The named thread and the traces in /data/anr show the lock or call.")
            self.add(issue, i)
            return True
        if tag == "SystemServer":
            if "Entered the Android system server" in msg and e.src in self.seen_am:
                issue = Issue("watchdog", "high", e, "system_server restarted (framework soft reboot)",
                              "restart", "system_server")
                issue.hint = "The framework restarted in the middle of the log. Look for a system crash or watchdog before it."
                self.add(issue, i)
                self.seen_am.discard(e.src)
                return True
            return False
        if tag == "Choreographer":
            m = re.search(r"Skipped (\d+) frames", msg)
            if not m:
                return False
            frames = int(m.group(1))
            if frames < self.jank_frames:
                return True
            issue = Issue("jank", "medium" if frames >= 300 else "low", e,
                          "Main thread skipped %d frames" % frames, "jank")
            issue.metric = frames
            issue.hint = ("The main thread was busy or blocked (60 frames is about 1 s at 60 Hz). Long blocks "
                          "become ANRs: profile what the main thread did just before.")
            self.add(issue, i)
            return True
        if tag == "StrictMode":
            if "StrictMode policy violation" in msg:
                self.strictmode(i, e)
                return True
            return False
        if tag == "am_anr":
            self.event_anr.append((i, e))
            return True
        if tag == "am_crash":
            self.event_crash.append((i, e))
            return True
        if tag == "am_proc_start":
            p = msg.strip("[] ").split(",")
            if len(p) >= 4 and p[1].isdigit():
                self.procs[int(p[1])] = p[3]
            return True
        return False

    def any_line(self, i, e):
        msg = e.msg
        if "avc: " in msg and "denied" in msg:
            m = re.search(r"denied\s+\{ ([^}]*)\}", msg)
            perms = m.group(1).strip() if m else "?"
            sc = re.search(r"scontext=u:r:([^:\s]+)", msg)
            tc = re.search(r"tcontext=u:(?:object_)?r:([^:\s]+)", msg)
            cl = re.search(r"tclass=(\S+)", msg)
            app = re.search(r"\bapp=(\S+)", msg) or re.search(r'comm="([^"]+)"', msg)
            enforcing = "permissive=1" not in msg
            title = "SELinux denied { %s } %s -> %s (%s)%s" % (
                perms, sc.group(1) if sc else "?", tc.group(1) if tc else "?", cl.group(1) if cl else "?",
                "" if enforcing else " [permissive: only logged]")
            issue = Issue("selinux", "low", e, title, norm(title, 120), app.group(1) if app else None)
            issue.hint = ("The SELinux policy blocked the access. For an app this means using a path or API that "
                          "apps may not use; for platform code the policy needs a rule.")
            self.add(issue, i)
            return True
        if "FAILED BINDER TRANSACTION" in msg:
            issue = Issue("binder", "medium", e, "Failed binder transaction " + msg.split("!!!")[-1].strip(), "binder")
            issue.hint = hint_for("FAILED BINDER TRANSACTION")
            self.add(issue, i)
            return True
        if "Tombstone written to" in msg:
            m = re.search(r"Tombstone written to:? (\S+)", msg)
            if m and self.last_native is not None:
                self.last_native.fields["Tombstone"] = m.group(1)
            return True
        if "Out of memory: Kill" in msg:
            m = re.search(r"Out of memory: Kill(?:ed)? process (\d+) \(([^)]+)\)", msg)
            if m:
                issue = Issue("lmk", "high", e, "Kernel OOM killer killed %s" % m.group(2), "oom",
                              m.group(2), int(m.group(1)))
                self.add(issue, i)
                self.explained.add(int(m.group(1)))
                return True
        if "/anr/" in msg and self.last_anr is not None:
            m = re.search(r"(?:Dumping to|Wrote stack traces to|Collecting stacks .*? into) (/\S+/anr/\S+)", msg)
            if m:
                self.last_anr.fields["Trace file"] = m.group(1).rstrip(".,")
                return True
        return False

    # -- main loop ---------------------------------------------------------

    def run(self):
        entries = self.entries
        consumed = self.consumed
        tagged = set(AM_TAGS + ("lowmemorykiller", "lmkd", "init", "Zygote", "Watchdog", "SystemServer",
                                "Choreographer", "StrictMode", "am_anr", "am_crash", "am_proc_start"))
        for i, e in enumerate(entries):
            if consumed[i]:
                continue
            tag, msg = e.tag, e.msg
            if tag == "AndroidRuntime":
                if "FATAL EXCEPTION" in msg:
                    self.java_crash(i, e)
                    continue
            elif tag == "DEBUG":
                if msg.startswith("*** ***"):
                    self.native_crash(i, e)
                    continue
            elif tag == "libc":
                m = re.match(r"Fatal signal (\d+) \((\w+)\), code (-?\d+)(?: \((\w+)\))?(?:, fault addr (\S+))?"
                             r"(?: in tid (\d+) \(([^)]*)\))?(?:, pid (\d+) \(([^)]*)\))?", msg)
                if m:
                    self.libc_fatal.append((i, e, m))
                    continue
            elif tag in AM_TAGS and msg.startswith("ANR in "):
                self.anr(i, e)
                continue
            if tag in tagged and self.tag_line(i, e):
                continue
            if self.any_line(i, e):
                continue
            if e.level in "FA":
                self.fatal_log(i, e)
                continue
            if "Exception" in msg or "Error" in msg or "Throwable" in msg or "Failure" in msg:
                m = RE_EXC.search(msg)
                if m:
                    self.exception(i, e, m)
        self.finish()
        return self.issues

    def finish(self):
        native = set((x.entry.src, x.pid) for x in self.issues if x.kind == "native_crash")
        for i, e, m in self.libc_fatal:
            if (e.src, e.pid) in native:
                continue
            native.add((e.src, e.pid))
            title = "%s%s, no tombstone in the log" % (m.group(2), " (%s)" % m.group(4) if m.group(4) else "")
            issue = Issue("native_crash", "critical", e, title, "%s|notomb" % m.group(2),
                          self.procs.get(e.pid) or m.group(9))
            issue.fields["Signal"] = "%s%s" % (m.group(2), ", fault addr %s" % m.group(5) if m.group(5) else "")
            if m.group(7):
                issue.fields["Thread"] = "%s (tid %s)" % (m.group(7), m.group(6))
            issue.hint = hint_for(m.group(2))
            self.add(issue, i, [i])
        anrs = set((x.entry.src, x.pid) for x in self.issues if x.kind == "anr")
        for i, e in self.event_anr:
            p = e.msg.strip("[] ").split(",", 4)
            if len(p) < 5 or not p[1].isdigit() or (e.src, int(p[1])) in anrs:
                continue
            issue = Issue("anr", "critical", e, "ANR in %s: %s" % (p[2], p[4]),
                          norm(re.sub(r"\(.*", "", p[4]), 80), p[2], int(p[1]))
            issue.fields["Reason"] = p[4]
            issue.fields["Source"] = "events buffer only (am_anr); the ActivityManager block is not in the log"
            issue.hint = hint_for(p[4], ANR_HINTS) or ANR_HINTS[0][1]
            self.add(issue, i)
        crashes = set((x.entry.src, x.pid) for x in self.issues if x.kind == "java_crash")
        for i, e in self.event_crash:
            p = e.msg.strip("[] ").split(",")
            if len(p) < 5 or not p[0].isdigit() or (e.src, int(p[0])) in crashes:
                continue
            where = ":".join(p[-2:]) if len(p) >= 8 else ""
            text = ",".join(p[5:-2]) if len(p) >= 8 else ""
            issue = Issue("java_crash", "critical", e, "%s%s" % (p[4], ": " + text if text else ""),
                          "%s|%s" % (p[4], where), p[2], int(p[0]))
            issue.fields["Exception"] = p[4]
            if where:
                issue.fields["Thrown at"] = where
            issue.fields["Source"] = "events buffer only (am_crash); the stack trace is not in the log"
            issue.hint = hint_for(p[4] + " " + text)
            self.add(issue, i)
        self.issues.sort(key=lambda x: x.index)

    def context(self, issue, count):
        """The last lines the process logged before the issue."""
        if count <= 0 or issue.pid is None or issue.pid < 0:
            return []
        idx = self.by_pid.get((issue.entry.src, issue.pid))
        if not idx:
            return []
        end = bisect.bisect_left(idx, issue.index)
        skip = set(id(x) for x in issue.block)
        out = []
        for k in reversed(idx[:end]):
            e = self.entries[k]
            if id(e) in skip:
                continue
            out.append(e)
            if len(out) >= count:
                break
        return list(reversed(out))


# --------------------------------------------------------------------------
# Grouping and reporting
# --------------------------------------------------------------------------

def trim_block(lines, limit):
    if limit <= 0 or len(lines) <= limit:
        return list(lines)
    keep = set(range(min(limit // 2 + 1, len(lines))))
    for i, s in enumerate(lines):
        if "Caused by: " in s or "backtrace:" in s:
            keep.update(range(i, min(i + 5, len(lines))))
    out, gap = [], 0
    for i, s in enumerate(lines):
        if i in keep and len(out) < limit + 12:
            if gap:
                out.append("    ... (%d lines left out, use --max-stack 0 for all)" % gap)
                gap = 0
            out.append(s)
        else:
            gap += 1
    if gap:
        out.append("    ... (%d lines left out, use --max-stack 0 for all)" % gap)
    return out


def match_package(issue, package):
    if not package:
        return True
    proc = issue.process or ""
    if proc == package or proc.startswith(package + ":") or proc.startswith(package + "."):
        return True
    if issue.process:
        return False
    blob = issue.title + " " + " ".join(e.msg for e in issue.block[:60])
    return package in blob


def build_result(analyzer, names, stats, args):
    entries = analyzer.entries
    kinds = None
    if args.only:
        kinds = set()
        for k in [x.strip().lower() for x in args.only.split(",") if x.strip()]:
            if k in KIND_ALIASES:
                kinds.update(KIND_ALIASES[k])
            elif k in KIND_LABEL:
                kinds.add(k)
            else:
                raise ValueError("unknown type '%s'. Use: %s" % (
                    k, ", ".join(sorted(set(KIND_LABEL) | set(KIND_ALIASES)))))
    min_rank = SEV_RANK[args.min_severity]
    issues = [x for x in analyzer.issues
              if SEV_RANK[x.severity] <= min_rank and (kinds is None or x.kind in kinds)
              and match_package(x, args.package)]

    def where(e):
        return "%s:%d" % (names[e.src], e.n) if len(names) > 1 else "line %d" % e.n

    groups = OrderedDict()
    for x in issues:
        key = (x.kind, x.process or "", x.signature)
        g = groups.get(key)
        if g is None:
            g = groups[key] = {"first": x, "items": []}
        g["items"].append(x)
    kind_order = dict((k, i) for i, k in enumerate(KIND_LABEL))
    ordered = sorted(groups.values(), key=lambda g: (
        min(SEV_RANK[x.severity] for x in g["items"]), kind_order[g["first"].kind], g["first"].index))
    out_groups = []
    member = {}
    for n, g in enumerate(ordered, 1):
        items = g["items"]
        first = items[0]
        show = first
        if first.metric is not None:
            show = max(items, key=lambda x: x.metric)
        sev = min((x.severity for x in items), key=lambda s: SEV_RANK[s])
        for x in items:
            member[id(x)] = n
        related = []
        for x in items:
            for r in x.related:
                if r not in related:
                    related.append(r)
        pids = sorted(set(x.pid for x in items if x.pid is not None and x.pid >= 0))
        out_groups.append(OrderedDict([
            ("id", n), ("severity", sev), ("type", first.kind), ("type_label", KIND_LABEL[first.kind]),
            ("process", first.process), ("pids", pids), ("count", len(items)),
            ("first_time", first.entry.stamp()), ("last_time", items[-1].entry.stamp()),
            ("first_at", where(first.entry)), ("title", show.title),
            ("fields", OrderedDict((k, v) for k, v in show.fields.items() if v)),
            ("hint", show.hint),
            ("stack", trim_block([e.text() for e in show.block], args.max_stack) if len(show.block) > 1 else []),
            ("before", [e.text(240) for e in analyzer.context(show, args.context)]
             if first.kind in CONTEXT_KINDS else []),
            ("related", related[:12]),
        ]))
    timeline = [OrderedDict([("time", x.entry.stamp()), ("at", where(x.entry)), ("group", member[id(x)]),
                             ("severity", x.severity), ("type", x.kind), ("process", x.process),
                             ("pid", x.pid if x.pid is not None and x.pid >= 0 else None), ("title", x.title)])
                for x in issues]
    counts = OrderedDict()
    for k in KIND_LABEL:
        c = sum(1 for x in issues if x.kind == k)
        if c:
            counts[k] = c
    by_sev = OrderedDict((s, sum(1 for x in issues if x.severity == s)) for s in SEVERITIES)
    return OrderedDict([
        ("sources", names),
        ("lines", stats["lines"]), ("parsed_lines", stats["parsed"]), ("skipped_lines", stats["skipped"]),
        ("formats", stats["formats"]),
        ("time_range", [entries[0].stamp(), entries[-1].stamp()] if entries else []),
        ("filters", OrderedDict((k, v) for k, v in [
            ("package", args.package), ("only", args.only), ("since", args.since), ("until", args.until),
            ("min_severity", args.min_severity if args.min_severity != "low" else None)] if v)),
        ("counts", counts), ("by_severity", by_sev),
        ("groups", out_groups), ("timeline", timeline),
    ])


def verdict(result):
    c = result["counts"]
    if not c:
        return "No problems found at this severity level."
    parts = []
    for k, label in (("java_crash", "fatal exception"), ("native_crash", "native crash"), ("anr", "ANR"),
                     ("watchdog", "system watchdog/restart"), ("service_crash", "service crash"),
                     ("lmk", "low-memory kill"), ("process_death", "unexplained process death"),
                     ("kill", "system kill"), ("exception", "non-fatal exception"),
                     ("fatal_log", "fatal-level log"), ("binder", "binder failure"),
                     ("service_blocked", "blocked service start"), ("strictmode", "StrictMode violation"),
                     ("jank", "jank event"), ("selinux", "SELinux denial"),
                     ("exception_mention", "exception mention")):
        if c.get(k):
            if c[k] > 1:
                label = label + "es" if label.endswith("crash") else label + "s"
            parts.append("%d %s" % (c[k], label))
    return ", ".join(parts) + "."


def render_text(result, show=None, timeline_limit=60):
    L = []
    w = L.append
    groups = result["groups"]
    if show is not None:
        groups = [g for g in groups if g["id"] == show]
        if not groups:
            return "No issue with id %d (ids run from 1 to %d with these filters).\n" % (show, len(result["groups"]))
    else:
        w("# Logcat analysis")
        w("")
        w("Source: %s" % ", ".join(result["sources"]))
        rng = result["time_range"]
        w("Lines: %d read, %d parsed%s%s" % (
            result["lines"], result["parsed_lines"],
            ", %d not in a logcat format" % result["skipped_lines"] if result["skipped_lines"] else "",
            "; %s -> %s" % (rng[0], rng[1]) if rng and rng[0] else ""))
        if result["filters"]:
            w("Filters: " + ", ".join("%s=%s" % kv for kv in result["filters"].items()))
        w("Result: " + verdict(result))
        w("")
        if not groups:
            return "\n".join(L) + "\n"
        w("## Summary")
        w("")
        w("| # | Severity | Type | Process | Count | First seen | What |")
        w("|---|---|---|---|---|---|---|")
        for g in groups:
            title = g["title"].replace("|", "\\|")
            if len(title) > 110:
                title = title[:107] + "..."
            w("| %d | %s | %s | %s | %d | %s | %s |" % (
                g["id"], g["severity"], g["type"], g["process"] or "-", g["count"], g["first_time"] or "-", title))
        w("")
        w("## Details")
    for g in groups:
        w("")
        w("### [%d] %s: %s" % (g["id"], g["severity"].upper(), g["type_label"]))
        w("")
        w(g["title"])
        w("")
        w("- Process: %s%s" % (g["process"] or "unknown",
                               " (pid %s)" % ", ".join(str(p) for p in g["pids"][:8]) if g["pids"] else ""))
        if g["count"] > 1:
            w("- Seen %d times: first %s (%s), last %s" % (g["count"], g["first_time"], g["first_at"], g["last_time"]))
        else:
            w("- Seen once: %s (%s)" % (g["first_time"] or "no timestamp", g["first_at"]))
        for k, v in g["fields"].items():
            w("- %s: %s" % (k, v))
        if g["hint"]:
            w("- Usual cause: %s" % g["hint"])
        if g["related"]:
            w("- After it: " + "; ".join(g["related"]))
        if g["stack"]:
            w("")
            w("Log block:")
            w("```")
            L.extend(g["stack"])
            w("```")
        if g["before"]:
            w("")
            w("Last lines from the same process before it:")
            w("```")
            L.extend(g["before"])
            w("```")
    if show is None and len(result["timeline"]) > 1:
        w("")
        w("## Timeline")
        w("")
        tl = result["timeline"]
        for t in tl[:timeline_limit]:
            title = t["title"] if len(t["title"]) <= 120 else t["title"][:117] + "..."
            w("- %s [%d] %s %s%s: %s" % (t["time"] or t["at"], t["group"], t["severity"], t["type"],
                                         " " + t["process"] if t["process"] else "", title))
        if len(tl) > timeline_limit:
            w("- ... %d more (use --json for the full timeline)" % (len(tl) - timeline_limit))
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------

def time_filter(entries, since, until):
    def key(e, with_date):
        return (e.date + " " + e.time) if with_date else e.time

    def norm_arg(a):
        a = a.strip().replace("T", " ")
        m = re.match(r"^(?:\d{4}-)?(\d\d-\d\d) (\d\d:\d\d(?::\d\d(?:\.\d+)?)?)$", a)
        if m:
            return m.group(1) + " " + m.group(2), True
        if re.match(r"^\d\d:\d\d(?::\d\d(?:\.\d+)?)?$", a):
            return a, False
        raise ValueError("bad time '%s'. Use 'MM-DD HH:MM:SS' or 'HH:MM:SS'" % a)

    out = entries
    if since:
        s, d = norm_arg(since)
        out = [e for e in out if e.time and (not d or e.date) and key(e, d) >= s]
    if until:
        u, d = norm_arg(until)
        # '~' sorts after digits, so 'HH:MM' also covers the whole minute.
        out = [e for e in out if e.time and (not d or e.date) and key(e, d) <= u + "~"]
    return out


def build_parser():
    p = argparse.ArgumentParser(
        description="Find fatal exceptions, native crashes, ANRs, service crashes, kills and exceptions in Android logcat output.")
    p.add_argument("files", nargs="*", help="logcat text files, .gz, or bugreport .zip ('-' reads stdin)")
    p.add_argument("--adb", action="store_true", help="read the log buffers of a connected device (adb logcat -d)")
    p.add_argument("--serial", help="device serial for --adb (adb -s)")
    p.add_argument("--adb-path", default="adb", help="path of the adb program")
    p.add_argument("--buffers", default="main,system,crash,events", help="buffers for --adb (default: %(default)s)")
    p.add_argument("--save", metavar="FILE", help="with --adb: also save the raw log to FILE")
    p.add_argument("--package", help="only problems of this app/process (package name)")
    p.add_argument("--only", help="only these types, comma separated: crash, anr, service, exceptions, native, java, "
                                  "memory, system, or exact types such as java_crash, strictmode, jank, selinux")
    p.add_argument("--min-severity", choices=SEVERITIES, default="low",
                   help="lowest severity to report (default: low; 'info' adds normal system kills)")
    p.add_argument("--since", help="ignore lines before this time ('MM-DD HH:MM:SS' or 'HH:MM:SS')")
    p.add_argument("--until", help="ignore lines after this time")
    p.add_argument("--context", type=int, default=8, help="lines of the same process shown before each problem (default 8)")
    p.add_argument("--max-stack", type=int, default=40, help="longest log block printed per problem, 0 = all (default 40)")
    p.add_argument("--jank-frames", type=int, default=60, help="report skipped frames from this count (default 60)")
    p.add_argument("--show", type=int, metavar="ID", help="print only the problem with this id, in full")
    p.add_argument("--json", action="store_true", help="print JSON instead of text")
    p.add_argument("--out", metavar="FILE", help="write the report to FILE instead of standard output")
    p.add_argument("--fail-on", choices=SEVERITIES, help="exit with code 1 if a problem of this severity or worse is found")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.show is not None and args.max_stack == 40:
        args.max_stack = 0
    try:
        sources = []
        if args.adb:
            text = capture_adb(args.serial, args.buffers, adb=args.adb_path)
            if args.save:
                with io.open(args.save, "w", encoding="utf-8", newline="\n") as f:
                    f.write(text)
            sources.append(("adb logcat" + (" (%s)" % args.serial if args.serial else ""), text))
        files = list(args.files)
        if not files and not args.adb:
            if sys.stdin is not None and not sys.stdin.isatty():
                files = ["-"]
            else:
                sys.stderr.write("error: give a logcat file, '-' for stdin, or --adb. See --help.\n")
                return 2
        for path in files:
            sources.extend(read_source(path))
        entries, names = [], []
        stats = {"lines": 0, "parsed": 0, "skipped": 0, "formats": {}}
        for src, (name, text) in enumerate(sources):
            got, st = parse_lines(text.splitlines(), src)
            names.append(name)
            entries.extend(got)
            for k in ("lines", "parsed", "skipped"):
                stats[k] += st[k]
            for k, v in st["formats"].items():
                stats["formats"][k] = stats["formats"].get(k, 0) + v
        if not entries:
            sys.stderr.write(
                "error: no logcat lines found in %s (%d lines read). Expected 'adb logcat -v threadtime' output, "
                "the time or brief format, or the Android Studio Logcat format.\n" % (", ".join(names), stats["lines"]))
            return 2
        entries = time_filter(entries, args.since, args.until)
        analyzer = Analyzer(entries, package=args.package, jank_frames=args.jank_frames)
        analyzer.run()
        result = build_result(analyzer, names, stats, args)
    except (IOError, OSError, ValueError, zipfile.BadZipfile) as ex:
        sys.stderr.write("error: %s\n" % ex)
        return 2
    if args.json:
        text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    else:
        text = render_text(result, show=args.show)
    if args.out:
        with io.open(args.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        sys.stderr.write("report written to %s (%s)\n" % (args.out, verdict(result)))
    else:
        try:
            sys.stdout.write(text)
        except UnicodeEncodeError:
            sys.stdout.buffer.write(text.encode("utf-8", "replace"))
    if args.fail_on and any(SEV_RANK[g["severity"]] <= SEV_RANK[args.fail_on] for g in result["groups"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
