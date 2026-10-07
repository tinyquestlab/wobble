# Plan — S03

## Architecture

1. **The seam's menu learns two shapes** (`ports.py`, `macos.py`, `null.py`). They are plain
   data, as `Alternate` is:
   - `Checked(str)`: a label drawn with a native checkmark;
   - `Submenu(str)`: a label whose "handler" slot carries its own list of `(label, handler)`.
   A handler's tag stays its index, counted across the nested lists in order, so one table still
   routes every click. The null seam records a submenu as `["Settings", [...]]`, so a table reads
   the same words AppKit draws.
2. **A `Permissions` port** (`ports.py`, `macos.py`, `null.py`):
   - `state(kind) -> (str | None, why)`, where `kind` is `"bluetooth"`, `"accessibility"` or
     `"automation:<bundle>"`, and the state is `"granted"`, `"refused"`, `"not asked"` or `None`
     (could not be read);
   - `settings(kind) -> (ok, why)`, which opens that pane.

   The macOS side reads `AXIsProcessTrusted`, `CBManager.authorization`, and Automation by
   whatever task 01 finds. It never raises and never prompts.
3. **The menu** (`menubar.py`):
   - `permission_lines(...)` builds the alert lines for `items()`'s top;
   - `settings_menu(...)` builds the `Settings ›` list;
   - `title()` gains the `⚠`;
   - `login_line` becomes a `Checked` item inside the submenu.

   The menu only renders what the daemon hands it (principle 1). A new docstring paragraph
   covers principle 2: these lines are about the app and are not signals, as S02 argued for
   login.
4. **The daemon** (`daemon.py`): `offer()` reads the permissions on each refresh, next to
   `login`, and hands them over. `at_permission()` says a change once, like `at_login`. Each
   click calls `settings(kind)` and says the result.

## Files to touch

| File | Change |
|---|---|
| `src/platform_seam/ports.py` | `Checked`, `Submenu`, the `Permissions` Protocol |
| `src/platform_seam/macos.py` | the nested menu and checkmark in `Status.menu`; `Permissions` |
| `src/platform_seam/null.py`, `__init__.py` | null `Permissions`; recording nested menus |
| `src/mirrors/menubar.py` | alert lines, `⚠` in the title, `Settings ›`, login moved in |
| `src/daemon.py` | reading, saying, wiring |
| `tests/tables/check_permissions.py` (new), `tests/test_tables.py` | the port against a fake framework, with mutants |
| `tests/tables/check_menubar.py`, `check_seam.py`, `check_daemon_edges.py` | new rows; counts move |
| `requirements.txt` | only if task 01 needs a framework bleak does not already bring |
| `README.md`, `ROADMAP.md`, `docs/DESK-CHECKS.md`, `NOTES.md` | the menu, item 1 decided, item 2 built, Part B steps |

## Key decisions

- **Read on every refresh, not once at start.** Revoking takes effect at once (`Focus._trusted`
  says why), and the drawing promises that the line goes away by itself. A cached answer would
  show a grant the process lost hours ago.
- **The alert lines go at the top as well as ✗ in `Settings ›`.** Two places, on purpose: the
  top is what gets seen, and the submenu is where everything's state lives. Only the submenu was
  rejected, because a hidden ✗ is the silence this spec exists to end.
- **"Not asked" is not "refused".** An alert for a permission never asked would nag every new
  install about Automation for a Terminal it may never use.
- **The login line moves into `Settings ›` rather than staying above Quit.** One home for the
  app's own settings. S02's menu rows move with it; its words stay.
- **No Launch Services raise.** `spec.md` § Context gives the reason; ROADMAP records it as
  decided.

## Dependencies

- `CBManager.authorization` comes from `pyobjc-framework-CoreBluetooth`, which bleak already
  installs on macOS. Task 01 confirms it is in the venv.
- The pane URLs are not public API, and Apple has moved them before (Ventura renamed System
  Preferences). If one stops landing, the click says so: `openURL_` answers `False`, which is
  said.

## Gates this trips

- `tests/test_tables.py` row counts: `menubar`, `seam` and `daemon_edges`, plus a new
  `permissions` entry marked `mac`.
- `check_menubar.py`'s login rows and mutants (`login_below_the_separator` and others) are
  expected to fail until they are rewritten for the line's new home.
- `check_daemon_edges.py` mutants that quote `offer()`'s lines whole break if those lines move.
  S02 learnings: check them after any edit there.
