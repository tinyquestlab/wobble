#!/usr/bin/env python3
"""Known-answer checks for `src/platform_seam` — no AppKit dialog, no sound.

    venv/bin/python3 tests/tables/check_seam.py

Two contracts, each cited from where it is written down:

  (a) **selection** (`src/platform_seam/__init__.py` lines 31-52): which
      implementation gets picked, and what it says out loud when the pick was
      not what was asked for. `WOBBLE_PLATFORM` is read once at import time
      (module docstring, lines 12-14), so each case here is a fresh
      subprocess — there is no in-process way to ask the same package to
      choose twice.

  (b) **the null seam's own contract** (`src/platform_seam/null.py`'s module
      docstring, lines 1-12): "honest, not silent" — every port method returns
      the neutral value, a non-empty reason wherever the return shape has one,
      never raises, and is recorded in `CALLS` — except `pump`, which the
      module's own comment (lines 111-120) says is deliberately not recorded.
      The method list itself comes from introspecting `ports.py`'s
      `Protocol` classes, not from a hand-copied list, so a method ports.py
      gains later and null.py does not is a row that fails rather than a row
      that was never written.

`WOBBLE_PLATFORM=null` is set before this process imports the package at all
(line ~30 below), so part (b) never has to touch the real macOS seam or
PyObjC — it always drives `null.py` directly. Part (a) is the only place a
real subprocess environment is set, and it is set per-case, on purpose.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYTHON = sys.executable              # the one running this table, venv or not (task 78)

# Drives THIS process's own import of platform_seam to null, quietly, so part
# (b) below never has to load AppKit to get at `null.py`.
os.environ["WOBBLE_PLATFORM"] = "null"
sys.path.insert(0, str(ROOT))

from src.platform_seam import null, ports            # noqa: E402


class Sheet:
    def __init__(self, quiet: bool = False):
        self.quiet, self.bad = quiet, 0

    def row(self, what: str, got, want) -> None:
        good = want(got) if callable(want) else got == want
        self.bad += not good
        if not self.quiet:
            print(f"    {what:<64} "
                  f"{'ok' if good else f'<-- WRONG: {got!r}'}")

    def ok(self) -> bool:
        return not self.bad


def run_subprocess(env_extra: dict, script: str) -> subprocess.CompletedProcess:
    env = {**os.environ, **env_extra}
    return subprocess.run([PYTHON, "-c", script], cwd=str(ROOT), env=env,
                          capture_output=True, text=True, timeout=20)


# A script run in a fresh interpreter: import the package plainly and print
# what it picked. `sys.path` is set inline because the subprocess starts with
# none of this file's state.
PLAIN_IMPORT = (
    f"import sys; sys.path.insert(0, {str(ROOT)!r})\n"
    "from src import platform_seam\n"
    "print(platform_seam.PLATFORM)\n"
    "print(platform_seam.UNAVAILABLE)\n"
)

# A script that blocks `AppKit` before importing the package, with a
# `sys.meta_path` finder that raises `ModuleNotFoundError(name='AppKit')` —
# simulating "not installed" without touching the real venv, where AppKit
# actually does import fine (PyObjC is a dependency of bleak's CoreBluetooth
# backend, per requirements.txt).
BLOCKED_APPKIT_IMPORT = (
    "import sys, importlib.abc\n"
    "class BlockAppKit(importlib.abc.MetaPathFinder):\n"
    "    def find_spec(self, name, path, target=None):\n"
    "        if name == 'AppKit':\n"
    "            raise ModuleNotFoundError('blocked for check', name='AppKit')\n"
    "        return None\n"
    "sys.meta_path.insert(0, BlockAppKit())\n"
    f"sys.path.insert(0, {str(ROOT)!r})\n"
    "from src import platform_seam\n"
    "print(platform_seam.PLATFORM)\n"
    "print(platform_seam.UNAVAILABLE)\n"
)

# The same selection logic as `__init__.py` lines 31-52, transcribed rather
# than imported — used only by the "fallback printing nothing" mutant below,
# which needs a version of this logic with the stderr line removed. Importing
# the real module and monkeypatching its `print` would not touch this file
# alone, and mutating `src/platform_seam/__init__.py` itself is out of scope.
#
# It resolves the wanted seam file BY PATH, with `importlib.util`, rather than
# `importlib.import_module('.{_WANTED}', 'src.platform_seam')` the way
# `__init__.py` itself does — a first draft used that spelling and the mutant
# was never distinguishable from the real thing, because resolving a name
# relative to a package makes Python import the package first, which runs the
# very `__init__.py` this mutant exists to go without, stderr print included.
# Confirmed live: that draft reported "caught" for the wrong reason — the
# stderr the check saw was the real package's, not this script's.
SELECTION_NO_PRINT = (
    "import importlib.util, os, sys\n"
    f"_SEAM_DIR = {str(ROOT / 'src' / 'platform_seam')!r}\n"
    "_WANTED = os.environ.get('WOBBLE_PLATFORM') or 'null'\n"
    "_impl, _REASON = None, None\n"
    "if _WANTED != 'null':\n"
    "    _path = os.path.join(_SEAM_DIR, f'{_WANTED}.py')\n"
    "    if not os.path.exists(_path):\n"
    "        _REASON = f'there is no {_WANTED} seam file yet — running with no platform'\n"
    "    else:\n"
    "        try:\n"
    "            _spec = importlib.util.spec_from_file_location(_WANTED, _path)\n"
    "            _impl = importlib.util.module_from_spec(_spec)\n"
    "            _spec.loader.exec_module(_impl)\n"
    "        except ModuleNotFoundError as exc:\n"
    "            _REASON = f'the {_WANTED} seam needs {exc.name}, which is not installed — running with no platform'\n"
    "if _impl is None:\n"
    "    _null_path = os.path.join(_SEAM_DIR, 'null.py')\n"
    "    _spec = importlib.util.spec_from_file_location('null', _null_path)\n"
    "    _impl = importlib.util.module_from_spec(_spec)\n"
    "    _spec.loader.exec_module(_impl)\n"
    "    # the real __init__.py prints _REASON to stderr here — this mutant does not\n"
    "print(_impl.__name__)\n"
)


def selection_rows(sheet: Sheet) -> None:
    say = print
    say("\n  selection (src/platform_seam/__init__.py lines 31-52), each its own subprocess")

    r = run_subprocess({"WOBBLE_PLATFORM": "nosuch"}, PLAIN_IMPORT)
    stdout_lines = r.stdout.splitlines()
    sheet.row("WOBBLE_PLATFORM=nosuch falls back to null",
              stdout_lines[0] if stdout_lines else None, "null")
    sheet.row("…and says so on stderr: no such seam FILE",
              "there is no nosuch seam file yet" in r.stderr, True)

    r = run_subprocess({"WOBBLE_PLATFORM": "null"}, PLAIN_IMPORT)
    stdout_lines = r.stdout.splitlines()
    sheet.row("WOBBLE_PLATFORM=null chooses null directly",
              stdout_lines[0] if stdout_lines else None, "null")
    sheet.row("…quietly: nothing at all on stderr",
              r.stderr, "")
    sheet.row("…and UNAVAILABLE is None, not a manufactured reason",
              stdout_lines[1] if len(stdout_lines) > 1 else None, "None")

    r = run_subprocess({"WOBBLE_PLATFORM": "macos"}, BLOCKED_APPKIT_IMPORT)
    stdout_lines = r.stdout.splitlines()
    sheet.row("WOBBLE_PLATFORM=macos with AppKit blocked falls back to null",
              stdout_lines[0] if stdout_lines else None, "null")
    sheet.row("…and says so on stderr: needs AppKit, an IMPORT missing, not a FILE",
              "needs AppKit, which is not installed" in r.stderr, True)
    sheet.row("…and does NOT say 'no such seam file' — that would be the wrong reason",
              "there is no macos seam file" in r.stderr, False)


# =====================================================================
# (b) the null seam's contract, enumerated from ports.py by introspection
# =====================================================================

def protocol_methods(cls) -> list[str]:
    """Every method a `Protocol` class declares, by name — no hand-copied
    list, so a method ports.py gains later shows up here on its own."""
    return sorted(n for n in vars(cls)
                  if not n.startswith("_") and callable(getattr(cls, n)))


# port name -> (Protocol class, null implementation class)
PORTS = {
    "Sound": (ports.Sound, null.Sound),
    "Frontmost": (ports.Frontmost, null.Frontmost),
    "Focus": (ports.Focus, null.Focus),
    "Process": (ports.Process, null.Process),
    "Status": (ports.Status, null.Status),
    "Idle": (ports.Idle, null.Idle),
    "Login": (ports.Login, null.Login),
    "Permissions": (ports.Permissions, null.Permissions),
}

# How to call each method, and what "honest, not silent" means for its return:
#   args, kwargs, want_return (a literal, or a predicate for the reason slot),
#   want_calls (the exact CALLS entry expected, or None for "not recorded").
CONTRACT = {
    ("Sound", "play"): dict(
        args=("chime.wav",), kwargs={},
        want=(False, "no platform: no sound was played"),
        want_call=("Sound.play", ("chime.wav", None))),
    ("Sound", "stop"): dict(
        args=(), kwargs={}, want=None,
        want_call=("Sound.stop", ())),

    ("Frontmost", "app"): dict(
        args=(), kwargs={}, want=None,
        want_call=("Frontmost.app", ())),
    ("Frontmost", "title"): dict(
        args=(), kwargs={},
        want=(None, "no platform: there is no way to see which window is in "
                     "front, so signals are played whether or not you are "
                     "already looking at the session that raised them"),
        want_call=("Frontmost.title", ())),
    ("Frontmost", "window"): dict(
        args=(), kwargs={},
        want=(None, None, "no platform: there is no way to see which window is "
                          "in front, so signals are played whether or not you "
                          "are already looking at the session that raised them"),
        # Its own entry (null.py, Frontmost.window): before 2026-09-30 it
        # borrowed title()'s, against the module docstring's promise.
        want_call=("Frontmost.window", ())),
    ("Frontmost", "tab_tty"): dict(
        args=("com.example.terminal",), kwargs={},
        want=(None, "no platform: no terminal can be asked which tab is in front"),
        want_call=("Frontmost.tab_tty", ("com.example.terminal",))),

    ("Focus", "window"): dict(
        args=("wobble",), kwargs={},
        want=(False, "no platform: no window was raised"),
        want_call=("Focus.window", ("wobble", 1.5))),
    ("Focus", "url"): dict(
        args=("https://example.invalid",), kwargs={"app": "com.example"},
        want=(False, "no platform: no address was opened"),
        want_call=("Focus.url", ("https://example.invalid", "com.example"))),
    ("Focus", "tab"): dict(
        args=("ttys003",), kwargs={"app": "com.example"},
        want=(False, "no platform: no tab was selected"),
        want_call=("Focus.tab", ("ttys003", "com.example"))),
    ("Focus", "ask"): dict(
        args=(), kwargs={},
        want=(False, "no platform: there is no permission to ask for"),
        want_call=("Focus.ask", ())),

    ("Process", "started"): dict(
        args=(123,), kwargs={},
        want=(None, "no platform: there is no way to ask whether a process still runs"),
        want_call=("Process.started", (123,))),
    ("Process", "tty"): dict(
        args=(123,), kwargs={},
        want=(None, "no platform: there is no way to ask which terminal a process is on"),
        want_call=("Process.tty", (123,))),
    ("Process", "title"): dict(
        args=(123, "a tab"), kwargs={},
        want=(False, "no platform: there is no terminal to name a tab on"),
        want_call=("Process.title", (123, "a tab"))),
    ("Process", "children"): dict(
        args=(123,), kwargs={},
        want=(None, "no platform: there is no way to ask what a process started"),
        want_call=("Process.children", (123,))),
    ("Process", "command"): dict(
        args=(123,), kwargs={},
        want=(None, "no platform: there is no way to read a process's command line"),
        want_call=("Process.command", (123,))),

    ("Status", "show"): dict(
        args=("wobble: waiting",), kwargs={}, want=None,
        want_call=("Status.show", ("wobble: waiting",))),
    ("Status", "icon"): dict(
        args=(ports.BallIcon(True, "#FFE14D", None),), kwargs={},
        want=(False, "no platform: there is no menu bar to draw a ball in"),
        want_call=("Status.icon", (ports.BallIcon(True, "#FFE14D", None),))),
    ("Status", "on_click"): dict(
        args=(lambda: None,), kwargs={}, want=None,
        want_call="on_click",  # special-cased below: handler identity
    ),
    ("Status", "menu"): dict(
        args=([("Open", None), (None, None),
               (ports.Submenu("Settings"), [(ports.Checked("On"), None)])],),
        kwargs={}, want=None,
        # A submenu as `[label, [its labels]]` (spec 03, task 02).
        want_call=("Status.menu", (["Open", None, ["Settings", ["On"]]],))),
    ("Idle", "seconds"): dict(
        args=(), kwargs={},
        want=(None, "no platform: there is no way to ask when a key or the mouse last moved"),
        want_call=("Idle.seconds", ())),
    ("Login", "state"): dict(
        args=(), kwargs={},
        want=(None, "no platform: there is no way to open wobble at login"),
        want_call=("Login.state", ())),
    ("Login", "set"): dict(
        args=(True,), kwargs={},
        want=(False, "no platform: nothing was set to open at login"),
        want_call=("Login.set", (True,))),
    ("Login", "settings"): dict(
        args=(), kwargs={},
        want=(False, "no platform: there is no list of what opens at login to show"),
        want_call=("Login.settings", ())),
    ("Permissions", "kinds"): dict(
        args=(), kwargs={}, want=(),
        want_call=("Permissions.kinds", ())),
    ("Permissions", "state"): dict(
        args=("accessibility",), kwargs={},
        want=(None, "no platform: there is no permission to read"),
        want_call=("Permissions.state", ("accessibility",))),
    ("Permissions", "settings"): dict(
        args=("accessibility",), kwargs={},
        want=(False, "no platform: there is no System Settings to open"),
        want_call=("Permissions.settings", ("accessibility",))),
    ("Status", "pump"): dict(
        args=(), kwargs={}, want=None,
        want_call=None),  # deliberately NOT recorded (null.py lines 111-120)
}


def check_contract(sheet: Sheet, port_name: str, method_name: str,
                    impl_cls, spec: dict | None) -> None:
    instance = impl_cls()
    null.CALLS.clear()
    label = f"{port_name}.{method_name}"

    if spec is None:
        # A method ports.py declares that this table has no entry for — the
        # row that must fail when a method is added later with nothing here
        # to test it, per the task's own requirement.
        sheet.row(f"{label}: no dummy args registered for it — add one", "missing", "registered")
        return

    method = getattr(instance, method_name)
    try:
        got = method(*spec["args"], **spec["kwargs"])
    except Exception as exc:  # the one thing the contract forbids outright
        sheet.row(f"{label}: never raises", f"raised {type(exc).__name__}", "no exception")
        return

    sheet.row(f"{label}: returns the neutral value + reason, honestly",
              got, spec["want"])

    want_call = spec["want_call"]
    if want_call is None:
        sheet.row(f"{label}: pump is the one call deliberately not recorded",
                  null.CALLS, [])
    elif want_call == "on_click":
        sheet.row(f"{label}: the handler itself is recorded, not called",
                  null.CALLS, [("Status.on_click", (spec["args"][0],))])
    else:
        sheet.row(f"{label}: recorded in CALLS as (port.method, args)",
                  null.CALLS, [want_call])


def null_contract_rows(sheet: Sheet) -> None:
    print("\n  the null seam's contract (null.py's own docstring, lines 1-12)")
    for port_name, (proto_cls, impl_cls) in PORTS.items():
        for method_name in protocol_methods(proto_cls):
            check_contract(sheet, port_name, method_name, impl_cls,
                          CONTRACT.get((port_name, method_name)))


# =====================================================================
# mutants
# =====================================================================

def mutant_rows() -> list[tuple[str, bool]]:
    results = []

    # 1. a null method returning (None, None) — no neutral value that means
    #    anything, and no reason at all.
    class BrokenFocus:
        def window(self, hint, *, app=None, fits=None, folder=None, timeout=1.5):
            return None, None

    real = null.Focus().window("wobble")
    broken = BrokenFocus().window("wobble")
    results.append(("a null method returning (None, None)", real == broken))

    # 2. a Protocol that grows a method with no null counterpart — the
    #    enumeration in `null_contract_rows` above must not silently skip it.
    from typing import Protocol, runtime_checkable

    @runtime_checkable
    class SoundPlusVolume(Protocol):
        def play(self, path: str, volume: float | None = None) -> tuple[bool, str | None]: ...
        def stop(self) -> None: ...
        def volume(self) -> float: ...  # null.Sound has no such method

    methods = protocol_methods(SoundPlusVolume)
    has_null_counterpart = all(hasattr(null.Sound, m) for m in methods)
    results.append(("a Protocol method added with no null counterpart",
                    has_null_counterpart))  # True would mean the gap went unnoticed

    # 3. the fallback that picks null but prints nothing about why.
    r_real = run_subprocess({"WOBBLE_PLATFORM": "nosuch"}, PLAIN_IMPORT)
    r_mutant = run_subprocess({"WOBBLE_PLATFORM": "nosuch"}, SELECTION_NO_PRINT)
    real_said_something = "there is no nosuch seam file yet" in r_real.stderr
    mutant_said_something = "there is no nosuch seam file yet" in r_mutant.stderr
    results.append(("the fallback printing nothing about why",
                    real_said_something == mutant_said_something))

    return results


def main() -> int:
    print(__doc__.strip().splitlines()[0])
    sheet = Sheet()
    selection_rows(sheet)
    null_contract_rows(sheet)
    ok = sheet.ok()

    print("\n  the control — each rule removed in turn")
    for name, survived in mutant_rows():
        ok &= not survived
        print(f"    mutant: {name:<52} "
              f"{'<-- SURVIVED' if survived else 'caught'}")

    print("\n" + ("ALL CASES MATCH the known answer" if ok else
                  "SOMETHING DOES NOT MATCH — the rows above, not this line"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
