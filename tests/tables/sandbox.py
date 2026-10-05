#!/usr/bin/env python3
"""A throwaway repo-shaped tree, so a desk check never writes to `var/events`.

`tools/hook_event.sh` takes its events path from its own location — it is always
one level under the repo root and appends to `../var/events` — so a copy of it
under a temporary directory appends into that directory instead. The script is
copied, not symlinked: it resolves its own path with `pwd -P`, and a symlink
would resolve straight back to the repo.

**Why this exists.** `var/events` is the file a daemon somebody is actually
using is tailing. A check that unlinks it makes that daemon count a restart, and
every signal the check fires is a signal the real ball then plays — a phantom
`done` crying in a pocket while its owner is away from the desk. Nothing breaks
loudly: `hooks.Tail` opens by path and handles the file shrinking, which is
precisely why the collision went unnoticed. It is the same fault as Part D.9 of
`docs/DESK-CHECKS.md`, one layer down: two processes on one events file say
nothing about each other.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REAL_HOOK = ROOT / "tools" / "hook_event.sh"
REAL_EVENTS = ROOT / "var" / "events"


class Sandbox:
    """A `tools/` and a `var/` under a temp dir, with the real hook script."""

    def __init__(self) -> None:
        self.dir = Path(tempfile.mkdtemp(prefix="wobble-desk-"))
        (self.dir / "tools").mkdir()
        (self.dir / "var").mkdir()
        self.hook = self.dir / "tools" / "hook_event.sh"
        shutil.copy2(REAL_HOOK, self.hook)      # copy2 keeps the execute bit
        self.events = self.dir / "var" / "events"
        self.events.touch()

    def fire(self, what: str, session: str, project: str, extra: str = "",
             host: str = "") -> None:
        """A real Claude Code hook call, through the real script.

        `extra` is raw JSON members appended to the payload, e.g.
        `"notification_type":"idle_prompt"` (task 39). `host` is the app the
        session runs in (task 38), empty unless asked for: inherited, it would
        be whatever app launched the check, and a live leg would then pass only
        with that app in front.
        """
        payload = (f'{{"session_id":"{session}","cwd":"/Users/x/{project}",'
                   f'"hook_event_name":"t"{"," + extra if extra else ""}}}')
        env = {**os.environ, "__CFBundleIdentifier": host}
        subprocess.run([str(self.hook), what], input=payload, text=True, check=True,
                       env=env)

    def scribble(self, text: str) -> None:
        """Something that is not a hook line, appended where the hooks write."""
        with self.events.open("a") as handle:
            handle.write(text + "\n")

    def reset(self) -> None:
        """Empty it between scenarios. The path stays, so the tree stays valid."""
        self.events.write_text("")

    def prove_isolated(self) -> str:
        """Fire one event and check where it actually landed.

        Comparing the copied script against the original would prove nothing —
        it was copied a moment ago. What can genuinely go wrong is the copy
        writing somewhere other than here, so this asks the filesystem: the
        sandbox file has to grow and the repo's has to be untouched. Raises
        rather than returning a verdict nobody reads.
        """
        live_before = REAL_EVENTS.stat().st_size if REAL_EVENTS.exists() else None
        mine_before = self.events.stat().st_size
        self.fire("done", "isolation-probe", "nowhere")
        live_after = REAL_EVENTS.stat().st_size if REAL_EVENTS.exists() else None
        if self.events.stat().st_size <= mine_before:
            raise SystemExit(f"the hook wrote nothing to {self.events}")
        if live_after != live_before:
            raise SystemExit(f"the hook wrote to {REAL_EVENTS} — a live daemon "
                             f"would have played every signal this check fires")
        self.reset()
        return f"{self.events} (the real hook script, writing nowhere near var/)"
