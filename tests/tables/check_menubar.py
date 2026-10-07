#!/usr/bin/env python3
"""Check the menu bar mirror without a menu bar: the title table, and the wiring.

    venv/bin/python3 tests/tables/check_menubar.py

`WOBBLE_PLATFORM=null` is set before the seam is imported, so every call the
mirror makes lands in `null.CALLS` instead of AppKit — the null half was built
to be exactly this fake, and a second one written here would be a fake of a
fake. What it proves is what the mirror ASKED FOR; that the ask reaches a real
status item is `macos.py`'s job and a by-hand check with the daemon running.

Thirteen claims, and each has a mutant that must break it:

  - the title says how many are pending, and says 'no ball' in words
  - …while the ball is not drawn: drawn, the title is the count alone, and
    the menu says the link's state and the battery, greyed, above the line
    that changes the link (task 63 — two more mutants)
  - 'you switched it off' and 'I cannot find it' are different sentences, because
    they ask the reader for opposite things
  - a connected ball shows what is left in it
  - the sounds being switched off is a word in the title and not only a line in
    the menu, because a mute you forgot about looks exactly like a dead daemon
  - …and that line says what the click will do, not what is true now
  - a beat with no ball plays the Mac's sound; the same beat with a ball plays
    nothing, because the ball is already speaking
  - a silent beat is silent on both surfaces
  - the menu offers one action about the ball, and it is the true one
  - it lists what is pending, in the order the core hands over, and choosing a
    line attends THAT session and not another
  - …and an empty queue is a line saying so, for the same reason the dot is
    hollow rather than absent
  - quit is the last line, in every state
  - …with a separator above it, because the line it would otherwise touch is the
    one that switches the ball's link
  - …and it is there in a `--no-ball` run too, where it is the only live line
  - what came back from before a restart is listed under a separator of its
    own, the held entry placed by its own flag, and still chosen by session
    (task 47 — two more mutants)

And the drawn ball (task 58), with a clock of the check's own: the connect
flash, the held light, a beat's pulse and a catch's longer one, B cutting it,
the dot leaving the words only once the seam has drawn the ball, and a drawing
that cannot be made said once. Since task 60 the light is the centre's alone:
a held light only for a voice that holds one, breathing in 9's shape, and every
flash counted and timed, so the seam can restart it. Since task 63 the
battery reaches the drawing only while connected, a link switched off or no
ball mirror fades it, and the words beside it are the count alone. Its mutants are lines of `src/mirrors/menubar.py`
replaced one at a time, each of which must turn a row wrong.

And `Settings ›` (spec 03): opening at login is a checkmark in it, no longer a
line above Quit; a refused permission is a line at the very top, whose click
opens its pane, and a `⚠` last in the title, drawn ball or not; what was never
asked or cannot be read is never an alert and never checked; and a change only
the submenu sees still rebuilds the menu.

Plus the seam rule, mechanically: a mirror may name the seam and may not name an
OS. CLAUDE.md states it in prose, and prose is what loses to a convenient import
at 11pm.
"""
from __future__ import annotations

import ast
import glob
import importlib.util
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ["WOBBLE_PLATFORM"] = "null"          # before the seam is imported

from src import platform_seam                                          # noqa: E402
from src.core.ladder import Voice                                      # noqa: E402
from src.core.signals import Event, Kind, Queue                        # noqa: E402
from src.core.attention import Standing, Status                       # noqa: E402
from src.mirrors.menubar import (SEPARATOR, Menubar, items, line,      # noqa: E402
                                 login_line, render, status_words)
from src.platform_seam import null                                     # noqa: E402
from src.platform_seam.ports import (Alternate, BallIcon, Checked,    # noqa: E402
                                     Submenu)

def _pending() -> tuple:
    """Four sessions in three projects, whose right order is not their alphabetical one.

    Built through a real `Queue` rather than by hand: `pending()` is the thing
    being rendered, and an expectation written from hand-made rows would agree
    with the mirror while both disagreed with the queue. `wobble` carries two
    sessions, so two lines share a name and must be told apart by id (task 41);
    sorted by name the list would come out api-server, notebooks, wobble, which
    is a different list — that is what makes the ordering rule visible rather
    than accidental.
    """
    q = Queue()
    for session, kind, project, at in (("a", Kind.NEEDS, "wobble", 1.0),
                                       ("b", Kind.NEEDS, "wobble", 2.0),
                                       ("c", Kind.NEEDS, "api-server", 3.0),
                                       ("d", Kind.DONE, "notebooks", 0.0)):
        q.add(Event(session=session, kind=kind, project=project, at=at,
                    window_hint=f"win-{project}"))
    return tuple(q.pending())


PENDING = _pending()

CRY = Voice(effect=213, mac_sound="/System/Library/Sounds/Glass.aiff")
WAVE = Voice(effect=199, mac_sound="/System/Library/Sounds/Sosumi.aiff")
FLASH = Voice(effect=213, silent=True, mac_sound=None)
MUTE_BUT_LOUD = Voice(effect=213, silent=True,
                      mac_sound="/System/Library/Sounds/Glass.aiff")


class Sheet:
    def __init__(self, quiet: bool = False):
        self.quiet, self.bad = quiet, 0

    def row(self, what: str, got, want) -> None:
        good = got == want
        self.bad += not good
        if not self.quiet:
            print(f"    {what:<52} {'ok' if good else f'<-- WRONG: {got!r}, wanted {want!r}'}")

    def ok(self) -> bool:
        return not self.bad


def sounds() -> list[str]:
    """The sound files asked for since the last clear, in order."""
    return [args[0] for name, args in null.CALLS if name == "Sound.play"]


def titles() -> list[str]:
    return [args[0] for name, args in null.CALLS if name == "Status.show"]


def run_all(make_title, make_beat, quiet: bool = False) -> bool:
    sheet = Sheet(quiet)
    say = (lambda _: None) if quiet else (lambda line: print(line))

    say("\n  the title, with a ball connected")
    sheet.row("nothing pending is a hollow dot, never nothing", make_title(0, True), "○")
    sheet.row("one pending fills the dot and counts it", make_title(1, True), "● 1")
    sheet.row("five pending", make_title(5, True), "● 5")

    say("\n  the title, with no ball — criteria 8 and 9, in words")
    sheet.row("nothing pending still says there is no ball",
              make_title(0, False), "○ · no ball")
    sheet.row("two pending says both facts", make_title(2, False), "● 2 · no ball")
    sheet.row("…and 'no ball' is spelled out, not implied",
              "no ball" in make_title(2, False), True)

    say("\n  the title, with the ball switched off on purpose")
    # The two disconnected states have to read differently. 'no ball' sends a
    # person to go and press the ball's button; 'ball off' tells them nothing is
    # wrong and they did it themselves. One sentence for both would leave
    # somebody hunting a ball that is working perfectly on the desk beside them.
    sheet.row("switched off says so, not 'no ball'",
              make_title(0, False, ball_off=True), "○ · ball off")
    sheet.row("…and still counts what is waiting",
              make_title(3, False, ball_off=True), "● 3 · ball off")
    sheet.row("…and the two sentences are not the same one",
              make_title(0, False, ball_off=True) == make_title(0, False), False)

    say("\n  the title, with a ball and a battery reading")
    sheet.row("a connected ball shows what is left in it",
              make_title(2, True, battery=87), "● 2 · 87%")
    sheet.row("…with nothing pending too", make_title(0, True, battery=100), "○ · 100%")
    # None is "nobody has read it yet", which is not 0 and not 100. Showing
    # either would be a number no ball ever said — and 0% is the one that would
    # send somebody to find a charger for a ball that is full.
    sheet.row("a ball with no reading yet shows no percentage",
              make_title(0, True), "○")

    say("\n  the title, with the sounds switched off")
    # The one state here you cannot tell from the outside: a muted ball and a
    # ball with nothing to say both make no sound. A mute you have forgotten
    # about is a notifier that stopped, which is what principle 7 forbids — so
    # it is a word in the title and not only a line in the menu.
    sheet.row("muted is said in the title, not only in the menu",
              make_title(2, True, battery=87, muted=True), "● 2 · muted · 87%")
    # `find`, not `index`: a mutant that drops the word altogether must make
    # this row say the wrong thing rather than end the run in a traceback that
    # could have come from anywhere — the same rule `switches_part` follows.
    said = make_title(2, True, battery=87, muted=True)
    sheet.row("…before the battery, because it is about this daemon",
              -1 < said.find("muted") < said.find("87%"), True)
    # It silences the Mac as well, so it is still true with no ball — the run
    # where it is the ONLY thing keeping the room quiet.
    sheet.row("…and it is said with no ball too, which is when it matters most",
              make_title(1, False, muted=True), "● 1 · muted · no ball")
    sheet.row("…and nothing is said when the sounds are on",
              "muted" in make_title(2, True, battery=87), False)

    say("\n  a beat — who makes the sound")
    null.CALLS.clear()
    make_beat(WAVE, False)
    sheet.row("no ball: the Mac plays the needs wave", sounds(),
              ["/System/Library/Sounds/Sosumi.aiff"])

    null.CALLS.clear()
    make_beat(CRY, False)
    sheet.row("no ball: the Mac plays the done cry", sounds(),
              ["/System/Library/Sounds/Glass.aiff"])

    null.CALLS.clear()
    make_beat(WAVE, True)
    sheet.row("ball connected: the Mac stays out of it", sounds(), [])

    null.CALLS.clear()
    make_beat(FLASH, False)
    sheet.row("the silent pulse makes no sound with no ball", sounds(), [])

    null.CALLS.clear()
    make_beat(MUTE_BUT_LOUD, False)
    sheet.row("silent beats a configured sound, both surfaces", sounds(), [])

    return sheet.ok()


