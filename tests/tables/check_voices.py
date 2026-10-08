#!/usr/bin/env python3
"""Check the partners a `done` speaks with: the `voices` block and `ladder.load(voice=…)`.

    venv/bin/python3 tests/tables/check_voices.py

Spec 04, task 02. What changes with the partner — `led`, `tint`, `cries` — lives
in `config/signals.json`'s `voices`, and `load(voice=…)` lays the chosen one over
`done`. The reference leg is criterion 3: Pikachu chosen is the ladder of the
config before the block, read field by field. Eevee is then everything Pikachu
is except those three and the cry `@cry` resolves to.

Each refusal is the shipped config with one thing broken, and must carry the
words named. Every voice is checked at load, so a broken Eevee is refused while
Pikachu is the one chosen.

**The control is mutants**, as in `check_ladder_refusals.py`: `src/core/ladder.py`
with one rule's text replaced, compiled as its own module. A mutant whose text
is not in the file exactly once is reported wrong, not caught.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
SOURCE = ROOT / "src" / "core" / "ladder.py"
SHIPPED = json.loads((ROOT / "config" / "signals.json").read_text())
TMP = Path(tempfile.mkdtemp(prefix="check-voices-"))

from src.core.signals import Kind                                      # noqa: E402

spec = importlib.util.spec_from_file_location("fetch_cry", ROOT / "tools" / "fetch_cry.py")
fetch_cry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch_cry)

DONE = Kind.DONE


class Sheet:
    def __init__(self, quiet: bool = False) -> None:
        self.bad = 0
        self.quiet = quiet

    def head(self, text: str) -> None:
        if not self.quiet:
            print(f"\n  {text}")

    def row(self, what: str, got, want) -> None:
        good = got == want
        self.bad += not good
        if not self.quiet:
            print(f"    {what:<66} {'ok' if good else f'<-- WRONG: {got!r}, wanted {want!r}'}")


def load_module(patch: tuple[str, str] | None = None):
    text = SOURCE.read_text()
    if patch is not None:
        if text.count(patch[0]) != 1:
            return None
        text = text.replace(*patch)
    # Its own name, so the real `src.core.ladder` stays as it was.
    spec = importlib.util.spec_from_file_location("src.core.ladder_under_check", SOURCE)
    module = importlib.util.module_from_spec(spec)
    module.__package__ = "src.core"
    sys.modules[spec.name] = module
    exec(compile(text, str(SOURCE), "exec"), module.__dict__)
    return module


def written(name: str, raw) -> Path:
    """`raw` as `<name>/signals.json`: one file name for all, so the warnings, which name it, agree."""
    path = TMP / name / "signals.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(raw))
    return path


def broken(change) -> dict:
    raw = copy.deepcopy(SHIPPED)
    change(raw)
    return raw


def before_voices(raw: dict) -> dict:
    """The config as it was before task 02: Pikachu's three keys back in `done`, no block."""
    old = copy.deepcopy(raw)
    old["kinds"]["done"].update({k: old["voices"]["pikachu"][k] for k in ("led", "tint", "cries")})
    del old["voices"]
    return old


def attempt(call):
    try:
        return call()
    except Exception as exc:              # a refusal here is a wrong row, not a crash
        return f"raised {type(exc).__name__}: {exc}"


def refusal(mod, path: Path, **kw) -> str:
    """The sentence a refusal carries, or what happened instead."""
    try:
        mod.load(path, **kw)
    except ValueError as exc:
        return str(exc)
    except Exception as exc:              # the wrong refusal is a wrong row, not a crash
        return f"raised {type(exc).__name__}: {exc}"
    return "loaded"


def shifted(cry: int) -> int | None:
    """Pikachu's id as Eevee's (spec 04, open question 1): N+29, 230→231, 300→301,
    181 dropped, and anything that is no partner's kept."""
    if 20 <= cry <= 39:
        return cry + 29
    return {230: 231, 300: 301, 181: None}.get(cry, cry)


def no_proud(r: dict) -> None:
    """Pikachu with no proud, Eevee with one, and `done` with no number for it."""
    r["voices"]["pikachu"]["cries"].pop("proud")
    r["kinds"]["done"].pop("long_turn_s")


