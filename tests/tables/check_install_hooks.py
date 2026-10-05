#!/usr/bin/env python3
"""Check `tools/install_hooks.py` against temp settings files, never the real one.

    venv/bin/python3 tests/tables/check_install_hooks.py

`install_hooks.py`'s own docstring makes four promises about a file "that
belongs to the person, not to the project": it shows the exact block first,
never touches a hook it did not write, backs the file up before writing, and
writes through a temp file so a half-written `settings.json` can never exist.
This is the check for all four, plus `--uninstall`'s mirror of the same
promises, run only against files under `tempfile.mkdtemp()`.

**Every call passes `--settings <tmp path>` explicitly.** The real
`~/.claude/settings.json` is never opened — not even to read it back — because
it can hold other people's hooks and whatever they configured them with. The
one row that mentions it compares `os.stat()` (size, mtime_ns) before and
after the whole run, which is the only way to say "untouched" without opening
the file (the hard rule in this task, and principle 7's own point: a check
that silently corrupted the thing it was meant to guard is worse than none).

Each behaviour is checked against a hand-built settings file that also carries
other people's hooks on the same events, in other groups, and unrelated
top-level keys — so "preserved exactly" is a real claim, not "the file still
parses". The control at the end is six mutants, one per promise above plus
`command_for`'s `|| true` and `plan`'s idempotence check; each is expected to
turn at least one row wrong.
"""
from __future__ import annotations

import builtins
import io
import json
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from src import hooks                                                 # noqa: E402
import install_hooks                                                  # noqa: E402


class Sheet:
    def __init__(self, quiet: bool = False):
        self.quiet, self.bad = quiet, 0

    def row(self, what: str, got, want) -> None:
        good = got == want
        self.bad += not good
        if not self.quiet:
            print(f"    {what:<58} {'ok' if good else f'<-- WRONG: {got!r}, wanted {want!r}'}")

    def ok(self) -> bool:
        return not self.bad


def box() -> Path:
    return Path(tempfile.mkdtemp(prefix="wobble-install-hooks-check-"))


def safe_stat(path: Path):
    """Size and mtime only — never opened. `None` if it does not exist."""
    try:
        st = path.stat()
    except OSError:
        return None
    return (st.st_size, st.st_mtime_ns)


def run_main(argv: list[str], answers: list[str] | None = None):
    """`install_hooks.main(argv)` in-process, stdin's `input()` scripted.

    Returns `(rc, exit_code, output)`: `rc` is the return value when `main`
    returns normally (`exit_code` then `None`); `exit_code` is `SystemExit`'s
    argument when it raises instead (`rc` then `None`, since it never returns).
    """
    old_input = builtins.input
    queue = list(answers or [])
    builtins.input = lambda prompt="": (queue.pop(0) if queue else "n")
    buf = io.StringIO()
    rc = exit_code = None
    try:
        with redirect_stdout(buf):
            try:
                rc = install_hooks.main(argv)
            except SystemExit as exc:
                exit_code = exc.code
    finally:
        builtins.input = old_input
    return rc, exit_code, buf.getvalue()


def backups_in(directory: Path) -> list[str]:
    return sorted(p.name for p in directory.glob("*.wobble-backup-*"))


def tmp_leftovers_in(directory: Path) -> list[str]:
    return sorted(p.name for p in directory.glob("*.wobble-tmp"))


def entries_for(data: dict, event: str) -> list[str]:
    """Every command string wired to `event`, group order preserved."""
    return [entry.get("command") for group in data.get("hooks", {}).get(event, [])
            for entry in group.get("hooks", [])]


# ---------------------------------------------------------------------------
# The table. Runs once honestly, then once per mutant (quiet=True).
# ---------------------------------------------------------------------------

