#!/usr/bin/env python3
"""Check that a signal goes quiet while you are looking at it — and comes back.

    venv/bin/python3 tests/tables/check_watching.py      # takes about 20 seconds
    venv/bin/python3 tests/tables/check_watching.py --scripted   # the suite's way (task 80)

"If I am still focused on the terminal, no need to notify" is three pieces in
three layers, and each one can be right while the whole thing does nothing:

  - the seam reads the title of the window in front (`macos.Frontmost.title`)
  - the core decides whether that is this session's window (`Entry.in_window`)
  - the daemon's signaller plays nothing while it is, **and stops its clock**

The third is the one that is easy to get wrong in a way nobody notices. Staying
quiet is not the same as being used up: a `done` you watched arrive has not
cried yet, so it must cry the moment you look away rather than having spent both
its beats in silence while you read the output. The rows below take a timeline
apart second by second to ask that, which is a thing no amount of sitting at the
desk can see happening.

**The failure this whole file is really guarding is the silent no-op.** Every
layer can be correct and the feature still never fire, because a terminal that
does not put the folder name in its window title matches nothing — and the only
symptom is notifications that keep arriving, which is also what it looks like
when the feature is switched off. So Part 4 runs the real daemon and the real
seam against the window actually in front of this desk right now, with a
reference leg beside it that MUST make a noise. Both quiet means the check
learnt about itself, not about the daemon.

**The control is ten mutants**, three of them on the safety direction: not
knowing what is in front must never be able to silence a signal (principle 7).
Each must break the table, or the table is not testing what it says it is.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "tables"))

from sandbox import Sandbox                                           # noqa: E402
from src import hooks                                                 # noqa: E402
from src.core.ladder import load as load_ladder                      # noqa: E402
from src.core.signals import (DESKTOP, TERMINAL, VSCODE, WARP, Entry, Kind,  # noqa: E402
                              Waiting)
from src.daemon import Away, HeldAway, LookAway, Signaller            # noqa: E402
from src.platform_seam import macos                                   # noqa: E402
from src.platform_seam import null                                    # noqa: E402
from src.platform_seam import ports                                   # noqa: E402

# The same two codes `check_focus.py` met on a live desk: -25212
# (kAXErrorNoValue) from a window mid-close, -25200 (kAXErrorFailure) from an
# app that answers a question and then refuses the next one.
NO_VALUE, FAILURE = -25212, -25200

# Layer 0 is where application windows live. 24 is the menu bar's, and it is on
# screen at all times — so it is the thing a `_front_pid` that forgot to look at
# the layer would report as the window you are looking at, forever.
APP_LAYER, MENU_BAR_LAYER = 0, 24

# A folder name no window on any desk can carry. It is the reference leg: the
# daemon must make a noise for it, and a run where it does not has proved
# nothing about the leg that went quiet.
IMPOSSIBLE = "no-such-window-9f3a"

# The suite runs everything but what depends on this desk's screen: the locked
# row, Terminal's tab in front and the end-to-end legs. Those stay at the desk,
# where a run without them proves nothing about them (task 80).
SCRIPTED = "--scripted" in sys.argv[1:]

WORD = re.compile(r"[A-Za-z0-9_-]{4,}")


class Sheet:
    def __init__(self, quiet: bool = False):
        self.quiet, self.bad = quiet, 0

    def row(self, what: str, got, want) -> None:
        good = want(got) if callable(want) else got == want
        self.bad += not good
        if not self.quiet:
            print(f"    {what:<58} {'ok' if good else f'<-- WRONG: {got!r}'}")

    def blind(self, what: str, answer, *must_name: str) -> None:
        """It could not tell, and the sentence names every one of `must_name`.

        `(None, None)` is a different answer and this helper refuses it on
        purpose: it means "asked, and nothing is in front", which the caller
        reads as "carry on and signal". A layer that cannot see at all saying
        that would silence nothing and explain nothing — the shape a helper
        checking only `title is None` would wave straight through.
        """
        title, why = answer
        if title is not None:
            self._fail(what, f"it answered a title anyway: {title!r}")
            return
        if not why:
            self._fail(what, "could not tell, and said nothing about why")
            return
        missing = [name for name in must_name if name.casefold() not in why.casefold()]
        if missing:
            self._fail(what, f"could not tell without naming {missing}: {why}")
            return
        if not self.quiet:
            print(f"    {what:<58} blind, naming {list(must_name)}")

    def _fail(self, what: str, detail: str) -> None:
        self.bad += 1
        if not self.quiet:
            print(f"    {what:<58} <-- {detail}")

    def ok(self) -> bool:
        return not self.bad


# --- the seam ---------------------------------------------------------------

class FakeFront:
    """The window server and the Accessibility API, as much as `title()` uses.

    A whole-module substitute rather than a patched method, the same way
    `check_focus.py` does it, so nothing of ours leaks into the thing our branch
    is being checked against. `titles` maps a pid to the title of its focused
    window; a pid missing from it is an app with no focused window at all.
    """

    kCGWindowListOptionOnScreenOnly = 1
    kCGWindowListExcludeDesktopElements = 16
    kCGNullWindowID = 0
    kCGWindowLayer = "kCGWindowLayer"
    kCGWindowOwnerPID = "kCGWindowOwnerPID"
    kAXFocusedWindowAttribute = "AXFocusedWindow"
    kAXTitleAttribute = "AXTitle"

    def __init__(self, windows, titles, *, trusted=True, locked=False,
                 focused_err=0, title_err=0):
        self.windows, self.titles = windows, titles
        self.trusted, self.locked = trusted, locked
        self.focused_err, self.title_err = focused_err, title_err
        self.timeouts: list = []
        self.options: list = []
        self.asked = 0
        self.listed = 0

    def AXIsProcessTrusted(self):
        return self.trusted

    def CGSessionCopyCurrentDictionary(self):
        # `locked=None` is the third answer macOS gives: no window server
        # session at all, which is not a locked screen.
        if self.locked is None:
            return None
        return {"CGSSessionScreenIsLocked": self.locked}

    def CGWindowListCopyWindowInfo(self, option, relative):
        self.listed += 1
        self.options.append((option, relative))
        return list(self.windows)

    def AXUIElementCreateApplication(self, pid):
        return ("app", pid)

    def AXUIElementSetMessagingTimeout(self, element, seconds):
        self.timeouts.append((element, seconds))

    def AXUIElementCopyAttributeValue(self, element, attribute, _placeholder):
        self.asked += 1
        if attribute == self.kAXFocusedWindowAttribute:
            if self.focused_err:
                return self.focused_err, None
            return (0, ("win", element[1])) if element[1] in self.titles else (0, None)
        if attribute == self.kAXTitleAttribute:
            if self.title_err:
                return self.title_err, None
            return 0, self.titles[element[1]]
        raise AssertionError(f"nothing asks for {attribute}")


def on_screen(pid: int, layer: int = APP_LAYER) -> dict:
    return {"kCGWindowLayer": layer, "kCGWindowOwnerPID": pid}


def install(windows, titles, **kwargs) -> FakeFront:
    ax = FakeFront(windows, titles, **kwargs)
    macos._AX, macos._AX_WHY = ax, None
    macos._AX_MISSING, macos._AX_TRIED = None, True
    return ax


def desk(**kwargs) -> FakeFront:
    """The desk this check pretends to be sitting at, front to back.

    The menu bar is first on purpose: the window server really does hand it back
    ahead of everything else, and it is on screen while you look at any window
    at all. An implementation that took the first row would read it as what you
    are looking at for the whole life of the process.
    """
    return install(
        [on_screen(99, MENU_BAR_LAYER), on_screen(30), on_screen(40)],
        {30: "Install_hooks.py — wobble", 40: "x — other-repo"}, **kwargs)


class NoApplicationServices:
    """A real ImportError for a real import, from Python's own machinery."""

    def find_spec(self, name, path=None, target=None):
        if name == "ApplicationServices":
            raise ImportError("blocked at the desk — pretending it was never installed")
        return None


