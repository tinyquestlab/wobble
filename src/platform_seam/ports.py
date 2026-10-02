"""The services the MVP asks an operating system for, as `Protocol`s.

A port is a SERVICE with a small argument list and plain data on both sides —
play this file, raise the window whose title carries this, put this text in the
menu bar, tell me what is frontmost. Never a window, a menu, or an event loop.
Every method takes and returns plain data (`str`, `float`, `dict`, `tuple`,
`None`), so a Protocol can be satisfied by something that has never imported
PyObjC — which is exactly what `null.py` is.

Four, because `plan.md` names four. A port arrives here when a task needs it — and
task 40 needed a fifth, `Process`, to ask whether a session's claude still runs,
and task 64 a sixth, `Idle`, to ask whether anybody is at the keyboard.

`@runtime_checkable` makes `isinstance(x, Sound)` a real check on method names —
the cheapest proof that an implementation did not drift from what it claims.
"""
from __future__ import annotations

from typing import Callable, NamedTuple, Protocol, runtime_checkable


class Alternate(str):
    """A menu label shown in place of the line above it while ⌥ is held (task 68).

    Still a `str`, so every caller that reads a menu as words reads it the same;
    only `Status.menu` asks which kind it is. A row for doing something rarer to
    the same line — silencing a session rather than going to it — and hidden
    until asked for, the way macOS hides its own.
    """

    __slots__ = ()


class BallIcon(NamedTuple):
    """The menu bar's ball, as plain data (task 58): a tuple, like every other
    thing that crosses this seam.

    `connected` fills the top half. Every light is in the centre, where the
    real ball's button ring is (task 60). `centre` is the colour of the light
    the ball is holding, or `None` for none, and `breath` the shape it rises
    and falls in: `(hold, fall, rise)` in seconds, or `None` to hold it still.
    `pulse` is the colour the centre flashes for a moment — a beat, a catch, a
    ball connecting — or `None`, and `pulse_s` how long that flash plays.
    `beat` counts the flashes, so two alike in a row are still two. The
    colours are `#RRGGBB`, the core's `Voice.tint`. `muted` sets a crossed-out
    speaker beside the ball, in place of the title's word (task 61).

    `battery` is the percentage left in a connected ball, or `None` for no
    reading, and the top half is filled down to it; `off` fades the whole ball,
    for a link switched off or a run with no ball mirror (task 63).
    """

    connected: bool
    centre: str | None = None
    pulse: str | None = None
    breath: tuple[float, float, float] | None = None
    pulse_s: float = 0.0
    beat: int = 0
    muted: bool = False
    battery: int | None = None
    off: bool = False


@runtime_checkable
class Sound(Protocol):
    """Play (and stop) one sound file. This is the no-ball mode's voice: when
    no ball is connected the Mac makes the sound instead (criterion 8).

    `play` returns `(ok, err)` rather than raising, because a notifier that dies
    on a missing audio file has become the silence it exists to prevent
    (principle 7). `stop` exists because dismissing has to cut a sound already
    playing — the click is the B button, and B means silence now (criterion 4).
    """

    def play(self, path: str, volume: float | None = None) -> tuple[bool, str | None]: ...

    def stop(self) -> None: ...


@runtime_checkable
class Frontmost(Protocol):
    """What is in front, right now — plain data, never an AppKit object.

    `app` returns `None` when it cannot tell, which is a different answer from
    "no app is frontmost" and callers must not collapse the two.

    `title` is the window, not the app, and it exists so that a signal can stay
    quiet while you are already looking at the session that raised it. Whether a
    given title IS that session is not asked here: matching a hint against a
    title is ordinary string work with no operating system in it, so it lives in
    the core (`Entry.in_window`) and this side answers only the fact.

    **`title` returns `(title, why not)` and BOTH can be `None`.** Three answers
    in two fields, and the caller has to keep them apart:

      - `("Install_hooks.py — wobble", None)` — this is the window in front.
      - `(None, "…")` — nobody could be asked, and the sentence says why. The
        caller must carry on as though nothing were in front: a check that
        cannot run must not be able to silence a notification (principle 7).
      - `(None, None)` — asked, answered, and there is genuinely no window in
        front to name. A locked screen is this one, deliberately: you are not
        looking at anything, and it is not an error that nothing could be read.

    That is the opposite convention to `Focus.window` below, where a bare
    `False` is forbidden — and the reason is that here the uninteresting answer
    is the common one. This is asked on every poll for as long as something is
    pending, so a sentence attached to every "no" would be a sentence four times
    a second.
    """

    def app(self) -> dict | None: ...

    def title(self) -> tuple[str | None, str | None]: ...

    def window(self) -> tuple[str | None, str | None, str | None]:
        """`(title, app, why not)`: `title()`'s answer, with the bundle id of the
        app that owns that window — `None` when it cannot be named. From the same
        read as the title, so the two can never belong to different windows.
        Task 38: a title alone is shared by every app showing the same folder."""
        ...

    def tab_tty(self, app: str, *, timeout: float = 2.0) -> tuple[str | None, str | None]:
        """`(tty, why not)`: the tty of the tab in front in terminal `app`,
        `ttys003`. The same three answers as `title`: a tty; `(None, "…")`,
        nobody could be asked; `(None, None)`, asked, and no tab is in front.
        It blocks for an Apple event, so it is never asked on the daemon's own
        loop. Task 43: Terminal's titles do not say which claude a tab holds."""
        ...


