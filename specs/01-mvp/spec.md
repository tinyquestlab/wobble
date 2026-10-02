# S01 — MVP: the ball tells you

## What

Claude Code finishes, or gets blocked waiting on you. A Poké Ball Plus in your pocket plays a
sound, lights its LED and rumbles. You press the ball's B button: it goes quiet, the LED goes out,
and the window of the session that was waiting comes to the front.

With no ball connected, the same thing happens on the Mac: the menu bar item carries the state and
the Mac plays the sound. Clicking that item is the B button.

## Why

Walking away from the desk currently means either staying to watch a screen that is doing nothing,
or coming back to find out that the agent has been blocked for twenty minutes. The feedback has to
reach the hand, because the hand is what leaves the desk.

The no-ball mode is not a courtesy: it is how the thing gets developed, and it is how anyone
without the hardware meets it.

## Acceptance criteria

1. A Claude Code session finishes → within ~2 s the ball plays Pikachu's cry once, its LED comes
   on, and the menu bar shows one pending.
2. A Claude Code session blocks on a permission prompt → the ball plays the capture-wave effect,
   repeating on a steady interval (see 3 — "a growing gap" was the guess this replaced), and its
   LED comes on. `needs` goes to the top of the queue even
   if a `done` was already waiting.
3. Nothing is dismissed → the signal keeps speaking until it is. **The LED keeps pulsing while it
   is pending**, silently. The menu bar still shows it pending.

   Changed 2026-09-22, at the desk: this said "repeats at ~2 min and ~5 min, then stops", and that
   was a guess written before anything had been felt through a pocket. What the desk settled is
   `needs` = effect `199` **every 1.5 s until dismissed** — one beat, one interval, nothing that
   grows or accelerates; two richer shapes were built and set aside (`learnings.md`). A signal that
   stops on its own is a notification lost on purpose, which principle 7 forbids; what ends it is a
   dismissal. `done` plays its cry **once** and then leans on the silent pulse — a choice, not a
   measurement, and labelled as one in `config/signals.json`. The 1.5 s and the ids live in that
   file so the numbers change without a code edit (plan.md).

   Changed 2026-09-22, at the desk: this said "the LED stays on", and the ball cannot do that —
   an LED is a transient animation with no state to hold. What it can do is flash on demand, and
   with a silent resource in the slot it does so with no sound, so the pulse is what carries
   "pending".

   Changed 2026-09-22, from a film of the ball: "`done` plays its cry **once** and then leans on
   the silent pulse" was true and still left the ball dark. The pulse was written as what starts
   once the beats are used up, so the first blink fell 30 s behind the cry — and the camera
   measures 60.1 s, because the pulse due at 30 s was spent uploading the mute and dropped. A
   `done` is now: the cry, a blink every 3 s from that moment, the cry once more at 30 s, and
   blinking from then until somebody comes. **Beats and the pulse run together**; the beats stop
   after two and the blinking does not stop at all. The blink itself measures 1.47–1.50 s and is
   the same length whichever resource is in the slot, so at 3 s the ball is lit about half the
   time. All of it lives in `config/signals.json` (`every_s`, the new `times`, `pulse.every_s`).

   Changed 2026-09-25 (task 35), and it puts back the words of the first draft: **the LED stays
   on.** The ball can hold a light after all — effect `9` shows the colour in the stroll LED slot
   and stays on by itself until `180`. So a `done` is `9` then its cry (`129`, from the stroll cry
   slot), the cry once more at 30 s, and the held light from then until somebody comes; nothing is
   sent between beats, and the silent pulse, `pulse.every_s` and `after_beat_s` are gone. A `needs`
   is unchanged at `199` every 1.5 s. Muted, a `done` is `9` alone and a `needs` is `4`.
4. Press B → the ball goes silent, the LED goes out, the menu bar drops to the remaining count,
   and that session's window comes to the front.
5. That session is given a new prompt → the next pending signal surfaces with its full signal.
   **And a prompt in ANY session drops that session's own pending entry**: if you typed in it, you
   were there, and a notification you have already answered is not worth showing.

   Added 2026-09-22: the second sentence is new. The only signal the MVP has for "you went to it"
   is a prompt — merely looking at the window is not visible from the core.

   Narrowed 2026-09-22: **a prompt the agent wrote to itself is not a person arriving.**
   `UserPromptSubmit` also fires when a background task hands its result back and the session
   starts a turn on its own, and that was silently resolving signals nobody had seen. Real
   payloads were compared rather than reasoned about: an injected turn and a typed one carry
   exactly the same keys, so there is no flag to read and the text is all there is — an injected
   turn opens with a lone wrapper tag on its own line. `hooks.by_person` is the heuristic, it is
   fallible, and it fails towards leaving the signal pending and still speaking, which is the loud
   half of principle 7. The daemon counts and names every turn it refuses on these grounds, so a
   signal that will not go away has a line explaining why.
