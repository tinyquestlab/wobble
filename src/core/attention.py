"""One attention at a time, and nothing lost while it lasts.

Dismissing is not "show me the next one" (constitution principle 8). It means
*I am handling this now*: that session becomes the one you are dealing with, and
the queue goes quiet behind it. Events keep arriving and keep being filed — the
freeze is about what surfaces, never about what is kept.

What ends a freeze:

  - **that session's next prompt** (`prompted`). A signal that already exists, so
    no timer has to guess whether you are finished with it (plan.md). That is the
    only ending where the thing is actually resolved.
  - **the snooze** (`tick`), ~5 min later. Dismissing is a promise — you said you
    would look — and a promise not kept brings the signal **back**, to the back
    of the queue (task 54). It is not dropped: that would be the silence
    principle 7 forbids. It is not put back where it was either, because the
    ones that waited behind it while it was held have waited longer.
  - **pressing B again** (`dismiss`), which moves you to the next pending one,
    or choosing a line from the menu bar's list (`attend`, task 21), which
    moves you to that one (criterion 7). The one you were on goes **back into
    the queue**, at the back, exactly as the snooze returns a dismissed
    signal. Settled
    2026-09-22: finishing something is closing its session, so no press of B
    ever ends a signal — B chooses what you are dealing with, and a prompt is
    what says you dealt with it.
  - **that session closing** (`ended`, task 22), or its claude dying (task 40).
    This one is not an answer and does not pretend to be: closing a tab says
    only that the session has stopped waiting — and a freeze over nothing would
    keep the whole queue quiet until the snooze fired five minutes later.
  - **silencing it** (`silence`, task 68): B held, or the menu's ⌥ row. It goes
    back quiet, and so does everything its session says until you type in it
    or answer a question of its own — asked for at the desk, 2026-10-01.

**A `done` you took with B comes back quiet** (task 68, `Queue.restore`): from
the snooze, a skip or another menu line. It has been seen; it stays listed and
B still reaches it. A `needs` comes back live, as before.

**A held `done` is quiet only while you are at it** (tasks 52, 54). Over it the
top `needs` speaks at once. Everything else waits while you are in its window,
and speaks once you have been out of it for a glance's grace (the daemon says
which, `set_away`), so what you walked away from holds nothing up: from
16:47:53 on 2026-09-29 a `done` held for a background run with nothing to do in
it kept another session's `done` quiet, and leaving it should have freed it.

**A held `needs` holds everything** (task 55), wherever you are, until you
answer it, skip it or its snooze fires: the only thing a needs waits for is
another needs. Asked for at the desk after a second session's `needs` spoke 3 s
after B took the first one's, at 18:09:13 on 2026-09-29. Either way the held one keeps its snooze — B
means *seen, leave it with me*, not *chase me if I leave*. Seen at the desk 2026-09-29: from 15:20:05
a held `done` in the Claude app kept another session's `needs`, queued at 15:20:47, silent
until B at 15:22:52. Task 51 ended the hold instead, once its window was left
for 3 s, and the one you had already seen cried again — being chased by it was
not wanted, the same afternoon.

**Walking away from a held `needs` breaks it out** (task 56). Taken with B, its
window in front, then left for the grace without an answer: the one break in
task 55's rule, and only for the held one itself. Its own pulse comes back
until you are in its window again — asked for at the desk, 2026-09-30: going to
the needs and not answering shows the broke-out red and brings the pulse back.
Everything else
stays held. Answering one is the catch (`Answered.caught`).

**A prompt anywhere resolves that session's own pending entry**, held or not. If
you typed in it, you were there, and a notification you have already answered is
not worth showing.

**A prompt in another session of the same project answers nothing here.** Since
task 41 (2026-09-28) an entry is one session. From task 20 it was the project,
and typing in one of its sessions ended the hold on all of them and let the rest
fall back into the queue; with Warp and the desktop app open on one folder, that
answered a session you never went to.

**Looking at it is not the same as having answered it**, and only one of the two
lives in this file. A prompt RESOLVES — the entry goes, for good. Having that
session's window in front of you only makes it *quiet*: the entry stays, the
count stays, and the moment you look away it speaks. Settled 2026-09-22, on the
ask "if I am still focused on the terminal, no need to notify". It is not here
because it is not a state of the attention — nothing is dismissed, nothing is
held, nothing is waiting on a snooze. It is a question the daemon asks the seam
each poll and hands to `Entry.in_window`, and what it changes is the signaller's
clock. The one thing worth knowing from here: a signal you looked at and walked
away from is still pending, because you never answered it.

`current()` is a pure question and `tick()` is the only thing that moves time.
A query that quietly advanced a state machine would hide exactly the bug this
one can have — a freeze that ends by being looked at rather than by the rules.

No clock here either: every entry point takes `now`. See `signals.py`.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .signals import Entry, Kind, Queue, Waiting

# ~5 minutes (spec.md criterion 6, settled 2026-09-22). A guess in the same way
# the ladder's numbers were guesses before the desk: the time-to-press has never
# been measured, and it is what this should come from. It is a default only —
# `config/signals.json` carries the number the daemon actually passes in, so
# changing your mind costs no code.
SNOOZE_S = 300.0


class Why(str, Enum):
    """Why an attention ended. The core says which; a mirror says it in words."""

    PROMPT = "prompt"          # you went back to that session — it is resolved
    SNOOZE = "snooze"          # you did not, so it came back
    SKIP = "skip"              # B again: not this one — so it came back too
    END = "end"                # its last session closed — nothing left to hold
    SILENCE = "silence"        # you silenced it, so it went back quiet (task 68)


class Status(str, Enum):
    """Where one waiting session stands (task 36). The core says which; a mirror words it."""

    SIGNALLING = "signalling"  # the top of the queue, speaking
    WATCHED = "watched"        # the top of the queue, quiet because its window is in front
    ATTENDING = "attending"    # B took it, and the snooze will bring it back
    WAITING = "waiting"        # ready, and behind another one
    QUIET = "quiet"            # back from before a restart, and not signalled (task 47)
    SEEN = "seen"              # a done you took with B, back and not signalled (task 68)
    SILENCED = "silenced"      # its session is silenced by hand (task 68)


@dataclass(frozen=True, slots=True)
class Standing:
    """A session's status, and for an attended one how long until the snooze returns it."""

    status: Status
    back_in: float | None = None      # seconds, ATTENDING only