@runtime_checkable
class Focus(Protocol):
    """Bring forward the window whose title carries `hint` (criterion 4).

    `(ok, err)` and not an exception, for the reason criterion 10 exists:
    Accessibility can be refused, and when it is, focusing is skipped and the
    refusal is said in words — while the notification itself still works. `err`
    is that sentence. Returning `(False, None)` is not allowed: a failure with
    no reason is the silence principle 7 forbids.

    **`ok` carries a sentence too (task 38): what came forward.** The log used
    to say "its window came forward" and never which one, so a raise that
    landed on the wrong window read exactly like the right one at the desk.

    `fits` is the core's rule for "is this title the project's window"
    (`Entry.names`); without it, `hint` is a substring of the title. `app` is
    the bundle id the session runs in: given, only that app is looked in, and
    when none of its windows fits the app itself comes forward — a terminal open
    in the same folder must never take the raise from the editor running the
    session. Two windows of one app that both fit are still indistinguishable;
    the first is focused — a known edge in `spec.md`.

    `folder` (task 69) is the session's own folder, given only for an app that
    answers "open this folder" with the window already holding it: when no
    window of `app` fits — macOS lists only the current desktop's — the folder
    is opened in `app`, which brings that window forward wherever it is. The
    reason names `folder` then, and only then: it is how the caller tells a
    desktop switch from a plain raise.
    """

    def window(self, hint: str, *, app: str | None = None,
               fits: Callable[[str], bool] | None = None,
               folder: str | None = None,
               timeout: float = 1.5) -> tuple[bool, str | None]: ...

    # **Two ways to the very session, not just its app (task 42).** Both answer
    # like `window`, and neither falls back on its own: when one fails the caller
    # says so and asks `window`, so the log shows which way B actually went.

    def url(self, url: str, *, app: str,
            timeout: float = 1.5) -> tuple[bool, str | None]:
        """Open an address the session's own app (`app`, a bundle id) gave for
        it, and say whether that app came forward. The caller checks the
        address; this opens what it is handed."""
        ...

    def tab(self, tty: str, *, app: str,
            timeout: float = 30.0) -> tuple[bool, str | None]:
        """Select the tab of terminal `app` whose tty is `tty` (`ttys003`), and
        bring it forward. `timeout` is long because the first ask can wait on
        a consent dialog a person has to answer."""
        ...

    def ask(self) -> tuple[bool, str | None]:
        """Whether raising is permitted; when it is not, ask the OS's own way
        (task 50). `(True, None)` granted, `(False, "…")` not yet, saying what
        was asked and what to do. It never waits for the answer."""
        ...