def waiting_part(menu: list) -> list:
    """Everything above the first separator — what is pending, or that nothing is."""
    return menu[:menu.index(SEPARATOR)] if SEPARATOR in menu else menu


def switches_part(menu: list) -> list:
    """Between the two separators — the two lines about how this daemon speaks.

    Mute first, then the ball's link (task 34). The rows below say what the menu
    offers for the LINK, and the link is the part that changes with the ball.
    Quit is the same line in every state, and the pending list does not move
    with the radio, so folding either into those expectations would make one
    fact appear four times and hide the one being asked about.

    A menu with no separator at all is returned whole rather than raising. Two
    of the mutants below are exactly that, and a mutant that ends the run in a
    traceback proves less than one that makes the table say the wrong thing: a
    crash could have come from anywhere, a wrong row names the rule.
    """
    if SEPARATOR not in menu:
        return menu
    below = menu[menu.index(SEPARATOR) + 1:]
    return below[:below.index(SEPARATOR)] if SEPARATOR in below else below


def mute_part(menu: list) -> list:
    """The mute line: the first of the two switches, when there are two.

    Taken by position rather than by label, because the label is one of the
    things being checked and a slice that went looking for the word "mute"
    would agree with any mutant that spelled it right.
    """
    part = switches_part(menu)
    return part[:1] if len(part) > 1 else []


def ball_part(menu: list) -> list:
    """The link line, which is whatever is left once mute is taken off the top."""
    part = switches_part(menu)
    return part[1:] if len(part) > 1 else part


def ball_lines(menu: list) -> list[str]:
    return [label for label, _ in ball_part(menu)]


def waiting_lines(menu: list) -> list[str]:
    return [label for label, _ in waiting_part(menu)]


def above_quit(menu: list):
    """The line quit sits under, or `None` if quit has nothing above it."""
    return menu[-2] if len(menu) >= 2 else None


def menu_rows(make, quiet: bool = False) -> bool:
    """The menu: what is waiting, one action about the ball, then a way out.

    `make` is `items` — or a mutant of it, which is why this is a function.
    """
    sheet = Sheet(quiet)
    if not quiet:
        print("\n  the menu — one action about the ball, and it never lies about it")

    # The labels, because the labels are the whole interface: a person reads one
    # word and clicks. "Connect" offered while the daemon is already scanning
    # would be a button that does nothing, which is principle 7's failure with a
    # mouse pointer on it.
    sheet.row("a connected ball offers to disconnect",
              ball_lines(make(True)), ["Disconnect the ball"])
    # Task 63: with the ball drawn the title no longer says the link in words,
    # so the menu does, greyed, above the line that changes it — principle 7
    # as amended puts the words one click away.
    sheet.row("a switched-off one says so, then offers to connect",
              ball_lines(make(False, ball_off=True)), ["Ball off", "Connect the ball"])
    sheet.row("one being looked for says so, then offers to stop",
              ball_lines(make(False)),
              ["No ball — looking for one", "Stop looking for the ball"])
    act = lambda: None
    sheet.row("…both states there to read, not to click",
              [ball_part(m)[0][1] for m in (make(False, ball_off=True, on_connect=act),
                                            make(False, on_disconnect=act))], [None, None])
    sheet.row("a connected ball with a reading says it, above disconnect",
              ball_lines(make(True, battery=87)), ["Battery 87%", "Disconnect the ball"])
    sheet.row("…to read, not to click",
              ball_part(make(True, battery=87, on_disconnect=act))[0][1], None)
    wired = make(True, pending=PENDING, on_attend=lambda p: None,
                 on_connect=lambda: None, on_disconnect=lambda: None,
                 on_mute=lambda: None, on_quit=lambda: None)
    sheet.row("…and every line that is not a separator does something",
              [h is not None for l, h in wired if l is not None],
              [True] * (len(PENDING) + 3))

    # Mute (task 34). The label says what the CLICK does, not what is true now:
    # the title already carries the state, and a line reading "Muted" is a fact
    # to read rather than a switch to press — which is how somebody ends up
    # clicking it to turn mute on and turning it off instead.
    sheet.row("with the sounds on, the line offers to switch them off",
              [label for label, _ in mute_part(make(True))], ["Mute the sounds"])
    sheet.row("…and with them off, to switch them back on",
              [label for label, _ in mute_part(make(True, muted=True))],
              ["Unmute the sounds"])
    sheet.row("…and it is the same one line either way, never two",
              [len(mute_part(make(True, muted=m))) for m in (False, True)], [1, 1])
    # Above the link and below the queue: both lines are about how this daemon
    # speaks rather than about what it has to say, and mute is the smaller act —
    # the sounds come back on the next click, the radio costs a reconnect.
    sheet.row("…sitting between the queue and the link, in that order",
              [label for label, _ in switches_part(make(True))],
              ["Mute the sounds", "Disconnect the ball"])
    clicked: list = []
    for _, handler in mute_part(make(True, on_mute=lambda: clicked.append(True))):
        # Recorded rather than called when it is dead, for the reason
        # `switches_part` gives: a wrong row names the rule, a traceback does not.
        clicked.append("<nothing to click>") if handler is None else handler()
    sheet.row("…and clicking it does something", clicked, [True])

    # The pending list. The order is not this file's opinion: `pending()` put
    # needs above done and the older of two needs first, and a mirror that
    # re-sorts is a second place for that decision to live (principle 1).
    sheet.row("one line per session, in the order the core hands over",
              [label.split(" — ")[0] for label in waiting_lines(make(True, pending=PENDING))],
              ["wobble · a", "wobble · b", "api-server", "notebooks"])
    sheet.row("…naming the session only where two share a project",
              waiting_lines(make(True, pending=PENDING)),
              ["wobble · a — needs", "wobble · b — needs", "api-server — needs",
               "notebooks — done"])
    # Task 36: each line says where it stands, in the four words agreed at the
    # desk. The standings are the core's, handed in by session (task 41).
    stood = {"a": Standing(Status.SIGNALLING),
             "b": Standing(Status.WAITING),
             "c": Standing(Status.ATTENDING, back_in=241.0),
             "d": Standing(Status.WAITING)}
    sheet.row("with standings, each line says where it stands",
              waiting_lines(make(True, pending=PENDING, standing=stood)),
              ["wobble · a — needs · signalling",
               "wobble · b — needs · waiting its turn",
               "api-server — needs · attending (back in 5m)",
               "notebooks — done · waiting its turn"])
    sheet.row("…the watched one says you are looking at it",
              waiting_lines(make(True, pending=PENDING[:1],
                                 standing={"a": Standing(Status.WATCHED)})),
              ["wobble — needs · quiet, you're looking at it"])
    # Rounded up, so the last seconds read "1m" and never "0m".
    sheet.row("…and the countdown rounds up, never to 0m",
              [line(PENDING[3], Standing(Status.ATTENDING, back_in=s))
               for s in (300.0, 60.0, 59.0, 0.0)],
              ["notebooks — done · attending (back in 5m)",
               "notebooks — done · attending (back in 1m)",
               "notebooks — done · attending (back in 1m)",
               "notebooks — done · attending (back in 1m)"])
    sheet.row("…and the log's words leave the countdown out",
              [status_words(Standing(Status.ATTENDING, back_in=241.0), countdown=False)],
              ["attending"])
    # Clicked in order, and the answers must come back in that same order. The
    # bug this is really watching for is late binding: every row closing over
    # the same variable reads perfectly and sends you to the last session.
    chosen: list[str] = []
    for _, handler in waiting_part(make(True, pending=PENDING, on_attend=chosen.append)):
        # A dead line is recorded rather than called: a mutant that leaves one
        # there must make this row say the wrong thing, not end the run in a
        # traceback that could have come from anywhere.
        chosen.append("<nothing to click>") if handler is None else handler()
    sheet.row("…and choosing one aims at THAT session, not at another",
              chosen, ["a", "b", "c", "d"])
    # The same reasoning as the hollow dot: a menu that shrank to the link and
    # a way out would look like a daemon that had lost the queue.
    sheet.row("an empty queue says so rather than showing nothing",
              waiting_lines(make(True)), ["Nothing waiting"])
    sheet.row("…greyed, because there is nothing there to choose",
              [h for _, h in waiting_part(make(True))], [None])
    # `--no-ball` has no ball mirror behind it, so there is nothing to connect.
    # Saying why, greyed, beats offering an action that cannot happen.
    no_mirror = make(False, have_ball_mirror=False)
    sheet.row("a --no-ball run offers no action on the ball",
              [h for _, h in ball_part(no_mirror)], [None])
    sheet.row("…and says why rather than showing nothing",
              "--no-ball" in ball_lines(no_mirror)[0], True)

    # Quit, in all four states at once. Not one row per state: what is being
    # claimed is that the way out does not move, and a claim about sameness is
    # only visible when the four are put side by side.
    states = [make(True), make(False), make(False, ball_off=True),
              make(False, have_ball_mirror=False)]
    sheet.row("quit is the last line whatever the ball is doing",
              [m[-1][0] for m in states], ["Quit wobble"] * 4)
    # The line above quit switches the ball's link, which costs a reconnect;
    # quit ends the run, and only one of those is undone by choosing the other
    # line. A thumb-width apart with nothing between them is how that happens.
    sheet.row("…always behind a separator, never touching the ball's line",
              [above_quit(m) for m in states], [SEPARATOR] * 4)
    sheet.row("…and it does something when chosen",
              make(True, on_quit=lambda: None)[-1][1] is not None, True)
    # A run with no ball mirror is the one where a person most needs a way out.
    # Mute is the only other line in it that does anything — the Mac sounds are
    # muted by it too, which is why it is offered there at all (task 34).
    sheet.row("…including in a --no-ball run, where two lines are live",
              [h is not None for l, h in
               make(False, have_ball_mirror=False, on_mute=lambda: None,
                    on_quit=lambda: None)
               if l is not None], [False, True, False, True])
    return sheet.ok()


