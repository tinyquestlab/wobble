# S01 — MVP: the ball tells you

## What

Claude Code finishes, or gets stuck waiting on you. A Poké Ball Plus in your pocket lights up,
cries or wobbles. You press its button: it goes quiet, and the window of the session that was
waiting comes to the front. With no ball, the menu bar and the Mac's own sounds do the same, and a
right-click on the menu bar ball is the button.

## Why

Walking away from the desk means either watching a screen that is doing nothing, or coming back to
find the agent stuck for twenty minutes. The feedback has to reach the hand, because the hand is
what leaves the desk. The no-ball mode is not a courtesy: it is how wobble is developed, and how
anyone without the hardware meets it.

## Acceptance criteria

Each criterion is the behaviour as built. Where the desk changed it, the line under it says which
task did, and the full story is in that task's entry in `learnings.md` and in the archived text.

1. **A session finishes** → within ~2 s the ball lights and cries, and the menu bar counts one.
2. **A session asks for permission** → the ball wobbles (`199`) every 1.5 s, and the `needs` goes
   ahead of any `done` already waiting. *It beats as the prompt shows, not 6 s later (task 72).*
3. **Nothing is dismissed** → the signal keeps speaking until it is. A `done` is `9`, the held
   light, then its cry; the cry again at 30 s; the light held until someone comes. A `needs` beats
   until it is dealt with. Muted, a `done` is `9` alone and a `needs` is `4`. *The ladder that
   stopped on its own and the silent blink are gone (tasks 10, 16, 35).*
4. **Press B** → the ball goes quiet, the count drops, and that session's window comes to the
   front. *The very session, in any host and on any desktop (tasks 42, 43, 66, 69).*
5. **A prompt in a session** → resolves that session, and drops its own entry wherever it sits in
   the queue. A turn the agent wrote itself is not a person (`hooks.by_person`, which fails toward
   speaking). *An answer given where it was asked counts too (tasks 49, 65, 71); so does the end of
   the turn (task 73).*
6. **Press B, then nothing** → after 5 min the same signal comes back, at the back of the queue. A
   `needs` speaks over a held `done`; a held `needs` holds everything until it is answered. *Tasks
   52, 54, 55; a seen `done` comes back quiet (task 68).*
7. **Press B while attending** → skips to the next; the skipped one goes to the back of the queue.
   B never ends a signal: a prompt does. With nothing else waiting, a second press asks for the
   window again (task 46).
8. **No ball** → all of the above on the menu bar, with the Mac's sounds. The menu ball is hollow
   while a ball is looked for, faded while switched off, and the words are in its menu (task 63).
9. **The ball disconnects** → the menu ball goes hollow, which a connected one never is, and its
   menu says so in words. Silence never has to be interpreted.
10. **Accessibility refused** → focusing is skipped and wobble says so in words; the signal itself
    still works.

## Edge cases

- **B is an edge, not a level.** Byte 1 is a state: a press counts on 0→1, needs the release, and
  assumes one when packets stop. A hold of 2 s is a silence, so a tap fires on the release (task 68).
- **A write is lost.** Writes are without response; each retries up to three times and every retry
  is logged.
- **The link ages.** Retries grow more frequent past ~12 minutes on one link
  (`docs/PROTOCOL.md` §9). It has held day to day in use; retries over hours were never measured.
- **The ball holds a light only through `9`.** Every other light goes out by itself; `180` is the
  only way to turn `9`'s off (task 35).
- **Two sessions in one folder** are two entries, told apart by their process (tasks 40, 41).
- **The ball is asleep.** It advertises only after its top button is pressed, so the scan never
  gives up (task 32) and the menu ball stays hollow until it answers.
- **Several pending, then the ball connects.** The queue lives in the core, so a ball arriving late
  shows the current state rather than replaying history.

## Out of scope

Everything in `constitution.md`'s non-goals. Named because they tempted while building this one: no
creature, no gamification, no second agent, no Windows or Linux build.

## Outcome

All ten criteria are met. The desk proved each with the ball (`docs/DESK-CHECKS.md` Part C has the
verdicts); the suite of tasks 74–85 keeps the part that needs no radio proved on every push.

| # | At the desk | In the suite (`tests/tables/`) |
|---|---|---|
| 1 | Part B step 1; `check_criteria` | `ball_mirror`, `daemon_edges` |
| 2 | Part B steps 18, 29 | `queue`, `ladder` |
| 3 | Part B step 18; a camera at the ball | `ladder`, `ball_worker` |
| 4 | Part B steps 3, 5, 23, 26 | `attention`, `raise` |
| 5 | Part B steps 9, 22, 28 | `attention`, `hooks` |
| 6 | Part B steps 19, 25 | `attention`, `queue` |
| 7 | Part B step 19 | `attention` |
| 8 | Part B steps 10, 27; no ball, every day | `menubar`, `own_sounds` |
| 9 | Part B steps 6, 11 | `ball_mirror`, `menubar` |
| 10 | Part B step 8 | `focus` (macOS) |

Released as `v0.1.0-beta` on 2026-10-02.
