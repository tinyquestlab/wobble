#!/usr/bin/env python3
"""The config refusals check_ladder does not reach, each against its removal.

    venv/bin/python3 tests/tables/check_ladder_refusals.py

`ladder.load` refuses a broken `config/signals.json` with a sentence naming the
file and the key (principle 7: a config that loads wrong fails where nobody can
see it). check_ladder asks the missing file, a missing kind and `every_s`; this
asks the rest — invalid JSON, no `kinds`, each optional object given as a
non-object, and an LED index outside u16. Each fixture is the shipped config
with exactly one thing broken, so the refusal can only be about that thing, and
the shipped config itself loading clean is the reference leg.

A mutant is `src/core/ladder.py` with one guard replaced by `if False:`, compiled
as its own module; the guard's line must occur exactly once or the mutant is
reported as not applied rather than as caught.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
SOURCE = ROOT / "src" / "core" / "ladder.py"
SHIPPED = json.loads((ROOT / "config" / "signals.json").read_text())
TMP = Path(tempfile.mkdtemp(prefix="check-ladder-refusals-"))


class Sheet:
    def __init__(self, quiet: bool = False) -> None:
        self.bad = 0
        self.quiet = quiet

    def row(self, what: str, got, want) -> None:
        good = got == want
        self.bad += not good
        if not self.quiet:
            print(f"    {what:<62} {'ok' if good else f'<-- WRONG: {got!r}, wanted {want!r}'}")


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
    path = TMP / name
    path.write_text(raw if isinstance(raw, str) else json.dumps(raw))
    return path


def broken(change) -> dict:
    raw = copy.deepcopy(SHIPPED)
    change(raw)
    return raw


def a_kind(raw: dict) -> str:
    return next(iter(raw["kinds"]))


CASES = [
    # (what, file name, contents, words the sentence must carry)
    ("invalid JSON: refused as such, naming the file", "bad.json", '{"kinds": ',
     ("bad.json", "is not valid JSON")),
    ("no 'kinds' object", "nokinds.json", broken(lambda r: r.pop("kinds")),
     ("nokinds.json", "has no 'kinds' object")),
    ("'kinds' is a list, not an object", "listkinds.json",
     broken(lambda r: r.update(kinds=[])), ("listkinds.json", "has no 'kinds' object")),
    ("after_prompt given as a number", "ap.json",
     broken(lambda r: r.update(after_prompt=5)), ("ap.json", "'after_prompt' is 5")),
    ("look_away given as a list", "la.json",
     broken(lambda r: r.update(look_away=[1])), ("la.json", "'look_away' is [1]")),
    ("a glance of zero seconds", "lg.json",
     broken(lambda r: r["look_away"].update(glance_s=0)), ("lg.json", "look_away.glance_s is 0")),
    ("after_end given as a string", "ae.json",
     broken(lambda r: r.update(after_end="2")), ("ae.json", "'after_end' is '2'")),
    ("an LED index above u16", "led.json",
     broken(lambda r: r["kinds"][a_kind(r)].update(led=0x10000)),
     ("led.json", ".led is 65536", "an LED index is a u16 or null")),
    ("an LED index that is a bool", "ledbool.json",
     broken(lambda r: r["kinds"][a_kind(r)].update(led=True)),
     ("ledbool.json", ".led is True")),
    # Task 56 and 58: the catch's endings and the menu bar's colours.
    ("outcomes given as a list", "outlist.json",
     broken(lambda r: r.update(outcomes=[])), ("outlist.json", "'outcomes' is []")),
    ("an outcome nothing plays", "outname.json",
     broken(lambda r: r["outcomes"].update(escaped=r["outcomes"]["caught"])),
     ("outname.json", "outcomes.escaped is not an outcome")),
    ("an outcome given as a number", "outnum.json",
     broken(lambda r: r["outcomes"].update(caught=201)),
     ("outnum.json", "outcomes.caught is 201")),
    ("an outcome with no mute_effect", "outmute.json",
     broken(lambda r: r["outcomes"]["broke_out"].pop("mute_effect")),
     ("outmute.json", "outcomes.broke_out has no 'mute_effect'")),
    ("an outcome lasting zero seconds", "outlast.json",
     broken(lambda r: r["outcomes"]["caught"].update(lasts_s=0)),
     ("outlast.json", "outcomes.caught.lasts_s is 0")),
    ("an outcome lasting True seconds", "outlastb.json",
     broken(lambda r: r["outcomes"]["caught"].update(lasts_s=True)),
     ("outlastb.json", "outcomes.caught.lasts_s is True")),
    # Task 68: the silence holds a light and makes no sound.
    ("an outcome silent as a string", "outsilent.json",
     broken(lambda r: r["outcomes"]["silenced"].update(silent="yes")),
     ("outsilent.json", "outcomes.silenced.silent is 'yes'")),
    ("a silent outcome that names a Mac sound", "outsilentmac.json",
     broken(lambda r: r["outcomes"]["silenced"].update(
         mac_sound="/System/Library/Sounds/Tink.aiff")),
     ("outsilentmac.json", "outcomes.silenced is silent and names a mac_sound")),
    ("an outcome's light out of range", "outlight.json",
     broken(lambda r: r["outcomes"]["silenced"].update(light=-1)),
     ("outlight.json", "outcomes.silenced.light")),
    ("a tint with no # (seven hex digits instead)", "tint.json",
     broken(lambda r: r["kinds"]["needs"].update(tint="0FFB000")),
     ("tint.json", "needs.tint is '0FFB000'", "#RRGGBB")),
    ("a tint that is not hex", "tinthex.json",
     broken(lambda r: r["outcomes"]["caught"].update(tint="#GGGGGG")),
     ("tinthex.json", "outcomes.caught.tint is '#GGGGGG'")),
    ("a tint too short", "tintlen.json",
     broken(lambda r: r["voices"]["pikachu"].update(tint="#FFF")),
     ("tintlen.json", "voices.pikachu.tint is '#FFF'")),
    # Tasks 57 and 64: the pools a done cries from, and the numbers that pick them.
    ("cries given as a number", "crynum.json",
     broken(lambda r: r["voices"]["pikachu"].update(cries=129)),
     ("crynum.json", "voices.pikachu.cries is 129", "an object naming pools")),
    ("cries as task 57's list", "crylist.json",
     broken(lambda r: r["voices"]["pikachu"].update(cries=[20, 21])),
     ("crylist.json", "voices.pikachu.cries is a list", "the old list is 'happy'")),
    ("a pool nothing picks", "crypool.json",
     broken(lambda r: r["voices"]["pikachu"]["cries"].update(angry=[20])),
     ("crypool.json", "voices.pikachu.cries.angry is not a pool")),
    ("happy with only one in it", "cryone.json",
     broken(lambda r: r["voices"]["pikachu"]["cries"].update(happy=[129])),
     ("cryone.json", "voices.pikachu.cries.happy is [129]", "belongs in 'effect'")),
    ("another pool empty", "cryempty.json",
     broken(lambda r: r["voices"]["pikachu"]["cries"].update(call=[])),
     ("cryempty.json", "voices.pikachu.cries.call is []", "at least 1 effect id")),
    ("a cry listed twice", "crytwice.json",
     broken(lambda r: r["voices"]["pikachu"]["cries"].update(happy=[20, 21, 20])),
     ("crytwice.json", "voices.pikachu.cries.happy has an id in it twice")),
    ("a cry above u16", "crybig.json",
     broken(lambda r: r["voices"]["pikachu"]["cries"].update(sad=[20, 0x10000])),
     ("crybig.json", "voices.pikachu.cries.sad[1] is 65536")),
    ("a cry that is a bool", "crybool.json",
     broken(lambda r: r["voices"]["pikachu"]["cries"].update(happy=[20, True])),
     ("crybool.json", "voices.pikachu.cries.happy[1] is True")),
    ("no happy to fall back to", "crynohappy.json",
     broken(lambda r: r["voices"]["pikachu"]["cries"].pop("happy")),
     ("crynohappy.json", "voices.pikachu.cries has no 'happy'")),
    ("proud with no long_turn_s", "cryproud.json",
     broken(lambda r: r["kinds"]["done"].pop("long_turn_s")),
     ("cryproud.json", "done has no 'long_turn_s'")),
    ("lonely with no lonely_after_s", "crylonely.json",
     broken(lambda r: r["kinds"]["done"].pop("lonely_after_s")),
     ("crylonely.json", "done has no 'lonely_after_s'")),
    ("a long turn of zero seconds", "crylong0.json",
     broken(lambda r: r["kinds"]["done"].update(long_turn_s=0)),
     ("crylong0.json", "done.long_turn_s is 0", "a positive number")),
    ("a greet lasting True seconds", "crygreetb.json",
     broken(lambda r: r["kinds"]["done"].update(greet_lasts_s=True)),
     ("crygreetb.json", "done.greet_lasts_s is True")),
    ("a time away of zero seconds", "cryaway0.json",
     broken(lambda r: r["kinds"]["done"].update(greet_away_s=0)),
     ("cryaway0.json", "done.greet_away_s is 0")),
    ("lonely no later than the last beat", "cryearly.json",
     broken(lambda r: r["kinds"]["done"].update(lonely_after_s=30)),
     ("cryearly.json", "done.lonely_after_s is 30s", "has to come later")),
    ("lonely with no last beat", "crytimes.json",
     broken(lambda r: r["kinds"]["done"].update(times=None)),
     ("crytimes.json", "done.times is null", "there is no last one")),
    ("idle given as a number", "idlenum.json",
     broken(lambda r: r.update(idle=60)), ("idlenum.json", "'idle' is 60")),
    ("idle negative", "idleneg.json",
     broken(lambda r: r["idle"].update(after_s=-1)), ("idleneg.json", "idle.after_s is -1")),
    ("idle True seconds", "idlebool.json",
     broken(lambda r: r["idle"].update(after_s=True)), ("idlebool.json", "idle.after_s is True")),
]


def refusal(ladder_mod, path: Path):
    """The sentence a refusal carries, or what happened instead."""
    try:
        ladder_mod.load(path)
    except ValueError as exc:
        return str(exc)
    except Exception as exc:              # the wrong refusal is a wrong row, not a crash
        return f"raised {type(exc).__name__}: {exc}"
    return "loaded"


def read(ladder_mod, path: Path, pick):
    """One fact off a config that must load, or what happened instead."""
    try:
        return pick(ladder_mod.load(path))
    except Exception as exc:              # a refusal here is a wrong row, not a crash
        return f"raised {type(exc).__name__}"


def table(sheet: Sheet, ladder_mod) -> None:
    shipped = written("shipped.json", SHIPPED)
    got = refusal(ladder_mod, shipped)
    sheet.row("reference: the shipped config, copied, loads clean", got, "loaded")
    for what, name, raw, words in CASES:
        said = refusal(ladder_mod, written(name, raw))
        sheet.row(what, [w for w in words if w not in said], [])
    # The optional objects really are optional: absent loads, and wait_s defaults.
    bare = broken(lambda r: [r.pop(k, None) for k in ("after_prompt", "look_away", "after_end")])
    try:
        got = ladder_mod.load(written("bare.json", bare))
        got = (got.after_prompt_s, got.look_away_s, got.glance_s, got.after_end_s)
    except Exception as exc:
        got = f"raised {exc!r}"
    sheet.row("all three optional objects absent: loads, every wait 0", got,
              (0.0, 0.0, 0.0, 0.0))
    # An LED of null is no LED, not a refusal.
    nulled = broken(lambda r: r["kinds"][a_kind(r)].update(led=None))
    sheet.row("led null: loads", refusal(ladder_mod, written("lednull.json", nulled)), "loaded")
    # A `_` key under outcomes is a note, not an outcome.
    sheet.row("outcomes' _about is a note, not an outcome",
              read(ladder_mod, written("about.json", SHIPPED),
                   lambda got: sorted(got.outcomes)),
              ["broke_out", "caught", "silenced"])
    # The pools are kept in the config's order, and a kind without them has none.
    sheet.row("done's happy loads in order; needs has no pools",
              read(ladder_mod, written("cries.json", SHIPPED),
                   lambda got: ({k.value: v for k, v in got.moods.items()}["done"]
                                .pools["happy"][:3], "needs" in {k.value for k in got.moods})),
              ((20, 32, 34), False))
    noted = broken(lambda r: r["voices"]["pikachu"]["cries"].update(_note="a note"))
    sheet.row("a _ key under cries is a note, not a pool",
              read(ladder_mod, written("crynote.json", noted),
                   lambda got: "_note" in next(iter(got.moods.values())).pools), False)
    plain = broken(lambda r: [*(v["cries"].pop("proud") for v in r["voices"].values()
                                if isinstance(v, dict)),
                              r["kinds"]["done"].pop("long_turn_s"),
                              r["kinds"]["done"].pop("greet_lasts_s")])
    sheet.row("no proud, no long_turn_s, no greet_lasts_s: loads, both None",
              read(ladder_mod, written("cryplain.json", plain),
                   lambda got: [(m.long_turn_s, m.greet_lasts_s) for m in got.moods.values()]),
              [(None, None)])
    sheet.row("greet_away_s absent: None, idle.after_s as before task 67",
              read(ladder_mod, written("crynoaway.json",
                                       broken(lambda r: r["kinds"]["done"].pop("greet_away_s"))),
                   lambda got: [m.greet_away_s for m in got.moods.values()]), [None])
    sheet.row("idle loads from the shipped config",
              read(ladder_mod, written("idle.json", SHIPPED), lambda got: got.idle_s), 60.0)
    sheet.row("idle absent: 0, off",
              read(ladder_mod, written("idlenone.json", broken(lambda r: r.pop("idle"))),
                   lambda got: got.idle_s), 0.0)
    sheet.row("idle 0 loads: off",
              read(ladder_mod, written("idle0.json",
                                       broken(lambda r: r["idle"].update(after_s=0))),
                   lambda got: got.idle_s), 0.0)
    # A tint is kept upper-case, so two spellings of one colour are one colour.
    lower = broken(lambda r: r["kinds"]["needs"].update(tint="#ffb000"))
    sheet.row("a lower-case tint loads, upper-cased",
              read(ladder_mod, written("tintlow.json", lower),
                   lambda got: next(v.tint for k, v in got.voices.items()
                                    if k.value == "needs")), "#FFB000")


MUTANTS = [
    ("invalid JSON let through as a crash",
     ("    except json.JSONDecodeError as exc:\n        raise ValueError(",
      "    except KeyError as exc:\n        raise ValueError(")),
    ("no 'kinds' check", ("    if not isinstance(kinds, dict):\n", "    if False:\n")),
    ("no after_prompt shape check", ("    if not isinstance(after_prompt, dict):\n", "    if False:\n")),
    ("no look_away shape check", ("    if not isinstance(look_away, dict):\n", "    if False:\n")),
    ("no after_end shape check", ("    if not isinstance(after_end, dict):\n", "    if False:\n")),
    ("LED range unchecked",
     ("isinstance(value, bool) or not 0 <= value <= 0xFFFF:\n        raise ValueError(f\"{path}: {where}.led",
      "isinstance(value, bool) or not 0 <= value <= 0xFFFFF:\n        raise ValueError(f\"{path}: {where}.led")),
    ("a bool LED let through",
     ("    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 0xFFFF:\n"
      "        raise ValueError(f\"{path}: {where}.led",
      "    if not isinstance(value, int) or not 0 <= value <= 0xFFFF:\n"
      "        raise ValueError(f\"{path}: {where}.led")),
    ("outcomes shape unchecked", ("    if not isinstance(given, dict):\n", "    if False:\n")),
    ("an unknown outcome let through", ("        if name not in OUTCOMES:\n", "        if False:\n")),
    ("an outcome's shape unchecked",
     ("        if not isinstance(entry, dict):\n            raise ValueError(f\"{path}: {where} is {entry!r}",
      "        if False:\n            raise ValueError(f\"{path}: {where} is {entry!r}")),
    ("_ notes read as outcomes", ("        if name.startswith(\"_\"):\n            continue\n"
                                  "        where = f\"outcomes.{name}\"",
                                  "        if False:\n            continue\n"
                                  "        where = f\"outcomes.{name}\"")),
    ("lasts_s zero let through", ("isinstance(value, bool) or value <= 0:\n        raise ValueError(\n            f\"{path}: {where}.lasts_s",
                                  "isinstance(value, bool) or value < 0:\n        raise ValueError(\n            f\"{path}: {where}.lasts_s")),
    ("a bool lasts_s let through", ("    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:\n        raise ValueError(\n            f\"{path}: {where}.lasts_s",
                                    "    if not isinstance(value, (int, float)) or value <= 0:\n        raise ValueError(\n            f\"{path}: {where}.lasts_s")),
    ("tint's # unchecked", ("or value[0] != \"#\"", "or False")),
    ("tint's digits unchecked", ("            or any(c not in \"0123456789abcdefABCDEF\" for c in value[1:])):",
                                 "            ):")),
    ("tint's length unchecked", ("len(value) != 7", "len(value) < 2")),
    ("tint not upper-cased", ("    return value.upper()\n", "    return value\n")),
    ("task 57's list not named", ("    if isinstance(value, list):\n", "    if False:\n")),
    ("cries' shape unchecked", ("    if not isinstance(value, dict):\n        raise ValueError(\n"
                                "            f\"{path}: {where}.cries",
                                "    if False:\n        raise ValueError(\n"
                                "            f\"{path}: {where}.cries")),
    ("_ notes read as pools", ("        if name.startswith(\"_\"):\n            continue\n"
                               "        at = ", "        if False:\n            continue\n"
                               "        at = ")),
    ("a pool nothing picks let through", ("        if name not in POOLS:\n", "        if False:\n")),
    ("happy of one let through", ('least = 2 if name == "happy" else 1',
                                  'least = 1')),
    ("an empty pool let through", ('least = 2 if name == "happy" else 1',
                                   'least = 2 if name == "happy" else 0')),
    ("a cry listed twice let through", ("    if len(set(got)) != len(got):\n", "    if False:\n")),
    ("no happy let through", ('    if "happy" not in pools:\n', "    if False:\n")),
    ("proud without its number", ('"long_turn_s", "proud" in pools,', '"long_turn_s", False,')),
    ("lonely without its number", ('"lonely_after_s", "lonely" in pools,',
                                   '"lonely_after_s", False,')),
    ("a zero number of seconds let through",
     ("isinstance(value, bool) or value <= 0:\n        raise ValueError(\n"
      "            f\"{path}: {where}.{key}",
      "isinstance(value, bool) or value < 0:\n        raise ValueError(\n"
      "            f\"{path}: {where}.{key}")),
    ("a bool number of seconds let through",
     ("    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:\n"
      "        raise ValueError(\n            f\"{path}: {where}.{key}",
      "    if not isinstance(value, (int, float)) or value <= 0:\n"
      "        raise ValueError(\n            f\"{path}: {where}.{key}")),
    ("lonely before the last beat let through", ("        if lonely <= last:\n",
                                                 "        if False:\n")),
    ("lonely with no last beat unexplained", ("        if times is None:\n            raise ValueError(\n"
                                              "                f\"{path}: {where}.cries.lonely",
                                              "        if False:\n            raise ValueError(\n"
                                              "                f\"{path}: {where}.cries.lonely")),
    ("idle's shape unchecked", ("    if not isinstance(idle, dict):\n", "    if False:\n")),
    ("a negative idle let through", ("isinstance(idle_s, bool) or idle_s < 0:",
                                     "isinstance(idle_s, bool) or idle_s < -5:")),
    ("a bool idle let through", ("if not isinstance(idle_s, (int, float)) or isinstance(idle_s, bool) or",
                                 "if not isinstance(idle_s, (int, float)) or")),
    ("idle never read", ("        idle_s=float(idle_s),\n", "        idle_s=0.0,\n")),
    ("idle on when absent", ('idle.get("after_s", 0.0)', 'idle.get("after_s", 60.0)')),
    ("a cry's range unchecked", ("isinstance(cry, bool) or not 0 <= cry <= 0xFFFF:",
                                 "isinstance(cry, bool) or not 0 <= cry <= 0xFFFFF:")),
    ("a bool cry let through", ("if not isinstance(cry, int) or isinstance(cry, bool) or",
                                "if not isinstance(cry, int) or")),
    ("cries never read", ("            moods[kind] = _moods(entry, path, kind.value, every[kind], times[kind])\n",
                          "            pass\n")),
    ("led null refused", ("    value = entry.get(\"led\")\n    if value is None:\n        return None\n",
                          "    value = entry.get(\"led\")\n    if False:\n        return None\n")),
]


def main() -> int:
    print(__doc__.strip().splitlines()[0])
    sheet = Sheet()
    print("\n  ladder.load")
    table(sheet, load_module())
    print("\n  mutants — each must turn at least one row wrong")
    for name, patch in MUTANTS:
        mod = load_module(patch)
        if mod is None:
            sheet.row(f"mutant: {name}", "NOT APPLIED", "caught")
            continue
        quiet = Sheet(quiet=True)
        table(quiet, mod)
        sheet.row(f"mutant: {name}", "caught" if quiet.bad else "survived", "caught")
    shutil.rmtree(TMP, ignore_errors=True)
    print("\n  " + ("ALL CASES MATCH the known answer" if not sheet.bad
                   else f"{sheet.bad} WRONG — the rows above"))
    return 1 if sheet.bad else 0


if __name__ == "__main__":
    sys.exit(main())
