#!/usr/bin/env python3
"""Check the ball mirror's stroll slots, held light and battery — without a ball.

    venv/bin/python3 tests/tables/check_ball_mirror.py

The link is faked, and only the link: the framing, the cutting, the upload loop
and the mirror itself are the real ones, so what this drives is the code that
will meet the hardware. Every frame the mirror hands the fake is unframed back
into `("upload", n)`, `("led", index)` or `("effect", id)`, which is the wire as
a list you can compare against a known answer.

**What it is actually testing is task 35's design: two resources, written once,
and a held light standing in for the old silent pulse** (`src/mirrors/ball.py`'s
own docstring, and `~/dev/pokeball/research/STROLL-SLOTS.md`). The cry goes up
once, on connect, into the stroll slot (`04 3c 00`) — never the catch slot
(`04 3e 00`, which effect 213 plays and which stays free for catching). A
colour is one frame (`01 fc 01`), sent only when it changed. Neither is ever
re-sent on a beat, so what this file checks is a shape rather than a log line:
which beats touch the slot (none, after connect), which beats put up a light
that then holds itself (9, 199, 4), and which merely find that light already
up (nothing — a second `done` over a lit 9 is the cry alone).

Seven mutants, each dropping one rule of the new design:

  - a partial upload trusted as a good slot
  - no LED resource ever sent
  - a held light claimed as up even though the send that was meant to raise it
    never acked
  - a held light resent on every beat, lit or not
  - the link switched off in the menu bar and left running anyway
  - a battery that cannot be read written down as 0%, and one asked every wake

Five mutants that used to live here modelled the OLD one-slot design — a single
audio resource swapped between a cry and a silence, with `Ball.wants()` deciding
which the slot should hold. Task 35 removed the swap along with the slot: mute
is now its own effect id per kind (`check_mute.py`'s job), and the ball never
uploads more than the cry it started with. `UploadsOnEveryBeat`,
`PulsesWithoutSwapping`, `SkipsTheSwappedPulse`, `CryOverAnything` and
`ColoursAfterTheEffect` are gone rather than patched, because the thing each of
them broke — the slot swap — does not exist any more to break.

The voices come from `config/signals.json` rather than from literals here: a
policy checked against a vocabulary this file made up would pass while the
shipped one did something else.

**The battery and the switch are here rather than in `check_menubar.py`** even
though the menu bar is what shows them. The percentage and the words "ball off"
are facts about a radio, and this is the only file that owns one — the menu bar
renders whatever it is handed and has no way to be wrong about where the number
came from. Splitting them the other way would check the rendering twice and the
reading never.
"""
from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.ball import link as link_mod                                  # noqa: E402
from src.ball import protocol, resource                                # noqa: E402
from src.core.ladder import load as load_ladder                        # noqa: E402
from src.core.signals import Kind                                      # noqa: E402
from src.mirrors.ball import CRY, UNKNOWN, Ball                        # noqa: E402

REAL_CRY = (Path(__file__).resolve().parents[2] / "assets/cries/pikachu.wav")

# The six catch LEDs the old project's sniffer captures caught, copied from its
# `src/ball/replay.py` (`LED_BY_CREATURE`, captures 01-03; docs/PROTOCOL.md §8.4)
# so this leg runs without that checkout. Until task 77 it was imported from
# ~/dev/pokeball, and skipped wherever that was missing.
CAPTURED_LEDS = {name: bytes.fromhex(hexed) for name, hexed in {
    "bellsprout": "030001fd014c4544000000000000000a02010100001e5400",
    "caterpie":   "030001fd014c4544000000000000000a02010100001e8201",
    "kakuna":     "030001fd014c4544000000000000000a02010100001eac01",
    "pidgey":     "030001fd014c4544000000000000000a02010100001e5801",
    "pikachu":    "030001fd014c4544000000000000000a02010100001e8a00",
    "rattata":    "030001fd014c4544000000000000000a02010100001e3504",
}.items()}
ACK = b"\x01\x02\x00\x03\x00"


class FakeClient:
    """The GATT side of the link: one read, and it counts them.

    `answer` is either the bytes the characteristic returns or an exception to
    raise instead. Both are real: the ball answers `2A19` with one byte, and a
    link that is otherwise perfectly healthy can refuse the read outright —
    bleak raises its own family for that, which is why what is raised here is a
    plain exception and not something this file invented a class for.
    """

    def __init__(self, answer: bytes | Exception = b"\x57"):   # 0x57 == 87%
        self.answer = answer
        self.asked: list[str] = []

    async def read_gatt_char(self, uuid):
        self.asked.append(str(uuid))
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


