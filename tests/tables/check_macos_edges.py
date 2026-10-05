#!/usr/bin/env python3
"""Check the edges of the macOS seam that no other check reaches.

    venv/bin/python3 tests/tables/check_macos_edges.py

`check_macos_seam.py` proves the menu bar and a real `afplay`, `check_focus.py`
the window sweep, `check_raise.py` which way B takes, `check_sessions.py` the
registry and the happy `tty`. What is left is the refusals (principle 7: each
one says so in words) of `Sound.play`, `Frontmost.tab_tty`, `Focus.url`,
`Focus.tab`, `_landed`, `Focus.ask`, `Process.started/tty/title`, plus the
right click on the status item. Every known answer comes from the method's own
docstring or from the sentence it is documented to say.

**Nothing here touches the real screen.** `osascript`, `afplay`, Launch
Services, activation and `AXIsProcessTrustedWithOptions` (it can show a system
dialog, task 50) all go to fakes that record what they were asked, and a
tripwire on the real `subprocess` refuses and records any `osascript`/`afplay`/
`open` that slips past them. The tripwire has its own reference leg first.

**Process.title writes to a real pseudo-terminal** (`os.openpty()`), and what
the master reads is compared with the literal OSC 2 bytes: a real artifact,
not a fixture. The only tty this file ever writes to is that slave. The
`Process.tty` legs are real processes against `ps -o tty=`, the second source
(principle 4): a child on the pty, a child with no terminal, a dead pid, pid 1.

**The control is mutants made from the source itself**: one rule's text in
`macos.py` is replaced, the method recompiled, and the table re-run. A mutant
whose text is no longer in the file is reported as wrong, so this cannot go
quietly stale when `macos.py` changes.
"""
from __future__ import annotations

import __future__
import ctypes
import fcntl
import inspect
import os
import select
import signal
import struct
import subprocess
import sys
import textwrap
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.platform_seam import macos                                   # noqa: E402

TERMINAL, VSCODE, WARP = "com.apple.Terminal", "com.microsoft.VSCode", "dev.warp.Warp-Stable"
SOUND = "/System/Library/Sounds/Sosumi.aiff"
TITLE = "quarry · d711"          # the title Warp took at the desk, `Process.title`'s docstring
WARP_TAB = "warp://session/" + "4de8df8f" * 4
NO_TTY = "wobble-no-such-tty"    # /dev/ has no such node; `title()` must fail to open it

# Real osascript stderr for the two refusals the seam tells apart (task 43).
NOT_ALLOWED = "execution error: Not authorized to send Apple events to Terminal. (-1743)\n"
NO_TAB = "execution error: Can’t get selected tab of window 1. (-1728)\n"


# --- the sheet ---------------------------------------------------------------

class Sheet:
    def __init__(self, quiet: bool = False) -> None:
        self.quiet, self.bad, self.rows = quiet, 0, 0

    def head(self, text: str) -> None:
        if not self.quiet:
            print(f"\n  {text}")

    def row(self, what: str, got, want) -> None:
        good = got == want
        self.bad += not good
        self.rows += 1
        if not self.quiet:
            print(f"    {what:<70} {'ok' if good else f'<-- WRONG: {got!r}, wanted {want!r}'}")


class Blocked(Exception):
    """A write that would have stalled the daemon's loop, cut by an alarm."""


def attempt(call):
    """The answer, or what it raised: a seam that raises has broken principle 7."""
    try:
        return call()
    except Blocked:
        return "blocked"
    except Exception as exc:                                          # noqa: BLE001
        return f"raised {type(exc).__name__}: {exc}"


class deadline:
    """An alarm that turns a blocked syscall into `Blocked` after `seconds`."""

    def __init__(self, seconds: float) -> None:
        self.seconds = seconds

    def __enter__(self):
        def ring(_sig, _frame):
            raise Blocked
        self.old = signal.signal(signal.SIGALRM, ring)
        signal.setitimer(signal.ITIMER_REAL, self.seconds)

    def __exit__(self, *_):
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, self.old)


# --- the tripwire on the real subprocess --------------------------------------

REAL_RUN, REAL_POPEN = subprocess.run, subprocess.Popen
FORBIDDEN = {"osascript", "afplay", "open"}
ESCAPED: list = []


def _argv0(args) -> str:
    first = args[0] if isinstance(args, (list, tuple)) and args else str(args).split(" ")[0]
    return os.path.basename(str(first))


def _tripwire_run(args, *a, **k):
    if _argv0(args) in FORBIDDEN:
        ESCAPED.append(list(args))
        raise PermissionError(f"the desk refused a real {_argv0(args)}")
    return REAL_RUN(args, *a, **k)


def _tripwire_popen(args, *a, **k):
    if _argv0(args) in FORBIDDEN:
        ESCAPED.append(list(args))
        raise PermissionError(f"the desk refused a real {_argv0(args)}")
    return REAL_POPEN(args, *a, **k)


# --- fakes that record --------------------------------------------------------

class FakeSubprocess:
    """What `macos.subprocess` is while the table runs: `run` and `Popen` recorded."""

    DEVNULL = subprocess.DEVNULL
    TimeoutExpired = subprocess.TimeoutExpired
    CompletedProcess = subprocess.CompletedProcess

    def __init__(self, answer=None, popen_raises=None) -> None:
        # `answer` is (returncode, stdout, stderr), or an exception to raise.
        self.answer = answer if answer is not None else (0, "", "")
        self.popen_raises = popen_raises
        self.runs: list = []
        self.popens: list = []

    def run(self, args, **kw):
        self.runs.append((list(args), kw))
        if isinstance(self.answer, BaseException):
            raise self.answer
        code, out, err = self.answer
        return subprocess.CompletedProcess(args, code, out, err)

    def Popen(self, args, **kw):                                      # noqa: N802
        self.popens.append((list(args), kw))
        if self.popen_raises is not None:
            raise self.popen_raises
        return FakeProcess()


class FakeProcess:
    """An `afplay` that is still playing until terminated."""

    def __init__(self) -> None:
        self.terminated = 0

    def poll(self):
        return 0 if self.terminated else None

    def terminate(self):
        self.terminated += 1