def checks(sheet: Sheet) -> None:
    script = install_hooks.HOOK_SCRIPT      # the real tools/hook_event.sh's
    LOG = install_hooks.LOG                 # path — named in strings, never run

    # ---- command_for: the exact shape --------------------------------------
    sheet.row("command_for's shape: <script> <what> >/dev/null 2>>LOG || true",
              install_hooks.command_for("done", script),
              f"{script} done >/dev/null 2>>{LOG} || true")

    # ---- a missing settings file, --yes ------------------------------------
    d = box()
    settings = d / "settings.json"
    rc, exit_code, out = run_main(["--settings", str(settings), "--yes"])
    sheet.row("missing file + --yes: main() returns 0, no SystemExit", (rc, exit_code), (0, None))
    sheet.row("...and creates the file", settings.exists(), True)
    data = json.loads(settings.read_text()) if settings.exists() else {}
    for event, what in install_hooks.HOOK_FOR.items():
        sheet.row(f"...{event}: one entry, shaped exactly like command_for's",
                  entries_for(data, event), [install_hooks.command_for(what, script)])
    sheet.row("...no backup for a file that did not exist", backups_in(d), [])
    sheet.row("...no .wobble-tmp left behind", tmp_leftovers_in(d), [])
    ok, sentence = hooks.wiring(settings, script)
    sheet.row("...and hooks.wiring(tmp) now says ok", ok, True)

    # ---- an existing file with other people's hooks + unrelated keys ------
    d = box()
    settings = d / "settings.json"
    other_group = {"matcher": "Bash", "hooks": [
        {"type": "command", "command": "/opt/other-tool/notify.sh done"}]}
    original = {
        "otherTopLevelKey": {"nested": [1, 2, 3]},
        "hooks": {
            "Stop": [other_group],
            "UnrelatedEvent": [{"hooks": [{"type": "command", "command": "echo unrelated"}]}],
        },
    }
    settings.write_text(json.dumps(original, indent=2))
    original_bytes = settings.read_bytes()
    rc, exit_code, out = run_main(["--settings", str(settings), "--yes"])
    sheet.row("existing file + --yes: returns 0, no SystemExit", (rc, exit_code), (0, None))
    sheet.row("...says it wrote over a backup", "Written. Backup:" in out, True)
    data = json.loads(settings.read_text())
    sheet.row("...an unrelated top-level key is preserved exactly",
              data.get("otherTopLevelKey"), original["otherTopLevelKey"])
    sheet.row("...an unrelated event is preserved exactly",
              data["hooks"].get("UnrelatedEvent"), original["hooks"]["UnrelatedEvent"])
    sheet.row("...the other tool's group on Stop is untouched, ours appended beside it",
              data["hooks"].get("Stop"),
              [other_group, {"hooks": [{"type": "command",
                                        "command": install_hooks.command_for("done", script)}]}])
    for event, what in install_hooks.HOOK_FOR.items():
        if event == "Stop":
            continue
        sheet.row(f"...{event}: added fresh, one entry",
                  entries_for(data, event), [install_hooks.command_for(what, script)])
    made = backups_in(d)
    sheet.row("...exactly one backup was made", len(made), 1)
    sheet.row("...whose bytes equal the original, byte for byte",
              (d / made[0]).read_bytes() if made else None, original_bytes)
    sheet.row("...no .wobble-tmp left behind", tmp_leftovers_in(d), [])

    # ---- idempotence: a second run on the now-fully-wired file -------------
    before_bytes, before_mtime = settings.read_bytes(), settings.stat().st_mtime_ns
    rc, exit_code, out = run_main(["--settings", str(settings), "--yes"])
    sheet.row("second run: returns 0, no SystemExit", (rc, exit_code), (0, None))
    sheet.row("...says nothing to do, naming N from HOOK_FOR",
              f"Nothing to do — all {len(install_hooks.HOOK_FOR)} are already wired." in out, True)
    sheet.row("...bytes are byte-for-byte unchanged", settings.read_bytes(), before_bytes)
    sheet.row("...mtime is unchanged (no rewrite happened)", settings.stat().st_mtime_ns, before_mtime)
    sheet.row("...no second backup appeared", len(backups_in(d)), 1)

    # ---- a partial install: one of ours already there ----------------------
    d = box()
    settings = d / "settings.json"
    settings.write_text(json.dumps({"hooks": {"Stop": [
        {"hooks": [{"type": "command", "command": install_hooks.command_for("done", script)}]}]}}))
    rc, exit_code, out = run_main(["--settings", str(settings), "--yes"])
    expect_pending = len(install_hooks.HOOK_FOR) - 1
    sheet.row("partial install: returns 0, no SystemExit", (rc, exit_code), (0, None))
    sheet.row(f"...says {expect_pending} entries to add",
              f"{expect_pending} entries to add." in out, True)
    data = json.loads(settings.read_text())
    sheet.row("...Stop is not duplicated, still exactly one group",
              entries_for(data, "Stop"), [install_hooks.command_for("done", script)])
    for event, what in install_hooks.HOOK_FOR.items():
        if event == "Stop":
            continue
        sheet.row(f"...{event}: was missing, now added",
                  entries_for(data, event), [install_hooks.command_for(what, script)])

    # ---- invalid JSON: refuse, and never touch the file ---------------------
    d = box()
    settings = d / "settings.json"
    settings.write_text("{ this is not json, no closing brace")
    before_bytes = settings.read_bytes()
    rc, exit_code, out = run_main(["--settings", str(settings), "--yes"])
    sheet.row("invalid JSON: main() never returns, it raises SystemExit", (rc, exit_code is not None),
              (None, True))
    sheet.row("...naming the file and refusing to touch it",
              (str(settings) in str(exit_code), "is not valid JSON" in str(exit_code),
               "Refusing to touch it" in str(exit_code)),
              (True, True, True))
    sheet.row("...file bytes are untouched", settings.read_bytes(), before_bytes)

    # ---- asking (no --yes) ---------------------------------------------------
    d = box()
    settings = d / "settings.json"
    rc, exit_code, out = run_main(["--settings", str(settings)], answers=["n"])
    sheet.row("asked, answers n: returns 1, no SystemExit", (rc, exit_code), (1, None))
    sheet.row("...says nothing written", "Nothing written." in out, True)
    sheet.row("...and writes nothing at all", settings.exists(), False)
    rc, exit_code, out = run_main(["--settings", str(settings)], answers=["y"])
    sheet.row("asked, answers y: returns 0, no SystemExit", (rc, exit_code), (0, None))
    sheet.row("...and writes the file", settings.exists(), True)

    # ---- --print: shows, changes nothing -------------------------------------
    d = box()
    settings = d / "settings.json"
    expect_sentence = hooks.wiring(settings, script)[1]
    rc, exit_code, out = run_main(["--settings", str(settings), "--print"])
    sheet.row("--print on a missing file: returns 0, no SystemExit", (rc, exit_code), (0, None))
    sheet.row("...changes nothing — the file still does not exist", settings.exists(), False)
    sheet.row("...and prints wiring()'s own sentence", expect_sentence in out, True)

    run_main(["--settings", str(settings), "--yes"])              # now fully wire it
    before_bytes, before_mtime = settings.read_bytes(), settings.stat().st_mtime_ns
    expect_sentence = hooks.wiring(settings, script)[1]
    rc, exit_code, out = run_main(["--settings", str(settings), "--print"])
    sheet.row("--print on a wired file: returns 0, no SystemExit", (rc, exit_code), (0, None))
    sheet.row("...changes nothing — bytes and mtime unchanged",
              (settings.read_bytes(), settings.stat().st_mtime_ns), (before_bytes, before_mtime))
    sheet.row("...and prints wiring()'s ok sentence", expect_sentence in out, True)

    # ---- --uninstall: shared group, an ours-only event, unrelated stuff ------
    d = box()
    settings = d / "settings.json"
    shared_group = {"matcher": "Bash", "hooks": [
        {"type": "command", "command": "/opt/other-tool/notify.sh done"},
        {"type": "command", "command": install_hooks.command_for("done", script)},
    ]}
    ours_only_group = {"hooks": [
        {"type": "command", "command": install_hooks.command_for("needs", script)}]}
    original = {
        "otherTopLevelKey": "keep me",
        "hooks": {
            "Stop": [shared_group],
            "Notification": [ours_only_group],
            "UnrelatedEvent": [{"hooks": [{"type": "command", "command": "echo unrelated"}]}],
        },
    }
    settings.write_text(json.dumps(original, indent=2))
    original_bytes = settings.read_bytes()
    rc, exit_code, out = run_main(["--settings", str(settings), "--uninstall", "--yes"])
    sheet.row("uninstall: returns 0, no SystemExit", (rc, exit_code), (0, None))
    data = json.loads(settings.read_text())
    sheet.row("...the other tool's entry in the shared group survives, ours is gone",
              data["hooks"].get("Stop"),
              [{"matcher": "Bash", "hooks": [
                  {"type": "command", "command": "/opt/other-tool/notify.sh done"}]}])
    sheet.row("...an event that was only ever ours is dropped, not left empty",
              "Notification" in data.get("hooks", {}), False)
    sheet.row("...an unrelated event is untouched",
              data["hooks"].get("UnrelatedEvent"), original["hooks"]["UnrelatedEvent"])
    sheet.row("...an unrelated top-level key is untouched",
              data.get("otherTopLevelKey"), original["otherTopLevelKey"])
    made = backups_in(d)
    sheet.row("...exactly one backup was made", len(made), 1)
    sheet.row("...whose bytes equal the pre-uninstall original",
              (d / made[0]).read_bytes() if made else None, original_bytes)
    sheet.row("...no .wobble-tmp left behind", tmp_leftovers_in(d), [])

    # ---- --uninstall: nothing of ours -----------------------------------------
    d = box()
    settings = d / "settings.json"
    settings.write_text(json.dumps({"hooks": {"Stop": [
        {"hooks": [{"type": "command", "command": "/opt/other-tool/notify.sh done"}]}]}}))
    before_bytes, before_mtime = settings.read_bytes(), settings.stat().st_mtime_ns
    rc, exit_code, out = run_main(["--settings", str(settings), "--uninstall", "--yes"])
    sheet.row("uninstall, nothing of ours: returns 0, no SystemExit", (rc, exit_code), (0, None))
    sheet.row(f"...says nothing of ours in {settings.name}",
              f"Nothing of ours in {settings}." in out, True)
    sheet.row("...writes nothing at all",
              (settings.read_bytes(), settings.stat().st_mtime_ns), (before_bytes, before_mtime))
    sheet.row("...no backup appeared", backups_in(d), [])

    # ---- --uninstall: asking, answer n and answer y ---------------------------
    d = box()
    settings = d / "settings.json"
    settings.write_text(json.dumps({"hooks": {"Stop": [
        {"hooks": [{"type": "command", "command": install_hooks.command_for("done", script)}]}]}}))
    before_bytes, before_mtime = settings.read_bytes(), settings.stat().st_mtime_ns
    rc, exit_code, out = run_main(["--settings", str(settings), "--uninstall"], answers=["n"])
    sheet.row("uninstall, asked, answers n: returns 1, no SystemExit", (rc, exit_code), (1, None))
    sheet.row("...says nothing written", "Nothing written." in out, True)
    sheet.row("...writes nothing at all",
              (settings.read_bytes(), settings.stat().st_mtime_ns), (before_bytes, before_mtime))
    sheet.row("...no backup appeared", backups_in(d), [])
    rc, exit_code, out = run_main(["--settings", str(settings), "--uninstall"], answers=["y"])
    sheet.row("uninstall, asked, answers y: returns 0, no SystemExit", (rc, exit_code), (0, None))
    data = json.loads(settings.read_text())
    sheet.row("...and it is actually gone", "Stop" in data.get("hooks", {}), False)

    # ---- the script-missing and not-executable refusals in main() -------------
    saved_script = install_hooks.HOOK_SCRIPT
    try:
        d = box()
        install_hooks.HOOK_SCRIPT = d / "no-such-hook_event.sh"          # never tools/hook_event.sh
        rc, exit_code, out = run_main(["--settings", str(d / "settings.json"), "--yes"])
        sheet.row("main(): the script is missing -> SystemExit naming it",
                  (rc, exit_code is not None and "is missing — that is the hook itself" in str(exit_code)),
                  (None, True))

        d = box()
        not_exec = d / "hook_event.sh"                                    # a temp file, chmod'd, not tools/
        not_exec.write_text("#!/bin/sh\necho hi\n")
        not_exec.chmod(0o644)
        install_hooks.HOOK_SCRIPT = not_exec
        rc, exit_code, out = run_main(["--settings", str(d / "settings.json"), "--yes"])
        sheet.row("main(): the script is not executable -> SystemExit naming chmod +x",
                  (rc, exit_code is not None and "is not executable. Run: chmod +x" in str(exit_code)),
                  (None, True))
    finally:
        install_hooks.HOOK_SCRIPT = saved_script


