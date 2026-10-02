"""Claude Code as this project's one event source: the file, and what it says.

`tools/hook_event.sh` appends `<what>\\t<raw json>` to `var/events` and parses
nothing. This module is the other half: which Claude Code hook means what, how
to read a line back, how to follow the file, and how to tell whether the hooks
are wired at all.

It is deliberately NOT in `src/core/`. The core knows `done` and `needs`; that
`Stop` means one and `Notification` the other is knowledge about one particular
agent, and a second agent would add a file beside this one rather than change
the core (the same shape as the platform seam).
"""
from __future__ import annotations

import glob
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from .core.signals import Event, Kind

ROOT = Path(__file__).resolve().parents[1]
EVENTS = ROOT / "var" / "events"
HOOK_SCRIPT = ROOT / "tools" / "hook_event.sh"
SETTINGS = Path(os.path.expanduser("~/.claude/settings.json"))
# Claude Code's own registry of running sessions, one `<pid>.json` per live
# claude (task 40, checked here 2026-09-28). Undocumented, so every field is read leniently.
SESSIONS = Path(os.path.expanduser("~/.claude/sessions"))
# Each session's transcript, `<project dir>/<session id>.jsonl`. VS Code titles a
# session's tab from the `custom-title` or `ai-title` records in it, which the
# registry does not carry (task 43, measured 2026-09-28: registry `wobble-b8`,
# tab and `aiTitle` both `Session planning`).
PROJECTS = Path(os.path.expanduser("~/.claude/projects"))

# Which Claude Code hook carries which word. Verified against a live, working
# configuration on 2026-09-22:
# `Stop` fires when a turn ends, `Notification` when Claude is waiting on the
# person, `UserPromptSubmit` when they type. Typing is not the only answer: a
# permission prompt or an AskUserQuestion is answered in place, and no
# `UserPromptSubmit` follows (task 49, seen 2026-09-29 13:55).
#
# `SessionEnd` added at task 22, and it is the one that stops a queue growing
# for good: without it the only thing that takes an entry out is that session's
# next prompt, so a tab you read and closed leaves something nothing can ever
# resolve. It was already wired to other people's hooks in this settings file on
# 2026-09-23, which is how its existence was confirmed rather than assumed.
#
# `PostToolUse` and `PostToolUseFailure` added at task 49: the tool that asked
# has run, so whatever it asked was answered. `Failure` because a Bash you
# allowed that exits 1 fires that one and not the other (both measured
# 2026-09-29 on a `claude -p` in the scratchpad, 2.1.160). A tool you refused
# fires neither, and its needs waits for what you type next, as before.
#
# `StopFailure` added at task 64: it fires INSTEAD of `Stop` when an API error
# ends the turn (measured 2026-09-30 on 2.1.160, a `claude -p` on a model that
# does not exist; `var/desk/payloads/stopfailure-01.json`). Unwired, that turn
# ended with nothing said at all. It is a `done` that cries sad.
HOOK_FOR = {
    "Stop": "done",
    "StopFailure": "failed",
    "Notification": "needs",
    "UserPromptSubmit": "prompt",
    "SessionEnd": "end",
    "PostToolUse": "answered",
    "PostToolUseFailure": "answered",
}

# Three words are deliberately absent, and for the same reason: none is a thing
# being said. `prompt` and `answered` resolve a signal and `end` stops one
# waiting — all act on the queue rather than joining it, so `as_event` hands
# back `None` for them and the daemon handles each on its own branch.
KIND_OF = {"done": Kind.DONE, "failed": Kind.DONE, "needs": Kind.NEEDS}

# A lone opening tag on the first line — `<task-notification>`, and whatever
# else Claude Code wraps an injected turn in.
TAG = re.compile(r"<[A-Za-z][A-Za-z0-9_-]*>")

# The only three addresses B ever opens (tasks 42 and 43), each checked whole,
# because opening whatever a line or a file says would let either say anything.
# Warp's is the shell's `WARP_FOCUS_URL` (32 hex, measured 2026-09-28); the
# desktop's id is what the app's own handler accepts (`claudeURLHandler` in
# `app.asar`, tasks.md task 40); VS Code's is the session id itself, a UUID.
WARP_URL = re.compile(r"warp://session/[0-9A-Fa-f-]{32,36}")
DESKTOP_ID = re.compile(r"local_[A-Za-z0-9-]{1,64}")
SESSION_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


