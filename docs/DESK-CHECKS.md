# Desk checks — S01 MVP

How this project is verified, in two halves (constitution principle 3). Part A is what a command
can answer: the tables that need no radio are the suite, under `tests/tables/`, run by pytest here
and on every push; the few that touch this desk's world stay in `var/desk/`. Part B is what only a
hand and a ball can answer.

Each table prints its own verdict on the last line, and the suite also counts its rows, so a table
that stops asking something fails rather than passing shorter. Nothing here reports a pass it did
not see. What a desk run measured is written down here and in `specs/01-mvp/learnings.md`.

---

## Part A — what a command can answer

```bash
venv/bin/python3 -m pytest                  # every table below, one process each
venv/bin/python3 -m pytest -m "not slow"    # all but ball_worker, raise and daemon_edges
venv/bin/python3 -m pytest -k ladder        # one table by name
```

A table can also be run on its own, as it was at the desk, and prints the same rows:

```bash
venv/bin/python3 tests/tables/check_queue.py        # the order signals come in, one entry per project
venv/bin/python3 tests/tables/check_attention.py    # dismissal, the freeze, the snooze, the fall-back, the close
venv/bin/python3 tests/tables/check_ladder.py       # the cadence, from config/signals.json
venv/bin/python3 tests/tables/check_ladder_refusals.py # the broken signals.json it refuses, and how
venv/bin/python3 tests/tables/check_cries.py        # which cry a done says, by mood
venv/bin/python3 tests/tables/check_mute.py         # mute mode: what the core takes out, and what it leaves in
venv/bin/python3 tests/tables/check_hooks.py        # which turns count as a person arriving
venv/bin/python3 tests/tables/check_hooks_edges.py  # hooks.py's refusals: unreadable, malformed, gone
venv/bin/python3 tests/tables/check_install_hooks.py # the hook entries it writes, merges and refuses
venv/bin/python3 tests/tables/check_protocol.py     # frames, acks and resource cuts, byte for byte, no radio
venv/bin/python3 tests/tables/check_link_log.py     # what link.py says reaches the day's file
venv/bin/python3 tests/tables/check_needs_rhythm.py # a beat's retries fit its gap; a dropped beat is said
venv/bin/python3 tests/tables/check_ball_mirror.py  # slot policy, colour, the link switch, the battery
venv/bin/python3 tests/tables/check_ball_worker.py  # 3 min: the ball mirror's worker loop, bleak never imported
venv/bin/python3 tests/tables/check_menubar.py      # what the mirror renders and asks for
venv/bin/python3 tests/tables/check_own_sounds.py   # your own Mac sounds, and what the ball keeps
venv/bin/python3 tests/tables/check_seam.py         # the null seam and the ports it must satisfy
venv/bin/python3 tests/tables/check_raise.py        # which way B takes to a session, and every refusal
venv/bin/python3 tests/tables/check_log.py          # the daily log: the name, midnight, the sweep
venv/bin/python3 tests/tables/check_daemon_edges.py # 20 min alone (the suite runs it in slices): the real daemon in a scripted world
```

On a Mac the suite adds the `mac` tier, which drives the real seam with its framework stubbed:

```bash
venv/bin/python3 tests/tables/check_focus.py        # raising a window, and every refusal
venv/bin/python3 tests/tables/check_macos_edges.py  # the macOS seam's failure sentences, osascript stubbed
venv/bin/python3 tests/tables/check_menu_light.py   # the menu ball's light, layer by layer
venv/bin/python3 tests/tables/check_watching.py --scripted # quiet while you look at it, back when you don't
```

These stay at the desk. They touch the screen, a grant, `/Applications` or a real session, so
they are run by hand before a release and never on CI:

```bash
venv/bin/python3 tests/tables/check_watching.py     # 20s: all of it, the live legs against your screen
venv/bin/python3 var/desk/check_macos_seam.py   # the seam read back out of AppKit itself
venv/bin/python3 var/desk/check_daemon.py       # one whole episode, every seam at once
venv/bin/python3 var/desk/check_criteria.py     # the criteria one episode cannot reach
venv/bin/python3 var/desk/check_rhythm.py       # 40s: the shape of a done, in real time
venv/bin/python3 var/desk/check_app.py          # wobble.app: the build, the launcher, the lock
venv/bin/python3 var/desk/check_build_app.py    # build_app.py's refusals and its three grant sentences
venv/bin/python3 var/desk/check_sessions.py     # each session's claude in the registry, and whether it runs
```

`var/desk/` is gitignored on purpose: its scripts are instruments for this desk. The suite's
helpers, `sandbox.py` and `edge_harness.py`, live in `tests/tables/`; the desk scripts that need
`sandbox.py` import it from there, so there is one copy of it.

- **`check_daemon_edges.py`** runs the real daemon through `edge_harness.py`: the null seam, with
  the registry, the processes, the window in front, the terminal's tab and the hook wiring each
  read from a file the check rewrites while the daemon runs. It reaches the restore, the stale
  aim, the lock refusals, a seam that raises, and a ball that will not let go — every one a
  branch no real session can be steered into on cue.
- **`check_build_app.py`** runs real `clang` and `codesign` into a temp dir under `var/`, stubs
  `pgrep` and `tccutil` (a real reset clears a real grant), fails on any other command, and
  stats the real `/Applications/wobble.app` before and after.

Four of them touch the world rather than a fake:

- **`check_macos_seam.py`** puts a real item in the menu bar, really plays a sound, and builds the
  real menu — then asks AppKit, not itself, whether the separator is a separator and
  whether choosing *Quit wobble* reaches the quit handler rather than the line above it.
- **`check_daemon.py`** presses B on a signal whose project is `wobble`, and the real seam then
  goes looking for a real window with that in its title. **It will move a window on your screen**
  if one is open. That is criterion 4 happening rather than being simulated — and having moved it,
  it refuses to run again until you click away, because the window it just brought forward is the
  one whose signals now stay quiet. It says which window and why rather than reporting a defect
  that is the daemon behaving correctly.
- **`check_watching.py`** reads the title of whatever window is in front of you *right now* and
  runs the real daemon against it. It moves nothing and needs no ball, but it needs the screen
  **unlocked with a titled window in front**, and it will say so rather than passing quietly if it
  is not — see the note below.
- **`check_app.py`** builds throwaway bundles under `local.wobble.check` and has the Finder open
  one (`open`), because who macOS holds responsible only exists for a launch it did. The bundle has
  no Dock icon and shows nothing. It never asks for a permission: it runs the same launcher from
  this terminal first, and runs the real daemon through one only if that is trusted, since the
  daemon's `--ask-access` would otherwise put up macOS's dialog for the check's identifier. It
  installs nothing and never touches `local.wobble`.

**`check_watching.py`'s last part cannot be faked, and it refuses to pretend.** The feature it
proves — a signal stays quiet while you are looking at the session that raised it — fails in a way
that looks exactly like being switched off: a terminal that does not put the folder name in its
window title matches nothing, and the only symptom is notifications that keep arriving. So the last
part takes the title of the window actually in front, fires one signal that matches it and one that
cannot, and demands that the second makes a noise. **Both quiet means the check learnt about
itself.** With the screen locked there is no window in front at all, so those legs do not run and
the script says which window to click and stops short of a verdict.

**`check_log.py` is the one that reaches midnight without waiting for it.** The daily log picks its
file from the clock as each line is written, so the rule that matters — a daemon left running
overnight starts a new file rather than filling yesterday's — only exists at a moment no check can
schedule. `log.Daily` therefore takes its clock as an argument, and the check moves it. The
alternative was to read the code and agree with it.

Its sweep rows are asked in both directions on purpose. Deleting by the file's **mtime** needs no
parsing and reads perfectly well, and it empties the whole directory the first time it is restored
from a backup, because every mtime is then the restore's. Deleting by everything in the directory
is the other one, and its blast radius is whatever else anybody put next to the logs. So the check
plants four files — an old name with a fresh mtime, a fresh name with a 400-day-old mtime, and two
that are not ours at all — and says which of them survives.

And one of them spends real time, because what it is checking only exists in time:

- **`check_rhythm.py`** runs for **70 seconds** and does nothing for most of them. A `done` is a
  cry, five seconds of quiet, a blink every 3 s, the cry once more at 30 s, and blinking from then
  on — a shape no known-answer table can hold, because every table finishes in a millisecond and
  every defect it found was a gap between two events. It fires one `done` into its own temporary
  events file and times what comes out of a real daemon's transcript. It is the only script here
  that would have caught any of the three timing defects in Part D.

**None of them scans for a ball.** Every script that starts a daemon passes `--no-ball`, because a
second CoreBluetooth scan next to a daemon that is holding the link is a hazard to somebody's
measurement — and everything here proves the core and the seams, which need no radio. The ball's
own half is Part B.

One trap worth knowing before you read a failure: **the menu bar item a desk-check daemon puts up
is a real item in the real menu bar, and clicking it is a real B press.** That happened twice on
2026-09-22 — once as a single stray press, and once as six of them inside five seconds — and both
times nine rows reported a schedule that had in fact been ended by a click. Two things were done
about it, and only the second one is a fix:

- Rows count focus verdicts against presses, so a stray click changes both.
- `check_rhythm.py` now passes **`--no-menubar`** and puts no item up at all. Its first row asks
  whether anything pressed B during the run, so the check accuses the interference by name instead
  of letting the rows below it accuse the code.

### Every script is checked against its own removal

A table of known answers proves nothing if the table is also the implementation's opinion. So each
script ends by running the same table against deliberately broken versions of the code — the LED
never uploaded, the snooze that never fires, the refusal with no sentence, the silent pulse that
beeps. Each one **must** break the table. A mutant that survives is a row that was never testing
anything, and is reported as loudly as a failure.

**Four of them are strategies that were genuinely on the table**, not typos, and they are the whole
proof of task 20 — the queue holding one entry per project instead of one per session. Counting
sessions instead of projects is the bug that started it: the bar read `● 2` with one terminal open.
Collapsing a project to its newest event is the version that reads as obviously right and loses the
`done` sitting behind a `needs` in the same folder. Ordering inside a project by arrival puts the
finished session above the blocked one. And in `check_attention`, a prompt that finishes the whole
project throws away the same `done` from the other end — you answered one session, so the row
vanishes, and nothing is ever said about what was underneath it. All four are caught, and the
fixture is built so that age alone gives the wrong answer: the `needs` arrives **first** and the
`done` second, so nothing but the kind can put the `needs` on top.

**One mutant breaks a config instead of the code.** Task 24 made a `done` sound the same on the Mac
as on the ball, and the way it does that is `"@cry"` in `config/signals.json` — a token meaning
*whatever voice the ball is using*, resolved when the config loads. A path typed there would have
worked today and been a second copy of the same fact, free to disagree with `--cry` tomorrow. So
`check_ladder` loads the config twice, with different cries, and the mutant is the version that
answers `"@cry"` from the shipped path and ignores the one it was handed. It breaks exactly the two
rows that are about `--cry` and leaves the three that are not, which is how you know the rows are
about the resolution and not about the sound.

