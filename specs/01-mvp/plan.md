# S01 — Plan

## Shape

```
Claude Code hooks ──► var/events (append-only)
                          │
                          ▼
                    ┌───────────┐      what is pending, whose turn it is,
                    │   core    │      which signal, when it repeats
                    └─────┬─────┘
                          │  state, never rendering
              ┌───────────┴───────────┐
              ▼                       ▼
        mirrors/ball.py        mirrors/menubar.py
        (BLE: sound, LED,      (dot + count + the Mac's own sound)
         rumble, B button)     (click = B)
              │                       │
              └───────► platform_seam (Sound, Focus, Status, Frontmost)
```

The core holds the queue and the attention state machine and knows nothing about BLE, AppKit or
osascript. A mirror renders and reports input. The seam is the only place an OS is named.

## Key decisions

**The signal vocabulary is a config file, not code.** `config/signals.json`: per event kind, which
effect id, how many beats, which LED palette index, which ladder. Learned the hard way — the ids
are chosen by ear at the desk and change as more of the ball's sound bank gets identified, and that
must not be a code edit.

| kind | sound | repeat ladder | LED |
|---|---|---|---|
| `done` | Pikachu's cry — effect `213`, the uploaded slot | now, +2 min, +5 min, stop | on, stays |
| `needs` | capture waves — `198`→`199`→`200` | now, +2 min, +5 min, stop | on, stays |

`213` plays whatever was last uploaded, so the cry is uploaded on connect and on voice change,
never on an event — the transfer takes ~1.66 s and a notification cannot wait for it.

*Superseded by tasks 10 and 35 — the live map is `config/signals.json`: `done` is `9` + `129` from
the stroll slots, `needs` is `199`, and `213` is no longer played. The rule above still holds, for
`129`'s slot.*

**`needs` always goes to the top.** Someone is stopped. `done` is ordered by age within its kind.

**Attention is a state, not a pop.** Dismissing marks that session *attending* and freezes the
queue silently. What resolves it is that session's next `UserPromptSubmit` hook — a signal that
already exists, so no timer is guessing at "are they done with it yet". **A ~5 min snooze brings
the dismissed signal back** if that prompt never arrives, into the place it had: dismissing is a
promise, and a frozen queue nobody releases is a lost notification with silence as its only
symptom. Settled 2026-09-22; this said a ~10 min net that unfroze and moved on, which loses the
one you dismissed.

**A prompt in any session drops that session's own pending entry.** You were there; the
notification is answered. It only *releases the hold* when it is the held session.

**B is an edge, not a level.** Input byte 1 is a bitmask (`0x01` top button, `0x02` stick click).
Press counts on 0→1, requires the release before the next, and assumes release when packets stop.
**B is `0x01`** — measured 2026-09-22 with both bits watched and only B pressed; task 07 had it
written down as `0x02` and that was wrong.

**The core runs with no mirror attached.** That is the development mode and the no-ball mode, and
it is the same code path.

## What the protocol layer carries over, and what is new

Carried over — read, judged, and rewritten where it does not fit:

- the GATT uuids and `find_ball` scan
- the `<opcode:u8><len:u16 LE><payload>` framing and the opening sequence
- the `0x08` chunked resource transfer
- the input decode (17-byte packet: counter, buttons, stick, accel/gyro)
- `src/platform_seam/ports.py` — the Protocol shapes, trimmed to what the MVP uses

Not carried over: the daemon, the websocket panel, the pet, the affection ledger, the menu bar, the
event fan-out — grown past their own good decisions elsewhere, and this spec rebuilds only the
parts it needs.

Not duplicated: the protocol research, now in `docs/PROTOCOL.md` and cited by section number
wherever a fact came from it.

## Open questions this spec must answer at the desk

1. Which palette index turns the LED off — id 0 does not (`docs/PROTOCOL.md` §6.3).
2. Whether an LED index alone lights the ball, or needs an effect played after it (never run).
3. Whether the capture waves (~6× the rumble floor) can be felt through a pocket, given `241`
   reaches ~27×.
4. Whether the by-ear catalogue or the accelerometer is right about 198/199/200 being the same.
5. Whether the ball stays usable connected for hours.

Each is a task below, and each answer goes in `learnings.md` with how it was measured.
