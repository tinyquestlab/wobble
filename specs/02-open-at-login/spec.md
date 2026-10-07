# S02 — wobble.app opens at login

**Source branch:** main · **Working branch:** main
**Repo(s):** wobble

## Context

`ROADMAP.md`, "Half placed — wobble as an app": the first of its three remaining items. Today
wobble runs only after someone opens it, so every login after a restart is a stretch of silence
that looks like "nothing is waiting" — the failure principle 7 is written against. It also leaves
holes in `var/logs/signals.tsv` during the weeks S01's session left for reading real use.
`tools/build_app.py` already installs into `/Applications` with this step in mind.

## What to build

A line in the menu bar's menu, above Quit, that switches opening at login on and off. On is a
per-user LaunchAgent that opens `/Applications/wobble.app` through Launch Services when you log in,
exactly as a double-click would, so the app's grants (Bluetooth, Accessibility) are untouched. Off
removes it. It starts off; nothing turns it on but that line.

## Acceptance criteria

1. **On, then log out and in** → wobble.app is running, with the same Bluetooth and Accessibility
   grants as before (B raises a window, the ball connects), with no prompt from macOS.
2. **Off, then log out and in** → wobble does not start.
3. **The line says what a click will do, and the truth on disk decides it** → "Open wobble at
   login" when it is off, "Stop opening wobble at login" when it is on. Read again on every
   refresh, so a file removed by hand is never shown as still on.
4. **Switched off in System Settings** (General › Login Items & Extensions › App Background
   Activity) → the menu says so in words, never claims it is on, and its click opens that pane:
   macOS keeps that "off" past a rewrite of the file, so only the person can lift it (task 01).
5. **Every refusal is said** → no `/Applications/wobble.app`, a file that cannot be written or
   removed, the null seam: a greyed line or a log line in words, never a click that does nothing.
6. **The quit door is unchanged** → Quit still ends the run, and an app opened at login quits the
   same way. Nothing restarts it until the next login.
7. **The suite stays green**, with a table for the new seam port and the menu line, and Part B of
   `docs/DESK-CHECKS.md` has the one step only a logout can answer.

## Approach

See `plan.md`: a `Login` port in the seam, a LaunchAgent file as the macOS side, a menu line wired
like Quit and Mute. Measured first (task 01), built after.

## Edge cases

- **Started from a terminal.** The line still works: it points at the installed app, not at the
  process that clicked it. With no app in `/Applications`, it is greyed and says why.
- **The app deleted later, the agent left behind.** `open` fails at login with nobody to see it.
  Uninstall in README removes the file; the daemon also says at start when the agent points at an
  app that is not there.
- **A terminal daemon already running at login.** Cannot happen at login itself; later, the
  existing "another wobble daemon is already running" refusal covers it.
- **Logged in, then on.** Nothing starts now — it is already running. The agent is only read at
  the next login.
- **Background Items notification.** macOS 13+ shows "Background Items Added" when the file
  appears. Expected, not an error; README names it.

## Glossary & concepts (learning)

- **LaunchAgent** — a small `.plist` in `~/Library/LaunchAgents` that tells `launchd` (the Mac's
  process starter) to run a command for this user, here once at login (`RunAtLoad`).
- **SMAppService** — Apple's newer API for login items (macOS 13+). Only the app's own process can
  register itself with it, which here would mean changing the launcher's bytes.
- **Launch Services / `open`** — what the Finder uses to start an app. Starting wobble through it
  keeps it the same app in macOS's eyes, so its grants hold.
- **BTM (Background Task Management)** — the macOS 13+ list behind System Settings › Login Items.
  It can switch an agent off while its file stays in place.

## Open questions

1. ~~Can wobble read BTM's verdict without root?~~ **Yes** (task 01): `SMAppService.
   statusForLegacyURL_` reads `enabled` / `requiresApproval` / `notRegistered`, via
   `pyobjc-framework-ServiceManagement`, a new dependency.

## Outcome

| # | Criterion | Result |
|---|---|---|
| 1 | On, log out and in → running, with its grants | ✅ task 01, a real login: B raised a window, no prompt; the port writes the same bytes (`plutil -p`, 11:18) |
| 2 | Off, log out and in → not started | ⏳ by construction (no file, nothing for `launchd`); Part B step 30 at the next logout |
| 3 | The line says what a click will do, read from disk | ✅ `check_menubar.py`; at the desk, off and on again from the menu, both in `var/app.out` |
| 4 | Switched off in System Settings → said, never "on", click opens the pane | ✅ in the tables (`check_login.py`, `check_menubar.py`); the pane's click at the desk is Part B step 30 |
| 5 | Every refusal said | ✅ `check_login.py` (no app, unwritable folder, macOS unreachable), `check_seam.py` (null), greyed line |
| 6 | Quit unchanged | ✅ `check_menubar.py`'s Quit rows; no `KeepAlive` in the agent |
| 7 | Suite green, a table for the port and the line, a Part B step | ✅ 25 passed, slow included; `check_login.py` 35 rows; step 30 |

---
