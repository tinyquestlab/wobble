# Plan — S02

## Architecture

1. **A `Login` port** in `src/platform_seam/ports.py`: `state()` → `(on, why)` and `set(on)` →
   `(ok, why)`, in the seam's usual `(value, words)` shape. Opening at login is OS-specific, so it
   lives behind the seam (principle 6); Windows and Linux get their own file later.
2. **The macOS side** in `src/platform_seam/macos.py`: writes or removes
   `~/Library/LaunchAgents/local.wobble.login.plist` — `ProgramArguments` `/usr/bin/open
   /Applications/wobble.app`, `RunAtLoad`, `LimitLoadToSessionType` `Aqua`,
   `AssociatedBundleIdentifiers` `local.wobble` (so Login Items shows wobble's name), no
   `KeepAlive`. `state()` is the file on disk and BTM's verdict on it (`SMAppService.
   statusForLegacyURL_`), read every time, in four answers:

   | File | BTM | Menu line | Its click |
   |---|---|---|---|
   | none | — | Open wobble at login | write the file |
   | there | `enabled`, or `notFound` (BTM lags a write by ~2 s) | Stop opening wobble at login | remove it |
   | there | `requiresApproval` | Off in Login Items — open System Settings | `openSystemSettingsLoginItems()` |
   | — | no `/Applications/wobble.app` | greyed: needs wobble.app in /Applications | none |
3. **The null side** in `src/platform_seam/null.py`: refuses in words, like every other null port.
4. **The menu line** in `src/mirrors/menubar.py`: `items(..., login=..., on_login=...)`, one line
   above the separator over Quit, wired in `src/daemon.py` next to `on_quit`.
5. **The log**: one line on each switch and one at start saying whether it is on, so a day's log
   answers "did it start by itself".

## Files to touch

| File | Change |
|---|---|
| `src/platform_seam/ports.py` | the `Login` Protocol |
| `src/platform_seam/macos.py` | the LaunchAgent writer/reader |
| `src/platform_seam/null.py` | the refusal |
| `src/mirrors/menubar.py` | the line, its two labels, its docstring paragraph |
| `src/daemon.py` | wiring, the start line, the switch's log line |
| `tests/tables/check_login.py` + `tests/test_tables.py` | new table: plist shape, on/off/refusals, against a temp dir |
| `tests/tables/check_menubar.py` | rows for the line's labels and its place above Quit |
| `requirements.txt` | `pyobjc-framework-ServiceManagement`, for BTM's verdict (task 01) |
| `README.md`, `docs/DESK-CHECKS.md`, `ROADMAP.md` | how to switch it, uninstall, Part B step, the item ticked |

## Key decisions

- **A LaunchAgent that calls `open`, not SMAppService.** SMAppService registers only the calling
  app's own bundle; the daemon is Python, a child of the launcher, so the call would have to live in
  `tools/app/launcher.c` — new bytes, every grant asked again (task 48). A LaunchAgent changes no
  byte of the bundle. A System Events "login item" was the third road: it needs an Automation grant
  of its own, which is worse than none.
- **`open` and not the bundle's executable directly.** Run by `launchd`, the launcher would be
  started outside Launch Services; whether macOS then holds it responsible the same way is a
  question task 48 never measured. `open` is the double-click, which it did.
- **Labels follow Mute's rule, not a checkmark.** "The label says what the click will do"
  (`menubar.items`). A ✓ would need a new seam type for one line; the menu already has an idiom.
- **The file is the truth, read every refresh, never cached.** A copy in memory is the menu
  claiming something the disk no longer says.
- **Principle 2: the same boundary as Quit.** Opening at login is not a signal, a state or a queue;
  it is how the process gets started, which the ball cannot do either. The docstring says so.
- **Off by default.** Turning on something that runs at every login is the person's call.
- **BTM's "off" wins, and wobble never works around it.** Task 01: switched off in System Settings,
  the file stays and a rewrite does not lift it. Removing and rewriting to force it would be fighting
  the person's own switch; the line sends them to the pane instead.

## Dependencies

- macOS 13+ (BTM). This Mac is 26.6.2.
- `/Applications/wobble.app` built by `tools/build_app.py --install`. Moving or rebuilding the repo
  does not touch the agent: it names the app, not the repo.

## Gates this trips

- `check_menubar.py`: rows that pin the menu's length or the line above Quit move by one. Expected.
- `check_seam.py`, if it enumerates the ports. Expected.
