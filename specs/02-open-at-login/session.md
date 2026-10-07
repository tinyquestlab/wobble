# Session — 02-open-at-login

## Status: DONE · 2026-10-07 · committed; Part B step 30 waits for a logout

## Next
Committed in three (port, menu line, docs), not pushed. Part B step 30 at the next logout
(criterion 2 and the pane's click). The agent at `~/Library/LaunchAgents/local.wobble.login.plist`
is the port's own now, and on.

**Source branch:** main · **Working branch:** main
**Repo(s):** wobble · **PR:** none, solo repo

## Open decisions
None.

## Tasks status
6 of 6 (`tasks.md`).

## What was done
- 2026-10-07: task 06. Learnings promoted to `NOTES.md`; Outcome filled — criterion 2 and the
  pane's click wait for a logout (Part B step 30).
- 2026-10-07: task 05. `docs/no-developer-account-2026-10-07.md`: options A–E, recommendation A
  (as now). README's library count fixed to five.
- 2026-10-07: task 04. README, DESK-CHECKS Part B step 30, ROADMAP. The menu line clicked off and
  on at the desk, both said in the log, the agent rewritten and `enabled`.
- 2026-10-07: task 03. The login line above Quit, read every refresh; the log says it at start and
  on every change. Full suite green after one stale mutant in `check_daemon_edges.py` was re-aimed.
- 2026-10-07: task 02. The `Login` port — the LaunchAgent writer on macOS, a refusal in null —
  with `check_login.py` (35 rows, mutants caught) and Login in `check_seam.py`. Task 05 added: how
  other open-source Mac apps ship without a paid Apple Developer account, researched last.
- 2026-10-07: task 01. A real login started the app through the agent with its grants; BTM's
  verdict is readable, and its "off" survives a rewrite, so the menu gets a fourth state.
- 2026-10-07: spec chosen over Windows (phase 02) — the gap on the one platform in use. The switch
  goes in the menu, above Quit; mechanism a LaunchAgent calling `open`.

## Inputs ingested
None.

## Pre-compact snapshot
<!-- Written by pre-compact.sh on every compaction, replaced whole. Edit above, not here. -->

**2026-10-07 11:21** - branch `main`

Next open task: **05 — no paid Apple Developer account: what other open-source Mac apps do.** Asked on

### Uncommitted
```
 M README.md
 M ROADMAP.md
 M docs/DESK-CHECKS.md
 M requirements.txt
 M src/daemon.py
 M src/mirrors/menubar.py
 M src/platform_seam/__init__.py
 M src/platform_seam/macos.py
 M src/platform_seam/null.py
 M src/platform_seam/ports.py
 M tests/tables/check_daemon_edges.py
 M tests/tables/check_menubar.py
 M tests/tables/check_seam.py
 M tests/test_tables.py
?? specs/02-open-at-login/
?? tests/tables/check_login.py
```

### Recent commits
```
a341d66 doc [S01 #90 #91]: read back real use and close the spec again
4f02d2d feat [S01 #86 #87 #88 #89]: say each signal's life, away and back, a re-queue, and keep a row per end
93d9705 doc [S01]: read the usage logs into a baseline
8a10a05 doc [S01]: close the MVP spec's session as done
06fdc06 test [S01 #79]: widen the alternating raise past the presses
```
