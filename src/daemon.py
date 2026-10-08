"""The one process that is always running: tail the events, work the queue.

    venv/bin/python3 -m src.daemon
    venv/bin/python3 -m src.daemon --replay      # play var/events from the top
    venv/bin/python3 -m src.daemon --poll 0.1

It wires the pieces that already exist and adds nothing of its own: the hook
file (`hooks.Tail`), the queue (`core.signals`), the attention (`core.
attention`), the vocabulary (`core.ladder`) and the two mirrors (`mirrors.
menubar`, `mirrors.ball`). It still prints every beat as well — an effect id is
a thing you feel and not a thing you see, and the terminal is where it can be
checked against what the ball actually did.

**It owns the run loop the menu bar item needs.** Once per poll it asks the seam
to deliver whatever AppKit has for it (`status.pump`), which is what turns a
click into a B press without a second thread anywhere in the process. The full
reasoning is in `platform_seam/macos.py`.

**Three doors open onto one B.** The ball's own button, the menu bar item, and
Enter. They set the same event, on purpose: giving them separate paths is how
they slowly stop behaving alike, and Enter in particular is how dismissal, the
freeze and the snooze get walked through with no hardware in the room — which is
the mode this whole project is developed in (`--no-ball` makes it explicit).

**Everything it says is also written down, one file per day** (`src/log.py`),
because the terminal answers "what is it doing" and cannot answer "what did it
do while I was out". The log follows the events file rather than being pinned at
`var/logs`, so a desk check running against a throwaway tree logs into that tree
and the real record stays a record of real runs.

**It says, out loud, when the hooks are not wired.** With no hooks this is a
process watching a file nobody writes, and the only symptom is a quiet
afternoon (principle 7). It re-checks while it runs, so wiring them without
restarting is noticed.
"""
from __future__ import annotations

import argparse
import asyncio
import fcntl
import logging
import math
import os
import random
import signal
import sys
import threading
import time
from dataclasses import dataclass, replace
from pathlib import Path

from . import log, platform_seam
from .core.attention import Attention, Silenced, Standing, Taken
# `CRY` moved into `core.ladder` in task 24: the config names the same file
# (`"mac_sound": "@cry"`), and two definitions of one path are two things to
# keep in step. It is imported rather than redefined for that reason alone.
from .core.ladder import CRY, DEFAULT_PARTNER, ROOT, Ladder, cry_of, load as load_ladder
from .core.signals import TERMINAL, VSCODE, WARP, Entry, Kind, Queue, Waiting
from .hooks import (BASH, EVENTS, HookLine, Running, Tail, Titles, answers, parse,
                    registry, restates, running, runs_bash, short, wiring)
from .ball.button import HOLD_S
from .mirrors.ball import Ball
from .mirrors.menubar import Menubar
from .mirrors.menubar import items as menubar_items, status_words

WIRING_EVERY_S = 30.0

# One daemon per events file (task 50). Two would play every signal twice and
# fight each other for the ball, and once wobble is an app that also starts at
# login, a second one started from a terminal is an ordinary afternoon.
LOCK_NAME = "daemon.lock"

# The partner a done speaks with, kept beside the events file like the lock and
# the log, so a sandbox daemon never reads or writes the real one (spec 04, task 03).
PARTNER_NAME = "partner"

# How long Quit waits for the ball to let go before going anyway. Not a guess
# about Bluetooth: `open_ball`'s context manager is what disconnects, and it
# only runs if the worker gets a turn, so this is the worker being given one.
# Bounded because a daemon that would not quit is worse than a link the ball
# times out of by itself a few seconds later. 3 s and not 2 since task 35: the
# worker sends a 180 before it lets go (one try, 1.5 s at most), so a quit does
# not leave 9 lit for tens of minutes.
QUIT_GRACE_S = 3.0

# How often each waiting session's claude is asked whether it still runs (task
# 40). One `sysctl` per session, so cheap; not every poll, because a claude
# killed without its `SessionEnd` is a queue that has been wrong for minutes,
# and five more seconds of it changes nothing anyone can hear.
ALIVE_EVERY_S = 5.0

# How often the registry is re-read for VS Code's tab names while something is
# pending (task 43). A tab renamed by its first prompt is watched by its new
# name within this, and a stale name errs loud: the session reads as not watched.
TABS_EVERY_S = 1.0

# How often a session waiting on a Bash permission question has its claude's
# children read for the approved command (task 65). Two calls per child, and
# only while such a question waits; a second late is a beat at most.
APPROVED_EVERY_S = 1.0

# How often the permissions are read again (spec 03, task 05). Bluetooth's read
# measured ~12 ms here, against nothing for the other two, and the menu refreshes
# four times a second; a grant switched in System Settings is in the menu within
# this, which is quicker than anybody gets back from the Settings window.
PERMISSIONS_EVERY_S = 2.0

# How often `var/partner` is read again (spec 04, task 03): a hand edit, or the
# menu's write in task 04, is heard within this. One small file, so the cost is
# a stat and a read.
PARTNER_EVERY_S = 2.0


def stamp() -> str:
    return time.strftime("%H:%M:%S")


# The project column. 22 because the longest name that actually shows up here
# is a desk check's own (`wobble-desk-criteria`, 20) and a column that collides
# with its own contents is not a column. Nothing is truncated to fit: the name
# is the thing being scanned for, and two projects cut to the same 15
# characters would read as one. A longer name pushes the line right instead,
# which is visible and says what happened.
COLUMN = 22

# What stands in the column on a line that is about the daemon rather than
# about any project — the banner, the hook wiring, a line nobody could parse.
# A word like "daemon" would read as a folder called daemon and grep like one.
NO_PROJECT = "·"


def say(what: str, detail: str = "", project: str = "") -> None:
    # One string, two destinations, and they stay identical: seven desk checks
    # parse this stdout, so the day the file and the screen disagree is the day
    # one of them stops being evidence. `log.write` does nothing until `run`
    # starts it (`src/log.py`).
    line = f"{stamp()}  {project or NO_PROJECT:<{COLUMN}}{what:<22}{detail}"
    print(line, flush=True)
    log.write(line)


def shaped(record: logging.LogRecord) -> str:
    """A line from elsewhere in the package, in the columns `say` just used.

    Handed to `log.start`, which puts it on the root logger so that
    `src.ball.link`'s retries and losses land in the day's file and on the
    terminal together instead of only on whichever terminal happened to be
    running the daemon (`src/log.py`). The project column is empty because a
    link knows about a wire, not about whose build is waiting on it.
    """
    tag = record.name.rsplit(".", 1)[-1]
    if record.levelno >= logging.WARNING:
        # `went unacked` and `never acked` are one word apart and mean very
        # different things; the level is the part that survives skimming.
        tag += f" {record.levelname.lower()}"
    return (f"{time.strftime('%H:%M:%S', time.localtime(record.created))}  "
            f"{NO_PROJECT:<{COLUMN}}{tag:<22}{record.getMessage()}")


def describe(entry: Entry | Waiting | None) -> str:
    """What is waiting, in one phrase. Takes either — both carry the two facts.

    The project is NOT in it: since task 23 it is a column of its own, and
    repeating it here would put the same word twice on every line that has one.
    """
    if entry is None:
        return "nothing"
    # Which session, so two in one folder read as two (task 40).
    return f"{entry.kind.value} · {short(entry.session)}"


def span(seconds: float) -> str:
    """A wait as a person reads it — 25s, 4m12s, 1h46m (task 86)."""
    s = max(0, round(seconds))
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m{s % 60:02d}s"
    return f"{s // 3600}h{s % 3600 // 60:02d}m"


@dataclass(slots=True)
class Life:
    """One wait, as the line that ends it tells it (task 86): when it began, and its beats.

    The daemon's own, not `Waiting.since`: a row back from a snooze or a let-go
    is refiled with a fresh `since` (`Queue.restore`), and the wait it ends still
    began at its first signal. Counted per session, because the Signaller's count
    starts over whenever another signal takes the floor. `heard` is a beat that
    was not silent and went to the ball, or that the Mac played.
    """

    kind: Kind
    start: float
    beats: int = 0
    heard: int = 0


def recall(lines: list[str], queue: Queue, at: float,
           asked: dict[str, str] | None = None,
           asker: dict[str, str] | None = None) -> dict[str, str]:
    """File what `lines` leave pending, saying nothing, and hand back Warp's tabs (task 47).

    The loop's own rules — a prompt a person typed or an end takes a session
    out, so does the answer to the question it asked (task 49), a signal files
    it — minus every word and every beat: this is the file
    from before the restart, read back, not something happening now. Until
    2026-09-29 the daemon started at the end of the file, and every quit threw
    away what was still pending while its line said it would come back.

    `asked` is filled with the tool each session last asked about, so a needs
    that comes back can still be answered where it was asked (task 49), and
    `asker` with which agent asked it (task 71). A question's own notice is
    skipped here as it is live (task 72).
    """
    tabs: dict[str, str] = {}
    asked = {} if asked is None else asked
    asker = {} if asker is None else asker
    asking: dict[str, HookLine] = {}
    for line in lines:
        hook = parse(line)
        if hook is None or hook.reminder or (hook.what == "prompt" and not hook.by_person):
            continue
        if hook.focus_url:
            tabs[hook.session] = hook.focus_url
        if hook.what == "answered":
            entry = queue.get(hook.session)
            if (answers(hook, asked.get(hook.session, ""), asker.get(hook.session, ""))
                    and entry is not None and entry.kind is Kind.NEEDS):
                queue.drop_session(hook.session)
                asking.pop(hook.session, None)
            continue
        if restates(hook, asking.pop(hook.session, None)):
            continue
        if hook.what == "asking":
            asking[hook.session] = hook
        needs = hook.what in ("needs", "asking")
        asked[hook.session] = hook.tool if needs else ""
        asker[hook.session] = hook.agent if needs else ""
        if hook.what in ("prompt", "end"):
            queue.drop_session(hook.session)
            continue
        event = hook.as_event(at)
        if event is not None:
            queue.add(event)
    return tabs