class FakeApp:
    """As much of `NSRunningApplication` as `Focus` reads. Never activated here."""

    def __init__(self, name, bundle, pid) -> None:
        self.name, self.bundle, self.pid = name, bundle, pid

    def localizedName(self):                                          # noqa: N802
        return self.name

    def bundleIdentifier(self):                                       # noqa: N802
        return self.bundle

    def processIdentifier(self):                                      # noqa: N802
        return self.pid

    def activateWithOptions_(self, _options):                         # noqa: N802
        raise AssertionError("this check never activates an app")


class FakeURL:
    def __init__(self, text) -> None:
        self.text = text


class FakeNSURL:
    """`NSURL.URLWithString_`, answering None for the strings it is told to."""

    refuse: set = set()
    asked: list = []

    @classmethod
    def URLWithString_(cls, text):                                    # noqa: N802
        cls.asked.append(text)
        return None if text in cls.refuse else FakeURL(text)


class FakeWorkspace:
    """`NSWorkspace.sharedWorkspace()`: the running apps and Launch Services."""

    def __init__(self, apps, opens=True, ax=None) -> None:
        self.apps, self.opens, self.ax = apps, opens, ax
        self.opened: list = []

    def sharedWorkspace(self):                                        # noqa: N802
        return self

    def runningApplications(self):                                    # noqa: N802
        return self.apps

    def openURL_(self, url):                                          # noqa: N802
        self.opened.append(url.text)
        return self.opens


class FakeRunning:
    @staticmethod
    def runningApplicationWithProcessIdentifier_(_pid):              # noqa: N802
        return None


class FakeAX:
    """ApplicationServices, for what `Frontmost.title` and `Focus.ask` read.

    Anything that would move a window is an AssertionError: `_forward` and
    `_arrived` are replaced on the instance, so nothing here should reach them.
    """

    kAXFocusedWindowAttribute = "AXFocusedWindow"
    kAXTitleAttribute = "AXTitle"
    kAXTrustedCheckOptionPrompt = "AXTrustedCheckOptionPrompt"
    kCGWindowListOptionOnScreenOnly = 1
    kCGWindowListExcludeDesktopElements = 16
    kCGNullWindowID = 0
    kCGWindowLayer = "kCGWindowLayer"
    kCGWindowOwnerPID = "kCGWindowOwnerPID"

    def __init__(self, trusted=True, locked=False, front=None, title=TITLE) -> None:
        self.trusted, self.locked, self.front, self.title = trusted, locked, front, title
        self.prompted: list = []

    def AXIsProcessTrusted(self):                                     # noqa: N802
        return self.trusted

    def AXIsProcessTrustedWithOptions(self, options):                 # noqa: N802
        self.prompted.append(dict(options))
        return self.trusted

    def CGSessionCopyCurrentDictionary(self):                         # noqa: N802
        return {"CGSSessionScreenIsLocked": self.locked}

    def CGWindowListCopyWindowInfo(self, _option, _relative):         # noqa: N802
        if self.front is None:
            return []
        return [{self.kCGWindowLayer: 0, self.kCGWindowOwnerPID: self.front}]

    def AXUIElementCreateApplication(self, pid):                      # noqa: N802
        return ("app", pid)

    def AXUIElementSetMessagingTimeout(self, _element, _seconds):     # noqa: N802
        pass

    def AXUIElementCopyAttributeValue(self, element, attribute, _placeholder):  # noqa: N802
        if attribute == self.kAXFocusedWindowAttribute:
            return 0, ("win", element[1])
        if attribute == self.kAXTitleAttribute:
            return (0, self.title) if self.title else (-25212, None)
        raise AssertionError(f"nothing here asks for {attribute}")

    def AXUIElementSetAttributeValue(self, *_):                       # noqa: N802
        raise AssertionError("this check never makes a window main or frontmost")

    def AXUIElementPerformAction(self, *_):                           # noqa: N802
        raise AssertionError("this check never raises a window")


class NoApplicationServices:
    """A real ImportError for a real import, as `check_focus.py` makes it."""

    def find_spec(self, name, path=None, target=None):
        if name == "ApplicationServices":
            raise ImportError("blocked at the desk — pretending it was never installed")
        return None


class OsProxy:
    """`macos.os` for one `title()` call: real `os`, with opens and closes kept."""

    def __init__(self, **over) -> None:
        self.over = over
        self.opened: list = []
        self.closed: list = []

    def open(self, path, flags):
        fd = os.open(path, flags)
        self.opened.append(fd)
        return fd

    def close(self, fd):
        self.closed.append(fd)
        os.close(fd)

    def __getattr__(self, name):
        return self.over[name] if name in self.over else getattr(os, name)


class CtypesProxy:
    """`macos.ctypes` with one library that will not load."""

    ALL = object()

    def __init__(self, refuse) -> None:
        self.refuse = refuse

    def CDLL(self, name, **kw):                                       # noqa: N802
        if name == self.refuse:
            raise OSError(f"dlopen({name}) refused at the desk")
        return ctypes.CDLL(name, **kw)

    def __getattr__(self, name):
        return getattr(ctypes, name)


class FakeLib:
    """libc and libproc at once, answering as told and keeping what was asked."""

    def __init__(self, sysctl=0, filled=136, errno=0, tdev=0, devname=None) -> None:
        self.sysctl_rc, self.filled, self.errno = sysctl, filled, errno
        self.tdev, self.devname_answer = tdev, devname
        self.named: list = []

    def sysctl(self, *_):
        ctypes.set_errno(self.errno)
        return self.sysctl_rc

    def proc_pidinfo(self, _pid, _flavor, _arg, buf, _size):
        struct.pack_into("<I", buf, macos._E_TDEV, self.tdev)
        ctypes.set_errno(self.errno)
        return self.filled

    def devname(self, tdev, mode):
        self.named.append((tdev, mode))
        return self.devname_answer


class FakeEvent:
    def __init__(self, kind, flags=0) -> None:
        self.kind, self.flags = kind, flags

    def type(self):
        return self.kind

    def modifierFlags(self):                                          # noqa: N802
        return self.flags


class FakeNSApplication:
    event = None

    @classmethod
    def sharedApplication(cls):                                       # noqa: N802
        return cls

    @classmethod
    def currentEvent(cls):                                            # noqa: N802
        return cls.event


# --- installing and restoring --------------------------------------------------

SAVED = {name: getattr(macos, name) for name in (
    "NSWorkspace", "NSURL", "NSApplication", "NSRunningApplication", "subprocess", "os",
    "ctypes", "_AX", "_AX_WHY", "_AX_MISSING", "_AX_TRIED")}