# The seam's `(state, why)` for each of the four answers `Login.state` gives (spec 02).
LOGIN_OFF, LOGIN_ON = ("off", None), ("on", None)
LOGIN_DISABLED = ("disabled", "switched off in System Settings › General › Login Items & "
                              "Extensions › App Background Activity — switch wobble on there")
LOGIN_NO_APP = (None, "wobble.app is not in /Applications — build it with "
                      "tools/build_app.py --install first")


def settings_part(menu: list) -> list:
    """What `Settings ›` holds, or `[]` with no such line (spec 03)."""
    return next((h for label, h in menu if isinstance(label, Submenu)), [])


def login_part(menu: list) -> list:
    """The last line of `Settings ›`, where the login switch lives since spec 03."""
    part = settings_part(menu)
    return part[-1:] if part and part[-1] != SEPARATOR else []


def kinded(lines: list) -> list:
    """Labels with their kind: a `Checked` line equals its plain words as a `str`."""
    return [(type(label).__name__, label) for label, _ in lines]


def login_rows(make, quiet: bool = False) -> bool:
    """The login switch: a checkmark in `Settings ›`, read from the seam (specs 02, 03)."""
    sheet = Sheet(quiet)
    if not quiet:
        print("\n  opening at login — a checkmark in Settings › (specs 02, 03)")
    act = lambda: None
    said = lambda login, **kw: kinded(login_part(make(True, login=login, **kw)))
    sheet.row("off: the line offers to open wobble at login, unchecked",
              said(LOGIN_OFF), [("str", "Open wobble at login")])
    sheet.row("on: the same line, checked",
              said(LOGIN_ON), [("Checked", "Open wobble at login")])
    sheet.row("on with a doubt the OS left: still checked",
              said(("on", "macOS could not be asked")), [("Checked", "Open wobble at login")])
    # Task 01: switched off in System Settings, the file stays and a rewrite is
    # still off, so a checkmark would be a claim the disk makes and macOS does not.
    sheet.row("switched off in Settings: says so, offers the pane",
              said(LOGIN_DISABLED), [("str", "Off in Login Items — open System Settings")])
    sheet.row("no app to open: greyed, with why's first clause",
              [(label, h) for label, h in login_part(make(True, login=LOGIN_NO_APP,
                                                           on_login=act))],
              [("Cannot open at login: wobble.app is not in /Applications", None)])
    sheet.row("a state nobody knows: greyed, never shown as on",
              [(type(label).__name__, h) for label, h in
               login_part(make(True, login=("maybe", None), on_login=act))],
              [("str", None)])
    clicked: list = []
    for login in (LOGIN_OFF, LOGIN_ON, LOGIN_DISABLED):
        for _, handler in login_part(make(True, login=login,
                                          on_login=lambda: clicked.append(True))):
            clicked.append("<nothing to click>") if handler is None else handler()
    sheet.row("off, on, switched off: each line does something",
              clicked, [True] * 3)
    states = [make(True, login=LOGIN_ON), make(False, login=LOGIN_ON),
              make(False, ball_off=True, login=LOGIN_ON),
              make(False, have_ball_mirror=False, login=LOGIN_ON)]
    sheet.row("Settings › is the line above Quit's separator, any ball state",
              [kinded(m[-3:]) for m in states],
              [[("Submenu", "Settings"), ("NoneType", None), ("str", "Quit wobble")]] * 4)
    sheet.row("…with the login switch alone in it, and nothing else moved",
              [label for label, _ in switches_part(make(True, login=LOGIN_OFF))],
              ["Mute the sounds", "Disconnect the ball"])
    sheet.row("with no state handed in, no Settings ›: the menu as before",
              make(True, login=None), make(True))
    return sheet.ok()


def _lines(menu: list, change) -> list:
    """Every line, a submenu's too, through `change(label, handler)`."""
    return [(label, _lines(h, change)) if isinstance(label, Submenu) else change(label, h)
            for label, h in menu]


def login_out_of_settings(*a, **kw) -> list:
    """The switch left above Quit, where spec 02 had it, and not in Settings ›."""
    menu = items(*a, **kw)
    if kw.get("login") is None:
        return menu
    switch = login_line(kw["login"], kw.get("on_login"))
    return [line for line in menu if not isinstance(line[0], Submenu)][:-2] + [
        switch, SEPARATOR, menu[-1]]


def login_never_checked(*a, **kw) -> list:
    """On drawn as plain words: the same label for on and off, so the click reads backwards."""
    return _lines(items(*a, **kw), lambda label, h: (
        str(label) if isinstance(label, Checked) and "at login" in label else label, h))


def login_trusts_the_file(*a, **kw) -> list:
    """Switched off in System Settings read as on: the file is there, after all."""
    if kw.get("login") is not None and kw["login"][0] == "disabled":
        kw = {**kw, "login": LOGIN_ON}
    return items(*a, **kw)


def login_greyed_still_clicks(*a, **kw) -> list:
    """The refusal greyed in words but wired to the click all the same."""
    return _lines(items(*a, **kw), lambda label, h: (
        label, kw.get("on_login") if str(label).startswith("Cannot open at login") else h))


def login_line_dropped(*a, **kw) -> list:
    """No line at all: the switch wired in the daemon and never shown."""
    return items(*a, **{**kw, "login": None})


# The daemon's `{kind: (state, why)}`, in the seam's order (spec 03).
TERMINAL = "automation:com.apple.Terminal"
GRANTED = {"bluetooth": ("granted", None), "accessibility": ("granted", None),
           TERMINAL: ("granted", None)}
AX_OFF = {**GRANTED, "accessibility": ("refused", "Accessibility is switched off")}
ALL_OFF = {kind: ("refused", "off") for kind in GRANTED}
AX_ALERT = "⚠ Accessibility off — B raises no window · Open…"


def below_alerts(menu: list) -> list:
    """The menu with the ⚠ lines and their separator taken off the top."""
    alerts = 0
    while alerts < len(menu) and str(menu[alerts][0]).startswith("⚠"):
        alerts += 1
    return menu[alerts + 1:] if alerts else menu