class FakeLink:
    """Acks everything, and remembers what it was asked to send.

    `lose` names a label fragment whose frame goes unacked, which is how the
    partial-upload and the unacked-light cases are reached — states the real
    ball cannot be talked into on demand. `frames` is the raw payload behind
    each `wire` entry, same index — kept so a row can look inside a frame
    rather than only at its shape, which is what the "never the catch slot's
    header" rows below need. `kwargs` is what each `send()` was asked for, for
    the one row that cares how many attempts a call was budgeted.
    """

    def __init__(self, lose: str | None = None):
        self.wire: list[tuple[str, int]] = []
        self.frames: list[bytes] = []
        self.kwargs: list[dict] = []
        self.lose = lose
        self.input_sink = None
        self.held = 0
        self.client = FakeClient()

    def hold(self):
        link = self

        class _Held:
            async def __aenter__(self):
                link.held += 1
                return link

            async def __aexit__(self, *_exc):
                return False

        return _Held()

    async def send(self, data: bytes, label: str = "", **kw):
        opcode, payload = protocol.unframe(data)
        self.frames.append(payload)
        self.kwargs.append(kw)
        if opcode == protocol.OP_RESOURCE:
            # Audio and colour ride the same opcode and are told apart by the
            # kind byte, not by the caller. Recorded separately because an LED
            # frame also carries index 0, so counting `0`s alone would read one
            # colour as a whole audio upload — which is exactly the confusion
            # that let the ball go dark for a day.
            if payload[0] == resource.KIND_LED:
                # `fc_blob`'s last two bytes are the RISING half, tagged with
                # `FC_FADE` (task 35) — reading them back would see 138|0x1000,
                # not 138. The plain index is the FALLING half, at blob[17:19],
                # which sits at payload[19:21] behind the two-byte LED header.
                self.wire.append(("led", int.from_bytes(payload[19:21], "little")))
            else:
                self.wire.append(("upload", payload[1]))   # the index byte
        else:
            self.wire.append(("effect", int.from_bytes(payload, "little")))
        return None if (self.lose and self.lose in label) else ACK


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


def made(cls=Ball, cry=REAL_CRY, said=None):
    return cls(cry, on_press=lambda: None,
               say=lambda what, detail="": (said if said is not None else []).append(what))


def uploads(link: FakeLink) -> int:
    """How many resources went up — an upload is several frames, index 0 opens."""
    return sum(1 for kind, n in link.wire if kind == "upload" and n == 0)


def effects(link: FakeLink) -> list[int]:
    return [n for kind, n in link.wire if kind == "effect"]


def colours(link: FakeLink) -> list[int]:
    return [n for kind, n in link.wire if kind == "led"]


def never_213_or_catch(link: FakeLink) -> tuple[bool, bool]:
    """Whether 213 was ever played on this link, and whether any frame opened
    with the catch LED's own header (`01 fd 01`) — the two ways the catch slot
    could leak onto the wire, checked together because both mean the same
    thing: this project touched the slot task 35 reserved for catching."""
    saw_213 = any(k == "effect" and n == protocol.SLOT_EFFECT for k, n in link.wire)
    saw_catch_led = any(k == "led" and f[2:5] == bytes.fromhex("01fd01")
                        for (k, _), f in zip(link.wire, link.frames))
    return saw_213, saw_catch_led


# --- the table, driven so a mutant can be swapped in --------------------------