def restore() -> None:
    for name, value in SAVED.items():
        setattr(macos, name, value)


def desk(apps=(), *, trusted=True, locked=False, front=None, title=TITLE, opens=True,
         answer=None, popen_raises=None):
    """A whole fake macOS behind the seam; hands back (ax, workspace, subprocess)."""
    restore()
    ax = FakeAX(trusted=trusted, locked=locked, front=front, title=title)
    work = FakeWorkspace(list(apps), opens=opens, ax=ax)
    sub = FakeSubprocess(answer=answer, popen_raises=popen_raises)
    FakeNSURL.refuse, FakeNSURL.asked = set(), []
    macos.NSWorkspace, macos.NSURL, macos.NSRunningApplication = work, FakeNSURL, FakeRunning
    macos.subprocess = sub
    macos._AX, macos._AX_WHY, macos._AX_MISSING, macos._AX_TRIED = ax, None, None, True
    return ax, work, sub


class no_framework:
    """ApplicationServices missing for real: the import itself is blocked."""

    def __enter__(self):
        macos._AX, macos._AX_WHY, macos._AX_MISSING, macos._AX_TRIED = None, None, None, False
        self.saved = sys.modules.pop("ApplicationServices", None)
        self.blocker = NoApplicationServices()
        sys.meta_path.insert(0, self.blocker)

    def __exit__(self, *_):
        sys.meta_path.remove(self.blocker)
        if self.saved is not None:
            sys.modules["ApplicationServices"] = self.saved


def landing(focus, *, arrive=True, forward=""):
    """Replace `_arrived`/`_forward` on this one instance, and record their calls."""
    seen = {"waits": [], "forwarded": 0}

    def arrived(_ax, _pid, wait=0.5):
        seen["waits"].append(wait)
        return arrive

    def forwarded(_ax, _running):
        seen["forwarded"] += 1
        return forward
    focus._arrived, focus._forward = arrived, forwarded
    return seen


class Pty:
    """One real pseudo-terminal, the only tty this file ever writes to."""

    def __enter__(self):
        self.master, self.slave = os.openpty()
        self.name = os.ttyname(self.slave).removeprefix("/dev/")
        fcntl.fcntl(self.master, fcntl.F_SETFL,
                    fcntl.fcntl(self.master, fcntl.F_GETFL) | os.O_NONBLOCK)
        return self

    def read(self) -> bytes:
        got = b""
        while select.select([self.master], [], [], 0.05)[0]:
            try:
                chunk = os.read(self.master, 4096)
            except BlockingIOError:
                break
            if not chunk:
                break
            got += chunk
        return got

    def fill(self) -> None:
        """Write to the slave until it takes no more: a terminal that stopped reading."""
        fd = os.open(f"/dev/{self.name}", os.O_WRONLY | os.O_NOCTTY | os.O_NONBLOCK)
        try:
            for chunk in (4096, 1024, 256, 64, 16, 4, 1):
                while True:
                    try:
                        os.write(fd, b"x" * chunk)
                    except BlockingIOError:
                        break
        finally:
            os.close(fd)

    def __exit__(self, *_):
        os.close(self.master)
        os.close(self.slave)


def osc2(text: str) -> bytes:
    """What `Process.title` is documented to write, spelt out as bytes."""
    return b"\x1b]2;" + text.encode() + b"\x07"


def on_pty(proc, pty, asked=None):
    """Point `proc.tty` at the pty's slave, keeping which pids were asked."""
    def tty(pid):
        if asked is not None:
            asked.append(pid)
        return pty.name, None
    proc.tty = tty
    return proc


# --- the table -----------------------------------------------------------------

def table(sheet: Sheet) -> None:
    sound_edges(sheet)
    tab_tty_edges(sheet)
    url_edges(sheet)
    tab_edges(sheet)
    landed_edges(sheet)
    ask_edges(sheet)
    started_edges(sheet)
    tty_edges(sheet)
    title_edges(sheet)
    click_edges(sheet)
    restore()


def sound_edges(sheet: Sheet) -> None:
    sheet.head("Sound.play — the volume reaches afplay, and a spawn that fails says so")
    _, _, sub = desk()
    sound = macos.Sound()
    sheet.row("a volume is handed to afplay as -v, before the path",
              (attempt(lambda: sound.play(SOUND, volume=0.3)), sub.popens[-1][0]),
              ((True, None), ["afplay", "-v", "0.3", SOUND]))
    sheet.row("…with its output thrown away, never waited for",
              sub.popens[-1][1], {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL})
    sound.play(SOUND, volume=0.0)
    sheet.row("a volume of 0.0 is a volume, not a missing one",
              sub.popens[-1][0], ["afplay", "-v", "0.0", SOUND])
    sound.play(SOUND)
    sheet.row("no volume, no -v", sub.popens[-1][0], ["afplay", SOUND])

    _, _, sub = desk(popen_raises=OSError(2, "No such file or directory"))
    sound = macos.Sound()
    playing = FakeProcess()
    sound._playing = playing
    sheet.row("afplay that cannot start is said, not raised",
              attempt(lambda: sound.play(SOUND, volume=0.5)),
              (False, f"could not play {SOUND}: [Errno 2] No such file or directory"))
    sheet.row("…the sound already playing was still cut first (criterion 4)",
              (playing.terminated, sound._playing), (1, None))


