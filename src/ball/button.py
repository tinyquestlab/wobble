"""B, as an edge — a press read out of a stream that only reports a level.

Byte 1 of the input packet is a bitmask of what is held *right now*
(PROTOCOL.md §5, decoded by `protocol.decode_input`). At the 33.3 Hz this link runs at, a
button held for a fifth of a second is seven packets all saying "down", so
anything acting on the level acts seven times. A press is the 0->1 transition,
and the release is required before the next one counts.

What this adds over the throwaway watcher it grew from (`var/desk/episode.py`,
built for task 06's desk runs): **an assumed release when the packets stop.**
The desk version deliberately had none — a desk run is seconds long and silence
there means the link died, which is worth seeing rather than papering over. A
daemon carried around for an afternoon is the other case, and it is the one the
spec's edge case is about.

**The failure the spec cites is not the failure this covers, and they are worth
keeping apart.** What was once observed live was a button reading `down`
for 43 s with the stream still flowing, its release edge lost — every press in
that window produced no edge at all. That is the *latched level* flavour and it
needs packets to keep arriving. This file covers the flavour spec.md names —
no packet at all for a short window. Nothing here catches the 43 s one; it would
need a second rule, and that rule has its own forged-edge cost (see `SILENCE_S`).

Nothing in this file talks to a radio: it is fed `(t, raw)` and nothing else, so
it can be driven by `link.input_sink` or by a scripted stream with a known
answer (`var/desk/fake_button.py`).

**A tap is the release, not the press** (task 68). B fired on the 0->1 edge
until then, so a hold could never be told from a tap: by the time a thumb had
been down two seconds, the tap had already let the signal go. Now `on_press`
runs when B comes back up — or when a stall assumes it did — and `on_hold`
runs once, while it is still down, at `HOLD_S`; a hold is never followed by a
tap. The cost is a tap felt a fifth of a second later, and a press whose
release the link never delivers (the ball going away mid-press) is lost
rather than counted.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time

from . import protocol
from .link import BallNotFound, open_ball

log = logging.getLogger(__name__)

# The words are the physical labels for the two bits (PROTOCOL.md §5). Nothing
# depends on them being the right way round — `0x01` is the bit B reports and
# that is measured; whether "top" is the best word for it is only a log line.
NAMES = {protocol.BTN_TOP: "top", protocol.BTN_STICK: "stick"}
ANY = protocol.BTN_TOP | protocol.BTN_STICK

# Which bit is "B": `0x01`.
#
# **Measured at the desk 2026-09-22, and it is not what tasks.md said.** The spec
# work had B as the stick click (`0x02`). The guided check watched BOTH bits, the
# person pressed B and nothing else through all three steps, and every press came
# back on `0x01`. So `0x02` was a wrong assignment on paper, not a hand reaching
# for the wrong button.
#
# It also agrees with the one other thing known about the stick: pressing it puts
# this ball into its own play mode (learnings, the amber glow), which a dismissal
# has no business starting.
#
# `--button any` is what a desk run should use, and it is the default: a check
# that only listens to the bit we already believe in cannot tell us we were
# wrong, which is the whole reason this one could.
B = protocol.BTN_TOP

# How long with no packet before the level in hand is treated as stale.
#
# The stream is uniform: the mode of 2749 gaps is 30 ms and only 51 of them pass
# 45 ms (learnings, task 05). 0.5 s is ~17 packets missing in a row, which
# nothing measured on this link comes near — while a disconnect, a sleeping ball
# or a notify dropout is seconds, not tenths.
#
# **The cost is a forged press, bounded at one per stall.** If the button really
# was held across the gap, the packet that resumes the stream reads `down`
# against a memory of `up`, which is a rising edge no thumb made. Not clearing
# the level would avoid that, but in the latched case it would forge an edge
# every latch window for as long as the latch lasted. Here the level is re-read
# from the very packet that forged the
# edge, so the next packet is honest again: one spurious press per stall, never
# a stream of them. `assumed_releases` counts them so the trade stays visible.
SILENCE_S = 0.5

# How long B stays down before it is a hold and not a tap (task 68): what
# silences a session. 2.0 is a GUESS, approved at the desk on 2026-10-01 with
# a drawing of the ball's queue — long enough that no tap
# reaches it, short enough to be a deliberate act and not a wait. Measured from
# the packet that read the press, at the link's 30 ms, so it is late by at most
# one packet.
HOLD_S = 2.0


def names(bits: int) -> str:
    """`0x03` -> `"top+stick"`. For a log line that reads as something."""
    return "+".join(n for b, n in NAMES.items() if bits & b) or "none"


class Button:
    """Presses on `mask`, from the level stream. Feed it, read the counters.

    Drop it straight into `link.input_sink` — the signature is that hook's
    `(t, raw)`, with `t` monotonic and all in one timebase (the hook passes
    `time.perf_counter()`).

    `on_press(t, bits)` is a tap, run on the release; `on_hold(t, bits)` is a
    hold, run once at `hold` seconds down, and no tap follows it (task 68).
    Both run inside the BLE notification callback, so they have to be cheap
    and must not block: setting an `asyncio.Event` or appending to a list, not
    awaiting anything. That is the same discipline `Link._on_input` already
    states.
    """

    def __init__(self, mask: int = B, *, on_press=None, on_hold=None,
                 silence: float = SILENCE_S, hold: float = HOLD_S):
        if not mask:
            raise ValueError("a Button watching no bits would never fire")
        self.mask = mask
        self.on_press = on_press
        self.on_hold = on_hold
        self.silence = silence
        self.hold = hold
        # Read these. A press count with no packet count beside it cannot tell
        # "nobody pressed" from "the stream was dead", and those are the two
        # answers a desk run has to choose between.
        self.packets = 0
        self.malformed = 0            # notifications that were not the 17-byte shape
        self.presses = 0              # thumbs down, each the start of a tap or a hold
        self.taps = 0                 # presses let go before `hold` (task 68)
        self.holds = 0                # presses still down at `hold` (task 68)
        self.assumed_releases = 0     # stalls long enough to distrust the level
        self.max_gap = 0.0            # the biggest silence seen, in seconds
        # How many packets each completed press stayed down for. The floor is 1,
        # and a press that never lands on a sample cannot be seen at all — see
        # the note in the summary. Measured because a swallowed press is
        # otherwise indistinguishable from a thumb that missed the button.
        self.press_lengths: list[int] = []
        self._down = 0
        self._down_packets = 0
        self._last_t: float | None = None
        # The press in hand: when it read down, which bits, and whether it has
        # already been a hold — so its release is not also a tap.
        self._pressed_at: float | None = None
        self._pressed = 0
        self._held = False

    @property
    def down(self) -> int:
        """The bits currently held, as last seen. A level, not an event."""
        return self._down

    def feed(self, t: float, raw: bytes) -> int:
        """One input notification. Returns the bits that just went 0->1."""
        self.packets += 1
        packet = protocol.decode_input(raw)
        if packet is None:
            # Counted, not decoded around: a packet of another length is a fact
            # about the link, and guessing at its bytes would be a press invented
            # out of noise. It leaves `_last_t` alone on purpose — the silence
            # rule is about how long there has been no readable level, and a
            # notification we cannot read is not one.
            self.malformed += 1
            return 0

        if self._last_t is not None:
            gap = t - self._last_t
            self.max_gap = max(self.max_gap, gap)
            if gap > self.silence and self._down:
                self.assumed_releases += 1
                log.warning("%s read down and then %.2fs arrived with no packet — "
                            "assuming the release happened in the dark",
                            names(self._down), gap)
                self._down = 0
                # Not recorded as a press length: the stall cut it short, so its
                # duration is a fact about the link and not about the thumb.
                self._down_packets = 0
                self._let_go(self._last_t)
        self._last_t = t

        held = packet.buttons & self.mask
        rising = held & ~self._down
        falling = self._down & ~held
        self._down = held
        if falling and self._down_packets:
            self.press_lengths.append(self._down_packets)
            self._down_packets = 0
        if falling and not held:
            self._let_go(t)
        if rising:
            self.presses += 1
            self._down_packets = 1
            if self._pressed_at is None:
                self._pressed_at, self._pressed, self._held = t, rising, False
            log.debug("press: %s", names(rising))
        elif held:
            self._down_packets += 1
        if (held and self._pressed_at is not None and not self._held
                and t - self._pressed_at >= self.hold):
            self._held = True
            self.holds += 1
            log.debug("hold: %s", names(self._pressed))
            if self.on_hold is not None:
                self.on_hold(t, self._pressed)
        return rising

    def _let_go(self, t: float) -> None:
        """Every watched bit is up: the press in hand ends, as a tap unless it was a hold."""
        pressed, held = self._pressed, self._held
        if self._pressed_at is None:
            return
        self._pressed_at, self._pressed, self._held = None, 0, False
        if held:
            return
        self.taps += 1
        log.debug("tap: %s", names(pressed))
        if self.on_press is not None:
            self.on_press(t, pressed)

    __call__ = feed

    def stats(self) -> dict:
        """What the run saw, as numbers somebody can read."""
        return {
            "packets": self.packets,
            "malformed": self.malformed,
            "presses": self.presses,
            "taps": self.taps,
            "holds": self.holds,
            "assumed_releases": self.assumed_releases,
            "max_gap_ms": round(self.max_gap * 1000, 1),
            "shortest_press_packets": min(self.press_lengths, default=None),
        }


# --- the desk check ---------------------------------------------------------
# `python -m src.ball.button` is task 07's proof, and it proves something no run
# has produced yet: **no press has ever been seen.** The episode runs counted
# packets and printed "no button edge was ever seen" every time, which says the
# stream was alive and says nothing at all about whether a thumb reads as an
# edge. Those are two different facts and this is the one still missing.

#
# It walks the three checks out loud, one at a time, because a desk check where
# the person is reading a docstring with a ball in one hand is a desk check that
# gets done once and approximately. The script says what to do, waits for a key,
# opens a window, and compares what arrived with what that step meant — so the
# run produces a verdict rather than a log to interpret afterwards.
#
# **The window opens on a keypress and never on a countdown.** The first version
# counted "3… 2… 1… GO" into each step and it was not followable with a ball in
# hand: the run sets the pace, the person does not, and a step missed by half a
# second reads as a button that does not work. Waiting costs nothing here — the
# ball keeps streaming while we wait, because the key is read on a thread and the
# loop is never blocked.

MASKS = {"b": B, "top": protocol.BTN_TOP, "any": ANY}

# name, what to do, presses it must read as, how long the window stays open
STEPS = (
    ("one tap", "tap the button once and let go", 1, 5.0),
    ("a long hold", "press it and HOLD it down until the window says stop", 1, 6.0),
    ("two taps", "tap it twice, quickly", 2, 6.0),
)


STEP_ATTEMPTS = 3       # a step may be retried; the last attempt is the one recorded


def _read_one_key() -> str:
    """One keystroke, no Enter needed. Blocking — call it off the loop."""
    if not sys.stdin.isatty():
        return sys.stdin.readline()[:1] or " "
    import termios
    import tty
    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)       # cbreak, not raw: Ctrl-C still interrupts
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)


async def wait_for_key(prompt: str) -> str:
    """Block the person, never the loop.

    The read runs on a thread, so the ball's 33 packets a second keep arriving
    while the prompt sits there. Blocking the loop instead would stall the
    stream — and a stall past `SILENCE_S` is exactly what makes this module
    assume a release, so a lazy `input()` here would manufacture the one event
    the file exists to handle.
    """
    print(prompt, end="", flush=True)
    key = await asyncio.to_thread(_read_one_key)
    print(flush=True)
    return key


async def window(seconds: float) -> tuple[float, float]:
    """Hold a window open for `seconds`, ticking once a second. Returns its ends."""
    started = time.perf_counter()
    ends = started + seconds
    while True:
        left = ends - time.perf_counter()
        if left <= 0.05:
            break
        await asyncio.sleep(min(1.0, left))
        left = ends - time.perf_counter()
        if left > 0.5:
            print(f"      …{left:.0f}s", flush=True)
    return started, time.perf_counter()


async def guided(seen: list) -> list[dict]:
    """The three checks, one at a time, each opened by the person."""
    results = []
    for n, (name, what, want, secs) in enumerate(STEPS, 1):
        print(f"\n  step {n}/{len(STEPS)} — {name}")
        print(f"      what to do: {what}")
        print(f"      it has to read as {want} press(es)")
        attempt = 0
        while True:
            attempt += 1
            await wait_for_key("      press SPACE when you are ready — "
                               "the window opens the moment you do… ")
            print("      GO", flush=True)
            opened, closed = await window(secs)
            print("      stop.", flush=True)
            got = [p for p in seen if opened <= p[0] <= closed]
            which = "+".join(sorted({names(bits) for _, bits in got})) or "—"
            ok = len(got) == want
            print(f"      -> {len(got)} press(es) on {which}: "
                  f"{'ok' if ok else f'WRONG, this step means {want}'}")
            if ok or attempt >= STEP_ATTEMPTS:
                break
            key = await wait_for_key("      SPACE to try this step again, "
                                     "q to move on… ")
            if key.lower() == "q":
                break
        results.append({"step": name, "want": want, "got": len(got),
                        "which": which, "ok": ok, "attempts": attempt})
    return results


async def free(button: Button, seconds: float) -> None:
    """Just watch, and say what is arriving. For when a step fails and you want to look."""
    started = time.perf_counter()
    print(f"\n  watching for {seconds:.0f}s — press whatever you like. Ctrl-C ends it.\n")
    while (left := seconds - (time.perf_counter() - started)) > 0:
        await asyncio.sleep(min(5.0, left))
        print(f"      {time.perf_counter() - started:5.1f}s  {button.packets} packets, "
              f"{button.presses} press(es)", flush=True)


async def run(args) -> int:
    t0 = 0.0
    seen: list[tuple[float, int]] = []

    def heard(word: str):
        # A hold counts as the one press it is (task 68): the long-hold step
        # wants exactly one, and a hold is never followed by a tap.
        def record(t: float, bits: int) -> None:
            gap = f"   ({t - seen[-1][0]:.2f}s after the last)" if seen else ""
            seen.append((t, bits))
            print(f"      {t - t0:5.1f}s  {word}  {names(bits)}{gap}", flush=True)
        return record

    button = Button(MASKS[args.button], on_press=heard("TAP "), on_hold=heard("HOLD"),
                    silence=args.silence)
    results: list[dict] = []
    stats: dict = {}
    elapsed = 0.0
    try:
        async with open_ball(args.addr, scan_timeout=args.scan) as link:
            link.input_sink = button
            t0 = time.perf_counter()
            print("\n  connected. The ball buzzes once on connecting — that is the link, "
                  "not you.")
            print("  Ctrl-C to stop — never Ctrl-Z, a suspended process keeps the link "
                  "and the ball then refuses to reconnect.")
            await asyncio.sleep(args.settle)
            try:
                if args.free:
                    await free(button, args.seconds)
                else:
                    results = await guided(seen)
            except (KeyboardInterrupt, asyncio.CancelledError):
                print("\n  stopped by hand", flush=True)
            elapsed = time.perf_counter() - t0
            stats = link.stats()
    except BallNotFound as exc:
        print(exc, file=sys.stderr)
        return 2

    print()
    ok = bool(results) and all(r["ok"] for r in results)
    for r in results:
        tries = f"  ({r['attempts']} attempts)" if r["attempts"] > 1 else ""
        print(f"  {r['step']:<14} wanted {r['want']}, got {r['got']} on {r['which']:<12}"
              f"{'ok' if r['ok'] else '<-- WRONG'}{tries}")
    outside = len(seen) - sum(r["got"] for r in results)
    if results and outside:
        print(f"  {outside} press(es) landed outside a counted window — between steps, "
              f"or in an attempt that was retried. Not a failure, just not evidence")

    rate = button.packets / elapsed if elapsed else 0.0
    print(f"\n  {button.packets} input packets in {elapsed:.1f}s ({rate:.1f} Hz), "
          f"{button.malformed} malformed, biggest gap {button.max_gap * 1000:.0f} ms "
          f"(the silence rule fires past {button.silence * 1000:.0f} ms)")
    print(f"  presses: {button.presses} ({button.taps} taps, {button.holds} holds past "
          f"{button.hold:g}s)  ·  assumed releases: {button.assumed_releases}")
    if button.press_lengths:
        shortest = min(button.press_lengths)
        print(f"  shortest press held for {shortest} packet(s) "
              f"(~{shortest * 30} ms). The floor is 1: a press that begins and "
              f"ends between two samples is invisible, here and on the ball.")
    if stats:
        print(f"  link: {stats['input_packets']} packets seen by the link itself, "
              f"{stats['frames_acked']}/{stats['frames_sent']} frames acked")

    if not seen:
        print("\n  No edge was ever seen. That is not the same fact as 'nothing was")
        print(f"  pressed': {button.packets} packets arriving says the stream was alive,")
        print("  so if a button WAS pressed, this decode does not read it on this ball.")
        return 1
    which = sorted({names(bits) for _, bits in seen})
    print(f"\n  the button(s) that answered: {', '.join(which)}")
    if results:
        print("  " + ("ALL THREE STEPS READ AS THEY SHOULD — B is an edge on this ball"
                      if ok else
                      "SOMETHING DID NOT READ — the rows above say which, and running it "
                      "again is cheap"))
    return 0 if ok or args.free else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m src.ball.button", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--button", choices=sorted(MASKS), default="any",
                    help="which bit counts as a press. The default watches both "
                         "on purpose: which one is 'B' is the thing this run "
                         "settles (default: any)")
    ap.add_argument("--free", action="store_true",
                    help="skip the three steps and just watch, for looking at "
                         "something that did not read right")
    ap.add_argument("--seconds", type=float, default=60.0, metavar="S",
                    help="how long --free watches for (default: 60)")
    ap.add_argument("--settle", type=float, default=3.0, metavar="S",
                    help="quiet time after connecting, before the first step "
                         "(default: 3)")
    ap.add_argument("--silence", type=float, default=SILENCE_S, metavar="S",
                    help=f"gap with no packet after which the level is treated as "
                         f"stale (default: {SILENCE_S})")
    ap.add_argument("--scan", type=float, default=45.0, metavar="S",
                    help="how long to scan for the ball — it sleeps fast and the "
                         "scan needs its top button pressed (default: 45)")
    ap.add_argument("--addr", default=None, help="BLE address, skipping the scan")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="log every press and every assumed release")
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)-7s %(message)s")
    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main())
