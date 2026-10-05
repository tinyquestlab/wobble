#!/usr/bin/env python3
"""A `done` cries in a mood that answers what you did, and 129 when there is no choice (tasks 57, 64).

    venv/bin/python3 tests/tables/check_cries.py

The shipped config's `done.cries` pools, and `Signaller` picking from them: the
first beat's pool from how the turn went (sad, call, soft, proud, happy), the
second beat's `call`, a `lonely` beat `lonely_after_s` after the first when
nobody came, and a `greet` once you come back to one that has called. Never the
same cry twice running when the pool has another; none at all muted or with
`--one-cry` — which is when 129, the uploaded cry, plays. The light, the LED and
the Mac's sound do not change with it: the Mac has no recording of the built-in
cries, so it keeps pikachu.wav (`docs/POKEBALL-FINDINGS.md` §6).

The reference leg runs first: `--one-cry` is the behaviour from before task 57,
and has to still be exactly that. Each rule then has a mutant — one line of
`src/daemon.py` replaced — that must turn a row wrong.
"""
from __future__ import annotations

import importlib.util
import random
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.core.ladder import CRY, load               # noqa: E402
from src.core.signals import Entry, Kind, Waiting   # noqa: E402

SOURCE = ROOT / "src" / "daemon.py"
LADDER = load()
# The shipped pools, written out here and not read back from the config, so a
# config edit shows up as a row rather than being agreed with (task 64).
POOLS = {"happy": (20, 32, 34, 181, 230), "proud": (32, 34), "sad": (21, 22),
         "call": (33,), "soft": (230,), "greet": (29,), "lonely": (143,)}
EVERY = LADDER.every[Kind.DONE]
LONELY = 300.0


class Sheet:
    def __init__(self, quiet: bool = False) -> None:
        self.bad = 0
        self.quiet = quiet

    def row(self, what: str, got, want) -> None:
        good = got == want
        self.bad += not good
        if not self.quiet:
            print(f"    {what:<66} {'ok' if good else f'<-- WRONG: {got!r}, wanted {want!r}'}")

    def section(self, title: str) -> None:
        if not self.quiet:
            print(f"\n  {title}")


def load_daemon(patch: tuple[str, str] | None = None):
    """`src.daemon` under its own name, with one line replaced, or `None` when
    that line is not there exactly once."""
    text = SOURCE.read_text()
    if patch is not None:
        if text.count(patch[0]) != 1:
            return None
        text = text.replace(*patch)
    spec = importlib.util.spec_from_file_location("src.daemon_under_check", SOURCE)
    module = importlib.util.module_from_spec(spec)
    module.__package__ = "src"
    sys.modules[spec.name] = module
    exec(compile(text, str(SOURCE), "exec"), module.__dict__)
    return module


def entry(session: str, kind: Kind = Kind.DONE, at: float = 0.0, **lead) -> Entry:
    return Entry(project="crying", window_hint="crying",
                 waiting=(Waiting(session=session, kind=kind, project="crying",
                                  window_hint="crying", since=0.0, at=at, **lead),))


def first(signaller, sessions, kind=Kind.DONE, **lead):
    """The first beat's effect of each session in turn, one after another."""
    got = []
    for n, session in enumerate(sessions):
        voice = signaller.due(entry(session, kind, **lead), float(n))
        got.append(None if voice is None else voice.effect)
    return got


def greet(signaller, done, now: float = 1000.0):
    """The greet's voice alone, asked long after any beat unless `now` says otherwise."""
    return signaller.greet(done, now)[0]


def mood_of(make, *, idle_front=False, **lead):
    sig = make()
    voice = sig.due(entry("mood", **lead), 0.0, idle_front=idle_front)
    return sig.mood, voice and voice.effect in POOLS.get(sig.mood, ())