**Three more arrived with task 22**, the `SessionEnd` hook, and one of them is not a mutation at all
— it is the code as it shipped. `NeverEnds` is a version where a closing session changes nothing,
which is exactly what happened while no such hook was wired: the only thing that could take an entry
out was that same session's next prompt, and a tab whose output you read and then closed was never
going to write one. It queued, it cried, and it sat there until the snooze or a restart. The other
two are the two tempting shortcuts. `EndFinishesTheProject` takes the whole folder down with the
session you closed — the same collapse task 20 rejected, arriving by the other door and more
tempting here, because closing a tab really does feel like being finished. `EndReleasesTheHold`
treats a close exactly as a prompt is treated and ends the attention on that project; the difference
is that a prompt proves you were there and a close proves only that one session stopped waiting.
All three are caught by the same six rows.

### One script is checked against real payloads, not written ones

`check_hooks.py` asks which turns count as a person arriving, and the input it takes is a Claude
Code hook payload — so a fixture written by hand would carry the same assumption as the function
under test, and agree with it for the same wrong reason. The fixtures in `tests/fixtures/payloads/` are
**real lines lifted out of `var/events`**, an injected one among them, then scrubbed: the home is
`/home/user`, a typed prompt is a stand-in of the same shape, and `launched-01.json` keeps only the
real one's keys (task 76). The raw ones stay in `var/desk/payloads/`, kept with:

```bash
venv/bin/python3 var/desk/capture_payloads.py                # list what is in var/events
venv/bin/python3 var/desk/capture_payloads.py typed 3        # keep line 3, labelled by you
venv/bin/python3 var/desk/capture_payloads.py injected 11
```