def tab_tty_edges(sheet: Sheet) -> None:
    sheet.head("Frontmost.tab_tty — the tab in front, or why its folder decides (task 43)")
    terminal = FakeApp("Terminal", TERMINAL, 300)
    front = macos.Frontmost()

    _, _, sub = desk([terminal])
    sheet.row("an app with no known script: said, and nothing run",
              (attempt(lambda: front.tab_tty(VSCODE)), sub.runs),
              ((None, f"no way is known to read {VSCODE}'s tab, so its folder decides"), []))
    _, _, sub = desk([FakeApp("Code", VSCODE, 30)])
    sheet.row("Terminal not running: nothing to say, and it is not launched",
              (attempt(lambda: front.tab_tty(TERMINAL)), sub.runs), ((None, None), []))

    _, _, sub = desk([terminal], answer=subprocess.TimeoutExpired("osascript", 2.0))
    sheet.row("osascript timing out: a consent dialog may be waiting",
              attempt(lambda: front.tab_tty(TERMINAL)),
              (None, f"Terminal did not say its tab in 2s — a consent dialog may be "
                     f"waiting — so its folder decides"))
    sheet.row("…asked with the script alone, captured, text, and the timeout",
              sub.runs, [(["osascript", "-e", macos._FRONT_TTY_SCRIPTS[TERMINAL]],
                          {"capture_output": True, "text": True, "timeout": 2.0})])
    _, _, sub = desk([terminal], answer=subprocess.TimeoutExpired("osascript", 0.5))
    sheet.row("…a fractional timeout is said as it was given",
              attempt(lambda: front.tab_tty(TERMINAL, timeout=0.5)),
              (None, f"Terminal did not say its tab in 0.5s — a consent dialog may be "
                     f"waiting — so its folder decides"))

    _, _, sub = desk([terminal], answer=OSError(8, "Exec format error"))
    sheet.row("osascript that will not run is said",
              attempt(lambda: front.tab_tty(TERMINAL)),
              (None, f"osascript could not run ([Errno 8] Exec format error), so "
                     f"Terminal's folder decides"))
    _, _, sub = desk([terminal], answer=(1, "", NOT_ALLOWED))
    sheet.row("-1743: Automation refused, and where to allow it",
              attempt(lambda: front.tab_tty(TERMINAL)),
              (None, f"macOS has not let wobble ask Terminal which tab is in front, so "
                     f"its folder decides — allow it in System Settings › Privacy & "
                     f"Security › Automation"))
    _, _, sub = desk([terminal], answer=(1, "", NO_TAB))
    sheet.row("any other failure (a window with no tab) is an answer: nothing",
              attempt(lambda: front.tab_tty(TERMINAL)), (None, None))
    _, _, sub = desk([terminal], answer=(0, "/dev/ttys004\n", ""))
    sheet.row("/dev/ttys004 comes back as ttys004",
              attempt(lambda: front.tab_tty(TERMINAL)), ("ttys004", None))
    _, _, sub = desk([terminal], answer=(0, "ttys005\n", ""))
    sheet.row("…and a tty with no prefix is left alone",
              attempt(lambda: front.tab_tty(TERMINAL)), ("ttys005", None))
    _, _, sub = desk([terminal], answer=(0, "\n", ""))
    sheet.row("no window at all: the empty answer is nothing, not ''",
              attempt(lambda: front.tab_tty(TERMINAL)), (None, None))


def url_edges(sheet: Sheet) -> None:
    sheet.head("Focus.url — Launch Services, and what came forward")
    warp = FakeApp("Warp", WARP, 500)

    with no_framework():
        _, work, _ = desk([warp])
        macos._AX, macos._AX_WHY, macos._AX_MISSING, macos._AX_TRIED = None, None, None, False
        got = attempt(lambda: macos.Focus().url(WARP_TAB, app=WARP))
        sheet.row("no Accessibility framework: its sentence, and nothing opened",
                  (got, "pyobjc-framework-ApplicationServices" in str(got), work.opened),
                  ((False, macos._AX_WHY), True, []))

    ax, work, _ = desk([warp], locked=True)
    sheet.row("a locked screen: LOCKED, and nothing opened",
              (attempt(lambda: macos.Focus().url(WARP_TAB, app=WARP)), work.opened,
               FakeNSURL.asked), ((False, macos.LOCKED), [], []))
    ax, work, _ = desk([FakeApp("Code", VSCODE, 30)])
    sheet.row("the session's app not open: said, and nothing opened",
              (attempt(lambda: macos.Focus().url(WARP_TAB, app=WARP)), work.opened),
              ((False, f"the app this session runs in ({WARP}) is not open, so "
                       f"{WARP_TAB} was not opened — nothing came forward"), []))
    ax, work, _ = desk([warp])
    FakeNSURL.refuse = {"not a url"}
    sheet.row("a string NSURL will not parse: said, and nothing opened",
              (attempt(lambda: macos.Focus().url("not a url", app=WARP)), work.opened),
              ((False, "macOS would not open not a url — nothing came forward"), []))
    ax, work, _ = desk([warp], opens=False)
    focus = macos.Focus()
    seen = landing(focus)
    sheet.row("Launch Services refusing: said, and not read back as landed",
              (attempt(lambda: focus.url(WARP_TAB, app=WARP)), work.opened, seen["waits"]),
              ((False, f"macOS would not open {WARP_TAB} — nothing came forward"),
               [WARP_TAB], []))
    ax, work, _ = desk([warp], front=500)
    focus = macos.Focus()
    seen = landing(focus)
    sheet.row("opened: its app came forward, and the title in front is said",
              attempt(lambda: focus.url(WARP_TAB, app=WARP, timeout=0.8)),
              (True, f"Warp opened {WARP_TAB} and came forward, {TITLE!r} in front"))
    sheet.row("…read back within the url's own timeout, and not pushed",
              (seen["waits"], seen["forwarded"]), ([0.8], 0))