def table(sheet: Sheet, daemon) -> None:
    make = lambda seed=7, ladder=LADDER: daemon.Signaller(ladder, rng=random.Random(seed))  # noqa: E731

    sheet.section("reference leg — --one-cry is the behaviour from before task 57")
    one = make()
    one.one_cry = True
    sheet.row("--one-cry: every done cries 129, the uploaded one",
              set(first(one, [f"s{n}" for n in range(30)])), {129})
    sheet.row("…and a needs is still 199", first(one, ["n1"], Kind.NEEDS), [199])
    one = make()
    one.one_cry = True
    done = entry("one")
    got = [one.due(done, 0.0), one.due(done, EVERY + 0.1)]
    sheet.row("…its two beats are 129 and nothing more, not even lonely",
              ([v and v.effect for v in got], one.due(done, LONELY + 1.0)), ([129, 129], None))
    sheet.row("…and it never greets", greet(one, done), None)

    sheet.section("the shipped vocabulary")
    moods = LADDER.moods.get(Kind.DONE)
    sheet.row("done's pools are the seven of task 64", moods and moods.pools, POOLS)
    sheet.row("…a long turn is 600s, lonely 300s after, a greet lasts 2s",
              moods and (moods.long_turn_s, moods.lonely_after_s, moods.greet_lasts_s),
              (600.0, LONELY, 2.0))
    sheet.row("…and stays quiet within 10s of a beat (task 67)",
              moods and moods.greet_quiet_s, 10.0)
    sheet.row("needs has none: it is the ball's wobble, not a voice",
              LADDER.moods.get(Kind.NEEDS), None)
    sheet.row("idle counts after 60s", LADDER.idle_s, 60.0)

    sheet.section("the first beat's mood answers how the turn went")
    sheet.row("a plain done is happy", mood_of(make), ("happy", True))
    sheet.row("a turn an API error ended is sad", mood_of(make, failed=True), ("sad", True))
    sheet.row("one back from a snooze or a let-go calls", mood_of(make, returned=True),
              ("call", True))
    sheet.row("its window in front, nobody at the keys: soft", mood_of(make, idle_front=True),
              ("soft", True))
    sheet.row("a turn of 600s is proud", mood_of(make, turn_s=600.0), ("proud", True))
    sheet.row("…599s is not", mood_of(make, turn_s=599.0), ("happy", True))
    sheet.row("…and a turn nobody timed is not", mood_of(make, turn_s=None), ("happy", True))
    sheet.row("sad wins over call", mood_of(make, failed=True, returned=True), ("sad", True))
    sheet.row("call wins over soft", mood_of(make, returned=True, idle_front=True),
              ("call", True))
    sheet.row("soft wins over proud", mood_of(make, idle_front=True, turn_s=900.0),
              ("soft", True))
    no_soft = replace(LADDER, moods={Kind.DONE: replace(
        moods, pools={k: v for k, v in moods.pools.items() if k != "soft"})})
    try:
        got = mood_of(lambda: make(ladder=no_soft), idle_front=True)
    except Exception as error:  # noqa: BLE001 — a mutant crashing is a wrong row
        got = f"raised {type(error).__name__}"
    sheet.row("a pool the config leaves out falls back to happy", got, ("happy", True))

    sig = make()
    done = entry("aaaa")
    one_ = sig.due(done, 0.0)
    two = sig.due(done, EVERY + 0.1)
    sheet.row("its second beat calls, 33", (sig.mood, two and two.effect), ("call", 33))
    sheet.row("…with the light, the LED and the Mac's sound untouched",
              [(v.light, v.led, v.mac_sound) for v in (one_, two)],
              [(9, 138, str(CRY))] * 2)
    sheet.row("its held light names the cry of its last beat",
              sig.showing(done).effect, two.effect)

    sheet.section("lonely: once, lonely_after_s after the first beat, when nobody came")
    sig = make()
    done = entry("lone")
    sig.due(done, 0.0)
    sig.due(done, EVERY + 0.1)
    sheet.row("nothing just before", sig.due(done, LONELY - 0.1), None)
    got = sig.due(done, LONELY)
    sheet.row("…then 143, on the done's light 9",
              (sig.mood, got and got.effect, got and got.light), ("lonely", 143, 9))
    sheet.row("…and never again", [sig.due(done, LONELY + t) for t in (EVERY, LONELY, 3600.0)],
              [None] * 3)
    sig = make()
    done = entry("back", returned=True)
    sig.due(done, 0.0)
    sig.due(done, EVERY + 0.1)
    sheet.row("one that came back has been ignored once already: no lonely",
              sig.due(done, LONELY + 1.0), None)
    sig = make()
    done = entry("seen")
    sig.due(done, 0.0)
    sig.due(done, EVERY + 0.1)
    sig.due(done, 100.0, watched=True)
    sig.due(done, 200.0)                           # 100 s looked at, handed back
    sheet.row("time spent looking at it is handed back to lonely too",
              (sig.due(done, LONELY + 50.0), (sig.due(done, LONELY + 100.0) or None) and sig.mood),
              (None, "lonely"))

    sheet.section("the pick")
    sig = make()
    run = first(sig, [f"s{n}" for n in range(400)])
    sheet.row("400 dones: every first beat cried one of happy's", set(run) <= set(POOLS["happy"]),
              True)
    sheet.row("…never the same cry twice running",
              sum(a == b for a, b in zip(run, run[1:])), 0)
    sheet.row("…and all five were heard", len(set(run)), 5)
    sig = make()
    sheet.row("a pool of one repeats rather than going silent",
              first(sig, ["r1", "r2"], returned=True), [33, 33])
    sig = make(3)
    got = first(sig, ["d1", "n1", "d2"], Kind.DONE)
    sheet.row("a done after a done, with something between, still differs",
              got[0] != got[2], True)
    a = first(make(11), [f"s{n}" for n in range(20)])
    b = first(make(11), [f"s{n}" for n in range(20)])
    c = first(make(12), [f"s{n}" for n in range(20)])
    sheet.row("the pick comes from the rng it is given", (a == b, a != c), (True, True))

    sheet.section("muted")
    sig = make()
    sig.muted = True
    sheet.row("every first beat is done's own mute, 9",
              set(first(sig, [f"m{n}" for n in range(5)]) + first(sig, ["mf"], failed=True)),
              {9})
    sig = make()
    sig.muted = True
    done = entry("mute")
    got = [sig.due(done, 0.0), sig.due(done, EVERY + 0.1), sig.due(done, LONELY)]
    sheet.row("…and so are its call and its lonely", [v and v.effect for v in got], [9, 9, 9])
    sheet.row("…a greet is spent and plays nothing", greet(sig, done), None)
    sig.muted = False
    sheet.row("…not saved for after the mute", greet(sig, done), None)

    sheet.section("the greet: once, for a done that has called")
    sig = make()
    done = entry("hi")
    sig.due(done, 0.0)
    sheet.row("not after one beat: it has not called yet", greet(sig, done), None)
    sig.due(done, EVERY + 0.1)
    sheet.row("another signal's greet is not this one's", greet(sig, entry("other")), None)
    before = (sig.beats, sig.last_beat)
    got = greet(sig, done)
    sheet.row("after two: 29, on the done's light, lasting 2s, no budget",
              got and (got.effect, got.light, got.lasts_s, got.budget_s), (29, 9, 2.0, None))
    sheet.row("…a one-shot: it is not counted and moves no clock",
              (sig.beats, sig.last_beat), before)
    sheet.row("…and only once", greet(sig, done), None)
    sig.due(entry("next"), 400.0)
    sig.due(entry("next"), 400.0 + EVERY + 0.1)
    sheet.row("the next signal greets again", (greet(sig, entry("next")) or None) and 29, 29)
    sig = make()
    done = entry("ret", returned=True)
    sheet.row("one that came back: not before it cried", greet(sig, done), None)
    sig.due(done, 0.0)
    sheet.row("…and after one beat, yes", (greet(sig, done) or None) and 29, 29)
    sheet.row("nothing pending, nothing to greet", greet(make(), None), None)

    sheet.section("the greet: once per done, whatever brings it back (task 67)")
    sig = make()
    done = entry("snz")
    sig.due(done, 0.0)
    sig.due(done, EVERY + 0.1)
    sheet.row("reference: greeted after its call", (greet(sig, done) or None) and 29, 29)
    sig.due(None, 1100.0)                            # snoozed: nothing has the floor
    back = entry("snz", returned=True)
    sig.due(back, 1400.0)
    sheet.row("the same done back from its snooze, called again: no second greet",
              sig.greet(back, 2000.0), (None, None))
    sig.due(entry("other"), 2100.0)                  # another took the floor between
    sig.due(back, 2200.0)
    sheet.row("…nor after another signal had the floor", greet(sig, back, 3000.0), None)
    fresh = entry("snz", at=3100.0)
    sig.due(fresh, 3100.0)
    sig.due(fresh, 3100.0 + EVERY + 0.1)
    sheet.row("a new done in that session greets again",
              (greet(sig, fresh, 4000.0) or None) and 29, 29)

    sheet.section("the greet: never on top of something that just played (task 67)")
    sig = make()
    done = entry("q")
    sig.due(done, 0.0)
    called = EVERY + 0.1
    sig.due(done, called)
    sheet.row("8s after its call: spent in silence, saying what played and when",
              sig.greet(done, called + 8.0),
              (None, "effect 33 played 8s ago, and a greet over it is one effect too "
                     "many (greet_quiet_s 10)"))
    sheet.row("…and not kept for later", greet(sig, done, called + 100.0), None)
    sig = make()
    sig.due(done, 0.0)
    sig.due(done, called)
    sheet.row("10s after it, the greet plays", (greet(sig, done, called + 10.0) or None) and 29, 29)
    plain = replace(LADDER, moods={Kind.DONE: replace(LADDER.moods[Kind.DONE], greet_quiet_s=None)})
    sig = make(ladder=plain)
    sig.due(done, 0.0)
    sig.due(done, called)
    sheet.row("with no greet_quiet_s, the behaviour before it: at once",
              (greet(sig, done, called) or None) and 29, 29)


