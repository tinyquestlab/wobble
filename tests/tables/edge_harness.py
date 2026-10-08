#!/usr/bin/env python3
"""The real daemon, with everything outside it read from files a check writes.

    WOBBLE_EDGE=<dir> venv/bin/python3 tests/tables/edge_harness.py <daemon args>

For `tests/tables/check_daemon_edges.py`. Starts from the null seam
(`WOBBLE_PLATFORM=null`, so nothing reaches the screen or the speakers) and
replaces only what a scenario has to steer, each read afresh on every call so
the check can move the world while the daemon runs:

    reg/*.json   Claude Code's registry, in its own file format (hooks.registry)
    proc.json    {"<pid>": {"started": s|null, "tty": t|null, "kids": [pid…],
                 "argv": [arg…]}} or {"blind": why}; "blind_kids": why makes
                 only `children` blind (task 65)
    front        "<title>\\t<bundle id>\\t<could-not-tell sentence>"
    tabtty       Terminal's tab in front: a tty, or "!raise" for a seam fault
    wire         "ok" or anything else: what `wiring()` answers
    aim          a session id: a pending-list line clicked on the next pump
    silence      a session id: its ⌥ "Silence <project>" row clicked (task 68)
    moves        seconds: Focus.window puts its window in `front` and takes
                 that long, a VS Code link records where it landed, and each
                 call prints FAKEFOCUS with how many are in flight (task 66)
    steal        written into `front` as a raise's window step ends: a click
    steal_after  the same, as a VS Code link's step ends
    titled       appended by process.title: "<pid>\\t<text>" per call
    ball         present: a fake ball mirror; its text is "letgo" or "stuck"
    perms        {"<kind>": [state, why]}: what Permissions reads, in that order;
                 none is no permission at all, as on the null seam (spec 03)
    permission   a kind: its menu line clicked; the pane is printed FAKEPANE
    choose       a partner: its `Settings › Voice` line clicked, greyed or not (spec 04)
    cries/       present: where each partner's cry is looked for, in place of
                 assets/cries/, so a cry fetched or not is the check's (spec 04)

Every title the menu bar is handed is printed FAKETITLE, once per change, and
what `Settings › Voice` is handed FAKEVOICES, `[in use, {partner: why not}]` in JSON.

Nothing here ever touches Claude Code's folder: the registry and the
transcripts are both replaced. `WOBBLE_MUTANT` names one rule to break, and `WOBBLE_PATCH`
(`[old, new]`, JSON) replaces one line of the daemon's own source.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
import time
from pathlib import Path

os.environ["WOBBLE_PLATFORM"] = "null"
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src import hooks, platform_seam          # noqa: E402

BOX = Path(os.environ["WOBBLE_EDGE"])
MUTANT = os.environ.get("WOBBLE_MUTANT", "")


def _read(name: str, default: str = "") -> str:
    try:
        return (BOX / name).read_text()
    except OSError:
        return default


class Process:
    def _proc(self) -> dict:
        try:
            return json.loads(_read("proc.json", "{}"))
        except ValueError:
            return {}

    def started(self, pid):
        proc = self._proc()
        if "blind" in proc:
            return None, proc["blind"]
        return proc.get(str(pid), {}).get("started"), None

    def tty(self, pid):
        return self._proc().get(str(pid), {}).get("tty"), None

    def children(self, pid):
        proc = self._proc()
        if "blind_kids" in proc:
            return None, proc["blind_kids"]
        return tuple(proc.get(str(pid), {}).get("kids", [])), None

    def command(self, pid):
        argv = self._proc().get(str(pid), {}).get("argv")
        return (tuple(argv) if argv is not None else None), None

    def title(self, pid, text):
        with (BOX / "titled").open("a") as handle:
            handle.write(f"{pid}\t{text}\n")
        return True, f"named on pid {pid}'s terminal (scripted)"


class Front:
    def _parts(self):
        parts = (_read("front").rstrip("\n").split("\t") + ["", "", ""])[:3]
        return tuple(part or None for part in parts)

    def title(self):
        title, _, blind = self._parts()
        return title, blind

    def window(self):
        return self._parts()

    def tab_tty(self, app, *, timeout=2.0):
        got = _read("tabtty").strip()
        if got == "!raise":
            raise RuntimeError("scripted seam fault")
        return got or None, None


_flying = [0]
_flying_lock = threading.Lock()


def _fly(by: int) -> int:
    with _flying_lock:
        _flying[0] += by
        return _flying[0]


def _front_set(text: str) -> None:
    tmp = BOX / ".front.harness"
    tmp.write_text(text)
    tmp.replace(BOX / "front")


class Focus:
    def window(self, hint, *, app=None, fits=None, folder=None, timeout=1.5):
        hold = _read("moves").strip()
        if hold:
            print(f"FAKEFOCUS window {hint} ({_fly(1)} in flight)", flush=True)
            _front_set(f"Claude Code — {hint}\t{app or ''}\t")
            time.sleep(float(hold))
            if _read("steal"):
                _front_set(_read("steal"))
            _fly(-1)
        return True, f"scripted: window {hint!r} came forward"

    def url(self, url, *, app, timeout=1.5):
        hold = _read("moves").strip()
        if hold and url.startswith("vscode:"):
            n = _fly(1)
            into = Front().title()[0]
            print(f"FAKEFOCUS pick {url.rsplit('=', 1)[-1][:4]} into {into!r} "
                  f"({n} in flight)", flush=True)
            time.sleep(float(hold) / 3)
            if _read("steal_after"):
                _front_set(_read("steal_after"))
            _fly(-1)
        return True, f"scripted: {url} opened"

    def tab(self, tty, *, app, timeout=30.0):
        return True, f"scripted: tab on {tty} picked"

    def ask(self):
        return True, None


class Idle:
    """`BOX/idle`: seconds since the last input, or `blind`; none is 0 (task 64)."""
    def seconds(self):
        got = _read("idle", "0").strip()
        if got == "blind":
            return None, "scripted: the idle time is out of reach"
        return float(got or 0), None


class Permissions:
    """`BOX/perms`, read afresh on every call (spec 03)."""

    def _perms(self) -> dict:
        try:
            return json.loads(_read("perms", "{}"))
        except ValueError:
            return {}

    def kinds(self):
        return tuple(self._perms())

    def state(self, kind):
        state, why = self._perms().get(kind, [None, f"there is no permission called {kind!r}"])
        return state, why

    def settings(self, kind):
        print(f"FAKEPANE {kind}", flush=True)
        return True, f"scripted: {kind}'s pane opened"


_titles = [None]
_show = platform_seam.status.show


def _show_said(text):
    if text != _titles[0]:
        _titles[0] = text
        print(f"FAKETITLE {text}", flush=True)
    return _show(text)


platform_seam.process = Process()
platform_seam.permissions = Permissions()
platform_seam.status.show = _show_said
platform_seam.frontmost = Front()
platform_seam.focus = Focus()
platform_seam.idle = Idle()

if os.environ.get("WOBBLE_PATCH"):
    # A mutant of the loop itself: one line of src/daemon.py replaced, compiled
    # under the module's own name, so the relative imports resolve as usual.
    import importlib.util
    _old, _new = json.loads(os.environ["WOBBLE_PATCH"])
    _path = (Path(__file__).resolve().parents[2] / "src/daemon.py")
    _text = _path.read_text()
    if _text.count(_old) != 1:
        sys.exit(f"edge_harness: the mutant's line is in src/daemon.py "
                 f"{_text.count(_old)} times, not once: {_old!r}")
    _spec = importlib.util.spec_from_file_location("src.daemon", _path)
    daemon = importlib.util.module_from_spec(_spec)
    sys.modules["src.daemon"] = daemon
    exec(compile(_text.replace(_old, _new), str(_path), "exec"), daemon.__dict__)
else:
    from src import daemon                     # noqa: E402

daemon.running = lambda session: hooks.running(session, folder=BOX / "reg")
daemon.registry = lambda: hooks.registry(BOX / "reg")
daemon.wiring = lambda: ((True, "wired (scripted)") if _read("wire", "ok").strip() == "ok"
                         else (False, "NOT wired (scripted)"))


class Titles:
    """No transcript is read: a VS Code session's only title is scripted."""

    def of(self, session):
        return frozenset({f"transcript title {session[:4]}"})


