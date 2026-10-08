#!/usr/bin/env python3
"""The daemon's own edges, each in a sandbox daemon with the world scripted.

    venv/bin/python3 tests/tables/check_daemon_edges.py
    venv/bin/python3 tests/tables/check_daemon_edges.py --part mutants:2/4   # one slice

The branches no other check reaches (coverage, 2026-09-29): a restart that
brings back a Warp tab and drops the dead, a Warp tab named and then watched, a
VS Code tab and a Terminal tty told apart from their twins, a claude resumed
under a new pid or gone without its SessionEnd, the lock in all three of its
failures, the ball let go on quit or not, and the lines said only on an edge
(injected turn, CANNOT SEE FOCUS / PROCESSES / TAB, events file restarted,
HOOKS changing, NO SOUND, CONFIG, B aimed at nothing), and task 56's catch:
caught on an answer, broken out on a walk-away; task 57's cries, said in
the banner and heard in a done's beat, with `--one-cry` and another `--cry`; and
task 64's moods — a long turn proud, an API error sad, a window in front nobody
touches soft, lonely after the beats, a greet on B and on coming back — with the
idle time scripted (`BOX/idle`), never read off this desk; and task 65's
approved Bash, a question answered when its command starts, with the claude's
children scripted (`proc.json`); and task 66's B mashed between two VS Code
sessions, one raise at a time and no link into another window, with the front
window moved under the raise (`moves`, `steal`); and task 67's glance, a window
passed through that is not looked at and one already in front that is; and
task 68's silence, by B held (a stdin line `hold`) and by the menu's ⌥ row
(`BOX/silence`), ended by a prompt or an answer and by nothing else; and task
86's life of a signal, its wait and its beats said on the line that ends it, and
task 87's left and back at the keys, and task 88's re-queue said and each beat
numbered, and task 89's row per ended signal in the sandbox's `logs/signals.tsv`;
and spec 03's permissions, each said once per change, a `⚠` in the title while
one is refused, Terminal closed leaving its refusal standing, and a line's click
opening its pane, with what is granted scripted (`BOX/perms`); and spec 04's
voice, read from `var/voice` at startup and again while running, a name refused
by the allowlist, and the cries fetched or not scripted (`BOX/cries`).

Every daemon is the real `src.daemon` run by `tests/tables/edge_harness.py`, on a
sandbox events file written by the real `tools/hook_event.sh`
(`tests/tables/sandbox.py`). The null seam is underneath, so nothing reaches the
screen or the speakers; the registry is fixture files in Claude Code's own
format, never `~/.claude`. Each rule then has a mutant — one line of
`src/daemon.py` replaced — that must turn a row wrong.
"""
from __future__ import annotations

import fcntl
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tables"))
from sandbox import Sandbox                                           # noqa: E402

PY = sys.executable                  # the one running this table, venv or not (task 79)
HARNESS = str(ROOT / "tests" / "tables" / "edge_harness.py")
WARP = "dev.warp.Warp-Stable"                     # src/core/signals.py
TERMINAL = "com.apple.Terminal"
VSCODE = "com.microsoft.VSCode"
FOCUS = "warp://session/" + "0123456789abcdef" * 2   # 32 hex, hooks.WARP_URL
OTHER = "Some other window\tcom.other.App\t"
# `say`'s columns: stamp, two spaces, project 22 wide, label 22 wide, detail.
LINE = re.compile(r"^\d\d:\d\d:\d\d  (.{22})(.{22})(.*)$")


class Sheet:
    def __init__(self, quiet: bool = False) -> None:
        self.bad = 0
        self.quiet = quiet

    def row(self, what: str, got, want) -> None:
        good = got == want
        self.bad += not good
        if not self.quiet:
            print(f"    {what:<66} {'ok' if good else f'<-- WRONG: {got!r}, wanted {want!r}'}")


class Daemon:
    """One harness daemon on a sandbox, its lines collected as they come."""

    def __init__(self, box: Sandbox, *args: str, env: dict | None = None,
                 patch: tuple[str, str] | None = None) -> None:
        self.box = box
        self.edge = box.dir / "edge"
        self.lines: list[str] = []
        extra = dict(env or {})
        if patch is not None:
            extra["WOBBLE_PATCH"] = json.dumps(list(patch))
        self.proc = subprocess.Popen(
            [PY, HARNESS, "--events", str(box.events), "--poll", "0.05",
             "--snooze", "600", *args],
            cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, bufsize=1,
            env={**os.environ, "PYTHONUNBUFFERED": "1", "WOBBLE_EDGE": str(self.edge),
                 **extra})
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        for line in self.proc.stdout:
            self.lines.append(line.rstrip("\n"))

    def said(self, label: str, has: str = "", project: str = "") -> list[str]:
        """Every detail said under `label` that holds `has`."""
        found = []
        for line in list(self.lines):
            m = LINE.match(line)
            if (m and m.group(2).strip() == label and has in m.group(3)
                    and (not project or m.group(1).strip() == project)):
                found.append(m.group(3))
        return found

    def wait(self, label: str, has: str = "", timeout: float = 8.0, n: int = 1,
             project: str = "") -> bool:
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if len(self.said(label, has, project)) >= n:
                return True
            if self.proc.poll() is not None:
                time.sleep(0.2)
                return len(self.said(label, has, project)) >= n
            time.sleep(0.05)
        return False

    def press(self) -> None:
        self.proc.stdin.write("\n")
        self.proc.stdin.flush()

    def hold(self) -> None:
        """B held on the ball, as `keys` reads it (task 68)."""
        self.proc.stdin.write("hold\n")
        self.proc.stdin.flush()

    def stop(self) -> int | str:
        if self.proc.poll() is None:
            self.proc.send_signal(signal.SIGTERM)
        try:
            return self.proc.wait(8)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            return "still running 8 s after SIGTERM"


class World:
    """The files `edge_harness.py` reads the world from."""

    def __init__(self, box: Sandbox) -> None:
        self.box = box
        self.edge = box.dir / "edge"
        (self.edge / "reg").mkdir(parents=True)
        self.set("front", OTHER)
        self.set("wire", "ok")

    def set(self, name: str, text: str) -> None:
        tmp = self.edge / f".{name}.tmp"
        tmp.write_text(text)
        tmp.replace(self.edge / name)

    def proc(self, table: dict) -> None:
        self.set("proc.json", json.dumps(table))

    def register(self, session: str, pid: int, entrypoint: str = "cli",
                 name: str = "") -> None:
        """One registry file, as Claude Code writes them: `<pid>.json` (task 40)."""
        data = {"pid": pid, "sessionId": session, "entrypoint": entrypoint}
        if name:
            data["name"] = name
        (self.edge / "reg" / f"{pid}.json").write_text(json.dumps(data))

    def unregister(self, pid: int) -> None:
        (self.edge / "reg" / f"{pid}.json").unlink()

    def fire(self, what: str, session: str, project: str, *, host: str = "",
             focus: str = "", prompt: str | None = None,
             extra: dict | None = None) -> None:
        """A hook call through the real script, its environment chosen here.

        Not `Sandbox.fire`: that inherits this process's environment, and a
        check run from a Warp tab would hand every line that tab's
        WARP_FOCUS_URL (tools/hook_event.sh's fourth field).
        """
        payload = {"session_id": session, "cwd": f"/Users/x/{project}",
                   "hook_event_name": "t"}
        if prompt is not None:
            payload["prompt"] = prompt
        payload.update(extra or {})
        env = {"PATH": "/usr/bin:/bin", "__CFBundleIdentifier": host,
               "WARP_FOCUS_URL": focus}
        # Compact, as Claude Code writes it: `answered` is read with a sed that
        # wants `{"session_id":"` at the very start (tools/hook_event.sh).
        subprocess.run([str(self.box.hook), what],
                       input=json.dumps(payload, separators=(",", ":")),
                       text=True, check=True, env=env)


# --- the scenarios: each returns its rows, each row (what, got, want) ---------

def restore(patch=None, mutant=""):
    """Task 47: a restart restores the living, drops the dead, keeps Warp's tab."""
    box = Sandbox()
    world = World(box)
    world.register("aaaa1111", 3001)
    world.register("cccc3333", 3003)
    world.proc({"3001": {"started": 1000.0}, "3003": {"started": None}})
    world.fire("needs", "aaaa1111", "warpy", host=WARP, focus=FOCUS)
    world.fire("done", "bbbb2222", "gone-repo")        # not in the registry
    world.fire("done", "cccc3333", "dead-repo")        # in it, its pid not running
    d = Daemon(box, "--no-ball", patch=patch,
               env={"WOBBLE_MUTANT": mutant} if mutant else None)
    d.wait("restart")
    d.press()
    d.wait("focused")
    rc = d.stop()
    return [
        ("restart: the living one is restored", len(d.said("restored", project="warpy")), 1),
        ("restart: 1 back, 2 dropped (one unregistered, one dead)",
         [("1 back" in s, "2 dropped: their claude is not running" in s)
          for s in d.said("restart")], [(True, True)]),
        ("restart: B on it opens the Warp tab its old line carried",
         [FOCUS in s for s in d.said("focused")], [True]),
        ("restart: quits clean", rc, 0),
    ]