@dataclass(frozen=True, slots=True)
class Release:
    """An attention that ended, as something a mirror can render.

    A sentence is not built here on purpose: principle 1 gives the core *what is
    being said* and leaves *how to say it* to each surface. What matters is that
    every release is reportable — a safety net that fires silently is the same
    defect as the silence it exists to prevent.
    """

    session: str
    project: str
    why: Why
    waited: float              # seconds the attention lasted
    returned: bool = False     # whether it went back into the queue


@dataclass(frozen=True, slots=True)
class Taken:
    """What a press of B changed. Two facts, and a press can carry both.

    `released` is filled only when you were already attending something, which
    is criterion 7's skip. It is a `Release` like the snooze's and for the same
    reason: the one you stepped away from went back into the queue, and
    `returned` says whether it found its place or was beaten to it by a newer
    signal from the same session.

    `again` is the press that had nowhere to skip to (task 46): nothing else
    was waiting, so the attention stands and its window is asked for once more.
    """

    attending: Entry | None = None    # the one you are dealing with now
    released: Release | None = None   # the one this press stepped away from
    again: bool = False               # the same one, its window tried again


@dataclass(frozen=True, slots=True)
class Answered:
    """What a prompt in some session changed. Falsy when it changed nothing.

    Until task 41 it also carried `left`, what the session's project still had
    waiting; an entry is one session now, so nothing is ever left.
    """

    released: Release | None = None   # the hold it ended, if it was holding that one
    dropped: Waiting | None = None    # the session it resolved, if there was one
    caught: bool = False              # a `needs` was answered: the catch (task 56)
    unsilenced: bool = False          # it ended that session's silence (task 68)

    def __bool__(self) -> bool:
        return (self.released is not None or self.dropped is not None
                or self.unsilenced)


