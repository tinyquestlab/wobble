"""How often a signal speaks, and what it says when it does.

The vocabulary is a config file and not code (`plan.md`): the effect ids are
chosen by ear at the desk and change as more of the ball's sound bank gets
identified, and that must never be a code edit. This file reads
`config/signals.json` and answers two questions, both pure:

  - **what** should be played for a kind — `voice()`
  - **when** the next beat of it falls — `next_beat()`

No clock here either; `now` arrives as an argument. A mirror plays what it is
handed and decides nothing (principle 1).

**The held light is the pulse** (task 35). A `done` puts up effect 9, the
stroll light, and 9 stays on by itself — tens of minutes in the desk
logs — until something sends 180. So "still waiting" costs nothing after the
first beat: no clock, no silent flash every 3 s, no upload into a slot a cry is
coming out of. That is what removed the pulse, its `after_beat_s`, and the cry
gap that guarded it. A `needs` never needed one either: it beats every 1.5 s
until somebody dismisses it.

**Mute is per kind, because the ids are.** The ball has no volume, so a muted
voice is a different id that makes no sound: 4 for `needs` (199's light and
rumble with the sound taken out) and 9 for `done` (the light alone). Each kind
names its own in the config.

**What the desk settled, and what it did not.** `needs` is `199` every 1.5 s
until dismissed — one number to turn, measured and then judged at the desk on
2026-09-22. `done` speaking twice, 30 s apart, is a CHOICE. The config says which is which next to each number, because a guess
that loses its label becomes a measurement in about a week.

**A catch ends one of two ways** (task 56), and those are `outcome()`, not
kinds: nothing queues them and nothing repeats them. Answering a `needs` is
`caught` (201), and walking away from one you took is `broke_out` (206). Both
are optional in the config, so a file written before them loads and plays
neither — and the daemon's banner says so.

**A `done` cries in a mood** (task 64). Its `cries` name pools — `happy`,
`proud`, `sad`, `call`, `soft`, `greet`, `lonely` — and the Signaller picks the
pool from what happened: how the turn ended, how long it ran, whether it came
back, whether you are in front of it and still. This file only loads the pools
and their numbers; which pool a beat gets is the Signaller's.

**A `done` speaks as one partner** (spec 04, task 02). The config's
`partners` block holds what changes with the partner — `led`, `tint`, `cries` —
and `load(partner=…)` lays the chosen one over `done`, so everything past this
file sees the same `Ladder` as before. Every partner is checked at load, not only
the chosen one, so switching to another can never be the moment a typo shows.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path

from .signals import Kind

CONFIG = Path(__file__).resolve().parents[2] / "config" / "signals.json"

# The cry the ball speaks with, and — since task 24 — the sound the Mac makes
# for the same signal when there is no ball. It is here rather than in the
# daemon because the config refers to it by name: `"mac_sound": "@cry"` is how
# a kind says *whatever voice the ball is using*, so the two can never drift
# apart by editing one of them. `--cry` overrides both at once.
ROOT = Path(__file__).resolve().parents[2]
CRIES = ROOT / "assets" / "cries"
# The partner a run speaks with when nobody chose one: the only one before spec 04.
DEFAULT_PARTNER = "pikachu"
CRY = CRIES / f"{DEFAULT_PARTNER}.wav"

# What that looks like in the config file. A path would be a second copy of the
# same fact, free to disagree with `--cry` — which is exactly the divergence
# task 24 exists to close.
CRY_TOKEN = "@cry"

# The two ways a catch ends (task 56), by the names the config gives them.
# Anything else under `outcomes` is refused: a misspelt one would load, never
# play, and look in charge.
OUTCOMES = ("caught", "broke_out", "silenced")

# The moods a kind's cries come in (task 64), by the names the config gives
# them. `happy` is the one every beat falls back to, so it is the one required.
POOLS = ("happy", "proud", "sad", "call", "soft", "greet", "lonely")

# What a partner lays over `done` (spec 04, task 02), and all of it is required:
# a partner missing one would quietly keep the other's.
PARTNER_KEYS = ("led", "tint", "cries")

# 199's motor runs for 571 ms (learnings, task 05). An interval under that sends
# the next beat into a motor that never stopped: one continuous buzz, not a
# faster pulse, with the wire lock serialising the writes behind it. The number
# on the flag stops being the number felt, so the loader says so.
MOTOR_FLOOR_S = 0.6


@dataclass(frozen=True, slots=True)
class Voice:
    """What to play for one signal. Plain data, straight to a mirror.

    `led` is an LED resource index to put in the slot first, or `None` — task 04
    measured that an index alone does nothing and that an effect lights the ball
    on its own, so `None` is the honest default rather than a missing feature.

    `light` is an effect that puts up a light which stays on by itself, sent
    before `effect` when the ball is not already holding it — or `None` for a
    voice whose effect is its own light. It is how a `done` stays lit while it
    waits (criterion 3) with nothing sent after its beats (task 35).

    `silent` means this beat makes no sound anywhere: the effect is one without
    a voice, and the Mac stays quiet as well.

    `budget_s` is how long this voice has before the next beat of its own kind
    falls due — its gap in the rhythm — or `None` for one that plays once. The
    core hands the number over and has no opinion about what a mirror does with
    it (principle 1); on the ball it is how long the effect frame may be retried
    for, because a beat still being retried when the next one is due has stopped
    being a beat, and landing it late is worse in a rhythm than not landing it.
    Measured 2026-09-23: `needs` beats every 1.5s and the wire's own 5s ack
    timeout held the mirror's single worker for over ten, so seven beats in a
    row came out of the ball as one sound.

    `mac_sound` is the same beat for the surface that has no motor: with no ball
    connected the Mac makes the sound instead (criterion 8), so one kind's voice
    is described once here rather than split between this file and a mirror.
    It is a path and nothing else — the core never opens it, and which surface
    plays it is a mirror's business. `silent` wins over it: a beat that makes no
    noise on the ball makes none on the Mac either.

    `tint` is the colour this voice lights the ball with, as `#RRGGBB`, for a
    surface that has no LED to put it in — the menu bar's ball (task 58). The
    ball never reads it: its colour comes from `led` or from the firmware.

    `lasts_s` is how long an effect that plays once goes on for, so a mirror
    does not cut it short (task 56): the ball's next step after a beat can be
    180, which ends every light, and 201 ended at once is not a catch.
    """

    effect: int
    led: int | None = None
    silent: bool = False
    mac_sound: str | None = None
    budget_s: float | None = None
    light: int | None = None
    tint: str | None = None
    lasts_s: float | None = None


@dataclass(frozen=True, slots=True)
class Moods:
    """A kind's cries by mood, and the numbers that choose between them (task 64).

    `pools` maps a name in `POOLS` to its ids, in the config's order; `happy` is
    always there. `long_turn_s` is how long a turn has to run for its first beat
    to be `proud`, `lonely_after_s` how long after the first beat an unanswered
    signal cries `lonely`, and `greet_lasts_s` how long the greet is left to play
    before anything is sent over it. Each is `None` when its pool is absent.
    `greet_quiet_s` is how long after anything played the greet is spent in
    silence instead (task 67); `None` is the behaviour before it. `greet_away_s`
    is how long away from the keys, or asleep, counts as coming back (task 67);
    `None` is the behaviour before it, `idle.after_s`.
    """

    pools: dict[str, tuple[int, ...]]
    long_turn_s: float | None = None
    lonely_after_s: float | None = None
    greet_lasts_s: float | None = None
    greet_quiet_s: float | None = None
    greet_away_s: float | None = None


@dataclass(frozen=True, slots=True)
class Ladder:
    voices: dict[Kind, Voice]
    every: dict[Kind, float | None]
    times: dict[Kind, int | None]
    # The effect each kind plays while muted (task 35). Per kind because there
    # is no volume on the ball: quiet is a different id, and which one keeps a
    # kind recognisable is a judgement about that kind.
    mutes: dict[Kind, int]
    snooze_s: float
    # How long the ball holds its tongue after a person types (task 25). Zero
    # is the whole of the old behaviour, which is why it has a default and
    # `snooze_s` does not: a config written before this key keeps working and
    # keeps signalling, and the daemon prints the effective number in its
    # banner every run so a key lost in an edit is not invisible.
    after_prompt_s: float = 0.0
    # How long a window you just left still counts as looked at (task 37). Zero
    # is the behaviour before it, the same way as `after_prompt_s`: a config
    # written without the key speaks the moment you look away.
    look_away_s: float = 0.0
    # How long a window has to be in front before it counts as looked at (task
    # 67). Zero is the behaviour before it: looked at the moment it is in front.
    glance_s: float = 0.0
    # How long the ball holds its tongue after a session closes (task 44), so
    # the next cry is not read as the tab just closed. Zero is the behaviour
    # before it, the same way as `after_prompt_s`.
    after_end_s: float = 0.0
    # How a catch ends (task 56), by name, and what each plays muted. Empty is
    # a config written before them: nothing plays for either.
    outcomes: dict[str, Voice] = field(default_factory=dict)
    outcome_mutes: dict[str, int] = field(default_factory=dict)
    # The ids a kind may cry with instead of its `effect`, by mood (tasks 57,
    # 64). Absent for a kind that has one voice: the pick is the Signaller's,
    # and `effect` stays the fallback for when it cannot choose.
    moods: dict[Kind, Moods] = field(default_factory=dict)
    # How long without a key or the mouse before a window in front stops
    # counting as looked at (task 64). Zero is the behaviour before it: in
    # front is watched, however long nobody has touched anything.
    idle_s: float = 0.0
    # The partner a `done` speaks with, and every one the config offers (spec
    # 04). `None` and empty are a config with no `partners` block: Pikachu, fixed.
    partner: str | None = None
    partners: tuple[str, ...] = ()
    # Things worth saying out loud that are not errors. The core does not print
    # (principle 1) and does not swallow (principle 7), so it hands them over.
    warnings: list[str] = field(default_factory=list)

    """The whole vocabulary, loaded and checked once."""

    def muted(self, kind: Kind, voice: Voice) -> Voice:
        """The same voice with the sound taken out of it, and nothing else.

        The one place mute is decided, because it has to be. Two mirrors each
        working out for themselves what "quiet" means is how the ball and the
        menu bar drift into two different ideas of the same switch — and a
        mirror choosing to stay silent at all is a mirror inventing state
        (principle 1). It is handed a voice that is already mute, not asked to
        invent one.

        The effect becomes the kind's `mute_effect`, because the protocol has
        no volume: every id brings its own sound, so silence is a choice of id.
        `mac_sound` goes because a mute that leaves the laptop chiming is not
        one. `led`, `light`, `budget_s` and every number in the rhythm are
        untouched: what is removed is the noise, not the signal. A muted `done`
        is 9 with 9 as its light, which the ball sends once and not twice.
        """
        return replace(voice, effect=self.mutes[kind], silent=True, mac_sound=None)

    def voice(self, kind: Kind, muted: bool = False) -> Voice:
        got = self.voices[kind]
        return self.muted(kind, got) if muted else got

    def outcome(self, name: str, muted: bool = False) -> Voice | None:
        """What a catch ending `name` plays, or `None` when the config has none.

        Muted the same way a kind is: the id is swapped for the outcome's own
        `mute_effect` and the Mac stays quiet, and nothing else changes.
        """
        got = self.outcomes.get(name)
        if got is None or not muted:
            return got
        return replace(got, effect=self.outcome_mutes[name], silent=True, mac_sound=None)

    def next_beat(self, kind: Kind, last: float | None, now: float,
                  played: int = 0) -> float | None:
        """When the next beat of `kind` is due, or `None` if it has said its piece.

        `last is None` means nothing has been played yet, and the answer is
        `now`: the first beat is always due immediately (criterion 1's "within
        ~2 s" is the daemon's latency, not a delay anybody adds).

        `played` is how many beats this signal has already had. A kind with a
        `times` runs out after that many and leaves its held light to carry it;
        a kind with none never does. It is an argument rather than state because this
        file has no clock and no memory — the caller owns both.
        """
        limit = self.times[kind]
        if limit is not None and played >= limit:
            return None
        if last is None:
            return now
        every = self.every[kind]
        return None if every is None else last + every


def cry_of(partner: str) -> Path:
    """Where a partner's cry is, as `tools/fetch_cry.py --partner` writes it (spec 04, task 01)."""
    return CRIES / f"{partner}.wav"


def load(path: Path | str = CONFIG, *, cry: Path | str | None = None,
         partner: str = DEFAULT_PARTNER) -> Ladder:
    """Read the config, or refuse with a sentence naming the file and the key.

    `cry` is what `"@cry"` resolves to in a `mac_sound` — the daemon passes
    whatever `--cry` points at, so the sound the Mac makes for a `done` is the
    same file the ball is speaking with and cannot be changed on its own.
    `None` is the chosen partner's own cry.

    `partner` is the one laid over `done` (spec 04, task 02). One the config
    does not list is refused by name, not swapped for another.
    """
    path = Path(path)
    try:
        raw = json.loads(path.read_text())
    except FileNotFoundError:
        raise FileNotFoundError(
            f"{path} is missing — it is the signal vocabulary, not an optional "
            f"tuning file, and nothing can be played without it") from None
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from None

    by_partner = _partners(raw, path)
    if by_partner is None and partner != DEFAULT_PARTNER:
        raise ValueError(
            f"{path} has no 'partners' object, so a done speaks only as "
            f"{DEFAULT_PARTNER}; partner {partner!r} needs one")
    if by_partner is not None and partner not in by_partner:
        raise ValueError(
            f"{path}: partner {partner!r} is not in 'partners' — the ones there are "
            f"{', '.join(by_partner)}")
    if cry is None:
        cry = cry_of(partner)

    warnings: list[str] = []
    voices: dict[Kind, Voice] = {}
    every: dict[Kind, float | None] = {}
    times: dict[Kind, int | None] = {}
    mutes: dict[Kind, int] = {}
    moods: dict[Kind, Moods] = {}
    kinds = raw.get("kinds")
    if not isinstance(kinds, dict):
        raise ValueError(f"{path} has no 'kinds' object")

    for kind in Kind:
        entry = kinds.get(kind.value)
        if entry is None:
            raise ValueError(
                f"{path} has no entry for kind {kind.value!r}. Every kind the "
                f"core can queue has to have a voice, or a signal arrives with "
                f"nothing to play and fails where nobody can see it")
        _gone(entry, path, kind.value)
        if kind is Kind.DONE and by_partner is not None:
            _laid(entry, path, kind.value)
            done = entry
            entry = {**entry, **by_partner[partner]}
        # Read before the voice is built, because the voice carries it.
        every[kind] = _every(entry, path, kind.value, warnings)
        voices[kind] = Voice(effect=_effect(entry, path, kind.value),
                             led=_led(entry, path, kind.value),
                             mac_sound=_mac_sound(entry, path, kind.value, cry),
                             budget_s=every[kind],
                             light=_light(entry, path, kind.value),
                             tint=_tint(entry, path, kind.value))
        times[kind] = _times(entry, path, kind.value, every[kind], warnings)
        mutes[kind] = _mute_effect(entry, path, kind.value)
        if "cries" in entry:
            moods[kind] = _moods(entry, path, kind.value, every[kind], times[kind])
        if every[kind] is None and voices[kind].light is None:
            warnings.append(
                f"{path}: {kind.value} plays once and holds no light, so on the "
                f"ball nothing will say it is still pending after the first beat. "
                f"Only the menu bar would carry it.")

    # The partners not chosen, through the same checks as the one that was:
    # their pools may need a number `done` does not carry.
    for other in (by_partner or {}):
        if other != partner:
            _moods({**done, **by_partner[other]}, path, Kind.DONE.value,
                   every[Kind.DONE], times[Kind.DONE])

    snooze = raw.get("snooze")
    if not isinstance(snooze, dict) or "after_s" not in snooze:
        raise ValueError(
            f"{path} has no 'snooze' object with an 'after_s'. It is how long a "
            f"dismissed signal stays quiet before it comes back, and leaving it "
            f"out would be a promise with no deadline")
    after = snooze["after_s"]
    if not isinstance(after, (int, float)) or isinstance(after, bool) or after <= 0:
        raise ValueError(
            f"{path}: snooze.after_s is {after!r}; it has to be a positive number "
            f"of seconds — a snooze of zero brings the signal back the moment it "
            f"is dismissed, which is ignoring the press")

    # Optional, unlike `snooze`: there is no promise here to leave without a
    # deadline, and absent means the beat is not held at all.
    after_prompt = raw.get("after_prompt", {})
    if not isinstance(after_prompt, dict):
        raise ValueError(
            f"{path}: 'after_prompt' is {after_prompt!r}; it has to be an object "
            f"with a 'wait_s' in it, the same shape as 'snooze'")
    wait = after_prompt.get("wait_s", 0.0)
    if not isinstance(wait, (int, float)) or isinstance(wait, bool) or wait < 0:
        raise ValueError(
            f"{path}: after_prompt.wait_s is {wait!r}; it has to be a number of "
            f"seconds and not a negative one — it is how long the ball waits "
            f"after somebody types before it speaks")

    # Optional for the same reason, and absent means no wait: the old behaviour.
    look_away = raw.get("look_away", {})
    if not isinstance(look_away, dict):
        raise ValueError(
            f"{path}: 'look_away' is {look_away!r}; it has to be an object "
            f"with a 'wait_s' in it, the same shape as 'after_prompt'")
    away = look_away.get("wait_s", 0.0)
    if not isinstance(away, (int, float)) or isinstance(away, bool) or away < 0:
        raise ValueError(
            f"{path}: look_away.wait_s is {away!r}; it has to be a number of "
            f"seconds and not a negative one — it is how long a window you just "
            f"left still counts as looked at")
    glance = _seconds(look_away, path, "look_away", "glance_s", False,
                      "how long a window has to be in front before it counts as looked at")

    # Optional for the same reason, and absent means no wait: the old behaviour.
    after_end = raw.get("after_end", {})
    if not isinstance(after_end, dict):
        raise ValueError(
            f"{path}: 'after_end' is {after_end!r}; it has to be an object "
            f"with a 'wait_s' in it, the same shape as 'after_prompt'")
    closed = after_end.get("wait_s", 0.0)
    if not isinstance(closed, (int, float)) or isinstance(closed, bool) or closed < 0:
        raise ValueError(
            f"{path}: after_end.wait_s is {closed!r}; it has to be a number of "
            f"seconds and not a negative one — it is how long the ball waits "
            f"after a session closes before it speaks")

    # Optional for the same reason, and absent means off: the old behaviour.
    idle = raw.get("idle", {})
    if not isinstance(idle, dict):
        raise ValueError(
            f"{path}: 'idle' is {idle!r}; it has to be an object with an "
            f"'after_s' in it, the same shape as 'snooze'")
    idle_s = idle.get("after_s", 0.0)
    if not isinstance(idle_s, (int, float)) or isinstance(idle_s, bool) or idle_s < 0:
        raise ValueError(
            f"{path}: idle.after_s is {idle_s!r}; it has to be a number of seconds "
            f"and not a negative one — it is how long with no key or mouse before a "
            f"window in front stops counting as looked at, and 0 is never")

    outcomes, outcome_mutes = _outcomes(raw, path, cry)

    if "mute" in raw:
        # Refused, not ignored: a top-level mute effect loaded quietly next to
        # the per-kind ones would be a number that looks in charge and is not.
        raise ValueError(
            f"{path}: the top-level 'mute' is gone — each kind names its own "
            f"'mute_effect' now, because quiet is a different id per kind")

    return Ladder(
        voices=voices,
        every=every,
        times=times,
        mutes=mutes,
        snooze_s=float(after),
        after_prompt_s=float(wait),
        look_away_s=float(away),
        glance_s=glance or 0.0,
        after_end_s=float(closed),
        outcomes=outcomes,
        outcome_mutes=outcome_mutes,
        moods=moods,
        idle_s=float(idle_s),
        partner=None if by_partner is None else partner,
        partners=tuple(by_partner or ()),
        warnings=warnings,
    )


def _partners(raw: dict, path: Path) -> dict[str, dict] | None:
    """The partners a `done` may speak with (spec 04, task 02), or `None` when
    the config has none. Each is checked whole here, under its own name, so a
    refusal points at `partners.eevee` and not at the `done` it was laid over.

    A name is lower-case letters only: it becomes a file name (`cry_of`) and
    the word kept in `var/partner`.
    """
    block = raw.get("partners")
    if block is None:
        return None
    if not isinstance(block, dict):
        raise ValueError(
            f"{path}: 'partners' is {block!r}; it has to be an object naming each "
            f"partner a done may speak with")
    by_partner: dict[str, dict] = {}
    for name, held in block.items():
        if name.startswith("_"):
            continue
        where = f"partners.{name}"
        if not name.isascii() or not name.isalpha() or not name.islower():
            raise ValueError(
                f"{path}: {where} is not a partner's name — lower-case letters only, "
                f"since it names the cry's file")
        if not isinstance(held, dict):
            raise ValueError(f"{path}: {where} is {held!r}; it has to be an object")
        for key in held:
            if not key.startswith("_") and key not in PARTNER_KEYS:
                raise ValueError(
                    f"{path}: {where}.{key} is not a partner's — a partner holds "
                    f"{', '.join(PARTNER_KEYS)}, and the rest of done is the same for both")
        for key in PARTNER_KEYS:
            if key not in held:
                raise ValueError(
                    f"{path}: {where} has no '{key}'; without it this partner would "
                    f"keep another's, and nothing would say so")
        _led(held, path, where)
        _tint(held, path, where)
        _pools(held["cries"], path, where)
        by_partner[name] = {key: held[key] for key in PARTNER_KEYS}
    if not by_partner:
        raise ValueError(
            f"{path}: 'partners' names no partner; leave it out for Pikachu alone")
    return by_partner


def _laid(entry: dict, path: Path, where: str) -> None:
    """Refuse a `done` that still holds what a partner lays over it: two copies
    of one colour would load, and only one of them would be the one shown."""
    for key in PARTNER_KEYS:
        if key in entry:
            raise ValueError(
                f"{path}: {where}.{key} is also in each partner — with a 'partners' "
                f"object it lives there, and one here would be ignored")


def _outcomes(raw: dict, path: Path, cry: Path | str) -> tuple[dict[str, Voice], dict[str, int]]:
    """The catch's two endings (task 56) and the silence (task 68), or none at
    all when the key is absent. Each may hold a `light` before its effect and be
    `silent`, as the silence is: a blue held behind a tick, and no sound."""
    given = raw.get("outcomes", {})
    if not isinstance(given, dict):
        raise ValueError(
            f"{path}: 'outcomes' is {given!r}; it has to be an object naming "
            f"{' and '.join(OUTCOMES)}")
    voices: dict[str, Voice] = {}
    mutes: dict[str, int] = {}
    for name, entry in given.items():
        if name.startswith("_"):
            continue
        where = f"outcomes.{name}"
        if name not in OUTCOMES:
            raise ValueError(
                f"{path}: {where} is not an outcome — the ones there are "
                f"{', '.join(OUTCOMES)}, and one nothing ever plays would look in charge")
        if not isinstance(entry, dict):
            raise ValueError(f"{path}: {where} is {entry!r}; it has to be an object")
        silent = entry.get("silent", False)
        if not isinstance(silent, bool):
            raise ValueError(f"{path}: {where}.silent is {silent!r}; it is true or false")
        mac_sound = _mac_sound(entry, path, where, cry)
        if silent and mac_sound is not None:
            raise ValueError(
                f"{path}: {where} is silent and names a mac_sound — a silent "
                f"outcome makes no sound on either surface, so one of the two is wrong")
        voices[name] = Voice(effect=_effect(entry, path, where),
                             led=_led(entry, path, where),
                             silent=silent,
                             mac_sound=mac_sound,
                             light=_light(entry, path, where),
                             tint=_tint(entry, path, where),
                             lasts_s=_lasts(entry, path, where))
        mutes[name] = _mute_effect(entry, path, where)
    return voices, mutes


def _tint(entry: dict, path: Path, where: str) -> str | None:
    """The colour a surface with no LED shows for this voice, or `None` (task 58)."""
    value = entry.get("tint")
    if value is None:
        return None
    if (not isinstance(value, str) or len(value) != 7 or value[0] != "#"
            or any(c not in "0123456789abcdefABCDEF" for c in value[1:])):
        raise ValueError(
            f"{path}: {where}.tint is {value!r}; it is a colour written #RRGGBB, "
            f"or null for none")
    return value.upper()


def _lasts(entry: dict, path: Path, where: str) -> float | None:
    """How long an effect that plays once goes on for, or `None` (task 56)."""
    value = entry.get("lasts_s")
    if value is None:
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
        raise ValueError(
            f"{path}: {where}.lasts_s is {value!r}; it has to be a positive number "
            f"of seconds, or null when nothing needs to wait for it")
    return float(value)


def _effect(entry: dict, path: Path, where: str) -> int:
    value = entry.get("effect")
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 0xFFFF:
        raise ValueError(
            f"{path}: {where}.effect is {value!r}; it has to be an effect id in "
            f"the u16 space the ball accepts")
    return value


def _moods(entry: dict, path: Path, where: str, every: float | None,
           times: int | None) -> Moods:
    """A kind's cries by mood (task 64), and the numbers that pick between them.

    `happy` needs two ids or more — one is `effect` spelt another way — and
    every other pool one or more; none twice in a pool, since a repeat weights
    the pick without saying so. A pool that needs a number refuses to load
    without it, because one that can never be chosen would look in charge.
    """
    pools = _pools(entry["cries"], path, where)
    long_turn = _seconds(entry, path, where, "long_turn_s", "proud" in pools,
                         "how long a turn runs before its done is proud")
    lonely = _seconds(entry, path, where, "lonely_after_s", "lonely" in pools,
                      "how long after the first beat a done nobody came to is lonely")
    greet = _seconds(entry, path, where, "greet_lasts_s", False,
                     "how long the greet plays before anything is sent over it")
    greet_quiet = _seconds(entry, path, where, "greet_quiet_s", False,
                           "how long after anything played a greet stays silent")
    greet_away = _seconds(entry, path, where, "greet_away_s", False,
                          "how long away from the keys counts as coming back")
    if lonely is not None:
        if times is None:
            raise ValueError(
                f"{path}: {where}.cries.lonely is a beat after the last one, and "
                f"{where}.times is null — there is no last one")
        last = (every or 0.0) * (times - 1)
        if lonely <= last:
            raise ValueError(
                f"{path}: {where}.lonely_after_s is {lonely:g}s, and the last of "
                f"{where}'s {times} beats is {last:g}s after the first — lonely is "
                f"the beat after them, so it has to come later")
    return Moods(pools=pools, long_turn_s=long_turn, lonely_after_s=lonely,
                 greet_lasts_s=greet, greet_quiet_s=greet_quiet,
                 greet_away_s=greet_away)


def _pools(value, path: Path, where: str) -> dict[str, tuple[int, ...]]:
    """The cries under `where`, by mood, checked: the pools half of `_moods`,
    on its own so each partner's are read under that partner's name (spec 04)."""
    if isinstance(value, list):
        raise ValueError(
            f"{path}: {where}.cries is a list; since task 64 it is an object naming "
            f"pools ({', '.join(POOLS)}), each a list of effect ids — the old list "
            f"is 'happy'")
    if not isinstance(value, dict):
        raise ValueError(
            f"{path}: {where}.cries is {value!r}; it has to be an object naming "
            f"pools ({', '.join(POOLS)})")
    pools: dict[str, tuple[int, ...]] = {}
    for name, ids in value.items():
        if name.startswith("_"):
            continue
        at = f"{where}.cries.{name}"
        if name not in POOLS:
            raise ValueError(
                f"{path}: {at} is not a pool — the ones there are {', '.join(POOLS)}, "
                f"and one nothing ever picks would look in charge")
        least = 2 if name == "happy" else 1
        if not isinstance(ids, list) or len(ids) < least:
            raise ValueError(
                f"{path}: {at} is {ids!r}; it has to be a list of at least {least} "
                f"effect id{'s' if least > 1 else ''}"
                + (" — a single cry belongs in 'effect'" if name == "happy" else ""))
        for n, cry in enumerate(ids):
            if not isinstance(cry, int) or isinstance(cry, bool) or not 0 <= cry <= 0xFFFF:
                raise ValueError(
                    f"{path}: {at}[{n}] is {cry!r}; each cry has to be an "
                    f"effect id in the u16 space the ball accepts")
        got = tuple(ids)
        if len(set(got)) != len(got):
            raise ValueError(
                f"{path}: {at} has an id in it twice; each is picked as often as "
                f"it is listed, so a repeat is a weighting nobody wrote down")
        pools[name] = got
    if "happy" not in pools:
        raise ValueError(
            f"{path}: {where}.cries has no 'happy'; it is the pool every beat falls "
            f"back to, so the others cannot stand without it")
    return pools


def _seconds(entry: dict, path: Path, where: str, key: str, needed: bool,
             what: str) -> float | None:
    """A positive number of seconds under `key`, or `None` when it is absent and allowed to be."""
    value = entry.get(key)
    if value is None:
        if needed:
            raise ValueError(
                f"{path}: {where} has no '{key}'; it is {what}, and the pool that "
                f"needs it would never be picked without it")
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
        raise ValueError(
            f"{path}: {where}.{key} is {value!r}; it has to be a positive number of "
            f"seconds — {what}")
    return float(value)


def _light(entry: dict, path: Path, where: str) -> int | None:
    """The held light sent before this kind's beat, or `None` for none."""
    if entry.get("light") is None:
        return None
    return _effect({"effect": entry["light"]}, path, f"{where}.light")


def _mute_effect(entry: dict, path: Path, where: str) -> int:
    """What this kind plays while muted. Required: a kind with no quiet id would
    either keep its sound under mute or fall silent and still, and neither is
    something a person switching mute on asked for."""
    if "mute_effect" not in entry:
        raise ValueError(
            f"{path}: {where} has no 'mute_effect'. Mute swaps the id, since the "
            f"ball has no volume, so every kind has to name the one it plays quiet")
    return _effect({"effect": entry["mute_effect"]}, path, f"{where}.mute_effect")


def _gone(entry: dict, path: Path, where: str) -> None:
    """Refuse the keys task 35 removed, rather than loading them as if they did
    something. A `pulse` left in the file would read as a blink the ball no
    longer does, and nobody would notice it was being ignored."""
    for key in ("pulse", "after_beat_s"):
        if key in entry:
            raise ValueError(
                f"{path}: {where}.{key} is gone — the held light is the pulse now "
                f"({where}.light), and nothing is sent between beats")


def _led(entry: dict, path: Path, where: str) -> int | None:
    value = entry.get("led")
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 0xFFFF:
        raise ValueError(f"{path}: {where}.led is {value!r}; an LED index is a u16 or null")
    return value


def _mac_sound(entry: dict, path: Path, where: str,
               cry: Path | str = CRY) -> str | None:
    """The no-ball voice for this beat, or `None` for a beat the Mac stays out of.

    `"@cry"` means *the voice the ball is using*, resolved to whatever `--cry`
    points at (task 24, asked for as "the done's sound on the Mac should be the
    one that goes to the ball"). Written as a token rather than a path because the two have to be
    the same file by construction: a second absolute path in the config would be
    free to drift, and the symptom of that drift is the Mac and the ball saying
    different things for the same signal — which nobody would notice, because
    only one of them is ever audible at a time.

    Not checked for existence here: the core does not touch a filesystem, and a
    file that is there at load time is not a file that is there an hour later.
    The seam's `Sound.play` is where a missing path turns into a sentence.
    """
    value = entry.get("mac_sound")
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(
            f"{path}: {where}.mac_sound is {value!r}; it is a path to a sound "
            f"file, {CRY_TOKEN!r} for whatever voice the ball is using, or null "
            f"when this beat should make no sound on the Mac")
    if value == CRY_TOKEN:
        return str(cry)
    # A relative path is the repo's own `sounds/` (task 70): read against this
    # checkout, since the daemon is started from anywhere.
    return value if Path(value).is_absolute() else str(ROOT / value)


def _every(entry: dict, path: Path, where: str, warnings: list[str]) -> float | None:
    if "every_s" not in entry:
        raise ValueError(
            f"{path}: {where} has no 'every_s'. Leaving it out would be a silent "
            f"default; null is how you say 'play it once'")
    value = entry["every_s"]
    if value is None:
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
        raise ValueError(
            f"{path}: {where}.every_s is {value!r}; it has to be a positive "
            f"number of seconds, or null for once")
    if value < MOTOR_FLOOR_S:
        warnings.append(
            f"{path}: {where}.every_s is {value:g}s, under the ~{MOTOR_FLOOR_S:g}s "
            f"the motor runs for — the beats will run into each other and read as "
            f"one continuous buzz, so the number written here is not the number felt.")
    return float(value)


def _times(entry: dict, path: Path, where: str, every: float | None,
           warnings: list[str]) -> int | None:
    """How many beats this kind gets before its held light carries it alone, or `None`.

    Absent and `null` both mean "no limit", which is what a `needs` wants: it
    speaks until somebody dismisses it, and a count would be a way for it to
    fall silent on its own — the thing criterion 3 forbids.

    `every_s: null` already means "once", so a `times` next to it is either
    agreeing or contradicting, and a contradiction that loads quietly is how a
    number stops meaning what it says.
    """
    if "times" not in entry or entry["times"] is None:
        return None
    value = entry["times"]
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(
            f"{path}: {where}.times is {value!r}; it has to be a whole number of "
            f"beats, at least 1, or null for 'until it is dismissed'")
    if every is None and value != 1:
        raise ValueError(
            f"{path}: {where}.every_s is null, which already means 'play it once', "
            f"but {where}.times says {value}. There is no interval to space them "
            f"by, so the second one would never be due")
    return value