def seam_rows(make, quiet: bool = False) -> bool:
    sheet = Sheet(quiet)

    if not quiet:
        print("\n  the seam — the title of the window in front, and nothing more")
    ax = desk()
    sheet.row("the front window's title, with no sentence beside it",
              make(macos.Frontmost()).title(), ("Install_hooks.py — wobble", None))
    sheet.row("…the menu bar above it was walked past, not read",
              ax.timeouts, [(("app", 30), macos._FRONT_APP_S)])
    sheet.row("…and the window server was asked for on-screen windows only",
              ax.options, [(FakeFront.kCGWindowListOptionOnScreenOnly
                            | FakeFront.kCGWindowListExcludeDesktopElements,
                            FakeFront.kCGNullWindowID)])

    install([on_screen(40), on_screen(30)],
            {30: "Install_hooks.py — wobble", 40: "x — other-repo"})
    sheet.row("the front one is the front one, not a favourite",
              make(macos.Frontmost()).title(), ("x — other-repo", None))

    if not quiet:
        print("\n  …and every way it cannot tell, told apart from 'nothing is there'")
    ax = desk(locked=True)
    sheet.row("a locked screen names no window",
              make(macos.Frontmost()).title(), (None, None))
    # macOS answers every title as its own app's name while locked, so a folder
    # called `Code` would read as the window in front for as long as nobody was
    # at the desk — which is exactly when a notification matters. Asking nothing
    # is the check, not answering None: a refusal that still reads titles is a
    # failure that happened to return the right value.
    sheet.row("…and it did not go looking at titles it cannot trust",
              (ax.listed, ax.asked), (0, 0))

    desk(locked=None)
    sheet.row("no window server session at all is not a locked screen",
              make(macos.Frontmost()).title(), ("Install_hooks.py — wobble", None))

    install([on_screen(99, MENU_BAR_LAYER)], {})
    sheet.row("nothing but overlays on screen is nothing in front",
              make(macos.Frontmost()).title(), (None, None))

    install([on_screen(30)], {})
    sheet.row("an app with no focused window is nothing in front",
              make(macos.Frontmost()).title(), (None, None))

    desk(focused_err=NO_VALUE)
    sheet.row("an app that refuses to name its focused window",
              make(macos.Frontmost()).title(), (None, None))

    desk(title_err=FAILURE)
    sheet.row("an app that hands over a window and refuses its title",
              make(macos.Frontmost()).title(), (None, None))

    install([on_screen(30)], {30: ""})
    sheet.row("an empty title is not a title",
              make(macos.Frontmost()).title(), (None, None))

    # The one refusal that carries a sentence, because it is the one somebody
    # can do something about — and a signal that plays when it should not is a
    # thing to explain, not a thing to hide.
    ax = desk(trusted=False)
    sheet.blind("Accessibility refused", make(macos.Frontmost()).title(),
                "Accessibility", "System Settings", "will be played")
    sheet.row("…and the refusal touched nothing at all",
              (ax.listed, ax.asked), (0, 0))

    return sheet.ok()


# --- the core ---------------------------------------------------------------

def entry(hint: str, kind: Kind = Kind.DONE) -> Entry:
    """One session waiting — the shape since task 41.

    The window hint is the only thing these rows are about, so the entry is
    built by hand rather than through a `Queue`: a check that went through the
    queue to reach `in_window` would fail for two different reasons at once.
    """
    return Entry(project="p", window_hint=hint,
                 waiting=(Waiting(session="S", kind=kind, project="p",
                                  window_hint=hint, since=0.0, at=0.0),))


def core_rows(match, quiet: bool = False) -> bool:
    sheet = Sheet(quiet)
    if not quiet:
        print("\n  the core — is that title this session's window?")
    sheet.row("the folder name inside a longer title",
              match(entry("wobble"), "Install_hooks.py — wobble"), True)
    sheet.row("case is not what tells two projects apart",
              match(entry("WoBBle"), "install_hooks.py — wobble"), True)
    sheet.row("a title that is exactly the folder name",
              match(entry("wobble"), "wobble"), True)
    sheet.row("another project's window is not this one",
              match(entry("wobble"), "server.ts — quarry"), False)

    if not quiet:
        print("\n  …and every unknown falls the safe way — never into silence")
    sheet.row("nobody could be asked what is in front",
              match(entry("wobble"), None), False)
    sheet.row("nothing is in front", match(entry("wobble"), ""), False)
    sheet.row("a signal carrying no window hint at all",
              match(entry(""), "Install_hooks.py — wobble"), False)
    sheet.row("…or a hint that is only spaces",
              match(entry("   "), "Install_hooks.py — wobble"), False)
    return sheet.ok()


def hosted(hint: str, host: str) -> Entry:
    """`entry`, from a session that knows the app it runs in (task 38)."""
    return Entry(project="p", window_hint=hint, host=host,
                 waiting=(Waiting(session="S", kind=Kind.DONE, project="p",
                                  window_hint=hint, since=0.0, at=0.0, host=host),))


def host_rows(match, quiet: bool = False) -> bool:
    """The app first, then the title — the real titles of 2026-09-28's desk."""
    sheet = Sheet(quiet)
    if not quiet:
        print("\n  the app it runs in (task 38) — a title alone is shared")
    vs = hosted("wobble", VSCODE)
    sheet.row("VS Code: the folder is the last segment",
              match(vs, "entendi - teste 19 — wobble", VSCODE), True)
    sheet.row("VS Code: another folder's tab that says the word",
              match(vs, "Wobble needs setup — pokeball", VSCODE), False)
    sheet.row("VS Code: a window with no tab is just the folder",
              match(vs, "wobble", VSCODE), True)
    sheet.row("a terminal in front with this folder's title is not VS Code",
              match(vs, "zsh — wobble", "com.apple.Terminal"), False)
    sheet.row("the front app unknown: the title alone decides",
              match(vs, "entendi - teste 19 — wobble", None), True)
    sheet.row("a line with no host keeps the substring it had",
              match(entry("wobble"), "Wobble needs setup — pokeball", VSCODE), True)
    sheet.row("an unmeasured host keeps the substring, in its own app",
              match(hosted("wobble", "com.apple.Terminal"), "wobble — -zsh — 80×24",
                    "com.apple.Terminal"), True)
    return sheet.ok()


def twin_rows(match, quiet: bool = False) -> bool:
    """Two Claude tabs in one VS Code window (task 43): the active one is watched."""
    sheet = Sheet(quiet)
    if not quiet:
        print("\n  two sessions in one VS Code window (task 43) — the tab in front")
    vs = hosted("wobble", VSCODE)
    # The desk's own case, 2026-09-28: a renamed session owns its custom title
    # and its ai-title; a new one owns its ai-title and a registry name its tab
    # never shows.
    oi = frozenset({"Oi", "Pokeball slots"})
    tabs = oi | {"Session planning", "wobble-b8"}
    sheet.row("its own tab in front: watched",
              match(vs, "Oi — wobble", VSCODE, oi, tabs), True)
    sheet.row("…by any title it owns, not only the first",
              match(vs, "Pokeball slots — wobble", VSCODE, oi, tabs), True)
    sheet.row("the twin's tab in front: not watched, so it signals",
              match(vs, "Session planning — wobble", VSCODE, oi, tabs), False)
    sheet.row("a file in front: the folder rule, Claude may be beside it",
              match(vs, "tasks.md — wobble", VSCODE, oi, tabs), True)
    sheet.row("its own titles unknown: a twin's tab is still not it",
              match(vs, "Session planning — wobble", VSCODE, frozenset(), tabs), False)
    sheet.row("its own tab in another folder's window: not watched",
              match(vs, "Oi — pokeball", VSCODE, oi, tabs), False)
    sheet.row("a Terminal title that says a tab name is not VS Code's rule",
              match(hosted("wobble", "com.apple.Terminal"), "Session planning — wobble",
                    "com.apple.Terminal", oi, tabs), True)

    # Warp (task 43): the daemon names each claude's tab `<project> · <id4>`,
    # and the window's title is the active tab's (2026-09-28, `quarry · d711`).
    if not quiet:
        print("\n  two sessions of one folder in Warp (task 43) — the tab the daemon named")
    wp = hosted("quarry", WARP)
    mine, named = frozenset({"quarry · d711"}), frozenset({"quarry · d711", "quarry · c431"})
    sheet.row("Warp: its own named tab in front: watched",
              match(wp, "quarry · d711", WARP, mine, named), True)
    sheet.row("Warp: the twin's named tab in front: not watched, so it signals",
              match(wp, "quarry · c431", WARP, mine, named), False)
    sheet.row("Warp: a tab the daemon never named: the folder rule",
              match(wp, "quarry", WARP, mine, named), True)
    sheet.row("Warp: its own name could not be written: a twin's is still not it",
              match(wp, "quarry · c431", WARP, frozenset(), named), False)
    return sheet.ok()


