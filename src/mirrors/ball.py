"""The ball: a signal you can feel, and the button that answers it.

The other mirror of the same core. It renders what it is handed — a `Voice` and
which light should be showing — and decides nothing about which signal is owed
(principle 1).
What it does own is the *device*: one BLE link, the stroll slots behind it, and
the fact that both of those can go away without warning.

**It does not go through `platform_seam`, and that is on purpose.** The seam is
for things only macOS can do; `bleak` runs everywhere, so `src/ball/` is its own
package and this file talks to it directly. `check_menubar.py` enforces the rest
of the rule mechanically — a mirror still may not name AppKit or `bleak` itself.

**Everything it plays lives in the stroll slots** (task 35). The ball keeps
two sets of uploaded resources, addressed by the three bytes in front of each
upload (`docs/PROTOCOL.md` §7.2): the catch set that 213
plays, and the stroll set that 9 and 129 play. wobble writes only the stroll
set, and never plays 213, so catching stays free for catching:

    04 3c 00   the cry     -> 129 plays it, with a strong rumble
    01 fc 01   the colour  -> 9 shows it, and stays on until 180

Each is written once and then only read, so nothing is ever uploaded on a
notification's path. The cry goes up on connect — the one upload a person is
waiting through, and they are waiting through a connection. The colour is one
frame, sent only when it changed.

Until task 35 all of it lived in the catch slot, one slot wanted for two
things — the cry, and a silent flash every 3 s — and every flash was an upload
of silence over the cry, sometimes while the cry was still coming out of it
(filmed at the desk, 2026-09-23). The swap, the wait for a sounding cry, and the
gap in the config that protected it all went with that slot.

**The held light is what says "still waiting".** 9 stays on by itself, so a
`done` is 9 then 129, and later beats send 129 alone while 9 is still held.
A light replaces a light: a `needs` beating 199 takes the ball over, and a
`done` that gets the floor back sends 9 again. What this file tracks is which
light it last put up (`lit`), because the ball cannot be asked.

**The daemon says what should be showing, and this file makes the ball show
it** (`refresh`). Nothing showing is 180, the only id that turns every light
off: an empty queue, a B press with nothing behind it, a snooze, a signal you
are looking at, a quit — and every connect, so a light left on by a crash does
not outlive the next link. A `done` that should be showing and is dark (after
you looked away, after a reconnect) gets its 9 back without a beat.

**Silence is never inferred.** A ball that is not there, a link that dropped, a
frame that went unacked and a slot whose contents nobody can name are four
different facts, and each of them is said in words (principle 7). "Unknown" is
a real state of the cry slot: an upload that stops half way leaves the ball
holding something with a hole in it, and there is no way to read it back.
"""
from __future__ import annotations

import asyncio
import contextlib
import time
from pathlib import Path
from typing import Callable

from ..ball import cry as cry_mod
from ..ball import link as link_mod
from ..ball import protocol, resource
from ..ball.button import Button
from ..core.ladder import Voice

# What the cry slot is holding. `UNKNOWN` is not a placeholder for "we have not
# checked" — there is nothing to check against, so it is what a failed upload
# leaves behind and it has to be carried rather than guessed away.
UNKNOWN, CRY = "unknown", "cry"

# How long to wait before looking again after the link FAILED — bleak raised,
# Bluetooth is off, the connect threw. Not the gap between scans: since task 32
# there is no gap, because one scanner stays up until the ball advertises.
#
# It used to be that gap, and the comment here argued for it: a short retry
# would be "a scan running all afternoon", and 20 s was "fast enough that a
# press is noticed within a minute". Both halves were wrong in the way that
# matters. A press IS noticed within a minute, and a minute of pressing a button
# that does nothing is long enough to conclude the thing is broken — measured at
# the desk at ~55 s. And the scan was already running all afternoon: 139 scans
# found nothing in one day, 25 s each, 58 minutes of radio, for a duty cycle
# that spent 46% of itself deaf. Continuous is 1.9x that, not infinitely more,
# and it measured at 1.42% of one core against 0.75% for the cycle it replaces —
# about 24 s of CPU per hour to never miss a press again.
RETRY_S = 20.0