REFUSED = [
    # (what, file, contents, load's keywords, words the sentence must carry)
    ("a voice the config does not list", "unknown", SHIPPED, {"voice": "charmander"},
     ("voice 'charmander' is not in 'voices'", "pikachu, eevee")),
    ("an old config asked for Eevee", "oldeevee", before_voices(SHIPPED), {"voice": "eevee"},
     ("has no 'voices' object", "voice 'eevee' needs one")),
    ("done still holding its cries", "donecries",
     broken(lambda r: r["kinds"]["done"].update(cries=r["voices"]["pikachu"]["cries"])), {},
     ("done.cries is also in each voice",)),
    ("done still holding its led", "doneled",
     broken(lambda r: r["kinds"]["done"].update(led=138)), {}, ("done.led is also in each voice",)),
    ("voices given as a list", "voicelist", broken(lambda r: r.update(voices=[])), {},
     ("'voices' is []",)),
    ("a voice given as a number", "voicenum", broken(lambda r: r["voices"].update(eevee=7)), {},
     ("voices.eevee is 7",)),
    ("a voice with no led", "noled", broken(lambda r: r["voices"]["eevee"].pop("led")), {},
     ("voices.eevee has no 'led'",)),
    ("a voice with no cries", "nocries", broken(lambda r: r["voices"]["eevee"].pop("cries")), {},
     ("voices.eevee has no 'cries'",)),
    ("a voice holding what is done's", "extra",
     broken(lambda r: r["voices"]["eevee"].update(effect=129)), {},
     ("voices.eevee.effect is not a voice's",)),
    ("a voice's name that is not a file name", "badname",
     broken(lambda r: r["voices"].update({"Eevee 2": r["voices"]["eevee"]})), {},
     ("voices.Eevee 2 is not a voice's name",)),
    ("a block naming no voice", "empty",
     broken(lambda r: r.update(voices={"_about": "nothing"})), {}, ("'voices' names no voice",)),
    ("Eevee's pool broken, Pikachu chosen", "eeveepool",
     broken(lambda r: r["voices"]["eevee"]["cries"].update(angry=[49])), {},
     ("voices.eevee.cries.angry is not a pool",)),
    ("Eevee's led broken, Pikachu chosen", "eeveeled",
     broken(lambda r: r["voices"]["eevee"].update(led=0x10000)), {}, ("voices.eevee.led is 65536",)),
    ("Eevee's tint broken, Pikachu chosen", "eeveetint",
     broken(lambda r: r["voices"]["eevee"].update(tint="beige")), {}, ("voices.eevee.tint is 'beige'",)),
    ("Eevee's proud with no number in done, Pikachu chosen", "eeveeproud", broken(no_proud), {},
     ("done has no 'long_turn_s'",)),
]


def table(sheet: Sheet, mod) -> None:
    shipped = written("shipped", SHIPPED)
    sheet.head("the shipped config")
    pika = attempt(lambda: mod.load(shipped))
    eevee = attempt(lambda: mod.load(shipped, voice="eevee"))
    sheet.row("loads, and no voice named is Pikachu",
              getattr(pika, "partner", pika), "pikachu")
    sheet.row("the partners are Pikachu and Eevee, notes left out",
              getattr(pika, "partners", pika), ("pikachu", "eevee"))
    sheet.row("they are the voices fetch_cry fetches",
              sorted(getattr(pika, "partners", ())), sorted(fetch_cry.VOICES))
    sheet.row("Eevee loads, and says so", getattr(eevee, "partner", eevee), "eevee")

    sheet.head("Pikachu is today's ladder (criterion 3)")
    old = attempt(lambda: mod.load(written("before", before_voices(SHIPPED))))
    sheet.row("the config before the block loads, with no partner",
              (getattr(old, "partner", old), getattr(old, "partners", old)), (None, ()))
    sheet.row("Pikachu chosen is that ladder, field by field",
              attempt(lambda: replace(pika, partner=None, partners=()) == old), True)
    done = attempt(lambda: pika.voice(DONE))
    sheet.row("done: led 138, Pikachu's yellow, pikachu.wav on the Mac",
              attempt(lambda: (done.led, done.tint, done.mac_sound)),
              (138, "#FFE14D", str(mod.cry_of("pikachu"))))
    sheet.row("done's happy is Pikachu's",
              attempt(lambda: pika.moods[DONE].pools["happy"]), (20, 32, 34, 181, 230))

    sheet.head("Eevee")
    edone = attempt(lambda: eevee.voice(DONE))
    sheet.row("done: led 1180, a beige, eevee.wav on the Mac",
              attempt(lambda: (edone.led, edone.tint, edone.mac_sound)),
              (1180, "#E6C89A", str(mod.cry_of("eevee"))))
    sheet.row("her pools are Pikachu's, shifted (N+29, 230→231, 181 dropped)",
              attempt(lambda: eevee.moods[DONE].pools),
              attempt(lambda: {mood: tuple(e for e in map(shifted, ids) if e is not None)
                               for mood, ids in pika.moods[DONE].pools.items()}))
    sheet.row("done is Pikachu's done but for led, tint and the cry",
              attempt(lambda: replace(edone, led=done.led, tint=done.tint,
                                      mac_sound=done.mac_sound) == done), True)
    sheet.row("her moods' numbers are Pikachu's",
              attempt(lambda: replace(eevee.moods[DONE], pools=pika.moods[DONE].pools)
                      == pika.moods[DONE]), True)
    sheet.row("the rest of the ladder is Pikachu's",
              attempt(lambda: replace(eevee, voices=pika.voices, moods=pika.moods,
                                      partner=pika.partner) == pika), True)
    custom = attempt(lambda: mod.load(shipped, voice="eevee", cry="/tmp/other.wav"))
    sheet.row("Eevee with a --cry: the Mac plays that file, the led stays hers",
              attempt(lambda: (custom.voice(DONE).mac_sound, custom.voice(DONE).led)),
              ("/tmp/other.wav", 1180))
    sheet.row("no voice cries 213, kept free for the catch",
              [name for name, v in SHIPPED["voices"].items() if isinstance(v, dict)
               and any(213 in ids for ids in v["cries"].values() if isinstance(ids, list))], [])

    sheet.head("refused, each with a sentence naming it")
    for what, name, raw, kw, words in REFUSED:
        said = refusal(mod, written(name, raw), **kw)
        sheet.row(what, [w for w in words if w not in said], [])