def terminal_rows(match, quiet: bool = False) -> bool:
    """Two claudes of one folder in Terminal (task 43): the tab's tty decides."""
    sheet = Sheet(quiet)
    if not quiet:
        print("\n  two sessions of one folder in Terminal (task 43) — the tab's tty")
    tm = hosted("quarry", TERMINAL)
    mine, claudes = frozenset({"ttys003"}), frozenset({"ttys003", "ttys005"})
    sheet.row("Terminal: its own tab in front: watched",
              match(tm, "quarry — claude — 80×24", TERMINAL, mine, claudes, "ttys003"), True)
    sheet.row("…even when claude's title names no folder",
              match(tm, "✳ Claude Code", TERMINAL, mine, claudes, "ttys003"), True)
    sheet.row("Terminal: the twin's tab in front: not watched, so it signals",
              match(tm, "quarry — claude — 80×24", TERMINAL, mine, claudes, "ttys005"), False)
    sheet.row("Terminal: a tab with no claude, in the folder: the folder rule",
              match(tm, "quarry — -zsh — 80×24", TERMINAL, mine, claudes, "ttys007"), True)
    sheet.row("Terminal: a tab with no claude, elsewhere: not watched",
              match(tm, "pokeball — -zsh — 80×24", TERMINAL, mine, claudes, "ttys007"), False)
    sheet.row("Terminal: its tab could not be read: the folder rule",
              match(tm, "quarry — claude — 80×24", TERMINAL, mine, claudes, None), True)
    sheet.row("Terminal: its own tty unknown: a twin's tab is still not it",
              match(tm, "quarry — claude — 80×24", TERMINAL, frozenset(), claudes, "ttys005"),
              False)
    sheet.row("Terminal's tty with Warp in front: the app comes first",
              match(tm, "quarry", WARP, mine, claudes, "ttys003"), False)
    sheet.row("a Warp session is not told apart by Terminal's tty",
              match(hosted("quarry", WARP), "quarry", WARP, mine, claudes, "ttys005"), True)
    return sheet.ok()


# --- the signaller's clock --------------------------------------------------

def timeline(make, kind: Kind, steps, ladder) -> list[tuple[float, str]]:
    """Run `(now, watched)` steps through one signaller and list when it beat.

    `due` answers one `Voice` or `None` now (task 35 — there is no pulse left
    to tell apart from a beat), so every non-`None` answer IS a beat. The
    label stays in the tuple only because the rows below still read
    `how == "beat"`, unchanged from when there were two kinds of answer.
    """
    signaller = make(Signaller(ladder))
    seen: Entry = entry("w", kind)
    played: list[tuple[float, str]] = []
    for now, watched in steps:
        voice = signaller.due(seen, now, watched=watched)
        if voice is not None:
            played.append((round(now, 2), "beat"))
    return played


def ticks(spans, step: float = 0.25) -> list[tuple[float, bool]]:
    """`[(seconds, watched), …]` turned into a poll every `step`, as the daemon polls."""
    out: list[tuple[float, bool]] = []
    at = 0.0
    for length, watched in spans:
        end = at + length
        while at < end - 1e-9:
            out.append((round(at, 4), watched))
            at = round(at + step, 4)
        at = round(end, 4)
    return out


def clock_rows(make, ladder, quiet: bool = False) -> bool:
    sheet = Sheet(quiet)
    beat_every = ladder.every[Kind.DONE]
    beats_allowed = ladder.times[Kind.DONE]

    if not quiet:
        print("\n  the clock — watched, it stops; looked away, it speaks")
    # Watched from the first second, for longer than the whole `done` schedule
    # would have taken. Nothing at all may play in that time: not the cry, and
    # not the silent flash either — the ball is in the same room as the screen.
    watched_through = 2 * beat_every + 20
    played = timeline(make, Kind.DONE,
                      ticks([(watched_through, True)]), ladder)
    sheet.row(f"a done watched for {watched_through:g}s plays nothing at all",
              played, [])

    # …and has NOT been used up by it. This is the whole difference between
    # staying quiet and spending the signal in silence while you read the
    # output: it has not cried yet, so it cries now.
    played = timeline(make, Kind.DONE,
                      ticks([(watched_through, True), (5.0, False)]), ladder)
    sheet.row("…and cries the moment you look away",
              [how for _, how in played[:1]], ["beat"])
    sheet.row("…at the second you looked, not one interval later",
              [when for when, _ in played[:1]], [watched_through])

    # A glance away and back is the symmetric failure: the signal that already
    # cried must not cry again the instant you stop looking, which is what a
    # freeze that never hands the time back produces.
    glance = 2 * beat_every
    played = timeline(make, Kind.DONE,
                      ticks([(0.5, False), (glance, True), (1.0, False)]), ladder)
    sheet.row(f"a cry, then {glance:g}s of watching, is not a second cry",
              [how for _, how in played], ["beat"])

    # The second cry falls its own interval after the first SPOKE, with the
    # watched seconds handed back rather than counted.
    played = timeline(
        make, Kind.DONE,
        ticks([(0.5, False), (glance, True), (beat_every + 2.0, False)]), ladder)
    sheet.row("…it falls one interval after the first, counting from the look away",
              [when for when, how in played if how == "beat"],
              [0.0, round(glance + beat_every, 4)])

    # And a done still speaks its configured number of times across all of it.
    # A freeze that forgot the beats already had would hand out more.
    played = timeline(
        make, Kind.DONE,
        ticks([(0.5, False), (glance, True), (0.5, False), (glance, True),
               (4 * beat_every, False)]), ladder)
    sheet.row(f"…and a done still cries exactly {beats_allowed}x across the lot",
              sum(how == "beat" for _, how in played), beats_allowed)

    # A needs never falls silent on its own (criterion 3), so what has to hold
    # for it is that watching does not turn into a burst when you look away.
    needs_every = ladder.every[Kind.NEEDS]
    played = timeline(make, Kind.NEEDS,
                      ticks([(20.0, True), (2 * needs_every, False)]), ladder)
    sheet.row("a needs watched for 20s plays nothing either",
              [when for when, _ in played if when < 20.0], [])
    sheet.row("…and comes back at its own pace, not as a burst",
              sum(1 for _, how in played), lambda v: v <= 3)

    # Nothing pending clears the watch too. Without this a signal watched and
    # then answered would hand its seconds to whatever came next.
    signaller = make(Signaller(ladder))
    seen = entry("w")
    signaller.due(seen, 0.0, watched=True)
    signaller.due(None, 10.0)
    sheet.row("an empty queue forgets it was being watched",
              signaller.watched_since, None)

    return sheet.ok()


