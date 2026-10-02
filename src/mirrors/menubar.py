"""The menu bar: a ball, a count, and the truth about the ball.

It renders what the core handed over and nothing else (principle 1) — how many
entries are pending, and whether a ball is connected. Both arrive as arguments.
Nothing here reaches back into the queue, holds a copy of it, or remembers a
state of its own between calls, because a mirror that keeps state is a second
place for the answer to be wrong. The one exception is how long a pulse still
has, and the ball below says why.

The click is not chrome. With no ball a right-click on this item IS the B button
(criterion 8), so it goes back across the seam as input, exactly where the ball's
own button goes.

**What the title says** — with the ball drawn, the count alone and nothing
else, since the drawing says the rest (task 63). When the seam cannot draw it:

    ○                 nothing is waiting
    ● 2               two sessions are
    ○ · no ball       nothing waiting, and no ball to feel it with
    ● 2 · no ball     two waiting, and you will only hear them from the Mac
    ○ · ball off      there is no link because you switched it off
    ● 2 · 87%         two waiting, the ball has them, and it has 87% left
    ● 2 · muted · 87% the same, with the sound switched off — it only buzzes

**The ball beside the words** (task 58). The item is a ball drawn in code,
never Nintendo's art, and it shows what the ball on the desk shows, in its
centre, where the real one's button ring lights (task 60). A held light — a
`done`'s 9 — is the centre in its colour (`Voice.tint`), rising and falling in
the shape the ball's own does (`STROLL_BREATH`); a `needs` holds none, since 199
plays once per beat and is dark between. Every beat flashes the centre in that
beat's colour, for as long as a catch plays (`lasts_s`), and it flashes white
once when a ball connects. Connected, its top half is red down to what is left
in the battery and its bottom half is filled; looking for one, it is hollow;
with the link switched off, or no ball mirror in this run, the whole ball is
faded (task 63). Once the ball is drawn the words keep only the count, because
the drawing is the dot, the link and the battery at once; when the seam cannot
draw it the title is exactly the table above.

The pulse is the one thing this file remembers between calls: until when the
last beat's light lasts. It is about the drawing and not about the queue — which
beat played is the core's, handed over in `beat` — and the ball mirror keeps the
same fact for the same reason (`Ball._linger`). The constitution's "no
animation" is read as being about the creature (tasks.md, 58): this is the
ball's own light, mirrored.

The hollow dot is the reason there is always something in the menu bar. An item
that disappeared when the queue emptied would make "nothing is waiting" and "the
daemon died" look identical, and telling those two apart from across the room is
the whole job (principle 7). Filled versus hollow carries the state that gets
read at a glance; the count is for when you actually look.

**A lost link is a drawing that cannot pass for a connected one** (task 63,
principle 7 as amended 2026-09-30). Until then criteria 8 and 9 asked for it in
words, because a quieter icon is indistinguishable from an icon you have stopped
noticing. A hollow ball is not a quieter connected one: a connected ball is never
hollow, since its bottom half is filled even at 0%. The words are one click away,
in the menu, and back in the title whenever the ball is not drawn. Faded is kept
for switched off alone, because faded reads as "disabled", and only that one is.

**"ball off" and "no ball" are different sentences, and different drawings, on
purpose.** They demand opposite things: one is "press the ball's button, it went
to sleep", the other is "you turned this off, nothing is wrong". Collapsing them
would leave somebody hunting a ball that is on the desk working perfectly.

**"muted" is in the title and not only in the menu** (task 34). A mute you have
forgotten about is a notifier that stopped, which is exactly what principle 7
forbids — and it is the one state here you cannot tell from the outside, because
a muted ball and a ball with nothing to say both make no sound. It sits before
the battery because it is about what this daemon will do and the percentage is
about the hardware, and it is a whole word for the same reason "no ball" is.
With the ball drawn, the word gives way to a crossed-out speaker beside it (task
61), asked for "just for now": a stopgap until the ball itself can show a mute.
When the ball is not drawn, or the mark cannot be, the word stays.

**The battery is the red, and its number is in the menu** (task 63). In the
words, when the ball is not drawn, the percentage replaces them rather than
joining them: a connected ball needs no "ball" in the title — the number is
only ever shown when there is one, so it says both things at once and keeps the
item narrow enough to live beside everything else in a menu bar.

**Left-click opens the menu, right-click presses B** — swapped at task 21, when
the menu stopped being a place to switch the radio and became the list of what
is waiting. The left click is what every other item on the strip answers with a
menu; the list reaches any project while B only ever takes the top of the queue;
and a stray click now costs an Escape instead of attending a signal that cannot
be un-attended. `platform_seam` decides which gesture is which, because it is
the only thing that sees them arrive — `ports.Status` says so in full.

That the ball's own link can be switched from that menu is not the menu bar
inventing state: the link is the ball mirror's, this asks it, and the answer
comes back through the same two facts this file already renders.

Quitting lives in that menu too, under a separator, and `items` says why that
is not the screen growing a feature the ball has not got.
"""
from __future__ import annotations