def live(patch=None):
    """Warp and VS Code tabs, injected turns, and the lines said on an edge."""
    box = Sandbox()
    world = World(box)
    world.register("dddd4444", 4001)
    world.register("vvvv5555", 4005, entrypoint="claude-vscode", name="vs name")
    world.proc({"4001": {"started": 1.0}, "4005": {"started": 1.0}})
    d = Daemon(box, "--no-ball", patch=patch)
    rows = []
    d.wait("restart")

    # Criterion 5: a turn the agent injected resolves nothing; task 43 names the tab.
    world.fire("prompt", "dddd4444", "warpy", host=WARP,
               prompt="<task-notification>\nsome background task finished")
    d.wait("injected turn")
    rows.append(("injected turn: said, and counted", d.said("injected turn", "(1 so far)"),
                 ["it re-invoked itself — not a person, so nothing was resolved (1 so far)"]))
    d.wait("tab named")
    rows.append(("Warp: the tab is named <project> · <id4>, on its claude's pid",
                 (box.dir / "edge" / "titled").read_text()
                 if (box.dir / "edge" / "titled").exists() else "", "4001\twarpy · dddd\n"))
    world.fire("needs", "eeee6666", "warpy", host=WARP)
    d.wait("TAB NOT NAMED")
    rows.append(("Warp: a session not in the registry says why no tab was named",
                 [("not in Claude Code's registry" in s, "Warp tells it from a twin" in s)
                  for s in d.said("TAB NOT NAMED")], [(True, True)]))
    # Null seam, no ball: the beat was heard by nobody, and that is said.
    rows.append(("no ball, no sound: NO SOUND says the beat was not heard",
                 d.wait("NO SOUND", "with no ball, that beat was not heard at all"), True))
    world.fire("prompt", "eeee6666", "warpy", host=WARP, prompt="ok")
    d.wait("resolved", project="warpy")

    # Task 43: the Warp tab the daemon named is that session's and nobody else's.
    world.set("front", f"warpy · dddd\t{WARP}\t")
    world.fire("needs", "dddd4444", "warpy", host=WARP)
    rows.append(("Warp: its own named tab in front keeps it quiet",
                 d.wait("not signalling", project="warpy"), True))
    world.fire("prompt", "dddd4444", "warpy", host=WARP, prompt="ok")
    d.wait("resolved", n=2, project="warpy")

    # Task 43: a VS Code tab carrying one of its transcript's titles.
    world.set("front", f"transcript title vvvv — vsproj\t{VSCODE}\t")
    world.fire("needs", "vvvv5555", "vsproj", host=VSCODE)
    rows.append(("VS Code: its own tab in front keeps it quiet",
                 d.wait("not signalling", project="vsproj"), True))
    world.fire("prompt", "vvvv5555", "vsproj", host=VSCODE, prompt="ok")
    d.wait("resolved", project="vsproj")
    beats = len(d.said("play (beat)", project="vsproj"))
    world.fire("needs", "wwww7777", "vsproj", host=VSCODE)     # its twin, same folder
    # 8 s: the prompt just above holds every beat for after_prompt.wait_s (5 s).
    rows.append(("VS Code: the same tab does not quiet its twin in the same folder",
                 (d.wait("play (beat)", project="vsproj", n=beats + 1, timeout=8),
                  len(d.said("not signalling", project="vsproj"))), (True, 1)))
    world.fire("prompt", "wwww7777", "vsproj", host=VSCODE, prompt="ok")
    d.wait("resolved", n=2, project="vsproj")

    # Principle 7: could-not-tell is said once per reason, not once per poll.
    world.set("front", "\t\tscripted: nobody can see the window in front")
    world.fire("needs", "vvvv5555", "vsproj", host=VSCODE)
    d.wait("CANNOT SEE FOCUS")
    time.sleep(1.0)
    rows.append(("CANNOT SEE FOCUS: said once, with the seam's sentence",
                 d.said("CANNOT SEE FOCUS"), ["scripted: nobody can see the window in front"]))

    # A pending-list line for a session no longer waiting does nothing, and says so.
    world.set("aim", "zzzz9999")
    rows.append(("B aimed at a session not waiting: said, nothing let go",
                 d.wait("B aimed", "zzzz was not waiting any more — nothing changed"), True))

    world.set("wire", "no")
    rows.append(("hooks unwired mid-run: HOOKS NOT WIRED said",
                 d.wait("HOOKS NOT WIRED", "NOT wired (scripted)"), True))
    world.set("wire", "ok")
    rows.append(("…and wired again: HOOKS said a second time",
                 d.wait("HOOKS", "wired (scripted)", n=2), True))

    box.events.write_text("")                  # truncated under a running daemon
    rows.append(("events file truncated: said, with the count",
                 d.wait("events file restarted", "1x — it was truncated or replaced"), True))
    rows.append(("live: quits clean", d.stop(), 0))
    return rows


def terminal(patch=None):
    """Task 43: in Terminal, the tab's tty decides whose window is in front."""
    box = Sandbox()
    world = World(box)
    world.register("tttt7777", 5001)
    world.register("uuuu8888", 5002)
    world.proc({"5001": {"started": 1.0, "tty": "ttys011"},
                "5002": {"started": 1.0, "tty": "ttys012"}})
    world.set("front", f"anything at all\t{TERMINAL}\t")
    world.set("tabtty", "ttys011")
    d = Daemon(box, "--no-ball", patch=patch)
    d.wait("restart")
    world.fire("needs", "tttt7777", "termy", host=TERMINAL)
    rows = [("Terminal: the tab in front is read and said",
             d.wait("in front", "Terminal's tab on ttys011"), True),
            ("Terminal: its own tty in front keeps it quiet",
             d.wait("not signalling", project="termy"), True)]
    world.set("tabtty", "ttys012")                  # its twin's tab
    rows.append(("Terminal: its twin's tab in front lets it speak again",
                 d.wait("signalling", "you looked away", project="termy"), True))
    world.set("tabtty", "!raise")
    rows.append(("Terminal: a seam fault asking the tab is said, and the loop lives",
                 d.wait("CANNOT SEE TAB",
                        "asking Terminal's tab failed (RuntimeError('scripted seam fault'))"),
                 True))
    rows.append(("terminal: quits clean", d.stop(), 0))
    return rows


def processes(patch=None):
    """Task 40: a claude killed without its SessionEnd, or resumed under a new pid."""
    box = Sandbox()
    world = World(box)
    world.register("pppp1111", 6001)
    world.register("qqqq2222", 6002)
    world.proc({"6001": {"started": 1.0}, "6002": {"started": 1.0}})
    d = Daemon(box, "--no-ball", patch=patch)
    d.wait("restart")
    world.fire("needs", "pppp1111", "procy")
    world.fire("needs", "qqqq2222", "procq")
    d.wait("queued", "2 pending")
    world.proc({"blind": "scripted: no process list"})
    d.wait("CANNOT SEE PROCESSES")
    time.sleep(1.0)
    rows = [("CANNOT SEE PROCESSES: said once, and nothing dropped for it",
             (len(d.said("CANNOT SEE PROCESSES", "scripted: no process list")),
              d.said("process gone")), (1, []))]
    # Resumed: the old pid dead, the registry now naming a newer, living one.
    world.register("pppp1111", 6011)
    world.unregister(6001)
    world.proc({"6001": {"started": None}, "6011": {"started": 2.0}, "6002": {"started": 1.0}})
    rows.append(("resumed: the session follows its new pid, nothing dropped",
                 (d.wait("session", "pppp — now pid 6011; pid 6001 is gone, the session is not"),
                  d.said("process gone")), (True, [])))
    world.set("aim", "pppp1111")
    d.wait("B aimed", "attending")
    world.proc({"6011": {"started": None}, "6002": {"started": None}})
    rows.append(("gone, pending: dropped, with its pid",
                 d.wait("process gone", "its claude (pid 6002) is not running", project="procq"),
                 True))
    rows.append(("gone, attended: the hold is released, and said",
                 d.wait("released", "nothing left in it to attend", project="procy"), True))
    rows.append(("processes: quits clean", d.stop(), 0))
    return rows


def watching_flag(patch=None, anyway=True):
    """--notify-anyway, and a config the ladder warns about (CONFIG)."""
    box = Sandbox()
    world = World(box)
    world.set("front", "notify-repo\tcom.other.App\t")        # its own window, by title
    config = json.loads((ROOT / "config" / "signals.json").read_text())
    config["kinds"]["needs"]["every_s"] = 0.1       # under the motor's floor (ladder._every)
    (box.dir / "signals.json").write_text(json.dumps(config))
    d = Daemon(box, "--no-ball", *(["--notify-anyway"] if anyway else []), patch=patch,
               env={"WOBBLE_CONFIG": str(box.dir / "signals.json")})
    d.wait("restart")
    world.fire("needs", "nnnn1111", "notify-repo")
    d.wait("play (beat)", timeout=4)
    time.sleep(0.5)
    rc = d.stop()
    return [("CONFIG: a needs every 0.1 s is warned about",
             any("needs.every_s is 0.1s, under the ~" in s for s in d.said("CONFIG")), True),
            ("--notify-anyway: said at startup" if anyway else
             "reference leg: no flag, no --notify-anyway line",
             len(d.said("watching", "not looked at (--notify-anyway)")), 1 if anyway else 0),
            ("--notify-anyway: its own window in front, and it plays anyway"
             if anyway else "reference leg: without the flag, its window keeps it quiet",
             (bool(d.said("play (beat)")), bool(d.said("not signalling"))),
             (True, False) if anyway else (False, True)),
            ("notify-anyway: quits clean", rc, 0)]


def locks(patch=None):
    """Task 50: the three ways `claim` can fail, and which of them stops the run."""
    rows = []
    box = Sandbox()
    World(box)
    (box.dir / "var" / "daemon.lock").mkdir()           # cannot even be opened
    d = Daemon(box, "--no-ball", patch=patch)
    rows.append(("lock unopenable: LOCK NOT HELD, and the run goes on",
                 (d.wait("LOCK NOT HELD", "could not open"), d.wait("restart")), (True, True)))
    rows.append(("lock unopenable: quits clean", d.stop(), 0))

    box = Sandbox()
    World(box)
    held = (box.dir / "var" / "daemon.lock").open("a+")   # empty: no pid written
    fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
    d = Daemon(box, "--no-ball", patch=patch)
    rc = d.proc.wait(10)
    time.sleep(0.2)
    rows.append(("lock held, no pid in it: ALREADY RUNNING says so, exit 1",
                 ([("its pid unwritten" in s) for s in d.said("ALREADY RUNNING")], rc),
                 ([True], 1)))
    held.close()

    box = Sandbox()
    World(box)
    d = Daemon(box, "--no-ball", patch=patch, env={"WOBBLE_FLOCK": "oserror"})
    rows.append(("flock itself failing: LOCK NOT HELD, and the run goes on",
                 (d.wait("LOCK NOT HELD", "could not lock"), d.wait("restart")), (True, True)))
    rows.append(("flock failing: quits clean", d.stop(), 0))
    return rows


