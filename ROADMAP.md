# Roadmap — wobble

One phase at a time. A phase gets a `specs/NN-<slug>/` folder when it actually starts, never
before — a roadmap pointing at a half-written spec is a roadmap nobody trusts.

## 01 — MVP *(current — `specs/01-mvp/`)*

Leave Claude Code working, walk away with the ball, be told when it finishes or when it needs you.
Two mirrors: the ball (sound, LED, rumble) and a menu bar dot. Dismiss with the ball's B button —
or by clicking the menu bar item when there is no ball, in which case the Mac makes the sound.
One attention at a time, `needs` always on top of the queue. macOS only, behind the platform seam.

## 02 — The test suite

Everything that is not the radio, tested automatically: the queue, the attention state machine,
the repeat ladder, the signal config, the input edge detection. Written after the MVP's shape has
stopped moving, which is why it is not phase 01 (constitution principle 3). The desk checks stay —
they are the only thing that can verify the ball.

## 03 — Windows

`bleak` already speaks WinRT, so the BLE layer ports for free. What this phase writes is one seam
file: `SetForegroundWindow` for focus, `Shell_NotifyIcon` for the tray, `winsound` for the sound.
No core change is allowed; if one is needed, the seam was drawn wrong.

## 04 — Linux

Same shape, one file: `wmctrl`/`xdotool` for focus on X11, `paplay`/`aplay` for sound. Two things
to be honest about up front — Wayland cannot raise another app's window at all, and a Linux
desktop may have no tray. Both are walls, not gaps; the phase ships the degraded behaviour and
says so in words.

## 05 — More voices

The ball holds one uploaded stroll cry at a time (effect `129` plays whatever was uploaded last,
`docs/PROTOCOL.md` §7.2). Pikachu first, then Eevee, then whatever else. On the new ball both
partners already have built-in sounds (§6.5); the old one needs the upload.

## 06 — Buddy

The creature on screen, as a **mirror plus a game**: it shows exactly what the core says, and the
game sits on top of that without changing it. It is the most tempting idea here and the one most
likely to sink the rest — it arrives only once the MVP is boring.

## 07 — Gamification

Levels, affection, quests. On top of Buddy, never instead of it.

## 08 — Other agents

Gemini, Grok, Codex, whatever comes next. The core already speaks in signals rather than in Claude
Code's vocabulary; this phase writes an adapter per agent and changes nothing else.

## Not placed yet — how much is left

Claude's plan usage (the 5-hour and 7-day windows), parked 2026-09-28 until after the MVP. It is
not "finished or needs you", so it needs an amendment to `constitution.md` before it becomes a
phase, and principle 2 needs an answer for the ball first: the menu bar may not show usage the ball
cannot say. Wanted in the menu and on the settings screen below (2026-09-30).

## Not placed yet — a settings screen

Asked for 2026-09-30, after the permission warning was left out of the menu: a screen for that
and more in the future. One window for what today lives in flags and in
`config/signals.json`:

- the permissions, and which one is missing — the last item of "wobble as an app" below;
- the colours and sounds of each signal;
- which ball it is: the new ball plays Pikachu from its own ids, the old one needs the uploaded cry
  on `129` (task 57). When a new ball connects, a short wizard asks, and "it did not play" switches
  to the fallback;
- Claude usage, above.

"No window" is a non-goal of the MVP, so this needs an amendment to `constitution.md` first.

## Not placed yet — a floating ball

Asked for 2026-09-30: wobble could have a floating ball on screen that does what the menu bar ball does (task 58). It is for people who do not have the ball yet, so
they can see what having one is like. It is a window, and it moves, so it needs the same amendment
as the settings screen.

## Half placed — wobble as an app

Built in spec 01 as task 50, after the constitution's amendment of 2026-09-29 (a locally built
`.app` is not a release) and task 48's measurement. `tools/build_app.py` builds
`/Applications/wobble.app` from the repo: a small launcher of its own, so macOS files Bluetooth and
Accessibility under wobble, and a start script in the repo, so a `git pull` or a new Python keeps
the grant. It asks for Accessibility once, on first launch, through the system's own prompt: task
48 measured that the front window's title cannot be read without it. What is left:

- starting at login through `SMAppService`, which macOS refuses outside `/Applications` (the app
  now lives there). A LaunchAgent pointing at the bundle is the other road;
- raising windows through Launch Services (`NSWorkspace.openApplication`), which needs no
  permission, so Accessibility might not be needed at all;
- saying a missing permission somewhere a person looks: with no terminal, the daemon's words reach
  only `var/app.out` and the day's log.

## Built — silencing a session

Built in spec 01 as task 68: B held on the ball, or ⌥ on a menu row. Raised 2026-09-29 and first
parked; the ask as it stood then: Some sessions have to
stay open but do not matter right now, and when something urgent needs focus their signals get in
the way. The ask: silence one of them without closing it. It would reuse the quiet state task 47
built for entries restored after a restart. A quiet entry is listed but not counted or signalled,
B reaches it last, and its next event makes it live again. So the new part is only how a person
sets it, and when it wakes up again.

A long-press on the ball's button was the first thought, and the one built. Principle 2 applies:
the menu bar offers no silence the ball cannot give.
