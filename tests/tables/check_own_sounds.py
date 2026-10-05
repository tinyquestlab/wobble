#!/usr/bin/env python3
"""Check your own Mac sounds and the ball's cry gate (task 70), with no ball.

    venv/bin/python3 tests/tables/check_own_sounds.py

What it settles:
  - the shipped config plays wobble's own `sounds/`, read against the checkout
  - a file in assets/sounds/ named after a kind or an outcome replaces that
    one's Mac sound, and nothing else about it: the effect, the light and the
    led the ball reads are the config's
  - `silenced` is not a name, a misspelt name plays nothing, and both are said
  - two files with one name settle the same way every run, and say which plays
  - a mute still takes your sound out
  - `--cry` from anywhere but assets/cries/ is refused before anything starts,
    a `..` walk out of it included

The listening is the desk's: whether the file plays is `afplay`'s, not this.
"""
from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ["WOBBLE_PLATFORM"] = "null"          # before the seam is imported

from src import daemon                                                  # noqa: E402
from src.core.ladder import ROOT, load                                  # noqa: E402
from src.core.signals import Kind                                       # noqa: E402


class Sheet:
    def __init__(self) -> None:
        self.bad = 0

    def row(self, label: str, got, want, quiet: bool = False) -> None:
        good = got == want
        self.bad += not good
        if not quiet:
            print(f"    {label:<62} {'ok' if good else f'got {got!r}, want {want!r}'}")


def folder(tmp: Path, *names: str) -> Path:
    for name in names:
        (tmp / name).write_bytes(b"not a sound, and nothing here plays it")
    return tmp


def rows(own=daemon.own_sounds, quiet: bool = False) -> int:
    sheet = Sheet()
    ladder = load()
    if not quiet:
        print("\n  the shipped config")
    sheet.row("needs plays sounds/needs.wav, read against the checkout",
              ladder.voices[Kind.NEEDS].mac_sound, str(ROOT / "sounds" / "needs.wav"), quiet)
    sheet.row("caught plays sounds/caught.wav, the same way",
              ladder.outcomes["caught"].mac_sound, str(ROOT / "sounds" / "caught.wav"), quiet)
    sheet.row("…and both are there to play",
              [Path(ladder.voices[Kind.NEEDS].mac_sound).is_file(),
               Path(ladder.outcomes["caught"].mac_sound).is_file()], [True, True], quiet)

    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        if not quiet:
            print("\n  your own sounds")
        sheet.row("no folder: the ladder as loaded, and nothing said",
                  own(ladder, tmp / "missing"), (ladder, [], []), quiet)
        sheet.row("an empty folder: the same",
                  own(ladder, tmp), (ladder, [], []), quiet)

        mine = folder(tmp, "needs.wav", "done.m4a", "caught.aiff", "broke_out.MP3",
                      "silenced.wav", "need.wav", "done.mp3", ".DS_Store")
        got, used, ignored = own(ladder, mine)
        sheet.row("each named file plays for its own kind or outcome",
                  (got.voices[Kind.NEEDS].mac_sound, got.voices[Kind.DONE].mac_sound,
                   got.outcomes["caught"].mac_sound, got.outcomes["broke_out"].mac_sound),
                  tuple(str(mine / n) for n in
                        ("needs.wav", "done.m4a", "caught.aiff", "broke_out.MP3")), quiet)
        sheet.row("…and only the Mac sound moves: what the ball reads is the config's",
                  ({k: replace(v, mac_sound=None) for k, v in got.voices.items()},
                   {k: replace(v, mac_sound=None) for k, v in got.outcomes.items()}),
                  ({k: replace(v, mac_sound=None) for k, v in ladder.voices.items()},
                   {k: replace(v, mac_sound=None) for k, v in ladder.outcomes.items()}), quiet)
        sheet.row("silenced stays without a sound, whatever is in the folder",
                  got.outcomes["silenced"].mac_sound, None, quiet)
        sheet.row("what was used is said, by name",
                  sorted(used), ["broke_out broke_out.MP3", "caught caught.aiff",
                                 "done done.m4a", "needs needs.wav"], quiet)
        sheet.row("what plays for nothing is said, hidden files aside",
                  sorted(ignored), ["done.mp3 (done.m4a plays)", "need.wav", "silenced.wav"],
                  quiet)
        sheet.row("a mute still takes your sound out",
                  got.muted(Kind.NEEDS, got.voices[Kind.NEEDS]).mac_sound, None, quiet)
        sheet.row("the loaded ladder is not rewritten by asking",
                  ladder.voices[Kind.NEEDS].mac_sound, str(ROOT / "sounds" / "needs.wav"),
                  quiet)
    return sheet.bad


def refused(cry: str) -> tuple[int | None, str]:
    said = io.StringIO()
    with contextlib.redirect_stderr(said):
        try:
            daemon.main(["--no-ball", "--cry", cry])
        except SystemExit as stop:
            return stop.code, said.getvalue()
    return None, said.getvalue()


def gate_rows() -> int:
    sheet = Sheet()
    print("\n  the ball's cry — only one fetched into assets/cries/")
    code, said = refused(str(ROOT / "sounds" / "needs.wav"))
    sheet.row("a sound of wobble's own is refused before anything starts",
              (code, "the ball speaks only with a cry fetched there" in said), (2, True))
    sheet.row("…and the refusal says where your own sounds go",
              str(daemon.OWN_SOUNDS) in said, True)
    code, _ = refused(str(ROOT / "assets" / "cries" / ".." / ".." / "config" / "signals.json"))
    sheet.row("a .. walk out of assets/cries/ is refused too", code, 2)
    return sheet.bad


def honours_silenced(ladder, folder_):
    names = daemon.OWN_NAMES
    daemon.OWN_NAMES = names + ("silenced",)
    try:
        return daemon.own_sounds(ladder, folder_)
    finally:
        daemon.OWN_NAMES = names


def swallows_misnamed(ladder, folder_):
    got, used, _ = daemon.own_sounds(ladder, folder_)
    return got, used, []


def reaches_the_ball(ladder, folder_):
    got, used, ignored = daemon.own_sounds(ladder, folder_)
    voices = {k: replace(v, effect=0) if (v.mac_sound or "").startswith(str(folder_)) else v
              for k, v in got.voices.items()}
    return replace(got, voices=voices), used, ignored


def main() -> int:
    print(__doc__.strip().splitlines()[0])
    bad = rows() + gate_rows()
    print("\n  the control — each must break the table")
    for label, mutant in (("a silenced that chimes", honours_silenced),
                          ("a misspelt file that plays nothing, unsaid", swallows_misnamed),
                          ("your sound reaching what the ball plays", reaches_the_ball)):
        survived = rows(mutant, quiet=True) == 0
        bad += survived
        print(f"    {label:<62} "
              f"{'<-- SURVIVED, so the suite does not test it' if survived else 'caught'}")
    print("\n" + ("ALL CASES MATCH the known answer" if not bad
                  else "SOMETHING DOES NOT MATCH — the rows above, not this line"))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
