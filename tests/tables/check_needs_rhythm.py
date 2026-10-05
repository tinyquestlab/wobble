#!/usr/bin/env python3
"""The `needs` rhythm: a beat's retries fit its gap, and a dropped one is said.

The defect, measured 2026-09-23 on `needs` (every_s 1.5): one 5s ack timeout in
`link.send` blocks the mirror's only worker for longer than three beats, and
`Ball.beat` kept overwriting `self._beat` in silence. The daemon printed seven
`play (beat) effect 199` lines between 15:21:54 and 15:22:00 and the ball made
one sound. `beat late` reported 1.0s of it, because `_beat_at` was reset by
whichever beat had arrived last rather than kept from the one still waiting.

Two halves. The gap is what `Voice.budget_s` now carries from the config, so
the effect frame is retried inside the beat's own place in the rhythm instead
of for fifteen seconds. The count is what `Ball.beat` keeps when a beat it has
not played yet is overwritten.

Run it: venv/bin/python3 tests/tables/check_needs_rhythm.py
"""
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.ball import link as link_mod                              # noqa: E402
from src.core.ladder import Voice, load                            # noqa: E402
from src.core.signals import Kind                                  # noqa: E402
from src.mirrors.ball import Ball                                  # noqa: E402

WIDTH = 58
rows: list[bool] = []
said: list[str] = []


def row(what: str, ok: bool, detail=None) -> None:
    rows.append(ok)
    print(f"    {what:<{WIDTH}} " + ("ok" if ok else f"<-- WRONG: {detail}"))


def fresh() -> Ball:
    said.clear()
    return Ball(Path("nowhere.wav"), on_press=lambda: None,
                say=lambda w, d="": said.append(f"{w}|{d}"))


class Wire:
    """A link whose effect frame takes `blocks` seconds to be answered."""

    def __init__(self, ball: Ball, blocks: float = 0.0, beats: int = 0):
        self.ball, self.blocks, self.beats = ball, blocks, beats
        self.client = None
        self.sent: list[tuple[str, dict]] = []

    async def send(self, data, label="", **kw):
        self.sent.append((label, kw))
        # The daemon does not stop deciding while the wire is busy — that is the
        # whole defect — so the beats it would have called arrive here.
        for _ in range(self.beats):
            self.ball.beat(Voice(effect=199))
        if self.blocks:
            await asyncio.sleep(self.blocks)
        return b"\x01\x02\x00\xc7\x00"


print(__doc__.splitlines()[0])
print()

print("  the gap the core hands over")
ladder = load(Path("config/signals.json"))
needs, done = ladder.voice(Kind.NEEDS), ladder.voice(Kind.DONE)
row("`needs` carries its own 1.5s gap", needs.budget_s == 1.5, needs.budget_s)
row("…and `done` carries its 30s one", done.budget_s == 30.0, done.budget_s)
# Task 35: the held light is the pulse, and nothing is sent between beats any
# more — so there is no pulse gap left to carry, and no `pulse()` left to ask.
row("…and nothing is sent between beats any more — there is no pulse",
    not hasattr(ladder, "pulse"), dir(ladder))

print()
print("  what the wire is actually given")


def effect_frame(voice) -> dict:
    """The kwargs of the effect frame `_play` sends for this voice.

    By label, not by position: `_colour` and the held light both go first and
    are deliberately NOT budgeted. Mute is a different effect id now, not a
    slot swap (task 35), so nothing here needs to touch `ball.slot` first.
    """
    ball = fresh()
    wire = Wire(ball)
    asyncio.run(ball._play(wire, voice, queued_at=None))
    return next(kw for label, kw in wire.sent if label.startswith("effect "))


def worst(kw: dict) -> float:
    return kw["timeout"] * kw["attempts"]


needs_kw, done_kw = effect_frame(needs), effect_frame(done)
row("a `needs` beat's whole send fits inside its own gap",
    worst(needs_kw) <= needs.budget_s + 1e-9, (needs_kw, needs.budget_s))
# The rule the first draft of this broke. It divided the gap by ATTEMPTS, which
# is 0.5s an attempt — under the 0.52-0.61s an established link takes to ack
# (research §8.16), so every healthy frame would have been retried twice and
# then called silent. Fewer attempts, never shorter ones.
row("…as ONE attempt, because 1.5s cannot afford a retry",
    (needs_kw["attempts"], needs_kw["timeout"]) == (1, 1.5), needs_kw)
row("…and no attempt is under the slowest ack ever measured",
    needs_kw["timeout"] >= link_mod.SLOWEST_ACK_S * 0.75, needs_kw)
row("a 30s gap does not LOOSEN the wire's own 5s x 3",
    (done_kw["timeout"], done_kw["attempts"])
    == (link_mod.ACK_TIMEOUT, link_mod.ATTEMPTS), done_kw)

# Every voice the shipped config can play, against both halves of the rule at
# once — the gap is never overrun, and an attempt is never too short to land.
every_voice = [ladder.voice(k) for k in Kind]
kws = [(v, effect_frame(v)) for v in every_voice]
row("no voice in the config overruns its own gap",
    all(worst(kw) <= v.budget_s + 1e-9 for v, kw in kws),
    [(v.effect, kw) for v, kw in kws])
