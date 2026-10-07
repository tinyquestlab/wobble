"""Every port, with nothing on the other end — the no-platform implementation.

**Honest, not silent.** A no-op that swallowed the call and returned nothing
would let a headless run pass by accident, and that is the one failure this
project cannot have (principle 7). So every method returns the neutral value the
real one returns in its least capable real case — never an exception, never a
value a caller cannot use, and never a `False` with no reason attached.

Every call is recorded in `CALLS` as `(port.method, args)`. A module-level list
rather than one per instance, because `__init__.py` builds the singletons once at
import time and what you want to see is the order across all of them.
`CALLS.clear()` resets it.
"""
from __future__ import annotations

CALLS: list[tuple] = []


def _record(name: str, *args) -> None:
    CALLS.append((name, args))


class Sound:
    def play(self, path: str, volume: float | None = None) -> tuple[bool, str | None]:
        _record("Sound.play", path, volume)
        return False, "no platform: no sound was played"

    def stop(self) -> None:
        _record("Sound.stop")


_NO_FRONT = ("no platform: there is no way to see which window is in "
             "front, so signals are played whether or not you are "
             "already looking at the session that raised them")


class Frontmost:
    def app(self) -> dict | None:
        _record("Frontmost.app")
        return None

    def title(self) -> tuple[str | None, str | None]:
        # A sentence and not a bare `(None, None)`, and the difference decides
        # behaviour rather than wording. `(None, None)` means "asked, and there
        # is no window in front", which is a fact this has no way to establish.
        # What is true here is that nobody can be asked — so it is the
        # could-not-tell answer, the caller signals as it always would, and the
        # reason is there to be printed.
        _record("Frontmost.title")
        return None, _NO_FRONT

    def window(self) -> tuple[str | None, str | None, str | None]:
        # Its own entry, not title()'s: the docstring promises every call is
        # recorded under its own name, and a borrowed one hides who asked.
        _record("Frontmost.window")
        return None, None, _NO_FRONT

    def tab_tty(self, app: str, *, timeout: float = 2.0) -> tuple[str | None, str | None]:
        _record("Frontmost.tab_tty", app)
        return None, "no platform: no terminal can be asked which tab is in front"


class Focus:
    def window(self, hint: str, *, app: str | None = None, fits=None,
               folder: str | None = None,
               timeout: float = 1.5) -> tuple[bool, str | None]:
        _record("Focus.window", hint, timeout)
        return False, "no platform: no window was raised"

    def url(self, url: str, *, app: str, timeout: float = 1.5) -> tuple[bool, str | None]:
        _record("Focus.url", url, app)
        return False, "no platform: no address was opened"

    def tab(self, tty: str, *, app: str, timeout: float = 30.0) -> tuple[bool, str | None]:
        _record("Focus.tab", tty, app)
        return False, "no platform: no tab was selected"

    def ask(self) -> tuple[bool, str | None]:
        _record("Focus.ask")
        return False, "no platform: there is no permission to ask for"


class Process:
    def started(self, pid: int) -> tuple[float | None, str | None]:
        # The could-not-tell answer, never `(None, None)`: that one says the
        # process is gone, and would take its signal out of the queue.
        _record("Process.started", pid)
        return None, "no platform: there is no way to ask whether a process still runs"

    def tty(self, pid: int) -> tuple[str | None, str | None]:
        _record("Process.tty", pid)
        return None, "no platform: there is no way to ask which terminal a process is on"

    def title(self, pid: int, text: str) -> tuple[bool, str | None]:
        _record("Process.title", pid, text)
        return False, "no platform: there is no terminal to name a tab on"

    def children(self, pid: int) -> tuple[tuple[int, ...] | None, str | None]:
        # Could-not-tell, never `()`: an empty list is a fact this cannot know.
        _record("Process.children", pid)
        return None, "no platform: there is no way to ask what a process started"

    def command(self, pid: int) -> tuple[tuple[str, ...] | None, str | None]:
        _record("Process.command", pid)
        return None, "no platform: there is no way to read a process's command line"


class Idle:
    def seconds(self) -> tuple[float | None, str | None]:
        _record("Idle.seconds")
        return None, "no platform: there is no way to ask when a key or the mouse last moved"


class Login:
    def state(self) -> tuple[str | None, str | None]:
        _record("Login.state")
        return None, "no platform: there is no way to open wobble at login"

    def set(self, on: bool) -> tuple[bool, str | None]:
        _record("Login.set", on)
        return False, "no platform: nothing was set to open at login"

    def settings(self) -> tuple[bool, str | None]:
        _record("Login.settings")
        return False, "no platform: there is no list of what opens at login to show"


class Status:
    # Nothing to write to, and no shadow title kept — the state is already in the
    # core, and a mirror of a mirror is just somewhere else to be wrong.
    def show(self, title: str) -> None:
        _record("Status.show", title)

    def icon(self, ball) -> tuple[bool, str | None]:
        # Refused, so the mirror keeps its dot in the words: with no menu bar
        # there is nothing to draw in, and the title is all a check can read.
        _record("Status.icon", ball)
        return False, "no platform: there is no menu bar to draw a ball in"

    def on_click(self, handler) -> None:
        # Registered and never called: there is no item to click. The handler is
        # held anyway so a caller can see it was installed.
        _record("Status.on_click", handler)

    def menu(self, items) -> None:
        # The labels are recorded and the handlers are not: with no item there
        # is nothing to click at all, so what a check can usefully ask is what
        # the mirror decided to offer, and a list of bound methods answers that
        # less clearly than the words do.
        _record("Status.menu", [label for label, _ in items])

    def pump(self) -> None:
        # No event loop, so nothing is ever holding an event for us.
        #
        # The one method that is NOT recorded, and the exception is the reason:
        # every other call here happens because something decided to make it,
        # a handful of times. This one is called on a timer, four times a
        # second for as long as the daemon runs — recording it would bury the
        # decisions in a list of heartbeats, and grow without limit in exactly
        # the mode this project is developed in.
        pass