def hold_rows(make, ladder, quiet: bool = False) -> bool:
    """The 5s after-prompt hold, and a key change resetting the schedule.

    Both are `due`'s business rather than `watched`'s: the hold delays a beat
    without stopping its clock (unlike `watched`, five seconds against a
    thirty second cadence buys nothing worth freezing for), and a key change
    is what lets a fallback speak at once instead of waiting out the schedule
    of the thing it replaced.
    """
    sheet = Sheet(quiet)
    if not quiet:
        print("\n  the hold — a hand that just typed buys the ball five seconds")

    hold = ladder.after_prompt_s
    signaller = make(Signaller(ladder))
    seen = entry("w", Kind.DONE)
    held = [signaller.due(seen, now, hold_until=hold) for now in (0.0, hold / 2)]
    sheet.row(f"a first beat held back for the whole {hold:g}s after a prompt",
              held, [None, None])
    sheet.row("…and fires the moment the hold lifts, not one interval later",
              signaller.due(seen, hold, hold_until=hold) is not None, True)

    if not quiet:
        print("\n  …and a different signal taking the floor does not wait out its schedule")
    signaller = make(Signaller(ladder))
    first = entry("w", Kind.DONE)
    signaller.due(first, 0.0)
    still_mid_schedule = signaller.due(first, 0.25)
    sheet.row("mid-schedule, the same kind is not due again yet",
              still_mid_schedule, None)
    second = entry("w", Kind.NEEDS)
    sheet.row("a different kind taking the floor speaks at once",
              signaller.due(second, 0.5) is not None, True)

    return sheet.ok()


def showing_rows(make, ladder, quiet: bool = False) -> bool:
    """`Signaller.showing` — the voice whose held light should be up right now."""
    sheet = Sheet(quiet)
    if not quiet:
        print("\n  the held light — dark before the cry, lit after it, dark while watched")

    sheet.row("nothing pending shows nothing",
              make(Signaller(ladder)).showing(None), None)

    seen = entry("w", Kind.DONE)
    signaller = make(Signaller(ladder))
    signaller.due(seen, 0.0)                          # the first beat, so a light exists
    sheet.row("watched shows nothing, even with a light already earned",
              signaller.showing(seen, watched=True), None)

    fresh = make(Signaller(ladder))
    sheet.row("before the first beat, still dark",
              fresh.showing(seen), None)
    hold = ladder.after_prompt_s
    fresh.due(seen, 0.0, hold_until=hold)              # never beats: the hold is still open
    sheet.row("…including a never-beaten signal under the after-prompt hold — "
              "its light must not arrive before its own cry",
              fresh.showing(seen), None)

    lit = signaller.showing(seen)
    sheet.row("the ladder's voice once it has beaten",
              (lit.effect in ladder.moods[Kind.DONE].pools["happy"], lit.light) if lit else lit, (True, 9))

    # `done` gets 2 beats, 30s apart (config/signals.json). Spend both and
    # confirm the light carries on once `due` has nothing further to give —
    # the whole point of the held light replacing the old pulse (task 35).
    every = ladder.every[Kind.DONE]
    signaller.due(seen, every)
    nothing_more_due = signaller.due(seen, 2 * every)
    sheet.row(f"nothing more due after its {ladder.times[Kind.DONE]} beats",
              nothing_more_due, None)
    sheet.row("…but the light carries on regardless",
              signaller.showing(seen) is not None, True)

    signaller.muted = True
    sheet.row("muted swaps the light's voice the same way it swaps the beat's",
              signaller.showing(seen).effect, ladder.mutes[Kind.DONE])
    signaller.muted = False

    sheet.row("watching it again goes dark",
              signaller.showing(seen, watched=True), None)
    sheet.row("…and looking away brings the voice back",
              signaller.showing(seen) is not None, True)

    return sheet.ok()


def look_away_rows(make, ladder, quiet: bool = False) -> bool:
    """Task 37: a window you just left still counts as looked at, for a while.

    Asked at the desk 2026-09-28 because a glance away and back was a light and
    a buzz each way. `make` builds the `LookAway` under test.
    """
    sheet = Sheet(quiet)
    if not quiet:
        print("\n  looking away — the window you left still counts, for a few seconds")
    wait = ladder.look_away_s
    sheet.row("the config gives it a wait at all", wait > 0, True)

    away = make(LookAway(wait))
    away.watched("w", True, 0.0)
    sheet.row(f"just after you leave, still looked at",
              away.watched("w", False, 1.0), True)
    sheet.row(f"…and a poll short of {wait:g}s, still",
              away.watched("w", False, 1.0 + wait - 0.25), True)
    sheet.row(f"…and at {wait:g}s, no longer",
              away.watched("w", False, 1.0 + wait), False)
    sheet.row("…and it stays that way while you stay away",
              away.watched("w", False, 1.0 + 2 * wait), False)

    away = make(LookAway(wait))
    away.watched("w", True, 0.0)
    away.watched("w", False, 1.0)
    away.watched("w", True, 2.0)                       # back inside the wait
    sheet.row("back inside the wait, then away again: the wait starts over",
              away.watched("w", False, 3.0 + wait - 0.25), True)

    away = make(LookAway(wait))
    away.watched("w", True, 0.0)
    sheet.row("another session at the top gets none of it",
              away.watched("x", False, 1.0), False)
    sheet.row("nothing at the top is nothing looked at",
              make(LookAway(wait)).watched(None, False, 0.0), False)
    sheet.row("never looked at, never counted as looked at",
              make(LookAway(wait)).watched("w", False, 0.0), False)
    sheet.row("a wait of zero is the old behaviour: away is away",
              (lambda a: (a.watched("w", True, 0.0), a.watched("w", False, 0.25)))(
                  make(LookAway(0.0))), (True, False))

    # The two pieces together, as the daemon runs them: a done that arrived
    # while you watched cries `wait` after you leave, not the moment you do.
    signaller, away = Signaller(ladder), make(LookAway(wait))
    seen = entry("w", Kind.DONE)
    cried = []
    for now, looking in ticks([(20.0, True), (2 * wait, False)]):
        if signaller.due(seen, now, watched=away.watched("w", looking, now)) is not None:
            cried.append(now)
    sheet.row(f"a done watched then left cries {wait:g}s after you leave",
              cried[:1], [20.0 + wait])

    return sheet.ok()


def glance_rows(make, ladder, quiet: bool = False) -> bool:
    """Task 67: a window passed through is not a window looked at.

    At the desk 2026-10-01 10:11:05 the done's own window was in front for
    under a second, and that was a 180 and then a 9 with its buzz.
    """
    sheet = Sheet(quiet)
    if not quiet:
        print("\n  a glance — a window counts as looked at only after a moment in front")
    glance, wait = ladder.glance_s, ladder.look_away_s
    sheet.row("the config gives a glance at all", glance > 0, True)

    sheet.row("in front since before it was pending: looked at at once",
              make(LookAway(wait, glance)).watched("w", True, 5.0, None), True)
    away = make(LookAway(wait, glance))
    sheet.row("come to the front just now: not yet", away.watched("w", True, 10.0, 10.0), False)
    sheet.row(f"…a poll short of {glance:g}s, still not",
              away.watched("w", True, 10.0 + glance - 0.25, 10.0), False)
    sheet.row(f"…at {glance:g}s, looked at", away.watched("w", True, 10.0 + glance, 10.0), True)

    away = make(LookAway(wait, glance))
    away.watched("w", True, 10.0, 10.0)
    sheet.row("passed through and gone: no grace, it was never looked at",
              away.watched("w", False, 10.5, 10.5), False)

    away = make(LookAway(wait, glance))
    away.watched("w", True, 0.0, None)
    sheet.row("already looked at, its title changes: still looked at",
              away.watched("w", True, 20.0, 20.0), True)
    away = make(LookAway(wait, glance))
    away.watched("w", True, 0.0, None)
    away.watched("w", False, 1.0, 1.0)
    sheet.row("back inside the wait: at once, no glance to wait out",
              away.watched("w", True, 2.0, 2.0), True)
    sheet.row("a glance of zero is the old behaviour: in front is looked at",
              make(LookAway(wait, 0.0)).watched("w", True, 10.0, 10.0), True)

    # The two pieces together, as the daemon runs them: when the light went out.
    def dark(spans) -> list[float]:
        signaller, away = Signaller(ladder), make(LookAway(wait, glance))
        seen, since, was, out = entry("w", Kind.DONE), None, None, []
        for now, looking in ticks(spans):
            if was is not None and looking != was:
                since = now
            was = looking
            watched = away.watched("w", looking, now, since)
            signaller.due(seen, now, watched=watched)
            if now >= 5.0 and signaller.showing(seen, watched=watched) is None:
                out.append(now)
        return out

    sheet.row("half a second in its window: its light never goes out",
              dark([(5.0, False), (0.5, True), (8.0, False)]), [])
    sheet.row(f"…two seconds there: dark from {glance:g}s in to {wait:g}s after leaving",
              (lambda d: (d[:1], d[-1:]))(dark([(5.0, False), (2.0, True), (8.0, False)])),
              ([5.0 + glance], [7.0 + wait - 0.25]))
    return sheet.ok()