@runtime_checkable
class Process(Protocol):
    """Facts about another process, by pid (task 40).

    **`started` returns `(when, why not)`, three answers like `Frontmost.title`:**

      - `(1790468288.77, None)` — it runs, and started then (epoch seconds).
      - `(None, None)` — asked, and there is no process with that pid.
      - `(None, "…")` — nobody could be asked. The caller must keep the session
        as though it ran: a check that cannot run must not be able to take a
        signal out of the queue (principle 7).

    The start time is what tells a claude from whatever was later handed its
    pid; comparing it to the registry is Claude Code knowledge and lives in
    `hooks.Running.alive`.
    """

    def started(self, pid: int) -> tuple[float | None, str | None]: ...

    def tty(self, pid: int) -> tuple[str | None, str | None]:
        """The pid's controlling terminal, `ttys003`, as `started` answers:
        `(None, None)` when it has none or is gone, `(None, "…")` when nobody
        could be asked (task 42)."""
        ...

    def title(self, pid: int, text: str) -> tuple[bool, str | None]:
        """Name the terminal tab the pid runs in `text`, as an OSC 2 on its tty
        (task 43). `(True, "…")` when written, `(False, "…")` saying why not:
        a tab left unnamed is watched by folder only, which is the loud side."""
        ...

    def children(self, pid: int) -> tuple[tuple[int, ...] | None, str | None]:
        """The pids this pid started that still run: `()` for none or gone,
        `(None, "…")` when nobody could be asked (task 65)."""
        ...

    def command(self, pid: int) -> tuple[tuple[str, ...] | None, str | None]:
        """The pid's argv, as `started` answers: `(None, None)` when it is
        gone, `(None, "…")` when it could not be read (task 65)."""
        ...


@runtime_checkable
class Idle(Protocol):
    """How long since anybody touched the keyboard or the mouse (task 64).

    `seconds` returns `(how long, why not)`: `(12.4, None)`, or `(None, "…")`
    when nobody could be asked. The caller treats an unknown as somebody being
    there — the behaviour before this port — and says so once.
    """

    def seconds(self) -> tuple[float | None, str | None]: ...


@runtime_checkable
class Status(Protocol):
    """The menu bar item — owned by the seam, written by the mirror.

    The item is not kept by the caller with the seam writing onto it. CLAUDE.md
    is stricter than that: nothing OS-specific lives outside this
    package, and an `NSStatusItem` held by `mirrors/menubar.py` would be exactly
    that. So the item is created, held and destroyed in here, and the mirror only
    ever hands over a string.

    `on_click` is how the press gets back across the seam — it is the B button
    when there is no ball (criterion 8), so it is input, not chrome.

    **Who owns the run loop — settled at task 12: the caller does.** `pump()` is
    that answer. A status item needs somebody to deliver its events, and the two
    ways to do that are to hand the thread to the UI framework and be called
    back, or to keep the thread and ask the framework what it is holding. The
    daemon already owns a loop that polls a file four times a second, so it asks:
    `pump()` returns immediately, having delivered whatever had arrived. Nothing
    in this project runs on a second thread, and no call has to be marshalled
    onto one. The cost is that a click is seen up to one poll interval late,
    which for a notification that has been waiting for somebody to walk back to
    the desk is nothing at all.

    An implementation with no event loop behind it — `null` — does nothing here,
    and that is not a stub: there is genuinely nothing holding an event for it.

    **Two doors, and task 21 swapped which gesture opens which.** A left click
    opens whatever `menu` was last handed; a right click — or a control-click,
    the same intent from a trackpad — is the B button (criterion 8). It was the
    other way round from task 12 until the menu grew the list of what is
    waiting: the left click is the gesture every other item on the strip answers
    with a menu, the list reaches every project while B only ever takes the top
    of the queue, and an accidental click should cost an Escape rather than
    attend a signal that cannot be un-attended. The seam is where this is
    decided, because AppKit is the only thing that knows which gesture arrived.

    Items are plain data like everything else here — `(label, handler)`, with a
    `None` handler for a line that is only there to be read and a `None` label
    for a separator. The mirror rebuilds the whole list whenever it changes
    rather than mutating one; a menu is small, and the alternative is a second
    place the state lives.

    **`icon` draws the ball beside the title** (task 58), and answers `(ok, why
    not)` like `Sound.play`: a ball that could not be drawn is said, and the
    mirror keeps the dot in the words instead, so the item never loses the
    state it carries. How the ball is drawn is the seam's — the mirror hands
    over three facts, never a path or an image.

    **It blocks while it is open.** A menu runs its own tracking loop, so the
    `pump()` that opened it does not return until the menu is dismissed. The
    daemon's tick stops for that long. That is accepted rather than worked
    around: the alternative is a second thread, which nothing in this project
    has, and the BLE link is held by the OS rather than by this process, so a
    second or two of a stopped Python loop does not drop the ball.
    """

    def show(self, title: str) -> None: ...

    def icon(self, ball: BallIcon) -> tuple[bool, str | None]: ...

    def on_click(self, handler: Callable[[], None]) -> None: ...

    def menu(self, items: list[tuple[str | None, Callable[[], None] | None]]) -> None: ...

    def pump(self) -> None: ...