import math
import time
from typing import Callable

from .. import platform_seam
from ..core.attention import Standing, Status
from ..platform_seam.ports import Alternate, BallIcon
from ..core.ladder import Voice
from ..core.signals import Entry
from ..hooks import short


def render(pending: int, ball_connected: bool, *,
           ball_off: bool = False, battery: int | None = None,
           muted: bool = False, ball_drawn: bool = False) -> str:
    """The whole title, from the facts it is handed. Pure, so it can be checked
    against a table rather than against a screenshot.

    `ball_drawn` is the drawn ball being there beside it (task 58): the dot,
    the link, the battery and the mute are then the drawing's, and the words
    keep only the count (task 63).

    `ball_off` only means anything while disconnected — switching it off and
    being connected cannot both be true, and if they ever are, being connected
    is what a person needs to know.

    `muted` is shown with a ball and without one, because it silences both
    surfaces — the module docstring says why it is shown at all. A drawn ball
    carries it as a mark (task 61), so the word is only for when there is none.
    """
    if ball_drawn:
        return f"{pending}" if pending else ""
    parts = [f"● {pending}" if pending else "○"]
    if muted:
        parts.append("muted")
    if ball_connected:
        if battery is not None:
            parts.append(f"{battery}%")
    else:
        parts.append("ball off" if ball_off else "no ball")
    return " · ".join(parts)


# A line with no label at all: the seam turns it into a real separator. A label
# of `""` would be a blank line that reads as a bug, and a `None` handler is
# already taken — it means "a line to read, not to click".
SEPARATOR: tuple[None, None] = (None, None)


# How long a beat lights the drawn ball when its voice does not say (task 58).
# A CHOICE: about as long as 199 looks lit on the ball, never timed.
PULSE_S = 0.5
# The shape a held light rises and falls in (task 60): 9 with Pikachu's stroll
# LED, whose four steps are 20, 15, 0 and 9 units of ~52 ms — hold, fade to dark,
# nothing, fade back up — 2.27 s a cycle on camera (`docs/PROTOCOL.md` §8.2).
# MEASURED, and the same for every colour: `fc_blob`
# changes only the colours in that body.
STROLL_BREATH = (1.04, 0.78, 0.47)
# The white a ball connecting lights it with, and for how long — a CHOICE.
CONNECTED = "#FFFFFF"
CONNECTED_S = 0.8


# The four words agreed at the desk, 2026-09-28 (task 36).
STATUS_WORDS = {
    Status.SIGNALLING: "signalling",
    Status.WATCHED: "quiet, you're looking at it",
    Status.ATTENDING: "attending",
    Status.WAITING: "waiting its turn",
    Status.QUIET: "from before the restart",       # task 47
    Status.SEEN: "seen, kept quiet",               # task 68
    Status.SILENCED: "silenced until you type in it",  # task 68
}


def status_words(standing: Standing, *, countdown: bool = True) -> str:
    """A standing as words. The daemon's log asks for it without the countdown,
    so that a minute passing is not a line of its own."""
    said = STATUS_WORDS[standing.status]
    if countdown and standing.back_in is not None:
        # Whole minutes, rounded up: the menu is rebuilt when its words change,
        # so this is at most one rebuild a minute, and "back in 0m" is never shown.
        said += f" (back in {max(1, math.ceil(standing.back_in / 60))}m)"
    return said


