#!/usr/bin/env python3
"""Does what `src/ball/link.py` says reach the day's file, or only a terminal?

The defect this pins, measured 2026-09-23 on a 29-minute run: 34 `went unacked`
/ `never acked` lines on the terminal and 0 of them in `var/logs/`, because
`src/log.py` attached its handler to `wobble.daemon` alone and every module
logger fell through to `logging.lastResort` — stderr, WARNING and above. Its
INFO `opening replayed` was dropped in both. Principle 7: the link went quiet
for a reason nobody could see, and nobody could see it afterwards either.

Run it: venv/bin/python3 tests/tables/check_link_log.py
"""
import contextlib
import io
import logging
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src import daemon, log                                       # noqa: E402
from src.ball import link as balllink                             # noqa: E402

WIDTH = 56
rows: list[bool] = []


def row(said: str, ok: bool, detail: str = "") -> None:
    rows.append(ok)
    print(f"    {said:<{WIDTH}} " + ("ok" if ok else f"<-- WRONG: {detail}"))


def run(*, wire: bool) -> tuple[list[str], list[str]]:
    """One session's file and stderr. `wire=False` is the world before the fix."""
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
    log._rooted.clear()
    path, _ = log.start(Path(tempfile.mkdtemp()) / "logs", 14,
                        shape=daemon.shaped if wire else None)
    if not wire:
        for handler in list(root.handlers):
            root.removeHandler(handler)
        log._rooted.clear()
    # Constructed before the redirect takes effect, so the handler already holds
    # the real stderr — hence a fresh one, pointed where it can be read back.
    seen = io.StringIO()
    if wire:
        loud = logging.StreamHandler(seen)
        loud.setFormatter(log.Shaped(daemon.shaped))
        root.addHandler(loud)
    with contextlib.redirect_stderr(io.StringIO()), \
            contextlib.redirect_stdout(io.StringIO()):
        balllink.log.warning("effect 213: %s went unacked in %.1fs — attempt %d/%d",
                             "030200d500", 5.0, 1, 3)
        balllink.log.info("opening replayed — %d input packet(s) so far", 7)
        daemon.say("slot", "the cry is in — 17 frames, 6.8s", project="wobble")
    return path.read_text().splitlines(), seen.getvalue().splitlines()


print(__doc__.splitlines()[0])
print()
print("  what the link says, once the root is wired")
body, terminal = run(wire=True)
row("a lost frame is in the file at all",
    any("went unacked" in l for l in body), body)
row("…and it carries the time it happened",
    any(l.startswith(("0", "1", "2")) and "went unacked" in l for l in body), body)
row("…tagged by module and level, so it reads like the rest",
    any("link warning" in l for l in body), body)
# `say` lays out `{stamp:8}  {project:<22}{what:<22}{detail}`, so the third
# column opens at 32 whatever is in the first two. A line that is merely in
# the file but not in the columns is one a person stops reading past.
row("…in the same columns `say` uses",
    all(l[31] == " " and l[32] != " " for l in body), body)
row("an INFO the terminal never showed is kept too",
    any("opening replayed" in l for l in body), body)
row("…and the terminal still gets the loud one",
    any("went unacked" in l for l in terminal), terminal)
row("`say`'s own line is still byte for byte what it printed",
    any(l.endswith("the cry is in — 17 frames, 6.8s") and "wobble" in l
        for l in body), body)
row("…and is not repeated by the wiring",
    sum("17 frames" in l for l in body) == 1, body)

print()
print("  the control — the wiring removed, which must break every row above")
before, before_err = run(wire=False)
row("the lost frame is nowhere in the file", not any("went unacked" in l
                                                     for l in before), before)
row("…and the INFO is nowhere at all",
    not any("opening replayed" in l for l in before + before_err), before)
row("…while `say`'s line is written exactly as before",
    any("17 frames" in l for l in before), before)

print()
print("ALL CASES MATCH the known answer" if all(rows)
      else "SOMETHING DOES NOT — the rows above, not this line")
sys.exit(0 if all(rows) else 1)