def ball(patch=None):
    """Task 35: a connected ball gets the beat, and is let go before quitting."""
    rows = []
    for how, label, has in (("letgo", "ball let go", "took "),
                            ("stuck", "BALL NOT LET GO", "still connected after 0.6s")):
        box = Sandbox()
        world = World(box)
        world.set("ball", how)
        d = Daemon(box, patch=patch)
        d.wait("restart")
        d.wait("ball", "scanning; its voice will be")
        for _ in range(100):
            if "FAKEBALL connected" in d.lines:
                break
            time.sleep(0.05)
        world.fire("needs", "bbbb1111", "bally",
                   extra={"notification_type": "permission_prompt",
                          "message": "Claude needs your permission to use Bash"})
        d.wait("play (beat)")
        world.fire("answered", "bbbb1111", "bally", extra={"tool_name": "Bash"})
        d.wait("play (caught)")
        time.sleep(0.3)
        rc = d.stop()
        if how == "letgo":
            rows.append(("ball: the beat goes to the ball (needs is effect 199)",
                         "FAKEBALL beat 199" in d.lines, True))
            rows.append(("ball: the catch goes to the ball too (task 56, 201)",
                         "FAKEBALL beat 201" in d.lines, True))
            rows.append(("ball: connected, so the Mac says no NO SOUND",
                         d.said("NO SOUND"), []))
        rows.append((f"ball {how}: {label} said on quit, exit 0",
                     (len(d.said(label, has)), rc), (1, 0)))
    return rows


def catch(patch=None):
    """Task 56: an answered needs is caught, one taken and walked away from breaks out."""
    box = Sandbox()
    world = World(box)
    d = Daemon(box, "--no-ball", patch=patch)
    rows = []
    d.wait("restart")
    rows.append(("banner: 'a catch' names both outcomes and their mutes",
                 d.said("a catch"), ["caught 201 (muted 193) · broke out 206 (muted 191)"]))
    asks = {"notification_type": "permission_prompt",
            "message": "Claude needs your permission to use Bash"}

    # Answered where it asked: the tool's own PostToolUse (task 49).
    world.fire("needs", "aaaa1111", "catchy", extra=asks)
    d.wait("play (beat)", project="catchy")
    world.fire("answered", "aaaa1111", "catchy", extra={"tool_name": "Bash"})
    rows.append(("answered where it asked: 201 played, and why",
                 d.wait("play (caught)", "effect 201 — its question was answered"), True))
    rows.append(("…with no ball, the catch says it was not heard",
                 d.wait("NO SOUND", "that was not heard at all"), True))
    # An answer to a tool nobody asked about catches nothing.
    world.fire("needs", "cccc2222", "catchy", extra=asks)
    d.wait("play (beat)", project="catchy", n=2)
    world.fire("answered", "cccc2222", "catchy", extra={"tool_name": "Read"})
    world.fire("prompt", "cccc2222", "catchy", prompt="ok")
    rows.append(("answered by a prompt in its session: 201 played, and why",
                 d.wait("play (caught)", "answered by a prompt in its session"), True))
    rows.append(("…and only those two caught: the other tool's answer caught nothing",
                 len(d.said("play (caught)")), 2))

    # A done answered by a prompt is not a catch.
    world.fire("done", "dddd3333", "donny")
    d.wait("play (beat)", project="donny")
    world.fire("prompt", "dddd3333", "donny", prompt="ok")
    d.wait("resolved", project="donny")
    time.sleep(0.3)
    rows.append(("a done resolved by a prompt plays no catch", len(d.said("play (caught)")), 2))

    # Taken with B but never come forward: not a catch you walked away from.
    world.fire("needs", "bbbb4444", "breaky", extra=asks)
    d.wait("play (beat)", project="breaky")
    d.press()
    d.wait("focused", project="breaky")
    time.sleep(3.8)                                  # past look_away.wait_s (3.0)
    rows.append(("taken but its window never in front: it does not break out",
                 d.said("broke out"), []))

    # Come forward, then left for look_away.wait_s: it breaks out, once.
    world.set("front", "breaky — zsh\tcom.other.App\t")
    time.sleep(0.4)
    world.set("front", OTHER)
    rows.append(("left its window for 3s without answering: broke out said",
                 d.wait("broke out", "you left its window 3s ago without answering",
                        project="breaky", timeout=6), True))
    rows.append(("…and 206 played", d.wait("play (broke out)", "effect 206"), True))
    rows.append(("…its own pulse waits for the catch to finish",
                 d.said("holding", "a catch is still playing", project="breaky")
                 if d.wait("holding", "a catch is still playing", project="breaky") else [],
                 ["needs · bbbb — a catch is still playing, so it waits 2s before speaking"]))
    rows.append(("…then it beats again", d.wait("play (beat)", project="breaky", n=2,
                                                 timeout=6), True))
    time.sleep(1.0)
    rows.append(("…said once per leave, not once per poll",
                 (len(d.said("broke out")), len(d.said("play (broke out)"))), (1, 1)))
    rows.append(("…and not as something speaking over the hold: it is the hold",
                 d.said("over the hold", project="breaky"), []))
    rows.append(("catch: quits clean", d.stop(), 0))
    return rows


SNAPSHOT_ARGV = ["/bin/zsh", "-c", "source /Users/x/.claude/shell-snapshots/"
                 "snapshot-zsh-1790821318307-lr326q.sh 2>/dev/null || true && eval 'make'"]


def approved(patch=None):
    """Task 65: a Bash question is answered when its command starts, not when it ends."""
    box = Sandbox()
    world = World(box)
    rows = []
    asks = {"notification_type": "permission_prompt",
            "message": "Claude needs your permission to use Bash"}
    old_mcp = {"started": 1.0, "argv": ["npm exec chrome-devtools-mcp@latest"]}
    world.register("abab1111", 7001)
    world.proc({"7001": {"started": 1.0, "kids": [7101, 7103]}, "7101": old_mcp,
                "7103": {"started": 1.0, "argv": SNAPSHOT_ARGV}})
    d = Daemon(box, "--no-ball", patch=patch)
    d.wait("restart")
    world.fire("needs", "abab1111", "bashy", extra=asks)
    d.wait("play (beat)", project="bashy")
    # The question's own hook, after it: a child, but not a Bash.
    world.proc({"7001": {"started": 1.0, "kids": [7101, 7103, 7102]}, "7101": old_mcp,
                "7103": {"started": 1.0, "argv": SNAPSHOT_ARGV},
                "7102": {"started": time.time(), "argv": ["/bin/sh", "-c", "hook_event.sh needs"]}})
    time.sleep(1.0)
    rows.append(("a Bash from before the question, a hook and an MCP server: not an answer",
                 d.said("resolved", project="bashy"), []))
    world.proc({"7001": {"started": 1.0, "kids": [7101, 7104]}, "7101": old_mcp,
                "7104": {"started": time.time(), "argv": SNAPSHOT_ARGV}})
    rows.append(("its Bash starting answers it, and says which pid",
                 d.wait("resolved", "needs · abab — its Bash started (pid 7104), so it was "
                                    "approved", project="bashy"), True))
    rows.append(("…and that is a catch", d.wait("play (caught)", "its question was answered"),
                 True))
    world.fire("answered", "abab1111", "bashy", extra={"tool_name": "Bash"})
    time.sleep(0.6)
    rows.append(("…its PostToolUse, when the command ends, answers nothing more",
                 (len(d.said("resolved", project="bashy")), len(d.said("play (caught)"))),
                 (1, 1)))

    # A question that is no longer about Bash: the old one's time is stale.
    world.register("ghgh4444", 7004)
    world.proc({"7004": {"started": 1.0, "kids": []}})
    world.fire("needs", "ghgh4444", "staley", extra=asks)
    d.wait("queued", project="staley")
    world.fire("prompt", "ghgh4444", "staley", prompt="no, do this")
    d.wait("resolved", project="staley")
    world.fire("needs", "ghgh4444", "staley", extra={
        "notification_type": "permission_prompt",
        "message": "Claude needs your permission to use Read"})
    d.wait("queued", project="staley", n=2)
    world.proc({"7004": {"started": 1.0, "kids": [7105]},
                "7105": {"started": time.time(), "argv": SNAPSHOT_ARGV}})
    time.sleep(1.0)
    rows.append(("a question about Read is not answered by a Bash starting",
                 len(d.said("resolved", project="staley")), 1))

    # Children nobody can read: said once, and the question stays.
    world.register("cdcd2222", 7002)
    world.proc({"blind_kids": "scripted: no child list",
                "7002": {"started": 1.0, "kids": [7106]},
                "7106": {"started": time.time() + 5, "argv": SNAPSHOT_ARGV}})
    world.fire("needs", "cdcd2222", "blindy", extra=asks)
    d.wait("CANNOT SEE CHILDREN")
    time.sleep(1.0)
    rows.append(("CANNOT SEE CHILDREN: said once, and the question stays",
                 (len(d.said("CANNOT SEE CHILDREN", "scripted: no child list")),
                  d.said("resolved", project="blindy")), (1, [])))
    rows.append(("approved: quits clean", d.stop(), 0))
    return rows


HAPPY = (20, 32, 34, 181, 230)                      # config/signals.json, task 64


def effect_of(line: str) -> int | None:
    return int(line.split("effect ")[1].split()[0]) if "effect " in line else None


