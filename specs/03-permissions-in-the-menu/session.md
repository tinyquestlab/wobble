# Session — 03-permissions-in-the-menu

## Status: done · 2026-10-07 · all 7 tasks built; Part B step 31 passed for Accessibility

## Next
By hand: step 31's Bluetooth leg, if wanted, and spec 02's step 30 at the next logout.

**Source branch:** main · **Working branch:** main
**Repo(s):** wobble · **PR:** none, solo repo

## Open decisions
None. The menu's shape was approved from `var/drawings/spec03-menu.html`.

## Tasks status
7 of 7 (`tasks.md`).

## What was done
- 2026-10-07: spec written. The ROADMAP's Launch Services raise is decided not to do (`spec.md` §
  Context).
- 2026-10-07: task 01 measured the three reads and the panes from a terminal.
- 2026-10-07: tasks 02–05 built: the seam's submenu and checkmark, the `Permissions` port, the menu
  (alerts, ⚠, `Settings ›`, login moved in), the daemon reading every 2 s.
- 2026-10-07: tasks 06–07: README, ROADMAP, DESK-CHECKS step 31; learnings sorted into NOTES.md.
- 2026-10-07: Part B step 31 in wobble.app: revoked 17:08:19, pane opened 17:08:41, granted
  17:08:47, all said once; focus read again with no restart.

## Inputs ingested
None.

## Pre-compact snapshot
<!-- Written by pre-compact.sh on every compaction, replaced whole. Edit above, not here. -->

**2026-10-07 16:32** - branch `main`

Next open task: **02 — the seam's menu: a submenu and a checkmark.** `Checked` and `Submenu` in

### Uncommitted
```
 M src/mirrors/menubar.py
 M src/platform_seam/__init__.py
 M src/platform_seam/macos.py
 M src/platform_seam/null.py
 M src/platform_seam/ports.py
 M tests/tables/check_menubar.py
 M tests/tables/check_seam.py
 M tests/test_tables.py
?? specs/03-permissions-in-the-menu/
?? tests/tables/check_menu_shapes.py
?? tests/tables/check_permissions.py
```

### Recent commits
```
bde5ab8 doc [S02 #01 #04 #05 #06]: measure, document and close opening at login
5e11dca feat [S02 #03]: switch opening at login from the menu, and say it in the log
6133c51 feat [S02 #02]: add the Login seam port, a LaunchAgent on macOS
a341d66 doc [S01 #90 #91]: read back real use and close the spec again
4f02d2d feat [S01 #86 #87 #88 #89]: say each signal's life, away and back, a re-queue, and keep a row per end
```