class Signaller:
    """Whose turn it is to be played, when its next beat falls, and whether
    its light should be up.

    There is nothing between beats any more (task 35). A `done` puts up 9, the
    stroll light, and 9 stays on by itself until 180, so the held light is what
    says "still waiting" — the 3 s silent pulse, and the cry gap that kept it
    off a sounding cry, went with the one audio slot they were working around.
    What is left here is the beat, and `showing`: the voice whose light the
    ball should be holding right now, or `None` for dark.

    **Watched, its clock stops.** While the session's own window is the one in
    front of you there is nothing to tell you, so nothing is played — and the
    time that passes is not counted either. That is the difference between
    staying quiet and being used up: a `done` you watched arrive has not cried
    yet, so it cries the moment you look away, rather than having spent both its
    beats in silence while you read the output. The same freeze stops a glance
    away and back from being a second cry, because the beats it has already had
    are remembered. Added 2026-09-22, for "if I am still focused on the
    terminal, no need to notify". Its light goes off while you look, and comes
    back when you look away.

    **And a hand that has just typed gets five seconds.** `hold_until` is a
    moment no beat may land before, and the daemon sets it from the last prompt
    a person actually sent. It is the other half of the rule above: that one
    silences the project whose window you are reading, this one silences the
    ball while you are still at the keyboard — measured 2026-09-23 as a prompt
    at 13:14:23 and another project's cry at 13:14:24. The beat is delayed and
    not spent, exactly as a watched one is. A signal that has already beaten
    keeps its light through the hold, because the light was already saying
    what it says; one that has never beaten stays dark, so its light never
    arrives ahead of its own cry (DESK-CHECKS Part D.2).

    **And each beat of a `done` cries in a mood (tasks 57, 64).** The pool is
    picked from what happened, and one cry from the pool, never the one played
    last when the pool has another. The first beat is `sad` for a turn an API
    error ended, `call` for one back from a snooze or a let-go, `soft` when its
    window is in front and nobody has touched anything (`idle_front`), `proud`
    for a long turn, and `happy` otherwise; the beats after it are `call`; and
    `lonely_after_s` after the first, a signal nobody came to cries `lonely`
    once more — never one that came back, which has been ignored once already.
    A pool the config leaves out falls back to `happy`. `rng` is handed in so a
    check can seed it. Muted, every beat is the mute's own id, and with `one_cry`
    every signal plays the kind's own `effect` — 129, the uploaded cry, which is
    the one that works on both balls — with no lonely beat and no greet.

    **And a `done` that has called greets you once (task 64).** `greet` is asked
    when you come back — B, or the first input after a long idle — and answers
    the `greet` pool once per signal, only for one whose second beat played or
    that came back and cried. It is a one-shot for the daemon to play, not a
    beat: it is not counted and moves no clock. Asked within `greet_quiet_s` of
    the last beat, it is spent in silence instead (task 67): one effect at a
    time, not a cry and a greet on top of each other.
    """

    def __init__(self, ladder, rng: random.Random | None = None):
        self.ladder = ladder
        self.rng = rng if rng is not None else random.Random()
        # A runtime switch like `muted`: the ladder says what a done may cry
        # with, this says whether the ball in the room can play them (task 57).
        self.one_cry = False
        # The cry and the mood the last beat was given, and the last cry given
        # to anything, so the next one can differ from it.
        self.cry: int | None = None
        self.mood: str | None = None
        self.last_cry: int | None = None
        # Mute mode (task 34), and it is a runtime switch rather than part of
        # the vocabulary: the ladder is what the signals ARE, this is whether
        # the room is allowed to hear them. Kept here because these lines are
        # every place a `Voice` leaves the core for a mirror, so one flag read
        # in one file is the whole of it — the ball and the menu bar cannot end
        # up with different ideas of what muted means.
        self.muted = False
        self.key: tuple[str, str] | None = None
        self.last_beat: float | None = None
        # The first beat's moment, which the lonely one is timed from (task 64).
        self.first_beat: float | None = None
        self.beats = 0
        # The done each session last greeted, as its kind and newest event: once
        # per signal (task 64), and one a snooze or a let-go brings back is the
        # same signal, not a new one to greet again (task 67).
        self.greeted: dict[str, tuple[str, float]] = {}
        # When the last beat played, and its effect, so a greet does not land on
        # top of it (task 67). Any signal's: the ball has one sound lane.
        self.sounded: tuple[float, int | None] | None = None
        # When the watching started, or `None` when nobody is. Everything else
        # here is a moment on the same monotonic clock, so holding the start is
        # all it takes to give the time back when it ends.
        self.watched_since: float | None = None

    def due(self, entry: Entry | None, now: float, *,
            watched: bool = False,
            hold_until: float | None = None,
            idle_front: bool = False):
        """The `Voice` to play now, or `None`.

        `watched` is "its own window is in front of you". Nothing plays, and
        the clock stops for as long as it lasts — see the class docstring for
        why stopping it is the point rather than a refinement.

        `hold_until` is "somebody just typed": no beat lands before it. Unlike
        `watched` the clock is NOT stopped — the hold is five seconds and the
        cadence it would distort is thirty, so freezing it would buy nothing
        and cost the second cry its place.

        `idle_front` is "its window is in front, and nobody has touched anything
        for `idle_s`": not watched any more, and a first beat then is `soft`.
        """
        if entry is None:
            self.key = self.last_beat = self.first_beat = None
            self.watched_since = None
            self.beats = 0
            return None
        # Keyed by session, because that is what an entry is again (task 41).
        key = (entry.session, entry.kind.value)
        if key != self.key:
            # A different thing has the floor. It speaks at once rather than
            # inheriting the last one's schedule.
            self.key, self.last_beat, self.first_beat = key, None, None
            self.watched_since = None
            self.beats = 0
            self.cry = self.mood = None

        if watched:
            if self.watched_since is None:
                self.watched_since = now
            return None
        if self.watched_since is not None:
            # Hand the time back by moving the deadline forward by what was
            # spent. `None` is exactly right to leave alone: a signal that has
            # not spoken yet is due now, whenever now turns out to be.
            spent = now - self.watched_since
            self.watched_since = None
            if self.last_beat is not None:
                self.last_beat += spent
            if self.first_beat is not None:
                self.first_beat += spent

        if hold_until is not None and now < hold_until:
            return None

        beat = self.ladder.next_beat(entry.kind, self.last_beat, now, self.beats)
        if beat is None:
            beat = self._lonely(entry)
        if beat is None or beat > now:
            return None
        # From `now`, not from `beat` (the due time). Anchoring on the due
        # time compounds: a beat can only leave on a poll tick, a few ms
        # after it was due, and that lateness carries into the next due
        # time until it crosses a whole tick and one gap collapses — the
        # sawtooth measured in task 30 (`var/desk/probe_beat_jitter.py`:
        # steady 1.53 s, gaps of ~1.28 s every 8-9 beats). `now` means a
        # gap can never be shorter than `every_s`, at the cost of running
        # a few ms slow forever instead of correcting itself.
        self.last_beat = now
        if self.first_beat is None:
            self.first_beat = now
        self.mood = self._mood(entry, idle_front)
        self.cry = self._pick(entry.kind, self.mood)
        self.beats += 1
        voice = self._voiced(entry.kind)
        self.sounded = (now, voice.effect)
        return voice

    def greet(self, entry: Entry | None, now: float):
        """The greet to play as you come back to `entry`, and why not (tasks 64, 67).

        `(voice, None)` to play it, `(None, why)` when it is spent in silence
        because a beat played `greet_quiet_s` ago, and `(None, None)` when
        there is no greet to give. Once per signal — per event, so the same
        done back from a snooze is not greeted twice — and only for one that has
        called: its second beat played, or it came back and cried. Muted, it is
        spent and plays nothing — a greet is a sound and nothing else.
        """
        if (entry is None or self.key != (entry.session, entry.kind.value)
                or self.greeted.get(entry.session) == (entry.kind.value, entry.at)
                or self.one_cry):
            return None, None
        moods = self.ladder.moods.get(entry.kind)
        if moods is None or "greet" not in moods.pools:
            return None, None
        if not (self.beats >= 2 or (entry.returned and self.beats >= 1)):
            return None, None
        self.greeted[entry.session] = (entry.kind.value, entry.at)
        if self.muted:
            return None, None
        if (moods.greet_quiet_s is not None and self.sounded is not None
                and now - self.sounded[0] < moods.greet_quiet_s):
            at, effect = self.sounded
            return None, (f"effect {effect} played {now - at:.0f}s ago, and a greet "
                          f"over it is one effect too many (greet_quiet_s "
                          f"{moods.greet_quiet_s:g})")
        cry = self._pick(entry.kind, "greet")
        return replace(self.ladder.voice(entry.kind), effect=cry, budget_s=None,
                       lasts_s=moods.greet_lasts_s), None

    def _lonely(self, entry: Entry) -> float | None:
        """When the lonely beat falls, once the kind's own beats are spent, or `None`."""
        moods = self.ladder.moods.get(entry.kind)
        times = self.ladder.times[entry.kind]
        if (moods is None or "lonely" not in moods.pools or self.one_cry
                or entry.returned or self.first_beat is None
                or times is None or self.beats != times):
            return None
        return self.first_beat + moods.lonely_after_s

    def _mood(self, entry: Entry, idle_front: bool) -> str | None:
        """The pool this beat cries from, or `None` for the kind's own effect."""
        moods = self.ladder.moods.get(entry.kind)
        if moods is None or self.one_cry:
            return None
        times = self.ladder.times[entry.kind]
        if self.beats == 0:
            proud = (moods.long_turn_s is not None and entry.turn_s is not None
                     and entry.turn_s >= moods.long_turn_s)
            name = ("sad" if entry.failed else "call" if entry.returned else
                    "soft" if idle_front else "proud" if proud else "happy")
        elif times is not None and self.beats >= times:
            name = "lonely"
        else:
            name = "call"
        return name if name in moods.pools else "happy"

    def showing(self, entry: Entry | None, *, watched: bool = False):
        """The voice whose light should be up now, or `None` for dark.

        Asked after `due` for the same entry, so `beats` belongs to it. Dark
        when nothing is pending, when you are looking at it, and before its
        first beat — a light with no cry yet in front of it would be a signal
        arriving out of order. The mirror turns `None` into 180, and a voice
        whose held light has gone out into that light again.
        """
        if entry is None or watched or self.beats == 0:
            return None
        return self._voiced(entry.kind)

    def _pick(self, kind: Kind, mood: str | None) -> int | None:
        """A cry from `mood`'s pool, or `None` for the kind's own effect."""
        if mood is None:
            return None
        pool = self.ladder.moods[kind].pools[mood]
        cry = self.rng.choice([cry for cry in pool if cry != self.last_cry] or list(pool))
        self.last_cry = cry
        return cry

    def _voiced(self, kind: Kind):
        """The kind's voice, crying the one picked for it. Muted, the mute's own id."""
        voice = self.ladder.voice(kind, self.muted)
        if self.cry is None or self.muted:
            return voice
        return replace(voice, effect=self.cry)


def _spans(ids: tuple[int, ...]) -> str:
    """`20-39, 181, 230, 300`: runs of consecutive ids written as one."""
    runs: list[list[int]] = []
    for n in sorted(ids):
        if runs and n == runs[-1][-1] + 1:
            runs[-1].append(n)
        else:
            runs.append([n])
    return ", ".join(f"{run[0]}-{run[-1]}" if len(run) > 1 else f"{run[0]}" for run in runs)


class LookAway:
    """Whether the signal at the top still counts as looked at (task 37).

    `watched` from the seam is instant, and a glance away and back was a light
    and a buzz each way — four of them in 25 s at the desk, 2026-09-28. So a
    window you leave keeps counting as looked at for `wait_s` more, and coming
    back inside that is as if you never left. It is kept per session (task 41): a
    different signal taking the top owes you nothing, and gets no grace that
    belonged to another window.

    The other way round, a window passed through is not looked at (task 67):
    one in front under `glance_s` was a 180 and then a 9 with its buzz, at the
    desk 2026-10-01 10:11:05. `front_since` is when the front window last
    changed, `None` for one already there when something became pending — a
    done arriving while you read its window stays quiet at once. A session
    already counted (watched, or inside its `wait_s`) does not wait again.
    """

    def __init__(self, wait_s: float, glance_s: float = 0.0):
        self.wait_s = wait_s
        self.glance_s = glance_s
        # The session last looked at, and when its window stopped being in
        # front — `None` while it still is.
        self.session: str | None = None
        self.left_at: float | None = None

    def watched(self, session: str | None, looking: bool, now: float,
                front_since: float | None = None) -> bool:
        if session is not None and looking and (
                session == self.session or front_since is None
                or now >= front_since + self.glance_s):
            self.session, self.left_at = session, None
            return True
        if session is not None and session == self.session:
            if self.left_at is None:
                self.left_at = now
            if now < self.left_at + self.wait_s:
                return True
        self.session = self.left_at = None
        return False


class Away:
    """Whether you just came back to the keys from a long time away (task 67).

    The greet for coming back waited for `idle.after_s`, the soft's minute, and
    it should only follow a long time away — the Mac asleep, or 15 minutes (the
    desk, 2026-10-01). Away is `away_s` with no key or mouse, or the Mac asleep
    that long: `time.monotonic` is mach_absolute_time here and stops in sleep,
    so a sleep is the wall clock running ahead of it between two polls. Whether
    the idle reading counts through a sleep was not measured, so either is
    enough. Back is the first poll the idle drops after that, said once.
    `idle_s` of `None` (nothing pending, or blind) forgets the time away.

    `went` is the why on the one poll you count as away, and `gone_s` how long
    you were, on wall time from the last touch, so a sleep is in it (task 87:
    until then away and ignoring read the same in the log).
    """

    def __init__(self, away_s: float):
        self.away_s = away_s
        self.idle_was: float | None = None
        # Why you count as away, latched until you come back or it is forgotten.
        self.why: str | None = None
        self.clocks: tuple[float, float] | None = None
        # Wall time of the last touch before going away, while away.
        self.left: float | None = None
        self.went: str | None = None
        self.gone_s = 0.0

    def back(self, idle_s: float | None, wall: float, mono: float) -> str | None:
        clocks, self.clocks = self.clocks, (wall, mono)
        was, self.idle_was = self.idle_was, idle_s
        self.went = None
        if not self.away_s or idle_s is None:
            self.why = self.left = None
            return None
        away = self.why is not None
        if clocks is not None:
            slept = (wall - clocks[0]) - (mono - clocks[1])
            if slept >= self.away_s:
                self.why = f"the Mac slept {slept:.0f}s"
                if not away:
                    self.left = clocks[0]
        if idle_s >= self.away_s and (self.why is None or not self.why.startswith("the Mac")):
            self.why = f"{idle_s:.0f}s with no key or mouse"
            if not away:
                self.left = wall - idle_s
        if self.why is not None and not away:
            self.went = self.why
        if self.why is not None and was is not None and idle_s < was:
            why, self.why = self.why, None
            self.gone_s = wall - (self.left if self.left is not None else wall)
            self.left = None
            return why
        return None