def permission_rows(make, quiet: bool = False) -> bool:
    """A refused permission: a line at the top and a ✗ in Settings ›, each to its pane (spec 03)."""
    sheet = Sheet(quiet)
    if not quiet:
        print("\n  a missing permission, said where a person looks (spec 03)")
    opened: list = []
    menu = make(True, permissions=AX_OFF, on_permission=opened.append)
    sheet.row("Accessibility refused: a line at the very top",
              [label for label, _ in menu[:2]], [AX_ALERT, None])
    sheet.row("…above what is waiting, which is otherwise unmoved",
              menu[2:4], make(True)[:2])
    (menu[0][1] or (lambda: None))()
    sheet.row("…and its click opens Accessibility's pane", opened, ["accessibility"])
    sheet.row("all granted: no line at the top",
              make(True, permissions=GRANTED)[0], ("Nothing waiting", None))
    sheet.row("several refused: one line each, in the order handed over",
              [label for label, _ in make(True, permissions=ALL_OFF)[:4]],
              ["⚠ Bluetooth off — the ball cannot connect · Open…", AX_ALERT,
               "⚠ Automation · Terminal off — B cannot pick the tab · Open…", None])
    # Criterion 3: the radio being off is still the link line's, and only there.
    sheet.row("Bluetooth refused: the link lines are the same as without it",
              ball_lines(below_alerts(make(False, permissions={"bluetooth": ("refused", "off")}))),
              ball_lines(make(False)))
    sheet.row("never asked is not missing: no line at the top",
              make(True, permissions={"bluetooth": ("not asked", "never")})[0],
              ("Nothing waiting", None))
    sheet.row("unreadable is not missing either: no line at the top",
              make(True, permissions={"accessibility": (None, "gone")})[0],
              ("Nothing waiting", None))

    if not quiet:
        print("\n  Settings ›: every permission's state, then the login switch")
    opened.clear()
    part = settings_part(make(True, permissions=AX_OFF, on_permission=opened.append,
                              login=LOGIN_ON, on_login=lambda: None))
    sheet.row("a header, each permission, a separator, the login switch",
              kinded(part),
              [("str", "Permissions"), ("Checked", "Bluetooth — the ball can connect"),
               ("str", AX_ALERT), ("Checked", "Automation · Terminal — B picks the tab"),
               ("NoneType", None), ("Checked", "Open wobble at login")])
    sheet.row("granted lines are to read, and so is the header",
              [h is None for _, h in part[:4]], [True, True, False, True])
    if len(part) > 2:
        (part[2][1] or (lambda: None))()
    sheet.row("the refused line opens its pane", opened, ["accessibility"])
    said = lambda permissions: kinded(settings_part(make(True, permissions=permissions)))
    sheet.row("Accessibility never asked: greyed, says so",
              said({"accessibility": ("not asked", "never")}),
              [("str", "Permissions"), ("str", "Accessibility — not asked yet")])
    sheet.row("Automation never asked, or Terminal not running: not listed",
              [said({TERMINAL: ("not asked", "never")}), said({TERMINAL: ("not running", "")})],
              [[], []])
    # Criterion 7: an unknown state is never shown as ✓.
    sheet.row("unreadable: greyed, never checked",
              settings_part(make(True, permissions={"accessibility": (None, "gone")})),
              [("Permissions", None), ("Accessibility — cannot be read", None)])
    sheet.row("a state nobody knows reads as unreadable, never checked",
              said({"bluetooth": ("maybe", None)}),
              [("str", "Permissions"), ("str", "Bluetooth — cannot be read")])
    sheet.row("permissions and no login: no separator, no switch",
              [label for label, _ in settings_part(make(True, permissions=GRANTED))][-1],
              "Automation · Terminal — B picks the tab")
    sheet.row("with nothing handed in, no Settings › at all",
              make(True, permissions={}), make(True))
    return sheet.ok()


def alert_only_in_settings(*a, **kw) -> list:
    """A refused permission said only in Settings ›: the hidden ✗ the spec ends."""
    menu = items(*a, **kw)
    while menu and str(menu[0][0]).startswith("⚠"):
        menu = menu[1:]
    return menu[1:] if menu and menu[0] == SEPARATOR else menu


def alert_that_opens_nothing(*a, **kw) -> list:
    """The ⚠ lines drawn, and not wired to their pane."""
    return _lines(items(*a, **kw), lambda label, h: (label, None if str(label).startswith("⚠")
                                                     else h))


def unreadable_as_granted(*a, **kw) -> list:
    """What could not be read shown as granted (criterion 7)."""
    permissions = {kind: ("granted", None) if state not in ("refused", "not asked",
                                                            "not running") else (state, why)
                   for kind, (state, why) in (kw.get("permissions") or {}).items()}
    return items(*a, **{**kw, "permissions": permissions})


def never_asked_as_refused(*a, **kw) -> list:
    """A permission never asked alerted as missing: every new install nagged."""
    permissions = {kind: ("refused", why) if state == "not asked" else (state, why)
                   for kind, (state, why) in (kw.get("permissions") or {}).items()}
    return items(*a, **{**kw, "permissions": permissions})


def permissions_in_their_own_order(*a, **kw) -> list:
    """The alerts sorted by name, not in the seam's worst-loss-first order."""
    permissions = dict(sorted((kw.get("permissions") or {}).items()))
    return items(*a, **{**kw, "permissions": permissions})


def _restored() -> tuple:
    """quarry's done from before a restart, then wobble's needs and notebooks's
    done since — notebooks held by B, so the daemon appends it last (task 47)."""
    q = Queue()
    q.add(Event(session="a", kind=Kind.DONE, project="quarry", at=0.0, window_hint="quarry"))
    q.hush()
    for session, kind, project, at in (("b", Kind.NEEDS, "wobble", 1.0),
                                       ("c", Kind.DONE, "notebooks", 2.0)):
        q.add(Event(session=session, kind=kind, project=project, at=at,
                    window_hint=project))
    held = q.drop("c")
    return (*q.pending(), held)


RESTORED = _restored()


def restored_lines(menu: list) -> list:
    """Every line above the separator over mute, separators included."""
    labels = [label for label, _ in menu]
    return labels[:labels.index("Mute the sounds") - 1] if "Mute the sounds" in labels else labels


def restored_rows(make, quiet: bool = False) -> bool:
    """Task 47: the quiet ones under a separator of their own."""
    sheet = Sheet(quiet)
    if not quiet:
        print("\n  task 47 — back from before a restart, under a separator of its own")
    stood = {"a": Standing(Status.QUIET)}
    sheet.row("live first, the held one with them, then the quiet one",
              restored_lines(make(True, pending=RESTORED, standing=stood)),
              ["wobble — needs", "notebooks — done", None,
               "quarry — done · from before the restart"])
    sheet.row("…and quiet ones alone need no separator above them",
              restored_lines(make(True, pending=RESTORED[1:2], standing=stood)),
              ["quarry — done · from before the restart"])
    chosen: list[str] = []
    for label, handler in make(True, pending=RESTORED, on_attend=chosen.append):
        if label is not None and label.startswith("quarry"):
            chosen.append("<nothing to click>") if handler is None else handler()
    sheet.row("…and choosing it aims at its session", chosen, ["a"])
    return sheet.ok()


def silence_rows(make, quiet: bool = False) -> bool:
    """Task 68: each row's ⌥ twin silences its session, and only while it can."""
    sheet = Sheet(quiet)
    if not quiet:
        print("\n  task 68 — ⌥ shows each row's 'Silence <project>' in its place")
    stood = {"a": Standing(Status.QUIET)}
    hushed: list[str] = []
    menu = make(True, pending=RESTORED, standing=stood, on_silence=hushed.append)
    sheet.row("every row, live or quiet, is followed by its ⌥ twin",
              restored_lines(menu),
              ["wobble — needs", "Silence wobble", "notebooks — done", "Silence notebooks",
               None, "quarry — done · from before the restart", "Silence quarry"])
    sheet.row("…each one an Alternate, so the seam hides it until ⌥",
              [isinstance(l, Alternate) for l in restored_lines(menu) if l is not None],
              [False, True, False, True, False, True])
    for label, handler in menu:
        if isinstance(label, Alternate):
            handler()
    sheet.row("…and choosing one silences that row's session", hushed, ["b", "c", "a"])
    gone = make(True, pending=RESTORED[:1], standing={"b": Standing(Status.SILENCED)},
                on_silence=hushed.append)
    sheet.row("a session already silenced offers none",
              restored_lines(gone), ["wobble — needs · silenced until you type in it"])
    twins = tuple(Event(session=s, kind=Kind.DONE, project="wobble", at=float(i),
                        window_hint="wobble") for i, s in enumerate(("abcd1234", "efgh5678")))
    q = Queue()
    for e in twins:
        q.add(e)
    named = [l for l in restored_lines(make(True, pending=q.pending(), on_silence=hushed.append))
             if isinstance(l, Alternate)]
    sheet.row("two sessions of one project are told apart by their id",
              len(set(named)) == 2 and all("·" in l for l in named), True)
    sheet.row("with no on_silence the menu has no ⌥ rows at all",
              [l for l in restored_lines(make(True, pending=RESTORED, standing=stood))
               if isinstance(l, Alternate)], [])
    return sheet.ok()


def silence_rows_without_the_alternate(*a, **kw) -> list:
    """The twin as a plain line, always on screen beside the row it silences."""
    return [(str(l), h) if isinstance(l, Alternate) else (l, h) for l, h in items(*a, **kw)]


def silence_offered_when_already_silenced(*a, **kw) -> list:
    """The twin that ignores the row's standing."""
    return items(*a, **{**kw, "standing": {}})


# --- the mutants --------------------------------------------------------------
# Each drops exactly one rule. A suite that still passes against one of them was
# not testing that rule.

def title_blind_to_the_ball(pending: int, ball_connected: bool, **kw) -> str:
    """Renders the count perfectly and never mentions the ball."""
    return f"● {pending}" if pending else "○"