def tab_edges(sheet: Sheet) -> None:
    sheet.head("Focus.tab — Terminal's tab by its tty (tasks 38, 43)")
    terminal = FakeApp("Terminal", TERMINAL, 300)
    script = macos._TAB_SCRIPTS[TERMINAL]

    _, _, sub = desk([terminal])
    sheet.row("an app with no tab script: said, and nothing run",
              (attempt(lambda: macos.Focus().tab("ttys003", app=VSCODE)), sub.runs),
              ((False, f"no way is known to pick a tab in {VSCODE} — nothing was selected"),
               []))
    with no_framework():
        _, _, sub = desk([terminal])
        macos._AX, macos._AX_WHY, macos._AX_MISSING, macos._AX_TRIED = None, None, None, False
        got = attempt(lambda: macos.Focus().tab("ttys003", app=TERMINAL))
        sheet.row("no Accessibility framework: its sentence, and nothing run",
                  (got, "pyobjc-framework-ApplicationServices" in str(got), sub.runs),
                  ((False, macos._AX_WHY), True, []))
    _, _, sub = desk([terminal], locked=True)
    sheet.row("a locked screen: LOCKED, and nothing run",
              (attempt(lambda: macos.Focus().tab("ttys003", app=TERMINAL)), sub.runs),
              ((False, macos.LOCKED), []))
    _, _, sub = desk([FakeApp("Code", VSCODE, 30)])
    sheet.row("Terminal not open: said, and never launched by `tell`",
              (attempt(lambda: macos.Focus().tab("ttys003", app=TERMINAL)), sub.runs),
              ((False, f"the app this session runs in ({TERMINAL}) is not open — "
                       f"nothing was selected"), []))

    _, _, sub = desk([terminal], answer=subprocess.TimeoutExpired("osascript", 30.0))
    sheet.row("osascript timing out: a consent dialog may be waiting",
              attempt(lambda: macos.Focus().tab("ttys003", app=TERMINAL)),
              (False, "Terminal did not answer in 30s — a consent dialog may be waiting "
                      "on screen. Nothing was selected"))
    sheet.row("…the tty is argv, never spliced into the script",
              sub.runs, [(["osascript", "-e", script, "/dev/ttys003"],
                          {"capture_output": True, "text": True, "timeout": 30.0})])
    _, _, sub = desk([FakeApp(None, TERMINAL, 300)],
                     answer=subprocess.TimeoutExpired("osascript", 30.0))
    sheet.row("…an app with no name is called by its bundle id",
              attempt(lambda: macos.Focus().tab("ttys003", app=TERMINAL))[1].split(" did ")[0],
              TERMINAL)

    _, _, sub = desk([terminal], answer=OSError(8, "Exec format error"))
    sheet.row("osascript that will not run is said",
              attempt(lambda: macos.Focus().tab("ttys003", app=TERMINAL)),
              (False, "osascript could not run ([Errno 8] Exec format error) — nothing "
                      "was selected"))
    _, _, sub = desk([terminal], answer=(1, "", NOT_ALLOWED))
    sheet.row("-1743: Automation refused, and where to allow it",
              attempt(lambda: macos.Focus().tab("ttys003", app=TERMINAL)),
              (False, "macOS has not let wobble control Terminal, so its tab was not "
                      "selected — allow it in System Settings › Privacy & Security › "
                      "Automation. The notification itself is unaffected."))
    noisy = "  execution error: " + "e" * 300 + "\n"
    _, _, sub = desk([terminal], answer=(1, "", noisy))
    sheet.row("any other failure: refused, with stderr cut to 200 characters",
              attempt(lambda: macos.Focus().tab("ttys003", app=TERMINAL)),
              (False, "Terminal refused to select a tab (execution error: " + "e" * 183
                      + ") — nothing was selected"))
    _, _, sub = desk([terminal], answer=(0, "none\n", ""))
    focus = macos.Focus()
    seen = landing(focus)
    sheet.row("exit 0 saying none: no tab is on that tty",
              (attempt(lambda: focus.tab("ttys003", app=TERMINAL)), seen["waits"]),
              ((False, "no tab of Terminal is on ttys003 — nothing was selected"), []))
    _, _, sub = desk([terminal], answer=(0, "found\n", ""), front=300)
    focus = macos.Focus()
    seen = landing(focus)
    sheet.row("found: selected, and read back as landed",
              attempt(lambda: focus.tab("ttys003", app=TERMINAL)),
              (True, f"Terminal selected its tab on ttys003 and came forward, "
                     f"{TITLE!r} in front"))
    sheet.row("…read back for half a second, and not pushed",
              (seen["waits"], seen["forwarded"]), ([0.5], 0))


def landed_edges(sheet: Sheet) -> None:
    sheet.head("_landed and _app — after the act, is its app in front?")
    terminal = FakeApp("Terminal", TERMINAL, 300)
    desk([FakeApp("Code", VSCODE, 30), terminal], front=300)
    focus = macos.Focus()
    sheet.row("_app finds the running app by bundle id", focus._app(TERMINAL), terminal)
    sheet.row("…and answers None rather than launching one", focus._app(WARP), None)

    ax, _, _ = desk([terminal], front=300)
    focus = macos.Focus()
    seen = landing(focus, arrive=False, forward=" via Accessibility")
    sheet.row("not arrived: brought forward, and says how",
              attempt(lambda: focus._landed(ax, terminal, "did x", 0.5)),
              (True, f"Terminal did x and came forward via Accessibility, {TITLE!r} in front"))
    sheet.row("…pushed exactly once", seen["forwarded"], 1)
    ax, _, _ = desk([terminal], front=300)
    focus = macos.Focus()
    landing(focus, arrive=False, forward=None)
    sheet.row("kept behind, both ways: not a success",
              attempt(lambda: focus._landed(ax, terminal, "did x", 0.5)),
              (False, "Terminal did x, but macOS kept it behind, both ways — nothing "
                      "came forward"))
    ax, _, _ = desk([terminal], front=300, title=None)
    focus = macos.Focus()
    landing(focus)
    sheet.row("no title in front: the sentence ends at 'came forward'",
              attempt(lambda: focus._landed(ax, terminal, "did x", 0.5)),
              (True, "Terminal did x and came forward"))
    ax, _, _ = desk([terminal], front=300, locked=True)
    focus = macos.Focus()
    landing(focus)
    sheet.row("locked while landing: no title is believed",
              attempt(lambda: focus._landed(ax, terminal, "did x", 0.5)),
              (True, "Terminal did x and came forward"))
    ax, _, _ = desk([terminal], front=300, title=None)
    focus = macos.Focus()
    landing(focus)
    sheet.row("no name: the bundle id stands in",
              attempt(lambda: focus._landed(ax, FakeApp(None, TERMINAL, 300), "did x", 0.5)),
              (True, f"{TERMINAL} did x and came forward"))
    sheet.row("no name and no bundle: 'its app'",
              attempt(lambda: focus._landed(ax, FakeApp(None, None, 300), "did x", 0.5)),
              (True, "its app did x and came forward"))