def line(entry: Entry, standing: Standing | None = None, *, twin: bool = False) -> str:
    """One pending session, as one line of a menu.

    The mirror's own phrasing and not the daemon's: `daemon.describe` says the
    same two facts into a column where the project is already written down the
    left, so it deliberately leaves the project out. Here there is no column and
    the name is the thing you are choosing between, so it goes first. Principle
    1 gives the core *what is being said* and each surface *how to say it*; two
    surfaces phrasing one fact differently is that rule working rather than a
    second copy of it.

    `twin` is another line with the same project (task 41): only then does the
    session id tell the two apart, and only then is it worth the width.
    """
    name = f"{entry.project} · {short(entry.session)}" if twin else entry.project
    said = f"{name} — {entry.kind.value}"
    if standing is not None:
        said += f" · {status_words(standing)}"
    return said


def _aim(on_attend, session: str):
    """The handler for one row, or `None` when nothing was wired up.

    A function and not a lambda inside the loop, for one reason: `session` is a
    parameter here, so each row closes over its own id. Built in a
    comprehension instead, every row would close over the same variable and the
    whole list would attend whatever the last one was — the late-binding bug,
    which in a menu shows up as clicking one line and getting another.
    """
    if on_attend is None:
        return None
    return lambda: on_attend(session)