def title_vanishes_when_quiet(pending: int, ball_connected: bool, **kw) -> str:
    """The item that disappears — 'nothing waiting' and 'the daemon died' become
    the same picture."""
    if not pending:
        return ""
    return render(pending, ball_connected, **kw)


def title_conflates_off_and_missing(pending: int, ball_connected: bool, **kw) -> str:
    """Every disconnected state is 'no ball' — the state is carried and thrown
    away, which is the version that would survive a careless refactor."""
    return render(pending, ball_connected, battery=kw.get("battery"))


def title_drops_the_battery(pending: int, ball_connected: bool, **kw) -> str:
    """Knows about being switched off and not about what is left in the ball."""
    return render(pending, ball_connected, ball_off=kw.get("ball_off", False))


def title_forgets_the_mute(pending: int, ball_connected: bool, **kw) -> str:
    """Mute lives in the menu and never reaches the title — which is the version
    that looks finished, because the switch works and the menu says so. What it
    costs is the whole of principle 7: from across the room a muted daemon and a
    dead one are the same silence, and the menu is not somewhere you look when
    nothing is happening."""
    return render(pending, ball_connected, **{**kw, "muted": False})


class DoublesTheVoice(Menubar):
    """Plays the Mac's sound even while a ball is speaking."""

    def beat(self, voice, *, ball_connected):
        if voice.mac_sound is None or voice.silent:
            return False, None
        return platform_seam.sound.play(voice.mac_sound)


class BreaksTheSilentPulse(Menubar):
    """Honours the ball, ignores `silent` — the quiet flash beeps every 30 s."""

    def beat(self, voice, *, ball_connected):
        if ball_connected or voice.mac_sound is None:
            return False, None
        return platform_seam.sound.play(voice.mac_sound)


def the_list_in_its_own_order(*a, **kw) -> list:
    """Alphabetical. Tidier to look at, and it puts a finished project above a
    blocked one — the order the core hands over IS a decision it already made,
    and re-sorting it here is a mirror overruling the core."""
    return items(*a, **{**kw,
                        "pending": tuple(sorted(kw.get("pending", ()),
                                                key=lambda e: e.project))})


def every_line_attends_the_last(*a, **kw) -> list:
    """Late binding, written out: the labels are all correct and every handler
    closes over the same name. It reads right, and it goes to the wrong session
    — the failure that looks like the menu ignoring the click you made."""
    menu = items(*a, **kw)
    pending, on_attend = kw.get("pending", ()), kw.get("on_attend")
    if not pending or on_attend is None:
        return menu
    return [*[(label, lambda: on_attend(pending[-1].session))
              for label, _ in menu[:len(pending)]], *menu[len(pending):]]


def twins_look_alike(*a, **kw) -> list:
    """Task 41: two sessions of one project as two identical lines, so a
    click is a guess at which of them it will raise."""
    menu = items(*a, **kw)
    pending, standing = kw.get("pending", ()), kw.get("standing") or {}
    return [*[(line(entry, standing.get(entry.session)), handler)
              for entry, (_, handler) in zip(pending, menu)], *menu[len(pending):]]


def an_empty_queue_shows_nothing(*a, **kw) -> list:
    """Nothing waiting, so nothing is drawn. Honest-looking, and it makes a
    daemon that has lost its queue identical to one whose queue is empty."""
    menu = items(*a, **kw)
    return menu[1:] if not kw.get("pending") else menu


def quit_with_no_separator(*a, **kw) -> list:
    """Every label right, quit still last, and nothing between it and the line
    that switches the ball's link. This is the version that passes a review: the
    separator is the only thing that was dropped, and a separator looks like
    decoration right up until somebody ends the run reaching for Disconnect."""
    return [line for line in items(*a, **kw) if line != SEPARATOR]


def quit_goes_first(*a, **kw) -> list:
    """The same lines, in the order a menu builder would produce by accident —
    the way out at the top, where the thumb lands on the way to anything else."""
    menu = items(*a, **kw)
    return [menu[-1], *menu[:-1]]


def mute_label_never_changes(*a, **kw) -> list:
    """One label for both states. The switch still works and the title still says
    `muted` — so the only symptom is a line offering to mute something that is
    already muted, and the click that reads as "make sure it is off" turns it on."""
    menu = items(*a, **kw)
    return [("Mute the sounds", h) if label in ("Mute the sounds",
                                                "Unmute the sounds")
            else (label, h) for label, h in menu]


def no_quit_without_a_ball(*a, **kw) -> list:
    """Quit everywhere except the `--no-ball` run — that is, missing from the
    one menu where nothing else does anything at all."""
    menu = items(*a, **kw)
    return menu[:-2] if not kw.get("have_ball_mirror", True) else menu


def the_battery_left_out(*a, **kw) -> list:
    """The reading reaches the drawing and never the menu (task 63), so a red
    top is the only place the number is — and 40% or 60% of a half is not
    something anyone reads."""
    return items(*a, **{**kw, "battery": None})


def the_link_said_only_by_its_action(*a, **kw) -> list:
    """The state lines dropped: 'Stop looking for the ball' implies the state,
    and implying is what principle 7 as amended asks the menu not to do (task 63)."""
    return [row for row in items(*a, **kw)
            if row[0] not in ("Ball off", "No ball — looking for one")]


# --- the seam rule, mechanically ---------------------------------------------

FORBIDDEN = {"AppKit": "an OS", "Foundation": "an OS", "Cocoa": "an OS",
             "objc": "an OS", "rumps": "a menu bar",
             "subprocess": "osascript by the back door",
             "bleak": "the radio — a mirror of one surface may not hold another's"}


def quiet_ones_with_no_separator(*a, **kw) -> list:
    """The restored rows run straight on from the live ones (task 47)."""
    menu = items(*a, **kw)
    last = [i for i, row in enumerate(menu) if row == SEPARATOR][-2:]
    return [row for i, row in enumerate(menu) if row != SEPARATOR or i in last]


def split_at_the_first_quiet_one(*a, **kw) -> list:
    """The list in the order handed over, split where the first quiet row is —
    so the held one, which the daemon appends last, lands below the separator."""
    pending, standing = kw.get("pending", ()), kw.get("standing") or {}
    aim = kw.get("on_attend")
    rows = [(line(e, standing.get(e.session)),
             (lambda s=e.session: aim(s)) if aim else None) for e in pending]
    first = next((i for i, e in enumerate(pending) if e.quiet), 0)
    if first:
        rows.insert(first, SEPARATOR)
    rest = items(*a, **{**kw, "pending": ()})
    return [*(rows or rest[:1]), *rest[1:]]


def mirrors_name_no_os() -> bool:
    """A mirror goes through the seam or it is not a mirror (CLAUDE.md)."""
    bad = []
    paths = sorted(glob.glob(str(Path(__file__).resolve().parents[2] / "src/mirrors/*.py")))
    if not paths:                   # an empty glob would pass this vacuously (task 74)
        bad.append("no src/mirrors/*.py found at all")
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
                why = FORBIDDEN.get(name.split(".")[0])
                if why:
                    bad.append(f"{path.split('/')[-1]} imports {name} ({why})")
    for line in bad:
        print(f"    {line:<52} <-- MUST NOT")
    if not bad:
        print(f"    {'src/mirrors names no OS, only the seam':<52} ok")
    return not bad


# --- the drawn ball (task 58) -------------------------------------------------

MENUBAR = (Path(__file__).resolve().parents[2] / "src/mirrors/menubar.py")
NEEDS_BEAT = Voice(effect=199, tint="#FFB000")
DONE_HELD = Voice(effect=129, light=9, tint="#FFE14D")
CAUGHT = Voice(effect=201, tint="#3CC85A", lasts_s=2.0)
BROKE = Voice(effect=206, tint="#E8342A", lasts_s=2.0)
NEEDS_HELD = Voice(effect=199, tint="#FFB000")        # what `showing` hands for a needs
# 9 with the stroll LED: 20, 15 and 9 units of ~52 ms (FC-LED.md 3h leg 0),
# written out here so a mutant of the constant is a mutant this row sees.
BREATH = (1.04, 0.78, 0.47)
NO_TINT = Voice(effect=199)
CANNOT = "no platform: there is no menu bar to draw a ball in"


class Drawn(null.Status):
    """The null seam, except that a ball can be drawn: what macOS answers."""

    def icon(self, ball):
        null._record("Status.icon", ball)
        return True, None


class DrawnStill(null.Status):
    """A seam that draws the ball but cannot move its light (task 60)."""

    def icon(self, ball):
        null._record("Status.icon", ball)
        return True, "could not light the ball's centre in the menu bar (x), so its light is drawn still"


UNMARKED = ("could not draw the mute mark beside the ball in the menu bar "
            "(no speaker.slash.fill on this macOS)")


class Unmarked(null.Status):
    """A seam that draws the ball but has no mute mark to draw beside it (task 61)."""

    def icon(self, ball):
        null._record("Status.icon", ball)
        return (False, UNMARKED) if ball.muted else (True, None)


