#!/usr/bin/env python3
"""Run the core's queue against known answers. No ball, no clock, no waiting.

    venv/bin/python3 tests/tables/check_queue.py

Every case is a little story with times written into it, so a ten-minute one
costs nothing to run. The expected order is worked out from the rules in
`plan.md` — `needs` above `done`, oldest first within a kind, one entry per
session (task 41) — and never read off what the code did.

**The control is the `kind-blind` column**: the same entries sorted by age alone,
ignoring priority. A priority case whose blind order matches its expected order
is not testing priority, it is agreeing with it by accident, and the run says so
at the end rather than leaving it to be assumed.

**The second table is task 41's**, where a folder has more than one session,
and there the control is three mutants rather than a column. Each is one piece
of task 20's per-project fold (2026-09-23 to 2026-09-28), which this undoes:
counting projects, listing one line per project, and B taking the whole project
out. All three have to break the table.

**The third is task 47's**, what comes back quiet after a restart, and its
controls are five mutants, one per rule. The first is the kind-blind column
carried over: a quiet `needs` sorted by kind alone lands above a live `done`,
which is the order the table must refuse.
"""
from __future__ import annotations

import ast
import dataclasses
import glob
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.core.signals import Entry, Event, Kind, Queue          # noqa: E402

DONE, NEEDS = Kind.DONE, Kind.NEEDS


def build(script: list[tuple[str, Kind, float]]) -> Queue:
    """`[(session, kind, at), …]` filed in the order given."""
    queue = Queue()
    for session, kind, at in script:
        queue.add(Event(session=session, kind=kind, project=f"p-{session}",
                        window_hint=f"win-{session}", at=at))
    return queue


# name, script, expected order, expected length, does it test priority
CASES = [
    ("nothing pending", [], [], 0, False),

    ("needs above done, whatever arrived first",
     [("A", DONE, 0.0), ("B", NEEDS, 1.0)], ["B", "A"], 2, True),

    ("oldest first inside a kind",
     [("A", DONE, 0.0), ("B", DONE, 1.0)], ["A", "B"], 2, False),

    ("both rules at once",
     [("A", DONE, 0.0), ("B", DONE, 1.0), ("C", NEEDS, 2.0), ("D", NEEDS, 3.0)],
     ["C", "D", "A", "B"], 4, True),

    ("one entry per session",
     [("A", DONE, 0.0), ("A", DONE, 5.0), ("A", DONE, 9.0)], ["A"], 1, False),

    ("repeating does not send you to the back",
     [("A", NEEDS, 0.0), ("B", NEEDS, 1.0), ("A", NEEDS, 10.0)], ["A", "B"], 2, False),

    ("a kind change restarts the wait",
     [("A", DONE, 0.0), ("B", NEEDS, 5.0), ("A", NEEDS, 10.0)], ["B", "A"], 2, False),

    # The first draft of this case put B's needs BEFORE the replacement, and the
    # kind-blind control caught it: age alone gave the same answer, so it would
    # have passed with the priority rule deleted. B now arrives last, so the only
    # thing that can put it on top is its kind.
    ("a done replaces a pending needs",
     [("A", NEEDS, 0.0), ("A", DONE, 5.0), ("B", NEEDS, 20.0)], ["B", "A"], 2, True),
]


# --- task 41: two sessions in one folder are two entries ------------------

# Two sessions in `wobble` (say Warp and the desktop app) and one elsewhere.
TOGETHER = [("A", NEEDS, "wobble", 0.0),
            ("B", DONE, "wobble", 1.0),
            ("C", DONE, "work", 2.0)]


class CountsProjects(Queue):
    """Task 20's count: windows to visit, taken to be one per folder."""

    def __len__(self) -> int:
        return len({w.project for w in self._waiting.values()})


class OneLinePerProject(Queue):
    """Task 20's list: a folder's most urgent session speaks for all of it."""

    def pending(self) -> list[Entry]:
        leads: dict[str, Entry] = {}
        for entry in super().pending():
            leads.setdefault(entry.project, entry)
        return list(leads.values())


class DropsTheProject(Queue):
    """Task 20's B: attending one session took its whole folder out."""

    def drop(self, session: str) -> Entry | None:
        entry = super().drop(session)
        if entry is not None:
            for other in [w.session for w in self._waiting.values()
                          if w.project == entry.project]:
                del self._waiting[other]
        return entry


def together(make, quiet: bool = False) -> bool:
    """The whole of task 41, run against `make()` — the real queue or a mutant."""
    ok = True

    def row(what: str, got, want) -> None:
        nonlocal ok
        good = got == want
        ok &= good
        if not quiet:
            print(f"  {what:<52} "
                  f"{'ok' if good else f'<-- WRONG: {got!r}, wanted {want!r}'}")

    queue = make()
    for session, kind, project, at in TOGETHER:
        queue.add(Event(session=session, kind=kind, project=project,
                        window_hint=project, at=at))

    row("two sessions in one folder are two entries",
        [e.session for e in queue.pending()], ["A", "B", "C"])
    row("...and the count is sessions", len(queue), 3)

    top = queue.top()
    row("each entry is one session",
        (top.session, top.project, top.kind.value, len(top)), ("A", "wobble", "needs", 1))

    taken = queue.drop("A")
    row("B takes that session, not its folder",
        (taken.session, len(queue), "B" in queue), ("A", 2, True))

    queue.add(Event(session="A", kind=DONE, project="wobble",
                    window_hint="wobble", at=9.0))
    row("a session that signalled again is not restored over",
        (queue.restore(taken), queue.get("A").kind.value), (False, "done"))
    queue.drop_session("A")
    row("...and one that did not goes back",
        (queue.restore(taken), queue.get("A").kind.value), (True, "needs"))
    return ok


