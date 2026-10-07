#!/usr/bin/env python3
"""Check which cry `tools/fetch_cry.py` fetches, where it writes it, and that the install fetches each voice.

    venv/bin/python3 tests/tables/check_fetch_cry.py

The voices are the partners, Pikachu and Eevee, by National Dex number (spec 04,
task 01): `--voice` names one, `--dex` any other Pokémon, written under its
number so it never takes a voice's file.

**Nothing here touches the network or `assets/cries/`.** Each run of `main()`
is pointed at a file that is already there, so it stops at "kept" before any
download.

**The control is mutants**, as in `check_permissions.py`: one rule's text in
`fetch_cry.target` or in `install.sh` replaced, the table re-run. A mutant whose
text is gone is reported wrong.
"""
from __future__ import annotations

import __future__
import contextlib
import importlib.util
import inspect
import io
import re
import sys
import tempfile
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("fetch_cry", ROOT / "tools" / "fetch_cry.py")
fetch_cry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch_cry)
INSTALL = (ROOT / "install.sh").read_text()
CRIES = fetch_cry.CRIES


class Sheet:
    def __init__(self, quiet: bool = False) -> None:
        self.quiet, self.bad, self.rows = quiet, 0, 0

    def head(self, text: str) -> None:
        if not self.quiet:
            print(f"\n  {text}")

    def row(self, what: str, got, want) -> None:
        good = got == want
        self.bad += not good
        self.rows += 1
        if not self.quiet:
            print(f"    {what:<70} {'ok' if good else f'<-- WRONG: {got!r}, wanted {want!r}'}")


def attempt(call):
    try:
        return call()
    except Exception as exc:                                          # noqa: BLE001
        return f"raised {type(exc).__name__}: {exc}"


def run(*argv: str) -> tuple[object, str]:
    """`main()` with these arguments: its exit, and what it printed."""
    out, err = io.StringIO(), io.StringIO()
    saved = sys.argv
    sys.argv = ["fetch_cry.py", *argv]
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = fetch_cry.main()
    except SystemExit as exc:
        code = exc.code
    finally:
        sys.argv = saved
    return code, out.getvalue() + err.getvalue()


def installed_voices(install: str) -> list[str]:
    """The voices install.sh loops over, if each one is fetched by `--voice` and may fail."""
    loop = re.search(r"^for voice in ([\w ]+); do\n(.*?)^done$", install, re.M | re.S)
    if not loop:
        return []
    body = loop.group(2)
    if 'fetch_cry.py --voice "$voice" ||' not in body:
        return []
    return loop.group(1).split()


def table(sheet: Sheet, install: str = INSTALL) -> None:
    sheet.head("which cry, and where it goes")
    sheet.row("the voices are exactly the two partners",
              fetch_cry.VOICES, {"pikachu": 25, "eevee": 133})
    sheet.row("no voice named → Pikachu, into pikachu.wav",
              attempt(lambda: fetch_cry.target("pikachu", None, None)), (25, CRIES / "pikachu.wav"))
    sheet.row("--voice eevee → dex 133, into eevee.wav",
              attempt(lambda: fetch_cry.target("eevee", None, None)), (133, CRIES / "eevee.wav"))
    sheet.row("--dex 16 → into 16.wav, never pikachu.wav",
              attempt(lambda: fetch_cry.target("pikachu", 16, None)), (16, CRIES / "16.wav"))
    sheet.row("--dex 16 with --voice eevee → the dex wins",
              attempt(lambda: fetch_cry.target("eevee", 16, None)), (16, CRIES / "16.wav"))
    sheet.row("--voice eevee --out x.wav → Eevee, into x.wav",
              attempt(lambda: fetch_cry.target("eevee", None, Path("x.wav"))), (133, Path("x.wav")))
    sheet.row("--dex 16 --out x.wav → 16, into x.wav",
              attempt(lambda: fetch_cry.target("pikachu", 16, Path("x.wav"))), (16, Path("x.wav")))
    names = {attempt(lambda v=v: fetch_cry.target(v, None, None))[1] for v in fetch_cry.VOICES}
    sheet.row("each voice has a file of its own", len(names), len(fetch_cry.VOICES))

    sheet.head("the command line")
    with tempfile.TemporaryDirectory() as tmp:
        there = Path(tmp) / "cry.wav"
        there.write_bytes(b"already here")
        code, said = run("--voice", "eevee", "--out", str(there))
        sheet.row("--voice eevee onto a file already there → exit 0", code, 0)
        sheet.row("… says it was kept", "already there — kept" in said, True)
        sheet.row("… and leaves it as it was", there.read_bytes(), b"already here")
        code, said = run("--voice", "charmander", "--out", str(there))
        sheet.row("--voice charmander → refused by the command line (exit 2)", code, 2)
        sheet.row("… naming the voices there are", "eevee" in said and "pikachu" in said, True)

    sheet.head("install.sh")
    voices = installed_voices(install)
    sheet.row("fetches every voice, by --voice, and goes on if one fails",
              sorted(voices), sorted(fetch_cry.VOICES))
    sheet.row("the old Pikachu-only call is gone", "tools/fetch_cry.py ||" in install, False)