class HeldAway:
    """Whether you are out of the held one's window, past a glance (tasks 51, 52, 54, 55).

    The same grace `LookAway` gives, the other way round: that one keeps a
    signal quiet for `wait_s` after you leave its window, this one says you have
    been away that long. What it changes is only whether the queue may speak
    over a held `done` (`Attention.set_away`; a held `needs` holds everything,
    task 55), so a raise that never came forward counts as away too: nobody is at a window that is not in front. Task 51 waited for the window to have been in front first, when
    being away ended the hold itself.

    `seen` is that wait coming back for one thing only (task 56): a held
    `needs` breaks out when you leave a window you were at, and a raise that
    never came forward is not a catch you walked away from.
    """

    def __init__(self, wait_s: float):
        self.wait_s = wait_s
        self.session: str | None = None
        self.left_at: float | None = None
        self.seen = False

    def reset(self) -> None:
        """A new hold began: nothing it saw before counts."""
        self.session, self.left_at, self.seen = None, None, False

    def away(self, session: str, here: bool, now: float) -> bool:
        if session != self.session:
            self.session, self.left_at, self.seen = session, None, False
        if here:
            self.left_at, self.seen = None, True
            return False
        if self.left_at is None:
            self.left_at = now
        return now >= self.left_at + self.wait_s


def ways(entry: Entry, run: Running | None, focus_url: str) -> list[tuple[str, str | int]]:
    """How B can reach this session, best first (task 42).

    `("url", address)` opens the session itself: the desktop app's deep link,
    or Warp's tab. `("tab", pid)` picks the terminal tab on that claude's tty.
    `("window", hint)` is task 38's app-and-title raise, so every other way has
    somewhere to fall back to. `("pick", address)` comes after it and is tried
    only once that window came forward: VS Code's link to the session's tab
    (task 43), which in any other window would open a second copy. A url needs
    the host, because what it is checked against is that app coming forward.
    """
    found: list[tuple[str, str | int]] = []
    if entry.host and run is not None and run.deep_link:
        found.append(("url", run.deep_link))
    if entry.host and focus_url:
        found.append(("url", focus_url))
    elif entry.host and run is not None and run.entrypoint == "cli":
        found.append(("tab", run.pid))
    found.append(("window", entry.window_hint))
    if entry.host and run is not None and run.vscode_link:
        found.append(("pick", run.vscode_link))
    return found


def folder_of(entry: Entry, run: Running | None) -> str | None:
    """The folder B may open to reach this session's window, or `None` (task 69).

    Only for VS Code's own extension: it starts claude in the folder its window
    opened, so opening that folder is that window, on whichever desktop it is.
    A `cli` in VS Code's terminal may have started in a subfolder, and opening
    one no window holds makes a new window. Warp and Terminal answer a folder
    with a new tab.
    """
    if run is None or entry.host != VSCODE or run.entrypoint != "claude-vscode":
        return None
    return run.cwd or None


def reach(entry: Entry, run: Running | None, focus_url: str) -> tuple[bool, str]:
    """Try `ways` in order, on the worker thread; one sentence for all of it.

    A way that failed before one that worked is said in the same sentence, so
    the log shows both where B landed and why it did not land nearer.
    """
    missed: list[str] = []
    found = ways(entry, run, focus_url)
    for at, (way, what) in enumerate(found):
        if way == "pick":
            continue
        if way == "url":
            ok, why = platform_seam.focus.url(str(what), app=entry.host)
        elif way == "tab":
            tty, blind = platform_seam.process.tty(int(what))
            if tty is None:
                missed.append(blind or f"pid {what} is on no terminal")
                continue
            ok, why = platform_seam.focus.tab(tty, app=entry.host)
        else:
            folder = folder_of(entry, run)
            ok, why = platform_seam.focus.window(str(what), app=entry.host or None,
                                                 fits=entry.names, folder=folder)
        if ok:
            said = came = why or "its window came forward"
            for pick in (what for kind, what in found[at + 1:] if kind == "pick"):
                ok, said = picked(entry, str(pick), said)
            # A picked tab is what it says (task 66), but a desktop switch is
            # said beside it: the seam names the folder only when it opened it
            # (task 69), and "focused" alone hid that at the desk on 2026-10-01.
            if way == "window" and folder and folder in came and came not in said:
                said = f"{came}; then {said}"
            return ok, said + (f" (first: {'; '.join(missed)})" if missed else "")
        missed.append(why or f"the {way} way failed, and nothing said why")
    return False, "; then ".join(missed)


# How long a raised window may take to read as the one in front (task 66).
SETTLE_S = 0.5


def settled(entry: Entry) -> tuple[str | None, str | None, str | None]:
    """The window in front, given up to `SETTLE_S` to become the session's own.

    Two VS Code windows are one app, so bringing the app forward waits for
    nothing (`_arrived` is true at once) and the raised window may still read
    as not focused for a moment. Nobody has measured how long, so a short poll
    on the worker thread rather than one read that could call it someone else's.
    """
    deadline = time.monotonic() + SETTLE_S
    while True:
        title, app, blind = platform_seam.frontmost.window()
        if entry.in_window(title, app) or time.monotonic() >= deadline:
            return title, app, blind
        time.sleep(0.05)


def picked(entry: Entry, pick: str, said: str) -> tuple[bool, str]:
    """Open VS Code's link to the session's tab, only into its own window (task 66).

    VS Code hands the link to whichever window is in front, and one that does
    not hold the session opens a second copy of it (`Running.vscode_link`).
    The window step just brought the right one forward, but a click or another
    raise can land in between: three copies in 20 s at the desk on 2026-10-01
    (spec 01, task 66). So the window in
    front is read again just before, by the watched check's own rule, and the
    link is opened only into the session's window. Nothing readable in front is
    not its window either: a copy left behind is worse than a tab not picked.

    And `focused` is earned by what is in front afterwards, not by the link
    having opened: that day's log said `focused` beside another project's title.
    """
    title, app, blind = settled(entry)
    if not entry.in_window(title, app):
        if title:
            return False, (f"{said}, but by then {title!r} was in front, so its own "
                           f"tab was not picked — there it would open a second copy")
        return True, (f"{said}, but its own tab was not picked: "
                      f"{blind or 'nothing could be seen in front'}")
    opened, how = platform_seam.focus.url(pick, app=entry.host)
    if not opened:
        return True, f"{said}, but its own tab was not picked: {how}"
    how = how or f"opened {pick}"
    title, app, blind = settled(entry)
    if entry.in_window(title, app):
        return True, how
    if title:
        return False, f"{how}, but {title!r} is in front, not its own window"
    return True, f"{how} ({blind or 'nothing could be seen in front'})"


async def raise_window(entry: Entry, run: Running | None = None,
                       focus_url: str = "") -> None:
    """Bring the dismissed session's window forward, off the loop's thread.

    Off it because the scan asks every app on screen for its window titles, and
    an app that is wedged answers when its timeout runs out rather than never.
    On the loop that would be a stall with no beat, no menu bar and nothing read
    from the events file — the notifier going quiet to raise a window, which is
    the wrong way round. Measured at the desk: the scan is under 10 ms and the
    raise itself about a second from a worker thread, so this lands well after
    the B press it belongs to and says so on its own line.

    Nothing is awaited by the caller and nothing is retried. A window that would
    not come forward is a thing to be told about, not a thing to keep trying at.
    """
    # The session itself where its app can be asked for it (task 42), else its
    # app and the core's own title rule, so B lands where the watched check
    # looks (task 38).
    ok, why = await asyncio.to_thread(reach, entry, run, focus_url)
    say("focused" if ok else "NOT FOCUSED",
        why or "nothing came forward, and nothing said why", project=entry.project)


class Raises:
    """One raise at a time, and the latest press wins (task 66).

    Each press used to get its own worker thread, so two raises ran at once and
    each opened its VS Code link into the window the other had just brought
    forward: a second copy of the session, three in 20 s of alternating B at
    the desk (spec 01, task 66). One
    worker takes them in turn now, and a press that lands while another is
    still waiting replaces it, so mashing B ends on the last session pressed
    rather than on a queue of windows flapping. The one replaced says so, so
    every press that took something still has its line.
    """

    def __init__(self) -> None:
        self.waiting: tuple[Entry, Running | None, str] | None = None
        self.ready = asyncio.Event()

    def ask(self, entry: Entry, run: Running | None, focus_url: str) -> None:
        if self.waiting is not None:
            say("NOT FOCUSED", f"never tried — B moved on to {describe(entry)} in "
                               f"{entry.project} before its turn",
                project=self.waiting[0].project)
        self.waiting = (entry, run, focus_url)
        self.ready.set()

    async def work(self) -> None:
        while True:
            await self.ready.wait()
            self.ready.clear()
            job, self.waiting = self.waiting, None
            try:
                await raise_window(*job)
            # A seam fault ends that raise, not every raise after it: the
            # worker is the only one, and B with nothing coming forward and
            # nothing said is the silence principle 7 is written against.
            except Exception as exc:          # noqa: BLE001
                say("NOT FOCUSED", f"the raise failed: {exc!r}", project=job[0].project)


async def keys(press: asyncio.Event, hold: asyncio.Event) -> None:
    """Enter, on a thread, standing in for the ball's B button.

    A line reading `hold` is B held instead (task 68), so the silence can be
    driven with no ball, as every other B is.

    A daemon thread of its own and not `asyncio.to_thread`: `asyncio.run` joins
    the default executor on the way out, and a `readline` blocked on a terminal
    never returns, so every quit hung there after saying "stopped" — measured
    with SIGTERM on 2026-09-25 (task 35), still alive 15 s later.
    """
    loop = asyncio.get_running_loop()

    def read() -> None:
        for typed in iter(sys.stdin.readline, ""):  # "" is stdin closed: no more B
            loop.call_soon_threadsafe(hold.set if typed.strip() == "hold" else press.set)

    threading.Thread(target=read, name="keys", daemon=True).start()


# Your own Mac sounds (task 70): a file here named after a kind or an outcome
# plays instead of the config's, on the Mac only. The ball keeps its own
# effects and a Pokémon's cry, so what sounds in your hand is never whatever
# file someone dropped in. `silenced` is not a name: a silence that chimes is
# not one (task 68).
OWN_SOUNDS = ROOT / "assets" / "sounds"
OWN_NAMES = (Kind.NEEDS.value, Kind.DONE.value, "caught", "broke_out")
# What `afplay` reads. In this order, so two files with one name are settled
# the same way every run.
OWN_TYPES = (".wav", ".aiff", ".aif", ".m4a", ".mp3", ".caf")


def own_sounds(ladder: Ladder, folder: Path = OWN_SOUNDS) -> tuple[Ladder, list[str], list[str]]:
    """The ladder with your own Mac sounds in it: `(ladder, used, ignored)`.

    Here and not in the core, which does not touch a filesystem (`_mac_sound`).
    Only `mac_sound` changes, so a mute still takes it out (`Ladder.muted`) and
    the ball, which reads `effect`, never hears of it. Anything in the folder
    that is not a name and a type above is listed back, never guessed at: a
    `need.wav` that plays nothing has to say why (principle 7).
    """
    if not folder.is_dir():
        return ladder, [], []
    found: dict[str, Path] = {}
    ignored: list[str] = []
    for path in sorted(folder.iterdir(), key=lambda p: (OWN_TYPES.index(p.suffix.lower())
                                                        if p.suffix.lower() in OWN_TYPES
                                                        else len(OWN_TYPES), p.name)):
        if path.name.startswith("."):
            continue
        if not (path.is_file() and path.stem in OWN_NAMES and path.suffix.lower() in OWN_TYPES):
            ignored.append(path.name)
        elif path.stem in found:
            ignored.append(f"{path.name} ({found[path.stem].name} plays)")
        else:
            found[path.stem] = path
    voices = {kind: replace(voice, mac_sound=str(found[kind.value]))
              if kind.value in found else voice for kind, voice in ladder.voices.items()}
    outcomes = {name: replace(voice, mac_sound=str(found[name]))
                if name in found else voice for name, voice in ladder.outcomes.items()}
    used = [f"{name} {path.name}" for name, path in found.items()]
    return replace(ladder, voices=voices, outcomes=outcomes), used, ignored