MUTANTS = [
    ("counting projects", CountsProjects),
    ("one line per project", OneLinePerProject),
    ("B taking the whole project out", DropsTheProject),
]


# --- task 47: what was pending before a restart comes back quiet -----------

class QuietByKind(Queue):
    """The ordering before task 47: kind and age, quiet or not."""

    def pending(self) -> list[Entry]:
        return sorted(super().pending(), key=lambda e: (e.rank, e.since))


class TopSignalsQuiet(Queue):
    """A top that hands the signal a quiet one when nothing live is waiting."""

    def top(self, *, quiet: bool = False) -> Entry | None:
        return super().top(quiet=True)


class CountsQuiet(Queue):
    """A title that counts the restored ones: a '3' up all day."""

    def live(self) -> int:
        return len(self)


class AddKeepsQuiet(Queue):
    """A new event that files over a quiet row and leaves it quiet."""

    def add(self, event: Event) -> Entry:
        was = self._waiting.get(event.session)
        entry = super().add(event)
        if was is not None and was.quiet:
            self._waiting[event.session] = dataclasses.replace(
                self._waiting[event.session], quiet=True)
        return self.get(event.session)


class RestoreWakes(Queue):
    """A snooze that brings a restored one back live, speaking."""

    def restore(self, entry: Entry, superseded: frozenset[str] = frozenset()) -> bool:
        woke = Entry(project=entry.project, window_hint=entry.window_hint, host=entry.host,
                     waiting=tuple(dataclasses.replace(w, quiet=False) for w in entry.waiting))
        return super().restore(woke, superseded)


RESTORED_MUTANTS = [
    ("a quiet needs sorted above a live done", QuietByKind),
    ("a quiet one at the top of what signals", TopSignalsQuiet),
    ("the title counting the quiet ones", CountsQuiet),
    ("a new event leaving it quiet", AddKeepsQuiet),
    ("a snooze bringing it back live", RestoreWakes),
]


def restored(make, quiet: bool = False) -> bool:
    """The whole of task 47's queue half, run against `make()`."""
    ok = True

    def row(what: str, got, want) -> None:
        nonlocal ok
        good = got == want
        ok &= good
        if not quiet:
            print(f"  {what:<52} {'ok' if good else f'<-- WRONG: {got!r}, wanted {want!r}'}")

    queue = make()
    # Before the restart: A blocked, then B finished. Read back, then hushed.
    for session, kind, at in (("A", NEEDS, 0.0), ("B", DONE, 1.0)):
        queue.add(Event(session=session, kind=kind, project=f"p-{session}",
                        window_hint=f"win-{session}", at=at))
    row("hush says how many it quieted", queue.hush(), 2)
    # After it: C finishes. Later than both and a lower kind than A, so only
    # the quiet rule can put it first.
    queue.add(Event(session="C", kind=DONE, project="p-C", window_hint="win-C", at=5.0))
    row("a live done above a quiet needs", order(queue), ["C", "A", "B"])
    row("…and the title counts only the live one", queue.live(), 1)
    row("…while every one is still pending", len(queue), 3)
    queue.drop_session("C")
    row("nothing live: nothing to signal", queue.top(), None)
    row("…but B's question still finds the first quiet one",
        getattr(queue.top(quiet=True), "session", None), "A")
    taken = queue.drop("B")
    queue.restore(taken)
    row("a quiet one put back stays quiet", getattr(queue.get("B"), "quiet", None), True)
    queue.add(Event(session="A", kind=NEEDS, project="p-A", window_hint="win-A", at=9.0))
    row("a new event from it makes it live", getattr(queue.top(), "session", None), "A")
    row("…and counted", queue.live(), 1)
    return ok


def order(queue: Queue) -> list[str]:
    return [e.session for e in queue.pending()]


def blind(queue: Queue) -> list[str]:
    """The control: age alone, priority thrown away."""
    return [e.session for e in sorted(queue.pending(), key=lambda e: e.since)]


def refuses(what: str, call, exc) -> bool:
    try:
        call()
    except exc:
        print(f"  {what:<52} refused, as it should")
        return True
    print(f"  {what:<52} <-- WENT THROUGH, and must not have")
    return False