def items(ball_connected: bool, *, ball_off: bool = False,
          have_ball_mirror: bool = True, battery: int | None = None,
          pending: tuple[Entry, ...] = (),
          standing: dict[str, Standing] | None = None, muted: bool = False, on_attend=None, on_connect=None,
          on_disconnect=None, on_mute=None, on_quit=None, on_silence=None) -> list:
    """What the menu offers, as `(label, handler)` pairs.

    A `None` handler is a line that is only there to be read, and there are three
    kinds of those. One is the run started with `--no-ball`: offering "Connect" in a
    run that has no ball mirror behind it would be a button that does nothing,
    which is the silent failure principle 7 is written against. Another is an
    empty queue, and it is there for the same reason the dot is hollow rather
    than absent — a menu that shrank to the link and a way out would look like a
    daemon that had lost the queue, and saying "nothing is waiting" costs one
    greyed line and answers the question. The third is the link's state, above
    the line that changes it (task 63): the title stops saying it in words once
    the ball is drawn, and principle 7 as amended puts them one click away. The
    battery is a line only with a reading, for the reason the title never showed
    a percentage no ball said.

    **The pending list is the core's, rebuilt every refresh** (task 21).
    `queue.pending()` is already the order they should be dealt with — `needs`
    first, oldest first within a kind — so this renders that list and does not
    sort, filter or remember one of its own. A mirror holding its own copy of
    the queue is principle 1's failure, and here it would show up as a menu
    offering a session that stopped waiting a minute ago.

    **Each line's status is the core's too** (task 36): `standing` comes from
    `Attention.standing`, and this file only chooses the words. A row with no
    standing is shown without one, rather than guessed at.

    **Choosing a line is not a feature the ball has not got.** Principle 2 bars
    the screen from answering a notification in a way the ball cannot, and the
    ball reaches every one of these lines: B takes the top, B again skips to the
    next, and going round the queue that way arrives anywhere the list does. The
    menu is fewer gestures to the same place, which is a convenience about a
    surface rather than a power the ball lacks. What would break principle 2 is
    a line that *resolved* a signal, because finishing something is closing its
    session and no press of B has ever done it (criterion 7).

    **Quit is always the last line, and it is not a feature the ball is missing.**
    This is the boundary of principle 2 rather than a hole in it: stopping the
    daemon is not something the core can say — it is not a signal, a state or a
    queue — it is how you put down the process you started, in the one place
    this process has a handle. The ball cannot start the daemon either.

    **Two separators, and each one is keeping two unlike things apart.** Above
    the link, because choosing a project and switching the radio are different
    kinds of act; above quit, because the line over it switches the ball's link
    at the cost of a reconnect while this one ends the run, and only one of
    those is undone by choosing the opposite line.

    **The quiet ones go under a separator of their own** (task 47): what came
    back from before a restart is listed but not counted, and a line that
    looks like the ones above it would read as a signal that forgot to speak.
    The held entry is placed by its own flag, since the daemon appends it last.

    **Mute sits with the link and not with the queue** (task 34), because both
    lines are about how this daemon speaks rather than about what it has to say
    — and it goes above the link because it is the smaller act of the two: the
    sounds come back on the next click, while switching the radio costs a
    reconnect. It is offered in a `--no-ball` run as well, where it is the only
    one of the two that still does anything: the Mac sounds are muted by it too.

    **Each waiting line has a twin under ⌥, "Silence <project>"** (task 68),
    when `on_silence` is wired: the menu's half of B held on the ball, so it is
    no power the ball lacks. An `Alternate` label, so it takes a slot of its own
    and shows only while ⌥ is down. A session already silenced has none —
    typing in it is what lifts it, and a row that did nothing would be a lie.

    **Every line, separators included, holds its place in this list.** The seam
    tags each menu item with its index here, so a separator that did not take a
    slot would shift every handler below it onto the wrong line — see `Status.
    menu` in `platform_seam/macos.py`, and `learnings.md` for the session that
    cost. The list changing length between refreshes is fine and expected: the
    seam rebuilds the whole menu from it rather than editing the one it has.
    """
    if not have_ball_mirror:
        link = [("No ball in this run (--no-ball)", None)]
    elif ball_connected:
        link = [*([(f"Battery {battery}%", None)] if battery is not None else []),
                ("Disconnect the ball", on_disconnect)]
    else:
        # The wording splits the same way the drawing does: with the link switched
        # off this is a promise to go and look, and otherwise it is already
        # looking and the honest offer is to stop.
        link = [("Ball off", None), ("Connect the ball", on_connect)] if ball_off else [
            ("No ball — looking for one", None), ("Stop looking for the ball", on_disconnect)]
    # The label says what the click will do, not what is true now — "Muted" as
    # a state would be a line you read rather than a switch you press, and the
    # title already carries the state.
    mute = [("Unmute the sounds" if muted else "Mute the sounds", on_mute)]
    # `standing` is keyed by session, the same key a row aims at (tasks 36, 41).
    standing = standing or {}
    projects = [entry.project for entry in pending]
    rows: dict[bool, list] = {False: [], True: []}
    for entry in pending:
        twin = projects.count(entry.project) > 1
        said = standing.get(entry.session)
        rows[entry.quiet].append((line(entry, said, twin=twin),
                                  _aim(on_attend, entry.session)))
        if on_silence is not None and (said is None or said.status is not Status.SILENCED):
            name = f"{entry.project} · {short(entry.session)}" if twin else entry.project
            rows[entry.quiet].append((Alternate(f"Silence {name}"),
                                      _aim(on_silence, entry.session)))
    waiting = rows[False] + ([SEPARATOR] if rows[False] and rows[True] else []) + rows[True]
    return [*(waiting or [("Nothing waiting", None)]), SEPARATOR,
            *mute, *link, SEPARATOR, ("Quit wobble", on_quit)]