row("…and none of them retries faster than the ball can answer",
    all(kw["timeout"] >= link_mod.SLOWEST_ACK_S * 0.75 for _, kw in kws),
    [(v.effect, kw) for v, kw in kws])

ball = fresh()
wire = Wire(ball)
asyncio.run(ball._play(wire, needs, queued_at=None))
row("a needs beat sends effect 199 only — no led frame, no light",
    [label for label, _ in wire.sent] == ["effect 199"], wire.sent)

# `done` has both: a led frame for its colour and a light frame for the 9 it
# holds behind the cry (task 35). Neither is budgeted — a colour or a light
# with a hole in it costs more than a beat landing late.
ball = fresh()
wire = Wire(ball)
asyncio.run(ball._play(wire, done, queued_at=None))
row("done's led and light frames are not budgeted — only its effect frame is",
    all("timeout" not in kw for label, kw in wire.sent if not label.startswith("effect ")),
    wire.sent)

print()
print("  counting what was overwritten")
ball = fresh()
ball.beat(Voice(effect=199))
first = ball._beat_at
time.sleep(0.05)
ball.beat(Voice(effect=199))
ball.beat(Voice(effect=199))
row("two beats on top of a waiting one count as two missed",
    ball._missed == 2, ball._missed)
row("…and the stamp stays on the FIRST, not the newest",
    ball._beat_at == first, (ball._beat_at, first))
row("…and only the newest voice survives, one beat deep",
    ball._beat is not None and ball._missed == 2, ball._beat)

ball = fresh()
ball.beat(Voice(effect=199))
row("a beat onto an empty slot misses nothing",
    ball._missed == 0, ball._missed)

print()
print("  what the person reading the log is told")
ball = fresh()
ball.beat(Voice(effect=199))
# Exactly what `_session` does before it plays: the slot is emptied, so the
# first beat that arrives during the send lands on an empty one and is the
# beat that gets played next rather than one that was missed.
voice, ball._beat = ball._beat, None
queued, ball._beat_at = ball._beat_at, None
missed, ball._missed = ball._missed, 0
asyncio.run(ball._play(Wire(ball, blocks=0.6, beats=3), voice,
                       queued_at=queued, missed=missed))
late = [s for s in said if s.startswith("beat late")]
row("a beat the worker reached at once says nothing",
    not late, said)
row("…and of three arriving mid-send, two are held as missed",
    ball._missed == 2, ball._missed)

ball = fresh()
ball.beat(Voice(effect=199))
time.sleep(0.05)
ball.beat(Voice(effect=199))
ball.beat(Voice(effect=199))
queued, missed = ball._beat_at, ball._missed
asyncio.run(ball._play(Wire(ball), Voice(effect=199),
                       queued_at=queued, missed=missed))
late = [s for s in said if s.startswith("beat late")]
row("beats dropped are always worth a line, however short the wait",
    len(late) == 1, said)
row("…and it says how many were never felt",
    late and "2 beat(s)" in late[0], late)
row("…and does not claim nothing was dropped",
    late and "nothing was dropped" not in late[0], late)

print()
print("  the control — each rule removed, every one must break the table")
ok = rows[:]
ball = fresh()
ball.beat(Voice(effect=199))
kept = ball._beat_at
time.sleep(0.05)
ball._beat_at = time.monotonic()          # the old `beat`: reset every call
print(f"    {'_beat_at reset by the newest beat':<{WIDTH}} "
      + ("caught" if ball._beat_at != kept else "<-- NOT CAUGHT"))
rows.append(ball._beat_at != kept)

ball = fresh()
asyncio.run(ball._play(Wire(ball), Voice(effect=199),
                       queued_at=time.monotonic(), missed=0))
print(f"    {'a silent drop count says nothing at all':<{WIDTH}} "
      + ("caught" if not [s for s in said if s.startswith('beat late')]
         else "<-- NOT CAUGHT"))
rows.append(not [s for s in said if s.startswith("beat late")])

ball = fresh()
wire = Wire(ball)
asyncio.run(ball._play(wire, Voice(effect=199), queued_at=None))   # budget_s None
spent = next(kw for label, kw in wire.sent if label.startswith("effect "))
caught = (spent.get("timeout"), spent.get("attempts")) == (link_mod.ACK_TIMEOUT,
                                                           link_mod.ATTEMPTS)
# The first draft of the budget, kept as a control because it passed every
# other row in this table: the gap divided by ATTEMPTS. It is the rule that
# retries a frame the ball was going to ack (research §8.16).
draft = needs.budget_s / link_mod.ATTEMPTS
caught = draft < link_mod.SLOWEST_ACK_S * 0.75
print(f"    {'the gap split three ways, under a measured ack':<{WIDTH}} "
      + ("caught" if caught else "<-- NOT CAUGHT"))
rows.append(caught)

print(f"    {'a voice with no gap, back to the 5s that caused this':<{WIDTH}} "
      + ("caught" if caught else "<-- NOT CAUGHT"))
rows.append(caught)

print()
print("ALL CASES MATCH the known answer" if all(rows)
      else "SOMETHING DOES NOT — the rows above, not this line")
sys.exit(0 if all(rows) else 1)