def load_menubar(patch: tuple[str, str] | None = None):
    """`src.mirrors.menubar` under its own name, one line replaced, or `None`
    when that line is not there exactly once."""
    text = MENUBAR.read_text()
    if patch is not None:
        if text.count(patch[0]) != 1:
            return None
        text = text.replace(*patch)
    spec = importlib.util.spec_from_file_location("src.mirrors.menubar_under_check", MENUBAR)
    module = importlib.util.module_from_spec(spec)
    module.__package__ = "src.mirrors"
    sys.modules[spec.name] = module
    exec(compile(text, str(MENUBAR), "exec"), module.__dict__)
    return module


def icons() -> list:
    return [args[0] for name, args in null.CALLS if name == "Status.icon"]


def ball_rows(mod, quiet: bool = False) -> bool:
    sheet = Sheet(quiet)
    say = (lambda _: None) if quiet else print
    t = [0.0]
    real = platform_seam.status
    B = BallIcon
    try:
        say("\n  the drawn ball — the reference leg: a seam that cannot draw it")
        null.CALLS.clear()
        bar = mod.Menubar(on_press=lambda: None, clock=lambda: t[0])
        said = bar.refresh(0, ball_connected=False)
        sheet.row("it asks for a hollow ball with nothing lit", icons(), [B(False)])
        sheet.row("…is refused, and the title keeps its dot", titles()[-1], "○ · no ball")
        sheet.row("…and why is handed back to be said, with what is kept",
                  said, f"{CANNOT} — the menu bar keeps its dot in the words")
        sheet.row("…once: the same ball again asks and says nothing",
                  (bar.refresh(0, ball_connected=False), len(icons())), (None, 1))
        t[0] += 1.0
        sheet.row("…nor a new ball refused for the same reason",
                  bar.refresh(1, ball_connected=True), None)

        say("\n  the drawn ball — a seam that draws it and cannot move its light")
        platform_seam.status = DrawnStill()
        bar = mod.Menubar(on_press=lambda: None, clock=lambda: t[0])
        said = bar.refresh(1, ball_connected=False)
        sheet.row("why is said as it is: the dot is not what is kept",
                  said, DrawnStill().icon(B(False))[1])
        sheet.row("…and the words lose the dot, since the ball is drawn",
                  titles()[-1], "1")

        say("\n  the drawn ball — a seam that draws it")
        platform_seam.status = Drawn()
        null.CALLS.clear()
        t[0] = 0.0
        bar = mod.Menubar(on_press=lambda: None, clock=lambda: t[0])
        sheet.row("drawn, the words keep the count and lose the dot",
                  (bar.refresh(2, ball_connected=False), titles()[-1]), (None, "2"))
        bar.refresh(0, ball_connected=True)
        sheet.row("a ball connecting fills the top half and flashes white for 0.8 s",
                  icons()[-1], B(True, None, "#FFFFFF", None, 0.8, 1))
        sheet.row("…and a connected ball with nothing waiting is the drawing alone",
                  titles()[-1], "")
        t[0] = 0.79
        bar.refresh(0, ball_connected=True)
        sheet.row("…still white just before 0.8s", icons()[-1].pulse, "#FFFFFF")
        t[0] = 0.81
        bar.refresh(0, ball_connected=True)
        sheet.row("…and only the top half after", icons()[-1], B(True, beat=1))
        t[0] = 5.0
        bar.refresh(0, ball_connected=True)
        sheet.row("staying connected lights nothing again", icons()[-1], B(True, beat=1))
        bar.refresh(1, ball_connected=True, showing=NEEDS_HELD)
        sheet.row("a needs holds no light: 199 is dark between its beats",
                  icons()[-1], B(True, beat=1))
        bar.refresh(1, ball_connected=True, showing=DONE_HELD)
        sheet.row("a done holds the centre's colour, breathing in 9's shape",
                  icons()[-1], B(True, "#FFE14D", None, BREATH, 0.0, 1))

        null.CALLS.clear()
        bar.beat(NEEDS_BEAT, ball_connected=True)
        sheet.row("a beat with a ball speaking makes no Mac sound", sounds(), [])
        bar.refresh(1, ball_connected=True, showing=DONE_HELD)
        sheet.row("…but the centre flashes with it, in its colour, for 0.5 s",
                  icons()[-1], B(True, "#FFE14D", "#FFB000", BREATH, 0.5, 2))
        t[0] = 5.49
        bar.refresh(1, ball_connected=True, showing=DONE_HELD)
        sheet.row("…for half a second", icons()[-1].pulse, "#FFB000")
        t[0] = 5.51
        bar.refresh(1, ball_connected=True, showing=DONE_HELD)
        sheet.row("…and then the held light alone, still breathing", icons()[-1],
                  B(True, "#FFE14D", None, BREATH, 0.0, 2))

        t[0] = 6.0
        bar.beat(NEEDS_BEAT, ball_connected=True)
        bar.refresh(1, ball_connected=True, showing=NEEDS_HELD)
        t[0] = 6.2
        bar.beat(NEEDS_BEAT, ball_connected=True)
        bar.refresh(1, ball_connected=True, showing=NEEDS_HELD)
        sheet.row("two beats alike are two flashes, each counted",
                  [(i.pulse, i.beat) for i in icons()[-2:]], [("#FFB000", 3), ("#FFB000", 4)])
        t[0] = 6.6
        bar.refresh(1, ball_connected=True, showing=NEEDS_HELD)
        sheet.row("…and the second is timed from its own beat", icons()[-1].pulse, "#FFB000")

        t[0] = 10.0
        bar.beat(CAUGHT, ball_connected=False)
        t[0] = 11.9
        bar.refresh(0, ball_connected=False)
        sheet.row("a catch flashes green for as long as it plays: at 1.9s",
                  icons()[-1], B(False, None, "#3CC85A", None, 2.0, 5))
        t[0] = 12.01
        bar.refresh(0, ball_connected=False)
        sheet.row("…and not at 2.0s, with the top half hollow: the ball went",
                  icons()[-1], B(False, beat=5))
        bar.beat(BROKE, ball_connected=False)
        bar.refresh(0, ball_connected=False)
        sheet.row("a break-out flashes red, for as long", icons()[-1],
                  B(False, None, "#E8342A", None, 2.0, 6))
        t[0] = 14.1

        bar.beat(NO_TINT, ball_connected=False)
        bar.refresh(0, ball_connected=False)
        sheet.row("a voice with no tint lights nothing, nor counts",
                  icons()[-1], B(False, beat=6))
        bar.beat(NEEDS_BEAT, ball_connected=False)
        bar.quiet()
        bar.refresh(0, ball_connected=False)
        sheet.row("B cuts the light with the sound", icons()[-1], B(False, beat=7))
        t[0] = 20.0
        bar.refresh(0, ball_connected=True)
        sheet.row("a ball coming back flashes white again",
                  (icons()[-1].pulse, icons()[-1].beat), ("#FFFFFF", 8))

        null.CALLS.clear()
        t[0] = 30.0
        for _ in range(8):
            bar.refresh(1, ball_connected=True, showing=DONE_HELD)
        sheet.row("eight identical refreshes draw once", len(icons()), 1)

        say("\n  the drawn ball — muted (task 61)")
        bar.refresh(1, ball_connected=True, battery=87, muted=True)
        sheet.row("a mute is handed to the drawing", icons()[-1].muted, True)
        sheet.row("…and the word leaves the title for its mark", titles()[-1], "1")
        bar.refresh(1, ball_connected=True, battery=87)
        sheet.row("unmuted, the mark goes", icons()[-1].muted, False)
        platform_seam.status = Unmarked()
        bar = mod.Menubar(on_press=lambda: None, clock=lambda: t[0])
        said = bar.refresh(1, ball_connected=True, battery=87, muted=True)
        sheet.row("with no mark to draw, the title keeps the word and the dot",
                  titles()[-1], "● 1 · muted · 87%")
        sheet.row("…and why is said", said, f"{UNMARKED} — the menu bar keeps its dot in the words")

        say("\n  the drawn ball — the link and the battery (task 63)")
        platform_seam.status = Drawn()
        bar = mod.Menubar(on_press=lambda: None, clock=lambda: t[0])
        bar.refresh(2, ball_connected=True, battery=87)
        sheet.row("the battery is handed to the drawing", icons()[-1].battery, 87)
        sheet.row("…and the words are the count alone", titles()[-1], "2")
        bar.refresh(2, ball_connected=False, battery=87)
        # The ball mirror clears its reading on a drop; this is the menu bar
        # not relying on that, since a red top is only ever a connected ball's.
        sheet.row("a reading left over from a lost link is not drawn",
                  icons()[-1].battery, None)
        sheet.row("looking for a ball is hollow, not faded",
                  (icons()[-1].connected, icons()[-1].off), (False, False))
        sheet.row("…and the words are the count alone", titles()[-1], "2")
        bar.refresh(0, ball_connected=False, ball_off=True)
        sheet.row("switched off is faded", icons()[-1].off, True)
        sheet.row("…and says nothing in words", titles()[-1], "")
        bar.refresh(0, ball_connected=False, have_ball_mirror=False)
        sheet.row("a run with no ball mirror is faded too", icons()[-1].off, True)
        bar.refresh(0, ball_connected=True, ball_off=True)
        sheet.row("connected is never faded, whatever else is said", icons()[-1].off, False)

        say("\n  the drawn ball — the words beside it")
        sheet.row("drawn, with a battery", mod.render(2, True, battery=87, ball_drawn=True),
                  "2")
        sheet.row("drawn and switched off",
                  mod.render(3, False, ball_off=True, ball_drawn=True), "3")
        sheet.row("drawn, muted and no ball: the mute is the mark's",
                  mod.render(1, False, muted=True, ball_drawn=True), "1")
        sheet.row("not drawn, muted and no ball: the mute is the word",
                  mod.render(1, False, muted=True), "● 1 · muted · no ball")
        sheet.row("drawn and nothing to say", mod.render(0, True, ball_drawn=True), "")
    except Exception as exc:              # a mutant that crashes is a wrong row
        sheet.row("the drawn ball's rows ran to the end", f"raised {exc!r}", "ran")
    finally:
        platform_seam.status = real
    return sheet.ok()