MUTANTS = [
    ("the voice ignored", ("entry = {**entry, **voiced[voice]}",
                           "entry = {**entry, **voiced[DEFAULT_VOICE]}")),
    ("@cry not following the voice", ("        cry = cry_of(voice)\n", "        cry = CRY\n")),
    ("the voices not chosen unchecked", ("        if other != voice:\n", "        if False:\n")),
    ("done allowed to keep its cries", ("            _laid(entry, path, kind.value)\n",
                                        "            pass\n")),
    ("an unknown voice let through", ("    if voiced is not None and voice not in voiced:\n",
                                      "    if False:\n")),
    ("Eevee from an old config let through",
     ("    if voiced is None and voice != DEFAULT_VOICE:\n", "    if False:\n")),
    ("voices' shape unchecked", ("    if not isinstance(block, dict):\n", "    if False:\n")),
    ("a voice's shape unchecked", ("        if not isinstance(held, dict):\n", "        if False:\n")),
    ("a voice's name unchecked",
     ("if not name.isascii() or not name.isalpha() or not name.islower():", "if False:")),
    ("a voice's extra key let through",
     ('if not key.startswith("_") and key not in VOICE_KEYS:', "if False:")),
    ("a voice's missing key let through", ("            if key not in held:\n",
                                           "            if False:\n")),
    ("a voice's led unchecked", ("        _led(held, path, where)\n", "        pass\n")),
    ("a voice's tint unchecked", ("        _tint(held, path, where)\n", "        pass\n")),
    ("an empty block let through", ("    if not voiced:\n", "    if False:\n")),
    ("the partner not recorded", ("        partner=None if voiced is None else voice,\n",
                                  "        partner=None,\n")),
    ("the partners not recorded", ("        partners=tuple(voiced or ()),\n",
                                   "        partners=(),\n")),
]


def main() -> int:
    print(__doc__.strip().splitlines()[0])
    sheet = Sheet()
    table(sheet, load_module())
    print("\n  mutants — each must turn at least one row wrong")
    for name, patch in MUTANTS:
        mod = load_module(patch)
        if mod is None:
            sheet.row(f"mutant: {name}", "NOT APPLIED", "caught")
            continue
        quiet = Sheet(quiet=True)
        try:
            table(quiet, mod)
        except Exception:                 # a crash under a mutant is the mutant caught
            quiet.bad += 1
        sheet.row(f"mutant: {name}", "caught" if quiet.bad else "survived", "caught")
    shutil.rmtree(TMP, ignore_errors=True)
    print("\n  " + ("ALL CASES MATCH the known answer" if not sheet.bad
                   else f"{sheet.bad} WRONG — the rows above"))
    return 1 if sheet.bad else 0


if __name__ == "__main__":
    sys.exit(main())