# What `src/core/` may not import, and why each one is on the list. CLAUDE.md
# states the rule in prose; this is the mechanical half, because a prose rule is
# the one that loses to a convenient import at 11pm.
FORBIDDEN = {
    "bleak": "the radio",
    "AppKit": "an OS", "Foundation": "an OS", "Cocoa": "an OS", "objc": "an OS",
    "rumps": "a menu bar",
    "subprocess": "osascript by the back door",
    "time": "a clock — the core takes `now` as an argument, so ordering is a "
            "property of the data and a ten-minute story runs instantly",
}
FORBIDDEN_PREFIXES = {
    "src.ball": "a mirror's protocol",
    "src.mirrors": "a mirror",
    "src.platform_seam.macos": "the seam's macOS half",
}


def core_imports_nothing_os_shaped() -> bool:
    """The seam rule, enforced instead of stated (CLAUDE.md, principle 6)."""
    bad = []
    paths = sorted(glob.glob(str(Path(__file__).resolve().parents[2] / "src/core/*.py")))
    if not paths:                   # an empty glob would pass this vacuously (task 74)
        bad.append("no src/core/*.py found at all")
    for path in paths:
        tree = ast.parse(open(path).read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                root = name.split(".")[0]
                why = FORBIDDEN.get(root) or next(
                    (w for p, w in FORBIDDEN_PREFIXES.items() if name.startswith(p)), None)
                if why:
                    bad.append(f"{path.split('/')[-1]} imports {name} ({why})")
    for line in bad:
        print(f"  {line:<52} <-- MUST NOT")
    if not bad:
        print(f"  {'src/core imports nothing OS-shaped, and no clock':<52} ok")
    return not bad


def main() -> int:
    print(__doc__.strip().splitlines()[0])
    print(f"\n  {'case':<40} {'want':<20} {'got':<20} kind-blind")
    ok = True
    toothless = []
    for name, script, want, size, tests_priority in CASES:
        queue = build(script)
        got = order(queue)
        control = blind(queue)
        good = got == want and len(queue) == size
        ok &= good
        print(f"  {name:<40} {str(want):<20} {str(got):<20} {control}"
              f"{'' if good else '   <-- WRONG'}")
        if tests_priority and control == want:
            toothless.append(name)

    print()
    first = build(CASES[3][1])
    top = first.top()
    ok &= top is not None and top.session == "C"
    print(f"  {'top() is the first of pending()':<52} "
          f"{'ok' if top and top.session == 'C' else '<-- WRONG'}")
    empty = build([])
    ok &= empty.top() is None and len(empty) == 0
    print(f"  {'an empty queue has no top and no length':<52} "
          f"{'ok' if empty.top() is None and not len(empty) else '<-- WRONG'}")

    queue = build([("A", NEEDS, 0.0), ("B", DONE, 1.0)])
    dropped = queue.drop("A")
    missing = queue.drop("nobody")
    good = dropped is not None and dropped.session == "A" and missing is None and len(queue) == 1
    ok &= good
    print(f"  {'drop returns the entry, and None for a stranger':<52} "
          f"{'ok' if good else '<-- WRONG'}")

    entry = queue.top()
    ok &= refuses("an entry cannot be edited by a mirror",
                  lambda: setattr(entry, "project", "x"),
                  dataclasses.FrozenInstanceError)
    # A derived one refuses too, but through the slots machinery rather than the
    # dataclass's own `__setattr__`, so the exception is not the same one. Found
    # on 2026-09-23 when `kind` became a property: the old row asserted
    # `FrozenInstanceError` and got a `TypeError` out of CPython's frozen+slots
    # `super()` call. Still refused, which is all a mirror needs to be told.
    ok &= refuses("...and neither can a derived one",
                  lambda: setattr(entry, "kind", NEEDS),
                  (dataclasses.FrozenInstanceError, AttributeError, TypeError))
    ok &= refuses("an event with no session id",
                  lambda: Event(session="", kind=DONE, project="p", at=0.0), ValueError)
    ok &= refuses("an event with no project to be filed under",
                  lambda: Event(session="A", kind=DONE, project="", at=0.0), ValueError)
    ok &= refuses("a kind that is a bare string",
                  lambda: Event(session="A", kind="done", project="p", at=0.0), TypeError)

    print()
    ok &= together(Queue)
    print()
    for what, mutant in MUTANTS:
        caught = not together(mutant, quiet=True)
        ok &= caught
        print(f"  mutant: {what:<44} "
              f"{'caught' if caught else '<-- SURVIVED, so the table proves nothing'}")

    print("\n  task 47: back from before a restart, quietly")
    ok &= restored(Queue)
    print()
    for what, mutant in RESTORED_MUTANTS:
        caught = not restored(mutant, quiet=True)
        ok &= caught
        print(f"  mutant: {what:<44} "
              f"{'caught' if caught else '<-- SURVIVED, so the table proves nothing'}")

    print()
    ok &= core_imports_nothing_os_shaped()

    if toothless:
        ok = False
        print(f"\n  these cases claim to test priority but their kind-blind control "
              f"agrees with them,\n  so they would pass with the rule deleted: {toothless}")
    else:
        print("\n  every priority case disagrees with its kind-blind control — "
              "the rule is what orders them")

    print("\n" + ("ALL CASES MATCH the known answer" if ok
                  else "SOMETHING DOES NOT MATCH — the rows above, not this line"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
