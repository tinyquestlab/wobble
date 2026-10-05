# S01 — Plan

The shape as built. Where the desk changed a decision, the task that did is named, and its entry in
`learnings.md` has how it was measured.

## Shape

```
Claude Code hooks ──► tools/hook_event.sh ──► var/events (append-only)
                                                  │
                                                  ▼
                                            ┌───────────┐   what is pending, whose turn,
                                            │   core    │   which voice, when it beats
                                            └─────┬─────┘
                                                  │  state, never rendering
                                   ┌──────────────┴──────────────┐
                                   ▼                             ▼
                             mirrors/ball.py              mirrors/menubar.py
                             (BLE: light, cry,            (the drawn ball, the count,
                              rumble, the button)          the menu, the Mac's sounds)
                                   │                             │
                                   └──────► platform_seam ◄──────┘
                          (Sound, Focus, Status, Frontmost, Process, Idle)
```

`src/daemon.py` is the one process that runs: it tails `var/events`, feeds the core, and hands each
mirror what the core decided. The core holds the queue and the attention state machine and knows
nothing about BLE, AppKit or osascript. A mirror renders and reports input. The seam is the only
place an OS is named; `null.py` is what runs with no Mac under it.

## Key decisions

**The signal vocabulary is a config file, not code.** `config/signals.json` holds every effect id,
colour, interval, mood pool and Mac sound, each with where it came from. The ids are chosen at the
desk and change as more of the ball's bank is identified; that must not be a code edit.

| signal | voiced | muted |
|---|---|---|
| `done` | `9`, the held light, then a cry (`129`, or the mood's own); the cry again at 30 s | `9` on both beats |
| `needs` | `199` every 1.5 s | `4` every 1.5 s |
| caught / broke out | `201` green / `206` red | `193` / `191` |
| silenced | `179` blue and `2`, a weak tick | the same |
| nothing pending | `180`, which turns `9`'s light off | the same |

**wobble lives in the stroll slots** (`04 3c 00` for the cry, `01 fc 01` for the colour), uploaded
on connect and never on an event: the transfer takes ~1.66 s and a signal cannot wait for it.
`213` and the catch slots are left free for catching (task 35).

**`needs` always goes first.** Someone is stopped. `done`s are ordered by age.

**Attention is a state, not a pop.** B marks a session attending and holds the queue quiet. Its
prompt, or an answer where it asked, resolves it; otherwise a 5 min snooze brings the signal back,
to the back of the queue (task 54). Dismissing is a promise, and a hold nobody releases is a lost
signal whose only symptom is silence. B never ends a signal (criteria 5–7).

**One entry per session.** Sessions are known by their process, through Claude Code's own
registry, so two in one folder are two entries and a closed one is noticed (tasks 40, 41).

**B is an edge, not a level.** Byte 1 is a bitmask: `0x01` is B, `0x02` the stick click, measured
with both watched (task 07 had them the other way). A tap fires on the release; a 2 s hold
silences (task 68).

**The core runs with no mirror attached.** That is the development mode and the no-ball mode, and
it is the same code path. It is also what lets the suite (tasks 74–85) run on Linux.

## What came from the earlier project

Read, judged, and rewritten where it did not fit: the GATT uuids and the scan, the
`<opcode:u8><len:u16 LE><payload>` framing and the opening sequence, the `0x08` chunked transfer,
the 17-byte input decode, and the seam's Protocol shapes. Not carried over: its daemon, panel, pet
and event fan-out. Its protocol research is `docs/PROTOCOL.md`, cited by section wherever a fact
came from it.

## Open questions, answered at the desk

1. **Which index turns the LED off?** None: every light is a transient and goes out by itself
   (task 04). Only `9` holds one, and `180` turns it off (task 35).
2. **Does an LED index alone light the ball?** No; it needs an effect played after it (task 04).
3. **Are the capture waves felt through a pocket?** Yes, and better than `241`, which rumbles
   nearly twice as hard on the desk (task 05).
4. **Are `198`, `199` and `200` the same?** `199` and `200` are; `198` is a much weaker beat, heard
   and almost never felt through cloth (task 05).
5. **Does the link hold for hours?** It has held day to day in use (2026-09-30); retries over hours
   were never measured.
