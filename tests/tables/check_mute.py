#!/usr/bin/env python3
"""Check mute mode without a ball: what the core takes out, and what it leaves in.

    venv/bin/python3 tests/tables/check_mute.py

This is the half of task 34 that can be settled at a desk with no hardware on
it. The half that cannot is whether the motor still runs while a muted `needs`
buzzes — `tests/tables/probe_mute_candidates.py` answers that one with the ball in
hand, and nothing here claims a buzz.

**Task 35 moved what mute even is.** It used to be one shared id (213, the
catch slot's own) with a silence uploaded in front of it, so a muted `needs`
and a muted `done` came out identical — same effect, same colour, same
silence, told apart by rhythm alone, and that cost is what the old version of
this file recorded. Now each kind names its own quiet id in the config (`4`
for `needs`, `9` for `done`) and nothing is ever uploaded for it: mute is a
substitution the ladder makes, not a resource the mirror has to choose.

Eleven claims. The ones about the core each have a mutant below that must
break the suite; the rest are asked of the real mirror, the real menu bar and
the real daemon, which is a stronger thing than a mutant and is why they do
not have one:

  - a muted voice plays its OWN kind's quiet id — 4 for `needs`, 9 for `done`
    — because the ball has no volume, so silencing an id that plays out of its
    own sound bank means becoming a different id, not a softer version of it
  - …and it is `silent`
  - …and it has no Mac sound, because a mute that leaves the laptop chiming is
    the same notification arriving from the other side of the desk
  - the colour, the held light and the rhythm's own budget all survive: what
    is removed is the noise, not the signal
  - a muted `done`'s effect IS its own held light, so it is sent once and not
    as the held-light-then-cry pair — the ladder's half of that; the mirror's
    half is `check_ball_mirror.py`'s
  - the two kinds no longer share an id muted, so a single beat is not the
    coin toss the shared 213 used to be
  - the ladder itself is untouched by asking, so unmuting is reading the same
    table again rather than rebuilding it
  - the id a muted voice plays comes from the config file, one entry per kind,
    not a constant in the core
  - the ball mirror decides nothing about mute: it plays whatever id the
    ladder handed it, the same call either way, and the cry slot is not part
    of the question any more
  - the Mac plays nothing at all for a muted voice, with or without a ball
  - the daemon wires the switch to both surfaces: the real `run()` builds the
    real menu, the mute line is clicked, and the title changes
"""
from __future__ import annotations

import asyncio
import contextlib
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ["WOBBLE_PLATFORM"] = "null"          # before the seam is imported

from dataclasses import replace                                        # noqa: E402

from src import daemon                                                 # noqa: E402
from src.ball import protocol, resource                                # noqa: E402
from src.core.ladder import Voice, load                                # noqa: E402
from src.core.signals import Kind                                      # noqa: E402
from src.mirrors.ball import CRY, Ball                                 # noqa: E402
from src.mirrors.menubar import Menubar                                 # noqa: E402
from src.platform_seam import null                                     # noqa: E402


class Sheet:
    def __init__(self, quiet: bool = False):
        self.quiet, self.bad = quiet, 0

    def row(self, what: str, got, want) -> None:
        good = got == want
        self.bad += not good
        if not self.quiet:
            print(f"    {what:<54} {'ok' if good else f'<-- WRONG: {got!r}, wanted {want!r}'}")

    def ok(self) -> bool:
        return not self.bad


LADDER = load()