def run_all(cls, quiet: bool = False) -> bool:
    sheet = Sheet(quiet)
    say = (lambda _: None) if quiet else print
    ladder = load_ladder()
    done_voice = ladder.voice(Kind.DONE)
    needs_voice = ladder.voice(Kind.NEEDS)
    muted_done = ladder.voice(Kind.DONE, muted=True)
    muted_needs = ladder.voice(Kind.NEEDS, muted=True)

    say("\n  the session opens dark, and only then puts the cry up")
    ball = made(cls)
    link = FakeLink()
    asyncio.run(ball._lights_off(link, "on connect"))
    asyncio.run(ball._put(link))
    lights_off_at = next(i for i, (k, n) in enumerate(link.wire)
                        if k == "effect" and n == protocol.LIGHTS_OFF)
    cry_at = next(i for i, (k, n) in enumerate(link.wire) if k == "upload" and n == 0)
    sheet.row("180 lands before the cry goes up", lights_off_at < cry_at, True)
    opening = link.frames[cry_at]
    sheet.row("…and the cry opens with the stroll prefix",
              opening[2:5], resource.STROLL_CRY_PREFIX)
    sheet.row("…never the catch prefix — that upload is not this project's",
              opening[2:5] == resource.CRY_PREFIX, False)
    saw_213, saw_catch_led = never_213_or_catch(link)
    sheet.row("213 is never played here — that effect plays the catch slot", saw_213, False)
    sheet.row("…and no frame opened with the catch LED's own header", saw_catch_led, False)

    say("\n  a done's first beat: the colour, the held light, then the cry")
    ball = made(cls)
    link = FakeLink()
    asyncio.run(ball._play(link, done_voice))
    sheet.row("colour, then light, then cry — in that order", link.wire,
              [("led", done_voice.led), ("effect", done_voice.light),
               ("effect", done_voice.effect)])
    sheet.row("…and the light is what it now holds", ball.lit, done_voice.light)

    say("\n  a second done beat over the same lit light")
    mark = len(link.wire)
    asyncio.run(ball._play(link, done_voice))
    sheet.row("the colour is not re-sent, and neither is the light — the cry alone",
              link.wire[mark:], [("effect", done_voice.effect)])

    say("\n  a needs beat takes the floor and becomes what IS lit")
    mark = len(link.wire)
    asyncio.run(ball._play(link, needs_voice))
    sheet.row("needs has no held light of its own — one frame, its own effect",
              link.wire[mark:], [("effect", needs_voice.effect)])
    sheet.row("…and the ball now holds ITS light, replacing the done's",
              ball.lit, needs_voice.effect)

    say("\n  a done that gets the floor back sends its held light again")
    mark = len(link.wire)
    asyncio.run(ball._play(link, done_voice))
    sheet.row("a light replaces a light — 9 comes back, then the cry",
              link.wire[mark:], [("effect", done_voice.light), ("effect", done_voice.effect)])

    say("\n  across that whole walk: no upload, no 213, no catch LED")
    sheet.row("no upload ever rides a beat", uploads(link), 0)
    saw_213, saw_catch_led = never_213_or_catch(link)
    sheet.row("213 is never played", saw_213, False)
    sheet.row("…and no frame opened with the catch LED's own header", saw_catch_led, False)

    say("\n  muted: the light and the buzz, never the two-frame pattern")
    ball = made(cls)
    link = FakeLink()
    asyncio.run(ball._play(link, muted_done))
    sheet.row("a muted done's effect goes out once, not the held-light + cry pair",
              effects(link), [muted_done.effect])
    sheet.row("…its colour still fires like any other beat", colours(link), [muted_done.led])
    mark = len(link.wire)
    asyncio.run(ball._play(link, muted_needs))
    sheet.row("a muted needs is one frame, the same shape as an unmuted one",
              link.wire[mark:], [("effect", muted_needs.effect)])

    say("\n  refresh(None) turns everything off; `lit` clears with it")
    ball = made(cls)
    ball.lit, ball.colour = done_voice.light, done_voice.led
    link = FakeLink()
    ball.refresh(None)
    asyncio.run(ball._show(link))
    sheet.row("nothing owed a light sends 180", link.wire, [("effect", protocol.LIGHTS_OFF)])
    sheet.row("…and `lit` clears", ball.lit, None)

    say("\n  refresh(done) while dark after a beat brings its light back alone")
    spoken_back: list[str] = []
    ball = made(cls, said=spoken_back)
    ball.colour = done_voice.led           # already the right colour: no led frame expected
    link = FakeLink()
    ball.refresh(done_voice)
    asyncio.run(ball._show(link))
    sheet.row("just the light, nothing else", link.wire, [("effect", done_voice.light)])
    sheet.row("…and `lit` follows it", ball.lit, done_voice.light)
    sheet.row("…said as 'light back'", "light back" in spoken_back, True)

    say("\n  an unacked light-back never claims to have landed (principle 7)")
    spoken_show: list[str] = []
    ball = made(cls, said=spoken_show)
    ball.colour = done_voice.led
    link = FakeLink(lose="light")
    ball.refresh(done_voice)
    asyncio.run(ball._show(link))
    sheet.row("`lit` is NOT claimed when the light goes unacked", ball.lit, None)
    sheet.row("…and it says NO LIGHT", "NO LIGHT" in spoken_show, True)

    say("\n  an unacked 180 leaves the ball lit, as far as anyone can tell")
    spoken_180: list[str] = []
    ball = made(cls, said=spoken_180)
    ball.lit = done_voice.light
    link = FakeLink(lose="effect 180")
    asyncio.run(ball._lights_off(link, "a reason"))
    sheet.row("`lit` is left exactly as it was", ball.lit, done_voice.light)
    sheet.row("…and it says LIGHT STILL ON", "LIGHT STILL ON" in spoken_180, True)

    say("\n  letting go sends 180 with one attempt, not the usual three")
    ball = made(cls)
    link = FakeLink()
    ball.set_wanted(False)
    asyncio.run(ball._lights_off(link, "before letting go", timeout=1.5, attempts=1))
    sheet.row("180 goes out", effects(link), [protocol.LIGHTS_OFF])
    sheet.row("…budgeted at one attempt, the same as a quit gives it",
              link.kwargs[-1].get("attempts"), 1)

    say("\n  a partial upload is a state, not a shrug (principle 7)")
    ball = made(cls)
    broken = FakeLink(lose="frame 1")
    ok = asyncio.run(ball._put(broken))
    sheet.row("an unacked frame is not a good slot", ok, False)
    sheet.row("…and the slot is UNKNOWN, not 'cry'", ball.slot, UNKNOWN)

    say("\n  the battery — a reading, never a guess")
    read: list[str] = []
    ball = made(cls, said=read)
    link = FakeLink()
    sheet.row("nothing is claimed before anybody asked", ball.battery, None)
    asyncio.run(ball._read_battery(link, announce=True))
    sheet.row("the byte the ball sent is the percentage", ball.battery, 87)
    # The one row here whose answer this file did not choose. `2A19` is the
    # standard battery-level characteristic, not something this device invented,
    # and reading a UUID this repo made up would pass every row above it while
    # the ball answered nothing.
    sheet.row("…read from 2A19, the standard characteristic",
              link.client.asked, [protocol.BATTERY])
    sheet.row("…and said once, when the link comes up", read.count("battery"), 1)
    asyncio.run(ball._read_battery(link))
    sheet.row("a read straight after does not go to the radio",
              len(link.client.asked), 1)

    refused: list[str] = []
    ball = made(cls, said=refused)
    dead = FakeLink()
    dead.client.answer = RuntimeError("characteristic not found")
    asyncio.run(ball._read_battery(dead, announce=True))
    # The failure that matters, because it fails silently: 0 is a real reading
    # and an alarming one, so a refusal standing in as 0 puts a dying ball in
    # the menu bar that no ball ever reported. `None` renders as no percentage
    # at all, which is the truth.
    sheet.row("a refused read is not a 0%", ball.battery, None)
    sheet.row("…and it is said out loud, once", refused, ["no battery reading"])

    say("\n  the link switched off and on — the menu bar's two buttons")
    spoken: list[str] = []
    ball = made(cls, said=spoken)
    sheet.row("a ball wants a link until it is told not to", ball.wanted, True)
    ball.set_wanted(True)
    sheet.row("…so asking for one again is not an event", spoken, [])
    ball.set_wanted(False)
    sheet.row("switching it off says so", spoken, ["ball off"])
    # The half that is easy to leave out, because the flag alone makes the menu
    # bar look right: without this the ball goes on holding the link and ringing
    # for everything, and the only thing that changed is the label.
    sheet.row("…and drops the session it is holding", ball._dropped.is_set(), True)
    ball.set_wanted(False)
    sheet.row("…and a second off is not a second event", spoken, ["ball off"])
    ball.set_wanted(True)
    sheet.row("switching it on asks for the link back",
              spoken, ["ball off", "ball wanted"])
    sheet.row("…and cuts short the retry it is sitting in", ball._asked.is_set(), True)

    say("\n  B on the ball: a tap is the release, a hold is the silence (task 68)")
    heard: list[str] = []
    ball = cls(REAL_CRY, on_press=lambda: heard.append("tap"),
               on_hold=lambda: heard.append("hold"), say=lambda *_: None)
    up, down = bytes([0, 0, 0, 0, 0]) + bytes(12), bytes([0, protocol.BTN_TOP, 0, 0, 0]) + bytes(12)
    feed = ball._button.feed
    feed(0.00, up)
    feed(0.03, down)
    sheet.row("B down is nothing yet — it may become a hold", heard, [])
    feed(0.20, up)
    sheet.row("…and its release is the tap", heard, ["tap"])
    for i in range(80):                       # 2.4 s down, a packet every 30 ms
        feed(0.30 + i * 0.03, down)
    feed(2.73, up)
    sheet.row("held past HOLD_S: one hold, and no tap after it", heard, ["tap", "hold"])
    plain = made(cls)
    for i in range(80):
        plain._button.feed(i * 0.03, down)
    plain._button.feed(2.43, up)
    sheet.row("a ball given no on_hold takes the hold as nothing, not a tap",
              (plain._button.holds, plain._button.taps), (1, 0))

    say("\n  the silence's confirmation: blue held, then the tick (task 68)")
    silenced = ladder.outcome("silenced")
    ball = made(cls)
    link = FakeLink()
    asyncio.run(ball._play(link, silenced))
    sheet.row("179, the blue, then 2, the weak tick", link.wire,
              [("effect", 179), ("effect", 2)])
    sheet.row("…and blue is what the ball now holds, for _show to end", ball.lit, 179)

    return sheet.ok()


