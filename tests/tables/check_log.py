#!/usr/bin/env python3
"""Check the daily log: the name, the copy, midnight, and what gets deleted.

    venv/bin/python3 tests/tables/check_log.py

Every run here happens in a throwaway directory and the clock is handed in, so
the one rule that only exists in the passage of time — midnight — is reachable
without waiting for it. `Daily` takes its clock as an argument for exactly this
reason; a check that had to read the code to believe in the rolling would be
proving the code says what it says.

Eight claims, each with a mutant that must break it:

  - the file is named after the day, and the day is read as each line is written
  - what is in the file is what the terminal got, character for character
  - crossing midnight opens tomorrow's file and leaves yesterday's alone
  - a day nothing was said on has no file, rather than an empty one
  - the sweep goes by the date in the NAME, never by the mtime
  - …and leaves anything that is not one of ours where it is
  - keeping 0 days keeps everything
  - the log follows the events file, so a desk run cannot write into the record

And task 89's `signals.tsv`, one row per ended signal kept past the fortnight —
three claims, each with its own mutant of `log.ended`:

  - one header, then one row per end, fields as the daemon handed them
  - an end with a name that is not ours is filed as `other`, never as itself
  - a file it cannot write says so in words, the way `start` does — and the sweep
    leaves the file where it is, a claim the sweep's own mutants already break

Plus an end-to-end leg: a real daemon, `--no-ball --no-menubar`, against a
throwaway events file. What it proves is the join — that the file it wrote is
its own stdout, and that `var/logs` was not touched by a check running beside
the daemon somebody is actually using. That last one is not hypothetical: every
desk check in this directory was writing into the live `var/events` until
2026-09-22, and this is the same mistake with a different file.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
import time
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src import log                                                    # noqa: E402

DAY = date(2026, 9, 23)
NEXT = DAY + timedelta(days=1)


class Sheet:
    def __init__(self, quiet: bool = False):
        self.quiet, self.bad = quiet, 0

    def row(self, what: str, got, want) -> None:
        good = want(got) if callable(want) else got == want
        self.bad += not good
        if not self.quiet:
            print(f"    {what:<56} "
                  f"{'ok' if good else f'<-- WRONG: {got!r}'}")

    def ok(self) -> bool:
        return not self.bad


def box() -> Path:
    return Path(tempfile.mkdtemp(prefix="wobble-log-check-"))


def lines_of(path: Path) -> list[str]:
    return path.read_text().splitlines() if path.exists() else []


def names_in(directory: Path) -> list[str]:
    return sorted(p.name for p in directory.iterdir()) if directory.exists() else []


def plant(directory: Path, name: str, *, days_old: int = 0) -> Path:
    """A file already in the log directory, optionally with an old mtime.

    The mtime is the whole point of two of the rows below: a directory that has
    been copied, restored from a backup or synced carries mtimes from the copy,
    so every file in it looks like it was written today — and a sweep that
    believed them would keep everything forever, while one that believed the
    opposite would take the lot.
    """
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text("planted\n")
    if days_old:
        when = time.time() - days_old * 86400
        os.utime(path, (when, when))
    return path


def rows(make, quiet: bool = False) -> bool:
    """The table. `make(directory, keep_days, clock)` builds the handler under
    test, so a mutant runs through exactly these rows and not a copy of them."""
    sheet = Sheet(quiet)
    say = (lambda _: None) if quiet else print

    # ---- the name, and when the day is decided -----------------------------
    say("\n  the file is named after the day")
    here = box() / "logs"
    clock = [DAY]
    handler = make(here, 14, lambda: clock[0])
    handler.handle(logging.LogRecord("x", logging.INFO, "", 0,
                                     "08:44:56  wobble                queued                done", (), None))
    sheet.row("one line makes one file, named for today",
              names_in(here), ["wobble-2026-09-23.log"])
    sheet.row("…holding exactly the string it was handed",
              lines_of(here / "wobble-2026-09-23.log"),
              ["08:44:56  wobble                queued                done"])

    # ---- midnight ----------------------------------------------------------
    # The rule that only exists in time, and the reason the clock is a
    # parameter. A daemon is a process that runs for days.
    say("\n  midnight, with the daemon never restarted")
    clock[0] = NEXT
    handler.handle(logging.LogRecord("x", logging.INFO, "", 0,
                                     "00:00:04  play (beat)           effect 213", (), None))
    sheet.row("the next line goes into the next day's file",
              names_in(here), ["wobble-2026-09-23.log", "wobble-2026-09-24.log"])
    sheet.row("…and yesterday's is left exactly as it was",
              lines_of(here / "wobble-2026-09-23.log"),
              ["08:44:56  wobble                queued                done"])
    sheet.row("…with the new line in the new file, alone",
              lines_of(here / "wobble-2026-09-24.log"),
              ["00:00:04  play (beat)           effect 213"])
    handler.close()

    # ---- a quiet day -------------------------------------------------------
    say("\n  a day nothing happened on")
    quietly = box() / "logs"
    idle = make(quietly, 14, lambda: DAY)
    sheet.row("a handler nobody wrote to still makes no file",
              names_in(quietly), [])
    idle.close()

    # ---- the sweep ---------------------------------------------------------
    # Two ways to be wrong in opposite directions, so both are asked. The mtime
    # is the tempting one because it needs no parsing.
    say("\n  what gets deleted, and by which clock")
    old = box() / "logs"
    plant(old, "wobble-2026-09-01.log", days_old=0)       # old name, fresh mtime
    plant(old, "wobble-2026-09-22.log", days_old=400)     # fresh name, old mtime
    plant(old, "notes.txt", days_old=400)
    plant(old, "wobble-backup.log", days_old=400)
    plant(old, log.SIGNALS, days_old=400)
    swept = make(old, 14, lambda: DAY)
    swept.open_for(DAY)
    sheet.row("the one whose NAME is old goes, whatever its mtime says",
              "wobble-2026-09-01.log" in names_in(old), False)
    sheet.row("…the one whose name is recent stays, whatever its mtime says",
              "wobble-2026-09-22.log" in names_in(old), True)
    sheet.row("…a file that is not ours is not ours to delete",
              [n for n in names_in(old) if not n.startswith("wobble-2")],
              ["notes.txt", "signals.tsv", "wobble-backup.log"])
    sheet.row("…and the signals kept past the fortnight stay (task 89)",
              "signals.tsv" in names_in(old), True)
    sheet.row("…and it says what it removed rather than doing it quietly",
              swept.swept, ["wobble-2026-09-01.log"])
    swept.close()

    say("\n  keeping everything")
    forever = box() / "logs"
    plant(forever, "wobble-2019-01-01.log")
    keeper = make(forever, 0, lambda: DAY)
    keeper.open_for(DAY)
    sheet.row("0 days is 'keep the lot', not 'keep none'",
              "wobble-2019-01-01.log" in names_in(forever), True)
    keeper.close()

    return sheet.ok()


AT = datetime(2026, 9, 23, 8, 44, 56)


def kept(ended, quiet: bool = False) -> bool:
    """Task 89's table. `ended` is `log.ended` or a mutant of it, writing where
    `log.start` last pointed it — the module's own state, as the daemon has it."""
    sheet = Sheet(quiet)
    say = (lambda _: None) if quiet else print

    say("\n  signals.tsv, kept past the fortnight (task 89)")
    here = box() / "logs"
    log.start(here, 14, lambda: DAY)
    said = [ended("needs", 25.4, 7, 3, "answered", clock=lambda: AT),
            ended("done", 4520, 2, 0, "teleported", clock=lambda: AT)]
    rows = lines_of(here / log.SIGNALS)
    sheet.row("one header, then a row per end, beside the logs",
              [r.split("\t")[0] for r in rows], ["date", "2026-09-23", "2026-09-23"])
    sheet.row("…the row as handed: when, kind, seconds, beats, heard, how",
              rows[1:2], ["2026-09-23\t08:44:56\tneeds\t25\t7\t3\tanswered"])
    sheet.row("…an end that is not one of ours filed as other",
              [r.rsplit("\t", 1)[-1] for r in rows[2:]], ["other"])
    sheet.row("…and nothing to say when it was written",
              said, [None, None])

    say("\n  signals.tsv that cannot be written")
    wall = box() / "logs"
    log.start(wall, 14, lambda: DAY)
    (wall / log.SIGNALS).mkdir()                   # a directory where the file goes
    words = ended("done", 9, 0, 0, "there", clock=lambda: AT)
    sheet.row("no traceback, and it says why, in words",
              words is not None and "are not kept" in words, True)
    return sheet.ok()