def core_rows(mute, quiet: bool = False) -> bool:
    """What `Ladder.muted` takes out and what it leaves alone.

    `mute` is that method, called as `mute(kind, voice)` — or a mutant of it
    with the same shape, which is why this takes the kind rather than closing
    over `Kind.NEEDS` the way the single-argument version used to let it.
    """
    sheet = Sheet(quiet)
    if not quiet:
        print("\n  the core — the sound comes out, nothing else does")

    needs = LADDER.voices[Kind.NEEDS]
    muted_needs = mute(Kind.NEEDS, needs)

    # 199 is the whole reason mute needs a transformation at all: it plays out
    # of the firmware's own sound bank, so no upload reaches it and the
    # protocol has no volume — leaving the id in place would be a mute that
    # still makes a noise.
    sheet.row("a muted needs stops being 199", muted_needs.effect, LADDER.mutes[Kind.NEEDS])
    sheet.row("…and it is silent", muted_needs.silent, True)
    sheet.row("…and the Mac is not left as the second voice",
              muted_needs.mac_sound, None)
    sheet.row("the colour survives", muted_needs.led, needs.led)
    sheet.row("…and so does the budget the rhythm gave it",
              muted_needs.budget_s, needs.budget_s)
    sheet.row("…and needs still holds no light of its own, muted or not",
              muted_needs.light, needs.light)

    done = LADDER.voices[Kind.DONE]
    muted_done = mute(Kind.DONE, done)
    sheet.row("a muted done keeps its held light and loses its cry",
              (muted_done.mac_sound, muted_done.silent, muted_done.light),
              (None, True, done.light))
    sheet.row("the colour survives on a muted done too", muted_done.led, done.led)
    sheet.row("…and so does its budget", muted_done.budget_s, done.budget_s)
    # The invariant the mirror leans on to send one frame instead of two
    # (`Ball._play`, `check_ball_mirror.py`): a voice whose effect IS its own
    # light never has a held light resent behind it.
    sheet.row("…and a muted done's effect IS its own held light",
              muted_done.effect, muted_done.light)

    # The ambiguity the old shared 213 cost, now gone: each kind names its own
    # quiet id, so a single muted beat is not a coin toss between the two.
    sheet.row("a muted needs and a muted done no longer share an id",
              muted_needs.effect == muted_done.effect, False)
    sheet.row("…the colour already told them apart before rhythm had to",
              muted_needs.led == muted_done.led, False)
    return sheet.ok()


# --- the mutants --------------------------------------------------------------
# Each drops exactly one rule. A suite that still passes against one of them was
# not testing that rule.

def mute_keeps_the_effect(kind: Kind, voice: Voice) -> Voice:
    """Sets `silent` and leaves the id alone — a muted needs still comes out of
    the firmware's own 199, at full volume, repeating every 1.5s until somebody
    comes."""
    return replace(voice, silent=True, mac_sound=None)


def mute_forgets_the_mac(kind: Kind, voice: Voice) -> Voice:
    """Mutes the ball perfectly and leaves the laptop chiming. Invisible with a
    ball connected, because `menubar.beat` refuses while the ball is speaking —
    so it only shows up in the run where the ball went to sleep, which is the
    run where somebody most wanted the quiet."""
    return replace(voice, effect=LADDER.mutes[kind], silent=True)


def mute_flattens_the_rhythm(kind: Kind, voice: Voice) -> Voice:
    """Takes the colour, the held light and the budget out along with the
    sound. The tidy version: if it makes no noise, why carry the rest? What it
    costs is the only things left that tell a muted needs from a muted done
    apart, now that they no longer share an id."""
    return replace(voice, effect=LADDER.mutes[kind], silent=True, mac_sound=None,
                   led=None, budget_s=None, light=None)


def mute_shares_one_id(kind: Kind, voice: Voice) -> Voice:
    """Mutes every kind to the same id, the way 213 used to. A muted needs and
    a muted done become indistinguishable in a single beat again — exactly the
    cost task 35 removed by giving each kind its own quiet id."""
    return replace(voice, effect=LADDER.mutes[Kind.DONE], silent=True, mac_sound=None)


class FakeLink:
    """The minimal half of `check_ball_mirror.py`'s fake: acks everything and
    remembers what it was asked to send, as `(kind, id)` pairs. This file only
    needs to see whether a muted beat is an upload, an LED write or an effect —
    not to fail one on purpose, which is the rest of that file's job."""

    def __init__(self):
        self.wire: list[tuple[str, int]] = []

    async def send(self, data: bytes, label: str = "", **kw):
        opcode, payload = protocol.unframe(data)
        if opcode == protocol.OP_RESOURCE:
            if payload[0] == resource.KIND_LED:
                self.wire.append(("led", int.from_bytes(payload[19:21], "little")))
            else:
                self.wire.append(("upload", payload[1]))
        else:
            self.wire.append(("effect", int.from_bytes(payload, "little")))
        return b"\x01\x02\x00\x03\x00"