# --- the mutants --------------------------------------------------------------
# Five mutants that used to live here are gone outright rather than patched:
# UploadsOnEveryBeat, PulsesWithoutSwapping, SkipsTheSwappedPulse, CryOverAnything
# and ColoursAfterTheEffect all broke the one-slot swap between a cry and a mute
# resource, which task 35 removed along with the slot itself — there is no
# `wants()`, no `MUTE`, and nothing left to swap. What replaces them below
# targets the design that actually shipped: a held light and its own state
# (`Ball.lit`), not a slot.

class TrustsTheUpload(Ball):
    """Records the slot before knowing whether it landed — the hole nobody can
    name, reported as a voice."""

    async def _put(self, link):
        await super()._put(link)
        self.slot = CRY
        return True


class NeverColours(Ball):
    """The bug as it actually shipped: no LED resource is ever sent, so a done
    beats into a ball that never shows its colour and 9 is indistinguishable
    from any other done, from across the room."""

    async def _colour(self, link, index):
        return


class ClaimsTheLightAnyway(Ball):
    """Sets `lit` whether or not the held-light send actually acked. A later
    beat then trusts a light that was never shown and skips the resend that
    would have fixed it — silence standing in as done, from the one place
    principle 7 exists to catch it."""

    async def _show(self, link):
        want = self._showing
        if want is None:
            if self.lit is not None:
                await self._lights_off(link, "nothing is owed a light right now")
            return
        if want.light is None or self.lit == want.light:
            return
        await self._colour(link, want.led)
        await link.send(protocol.effect(want.light), f"light {want.light}")
        self.lit = want.light