MUTANTS = [
    ("never varied", ("        self.cry = self._pick(entry.kind, self.mood)",
                      "        self.cry = None")),
    ("the same cry allowed twice running", ("if cry != self.last_cry", "if True")),
    ("--one-cry ignored", ("if moods is None or self.one_cry:", "if moods is None:")),
    ("muted still cries", ("if self.cry is None or self.muted:", "if self.cry is None:")),
    ("the held light not the cry", ("        return self._voiced(entry.kind)\n\n    def _pick",
                                    "        return self.ladder.voice(entry.kind, self.muted)\n\n"
                                    "    def _pick")),
    ("its own rng, not the one given", ("self.rng = rng if rng is not None else random.Random()",
                                        "self.rng = random.Random()")),
    ("a failed turn not sad", ('"sad" if entry.failed else ', "")),
    ("a returned one not calling", ('else "call" if entry.returned else', "else")),
    ("idle in front not soft", ('"soft" if idle_front else ', "")),
    ("proud only past long_turn_s", ("entry.turn_s >= moods.long_turn_s",
                                     "entry.turn_s > moods.long_turn_s")),
    ("call over sad", ('name = ("sad" if entry.failed else "call" if entry.returned else',
                       'name = ("call" if entry.returned else "sad" if entry.failed else')),
    ("the second beat happy, not calling", ('            name = "call"\n        return name',
                                            '            name = "happy"\n        return name')),
    ("a missing pool not falling back", ('return name if name in moods.pools else "happy"',
                                         "return name")),
    ("never lonely", ("            beat = self._lonely(entry)", "            beat = None")),
    ("lonely for one that came back too", ("or entry.returned or self.first_beat is None",
                                           "or self.first_beat is None")),
    ("lonely timed from the last beat", ("return self.first_beat + moods.lonely_after_s",
                                         "return self.last_beat + moods.lonely_after_s")),
    ("lonely not handed back the looked-at time", ("self.first_beat += spent", "pass")),
    ("lonely again and again", ("or times is None or self.beats != times):",
                                "or times is None or self.beats < times):")),
    ("greet before it called", ("if not (self.beats >= 2 or", "if not (self.beats >= 1 or")),
    ("greet every time", ("        self.greeted[entry.session] = (entry.kind.value, entry.at)\n"
                          "        if self.muted:",
                          "        if self.muted:")),
    ("greet plays muted", ('        if self.muted:\n            return None, None\n'
                           '        if (moods.greet_quiet_s',
                           '        if (moods.greet_quiet_s')),
    ("greet saved through the mute", ("        self.greeted[entry.session] = (entry.kind.value, entry.at)\n"
                                      "        if self.muted:\n            return None, None\n",
                                      "        if self.muted:\n            return None, None\n"
                                      "        self.greeted[entry.session] = (entry.kind.value, entry.at)\n")),
    ("greet over a fresh sound", ("and now - self.sounded[0] < moods.greet_quiet_s):", "and False):")),
    ("greet_quiet_s itself still quiet", ("and now - self.sounded[0] < moods.greet_quiet_s):",
                                          "and now - self.sounded[0] <= moods.greet_quiet_s):")),
    ("a silent greet kept for later", ("            at, effect = self.sounded\n",
                                       "            del self.greeted[entry.session]\n"
                                       "            at, effect = self.sounded\n")),
    ("a beat not remembered", ("        self.sounded = (now, voice.effect)\n", "")),
    ("greet with --one-cry", ("\n                or self.one_cry):\n            return None, None", "):\n            return None, None")),
    ("greet counted as a beat", ('        cry = self._pick(entry.kind, "greet")',
                                 '        self.beats += 1\n'
                                 '        cry = self._pick(entry.kind, "greet")')),
    ("greet not a one-shot", ("lasts_s=moods.greet_lasts_s)", "lasts_s=None)")),
    ("greeted kept into the next done", ("== (entry.kind.value, entry.at)\n                or self.one_cry",
                                         "is not None\n                or self.one_cry")),
    ("greeted again back from a snooze", ("            self.beats = 0\n            return None\n",
                                          "            self.beats = 0\n            self.greeted.clear()\n"
                                          "            return None\n")),
    ("greeted again after another had the floor", ("            self.beats = 0\n            self.cry = self.mood = None",
                                                   "            self.beats = 0\n            self.greeted.clear()\n"
                                                   "            self.cry = self.mood = None")),
    ("greet for any signal", ("if (entry is None or self.key != (entry.session, entry.kind.value)\n"
                              "                or self.greeted",
                              "if (entry is None\n                or self.greeted")),
]


def main() -> int:
    print(__doc__.strip().splitlines()[0])
    sheet = Sheet()
    table(sheet, load_daemon())
    print("\n  mutants — each must turn at least one row wrong")
    for name, patch in MUTANTS:
        mod = load_daemon(patch)
        if mod is None:
            sheet.row(f"mutant: {name}", "NOT APPLIED", "caught")
            continue
        quiet = Sheet(quiet=True)
        try:
            table(quiet, mod)
        except Exception:  # noqa: BLE001 — a mutant that crashes the table is caught
            quiet.bad += 1
        sheet.row(f"mutant: {name}", "caught" if quiet.bad else "survived", "caught")
    print("\n  " + ("ALL CASES MATCH the known answer" if not sheet.bad
                   else f"{sheet.bad} WRONG — the rows above"))
    return 1 if sheet.bad else 0


if __name__ == "__main__":
    sys.exit(main())