def daemon_rows() -> bool:
    """The switch, through the real daemon and out of the seam.

    Everything above this is the core and the mirrors asked directly, and the
    one thing that cannot prove is the wiring: a flag that is read in the right
    places and handed to neither surface passes every row above. So the real
    `run()` is started here with the null seam underneath it, the mute line is
    taken out of the menu the daemon actually built, and it is clicked.

    `asyncio.run` is borrowed rather than the arguments being faked, because the
    parser is built inside `main` and a `Namespace` written here would be a
    second copy of the daemon's own defaults — free to agree with this file
    while disagreeing with the flag a person types.
    """
    print("\n  the daemon — the switch reaches both surfaces")
    sheet = Sheet()
    box = Path(tempfile.mkdtemp(prefix="wobble-mute-"))
    (box / "events").write_text("")

    # The seam records labels only, and the handler is the thing being clicked.
    built: list[list] = []
    original = null.Status.menu

    def keep(self, menu):
        built.append(list(menu))
        return original(self, menu)

    # `daemon.asyncio` IS the asyncio module, so this swap is global for as long
    # as it is in place — hence the saved reference below and the `finally`.
    # Calling `asyncio.run` inside the replacement would call the replacement.
    run_real = asyncio.run

    def bounded(coro):
        """Run the daemon's own coroutine, briefly, and stop it."""
        async def wrapped():
            task = asyncio.ensure_future(coro)
            await asyncio.sleep(1.2)
            clicked[0]()                      # the mute line, from the live menu
            await asyncio.sleep(0.6)
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            return 0
        return run_real(wrapped())

    clicked = [lambda: None]
    seen: list[str] = []

    null.Status.menu = keep
    stdin, sys.stdin = sys.stdin, open(os.devnull)
    asyncio.run = bounded
    # The daemon's banner is well over ten lines and would bury the rows below.
    # Kept rather than dropped: if a row goes wrong, what the daemon said on its
    # way up is the first thing to read.
    spoken: list[str] = []
    said, daemon.say = daemon.say, lambda *a, **kw: spoken.append(" ".join(map(str, a)))
    try:
        def click_the_mute_line():
            # Taken out of the menu the daemon built a moment ago, by position:
            # asking for it by label would agree with any wiring that spelled
            # the word right and connected it to nothing.
            menu = built[-1]
            here = [i for i, (label, _) in enumerate(menu) if label is None]
            label, handler = menu[here[0] + 1]
            seen.append(label)
            handler()
        clicked[0] = click_the_mute_line
        null.CALLS.clear()
        daemon.main(["--no-ball", "--poll", "0.1", "--events", str(box / "events"),
                     "--log-dir", str(box / "logs")])
    finally:
        asyncio.run = run_real
        daemon.say = said
        null.Status.menu = original
        sys.stdin.close()
        sys.stdin = stdin

    titles = [args[0] for name, args in null.CALLS if name == "Status.show"]
    sheet.row("the run starts speaking, and says nothing about mute",
              "muted" in titles[0], False)
    sheet.row("…and the menu offers to switch the sounds off", seen,
              ["Mute the sounds"])
    sheet.row("…and clicking it puts the word in the title",
              "muted" in titles[-1], True)
    sheet.row("…and turns the line round, so the next click undoes it",
              built[-1][built[-1].index((None, None)) + 1][0],
              "Unmute the sounds")
    # It says so out loud as well, because the title only saves you while you
    # are looking at the menu bar and the log is the run nobody was watching.
    sheet.row("…and says which way it went, in the log too",
              "muted" in spoken[-1], True)
    if not sheet.ok():
        print("\n    what the daemon said on its way up:")
        for line in spoken:
            print(f"      {line}")
    shutil.rmtree(box, ignore_errors=True)
    return sheet.ok()