def ask_edges(sheet: Sheet) -> None:
    sheet.head("Focus.ask — the system's own dialog, only when it is needed (task 50)")
    with no_framework():
        desk()
        macos._AX, macos._AX_WHY, macos._AX_MISSING, macos._AX_TRIED = None, None, None, False
        got = attempt(lambda: macos.Focus().ask())
        # Its own sentence, not Focus's: nobody tried to raise a window here.
        sheet.row("no Accessibility framework: its own sentence, not 'no window was raised'",
                  (got, "pyobjc-framework-ApplicationServices" in str(got),
                   "no window was raised" in str(got)),
                  ((False, macos._CANNOT_ASK.format(why=macos._AX_MISSING)), True, False))
    ax, _, _ = desk(trusted=True)
    sheet.row("already trusted: yes, and no dialog shown",
              (attempt(lambda: macos.Focus().ask()), ax.prompted), ((True, None), []))
    ax, _, _ = desk(trusted=False)
    sheet.row("not trusted: the dialog asked for with the prompt option",
              (attempt(lambda: macos.Focus().ask()), ax.prompted),
              ((False, "macOS has not granted Accessibility yet, so its own dialog was "
                       "shown — allow wobble in System Settings › Privacy & Security › "
                       "Accessibility. Until then no window is raised, and a signal "
                       "plays even while you look at its session."),
               [{"AXTrustedCheckOptionPrompt": True}]))
    ax.trusted = True
    sheet.row("…and asked fresh: granted a moment later, it says yes",
              (attempt(lambda: macos.Focus().ask()), len(ax.prompted)), ((True, None), 1))


def started_edges(sheet: Sheet) -> None:
    sheet.head("Process.started — could not tell is not the same as gone")
    restore()
    sheet.row("a pid that is not a number: out of reach, said",
              attempt(lambda: macos.Process().started("abc")),
              (None, "sysctl is out of reach (invalid literal for int() with base 10: "
                     "'abc'), so whether pid abc runs is unknown"))
    macos.ctypes = CtypesProxy(None)
    sheet.row("libc that will not load: out of reach, said",
              attempt(lambda: macos.Process().started(4242)),
              (None, "sysctl is out of reach (dlopen(None) refused at the desk), so "
                     "whether pid 4242 runs is unknown"))
    restore()
    proc = macos.Process()
    proc._libc = FakeLib(sysctl=-1, errno=12)
    sheet.row("sysctl failing: its errno said, not a dead pid",
              attempt(lambda: proc.started(4242)),
              (None, "sysctl could not read pid 4242 (errno 12), so whether it still runs "
                     "is unknown"))
    proc._libc = object()
    sheet.row("a libc with no sysctl: out of reach, said",
              attempt(lambda: proc.started(4242)),
              (None, "sysctl is out of reach ('object' object has no attribute 'sysctl'), "
                     "so whether pid 4242 runs is unknown"))


def tty_edges(sheet: Sheet) -> None:
    sheet.head("Process.tty — which terminal, or why it cannot say (task 42)")
    restore()
    sheet.row("a pid that is not a number: out of reach, said",
              attempt(lambda: macos.Process().tty("abc")),
              (None, "libproc is out of reach (invalid literal for int() with base 10: "
                     "'abc'), so pid abc's terminal is unknown"))
    macos.ctypes = CtypesProxy("/usr/lib/libproc.dylib")
    sheet.row("libproc that will not load: out of reach, said",
              attempt(lambda: macos.Process().tty(4242)),
              (None, "libproc is out of reach (dlopen(/usr/lib/libproc.dylib) refused at "
                     "the desk), so pid 4242's terminal is unknown"))
    restore()
    proc = macos.Process()
    proc._libc, proc._proc = FakeLib(), object()
    sheet.row("a libproc with no proc_pidinfo: out of reach, said",
              attempt(lambda: proc.tty(4242)),
              (None, "libproc is out of reach ('object' object has no attribute "
                     "'proc_pidinfo'), so pid 4242's terminal is unknown"))
    # Real: launchd is root's, and proc_pidinfo refuses another user's pid with
    # EPERM (measured 2026-09-29 while writing this). Unknown, never "no terminal".
    if os.getuid() != 0:
        sheet.row("pid 1, root's: EPERM is could-not-tell, not a dead pid",
                  attempt(lambda: macos.Process().tty(1)),
                  (None, "proc_pidinfo could not read pid 1 (errno 1), so its terminal "
                         "is unknown"))
    proc = macos.Process()
    lib = FakeLib(tdev=0x1000ABC, devname=None)
    proc._libc, proc._proc = lib, lib
    sheet.row("a device /dev has no name for: said, with the device",
              attempt(lambda: proc.tty(4242)),
              (None, "pid 4242's terminal (device 0x1000abc) has no name in /dev"))
    sheet.row("…asked of devname as a character device", lib.named, [(0x1000ABC, 0o020000)])
    lib = FakeLib(tdev=0x1000ABC, devname=b"ttys042")
    proc._libc, proc._proc = lib, lib
    sheet.row("…and the name devname gives is the answer", attempt(lambda: proc.tty(4242)),
              ("ttys042", None))