BALL_MUTANTS = [
    ("a connect never lit", ("if ball_connected and not self._connected:", "if False:")),
    ("lit white on every refresh while connected",
     ("if ball_connected and not self._connected:", "if ball_connected:")),
    ("a pulse that never ends",
     ("if self._pulse is not None and now >= self._pulse[1]:", "if False:")),
    ("a catch as short as a beat", ("voice.lasts_s or PULSE_S)", "PULSE_S)")),
    ("no pulse while a ball speaks",
     ("        if voice.tint is not None:\n            self._flash",
      "        if voice.tint is not None and not ball_connected:\n            self._flash")),
    ("the held light never drawn",
     ("held = showing.tint if showing is not None and showing.light is not None else None",
      "held = None")),
    ("a needs holds a light too",
     ("showing.tint if showing is not None and showing.light is not None else None",
      "showing.tint if showing is not None else None")),
    ("a held light that does not breathe",
     ("STROLL_BREATH if held is not None else None,", "None,")),
    ("the breath in another shape",
     ("STROLL_BREATH = (1.04, 0.78, 0.47)", "STROLL_BREATH = (1.04, 0.47, 0.78)")),
    ("two beats alike are one flash", ("self._beats += 1", "pass")),
    ("a flash with no length handed over",
     ("pulse[2] if pulse is not None else 0.0,", "0.0,")),
    ("a flash timed from the first beat",
     ("self._pulse = (colour, self._clock() + seconds, seconds)",
      "self._pulse = self._pulse or (colour, self._clock() + seconds, seconds)")),
    ("the dot's sentence on a ball drawn still",
     ("news = why if self._drew else (", "news = (")),
    ("the dot's sentence dropped",
     ('f"{why} — the menu bar keeps its dot in the words")', "why)")),
    ("the dot kept beside the drawing",
     ("muted=muted, ball_drawn=self._drew, alert=alert))", "muted=muted, alert=alert))")),
    ("the dot dropped though nothing was drawn",
     ("self._drew, why = platform_seam.status.icon(ball)",
      "why = platform_seam.status.icon(ball)[1]; self._drew = True")),
    ("drawn on every refresh", ("        if ball != self._drawn:", "        if True:")),
    ("a refusal said every time", ("if why != self._cannot_draw:", "if True:")),
    ("the mute never handed to the drawing", ("self._beats, muted,", "self._beats, False,")),
    ("the words kept beside the drawing, as at task 61",
     ('    if ball_drawn:\n        return " ".join([*([f"{pending}"] if pending else []), '
      '*(["⚠"] if alert else [])])\n'
      '    parts = [f"● {pending}" if pending else "○"]\n    if muted:',
      '    parts = ([f"{pending}"] if pending else []) if ball_drawn else [\n'
      '        f"● {pending}" if pending else "○"]\n    if muted and not ball_drawn:')),
    ("the word dropped with no drawing",
     ('    if muted:\n        parts.append("muted")', '    if False:\n        parts.append("muted")')),
    ("the battery never handed to the drawing",
     ("                        battery if ball_connected else None,\n",
      "                        None,\n")),
    ("a reading drawn with no link", ("battery if ball_connected else None,", "battery,")),
    ("a switched-off link not faded",
     ("(ball_off or not have_ball_mirror))", "(not have_ball_mirror))")),
    ("a --no-ball run not faded", ("(ball_off or not have_ball_mirror))", "(ball_off))")),
    ("looking for a ball faded too",
     ("not ball_connected and (ball_off or not have_ball_mirror))", "not ball_connected)")),
    ("a connected ball faded when switched off",
     ("not ball_connected and (ball_off or not have_ball_mirror))",
      "(ball_off or not have_ball_mirror))")),
    ("B leaves the light lit",
     ("        self._pulse = None\n        platform_seam.sound.stop()",
      "        platform_seam.sound.stop()")),
]