def away_rows(make, ladder, quiet: bool = False) -> bool:
    """Task 67: back to the keys only after a long time away, or the Mac asleep that long.

    Each poll is `(idle_s, wall, mono)`. `time.monotonic` is mach_absolute_time
    on this Mac and stops in sleep, so a sleep is the wall running ahead of it.
    """
    sheet = Sheet(quiet)
    if not quiet:
        print("\n  back — after a long time away, or the Mac asleep, not after a minute")
    away_s = ladder.moods[Kind.DONE].greet_away_s
    sheet.row("the config gives a time away at all", away_s, 900.0)

    def run(polls, away_s=away_s):
        away = make(Away(away_s))
        return [away.back(idle, wall, mono) for idle, wall, mono in polls]

    sheet.row("a minute away, then a key: not back — a minute is the soft's",
              run([(59, 0, 0), (61, 2, 2), (0, 3, 3)])[-1], None)
    sheet.row(f"{away_s:g}s away, then a key: back, and why",
              run([(away_s - 1, 0, 0), (away_s + 1, 2, 2), (0, 3, 3)])[-1],
              f"{away_s + 1:.0f}s with no key or mouse")
    sheet.row("…once, not on every poll after",
              run([(away_s + 1, 0, 0), (0, 1, 1), (0.5, 2, 2), (0, 3, 3)])[2:], [None, None])
    sheet.row("away and still away: not back yet",
              run([(away_s + 1, 0, 0), (away_s + 2, 1, 1)])[-1], None)
    sheet.row("the Mac asleep an hour, woken by a key: back at once",
              run([(5, 0, 0), (1, 3601, 1)])[-1], "the Mac slept 3600s")
    sheet.row("…idle counting through the sleep: back at the first touch",
              run([(5, 0, 0), (3605, 3601, 1), (0, 3602, 2)]),
              [None, None, "the Mac slept 3600s"])
    sheet.row("asleep for less than the time away: not back",
              run([(5, 0, 0), (1, 601, 1)])[-1], None)
    sheet.row("a slow poll is not a sleep: both clocks moved",
              run([(5, 0, 0), (1, 3600, 3600)])[-1], None)
    sheet.row("nothing pending in between: the time away is forgotten",
              run([(away_s + 1, 0, 0), (None, 1, 1), (0, 2, 2), (0, 3, 3)])[2:], [None, None])
    sheet.row("a time away of zero: never back",
              run([(5, 0, 0), (1, 3601, 1)], away_s=0.0)[-1], None)
    return sheet.ok()


def here_rows(match, quiet: bool = False) -> bool:
    """Tasks 51, 52: where you are while a signal is held — the desktop app counts whole."""
    sheet = Sheet(quiet)
    if not quiet:
        print("\n  still at the held one (tasks 51, 52) — the desktop app is the app itself")
    app = hosted("my-workspace", DESKTOP)
    sheet.row("the Claude app in front, titled 'Claude': still there",
              match(app, "Claude", DESKTOP), True)
    sheet.row("…VS Code in front: left, whatever its title says",
              match(app, "notes — my-workspace", VSCODE), False)
    sheet.row("…the front app unknown: not there",
              match(app, "Claude", None), False)
    vs = hosted("wobble", VSCODE)
    sheet.row("VS Code keeps its window rule: its folder, still there",
              match(vs, "entendi - teste 19 — wobble", VSCODE), True)
    sheet.row("…another folder's window: left",
              match(vs, "server.ts — quarry", VSCODE), False)
    return sheet.ok()


def held_away_rows(make, ladder, quiet: bool = False) -> bool:
    """Task 52: away from the held one's window for a glance's grace, raised or not."""
    sheet = Sheet(quiet)
    if not quiet:
        print("\n  away from the held one — after the grace, whether or not it came forward")
    wait = ladder.look_away_s
    away = make(HeldAway(wait))
    sheet.row("its window never came forward: not yet at first",
              away.away("w", False, 0.0), False)
    sheet.row(f"…a poll short of {wait:g}s, not yet", away.away("w", False, wait - 0.25), False)
    sheet.row(f"…{wait:g}s: away, since nobody answers where they are not",
              away.away("w", False, wait), True)
    away = make(HeldAway(wait))
    away.away("w", True, 0.0)
    sheet.row("in front, then away: not yet", away.away("w", False, 1.0), False)
    sheet.row(f"…a poll short of {wait:g}s away, not yet",
              away.away("w", False, 1.0 + wait - 0.25), False)
    sheet.row(f"…{wait:g}s away: away", away.away("w", False, 1.0 + wait), True)
    sheet.row("…and back in front: not away any more", away.away("w", True, 2.0 + wait), False)

    away = make(HeldAway(wait))
    away.away("w", True, 0.0)
    away.away("w", False, 1.0)
    away.away("w", True, 2.0)                          # a glance, and back
    sheet.row("a glance away and back: the grace starts over",
              away.away("w", False, 3.0 + wait - 0.25), False)

    away = make(HeldAway(wait))
    away.away("w", False, 0.0)
    away.away("w", False, wait)
    away.reset()
    sheet.row("a new hold gets its own grace",
              (away.away("w", False, wait + 1.0), away.away("w", False, 2 * wait + 1.0)),
              (False, True))
    away = make(HeldAway(wait))
    away.away("w", False, 0.0)
    sheet.row("another session held gets its own grace too",
              (away.away("w", False, wait), away.away("x", False, wait + 0.5)),
              (True, False))
    return sheet.ok()


# --- the mutants ------------------------------------------------------------

class NeverSaysWhy(macos.Frontmost):
    def title(self):
        got, _ = super().title()
        return got, None


class AlwaysTrusted(macos.Frontmost):
    def _trusted(self, ax):
        return True


class IgnoresTheLock(macos.Frontmost):
    def _locked(self, ax):
        return False


class TakesTheTopWindow(macos.Frontmost):
    def _front_pid(self, ax):
        windows = ax.CGWindowListCopyWindowInfo(
            ax.kCGWindowListOptionOnScreenOnly
            | ax.kCGWindowListExcludeDesktopElements, ax.kCGNullWindowID) or []
        for window in windows:
            return int(window.get(ax.kCGWindowOwnerPID, 0)) or None
        return None


def unknown_is_quiet(e: Entry, title):
    return True if title is None else e.in_window(title)


def any_hint_matches(e: Entry, title):
    return True if not e.window_hint.strip() else e.in_window(title)


def title_only(e: Entry, title, app):
    return e.in_window(title)


def substring_everywhere(e: Entry, title, app):
    return (not (e.host and app and app != e.host) and bool(title)
            and e.window_hint.casefold() in title.casefold())


def folder_only(e: Entry, title, app, own, tabs):
    return e.in_window(title, app)


def tab_anywhere(e: Entry, title, app, own, tabs):
    """The tab rule applied in every app, not only VS Code."""
    if not e.in_window(title, app):
        return False
    tab = (title or "").rsplit(" — ", 1)[0].strip()
    return tab in own if tab in tabs else True


def vscode_only(e: Entry, title, app, own, tabs):
    """The tab rule in VS Code alone, as before Warp's tabs were named."""
    if not e.in_window(title, app):
        return False
    if e.host != VSCODE or " — " not in (title or ""):
        return True
    tab = title.rsplit(" — ", 1)[0].strip()
    return tab in own if tab in tabs else True


def first_title_only(e: Entry, title, app, own, tabs):
    """Owns one title, as if a session could only ever be shown by one name."""
    return e.in_window(title, app, own=frozenset(sorted(own)[:1]), tabs=tabs)


def tty_ignored(e: Entry, title, app, own, tabs, tty):
    """Terminal's tab never asked, as before task 43's Terminal part."""
    return e.in_window(title, app, own=own, tabs=tabs)