def cries(patch=None):
    """Tasks 57, 64: a done cries in a mood from Pikachu's own, and 129 when told to — said either way."""
    rows = []
    legs = [("by default", (), "a done cries in a mood, from Pikachu's own — happy 20, 32, 34, "
                                "181, 230 · proud 32, 34 · sad 21-22 · call 33 · soft 230 · "
                                "greet 29 · lonely 143. On the old ball these are only a tap: "
                                "run with --one-cry for 129, the uploaded one"),
            ("--one-cry", ("--one-cry",),
             "129 for every done, Pikachu's uploaded cry (--one-cry)"),
            # Pidgey's, fetched beside Pikachu's: since task 70 that folder is
            # the only place a --cry may come from.
            ("another --cry", ("--cry", str(ROOT / "assets" / "cries" / "pidgey.wav")),
             "129 for every done (--cry is pidgey.wav, and the built-in cries are Pikachu's)")]
    for how, args, banner in legs:
        box = Sandbox()
        world = World(box)
        d = Daemon(box, "--no-ball", *args, patch=patch)
        d.wait("restart")
        rows.append((f"{how}: the banner says which cry a done plays", d.said("cries"), [banner]))
        world.fire("done", "eeee5555", "crying")
        d.wait("play (beat)", project="crying")
        beat = d.said("play (beat)", project="crying")[:1]
        rows.append((f"{how}: …and the done's first beat cries it, its mood named",
                     [(effect_of(s) in HAPPY, " · happy — " in s) for s in beat]
                     if not args else [(effect_of(s), " · " in s.split(" — ")[0]) for s in beat],
                     [(True, True)] if not args else [(129, False)]))
        if not args:
            rows.append(("the banner says how long idle takes, and what it reads now",
                         d.said("idle"), ["a window in front stops counting as looked at "
                                          "after 60s with no key or mouse. Idle right now: 0s"]))
        rows.append((f"{how}: quits clean", d.stop(), 0))
    return rows


EEVEE = ("a done cries in a mood, from Eevee's own — happy 49, 61, 63, 231 · proud "
         "61, 63 · sad 50-51 · call 62 · soft 231 · greet 58 · lonely 143. On the old "
         "ball these are only a tap: run with --one-cry for 129, the uploaded one")
EEVEE_HAPPY = (49, 61, 63, 231)                     # config/signals.json, spec 04 task 02


def voiced(box: Sandbox, world: World, chosen: str | None) -> Path:
    """Both cries fetched into the sandbox, and `var/voice` holding `chosen` (spec 04)."""
    cries = world.edge / "cries"
    cries.mkdir()
    for name in ("pikachu", "eevee"):
        (cries / f"{name}.wav").write_bytes(b"RIFF")
    voice = box.dir / "var" / "voice"
    if chosen is not None:
        voice.write_text(chosen)
    return voice


def first_beat(d: Daemon, world: World, project: str) -> list[tuple[int | None, bool]]:
    """A done fired now: its first beat's effect, and whether it was happy."""
    world.fire("done", "eeee6666", project)
    d.wait("play (beat)", project=project)
    return [(effect_of(s), " · happy — " in s)
            for s in d.said("play (beat)", project=project)[:1]]


def voices(patch=None):
    """Spec 04, task 03: the voice `var/voice` names, changed live, kept by an allowlist."""
    rows = []
    box = Sandbox()
    world = World(box)
    voice = voiced(box, world, None)
    world.set("ball", "letgo")
    d = Daemon(box, patch=patch)
    d.wait("restart")
    rows.append(("no var/voice: Pikachu in the banner, nothing refused",
                 ([s.startswith("a done cries in a mood, from Pikachu's own")
                   for s in d.said("cries")], d.said("VOICE NOT KEPT")), ([True], [])))
    voice.write_text("eevee\n")
    d.wait("voice")
    time.sleep(1.0)                             # five reads of the same file
    rows.append(("eevee written: said once, its cry, its led and its moods",
                 d.said("voice"), [f"Eevee now, with eevee.wav and led 1180 — {EEVEE}"]))
    rows.append(("…the ball is handed Eevee's cry, once",
                 d.lines.count("FAKEBALL voice eevee.wav"), 1))
    rows.append(("…and the next done cries happy, from Eevee's own",
                 [(effect in EEVEE_HAPPY, happy)
                  for effect, happy in first_beat(d, world, "voiced")], [(True, True)]))
    voice.write_text("charmander")
    d.wait("voice", "Pikachu now")
    time.sleep(1.0)
    rows.append(("charmander written: refused once, and the voice is Pikachu again",
                 (d.said("VOICE NOT KEPT"), len(d.said("voice", "Pikachu now, with pikachu.wav "
                                                                "and led 138 — a done cries"))),
                 ([f"{voice.resolve()} names 'charmander', which is not a voice in the config — the "
                   f"ones there are pikachu, eevee. The voice is Pikachu"], 1)))
    rows.append(("…the ball is handed Pikachu's cry back, once",
                 d.lines.count("FAKEBALL voice pikachu.wav"), 1))
    (world.edge / "cries" / "eevee.wav").unlink()
    voice.write_text("eevee")
    d.wait("VOICE NOT KEPT", "never fetched")
    time.sleep(1.0)
    rows.append(("eevee chosen with its cry deleted: refused once, Pikachu kept",
                 ([s.endswith("— venv/bin/python3 tools/fetch_cry.py --voice eevee. "
                              "The voice is Pikachu")
                   for s in d.said("VOICE NOT KEPT", "never fetched")],
                  len(d.said("voice")), d.lines.count("FAKEBALL voice eevee.wav")),
                 ([True], 2, 1)))
    rows.append(("live: quits clean", d.stop(), 0))

    legs = [("eevee kept from the last run", "eevee", (), [EEVEE], [], EEVEE_HAPPY),
            ("an old name in var/voice", "mewtwo", (),
             None, ["'mewtwo', which is not a voice in the config — the ones there "
                    "are pikachu, eevee. The voice is Pikachu"], HAPPY),
            ("--cry given: var/voice is not read", "eevee",
             ("--cry", str(ROOT / "assets" / "cries" / "pidgey.wav")),
             ["129 for every done (--cry is pidgey.wav, and the built-in cries are Pikachu's)"],
             [], (129,)),
            ("--one-cry in Eevee's voice", "eevee", ("--one-cry",),
             ["129 for every done, Eevee's uploaded cry (--one-cry)"], [], (129,))]
    for how, chosen, args, banner, refused, cries in legs:
        box = Sandbox()
        world = World(box)
        voiced(box, world, chosen)
        d = Daemon(box, "--no-ball", *args, patch=patch)
        d.wait("restart")
        time.sleep(1.0)
        said = d.said("cries")
        rows.append((f"{how}: the banner names the voice, nothing changes after",
                     (said if banner is not None else
                      [s.startswith("a done cries in a mood, from Pikachu's own")
                       for s in said], d.said("voice")),
                     (banner if banner is not None else [True], [])))
        rows.append((f"{how}: refused at startup only if it must, once",
                     [s.split(" names ", 1)[-1] for s in d.said("VOICE NOT KEPT")], refused))
        rows.append((f"{how}: a done's first beat is that voice's",
                     [effect in cries for effect, _ in first_beat(d, world, "kept")], [True]))
        rows.append((f"{how}: quits clean", d.stop(), 0))
    return rows