@dataclass(frozen=True, slots=True)
class HookLine:
    """One line of `var/events`, decoded."""

    what: str                 # "done", "failed", "needs", "prompt", "end" or "answered"
    session: str
    project: str
    window_hint: str
    # Only ever false on a `prompt`: the turn was injected by the agent's own
    # machinery rather than typed. See `by_person` below for why that is not
    # the same question as "did this hook fire".
    by_person: bool = True
    # The app the session runs in, from the line's third field (task 38).
    host: str = ""
    # Warp's address for this session's tab, from the fourth (task 42): `""`
    # for any other host, an older line, or anything that is not `WARP_URL`.
    focus_url: str = ""
    # Only ever true on a `needs`: Claude Code's idle reminder, not a question.
    # See `reminds` below (task 39).
    reminder: bool = False
    # The tool a `needs` asked about, or the one an `answered` ran, as
    # `tool_key` spells it; `""` when the line does not say (task 49).
    tool: str = ""
    # Only ever true on an `answered`: the tool ran inside a subagent, which
    # carries `agent_id` (task 49). See `asked` below for why that is not read
    # as an answer.
    subagent: bool = False

    def as_event(self, at: float) -> Event | None:
        """The core's `Event`, or `None` when this line is not a signal."""
        kind = KIND_OF.get(self.what)
        if kind is None:
            return None
        return Event(session=self.session, kind=kind, project=self.project,
                     at=at, window_hint=self.window_hint, host=self.host,
                     failed=self.what == "failed")


def by_person(data: dict) -> bool:
    """Did a person type this turn, or did the agent re-invoke itself?

    `UserPromptSubmit` fires for both, and criterion 5 leans on it meaning the
    first: a pending entry is dropped because "if you typed in it, you were
    there". A background task finishing in that session is not a person
    arriving, and counting it as one loses a signal nobody ever saw.

    Measured 2026-09-22, by comparing real payloads rather than reasoning about
    them: an injected turn and a typed one carry **exactly the same keys**
    (`cwd`, `session_id`, `prompt_id`, `permission_mode`, `prompt`, ...), so
    there is no flag to read. The one difference is the text — an injected turn
    opens with a lone wrapper tag on its own line (`<task-notification>` is the
    one caught live), and a person's message does not.

    It is a heuristic, and it fails in the safe direction. Reading a person's
    message as machinery leaves the signal pending and still speaking, which is
    the loud failure principle 7 asks for; the other way round is the silent one.

    Found because watching the daemon's log from inside a Claude Code session
    fed the log back to it as events — but the defect is not about log-watching.
    Any background task, in any session, was resolving that session's signal.
    """
    text = data.get("prompt")
    if not isinstance(text, str):
        return True                      # not a prompt line: nothing to judge
    first = text.strip().split("\n", 1)[0].strip()
    return not TAG.fullmatch(first)


def reminds(data: dict) -> bool:
    """Is this `Notification` Claude Code's idle reminder, not a question?

    `Notification` fires for both, and `needs` promises the second: something
    is asking you. Measured 2026-09-28 on real payloads (task 39): a question
    arrives as `notification_type: "permission_prompt"`, and a session left
    alone for 60 s after its done sends `"idle_prompt"` with "Claude is
    waiting for your input". The latter was cried as a needs twice at the
    desk — from Terminal and from Warp, about 60 s after each done — while no
    session had asked anything. Its done already said it, so it adds nothing.

    Only that exact value is a reminder. A missing type (older payloads carry
    none) or one not seen yet stays a needs: the loud failure, principle 7.
    """
    return data.get("notification_type") == "idle_prompt"


# "Claude needs your permission to use AskUserQuestion" — the tool's shown
# name, which is not always its `tool_name`: `Send Message` for `SendMessage`
# (var/events, 2026-09-29).
ASKS_TO_USE = re.compile(r"permission to use (.+)$")