def main() -> int:
    print(__doc__.strip().splitlines()[0])

    bar = Menubar(on_press=lambda: None)

    def title(pending: int, ball_connected: bool, **kw) -> str:
        """Through the mirror and back out of the seam, not `render` directly —
        a title that is computed and never shown is the one failure this check
        would otherwise miss entirely."""
        null.CALLS.clear()
        bar.refresh(pending, ball_connected=ball_connected, **kw)
        shown = titles()
        return shown[-1] if shown else "<nothing was shown>"

    ok = run_all(title, lambda v, ball: bar.beat(v, ball_connected=ball))

    print("\n  the click is the B button")
    null.CALLS.clear()
    pressed = []
    Menubar(on_press=lambda: pressed.append(True))
    handlers = [args[0] for name, args in null.CALLS if name == "Status.on_click"]
    print(f"    {'a handler is installed on the status item':<52} "
          f"{'ok' if len(handlers) == 1 else '<-- WRONG: ' + str(len(handlers))}")
    ok &= len(handlers) == 1
    handlers[0]()           # the seam has no item to click, so the click is here
    print(f"    {'…and clicking it presses B':<52} "
          f"{'ok' if pressed else '<-- the press never arrived'}")
    ok &= bool(pressed)

    ok &= menu_rows(items)
    ok &= restored_rows(items)
    ok &= silence_rows(items)
    ok &= login_rows(items)
    ok &= permission_rows(items)

    print("\n  --no-menubar puts nothing in the menu bar at all")
    null.CALLS.clear()
    quiet_bar = Menubar(on_press=lambda: None, item=False)
    quiet_bar.refresh(3, ball_connected=False, menu=items(False))
    silent = Sheet()
    # Not "shows an empty title" — nothing is asked of the seam, so no status
    # item is ever created and there is nothing on screen to click.
    silent.row("nothing is shown", titles(), [])
    silent.row("no click handler is installed",
               [n for n, _ in null.CALLS if n == "Status.on_click"], [])
    silent.row("and no menu is built either",
               [n for n, _ in null.CALLS if n == "Status.menu"], [])
    ok &= silent.ok()

    print("\n  the menu is rebuilt when the words change, and not four times a second")
    null.CALLS.clear()
    steady = Menubar(on_press=lambda: None)
    for _ in range(8):
        steady.refresh(1, ball_connected=False, menu=items(False))
    built = [args[0] for n, args in null.CALLS if n == "Status.menu"]
    rebuild = Sheet()
    # The seam is handed labels only, so a `None` here IS the separator arriving
    # — the one line whose whole job is to be in the list.
    looking = ["Nothing waiting", None, "Mute the sounds", "No ball — looking for one",
               "Stop looking for the ball", None, "Quit wobble"]
    rebuild.row("eight identical refreshes build one menu", built, [looking])
    steady.refresh(1, ball_connected=True, menu=items(True))
    connected = ["Nothing waiting", None, "Mute the sounds",
                 "Disconnect the ball", None, "Quit wobble"]
    built = [args[0] for n, args in null.CALLS if n == "Status.menu"]
    rebuild.row("…and the ball arriving builds the next one", built,
                [looking, connected])
    # The list is what changes most often, and it is the reason the menu can
    # grow and shrink between two polls — the seam is handed a whole new list
    # each time rather than being asked to edit the one it has.
    steady.refresh(1, ball_connected=True, menu=items(True, pending=PENDING))
    built = [args[0] for n, args in null.CALLS if n == "Status.menu"]
    rebuild.row("…and so does a session joining the queue", built[-1],
                ["wobble · a — needs", "wobble · b — needs", "api-server — needs",
                 "notebooks — done", None, "Mute the sounds",
                 "Disconnect the ball", None, "Quit wobble"])
    ok &= rebuild.ok()

    print("\n  B cuts a sound already playing (criterion 4)")
    null.CALLS.clear()
    bar.quiet()
    stopped = [name for name, _ in null.CALLS if name == "Sound.stop"]
    print(f"    {'pressing B stops the Mac sound':<52} "
          f"{'ok' if stopped else '<-- nothing was stopped'}")
    ok &= bool(stopped)

    ok &= ball_rows(load_menubar())
    print("\n  the drawn ball's mutants — lines of menubar.py, each must break a row")
    for label, patch in BALL_MUTANTS:
        mod = load_menubar(patch)
        got = "NOT APPLIED" if mod is None else ("caught" if not ball_rows(mod, quiet=True)
                                                 else "SURVIVED")
        ok &= got == "caught"
        print(f"    {label:<52} {'caught' if got == 'caught' else '<-- ' + got}")

    ok &= alert_rows(sys.modules["src.mirrors.menubar"])
    print("\n  the ⚠ and Settings ›'s mutants — lines of menubar.py, each must break a row")
    for label, patch in ALERT_MUTANTS:
        mod = load_menubar(patch)
        got = "NOT APPLIED" if mod is None else ("caught" if not alert_rows(mod, quiet=True)
                                                 else "SURVIVED")
        ok &= got == "caught"
        print(f"    {label:<52} {'caught' if got == 'caught' else '<-- ' + got}")

    print("\n  the seam rule")
    ok &= mirrors_name_no_os()

    print("\n  the control — every rule removed in turn, each must break the suite")
    controls = (
        ("a title that never says 'no ball'",
         lambda: run_all(title_blind_to_the_ball,
                         lambda v, b: bar.beat(v, ball_connected=b), quiet=True)),
        ("an item that vanishes when the queue empties",
         lambda: run_all(title_vanishes_when_quiet,
                         lambda v, b: bar.beat(v, ball_connected=b), quiet=True)),
        ("the Mac doubling a ball that is already speaking",
         lambda: run_all(title, _beats_of(DoublesTheVoice), quiet=True)),
        ("a silent pulse that beeps", lambda: run_all(title, _beats_of(BreaksTheSilentPulse),
                                                      quiet=True)),
        ("'switched off' rendered as 'no ball'",
         lambda: run_all(title_conflates_off_and_missing,
                         lambda v, b: bar.beat(v, ball_connected=b), quiet=True)),
        ("a battery reading that never reaches the title",
         lambda: run_all(title_drops_the_battery,
                         lambda v, b: bar.beat(v, ball_connected=b), quiet=True)),
        ("quit sitting straight under Disconnect, no separator",
         lambda: menu_rows(quit_with_no_separator, quiet=True)),
        ("quit at the top of the menu instead of the bottom",
         lambda: menu_rows(quit_goes_first, quiet=True)),
        ("no way out of a --no-ball run",
         lambda: menu_rows(no_quit_without_a_ball, quiet=True)),
        ("the pending list sorted by name instead of by urgency",
         lambda: menu_rows(the_list_in_its_own_order, quiet=True)),
        ("every line in the list aiming at the same session",
         lambda: menu_rows(every_line_attends_the_last, quiet=True)),
        ("two sessions of one project as two identical lines",
         lambda: menu_rows(twins_look_alike, quiet=True)),
        ("an empty queue drawing no line at all",
         lambda: menu_rows(an_empty_queue_shows_nothing, quiet=True)),
        ("a mute the title never mentions",
         lambda: run_all(title_forgets_the_mute,
                         lambda v, b: bar.beat(v, ball_connected=b), quiet=True)),
        ("one mute label for both states, so the click reads backwards",
         lambda: menu_rows(mute_label_never_changes, quiet=True)),
        ("restored rows with no separator of their own (task 47)",
         lambda: restored_rows(quiet_ones_with_no_separator, quiet=True)),
        ("the held one split below the quiet ones",
         lambda: restored_rows(split_at_the_first_quiet_one, quiet=True)),
        ("the ⌥ twin as a plain line, always shown (task 68)",
         lambda: silence_rows(silence_rows_without_the_alternate, quiet=True)),
        ("a silenced session still offered the silence",
         lambda: silence_rows(silence_offered_when_already_silenced, quiet=True)),
        ("a battery the menu never says (task 63)",
         lambda: menu_rows(the_battery_left_out, quiet=True)),
        ("a lost link said only by the line that changes it",
         lambda: menu_rows(the_link_said_only_by_its_action, quiet=True)),
        ("the login switch left above Quit, out of Settings ›",
         lambda: login_rows(login_out_of_settings, quiet=True)),
        ("on drawn without its checkmark",
         lambda: login_rows(login_never_checked, quiet=True)),
        ("switched off in System Settings shown as on",
         lambda: login_rows(login_trusts_the_file, quiet=True)),
        ("a greyed login refusal that still clicks",
         lambda: login_rows(login_greyed_still_clicks, quiet=True)),
        ("no login line at all",
         lambda: login_rows(login_line_dropped, quiet=True)),
        ("a refused permission said only in Settings › (spec 03)",
         lambda: permission_rows(alert_only_in_settings, quiet=True)),
        ("a ⚠ line that opens nothing",
         lambda: permission_rows(alert_that_opens_nothing, quiet=True)),
        ("an unreadable permission shown as granted",
         lambda: permission_rows(unreadable_as_granted, quiet=True)),
        ("a permission never asked alerted as missing",
         lambda: permission_rows(never_asked_as_refused, quiet=True)),
        ("the alerts in an order of the menu's own",
         lambda: permission_rows(permissions_in_their_own_order, quiet=True)),
    )
    for label, run in controls:
        survived = run()
        ok &= not survived
        print(f"    {label:<52} "
              f"{'<-- SURVIVED, so the suite does not test it' if survived else 'caught'}")

    print("\n" + ("ALL CASES MATCH the known answer" if ok
                  else "SOMETHING DOES NOT MATCH — the rows above, not this line"))
    return 0 if ok else 1


def alert_rows(mod, quiet: bool = False) -> bool:
    """The `⚠` in the title, and a menu rebuilt for a change inside `Settings ›` (spec 03)."""
    sheet = Sheet(quiet)
    say = (lambda _: None) if quiet else print
    say("\n  a refused permission: a ⚠ in the title, last (spec 03)")
    null.CALLS.clear()
    bar = mod.Menubar(on_press=lambda: None)
    bar.refresh(0, ball_connected=False, alert=True)
    sheet.row("no drawing: the words end in ⚠", titles()[-1], "○ · no ball · ⚠")
    bar.refresh(2, ball_connected=True, battery=80, muted=True, alert=True)
    sheet.row("…after everything else they say", titles()[-1], "● 2 · muted · 80% · ⚠")
    bar.refresh(0, ball_connected=False)
    sheet.row("…and it goes when nothing is refused", titles()[-1], "○ · no ball")
    sheet.row("drawn, nothing waiting: the ⚠ alone beside the ball",
              mod.render(0, True, ball_drawn=True, alert=True), "⚠")
    sheet.row("drawn, two waiting: the count, then the ⚠",
              mod.render(2, True, ball_drawn=True, alert=True), "2 ⚠")
    sheet.row("drawn, nothing refused: as before",
              mod.render(2, True, ball_drawn=True), "2")

    say("\n  a change only Settings › sees still rebuilds the menu (spec 03)")
    null.CALLS.clear()
    bar = mod.Menubar(on_press=lambda: None)
    for login in (LOGIN_OFF, LOGIN_OFF, LOGIN_ON):
        bar.refresh(0, ball_connected=True, menu=mod.items(True, login=login))
    built = [args[0] for n, args in null.CALLS if n == "Status.menu"]
    # The seam's null records words only: a checkmark is the same words, so the
    # second build is the row, not what it lists.
    sheet.row("a checkmark coming on is a new menu, the same one twice is not",
              len(built), 2)
    bar.refresh(0, ball_connected=True, menu=mod.items(True, login=LOGIN_DISABLED))
    built = [args[0] for n, args in null.CALLS if n == "Status.menu"]
    sheet.row("…and so are new words inside Settings › alone",
              built[-1][-3:], [["Settings", ["Off in Login Items — open System Settings"]],
                               None, "Quit wobble"])
    return sheet.ok()


ALERT_MUTANTS = [
    ("no ⚠ in the words", ('    if alert:\n        parts.append("⚠")',
                           '    if False:\n        parts.append("⚠")')),
    ("no ⚠ beside the drawing", ('*(["⚠"] if alert else [])', "")),
    ("the menu compared by its words alone",
     ("return [(label, type(label).__name__, _shape(handler) if isinstance(label, Submenu) "
      "else None)\n            for label, handler in menu]",
      "return [label for label, handler in menu]")),
    ("a submenu's lines never compared",
     ("_shape(handler) if isinstance(label, Submenu) else None)", "None)")),
]


def _beats_of(cls):
    mutant = cls(on_press=lambda: None)
    return lambda voice, ball: mutant.beat(voice, ball_connected=ball)


if __name__ == "__main__":
    sys.exit(main())