daemon.Titles = Titles
daemon.WIRING_EVERY_S = 0.3
daemon.ALIVE_EVERY_S = 0.3
daemon.APPROVED_EVERY_S = 0.2
daemon.TABS_EVERY_S = 0.2
daemon.QUIT_GRACE_S = 0.6
daemon.PERMISSIONS_EVERY_S = 0.2
# Spec 04, task 04: a long read, so a click taken at once is told from one the next read took.
daemon.VOICE_EVERY_S = float(os.environ.get("WOBBLE_VOICE_EVERY_S", "0.2"))

if os.environ.get("WOBBLE_CONFIG"):
    from src.core import ladder
    daemon.load_ladder = lambda **kw: ladder.load(os.environ["WOBBLE_CONFIG"], **kw)

if (BOX / "cries").is_dir():
    daemon.cry_of = lambda voice: BOX / "cries" / f"{voice}.wav"

# A pending-list line, clicked where a real click lands: inside `pump`.
_attend = []
_silence = []
_permission = []
_voice = []
_voices_shown = []
_items = daemon.menubar_items


def _capture(*args, **kwargs):
    _attend[:] = [kwargs["on_attend"]]
    _silence[:] = [kwargs["on_silence"]] if kwargs.get("on_silence") else []
    _permission[:] = [kwargs["on_permission"]] if kwargs.get("on_permission") else []
    _voice[:] = [kwargs["on_voice"]] if kwargs.get("on_voice") else []
    shown = [kwargs.get("voice"), kwargs.get("voices")]
    if _voices_shown != [shown]:
        _voices_shown[:] = [shown]
        print(f"FAKEVOICES {json.dumps(shown)}", flush=True)
    return _items(*args, **kwargs)