def title_edges(sheet: Sheet) -> None:
    sheet.head("Process.title — one OSC 2 on a real pty, or a refusal (task 43)")
    restore()
    with Pty() as pty:
        asked: list = []
        proc = on_pty(macos.Process(), pty, asked)
        sheet.row("the tab is named, and says which tty",
                  attempt(lambda: proc.title(4242, TITLE)),
                  (True, f"named {pty.name}'s tab {TITLE!r}"))
        sheet.row("…the pty received exactly ESC ] 2 ; text BEL, in one piece",
                  pty.read(), b"\x1b]2;quarry \xc2\xb7 d711\x07")
        sheet.row("…asked for pid 4242's tty", asked, [4242])
        sheet.row("a no-break space (U+00A0) is text, not a control",
                  (attempt(lambda: proc.title(1, "a b"))[0], pty.read()),
                  (True, b"\x1b]2;a\xc2\xa0b\x07"))

    for label, text in (("ESC, the start of every other command", "x\x1b]0;evil"),
                        ("BEL, which would end the title early", "x\x07y"),
                        ("a newline", "a\nb"),
                        ("DEL (U+007F)", "x\x7fy"),
                        ("CSI as one C1 character (U+009B)", "x\x9by")):
        with Pty() as pty:
            asked = []
            proc = on_pty(macos.Process(), pty, asked)
            sheet.row(f"refused: {label} — and nothing written",
                      (attempt(lambda: proc.title(4242, text)), pty.read(), asked),
                      ((False, f"{text!r} holds a control character, so no tab was named"),
                       b"", []))

    proc = macos.Process()
    proc.tty = lambda pid: (None, None)
    sheet.row("a pid on no terminal: said",
              attempt(lambda: proc.title(4242, TITLE)),
              (False, "pid 4242 is on no terminal, so no tab was named"))
    blind = "libproc is out of reach (x), so pid 4242's terminal is unknown"
    proc.tty = lambda pid: (None, blind)
    sheet.row("a terminal that cannot be read: its own reason passed on",
              attempt(lambda: proc.title(4242, TITLE)), (False, blind))

    sheet.row("(reference) /dev/wobble-no-such-tty really does not exist",
              os.path.exists(f"/dev/{NO_TTY}"), False)
    proc.tty = lambda pid: (NO_TTY, None)
    sheet.row("a tty that will not open: said, with the OS's own reason",
              attempt(lambda: proc.title(4242, TITLE)),
              (False, f"/dev/{NO_TTY} would not open (No such file or directory), so no "
                      f"tab was named"))

    with Pty() as pty:
        sheet.row("(reference) the pty's slave is this user's",
                  os.fstat(pty.slave).st_uid, os.getuid())
        proxy = OsProxy(getuid=lambda: os.getuid() + 1)
        macos.os = proxy
        proc = on_pty(macos.Process(), pty)
        sheet.row("a tty not this user's: refused, and nothing written",
                  (attempt(lambda: proc.title(4242, TITLE)), pty.read()),
                  ((False, f"/dev/{pty.name} is not this user's, so no tab was named"), b""))
        sheet.row("…and the fd it opened was closed", proxy.closed, proxy.opened)
        restore()

    with Pty() as pty:
        data = osc2(TITLE)
        proxy = OsProxy(write=lambda fd, b: os.write(fd, b[:-1]))
        macos.os = proxy
        proc = on_pty(macos.Process(), pty)
        sheet.row("a short write: said, with how much went",
                  attempt(lambda: proc.title(4242, TITLE)),
                  (False, f"/dev/{pty.name} took {len(data) - 1} of {len(data)} bytes, so "
                          f"the tab may be unnamed"))
        sheet.row("…the pty holds the part that went, and no more",
                  (pty.read(), proxy.closed == proxy.opened and len(proxy.opened) == 1),
                  (data[:-1], True))
        restore()

    with Pty() as pty:
        pty.fill()
        proc = on_pty(macos.Process(), pty)
        with deadline(1.0):
            got = attempt(lambda: proc.title(4242, TITLE))
        sheet.row("a terminal that stopped reading: refused at once, never waited on",
                  got, (False, f"/dev/{pty.name} refused the write (Resource temporarily "
                               f"unavailable), so no tab was named"))


def click_edges(sheet: Sheet) -> None:
    sheet.head("the status item — right presses B, left opens the menu (task 21)")
    # These events are built here, so this proves the branch and nothing about
    # AppKit's dispatch; the real right click is DESK-CHECKS.md Part B step 10.
    restore()
    macos.NSApplication = FakeNSApplication
    clicks = macos._Clicks.alloc().init()
    done: list = []
    clicks.press = lambda: done.append("press")
    clicks.open_menu = lambda: done.append("menu")
    for label, event, want in (
            ("a right mouse up presses B", FakeEvent(macos.NSEventTypeRightMouseUp), ["press"]),
            ("a control-click is a right click", FakeEvent(
                macos.NSEventTypeRightMouseUp + 1000, macos.NSEventModifierFlagControl),
             ["press"]),
            ("a plain left click opens the menu", FakeEvent(
                macos.NSEventTypeRightMouseUp + 1000), ["menu"]),
            ("no current event is not a right click", None, ["menu"])):
        done.clear()
        FakeNSApplication.event = event
        attempt(lambda: clicks.clicked_(None))
        sheet.row(label, list(done), want)
    clicks.press = None
    done.clear()
    FakeNSApplication.event = FakeEvent(macos.NSEventTypeRightMouseUp)
    attempt(lambda: clicks.clicked_(None))
    sheet.row("a right click with no B handler opens nothing either", list(done), [])
    FakeNSApplication.event = None
    restore()


# --- the real processes, against ps -------------------------------------------

def ps_tty(pid: int) -> str:
    return REAL_RUN(["ps", "-o", "tty=", "-p", str(pid)],
                    capture_output=True, text=True).stdout.strip()