def chosen_partner(path: Path, partners: tuple[str, ...]) -> tuple[str, str | None]:
    """The partner `path` names, and why not when it cannot be that one (spec 04, task 03).

    An allowlist: a name is kept only when the config lists it and its cry was
    fetched. Anything else — unreadable, a name no longer listed, a cry deleted —
    is Pikachu, with the reason, which is the edge the spec settles. No file at
    all is Pikachu with nothing to say: that is every run before a choice.
    Pikachu's own cry is not asked for, since there is nothing to fall back to.
    """
    try:
        name = path.read_text().strip()
    except FileNotFoundError:
        return DEFAULT_PARTNER, None
    except (OSError, UnicodeDecodeError) as exc:
        return DEFAULT_PARTNER, f"{path} could not be read ({exc})"
    if name == DEFAULT_PARTNER:
        return name, None
    if name not in partners:
        return DEFAULT_PARTNER, (f"{path} names {name[:40]!r}, which is not a partner in the "
                                 f"config — the ones there are {', '.join(partners)}")
    if not cry_of(name).is_file():
        return DEFAULT_PARTNER, (f"{name}'s cry was never fetched ({cry_of(name)}) — "
                                 f"venv/bin/python3 tools/fetch_cry.py --partner {name}")
    return name, None


def claim(events: Path):
    """Take the one lock a daemon on `events` may hold: `(ok, handle, why)`.

    `ok` false is another daemon holding it, and this one must stop. `ok` true
    with no handle is a lock that could not be taken at all; the run goes on
    and says so, because refusing to notify over a lock file is the silence
    principle 7 forbids. The lock sits beside the events file, as the log does,
    so a desk check's sandbox daemon never collides with the real one (task 50).
    `flock` and not a pid file: the kernel lets go when the process dies, so a
    crash never leaves a lock behind that says someone is still running.
    """
    path = events.expanduser().resolve().parent / LOCK_NAME
    try:
        handle = path.open("a+")
    except OSError as exc:
        return True, None, (f"could not open {path} ({exc}), so a second daemon "
                            f"on this events file would not be stopped")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.seek(0)
        who = handle.read().strip()
        handle.close()
        return False, None, (f"another wobble daemon is already running on this events "
                             f"file ({f'pid {who}' if who else 'its pid unwritten'}, "
                             f"{path}), so this one stops rather than play every signal "
                             f"twice and fight it for the ball")
    except OSError as exc:
        handle.close()
        return True, None, (f"could not lock {path} ({exc}), so a second daemon on "
                            f"this events file would not be stopped")
    handle.seek(0)
    handle.truncate()
    handle.write(f"{os.getpid()}\n")
    handle.flush()
    return True, handle, None