def _pump():
    for name, handler in (("aim", _attend), ("silence", _silence),
                          ("permission", _permission), ("choose", _voice)):
        box = BOX / name
        if box.exists() and handler:
            session = box.read_text().strip()
            box.unlink()
            handler[0](session)


daemon.menubar_items = _capture
platform_seam.status.pump = _pump


class Ball:
    """The ball mirror's surface as the daemon uses it, and nothing else."""

    def __init__(self, cry, *, on_press, say, on_hold=None):
        self.connected = False
        self.wanted = True
        self.battery = 70

    async def run(self):
        self.connected = True
        print("FAKEBALL connected", flush=True)
        while True:
            await asyncio.sleep(0.05)
            if not self.wanted and _read("ball").strip() == "letgo":
                self.connected = False

    def beat(self, voice):
        print(f"FAKEBALL beat {voice.effect}", flush=True)

    def refresh(self, showing):
        pass

    def quiet(self):
        pass

    def set_wanted(self, on):
        self.wanted = on

    def revoice(self, cry):
        print(f"FAKEBALL voice {Path(cry).name}", flush=True)


if (BOX / "ball").exists():
    daemon.Ball = Ball

if MUTANT == "no-recall-tabs":
    _recall = daemon.recall
    daemon.recall = lambda *a, **k: (_recall(*a, **k), {})[1]

if os.environ.get("WOBBLE_FLOCK") == "oserror":
    import errno
    import fcntl
    import types

    def _no_lock(handle, how):
        raise OSError(errno.ENOLCK, "No locks available (scripted)")

    daemon.fcntl = types.SimpleNamespace(flock=_no_lock, LOCK_EX=fcntl.LOCK_EX,
                                         LOCK_NB=fcntl.LOCK_NB)

if os.environ.get("WOBBLE_KBI"):
    async def _interrupted(args):
        raise KeyboardInterrupt
    daemon.run = _interrupted

sys.exit(daemon.main(sys.argv[1:]))
