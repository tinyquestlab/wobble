"""What is being said, and what is still waiting to be said.

The vocabulary and the queue, and nothing else: no BLE, no AppKit, no
`osascript`, no clock. A mirror asks this what is pending and renders it; it
never invents a row of its own (constitution principle 1), which is also why
everything handed out of here is frozen.

**There is no clock in this file on purpose.** Every event carries the moment it
happened, so ordering is a property of the data rather than of when somebody
asked. That keeps the core free of the one OS service it would otherwise need,
and it means the whole queue can be checked without waiting for real seconds to
pass — `tests/tables/check_queue.py` runs a ten-minute story in no time at all.
Task 09's safety net will take `now` as an argument for the same reason.

The rules here come from `plan.md` and `spec.md`, not from taste:

  - `needs` always goes to the top. Somebody is stopped.
  - within a kind, oldest first: the one that has waited longest is next.
  - one entry per **session**. A session that signals twice is still one
    thing waiting for you; two sessions in the same folder are two.

**That last rule has changed twice.** Per session until 2026-09-23, then per
project (task 20): two sessions in one folder were taken to be one window, and
a session whose tab closed without a prompt left an entry nothing could
resolve. The second reason went away with task 22 (a session's end resolves
it) and task 40 (so does its process dying). The first stopped being true on
2026-09-28 (task 41): the same folder open in Warp and in the Claude desktop
app is two places to go, and tasks 42-43 raise and watch each session by itself
— by its tab, its tty, its desktop id. One entry per project would have raised
one of them and silenced both.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum


class Kind(str, Enum):
    """What happened to a session.

    A `str` enum because this value is written into `var/events` by the hooks
    (task 11) and is the key into `config/signals.json` (task 10) — it has to
    survive a round trip through JSON with no translation table in between.
    `Kind("needs")` is how a caller at that boundary turns text back into one,
    and it raises on anything else rather than inventing a third kind.
    """

    DONE = "done"      # the session finished
    NEEDS = "needs"    # the session is blocked, waiting on you


# The whole priority rule, as data. `needs` above `done` because someone is
# stopped (plan.md) — reading it off a tuple rather than a comparison keeps the
# rule in one place and makes a third kind a one-line change rather than a hunt.
ORDER: tuple[Kind, ...] = (Kind.NEEDS, Kind.DONE)

# The one host whose titles are measured (task 38): `__CFBundleIdentifier` of a
# Claude Code session in the VS Code extension, read from its own environment
# 2026-09-28. `Entry.names` says what it changes.
VSCODE = "com.microsoft.VSCode"
# Warp's, the host a hook line carries for a session in it (task 42). Its window
# title is the active tab's, and the daemon names each claude's tab (task 43).
WARP = "dev.warp.Warp-Stable"
# Terminal's. Its tabs are told apart by tty, not by title (task 43).
TERMINAL = "com.apple.Terminal"
# The Claude desktop app's, from its hook lines in var/events (21 of them by
# 2026-09-29). Its window is titled `Claude`, never the folder (task 51).
DESKTOP = "com.anthropic.claudefordesktop"


@dataclass(frozen=True, slots=True)
class Event:
    """One thing that happened, as the hooks will hand it over (task 11).

    `at` is a moment on a monotonic clock, supplied by whoever saw the event.
    The core never reads a clock itself — see the module docstring.
    """

    session: str
    kind: Kind
    project: str
    at: float
    window_hint: str = ""
    # The app the session runs in, as a bundle id — `""` when the hook line
    # carried none (an old line, or a host that sets no bundle). Task 38.
    host: str = ""
    # The turn ended in an API error (`StopFailure`), not a `Stop` (task 64).
    failed: bool = False
    # How long the turn ran, from the prompt a person typed to this event, or
    # `None` when no prompt was seen (task 64).
    turn_s: float | None = None

    def __post_init__(self) -> None:
        if not self.session:
            raise ValueError(
                "an event with no session id cannot be resolved by the prompt "
                "that answers it, and two of them would silently become one "
                "thing waiting inside their project")
        if not self.project:
            raise ValueError(
                "an event with no project has no name to be shown by and no "
                "window to be found by: the project is the menu's label and "
                "the window hint's default")
        if not isinstance(self.kind, Kind):
            raise TypeError(
                f"kind is {self.kind!r}; pass a Kind. At a text boundary — the "
                f"event file, a config key — use Kind(value), which refuses "
                f"anything that is not one of {[k.value for k in Kind]}")


@dataclass(frozen=True, slots=True)
class Waiting:
    """One session waiting: what the queue actually keeps. See `Entry`.

    `since` is when this session entered THIS kind, and `at` is its newest
    event. They differ on purpose. A session that has been blocked for ten
    minutes and signals `needs` again is still blocked since ten minutes ago —
    `since` holds, so it keeps its place in the order and does not quietly go
    to the back by repeating itself. A session whose kind CHANGES starts a new
    wait: finishing at 12:00 and blocking at 12:10 is something that has been
    blocking for nothing, not for ten minutes.
    """

    session: str
    kind: Kind
    project: str
    window_hint: str
    since: float
    at: float
    host: str = ""
    # Back from before a restart (task 47): kept, listed, reachable by B once
    # nothing live is waiting, and never signalled. Only a new event from the
    # session makes it live again — `Queue.add` builds a fresh row. Also a
    # `done` back from a snooze or a let-go, and a silenced session (task 68).
    quiet: bool = False
    # From its event (task 64): what the Signaller picks a mood from.
    failed: bool = False
    turn_s: float | None = None
    # Put back after a snooze or a let-go (task 64): it was ignored once, so
    # it starts at the call. Cleared by `Queue.add`, like `quiet`.
    returned: bool = False

    @property
    def rank(self) -> int:
        """Its place in `ORDER`. Lower sorts first."""
        return ORDER.index(self.kind)


@dataclass(frozen=True, slots=True)
class Entry:
    """One session waiting for you: what a mirror renders and what B takes.

    Frozen, and derived. The queue builds it on the way out from the session's
    `Waiting`, so there is no second copy of the truth to go stale — the same
    reason the mirrors are handed frozen rows.

    **`waiting` is a tuple of one since task 41** (2026-09-28). From task 20 it
    held every session of a project, with the most urgent one leading and the
    rest falling back into view when it was answered. The shape is kept rather
    than narrowed to a single field so `restore` and the hold can still carry
    an entry whole, and the queue is what now guarantees there is one.
    """

    project: str
    window_hint: str
    waiting: tuple[Waiting, ...]
    # The session's app, as a bundle id (task 38).
    host: str = ""

    def __post_init__(self) -> None:
        if not self.waiting:
            raise ValueError(
                f"an entry for {self.project!r} with nothing waiting in it is a "
                f"row that would be rendered, counted and signalled with no "
                f"session behind it — the queue drops the session instead")

    @property
    def lead(self) -> Waiting:
        """The session that gives this entry its kind and its place in line."""
        return self.waiting[0]

    @property
    def kind(self) -> Kind:
        return self.lead.kind

    @property
    def since(self) -> float:
        """How long this session has been waiting in its current kind."""
        return self.lead.since

    @property
    def at(self) -> float:
        """The newest event from anything in it."""
        return max(w.at for w in self.waiting)

    @property
    def session(self) -> str:
        """The session this entry is: what the queue, the hold and the menu key by.

        An identity again since task 41, having been reporting-only while the
        queue was keyed by project (task 20).
        """
        return self.lead.session

    @property
    def rank(self) -> int:
        """Its place in `ORDER`. Lower sorts first."""
        return self.lead.rank

    @property
    def quiet(self) -> bool:
        """Back from before a restart, and not signalled (task 47). See `Waiting`."""
        return self.lead.quiet

    @property
    def failed(self) -> bool:
        """Its turn ended in an API error (task 64). See `Event`."""
        return self.lead.failed

    @property
    def turn_s(self) -> float | None:
        """How long its turn ran, or `None` (task 64). See `Event`."""
        return self.lead.turn_s

    @property
    def returned(self) -> bool:
        """Back from a snooze or a let-go (task 64). See `Waiting`."""
        return self.lead.returned

    def __len__(self) -> int:
        """How many sessions are waiting in it: one, since task 41."""
        return len(self.waiting)

    def in_window(self, title: str | None, app: str | None = None, *,
                  own: frozenset[str] = frozenset(),
                  tabs: frozenset[str] = frozenset(),
                  tty: str | None = None) -> bool:
        """Whether `title`, in front in `app`, is the window this session runs in.

        Here rather than in the seam because there is no operating system in
        this: it is string work, and `Focus.window` is handed `names` below to
        find the window to raise, so the two can never disagree. Asking it on
        this side means the rule can be checked with no Mac in the room, and
        means a second platform inherits it rather than reimplementing it.

        `None` — nobody could be asked what is in front, or there is nothing in
        front — is `False`, and that direction is the whole safety of it: not
        knowing must never be able to silence a signal (principle 7).

        **The app comes first (task 38).** A title is shared by every app that
        happens to show the folder's name: a plain terminal open in `wobble`
        read as the VS Code session running there. So a session that knows its
        app is only ever watched from inside that app; `app=None` — the front
        app could not be named — falls back to the title alone, as before.

        **In VS Code, a Claude tab in front is that session only (task 43).**
        The title is `<active tab> — <folder>`. `tabs` is every title a Claude
        session's tab may carry (the registry's name, and its transcript's
        titles, `hooks.Titles`), and `own` is this session's. When the active tab
        is one of them, only a session that owns it is watched, so a twin in the
        same folder keeps signalling. When it is anything else (a file,
        `tasks.md — wobble` at the desk 2026-09-28), the folder rule stands: the
        Claude panel may be open beside it, and a cry while you read the code
        next to it is the false alarm that teaches you to ignore the ball.

        **In Warp, the tab the daemon named is that session only (task 43).**
        The window's title is the active tab's, and the daemon writes each
        claude's as `<project> · <id4>` (measured 2026-09-28: `claude` became
        `myproject · d711` 0.3 s after the write). `tabs` holds every name written,
        `own` this session's. Any other title keeps the folder rule.

        **In Terminal, the tab's tty is that session only (task 43).** `tty` is
        the tab in front's, and there `tabs` holds every claude's tty and `own`
        this session's. The tty decides alone, title or not: it names the tab,
        and what claude writes into the title does not. A tab with no claude,
        or a tty nobody could read, keeps the folder rule.
        """
        if self.host and app and app != self.host:
            return False
        if self.host == TERMINAL and tty and tty in tabs:
            return tty in own
        if not self.names(title):
            return False
        if self.host == VSCODE and title and " — " in title:
            tab = title.rsplit(" — ", 1)[0].strip()
        elif self.host == WARP and title:
            tab = title.strip()
        else:
            return True
        return tab in own if tab in tabs else True

    def here(self, title: str | None, app: str | None = None, *,
             own: frozenset[str] = frozenset(),
             tabs: frozenset[str] = frozenset(),
             tty: str | None = None) -> bool:
        """Whether you are still at this session while it is held (task 51).

        `in_window`, with one difference: the desktop app counts whole. Its
        window is titled `Claude`, so no title ever names the folder and it is
        never watched — the loud choice for a signal (task 40). For a hold the same answer would be the
        quiet one: it would never see you arrive, so it could never see you
        leave, and the hold would last the whole snooze.
        """
        if self.host == DESKTOP:
            return app == DESKTOP
        return self.in_window(title, app, own=own, tabs=tabs, tty=tty)

    def names(self, title: str | None) -> bool:
        """Whether a window called `title` is this session's folder, whatever app it is in.

        VS Code titles a window `<tab> — <folder>`, and the tab is whatever you
        named the conversation: `Wobble needs setup — otherproject` held the word
        `wobble` and silenced wobble's signal from otherproject's window, and took
        its B raise, seen at the desk 2026-09-28 (task 38). So there it is the
        last segment, whole. Every other app keeps the substring it had: their
        titles are not measured yet, and a rule written blind is a guess.
        """
        if not title or not self.window_hint.strip():
            return False
        hint = self.window_hint.casefold()
        if self.host == VSCODE:
            return title.rsplit(" — ", 1)[-1].strip().casefold() == hint.strip()
        return hint in title.casefold()


class Queue:
    """What is pending, in the order it should be dealt with.

    One entry per session (task 41). A second event from a session already
    waiting updates it rather than adding a row: a row per event lets a chatty
    session flood the list, and a count that climbs while one thing is wrong is
    a count nobody reads.
    """

    def __init__(self) -> None:
        # Keyed by session, and read out one entry per session (task 41).
        #
        # Insertion order is load-bearing: `sorted` is stable, so two things
        # with the same kind and the same `since` come out in the order they
        # first arrived, and updating a key does not move it — so "first
        # arrived" keeps meaning first arrived.
        self._waiting: dict[str, Waiting] = {}
        # Sessions silenced by hand (task 68): every row of theirs is quiet,
        # new ones included, until `unsilence`. Kept apart from the rows so a
        # session with nothing waiting stays silenced for its next event.
        self._silenced: set[str] = set()

    def add(self, event: Event) -> Entry:
        """File `event`, and return the entry it landed in.

        A kind that changes restarts that session's wait; a kind that repeats
        does not. See `Waiting`. A silenced session's row is born quiet (task 68).
        """
        old = self._waiting.get(event.session)
        keeps_waiting = old is not None and old.kind is event.kind
        self._waiting[event.session] = Waiting(
            session=event.session,
            kind=event.kind,
            project=event.project,
            window_hint=event.window_hint,
            since=old.since if keeps_waiting else event.at,
            at=event.at,
            host=event.host,
            quiet=event.session in self._silenced,
            failed=event.failed,
            turn_s=event.turn_s,
        )
        entry = self.get(event.session)
        assert entry is not None    # it was just put in
        return entry

    def holds(self, session: str) -> bool:
        """Whether this exact session is waiting right now.

        Asked by `attention._take` (task 33), which needs the answer from
        *before* a `drop` that is about to remove it — the one fact `restore`'s
        guard below reads, taken away by the line above the call.
        """
        return session in self._waiting

    def restore(self, entry: Entry, superseded: frozenset[str] = frozenset(), *,
                at: float | None = None) -> bool:
        """Put an entry back, minus any session that has signalled since.

        The snooze uses this: you dismissed something, never went back to it,
        and it returns (`attention.tick`). With `at`, each session comes back
        with that as its `since`, so it joins the back of its kind (task 54):
        until 2026-09-29 it kept its original `since` and landed where it was,
        so a skipped one cut in front of what had waited behind it. `since` is
        read for the order and nothing else. Without `at`, the order it had.
        With it, each one is marked `returned` as well (task 64): both doors
        that pass `at` are a signal coming back after being let go.

        **A `done` that comes back with `at` comes back quiet** (task 68): you
        took it with B, so it has been seen, and it stays listed and reachable
        by B without calling again — asked for at the desk, 2026-10-01: a done
        taken with B snoozes 5 minutes, does not ring again, and only stays in
        the queue. A `needs` comes back live:
        somebody is still stopped. A silenced session comes back quiet either way.

        A session that signalled again while it was being attended already has
        a newer row here, and that one wins: re-filing the old one would put a
        stale kind over a fresh one. `False` says nothing at all went back,
        which is the case worth saying out loud.

        `superseded` names sessions that must be refused for that same reason
        even though nothing of theirs is here any more, because the caller
        removed it between reading and restoring. Being present is the only
        evidence this method has, and a caller that destroys the evidence has to
        carry it instead — `drop(session)` on the session now being attended is
        exactly that caller, and task 33 is what it cost: the stale kind went
        back over the fresh one, and the menu showed one project twice, once
        under a kind that had already been answered.
        """
        back = False
        for waiting in entry.waiting:
            if waiting.session in self._waiting or waiting.session in superseded:
                continue
            quiet = waiting.quiet or waiting.session in self._silenced
            self._waiting[waiting.session] = (
                replace(waiting, quiet=quiet) if at is None else
                replace(waiting, since=at, returned=True,
                        quiet=quiet or waiting.kind is Kind.DONE))
            back = True
        return back

    def silence(self, session: str) -> None:
        """Make a session quiet until `unsilence`, its new events too (task 68).

        Its row, if it has one, goes quiet now: listed under the separator,
        reachable by B, never signalled. A session with nothing waiting is
        silenced all the same, for the hold that is about to put it back.
        """
        self._silenced.add(session)
        waiting = self._waiting.get(session)
        if waiting is not None:
            self._waiting[session] = replace(waiting, quiet=True)

    def unsilence(self, session: str) -> bool:
        """End a session's silence, and say whether it had one (task 68).

        Its rows are not woken: what ends a silence is a prompt or an answer,
        and those resolve what was waiting. The next event is live again.
        """
        was = session in self._silenced
        self._silenced.discard(session)
        return was

    def silenced(self, session: str) -> bool:
        """Whether that session is silenced by hand (task 68)."""
        return session in self._silenced

    def drop(self, session: str) -> Entry | None:
        """Take a session out as an entry — what B does. `None` if it was not in."""
        entry = self.get(session)
        if entry is not None:
            del self._waiting[session]
        return entry

    def drop_session(self, session: str) -> Waiting | None:
        """Take a session out — what a prompt or its end does.

        `None` if it was not in — dismissing the same thing twice, or a session
        that ended while its signal was in flight, are both ordinary. The
        caller decides whether that is worth saying out loud.
        """
        return self._waiting.pop(session, None)

    def get(self, session: str) -> Entry | None:
        """That session's entry, or `None` when it is not waiting."""
        waiting = self._waiting.get(session)
        if waiting is None:
            return None
        return Entry(project=waiting.project, window_hint=waiting.window_hint,
                     waiting=(waiting,), host=waiting.host)

    def hush(self) -> int:
        """Make every session waiting now quiet, and say how many (task 47).

        What a restart does to what it read back: the entries are kept, and none
        of them speaks until its session does something new.
        """
        self._waiting = {session: replace(waiting, quiet=True)
                         for session, waiting in self._waiting.items()}
        return len(self._waiting)

    def pending(self) -> list[Entry]:
        """Every session, `needs` first and oldest first within a kind.

        The quiet ones come after every live one (task 47): what was pending
        before a restart is reached once what arrived since has been.
        """
        entries = [entry for entry in (self.get(s) for s in self._waiting)
                   if entry is not None]
        return sorted(entries, key=lambda e: (e.quiet, e.rank, e.since))

    def top(self, *, quiet: bool = False) -> Entry | None:
        """The one to deal with now, or `None` when nothing is waiting.

        A quiet entry is never the one to signal, so it is the top only when
        asked for with `quiet=True` — which is B's question, not the signal's
        (task 47).
        """
        ordered = self.pending()
        if ordered and (quiet or not ordered[0].quiet):
            return ordered[0]
        return None

    def live(self) -> int:
        """How many sessions are waiting and not quiet. This is the count that
        is rendered: a restart must not leave a number up all day (task 47)."""
        return sum(not waiting.quiet for waiting in self._waiting.values())

    def __len__(self) -> int:
        """How many sessions are waiting, quiet ones included."""
        return len(self._waiting)

    def __contains__(self, session: object) -> bool:
        return session in self._waiting

    def __iter__(self):
        return iter(self.pending())