def moods(patch=None):
    """Task 64: the daemon hands the signaller what happened — the turn, the error, the idle."""
    box = Sandbox()
    world = World(box)
    world.set("idle", "0")
    config = json.loads((ROOT / "config" / "signals.json").read_text())
    config["after_prompt"]["wait_s"] = 0.0          # a prompt resolves; no hold to wait out
    done = config["kinds"]["done"]
    done.update(every_s=1.0, long_turn_s=1.0, lonely_after_s=3.0, greet_quiet_s=1.0,
                greet_away_s=90.0)
    (box.dir / "signals.json").write_text(json.dumps(config))
    # A B not answered comes back soon; argparse takes the last --snooze.
    d = Daemon(box, "--no-ball", "--snooze", "3", patch=patch,
               env={"WOBBLE_CONFIG": str(box.dir / "signals.json")})
    rows = []
    d.wait("restart")

    def first_beat(session, project, what="done", before=None):
        if before is not None:
            world.fire("prompt", session, project, prompt="go")
            time.sleep(before)
        world.fire(what, session, project)
        d.wait("play (beat)", project=project)
        world.fire("prompt", session, project, prompt="ok")     # resolved, so the next is alone
        d.wait("resolved", project=project)
        return [(effect_of(s), s.split(" — ")[0].rpartition(" · ")[2])
                for s in d.said("play (beat)", project=project)[:1]]

    rows.append(("reference: a quick turn is happy",
                 [(e in HAPPY, m) for e, m in first_beat("qqqq1111", "quick", before=0.0)],
                 [(True, "happy")]))
    rows.append(("a turn longer than long_turn_s is proud",
                 [(e in (32, 34), m) for e, m in first_beat("pppp2222", "proudy", before=1.3)],
                 [(True, "proud")]))
    rows.append(("a turn an API error ended is sad",
                 [(e in (21, 22), m) for e, m in first_beat("ffff3333", "faily", what="failed")],
                 [(True, "sad")]))
    rows.append(("…and its queued line says why",
                 d.said("queued", "the turn ended in an API error", project="faily")[:1],
                 ["done · ffff (1 pending) — the turn ended in an API error"]))

    world.fire("done", "llll4444", "lonely")
    d.wait("play (beat)", project="lonely", n=3, timeout=6)
    rows.append(("nobody came: two beats, then 143 once, on light 9",
                 [s.split(" — ")[0] for s in d.said("play (beat)", project="lonely")][2:],
                 ["effect 143 over light 9 · lonely"]))
    world.fire("prompt", "llll4444", "lonely", prompt="ok")
    d.wait("resolved", project="lonely")

    world.fire("done", "gggg5555", "greety")
    d.wait("play (beat)", project="greety", n=2)
    time.sleep(1.2)                                  # past greet_quiet_s (1.0)
    d.press()
    rows.append(("B on a done that has called: 29, once",
                 d.wait("play (greet)", "effect 29 — you came for it (B pressed)",
                        project="greety"), True))
    world.fire("prompt", "gggg5555", "greety", prompt="ok")
    d.wait("resolved", project="greety")

    # Task 67: B right on top of its call is one effect too many.
    world.fire("done", "hhhh5555", "hushy")
    d.wait("play (beat)", project="hushy", n=2)
    d.press()
    rows.append(("B right after its call: no greet, and says which effect played",
                 d.wait("no greet", "effect 33 played", project="hushy"), True))
    rows.append(("…so nothing plays over the call", d.said("play (greet)", project="hushy"), []))
    world.fire("prompt", "hhhh5555", "hushy", prompt="ok")
    d.wait("resolved", project="hushy")

    # Task 68: a done you took with B has been seen, so its snooze brings it back quiet.
    world.fire("done", "kkkk5555", "snoozy")
    d.wait("play (beat)", project="snoozy", n=2)
    time.sleep(1.2)                                  # past greet_quiet_s (1.0)
    d.press()
    d.wait("play (greet)", project="snoozy")
    rows.append(("B left unanswered: back from its snooze, quiet, and says why",
                 d.wait("snooze", "came back", project="snoozy")
                 and d.said("snooze", project="snoozy")[-1].endswith(", quiet — you had seen it"),
                 True))
    time.sleep(1.2)                                  # a beat's every_s (1.0) and then some
    rows.append(("…and it calls no more", len(d.said("play (beat)", project="snoozy")), 2))
    d.press()
    d.wait("B pressed", project="snoozy", n=2)
    time.sleep(0.5)
    rows.append(("…and B on it again: no second greet, and not for want of quiet",
                 (len(d.said("play (greet)", project="snoozy")),
                  d.said("no greet", project="snoozy")), (1, [])))
    world.fire("prompt", "kkkk5555", "snoozy", prompt="ok")
    d.wait("resolved", project="snoozy")

    world.set("front", "softy\tcom.other.App\t")
    world.fire("done", "ssss6666", "softy")
    rows.append(("reference: its window in front, somebody at the keys: quiet",
                 d.wait("not signalling", project="softy"), True))
    world.set("idle", "100")
    rows.append(("…nobody at the keys for idle.after_s: it speaks, and says why",
                 d.wait("signalling", "no input for 60s with its window in front",
                        project="softy"), True))
    d.wait("play (beat)", project="softy", n=2)
    time.sleep(1.2)                                  # past greet_quiet_s (1.0)
    rows.append(("…its first beat soft, 230, the second a call",
                 [s.split(" — ")[0] for s in d.said("play (beat)", project="softy")][:2],
                 ["effect 230 over light 9 · soft", "effect 33 over light 9 · call"]))
    rows.append(("…and nobody looked away, so that is not said",
                 d.said("signalling", "you looked away", project="softy"), []))
    world.set("idle", "0")
    rows.append(("back at the keys after greet_away_s: the greet, once, and why",
                 d.wait("play (greet)", "you are back: 100s with no key or mouse",
                        project="softy"), True))
    # Task 87: the absence is in the log on its own, timed from the last touch.
    gone = [m and int(m[1]) * 60 + int(m[2]) for m in
            (re.fullmatch(r"after (\d+)m(\d+)s", x) for x in d.said("back at the keys"))]
    rows.append(("…said as left and back, once each, back timed from the last touch",
                 (d.said("left the keys"), [100 <= g <= 130 if g else g for g in gone]),
                 (["100s with no key or mouse"], [True])))
    world.fire("prompt", "ssss6666", "softy", prompt="ok")
    d.wait("resolved", project="softy")
    # 2026-10-01 17:11:53: that greet's `hushed` was the name of the function
    # that says a silence too, so the next B held was None(...) and the daemon died.
    d.hold()
    rows.append(("…and a B held after that greet still says what it did",
                 d.wait("B held", "nothing waiting — nothing silenced"), True))

    # Task 67: a minute is the soft's, not an absence — no greet for it.
    world.set("idle", "0")
    world.set("front", "minute\tcom.other.App\t")
    world.fire("done", "mmmm6666", "minute")
    d.wait("not signalling", project="minute")
    world.set("idle", "70")
    # Past the lonely too (n=3): coming back within greet_quiet_s of it spends
    # the greet in silence, and a mutant survived that way once on a busy desk, 2026-10-01.
    d.wait("play (beat)", project="minute", n=3, timeout=6)
    time.sleep(1.2)                                  # past greet_quiet_s (1.0)
    world.set("idle", "0")
    time.sleep(1.0)
    rows.append(("a minute and a bit away, then a key: no greet",
                 d.said("play (greet)", project="minute"), []))
    rows.append(("…and not away either: still the one absence",
                 (len(d.said("left the keys")), len(d.said("back at the keys"))), (1, 1)))
    world.fire("prompt", "mmmm6666", "minute", prompt="ok")
    d.wait("resolved", project="minute")
    world.set("front", OTHER)

    world.set("idle", "blind")
    world.fire("done", "bbbb7777", "blindy")
    d.wait("play (beat)", project="blindy")
    time.sleep(0.5)
    rows.append(("an idle nobody can read: CANNOT SEE IDLE, once",
                 d.said("CANNOT SEE IDLE"),
                 ["scripted: the idle time is out of reach — a window in front keeps its "
                  "signal quiet however long nobody touches anything"]))
    rows.append(("…and the greet plays once each, in all", len(d.said("play (greet)")), 3))
    rows.append(("moods: quits clean", d.stop(), 0))
    return rows


JUNO = "4b84aaaa-1111-4111-8111-111111111111"
WOBBLY = "c2ceaaaa-2222-4222-8222-222222222222"


def alternating(patch=None):
    """Task 66: B mashed between two VS Code sessions opens no second copy of either."""
    box = Sandbox()
    world = World(box)
    world.register(JUNO, 8001, entrypoint="claude-vscode")
    world.register(WOBBLY, 8002, entrypoint="claude-vscode")
    world.proc({"8001": {"started": 1.0}, "8002": {"started": 1.0}})
    # A raise must outlast the four presses (~0.45 s): at 0.4 the last one landed after it
    # on a busy CI runner, 2026-10-05 (task 79).
    world.set("moves", "1.2")
    d = Daemon(box, "--no-ball", patch=patch)
    rows = []
    d.wait("restart")
    world.fire("needs", JUNO, "juno", host=VSCODE)
    world.fire("needs", WOBBLY, "wobbly", host=VSCODE)
    d.wait("queued", n=2)
    for _ in range(4):                 # the desk's press a second, faster
        d.press()
        time.sleep(0.15)
    d.wait("focused", n=2, timeout=6)
    time.sleep(0.5)

    def fake(kind: str) -> list[str]:
        return [line for line in list(d.lines) if line.startswith(f"FAKEFOCUS {kind} ")]

    took = len(d.said("B pressed"))
    rows.append(("4 presses, each taking the other session",
                 [s.startswith("attending") for s in d.said("B pressed")], [True] * 4))
    rows.append(("one raise at a time: never two seam calls in flight",
                 sorted({line.rsplit("(", 1)[1] for line in fake("window") + fake("pick")}),
                 ["1 in flight)"]))
    rows.append(("the two pressed while one was raising: each replaced, and said so",
                 len(d.said("NOT FOCUSED", "never tried — B moved on to")), 2))
    rows.append(("…so the first and the last pressed are the two raised, in order",
                 [line.split()[2] for line in fake("window")], ["juno", "wobbly"]))
    rows.append(("every link landed in its own session's window",
                 [line.split()[2] + " " + line.split("'")[1] for line in fake("pick")],
                 ["4b84 Claude Code — juno", "c2ce Claude Code — wobbly"]))
    rows.append(("every press says what became of its window",
                 len(d.said("focused")) + len(d.said("NOT FOCUSED")), took))

    # A click lands between the window coming forward and the link.
    world.set("steal", f"Specs — elsewhere\t{VSCODE}\t")
    picks = len(fake("pick"))
    d.press()
    rows.append(("another window in front by the pick: NOT FOCUSED, and which",
                 d.wait("NOT FOCUSED", "'Specs — elsewhere' was in front, so its own tab "
                                       "was not picked"), True))
    rows.append(("…and no link opened into it", len(fake("pick")), picks))

    # The link opens, then something else is in front.
    (world.edge / "steal").unlink()
    world.set("steal_after", f"Specs — elsewhere\t{VSCODE}\t")
    d.press()
    rows.append(("a link that opened with another window in front is NOT FOCUSED",
                 d.wait("NOT FOCUSED", "is in front, not its own window"), True))
    rows.append(("alternating: quits clean", d.stop(), 0))
    return rows