def tool_key(name: str) -> str:
    """A tool's name as both hooks can agree on it: `Send Message` is `SendMessage`."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def asked(data: dict) -> str:
    """Which tool a `Notification` is asking permission for, or `""` (task 49).

    What lets the tool's own `PostToolUse` answer it. The two hooks share no id
    — the `Notification` carries only its message — so the name is the match,
    and a name that does not match leaves the needs where it is: an MCP tool
    whose shown name is not its `tool_name`, a subagent's tool running while
    the main thread waits. Staying stale until the next Stop is the loud
    failure; clearing a question on another tool's word would be the silent
    one (principle 7).
    """
    if data.get("notification_type") != "permission_prompt":
        return ""
    match = ASKS_TO_USE.search(str(data.get("message") or ""))
    return tool_key(match.group(1)) if match else ""


def answers(line: HookLine, asked_for: str) -> bool:
    """Does this `answered` line answer the needs that asked about `asked_for`?

    Only from the main thread, and only the same tool (task 49). A subagent's
    `Notification` carries no `agent_id` (the base input is built without one,
    2.1.160), so its question looks like the main thread's; its tools' lines do
    carry one. Taking them as answers would let a background agent running Bash
    clear the question the main thread is still waiting on.
    """
    return (line.what == "answered" and not line.subagent
            and bool(line.tool) and line.tool == asked_for)


# The one tool whose start can be seen from outside (task 65): what a `needs`
# asking for it has to name, as `tool_key` spells it.
BASH = tool_key("Bash")

# How Claude Code starts a Bash call: a direct child of its own pid, `/bin/zsh -c
# source ~/.claude/shell-snapshots/snapshot-zsh-<ms>-<rand>.sh … && eval '<the
# command>'`. Measured 2026-09-30 on claude-vscode 2.1.282 (pid 43732); the CLI's
# 2.1.160 binary carries the same `snapshot-${shell}-${time}-${rand}.sh`. Its
# hooks run as `/bin/sh -c <hook>` and its MCP servers as `npm exec …`: neither
# sources a snapshot.
SNAPSHOT = re.compile(r"^source \S*/shell-snapshots/snapshot-")


def runs_bash(argv: tuple[str, ...]) -> bool:
    """Is this child of a claude one of its Bash calls running (task 65)?

    What answers a permission question for Bash the moment it is approved:
    its `PostToolUse` comes only when the command ends, and `make release`
    beat 199 for three minutes after the yes (2026-09-30, 23:39). No hook
    fires on the yes itself. Any argument, not argv[2], so a wrapper in front
    (a sandbox) still matches; anything else reads as not Bash, and the
    question waits for its `PostToolUse` as before (principle 7).
    """
    return any(SNAPSHOT.match(arg) for arg in argv)


def project_of(cwd: str) -> str:
    """The project a hook belongs to: the repo above the folder it fired in.

    Not `Path(cwd).name`, which is what this was until task 31. An agent that
    `cd`s into a subfolder for one tool call changes that answer for every hook
    that fires afterwards, and the same session then arrives under two project
    names — seen on screen as `src-tauri — done` for a session filed as `editor`
    three minutes earlier. Sweeping `var/events` found four real sessions doing
    it, so it is the shape of the thing rather than one odd session.

    `.exists()` and not `.is_dir()`: in a worktree `.git` is a file. A submodule
    stops at the submodule, which is the right answer — it is its own repo.

    **No repo above it at all is a real case, not a guard against the
    impossible**, and the folder's own name is the honest answer there: a cwd
    under the scratchpad has no `.git` anywhere above it.

    This walks the real filesystem, and `parse` runs it once per event line in
    the daemon — so `--replay` of an old events file answers with today's
    filesystem rather than that day's. Accepted rather than cached: a repo that
    moved between then and now is a rarer problem than a stale cache, and the
    walk is four `exists()` calls at the pace hooks actually arrive.
    """
    here = Path(cwd)
    for folder in (here, *here.parents):
        if (folder / ".git").exists():
            return folder.name
    return here.name


# Claude Code files a transcript under the folder its session started in, with
# every character but a letter or a digit spelled `-` (task 69): checked against
# all 4,565 lines of `var/events` on 2026-10-01, each landed on a real folder.
FILED = re.compile(r"[^A-Za-z0-9]")


def launched_in(cwd: str, transcript: str) -> str:
    """The folder this session was started in, or `""` when it cannot be told (task 69).

    What a window is titled after: VS Code names its window for the folder it
    opened, and the extension starts claude there. `project_of` answers the
    repo instead, and they come apart when the repo sits below that folder —
    `workspace` has no `.git`, `workspace/documents` does, so a session
    working in it was filed as `documents`, found no window by that name, and B
    never landed on it (2026-10-01, 14:48).

    The encoded name cannot be decoded — `my-dev` reads as two folders —
    so it is matched against `cwd` and each folder above it instead. A session
    that `cd`ed outside the folder it started in matches none, and `""` keeps
    the window hint at the project, as before.
    """
    if not cwd or not transcript:
        return ""
    filed = Path(transcript).parent.name
    here = Path(cwd)
    for folder in (here, *here.parents):
        if FILED.sub("-", str(folder)) == filed:
            return str(folder)
    return ""


def parse(line: str) -> HookLine | None:
    """One raw line, or `None` if it cannot be used.

    `None` rather than a best effort: a line with no session id cannot be
    dismissed, focused or resolved, and inventing one would merge two sessions
    into one entry. The caller counts the refusals — a hook writing lines nobody
    can read is a notifier that has silently stopped (principle 7).
    """
    what, tab, rest = line.rstrip("\n").partition("\t")
    # A third field since task 38: the host app's bundle id. A line written
    # before it has none and reads as `""`, the unknown the core already
    # handles. The script strips tabs from the payload, so this split is safe.
    # A fourth since task 42, Warp's focus URL, split off the same way.
    payload, _, rest = rest.partition("\t")
    host, _, focus_url = rest.partition("\t")
    focus_url = focus_url.strip()
    if not tab or what not in HOOK_FOR.values():
        return None
    try:
        data = json.loads(payload) if payload else {}
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    session = str(data.get("session_id") or "")
    if not session:
        return None
    # The project is the repo the session is working in, and the window hint is
    # the folder it was started in: a window running Claude Code is titled
    # after the folder it was opened in, which is all `Focus.window` has to go
    # on (spec.md, criterion 4). The two came apart at the desk — a repo below
    # the folder VS Code opened (task 69, `launched_in`) — and where the folder
    # cannot be told, the hint is the project, as it was until then.
    cwd = str(data.get("cwd") or "")
    project = project_of(cwd) if cwd else "(unknown project)"
    hint = Path(launched_in(cwd, str(data.get("transcript_path") or ""))).name or project
    return HookLine(what=what, session=session, project=project, window_hint=hint,
                    by_person=by_person(data), host=host.strip(),
                    focus_url=focus_url if WARP_URL.fullmatch(focus_url) else "",
                    reminder=what == "needs" and reminds(data),
                    tool=(asked(data) if what == "needs" else
                          tool_key(str(data.get("tool_name") or "")) if what == "answered"
                          else ""),
                    subagent=what == "answered" and bool(data.get("agent_id")))


class Tail:
    """Follows an append-only file, handing back whole lines as they arrive.

    Starts at the end by default. Replaying a day of events on startup would
    announce a hundred finished sessions at once, and the queue's own rule —
    one entry per session — would collapse them into something that looks like
    the present but is not. `from_end=False` is for reading a recorded file back
    at a desk — and, since task 47, for the daemon itself, which reads the past
    back quietly (`daemon.recall`) before it follows the file.

    A partial last line is kept, not returned: the hook's `printf` is one write,
    but a reader can still land between the bytes.
    """

    def __init__(self, path: Path | str = EVENTS, *, from_end: bool = True):
        self.path = Path(path)
        self.position = 0
        self.restarts = 0        # times the file shrank under us
        self._buffer = ""
        if from_end and self.path.exists():
            self.position = self.path.stat().st_size

    def lines(self) -> list[str]:
        """Whatever is new since the last call. Never blocks, never raises."""
        try:
            size = self.path.stat().st_size
        except OSError:
            return []
        if size < self.position:
            # Truncated or replaced. Reading on from the old offset would hand
            # back the middle of a line as though it were a whole one.
            self.restarts += 1
            self.position, self._buffer = 0, ""
        if size == self.position:
            return []
        try:
            with self.path.open("r", errors="replace") as fh:
                fh.seek(self.position)
                chunk = fh.read()
                self.position = fh.tell()
        except OSError:
            return []
        self._buffer += chunk
        *whole, self._buffer = self._buffer.split("\n")
        return whole


def short(session: str) -> str:
    """The id as the log prints it: its first four characters (task 40).

    Four because that is what tells apart the sessions one person has open at
    once — five on this Mac on 2026-09-28, no two sharing even a first two.
    """
    return session[:4]


@dataclass(frozen=True, slots=True)
class Running:
    """One live claude, as Claude Code's registry describes it (task 40).

    `entrypoint` is how it was started — `cli`, `claude-vscode` or
    `claude-desktop`, the three seen here. `name` is VS Code's tab name (and the
    first segment of its window title), `host_session` the desktop app's
    `local_` id that `claude://code/continue?session=` takes. Both are `""` when
    the registry carries none.
    """

    session: str
    pid: int
    entrypoint: str = ""
    name: str = ""
    host_session: str = ""
    # `startedAt`, in epoch seconds: what `alive` compares a pid against, so a
    # pid handed to some other process after this one died is not taken for it.
    started: float = 0.0
    # The folder it was started in, as the registry says (task 69): what VS
    # Code is asked to open when that folder's window is on another desktop.
    cwd: str = ""

    # How far the registry's `startedAt` may sit from the kernel's start time.
    # Measured 2026-09-28: 0.3–3.7 s behind the kernel's for all five live
    # sessions (it is written as claude boots). 60 s is over ten times what was seen, and far under how long pids take to wrap.
    DRIFT_S = 60.0

    @property
    def deep_link(self) -> str:
        """The desktop app's link to this very session, or `""` (task 42).

        Measured 2026-09-28: `claude://code/continue?session=local_<id>` opens
        that session and brings the app forward (tasks.md, task 40).
        """
        if self.entrypoint != "claude-desktop" or not DESKTOP_ID.fullmatch(self.host_session):
            return ""
        return f"claude://code/continue?session={self.host_session}"

    @property
    def vscode_link(self) -> str:
        """VS Code's link to this session's own tab, or `""` (task 43).

        Measured 2026-09-28 22:14:33: `vscode://anthropic.claude-code/open?
        session=<id>` selected the session's tab, already open beside a twin,
        and opened no second one — the extension's `createPanel` reveals a
        panel it holds (anthropic.claude-code 2.1.283). A window that does not
        hold it opens a new copy, so B opens this only after the session's own
        window came forward (`daemon.ways`).
        """
        if self.entrypoint != "claude-vscode" or not SESSION_ID.fullmatch(self.session):
            return ""
        return f"vscode://anthropic.claude-code/open?session={self.session}"

    def alive(self, started: float | None) -> bool:
        """Is the process the kernel reports for this pid, started at `started`
        (`None`: no such pid), still this claude?"""
        if started is None:
            return False
        return not self.started or abs(started - self.started) <= self.DRIFT_S


def running(session: str, folder: Path | str = SESSIONS) -> Running | None:
    """This session's entry in Claude Code's registry, or `None`.

    `None` is not "it is gone": an older Claude Code writes no registry, and a
    file can be caught mid-write. The caller keeps treating the session as it
    did before task 40, which is the loud direction (principle 7).
    """
    return next((run for run in registry(folder) if run.session == session), None)


def registry(folder: Path | str = SESSIONS) -> list[Running]:
    """Every session in Claude Code's registry, one `Running` each (task 43).

    Empty when the folder cannot be read. Only the `.json` files are read; the
    `.key` files beside them are not ours to open.

    **One session can have two files**, and the newest start wins. Resuming
    registers a new pid while the old one winds down, and
    a `kill -9` leaves its file behind (`learnings.md`, 2026-09-28). Taking
    whichever file came first could hand back the dead one.
    """
    try:
        files = list(Path(folder).glob("*.json"))
    except OSError:
        return []
    newest: dict[str, Running] = {}
    for path in files:
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        session = data.get("sessionId")
        if not isinstance(session, str) or not session:
            continue
        try:
            pid = int(data.get("pid") or path.stem)
        except (TypeError, ValueError):
            continue
        started = data.get("startedAt")
        run = Running(session=session, pid=pid,
                      entrypoint=str(data.get("entrypoint") or ""),
                      name=str(data.get("name") or ""),
                      host_session=str(data.get("hostSessionId") or ""),
                      started=started / 1000 if isinstance(started, (int, float)) else 0.0,
                      cwd=str(data.get("cwd") or ""))
        if session not in newest or run.started > newest[session].started:
            newest[session] = run
    return list(newest.values())


class Titles:
    """What VS Code may title each session's tab, read from its transcript (task 43).

    The latest `custom-title` (a name you gave it) and the latest `ai-title`
    (the one Claude Code made up), both kept: measured 2026-09-28, a renamed
    session carries both and its tab shows the custom one. Holding both costs
    nothing, since the tab in front is only compared against them.

    Transcripts run to tens of MB, so each is read once and then only from where
    the last read stopped, and a line not yet finished is left for the next
    read. A transcript that cannot be found or read gives no titles, and the
    daemon then falls back to the registry's name and to the folder rule.
    """

    KEYS = {"ai-title": "aiTitle", "custom-title": "customTitle"}

    def __init__(self, folder: Path | str = PROJECTS) -> None:
        self.folder = Path(folder)
        self._path: dict[str, Path] = {}
        self._offset: dict[str, int] = {}
        self._latest: dict[str, dict[str, str]] = {}

    def of(self, session: str) -> frozenset[str]:
        path = self._path.get(session)
        if path is None:
            found = sorted(self.folder.glob(f"*/{glob.escape(session)}.jsonl"))
            if not found:
                return frozenset()
            path = self._path[session] = found[0]
        latest = self._latest.setdefault(session, {})
        offset = self._offset.get(session, 0)
        try:
            if path.stat().st_size < offset:
                # Rewritten under us: read it again from the top.
                offset, latest = 0, self._latest.setdefault(session, {})
                latest.clear()
            with path.open("rb") as transcript:
                transcript.seek(offset)
                chunk = transcript.read()
        except OSError:
            return frozenset(latest.values())
        end = chunk.rfind(b"\n") + 1
        self._offset[session] = offset + end
        for line in chunk[:end].splitlines():
            if b'-title"' not in line:
                continue
            try:
                data = json.loads(line)
            except ValueError:
                continue
            key = self.KEYS.get(data.get("type")) if isinstance(data, dict) else None
            if key and isinstance(data.get(key), str) and data[key]:
                latest[data["type"]] = data[key]
        return frozenset(latest.values())


def wiring(settings: Path | str = SETTINGS,
           script: Path | str = HOOK_SCRIPT) -> tuple[bool, str]:
    """Are the hooks installed? Returns `(ok, the sentence to show a person)`.

    Principle 7 in its plainest form: with no hooks, this whole thing is a
    daemon watching a file nobody writes, and the only symptom is that nothing
    ever happens. So the answer is a sentence, not a boolean nobody prints.
    """
    settings, script = Path(settings), str(script)
    try:
        hooks = json.loads(settings.read_text()).get("hooks", {})
    except FileNotFoundError:
        return False, (f"{settings} does not exist, so no Claude Code hook is "
                       f"wired and nothing will ever reach this daemon. "
                       f"Run: venv/bin/python3 tools/install_hooks.py")
    except (json.JSONDecodeError, OSError) as exc:
        return False, (f"{settings} could not be read ({exc}), so whether the "
                       f"hooks are wired is unknown — which is not the same as "
                       f"them being fine")

    missing = [event for event in HOOK_FOR
               if not any(script in entry.get("command", "")
                          for group in hooks.get(event, [])
                          for entry in group.get("hooks", []))]
    if not missing:
        return True, f"hooks wired for {', '.join(HOOK_FOR)} in {settings}"
    return False, (f"NOT wired: {', '.join(missing)} — {settings} has no hook "
                   f"running {script}. Without them nothing reaches this daemon "
                   f"and the silence would look like a quiet afternoon. "
                   f"Run: venv/bin/python3 tools/install_hooks.py")