class Menubar:
    """The seam wiring: the title out, the click back in.

    `on_press` is handed straight to the seam. It is the same callable the
    daemon uses for Enter, on purpose — a click and a keypress are the same
    event arriving by different doors, and giving them separate paths is how the
    two slowly stop behaving alike.
    """

    def __init__(self, on_press: Callable[[], None], *, item: bool = True,
                 clock: Callable[[], float] = time.monotonic) -> None:
        # `item=False` is for a desk check that times a schedule. This daemon's
        # status item goes in the same menu bar as every other one, a click on
        # it is a B press, and a run that measures when signals stop must not be
        # endable by somebody clicking the wrong icon. Nothing in the seam is
        # touched at all in that mode: the item is created on first use, so not
        # using it is enough to not have one.
        self._item = item
        self._offered: list | None = None
        # The drawn ball (task 58): the pulse still lit as (colour, until, for),
        # how many there have been, the link as last seen so a connect is an
        # edge, and what was last drawn.
        self._clock = clock
        self._pulse: tuple[str, float, float] | None = None
        self._beats = 0
        self._connected = False
        self._drawn: BallIcon | None = None
        self._drew = False
        self._cannot_draw: str | None = None
        if item:
            platform_seam.status.on_click(on_press)

    def refresh(self, pending: int, *, ball_connected: bool,
                ball_off: bool = False, battery: int | None = None,
                muted: bool = False, have_ball_mirror: bool = True,
                menu: list | None = None,
                showing: Voice | None = None) -> str | None:
        """The title, the drawn ball and the menu, from what the core says now.

        `showing` is the voice whose light the ball should hold — the same one
        the ball mirror is handed — or `None` for dark. The battery reaches the
        drawing only while connected, and a link switched off, or none in this
        run, fades it (task 63). Returns why the ball
        could not be drawn as it should be, once, when that first becomes true
        or changes, as a sentence to say.
        """
        if not self._item:
            return None
        now = self._clock()
        if ball_connected and not self._connected:
            self._flash(CONNECTED, CONNECTED_S)
        self._connected = ball_connected
        if self._pulse is not None and now >= self._pulse[1]:
            self._pulse = None
        # Only a voice with a held light holds one here: the ball is dark
        # between a `needs`'s beats, and so is this.
        held = showing.tint if showing is not None and showing.light is not None else None
        pulse = self._pulse
        ball = BallIcon(ball_connected, held, pulse[0] if pulse is not None else None,
                        STROLL_BREATH if held is not None else None,
                        pulse[2] if pulse is not None else 0.0, self._beats, muted,
                        battery if ball_connected else None,
                        not ball_connected and (ball_off or not have_ball_mirror))
        news = None
        # Only when it changes, for the same reason as the menu below.
        if ball != self._drawn:
            self._drawn = ball
            self._drew, why = platform_seam.status.icon(ball)
            if why != self._cannot_draw:
                self._cannot_draw = why
                if why is not None:
                    news = why if self._drew else (
                        f"{why} — the menu bar keeps its dot in the words")
        platform_seam.status.show(
            render(pending, ball_connected, ball_off=ball_off, battery=battery,
                   muted=muted, ball_drawn=self._drew))
        # Only when the words change. `refresh` runs four times a second and
        # rebuilding an NSMenu at that rate would be a new menu under whatever
        # is currently open — the labels are the cheapest honest way to ask
        # whether anything actually moved.
        if menu is not None:
            words = [label for label, _ in menu]
            if words != self._offered:
                self._offered = words
                platform_seam.status.menu(menu)
        return news

    def beat(self, voice: Voice, *, ball_connected: bool) -> tuple[bool, str | None]:
        """Play this beat's Mac sound, if this beat has one to play here.

        Three ways a beat is silent on the Mac, and they are different facts:
        a ball is connected and already speaking, so the Mac would be a second
        voice for one event; the beat is silent everywhere (a muted beat, which
        on the ball is the light and its buzz alone); or the kind has no Mac sound configured at all.

        The `(ok, err)` from the seam is passed straight back up rather than
        being swallowed here — a sound that did not play is something the daemon
        has to be able to say out loud.

        Every beat lights the drawn ball, with a ball or without one (task 58):
        it mirrors the real ball, so it pulses whenever that one would.
        """
        if voice.tint is not None:
            self._flash(voice.tint, voice.lasts_s or PULSE_S)
        if ball_connected or voice.silent or voice.mac_sound is None:
            return False, None
        return platform_seam.sound.play(voice.mac_sound)

    def _flash(self, colour: str, seconds: float) -> None:
        self._beats += 1
        self._pulse = (colour, self._clock() + seconds, seconds)

    def quiet(self) -> None:
        """B was pressed: cut whatever is still sounding (criterion 4), and the
        light that went with it."""
        self._pulse = None
        platform_seam.sound.stop()