def glance(patch=None):
    """Task 67: a window passed through is not looked at; one already in front is."""
    box = Sandbox()
    world = World(box)
    config = json.loads((ROOT / "config" / "signals.json").read_text())
    config["after_prompt"]["wait_s"] = 0.0          # a prompt resolves; no hold to wait out
    (box.dir / "signals.json").write_text(json.dumps(config))
    d = Daemon(box, "--no-ball", patch=patch,
               env={"WOBBLE_CONFIG": str(box.dir / "signals.json")})
    rows = []
    d.wait("restart")
    rows.append(("banner: a glance is a second in front", d.said("a glance"),
                 ["1s in front before a window counts as looked at"]))

    world.fire("done", "gggg1111", "glancy")
    d.wait("play (beat)", project="glancy")
    world.set("front", "glancy — zsh\tcom.other.App\t")
    d.wait("in front", "glancy")
    time.sleep(0.4)
    world.set("front", OTHER)
    time.sleep(3.5)                                  # past look_away.wait_s (3.0)
    rows.append(("its window in front 0.4s: not counted as looked at, nor as left",
                 (d.said("not signalling", project="glancy"),
                  d.said("signalling", project="glancy")), ([], [])))
    world.set("front", "glancy — zsh\tcom.other.App\t")
    rows.append(("…in front past the glance: looked at",
                 d.wait("not signalling", "you are looking at its window", project="glancy"),
                 True))
    world.set("front", OTHER)
    rows.append(("…and left: the wait after looking away as before",
                 d.wait("signalling", "you looked away 3s ago", project="glancy", timeout=6),
                 True))
    world.fire("prompt", "gggg1111", "glancy", prompt="ok")
    d.wait("resolved", project="glancy")

    # Nothing pending, its window already in front: a done there is quiet at once.
    world.set("front", "steady — zsh\tcom.other.App\t")
    time.sleep(0.5)
    world.fire("done", "ssss2222", "steady")
    rows.append(("a done arriving in the window you are in: quiet at once",
                 d.wait("not signalling", project="steady"), True))
    time.sleep(1.5)
    rows.append(("…not one beat, not even inside the glance", d.said("play (beat)",
                                                                      project="steady"), []))
    rows.append(("glance: quits clean", d.stop(), 0))
    return rows


def silence(patch=None):
    """Task 68: a session silenced by B held or by its ⌥ row, until you type in it or answer it."""
    box = Sandbox()
    world = World(box)
    config = json.loads((ROOT / "config" / "signals.json").read_text())
    config["after_prompt"]["wait_s"] = 0.0          # a prompt resolves; no hold to wait out
    config["kinds"]["needs"]["every_s"] = 0.5
    config["kinds"]["done"]["every_s"] = 0.5
    (box.dir / "signals.json").write_text(json.dumps(config))
    d = Daemon(box, "--no-ball", patch=patch,
               env={"WOBBLE_CONFIG": str(box.dir / "signals.json")})
    rows = []
    d.wait("restart")
    rows.append(("banner: 'a silence' says how, what it plays, and until when",
                 d.said("a silence"), ["B held 2s or ⌥ in the menu: effect 2 over light 179, "
                                       "no sound — until you type in it or answer it"]))
    asks = {"notification_type": "permission_prompt",
            "message": "Claude needs your permission to use Bash"}

    def beats(project: str) -> int:
        return len(d.said("play (beat)", project=project))

    # B held with nothing pending: said, and nothing played.
    d.hold()
    rows.append(("B held on an empty queue: said, and nothing silenced",
                 d.wait("B held", "nothing waiting — nothing silenced"), True))

    # B held: the top of the queue, a needs, silenced, and it beats no more.
    world.fire("needs", "nnnn1111", "hushy", extra=asks)
    d.wait("play (beat)", project="hushy")
    d.hold()
    rows.append(("B held: the top of the queue silenced, and says until when",
                 d.wait("silenced", "nnnn — quiet until you type in it or answer it",
                        project="hushy"), True))
    rows.append(("…its confirmation played, effect 2 and silent, and why",
                 d.wait("play (silenced)", "effect 2 · silent — B held", project="hushy"), True))
    rows.append(("…and the menu says it",
                 d.wait("menu", "hushy nnnn: silenced until you type in it"), True))
    rows.append(("…a hold is not a press: nothing attended", d.said("B pressed"), []))
    was = beats("hushy")
    time.sleep(1.5)                                  # three of its every_s (0.5)
    rows.append(("…and it beats no more", beats("hushy"), was))

    # A new needs from it is not the prompt that ends the silence.
    world.fire("needs", "nnnn1111", "hushy", extra=asks)
    rows.append(("a new needs from it arrives quiet, and its queued line says why",
                 d.wait("queued", "silenced, so it waits quiet", project="hushy"), True))
    time.sleep(1.0)
    rows.append(("…and beats no more either", beats("hushy"), was))

    # An answer where it asked ends the silence: the next one speaks.
    world.fire("answered", "nnnn1111", "hushy", extra={"tool_name": "Bash"})
    rows.append(("an answer where it asked ends it, and says so",
                 d.wait("unsilenced", "its question was answered", project="hushy"), True))
    world.fire("done", "nnnn1111", "hushy")
    rows.append(("…so its next signal speaks",
                 d.wait("play (beat)", project="hushy", n=was + 1), True))
    world.fire("prompt", "nnnn1111", "hushy", prompt="ok")
    d.wait("resolved", project="hushy", n=2)

    # The ⌥ row: that session, by name, and a stale one refused out loud.
    world.fire("done", "dddd2222", "menuy")
    d.wait("play (beat)", project="menuy")
    world.set("silence", "dddd2222")
    rows.append(("its ⌥ row silences that session, and says how",
                 d.wait("play (silenced)", "silence chosen", project="menuy")
                 and bool(d.said("silenced", "dddd — quiet until", project="menuy")), True))
    world.set("silence", "zzzz9999")
    rows.append(("a ⌥ row for a session gone: said, and nothing silenced",
                 d.wait("silence chosen", "zzzz was not waiting any more — nothing silenced"),
                 True))
    # A prompt in it ends the silence, with nothing left waiting to resolve or not.
    world.fire("prompt", "dddd2222", "menuy", prompt="ok")
    rows.append(("a prompt in it ends it, and says so",
                 d.wait("unsilenced", "you typed in it, so it speaks again", project="menuy"),
                 True))
    world.fire("done", "dddd2222", "menuy")
    rows.append(("…so its next done speaks", d.wait("play (beat)", project="menuy", n=2), True))
    world.fire("prompt", "dddd2222", "menuy", prompt="ok")
    d.wait("resolved", project="menuy", n=2)

    # B held on the one being attended: let go into the queue, quiet.
    world.fire("done", "hhhh3333", "heldy")
    d.wait("play (beat)", project="heldy")
    d.press()
    d.wait("B pressed", project="heldy")
    d.hold()
    rows.append(("B held on the one you are on: let go into the queue, quiet",
                 d.wait("silenced", "the one you were on went back to the queue, quiet",
                        project="heldy"), True))
    rows.append(("silence: quits clean", d.stop(), 0))
    return rows


AX_OFF = "Accessibility is switched off in Privacy & Security: B raises no window"


def permissions(patch=None):
    """Spec 03: each permission said once per change, a ⚠ while one is refused, a click to its pane."""
    box = Sandbox()
    world = World(box)

    def perms(bluetooth="refused", accessibility="refused", terminal="granted") -> None:
        world.set("perms", json.dumps({
            "bluetooth": [bluetooth, "Bluetooth is switched off"],
            "accessibility": [accessibility, AX_OFF if accessibility == "refused" else None],
            "automation:" + TERMINAL: [terminal, {"refused": "Terminal refused",
                                                  "not running": "Terminal is not running"}
                                       .get(terminal)]}))

    def title() -> str:
        shown = [line[len("FAKETITLE "):] for line in list(d.lines)
                 if line.startswith("FAKETITLE ")]
        return shown[-1] if shown else "<no title>"

    def settle() -> None:
        time.sleep(1.0)                              # five of its reads (0.2 s)

    perms()
    d = Daemon(box, "--no-ball", patch=patch)
    rows = []
    rows.append(("Accessibility refused: said, with what stops",
                 d.wait("PERMISSION OFF", AX_OFF), True))
    rows.append(("Terminal's automation granted: said",
                 d.wait("permission", f"automation:{TERMINAL} granted"), True))
    settle()
    rows.append(("…each once, however many reads",
                 (len(d.said("PERMISSION OFF")), len(d.said("permission", "granted"))), (1, 1)))
    rows.append(("a --no-ball run: Bluetooth is never read, so never said",
                 [line for line in d.lines if "Bluetooth" in line or "bluetooth" in line], []))
    rows.append(("the title ends in ⚠", title().endswith(" · ⚠"), True))

    world.set("permission", "accessibility")
    rows.append(("its line clicked: the pane opened, and said",
                 d.wait("permission", "scripted: accessibility's pane opened")
                 and "FAKEPANE accessibility" in d.lines, True))

    perms(accessibility="granted")
    rows.append(("granted again: said", d.wait("permission", "accessibility granted"), True))
    settle()
    rows.append(("…and the ⚠ goes by itself", title().endswith("⚠"), False))

    perms(accessibility="granted", terminal="refused")
    rows.append(("Terminal refused: said", d.wait("PERMISSION OFF", "Terminal refused"), True))
    perms(accessibility="granted", terminal="not running")
    settle()
    rows.append(("Terminal closed: nothing said, the refusal stands",
                 (d.said("permission", "not running"), title().endswith(" · ⚠")), ([], True)))

    perms(accessibility=None)
    rows.append(("unreadable: said in capitals, never as granted",
                 d.wait("CANNOT SEE PERMISSION"), True))
    rows.append(("permissions: quits clean", d.stop(), 0))

    # With a ball mirror, the radio is the ball's link: a refusal is said.
    box = Sandbox()
    world = World(box)
    world.set("ball", "")
    perms(accessibility="granted")
    d = Daemon(box, patch=patch)
    rows.append(("with a ball: Bluetooth refused is said",
                 d.wait("PERMISSION OFF", "Bluetooth is switched off"), True))
    rows.append(("with a ball: quits clean", d.stop(), 0))
    return rows


def interrupted(patch=None):
    """main()'s last door: a KeyboardInterrupt before the handlers are up."""
    out = subprocess.run([PY, HARNESS, "--no-ball"], capture_output=True, text=True,
                         env={**os.environ, "WOBBLE_EDGE": "/nonexistent",
                              "WOBBLE_KBI": "1"}, timeout=30)
    return [("KeyboardInterrupt: 'stopped.' and exit 0",
             (out.stdout.strip(), out.returncode), ("stopped.", 0))]