# --- the mutants -------------------------------------------------------------

def header_every_row(kind, waited_s, beats, heard, how, clock=datetime.now):
    """The header written with every row. Opens fine in a spreadsheet glance and
    turns every second line of a fortnight's count into a row named 'date'."""
    at = clock()
    row = (at.date().isoformat(), at.strftime("%H:%M:%S"), kind, f"{waited_s:.0f}",
           str(beats), str(heard), how if how in log.HOWS else "other")
    try:
        with log._signals.open("a", encoding="utf-8") as out:
            out.write("\t".join(log.COLUMNS) + "\n")
            out.write("\t".join(row) + "\n")
    except OSError as exc:
        return f"{log._signals} — {exc.strerror or exc}; the signals are not kept"
    return None


def any_how(kind, waited_s, beats, heard, how, clock=datetime.now):
    """Files whatever end it was handed. One typo in the daemon and the column
    the whole file exists to count grows a value nobody will group by."""
    at = clock()
    row = (at.date().isoformat(), at.strftime("%H:%M:%S"), kind, f"{waited_s:.0f}",
           str(beats), str(heard), how)
    try:
        new = not log._signals.exists()
        with log._signals.open("a", encoding="utf-8") as out:
            if new:
                out.write("\t".join(log.COLUMNS) + "\n")
            out.write("\t".join(row) + "\n")
    except OSError as exc:
        return f"{log._signals} — {exc.strerror or exc}; the signals are not kept"
    return None