def run_battery(quiet: bool) -> Sheet:
    """The whole table, with an unexpected exception counted as a wrong row
    rather than crashing the mutant loop — a mutant broken badly enough to
    raise has still been caught."""
    sheet = Sheet(quiet)
    try:
        checks(sheet)
    except SystemExit as exc:
        sheet.row("the battery completes without an unexpected SystemExit",
                  f"SystemExit({exc.code!r})", None)
    except Exception as exc:                                          # noqa: BLE001
        sheet.row("the battery completes without an unexpected exception",
                  f"{type(exc).__name__}: {exc}", None)
    return sheet


# ---------------------------------------------------------------------------
# Mutants: one rule removed at a time. Each must turn at least one row wrong.
# ---------------------------------------------------------------------------

def patch_plan_never_already():
    """`plan()` that forgets duplicates are already wired — every run looks
    like the first one, so a second install would double every entry."""
    original = install_hooks.plan

    def mutant(data, script):
        return {event: install_hooks.command_for(what, script)
                for event, what in install_hooks.HOOK_FOR.items()}

    install_hooks.plan = mutant
    return lambda: setattr(install_hooks, "plan", original)


def patch_read_swallow_invalid():
    """`read()` that reads invalid JSON as an empty file instead of refusing —
    the next `--yes` would silently overwrite whatever could not be parsed."""
    original = install_hooks.read

    def mutant(settings):
        if not settings.exists():
            return {}
        try:
            return json.loads(settings.read_text())
        except json.JSONDecodeError:
            return {}

    install_hooks.read = mutant
    return lambda: setattr(install_hooks, "read", original)