class ResendsHeldLightEveryBeat(Ball):
    """Sends the held light on every beat, lit or not. A second `done` over an
    already-lit 9 becomes two frames instead of the cry alone — an extra buzz
    nobody asked to feel twice."""

    async def _play(self, link, voice, *, queued_at=None, missed=0):
        await self._colour(link, voice.led)
        if voice.light is not None and voice.light != voice.effect:
            if await link.send(protocol.effect(voice.light), f"light {voice.light}"):
                self.lit = voice.light
        timeout, attempts = link_mod.ACK_TIMEOUT, link_mod.ATTEMPTS
        if voice.budget_s is not None:
            attempts = max(1, min(attempts,
                                  int(voice.budget_s // link_mod.SLOWEST_ACK_S)))
            timeout = min(timeout, voice.budget_s / attempts)
        reply = await link.send(protocol.effect(voice.effect), f"effect {voice.effect}",
                                timeout=timeout, attempts=attempts)
        if reply is not None and (voice.light is None or voice.light == voice.effect):
            self.lit = voice.effect


class StaysOnWhenSwitchedOff(Ball):
    """Sets the flag and leaves the link alone.

    The menu bar reads "ball off" and the ball goes on ringing for everything,
    because nothing dropped the session it is sitting in. It is the shape of
    failure principle 7 is written against: the state and the sentence about the
    state disagree, and the sentence is the one a person believes.
    """

    def set_wanted(self, on: bool) -> None:
        if on == self.wanted:
            return
        self.wanted = on
        self.say("ball wanted" if on else "ball off", "")


class BatteryFallsBackToZero(Ball):
    """A read that did not happen, written down as 0%.

    Nothing crashes and the menu bar fills in — with a ball on the point of
    dying, which is a number no ball ever said. The right answer to "I could not
    ask" is to show no percentage at all.
    """

    async def _read_battery(self, link, *, announce: bool = False) -> None:
        await super()._read_battery(link, announce=announce)
        if self.battery is None:
            self.battery = 0


class BatteryAskedEveryWake(Ball):
    """The two-minute throttle removed.

    A round trip per wake, on a link that is also carrying uploads, for a number
    that moves once an hour — and the wakes are beats, so this is a GATT read
    landing in front of the thing somebody is waiting to feel.
    """

    async def _read_battery(self, link, *, announce: bool = False) -> None:
        # Negative infinity rather than 0: `time.monotonic()` is seconds since
        # boot, so a 0 here would still be throttled on a Mac that started less
        # than two minutes ago — a mutant that survives on one machine in a
        # hundred is worse than no mutant, because it survives silently.
        self._battery_at = float("-inf")
        await super()._read_battery(link, announce=announce)


def main() -> int:
    print(__doc__.strip().splitlines()[0])
    print("  (the 'never acked' lines on stderr are the partial-upload case being "
          "exercised\n   on purpose — they are the log this check asserts the state "
          "of, not a failure)")
    ok = run_all(Ball)

    print("\n  the LED bytes, against the six the Switch itself sent")
    # The only row here whose known answer was not written by this repo. The old
    # project keeps the six LED resources its three sniffer captures caught; if
    # `led_blob` can rebuild all six from their index alone, the twenty constant
    # bytes and the little-endian field are right, and 138 is Pikachu's because
    # a capture said so and not because anyone chose it.
    sheet3 = Sheet()
    for name, captured in sorted(CAPTURED_LEDS.items()):
        index = int.from_bytes(captured[-2:], "little")
        sheet3.row(f"{name} ({index}) rebuilds byte for byte",
                   resource.led_payload(resource.led_blob(index)), captured)
    sheet3.row("…and pikachu's index is the one in the config",
               int.from_bytes(CAPTURED_LEDS["pikachu"][-2:], "little"),
               load_ladder().voice(Kind.DONE).led)
    ok &= sheet3.ok()

    print("\n  the stroll LED — the one 9 actually reads")
    sheet4 = Sheet()
    sheet4.row("fc_blob(138) is pikachu's own capture, byte for byte",
               resource.fc_blob(138), resource.FC_PIKACHU)
    sample = resource.fc_blob(42)
    sheet4.row("…28 bytes, opening 01 fc 01", (len(sample), sample[:3]),
               (28, bytes.fromhex("01fc01")))
    sheet4.row("…the falling half carries the index, at 17-18",
               sample[17:19], (42).to_bytes(2, "little"))
    sheet4.row("…the rising half carries it with the fade bit, at 26-27",
               sample[26:28], (42 | resource.FC_FADE).to_bytes(2, "little"))
    ok &= sheet4.ok()

    print("\n  a voice that is not on disk is said out loud, not played")
    said: list[str] = []
    missing = Path(tempfile.mkdtemp(prefix="wobble-ball-")) / "nobody.wav"
    ball = Ball(missing, on_press=lambda: None,
                say=lambda what, detail="": said.append(f"{what}: {detail}"))
    link = FakeLink()
    landed = asyncio.run(ball._put(link))
    sheet2 = Sheet()
    sheet2.row("it does not claim to have uploaded", landed, False)
    sheet2.row("nothing went on the wire", link.wire, [])
    sheet2.row("the slot is UNKNOWN", ball.slot, UNKNOWN)
    sheet2.row("…and the sentence names the file",
               any("nobody.wav" in line for line in said), True)
    ok &= sheet2.ok()

    print("\n  the control — every rule removed in turn, each must break the table")
    for label, cls in (("a failed upload trusted as a voice", TrustsTheUpload),
                       ("no LED resource ever sent", NeverColours),
                       ("a held light claimed as up though it never acked",
                        ClaimsTheLightAnyway),
                       ("a held light resent on every beat, lit or not",
                        ResendsHeldLightEveryBeat),
                       ("switched off in the menu, still on the air",
                        StaysOnWhenSwitchedOff),
                       ("a battery that could not be read called 0%",
                        BatteryFallsBackToZero),
                       ("the battery asked on every single wake",
                        BatteryAskedEveryWake)):
        survived = run_all(cls, quiet=True)
        ok &= not survived
        print(f"    {label:<52} "
              f"{'<-- SURVIVED, so the table does not test it' if survived else 'caught'}")

    print("\n" + ("ALL CASES MATCH the known answer" if ok
                  else "SOMETHING DOES NOT MATCH — the rows above, not this line"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