@dataclass(frozen=True, slots=True)
class Ended:
    """What the end of a session changed. Falsy when it changed nothing.

    The same facts `Answered` carries, and a separate type because they mean
    something different: a prompt says you were there, an end only that the
    session stopped waiting. Folding the two together would have put that
    difference in a comment instead of in the name.

    Most session ends change nothing at all, which is why this is falsy: you
    answered the notification, then closed the tab an hour later. The caller
    decides whether a change is worth a line — `daemon.py` says the ones that
    took something out, and nothing for the rest.
    """

    released: Release | None = None   # the hold it ended, if it was that session's
    dropped: Waiting | None = None    # the session that stopped waiting

    def __bool__(self) -> bool:
        return self.released is not None or self.dropped is not None


@dataclass(frozen=True, slots=True)
class Silenced:
    """What silencing a session changed (task 68). Falsy when it found none.

    `released` is the hold it ended, when the silenced one was being attended:
    it goes back into the queue quiet, as `Why.SILENCE`.
    """

    session: str | None = None
    project: str | None = None
    released: Release | None = None

    def __bool__(self) -> bool:
        return self.session is not None


class Attention:
    """Which session you are dealing with, and what that hides while it lasts."""

    def __init__(self, queue: Queue, *, snooze: float = SNOOZE_S) -> None:
        if snooze <= 0:
            raise ValueError(
                f"a snooze of {snooze}s would bring the signal back the moment it "
                f"was dismissed, which is not a snooze — it is ignoring the press")
        self.queue = queue
        self.snooze = snooze
        self._entry: Entry | None = None
        self._since = 0.0
        # Out of the held one's window past the grace (task 52). The daemon's
        # to say, each poll: it asks the seam, this file does not.
        self._away = False
        # The held `needs` broke out (task 56): left, after being seen, with
        # no answer. Its own pulse speaks until you are back.
        self._broken = False

    # --- what is going on ---------------------------------------------------

    @property
    def entry(self) -> Entry | None:
        """The session being attended, as an entry, or `None`."""
        return self._entry

    @property
    def project(self) -> str | None:
        return self._entry.project if self._entry else None

    @property
    def session(self) -> str | None:
        """The session being attended, or `None`."""
        return self._entry.session if self._entry else None

    def frozen(self) -> bool:
        return self._entry is not None

    def current(self) -> Entry | None:
        """What should be signalled right now. `None` while the hold holds it.

        A held `needs` holds everything (task 55), and speaks itself once it
        has broken out (task 56). Over a held `done`, the top
        of the queue is signalled once you are away from it (task 54), or at
        once when it is a `needs` (task 52, the module docstring). `pending()`
        puts a `needs` first, so a `done` is never the top while one is waiting.

        Pure: ask it as often as you like. `tick` is what lets time act.
        """
        top = self.queue.top()
        if self._entry is None:
            return top
        if self._entry.kind is Kind.NEEDS:
            return self._entry if self._broken else None
        if self._away or (top is not None and top.kind is Kind.NEEDS):
            return top
        return None

    def set_away(self, away: bool, *, seen: bool = False) -> bool:
        """Whether you are out of the held one's window, past a glance's grace.

        Read by `current` only: for a held `done` it frees the queue (task
        55), and for a held `needs` whose window was in front this hold
        (`seen`) it is the break-out (task 56). True on that edge only, so the
        caller plays it once per time you leave. Back in its window, it is
        held again. A new hold starts from `False`, so what was true of the
        last one never leaks into it.
        """
        broke = (away and not self._away and seen and not self._broken
                 and self._entry is not None and self._entry.kind is Kind.NEEDS)
        self._away = away
        if not away:
            self._broken = False
        elif broke:
            self._broken = True
        return broke

    @property
    def broken(self) -> bool:
        """Whether the held `needs` has broken out and is speaking (task 56)."""
        return self._broken

    @property
    def away(self) -> bool:
        """What `set_away` last said, for the daemon's line about it."""
        return self._away

    def standing(self, entry: Entry, now: float, *,
                 watching: str | None = None) -> Standing:
        """Where `entry` stands, for the menu's list (task 36). Pure, like `current`.

        `watching` is the session whose window was in front at the top of the
        queue — the daemon's per-poll answer from the seam, which this file does
        not ask (see the module docstring). A session and not a flag, so a queue
        that changed after that answer cannot hand it to the wrong row. Matched
        by session, not by identity: the
        menu's rows are `queue.pending()` plus the held entry, and a held session
        that signalled again is back in `pending()` as a new `Entry` (task 33).
        """
        if self._entry is not None and entry.session == self._entry.session:
            return Standing(Status.ATTENDING,
                            back_in=max(0.0, self.snooze - (now - self._since)))
        if entry.quiet:
            return Standing(Status.SILENCED if self.queue.silenced(entry.session)
                            else Status.SEEN if entry.returned else Status.QUIET)
        top = self.current()
        if top is not None and entry.session == top.session:
            return Standing(Status.WATCHED if top.session == watching
                            else Status.SIGNALLING)
        return Standing(Status.WAITING)

    # --- what changes it ----------------------------------------------------

    def dismiss(self, now: float) -> Taken:
        """B was pressed. Take the top of the queue, whatever is at the top.

        Aimed at nothing: it is the press that means *the next one*, and it is
        the only gesture the ball has. `attend` is the aimed half, added at task
        21 for the menu bar's list — the two differ in which entry they read and
        in nothing else, which is why everything after that line is `_take`.

        The new entry leaves the queue, because criterion 4 says the count drops
        to what is left — a dismissed thing is not still waiting.

        Pressed while already attending, this is criterion 7's skip, and the one
        you were on **goes back into the queue**, at the back (task 54). Settled
        2026-09-22: B does not finish anything, it
        only chooses what you are dealing with; finishing is closing the session,
        which arrives here as a prompt. Before that, a skipped signal was dropped
        for good, by nothing more deliberate than being overwritten.

        **With nothing else pending there is nothing to skip to** (task 46), so
        the attention stands, `again` says so, and the caller raises its window
        once more. Until 2026-09-29 the skip ran anyway: the lone signal was let
        go, cried at once, and the next press took it back, so a B pressed again
        because the window did not come made a beat every time (tasks.md 38,
        18:41:26–18:41:37). The hold keeps the `since` of the first press: a
        retry is not a new promise, so it does not push the snooze back.

        A held session that signalled again has a newer row in the queue, so it
        is not alone and takes the skip as before — task 33's case, unchanged.

        **B reaches the quiet ones too** (task 47), once nothing live is left:
        they are never signalled, but principle 2 does not let the menu reach
        something the ball cannot.
        """
        # Read before anything is put back — see `_take`, which is where the
        # order matters and where the reason is written down.
        nxt = self.queue.top(quiet=True)
        if self._entry is not None and nxt is None:
            return Taken(attending=self._entry, again=True)
        return self._take(nxt, now)

    def attend(self, session: str, now: float) -> Taken:
        """A named session was chosen: the same press, aimed (task 21).

        The menu bar lists what is pending and choosing a line arrives here.
        Everything `dismiss` does happens here too — the entry leaves the queue,
        the one you were on goes back into it at the back — and the only
        difference is that the entry is named rather than taken off the top.

        **A session that is not waiting changes nothing at all.** The list is
        rebuilt from the core on every refresh, but a click still races a poll:
        the row you aimed at can have been answered, ended or snoozed in the
        quarter of a second between the menu being drawn and your finger
        landing. Falling back to the top would then attend something you did not
        choose and raise a window you did not ask for — a mirror answering a
        question nobody asked it. So nothing happens, and the caller says so:
        an empty `Taken` is a fact to report, not an error to swallow.
        """
        wanted = self.queue.get(session)
        if wanted is None:
            return Taken()
        return self._take(wanted, now)

    def _take(self, nxt: Entry | None, now: float) -> Taken:
        """Hold `nxt`, and put back what was being held. What both doors share.

        `dismiss` and `attend` differ in one line — which entry they read — and
        this is every consequence of it, in one copy. Two copies of the skip
        rule is how the ball's button and the menu's list would slowly stop
        behaving alike, which is the same reason the daemon gives its B doors
        one path rather than three.

        **The order is load-bearing.** The entry being taken leaves the queue
        BEFORE the one being let go is put back. The other way round, a skip
        with nothing else pending would make the one just released the top
        again, and B would hand you the same signal forever. That is also why
        the caller reads its entry before calling: by the time `restore` runs,
        `top()` is no longer the question that was asked.

        **And the same order is what task 33 had to pay for.** `restore` refuses
        a session the queue already holds, because a session that signalled
        again while it was being attended has a newer row and that one wins. It
        reads that from the queue — so when `nxt` is the held entry's own
        session, the drop below deletes the very row the guard would have read,
        and the stale kind is refiled over the fresh one. Taking the answer
        first is cheaper than reordering: the drop has to stay where it is.
        """
        held, since = self._entry, self._since
        superseded = frozenset(
            waiting.session for waiting in held.waiting
            if self.queue.holds(waiting.session)) if held is not None else frozenset()
        if nxt is not None:
            self.queue.drop(nxt.session)
        self._entry, self._since = nxt, (now if nxt is not None else 0.0)
        self._away = self._broken = False

        if held is None:
            return Taken(attending=nxt)
        return Taken(attending=nxt,
                     released=Release(session=held.session, project=held.project,
                                      why=Why.SKIP, waited=now - since,
                                      returned=self.queue.restore(held, superseded,
                                                                  at=now)))

    def silence(self, now: float, session: str | None = None) -> Silenced:
        """Silence a session until you type in it or answer it (task 68).

        Named, it is the menu's ⌥ row; a session neither waiting nor held is
        the same stale click `attend` refuses, and changes nothing. Unnamed, it
        is B held on the ball: the one being attended, else the top of the
        queue, quiet ones included — B's own question (`dismiss`), and the
        drawing of the ball's queue approved at the desk on 2026-10-01.

        A held one is let go into the queue, quiet, at the back. One that
        signalled again while held already has its newer row there, and that
        row goes quiet instead — `restore`'s refusal, as for a skip.
        """
        held = self._entry
        if session is None:
            top = self.queue.top(quiet=True)
            session = (held.session if held is not None else
                       top.session if top is not None else None)
        waiting = self.queue.get(session) if session is not None else None
        is_held = held is not None and held.session == session
        if session is None or (waiting is None and not is_held):
            return Silenced()
        project = held.project if is_held else waiting.project
        self.queue.silence(session)
        if not is_held:
            return Silenced(session=session, project=project)
        release = self._release(Why.SILENCE, now)
        return Silenced(session=session, project=project,
                        released=Release(session=release.session,
                                         project=release.project, why=release.why,
                                         waited=release.waited,
                                         returned=self.queue.restore(held, at=now)))

    def prompted(self, session: str, project: str, now: float) -> Answered:
        """A session was given a new prompt: you were there.

        **That session stops waiting**, wherever it was — a notification you
        have already answered is not worth showing. It may have been in the
        queue, or the entry being held; both are the same fact. It can be in
        both: a held session that signalled again has a newer row in the queue.

        **The hold ends** only if it is this session. Typing in another one —
        even in the same folder, since task 41 — is not an answer to the one
        being attended.

        **Its silence ends** (task 68), whether anything was waiting or not.

        `project` is not read. It is kept so both sides of the hook read alike.
        """
        unsilenced = self.queue.unsilence(session)
        dropped = self.queue.drop_session(session)
        caught = dropped is not None and dropped.kind is Kind.NEEDS
        held = self._entry
        released = None

        if held is not None and held.session == session:
            caught = caught or held.kind is Kind.NEEDS
            dropped = dropped or held.lead
            released = self._release(Why.PROMPT, now)

        return Answered(released=released, dropped=dropped, caught=caught,
                        unsilenced=unsilenced)

    def replied(self, session: str, now: float) -> Answered:
        """A question that session asked was answered where it was asked (task 49).

        `prompted` with one difference: only a `needs` goes. The answer is to
        the question, so a `done` from that session — one it said after, or
        one the hold is carrying — is left exactly where it is. It is still
        `Why.PROMPT` when it ends the hold: you went back to it, and that is
        what the word means.

        Which question is the caller's to match. The core knows `needs`, not
        tools (`hooks.asked`).

        **Its silence ends only when a `needs` was answered** (task 68): every
        tool the session runs is a line of this kind, and one that answers
        nothing is not you coming back to it.
        """
        entry = self.queue.get(session)
        dropped = (self.queue.drop_session(session)
                   if entry is not None and entry.kind is Kind.NEEDS else None)
        held = self._entry
        released = None

        if held is not None and held.session == session and held.kind is Kind.NEEDS:
            dropped = dropped or held.lead
            released = self._release(Why.PROMPT, now)

        unsilenced = dropped is not None and self.queue.unsilence(session)
        return Answered(released=released, dropped=dropped, caught=dropped is not None,
                        unsilenced=unsilenced)

    def ended(self, session: str, project: str, now: float) -> Ended:
        """A session closed: it stops waiting, and nothing more is claimed.

        The defect this closes is a slow one. Until task 22 the only thing that
        took an entry out was that same session's next prompt — so a session
        whose output you read and whose tab you then closed left something in
        the queue that nothing could ever resolve, speaking every few seconds
        until the snooze or a restart. `Queue.drop_session` has named this task
        in its own docstring since task 20, and `signals.py` names the case in
        its module docstring: it is the half of the task 20 rewrite that needed
        a hook to finish.

        **It is deliberately not `prompted`.** A prompt says *you were there and
        you dealt with it*. An end says only that this session is no longer
        waiting, and it says nothing about why: you may have finished with it,
        or typed `/clear`, or closed the window on your way out of the building.

        **If it was the one being held, the hold ends**, with `Why.END` to say
        which of the four endings it was. A hold with nothing in it is a freeze
        with nothing behind it: `current()` would keep the whole queue quiet
        until the snooze fired, for a session that is not waiting for anything —
        the silence principle 7 is written against. Until task 41 the hold could
        survive an end one session lighter; an entry is one session now, so an
        end in it always empties it.

        The reason the hook carries (`clear`, `logout`, `other`) is not read.
        Every one of them means the same thing here — that session is not
        waiting on you right now — and if it comes back it signals again, which
        is the direction that fails loudly rather than quietly.

        Its silence is forgotten (task 68): a session id is not reused, and a
        set that only grows is a leak with nothing to show for it.
        """
        self.queue.unsilence(session)
        dropped = self.queue.drop_session(session)
        held = self._entry
        released = None

        if held is not None and held.session == session:
            # It can have been in both — a session that signalled again while
            # it was being attended has a row in the queue too — and
            # `drop_session` above already took that one.
            dropped = dropped or held.lead
            released = self._release(Why.END, now)

        return Ended(released=released, dropped=dropped)

    def tick(self, now: float) -> Release | None:
        """Let time act. Returns the release when the snooze fires, else `None`.

        The dismissed entry goes back to the back of the queue (task 54) — a
        thing you ignored coming back is the whole point, and what waited
        behind it goes first. It does not go back if that session has signalled
        again in the meantime; the newer entry is already there and wins
        (`Queue.restore`).
        """
        if self._entry is None or now - self._since < self.snooze:
            return None
        held = self._entry
        release = self._release(Why.SNOOZE, now)
        return Release(session=release.session, project=release.project,
                       why=release.why, waited=release.waited,
                       returned=self.queue.restore(held, at=now))

    def _release(self, why: Why, now: float) -> Release:
        held = self._entry
        assert held is not None
        release = Release(session=held.session, project=held.project, why=why,
                          waited=now - self._since)
        self._entry, self._since, self._away, self._broken = None, 0.0, False, False
        return release
