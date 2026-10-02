"""Everything the daemon says, written down as well, one file per day.

    var/logs/wobble-2026-09-23.log

The terminal is still the primary instrument and stays that way: `say()` prints
exactly what it always printed, byte for byte, because five desk checks parse
that stdout. This is the second copy, for the one question a terminal cannot
answer — what happened while nobody was looking at it.

**One file per day, named after the day, chosen as each line is written.** The
shape Laravel's `daily` channel has, and asked for by name. The stdlib's
`TimedRotatingFileHandler` rotates the other way round — a live `wobble.log`
renamed to `wobble.log.2026-09-22` on rollover — so today's lines sit in a file
whose name says nothing and yesterday's move after the fact. Naming by the day
means the file you want is the file you can guess.

**Nothing here runs on a timer.** The day is read from the clock as each line is
written, so a daemon quiet across midnight rolls on its first line after it
rather than at it, and a day with no lines in it has no file at all. That is the
truth about the day rather than an empty page suggesting otherwise.

**It deletes old files, and the age comes from the name and not the mtime.** A
directory that has been copied or restored carries mtimes from the copy, and
sweeping by those would take the whole history in one pass. Anything whose name
does not parse as one of ours is left alone.

**It is not only `say`'s copy.** Everything else in the package logs to its own
module logger, and until `start` wired the root up those records fell through
to `logging.lastResort` — stderr, WARNING and above, and never this file.
Measured 2026-09-23 on a 29-minute run: 34 `went unacked` / `never acked` lines
from `src.ball.link` on the terminal, 0 of them in the day's file, and its INFO
`opening replayed` dropped in both. The link's own account of itself, which its
counters' comment insists somebody read, was going nowhere anybody could read
it — principle 7 arriving as an absence rather than as a silence.

Those records reach the file through `write` like everything else, by way of
`Relay`. One writer, so `Daily` keeps its single promise: the string it is
handed is the string in the file.

**A log that cannot be written is never a reason to stop notifying anybody.**
Principle 7 is about silence where a person expected a signal; this file is not
that, and a full disk must cost a line of complaint rather than the afternoon.
So `start` hands back words for the daemon to say instead of raising.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date, datetime, timedelta
from pathlib import Path

NAME = "wobble"

# Laravel's own default, and a fortnight is the span over which "was it doing
# this last week too?" is still a question somebody asks.
KEEP_DAYS = 14

# What `say` writes to. Everything else reaches this file through the root.
_log = logging.getLogger("wobble.daemon")
_log.setLevel(logging.INFO)
# Nothing of this belongs to anybody else's logging setup, and with no handler
# attached an INFO record is dropped rather than falling through to
# `logging.lastResort` — which is how `write` is a no-op until `start` is called.
_log.propagate = False

# The packages whose INFO is ours to keep. Everything else — bleak, asyncio,
# CoreBluetooth — reaches the handlers at WARNING and above through the root's
# own default level, which is what to want from a library: its complaints and
# not its narration.
OURS = ("src", NAME)

# The handlers `start` put on the root logger, remembered so a second call can
# take them off again. `var/desk/check_log.py` calls `start` a dozen times in
# one process, and a handler left behind writes every later line twice.
_rooted: list[logging.Handler] = []


def plain(record: logging.LogRecord) -> str:
    """A record from anywhere but `say`, when no caller laid out the columns."""
    return (f"{datetime.fromtimestamp(record.created):%H:%M:%S}  "
            f"{record.levelname.lower()} {record.name}: {record.getMessage()}")


class Shaped(logging.Formatter):
    """Those records, laid out by whoever owns the columns — see `start`."""

    def __init__(self, shape: Callable[[logging.LogRecord], str] | None = None):
        super().__init__()
        self.shape = shape or plain

    def format(self, record: logging.LogRecord) -> str:
        return self.shape(record)


class Relay(logging.Handler):
    """A record from elsewhere in the package, turned into one of `say`'s lines.

    It goes down the same path as the rest, rather than a second handler on the
    same file: `Daily` is a verbatim copier and it stays one. `write` logs to
    `_log`, which does not propagate, so nothing here comes back round.
    """

    def __init__(self, shape: Callable[[logging.LogRecord], str] | None = None):
        super().__init__(logging.NOTSET)
        self.formatter = Shaped(shape)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            write(self.format(record))
        except Exception:
            self.handleError(record)


def today() -> date:
    """Local, because the stamps in the lines are local. A file whose name is a
    UTC day holding lines timed in another one is a trap laid for one evening a
    year."""
    return date.today()


def filename(day: date) -> str:
    return f"{NAME}-{day:%Y-%m-%d}.log"


def day_of(path: Path) -> date | None:
    """The day a file belongs to, or `None` when the name is not one of ours.

    Asked before deleting, so "not ours" has to genuinely mean not ours: a file
    somebody dropped in this directory is left where it is rather than swept up
    as debris.
    """
    name = path.name
    if not (name.startswith(f"{NAME}-") and name.endswith(".log")):
        return None
    try:
        return datetime.strptime(name[len(NAME) + 1:-len(".log")], "%Y-%m-%d").date()
    except ValueError:
        return None


class Daily(logging.Handler):
    """One file per day, opened on that day's first line."""

    def __init__(self, directory: Path, keep_days: int = KEEP_DAYS,
                 clock: Callable[[], date] = today) -> None:
        super().__init__(logging.INFO)
        # The line already carries its own stamp and its own columns — the same
        # string the terminal got. Anything logging would add here would make
        # the two copies differ, and then one of them is the real one.
        self.setFormatter(logging.Formatter("%(message)s"))
        self.directory = Path(directory)
        self.keep_days = keep_days
        # Passed in rather than read from the clock inside, because the one rule
        # here that only exists in the passage of time is midnight, and a check
        # that cannot reach midnight proves the rolling by reading the code.
        self.clock = clock
        self.day: date | None = None
        self.stream = None
        self.swept: list[str] = []

    @property
    def path(self) -> Path:
        return self.directory / filename(self.day or self.clock())

    def open_for(self, day: date) -> None:
        """Point at that day's file, sweeping what has aged out of the window."""
        if day == self.day and self.stream is not None:
            return
        if self.stream is not None:
            self.stream.close()
        self.directory.mkdir(parents=True, exist_ok=True)
        # Line buffered: the terminal is live, and a copy running a buffer
        # behind it loses the last thing said before a crash — which is exactly
        # the thing somebody opens this file to read.
        self.stream = open(self.directory / filename(day), "a",
                           buffering=1, encoding="utf-8")
        self.day = day
        self.swept = self.sweep(day)

    def sweep(self, day: date) -> list[str]:
        """Delete the files older than the window. `keep_days <= 0` keeps all."""
        if self.keep_days <= 0:
            return []
        oldest = day - timedelta(days=self.keep_days - 1)
        gone = []
        for path in sorted(self.directory.glob(f"{NAME}-*.log")):
            its_day = day_of(path)
            if its_day is None or its_day >= oldest:
                continue
            try:
                path.unlink()
            except OSError:
                # A second daemon got there first, or the file is not ours to
                # remove. Either way it is not worth ending a run over.
                continue
            gone.append(path.name)
        return gone

    def emit(self, record) -> None:
        try:
            # Asked per line, not once at startup. A daemon is a process that
            # runs for days; one that picked its file when it started would
            # write Tuesday into Monday's file for as long as it stayed up.
            self.open_for(self.clock())
            self.stream.write(self.format(record) + "\n")
        except Exception:
            self.handleError(record)

    def close(self) -> None:
        if self.stream is not None:
            self.stream.close()
            self.stream = None
        super().close()