LIFE = re.compile(r" · after (\d+)s · (\d+) beats? \((\d+) heard\)$")


def lives(patch=None):
    """Task 86: every line that ends a signal says how long it waited, and its beats."""
    asks = {"notification_type": "permission_prompt",
            "message": "Claude needs your permission to use Bash"}
    sys.path.insert(0, str(ROOT))                  # the daemon's own `span`, not a copy of it
    from src.daemon import span
    rows = [("a wait as a person reads it: seconds, minutes, hours",
             [span(25), span(252), span(6372), span(59.6)], ["25s", "4m12s", "1h46m", "1m00s"])]
    box = Sandbox()
    world = World(box)
    world.set("ball", "letgo")
    d = Daemon(box, patch=patch)
    d.wait("restart")
    for _ in range(100):
        if "FAKEBALL connected" in d.lines:
            break
        time.sleep(0.05)
    world.fire("needs", "llll1111", "lively", extra=asks)
    d.wait("play (beat)", project="lively", n=2)
    world.fire("needs", "llll1111", "lively", extra=asks)          # task 88: the same wait
    d.wait("queued", project="lively", n=2)
    d.wait("play (beat)", project="lively", n=3)
    rows.append(("asked again: the same wait, said so with how long",
                 [bool(re.search(r" — again, waiting \ds$", x))
                  for x in d.said("queued", project="lively")], [False, True]))
    rows.append(("…and each beat its ladder's count, which carries on",
                 [x.rsplit(" · ", 1)[-1] for x in d.said("play (beat)", project="lively")][:3],
                 ["beat 1", "beat 2", "beat 3"]))
    world.fire("answered", "llll1111", "lively", extra={"tool_name": "Bash"})
    d.wait("resolved", project="lively")
    end = [LIFE.search(x) for x in d.said("resolved", project="lively")]
    beats = len(d.said("play (beat)", project="lively"))
    rows.append(("an answer's line: how long, and every beat, each heard on the ball",
                 [(int(m[1]) >= 3, int(m[2]), int(m[3])) if m else None for m in end],
                 [(True, beats, beats)]))
    world.fire("done", "eeee2222", "endy")
    d.wait("play (beat)", project="endy")
    world.fire("end", "eeee2222", "endy")
    d.wait("session ended", project="endy")
    rows.append(("a session's end says it too",
                 [bool(LIFE.search(x)) for x in d.said("session ended", project="endy")],
                 [True]))
    rows.append(("lives with a ball: quits clean", d.stop(), 0))
    kept = kept_rows(box)
    rows.append(("task 89: each end kept as a row in signals.tsv, with how it ended",
                 [(r["kind"], r["how"]) for r in kept], [("needs", "answered"), ("done", "closed")]))
    rows.append(("…the row the same life its line said",
                 [(int(r["beats"]), int(r["heard"])) for r in kept][:1], [(beats, beats)]))

    box = Sandbox()
    world = World(box)
    d = Daemon(box, "--no-ball", patch=patch)
    d.wait("restart")
    world.fire("needs", "nnnn3333", "unheard", extra=asks)
    d.wait("play (beat)", project="unheard", n=2)
    world.fire("prompt", "nnnn3333", "unheard", prompt="ok")
    d.wait("resolved", project="unheard")
    end = [LIFE.search(x) for x in d.said("resolved", project="unheard")]
    rows.append(("no ball and no sound played: its beats, none heard",
                 [(int(m[2]) >= 2, int(m[3])) if m else None for m in end], [(True, 0)]))
    rows.append(("lives with no ball: quits clean", d.stop(), 0))
    rows.append(("…and its row: you were there, nothing heard",
                 [(r["how"], r["heard"]) for r in kept_rows(box)], [("there", "0")]))
    return rows


def kept_rows(box: Sandbox) -> list[dict[str, str]]:
    """The sandbox's `signals.tsv` (task 89) — it follows the events file, as the log does."""
    path = box.events.parent / "logs" / "signals.tsv"
    if not path.exists():
        return []
    head, *body = path.read_text().splitlines()
    return [dict(zip(head.split("\t"), line.split("\t"))) for line in body]


SCENARIOS = [("restart", restore), ("live loop", live), ("Terminal", terminal),
             ("processes", processes), ("--notify-anyway", watching_flag),
             ("reference leg: no --notify-anyway",
              lambda patch=None: watching_flag(patch, anyway=False)),
             ("the lock", locks), ("the ball on quit", ball), ("a catch", catch),
             ("the cries", cries), ("the voices", voices), ("the moods", moods), ("an approved Bash", approved),
             ("alternating B", alternating), ("a glance", glance), ("the silence", silence),
             ("a signal's life", lives), ("the permissions", permissions),
             ("KeyboardInterrupt", interrupted)]

