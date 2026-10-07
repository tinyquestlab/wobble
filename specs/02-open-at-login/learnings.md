# Learnings — S02

## Learned

- **2026-10-07 — BTM's verdict on a LaunchAgent is readable without root, and it lags the file by
  ~2 s.** `SMAppService.statusForLegacyURL_` (pyobjc-framework-ServiceManagement 12.2.2, scratch
  venv) on `~/Library/LaunchAgents/local.wobble.login.plist`: `0 notRegistered` before the file,
  `3 notFound` right after writing it, `1 enabled` two seconds later. So `notFound` is "BTM has not
  seen it yet" as well as whatever else it means — a read straight after a write must not be
  reported as a refusal. Not loaded in `launchd` until the next login (`launchctl print` finds no
  service), as expected for `RunAtLoad` in a file written mid-session (task 01).
- **2026-10-07 — the agent started the app at a real login, with its grants.** Login at 10:20
  ("Reopen windows" unticked); `launchctl print gui/501/local.wobble.login`: `runs = 1`, `last
  exit code = 0`, `program = /usr/bin/open`. The launcher started 10:21:01 with PPID 1, its daemon
  under it; `var/app.out` at 10:21:02 says `accessibility granted` and the link scanning, with no
  prompt. Launch Services is the door, so the grants pinned to cdhash `52d9a5dd…` held (task 01).
  B brought the window forward, by hand. macOS showed "Background Items Added" right after the file
  was written, before the logout — so it arrives at the switch, not at the login.
- **2026-10-07 — switched off in Login Items, the file stays and BTM remembers it past a rewrite.**
  Off by hand in System Settings › General › Login Items & Extensions › App Background Activity:
  the plist untouched, `2 requiresApproval`, and `launchd` booted the service out (`launchctl
  print` finds none); the running app was left alone. Removing the file read `0 notRegistered`;
  writing the same bytes back read `2 requiresApproval` again, four reads over 8 s. So wobble cannot
  turn back on what the person turned off there — the menu has to say "off in Login Items" and send
  them to that pane, and "the file exists" alone would have been a menu claiming on (task 01).
  On macOS 26 the section is "App Background Activity" (not "Allow in the Background", as on
  15); wobble is listed by name with the app's own icon, as "Item from unidentified developer" —
  `AssociatedBundleIdentifiers` did its job, and ad hoc signing explains the rest.
- **2026-10-07 — switched back on in Login Items, it runs at once.** `1 enabled`, and `launchctl
  print` shows the service back with `runs = 1`, `last exit code = 0`: `RunAtLoad` fired on the
  switch, `open` found the app already running, and there was still one launcher (pid 70026). A
  second `open` of a running app is harmless, so no guard is needed against it (task 01).

- **2026-10-07 — a trailing comma in `daemon.py` staled a mutant in `check_daemon_edges.py`.**
  Adding `login=` after `on_silence=silencing.append)` turned its `)` into `,`, and the mutant that
  replaces that exact text reported itself stale — found only by the slow run, 12 min in. Before
  editing a line of `daemon.py`, grep `tests/tables/` for it: the mutants quote it whole.

## Concepts learned

- **LaunchAgent** — a `.plist` in `~/Library/LaunchAgents` that `launchd` runs for this user;
  `RunAtLoad` means once, at login.
- **BTM** — Background Task Management, the list behind System Settings › Login Items (macOS 13+).

## Promoted

- 2026-10-07 → `NOTES.md` History: the LaunchAgent road and why not SMAppService; no paid account
  needed (`docs/no-developer-account-2026-10-07.md`).
- 2026-10-07 → `NOTES.md` Learnings: BTM readable, its ~2 s lag; its "off" survives a rewrite;
  mutants quote daemon lines whole.