def main() -> int:
    print(__doc__.strip().splitlines()[0])

    ok = core_rows(LADDER.muted)

    print("\n  the ladder is read, never rewritten")
    sheet = Sheet()
    before = LADDER.voices[Kind.NEEDS]
    LADDER.muted(Kind.NEEDS, before)
    LADDER.voice(Kind.NEEDS, muted=True)
    sheet.row("asking for a muted voice does not mute the ladder",
              LADDER.voices[Kind.NEEDS], before)
    sheet.row("…so unmuting is the same table again, not a rebuild",
              LADDER.voice(Kind.NEEDS), before)
    sheet.row("…and the flag is what decides, nothing else",
              (LADDER.voice(Kind.NEEDS, False).effect,
               LADDER.voice(Kind.NEEDS, True).effect),
              (LADDER.voices[Kind.NEEDS].effect, LADDER.mutes[Kind.NEEDS]))
    ok &= sheet.ok()

    print("\n  the config owns the number, not the core")
    cfg = Sheet()
    # A number chosen against hardware lives in the file that holds every other
    # number chosen against hardware — one entry per kind, since each plays a
    # different quiet id.
    cfg.row("needs.mute_effect is loaded from signals.json", LADDER.mutes[Kind.NEEDS], 4)
    cfg.row("done.mute_effect is too, and it is a different id",
            LADDER.mutes[Kind.DONE], 9)
    cfg.row("…and it is what a muted voice comes out as",
            LADDER.voice(Kind.NEEDS, True).effect, LADDER.mutes[Kind.NEEDS])
    # Proved by moving it: a loader that ignored the key would pass the two rows
    # above on the default alone.
    moved = replace(LADDER, mutes={**LADDER.mutes, Kind.NEEDS: 198})
    cfg.row("…and moving it moves the voice", moved.voice(Kind.NEEDS, True).effect, 198)
    ok &= cfg.ok()

    print("\n  the ball mirror — decides nothing about mute; it only renders")
    mirror = Sheet()
    ball = Ball(Path("/nonexistent/cry.wav"), on_press=lambda: None,
                say=lambda what, detail="": None)
    ball.slot = CRY                    # as if a session were already up
    link = FakeLink()
    asyncio.run(ball._play(link, LADDER.voice(Kind.DONE, muted=True)))
    mirror.row("a muted done never uploads — the cry slot is not this call's business",
               any(k == "upload" for k, _ in link.wire), False)
    mirror.row("…it just plays the id the ladder handed it, held light and all",
               [n for k, n in link.wire if k == "effect"], [LADDER.mutes[Kind.DONE]])
    asyncio.run(ball._play(link, LADDER.voice(Kind.NEEDS, muted=True)))
    mirror.row("a muted needs is the exact same call, a different voice",
               [n for k, n in link.wire if k == "effect"][-1], LADDER.mutes[Kind.NEEDS])
    mirror.row("the cry slot the session already holds is untouched either way",
               ball.slot, CRY)
    ok &= mirror.ok()

    print("\n  the Mac — silent on the same voice, ball or no ball")
    mac = Sheet()
    bar = Menubar(on_press=lambda: None, item=False)
    for label, connected in (("with a ball connected", True),
                             ("with no ball at all", False)):
        null.CALLS.clear()
        bar.beat(LADDER.voice(Kind.DONE, True), ball_connected=connected)
        mac.row(f"a muted done makes no sound {label}",
                [n for n, _ in null.CALLS if n == "Sound.play"], [])
    # The control: the same beat unmuted, with no ball, DOES play — otherwise
    # the two rows above would pass on a Menubar that never makes a sound.
    null.CALLS.clear()
    bar.beat(LADDER.voice(Kind.DONE), ball_connected=False)
    mac.row("…and unmuted, with no ball, it still does",
            len([n for n, _ in null.CALLS if n == "Sound.play"]), 1)
    ok &= mac.ok()

    ok &= daemon_rows()

    print("\n  the control — every rule removed in turn, each must break the suite")
    controls = (
        ("a mute that leaves needs playing 199 out of the firmware bank",
         lambda: core_rows(mute_keeps_the_effect, quiet=True)),
        ("a mute that quietens the ball and not the laptop",
         lambda: core_rows(mute_forgets_the_mac, quiet=True)),
        ("a mute that takes the colour, the light and the rhythm with it",
         lambda: core_rows(mute_flattens_the_rhythm, quiet=True)),
        ("a mute that goes back to one shared id for every kind",
         lambda: core_rows(mute_shares_one_id, quiet=True)),
    )
    for label, run in controls:
        survived = run()
        ok &= not survived
        print(f"    {label:<54} "
              f"{'<-- SURVIVED, so the suite does not test it' if survived else 'caught'}")

    print("\n" + ("ALL CASES MATCH the known answer" if ok
                  else "SOMETHING DOES NOT MATCH — the rows above, not this line"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