def title_before_tty(e: Entry, title, app, own, tabs, tty):
    """The folder must be in the title before the tty is looked at."""
    return e.names(title) and e.in_window(title, app, own=own, tabs=tabs, tty=tty)


def any_tty_decides(e: Entry, title, app, own, tabs, tty):
    """Every tty read taken as a claude's, so a plain shell tab signals."""
    return e.in_window(title, app, own=own, tabs=tabs | ({tty} if tty else set()), tty=tty)


def exact_only(e: Entry, title):
    return bool(title) and bool(e.window_hint.strip()) and \
        e.window_hint.casefold() == title.casefold()


class NeverFreezes(Signaller):
    def due(self, entry, now, *, watched=False):
        return super().due(entry, now, watched=False)


class SpendsTheTime(Signaller):
    def due(self, entry, now, *, watched=False):
        # Quiet while watched, but the seconds go on being counted — the bug
        # that looks identical at the desk and eats the signal in silence.
        self.watched_since = None
        return None if watched else super().due(entry, now, watched=False)


class ForgetsTheBeats(Signaller):
    def due(self, entry, now, *, watched=False):
        if not watched and self.watched_since is not None:
            self.beats = 0
        return super().due(entry, now, watched=watched)


class NoGrace(LookAway):
    def watched(self, session, looking, now):
        return session is not None and looking


class GraceForAnyone(LookAway):
    """Keeps the grace when the top of the queue changes hands."""

    def watched(self, session, looking, now):
        if session is not None and self.session is not None and not looking:
            session = self.session
        return super().watched(session, looking, now)


class GraceNeverRestarts(LookAway):
    """Remembers the first time you left, not the last."""

    def watched(self, session, looking, now):
        left = self.left_at
        answer = super().watched(session, looking, now)
        if looking and left is not None:
            self.left_at = left
        return answer


class GlanceCounts(LookAway):
    """Any moment in front is a look, as before task 67."""

    def watched(self, session, looking, now, front_since=None):
        return super().watched(session, looking, now, None)


class FirstReadWaits(LookAway):
    """A window already in front is treated as just arrived."""

    def watched(self, session, looking, now, front_since=None):
        if front_since is None and self.session is None and looking:
            self.first = getattr(self, "first", now)
            front_since = self.first
        return super().watched(session, looking, now, front_since)


class EveryChangeWaits(LookAway):
    """The glance waited out even by a session already looked at."""

    def watched(self, session, looking, now, front_since=None):
        if looking and front_since is not None and now < front_since + self.glance_s:
            return False
        return super().watched(session, looking, now, front_since)


class OldBack(Away):
    """Back only on an idle reading that drops from past the time away, as before task 67."""

    def back(self, idle_s, wall, mono):
        was, self.idle_was = self.idle_was, idle_s
        if (self.away_s and was is not None and idle_s is not None
                and was >= self.away_s > idle_s):
            return f"{was:.0f}s with no key or mouse"
        return None


class SleepUnseen(Away):
    def back(self, idle_s, wall, mono):
        return super().back(idle_s, wall, wall)


class BackEveryPoll(Away):
    def back(self, idle_s, wall, mono):
        why = self.why
        answer = super().back(idle_s, wall, mono)
        if answer is not None:
            self.why = why
        return answer


class NeverForgets(Away):
    def back(self, idle_s, wall, mono):
        if idle_s is None:
            self.clocks = (wall, mono)
            return None
        return super().back(idle_s, wall, mono)


class OnlyOnceSeen(HeldAway):
    """Task 51's gate: never away until its window had been in front."""

    def __init__(self, wait_s):
        super().__init__(wait_s)
        self.seen = False

    def reset(self):
        super().reset()
        self.seen = False

    def away(self, session, here, now):
        if session != self.session:
            self.seen = False
        self.seen |= here
        answer = super().away(session, here, now)
        return answer and self.seen


class AwayAtOnce(HeldAway):
    def away(self, session, here, now):
        answer = super().away(session, here, now)
        return answer or not here


class ResetForgetsNothing(HeldAway):
    def reset(self):
        pass


# --- naming a Warp tab, against a real terminal ------------------------------

def title_legs() -> bool:
    """The real seam's `Process.title`, on a pty this check owns (task 43).

    A child on a fresh pty, so what reaches the terminal is read back from the
    other end byte for byte, and no tab of the desk is touched. The legs that
    must refuse are asked too, and must leave the pty empty.
    """
    import pty
    import select
    print("\n  naming a tab — the real seam, on a pty of this check's own")
    sheet = Sheet()
    process = macos.Process()

    def drain(fd: int) -> bytes:
        got = b""
        while select.select([fd], [], [], 0.3)[0]:
            try:
                piece = os.read(fd, 4096)
            except OSError:
                break
            if not piece:
                break
            got += piece
        return got

    pid, master = pty.fork()
    if pid == 0:
        os.execv("/bin/sleep", ["sleep", "5"])
    try:
        drain(master)
        ok, why = process.title(pid, "quarry · d711")
        sheet.row("a tab named: said so", (ok, bool(why) and "named" in why), (True, True))
        sheet.row("…and the terminal got exactly one OSC 2 with the name",
                  drain(master), "\033]2;quarry · d711\007".encode())
        ok, why = process.title(pid, "quarry\007\033]2;evil")
        sheet.row("a name holding a control character is refused, in words",
                  (ok, bool(why) and "control character" in why), (False, True))
        sheet.row("…and nothing reached the terminal", drain(master), b"")
    finally:
        os.kill(pid, 9)
        os.waitpid(pid, 0)
        os.close(master)
    gone = subprocess.Popen(["/usr/bin/true"])
    gone.wait()
    ok, why = process.title(gone.pid, "quarry · d711")
    sheet.row("a pid that just exited names nothing, and says so",
              (ok, bool(why)), (False, True))
    sheet.row("with no platform, no tab is named, in words",
              null.Process().title(1, "x")[0] is False and bool(null.Process().title(1, "x")[1]),
              True)
    sheet.row("the real seam still satisfies Process",
              isinstance(process, ports.Process), True)
    return sheet.ok()


def front_tty_legs() -> bool:
    """The real seam's `Frontmost.tab_tty`, against Terminal as it is (task 43).

    The second source is `ps`: the tty answered must be a terminal something
    runs on, and one of Terminal's own tabs. Nothing on screen is changed.
    """
    print("\n  Terminal's tab in front — the real seam, read only")
    sheet = Sheet()
    front = macos.Frontmost()
    tty, why = front.tab_tty(TERMINAL)
    listed = subprocess.run(
        ["osascript", "-e", f'tell application id "{TERMINAL}" to '
                            f'if (count windows) > 0 then tty of tabs of windows'],
        capture_output=True, text=True).stdout
    if tty is None and why is None and "/dev/" not in listed:
        print("    (Terminal has no window, so only the empty answer is checked)")
        sheet.row("no Terminal window: asked, and nothing in front", (tty, why), (None, None))
    else:
        on = subprocess.run(["ps", "-t", tty or "none", "-o", "pid="],
                            capture_output=True, text=True).stdout.split()
        print(f"    Terminal's tab in front is on {tty}; {len(on)} process(es) on it")
        sheet.row("Terminal answered a tty, with no reason attached",
                  (bool(tty), why), (True, None))
        sheet.row("…one of Terminal's own tabs", f"/dev/{tty}" in listed, True)
        sheet.row("…and ps finds something running on it", len(on) >= 1, True)
    sheet.blind("a terminal with no known script is refused, in words",
                front.tab_tty(WARP), "no way is known")
    sheet.blind("with no platform, no tab is read, in words",
                null.Frontmost().tab_tty(TERMINAL), "no platform")
    return sheet.ok()


# --- against the real desk --------------------------------------------------

def live_hint(title: str | None) -> str | None:
    """A folder name that would match the window really in front right now.

    Derived from the live title rather than assumed, because whether a terminal
    puts its folder in its title is a fact about that terminal. The last word is
    taken: a terminal that names both a file and a folder puts the folder last.
    """
    words = WORD.findall(title or "")
    return words[-1] if words else None


