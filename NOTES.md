# NOTES

Decisions and gotchas worth keeping past the spec that found them. The full account of each is in
that spec's `learnings.md`; this is the short, still-true version. Sorted from spec 01 at its close,
2026-10-01.

## History

- 2026-09-22 (spec 01, criterion 3): `needs` is effect `199` every 1.5 s until dismissed — one beat,
  one interval, nothing that grows. A signal that stops on its own is a notification lost on
  purpose (principle 7).
- 2026-09-25 (spec 01, task 35): a `done` is `9` (the held light) then its cry from the stroll slot,
  the cry once more at 30 s, and the light held until somebody comes. The silent pulse of tasks
  16/26/34 was removed, not improved, once the second resource set and `9`'s self-holding light
  were known. Muted: a `done` is `9` alone, a `needs` is `4`.
- 2026-09-22 (spec 01, criterion 5): a prompt in any session drops that session's own pending
  entry; an agent-injected turn is not a person (`hooks.by_person`, which fails towards keeping
  the signal).
- 2026-09-29 (spec 01, task 54): B never ends a signal. A dismissed one comes back after its snooze
  (`config/signals.json`, 5 min), and one skipped with B goes to the back of the queue; a `needs`
  stays ahead of every `done`.
- 2026-09-28 (spec 01, task 50): one daemon per events file, held by an `flock` beside it, so a
  crash never leaves a lock behind and a desk check's sandbox never collides with the real one.
- 2026-09-25 (spec 01, task 35): `213` is reserved for the catch; wobble does not use `213` or its `3e`/`fd` slots.

## Learnings

- 2026-09-22 (spec 01, task 03): an effect's ack carries no id of what played — each opcode has its
  own ack opcode (`protocol.ACK_OF`), and that is all. Only the ball itself proves what played.
- 2026-09-22 (spec 01, task 04): an LED resource alone does nothing; resource then effect lights
  the ball. Treat the two as one step.
- 2026-09-22 (spec 01, task 04): the ball has a soft amber breathing glow of its own, ball-local.
  Do not read it as one of our effects at a desk check.
- 2026-09-22 (spec 01, task 05): the input counter steps by 6 on this ball, not the 3 earlier
  notes said. Read the step from a live capture, not from inherited docs.
- 2026-09-22 (spec 01, task 05): a ranking of `198`/`199`/`200` from a run that plays them back to
  back measures their position, not their strength — played alone, the felt order reversed. The
  IMU is not a proxy for what a pocket feels; a person is.
- 2026-09-22 (spec 01, episode shape): a real catch is three single beats about 1.2 s apart, and
  the rumble has a floor of ~0.6 s between beats set by the motor, not the radio.
- 2026-09-22 (spec 01, task 06): `Link.hold()` holds the wire for all eight frames of an upload; a
  send during an upload waits for the whole of it.
- 2026-09-22 (spec 01, task 07): B is `0x01`, not `0x02`, and a press can be swallowed by the link.
  B is a 0→1 edge with an assumed release.
- 2026-09-22 (spec 01, task 11): hooks are `/bin/sh`, never Python — LaunchServices bounces a Dock
  icon for any invocation of the framework Python binary.
- 2026-09-22 (spec 01, task 11): the installer merges into `~/.claude/settings.json`, the person's
  own file, and never overwrites it.
- 2026-10-02: the Pikachu cry is fetched from PokeAPI at install (`tools/fetch_cry.py`) and
  converted to the ball's format; no cry is ever committed.
- 2026-09-22 (spec 01, task 15): a locked screen is the ordinary case for a notifier, not an edge.
  Window titles are unreadable while locked, so the seam reads the lock first and says so.
- 2026-09-22 (spec 01, task 16): quiet while you watch does not resolve a signal; it stays pending
  and quiet, and looking away lets it speak at once.
- 2026-09-25 (spec 01, task 35): the stroll ids — `9`/`10` buzz once at the start of a send, `10`
  stronger; `213` is the LED plus the captured Pokémon's cry, `129` the stroll one's; `198`–`200`
  are fixed catch UI; `9`'s light has never been seen to stop without `180`.
- 2026-09-28 (spec 01): a Claude desktop session that leaves no event ran outside this Mac's
  Claude Code; only the Code tab run Local loads the hooks. And the registry outlives a killed
  claude — a `~/.claude/sessions/<pid>.json` is not evidence the session runs (task 40).
- 2026-09-29 (spec 01, task 45): closing a Warp tab does not end its shell; Warp keeps both alive
  for its undo-close grace period, then ends them together.
- 2026-09-30 (spec 01, task 62): macOS 26 plates an app icon that leaves any pixel clear inside the
  squircle, whatever its outline.
- 2026-10-01 (spec 01, task 69): `open -b <bundle> <folder>` switches to the desktop that holds that
  folder's VS Code window; Accessibility only lists the current desktop's windows.
- 2026-10-01 (spec 01, task 63): on macOS 26 the menu bar follows the wallpaper, not the
  Light/Dark setting. A light-bar desk check needs a light wallpaper.
