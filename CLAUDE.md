# wobble

<!-- Personal project. This CLAUDE.md is committed to the repo (it's mine). -->
<!-- Inherits the global ~/.claude rules (plan-first, conventional commits, no AI attribution, etc). -->

Principles, non-goals and what this project refuses to become live in `constitution.md`.
Read it before proposing anything that adds a surface. It is not restated here.

## Stack & layout

Python 3.12, `bleak` for BLE, macOS only for now. No build step.

```
src/core/          the notification core: signals, the queue, the attention state machine
src/ball/          Poké Ball Plus over BLE — the protocol, as docs/PROTOCOL.md describes it
src/mirrors/       one file per surface: ball.py, menubar.py
src/platform_seam/ ports.py (Protocols) + macos.py + null.py — nothing OS-specific outside here
src/hooks.py       Claude Code's side: which hook means what, and reading var/events
src/log.py         the second copy of what the daemon says — one file per day
src/daemon.py      the one process that is always running: tail, queue, attend, signal
tools/app/         wobble.app's launcher and start script; tools/build_app.py builds it
config/            signals.json: which sound, which colour, which ladder, per event kind
docs/              PROTOCOL.md, HOW-THE-BALL-WORKS.md, DESK-CHECKS.md, references
specs/             one folder per spec (SDD)
var/               runtime state, gitignored — events, logs/, desk instruments
```

The core never imports a mirror and never imports the seam's macOS file. A mirror may only render
what the core hands it — see constitution principle 1.

## Run / test / build

```bash
python3.12 -m venv venv && venv/bin/pip install -r requirements.txt
# by name: the system python3 here is 3.9 — below bleak's floor of 3.10, and not the 3.12 we target
venv/bin/python3 -m src.daemon              # the daemon: holds the BLE link, tails the events
venv/bin/python3 tools/install_hooks.py     # wire the Claude Code hooks (restart Claude after)
venv/bin/python3 tools/build_app.py --install   # or as /Applications/wobble.app (task 50)
```

The app runs the same daemon from this repo (`tools/app/start`) and writes to `var/app.out`. Only
one daemon runs per events file, so quit the app before starting one from a terminal, or the other
way round. A terminal daemon stops with Ctrl-C, never Ctrl-Z: a suspended one keeps the ball's
link open (`kill -CONT <pid> && kill -INT <pid>` recovers it; spec 01, task 06). Rebuild the app only when `tools/app/launcher.c` or the repo's path changes: a grant is
pinned to the launcher's bytes, and `build_app.py` says whether they moved.

Verification is `docs/DESK-CHECKS.md`, by hand, with the ball. There is no automated suite during
the MVP and that is deliberate (constitution principle 3) — the suite is phase 02.

The daemon runs with no ball present: the menu bar mirror works alone, and shows that there is no
ball. That is the mode the whole thing is developed in.

## Conventions

- Everything written here is in English — code, identifiers, comments, docs, README, commit
  messages, specs, tasks, notes. We may talk in any language; the language of the conversation
  never decides the language of what lands in the repo.
- Plan before non-trivial changes; if unsure whether to act or plan, plan.
- Comments here cite their source — `docs/PROTOCOL.md` by section, the task a decision came from.
  That is this repo's convention and it wins over any global rule that forbids citing documents
  from code. Almost every fact in `src/ball/` is inherited from a sniffer capture nobody can
  casually re-run, and a claim with no source attached is how it turns into folklore.
- Commits: `<type> [S<NN> #<TT>]: <description>` — spec number + task number, imperative,
  no AI attribution (e.g. `feat [S01 #07]: play the repeat ladder for a done signal`).
  Docs-only -> `doc`. Outside any spec -> plain `<type>: <description>`.
- My own pace; no PR flow for now -- commit, and push when I want. If collaborators join, /cn-spec
  detects it on its own (repo contributors) and switches to a branch + PR per spec -- no config
  needed here unless I want to override that default.
- Not affiliated with Nintendo. Unofficial, non-commercial, and it stays that way. No Nintendo
  asset is ever committed to this repo — cries and art are fetched at install time, never shipped.

## References

Anything pasted in that isn't my own words — a quote, something said out loud, a screenshot, a
video/audio link, any external reference — goes in `docs/` at the repo root, not left buried in
chat, so it's still findable later. If it changes how we work here, fold the takeaway into
NOTES.md (decision/gotcha) or this file (convention worth keeping) — same sort /cn-spec's Learn
step already does with a spec's own learnings.md.

What is known about the ball lives in `docs/PROTOCOL.md`, each fact marked with how it is known
(capture, desk or sweep). Credits for third-party work are in `NOTICE.md`.

<!-- History, learnings & gotchas -> NOTES.md at the repo root (not auto-loaded every session). -->
