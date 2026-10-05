#!/usr/bin/env python3
"""Check the signal vocabulary and its cadence against known answers.

    venv/bin/python3 tests/tables/check_ladder.py

The beat times are worked out from the interval, never read off the run: drift
of a computed schedule into a plausible-looking one is exactly what a log hides.
Every refusal is exercised too — a config that is wrong has to say which file and
which key, because the alternative is a signal that plays nothing and explains
nothing.

**The control is three mutants**: one whose interval is ignored, one where `done`
repeats forever, and one that honours the interval but never runs out of beats.
All three must break the table, or the table is not testing cadence. The third
was added on 2026-09-22 with `times`: the first two both pass a ladder that
cries for ever, because neither of them is about the count.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.core import ladder as mod                                    # noqa: E402
from src.core.ladder import CRY, Ladder, Voice, load                  # noqa: E402
from src.core.signals import Kind                                     # noqa: E402

DONE, NEEDS = Kind.DONE, Kind.NEEDS
TMP = Path(tempfile.mkdtemp(prefix="wobble-ladder-"))


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


def chain(ladder: Ladder, kind: Kind, start: float, n: int) -> list[float]:
    """The first `n` beats, each asked for from the one before it.

    The count already played is handed over on every call, the way the daemon
    does it: the ladder keeps no memory, so a chain that forgot to count would
    be asking a different question than the run does.
    """
    out: list[float] = []
    last: float | None = None
    for _ in range(n):
        due = ladder.next_beat(kind, last, start, len(out))
        if due is None:
            break
        out.append(round(due, 3))
        last = due
    return out


def written(name: str, config: dict) -> Path:
    path = TMP / name
    path.write_text(json.dumps(config))
    return path


def base() -> dict:
    """A minimal config, shaped like the shipped one (task 35): a held light
    on `done`, real repeats on both kinds, and a `mute_effect` per kind — the
    pulse and its `after_beat_s` are gone, because the light held by the ball
    itself is what says "still waiting" now."""
    return {
        "kinds": {
            "needs": {"effect": 199, "every_s": 1.5, "led": None, "mute_effect": 4},
            "done": {"effect": 129, "every_s": 30.0, "times": 2, "led": 138,
                     "light": 9, "mute_effect": 9},
        },
        "snooze": {"after_s": 300.0},
    }


def refuses(what: str, call, must_name: str, exc=ValueError) -> bool:
    """It must refuse, and the sentence must name the file AND the offending key.

    The first draft of this helper checked a list of tokens and stopped at the
    first hit — which was always ".json", the path, present in every message. It
    printed "refused, and named ..." for all six cases while proving nothing
    about the key. A check whose first candidate always matches is not a check.
    """
    try:
        call()
    except exc as caught:
        said = str(caught)
        if ".json" not in said:
            print(f"    {what:<52} <-- refused without naming the file: {said}")
            return False
        if must_name not in said:
            print(f"    {what:<52} <-- refused without naming {must_name!r}: {said}")
            return False
        print(f"    {what:<52} refused, naming the file and {must_name!r}")
        return True
    print(f"    {what:<52} <-- WENT THROUGH, and must not have")
    return False


def run_all(make, quiet: bool = False) -> bool:
    sheet = Sheet(quiet)
    ladder = make(load())

    if not quiet:
        print("\n  what the shipped config says")
    # 138 is Pikachu's, captured (`src/ball/resource.led_blob`); only `done`
    # reads it — `needs`' colour is fixed by the firmware, so it carries
    # neither a `led` nor a `light` of its own (task 35).
    # `budget_s` is the voice's own gap, carried on it since task 28 so the ball
    # can retry a beat inside its place in the rhythm instead of for fifteen
    # seconds. Typed out here rather than read off the ladder: a number taken
    # from the same loader it is meant to pin would agree for the wrong reason.
    # The row two sections down checks it IS the cadence's number.
    # Task 70: the config says `sounds/needs.wav`, read against the checkout and
    # never against wherever the daemon was started from.
    sheet.row("needs is 199, with no held light of its own", ladder.voice(NEEDS),
              Voice(effect=199, led=None, silent=False,
                    mac_sound=str(mod.ROOT / "sounds" / "needs.wav"), budget_s=1.5,
                    light=None, tint="#FFB000"))
    # `"@cry"` in the config, resolved here. The row is written against `CRY`
    # rather than against a typed-out path, because a path typed here would
    # agree with a path typed in the config for the same wrong reason (task 24).
    sheet.row("done is 129, the stroll cry, with 9 held behind it", ladder.voice(DONE),
              Voice(effect=129, led=138, silent=False, mac_sound=str(CRY),
                    budget_s=30.0, light=9, tint="#FFE14D"))
    sheet.row("done holds a light behind its cry — that IS the pulse now (task 35)",
              ladder.voice(DONE).light, 9)
    sheet.row("needs never holds one — it beats every 1.5s until dismissed, "
              "never dark long enough to need one",
              ladder.voice(NEEDS).light, None)
    sheet.row("the snooze is five minutes", ladder.snooze_s, 300.0)
    # Task 25. Nothing else in this file would notice this going to zero, and a
    # zero here is not a crash — it is the ball crying into the keystroke again,
    # which is the thing that was asked to stop.
    sheet.row("a hand that just typed buys five seconds", ladder.after_prompt_s, 5.0)
    # Task 37. Zero here is not a crash either — it is a buzz for every glance.
    sheet.row("a window you left counts for three seconds more", ladder.look_away_s, 3.0)
    # Task 67. Zero is a 180 and a buzzing 9 for every window passed through.
    sheet.row("a window counts as looked at after a second in front", ladder.glance_s, 1.0)
    # Task 67. Without it, a minute away from the keys is a greet.
    sheet.row("coming back means fifteen minutes away, or asleep",
              ladder.moods[Kind.DONE].greet_away_s, 900.0)
    # Task 44. Zero is a cry into the tab you just closed.
    sheet.row("a session that just closed buys three seconds", ladder.after_end_s, 3.0)
    sheet.row("…and it loads with nothing to warn about", ladder.warnings, [])

    if not quiet:
        print("\n  mute — a different id per kind, because the ball has no volume")
    sheet.row("needs mutes to 4 — 199's colour, no sound", ladder.mutes[NEEDS], 4)
    sheet.row("done mutes to 9 — the held light alone, no cry", ladder.mutes[DONE], 9)
    sheet.row("a muted needs is effect 4, silent, with no Mac sound",
              ladder.voice(NEEDS, muted=True),
              Voice(effect=4, led=None, silent=True, mac_sound=None, budget_s=1.5,
                    light=None, tint="#FFB000"))
    sheet.row("a muted done is effect 9 — same light, same led, no cry, no Mac sound",
              ladder.voice(DONE, muted=True),
              Voice(effect=9, led=138, silent=True, mac_sound=None, budget_s=30.0,
                    light=9, tint="#FFE14D"))

    if not quiet:
        print("\n  how a catch ends (task 56) — once each, never queued")
    sheet.row("caught is 201, green, for 2s, with wobble's own click on the Mac",
              ladder.outcome("caught"),
              Voice(effect=201, mac_sound=str(mod.ROOT / "sounds" / "caught.wav"),
                    tint="#3CC85A", lasts_s=2.0))
    sheet.row("broke out is 206, red, for 2s, with Basso on the Mac",
              ladder.outcome("broke_out"),
              Voice(effect=206, mac_sound="/System/Library/Sounds/Basso.aiff",
                    tint="#E8342A", lasts_s=2.0))
    sheet.row("muted, caught is 193 — the green pulse, silent, no Mac sound",
              ladder.outcome("caught", muted=True),
              Voice(effect=193, silent=True, tint="#3CC85A", lasts_s=2.0))
    sheet.row("muted, broke out is 191 — the red pulse, silent, no Mac sound",
              ladder.outcome("broke_out", muted=True),
              Voice(effect=191, silent=True, tint="#E8342A", lasts_s=2.0))
    sheet.row("silenced is the tick 2 over blue 179, 1s, no sound anywhere (task 68)",
              ladder.outcome("silenced"),
              Voice(effect=2, light=179, silent=True, tint="#2F6BFF", lasts_s=1.0))
    sheet.row("…and muted it is the same, since it never had a sound",
              ladder.outcome("silenced", muted=True), ladder.outcome("silenced"))
    sheet.row("an outcome nobody named plays nothing", ladder.outcome("escaped"), None)

    if not quiet:
        print("\n  cadence — needs beats every 1.5s until something stops it")
    sheet.row("the first beat is due now, not later", ladder.next_beat(NEEDS, None, 10.0), 10.0)
    sheet.row("the next is one interval on", ladder.next_beat(NEEDS, 10.0, 10.0), 11.5)
    sheet.row("four beats from zero", chain(ladder, NEEDS, 0.0, 4), [0.0, 1.5, 3.0, 4.5])
    # The two halves of 1.5 must not drift apart: one decides when the daemon
    # calls the next beat, the other how long the ball may spend on this one.
    sheet.row("and the voice's budget is that same gap",
              ladder.voice(NEEDS).budget_s,
              ladder.next_beat(NEEDS, 10.0, 10.0) - 10.0)
    # The row that says `times: null` is not a large number: a hundred beats in
    # and it is still due. A needs falling silent on its own is criterion 3's
    # whole objection, and nothing else here would notice a cap creeping in.
    sheet.row("a hundred beats in it has not run out",
              ladder.next_beat(NEEDS, 10.0, 10.0, 100), 11.5)

    if not quiet:
        print("\n  cadence — done speaks twice, 30s apart, then leaves it to the light")
    sheet.row("its first beat is due now", ladder.next_beat(DONE, None, 10.0), 10.0)
    sheet.row("the second is half a minute on", ladder.next_beat(DONE, 10.0, 10.0, 1), 40.0)
    sheet.row("there is no third — 9 is still saying it", ladder.next_beat(DONE, 40.0, 40.0, 2),
              None)
    sheet.row("so a chain of four is two long", chain(ladder, DONE, 0.0, 4), [0.0, 30.0])

    return sheet.ok()


class IgnoresInterval(Ladder):
    def next_beat(self, kind, last, now, played=0):
        return now


class DoneRepeatsForever(Ladder):
    def next_beat(self, kind, last, now, played=0):
        return now if last is None else last + 1.5


class IgnoresTimes(Ladder):
    """Right interval, no limit — the cry that never stops apologising.

    The other two mutants both pass a ladder with no count at all, because
    neither of them is about how many. This one keeps the 30 s and drops only
    `times`, so the rows that say "there is no third" have something to catch.
    """

    def next_beat(self, kind, last, now, played=0):
        if last is None:
            return now
        every = self.every[kind]
        return None if every is None else last + every


OTHER_CRY = "/tmp/wobble-some-other-cry.wav"


def cry_rows() -> tuple[tuple[str, bool], ...]:
    """`"@cry"` is the ball's voice, not a path — so `--cry` has to move both.

    Written against `CRY` and `OTHER_CRY` rather than against typed-out paths:
    a path typed here would agree with a path typed in the config for the same
    wrong reason, and neither would notice the two drifting apart.
    """
    swapped = load(cry=OTHER_CRY)
    return (
        ("the shipped config resolves to the shipped cry",
         load().voice(DONE).mac_sound == str(CRY)),
        ("…and --cry moves what the Mac plays with it",
         swapped.voice(DONE).mac_sound == OTHER_CRY),
        ("needs keeps its own sound, and --cry does not reach it",
         swapped.voice(NEEDS).mac_sound == load().voice(NEEDS).mac_sound),
        ("the ball's own effect is untouched by any of it",
         swapped.voice(DONE).effect == 129),
    )


_REAL_MAC_SOUND = mod._mac_sound


def _deaf_to_cry(entry: dict, path: Path, where: str, cry=CRY):
    """`"@cry"` resolved against the shipped cry instead of the given one.

    Everything else it does, it still does — the refusals included. Only the
    token is answered from the wrong place, which is exactly how this would go
    wrong in the repo: not by breaking, by looking right.
    """
    if entry.get("mac_sound") == mod.CRY_TOKEN:
        return str(CRY)
    return _REAL_MAC_SOUND(entry, path, where, cry)


def main() -> int:
    print(__doc__.strip().splitlines()[0])
    ok = run_all(lambda l: l)

    print("\n  warnings — not errors, and not swallowed either")
    loud = base()
    loud["kinds"]["needs"]["every_s"] = 0.3
    motor = any("motor" in w for w in load(written("loud.json", loud)).warnings)

    # `every_s: null` already means "once", and a kind that plays once with no
    # held light has nothing left to say it is still pending after that first
    # beat — the ball only ever shows a light again on its NEXT beat, and a
    # kind with no interval has none coming.
    quiet = base()
    quiet["kinds"]["needs"]["every_s"] = None
    holds_no_light = any("holds no light" in w
                         for w in load(written("quiet.json", quiet)).warnings)

    for label, good in (("an interval under the motor floor is called out", motor),
                        ("a kind that plays once and holds no light is called out",
                         holds_no_light)):
        print(f"    {label:<52} {'ok' if good else '<-- SILENT, and must not be'}")
        ok &= good

    print("\n  refusals, each naming what is wrong and where")
    missing = base()
    del missing["kinds"]["needs"]
    no_every = base()
    del no_every["kinds"]["needs"]["every_s"]
    zero = base()
    zero["kinds"]["needs"]["every_s"] = 0
    huge = base()
    huge["kinds"]["needs"]["effect"] = 70000
    no_snooze = base()
    del no_snooze["snooze"]
    instant = base()
    instant["snooze"]["after_s"] = 0
    # An empty string is the one that would go through unnoticed: `afplay ""`
    # fails into a process nobody waits for, and the symptom is one silent beat.
    blank_sound = base()
    blank_sound["kinds"]["needs"]["mac_sound"] = ""
    # Zero beats is a kind that queues and then never says anything — the
    # silent failure principle 7 is written against, and it would load.
    no_beats = base()
    no_beats["kinds"]["needs"]["times"] = 0
    # `every_s: null` already says "once". A `times: 2` beside it asks for a
    # second beat with no interval to place it at, so it would never be due.
    contradiction = base()
    contradiction["kinds"]["done"]["every_s"] = None
    contradiction["kinds"]["done"]["times"] = 2
    # Task 25. A negative wait is a hold that has already expired dressed up as
    # a number somebody meant, and it would load silently — unlike `snooze`,
    # which is required, this block is optional, so a typo in it has no missing
    # key to trip over.
    back_in_time = base()
    back_in_time["after_prompt"] = {"wait_s": -1.0}
    left_backwards = base()
    left_backwards["look_away"] = {"wait_s": -1.0}
    closed_backwards = base()
    closed_backwards["after_end"] = {"wait_s": -1.0}
    # Task 35 removed the pulse and the cry-gap that guarded it. Left in a
    # config, either one would read as a blink the ball no longer does, and
    # nobody would notice it was being silently ignored rather than played.
    has_pulse = base()
    has_pulse["kinds"]["done"]["pulse"] = {"effect": 213, "every_s": 30.0, "silent": True}
    has_after_beat = base()
    has_after_beat["kinds"]["done"]["after_beat_s"] = 5.0
    # A top-level mute effect would look like it is in charge of every kind at
    # once and would not be — each kind names its own now, because the id that
    # makes no sound is a different one per kind.
    top_mute = base()
    top_mute["mute"] = 213
    # A kind with no quiet id would either keep its sound under mute or fall
    # silent and still, and neither is what a person switching mute on asked for.
    no_mute_effect = base()
    del no_mute_effect["kinds"]["needs"]["mute_effect"]

    ok &= refuses("a config that is not there",
                  lambda: load(TMP / "nope.json"), "nope.json", FileNotFoundError)
    ok &= refuses("a kind with no voice",
                  lambda: load(written("m.json", missing)), "needs")
    ok &= refuses("every_s left out entirely",
                  lambda: load(written("n.json", no_every)), "every_s")
    ok &= refuses("an interval of zero",
                  lambda: load(written("z.json", zero)), "every_s")
    ok &= refuses("an effect outside the u16 space",
                  lambda: load(written("h.json", huge)), "effect")
    ok &= refuses("no snooze at all", lambda: load(written("s.json", no_snooze)), "snooze")
    ok &= refuses("a snooze of zero", lambda: load(written("i.json", instant)), "snooze")
    ok &= refuses("a Mac sound that is an empty path",
                  lambda: load(written("b.json", blank_sound)), "mac_sound")
    ok &= refuses("a kind allowed zero beats",
                  lambda: load(written("t0.json", no_beats)), "needs.times")
    ok &= refuses("two beats with no interval to space them",
                  lambda: load(written("t2.json", contradiction)), "done.times")
    ok &= refuses("a wait after a prompt that runs backwards",
                  lambda: load(written("ap.json", back_in_time)), "after_prompt")
    ok &= refuses("a wait after looking away that runs backwards",
                  lambda: load(written("la.json", left_backwards)), "look_away")
    ok &= refuses("a wait after a session closes that runs backwards",
                  lambda: load(written("ae.json", closed_backwards)), "after_end")
    ok &= refuses("a pulse block left over from before task 35",
                  lambda: load(written("pulse.json", has_pulse)), "done.pulse")
    ok &= refuses("an after_beat_s left over from before task 35",
                  lambda: load(written("afterbeat.json", has_after_beat)), "done.after_beat_s")
    ok &= refuses("a top-level mute where each kind now names its own",
                  lambda: load(written("topmute.json", top_mute)), "mute")
    ok &= refuses("a kind with no mute_effect",
                  lambda: load(written("nomute.json", no_mute_effect)), "mute_effect")
    # The other half, and it is the row that keeps the one above honest: the
    # block is optional, so leaving it out has to mean no wait rather than an
    # error. `base()` has never had it, which is what makes this free to ask.
    # Task 56: a config from before the catch loads, and plays none of it.
    plain = load(written("noout.json", base()))
    no_catch = plain.outcomes == {} and plain.outcome("caught", muted=True) is None
    ok &= no_catch
    print(f"    {'a config with no outcomes plays no catch, not an error':<52} "
          f"{'ok' if no_catch else '<-- WRONG'}")
    no_wait = load(written("apn.json", base())).after_prompt_s == 0.0
    ok &= no_wait
    print(f"    {'a config with no wait at all is no wait, not an error':<52} "
          f"{'ok' if no_wait else '<-- WRONG'}")

    print("\n  times — the count that stops the sound without stopping the light")
    # `agree`'s `done` is given back its pre-task-35 shape — `every_s: null`,
    # played once — for the one thing this section is about: whether `times`
    # beside it is read as agreement or as a contradiction. The shipped `done`
    # never asks this question any more, because it really does repeat.
    agree = base()
    agree["kinds"]["done"]["every_s"] = None
    agree["kinds"]["done"]["times"] = 1
    once = load(written("t1.json", agree))
    rows = ((" times 1 beside every_s null is agreement, not contradiction",
             once.times[DONE] == 1),
            (" …and the one beat it allows is the first", once.next_beat(DONE, None, 0.0) == 0.0),
            (" …with nothing after it", once.next_beat(DONE, 0.0, 0.0, 1) is None),
            (" needs is left uncapped by the shipped config",
             load().times[Kind.NEEDS] is None))
    for label, good in rows:
        print(f"   {label:<53} {'ok' if good else '<-- WRONG'}")
        ok &= good

    print("\n  @cry — the Mac saying the same thing the ball says")
    for label, good in cry_rows():
        print(f"    {label:<52} {'ok' if good else '<-- WRONG'}")
        ok &= good
    # The rows above all pass against a `load()` that resolves `"@cry"` to the
    # shipped path and ignores the one it was handed — which is the config
    # keeping a second copy of the fact, the thing task 24 removed. So the
    # control is that mutant, and it has to break them.
    real = mod._mac_sound
    try:
        mod._mac_sound = _deaf_to_cry
        survived = all(good for _, good in cry_rows())
    finally:
        mod._mac_sound = real
    ok &= not survived
    print(f"    {'the control — @cry deaf to --cry':<52} "
          f"{'<-- SURVIVED, so the rows do not test it' if survived else 'caught'}")

    print("\n  the control — cadence removed three ways, all must break the table")
    for label, cls in (("the interval ignored", IgnoresInterval),
                       ("done repeating forever", DoneRepeatsForever),
                       ("the count of beats ignored", IgnoresTimes)):
        survived = run_all(lambda l, c=cls: _recast(l, c), quiet=True)
        ok &= not survived
        print(f"    {label:<52} "
              f"{'<-- SURVIVED, so the table does not test it' if survived else 'caught'}")

    print("\n" + ("ALL CASES MATCH the known answer" if ok
                  else "SOMETHING DOES NOT MATCH — the rows above, not this line"))
    return 0 if ok else 1


def _recast(ladder: Ladder, cls) -> Ladder:
    """The same vocabulary, in a class with one rule taken out."""
    return cls(voices=ladder.voices, every=ladder.every, times=ladder.times,
               mutes=ladder.mutes, snooze_s=ladder.snooze_s,
               after_prompt_s=ladder.after_prompt_s, look_away_s=ladder.look_away_s,
               glance_s=ladder.glance_s, moods=ladder.moods,
               after_end_s=ladder.after_end_s, outcomes=ladder.outcomes,
               outcome_mutes=ladder.outcome_mutes, warnings=ladder.warnings)


if __name__ == "__main__":
    sys.exit(main())