# One line of src/daemon.py each; the scenario that must catch it.
MUTANTS = [
    ("restart keeps a dead claude's signal", restore,
     ("if run is None or (blind is None and not run.alive(started)):", "if run is None:")),
    ("restart forgets the Warp tab", restore, None),
    ("an injected turn resolves like a prompt", live,
     ("if hook.what == \"prompt\" and not hook.by_person:", "if False:")),
    ("Warp tabs never named", live,
     ("if host != WARP or session in warp_tried:", "if True:")),
    ("a named Warp tab is not its own", live,
     ("own = own | {warp_tabs[entry.session]}", "own = own")),
    ("VS Code titles never read", live,
     ("for run in runs if run.entrypoint == \"claude-vscode\"}",
      "for run in runs if run.entrypoint == \"nothing\"}")),
    ("CANNOT SEE FOCUS said every poll", live,
     ("if blind is not None and blind != said_blind:", "if blind is not None:")),
    ("a stale aim says nothing", live,
     ("say(\"B aimed\", f\"{short(chosen)} was not waiting",
      "(lambda *a: None)(f\"{short(chosen)} was not waiting")),
    ("wiring checked once", live, ("if ok_now != ok:", "if False:")),
    ("restarts of the events file unsaid", live, ("if tail.restarts:", "if False:")),
    ("Terminal ttys never read", terminal,
     ("for run in runs if run.entrypoint == \"cli\"", "for run in runs if False")),
    ("a Terminal seam fault stops the loop", terminal,
     ("except Exception as exc:          # a seam fault", "except ValueError as exc:  # a seam fault")),
    ("liveness never asked", processes,
     ("if now >= alive_at + ALIVE_EVERY_S:", "if False:")),
    ("a resumed claude taken for gone", processes,
     ("if (fresh is not None and fresh.pid != run.pid", "if (False and fresh.pid != run.pid")),
    ("could-not-see-processes said every time", processes,
     ("if blind != said_blind_process:", "if True:")),
    ("--notify-anyway still reads the window", watching_flag,
     ("if target is not None and not args.notify_anyway:", "if target is not None:")),
    ("an unopenable lock refuses to run", locks,
     ("return True, None, (f\"could not open", "return False, None, (f\"could not open")),
    ("a catch unsaid in the banner", catch, ("        if catches else\n", "        if False else\n")),
    ("the silence unsaid in the banner", silence,
     ("    say(\"a silence\", f\"B held", "    (lambda *a: None)(\"a silence\", f\"B held")),
    ("an answer where it asked catches nothing", catch,
     ("                replied(hook.session, \"answered where it asked\", \"answered\")",
      "                pass")),
    ("a prompt's answer catches nothing", catch,
     ("                if answered.caught:\n                    outcome(\"caught\", \"it was",
      "                if False:\n                    outcome(\"caught\", \"it was")),
    ("a catch the next beat lands on", catch,
     ("(outcome_until, outcome_why)) if at is not None]", "(None, outcome_why)) if at is not None]")),
    ("a raise that never came forward breaks out", catch,
     ("if attention.set_away(away, seen=held_away.seen):",
      "if attention.set_away(away, seen=True):")),
    ("its window in front never counted as seen", catch,
     ("            self.left_at, self.seen = None, True",
      "            self.left_at = None")),
    ("a broken-out needs said as over its own hold", catch,
     ("and current.session != holding.session else None)", "else None)")),
    ("a catch never sent to the ball", ball,
     ("        if on_ball:\n            ball.beat(voice)", "        if False:\n            ball.beat(voice)")),
    ("--one-cry ignored", cries,
     ("signaller.one_cry = args.one_cry or other_voice", "signaller.one_cry = other_voice")),
    ("another --cry still given Pikachu's", cries,
     ("signaller.one_cry = args.one_cry or other_voice", "signaller.one_cry = args.one_cry")),
    ("the cries unsaid", cries,
     ("    say(\"cries\", cries())", "    (lambda *a: None)(\"cries\", cries())")),
    ("var/voice never read again", voices,
     ("if args.cry is None and now >= voice_at + VOICE_EVERY_S:", "if False:")),
    ("var/voice read under a --cry too", voices,
     ("if args.cry is None and now >= voice_at + VOICE_EVERY_S:",
      "if now >= voice_at + VOICE_EVERY_S:")),
    ("var/voice not read at startup", voices,
     ("partner, said_refused = (chosen_voice(voice_file, tuple(ladders)) if args.cry is None",
      "partner, said_refused = ((DEFAULT_VOICE, None) if args.cry is None")),
    ("a refusal at startup unsaid", voices,
     ("    if said_refused is not None:\n        say(\"VOICE NOT KEPT\"",
      "    if False:\n        say(\"VOICE NOT KEPT\"")),
    ("a refusal said on every read", voices,
     ("if refused != said_refused:", "if True:")),
    ("a change never reaches the signaller", voices,
     ("        signaller.ladder = ladder\n", "")),
    ("a change never reaches the ball", voices,
     ("            ball.revoice(cry_of(name))", "            pass")),
    ("a change unsaid", voices,
     ("        say(\"voice\", f\"{name.capitalize()} now", "        (lambda *a, **k: None)(\"voice\", f\"{name.capitalize()} now")),
    ("a voice kept with its cry never fetched", voices,
     ("if not cry_of(name).is_file():", "if False:")),
    ("a name the config does not list kept", voices,
     ("if name not in partners:", "if False:")),
    ("the banner's voice always Pikachu", voices,
     ("from {partner.capitalize()}'s own", "from Pikachu's own")),
    ("the mood unsaid on the play line", cries,
     ("            mood = (f\" · {signaller.mood}\" if signaller.mood and not signaller.muted",
      "            mood = (\"\" if True")),
    ("the idle banner unsaid", cries,
     ("        say(\"CANNOT SEE IDLE\" if said_idle_blind else \"idle\",",
      "        (lambda *a: None)(\"CANNOT SEE IDLE\" if said_idle_blind else \"idle\",")),
    ("a turn's length never measured", moods,
     ("                    event = replace(event, turn_s=now - prompted_at.pop(event.session))",
      "                    prompted_at.pop(event.session)")),
    ("a prompt never timed", moods, ("                prompted_at[hook.session] = now\n", "")),
    ("an API error unsaid on the queued line", moods,
     ("(\" — the turn ended in an API error\" if event.failed else \"\")", "\"\"")),
    ("idle never read", moods,
     ("            idle_s, idle_blind = platform_seam.idle.seconds()",
      "            idle_s, idle_blind = 0.0, None")),
    ("CANNOT SEE IDLE said every poll", moods,
     ("if idle_blind is not None and idle_blind != said_idle_blind:", "if idle_blind is not None:")),
    ("a blind idle unsaid", moods,
     ("if idle_blind is not None and idle_blind != said_idle_blind:", "if False:")),
    ("idle in front still counted as looked at", moods,
     ("        watched = watched and not still", "        watched = watched")),
    ("idle in front not soft", moods,
     ("                              idle_front=idle_front)", "                              idle_front=False)")),
    ("no input unsaid", moods,
     ("say(\"signalling\", f\"{describe(current)} — no input for \"",
      "(lambda *a, **k: None)(\"signalling\", f\"{describe(current)} — no input for \"")),
    ("idle said as looking away", moods,
     ("current.session == watching and not idle_front:", "current.session == watching:")),
    ("no greet on coming back", moods,
     ("        if came_back is not None and current is not None:\n", "        if False:\n")),
    ("back after a minute, as before task 67", moods,
     ("    keys_away = Away(back_s if back_s is not None else ladder.idle_s)",
      "    keys_away = Away(ladder.idle_s)")),
    ("the greet's reason named like the silence's sayer", moods,
     ("            greeting, no_greet = signaller.greet(current, now)\n",
      "            greeting, no_greet = signaller.greet(current, now); hushed = no_greet\n")),
    ("the reason for coming back unsaid", moods,
     ("f\"you are back: {came_back}\"", "f\"you are back\"")),
    ("no greet on B", moods,
     ("        greeting, no_greet = signaller.greet(taken.attending, now)\n",
      "        greeting, no_greet = None, None\n")),
    ("a greet spent in silence unsaid", moods,
     ("            say(\"no greet\", no_greet, project=taken.attending.project)\n",
      "            pass\n")),
    ("an approved Bash answers nothing", approved,
     ("        if asked_at and now >= approved_at + APPROVED_EVERY_S:",
      "        if False:")),
    ("a Bash from before the question answers it", approved,
     ("if started is None or started < since:", "if started is None:")),
    ("any child answers a Bash question", approved,
     ("if argv is not None and runs_bash(argv):", "if argv is not None:")),
    ("a stale Bash question still answered", approved,
     ("if asked.get(session) != BASH or run is None:", "if run is None:")),
    ("CANNOT SEE CHILDREN said every poll", approved,
     ("if blind != said_blind_children:", "if True:")),
    ("an answer by a Bash starting is no catch", approved,
     ("        if answered.caught:\n            outcome(\"caught\", \"its question",
      "        if False:\n            outcome(\"caught\", \"its question")),
    ("two raises at once", alternating,
     ("                await raise_window(*job)",
      "                asyncio.create_task(raise_window(*job))")),
    ("a replaced raise unsaid", alternating,
     ("            say(\"NOT FOCUSED\", f\"never tried",
      "            (lambda *a, **k: None)(\"NOT FOCUSED\", f\"never tried")),
    ("the link opened into whatever window is in front", alternating,
     ("    if not entry.in_window(title, app):\n        if title:",
      "    if False:\n        if title:")),
    ("focused because the link opened", alternating,
     ("    if entry.in_window(title, app):\n        return True, how",
      "    if True:\n        return True, how")),
    ("a glance taken as a look", glance,
     ("                session == self.session or front_since is None\n"
      "                or now >= front_since + self.glance_s):",
      "                True):")),
    ("a window already in front made to wait out a glance", glance,
     ("front_since = now if said_front is not None else None", "front_since = now")),
    ("the glance unsaid in the banner", glance,
     ("    say(\"a glance\", f\"{ladder.glance_s:g}s in front",
      "    (lambda *a: None)(\"a glance\", f\"{ladder.glance_s:g}s in front")),
    ("a seen done's quiet return unsaid", moods,
     ("                          + quietly(released.session)\n", "")),
    ("B held does nothing", silence,
     ("            hushed(attention.silence(now), \"B held\")", "            pass")),
    ("a hold typed read as a press", silence,
     ("hold.set if typed.strip() == \"hold\" else press.set", "press.set")),
    ("no ⌥ row offered", silence,
     ("            on_silence=silencing.append,", "            on_silence=None,")),
    ("the confirmation never played", silence,
     ("        outcome(\"silenced\", how, silenced.project)", "        pass")),
    ("a hold on nothing says nothing", silence,
     ("        if not silenced:\n", "        if not silenced:\n            return\n")),
    ("a silenced arrival not said quiet", silence,
     ("if queue.silenced(event.session) else \"\")", "if False else \"\")")),
    ("an answer's unsilence unsaid", silence,
     ("        if answered.unsilenced:\n            say(", "        if False:\n            say(")),
    ("a prompt's unsilence unsaid", silence,
     ("                if answered.unsilenced:\n", "                if False:\n")),
    ("away unsaid", moods,
     ("        if keys_away.went is not None:\n", "        if False:\n")),
    ("back timed from when it was noticed", moods,
     ("                self.left = wall - idle_s\n", "                self.left = wall\n")),
    ("a re-queue said as a new wait", lives,
     ("        again = had is not None and had.kind is event.kind\n",
      "        again = False\n")),
    ("a beat heard with nothing to hear it", lives,
     ("had.heard += not voice.silent and (connected or played)", "had.heard += 1")),
    ("an answer's life unsaid", lives,
     ("{how}{lived(answered.dropped, kept)}", "{how}")),
    ("an end not kept", lives,
     ("why = log.ended(entry.kind.value, now - had.start, had.beats, had.heard, how)",
      "why = None")),
    ("a permission said every read", permissions,
     ("        if permissions.get(kind) == read:\n            return\n",
      "        if False:\n            return\n")),
    ("Bluetooth never read, ball or not", permissions,
     ('if kind == "bluetooth" and ball is None:', 'if kind == "bluetooth":')),
    ("Bluetooth read in a --no-ball run", permissions,
     ('if kind == "bluetooth" and ball is None:', "if False:")),
    ("Terminal closed lifts its refusal", permissions,
     ('if read[0] == "not running" and kind in permissions:', "if False:")),
    ("permissions read once and never again", permissions,
     ("permissions_at = now\n", "permissions_at = now + 1e9\n")),
    ("no ⚠ in the title", permissions,
     ('return any(state == "refused" for state, _ in permissions.values())', "return False")),
    ("a permission's click opens nothing", permissions,
     ("ok, why = platform_seam.permissions.settings(kind)",
      'ok, why = False, "not wired"')),
    ("the ball kept on quit", ball,
     ("        ball.set_wanted(False)\n        letting_go", "        letting_go")),
]


def part() -> tuple[bool, range | None]:
    """Which slice `--part` asks for: `scenarios`, or `mutants:<i>/<n>`; all of it by default.

    Seventy mutants, each a daemon whose waits must run out, are twenty minutes of
    sleeping; the suite runs the slices side by side and adds their rows up (task 79).
    """
    args = sys.argv[1:]
    if "--part" not in args:
        return True, range(len(MUTANTS))
    which = args[args.index("--part") + 1]
    if which == "scenarios":
        return True, None
    i, n = (int(x) for x in which.removeprefix("mutants:").split("/"))
    return False, range(i, len(MUTANTS), n)


def main() -> int:
    print(__doc__.strip().splitlines()[0])
    sheet = Sheet()
    scenarios, mutants = part()
    for name, scenario in (SCENARIOS if scenarios else []):
        print(f"\n  {name}")
        for what, got, want in scenario():
            sheet.row(what, got, want)

    print("\n  mutants — each must turn at least one row wrong")
    source = (ROOT / "src" / "daemon.py").read_text()
    for name, scenario, patch in [MUTANTS[i] for i in (mutants or [])]:
        # A line that is not there once makes the harness refuse, which would
        # read as caught: that is the probe broken, not the rule defended.
        if patch is not None and source.count(patch[0]) != 1:
            sheet.row(f"mutant: {name} — its line is in src/daemon.py once",
                      source.count(patch[0]), 1)
            continue
        quiet = Sheet(quiet=True)
        rows = (scenario(mutant="no-recall-tabs") if patch is None else scenario(patch=patch))
        for what, got, want in rows:
            quiet.row(what, got, want)
        sheet.row(f"mutant: {name}", "caught" if quiet.bad else "survived", "caught")

    print("\n  " + ("ALL CASES MATCH the known answer" if not sheet.bad
                   else f"{sheet.bad} WRONG — the rows above"))
    return 1 if sheet.bad else 0


if __name__ == "__main__":
    sys.exit(main())
