#!/usr/bin/env python3
"""The corners of `src/hooks.py` no other desk check reaches.

    venv/bin/python3 tests/tables/check_hooks_edges.py

`check_hooks.py` already owns `by_person`, `reminds`, `asked`/`tool_key`/`answers`
against real captured payloads. `check_sessions.py` already owns the registry and
`Titles` against this Mac's real, live `~/.claude/sessions` and `~/.claude/projects`.
Neither ever forces the failure paths: a truncated `var/events`, a registry folder
that cannot be listed, a transcript that vanishes mid-read, a `settings.json`
missing or half-wired. Those are rare exactly because the daemon runs for weeks at
a time — which is why they are worth a known answer instead of "it has never
happened yet" (constitution principle 3: the desk check is the gate, and a gate
that only ever sees the happy path is not one).

Every fixture lives under `tempfile.mkdtemp()` and every call below passes an
explicit path — `Tail(path)`, `registry(folder)`, `wiring(settings, script)`,
`Titles(folder)` — never the module's defaults, which point at the real
`~/.claude/*`. Nothing here reads, writes or lists anything outside its own
temp directory.

Each known answer is read off `src/hooks.py`'s own docstrings, not off a run of
the code:

  - `Tail` — starts at the end of a file that already exists (not at 0); a
    missing file never raises; a file that shrank under it restarts the read
    from the top rather than gluing new bytes to a stale buffer; a partial
    last line is held back and handed back whole once its newline lands; a
    line, once returned, never comes back; a read that hits an `OSError`
    (a path that is a directory) comes back empty rather than raising.
  - `Running.alive` — no pid found at all (`started=None`) is never alive.
  - `registry()` — a folder `glob()` cannot read comes back `[]`; a file that
    is not JSON, or is JSON but not a dict, or carries no session id, or a pid
    that is not an int, is skipped rather than fatal; two files for one
    session — the newest `startedAt` wins; a `.key` file beside the `.json`
    is never read at all.
  - `Titles.of` — an `OSError` mid-read (the file disappears) hands back
    whatever was already known rather than raising; a line that contains
    `-title"` but is not valid JSON is skipped, and the good line beside it
    still reads.
  - `wiring()` — a missing `settings.json`, an unreadable/invalid one, some
    events wired and others not (named), and every event wired, are the four
    answers the function has.
  - `parse()` — invalid JSON, and JSON that parses to something other than a
    dict, both come back `None`, never an exception; `HookLine.as_event`
    answers `None` for the three words that resolve nothing on the queue
    (`prompt`, `end`, `answered`) and a real `Event` for the two that do.

**The control** is six mutants, each the rule it stands for removed. A mutant
that leaves every row above still matching has a hole in the table, so each
one is run through the whole table again and must turn at least one row wrong.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src import hooks as mod                                          # noqa: E402


class Sheet:
    def __init__(self, quiet: bool = False):
        self.quiet, self.bad = quiet, 0

    def row(self, what: str, got, want) -> None:
        good = got == want
        self.bad += not good
        if not self.quiet:
            print(f"    {what:<62} {'ok' if good else f'<-- WRONG: {got!r}, wanted {want!r}'}")

    def ok(self) -> bool:
        return not self.bad


def box() -> Path:
    return Path(tempfile.mkdtemp(prefix="wobble-hooks-edge-"))


def safe(fn, *args):
    """Calls `fn(*args)`, turning a raised exception into a value that can
    still be compared against a known answer instead of crashing this script —
    a mutant that makes `parse()` raise on bad input must show up as a WRONG
    row, not take the whole check down with it."""
    try:
        return fn(*args)
    except Exception as exc:                                          # noqa: BLE001
        return f"<raised {type(exc).__name__}: {exc}>"


def append(path: Path, text: str) -> None:
    with path.open("a") as fh:
        fh.write(text)


# ------------------------------------------------------------------ Tail ----

def tail_rows(sheet: Sheet, say) -> None:
    say("\n  Tail — from_end on an existing file (hooks.py:306)")
    ev = box() / "events"
    ev.write_text("old line 1\nold line 2\n")
    tail = mod.Tail(ev)
    sheet.row("position starts at the file's current size, not 0",
              tail.position, ev.stat().st_size)
    sheet.row("nothing already on disk comes back", tail.lines(), [])
    append(ev, "new line\n")
    sheet.row("only what arrived after that comes back", tail.lines(), ["new line"])

    say("\n  Tail — a missing file (hooks.py:312-313)")
    missing = box() / "not-written-yet"
    tail2 = mod.Tail(missing)
    sheet.row("from_end on a file that does not exist yet leaves position 0",
              tail2.position, 0)
    sheet.row("lines() on a missing file returns [], never raises",
              tail2.lines(), [])

    say("\n  Tail — the file shrinking under it (hooks.py:314-318)")
    ev3 = box() / "events"
    ev3.write_text("a" * 100 + "\n")
    tail3 = mod.Tail(ev3, from_end=False)
    first = tail3.lines()
    sheet.row("a full read first, so position has moved off 0", tail3.position > 0, True)
    sheet.row("restarts starts at 0", tail3.restarts, 0)
    ev3.write_text("short\n")                      # truncated in place, smaller
    got = tail3.lines()
    sheet.row("a shrink counts as one restart", tail3.restarts, 1)
    sheet.row("…and reads the new content from 0, not glued to the stale buffer",
              got, ["short"])
    ev3.unlink()
    ev3.write_text("x\n")                           # unlink + a new, shorter file
    got2 = tail3.lines()
    sheet.row("an unlink-and-replace with a shorter file is one restart too",
              tail3.restarts, 2)
    sheet.row("…and its content reads correctly from the top", got2, ["x"])

    say("\n  Tail — a partial last line (hooks.py's own promise, docstring)")
    ev4 = box() / "events"
    ev4.write_text("")
    tail4 = mod.Tail(ev4, from_end=False)
    append(ev4, "abc")                              # no trailing newline yet
    sheet.row("a partial line is held back, not returned early", tail4.lines(), [])
    append(ev4, "def\nghi\n")                        # the rest of it, plus one more
    sheet.row("once the newline lands, the whole line comes back joined",
              tail4.lines(), ["abcdef", "ghi"])
    sheet.row("and it never comes back a second time", tail4.lines(), [])

    say("\n  Tail — an OSError while reading, not while stat()-ing (hooks.py:326-327)")
    # A directory opened for reading raises `IsADirectoryError` (an OSError) —
    # measured here rather than assumed, since `Path.exists()` is true for a
    # directory too, so `size` is whatever `stat()` reports for it (never 0 on
    # APFS) and the code proceeds past the shrink/no-change checks into the
    # `open()` that actually fails.
    as_dir = box()
    tail5 = mod.Tail(as_dir, from_end=False)
    sheet.row("reading a path that turns out to be a directory comes back empty",
              tail5.lines(), [])


def tail_leaks_partial(self):
    """Mutant: the trailing partial line is returned instead of held back."""
    try:
        size = self.path.stat().st_size
    except OSError:
        return []
    if size < self.position:
        self.restarts += 1
        self.position, self._buffer = 0, ""
    if size == self.position:
        return []
    try:
        with self.path.open("r", errors="replace") as fh:
            fh.seek(self.position)
            chunk = fh.read()
            self.position = fh.tell()
    except OSError:
        return []
    self._buffer += chunk
    lines = self._buffer.split("\n")
    self._buffer = ""
    return lines


def tail_ignores_shrink(self):
    """Mutant: the shrink-detection branch removed — a shrunk file is read on
    from the old offset instead of restarting from 0."""
    try:
        size = self.path.stat().st_size
    except OSError:
        return []
    if size == self.position:
        return []
    try:
        with self.path.open("r", errors="replace") as fh:
            fh.seek(self.position)
            chunk = fh.read()
            self.position = fh.tell()
    except OSError:
        return []
    self._buffer += chunk
    *whole, self._buffer = self._buffer.split("\n")
    return whole


# --------------------------------------------------------------- Running ----

def running_rows(sheet: Sheet, say) -> None:
    say("\n  Running.alive — started=None (hooks.py:397-398)")
    run = mod.Running(session="x", pid=1, started=1000.0)
    sheet.row("no pid found at all is never alive, whatever this Running started at",
              run.alive(None), False)
    sheet.row("(sanity: a real start close enough is alive)", run.alive(1000.0), True)


# --------------------------------------------------------------- registry ----

def registry_rows(sheet: Sheet, say) -> None:
    say("\n  registry() — the skip branches (hooks.py:432-442)")
    reg = box()

    def make(name: str, obj) -> None:
        (reg / name).write_text(obj if isinstance(obj, str) else json.dumps(obj))

    make("100.json", {"sessionId": "s-good", "pid": 100, "startedAt": 1_000_000,
                      "cwd": "/Users/x/dev-clients/my-workspace"})
    make("bad.json", "{not json")                                  # 432-433
    make("notdict.json", [1, 2, 3])                                 # 434-435
    make("nosession.json", {"sessionId": "", "pid": 5})             # 436-438
    make("nosession2.json", {"pid": 6})                             # sessionId absent
    make("badpid.json", {"sessionId": "s-badpid", "pid": "not-a-number"})  # 439-442
    make("111.json", {"sessionId": "s-dup", "pid": 111, "startedAt": 1_000})
    make("222.json", {"sessionId": "s-dup", "pid": 222, "startedAt": 5_000})
    make("444.json", {"sessionId": "s-key", "pid": 444, "startedAt": 1_000})
    make("444.key", {"sessionId": "s-key", "pid": 999, "startedAt": 999_999_999})

    result = mod.registry(reg)
    by_session = {run.session: run for run in result}
    sessions = set(by_session)

    sheet.row("a well-formed file becomes a Running", by_session.get("s-good") and
              by_session["s-good"].pid, 100)
    sheet.row("bad JSON, a non-dict payload, no sessionId and a non-int pid are "
              "all skipped, not fatal", sessions - {"s-good", "s-dup", "s-key"}, set())
    sheet.row("two files, one session: the newest startedAt wins",
              by_session["s-dup"].pid, 222)
    sheet.row("the .key file beside the .json is never read at all",
              by_session["s-key"].pid, 444)
    sheet.row("its folder is read, for a window on another desktop (task 69)",
              by_session["s-good"].cwd, "/Users/x/dev-clients/my-workspace")
    sheet.row("…and a file with none has none, never a guess",
              by_session["s-key"].cwd, "")

    say("\n  registry() — a folder glob() itself cannot read (hooks.py:425-427)")
    # A real chmod 000 directory does not reach this branch on this Python:
    # pathlib's own glob() silently swallows PermissionError and returns []
    # (measured here — 3.12.14, APFS), so the `except OSError` at 426-427 would
    # otherwise never run. Standing in for `Path` only around this one call
    # reaches it honestly instead of asserting it by reading the source.
    class BustedPath:
        def __init__(self, *_a, **_kw) -> None: ...
        def glob(self, *_a, **_kw):
            raise OSError("simulated: this folder cannot be listed")

    real_path = mod.Path
    try:
        mod.Path = BustedPath
        busted = mod.registry("/never-actually-touched")
    finally:
        mod.Path = real_path
    sheet.row("…comes back empty, not raising", busted, [])


def registry_first_wins(folder=mod.SESSIONS):
    """Mutant: sorted by name, first file per session kept — never compares
    `startedAt`, so the newest-wins rule is gone."""
    try:
        files = sorted(Path(folder).glob("*.json"))
    except OSError:
        return []
    newest: dict[str, mod.Running] = {}
    for path in files:
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        session = data.get("sessionId")
        if not isinstance(session, str) or not session:
            continue
        try:
            pid = int(data.get("pid") or path.stem)
        except (TypeError, ValueError):
            continue
        started = data.get("startedAt")
        run = mod.Running(session=session, pid=pid,
                          entrypoint=str(data.get("entrypoint") or ""),
                          name=str(data.get("name") or ""),
                          host_session=str(data.get("hostSessionId") or ""),
                          started=started / 1000 if isinstance(started, (int, float)) else 0.0)
        if session not in newest:                       # <- the mutation
            newest[session] = run
    return list(newest.values())


def registry_reads_key_files(folder=mod.SESSIONS):
    """Mutant: `.key` files are globbed and read too, same rule otherwise."""
    try:
        files = list(Path(folder).glob("*.json")) + list(Path(folder).glob("*.key"))
    except OSError:
        return []
    newest: dict[str, mod.Running] = {}
    for path in files:
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        session = data.get("sessionId")
        if not isinstance(session, str) or not session:
            continue
        try:
            pid = int(data.get("pid") or path.stem)
        except (TypeError, ValueError):
            continue
        started = data.get("startedAt")
        run = mod.Running(session=session, pid=pid,
                          entrypoint=str(data.get("entrypoint") or ""),
                          name=str(data.get("name") or ""),
                          host_session=str(data.get("hostSessionId") or ""),
                          started=started / 1000 if isinstance(started, (int, float)) else 0.0)
        if session not in newest or run.started > newest[session].started:
            newest[session] = run
    return list(newest.values())


# ----------------------------------------------------------------- Titles ----

def titles_rows(sheet: Sheet, say) -> None:
    say("\n  Titles.of — a malformed line, then the file disappearing (hooks.py:493-503)")
    folder = box()
    proj = folder / "proj"
    proj.mkdir()
    session = "abc-session"
    transcript = proj / f"{session}.jsonl"
    transcript.write_text('{"type":"ai-title","aiTitle":"First"}\n')

    titles = mod.Titles(folder)
    sheet.row("a normal read finds the title", titles.of(session), frozenset({"First"}))

    # Only the *latest* ai-title and the *latest* custom-title are kept (the
    # class's own docstring), so a second ai-title would just replace "First"
    # rather than add to it — a custom-title is what proves a good line reads
    # fine beside a bad one. Contains the `-title"` substring the scan looks
    # for, but is not valid JSON — the good line right after it must still be
    # read (502-503).
    append(transcript, '{"type":"custom-title","customTitle":"Broken"\n')
    append(transcript, '{"type":"custom-title","customTitle":"Mine"}\n')
    sheet.row("a malformed -title line is skipped, the good one beside it is not",
              titles.of(session), frozenset({"First", "Mine"}))

    transcript.unlink()
    sheet.row("the file disappearing mid-read hands back what was already known",
              titles.of(session), frozenset({"First", "Mine"}))


# ----------------------------------------------------------------- wiring ----

def wiring_rows(sheet: Sheet, say) -> None:
    say("\n  wiring() — the four answers (hooks.py:519-539)")
    folder = box()
    script = "/Users/x/wobble/tools/hook_event.sh"

    missing = folder / "no-settings.json"
    ok, msg = mod.wiring(missing, script)
    sheet.row("a settings.json that does not exist", ok, False)
    sheet.row("…says so by name", "does not exist" in msg, True)

    invalid = folder / "invalid.json"
    invalid.write_text("{not json")
    ok, msg = mod.wiring(invalid, script)
    sheet.row("a settings.json that cannot be read/parsed", ok, False)
    sheet.row("…says the state is unknown, not that it's fine",
              "could not be read" in msg, True)

    def hooks_for(*events: str) -> dict:
        return {event: [{"hooks": [{"command": script}]}] for event in events}

    partial = folder / "partial.json"
    partial.write_text(json.dumps({"hooks": hooks_for("Stop", "Notification")}))
    ok, msg = mod.wiring(partial, script)
    sheet.row("some events wired, some not: NOT wired", ok, False)
    named = set(msg.partition("NOT wired: ")[2].partition(" — ")[0].split(", "))
    sheet.row("…and it names exactly the missing ones",
              named, set(mod.HOOK_FOR) - {"Stop", "Notification"})

    full = folder / "full.json"
    full.write_text(json.dumps({"hooks": hooks_for(*mod.HOOK_FOR)}))
    ok, msg = mod.wiring(full, script)
    sheet.row("every event wired: ok", ok, True)
    sheet.row("…and says so", msg.startswith("hooks wired for"), True)


def wiring_lenient(settings, script):
    """Mutant: ok as soon as *some* event is wired, not only when none is missing."""
    settings, script = Path(settings), str(script)
    try:
        hooks = json.loads(settings.read_text()).get("hooks", {})
    except FileNotFoundError:
        return False, f"{settings} does not exist"
    except (json.JSONDecodeError, OSError) as exc:
        return False, f"{settings} could not be read ({exc})"
    missing = [event for event in mod.HOOK_FOR
               if not any(script in entry.get("command", "")
                          for group in hooks.get(event, [])
                          for entry in group.get("hooks", []))]
    if len(missing) < len(mod.HOOK_FOR):                          # <- the mutation
        return True, f"hooks wired for {', '.join(mod.HOOK_FOR)} in {settings}"
    return False, f"NOT wired: {', '.join(missing)} — {settings} has no hook running {script}"


# ------------------------------------------------------------------ parse ----

def parse_edge_rows(sheet: Sheet, say) -> None:
    say("\n  parse() — invalid JSON, a non-dict payload (hooks.py:258-263)")
    sheet.row("invalid JSON never raises, parses as None",
              safe(mod.parse, "done\t{not valid json"), None)
    array_payload = json.dumps([1, 2, 3])
    sheet.row("valid JSON that is not a dict is None too",
              safe(mod.parse, f"done\t{array_payload}"), None)

    say("\n  HookLine.as_event — None for the three that resolve nothing (hooks.py:113-119)")

    def parsed_for(what: str, extra: dict | None = None) -> mod.HookLine:
        data = {"session_id": "s1", "cwd": "/x/proj", **(extra or {})}
        line = mod.parse(f"{what}\t{json.dumps(data)}")
        assert line is not None, f"fixture broke: {what} did not parse"
        return line

    sheet.row("prompt is not a signal", parsed_for("prompt").as_event(0.0), None)
    sheet.row("end is not a signal", parsed_for("end").as_event(0.0), None)
    sheet.row("answered is not a signal",
              parsed_for("answered", {"tool_name": "Bash"}).as_event(0.0), None)

    event = parsed_for("done").as_event(123.0)
    sheet.row("done becomes a real Event", event is not None and event.kind, mod.KIND_OF["done"])
    sheet.row("…carrying session/project/at/window_hint/host across",
              (event.session, event.project, event.at, event.window_hint, event.host),
              ("s1", "proj", 123.0, "proj", ""))


def parse_raises(line: str):
    """Mutant: the try/except around json.loads removed (hooks.py:258-261) —
    bad JSON crashes instead of the line being quietly refused."""
    what, tab, rest = line.rstrip("\n").partition("\t")
    payload, _, rest = rest.partition("\t")
    host, _, focus_url = rest.partition("\t")
    focus_url = focus_url.strip()
    if not tab or what not in mod.HOOK_FOR.values():
        return None
    data = json.loads(payload) if payload else {}
    if not isinstance(data, dict):
        return None
    session = str(data.get("session_id") or "")
    if not session:
        return None
    cwd = str(data.get("cwd") or "")
    project = mod.project_of(cwd) if cwd else "(unknown project)"
    return mod.HookLine(what=what, session=session, project=project, window_hint=project,
                        by_person=mod.by_person(data), host=host.strip(),
                        focus_url=focus_url if mod.WARP_URL.fullmatch(focus_url) else "",
                        reminder=what == "needs" and mod.reminds(data),
                        tool=(mod.asked(data) if what == "needs" else
                              mod.tool_key(str(data.get("tool_name") or ""))
                              if what in ("answered", "asking") else ""),
                        agent=(str(data.get("agent_id") or "")
                               if what in ("answered", "asking") else ""))


# ------------------------------------------------------------------- all ----

def run_all(quiet: bool = False) -> bool:
    sheet = Sheet(quiet)
    say = (lambda _: None) if quiet else print
    tail_rows(sheet, say)
    running_rows(sheet, say)
    registry_rows(sheet, say)
    titles_rows(sheet, say)
    wiring_rows(sheet, say)
    parse_edge_rows(sheet, say)
    return sheet.ok()


MUTANTS = (
    ("Tail returns the trailing partial line instead of holding it back",
     mod.Tail, "lines", tail_leaks_partial),
    ("Tail ignores the file shrinking under it",
     mod.Tail, "lines", tail_ignores_shrink),
    ("registry() keeps the first file per session, not the newest start",
     mod, "registry", registry_first_wins),
    ("registry() also reads .key files",
     mod, "registry", registry_reads_key_files),
    ("wiring() calls it ok when an event is still missing",
     mod, "wiring", wiring_lenient),
    ("parse() raises on invalid JSON instead of refusing quietly",
     mod, "parse", parse_raises),
)


def main() -> int:
    print(__doc__.strip().splitlines()[0])
    ok = run_all()

    print("\n  the control — six mutants, each must turn at least one row above wrong")
    for label, target, attr, stand_in in MUTANTS:
        original = getattr(target, attr)
        setattr(target, attr, stand_in)
        try:
            survived = run_all(quiet=True)
        finally:
            setattr(target, attr, original)
        ok &= not survived
        print(f"    mutant: {label:<58} {'survived' if survived else 'caught'}")

    print("\n" + ("ALL CASES MATCH the known answer" if ok
                  else "SOMETHING DOES NOT MATCH — the rows above, not this line"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