async def run(args) -> int:
    # First, so the config warnings below land in the file as well. The
    # directory follows the events file unless it was named outright, which is
    # what keeps a desk check's thirty lines out of the real record.
    log_dir = Path(args.log_dir) if args.log_dir else log.beside(Path(args.events))
    log_path, log_said = log.start(log_dir, args.log_days, shape=shaped)

    # Before anything that touches the ball or the menu bar (task 50). The
    # handle is kept for the whole run: closing it is letting go.
    alone, lock, lock_said = claim(Path(args.events))
    if not alone:
        say("ALREADY RUNNING", lock_said)
        return 1
    if lock_said:
        say("LOCK NOT HELD", lock_said)

    # `--cry` decides both voices at once: the resource uploaded to the ball,
    # and what `"@cry"` resolves to for the Mac (task 24). Without it the cry
    # is a partner's, the one `var/partner` names, and every partner's ladder is
    # loaded now: a change mid-run is a lookup, never a config read that could
    # fail with nobody at the terminal (spec 04, task 03).
    ladder = load_ladder(cry=args.cry or cry_of(DEFAULT_PARTNER), partner=DEFAULT_PARTNER)
    for warning in ladder.warnings:
        say("CONFIG", warning)
    # Said only when the folder holds something: the run without it is the
    # ordinary one, and a file that plays nothing must not pass unseen (task 70).
    ladder, own, not_own = own_sounds(ladder)
    ladders = {DEFAULT_PARTNER: ladder}
    if args.cry is None:
        ladders.update({name: own_sounds(load_ladder(cry=cry_of(name), partner=name))[0]
                        for name in ladder.partners if name != DEFAULT_PARTNER})
    partner_file = Path(args.events).expanduser().resolve().parent / PARTNER_NAME
    partner, said_refused = (chosen_partner(partner_file, tuple(ladders)) if args.cry is None
                             else (DEFAULT_PARTNER, None))
    if said_refused is not None:
        say("PARTNER NOT KEPT", f"{said_refused}. The partner is {partner.capitalize()}")
    ladder = ladders[partner]
    if own:
        say("your sounds", f"on the Mac only, from {OWN_SOUNDS}: " + " · ".join(own))
    if not_own:
        say("NOT YOUR SOUNDS", f"{', '.join(not_own)} in {OWN_SOUNDS} play for nothing: "
                               f"a file there is named {', '.join(OWN_NAMES)}, as "
                               f"{', '.join(OWN_TYPES)}")

    queue = Queue()
    snooze = args.snooze if args.snooze else ladder.snooze_s
    attention = Attention(queue, snooze=snooze)
    signaller = Signaller(ladder)
    signaller.muted = args.mute
    # The built-in cries are a partner's own, so they go with that partner's
    # upload only: under another `--cry` a done keeps the voice it was given
    # (task 57), and the partner stays Pikachu (spec 04, task 03).
    other_voice = args.cry is not None and Path(args.cry).resolve() != CRY.resolve()
    signaller.one_cry = args.one_cry or other_voice
    # From the top either way (task 47): `--replay` plays it, and a plain run
    # reads it back quietly just before the loop (`recall`). One reader for
    # both, so no line can land between reading the past and following it.
    tail = Tail(Path(args.events), from_end=False)

    ok, sentence = wiring()
    say("HOOKS" if ok else "HOOKS NOT WIRED", sentence)
    say("events", f"{args.events}"
                  f"{' (from the top, played)' if args.replay else ' (read from the top — what'
                     ' was still pending comes back quietly)'}")
    # Said out loud rather than left to be found, because the whole point of a
    # second copy is the run nobody was watching, and a file you have to go
    # looking for is one you only find after you needed it.
    say("log" if log_path else "LOG NOT WRITING", log_said)
    say("B button", "the ball's own button, a right-click on the menu bar item, "
                    "or Enter" if not args.no_menubar else
                    "the ball's own button, or Enter")
    # Only when it is on. A line saying the sounds work would be printed on
    # every ordinary run to tell you nothing; a run that is going to stay quiet
    # has to say so, because from the room it looks identical to a run that
    # died (principle 7).
    if signaller.muted:
        say("muted", "started with --mute: the ball buzzes and lights, and "
                     "neither surface makes a sound. The menu switches it back.")
    # Only when there is an item to click. The `menu bar` line below already
    # says there is none, and a banner that names a gesture you cannot make is
    # the kind of true-sounding wrong sentence principle 7 is against.
    if not args.no_menubar:
        say("menu", "left-click the menu bar item for the list of what is waiting "
                    "— choosing a line goes to that project instead of the top one")
    say("to stop", "Ctrl-C here (or SIGTERM), or left-click the menu bar item and choose "
                   "Quit wobble" if not args.no_menubar else "Ctrl-C here "
                   "(--no-menubar, so there is no item to quit from)")
    say("menu bar", f"{platform_seam.PLATFORM}"
                    + (f" — {platform_seam.UNAVAILABLE}" if platform_seam.UNAVAILABLE
                       else ""))
    say("snooze", f"{snooze:g}s"
                  + ("" if not args.snooze else "  (overridden for this run)"))
    # Said every run, including when it is zero: a hold nobody can see is a
    # ball that looks slow to answer, and zero is a real setting rather than a
    # missing one (task 25).
    say("after a prompt", f"{ladder.after_prompt_s:g}s of quiet after you type "
                          f"before a beat lands"
        if ladder.after_prompt_s else
        "0s — a beat lands in the same moment you type (after_prompt.wait_s)")
    say("after looking away", f"{ladder.look_away_s:g}s before a window you left "
                              f"stops counting as looked at"
        if ladder.look_away_s else
        "0s — a signal speaks the moment you look away (look_away.wait_s)")
    say("a glance", f"{ladder.glance_s:g}s in front before a window counts as looked at"
        if ladder.glance_s else
        "0s — a window counts as looked at the moment it is in front (look_away.glance_s)")
    say("after a close", f"{ladder.after_end_s:g}s of quiet after a session "
                        f"closes before a beat lands"
        if ladder.after_end_s else
        "0s — a beat lands in the same moment a session closes (after_end.wait_s)")
    # Said every run, like the waits above: a config without them plays no
    # catch at all, and from the desk that looks like a catch that broke.
    catches = {name: voice for name, voice in ladder.outcomes.items() if name != "silenced"}
    say("a catch", " · ".join(
        f"{name.replace('_', ' ')} {voice.effect} (muted {ladder.outcome_mutes[name]})"
        for name, voice in catches.items())
        if catches else
        "nothing plays for an answer or a walk-away (no 'outcomes' in the config)")
    # Not a catch: B held or a ⌥ row, and its confirmation is the light alone (task 68).
    hush = ladder.outcomes.get("silenced")
    say("a silence", f"B held {HOLD_S:g}s or ⌥ in the menu: effect {hush.effect} over light "
                     f"{hush.light}, no sound — until you type in it or answer it"
        if hush is not None else
        "B held silences with nothing to confirm it (no 'outcomes.silenced' in the config)")

    def cries() -> str:
        """Which ids a done cries with, and whose they are (task 57, spec 04 task 03).

        The banner's line, and a change of partner's: the same sentence, so the
        log after a change reads like a run started with that partner.
        """
        moods = ladder.moods.get(Kind.DONE)
        fallback = ladder.voices[Kind.DONE].effect
        if moods is not None and not signaller.one_cry:
            return (f"a done cries in a mood, from {partner.capitalize()}'s own — "
                    + " · ".join(f"{name} {_spans(ids)}" for name, ids in moods.pools.items())
                    + f". On the old ball these are only a tap: run with --one-cry "
                      f"for {fallback}, the uploaded one")
        why = ("--one-cry" if args.one_cry else
               f"--cry is {Path(args.cry).name}, and the built-in cries are Pikachu's"
               if moods is not None else "no 'cries' for done in the config")
        whose = "" if other_voice else f", {partner.capitalize()}'s uploaded cry"
        return f"{fallback} for every done{whose} ({why})"

    # Said every run: which ids a done cries with depends on the ball, and the
    # old one plays these as a tap (docs/PROTOCOL.md §6.5).
    done_moods = ladder.moods.get(Kind.DONE)
    say("cries", cries())
    # Said every run, like the waits above (task 64): with it off, a window in
    # front keeps its signal quiet all night.
    said_idle_blind: str | None = None
    if ladder.idle_s:
        idle_now, said_idle_blind = platform_seam.idle.seconds()
        say("CANNOT SEE IDLE" if said_idle_blind else "idle",
            f"{said_idle_blind} — a window in front keeps its signal quiet however "
            f"long nobody touches anything" if said_idle_blind else
            f"a window in front stops counting as looked at after {ladder.idle_s:g}s "
            f"with no key or mouse. Idle right now: {idle_now:.0f}s")
    else:
        say("idle", "0s — a window in front counts as looked at however long nobody "
                    "touches anything (idle.after_s)")
    # Task 67: said every run, since it decides whether a long walk greets you.
    back_s = done_moods.greet_away_s if done_moods is not None else None
    if not ladder.idle_s:
        say("back", "never — nobody is seen coming back with idle.after_s at 0")
    elif back_s is not None:
        say("back", f"after {back_s:g}s with no key or mouse, or the Mac asleep that long")
    else:
        say("back", f"after {ladder.idle_s:g}s with no key or mouse — idle.after_s, "
                    f"with no greet_away_s for done")
    # Before `watching` reads a title, so its line tells the truth about a run
    # that had to ask (task 50).
    if args.ask_access:
        granted, asked = platform_seam.focus.ask()
        say("accessibility" if granted else "NO ACCESS YET",
            asked or "granted — windows can be raised and read")
    # Said at startup, with the title it can actually see, because the failure
    # mode of this one is that it quietly never fires. It matches a session's
    # folder name against the title of the window in front, and whether a given
    # terminal puts the folder in its title is a thing about that terminal, not
    # about this daemon — so the number to check is printed rather than trusted.
    if args.notify_anyway:
        say("watching", "not looked at (--notify-anyway) — a signal plays even "
                        "while you are looking at the session that raised it")
    else:
        front, blind = platform_seam.frontmost.title()
        say("CANNOT SEE FOCUS" if blind else "watching",
            blind or f"a signal stays quiet while its own window is in front. "
                     f"In front right now: {front or 'nothing'}")
    checked = time.monotonic()

    press = asyncio.Event()
    hold = asyncio.Event()          # B held on the ball: silence (task 68)
    # An Event and not a `return` out of the handler, for the same reason B is
    # one: a menu handler runs inside `status.pump()`, in the middle of a tick,
    # so what it does is leave a fact behind for the loop to read at the top.
    quitting = asyncio.Event()
    # Ctrl-C and SIGTERM end the run through the same door as Quit, because
    # that door is the one that turns the ball's light off before letting go.
    # Left to KeyboardInterrupt, the tasks are cancelled mid-flight and a
    # `done`'s 9 stays lit on the desk for tens of minutes with nobody driving
    # it (task 35).
    stopped_by: list[str] = []
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(
            signum, lambda name=signal.Signals(signum).name:
            (stopped_by.append(name), quitting.set()))
    # What a line in the pending list chose, left for the loop the same way.
    # A list rather than one slot because a handler must never be the thing that
    # decides two clicks cannot both count: the loop takes them in the order
    # they were clicked, and each one is a whole B press of its own.
    aimed: list[str] = []
    silencing: list[str] = []       # the menu's ⌥ rows, left the same way (task 68)
    asyncio.create_task(keys(press, hold))
    raises = Raises()
    asyncio.create_task(raises.work())
    menubar = Menubar(on_press=press.set, item=not args.no_menubar)
    if args.no_menubar:
        say("menu bar", "no item this run (--no-menubar) — nothing to click, and "
                        "Enter is the only B button left")

    # `--no-ball` is the development mode, not a degraded one: the menu bar
    # works alone and says so in words (CLAUDE.md). Without it the scan starts
    # now and the ball may take a press of its top button to answer at all.
    ball = None
    if args.no_ball:
        say("ball", "not looking for one (--no-ball) — the Mac plays every beat")
    else:
        cry = Path(args.cry or cry_of(partner))
        ball = Ball(cry, on_press=press.set, on_hold=hold.set, say=say)
        say("ball", f"scanning; its cry will be {cry.name}. Press the "
                    f"ball's top button so it advertises.")
        asyncio.create_task(ball.run())

    def mute(on: bool | None = None) -> None:
        """Switch the sounds off or back on (task 34).

        Both surfaces at once, which is the whole point: muting the ball and
        leaving the Mac chiming would be the same notification arriving from
        the other side of the desk. The core does the work — `Ladder.muted`
        rewrites the voice — so all this does is set the flag and tell the two
        mirrors that a beat they had already been handed is now stale.

        Whatever is sounding right now is cut. Somebody reaching for this is
        reaching for it because of a noise, and a mute that starts at the next
        signal would answer a second too late to be the thing they asked for.

        It is deliberately NOT remembered across restarts: a mute you cannot
        remember switching on is principle 7's silent notifier, and the title
        saying `muted` only saves you while you are looking at the menu bar. A
        run that starts speaking is the honest default; `--mute` is there for
        the case where you meant it.
        """
        signaller.muted = (not signaller.muted) if on is None else on
        menubar.quiet()
        if ball is not None:
            ball.quiet()
        say("muted" if signaller.muted else "unmuted",
            "the ball buzzes and lights, and neither surface makes a sound"
            if signaller.muted else
            "both surfaces have their voices back")

    partner_at = time.monotonic()

    def switch_partner(name: str, refused: str | None) -> None:
        """Speak as `name` from now on: each change said once, each refusal too (spec 04, task 03).

        The next beat takes the new ladder, moods and colour with it. A light a
        done already holds keeps its colour until the ball next writes it, the
        spec's edge case, owed the desk. The ball is handed the new cry, which
        goes up at its next idle wake, or on the next connect.
        """
        nonlocal ladder, partner, said_refused
        if refused != said_refused:
            said_refused = refused
            if refused is not None:
                say("PARTNER NOT KEPT", f"{refused}. The partner is {name.capitalize()}")
        if name == partner:
            return
        partner, ladder = name, ladders[name]
        signaller.ladder = ladder
        if ball is not None:
            ball.revoice(cry_of(name))
        say("partner", f"{name.capitalize()} now, with {cry_of(name).name} and led "
                       f"{ladder.voices[Kind.DONE].led} — {cries()}")

    def partner_lines() -> dict[str, str | None]:
        """Each partner in `Settings › Partner`, and why it cannot be chosen (task 04)."""
        if args.cry is not None:
            return {name: f"not while --cry {Path(args.cry).name} is given"
                    for name in ladder.partners}
        return {name: None if cry_of(name).is_file() else
                f"not fetched · tools/fetch_cry.py --partner {name}" for name in ladder.partners}

    def choose_partner(name: str) -> None:
        """A partner line clicked: kept in `var/partner`, and taken now, not at the next read.

        Spec 04, task 04.
        """
        # Written aside and moved in, so the 2 s read never sees half a name.
        new = partner_file.with_name(f".{PARTNER_NAME}.new")
        try:
            new.write_text(f"{name}\n")
            os.replace(new, partner_file)
        except OSError as exc:
            new.unlink(missing_ok=True)
            say("PARTNER NOT KEPT", f"{partner_file} could not be written ({exc}). "
                                    f"The partner is {partner.capitalize()}")
            return
        switch_partner(*chosen_partner(partner_file, tuple(ladders)))

    # What the menu's rows said last, status words without the countdown, so the
    # log gets a line when one changes and not every poll (task 36).
    said_menu: tuple = ()
    said_login: tuple = ()

    def at_login(login: tuple[str | None, str | None]) -> None:
        """Say opening at login when it changes, the first refresh included (spec 02).

        Read off the seam each refresh rather than said only on a click, so a
        switch in System Settings or a file removed by hand gets its line too,
        and a day's log answers "did it start by itself".
        """
        nonlocal said_login
        if login == said_login:
            return
        said_login = login
        state, why = login
        doubt = f" ({why})" if why else ""
        say("at login", {"off": "off — wobble starts only when somebody opens it",
                         "on": f"on — macOS opens wobble.app at every login{doubt}",
                         "disabled": f"asked for, but {why}"}.get(state, f"cannot — {why}"))

    def switch_login() -> None:
        """The menu's login line: the state read again at the click, then acted on.

        Read again rather than trusted from the label, because the label is
        whatever the last rebuild said and the disk is what is true now. Off in
        System Settings, the click opens it there and changes nothing itself.
        """
        state, _ = platform_seam.login.state()
        if state == "disabled":
            ok, why = platform_seam.login.settings()
        elif state in ("on", "off"):
            ok, why = platform_seam.login.set(state == "off")
        else:
            ok, why = False, "nothing to switch — the line should have been greyed"
        nonlocal said_login
        say("at login" if ok else "AT LOGIN NOT CHANGED", why or "")
        said_login = platform_seam.login.state()     # said just now, in the click's own words

    # Spec 03: `{kind: (state, why)}` as last read, in the seam's order, and when.
    permissions: dict[str, tuple[str | None, str | None]] = {}
    permissions_at: float | None = None

    def at_permission(kind: str, read: tuple[str | None, str | None]) -> None:
        """Say a permission when it changes, the first read included (spec 03, criterion 6).

        Worded like `at_login`: what it is now, and for a refusal what stops
        working, which is the seam's `why`. A refusal and a read that failed are
        in capitals, as every other line about something wobble cannot do.
        """
        if permissions.get(kind) == read:
            return
        state, why = read
        if state == "granted":
            say("permission", f"{kind} granted")
        elif state == "refused":
            say("PERMISSION OFF", why or kind)
        elif state in ("not asked", "not running"):
            say("permission", f"{kind} {state} — {why}" if why else f"{kind} {state}")
        else:
            say("CANNOT SEE PERMISSION", why or f"{kind} could not be read")

    def read_permissions(now: float) -> dict[str, tuple[str | None, str | None]]:
        """Every permission, read again once `PERMISSIONS_EVERY_S` has passed.

        Bluetooth is left out of a `--no-ball` run: nothing there uses the radio,
        and an alert for it would be a fix for nothing. "Not running" keeps the
        answer before it, since macOS answers nothing about an app that is not
        running (task 01) — a refusal does not lift because Terminal was closed.
        """
        nonlocal permissions_at
        if permissions_at is not None and now < permissions_at + PERMISSIONS_EVERY_S:
            return permissions
        permissions_at = now
        for kind in platform_seam.permissions.kinds():
            if kind == "bluetooth" and ball is None:
                continue
            read = platform_seam.permissions.state(kind)
            if read[0] == "not running" and kind in permissions:
                continue
            at_permission(kind, read)
            permissions[kind] = read
        return permissions

    def alerting() -> bool:
        """A `⚠` in the title: something is refused (spec 03)."""
        return any(state == "refused" for state, _ in permissions.values())

    def open_permission(kind: str) -> None:
        """A permission's line clicked: its pane opened, and said either way (spec 03)."""
        ok, why = platform_seam.permissions.settings(kind)
        say("permission" if ok else "SETTINGS NOT OPENED", why or kind)

    def offer(now: float, watching: str | None = None) -> list:
        """The menu behind a left click, rebuilt from what the ball mirror says now.

        Here and not in the mirror because the handlers are the wiring: the menu
        bar knows what to offer, the ball owns its link, and the daemon is the
        one place allowed to know both (`constitution.md`, principle 1).

        The held entry (task 29) is appended after the queue's own order: `B`
        already takes it out of `queue.pending()` and out of the title's count
        (`Queue.drop`, criterion 4), so it would otherwise vanish from the menu
        too for the whole snooze — the one thing you are actually dealing with
        disappearing from view before it is resolved. Clicking it is already
        safe with no new code: `attend()` on a session the queue no longer holds
        is the same no-op it is for any stale row (task 21).

        **Appended only when the queue does not already show that session**
        (task 33). A held session that signals again is back in `pending()` with
        its new kind, and appending the hold on top of it put the same session on
        two lines — the fresh one and a `needs` that had already been answered,
        while the title next to them counted 1. `Queue.pending` gives one line
        per session and the title counts the same lines; a mirror that adds a
        second one is inventing state, which is principle 1 read backwards.
        """
        nonlocal said_menu
        held = attention.entry
        pending = tuple(queue.pending())
        if held is not None and all(entry.session != held.session for entry in pending):
            pending += (held,)
        standing: dict[str, Standing] = {
            entry.session: attention.standing(entry, now, watching=watching)
            for entry in pending}
        said = tuple((f"{entry.project} {short(entry.session)}",
                      status_words(standing[entry.session], countdown=False))
                     for entry in pending)
        if said != said_menu:
            # The whole list on one line: it is what the menu showed from here on,
            # which a run read afterwards cannot rebuild from the other lines.
            said_menu = said
            say("menu", " · ".join(f"{project}: {words}" for project, words in said)
                        or "nothing waiting")
        login = platform_seam.login.state()
        at_login(login)
        return menubar_items(
            ball is not None and ball.connected,
            ball_off=ball is not None and not ball.wanted,
            have_ball_mirror=ball is not None,
            battery=ball.battery if ball is not None else None,
            pending=pending,
            standing=standing,
            muted=signaller.muted,
            on_attend=aimed.append,
            on_connect=lambda: ball.set_wanted(True),
            on_disconnect=lambda: ball.set_wanted(False),
            on_mute=mute,
            on_quit=quitting.set,
            on_silence=silencing.append,
            login=login,
            on_login=switch_login,
            permissions=read_permissions(now),
            on_permission=open_permission,
            partners=partner_lines(),
            partner=partner if args.cry is None else None,
            on_partner=choose_partner)

    def attended(taken: Taken, how: str) -> None:
        """What happens after the core was told, whichever door told it.

        One function because B and a chosen line are one act — criterion 4's
        silence, criterion 7's hand-back, and the window coming forward. Two
        copies of this would keep agreeing until the day one of them was
        changed, and the same reasoning is why `Attention.dismiss` and
        `Attention.attend` share `_take` rather than resembling each other.

        The sound is cut here rather than before the take, which is safe for
        exactly one reason: nothing between reading the press and this line
        makes a sound, and the tick's own beat is played further down, after it.
        """
        menubar.quiet()
        if ball is not None:
            ball.quiet()
        if not taken.again:
            held_away.reset()
        # Criterion 7: pressing B while already attending skips to the next,
        # and the one you were on goes to the back of the queue. Said out loud either
        # way — the count on the next line does not drop for it, and an entry
        # that reappears with nothing having announced it reads as a bug rather
        # than as the promise it is.
        if taken.released is not None:
            left = taken.released
            say("let go", "back in the queue, at the back" + quietly(left.session)
                          if left.returned else
                          "it signalled again while you were on it, so the "
                          "newer one stands",
                project=left.project)
        # Task 46: a lone B pressed again has nothing to skip to, so it asks
        # for the window once more rather than letting the signal cry again.
        say(how, f"raising {describe(taken.attending)} again — nothing else is waiting"
                 if taken.again else
                 f"attending {describe(taken.attending)} ({len(queue)} left)",
            project=taken.attending.project if taken.attending else "")
        # Task 64: a done that has called greets you as you come for it.
        greeting, no_greet = signaller.greet(taken.attending, now)
        if greeting is not None:
            once(greeting, "greet", f"you came for it ({how})",
                 taken.attending.project, playing="the greet is still playing")
        if no_greet is not None:
            say("no greet", no_greet, project=taken.attending.project)
        # Said on its own line when it lands, not promised here: until task 14
        # ran, "· focus <project>" was printed on the press whether a window
        # came forward or not.
        if taken.attending is not None:
            session = taken.attending.session
            raises.ask(taken.attending, known.get(session), tabs.get(session, ""))

    cannot_draw = menubar.refresh(queue.live(), ball_connected=False,
                                  muted=signaller.muted, have_ball_mirror=ball is not None,
                                  menu=offer(time.monotonic()), alert=alerting())
    if cannot_draw is not None:
        say("MENU BALL", cannot_draw)
    unreadable = 0
    injected = 0
    reminders = 0
    # The session whose signal is being held quiet because you are looking at
    # it, and the last could-not-tell sentence already said. Both exist to keep
    # a per-poll fact from becoming a per-poll line.
    watching: str | None = None
    said_blind: str | None = None
    # The window in front the last time it was said, and the app owning it —
    # `None` again once nothing is pending, so the next signal says it afresh.
    said_front: tuple[str | None, str | None] | None = None
    look_away = LookAway(ladder.look_away_s, ladder.glance_s)
    # Task 67: the greet for coming back waits for a long time away, not the
    # soft's minute. Without the key, the minute as before.
    keys_away = Away(back_s if back_s is not None else ladder.idle_s)
    front_since: float | None = None
    held_away = HeldAway(ladder.look_away_s)
    # The `needs` last said to speak over a hold, so it is said once (task 52).
    said_through: str | None = None
    # When a person last typed anywhere, and the hold already announced. An
    # injected turn is not a person and does not set it — the same distinction
    # criterion 5 is built on (`hooks.by_person`).
    typed_at: float | None = None
    # When a person last prompted each session, so a done knows how long its
    # turn ran (task 64).
    prompted_at: dict[str, float] = {}
    # The session last said to be speaking for nobody touching anything (task 64).
    said_idle: str | None = None
    # When a session last closed (task 44): the next beat waits `after_end_s`
    # from here, so it is not taken for the tab that was just closed.
    closed_at: float | None = None
    # The tool each session's last line asked about, `""` once anything else
    # followed it (task 49): what an `answered` line has to match.
    asked: dict[str, str] = {}
    # Which agent asked it, `""` for the main thread (task 71): an `answered`
    # has to come from the same one. `asking` holds the line that queued a
    # question until its notice, 6 s on, is seen and skipped (task 72).
    asker: dict[str, str] = {}
    asking: dict[str, HookLine] = {}
    # When each session's Bash question was read, in epoch seconds like a
    # process's start (task 65): a Bash started before it was not its answer.
    asked_at: dict[str, float] = {}
    approved_at = float("-inf")
    said_blind_children: str | None = None
    held: tuple[str, float] | None = None
    # Each signalling session's claude, from Claude Code's registry (task 40):
    # `None` for one looked up and not found, so it is not looked up per line.
    known: dict[str, Running | None] = {}
    # Each session's Warp tab address, from its hook lines (task 42).
    tabs: dict[str, str] = {}
    # Each VS Code session's possible tab titles, by session (task 43): the
    # registry's name and its transcript's titles.
    vscode_tabs: dict[str, frozenset[str]] = {}
    titles = Titles()
    # Each Warp session's tab name as the daemon wrote it (task 43), and the
    # sessions it was tried for, so a failure is said once, not per line.
    warp_tabs: dict[str, str] = {}
    warp_tried: set[str] = set()
    tabs_at = float("-inf")
    # Terminal's tab in front, asked off the loop at most once a second while
    # Terminal is in front, and each terminal claude's tty (task 43).
    term_ttys: dict[str, str] = {}
    front_tty: str | None = None
    tty_asking: asyncio.Future | None = None
    tty_at = float("-inf")
    said_tty_blind: str | None = None
    said_tty: str | None = None
    alive_at = time.monotonic()
    said_blind_process: str | None = None

    def look(session: str, project: str) -> None:
        """Find this session's claude, once, and say what was found."""
        if session in known:
            return
        run = known[session] = running(session)
        say("session", f"{short(session)} — {run.entrypoint or 'no entrypoint'}, "
                       f"pid {run.pid}" + (f", {run.name!r}" if run.name else "")
            if run else
            f"{short(session)} — not in Claude Code's registry, so a claude killed "
            f"without its SessionEnd would keep this waiting", project=project)

    def name_tab(session: str, project: str, host: str) -> None:
        """Name a Warp session's tab `<project> · <id4>`, once (task 43)."""
        if host != WARP or session in warp_tried:
            return
        warp_tried.add(session)
        look(session, project)
        run = known.get(session)
        text = f"{project} · {short(session)}"
        ok, why = (platform_seam.process.title(run.pid, text) if run is not None else
                   (False, "not in Claude Code's registry, so its terminal is unknown"))
        if ok:
            warp_tabs[session] = text
        say("tab named" if ok else "TAB NOT NAMED",
            f"{short(session)} — {why}" + ("" if ok else
                                           " — Warp tells it from a twin by folder only"),
            project=project)

    outcome_until: float | None = None
    outcome_why = "a catch is still playing"

    def outcome(name: str, why: str, project: str) -> None:
        """Play how a catch ended, once, on whichever surface is there (task 56)."""
        voice = ladder.outcome(name, signaller.muted)
        if voice is not None:
            once(voice, name.replace("_", " "), why, project,
                 playing="a catch is still playing")

    def once(voice, label: str, why: str, project: str, *, playing: str) -> None:
        """Play a one-shot — a catch's end, a greet (task 64) — on whichever surface is there.

        Not a beat: nothing repeats it and it is not the signaller's. What it
        owns is the hold after it, so the next beat does not land on top of it
        — light and sound are one lane each, and a later id replaces the
        earlier one (docs/PROTOCOL.md §6.2). `playing` is that hold's reason.
        """
        nonlocal outcome_until, outcome_why
        say(f"play ({label})",
            f"effect {voice.effect}{' · silent' if voice.silent else ''} — {why}",
            project=project)
        on_ball = ball is not None and ball.connected
        if on_ball:
            ball.beat(voice)
        _, why_not = menubar.beat(voice, ball_connected=on_ball)
        if why_not is not None:
            say("NO SOUND", f"{why_not} — with no ball, that was not heard at all",
                project=project)
        if voice.lasts_s is not None:
            # The loop's own `now`, as every other hold: a fresh clock read here
            # is later than it, and 2.0 s left then read "waits 3s".
            outcome_until, outcome_why = now + voice.lasts_s, playing

    def quietly(session: str) -> str:
        """Said after a row that came back, when it came back quiet (task 68)."""
        back = queue.get(session)
        if back is None or not back.quiet:
            return ""
        return (", quiet — it is silenced" if queue.silenced(session) else
                ", quiet — you had seen it")

    def hushed(silenced: Silenced, how: str, aimed_at: str | None = None) -> None:
        """A session silenced, by B held or by the menu's ⌥ row (task 68).

        The sound is cut first, as `mute` cuts it: somebody reaching for this
        is reaching for it because of a noise. Then the confirmation, which is
        an outcome and silent, so the light says it and the Mac says nothing.
        """
        if not silenced:
            # Principle 7: a hold that did nothing says so, as a stale row does.
            say(how, f"{short(aimed_at)} was not waiting any more — nothing silenced"
                     if aimed_at is not None else "nothing waiting — nothing silenced")
            return
        menubar.quiet()
        if ball is not None:
            ball.quiet()
        left = silenced.released
        say("silenced", f"{short(silenced.session)} — quiet until you type in it or "
                        f"answer it" + ("; the one you were on went back to the queue, quiet"
                                        if left is not None else ""),
            project=silenced.project)
        outcome("silenced", how, silenced.project)

    # Each session's wait as its end will tell it (task 86).
    lives: dict[str, Life] = {}

    def life(entry: Entry | Waiting) -> Life:
        """This session's wait, begun at its `since` when it began before this run did."""
        had = lives.get(entry.session)
        if had is None or had.kind is not entry.kind:
            had = lives[entry.session] = Life(entry.kind, entry.since)
        return had

    said_kept: str | None = None

    def lived(entry: Waiting, how: str) -> str:
        """How the wait that just ended went, said at the end of its line (task 86).

        Kept in `signals.tsv` too, under `how` (`log.HOWS`, task 89).
        """
        nonlocal said_kept
        had = life(entry)
        del lives[entry.session]
        why = log.ended(entry.kind.value, now - had.start, had.beats, had.heard, how)
        if why is not None and why != said_kept:
            say("SIGNALS NOT KEPT", why)
        said_kept = why
        return (f" · after {span(now - had.start)} · {had.beats} "
                f"beat{'' if had.beats == 1 else 's'} ({had.heard} heard)")

    def closed(over, what: str, why: str, how: str) -> None:
        """Say what a session leaving took out. Nothing, when it took nothing."""
        if over.dropped is not None:
            say(what, f"{describe(over.dropped)} — {why}{lived(over.dropped, how)}",
                project=over.dropped.project)
        if over.released is not None:
            say("released", f"after {over.released.waited:.0f}s — nothing "
                            f"left in it to attend",
                project=over.released.project)

    def replied(session: str, how: str, kept: str, typed: bool = True) -> None:
        """Its question was answered where it was asked (task 49), said as `how`.

        `typed` is False when no hand is known to have been at it: a turn's end
        says the question is over, not that somebody just answered (task 73).
        `kept` is how `signals.tsv` files it (task 89).
        """
        nonlocal typed_at
        # Answering in place is a hand at the keyboard as much as a prompt
        # is (task 53): at 16:24:19 on 2026-09-29 the next `done` cried in
        # the same second the question was answered. Armed as `prompt` arms it.
        if typed and (typed_at is None or now >= typed_at + ladder.after_prompt_s):
            typed_at = now
        asked.pop(session, None)
        asker.pop(session, None)
        asking.pop(session, None)
        asked_at.pop(session, None)
        answered = attention.replied(session, now)
        if answered.dropped is not None:
            say("resolved",
                f"{describe(answered.dropped)} — {how}{lived(answered.dropped, kept)}",
                project=answered.dropped.project)
        if answered.released is not None:
            say("released", f"after {answered.released.waited:.0f}s",
                project=answered.released.project)
        if answered.unsilenced:
            say("unsilenced", f"its question was answered — {how}",
                project=answered.dropped.project)
        if answered.caught:
            outcome("caught", "its question was answered", answered.dropped.project)

    if not args.replay:
        # Task 47: what was pending before the restart comes back, quietly, and
        # only for a claude still running — the file is never rotated, and a
        # day of closed tabs would otherwise come back with it. A process list
        # nobody could read keeps the session, the loud direction (principle 7).
        found = recall(tail.lines(), queue, time.monotonic(), asked, asker)
        gone = 0
        for entry in queue.pending():
            run = running(entry.session)
            started, blind = (platform_seam.process.started(run.pid) if run is not None
                              else (None, None))
            if run is None or (blind is None and not run.alive(started)):
                queue.drop_session(entry.session)
                gone += 1
                continue
            known[entry.session] = run
            if entry.session in found:
                tabs[entry.session] = found[entry.session]
        back = queue.hush()
        for entry in queue.pending():
            say("restored", f"{describe(entry)} — quiet until its session does "
                            f"something new", project=entry.project)
        # A short tag: the column is 22 wide, and a longer one runs into the count.
        say("restart", f"{back} back from before it (quiet) — not counted, not "
                       f"signalled; B reaches them once nothing new is waiting" + (f". {gone} dropped: their claude is not "
                                         f"running" if gone else ""))

    while True:
        now = time.monotonic()
        # Before anything reads `press`: this is where a click becomes one.
        platform_seam.status.pump()
        # And straight after it, because that is where Quit becomes one too.
        # Above the tail on purpose: an event that arrives in the same tick as
        # the choice to quit is left in the file rather than half-handled, and
        # the file is where the next daemon will find it.
        if quitting.is_set():
            break

        for line in tail.lines():
            hook = parse(line)
            if hook is None:
                unreadable += 1
                say("UNREADABLE LINE", f"{line[:60]!r} — {unreadable} so far. A hook "
                                       f"writing lines nobody can read is a notifier "
                                       f"that has stopped.")
                continue
            if hook.focus_url:
                tabs[hook.session] = hook.focus_url
            if hook.what == "answered":
                # One of these per tool call, so one that answers nothing says
                # nothing — and it is above `name_tab` because its line carries
                # no folder to name a tab after (`hook_event.sh`, task 49).
                if not answers(hook, asked.get(hook.session, ""),
                               asker.get(hook.session, "")):
                    continue
                replied(hook.session, "answered where it asked", "answered")
                continue
            if restates(hook, asking.pop(hook.session, None)):
                # Claude Code's notice of a question already beating since its
                # `asking` (task 72): queued again, one question would be two needs.
                say("its notice", f"needs · {short(hook.session)} — Claude Code's own, 6s "
                                  f"after the question it already queued",
                    project=hook.project)
                continue
            if hook.what == "asking":
                asking[hook.session] = hook
            name_tab(hook.session, hook.project, hook.host)
            if hook.what == "prompt" and not hook.by_person:
                # Not a person arriving, so it resolves nothing (criterion 5).
                # Counted and said rather than dropped quietly: if this ever
                # starts eating real prompts, the symptom is a signal that will
                # not go away, and this line is the only thing that would
                # explain it.
                injected += 1
                say("injected turn", f"it re-invoked itself — not a person, so "
                                     f"nothing was resolved ({injected} so far)",
                    project=hook.project)
                continue
            if hook.reminder:
                # Claude Code's 60 s "waiting for your input", not a question
                # (task 39, `hooks.reminds`). Said rather than dropped quietly,
                # for the same reason as an injected turn: if it ever starts
                # eating real questions, this line is what explains the silence.
                reminders += 1
                say("idle reminder", f"Claude Code's 60s 'waiting for your input' — "
                                     f"not a question, so nothing was queued "
                                     f"({reminders} so far)",
                    project=hook.project)
                continue
            if hook.what == "prompt":
                # Armed by the first keystroke of a burst, and not re-armed by
                # the ones after it: a prompt three seconds into a live window
                # would otherwise push the wait out again, and somebody typing
                # steadily would never hear the ball at all. Principle 7 is
                # what bounds this — five seconds is a pause, an unbounded one
                # is a signal that fell silent on its own.
                if typed_at is None or now >= typed_at + ladder.after_prompt_s:
                    typed_at = now
                prompted_at[hook.session] = now
                asked.pop(hook.session, None)
                asker.pop(hook.session, None)
                answered = attention.prompted(hook.session, hook.project, now)
                if answered.dropped is not None:
                    say("resolved", f"{describe(answered.dropped)} — you were there"
                                    f"{lived(answered.dropped, 'there')}",
                        project=answered.dropped.project)
                if answered.released is not None:
                    say("released", f"after {answered.released.waited:.0f}s",
                        project=answered.released.project)
                if answered.unsilenced:
                    say("unsilenced", "you typed in it, so it speaks again",
                        project=hook.project)
                if answered.caught:
                    outcome("caught", "it was answered by a prompt in its session",
                            hook.project)
                continue
            if hook.what == "end":
                # An end that took nothing out says nothing, and that is a
                # decision rather than an omission: most sessions close long
                # after whatever they signalled was dealt with, and a line per
                # closed tab would bury the ends that mean something. What it
                # DID take out is always said — a `done` nobody ever saw, gone
                # because the window it belonged to went away, is exactly the
                # thing principle 7 wants left on the record.
                known.pop(hook.session, None)
                tabs.pop(hook.session, None)
                asked.pop(hook.session, None)
                asker.pop(hook.session, None)
                prompted_at.pop(hook.session, None)
                warp_tabs.pop(hook.session, None)
                warp_tried.discard(hook.session)
                closed_at = now
                closed(attention.ended(hook.session, hook.project, now),
                       "session ended", "it stopped waiting when its session closed", "closed")
                continue
            event = hook.as_event(now)
            if event is not None:
                if event.kind is Kind.DONE and event.session in prompted_at:
                    event = replace(event, turn_s=now - prompted_at.pop(event.session))
                if event.kind is Kind.DONE and any(
                        entry is not None and entry.session == event.session
                        and entry.kind is Kind.NEEDS
                        for entry in (queue.get(event.session), attention.entry)):
                    # A turn that ended asks nothing any more (task 73): a denial
                    # runs no tool, so its Stop is the only word that it is over.
                    replied(event.session, "its turn ended", "turn ended", typed=False)
                asked[event.session] = hook.tool if event.kind is Kind.NEEDS else ""
                asker[event.session] = hook.agent if event.kind is Kind.NEEDS else ""
                if asked[event.session] == BASH:
                    asked_at[event.session] = time.time()
                look(event.session, event.project)
                had = lives.get(event.session)
                again = had is not None and had.kind is event.kind
                if not again:
                    had = lives[event.session] = Life(event.kind, now)
                # Task 88: a session signalling the kind it already waits on is
                # the same wait, said so, and where the earlier one stood.
                old = queue.get(event.session)
                held = attention.entry is not None and attention.entry.session == event.session
                queue.add(event)
                say("queued", f"{event.kind.value} · {short(event.session)} "
                              f"({len(queue)} pending)"
                              + (f" — again, waiting {span(now - had.start)}"
                                 + (", while you are on it" if held else "")
                                 + (", quiet until now" if old is not None and old.quiet
                                    and not queue.silenced(event.session) else "")
                                 if again else "")
                              + (" — the turn ended in an API error" if event.failed else "")
                              + (" — a subagent asks it, so only its answer counts"
                                 if asker[event.session] else "")
                              + (" — silenced, so it waits quiet"
                                 if queue.silenced(event.session) else ""),
                    project=event.project)

        # A claude killed before its SessionEnd ran — a closed Warp tab, a
        # crash — leaves its signal waiting for a prompt that cannot come (task
        # 40). Only sessions found in the registry are asked about; one that
        # could not be asked stays, which is the loud direction (principle 7).
        if now >= alive_at + ALIVE_EVERY_S:
            alive_at = now
            waiting = {(w.session, w.project)
                       for e in (*queue.pending(), attention.entry) if e is not None
                       for w in e.waiting}
            for session, project in sorted(waiting):
                run = known.get(session)
                if run is None:
                    continue
                started, blind = platform_seam.process.started(run.pid)
                if blind is not None:
                    if blind != said_blind_process:
                        said_blind_process = blind
                        say("CANNOT SEE PROCESSES", f"{blind} — a claude killed without "
                                                    f"its SessionEnd keeps its signal waiting")
                    continue
                if not run.alive(started):
                    # Resumed rather than gone: the same session, a newer pid.
                    fresh = running(session)
                    if (fresh is not None and fresh.pid != run.pid
                            and fresh.alive(platform_seam.process.started(fresh.pid)[0])):
                        known[session] = fresh
                        # A resumed claude may be in another tab: name it again.
                        warp_tabs.pop(session, None)
                        warp_tried.discard(session)
                        say("session", f"{short(session)} — now pid {fresh.pid}; pid "
                                       f"{run.pid} is gone, the session is not",
                            project=project)
                        continue
                    known.pop(session, None)
                    closed_at = now
                    closed(attention.ended(session, project, now), "process gone",
                           f"its claude (pid {run.pid}) is not running, and no "
                           f"SessionEnd said so", "gone")

        # A Bash question is answered the moment its command starts, not when it
        # ends (task 65): the yes fires no hook, and `PostToolUse` waits for the
        # command. Only a child started after the question was read; a claude
        # whose children cannot be read keeps its question, the loud direction.
        if asked_at and now >= approved_at + APPROVED_EVERY_S:
            approved_at = now
            for session, since in list(asked_at.items()):
                run = known.get(session)
                if asked.get(session) != BASH or run is None:
                    asked_at.pop(session, None)
                    continue
                kids, blind = platform_seam.process.children(run.pid)
                if blind is not None:
                    if blind != said_blind_children:
                        said_blind_children = blind
                        say("CANNOT SEE CHILDREN", f"{blind} — an approved Bash keeps "
                                                   f"its question waiting until it ends")
                    continue
                for kid in kids:
                    started, _ = platform_seam.process.started(kid)
                    if started is None or started < since:
                        continue
                    argv, _ = platform_seam.process.command(kid)
                    if argv is not None and runs_bash(argv):
                        replied(session, f"its Bash started (pid {kid}), so it was approved",
                                "approved")
                        break

        if tail.restarts:
            say("events file restarted", f"{tail.restarts}x — it was truncated or "
                                         f"replaced under us")
            tail.restarts = 0

        released = attention.tick(now)
        if released is not None:
            say("snooze", f"came back after {released.waited:.0f}s, at the back of the queue"
                          + quietly(released.session)
                          if released.returned else
                          f"let go after {released.waited:.0f}s — it had signalled "
                          f"again, so the newer one stands",
                project=released.project)

        connected = ball is not None and ball.connected

        if press.is_set():
            press.clear()
            attended(attention.dismiss(now), "B pressed")

        # After the plain press, and one at a time: each is a full press, so a
        # second choice releases the first exactly as a second B would. The
        # menu is rebuilt from the queue every refresh, but a click still races
        # a poll — by the time this reads it, the session may have been
        # answered, ended, or attended by the press just above.
        while aimed:
            chosen = aimed.pop(0)
            taken = attention.attend(chosen, now)
            if taken.attending is None:
                # Principle 7: it is a menu line that did nothing, so it says
                # so. NOT a fallback to the top of the queue — that would raise
                # a window nobody asked for, which is worse than the nothing it
                # was trying to avoid.
                say("B aimed", f"{short(chosen)} was not waiting any more — nothing "
                               f"changed, and nothing was let go")
                continue
            attended(taken, "B aimed")

        if hold.is_set():
            hold.clear()
            hushed(attention.silence(now), "B held")
        while silencing:
            chosen = silencing.pop(0)
            hushed(attention.silence(now, chosen), "silence chosen", aimed_at=chosen)

        current = attention.current()

        # Asked only when something is pending: it is the one read in this loop
        # that talks to the window server, and with an empty queue there is
        # nothing it could change. The answer feeds `Entry.in_window` — the
        # matching is ordinary string work and lives in the core, so the seam
        # only has to know how to see a title (`core/signals.py`).
        watched = False
        # The held one is asked about too (task 52): being out of its window
        # is what lets a `needs` speak over a held `needs`.
        target = current if current is not None else attention.entry
        if target is not None and not args.notify_anyway:
            front, front_app, blind = platform_seam.frontmost.window()
            if blind is not None and blind != said_blind:
                # Once per distinct reason, not once per poll: four times a
                # second it would be the only thing in the terminal. Said at
                # all because a signal that stays quiet for a reason nobody can
                # see is the silence principle 7 forbids — except here the cause
                # would be the opposite of quiet, so the sentence says which way
                # it fails.
                said_blind = blind
                say("CANNOT SEE FOCUS", blind)
            if (front, front_app) != said_front:
                # Task 67: the first read since nothing was pending is not a
                # change — you were already there, and a glance is a move.
                front_since = now if said_front is not None else None
                # On every change while something is pending, asked for at the
                # desk 2026-09-28 (task 38): the log said what played and never
                # where you were, so "it stayed quiet while I was elsewhere"
                # could only be taken on trust.
                said_front = (front, front_app)
                say("in front", f"{front!r} in {front_app or 'an app it could not name'}"
                    if front else "no window it can read")
            if now >= tabs_at + TABS_EVERY_S:
                tabs_at = now
                runs = registry()
                vscode_tabs = {run.session: titles.of(run.session)
                               | ({run.name} if run.name else frozenset())
                               for run in runs if run.entrypoint == "claude-vscode"}
                term_ttys = {run.session: tty for run in runs if run.entrypoint == "cli"
                             and (tty := platform_seam.process.tty(run.pid)[0])}
            if tty_asking is not None and tty_asking.done():
                try:
                    front_tty, why = tty_asking.result()
                except Exception as exc:          # a seam fault must not stop the loop
                    front_tty, why = None, f"asking Terminal's tab failed ({exc!r})"
                tty_asking = None
                if why is not None and why != said_tty_blind:
                    said_tty_blind = why
                    say("CANNOT SEE TAB", why)
                if front_tty != said_tty:
                    said_tty = front_tty
                    if front_tty:
                        say("in front", f"Terminal's tab on {front_tty}")
            if front_app != TERMINAL:
                front_tty = None
            elif tty_asking is None and now >= tty_at + TABS_EVERY_S:
                tty_at = now
                tty_asking = asyncio.ensure_future(
                    asyncio.to_thread(platform_seam.frontmost.tab_tty, TERMINAL))

            def tabs_of(entry: Entry) -> tuple[frozenset[str], frozenset[str]]:
                """This session's own tabs, and every Claude tab, for its host."""
                if entry.host == TERMINAL:
                    return (frozenset({term_ttys[entry.session]} if entry.session in term_ttys
                                      else ()),
                            frozenset(term_ttys.values()))
                own = vscode_tabs.get(entry.session, frozenset())
                if entry.session in warp_tabs:
                    own = own | {warp_tabs[entry.session]}
                return own, frozenset().union(*vscode_tabs.values(), warp_tabs.values())

            holding = attention.entry
            if holding is not None:
                own, claude_tabs = tabs_of(holding)
                away = held_away.away(
                    holding.session,
                    holding.here(front, front_app, own=own, tabs=claude_tabs,
                                 tty=front_tty), now)
                if attention.set_away(away, seen=held_away.seen):
                    say("broke out", f"{describe(holding)} — you left its window "
                                     f"{ladder.look_away_s:g}s ago without answering, so "
                                     f"it speaks again until you are back",
                        project=holding.project)
                    outcome("broke_out", "a needs you took and walked away from",
                            holding.project)
                current = attention.current()
            if current is not None:
                own, claude_tabs = tabs_of(current)
                watched = current.in_window(front, front_app, own=own, tabs=claude_tabs,
                                            tty=front_tty)
        elif target is None:
            said_front = None
        watched = look_away.watched(current.session if current is not None else None,
                                    watched, now, front_since)

        # Task 64: in front shields a signal only while somebody is at the keys.
        # An idle nobody could read counts as somebody there — the old rule.
        idle_s = None
        if target is not None:
            idle_s, idle_blind = platform_seam.idle.seconds()
            if idle_blind is not None and idle_blind != said_idle_blind:
                said_idle_blind = idle_blind
                say("CANNOT SEE IDLE", f"{idle_blind} — a window in front keeps its "
                                       f"signal quiet however long nobody touches anything")
        still = bool(ladder.idle_s) and idle_s is not None and idle_s >= ladder.idle_s
        idle_front = watched and still
        watched = watched and not still
        came_back = keys_away.back(idle_s if ladder.idle_s else None, time.time(), now)
        # Task 87: a long wait split into away and seen-and-left. Only while
        # something is pending, the one time idle is read.
        if keys_away.went is not None:
            say("left the keys", keys_away.went)
        if came_back is not None:
            say("back at the keys", f"after {span(keys_away.gone_s)}")

        # Said on the edge (tasks 52, 54): a signal speaking while something is
        # held would otherwise read as the hold having broken.
        holding = attention.entry
        # The held one broken out is not speaking over a hold: it is the hold.
        through = (current.session if current is not None and holding is not None
                   and current.session != holding.session else None)
        if through != said_through:
            if through is not None:
                say("over the hold", f"{describe(current)} — " + (
                        f"you have been out of the {holding.kind.value} you are "
                        f"attending {ladder.look_away_s:g}s, so it holds nothing back"
                        if attention.away else
                        f"a needs speaks over the {holding.kind.value} you are attending"),
                    project=current.project)
            said_through = through

        # Said on the edges only, and keyed by session so the next signal says
        # it again rather than inheriting the last one's silence. Both
        # directions: you are owed the reason a thing went quiet, and the reason
        # it started up again.
        quiet_for = current.session if (current is not None and watched) else None
        if quiet_for != watching:
            if quiet_for is not None:
                say("not signalling", f"{describe(current)} — you are looking at its "
                                      f"window, so it stays pending and quiet",
                    project=current.project)
            elif current is not None and current.session == watching and not idle_front:
                say("signalling", f"{describe(current)} — you looked away"
                                  + (f" {ladder.look_away_s:g}s ago" if ladder.look_away_s
                                     else ""),
                    project=current.project)
            watching = quiet_for
        idle_for = current.session if idle_front else None
        if idle_for != said_idle:
            if idle_for is not None:
                say("signalling", f"{describe(current)} — no input for "
                                  f"{ladder.idle_s:g}s with its window in front",
                    project=current.project)
            said_idle = idle_for
        if came_back is not None and current is not None:
            greeting, no_greet = signaller.greet(current, now)
            if greeting is not None:
                once(greeting, "greet", f"you are back: {came_back}", current.project,
                     playing="the greet is still playing")
            if no_greet is not None:
                say("no greet", no_greet, project=current.project)

        # The later of the two holds, and the reason is the one that decides it.
        holds = [(at, why) for at, why in (
            (None if typed_at is None else typed_at + ladder.after_prompt_s,
             "you just typed"),
            (None if closed_at is None else closed_at + ladder.after_end_s,
             "a session just closed"),
            (outcome_until, outcome_why)) if at is not None]
        hold_until, hold_why = max(holds) if holds else (None, "")
        # Said once per hold rather than once per poll, and only when there is
        # something it is actually holding back. Principle 7: five seconds of a
        # ball saying nothing, for a reason nobody can see, is the silence this
        # project refuses — and the line after it is the beat itself, which is
        # why there is no second line for the hold ending.
        if (current is not None and not watched
                and hold_until is not None and now < hold_until):
            if held != (current.session, hold_until):
                held = (current.session, hold_until)
                # Up, not to nearest: 0.3 s left read "waits 0s" (log, 2026-09-28 21:20:11).
                say("holding", f"{describe(current)} — {hold_why}, so it waits "
                               f"{math.ceil(hold_until - now)}s before speaking",
                    project=current.project)

        voice = signaller.due(current, now, watched=watched, hold_until=hold_until,
                              idle_front=idle_front)
        if voice is not None:
            # The held light is named because it is the half of a `done` that
            # stays: the ball sends it only when it is not already up, so the
            # line says what the beat wants and the ball says what it did.
            light = (f" over light {voice.light}"
                     if voice.light is not None and voice.light != voice.effect
                     else "")
            # The mood after the light (task 64), so "effect N over light 9" reads as before.
            mood = (f" · {signaller.mood}" if signaller.mood and not signaller.muted
                    else "")
            say("play (beat)", f"effect {voice.effect}{light}{mood}"
                               f"{' · silent' if voice.silent else ''}"
                               # The ladder's own count (task 88): a 1 after
                               # an `again` is a ladder that started over.
                               f" — {describe(current)} · beat {signaller.beats}",
                project=current.project if current is not None else "")
            if connected:
                ball.beat(voice)
            played, why_not = menubar.beat(voice, ball_connected=connected)
            if current is not None:
                had = life(current)
                had.beats += 1
                had.heard += not voice.silent and (connected or played)
            if why_not is not None:
                say("NO SOUND", f"{why_not} — with no ball, that beat was not "
                                f"heard at all",
                    project=current.project if current is not None else "")

        # One answer for both surfaces: the menu bar's ball holds the light
        # the real one holds (task 58).
        showing = signaller.showing(current, watched=watched)
        cannot_draw = menubar.refresh(queue.live(), ball_connected=connected,
                                      ball_off=ball is not None and not ball.wanted,
                                      battery=ball.battery if ball is not None else None,
                                      muted=signaller.muted,
                                      have_ball_mirror=ball is not None,
                                      # After `menu=`: arguments are evaluated in
                                      # order, so this is what `offer` just read.
                                      menu=offer(now, watching=watching), showing=showing,
                                      alert=alerting())
        if cannot_draw is not None:
            say("MENU BALL", cannot_draw)
        if ball is not None:
            ball.refresh(showing)

        if now - checked > WIRING_EVERY_S:
            checked = now
            ok_now, sentence_now = wiring()
            if ok_now != ok:
                ok = ok_now
                say("HOOKS" if ok else "HOOKS NOT WIRED", sentence_now)

        # Read again rather than told: a hand edit is a change too (spec 04, task 03).
        if args.cry is None and now >= partner_at + PARTNER_EVERY_S:
            partner_at = now
            switch_partner(*chosen_partner(partner_file, tuple(ladders)))

        await asyncio.sleep(args.poll)

    # Quit, chosen from the menu bar. Everything below is the difference between
    # putting the ball down and dropping it — and every line of it is said out
    # loud, because a daemon that went away without a word is the one thing
    # principle 7 cannot allow, and quitting is the one time that is expected.
    say("quit", f"{stopped_by[0] if stopped_by else 'chosen from the menu bar'} — "
                f"{len(queue)} still pending, and the next run brings back the ones "
                f"whose claude is still running, quietly")
    menubar.quiet()
    if ball is not None and ball.connected:
        ball.set_wanted(False)
        letting_go = time.monotonic()
        while ball.connected and time.monotonic() - letting_go < QUIT_GRACE_S:
            await asyncio.sleep(0.05)
        say("ball let go" if not ball.connected else "BALL NOT LET GO",
            f"took {time.monotonic() - letting_go:.1f}s" if not ball.connected else
            f"still connected after {QUIT_GRACE_S:g}s — quitting anyway, and the "
            f"ball drops the link on its own once nothing is talking to it")
    say("stopped", "nothing is watching for signals from here on")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m src.daemon", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--events", default=str(EVENTS), help=f"default: {EVENTS}")
    ap.add_argument("--replay", action="store_true",
                    help="play the file from the top, instead of restoring what "
                         "was pending quietly (task 47)")
    ap.add_argument("--poll", type=float, default=0.25, metavar="S",
                    help="how often to look at the file (default: 0.25)")
    ap.add_argument("--snooze", type=float, default=0.0, metavar="S",
                    help="override config/signals.json's snooze, for a desk run "
                         "that cannot wait five minutes for it (default: 0 = use "
                         "the config)")
    ap.add_argument("--no-ball", action="store_true",
                    help="do not look for a ball at all — the menu bar alone, which "
                         "is how this is developed")
    ap.add_argument("--mute", action="store_true",
                    help="start with the sounds off: the ball buzzes and lights, "
                         "the Mac stays quiet, and the menu switches it back")
    ap.add_argument("--one-cry", action="store_true",
                    help="every done cries 129, the uploaded cry, instead of one of "
                         "the partner's built-in cries — for the old ball, which plays "
                         "those as a tap (task 57)")
    ap.add_argument("--no-menubar", action="store_true",
                    help="put no item in the menu bar — for a desk run that times "
                         "a schedule and must not be endable by a stray click")
    ap.add_argument("--notify-anyway", action="store_true",
                    help="signal even while you are already looking at the session "
                         "that raised it — for a desk run that times a ladder and "
                         "cannot have its clock stop when you watch it")
    ap.add_argument("--ask-access", action="store_true",
                    help="at startup, when Accessibility is not granted, show the "
                         "system's own dialog for it — what wobble.app does on "
                         "every launch (task 50). From a terminal the dialog would "
                         "be for the terminal, which is why it is not the default")
    ap.add_argument("--log-dir", default=None, metavar="DIR",
                    help="where the daily log goes (default: a 'logs' directory "
                         "beside the events file, so a desk run logs into its own "
                         "tree and not into the real record)")
    ap.add_argument("--log-days", type=int, default=log.KEEP_DAYS, metavar="N",
                    help=f"how many days of log files to keep, 0 for all "
                         f"(default: {log.KEEP_DAYS})")
    ap.add_argument("--cry", default=None, metavar="WAV",
                    help=f"the cry a done is signalled with — the resource uploaded "
                         f"to the ball, and the file the Mac plays when there is no "
                         f"ball (default: the partner var/{PARTNER_NAME} names, else "
                         f"{CRY.name}). Given, it fixes the cry for the run. Only a "
                         f"cry fetched into {CRY.parent.relative_to(ROOT)}/ — gitignored "
                         f"and filled at install time")
    args = ap.parse_args(argv)
    # Only a Pokémon's cry goes to the ball (task 70): it is what sounds in
    # your hand, and wobble's name is on it. Your own sounds are the Mac's,
    # in assets/sounds/.
    if args.cry is not None and not Path(args.cry).resolve().is_relative_to(CRY.parent.resolve()):
        ap.error(f"--cry {args.cry} is not in {CRY.parent}: the ball speaks only with a "
                 f"cry fetched there (tools/fetch_cry.py). A sound of your own goes in "
                 f"{OWN_SOUNDS}, for the Mac only")
    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        print("\nstopped.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