MUTANTS = [
    ("--voice ignored", "target", "VOICES[voice]", 'VOICES["pikachu"]'),
    ("--dex written over pikachu.wav", "target", 'CRIES / f"{dex}.wav"', 'CRIES / "pikachu.wav"'),
    ("--out ignored for a voice", "target", 'out or CRIES / f"{voice}.wav"', 'CRIES / f"{voice}.wav"'),
    ("--dex ignored", "target", "if dex is None:", "if True:"),
    ("install fetches Pikachu only", "install.sh", "for voice in pikachu eevee; do", "for voice in pikachu; do"),
    ("install stops on a failed fetch", "install.sh", '--voice "$voice" || echo', '--voice "$voice" && echo'),
]


def mutate(old: str, new: str):
    """`target` recompiled with `old` replaced, in fetch_cry's own globals; None if stale."""
    source = textwrap.dedent(inspect.getsource(fetch_cry.target))
    if source.count(old) != 1:
        return None
    local: dict = {}
    code = compile(source.replace(old, new), fetch_cry.__file__, "exec",
                   flags=__future__.annotations.compiler_flag, dont_inherit=True)
    exec(code, fetch_cry.__dict__, local)                             # noqa: S102
    return local["target"]


def mutants(sheet: Sheet) -> None:
    sheet.head("mutants — each rule removed in turn must make a row wrong")
    for name, where, old, new in MUTANTS:
        original = fetch_cry.target
        install = INSTALL
        if where == "install.sh":
            stale = INSTALL.count(old) != 1
            install = INSTALL.replace(old, new)
        else:
            broken = mutate(old, new)
            stale = broken is None
        if stale:
            sheet.row(f"mutant: {name}", f"stale: its text is not in {where} once", "caught")
            continue
        if where != "install.sh":
            fetch_cry.target = broken
        quiet = Sheet(quiet=True)
        try:
            table(quiet, install)
        except Exception:                                             # noqa: BLE001
            quiet.bad += 1
        finally:
            fetch_cry.target = original
        verdict = "caught" if quiet.bad else "survived"
        sheet.rows += 1
        sheet.bad += verdict != "caught"
        print(f"    {'mutant: ' + name:<70} {verdict}"
              + ("" if verdict == "caught" else "  <-- the table does not test it"))


def main() -> int:
    print(__doc__.strip().splitlines()[0])
    sheet = Sheet()
    table(sheet)
    mutants(sheet)
    print(f"\n{sheet.rows} rows, " + ("ALL CASES MATCH the known answer" if not sheet.bad else
                                       f"{sheet.bad} WRONG — the rows above, not this line"))
    return 0 if not sheet.bad else 1


if __name__ == "__main__":
    sys.exit(main())