def patch_write_no_backup():
    """`write()` with the backup step removed."""
    original = install_hooks.write

    def mutant(settings, data):
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text(json.dumps(data, indent=2) + "\n")
        return None

    install_hooks.write = mutant
    return lambda: setattr(install_hooks, "write", original)


def _doomed(data, script):
    hooks_ = data.get("hooks", {})
    return [(event, entry.get("command", ""))
            for event in install_hooks.HOOK_FOR
            for group in hooks_.get(event, [])
            for entry in group.get("hooks", [])
            if str(script) in entry.get("command", "")]


def patch_uninstall_drops_whole_groups():
    """Uninstall that drops an ENTIRE group if any entry in it is ours,
    taking whatever other hook shared that group down with it."""
    original = install_hooks.uninstall

    def mutant(settings, script, ask):
        data = install_hooks.read(settings)
        hooks_ = data.get("hooks", {})
        doomed = _doomed(data, script)
        if not doomed:
            print(f"Nothing of ours in {settings}.")
            return 0
        if ask and input("Remove it? [y/N] ").strip().lower() not in ("y", "yes"):
            print("Nothing written.")
            return 1
        for event in install_hooks.HOOK_FOR:
            groups = [g for g in hooks_.get(event, [])
                      if not any(str(script) in e.get("command", "") for e in g.get("hooks", []))]
            if groups:
                hooks_[event] = groups
            else:
                hooks_.pop(event, None)
        backup = install_hooks.write(settings, data)
        print(f"\nRemoved. Backup: {backup}")
        return 0

    install_hooks.uninstall = mutant
    return lambda: setattr(install_hooks, "uninstall", original)