def beside(events: Path) -> Path:
    """The logs directory belonging to a given events file.

    The log follows the events file rather than being pinned at `var/logs`, and
    that is the whole reason no desk check needs a line adding to it. A check
    runs its daemon against a throwaway events file in a throwaway tree, so its
    log lands in that tree too and the real one stays a record of real runs.
    The alternative was found the expensive way once already, on the events file
    itself: every desk check had been writing into the live daemon's.
    """
    return events.expanduser().resolve().parent / "logs"


def start(directory: Path, keep_days: int = KEEP_DAYS,
          clock: Callable[[], date] = today,
          shape: Callable[[logging.LogRecord], str] | None = None,
          ) -> tuple[Path | None, str]:
    """Begin writing, and hand back the file plus what to say about it.

    `shape` lays out a record that did not come from `say`. It is a callback
    rather than a format string because the columns belong to `say`, and a
    second copy of its widths in this file is two numbers that drift apart.

    Failure comes back as a sentence rather than an exception: see the module
    docstring — not being able to write this down is not a reason to stop
    telling somebody their build finished.
    """
    handler = Daily(directory, keep_days, clock)
    try:
        handler.open_for(clock())
    except OSError as exc:
        return None, (f"{directory} — {exc.strerror or exc}; "
                      f"nothing is being written down")
    # Replaced rather than added to. One process writes one log; a second call
    # that left the first handler in place would write every line twice, and
    # the check below calls this a dozen times in one process.
    for old in list(_log.handlers):
        _log.removeHandler(old)
        old.close()
    # The rest of the package logs to its own module loggers, which nothing has
    # ever attached a handler to — see the module docstring for what that cost.
    root = logging.getLogger()
    for old in _rooted:
        root.removeHandler(old)
    _rooted.clear()
    _log.addHandler(handler)
    # stderr and not stdout, because `say` owns stdout and seven desk checks
    # parse it. This is what `logging.lastResort` was doing by accident, with a
    # time on it now and without its WARNING floor.
    terminal = logging.StreamHandler()
    terminal.setFormatter(Shaped(shape))
    relay = Relay(shape)
    root.addHandler(terminal)
    root.addHandler(relay)
    _rooted.extend((terminal, relay))
    for name in OURS:
        logging.getLogger(name).setLevel(logging.INFO)

    kept = "kept for good" if keep_days <= 0 else f"{keep_days} days kept"
    swept = f", {len(handler.swept)} older removed" if handler.swept else ""
    return handler.path, f"{handler.path} ({kept}{swept})"


def write(line: str) -> None:
    """One line, exactly the string the terminal was given."""
    _log.info(line)