def keeps_quiet(kind, waited_s, beats, heard, how, clock=datetime.now):
    """A failure swallowed. The daemon carries on, as it should — and nobody
    learns that a fortnight from now there will be nothing to read."""
    at = clock()
    row = (at.date().isoformat(), at.strftime("%H:%M:%S"), kind, f"{waited_s:.0f}",
           str(beats), str(heard), how if how in log.HOWS else "other")
    try:
        new = not log._signals.exists()
        with log._signals.open("a", encoding="utf-8") as out:
            if new:
                out.write("\t".join(log.COLUMNS) + "\n")
            out.write("\t".join(row) + "\n")
    except OSError:
        return None
    return None



class PinsTheDayAtStartup(log.Daily):
    """Reads the clock once, in the constructor. Correct on any run short enough
    to check by hand, and wrong for exactly as long as the daemon stays up —
    which is the way it is meant to be used."""

    def __init__(self, directory, keep_days=log.KEEP_DAYS, clock=log.today):
        super().__init__(directory, keep_days, clock)
        self.frozen = clock()

    def emit(self, record):
        try:
            self.open_for(self.frozen)
            self.stream.write(self.format(record) + "\n")
        except Exception:
            self.handleError(record)


class SweepsByMtime(log.Daily):
    """Deletes by how old the file looks on disk. Needs no parsing, reads
    perfectly well, and empties the whole directory the first time it is
    restored from a backup — every mtime is the restore's."""

    def sweep(self, day):
        if self.keep_days <= 0:
            return []
        cutoff = time.time() - self.keep_days * 86400
        gone = []
        for path in sorted(self.directory.glob(f"{log.NAME}-*.log")):
            if path.stat().st_mtime < cutoff:
                path.unlink()
                gone.append(path.name)
        return gone


class SweepsEverything(log.Daily):
    """Globs the directory instead of matching the name. The blast radius is
    whatever else anybody ever put next to the logs."""

    def sweep(self, day):
        if self.keep_days <= 0:
            return []
        oldest = day - timedelta(days=self.keep_days - 1)
        gone = []
        for path in sorted(self.directory.iterdir()):
            its_day = log.day_of(path)
            if its_day is not None and its_day >= oldest:
                continue
            path.unlink()
            gone.append(path.name)
        return gone


class AddsItsOwnPrefix(log.Daily):
    """A formatter with logging's own furniture on it. Every line is still there
    and still readable — and the file has stopped being the same evidence as the
    screen, which is the only reason to trust either of them."""

    def __init__(self, directory, keep_days=log.KEEP_DAYS, clock=log.today):
        super().__init__(directory, keep_days, clock)
        self.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))