def patch_uninstall_leaves_empty_keys():
    """Uninstall that removes our entry from each group correctly, but never
    pops an event key once every group under it is gone."""
    original = install_hooks.uninstall

    def mutant(settings, script, ask):
        data = install_hooks.read(settings)
        hooks_ = data.get("hooks", {})
        doomed = _doomed(data, script)
        if not doomed:
            print(f"Nothing of ours in {settings}.")
            return 0
        if ask and input("Remove it? [y/N] ").strip().lower() not in ("y", "yes"):
            print("Nothing written.")
            return 1
        for event in install_hooks.HOOK_FOR:
            groups = []
            for group in hooks_.get(event, []):
                kept = [e for e in group.get("hooks", []) if str(script) not in e.get("command", "")]
                if kept:
                    groups.append({**group, "hooks": kept})
            hooks_[event] = groups            # never popped, even when []
        backup = install_hooks.write(settings, data)
        print(f"\nRemoved. Backup: {backup}")
        return 0

    install_hooks.uninstall = mutant
    return lambda: setattr(install_hooks, "uninstall", original)


def patch_command_for_no_true():
    """`command_for` with `|| true` dropped — a hook that fails can then
    block a prompt, which is the one thing the docstring says never happens."""
    original = install_hooks.command_for

    def mutant(what, script):
        return f"{script} {what} >/dev/null 2>>{install_hooks.LOG}"

    install_hooks.command_for = mutant
    return lambda: setattr(install_hooks, "command_for", original)


MUTANTS = (
    ("plan() that never sees already-wired (duplicates)", patch_plan_never_already),
    ("read() that returns {} on invalid JSON", patch_read_swallow_invalid),
    ("write() with no backup", patch_write_no_backup),
    ("uninstall that drops whole groups containing ours", patch_uninstall_drops_whole_groups),
    ("uninstall that leaves empty event keys", patch_uninstall_leaves_empty_keys),
    ("command_for without || true", patch_command_for_no_true),
)


def main() -> int:
    print(__doc__.strip().splitlines()[0])
    before_real = safe_stat(hooks.SETTINGS)

    sheet = run_battery(quiet=False)

    print("\n  mutants — each rule removed in turn must make the table wrong")
    survivors = 0
    for name, patcher in MUTANTS:
        restore = patcher()
        try:
            result = run_battery(quiet=True)
        finally:
            restore()
        survived = result.ok()
        survivors += survived
        print(f"    mutant: {name:<58} {'survived' if survived else 'caught'}")

    after_real = safe_stat(hooks.SETTINGS)
    sheet.row("the real ~/.claude/settings.json is untouched (os.stat only)", after_real, before_real)

    total_wrong = sheet.bad + survivors
    print("\n" + ("ALL CASES MATCH the known answer" if not total_wrong
                  else f"{total_wrong} WRONG — the rows above"))
    return 0 if not total_wrong else 1


if __name__ == "__main__":
    sys.exit(main())