def locked_now() -> bool:
    """Whether this desk is locked, asked of the real framework."""
    ax, _ = macos._ax()
    return ax is not None and macos.Frontmost()._locked(ax)


def raw_front_title() -> str | None:
    """The title macOS gives for the window in front, with no rule applied.

    The same two calls `title()` makes and none of its refusals, so what comes
    back is the raw answer the seam then decides what to do with. Only worth
    printing while the screen is locked, where the raw answer is the app's own
    name — the evidence for the branch that throws it away.
    """
    ax, _ = macos._ax()
    if ax is None:
        return None
    pid = macos.Frontmost()._front_pid(ax)
    if pid is None:
        return None
    element = ax.AXUIElementCreateApplication(pid)
    ax.AXUIElementSetMessagingTimeout(element, macos._FRONT_APP_S)
    err, window = ax.AXUIElementCopyAttributeValue(
        element, ax.kAXFocusedWindowAttribute, None)
    if err or window is None:
        return None
    err, title = ax.AXUIElementCopyAttributeValue(window, ax.kAXTitleAttribute, None)
    return None if err else str(title)


def end_to_end(sheet: Sheet, hint: str) -> None:
    """The real daemon, the real seam, and the window in front of this desk."""
    box = Sandbox()
    print(f"  events: {box.prove_isolated()}")
    daemon = subprocess.Popen(
        [sys.executable, "-m", "src.daemon",
         "--no-ball", "--no-menubar", "--poll", "0.1", "--events", str(box.events)],
        cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, bufsize=1,
        env={**os.environ, "PYTHONUNBUFFERED": "1"})

    # `--no-menubar` is not tidiness here, it is the case being checked. It
    # builds no NSApplication, so nothing pumps a run loop — and a `title()`
    # resting on `NSWorkspace`'s notification-fed cache would freeze at whatever
    # was in front when the process started and look entirely plausible doing it.
    time.sleep(1.5)
    box.fire("done", "LOUD", IMPOSSIBLE)
    time.sleep(2.5)
    box.fire("prompt", "LOUD", IMPOSSIBLE)
    time.sleep(0.8)
    # In the app that is in front, as a session you are looking at would be
    # (task 38): with no host the old substring rule would be all that ran.
    # Task 43: in VS Code a Claude tab in front is that session only, and any
    # other id is its twin and signals. So when the tab in front is a Claude
    # session, the quiet leg is that real session, found in the registry.
    title, app, _ = macos.Frontmost().window()
    tab = (title or "").rsplit(" — ", 1)[0].strip()
    titles = hooks.Titles()
    own = next((run.session for run in hooks.registry()
                if run.entrypoint == "claude-vscode"
                and tab in titles.of(run.session) | {run.name}), "QUIET")
    print(f"  the quiet leg is session {hooks.short(own)} (front {title!r}, {app})"
          + (f", the one whose tab {tab!r} is in front" if own != "QUIET" else ""))
    box.fire("done", own, hint, host=app or "")
    # Long enough for a cry and at least one flash after it, so silence here is
    # silence and not a gap between beats.
    time.sleep(8.0)
    box.fire("needs", "AFTER", IMPOSSIBLE)
    time.sleep(2.0)
    # Task 64: the real seam's idle decides whether a window in front still
    # counts, so a desk nobody touched turns the quiet leg loud for that reason.
    idle_s, idle_blind = macos.Idle().seconds()
    daemon.terminate()
    out = daemon.communicate(timeout=10)[0]

    print("\n" + "-" * 72)
    print(out.rstrip())
    print("-" * 72)

    lines = [" ".join(line.split()) for line in out.splitlines()]

    def first(token: str) -> int:
        return next((i for i, line in enumerate(lines) if token in line), len(lines))

    quiet_from = first(hint + " queued done")
    after_from = first(IMPOSSIBLE + " queued needs")
    between = lines[quiet_from:after_from]

    # Asked first, because every row below reads a slice bounded by these two
    # and a slice that is empty passes them all without looking at anything.
    sheet.row("both legs reached the daemon at all",
              (quiet_from < len(lines), after_from < len(lines)), (True, True))
    after = load_ladder().idle_s
    print(f"  idle at the end of the run: "
          f"{idle_blind if idle_s is None else f'{idle_s:.0f}s'} (counts after {after:g}s)")
    sheet.row("somebody was at the keys the whole run — else rerun, touching the mouse",
              idle_s is None or not after or idle_s < after, True)
    sheet.row("the reference leg makes a noise",
              sum("play (beat)" in line for line in lines[:quiet_from]),
              lambda v: v >= 1)
    sheet.row("…and the leg you are looking at plays nothing",
              [line for line in between if "play (" in line], [])
    sheet.row("…and says so, naming the window in front",
              sum("not signalling" in line for line in between), 1)
    sheet.row("…while the entry stays pending, not resolved",
              any("(2 pending)" in line for line in lines[after_from:]), True)
    sheet.row("a signal it is NOT looking at still speaks",
              sum("play (beat)" in line for line in lines[after_from:]),
              lambda v: v >= 1)
    sheet.row("nothing went blind on the way through",
              sum("CANNOT SEE FOCUS" in line for line in lines), 0)

    # The daemon's own startup line, read back as a second and structurally
    # different source for what is in front: this process asked AppKit, that one
    # asked it separately in its own address space. Agreement is the evidence;
    # a disagreement means the desk moved mid-run and the rows above are about
    # a window that is no longer there.
    said = next((line for line in lines if "In front right now:" in line), "")
    sheet.row("…and the daemon saw the same window this check did",
              hint.casefold() in said.casefold(), True)