def real_legs(sheet: Sheet) -> None:
    sheet.head("Process.tty and title on real processes — ps is the second source")
    restore()
    process = macos.Process()
    with Pty() as pty:
        # setsid, then the shell's `<` opens the slave: XNU hands a session leader
        # with no terminal the first tty it opens (measured 2026-09-29 against ps).
        child = REAL_POPEN(["/bin/sh", "-c", f"exec /bin/sleep 30 < /dev/{pty.name}"],
                           start_new_session=True, stdin=subprocess.DEVNULL,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            until = time.monotonic() + 3.0
            while ps_tty(child.pid) != pty.name and time.monotonic() < until:
                time.sleep(0.05)
            sheet.row(f"(reference) ps puts the child on our pty ({pty.name})",
                      ps_tty(child.pid), pty.name)
            sheet.row("the seam agrees with ps", process.tty(child.pid), (pty.name, None))
            sheet.row("title through the real tty(): named",
                      attempt(lambda: process.title(child.pid, "wobble edges")),
                      (True, f"named {pty.name}'s tab 'wobble edges'"))
            sheet.row("…and the pty read back the literal bytes",
                      pty.read(), b"\x1b]2;wobble edges\x07")
        finally:
            child.kill()
            child.wait()

    alone = REAL_POPEN(["/bin/sleep", "30"], start_new_session=True, stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        sheet.row("(reference) ps puts a setsid child on no terminal", ps_tty(alone.pid), "??")
        sheet.row("the seam agrees: NODEV is (None, None)", process.tty(alone.pid), (None, None))
    finally:
        alone.kill()
        alone.wait()
    gone = REAL_POPEN(["/usr/bin/true"])
    gone.wait()
    sheet.row("(reference) ps finds no pid that just exited", ps_tty(gone.pid), "")
    sheet.row("the seam: ESRCH is (None, None), a gone process",
              process.tty(gone.pid), (None, None))


# --- the mutants ----------------------------------------------------------------

MUTANTS = [
    ("title without the control-character refusal", macos.Process, "title",
     "if any(ord(c) < 0x20 or 0x7F <= ord(c) < 0xA0 for c in text):", "if False:"),
    ("title without DEL and the C1 range", macos.Process, "title",
     " or 0x7F <= ord(c) < 0xA0", ""),
    ("title writing to a tty owned by someone else", macos.Process, "title",
     "os.fstat(fd).st_uid != os.getuid()", "False"),
    ("title blocking on a terminal that stopped reading", macos.Process, "title",
     "os.O_WRONLY | os.O_NOCTTY | os.O_NONBLOCK", "os.O_WRONLY | os.O_NOCTTY"),
    ("title trusting a short write", macos.Process, "title",
     "if wrote != len(data):", "if False:"),
    ("tab_tty not recognising -1743", macos.Frontmost, "tab_tty",
     'if "-1743" in out.stderr:', "if False:"),
    ("tab_tty asking an app that is not running", macos.Frontmost, "tab_tty",
     "if home is None:", "if False:"),
    ("tab_tty keeping /dev/", macos.Frontmost, "tab_tty", '.removeprefix("/dev/")', ""),
    ("tab_tty naming the app by its bundle id", macos.Frontmost, "tab_tty",
     "name = str(home.localizedName() or app)", "name = app"),
    ("ask borrowing Focus's 'no window was raised'", macos.Focus, "ask",
     'return False, _CANNOT_ASK.format(why=_AX_MISSING or "it is not available")',
     "return False, _AX_WHY"),
    ("tab not recognising -1743", macos.Focus, "tab",
     'if "-1743" in out.stderr:', "if False:"),
    ("tab treating any exit 0 as found", macos.Focus, "tab",
     'if out.stdout.strip() != "found":', "if False:"),
    ("tab ignoring the locked screen", macos.Focus, "tab", "if self._locked(ax):", "if False:"),
    ("url ignoring the locked screen", macos.Focus, "url", "if self._locked(ax):", "if False:"),
    ("url opening for an app that is not open", macos.Focus, "url",
     "if home is None:", "if False:"),
    ("url trusting Launch Services blindly", macos.Focus, "url",
     "not NSWorkspace.sharedWorkspace().openURL_(address)",
     "not (NSWorkspace.sharedWorkspace().openURL_(address) or True)"),
    ("_landed claiming a window kept behind", macos.Focus, "_landed",
     "if how is None:", "if False:"),
    ("_landed pushing what already arrived", macos.Focus, "_landed",
     '"" if self._arrived(ax, home.processIdentifier(), wait) else self._forward(ax, home)',
     "self._forward(ax, home)"),
    ("_app taking any running app", macos.Focus, "_app",
     "if running.bundleIdentifier() == bundle:", "if True:"),
    ("ask prompting when already trusted", macos.Focus, "ask",
     "if _is_trusted(ax):", "if False:"),
    ("ask never prompting", macos.Focus, "ask",
     "ax.AXIsProcessTrustedWithOptions({ax.kAXTrustedCheckOptionPrompt: True})", "None"),
    ("Sound dropping the volume", macos.Sound, "play",
     'args += ["-v", str(volume)]', "pass"),
    ("Sound raising when afplay cannot start", macos.Sound, "play",
     "except OSError as exc:", "except ZeroDivisionError as exc:"),
    ("started swallowing a sysctl failure", macos.Process, "started",
     "if self._libc.sysctl(mib, 4, buf, ctypes.byref(size), None, 0) != 0:", "if False:"),
    ("tty calling every failure a dead pid", macos.Process, "tty",
     "if errno == _ESRCH:", "if True:"),
    ("tty naming a device /dev does not have", macos.Process, "tty",
     "if not name:", "if False:"),
]


def mutate(cls, method: str, old: str, new: str):
    """`method` recompiled with `old` replaced, in macos's own globals; None if stale."""
    source = textwrap.dedent(inspect.getsource(getattr(cls, method)))
    if source.count(old) != 1:
        return None
    local: dict = {}
    code = compile(source.replace(old, new), macos.__file__, "exec",
                   flags=__future__.annotations.compiler_flag, dont_inherit=True)
    exec(code, macos.__dict__, local)                                # noqa: S102
    return local[method]


def mutants(sheet: Sheet) -> None:
    sheet.head("mutants — each rule removed in turn must make a row wrong")
    for name, cls, method, old, new in MUTANTS:
        original = cls.__dict__[method]
        broken = mutate(cls, method, old, new)
        if broken is None:
            sheet.row(f"mutant: {name}", "stale: its text is not in macos.py once", "caught")
            continue
        setattr(cls, method, broken)
        quiet = Sheet(quiet=True)
        try:
            table(quiet)
        finally:
            setattr(cls, method, original)
            restore()
        verdict = "caught" if quiet.bad else "survived"
        sheet.rows += 1
        sheet.bad += verdict != "caught"
        print(f"    {'mutant: ' + name:<70} {verdict}"
              + ("" if verdict == "caught" else "  <-- the table does not test it"))


# --- main ---------------------------------------------------------------------

def main() -> int:
    print(__doc__.strip().splitlines()[0])
    subprocess.run, subprocess.Popen = _tripwire_run, _tripwire_popen
    sheet = Sheet()
    try:
        sheet.head("the tripwire itself (reference leg: it must catch one)")
        got = attempt(lambda: subprocess.run(["osascript", "-e", "return 1"]))
        sheet.row("a real osascript is refused, and recorded",
                  (got.startswith("raised PermissionError"), ESCAPED),
                  (True, [["osascript", "-e", "return 1"]]))
        ESCAPED.clear()
        sheet.row("(reference) the real ApplicationServices is not loaded at the start",
                  "ApplicationServices" in sys.modules, False)

        table(sheet)
        real_legs(sheet)
        mutants(sheet)

        sheet.head("guards — nothing real was touched")
        sheet.row("no osascript, afplay or open reached the real subprocess", ESCAPED, [])
        sheet.row("the real ApplicationServices was never loaded, so never prompted",
                  "ApplicationServices" in sys.modules, False)
        sheet.row("every seam global is back as it was",
                  all(getattr(macos, k) is v for k, v in SAVED.items()), True)
    finally:
        subprocess.run, subprocess.Popen = REAL_RUN, REAL_POPEN
        restore()

    print(f"\n  {sheet.rows} rows")
    print("\n" + ("ALL CASES MATCH the known answer" if not sheet.bad
                  else f"{sheet.bad} WRONG — the rows above"))
    return 0 if not sheet.bad else 1


if __name__ == "__main__":
    if sys.platform != "darwin":
        print("this one is macOS only, on purpose — it checks the macOS seam")
        sys.exit(0)
    sys.exit(main())
