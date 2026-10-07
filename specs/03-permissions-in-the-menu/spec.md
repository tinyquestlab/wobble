# S03 — wobble says a missing permission in its menu

**Source branch:** main · **Working branch:** main
**Repo(s):** wobble

## Context

`ROADMAP.md`, "Half placed — wobble as an app": the last two items.

The second item is the one built here. Without a terminal, a permission wobble lost reaches only
`var/app.out` and the day's log, which nobody opens. A grant is pinned to the launcher's bytes,
so a rebuild drops it, and the person can also switch it off in System Settings. Either way B
stops raising windows with nothing on screen saying so. That is the silent failure principle 7
forbids ("every missing permission says so in words, where the person can see it"). A menu line
for this was put off on 2026-09-30, to wait for a settings screen. It was reopened on 2026-10-07:
a submenu is not a window, so it needs no amendment to `constitution.md`.

The first item, raising windows through Launch Services so that Accessibility might not be
needed, is **decided not to do** (2026-10-07). Accessibility also reads the front window's title,
which is how a signal stays quiet while you look at its session. No route that needs no
permission can do that: the window server's own title needs Screen Recording. So wobble.app would
still ask for Accessibility, and the gain would be a better raise only for someone who refused
it. The user had parked this twice before (2026-09-29 and 2026-10-01).

## What to build

Drawn in `var/drawings/spec03-menu.html`. It is local and gitignored, and was approved on 2026-10-07.

- **An alert line at the top of the menu for each missing permission.** It is shown only while the
  permission is missing, says what stops working, and its click opens the right System Settings
  pane. For example: `⚠ Accessibility off — B raises no window   Open…`.
- **A `⚠` in the menu bar title** while any alert line is showing.
- **A `Settings ›` submenu**, above Quit. It shows the state of every permission all the time (✓
  is a line to read, ✗ is a click to the pane) and the login switch from S02, moved in as a
  native checkmark item.
- **A log line** whenever a permission changes, worded like the S02 login lines.

## Acceptance criteria

1. **Accessibility revoked while wobble.app runs** → within one menu refresh, the menu has the
   alert line, the title has `⚠`, and `Settings ›` shows ✗. Clicking either one opens Privacy &
   Security › Accessibility. No restart is needed.
2. **Granted again** → the alert line and `⚠` go away by themselves, and `Settings ›` shows ✓.
3. **Bluetooth refused** (denied, not merely the radio off) → an alert line of its own. The radio
   being off is still said by the link line, as today, and only there.
4. **Automation refused for a terminal wobble has asked** (today, only Terminal) → an alert line,
   and ✗ in `Settings ›` for that app. An app never asked is not listed.
5. **The login switch lives in `Settings ›`**, as a checkmark item that toggles. Its disabled
   and cannot-be-set states keep S02's words and clicks.
6. **Every permission change is said in the log**, once per change, with what stops working.
7. **Nothing that could not be read is shown as granted.** An unknown state is said in words, as
   a greyed line, and is never shown as ✓.
8. **The null seam and a `--no-menubar` run are unchanged**, apart from the log lines.
9. **The suite stays green.** There are tables for the new port and the menu's new shape, and
   Part B of `docs/DESK-CHECKS.md` gets the steps only a real revoke can answer.

## Approach

See `plan.md`. A `Permissions` port is added to the seam (it reads each permission and opens its
pane), and the seam's menu learns two shapes, a submenu and a checkmark. Measurement comes first,
in task 01: how Bluetooth and Automation can be read without asking, and the pane URLs on this
macOS. Building comes after.

## Edge cases

- **The first Accessibility call costs ~0.5 s per process** (S01 learnings, 2026-09-22). It is
  paid once at start already, so a read on each refresh does not pay it again.
- **A permission that was never asked** (Bluetooth before the first connect, Automation before
  Terminal is in front) is not "missing" and gets no alert line. In `Settings ›` it reads as not
  asked yet.
- **Several missing at once** → one alert line each, worst first: Bluetooth, then Accessibility,
  then Automation. Without the ball, wobble is the menu bar alone.
- **Started from a terminal** → the grants belong to the terminal app, not wobble (task 48,
  `responsible=`). The lines say what is true for this process, and the pane they open is the
  same one.
- **The menu is open when a permission changes** → it shows the change on its next rebuild, as
  every other line does.

## Glossary & concepts (learning)

- **TCC** (Transparency, Consent and Control): the macOS database behind Privacy & Security. It
  records which app may use Bluetooth, Accessibility and Automation, and pins each grant to the
  app's code signature.
- **Automation**: the permission for one app to send Apple events to another. wobble needs it to
  pick Terminal's tab. It is granted per pair of apps, so it is listed per target app.
- **`x-apple.systempreferences:` URLs**: links that open a given pane of System Settings, for
  example Privacy & Security › Accessibility.
- **Submenu**: an `NSMenuItem` with its own `NSMenu`. It opens beside the parent menu, so it is
  still a menu and not a window.

## Open questions

1. ~~Can Bluetooth's authorization be read without prompting?~~ Yes: the class method
   `CBManager.authorization()` answers 0–3 with no prompt. Whether it is the app's own answer is
   read in Part B, from the log task 05 writes.
2. ~~Can Automation for Terminal be read without asking?~~ Yes, with one gap:
   `AEDeterminePermissionToAutomateTarget` with `askUserIfNeeded=False` answers 0, -1743 or -1744,
   but -600 while Terminal is not running. The daemon keeps its last answer then.
3. ~~Do the pane URLs still land on macOS 26?~~ Yes, both forms. The classic
   `com.apple.preference.security?Privacy_<Pane>` is kept.

## Outcome

| # | Criterion | Result |
|---|---|---|
| 1 | Accessibility revoked → alert, ⚠, ✗, pane | built; within 2 s, not one refresh (learnings.md). `check_menubar`, `check_daemon_edges`; the app itself is Part B step 31 |
| 2 | Granted again → both go by themselves | built; `check_daemon_edges`; Part B step 31 |
| 3 | Bluetooth refused → its own line; radio off stays the link's | built; `check_menubar` row, `check_daemon_edges` with a ball |
| 4 | Automation refused → alert and ✗; never asked not listed | built; `check_menubar`, `check_permissions` |
| 5 | Login switch in `Settings ›`, checkmark | built; `check_menubar`, `check_menu_shapes` |
| 6 | Each change said once | built; `check_daemon_edges` |
| 7 | Unreadable never shown as granted | built; `check_permissions`, `check_menubar` |
| 8 | Null seam and `--no-menubar` unchanged but the log | null `Permissions` has no kinds; `check_seam`, `check_menubar` |
| 9 | Suite green, Part B steps | full suite green; Part B step 31 added, waiting for the desk |

---