# How long a beat may sit between the daemon calling it and this file getting
# to it before that is worth a line. The poll is 0.25 s and a wake is immediate,
# so anything past this is the worker having been busy — an upload, or the beat
# before — and not scheduling. Seen 2026-09-23: a beat logged at 14:26:14 that
# the ball did not make until 14:26:16.4, with nothing anywhere saying so,
# because by the time `_play` looked the upload had finished and the slot was
# right again (filmed at the desk).
LATE_BEAT_S = 0.5

# How often the battery is read again while the link is up. It is a one-byte
# GATT read on a link that is otherwise idle, so it is nearly free — but it is
# not free enough to do on every wake, and a percentage that moves once an hour
# does not need asking four times a second.
BATTERY_EVERY_S = 120.0


class Ball:
    """The ball mirror. Hand it beats, read `connected`, run `run()` beside it.

    `on_hold` is B held down (task 68), the silence; `on_press` is a tap, and
    the same callable the menu bar's click gets — a click and a B
    press are one event arriving by different doors, and the daemon must not be
    able to tell them apart (`mirrors/menubar.py` says the same thing from its
    side).

    `say(what, detail)` is how this file speaks. It does not print: the daemon
    owns the terminal, and a mirror that printed would be a second place the
    truth lives.
    """

    def __init__(self, cry_path: Path, *, on_press: Callable[[], None],
                 say: Callable[[str, str], None],
                 on_hold: Callable[[], None] | None = None) -> None:
        self.cry_path = Path(cry_path)
        self.say = say
        self.connected = False
        # Whether a link is WANTED, which is a different fact from whether there
        # is one. Both are this mirror's own — the core has no opinion about
        # radios — and keeping them apart is what lets the menu bar say "you
        # turned it off" instead of "I cannot find it". Those two sentences
        # demand opposite things from the person reading them (principle 7).
        self.wanted = True
        # Percent, or None for "nobody has read it yet". Never a 0 standing in
        # for unknown: 0 is a real and alarming reading.
        self.battery: int | None = None
        self.slot = UNKNOWN
        # Which fc colour index the ball is holding, or `None` for "none has
        # been sent on this link". Separate from `slot` because they are
        # separate resources and one does not disturb the other.
        self.colour: int | None = None
        # The effect whose light the ball is holding, or `None` for dark. Only
        # ever this file's own record — the ball cannot be asked — which is why
        # every connect starts with a 180 that makes `None` true.
        self.lit: int | None = None
        # What is going into the slot at this instant, or None. For as long as
        # it is set the ball holds neither the old resource nor the new one, and
        # `slot` reads UNKNOWN to match — the one moment where the belief above
        # would otherwise contradict the wire.
        self.writing: str | None = None
        # One beat deep, and the newest wins. A queue here would mean a stale
        # beat firing minutes after its moment passed — the ladder already
        # decides when something is due, and a beat that had to wait is a beat
        # whose turn is over.
        self._beat: Voice | None = None
        # When the beat now waiting was handed over — the FIRST one, kept across
        # anything that overwrites it, so the ball can say how long it sat. The
        # daemon prints a beat when it decides one; this is the other end.
        self._beat_at: float | None = None
        # How many beats were overwritten before the worker reached this one.
        # A beat taken off the slot by a newer one is never felt, and until
        # 2026-09-23 that happened in silence: `needs` beats every 1.5s, a
        # single 5s ack timeout in `link.send` blocks the only worker for more
        # than three of them, and the log went on printing a beat a beat while
        # the ball made one sound in ten seconds. Principle 7.
        self._missed = 0
        # The voice whose light should be up right now, or `None` for dark —
        # the daemon's answer, handed over every tick (`refresh`).
        self._showing: Voice | None = None
        self._woken = asyncio.Event()
        self._dropped = asyncio.Event()
        # Set when the link is asked for again, so turning it back on does not
        # sit out the rest of a twenty-second retry sleep. A person who just
        # chose "Connect" is watching the menu bar for it.
        self._asked = asyncio.Event()
        self._battery_at = 0.0
        # A tap on the release and a hold at `button.HOLD_S`, never both for one
        # press (task 68): the hold is what silences a session.
        self._button = Button(on_press=lambda _t, _bits: on_press(),
                              on_hold=None if on_hold is None else
                              lambda _t, _bits: on_hold())

    # --- what the daemon calls, none of which may block ---------------------

    def beat(self, voice: Voice) -> None:
        """This voice is due now. Played on the worker, not here."""
        if self._beat is not None:
            self._missed += 1
        else:
            # Only when the slot was empty. Reset on every call this would
            # measure the beat that has just arrived rather than the one that
            # has been waiting, and so report a fraction of the stall it exists
            # to reveal: 1.0s printed on 2026-09-23 where the worker had been
            # blocked in `link.send` for five.
            self._beat_at = time.monotonic()
        self._beat = voice
        self._woken.set()

    def refresh(self, showing: Voice | None) -> None:
        """Which signal's light should be up now, or `None` for none.

        The core's answer, not this file's: the daemon knows whether a signal
        is pending, looked at, held or snoozed, and all of them come down to
        this one voice or nothing. What this file does with it is the device's
        business — 180 for nothing, the voice's held light back if it went
        dark. Wakes the worker only on a change, so a tick that repeats itself
        costs nothing.
        """
        if showing != self._showing:
            self._showing = showing
            self._woken.set()

    def set_wanted(self, on: bool) -> None:
        """Ask for a link, or give one up. Returns at once either way.

        Turning it off drops the session the same way the ball going away does,
        so there is one path out of a connection rather than two. Turning it on
        only sets the flag and wakes the loop; the scan itself happens where
        every other scan happens.
        """
        if on == self.wanted:
            return
        self.wanted = on
        if on:
            self.say("ball wanted", "looking for it again")
            self._asked.set()
        else:
            self.say("ball off", "disconnected on purpose — the Mac takes the "
                                 "sounds back over until you switch it on again")
            self._dropped.set()

    def quiet(self) -> None:
        """B was pressed.

        The ball has no stop command — nothing in either capture stops a sound
        that has started, and an effect is under a second. What this can do is
        drop a beat that has not gone out yet, so a dismissal is not followed by
        the signal it just dismissed.
        """
        self._beat = self._beat_at = None

    # --- the worker ---------------------------------------------------------

    async def run(self) -> None:
        """Hold the link for as long as there is one, and say when there is not.

        `link.py` connects; it does not reconnect and does not announce coming
        back. That loop is here because "the ball disconnected" and "the ball is
        back" are both things criterion 9 asks to be said where a person can see
        them, and neither can be inferred from a link object.

        **Waiting happens in one place, and it is not here** (task 32). A link
        that dropped cleanly goes straight back to looking, because the looking
        IS the waiting now — `_look_for_ball` holds one scanner up until the
        ball advertises. `RETRY_S` is left for the case it was never really
        about: a link that failed, where going straight round would be a tight
        loop against a radio that is switched off.
        """
        first = True
        while True:
            if not self.wanted:
                # Waiting, not scanning. A retry loop that kept running while
                # the answer was "I turned it off" would be a radio nobody asked
                # for and a menu bar flickering between two truths.
                self._asked.clear()
                await self._asked.wait()
                continue
            failed = False
            try:
                await self._session(first)
            except link_mod.BallNotFound as exc:
                # Not an error. The ball sleeps quickly and does not advertise
                # while asleep, so this is the normal state of an afternoon.
                # Since task 32 the scan does not give up, so this only arrives
                # from a caller that set its own deadline — but it stays, and it
                # backs off, because a scan that raised is not one to reopen at
                # once.
                failed = True
                self.say("no ball", f"{exc} Retrying every {RETRY_S:.0f}s.")
            except asyncio.CancelledError:
                raise
            except Exception as exc:                    # bleak raises its own family
                failed = True
                self.say("BALL LINK FAILED", f"{type(exc).__name__}: {exc} — "
                                             f"retrying in {RETRY_S:.0f}s")
            finally:
                if self.connected:
                    # Only a link that happened makes the next one "back": a scan
                    # that failed at launch has nothing to come back from.
                    first = False
                    self.connected = False
                    self.slot = UNKNOWN
                    self.colour = None
                    self.lit = None
                    # Cleared rather than kept: a percentage from a ball that is
                    # no longer there is the most convincing kind of wrong,
                    # because it looks like a reading.
                    self.battery = None
                    # Said only when the link went away by itself. Switching it
                    # off is already announced by `set_wanted`, and a second
                    # sentence for one decision reads as two events.
                    if self.wanted:
                        self.say("ball disconnected",
                                 "the menu bar shows no ball from here on; the "
                                 "Mac takes the sounds back over")
            if failed:
                # Only after a failure (task 32). A clean drop goes round at
                # once and lands in the scanner, which is where waiting belongs
                # now — sleeping here as well would put the deaf window back, in
                # a smaller place where it is harder to see.
                #
                # Interruptible, so "Connect" does not have to sit out the rest
                # of a retry that was already running when it was chosen.
                self._asked.clear()
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(self._asked.wait(), RETRY_S)

    async def _look_for_ball(self):
        """Keep one scanner up until the ball advertises. `None` if given up on.

        The whole of task 32. Before it this was `open_ball()`'s own 25 s scan
        inside a loop that then slept 20 s, so nobody was listening for 46% of
        every 46 s cycle. The ball advertises for a few seconds after its top
        button is pressed and is asleep again well before the next scan opens —
        so a press landing in the gap was simply lost, and lost in the worst way
        principle 7 describes: nothing on the ball, nothing in the menu bar,
        nothing in the log. At the desk that reads as pressing a button that
        does not work, for about a minute, which is long enough to stop
        believing the button.

        The right answer for a device you want to stay connected to is not a
        better scan at all — it is a standing connection the controller holds
        (`connectPeripheral:` with no timeout, `autoConnect=true` on Android),
        which costs the host nothing because the radio does the waiting. It is
        refused here on purpose: bleak's CoreBluetooth backend never calls
        `retrievePeripheralsWithIdentifiers:`, so reaching it means raw PyObjC,
        and `src/ball/` is outside the seam precisely because bleak is the part
        that runs anywhere. Scanning continuously is the second-best answer and
        it is cheap enough to buy outright — 1.42% of one core, ~24 s of CPU per
        hour more than the cycle it replaces.

        **Said once per search, not once per cycle.** 427 of one day's 4070 log
        lines were this loop announcing that nothing had happened, and a noise
        floor that buries real events is principle 7 failing from the other end.
        """
        self.say("no ball", "one scan stays up from here until the ball answers, "
                            "so its top button works whenever you press it")
        scan = asyncio.ensure_future(link_mod.find_ball(timeout=None))
        given_up = asyncio.ensure_future(self._dropped.wait())
        try:
            await asyncio.wait([scan, given_up],
                               return_when=asyncio.FIRST_COMPLETED)
            # `scan.result()` re-raises, which is what we want: a scan that
            # threw is a link failure and `run` is the one that backs off.
            return scan.result() if scan.done() else None
        finally:
            # Both, and awaited: an un-awaited cancel leaves a `BleakScanner`
            # running with nobody holding it, and the next search would open a
            # second one on top of the first.
            for task in (scan, given_up):
                if not task.done():
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task

    async def _session(self, first: bool) -> None:
        """One connection, from the scan to the drop."""
        self._dropped.clear()
        device = await self._look_for_ball()
        if device is None:
            return              # given up on while we were looking
        async with link_mod.open_ball(
                device, on_disconnect=lambda _c: self._dropped.set()) as link:
            link.input_sink = self._button.feed
            self.connected = True
            self.say("ball connected" if first else "ball back",
                     "B is the ball's own button now, and the click still works")

            # Before the upload, because it is one byte and the upload is
            # seventeen frames: asking first means the menu bar has a number to
            # show during the two seconds the cry is going up.
            await self._read_battery(link, announce=True)

            # Dark first, whatever the last link left. A daemon that died with a
            # `done` showing leaves 9 on for tens of minutes, and this is the
            # first moment anything can end it. If a signal is still pending,
            # `_show` below puts its light back once the cry is in.
            await self._lights_off(link, "on connect, so no light a crash left "
                                         "on outlives the new link")

            # On connect, never on an event (plan.md; `docs/PROTOCOL.md` §7.3).
            # This is the one upload a person is waiting through, and
            # they are waiting through a connection, not a notification.
            await self._put(link)

            while not self._dropped.is_set():
                await self._show(link)
                await self._wait_for_work()
                if self._dropped.is_set():
                    break
                voice, self._beat = self._beat, None
                queued, self._beat_at = self._beat_at, None
                missed, self._missed = self._missed, 0
                if voice is not None:
                    await self._play(link, voice, queued_at=queued, missed=missed)
                    if voice.lasts_s is not None:
                        await self._linger(voice.lasts_s)
                elif self.slot != CRY:
                    # Off the notification path: an idle wake is the only
                    # moment a failed connect upload can be tried again without
                    # a beat waiting behind it.
                    self.say("slot", "the cry is not in the slot, so it goes up "
                                     "again while nothing is waiting on the link")
                    await self._put(link)
                # After the work of the wake, never before it: it is throttled
                # to once every couple of minutes, but a round trip is still a
                # round trip and nothing about a percentage is worth putting in
                # front of a beat somebody is waiting to hear.
                await self._read_battery(link)

            if not self.wanted:
                # Let go on purpose — Disconnect, or the daemon quitting — so
                # the link is still here to end the light with. One short try:
                # a quit waits for this, and a ball that will not ack is one
                # the next connect clears anyway.
                await self._lights_off(link, "before letting go, so the ball is "
                                             "not left lit with nobody driving it",
                                       timeout=1.5, attempts=1)

    async def _read_battery(self, link, *, announce: bool = False) -> None:
        """Read `2A19` and keep the percentage, or leave it as it was.

        A standard GATT characteristic rather than anything this device
        invented: one byte, 0-100, the same one the Switch reads
        (`docs/PROTOCOL.md` §9).

        **Never fatal, and never a guess.** A ball that will not answer this is
        still a ball that rings, so a refusal leaves `battery` at whatever it
        already was and says so once. Substituting a 0 or a 100 would put a
        number in the menu bar that no ball ever said.
        """
        now = time.monotonic()
        if not announce and now - self._battery_at < BATTERY_EVERY_S:
            return
        self._battery_at = now
        try:
            raw = await link.client.read_gatt_char(protocol.BATTERY)
        except Exception as exc:                        # bleak raises its own family
            # Once per link, not once per read: this is on a two-minute timer
            # and a ball that refuses it once will refuse it all afternoon.
            if announce:
                self.say("no battery reading", f"{type(exc).__name__}: {exc} — the "
                                               f"ball rings either way, and the menu "
                                               f"bar will not show a percentage")
            return
        if not raw:
            return
        was, self.battery = self.battery, raw[0]
        if announce or self.battery != was:
            self.say("battery", f"{self.battery}%")

    async def _wait_for_work(self) -> None:
        """Until there is a beat to play, or the link goes away.

        **Cleared after the wait, never before it.** Clearing first drops
        anything that arrived while the previous beat was still on the wire —
        and a beat can easily take seconds, since `link.send` retries three
        times at five seconds apiece. The symptom would be a `done` that the
        daemon logs and the ball never makes, with nothing anywhere saying a
        beat was lost; for the cry restore it is worse, because with an empty
        queue no later beat comes along to wake it.

        A spurious wake is the accepted cost and is harmless: the loop finds no
        beat and a light that is already right, and goes back to waiting.
        """
        waiters = [asyncio.ensure_future(self._woken.wait()),
                   asyncio.ensure_future(self._dropped.wait())]
        try:
            await asyncio.wait(waiters, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for waiter in waiters:
                waiter.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await waiter
        self._woken.clear()

    async def _linger(self, seconds: float) -> None:
        """Let an effect that plays once finish before `_show` can end it (task 56).

        The next thing the loop does is `_show`, and with nothing pending that
        is 180 — which ends every light at once, so 201 would be a flash and
        not a catch. A new beat or the link going cuts it short: the lane rule
        says a later id replaces the earlier one anyway. A `refresh` does not,
        and it is not lost either — `_show` reads what it asked for directly.
        """
        until = time.monotonic() + seconds
        while self._beat is None and not self._dropped.is_set():
            left = until - time.monotonic()
            if left <= 0:
                return
            self._woken.clear()
            waiters = [asyncio.ensure_future(self._woken.wait()),
                       asyncio.ensure_future(self._dropped.wait())]
            try:
                await asyncio.wait(waiters, timeout=left,
                                   return_when=asyncio.FIRST_COMPLETED)
            finally:
                for waiter in waiters:
                    waiter.cancel()

    # --- the lights -----------------------------------------------------------

    async def _show(self, link) -> None:
        """Make the ball show what `refresh` last asked for, if it does not.

        Nothing wanted and something lit is 180. A voice wanted whose held light
        is not up is that light, sent on its own with no beat — a `done` you
        looked away from, or one still pending across a reconnect. A voice with
        no held light (`needs`) is left to its own next beat, which is never
        more than 1.5 s away.
        """
        want = self._showing
        if want is None:
            if self.lit is not None:
                await self._lights_off(link, "nothing is owed a light right now")
            return
        if want.light is None or self.lit == want.light:
            return
        await self._colour(link, want.led)
        if await link.send(protocol.effect(want.light), f"light {want.light}"):
            self.lit = want.light
            self.say("light back", f"effect {want.light} — a signal is still "
                                   f"pending and its light was off")
        else:
            self.say("NO LIGHT", f"effect {want.light} went unacked — the ball "
                                 f"stays dark for a signal that is still pending")

    async def _lights_off(self, link, why: str, *,
                          timeout: float = link_mod.ACK_TIMEOUT,
                          attempts: int = link_mod.ATTEMPTS) -> None:
        """180, which ends every light — nothing else does, not even time."""
        reply = await link.send(protocol.effect(protocol.LIGHTS_OFF),
                                f"effect {protocol.LIGHTS_OFF}",
                                timeout=timeout, attempts=attempts)
        if reply is None:
            # `lit` is left as it was: the light is still on as far as anyone
            # can tell, and the next wake tries again.
            self.say("LIGHT STILL ON", f"effect {protocol.LIGHTS_OFF} went unacked "
                                       f"({why}) — the ball may stay lit until "
                                       f"something else reaches it")
            return
        self.lit = None
        self.say("lights off", f"effect {protocol.LIGHTS_OFF} — {why}")

    async def _play(self, link, voice: Voice, *,
                    queued_at: float | None = None, missed: int = 0) -> None:
        if queued_at is not None:
            waited = time.monotonic() - queued_at
            if waited >= LATE_BEAT_S or missed:
                # Said by whoever waited, not by whoever checked: a beat that sat
                # through the connect upload finds everything already right and
                # would otherwise say nothing — which is how the beat of
                # 14:26:14 came and went with a clean log and a ball that was
                # silent for another two seconds.
                # `queued_at` is the FIRST of the beats that piled up, not this
                # one, so the number is the length of the stall rather than of
                # its last instant.
                lost = (f"{missed} beat(s) behind it were overwritten and never felt"
                        if missed else "nothing was dropped")
                self.say("beat late", f"{waited:.1f}s between the daemon calling the "
                                      f"first of these and the ball getting to it — "
                                      f"the worker was busy, and {lost}")

        await self._colour(link, voice.led)

        # The held light first, and only when it is not already up: 9 buzzes on
        # every send, and a second `done` beat over a lit 9 is the cry alone. A
        # voice whose effect IS its light (a muted `done`) sends it once, below.
        if (voice.light is not None and voice.light != voice.effect
                and self.lit != voice.light):
            if await link.send(protocol.effect(voice.light), f"light {voice.light}"):
                self.lit = voice.light
            else:
                self.say("NO LIGHT", f"effect {voice.light} went unacked — this "
                                     f"beat plays with no light held behind it")

        # The whole send fits inside this beat's own gap. A beat still being
        # retried when the next one is due has stopped being a beat, and the
        # retry then plays it late, which a rhythm reads as a hole followed by
        # a stumble. `budget_s` is the core's number (principle 1); how to
        # spend it on a radio is this file's business.
        #
        # Spent as FEWER attempts, not shorter ones. The first draft of this
        # divided the gap by `ATTEMPTS`, which gave `needs` 0.5s an attempt —
        # under the 0.52-0.61s an established link actually takes to ack
        # (`docs/PROTOCOL.md` §9). That version retries every healthy frame, writes
        # the effect two extra times, and ends on a `BALL SILENT` for a beat
        # the ball played. So a beat that cannot afford a retry does not get
        # one: `needs` is a single write, and the next beat 1.5s later is its
        # own retry. PROTOCOL.md §9 puts that at 85% landing first try.
        #
        # `_put`, `_colour` and the held light keep the full timeout and all
        # three attempts on purpose: a resource with a hole in it cannot be read
        # back or cleared, and a light that did not go up is dark for as long
        # as the signal waits.
        # Below `SLOWEST_ACK_S` the two rules cannot both hold — `MOTOR_FLOOR_S`
        # lets a gap go to 0.6s, and no ack has ever come back that fast. The
        # gap wins: a beat that cannot be acked inside its own place in the
        # rhythm is one the log should call silent, not one the worker waits
        # out. `check_needs_rhythm.py` holds the shipped config to the other
        # side of that line.
        timeout, attempts = link_mod.ACK_TIMEOUT, link_mod.ATTEMPTS
        if voice.budget_s is not None:
            attempts = max(1, min(attempts,
                                  int(voice.budget_s // link_mod.SLOWEST_ACK_S)))
            timeout = min(timeout, voice.budget_s / attempts)
        reply = await link.send(protocol.effect(voice.effect),
                                f"effect {voice.effect}",
                                timeout=timeout, attempts=attempts)
        if reply is None:
            # The attempt count is in the line because it is now a number that
            # varies: a 1.5s beat gets one write and no retry, and "after every
            # retry" would be a lie about a send that never had one.
            self.say("BALL SILENT", f"effect {voice.effect} went unacked after "
                                    f"{attempts} attempt(s) in {timeout * attempts:.1f}s "
                                    f"— that beat was never felt")
        elif voice.light is None or voice.light == voice.effect:
            # A light replaces a light: an effect that is its own light is what
            # the ball holds now. One with a held light behind it set `lit`
            # above, and only if that light actually went up.
            self.lit = voice.effect

    async def _colour(self, link, index: int | None) -> None:
        """Put `index` in the stroll LED (`01 fc 01`), if it is not already there.

        One frame, so this is allowed to precede the light it colours. A voice
        with no `led` leaves the colour alone rather than clearing it: 199 and 4
        bring their own, and only 9 reads this one. The ball keeps it across a
        restart (`docs/PROTOCOL.md` §8.2), so it is sent once per
        link at most.
        """
        if index is None or index == self.colour:
            return
        payload = resource.led_payload(resource.fc_blob(index))
        reply = await link.send(protocol.frame(protocol.OP_RESOURCE, payload),
                                f"led {index}")
        if reply is None:
            # Not fatal, and deliberately not `UNKNOWN`: one frame either landed
            # or it did not, so the ball is still holding whatever it held and
            # `self.colour` still names it. The beat goes out uncoloured.
            self.say("NO COLOUR", f"the LED resource for {index} went unacked — the "
                                  f"light shows whatever colour was there before")
            return
        self.colour = index

    async def _put(self, link) -> bool:
        """Upload the cry into the stroll slot (`04 3c 00`). `True` if it all acked.

        A partial upload leaves the ball holding a resource with a hole in it,
        and there is no way to clear it or read it back — so the slot goes to
        `UNKNOWN` and stays there until something uploads over it. 129 in that
        state plays half a cry, or the previous one, or nothing, and none of
        those says which happened.
        """
        what = CRY
        try:
            blob = resource.normalise_wav(self.cry_path.read_bytes())
            payloads = resource.cut(blob, resource.STROLL_CRY_PREFIX)
        except (OSError, ValueError) as exc:
            self.slot = UNKNOWN
            self.say("NO CRY", f"{self.cry_path}: {exc} — the ball cannot be given a "
                               f"voice, so a done will cry with whatever it last held")
            return False

        started = time.monotonic()
        # The slot genuinely holds neither thing while the frames are on the
        # wire, and UNKNOWN is the word this file already has for that. Set
        # here and not at the top of the method: the branch above fails before
        # anything reaches the ball, so until this line it is still holding
        # whatever it held.
        self.writing, self.slot = what, UNKNOWN
        try:
            lost = await cry_mod.upload(link, payloads, what)
        finally:
            self.writing = None
        took = time.monotonic() - started
        if lost:
            self.slot = UNKNOWN
            self.say("SLOT UNKNOWN", f"{lost} of {len(payloads)} frame(s) of the {what} "
                                     f"never acked. The ball holds something nobody can "
                                     f"name; the next upload is what clears it.")
            return False
        self.slot = what
        # Timed every single time, not sampled. This number is why the cry goes
        # up on connect and nowhere else: PROTOCOL.md §7.3 has it at 1.3-2.6 s
        # on a fresh link, and §9 has the link degrading roughly fourfold past
        # twelve minutes — so an afternoon of these lines is the evidence for
        # whether that holds on this link, on this Mac, with this cry.
        self.say("slot", f"the {what} is in — {len(payloads)} frames, {took:.1f}s")
        return True