6. Press B and then do nothing → after ~5 min **that same signal comes back**, into the place it
   had in the queue. Nothing is ever lost silently.

   Changed 2026-09-22: this said "after ~10 min the queue unfreezes on its own and the next signal
   surfaces", and moving on is exactly how the dismissed one gets lost. Dismissing is a promise —
   you said you would look — so a promise not kept returns the signal rather than replacing it.
   The 5 min is a judgement and lives in `config/signals.json`; the time-to-press, still unmeasured,
   is what it should come from. It does not come back if that session signalled again meanwhile:
   the newer entry is already in the queue and wins.

   Changed 2026-09-29 (task 52): **a `needs` speaks over the promise; nothing else ends it
   early.** The one B took keeps its snooze wherever you go. B means "seen, leave it with me",
   not "chase me if I leave". The `done`s behind it stay quiet. A `needs` in the queue speaks
   over a held `done` at once. Over a held `needs`, it speaks once you have been out of that
   window for the look-away grace (`look_away.wait_s`, 3 s), so an answer in progress is not
   interrupted. In the desktop app the app itself in front counts as being in that window,
   because its window never carries the folder's name. Seen at the desk at 15:20: a `done` held
   in the Claude app kept project-b's `needs` quiet for two minutes. Task 51 put the held one back in
   the queue once its window was left for 3 s. It passed at the desk the same afternoon, and
   was rejected at the desk: the signal already seen cried again and held its dismisser to it.

   Changed 2026-09-29 (task 54): **out of the held window, the hold holds nothing back, and what
   comes back goes to the back of the queue.** Once you have been out of the held one's window for
   the look-away grace, any signal speaks, a `done` too. At the window, a `done` still waits, and a
   `needs` still speaks over a held `done`. The held one keeps its snooze either way. When the
   snooze fires it rejoins the queue behind what waited meanwhile, not in the place it had; a
   `needs` is still ahead of every `done`. Seen at the desk from 16:47:53: project-a's `done`, held
   while a background run went on with nothing to do in it, kept project-b's `done` quiet while
   the person at the desk was elsewhere.

   Changed 2026-09-29 (task 54 narrowed by task 55): **a held `needs` holds everything, wherever
   you are,** until it is answered or prompted, skipped with B, or its snooze fires. Leaving its
   window frees nothing; only a held `done` lets the queue speak once you are away. Seen at the
   desk at 18:09:13: B on project-b's `needs`, and project-c's `needs` spoke over it 3 s later.
   Said at the desk: "the only thing a needs waits for is another needs".
7. Press B while already attending one → skips to the next pending, and **the one you were on
   goes back into the queue**, into the place it had, exactly as 6 returns a dismissed signal.

   Added 2026-09-22, after the desk pass: this said only "skips to the next pending", and what
   happened to the one skipped was left unsaid — so it was dropped, by nothing more deliberate
   than being overwritten, and nothing anywhere mentioned it. Settled: **finishing something is
   closing its session.** No press of B ever ends a signal; B chooses what you are dealing with,
   and a prompt (criterion 5) is what says you dealt with it. So a second press on a lone signal
   hands it straight back rather than making it go away — the honest answer, not an accident.
   It does not go back if that session signalled again meanwhile, for 6's reason.

   Changed 2026-09-29 (task 46): with nothing else pending there is no next to skip to, so a
   second press on a lone signal keeps it and asks for its window again. Handing it straight back
   made it cry at once, so a B pressed because the window did not come cost a beat every time.
   The snooze still counts from the first press.

   Changed 2026-09-29 (task 54): the one you were on goes to the back of the queue, as 6 now
   returns a dismissed one, rather than into the place it had.
8. No ball connected → every one of the above happens on the menu bar, with the Mac playing the
   sound, and the menu bar shows there is no ball: a hollow ball while one is looked for, a faded
   one while the link is switched off, and the words in its menu.
9. The ball disconnects mid-session → the menu bar's ball goes hollow, which a connected one never
   is, and its menu says so in words. Silence never has to be interpreted.

   Changed 2026-09-30 (task 63): 8 and 9 asked for the words in the title. The drawing carries
   them now, as principle 7 was amended to allow, with the words one click away in the menu, and
   back in the title whenever the ball cannot be drawn.
10. Accessibility permission is refused → focusing is skipped and the app says so, in words. The
    notification itself still works.

## Edge cases

- **B reads as stuck.** Input byte 1 is a *state*, not an event. B must be a 0→1 edge with the
  release required before the next press counts, plus an assumed release when no packet arrives
  for a short window. A bug with this shape was seen before: the stick axis had the same failure once.
- **A write is lost.** The ball's output characteristic is write-without-response, so a lost frame
  raises no error anywhere. Every write retries up to three times and logs each retry.
- **The link ages.** Retries got roughly four times more frequent past ~12 minutes on one link
  (`docs/PROTOCOL.md` §9). Whether the ball survives hours in a pocket is unmeasured, and
  is a desk check in this spec.
- **There is no LED state at all, so there is nothing to turn off.** Measured 2026-09-22: an LED
  resource alone does nothing, the same resource followed by an effect lights the ball, and the
  light goes out on its own. Hunting a palette index that "reads as dark" was hunting something
  that cannot exist. The LED is driven by repetition, not by being set.
- **Two sessions in the same project folder.** Window matching is by title; two windows with the
  same project name are indistinguishable. Focus the first match and do not pretend otherwise.
- **The ball is asleep.** It sleeps quickly when not handled and must be woken with the top button
  before it advertises. The menu bar must show "no ball" rather than look connected: a hollow ball, and
  the words in its menu (task 63).
- **Several pending, ball then connects.** The queue lives in the core, not in a mirror, so a ball
  arriving late picks up the current state rather than replaying history.

## Out of scope

Everything in `constitution.md`'s non-goals. Named here because they will be tempting while
building this one: no creature, no gamification, no second agent, no Windows/Linux implementation,
no automated test suite.
