#!/usr/bin/env python3
"""Wire this project's Claude Code hooks, and show exactly what it adds.

    venv/bin/python3 tools/install_hooks.py            # show, then ask
    venv/bin/python3 tools/install_hooks.py --print    # show only, change nothing
    venv/bin/python3 tools/install_hooks.py --yes      # no question
    venv/bin/python3 tools/install_hooks.py --uninstall

**This edits a file that belongs to the person, not to the project**, so it
behaves like it: it prints the exact block first, it never touches a hook it did
not write (there are other people's hooks in there), it backs the file up before
writing, and it writes through a temporary file so a half-written
`settings.json` can never exist — that one would break Claude Code itself, not
just this.

It is idempotent. Running it twice adds nothing the second time, because the
entry is recognised by the script path it runs.

Restart Claude Code afterwards: hooks are read when a session starts.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.hooks import HOOK_FOR, HOOK_SCRIPT, SETTINGS, wiring    # noqa: E402

LOG = "/tmp/wobble-hook.log"


def command_for(what: str, script: Path) -> str:
    """The command line, shaped like the ones already in there.

    `>/dev/null` because a hook's stdout is read by Claude Code; `2>>` a log
    because a hook's stderr would otherwise vanish, and `|| true` because a hook
    that can fail is a hook that can block a prompt. The script already exits 0
    on every path — this is the second lock on the same door.
    """
    return f"{script} {what} >/dev/null 2>>{LOG} || true"


def read(settings: Path) -> dict:
    if not settings.exists():
        return {}
    try:
        return json.loads(settings.read_text())
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"{settings} is not valid JSON ({exc}). Refusing to touch it — "
            f"rewriting a settings file we cannot parse would lose whatever is "
            f"in there. Fix the JSON and run this again.")


def plan(data: dict, script: Path) -> dict[str, str]:
    """Which hook events need an entry, and what is already there."""
    hooks = data.get("hooks", {})
    out = {}
    for event, what in HOOK_FOR.items():
        already = any(str(script) in entry.get("command", "")
                      for group in hooks.get(event, [])
                      for entry in group.get("hooks", []))
        out[event] = "already wired" if already else command_for(what, script)
    return out


def write(settings: Path, data: dict) -> Path | None:
    """Back up, then replace atomically. Returns the backup path, if any."""
    backup = None
    if settings.exists():
        backup = settings.with_suffix(
            settings.suffix + f".wobble-backup-{time.strftime('%Y%m%d-%H%M%S')}")
        shutil.copy2(settings, backup)
    settings.parent.mkdir(parents=True, exist_ok=True)
    temp = settings.with_suffix(settings.suffix + ".wobble-tmp")
    temp.write_text(json.dumps(data, indent=2) + "\n")
    os.replace(temp, settings)     # atomic: the file is never half-written
    return backup


def install(settings: Path, script: Path, ask: bool) -> int:
    data = read(settings)
    todo = plan(data, script)
    pending = {e: c for e, c in todo.items() if c != "already wired"}

    print(f"\nsettings file: {settings}")
    print(f"hook script:   {script}\n")
    for event, what in HOOK_FOR.items():
        line = todo[event]
        print(f"  {event:<18} -> {line}")
    if not pending:
        # Counted from `HOOK_FOR` rather than spelled out: this said "all three"
        # until task 22 added a fourth, and a sentence that has to be remembered
        # is one that goes stale the moment nobody does.
        print(f"\nNothing to do — all {len(HOOK_FOR)} are already wired.")
        return 0

    other = sum(len(g.get("hooks", [])) for e in HOOK_FOR
                for g in data.get("hooks", {}).get(e, []))
    print(f"\n{len(pending)} entr{'y' if len(pending) == 1 else 'ies'} to add. "
          f"{other} hook(s) already on those events stay exactly as they are.")

    if ask:
        answer = input("\nWrite it? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("Nothing written.")
            return 1

    hooks = data.setdefault("hooks", {})
    for event, command in pending.items():
        hooks.setdefault(event, []).append(
            {"hooks": [{"type": "command", "command": command}]})
    backup = write(settings, data)
    print(f"\nWritten. Backup: {backup}" if backup else "\nWritten (no previous file).")
    print("Restart Claude Code — hooks are read when a session starts.")
    return 0


def uninstall(settings: Path, script: Path, ask: bool) -> int:
    data = read(settings)
    hooks = data.get("hooks", {})
    doomed = [(event, entry.get("command", ""))
              for event in HOOK_FOR
              for group in hooks.get(event, [])
              for entry in group.get("hooks", [])
              if str(script) in entry.get("command", "")]
    if not doomed:
        print(f"Nothing of ours in {settings}.")
        return 0
    print(f"\nWould remove from {settings}:")
    for event, command in doomed:
        print(f"  {event:<18} -> {command}")
    if ask and input("\nRemove it? [y/N] ").strip().lower() not in ("y", "yes"):
        print("Nothing written.")
        return 1

    for event in HOOK_FOR:
        groups = []
        for group in hooks.get(event, []):
            kept = [e for e in group.get("hooks", []) if str(script) not in e.get("command", "")]
            if kept:
                groups.append({**group, "hooks": kept})
        if groups:
            hooks[event] = groups
        else:
            hooks.pop(event, None)
    backup = write(settings, data)
    print(f"\nRemoved. Backup: {backup}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="python3 tools/install_hooks.py", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--settings", default=str(SETTINGS),
                    help=f"which settings file to wire (default: {SETTINGS}, the "
                         f"one that covers every project — a project-scoped file "
                         f"would only notify for this repo)")
    ap.add_argument("--print", dest="show", action="store_true",
                    help="show what would be added and change nothing")
    ap.add_argument("--yes", action="store_true", help="do not ask")
    ap.add_argument("--uninstall", action="store_true", help="take ours back out")
    args = ap.parse_args(argv)

    settings, script = Path(args.settings).expanduser(), HOOK_SCRIPT
    if not script.exists():
        raise SystemExit(f"{script} is missing — that is the hook itself")
    if not os.access(script, os.X_OK):
        raise SystemExit(f"{script} is not executable. Run: chmod +x {script}")

    if args.uninstall:
        return uninstall(settings, script, ask=not args.yes)
    if args.show:
        data = read(settings)
        print(f"\nsettings file: {settings}\nhook script:   {script}\n")
        for event, line in plan(data, script).items():
            print(f"  {event:<18} -> {line}")
        print(f"\n{wiring(settings, script)[1]}")
        return 0
    return install(settings, script, ask=not args.yes)


if __name__ == "__main__":
    sys.exit(main())