**The label is yours, not the code's.** Listing prints each prompt's first line and nothing more;
which kind of turn it was is answered by looking, not by asking `hooks.by_person`. Copy out
anything worth checking against while it is there: `check_daemon.py` and `check_criteria.py` no
longer unlink `var/events` (they run in `sandbox.py`'s throwaway tree), but it is still the only
place a genuine payload exists.

---

## Part B — what only a hand and a ball can answer

Wake the ball with its top button, start the daemon, and go through these. The daemon runs with no
ball present; that is the mode the whole thing is developed in, so anything below that does not say
"with the ball" can be done without one.

Only one process can hold the ball. Before starting, make sure no otherproject daemon and no second
wobble is running (`pgrep -fl 'src.daemon|otherproject'`) — in a previous round a stray one fired
real effects into desk runs more than once.

```bash
venv/bin/python3 -m src.daemon          # the real thing
```

1. **The ball lights.** Fire a `done` (finish a Claude Code turn, or `tools/hook_event.sh done`).
   The ball should say *"Pika-chu"* **and flash**. The cry alone with a dark ball is the defect
   found on 2026-09-22 and fixed; this is the step that confirms the fix against hardware.
2. **Superseded by task 35 — step 18 is this step now.** There is no silent flash any more: a
   `done` holds effect 9's light between its two cries. What follows is the old shape, kept for the
   record of how it was checked.

   **The flash keeps going after the voice stops.** Leave it and watch for a full minute. **Five**
   seconds after the cry the ball flashes silently, and again every three seconds; at thirty it
   cries a second time, and the blinking pauses five seconds for that one too; after that it is the
   flash alone, for as long as anything is pending.

   **Listen to the second cry, not just the first.** It is the one that tells you whether the gap
   is right: the first cry plays out of a slot that was filled on connect, and the second has to
   wait on its own upload, so a blink crowding it is audible there and nowhere else.

   Changed twice on 2026-09-22, and the second change was the one left unproved against hardware
   until the round of 2026-09-23 (Part C.3). It first said "thirty seconds after the cry the ball flashes again" — what the config
   used to do, and what a camera showed to be a ball that made a noise and went dark for **60.1 s**
   (Part D.10). It then said three seconds, and three seconds was an upload landing on top of the
   cry that was still sounding, heard at the desk as a cry coming out fast and choking (Part D.13).
   Five is the cry's own length with room around it, and it comes from the `.wav` rather than from
   a number somebody liked.
3. **The menu bar count drops on B.** Queue two signals, watch the bar (`● 2`), press B, watch it
   become `● 1`. The transcript's `(1 left)` is the core's count; the bar is the other half, and
   only an eye joins them.

   **The title with a queue in it, seen 2026-09-22 23:31** (`menubar-one-pending-battery.png`):
   `● 1 · 100%` — the dot filled for a connected ball, one pending, the battery where the word
   "ball" goes. So the row renders with a queue and not only empty, which is the half the earlier
   `○ · 100%` shot (step 10) could not show. **The drop on B is still unwatched**: this is one
   frame, and what the step asks for is two.
4. **B from the ball, in a pocket.** Put the ball in a pocket and press B through the cloth. It has
   to work without looking at it, because not looking at it is the entire point.
5. **The window comes forward.** With a window whose title carries the project, press B and watch
   it come to the front — the app in front of every other app, and that window in front of its own
   app's. Unlock the screen first; see criterion 10 below for why.
6. **The ball disconnects.** Walk out of range, or let it sleep. The menu bar must say so in words.
7. **Several pending, ball then connects.** Queue two signals with the ball asleep, then wake it.
   It should pick up the current state, not replay the two it missed.
8. **Accessibility refused.** Untick this process in System Settings › Privacy & Security ›
   Accessibility, restart the daemon, and press B. The notification must still work and the daemon
   must say, in words, that it did not raise anything. Run it with the app (step 20): untick
   *wobble*, not VS Code, and read the words in `var/app.out`.
9. **A signal does not answer itself.** Start something in Claude Code that runs in the background,
   walk away, and let it come back on its own. The turn it starts is a `UserPromptSubmit` like any
   other, and the signal must **still be pending** when you return. If the daemon printed
   `ignored  a turn the agent started itself`, that is the line to look for; if the signal is gone
   instead, `hooks.by_person` did not recognise the wrapper and the queue quietly emptied itself.
10. **The menu, the list inside it, and the right-click that is now the B button.** Left-click the
    menu bar item. A menu opens and the top of it is the queue: one line per project, `needs`
    before `done`, oldest first within a kind, with `, +N more` on a project that has several
    sessions waiting. Below a separator, one line about the ball — *Disconnect the ball* while
    connected, *Connect the ball* once you have, *Stop looking for the ball* while it is scanning —
    then a separator and *Quit wobble*. With an empty queue the list is a single greyed *Nothing
    waiting*, which is the hollow dot's argument in menu form.

    **Choose the second project, not the first**, and this is the half worth checking: taking the
    top is what B already did, so only a line below it proves the menu aimed anywhere. The
    transcript must read `B aimed  attending <kind> (N left)` against the project you chose, its
    window must come forward, and the next open of the menu must have lost that one line and kept
    the others in order.

    **Then right-click (or control-click) and confirm B fires.** The two gestures swapped at task
    21 — left opens the menu, right presses B — and the routing lives in `_Clicks.clicked_`, which
    reads the event AppKit is holding. What to look at, because with an empty queue nothing on
    screen moves: the daemon prints `B pressed` on every press whether or not there was anything to
    attend, so with `○` in the bar the line to watch for is `B pressed  attending nothing
    (0 left)`. No signal needs queueing first — queueing one would make the test worse, because
    then a changing count could be mistaken for the press when the press is the thing under test.

    **Seen 2026-09-22 23:02, before the swap** (`menubar-right-click-menu.png`): the menu opened on
    a right-click with *Disconnect the ball* in it, beside a title reading `○ · 100%` — a connected
    ball, nothing pending, and the percentage where the word "ball" would otherwise be. That pass
    proves the seam really does tell the two gestures apart on hardware, and that the labels match
    the state. What it cannot prove is which branch each gesture reaches **now**: the swap
    exchanged exactly those two branches, so the old screenshot is evidence for the mechanism and
    evidence against nothing. Neither gesture has been pressed since, and the list has only been
    seen in a smoke run driving the real NSMenu in process.
11. **Disconnect on purpose, and tell the two silences apart.** Choose *Disconnect the ball*. The
    menu ball must go **faded** and **not** hollow, with *Ball off* in its menu (task 63; until
    then the title read `ball off` against `no ball`): one of those means "press the ball's top
    button" and the other means "you did this, nothing is wrong", and a person hunting a ball that
    is working perfectly is the cost of collapsing them. Fire a `done` — the Mac takes the sound
    back over. Then *Connect the ball*, and it should come back **without waiting out a retry**;
    the retry sleep is interruptible for exactly this moment, so more than a second or two of
    nothing is a real finding.
12. **The battery is a reading, with the ball.** On connect the menu ball's top half turns red
    down to what is left, and its menu gains *Battery 87%* (task 63; until then the title
    gained `● 2 · 87%`), and the transcript says it once. Compare it against what the Switch or a phone
    reports for the same ball — this is one GATT byte from `2A19`, so the two should agree exactly,
    and a disagreement means the characteristic is not what it is assumed to be. **A ball with no
    percentage at all is a pass, not a failure**: it means the read was refused, `no battery
    reading` is in the transcript, and nothing invented a number.

    **A number arrived, 2026-09-22 23:02: `100%`.** That is a reading and not yet a measurement.
    `0x64` is exactly what a characteristic answers when it is pinned, defaulted or padded, and
    100 is the one value a wrong `2A19` is most likely to produce — so it is the most comforting
    result and the least evidence. What would settle it is any of: the same ball reading something
    other than 100 after a few hours of use, or the Switch reporting the same figure at the same
    moment. Until one of those, treat the plumbing as proved and the *value* as unconfirmed.
13. **What the menu costs the link, with the ball.** Open the menu and leave it open for ten
    seconds while a `done` is beating, then let it close. `popUpMenuPositioningItem_` runs a modal
    tracking loop, which blocks the daemon's poll for as long as the menu is up — so the questions
    are whether the ball drops, whether beats queue up and arrive in a burst afterwards, and
    whether the transcript says anything about the pause. **Nothing has measured this**, and it is
    the one thing the new surface could plausibly break.
14. **It stays quiet while you are looking at it — and speaks the moment you are not.** Start the
    daemon, and at startup read the line it prints: `watching  … In front right now: <title>`. That
    title is the whole feature, because the match is the folder name inside it. **If your folder
    name is not in that sentence, nothing below will ever fire** — and the symptom is notifications
    arriving normally, which is also what a working day looks like.

    Then, with that window in front, fire a `done` in it. The daemon must say `not signalling …
    you are looking at its window, so it stays pending and quiet`, the ball must stay silent and
    dark, and **the count must still go up** on both mirrors — quiet is not resolved. Now click
    another window. The cry must come **3 s later** (`look_away.wait_s`, task 37), not thirty: a `done` you watched
    arrive has not spent its beats, it has had its clock stopped. Click back and away again and it
    must not cry a second time out of turn. And a pass through its window, in front under a
    second (`look_away.glance_s`, task 67), is not a look: no `not signalling`, no 180 on the
    ball, and no 9 with its buzz three seconds later.

    **Two halves that are easy to only half-check.** Going quiet is the visible one and the one
    that will look right whatever happens; the one that costs you a notification is the clock, and
    the only way to see it is to look away and time the gap with something other than your patience.
    `check_watching.py` takes that apart second by second, and this step is what says the title it
    is matching on is a title your terminal really produces.

    **The clock half was answered on 2026-09-23, by ordinary use rather than by this step** — a
    `done` watched for 4 min 42 s and crying in the same second as the look-away. The transcript
    and why 282 seconds is the number that settles it are in Part E. What is left here is the
    hardware leg: that the ball itself is silent and **dark** through the watching, which a log
    cannot say.

    **A signal from a session you are *not* looking at must behave exactly as before.** That is the
    reference leg, and it is not optional: both going quiet is indistinguishable from the ball
    having died.
15. **Quit, and what it does with the ball and the queue.** Queue a signal or two, connect the
    ball, then left-click the item and choose *Quit wobble*. Four things, and the first is the
    only one you can see from across the room:

    - **The menu bar item goes.** Nothing is left behind, and no second item appears on the next
      run. That is the whole reason quitting exists in the menu rather than only at the terminal.
    - **The transcript says what it did**, in this order: `quit  chosen from the menu bar — N still
      pending, and the next run brings back the ones whose claude is still running, quietly`, then `ball let go  took 0.Ns`, then
      `stopped  nothing is watching for signals from here on`. A daemon that went away without a
      word is the one failure principle 7 cannot allow, and this is the one time going away is
      expected — so it is also the one time the words are all there is.
    - **The ball really lets go.** Its light goes out, and the next run finds it rather than
      waiting out a link the OS still thinks is open. If the line reads `BALL NOT LET GO` instead,
      the daemon quit anyway on purpose — the ball drops the link by itself a few seconds later —
      but it is worth knowing which happened, because "it quit instantly" and "it waited two
      seconds" are different answers about the same button.
    - **Nothing pending is thrown away** (task 47). Restart the daemon: each entry that was still
      waiting, in a claude that is still running, comes back as a `restored` line, then `restart  N back
      from before it (quiet)`. No sound and no light, the count stays at what arrived since,
      and the menu lists them under a separator of their own, `from before the restart`. B reaches
      them once nothing new is waiting. A new signal, a prompt or a close in one of those sessions
      works on it as usual. Quitting is putting the ball down, not answering anything.

    **And the misclick this is really guarding against.** The line above *Quit wobble* switches the
    ball's link. Open the menu and look at the gap: there must be a separator between them. Losing
    it is invisible in every automated check that reads labels — `check_macos_seam.py` asks AppKit
    itself whether item 1 `isSeparatorItem()` for exactly that reason — but what it costs is
    somebody ending the run while reaching for *Disconnect*.

16. **Five seconds between your keystroke and the ball** (task 25). With the ball connected and a
    `done` pending from a **different** project, type anything into a Claude Code prompt. The
    daemon must say `holding … you just typed, so it waits 5s before speaking`, the ball must stay
    silent for those five seconds, and the cry must then arrive on its own — plainly a second
    event and not an echo of the keystroke. That separation is the whole of the task, and it is
    the half no check can ask: `check_criteria` can prove the beat moved five seconds, and only an
    ear can say whether five seconds is enough for it to stop sounding like an answer.

    **Two things to watch that are not the cry.** A `done` that was **already flashing** keeps
    flashing through the hold — the light was already saying what it says, and stopping it would
    be the ball going dark for a reason nobody can see. A `done` that arrives **during** the hold
    stays dark for all five seconds, on purpose: its first flash would otherwise land ahead of its
    own cry, which is the stutter of Part D.2 coming back. So the two cases look different at the
    ball, and both are correct.

    **And the number a log makes look worse than it is.** From the keystroke, the cry is 5 s away
    and the first silent flash is 10 — five of hold and then the cry's own quiet. Typed out it
    reads like a long time to wait; at the desk the question is only whether the ball feels late,
    and nothing has asked it yet.

17. **Superseded in part by task 35**: muted is `4` for a `needs` and `9` for a `done` now, not
    `213`, so the "it does not buzz" answer below is about an id no longer played. Step 18 has the
    muted half.

    **Mute mode: the same ball, with the sound taken out of it** (task 34). With the ball
    connected, open the menu and choose *Mute the sounds*. The title gains the word — `● 1 · muted
    · 87%`, a crossed-out speaker beside the drawn ball since task 61 — and from then on every signal is a buzz and a flash and nothing else. Fire a `done`:
    the ball must **move** and stay silent. Fire a `needs` and leave it: it must buzz every 1.5 s,
    the same rhythm it has today, still silent. Choose *Unmute the sounds* and the voices come back.

    **Answered 2026-09-24, and the answer is no: it does not buzz.** `probe_mute_candidates.py`
    fired `213` in 1 of 8 rounds (median 1.73× its own floor) while `199`, on the same link in the
    same minute, fired 8 of 8 at a median of 21.9×. The `9.59×` that pointed here was one round of
    one id, against a floor shared by twenty ids, scored as a mean over 1.5 s — a ranking of the
    map, never a measurement of a single id. So muted, the ball flashes and stays still, and **the
    fix is the config key** (`mute.effect` in `config/signals.json`), no code. Which id goes in it
    is open: of the nine that buzz 2 of 2, the desk heard a voice on all but `171` and `172`, and
    those two are four times stronger than anything else in the map. Until that is settled, expect
    this step to pass on the silence and fail on the buzz.

    **Then check the two kinds apart.** Muted, `needs` and `done` are the same effect, the same
    colour and the same silence: a single buzz of one feels exactly like a single buzz of the
    other, and the only thing left telling them apart is the rhythm. That is a known cost rather
    than a defect, and what this step asks is whether it is a liveable one — whether "every second
    and a half" and "twice in a minute" are actually distinguishable in a pocket, or whether muted
    mode needs the two colours `led_chosen.json` has been holding since before this rewrite.

    **And leave it muted for a while on purpose.** The failure this mode invites is forgetting it
    is on, which is principle 7's silent notifier with a switch on it. The word in the title is the
    whole of the defence; the question for the desk is whether you actually see it there.

18. **The held light, and the two kinds told apart by eye** (task 35). With the ball connected
    and nothing pending, the ball is **dark** — every connect starts with `180`.

    - **A `done`.** The ball lights up with Pikachu's colour, buzzes lightly, and cries *"Pika-chu"*
      with a strong rumble — `play (beat) effect 129 over light 9` in the transcript. Then leave it
      and watch a full minute: the light **stays on**, pulsing by itself, with nothing in the log
      between beats. At 30 s it cries once more, **without** a second light buzz (9 is already
      up). After that, the light alone, for as long as it is pending.
    - **B.** The light goes out (`lights off`) with nothing else pending.
    - **A `needs`.** `199` every 1.5 s: the catch UI's wobble, its own colour. It must read as a
      different thing from a `done` **at a glance** — the reason these ids were chosen.
    - **A `needs` over a lit `done`, then B on the `needs`.** The light changes straight from one to
      the other with no dark moment between (light replaces light), and when the `done` gets the
      floor back its 9 comes back with a cry.
    - **Look at the session's own window** while its `done` is lit: the light goes out. Look away:
      3 s later it comes back (`light back`) with one light buzz and no cry. That extra buzz is by
      design. Look back **inside** the 3 s and nothing happens at all — no light, no buzz, no line
      in the log (task 37). Seen 2026-09-28 before task 37: all of it, with the light back at once.
    - **Muted.** A `done` is 9 alone — the light and its buzz, no cry — on both beats. A `needs` is
      `4` every 1.5 s: 199's colour and rumble, silent. Muting over a lit `done` changes nothing on
      the ball until the next beat.
    - **Quit, each way** — the menu, Ctrl-C in the terminal, `kill <pid>` — with a `done` lit: the
      ball goes dark before the transcript says `ball let go`, and the process is gone at once.

    **What would be a defect:** the light going out by itself while something is pending; a cry
    from `213`'s captured Pokémon instead of Pikachu (the catch slot touched); the ball left lit
    after any of the three quits.

19. **Each line in the menu says where it stands** (task 36). With two real sessions pending, open
    the menu. The top one reads `· signalling` and the other `· waiting its turn`. Bring the top
    one's window to the front and open the menu again: `· quiet, you're looking at it`. Press B:
    that line reads `· attending (back in 5m)`, counting down in whole minutes (never `0m`), and
    the other one stays `· waiting its turn` — nothing speaks while one is held. Each change
    writes one `menu` line to the transcript, without the countdown. B's one moves to the bottom
    of the list while held: it is out of the queue, which is also why the count drops by one.

    **An open menu does not change.** It runs a modal tracking loop that stops the daemon's poll
    until it closes (`ports.py`, `Status`; step 13), so the words are what was true when it opened,
    and the next open shows what moved. Seen 2026-09-28: a `done` arriving under an open menu
    appeared only after it was closed and opened again. That is the accepted trade-off, not a
    defect — and it means the flicker named as the risk when this was agreed cannot happen.

    **What would be a defect:** a line with no status; two lines both `signalling`; the countdown
    reading `0m` or not moving between two opens a minute apart; a `menu` line in the log every
    refresh instead of once per change. Seen 2026-09-28: all four words on the real menu, `5m` then
    `4m` a minute later, one `menu` line per change.

20. **wobble as an app** (task 50). Quit any daemon started from a terminal first, then:

    ```bash
    venv/bin/python3 tools/build_app.py --install --reset-grants   # replaces task 48's probe
    open /Applications/wobble.app
    ```

    The first launch asks twice, both times as *wobble* and not as VS Code or Python: Bluetooth,
    with the sentence from the Info.plist, and Accessibility, through the system's own dialog that
    sends you to System Settings. Allow both, then quit from the menu and open it again: nothing is
    asked the second time. `var/app.out` has the startup lines, with `accessibility granted`.
    Then, one at a time:
    - `venv/bin/python3 -m src.daemon` from a terminal while the app runs: it says
      `ALREADY RUNNING` with the app's pid and stops. The app keeps running.
    - Quit it and start the terminal daemon, then open the app: an alert *wobble stopped*, `exit
      status 1`, and `ALREADY RUNNING` in `var/app.out`.
    - *Quit wobble* from the menu: no alert, and `pgrep -fl 'wobble|src.daemon'` finds nothing — the
      launcher and the daemon are both gone.
    - Rebuild with `build_app.py --install` and nothing changed: `grants  the same bytes as before`,
      and the next launch asks nothing.

    **What would be a defect:** a dialog naming VS Code, Python or `sh`; asking again on the second
    launch; an alert on a Quit from the menu; a launcher left running with no daemon under it.

21. **A `done` cries in a mood** (task 64). With the ball connected, from real sessions only —
    `check_cries` and `check_daemon_edges` already answer which pool each case picks, so what is
    left is the ear and the eye. Rerun `tools/install_hooks.py` and restart Claude Code first, or
    the banner says `NOT wired: StopFailure`. Each case below is one line in the log, `play (beat)
    effect N over light 9 · <mood>`; the step is whether the sound fits the word.
    - **happy / proud / call.** A short turn: one of 20, 32, 34, 181, 230, then 33 thirty seconds
      later. A turn of 10 min or more: 32 or 34 first.
    - **lonely.** Leave a `done` unanswered: about 5 min after its first cry, 143 once more, and
      **light 9 held through it** — the ball's own light must not drop to dark or to 143's.
    - **soft.** Keep the session's window in front and touch nothing: after 60 s the log says `no
      input for 60s with its window in front`, and the ball cries 230. Touching the mouse before
      then keeps it quiet.
    - **greet.** After a `done` has cried twice, press B — or come back to the keys after 15
      minutes away, or the Mac asleep that long, while it is still pending (task 67): 29 once, `play (greet)` in the log, never a second time for
      the same signal, not even when its snooze brings it back. Pressed within 10 s of its call, nothing plays over the call: the log says
      `no greet — effect 33 played Ns ago` (task 67).
    - **sad.** A turn an API error ends (StopFailure): `queued … — the turn ended in an API error`,
      then 21 or 22.
    - **In the app.** Open `/Applications/wobble.app` and read `var/app.out`: the banner's `idle`
      line has a number, not `CANNOT SEE IDLE` — the HID idle time needs no permission, measured
      from the venv only.

    **What would be a defect:** a mood word that does not match what happened; 143 dropping the held
    light; a greet twice; a soft cry while the mouse was moving; any of these on the Mac's own
    sound, which plays `pikachu.wav` for every pool — that is the known limit, not a defect.

22. **An approved Bash stops its question at once** (task 65). From a real session with no
    allow rule for it, ask Claude to run a Bash that lasts — `sleep 60` is enough. When the
    permission prompt beats, approve it:
    - Within about a second of the yes, the log says `resolved … — its Bash started (pid N), so
      it was approved`, then `play (caught)`, and the beat stops while `sleep` still runs.
    - When `sleep` ends, nothing more is said for it: its `PostToolUse` answers nothing.
    - Once from the VS Code panel and once from the CLI in a terminal — only the first was
      measured when it was built.

    **What would be a defect:** the beat going on until the command ends; a question about
    another tool (a Read, an MCP tool) going quiet when some Bash starts; a `CANNOT SEE
    CHILDREN` line on this Mac.

23. **B mashed between two VS Code sessions opens no second tab** (task 66). Two VS Code
    windows, each with a Claude session waiting (a `needs` or a `done`). Press B about once a
    second for 15 s, so it alternates between them, then once more and wait two seconds:
    - No new tab titled "Claude Code" in either window, and the last session pressed is the
      one in front at the end.
    - The log has a `NOT FOCUSED — never tried — B moved on to …` line for each press that
      landed while another raise was still waiting.
    - Every `focused` line names its own project's window in front, never the other one.

    **What would be a defect:** a "Claude Code" tab appearing; a `focused` beside the other
    project's title; windows still flapping a few seconds after the last press.

24. **One effect at a time** (task 67). From real sessions only, with the ball connected:
    - **No greet over a call.** Let a `done` snooze (B, then wait 5 min). When it comes back
      with 33, press B within 10 s: no 29, and the log says `no greet — effect 33 played Ns
      ago`. Press B again later: still no 29 — one greet per done, snooze or not.
    - **A glance is not a look.** With a `done` pending, alt-tab through its window without
      stopping: no `not signalling`, no 180, and no 9 with its buzz 3 s later. Stop on it for
      two seconds and it does go quiet.
    - **Coming back.** Leave a `done` pending and walk away for a minute: nothing on return.
      Then for over 15 minutes, or close the lid that long: on the first key, 29 once and
      `you are back: …` in the log, naming which one it was. The banner's `back` line says 900s.

    **What would be a defect:** two sounds within a few seconds for one signal; a buzz from a
    window passed through; a greet after a minute at the coffee machine; no greet after the
    Mac slept.

25. **A seen done stays quiet, and a session can be silenced** (task 68). From real sessions
    only, with the ball connected:
    - **A seen done comes back quiet.** B on a `done`, then wait out the snooze: it is back in
      the menu as `seen, kept quiet`, the log's `snooze` line ends `quiet — you had seen it`,
      and the ball neither lights nor plays for it. A `needs` treated the same way comes back
      calling.
    - **The tap is the release now.** A quick B still takes the top; nothing happens until the
      button comes up. Feel whether that delay reads as a slow ball.
    - **Hold B for 2 s** on a session that is calling: blue 179 with a tick (effect 2), then
      180 after a second, no sound from either surface. The log says `silenced — … quiet until
      you type in it or answer it`; no `B pressed` for the hold, no window raised.
    - **Its next signal is quiet.** Let that session ask something new: the log's `queued`
      line ends `silenced, so it waits quiet`, and the ball stays still.
    - **Typing in it ends it.** Send a prompt there: `unsilenced — you typed in it`, and its
      next `done` beats again. Answering its own question where it asked does the same.
    - **The menu's ⌥ row.** With the menu open, hold ⌥: each pending line turns into
      `Silence <project>`; choose one, and the same confirmation plays. A silenced line shows
      `silenced until you type in it` and has no ⌥ row.

    **What would be a defect:** a tap firing on the press, or a hold also counting as a tap; a
    silenced session lighting the ball; the silence outliving a prompt in it; the confirmation
    making a sound. Judge the 2 s hold and the blue 179 as proposals — both are GUESSES.

26. **B reaches a window on another desktop, and a repo below the folder** (task 69). From real
    sessions only, with two desktops and a VS Code window on each:
    - **Its own window, by the folder.** A session in a repo below the folder VS Code opened
      (`workspace`, working in `workspace/documents`): the menu still lists it as
      `documents`. With its window in front, its signal stays quiet (`not signalling`); B on it
      from another window of the same desktop says `focused` beside `workspace`.
    - **Across desktops.** From desktop 2, B on a session whose window is on desktop 1: the
      Mac switches to desktop 1, that window comes forward with the session's tab, and the log
      says `… was opened in it and '…workspace…' came forward`. The same from the menu row.
    - **No new window.** Nothing opens that was not open before — no second VS Code window, no
      tab titled "Claude Code".

    **What would be a defect:** a new VS Code window; the desktop not switching; a `focused`
    beside another folder's title; a `NOT FOCUSED` for a window that did come.

27. **The Mac's own sounds, and yours** (task 70). With no ball (`--no-ball`, or the ball off from
    the menu), from real sessions only:
    - **wobble's own.** With `assets/sounds/` empty or absent: a `needs` plays `sounds/needs.wav`,
      a short wobble, every 1.5 s, and answering it plays `sounds/caught.wav`, the catch's click.
      Neither runs into the next beat.
    - **Yours.** A file named `needs` in `assets/sounds/` (any of `.wav .aiff .aif .m4a .mp3 .caf`),
      then a restart: the banner says `your sounds  … needs needs.wav`, and that file plays for
      the next `needs`. A file named anything else is said under `NOT YOUR SOUNDS`.
    - **The ball is untouched.** Connect the ball: the same `needs` wobbles with 199 and a done
      cries Pikachu, whatever is in `assets/sounds/`.

    **What would be a defect:** Tink or Hero on a fresh checkout; your file playing on the ball;
    a file in `assets/sounds/` that plays nothing and is not said.

28. **A subagent's question ends when that subagent's tool runs** (task 71). After
    `tools/install_hooks.py` wired `PermissionRequest` and Claude Code restarted, from a real
    session only:
    - **Ask something a subagent does with Bash** — an `Explore` or `general-purpose` agent told
      to run a command no rule allows yet. Its permission prompt shows in the main window.
    - **The needs says who asks.** The log's `queued needs` line ends `a subagent asks it, so only
      its answer counts`, and `var/events` has an `asking` line just before the `needs`, its
      `agent_id` filled.
    - **Approve it.** The beat stops within a second or two of the subagent's tool running: the log
      says `resolved needs · … — answered where it asked`, and the catch plays.
    - **The main thread is unchanged.** A main-thread Bash prompt still queues without
      `a subagent asks it` in its line, and its own answer still resolves it.

    **What would be a defect:** the needs beating on after the yes (juno, 2026-10-02, 13:19 — the
    bug this step exists for); a subagent's needs resolved by a main-thread tool; no `asking` line
    before a permission `needs`, which means the host fires them the other way round and the
    question falls back to the main thread's rule.

29. **A permission question beats as it shows** (task 72). From a real session, with the hooks of
    step 28:
    - **Ask for a Bash no rule allows.** The beat starts with the prompt on screen, not 6 s later:
      the log's `queued needs` line has the second of the `asking` line in `var/events`.
    - **Leave it unanswered for 10 s.** At about 6 s the log says `its notice needs · … — Claude
      Code's own`, and the menu still shows one needs, not two.
    - **Answer one within 6 s.** It beats, and the yes resolves it with the catch; no `its notice`
      follows.
    - **Deny one** (task 73). The beat stops when the turn ends: `resolved needs · … — its turn
      ended`, the catch, and the done after it. The needs does not come back.
    - **Ask with AskUserQuestion**, with nothing else waiting. It beats as it shows, like the Bash:
      `var/events` has an `asking` line for it (measured 2026-10-05, task 72).

    **What would be a defect:** a beat that starts only at the notice; two needs for one question;
    a needs still beating after a quick yes, or back after a denial; a prompt never shown that
    beats on (the risk task 72 accepted — write down what asked).

30. **wobble opens at login** (spec 02; the line is in **Settings ›** since spec 03). With
    `/Applications/wobble.app` built and running:
    - **Switch it on, log out and in.** *Open wobble at login* is checked, and after the login
      the app is running with its grants: B raises a window and the ball connects, with no
      prompt. `var/app.out` says `at login  on`.
    - **Switch it off, log out and in.** wobble does not start.
    - **Switch it off in System Settings** › General › Login Items & Extensions › App Background
      Activity, with it on in the menu. The line reads *Off in Login Items — open System
      Settings*, and clicking it opens that pane; switching wobble on there brings the line back,
      checked.
    - **Quit it after a login.** It stays quit until the next login.

    **What would be a defect:** a prompt for Bluetooth or Accessibility after a login; the line
    checked while System Settings has it off; a click that changes nothing and says nothing;
    wobble coming back after a Quit.

31. **A permission switched off says so in the menu** (spec 03). With `/Applications/wobble.app`
    built and running, and every permission allowed:
    - **Before anything.** No ⚠ line, no ⚠ in the title. **Settings ›** has *Bluetooth* and
      *Accessibility* checked, and the log has a `permission` line for each, with the app's own
      answers (spec 03 task 01 measured them only from a terminal).
    - **Switch Accessibility off** in Privacy & Security › Accessibility. Within two seconds the
      menu's top line reads *⚠ Accessibility off — B raises no window · Open…*, the title ends in
      ⚠, and the log says `PERMISSION OFF` once. Click the line: System Settings opens at
      Accessibility.
    - **Switch it back on.** The line and the ⚠ go by themselves, with no restart, and the log
      says `accessibility granted` once.
    - **Bluetooth off** in Privacy & Security › Bluetooth: its own ⚠ line, and the link line still
      says what it says today.

    **What would be a defect:** a refusal the menu does not show within a few seconds; a ⚠ that
    stays after the grant; a pane that is not the permission's; a log line every two seconds
    instead of once per change; any line that reads ✓ for a permission macOS could not answer.

32. **Eevee speaks** (spec 04). With both cries fetched (`./install.sh`), the new ball connected,
    and a real session to finish:
    - **Choose Eevee** in **Settings › Partner**. The ✓ moves at once, the log's `partner` line
      says `Eevee now, with eevee.wav and led 1180 — …` once, and `var/partner` reads `eevee`.
    - **Finish a session.** The ring lights beige, not yellow, and so does the menu bar's ball.
      The cry is Eevee's by ear: happy after a quick turn, proud after a long one, sad after an
      error (the ids in the log's `play (beat)` line are from `49`–`63`, `143` or `231`). Write
      down any mood that sounds wrong for Eevee — the mapping is a guess (spec 04, open
      question 1).
    - **The beige itself.** Look at the ring beside a real Eevee picture or the Switch's. Write
      down the value that looks right; `1180` is a guess (open question 2).
    - **`129` after the switch.** Quit, start with `--one-cry`, and finish a session: the ball
      plays Eevee's cry from the upload, not Pikachu's. On the old ball, without the flag, the
      same.
    - **Across a restart.** Quit and start again: the banner's `cries` line says
      `from Eevee's own`, and the menu's ✓ is still on Eevee.
    - **Back to Pikachu.** Choose it: yellow, `led 138`, Pikachu's cries, exactly as before.

    **What would be a defect:** a ✓ that does not move, or moves back; a yellow ring or Pikachu's
    cry after Eevee is chosen; `129` playing the old cry after a switch while connected; the
    choice lost on a restart; a log line every read instead of once per change.

### When your own eye is the instrument, point a camera at it

Steps 1 and 2 are about light and about time, and both are things a person watching is bad at:
thirty seconds of nothing feels like a minute, and a flash you were waiting for is one you are apt
to see. The Anker PowerConf C200 on the desk answers both, and the film is evidence that can be
re-read — a judgement made while staring at a ball cannot be.

```bash
ffmpeg -f avfoundation -framerate 30 -video_size 1280x720 -i "0:1" -t 115 run.mp4
ffmpeg -i run.mp4 -vf signalstats,metadata=print:key=lavfi.signalstats.YAVG -f null - 2>&1 \
  | grep -A1 pts_time                       # per-frame brightness; a flash is a spike
```

Turn the room light off — this is not a nicety, it is the whole measurement, and the numbers are
below. Device `0` is the camera and `1` its microphone; check with
`ffmpeg -f avfoundation -list_devices true -i ""`, because the numbering moves when anything else
is plugged in. The C200 offers 30 fps only — asking for 15 fails with `Selected framerate ... is
not supported`, and whatever you backgrounded to fire the signal has already fired by then.

**What this camera can and cannot see**, measured on 2026-09-22 rather than assumed:

| Leg | Against | Result |
|---|---|---|
| luma, lit room | LED flash | blind — baseline 54.6 ± 1.2, a flash lifts a crop by 1.4–1.8, and a 4σ search finds 0 events |
| audio, template injected at 0.35× room peak | the cry | found, 3.1 σ clear, top three windows |
| audio, real ball cry through this mic | the cry | **not found** — best 8.59, against 7.97 in a take with no cry at all |

The last row is the one that matters and it is the one nobody checks: a probe that finds a cry you
*inject* is not a probe that finds a cry the *ball* makes. The ball's speaker is small, band-limited
and playing ADPCM, so it arrives at the microphone unlike the `.wav` the template comes from. Read
against a take where the ball demonstrably cried, the matcher could not tell it from room noise —
so a quiet result from this leg is a fact about the microphone and not about the ball. `done` has
`mac_sound: "@cry"` since task 24, but the Mac only plays it when no ball is connected, so there is
still no louder fallback: when a ball is connected, the ball is the only thing making the sound.

Three traps, all met on 2026-09-22 and all in `specs/01-mvp/learnings.md`:

- **The audio will contradict the video, and the audio is the one that is wrong.** A broadband RMS
  window around a flash read 15 dB over the room and looked exactly like a cry that should not have
  been there. It was somebody moving in the room. What settles it is the shape and not the level —
  the cry peaks at 2 kHz with energy up to 3.5 kHz; a room noise peaks near 125 Hz with nothing
  above 1 kHz. One number from one field is not a finding.
- **The daemon you are filming is the code it was started with**, not the code on disk. Check its
  start time against the mtime of everything you have edited before believing the film is about the
  version you think it is.
- **Calibrate the probe on a take where the thing definitely happened, before believing a quiet
  result.** Not on a signal you injected yourself: that shares every assumption the probe does, and
  it passed here while the real article failed. The reference leg is the earlier film — the ball
  cried in it, so anything that cannot find the cry *there* has not measured the ball anywhere.

---

## Part C — the acceptance criteria, and where each one is answered

Verdicts as of **2026-09-22, 22:31**, on Darwin 25.6, Python 3.12.14, PyObjC 12.2.2. Rows 1 and 3
were reopened on **2026-09-23, 12:58** by a round on the ball itself — see 3 below.

| # | Criterion | Answered by | Verdict |
|---|---|---|---|
| 1 | `done` → cry once, LED on, one pending | `check_daemon`, `check_criteria`, `check_ball_mirror`; the ball itself for the LED | green — the ball lit on 2026-09-23 (the pulses watched; the beat's own flash not called out) |
| 2 | `needs` → wave repeating, LED on, above a waiting `done` | `check_queue`, `check_ladder`, `check_daemon` | green |
| 3 | Nothing dismissed → it keeps speaking; the LED pulses silently | `check_rhythm`, `check_criteria`, `check_ladder`, `check_ball_mirror`; a camera at the ball | green — the new rhythm seen on the ball 2026-09-23 |
| 4 | B → silent, LED out, count drops, the window comes forward | `check_macos_seam`, `check_daemon`, `check_focus`; live at 19:14 | green |
| 5 | A prompt surfaces the next; a prompt in **any** session drops its own entry | `check_attention`, `check_daemon`, `check_hooks` | green |
| 6 | B then nothing → **that same signal** comes back after ~5 min | `check_attention`, `check_daemon`, `check_criteria` | green, both endings |
| 7 | B while attending → skips, and the skipped one goes back to its place | `check_attention`, `check_criteria` | green |
| 8 | No ball → all of it on the menu bar, the Mac plays it, the bar shows "no ball" (a hollow ball, the words in its menu, task 63) | `check_menubar`, `check_macos_seam`, every `check_criteria` run | green |
| 9 | The ball disconnects → the menu bar's ball goes hollow, and its menu says so in words (task 63) | `check_ball_mirror` for switching it off on purpose; the link dropping by itself seen 7 times in the log, each followed by `ball disconnected` (2026-09-23 ×4, 09-28 ×3) | green; the hollow drawing after a real drop owed — all 7 predate task 63 |
| 10 | Accessibility refused → skipped, said in words, notification unaffected | `check_focus`, plus a real refusal: 2026-09-30, 20:08–21:11, 42 `NOT FOCUSED` in words and 43 beats played | green |

### 1 — a session finishes

The `queued` line for the `done` and `play (beat) effect 213` land in the same second
(`check_criteria`, 19:25:17 — before task 23 moved the project into a column, so that run's lines
read `queued done · wobble` rather than `wobble  queued  done`). The budget end to end: the hook script costs **10 ms** (measured five
times), the daemon polls every 250 ms, and a `done` beat carries **no upload on its path** — the
cry goes into the slot on connect, not on the event (task 13, at the ball). Comfortably inside the
~2 s the criterion asks for.

The LED half is fixed but **not yet seen lit**. The colour is a second resource riding the same
opcode, one frame, and it must be sent before the effect; nothing had ever uploaded one, so
task 13's ball cried in the dark. The fix is proved byte-for-byte against sniffer
captures (`check_ball_mirror` rebuilds all six captured LED resources from the index alone), but
the running daemon was deliberately not restarted, so no ball has flashed yet. **Part B step 1 is
the outstanding one.**

### 2 — a session blocks

`needs` beat 199 three times in four seconds while nobody answered, and B took the `needs` rather
than the `done` that had been queued after it (`check_daemon`, 19:23:33–19:23:37). The ordering
rule is proved separately against a kind-blind control: every priority case in `check_queue`
disagrees with a queue that ignores the kind, which is what makes the rule the thing doing the
ordering.

### 3 — nothing is dismissed

**Since task 35 (2026-09-25) this is carried by a held light, not by a pulse.** A `done` sends 9,
which stays on by itself until 180, so nothing is sent between beats and there is nothing in the
transcript to count: two beats 30 s apart and then silence, with the entry still pending. The
light itself is Part B step 18's to see. Everything below is the pulse this replaced, and how it
was proved at the time.

`check_rhythm`, 22:30:06–22:31:14, is the run long enough to see the whole shape, and it is the
shape the criterion now asks for: the cry at `0`, five seconds of quiet, a silent flash every 3 s
from `5`, the cry once more at `30` with its own five seconds, and flashing on to `68` where the
check stopped watching rather than where the daemon stopped. Counted across beats and pulses
together, **no dark stretch is longer than 5 s** and the blinking never speeds up below 3 s.

That last sentence used to be one rule — "every gap between one flash and the next is 3 s" — and
giving the cry its own five seconds broke it into two, which is worth saying because the break
looked like a regression for an afternoon. Blinks on a 3 s grid, pushed 5 s clear of a cry, no
longer line up with the next cry 30 s later: the last blink lands at `29` and the cry at `30`. One
row read that 1 s as the blinking having sped up. It has not — the blinking is still 3 s throughout
(`gaps between blinks: [3, 6]`, the 6 being the cry taking a blink's turn). What that second
actually is, is the LED lit at `29` for 1.47–1.50 s and still lit when the cry lights it again: one
continuous light, which is what a blink landing on the cry's own tick used to produce. So the check
now asks the two questions separately, and the second one rules out the middle case — a blink 2 s
ahead of a cry, which would go dark for half a second and then fire, and would read as a fault.

`check_criteria` (21:20:27–21:20:36) asks the narrower question the daemon's own seam answers: three
silent pulses, every one of them `· silent`, and `NO SOUND` never printed — the Mac is not asked to
play a beat that has no sound.

What this replaced was the defect. Until 2026-09-22 the pulse was written as the thing that starts
once the beats are used up, so the first flash fell a full interval *behind* the last cry; with one
cry and a 30 s pulse that is a ball which speaks and then goes dark. **A camera measured the dark
stretch at 60.1 s**, not 30, because the one pulse due inside it was the one spent uploading the
mute. See Part D.10.

**Seen on the ball, 2026-09-23 12:57:56–12:58:47** — the first hardware round of this rhythm, with
the daemon started after the change rather than before it. The cry at `12:57:56`, five seconds of
quiet, a silent flash every three seconds through `:01 :04 :07 :10 :13 :16 :19 :22 :25`, the second
cry at `12:58:26` — thirty seconds to the second — its own five seconds of quiet, then flashing
again from `:31` until B at `12:58:46`. The account from the room was *"pikachu first, then the
pulse, pikachu again, pulse"*, which is the config read back by an ear and an eye that had not
seen the transcript. **No choke on the second cry**, which is the symptom of Part D.13 and the one
thing this step exists to listen for.

The same round shows what the 5 s is buying. The second cry found the mute in the slot and waited
`1.7 s` for its own seventeen frames, so it sounded at `12:58:28` against a beat scheduled for
`:26`; the pulse after it came at `:31` — five seconds after the **scheduled** beat, not after the
sound. So the quiet the cry got to itself was about three seconds, against an effect that lasts
1.5 s: the flash and the voice are one effect and run together rather than one after the other.
That is the mechanism `_source_gap` describes, now with a real link in front of it. It is also the
limit of this instrument — the daemon's log is stamped to the second and everything being measured
here is one to three seconds long, so the margin is **comfortable, not quantified**. A number for
it wants the camera, as in Part D.10.

Two things the same film settled, both now in `config/signals.json`:

- **The flash is 1.47–1.50 s long**, measured across three of them, and **the same length whichever
  resource is in the slot** — the 17-frame cry and the 2-frame mute give an identical LED
  animation, because the animation belongs to effect `213` and not to the audio behind it. At a 3 s
  interval that leaves the ball lit about half the time. If that reads as too busy, `pulse.every_s`
  is the one number to turn.
- **The first silent flash still costs an upload**, but it is no longer *skipped*. The mute goes
  into the slot — two frames, 0.7 s — and the flash lands late rather than not at all. It used to
  be dropped, on a rule written for the cry's seventeen frames; with `done` blinking every 3 s the
  dropped one was always the first blink after a cry, which is the one that says the ball is still
  awake. `SkipsTheSwappedPulse` is the mutant that holds that line.

The 30 s between cries, the 3 s between flashes and the 2 cries are all **judgements, not
measurements**, and all three are labelled as such in `config/signals.json`.

`pulse.after_beat_s` is the fourth, and it is half of each. The 5 s is a judgement — Pikachu sounds
for 0.96 s, and the rest is room. What is not a judgement is that it is a **floor**: the daemon
reads the length of whatever `--cry` points at and uses `max(after_beat_s, that)`, because a longer
`.wav` dropped in later would otherwise walk straight back into the stutter with nothing anywhere
saying the config had stopped covering it. It says which of the two won on startup:

```
cry gap   5s after a cry before the blinking resumes (pikachu.wav sounds for 0.96s)
```

### 4 — press B

Three things and they were checked three ways. The sound is cut mid-play — `check_macos_seam`
confirms `afplay` running and then confirms it dead after `stop()`. The count drops — the core says
`(1 left)` in every transcript; the bar is Part B step 3. The window comes forward — seen live at
**19:14:14**, `focused  wobble — its window came forward`, one second after the press, with the
daemon still beating.

Raising is **two acts** and doing one is the failure that looks like success: `kAXRaiseAction` puts
the window in front of its own app's, `activateWithOptions_` puts that app in front of everything
else. `check_focus` asserts both, separately, and has a mutant for each.

There is nothing to turn the LED off with, and nothing needs to: an LED resource is not state, it
is a transient animation, and the light goes out on its own (task 04, measured).

### 5 — a prompt

`resolved  needs · wobble — you were there` (`check_daemon`, 21:20:15): a prompt in that session
dropped its own pending entry, and the `done` behind it took the floor in the same tick. The
mutant that leaves the entry queued is caught by `check_attention`.

**A prompt answers one session, not one project** (task 20, 2026-09-23). Two sessions in the same
folder are one entry and one trip to one window, but typing in the blocked one does not finish the
one that had already finished beside it. `check_criteria`, re-run at 10:26:59–10:27:01 after task 23
moved the project into a column, is the run — quoted in the normalised form the check prints, with
the padding collapsed:

```
10:26:59 wobble-desk-criteria queued needs (1 pending)
10:27:00 wobble-desk-criteria queued done (1 pending)
10:27:01 wobble-desk-criteria play (beat) effect 199 — needs (+1 more in it)
10:27:01 wobble-desk-criteria resolved needs — you were there
10:27:01 wobble-desk-criteria still waiting done — answering one session does not finish the others in it
10:27:01 wobble-desk-criteria play (beat) effect 213 — done
```

The second line is a second session, not a second place to go. The last one is where a collapse
would be silent.

That last line is the whole argument for keeping an entry's sessions rather than merging them into
a row: a collapse makes no noise at this point, and **silence is indistinguishable from working**.
The `still waiting` line exists for the same reason from the other side — a count that does not
drop after you answered something reads as a bug unless it says why. `check_attention`'s task 20
section pins the core's half against a mutant that takes the whole project down with the session
you answered.

**Not every prompt is a person.** `UserPromptSubmit` also fires when a background task hands its
result back and the session starts a turn on its own, and those were resolving signals nobody had
seen — the queue emptying itself while its owner was away from the desk. `hooks.by_person` is what
tells them apart and `check_hooks` is what checks it, against **real payloads and not written
ones**: an injected turn and a typed one carry exactly the same eight keys, so there is no flag to
read and the text is all there is. An injected turn opens with a lone wrapper tag on its own line.

It is a heuristic and it is fallible, so the direction it fails in is the thing that was chosen. A
prompt that merely *looks* injected leaves the signal pending and still speaking — loud, and
principle 7's half of the trade. The one known false positive is a typed message whose very first
line is nothing but a tag, `<hello>`; it is in `check_hooks` as a row, named as the accepted cost
rather than left to be discovered. The daemon counts and names every turn it refuses, so a signal
that will not go away has a line saying why.

### 6 — B and then nothing

Both endings, because the promise has two.

- It comes back: `snooze  wobble came back after 3s` (`check_daemon`, 19:23:40), into the place it
  had, beating again straight after.
- It does not, when that session signalled again meanwhile: `snooze  wobble let go after 4s — it
  had signalled again, so the newer one stands` (`check_criteria`, 19:25:55), with the newer signal
  left speaking.

The ~5 min lives in `config/signals.json` and every check overrides it; the time-to-press that
should have produced that number has still never been measured.

### 7 — B while attending

`check_criteria`, 20:26:31–20:26:35: the first press takes the `needs`, the second moves to the
`done` — and between them `let go  wobble — back in the queue, where it was`. The count does **not**
drop for the skipped one (`attending done · other-repo (1 left)`), because it really is still
waiting, and once the `done` is answered the `needs` starts beating again.

**Finishing something is closing its session**, settled at the desk on 2026-09-22. No press of B
ever ends a signal: B chooses what you are dealing with, and a prompt is what says you dealt with
it. So a second press on a lone signal hands it straight back rather than making it go away —
`check_attention` pins that case on its own, because it is the one that looks like a broken button
and is not.

This was the one defect the pass found in the core's behaviour rather than in a mirror. See Part D.

### 8 — no ball

Every `check_criteria` run is `--no-ball` and every one of them beats. The Mac's sound is not
assumed: `check_macos_seam` reads the title back off the real `NSStatusButton` and fires the click
through `performClick_` rather than by calling the Python handler — a misspelled selector passes a
direct call and never fires in the actual menu bar.

"No ball" was **words, not a shade of grey** (`○ · no ball`) until task 63, below, and the mutant that renders a title
which never says it is caught. Live at 19:23:32 with no ball awake: `ball  scanning; its voice will
be pikachu.wav. Press the ball's top button so it advertises.`

**And it is the ball's own voice.** Heard at the desk on 2026-09-23, 10:15:05, with the link
switched off a moment earlier (`ball off  disconnected on purpose — the Mac takes the sounds back
over`): a `done` came out as the cry, not as a chime. That is what task 24 is for, and the log
cannot show it — it records `play (beat) effect 213` and nothing about which file the Mac opened,
so this row only ever closes by ear. Fired into `var/events` under a **made-up project name**,
because a signal whose own window is in front stays quiet on purpose: aimed at the real folder it
would have been swallowed by the rule in step 3, and the silence would have read as a broken sound.

The title carries four states now, and `check_menubar` has a mutant per confusion:

| Title | Means |
|---|---|
| `○` / `● 2` | nothing waiting / two waiting, and no ball in this run at all |
| `● 2 · no ball` | two waiting, and the Mac is playing them because no ball answered |
| `○ · ball off` | you switched the link off; nothing is wrong |
| `● 2 · 87%` | two waiting, the ball has them, and it has 87% left |

Two of those mutants are new and both are collapses rather than errors: one renders `no ball` for a
link that was switched off, and one drops the percentage. Neither looks broken — they look like a
tidier title — which is why they are mutants and not a comment. The percentage **replaces** the
word "ball" rather than joining it, so a connected ball says both things in four characters; a ball
connected but not yet read shows no percentage rather than a `0%`.

**Since task 63 that table is the fallback**, for when the seam cannot draw the ball. With it
drawn, the title is the count alone and the drawing says the rest: a connected ball is red on
top down to the battery left and filled below, so it is never hollow even at 0%; one being
looked for is hollow; a link switched off, or a `--no-ball` run, is the whole ball faded. The
words are one click away, greyed above the line that changes the link — *Battery 87%*, *No
ball — looking for one*, *Ball off* — as principle 7, amended 2026-09-30, allows. Read as
pixels by `check_menu_light` and as rows by `check_menubar`, each with its mutants.

### 9 — the ball disconnects

A link now ends two ways, and the evidence is lopsided between them.

**The link going away by itself was never staged, and happened anyway.** The log has it seven
times — 2026-09-23 at 16:56:01, 18:59:57, 19:11:36 and 22:09:32; 2026-09-28 at 16:48:06,
22:08:16 and 22:25:47 — each one `THE BALL DISCONNECTED — link lost after N frame(s)`, then
`link closing`, then `ball disconnected` in the same second, so CoreBluetooth's own drop reaches
the loop (`src/mirrors/ball.py:225`) and the loop says so. That is Part B step 6 answered by
ordinary use. What none of the seven shows is task 63's hollow ball, since all of them came
before it; the next real drop is the one to look at the menu bar for.

**Switching it off from the menu is checked, because it is a decision and not a radio event.**
`check_ball_mirror` drives `set_wanted` both ways: off says so once, drops the session it is
holding, and a second off is not a second event; on asks for the link back and cuts short the retry
it was sitting in. The mutant is the one that looks right from the outside — it sets the flag, the
menu bar reads "ball off", and the ball goes on holding the link and ringing for everything.

The two are deliberately **different sentences**, `ball off` against `no ball`, and since task 63
different drawings, faded against hollow, because they ask
opposite things of whoever reads them: one is "press the ball's top button" and the other is "you
did this". Part B step 11 is the half an eye has to settle.

### 10 — Accessibility refused

Two refusals are real and one is faked, and the document says which.

- **Real:** the framework missing altogether. `check_focus` blocks `ApplicationServices` through
  `sys.meta_path`, so the `ImportError` comes from Python's own import machinery.
- **Real, and unplanned:** a locked screen. macOS answers every window title as its own app's name
  while locked, so looking would report that nothing matched — true, useless, and about the wrong
  thing. This was seen live over and over this evening (`NOT FOCUSED  the screen is locked…`) and
  is the reason that refusal exists at all.
- **Faked:** `AXIsProcessTrusted` answering `False`. macOS will not revoke a permission on request,
  so a whole stand-in framework says `False` instead. That proves our branch and nothing about what
  macOS says when the box is unticked.

**Part B step 8 is the half that cannot be faked, and it is manual.** It is written here rather
than quietly counted as covered.

**Seen 2026-09-30, unplanned.** Task 62's new icon moved wobble.app's cdhash, so its grant was
attached to bytes that no longer ran, while System Settings still showed the toggle on. From
20:08:32 to 21:10:59 every B said `NOT FOCUSED  macOS has not granted Accessibility…` in words
(42 times) and the beats went on playing (43 in the same window). `build_app.py --install
--reset-grants` and the toggle brought it back; from 21:11:05 every B came forward.

---

## Part D — what failed

Written down rather than tidied away. Every one of these was a green-looking system.

1. **The ball played the cry in the dark.** Task 13 went to the desk with a perfect audio slot and
   no LED resource ever uploaded. The cry was heard; the ball never lit; the daemon printed
   `play (pulse)` on schedule into literally nothing. Colour is a separate resource, and it must go
   **before** the effect — an LED resource cannot be read back, so a colour written after its
   effect dresses the *next* beat. On a config where every kind shares one colour that mistake is
   invisible, which is why it is a mutant now and not a comment. Fixed, and the ball was watched
   flashing on 2026-09-23 (Part C.3).

2. **The cry and its own silent flash fired in the same breath.** The pulse had no `last`, and "no
   last" means "due now" — so the flash the cry had already produced was produced again. Every
   piece was correct on its own; the join was wrong, and only the end-to-end check could see it.
   Fixed: the pulse starts one interval after the final beat.

3. **A locked screen reported a false absence.** Found by this pass. Focusing said "no window has
   'wobble' in its title" while a wobble window was open — accurate about what it could read and
   untrue about the world. Fixed: the lock is detected and named, and the sweep does not go looking
   at titles it cannot read.

4. **B while attending dropped a signal with no line anywhere.** Found by this pass. Pressing B
   again skips to the next (criterion 7) and the one you were on was gone — out of the queue, not
   restored by the snooze, and mentioned by nothing. That is the silence principle 7 forbids.
   Nine desk checks were green and none could see it: every one of them asks "did the right thing
   happen", and this was a thing that *stopped* happening. Fixed twice over — the daemon says what
   it stepped away from, and the core puts it back where it was. `check_attention` now runs against
   a mutant that drops it, so the old behaviour cannot come back quietly.

5. **A beat was eaten before it reached the wire.** `asyncio.Event.clear()` ran before the wait
   instead of after, so anything set while the previous beat was still going was thrown away — and
   a beat is not instant, since a send retries three times at five seconds apiece. The symptom is
   the worst kind: the daemon logs `play (beat)`, the ball does nothing, and nothing says a beat
   was lost. Found by re-reading the worker; the fake-link table passes either way, because nothing
   in it is slow enough to overlap.

6. **The probe said activation was broken, and the probe was the broken thing.** Three ways of
   activating a window in a row all appeared to fail, because `NSWorkspace.frontmostApplication()`
   refreshes off notifications and a script with no run loop never spins one — so it answers with
   whatever it knew at launch, forever. All three were working. The near-miss is the lesson: a
   blind probe produces exactly the failure a wrong theory predicts.

7. **The right creature, the wrong recording.** The cry was PokeAPI's game audio. The ball's own
   file had already been captured, lifted out of a sniffer capture — 8282 bytes, 17 frames,
   and it is the one that says *"Pika-chu"* aloud.

8. **A check that pinned column padding.** Three rows matched a guessed spacing and reported zero
   against a transcript full of beats. Transcript lines are normalised before matching now.

9. **Two daemons on one events file say nothing about each other.** Task 12's by-hand check was
   read against the transcript of an older process still tailing the same file. Both answered every
   event and nothing anywhere said there were two. Fixed by task 50, which needed it for the app:
   the second daemon on one events file says `ALREADY RUNNING` and stops (`check_app.py`).

10. **The pulse was correct, scheduled, logged — and nobody ever saw it.** Every check was green
    and the ball was dark. The pulse was written as what begins once the beats are used up, so with
    one cry and a 30 s interval the first flash landed 30 s *after* the last thing that made a
    noise — and the camera measured **60.1 s**, because the only pulse inside that stretch was the
    one spent uploading the mute and skipped. Nine known-answer tables agreed with the code because
    they were asking the arithmetic what the arithmetic thought; not one of them ran for a minute.
    Fixed: beats and pulse run together, `done` beats twice, the flash never stops. `check_rhythm`
    exists because of this and spends 70 s on purpose.

11. **The queue emptied itself while nobody was at the desk.** A `UserPromptSubmit` fires when a
    background task hands its result back and the session starts a turn on its own — so the agent
    was answering its own notifications, and criterion 5 read that as "you were there". Nothing
    looked wrong: the signal resolved, the line said `you were there`, and it was untrue. The two
    payloads were **compared rather than reasoned about**, and they carry exactly the same eight
    keys — there is no flag, so the text is all there is. Fixed as a named heuristic that fails
    loudly (`hooks.by_person`), with the one false positive written down as a row rather than left
    to be found.

12. **Every desk check wrote into the file the real daemon was tailing.** `check_daemon` and
    `check_criteria` both began by unlinking `var/events` and then fired signals through the real
    hook script — so a daemon holding a ball counted a restart it never mentioned and played every
    phantom `done` the check invented, in somebody's pocket, while they were away. Nothing failed,
    which is why it survived nine passes: `hooks.Tail` opens by path and handles the file shrinking,
    so the collision is invisible from both sides. This is item 9 one layer down, and it is the half
    that could be fixed today. Fixed: `sandbox.py` gives each run a repo-shaped temp tree, and each
    run *proves* its isolation by firing one event and checking `var/events` did not grow.

13. **The fix for item 10 introduced a stutter, and only an ear found it.** Blinking every 3 s put
    an upload on top of a cry that was still sounding: the cry comes out fast and chokes, heard at
    the desk and visible in nothing else. Every table was green — including `check_rhythm`, which
    measures *when* things are due and cannot hear what an upload does to a sound already playing.
    The one audio slot is the whole cause: a silent flash is a mute uploaded over the cry, so the
    interval between flashes and the length of the cry were never independent numbers and had been
    treated as if they were. Fixed with `pulse.after_beat_s` — a quiet the cry keeps to itself —
    and, because a constant would rot the moment `--cry` pointed somewhere else, the daemon reads
    the configured `.wav` and uses the longer of the two.

14. **A click on the menu bar ended a run that nine rows then described.** Twice in one session:
    one stray press, then six inside five seconds. A desk-check daemon puts a real item in the real
    menu bar and a click on it is a real B press, so the signal was attended and the beats stopped —
    and the rows reported a schedule that had been ended by a finger. **The cause was never
    established**, only the door closed: `--no-menubar` means there is no item to click, and a
    first row counts B presses so the check accuses the interference by name. The lesson is the one
    that generalises: a check that shares a surface with the person running it is measuring them
    too, and the honest fix is to remove the surface rather than to explain the number.

15. **A locked Mac calls every window by its app's name, and that is the one hour the silence
    matters.** Caught before it shipped, and only by going and looking. "Stay quiet while I am
    looking at the session" reads the title of the window in front; with the screen locked, the
    window server still reports a layer-0 window, and the accessibility read of its title comes
    back as `'Code'` — the *application's* name, not the window's. Pulled off this desk on
    2026-09-22 rather than reasoned about. So a project in a folder called `Code`, or `Finder`, or
    `Terminal`, would have read as the window you are looking at for exactly as long as nobody was
    at the desk, which is precisely when a notification is for. It would have failed silently and
    looked like a quiet afternoon. Fixed: the seam refuses a title read while locked and answers
    "nothing in front", which signals. The lock check is a mutant now (`IgnoresTheLock`), and
    `check_watching.py` proves it against the *real* framework whenever it happens to run on a
    locked desk, because a fake cannot testify about this one.

    The same shape is why the front window is read off the window server rather than off
    `NSWorkspace.frontmostApplication()`: item 6 measured that one answering with whatever it knew
    at launch in a process with no run loop, and the daemon has no run loop under `--no-menubar`.
    The obvious call would have been stale forever, which is the identical failure — a correct
    answer to a question nobody is asking any more.
16. **Three checks quietly became a question about which window you last clicked.** Found
    2026-09-23, the first time the whole suite was run with the screen unlocked. Every fixture in
    `check_daemon`, `check_criteria` and `check_rhythm` fires signals for the project `wobble`,
    because that is the repo — and the moment the quiet-while-watched rule landed, every one of
    those signals went silent whenever this repo's own window was in front. `check_rhythm` reported
    `NOTHING PLAYED AT ALL`; `check_daemon` lost its cadence row. **Both were the daemon working.**

    Worse than the failures was what came before them: `check_daemon` passed on the first run and
    failed on the second, because the run itself brings the `wobble` window forward on the B press.
    A suite that passes or fails on the order you run it in is not measuring what it says it is,
    and there is no row anywhere that would have said so. It only surfaced because the screen was
    locked for both of the previous days' runs, which had been hiding it in the other direction.

    Fixed two ways, deliberately not one. `check_rhythm` and `check_criteria` never needed the real
    project name — nothing in them expects a window to come forward — so they name a project no
    window can be titled after, and a longer hint cannot be a substring of a shorter title. Only
    `check_daemon` genuinely needs `wobble`, because raising that window *is* criterion 4, so it
    reads the desk before it starts, refuses with the reason and the fix, and says on the way out
    that it has left that window in front. The rule it asks with is `Entry.in_window` — the
    daemon's own, not a substring match written in the check, which could have disagreed with the
    thing it was guarding.

17. **Another app's window counted as looking at the session.** Found 2026-09-28 (task 38). A
    Terminal titled `wobble — -zsh` kept wobble's VS Code done quiet, and B raised that Terminal
    instead of the VS Code window running the session. The rule only matched the folder name
    anywhere in any title. The hook now records the app the session runs in, and the check refuses
    a front window of any other app. Then the check itself fell into the same gap: the sandbox's
    hook inherited the app that launched the check (VS Code), so `check_watching`'s live leg
    passed only with VS Code in front, and failed the one time WhatsApp was. The sandbox now
    carries a host only when told.

18. **Claude Code's idle reminder was cried as a question.** Found 2026-09-28 (task 39), the first
    time sessions ran in terminals: *"none of them sent a question"*. `Notification` also fires 60 s
    after a done in a session left alone (`idle_prompt`). No VS Code session had ever sent one,
    which is why five days of desk runs never saw it.

---

## Part E — not covered, and open

**Not covered by anything:**

- ~~**The Accessibility fallback doing the work** (task 38)~~ — **seen 2026-09-28, 21:25:33.**
  B selected a Terminal.app tab and the log says it `came forward via Accessibility` (task 42's
  desk run), so the fallback has now done the work at the desk and not only in check_focus.
- **VS Code's first tab link asks** (task 43), seen 2026-09-28 at 22:25:07. The first time B
  opens `vscode://anthropic.claude-code/open?…`, VS Code asks *"Allow 'Claude Code for VS Code'
  extension to open this URI?"*. While it waits, the log still says `Code opened … and came
  forward`, with the twin's title in front: that title, not the word `opened`, is the tell. Tick
  "Do not ask me again for this extension" once.
- **Terminal's windows told apart** (task 40). The Claude desktop app was measured 2026-09-28
  (task 40's entry): its window is `Claude` for every session, so its sessions are never watched,
  and B opens the session itself by its `claude://` link (task 42).
- ~~Criterion 9, the disconnect (Part B step 6)~~ — **answered from the log, 2026-09-30.** Seven
  natural drops, Part C.9. The hollow drawing after one is still to be seen.
- ~~The LED flashing on real hardware (Part B step 1)~~ — **answered 2026-09-23.** The silent
  pulses were watched on the ball across a whole `done`, so effect `213` does light it. What was
  not called out separately is the beat's own flash; the animation belongs to the effect and not to
  the resource behind it (task 16), so that half is an inference, not a second sighting.
- ~~**The new rhythm on real hardware** (Part B step 2)~~ — **answered 2026-09-23**, Part C.3. The
  film that measured the flash was of the *old* rhythm, because the daemon in front of the camera
  had been started before the change. A daemon started after it has now blinked every three seconds
  in front of an eye, cried twice thirty seconds apart, and not choked on the second cry. What is
  still not measured is the size of the margin around that second cry: a log stamped to the second
  cannot weigh a gap of one and a half. **Parked on purpose, 2026-09-23** — the gap behaves at this
  desk with this cry, and the number is only worth producing when there is a second voice to break
  it: `after_beat_s` is a floor that the daemon raises to the length of whatever `--cry` points at,
  so an Eevee cry, or any longer `.wav`, is the event that reopens this.
- ~~**A turn the agent started itself, seen end to end** (Part B step 9)~~ — **answered from the
  log, 2026-09-30.** 144 `injected turn` lines across the logs. One in flight: wobble 4f6f's `done`
  queued at 19:44:51, an injected turn at 19:47:22 resolved nothing, and the `done` was still there
  for B at 19:51:21.
- ~~**What opening the menu costs the BLE link** (Part B step 13)~~ — **answered as an inference,
  2026-09-30.** The menu was opened by hand all day; of the 11 `link closing` lines after 15:21,
  the one at 15:22:57 lost 2 of 99 frames and the 10 after it lost none and retried none. No line
  marks the menu opening, so the two are not tied beat by beat.
  What was written before: `popUpMenuPositioningItem_`
  runs a modal tracking loop, so the daemon's poll is blocked for as long as the menu is open. The
  link is held by CoreBluetooth outside this process, so a second or two ought to cost nothing —
  and "ought to" is the whole of the evidence. This is the one thing the new surface could
  plausibly break and it is the one thing nobody has watched.
- ~~**Both gestures, since the swap** (Part B step 10)~~ — **answered 2026-09-30**: confirmed at
  the desk that the right click is B and the left click opens the menu. What was written before: One screenshot from 2026-09-22 proves the
  seam tells a right click from a left one on real hardware. Task 21 then exchanged what the two
  branches do, and neither has been pressed on hardware since — so what is open is not the
  mechanism but which way round it is wired, which is the one thing a mutant cannot settle either:
  a check can only ask the seam what it thinks it routed, and here the question is what the mouse
  actually sent. The pending list has the same gap, one step further on: the real NSMenu was built
  and clicked in a smoke run, but in process, never by a hand.
- ~~**What the menu costs while it is open, now that it is the left click** (Part B step 10)~~ —
  the same inference as step 13 above. What was written before: The
  entry below this was written when opening the menu was deliberate and rare. It is now the
  ordinary gesture, so the modal tracking loop it runs — and the daemon tick it stops — is entered
  far more often than the evidence behind it assumed.
- ~~**Switching it off on purpose, on a ball** (Part B step 11)~~ — **answered 2026-09-30.** The log
  has 52 `ball off — disconnected on purpose`, 2026-09-28 to 09-30, each with `180` before the
  link was let go, and the reconnect skipping the retry sleep was seen on 09-29 (step 7 below).
  What was written before: Both directions are checked against
  tables and against a mutant; `ball off` has not been read off a real menu bar, and neither has
  the reconnect that is supposed to skip the retry sleep.
- **The battery against a second source** (Part B step 12). **Measured 2026-09-30, no code
  change:** the Switch shows no percentage, only a bar, which was read at the desk as ~67–70% while
  we read 47%. Across a week the `2A19` byte has only ever said 100, 75, 47 or 21, and it dips for
  seconds (21% at 21:04:00, 47% at 21:04:20), so it is a four-step gauge and not a percentage.
  Showing it as four levels is parked for now. What was written before: A value is in hand — `100%` — and it is
  the single most likely reading for a `2A19` that is *not* what it is assumed to be, so it
  confirms the plumbing and nothing about the number. One field, one reading, no agreement from
  anywhere else.
- ~~Whether the quiet-while-watched rule ever fires at this desk~~ — **answered 2026-09-23.**
  `check_watching.py`'s last part ran, unlocked, against `'Install_hooks.py — wobble'`: the leg it
  was looking at went quiet and said so, the reference leg beat normally, and the entry stayed
  pending rather than resolved. The rule is now proved reachable as well as correct.

  **And the half a script cannot ask was answered the same day, by ordinary use rather than by a
  check** (Part B step 14). A `done` arrived in `wobble` at 13:03:03 with its own window in front,
  and the log has four lines and nothing between them:

  ```
  13:03:03 wobble queued        done (1 pending)
  13:03:03 wobble not signalling done — you are looking at its window, so it stays pending and quiet
  13:07:45 wobble signalling    done — you looked away
  13:07:45 wobble play (beat)   effect 213 — done
  ```

  Four minutes and forty-two seconds watched, and the cry in the **same second** as the look-away.
  That is the clock being stopped rather than spent, and it is the only reading the numbers allow:
  a `done` has two beats 30 s apart, so a clock left running would have spent both inside those 282
  seconds and the ball would have had nothing left to say when the eye moved. Ten seconds later the
  other half is in the same transcript — `not signalling` at 13:07:52, `signalling` at 13:07:55,
  and what follows is a **pulse** and not a second cry: a glance away and back does not buy a beat,
  because the beats already had are remembered.

  Not every look-away in that log proves it, and the distinction is worth keeping. The one at
  13:14:33 looks identical and proves less: B had attended and let go of that entry seconds
  earlier, which resets the signaller's key and makes the next beat due at once for a reason that
  has nothing to do with watching. Same two lines, same second, and no measurement in it. The
  13:03:03 run is the one to cite because nothing happened during it.

  It answered a second question nobody asked. Three other checks started failing the moment the
  window was in front, because their fixtures fire for project `wobble` and that is the window this
  repo is edited in. `check_rhythm` and `check_criteria` now name a project no window can be titled
  after; `check_daemon` genuinely needs the real name — it presses B to raise that window — so it
  reads the desk first and refuses rather than reporting a defect that is the feature working.
  **A check whose verdict depends on which window you last clicked is not a known-answer check**,
  and all three were, silently, from the moment task 17 landed.
- **Quit, end to end** (Part B step 15). Three layers are proved and the fourth cannot be: the
  menu offers it in every state and always under a separator (`check_menubar`, against three
  mutants), AppKit really builds that separator and really dispatches the last line to the quit
  handler (`check_macos_seam`, read back out of a real `NSMenu`), and the daemon's teardown is
  ordinary code. What no script here can do is *choose* it — a status-item menu is opened by a
  hand, and nothing in this project drives the mouse. So the run that matters has never happened:
  whether the item disappears, whether the ball is let go inside the two-second grace or the
  transcript says `BALL NOT LET GO`, and whether what was pending comes back on the next run.
  **Chosen by hand on 2026-09-29 at 11:10:19, with the ball connected:** `180` went out, the
  ball was let go in 0.1 s, `stopped`, and `ps` found no daemon at 11:10:34. The one quit that
  stayed alive (2026-09-28 15:29:04, pid 7915) was in state `T`, stopped by job control, and
  not hung. It did not happen again. What was pending coming back on the next run was owed
  (this quit had 0), and it was not coming back at all: the daemon started at the end of the file.
  Task 47 fixed that, and at the desk at 13:16:41 the same day a restart brought 7 back quietly and
  dropped 10 whose claude was gone (task 47's entry in `specs/01-mvp/tasks.md`).
- ~~Several pending and then the ball connects (Part B step 7)~~ — **answered 2026-09-29.**
  The ball was switched off from the menu at 13:27:15. With it off, project-a de78's `done` and
  toolkit 554a's `needs` were both live, and the Mac played them. It was switched back on
  at 13:37:27 and connected at 13:37:30. It sent `180` and loaded the cry, then carried on with
  554a's `199` every ~1.5 s: the current signal and nothing else. No `129` and no `9` for de78.
  One beat that fell due while the cry was loading was dropped, not queued (`beat late … 1 beat(s)
  behind it were overwritten and never felt`), so no burst either. Confirmed by hand at the desk
  that the ball was on the needs. What is not covered is the ball *waking* by itself rather than being
  switched on: both end in the same connect, and that is an inference.
- ~~macOS actually answering `False` for Accessibility (Part B step 8)~~ — **seen 2026-09-30,
  20:08–21:11, against wobble.app's own grant** (Part C.10). What was written before:
  **Deferred on purpose, 2026-09-29, until wobble is an app** (ROADMAP, "wobble as an app").
  Task 50 built the app; the step is runnable once it is installed (Part B step 20).
  Today the grant belongs to whatever launched the daemon, which at this desk is VS Code's
  terminal. So the step can only be run by taking Accessibility away from VS Code as a whole, and
  it would have to be run again once the grant is wobble's own. Until then criterion 10 rests on
  `check_focus` and its mutants. Also worth knowing when it is run: since task 42, B opens a
  session by its link as well, which needs no Accessibility, so a window may still come forward
  with the grant refused.
- ~~**Does the link survive hours in a pocket?**~~ — **answered by use, 2026-09-30**: it has held,
  day to day. Not measured as retries over time. What was written before: `docs/PROTOCOL.md` §9
  measured retries getting roughly four times more frequent past ~12 minutes on one link. This spec calls it a desk check and it has
  not been run. A session was at 44 minutes when this document was written, which is a start and
  not a measurement.

**Open, not reproduced:**

- **Two raises at once.** B pressed twice fast, 2026-09-30 at 21:11:12 and 21:11:14, opened a
  second Claude tab in VS Code: each press runs `reach` in its own thread, and the `vscode://`
  link of one can land in a window the other brought forward. Retested at the desk and could not
  make it happen again, so serializing the raises is parked.

**Numbers that are judgements, not measurements** — all three are labelled as such in
`config/signals.json`, and all three want a desk check:

- the 30 s between a `done`'s two cries, and the 2 cries — a second sooner reads as nagging, a
  third for something already finished is noise, and neither sentence is a measurement;
- the 3 s between silent flashes. This one now has a measurement *beside* it rather than behind
  it: the flash is 1.47–1.50 s, so at 3 s the ball is lit about half the time. Whether that reads
  as waiting or as an alarm is still a judgement, and it is the number to turn first;
- the ~5 min snooze, which should come from a time-to-press nobody has produced;
- the 5 s a prompt buys (task 25). Asked for as a feeling — "not at the same moment" — and chosen to
  match the cry's own quiet rather than measured against anything. It is the number to turn if the
  ball starts reading as slow, and Part B step 16 is the check that would say so;
- the Mac's sound for a `needs` and for a catch (task 70). Task 24 gave `done` the cry itself, so
  there is nothing to judge there. A `needs` and a catch have no file the ball would have used:
  199 and 201 are firmware effects, and their audio is in no capture. Since 2026-10-02 the Mac
  plays wobble's own, `sounds/needs.wav` (0.450 s) and `sounds/caught.wav` (0.220 s), drawn in
  code from two measurements of the game's wobble and click (`sounds/README.md`). That they
  *read* as the game's is a judgement made by ear, and the ball's own recording, still never
  made, is what would settle it. Before them were Tink (0.564 s, a stand-in from the start) and
  Sosumi, whose note claimed it was short enough for a 1.5 s beat when `afinfo` said 1.539 s.
  Every clause of that note was false, and it read as a measurement for a day.

**The one open decision is closed.** When B is pressed while already attending, the signal you were
on goes back into the queue, into the place it had — the same thing the snooze does with a
dismissed one. Settled 2026-09-22: finishing something is closing its session, so B never ends a
signal, it only chooses what you are dealing with. `spec.md` criterion 7 carries the change.