class KeepsNothing(log.Daily):
    """`keep_days <= 0` read as 'keep zero days'. The most defensible reading of
    the number, and it deletes today's file on the way past."""

    def sweep(self, day):
        oldest = day - timedelta(days=max(self.keep_days, 1) - 1)
        gone = []
        for path in sorted(self.directory.glob(f"{log.NAME}-*.log")):
            its_day = log.day_of(path)
            if its_day is None or its_day >= oldest:
                continue
            path.unlink()
            gone.append(path.name)
        return gone


def main() -> int:
    print(__doc__.strip().splitlines()[0])
    ok = rows(log.Daily)

    # ---- where the log goes, which is the desk-check rule -------------------
    print("\n  the log follows the events file")
    where = Sheet()
    where.row("var/events logs into var/logs",
              log.beside(ROOT / "var" / "events"), ROOT / "var" / "logs")
    sandbox = Path(tempfile.mkdtemp(prefix="wobble-sandbox-")) / "events"
    where.row("…and a throwaway events file logs into its own tree",
              log.beside(sandbox), sandbox.resolve().parent / "logs")
    where.row("…so the two are never the same directory",
              log.beside(sandbox) != log.beside(ROOT / "var" / "events"), True)
    ok &= where.ok()

    # ---- a log that cannot be written ---------------------------------------
    # Principle 7 does not apply to this file — it is not the signal — so the
    # answer is a complaint and a daemon that carries on, not an exception.
    print("\n  a directory it cannot make")
    blocked = box() / "wall"
    blocked.write_text("not a directory\n")
    path, said = log.start(blocked / "logs", 14, lambda: DAY)
    refusal = Sheet()
    refusal.row("no file, and no traceback either", path, None)
    refusal.row("…and it says why, in words", "nothing is being written down" in said, True)
    ok &= refusal.ok()

    # ---- the end-to-end leg --------------------------------------------------
    print("\n  a real daemon, and the file it actually wrote")
    tree = box()
    events = tree / "events"
    events.touch()
    before = names_in(ROOT / "var" / "logs")
    daemon = subprocess.Popen(
        [sys.executable, "-m", "src.daemon", "--no-ball",
         "--no-menubar", "--poll", "0.1", "--events", str(events)],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, env={**os.environ, "PYTHONUNBUFFERED": "1"})
    time.sleep(2.0)
    daemon.terminate()
    out = daemon.communicate(timeout=10)[0]
    written = sorted((tree / "logs").glob("*.log"))
    live = Sheet()
    live.row("it made one file, in its own tree",
             [p.name for p in written], [f"wobble-{date.today():%Y-%m-%d}.log"])
    # The load-bearing one. Five checks parse this stdout, so a file that says
    # something else is a second version of events with equal standing.
    said_on_screen = [line for line in out.splitlines() if line != "stopped."]
    live.row("…character for character what the terminal said",
             lines_of(written[0]) if written else [], said_on_screen)
    live.row("…and it says at startup where that file is",
             sum("  log  " in line for line in out.splitlines()), 1)
    # The whole reason `beside` exists.
    live.row("…and the real var/logs was not touched",
             names_in(ROOT / "var" / "logs"), before)
    ok &= live.ok()

    ok &= kept(log.ended)

    print("\n  the control — every rule removed in turn, each must break the table")
    controls = (
        ("a day chosen once, when the daemon started", PinsTheDayAtStartup),
        ("a sweep that believes the mtime", SweepsByMtime),
        ("a sweep with no idea whose files these are", SweepsEverything),
        ("a file that no longer matches the screen", AddsItsOwnPrefix),
        ("'keep 0 days' read as 'keep nothing'", KeepsNothing),
    )
    for what, mutant in controls:
        survived = rows(mutant, quiet=True)
        ok &= not survived
        print(f"    {what:<56} "
              f"{'<-- SURVIVED' if survived else 'caught'}")
    for what, mutant in (("signals.tsv with a header on every row", header_every_row),
                         ("an end filed under any name it is handed", any_how),
                         ("signals.tsv that fails without a word", keeps_quiet)):
        survived = kept(mutant, quiet=True)
        ok &= not survived
        print(f"    {what:<56} "
              f"{'<-- SURVIVED' if survived else 'caught'}")

    print("\n" + ("ALL CASES MATCH the known answer" if ok else
                  "SOMETHING DOES NOT — the rows above, not this line"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
