#!/usr/bin/env python3
"""Tell a person arriving apart from the agent re-invoking itself.

    venv/bin/python3 tests/tables/check_hooks.py

Criterion 5 reads `UserPromptSubmit` as "you were there", and drops the pending
signal for that session on the strength of it. But that hook also fires when a
background task hands its result back and the agent starts a turn on its own —
no person anywhere — and on 2026-09-22 that resolved a real `done` nobody had
seen. `hooks.by_person` is the one line standing between those two.

**Every payload here is a real one**, captured out of `var/events` and kept in
`tests/fixtures/payloads/`. Writing the fixtures by hand was the tempting shortcut and
is exactly the trap: the shape a payload is imagined to have is the same shape
the heuristic was written against, so a hand-made table would agree with the code
for the same wrong reason. `capture_payloads.py` is how the folder is refilled;
which file is typed and which is injected is decided by reading the transcript,
never by asking the function under test. Each is scrubbed on the way in: the home
is `/home/user`, a typed prompt is a stand-in of the same shape, and
`launched-01.json` is rebuilt from the real one's keys (task 76).

**The control is three mutants**, one of them the defect as it actually shipped.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import replace
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))
from src import hooks as mod                                          # noqa: E402
from sandbox import Sandbox                                           # noqa: E402

PAYLOADS = ROOT / "tests" / "fixtures" / "payloads"
# Task 49's `answered` is the one word the script rewrites, so its rows go
# through the real script — in a sandbox, never into `var/events`.
BOX = Sandbox()


class Sheet:
    def __init__(self, quiet: bool = False):
        self.quiet, self.bad = quiet, 0

    def row(self, what: str, got, want) -> None:
        good = got == want
        self.bad += not good
        if not self.quiet:
            print(f"    {what:<52} {'ok' if good else f'<-- WRONG: {got!r}, wanted {want!r}'}")

    def ok(self) -> bool:
        return not self.bad


def captured(prefix: str) -> list[tuple[str, dict]]:
    return [(path.name, json.loads(path.read_text()))
            for path in sorted(PAYLOADS.glob(f"{prefix}-*.json"))]


def at_home(data: dict) -> dict:
    """A launched payload moved under a temp home that has its tree on disk (task 76).

    `project_of` walks the real filesystem, so the workspace with no `.git` and
    the repo below it with one have to exist; the fixture's `/home/user` is
    replaced by a folder that has them, and the transcript is re-filed to match.
    """
    home = Path(tempfile.mkdtemp(prefix="wobble-home-"))
    cwd = Path(data["cwd"].replace("/home/user", str(home)))
    cwd.mkdir(parents=True)
    (home / "my-workspace" / "documents" / ".git").mkdir()
    filed = mod.FILED.sub("-", str(home / "my-workspace"))
    return dict(data, cwd=str(cwd),
                transcript_path=str(home / ".claude" / "projects" / filed
                                    / Path(data["transcript_path"]).name))


def line_for(what: str, data: dict) -> str:
    """The same bytes `tools/hook_event.sh` writes — tab, then the raw JSON."""
    return f"{what}\t{json.dumps(data)}"


def run_all(quiet: bool = False) -> bool:
    sheet = Sheet(quiet)
    typed, injected, dones = captured("typed"), captured("injected"), captured("done")

    if not quiet:
        print(f"\n  real payloads on disk: {len(typed)} typed, {len(injected)} "
              f"injected, {len(dones)} done")
    # A table with nothing on one side of it passes for the wrong reason, so the
    # count is a row and not an assumption.
    sheet.row("there is at least one of each", (bool(typed), bool(injected), bool(dones)),
              (True, True, True))

    if not quiet:
        print("\n  a person typed it — every one of these must resolve a signal")
    for name, data in typed:
        sheet.row(f"{name} reads as a person", mod.by_person(data), True)

    if not quiet:
        print("\n  the agent re-invoked itself — these must resolve nothing")
    for name, data in injected:
        sheet.row(f"{name} reads as machinery", mod.by_person(data), False)

    if not quiet:
        print("\n  a line that is not a prompt has nothing to judge")
    for name, data in dones:
        sheet.row(f"{name} is left alone", mod.by_person(data), True)

    if not quiet:
        print("\n  the flag survives the round trip through parse()")
    for name, data in typed[:1]:
        parsed = mod.parse(line_for("prompt", data))
        sheet.row("a typed prompt parses, and is by a person",
                  (parsed is not None and parsed.what, parsed and parsed.by_person),
                  ("prompt", True))
    for name, data in injected[:1]:
        parsed = mod.parse(line_for("prompt", data))
        sheet.row("an injected one parses, and is not",
                  (parsed is not None and parsed.what, parsed and parsed.by_person),
                  ("prompt", False))
    for name, data in dones[:1]:
        parsed = mod.parse(line_for("done", data))
        sheet.row("a done carries by_person True, harmlessly",
                  (parsed is not None and parsed.what, parsed and parsed.by_person),
                  ("done", True))

    if not quiet:
        print("\n  the host app, the line's third field (task 38)")
    for name, data in dones[:1]:
        parsed = mod.parse(line_for("done", data) + "\tcom.microsoft.VSCode")
        sheet.row("a line with a host carries it to the event",
                  parsed and parsed.as_event(0.0).host, "com.microsoft.VSCode")
        parsed = mod.parse(line_for("done", data))
        sheet.row("a line from before task 38 still parses, host unknown",
                  (parsed is not None, parsed and parsed.host), (True, ""))
        parsed = mod.parse(line_for("done", data) + "\t")
        sheet.row("an empty host field is unknown, not a host called ''",
                  parsed and parsed.host, "")

    if not quiet:
        print("\n  a turn an API error ended — StopFailure, instead of Stop (task 64)")
    stops = captured("stopfailure")
    sheet.row("there is at least one, and it is the real hook's",
              [data.get("hook_event_name") for _, data in stops][:1], ["StopFailure"])
    sheet.row("StopFailure is wired as 'failed'", mod.HOOK_FOR.get("StopFailure"), "failed")
    for name, data in stops:
        parsed = mod.parse(through_script("failed", data))
        event = parsed and parsed.as_event(0.0)
        sheet.row(f"{name} parses as failed, its own session",
                  parsed and (parsed.what, parsed.session), ("failed", data["session_id"]))
        sheet.row(f"{name} is a done that failed",
                  event and (event.kind, event.failed), (mod.Kind.DONE, True))
    for name, data in dones[:1]:
        event = mod.parse(line_for("done", data)).as_event(0.0)
        sheet.row("a plain done did not fail", event and (event.kind, event.failed),
                  (mod.Kind.DONE, False))

    if not quiet:
        print("\n  a Notification: a question, or the 60 s idle reminder (task 39)")
    idle, asks = captured("idle"), captured("asks")
    sheet.row("there is at least one of each", (bool(idle), bool(asks)), (True, True))
    for name, data in idle:
        parsed = mod.parse(line_for("needs", data))
        sheet.row(f"{name} is a reminder, not a question",
                  (parsed is not None and parsed.what, parsed and parsed.reminder),
                  ("needs", True))
    for name, data in asks:
        parsed = mod.parse(line_for("needs", data))
        sheet.row(f"{name} is a question",
                  (parsed is not None and parsed.what, parsed and parsed.reminder),
                  ("needs", False))
    for name, data in asks[:1]:
        old = {k: v for k, v in data.items() if k != "notification_type"}
        parsed = mod.parse(line_for("needs", old))
        sheet.row("a Notification with no type stays a question",
                  parsed and parsed.reminder, False)
        parsed = mod.parse(line_for("needs", {**data, "notification_type": "new_kind"}))
        sheet.row("a type not seen yet stays a question", parsed and parsed.reminder, False)
    for name, data in dones[:1]:
        parsed = mod.parse(line_for("done", {**data, "notification_type": "idle_prompt"}))
        sheet.row("only a needs can be a reminder", parsed and parsed.reminder, False)

    if not quiet:
        print("\n  a tool that ran answers the one that asked (task 49)")
    ran, failed, sub = captured("ran"), captured("failed"), captured("sub")
    sheet.row("there is at least one ran, failed and subagent",
              (bool(ran), bool(failed), bool(sub)), (True, True, True))
    for name, data in ran + failed:
        line = through_script("answered", data)
        parsed = mod.parse(line)
        sheet.row(f"{name} parses as {data['tool_name']}, main thread",
                  parsed and (parsed.what, parsed.session, parsed.tool, parsed.agent),
                  ("answered", data["session_id"], mod.tool_key(data["tool_name"]), ""))
    for name, data in sub:
        parsed = mod.parse(through_script("answered", data))
        sheet.row(f"{name} is a subagent's, by its id", parsed and parsed.agent, data["agent_id"])
    for name, data in ran[:1]:
        # Derived from a real one: what a tool says must never be read as the
        # ids. As real keys, because a string's quotes arrive escaped and could
        # never match — an MCP tool's `tool_response` is an object of its own.
        # Ahead of the bulk, or the script's cut at 8000 hides them from the test.
        loud = {**data, "tool_response": {"tool_name": "Evil", "agent_id": "a1",
                                          "session_id": "deadbeef", "stdout": "y" * 20000}}
        line = through_script("answered", loud)
        parsed = mod.parse(line)
        sheet.row("a huge output is not forwarded",
                  len(line) < 400 and len(json.dumps(loud)) > 8000, True)
        sheet.row("…and what the tool said is not read as its ids or name",
                  parsed and (parsed.session, parsed.tool, parsed.agent),
                  (data["session_id"], mod.tool_key(data["tool_name"]), ""))
        no_id = {k: v for k, v in data.items() if k != "session_id"}
        sheet.row("no session id is a line the daemon refuses",
                  mod.parse(through_script("answered", no_id)), None)

    if not quiet:
        print("\n  …and who asks it: PermissionRequest (task 71)")
    perm_main, perm_sub = captured("perm-main"), captured("perm-sub")
    sheet.row("PermissionRequest is wired as 'asking'",
              mod.HOOK_FOR.get("PermissionRequest"), "asking")
    sheet.row("there is a main thread's and a subagent's PermissionRequest",
              (bool(perm_main), bool(perm_sub)), (True, True))
    for name, data in perm_main + perm_sub:
        line = through_script("asking", data)
        parsed = mod.parse(line)
        sheet.row(f"{name} parses as who asks for {data['tool_name']}",
                  parsed and (parsed.what, parsed.session, parsed.tool, parsed.agent),
                  ("asking", data["session_id"], mod.tool_key(data["tool_name"]),
                   data.get("agent_id", "")))
        # Its tool_input is the command about to run — never forwarded.
        sheet.row(f"…and {name}'s command is not in the line",
                  data["tool_input"]["command"] in line, False)
        sheet.row(f"…and {name} keeps the folder it is named by (task 72)",
                  parsed and parsed.project, mod.project_of(data["cwd"]))
        event = parsed and parsed.as_event(0.0)
        sheet.row(f"…and {name} is a needs, as the question shows (task 72)",
                  event and event.kind.value, "needs")

    if not quiet:
        print("\n  …and which tool a Notification asked about")
    wants = {"AskUserQuestion": "askuserquestion", "Bash": "bash",
             "Send Message": "sendmessage"}
    for name, data in asks:
        said = data.get("message", "").rpartition("permission to use ")[2]
        want = wants.get(said, "") if "permission to use " in data.get("message", "") else ""
        parsed = mod.parse(line_for("needs", data))
        sheet.row(f"{name} asks about {want or 'no tool it names'}",
                  parsed and parsed.tool, want)
    sheet.row("the shown name matches the tool's own",
              mod.tool_key("Send Message") == mod.tool_key("SendMessage"), True)
    for name, data in idle[:1]:
        parsed = mod.parse(line_for("needs", data))
        sheet.row("a reminder asks about nothing", parsed and parsed.tool, "")

    if not quiet:
        print("\n  …and what counts as the answer")
    if ran and sub and dones:
        main_bash = mod.parse(through_script("answered", ran[0][1]))
        sub_bash = mod.parse(through_script("answered", sub[0][1]))
        done = mod.parse(line_for("done", dones[0][1]))
        sheet.row("the same tool, from the main thread, answers",
                  mod.answers(main_bash, "bash"), True)
        sheet.row("…another tool does not", mod.answers(main_bash, "askuserquestion"), False)
        sheet.row("…a subagent's tool does not", mod.answers(sub_bash, "bash"), False)
        sheet.row("…unless that subagent asked (task 71)",
                  mod.answers(sub_bash, "bash", sub_bash.agent), True)
        sheet.row("…and then the main thread's does not",
                  mod.answers(main_bash, "bash", sub_bash.agent), False)
        sheet.row("…nor another subagent's",
                  mod.answers(sub_bash, "bash", "a" + sub_bash.agent), False)
        sheet.row("…nothing answers a question that named no tool",
                  mod.answers(main_bash, ""), False)
        sheet.row("…and a line that is not an answer is not one",
                  mod.answers(done, "bash"), False)

    if not quiet:
        print("\n  …and which needs is only the notice of an asking (task 72)")
    bash_asks = [(n, d) for n, d in asks if "permission to use Bash" in d.get("message", "")]
    needs = bash_asks and mod.parse(line_for("needs", bash_asks[0][1]))
    main_asks = perm_main and mod.parse(through_script("asking", perm_main[0][1]))
    sub_asks = perm_sub and mod.parse(through_script("asking", perm_sub[0][1]))
    if needs and main_asks and sub_asks:
        sheet.row("the notice after a subagent's asking restates it",
                  mod.restates(needs, sub_asks), True)
        sheet.row("…and after the main thread's",
                  mod.restates(needs, main_asks), True)
        sheet.row("…no asking before it is a question of its own",
                  mod.restates(needs, None), False)
        sheet.row("…nor one about another tool",
                  mod.restates(needs, replace(sub_asks, tool="askuserquestion")), False)
        sheet.row("…nor a needs that names no tool",
                  mod.restates(replace(needs, tool=""), sub_asks), False)
        sheet.row("…an idle reminder restates nothing",
                  mod.restates(replace(needs, reminder=True), sub_asks), False)
        sheet.row("…and an asking is never a notice",
                  mod.restates(sub_asks, sub_asks), False)
    else:
        sheet.row("a Bash needs and both askings, captured and parsed",
                  (bool(needs), bool(main_asks), bool(sub_asks)), (True, True, True))

    if not quiet:
        print("\n  the edges of the rule, stated rather than discovered later")
    # The tag has to be the whole first line. A person writing about markup, or
    # pasting a snippet under a sentence, is a person.
    sheet.row("a tag mentioned mid-sentence is a person",
              mod.by_person({"prompt": "why does <div> break the layout?"}), True)
    sheet.row("a tag on a later line is a person",
              mod.by_person({"prompt": "look at this:\n<task-notification>"}), True)
    sheet.row("text after the tag on line one is a person",
              mod.by_person({"prompt": "<task-notification> what happened?"}), True)
    sheet.row("leading blank lines do not hide the tag",
              mod.by_person({"prompt": "\n\n<task-notification>\nit finished"}), False)
    sheet.row("a closing tag is not an opening one",
              mod.by_person({"prompt": "</task-notification>"}), True)
    # The known false positive, written down on purpose. Somebody whose entire
    # message is `<hello>` is read as machinery and their signal keeps speaking
    # — the loud failure, which is the one principle 7 asks for.
    sheet.row("a lone tag typed by a person is misread, loudly",
              mod.by_person({"prompt": "<hello>"}), False)
    sheet.row("an empty prompt is a person, not machinery",
              mod.by_person({"prompt": ""}), True)
    sheet.row("a prompt that is not a string is not judged",
              mod.by_person({"prompt": None}), True)
    sheet.row("no prompt key at all is not judged", mod.by_person({}), True)

    if not quiet:
        print("\n  the window is the folder it started in, not the repo (task 69)")
    launched = [(name, at_home(data)) for name, data in captured("launched")]
    sheet.row("there is at least one, from below the folder it started in",
              bool(launched), True)
    for name, data in launched:
        parsed = mod.parse(line_for("done", data))
        sheet.row(f"{name}: the repo names it, the folder finds its window",
                  parsed and (parsed.project, parsed.window_hint), ("documents", "my-workspace"))
        sheet.row(f"{name}: …and the event carries the folder's word",
                  parsed and parsed.as_event(0.0).window_hint, "my-workspace")
        moved = dict(data, cwd=str(ROOT))
        parsed = mod.parse(line_for("done", moved))
        sheet.row(f"{name}: cd'ed out of where it started: the project",
                  parsed and (parsed.project, parsed.window_hint), (ROOT.name, ROOT.name))
        bare = {k: v for k, v in data.items() if k != "transcript_path"}
        parsed = mod.parse(line_for("done", bare))
        sheet.row(f"{name}: no transcript path: the project, as before",
                  parsed and parsed.window_hint, "documents")
    root = {"session_id": "r", "cwd": "/", "transcript_path": "/x/-/r.jsonl"}
    sheet.row("started at /: the folder has no name, so the project",
              mod.parse(line_for("done", root)).window_hint, mod.project_of("/"))
    for name, data in dones[:1]:
        parsed = mod.parse(line_for("done", data))
        sheet.row("a repo opened as itself: folder and project agree",
                  parsed and parsed.window_hint == parsed.project, True)

    return sheet.ok()


def through_script(what: str, data: dict) -> str:
    """The line the real `hook_event.sh` writes for this payload, in the sandbox."""
    BOX.reset()
    subprocess.run([str(BOX.hook), what], input=json.dumps(data, separators=(",", ":")),
                   text=True, check=True)
    return BOX.events.read_text().rstrip("\n")


def always_person(data: dict) -> bool:
    """The defect as it shipped: every UserPromptSubmit counted as a person."""
    return True


def never_person(data: dict) -> bool:
    """The other way round — nothing ever resolves, so nothing is ever dismissed."""
    return "prompt" not in data


def tag_anywhere(data: dict) -> bool:
    """Right idea, wrong anchor: a tag looked for anywhere in the text.

    This is the near miss worth having a control for. It catches every injected
    turn the real rule catches, so half the table cannot tell them apart — what
    it also eats is a person asking about `<div>`.
    """
    text = data.get("prompt")
    if not isinstance(text, str):
        return True
    return mod.TAG.search(text) is None


def never_reminds(data: dict) -> bool:
    """The defect as it shipped: every Notification cried as a needs."""
    return False


def always_reminds(data: dict) -> bool:
    """The other way round — no question would ever be cried."""
    return True


def main() -> int:
    print(__doc__.strip().splitlines()[0])
    ok = run_all()

    print("\n  the control — the rule removed three ways, all must break the table")
    real = mod.by_person
    try:
        for label, stand_in in (("every prompt taken as a person", always_person),
                                ("no prompt ever taken as one", never_person),
                                ("the tag looked for anywhere", tag_anywhere)):
            mod.by_person = stand_in
            survived = run_all(quiet=True)
            ok &= not survived
            print(f"    {label:<52} "
                  f"{'<-- SURVIVED, so the table does not test it' if survived else 'caught'}")
    finally:
        mod.by_person = real
    real = mod.launched_in
    try:
        for label, stand_in in (
                ("the folder never told, the project as before", lambda cwd, tr: ""),
                ("the folder taken from the cwd", lambda cwd, tr: cwd),
                ("the filed name split on its dashes",
                 lambda cwd, tr: "/" + Path(tr).parent.name.strip("-").replace("-", "/"))):
            mod.launched_in = stand_in
            survived = run_all(quiet=True)
            ok &= not survived
            print(f"    {label:<52} "
                  f"{'<-- SURVIVED, so the table does not test it' if survived else 'caught'}")
    finally:
        mod.launched_in = real
    real = mod.reminds
    try:
        for label, stand_in in (("every Notification taken as a question", never_reminds),
                                ("every Notification taken as a reminder", always_reminds)):
            mod.reminds = stand_in
            survived = run_all(quiet=True)
            ok &= not survived
            print(f"    {label:<52} "
                  f"{'<-- SURVIVED, so the table does not test it' if survived else 'caught'}")
    finally:
        mod.reminds = real

    # Task 49's rule, removed four ways, and the script's own guard once.
    stand_ins = (
        ("asked", "no Notification names its tool", lambda data: ""),
        ("tool_key", "names compared as spelled", lambda name: name),
        ("answers", "a subagent's tool taken as an answer",
         lambda line, asked_for, asker="": line.what == "answered" and bool(line.tool)
         and line.tool == asked_for),
        ("answers", "any tool taken as the answer",
         lambda line, asked_for, asker="": line.what == "answered" and bool(asked_for)),
        ("answers", "only the main thread answers, as before task 71",
         lambda line, asked_for, asker="": line.what == "answered" and not line.agent
         and bool(line.tool) and line.tool == asked_for),
        ("restates", "every notice a question of its own",
         lambda needs, asking: False),
        ("restates", "any line after an asking taken as its notice",
         lambda needs, asking: asking is not None),
        ("restates", "an idle reminder taken as the notice",
         lambda needs, asking: needs.what == "needs" and asking is not None
         and bool(needs.tool) and asking.tool == needs.tool),
    )
    for attr, label, stand_in in stand_ins:
        real = getattr(mod, attr)
        try:
            setattr(mod, attr, stand_in)
            survived = run_all(quiet=True)
        finally:
            setattr(mod, attr, real)
        ok &= not survived
        print(f"    {label:<52} "
              f"{'<-- SURVIVED, so the table does not test it' if survived else 'caught'}")
    # Task 64's StopFailure, removed three ways.
    real_hook_for, real_kind_of, real_as_event = mod.HOOK_FOR, mod.KIND_OF, mod.HookLine.as_event

    def never_failed(self, at):
        event = real_as_event(self, at)
        return event and replace(event, failed=False)
    for label, apply in (
            ("StopFailure not wired", lambda: setattr(
                mod, "HOOK_FOR", {k: v for k, v in real_hook_for.items() if k != "StopFailure"})),
            ("a failed turn is no signal at all", lambda: setattr(
                mod, "KIND_OF", {k: v for k, v in real_kind_of.items() if k != "failed"})),
            ("an asking is no needs, as before task 72", lambda: setattr(
                mod, "KIND_OF", {k: v for k, v in real_kind_of.items() if k != "asking"})),
            ("a failed turn is a done that did not fail", lambda: setattr(
                mod.HookLine, "as_event", never_failed))):
        try:
            apply()
            survived = run_all(quiet=True)
        finally:
            mod.HOOK_FOR, mod.KIND_OF = real_hook_for, real_kind_of
            mod.HookLine.as_event = real_as_event
        ok &= not survived
        print(f"    {label:<52} "
              f"{'<-- SURVIVED, so the table does not test it' if survived else 'caught'}")
    script = BOX.hook.read_text()
    try:
        BOX.hook.write_text(script.replace('head=${payload%%\\"tool_input\\"*}',
                                           'head=$payload'))
        assert BOX.hook.read_text() != script, "the mutant did not apply"
        survived = run_all(quiet=True)
    finally:
        BOX.hook.write_text(script)
    ok &= not survived
    print(f"    {'the script reads past tool_input':<52} "
          f"{'<-- SURVIVED, so the table does not test it' if survived else 'caught'}")
    try:
        BOX.hook.write_text(script.replace("*'\"tool_input\"'*) head=", "*'nothing'*) head="))
        assert BOX.hook.read_text() != script, "the mutant did not apply"
        survived = run_all(quiet=True)
    finally:
        BOX.hook.write_text(script)
    ok &= not survived
    print(f"    {'an asking forwarded whole, command and all':<52} "
          f"{'<-- SURVIVED, so the table does not test it' if survived else 'caught'}")
    try:
        BOX.hook.write_text(script.replace('if [ "$what" = asking ]; then', 'if false; then')
                            .replace('elif [ "$what" = answered ]; then',
                                     'elif [ "$what" = answered ] || [ "$what" = asking ]; then'))
        assert BOX.hook.read_text() != script, "the mutant did not apply"
        survived = run_all(quiet=True)
    finally:
        BOX.hook.write_text(script)
    ok &= not survived
    print(f"    {'an asking cut to three fields, as task 71 had it':<52} "
          f"{'<-- SURVIVED, so the table does not test it' if survived else 'caught'}")

    print("\n" + ("ALL CASES MATCH the known answer" if ok
                  else "SOMETHING DOES NOT MATCH — the rows above, not this line"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