def main() -> int:
    print(__doc__.strip().splitlines()[0])

    # Read live BEFORE anything fake is installed, and hold it: the rest of this
    # file replaces the whole framework behind the seam.
    live_title, live_why = (None, None) if SCRIPTED else macos.Frontmost().title()
    hint = live_hint(live_title)
    if SCRIPTED:
        print("\n  scripted: the legs that read this desk's screen are left to the desk")
    else:
        print(f"\n  in front of this desk right now: {live_title!r}"
              + (f"  ({live_why})" if live_why else ""))
    ok = True
    if not SCRIPTED and locked_now():
        # Not decoration, and not a fixture either. The rule it proves is the
        # one thing in `title()` that a fake cannot really test and that matters
        # most: macOS answers a window title as the name of its own app while
        # locked, so a project in a folder called `Code` or `Finder` would read
        # as the window in front for exactly as long as nobody is at the desk —
        # which is when a notification is for. Caught live, whenever the desk
        # happens to be in that state, against the real framework.
        sheet = Sheet()
        print(f"    …the screen is locked, and macOS would have answered "
              f"{raw_front_title()!r}")
        sheet.row("…so the seam refused it rather than believing it",
                  live_title, None)
        ok &= sheet.ok()

    ok &= seam_rows(lambda f: f)
    ok &= core_rows(lambda e, t: e.in_window(t))
    ok &= host_rows(lambda e, t, a: e.in_window(t, a))
    ok &= twin_rows(lambda e, t, a, o, s: e.in_window(t, a, own=o, tabs=s))
    ok &= terminal_rows(lambda e, t, a, o, s, y: e.in_window(t, a, own=o, tabs=s, tty=y))
    ladder = load_ladder()
    ok &= clock_rows(lambda s: s, ladder)
    ok &= hold_rows(lambda s: s, ladder)
    ok &= showing_rows(lambda s: s, ladder)
    ok &= look_away_rows(lambda a: a, ladder)
    ok &= glance_rows(lambda a: a, ladder)
    ok &= away_rows(lambda a: a, ladder)
    ok &= here_rows(lambda e, t, a: e.here(t, a))
    ok &= held_away_rows(lambda a: a, ladder)

    print("\n  the ports are the ports")
    sheet = Sheet()
    sheet.row("the real seam still satisfies Frontmost",
              isinstance(macos.Frontmost(), ports.Frontmost), True)
    sheet.row("…and so does the no-platform one",
              isinstance(null.Frontmost(), ports.Frontmost), True)
    # The no-platform answer is the could-not-tell one and not `(None, None)`,
    # and the difference is behaviour: `(None, None)` means "asked, nothing is
    # in front", which a headless box has no way to establish. Saying it would
    # silence nothing and explain nothing.
    sheet.blind("no platform says it cannot see, rather than 'nothing'",
                null.Frontmost().title(), "no platform", "played")
    ok &= sheet.ok()

    ok &= title_legs()
    if not SCRIPTED:
        ok &= front_tty_legs()

    print("\n  the framework missing — a real ImportError, not a pretend one")
    macos._AX, macos._AX_WHY = None, None
    macos._AX_MISSING, macos._AX_TRIED = None, False
    saved = sys.modules.pop("ApplicationServices", None)
    blocker = NoApplicationServices()
    sys.meta_path.insert(0, blocker)
    try:
        sheet = Sheet()
        # It must NOT say "no window was raised": that is `Focus`'s sentence for
        # `Focus`'s question, and handing it to somebody who asked what is in
        # front is a false sentence about a real failure.
        answer = macos.Frontmost().title()
        sheet.blind("it names the package to install",
                    answer, "pyobjc-framework-ApplicationServices", "which window is in front")
        # The phrase and not the word: this sentence ends "the session that
        # raised them", which is the signal and not a window, and a probe
        # looking for `raised` fails on the correct text. What must not appear
        # is `Focus`'s own sentence — a true statement about a real failure,
        # about the wrong question.
        sheet.row("…and does not borrow the sentence about raising a window",
                  "no window was raised" in (answer[1] or ""), False)
        # And the phrase above is still a phrase `Focus` actually says. Without
        # this the row is a guard that keeps passing after the wording it guards
        # against has been reworded — which is the same silent no-op this whole
        # file is about, one layer up.
        sheet.row("…and that sentence is one Focus really does hand out",
                  "no window was raised" in (macos._AX_WHY or ""), True)
        ok &= sheet.ok()
    finally:
        sys.meta_path.remove(blocker)
        if saved is not None:
            sys.modules["ApplicationServices"] = saved
        macos._AX, macos._AX_WHY = None, None
        macos._AX_MISSING, macos._AX_TRIED = None, False

    control = [
        ("the reason never given", lambda: seam_rows(lambda _f: NeverSaysWhy(), True)),
        ("the permission ignored", lambda: seam_rows(lambda _f: AlwaysTrusted(), True)),
        ("the locked screen ignored", lambda: seam_rows(lambda _f: IgnoresTheLock(), True)),
        ("the menu bar read as your window",
         lambda: seam_rows(lambda _f: TakesTheTopWindow(), True)),
        ("not knowing taken as looking", lambda: core_rows(unknown_is_quiet, True)),
        ("a signal with no hint silenced", lambda: core_rows(any_hint_matches, True)),
        ("the folder matched exactly, not inside", lambda: core_rows(exact_only, True)),
        ("the app never asked, as before task 38", lambda: host_rows(title_only, True)),
        ("VS Code read by substring, as before task 38",
         lambda: host_rows(substring_everywhere, True)),
        ("twins told apart by folder only, as before task 43",
         lambda: twin_rows(folder_only, True)),
        ("the tab rule used outside VS Code", lambda: twin_rows(tab_anywhere, True)),
        ("a session owning one title only", lambda: twin_rows(first_title_only, True)),
        ("Warp's named tab ignored, VS Code's rule only", lambda: twin_rows(vscode_only, True)),
        ("Terminal's tab never asked", lambda: terminal_rows(tty_ignored, True)),
        ("the folder required before the tty", lambda: terminal_rows(title_before_tty, True)),
        ("a shell tab's tty taken as a claude's", lambda: terminal_rows(any_tty_decides, True)),
        ("the clock never stopped",
         lambda: clock_rows(lambda _s: NeverFreezes(ladder), ladder, True)),
        ("the watched seconds spent anyway",
         lambda: clock_rows(lambda _s: SpendsTheTime(ladder), ladder, True)),
        ("the beats already had forgotten",
         lambda: clock_rows(lambda _s: ForgetsTheBeats(ladder), ladder, True)),
        ("looking away taken at once, as before task 37",
         lambda: look_away_rows(lambda a: NoGrace(a.wait_s), ladder, True)),
        ("the grace handed to whatever took the top",
         lambda: look_away_rows(lambda a: GraceForAnyone(a.wait_s), ladder, True)),
        ("the wait counted from the first time you left",
         lambda: look_away_rows(lambda a: GraceNeverRestarts(a.wait_s), ladder, True)),
        ("a glance taken as a look, as before task 67",
         lambda: glance_rows(lambda a: GlanceCounts(a.wait_s, a.glance_s), ladder, True)),
        ("a window already in front made to wait out a glance",
         lambda: glance_rows(lambda a: FirstReadWaits(a.wait_s, a.glance_s), ladder, True)),
        ("a window already looked at made to wait again",
         lambda: glance_rows(lambda a: EveryChangeWaits(a.wait_s, a.glance_s), ladder, True)),
        ("back on a minute's idle only, as before task 67",
         lambda: away_rows(lambda a: OldBack(a.away_s), ladder, True)),
        ("a sleep never seen", lambda: away_rows(lambda a: SleepUnseen(a.away_s), ladder, True)),
        ("back on every poll after", lambda: away_rows(lambda a: BackEveryPoll(a.away_s),
                                                       ladder, True)),
        ("the time away kept with nothing pending",
         lambda: away_rows(lambda a: NeverForgets(a.away_s), ladder, True)),
        ("the desktop app never here, as before task 51",
         lambda: here_rows(lambda e, t, a: e.in_window(t, a), True)),
        ("the desktop app here in any app",
         lambda: here_rows(lambda e, t, a: True if e.host == DESKTOP else e.here(t, a), True)),
        ("never away until its window came forward, as in task 51",
         lambda: held_away_rows(lambda a: OnlyOnceSeen(a.wait_s), ladder, True)),
        ("away at once, with no grace",
         lambda: held_away_rows(lambda a: AwayAtOnce(a.wait_s), ladder, True)),
        ("a new hold that inherits the old one's grace",
         lambda: held_away_rows(lambda a: ResetForgetsNothing(a.wait_s), ladder, True)),
    ]
    print(f"\n  the control — {len(control)} rules removed, each must break the table")
    for label, run in control:
        survived = run()
        ok &= not survived
        print(f"    {label:<58} "
              f"{'<-- SURVIVED, so the table does not test it' if survived else 'caught'}")

    # Put the real framework back before the daemon runs against it.
    macos._AX, macos._AX_WHY = None, None
    macos._AX_MISSING, macos._AX_TRIED = None, False

    print("\n  end to end — the real daemon against the window in front of you")
    sheet = Sheet()
    if SCRIPTED:
        print("    not run: scripted (DESK-CHECKS Part A runs it)")
    elif hint is None:
        # Not reported as a pass and not reported as a skip: a leg that did not
        # run has proved nothing, and the one failure this whole file guards is
        # a feature that quietly never fires.
        print(f"    {'nothing readable is in front, so these legs did NOT run':<58} "
              f"<-- {live_title!r}")
        print("    A locked screen reads as nothing in front, on purpose. Unlock it, "
              "click\n    a window whose title carries its folder name, and run this "
              "again.")
        ok = False
    else:
        print(f"    matching on {hint!r}, taken from the title above")
        end_to_end(sheet, hint)
        after, after_why = macos.Frontmost().title()
        same = live_hint(after) == hint
        sheet.row("…and the same window was still in front at the end", same, True)
        if not same:
            # Said in words because the row on its own reads as a defect in the
            # daemon, and it is not one: every row above was asked about a window
            # that is no longer there, so the run is void rather than failing.
            print(f"    the desk moved mid-run: {live_title!r} -> {after!r}"
                  + (f"  ({after_why})" if after_why else "")
                  + "\n    Nothing above is a verdict about the daemon — run it again "
                    "with that window in front.")
    ok &= sheet.ok()

    print("\n" + ("ALL CASES MATCH the known answer" if ok
                  else "SOMETHING DOES NOT MATCH — the rows above, not this line"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
