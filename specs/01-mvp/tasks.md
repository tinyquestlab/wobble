# S01 — Tasks

One commit each. Desk-check tasks commit their answers into `learnings.md`.

- [x] **01 — Skeleton.** `requirements.txt` (`bleak`), venv instructions, the package layout from
      `plan.md`, and `src/platform_seam/` with `ports.py` (Protocols) + `null.py`. Nothing else.
      Proves the shape before anything fills it.

- [x] **02 — The ball's protocol layer.** Ported from an earlier project, judged: scan by name
      (`Pokemon PBP`), connect, the opening sequence, `<opcode:u8><len:u16 LE><payload>` framing,
      ack on `...e8`, and the three-try retry that **logs every retry**. A retry that hides the
      loss rate turns a measurable defect into folklore.

- [x] **03 — Play an effect from the CLI.** `python -m src.ball.effect <id>`, printing the ack and
      exiting non-zero when a write went unacked. First proof against real hardware, and the tool
      every desk check below uses.

- [x] **04 — Desk check: the LED.** Does a palette index alone light the ball, or does it need an
      effect played after it? And which index reads as dark? Write both answers down before doing
      anything with them — plan.md open questions 1 and 2.

- [x] **05 — Desk check: the rumble, through a pocket.** Capture waves (`198`/`199`/`200`) against
      `241`, ball in a pocket, not in the hand. Also settle whether the by-ear catalogue or the
      accelerometer is right that 199 and 200 are the same as 198 — plan.md questions 3 and 4.

- [x] **06 — Pikachu's voice in the slot.** Upload the cry over the `0x08` chunked transfer, on
      connect and on voice change, never on an event. `213` then plays it. *Uploader, framing
      check and CLI done and proved at the desk; "on connect" is the daemon's and lands with the
      ball mirror (task 13).*

- [x] **07 — Input, and B as an edge.** Decode the 17-byte packet. B counts on 0→1, requires the
      release before the next press, and assumes release when packets stop arriving. *Corrected at
      the desk 2026-09-22: this said B is `0x02`, the stick click. Watching both bits while the
      person pressed only B, every press came back on `0x01`.*

- [x] **08 — The core: signals and the queue.** Event kinds (`done`, `needs`), one entry per
      session with its project and window hint, `needs` always on top, age within a kind. No BLE,
      no AppKit, no osascript anywhere in it.

- [x] **09 — Attention.** Dismissing marks a session attending and freezes the queue silently;
      that session's next prompt resolves it; a ~5 min snooze brings it back otherwise. Dismissing
      while attending skips to the next. A prompt in any session drops that session's own pending
      entry. *Changed 2026-09-22: this said a ~10 min safety net "releases it anyway" — moving on
      is how the dismissed one gets lost. See spec criteria 5 and 6.*

- [x] **10 — The repeat ladder.** `config/signals.json` drives sound, beats, LED index and the
      ladder (now, +2 min, +5 min, stop). The LED keeps pulsing silently while anything is
      pending, which needs a mute resource in the slot — so this depends on task 06, and
      not only the cry does.

- [x] **11 — Claude Code hooks.** An installer that wires the hooks, an append-only `var/events`,
      and the daemon that tails it. It must say, in words, when the hooks are not installed.

- [x] **12 — The menu bar mirror.** Dot plus pending count, a distinct "no ball" state, click as
      the B button, and the Mac's own sound when there is no ball. It may render only what the
      core gave it.

- [x] **13 — The ball mirror.** Signals out, B in, wired to the same core. Connect, disconnect and
      reconnect all say so where the person can see them. *Proved against the ball 2026-09-22:
      connect, the cry in 1.5 s, `done` firing with no upload on its path, the mute swap costing
      one flash and not the beat, B dismissing from the ball. One half was missed and found the
      same evening — the colour is a second resource and nothing had ever uploaded one, so the
      cry played into a dark ball. Fixed and verified byte-for-byte against the sniffer capture;
      the ball itself has not lit yet, because confirming it needs the restart the
      running daemon was deliberately not given.*

- [x] **14 — Focus the window.** Behind the seam: activate the app, raise the window whose title
      carries the project. When Accessibility is refused, skip it and say so in words — the
      notification still works. The refusal path gets exercised on purpose, not assumed.
      *Both halves are needed and both are checked: `kAXRaiseAction` puts the window in front of
      its own app's, activating puts that app in front of everything else. Doing one is the
      failure that looks like success. Measured: the sweep is under 50 ms warm, the raise about a
      second, so it runs off the loop's thread rather than stalling the beat.*

- [x] **15 — The desk-check pass.** `docs/DESK-CHECKS.md` covering every acceptance criterion in
      `spec.md`, run end to end, with what failed written down rather than tidied away.
      *Nine scripts, all green, all their mutants caught; criteria 1–8 and 10 answered, 9 has no
      evidence behind it and says so. Two defects found by the pass itself and fixed: a locked
      screen reported a false absence, and B while attending dropped a signal with no line
      anywhere. Part B is the hand-and-ball half — eight steps, of which four are still
      outstanding because they need the ball and the running daemon was deliberately not
      restarted.*

- [x] **16 — The rhythm a person can see, and the prompt nobody typed.** Two defects found by
      using the thing rather than by checking it. A `done` cried and then went dark, because the
      pulse was written as what starts once the beats run out; and `UserPromptSubmit` fires for a
      turn the agent starts itself, so the queue was quietly answering its own notifications.
      *The rhythm is now the cry, a blink every 3 s, the cry once more at 30 s, and blinking until
      somebody comes — beats and pulse running together, proved by `check_rhythm.py`, which spends
      70 s because that is the only way to see a shape. Filmed on the camera: the old dark stretch
      measured 60.1 s, and the flash itself is 1.47-1.50 s whichever resource is in the slot, so
      3 s leaves the ball lit about half the time. `hooks.by_person` tells a typed turn from an
      injected one — checked against real captured payloads, because the two carry identical keys
      and a fixture written by hand would have shared the assumption under test. It is a heuristic
      and it fails towards leaving the signal speaking. Found on the way: every desk check had been
      writing into the live daemon's events file. Neither fix is on the ball yet — the daemon
      holding the link predates them and was deliberately not restarted.*

- [x] **17 — Quiet while you are looking at it.** Asked for while using it: if the session that
      raised a signal is the window in front of you, there is nothing to tell you, so tell you
      nothing. The seam reads the title of the front window, the core decides whether that is this
      session's (`Entry.in_window`), and the signaller plays nothing while it is.
      *The part that is not obvious is the clock: quiet is not resolved, so the entry stays
      pending, both mirrors keep the count, and the signaller's deadlines are moved forward by
      the time spent watched — a `done` watched as it arrived cries the second you look away
      rather than having spent its beats in silence. `check_watching.py` takes that timeline
      apart against the real ladder; ten mutants, three of them on the direction that matters
      (not knowing what is in front must never silence a signal). Found on the way, live rather
      than reasoned about: macOS answers every window title as its own app's name while the
      screen is locked, so without an explicit lock check a folder called `Code` would have read
      as the window in front for exactly as long as nobody was at the desk. `--notify-anyway`
      exists so a desk check that times a ladder cannot have its clock stopped by being watched.
      Proved in every layer and NOT yet proved to fire at this desk: the end-to-end leg needs the
      screen unlocked with a titled window in front, and the screen was locked both times.*
      *Ran green 2026-09-23 against `'Install_hooks.py — wobble'`, so it is now proved reachable
      too — and it took three other checks down with it on the way, which is task 18's entry.*

- [x] **18 — A way out of the menu.** Asked for in one line: a Quit button in the menu bar. The
      menu grows a separator and *Quit wobble*; choosing it stops the daemon the way you would put
      the ball down rather than the way you would drop it.
      *Principle 2 is the thing to argue with here and the answer is in `items`' docstring:
      stopping the process is not part of the notification vocabulary — not a signal, not a state,
      not the queue — and the ball cannot start the daemon either. The separator is load-bearing
      twice: the line above it switches the ball's link, and only one of the two neighbours is
      undone by choosing the other; and mechanically, a separator that did not take a slot in the
      seam's handler list would shift every handler below it onto the wrong line. The tag row in
      `check_macos_seam.py` is the only thing that pins that convention — measured against both
      halves of the edit, and the behavioural rows pass against one of them. Quitting says every
      step out loud (principle 7's one expected silence), waits up to 2 s for the ball to let go
      and goes anyway, and leaves what is pending in `var/events` for the next run. Proved in the
      mirror, in the seam against a real `NSMenu`, and NOT end to end: nothing here drives a mouse,
      so choosing it is Part B step 15 and needs a hand. Found on the way: three desk checks had
      silently become questions about which window you last clicked — see DESK-CHECKS Part D 16.*

- [x] **19 — What it did while you were out.** Asked for by name after `var/daemon.log` turned out
      to be nobody's: a stale leftover from a `>` redirect on 2026-09-22, because the daemon only
      ever printed to a terminal. One file per day, named after the day, the shape Laravel's
      `daily` channel has.
      *`say()` stays the one door and stdout is unchanged byte for byte, which is not politeness —
      five desk checks parse it, and the day the file and the screen disagree is the day neither is
      evidence. The stdlib's `TimedRotatingFileHandler` was not used: it rotates the other way
      round, leaving today's lines in a file whose name says nothing. The decision worth arguing
      with is where the log goes — it follows `--events` rather than being pinned at `var/logs`, so
      a desk check logs into its own throwaway tree. That is the same mistake as the one already
      paid for on the events file itself, seen coming this time. The sweep reads the date out of
      the NAME: by mtime, one restore from a backup takes the whole history, and `check_log.py`
      plants a fresh-mtime old file and an old-mtime fresh one to say so. Five mutants, all caught,
      and midnight is reachable because `Daily` takes its clock as an argument.*

- [x] **20 — One entry per project, holding every session in it.** Asked for after the bar read
      `● 2` with one terminal open. Both were real — a signal fired by hand for a desk check and
      the session doing the work, in the same folder — but the queue was keyed by session and the
      number is read as *places to go and look*. The same key made a closed tab immortal: the only
      thing that resolves an entry is that session's next prompt, and a tab you closed never writes
      again.
      *The tidy version of this is a collapse — one row per project, newest event wins — and it is
      the version that loses. A `done` sitting behind a `needs` in the same folder goes when you
      answer the `needs`, and nothing ever says that session had finished: the silence principle 7
      forbids, settled on the ask that if something would be lost, the approach changes. So the queue keeps a
      `Waiting` per session and `Entry` became a derived view over them — its kind is the most
      urgent thing in it rather than the newest, and answering the lead **falls back** to what is
      underneath instead of emptying the row. `len(queue)` is projects, the number that is
      rendered; `queue.sessions()` is sessions, the number nobody is shown, there so a check can
      prove nothing was thrown away. B takes the whole project, because attending is one trip to
      one window and a sibling left behind would put the count straight back up the moment you got
      there; a prompt takes one session and says what is left. Nothing here is new information —
      `Entry.in_window` had already conceded the point by matching on the folder name, so two
      sessions in one folder were always the same window as far as anything in this repo can tell.
      Four mutants hold it: counting sessions, collapsing to the newest, and ordering inside a
      project by arrival in `check_queue`, plus a prompt that finishes the whole project in
      `check_attention`. All four caught. Found on the way: on a frozen `slots=True` dataclass,
      assigning to a **derived property** dies in CPython's `super()` call with a `TypeError`
      rather than `FrozenInstanceError` — still refused, which is all a mirror needs to be told,
      and the row now accepts either.*

- [x] **24 — The Mac says what the ball says.** Asked for by name: "the done sound should be the
      same as the one that goes to the ball, the Pikachu cry (buddy, later on); the needs sound
      should be the same sound that comes with 198-199". With a ball you heard Pikachu; without one you heard Glass, a chime
      nobody chose for meaning — the two surfaces had quietly become two vocabularies, which is
      principle 1 read backwards.
      *`done.mac_sound` is now `"@cry"`, and that is the whole design: not a path, a token meaning
      "whatever voice the ball is using", resolved by `core.ladder.load(cry=...)` against the same
      `--cry` the ball's slot is filled from. A path would have worked today and been a second copy
      of one fact, free to disagree tomorrow with nothing to notice. Threaded into the pulse too,
      where `mac_sound` is null today: a pulse taking the default instead would have given one kind
      two voices, which is the bug this task exists to remove. `needs` is the half that cannot be
      finished here — 198/199/200 are **firmware** effects, not uploaded resources, so their audio
      is in no sniffer capture and the internet only has the game's wobble, recorded off different
      hardware. It is Tink for now, a stand-in labelled as such in the config, until the ball is
      recorded at the desk; deferred on the ask that it could not be done right now, too noisy to
      capture cleanly, and the task should not be blocked on it. Found on the way: the note beside the old `needs` sound claimed Sosumi
      was "short enough not to run into the next beat 1.5 s later, which Submarine and Hero are
      not" — `afinfo` says Sosumi 1.539 s, Submarine 1.492 s, Hero 1.056 s. Every clause false, and
      the one it named as safe was the only one overrunning the beat. The mutant for all of this is
      a `_mac_sound` that answers `"@cry"` from the shipped path and ignores the one it was handed;
      it breaks exactly the two rows that are about `--cry` and leaves the three that are not.*

- [x] **23 — The project gets a column, in the log and on screen.** It used to be glued to the end
      of whatever the line was saying — `queued done · wobble (1 pending)` — which reads fine for
      one line and badly for forty, because the one word you scan a log for was in a different
      place on every row.
      *`say()` takes the project and puts it between the stamp and the verb; `describe()` stopped
      appending it, so it is said once per line rather than twice. Two decisions worth writing
      down. The column is 22 wide and **nothing is truncated to fit**: the longest name that really
      shows up is a desk check's own (`wobble-desk-criteria`, 20), and two projects cut to the same
      15 characters would read as one — a longer name pushes the line right instead, which is
      visible and explains itself. And a line that is about the daemon rather than about a project
      — the banner, the hook wiring, an unreadable line — gets `·` rather than a word: "daemon"
      would read as a folder called daemon and grep like one. Seven desk checks parse this stdout
      and all seven were updated in the same change; `check_rhythm`'s regex was the interesting one,
      because it skipped the stamp with `\s+` and would have quietly started `rest` at the project
      instead of at the verb, turning every `startswith` into a test of nothing.*

- [x] **22 — An ended session stops waiting.** Until now the only thing that could take an entry
      out of the queue was that same session's next prompt — so a session whose output you read and
      whose tab you then closed left something nothing could ever resolve. It queued, it cried
      every thirty seconds, and it sat there until the snooze or a restart. `signals.py` has
      described this case in its own docstring since task 20 and `Queue.drop_session` has named
      this task number; what was missing was the hook.
      *`SessionEnd` joins `HOOK_FOR`, which is enough to wire it (`install_hooks.py` iterates that
      dict) and enough for `wiring()` to start reporting it missing — it did, loudly, the moment
      the word was added. The word is `end`, and like `prompt` it is deliberately absent from
      `KIND_OF`: neither is a thing being said, both act on the queue rather than joining it, so
      `as_event` hands back `None` and the daemon handles each on its own branch.*
      *`Attention.ended` is the new entry point and the decision inside it is that **it is not
      `prompted`**. A prompt says you were there and dealt with it, which is why it ends the hold
      on that project outright. A close says only that this one session stopped waiting, and says
      nothing about why — you may have finished, or typed `/clear`, or shut the laptop. So the hold
      survives one session leaving it, one session lighter, and the attention's own clock is not
      touched: restarting it would hand the snooze five more minutes free every time a tab closed.
      The hold ends only when the entry empties, because a freeze with nothing behind it keeps the
      whole queue quiet for a project that is no longer waiting for anything (principle 7). `Why`
      gained `END` to say which of the four endings it was.*
      *An end that took nothing out says nothing, and that is a decision rather than an omission:
      most sessions close long after whatever they signalled was dealt with, and a line per closed
      tab would bury the ends that matter. What it did take out is always said — a `done` nobody
      ever saw, gone because the window it belonged to went away, is exactly what belongs on the
      record. Three mutants, and the first is not a mutation but the code as it shipped: a close
      that changes nothing, a close that finishes the whole project, a close that ends the hold the
      way a prompt does.*

- [x] **21 — The queue in the menu, and the gesture that opens it.** The item had a dot and a
      count, which says how many are waiting and nothing at all about which. So the menu grew the
      list: one line per project in `queue.pending()`'s own order — `needs` before `done`, oldest
      first within a kind — with `, +N more` where a project has several sessions in it, and
      choosing a line attends THAT project instead of the top of the queue. Asked for after
      watching the bar say `● 3` and having no way to ask which three.
      *`Attention.attend(project)` is the new door and it is deliberately not a second B.
      `dismiss` and `attend` differ only in which entry they pick — the top, or the one you named
      — and both hand it to `_take`, which holds everything that makes attending what it is:
      dropping it from the queue, releasing whatever was held as a `SKIP`, restoring that to the
      queue, starting the clock. The daemon does the same on its side, where `attended()` is the
      block the press and the aimed line share. Two doors, one act, and a mutant
      (`AimedLosesWhatItHeld`) to keep them from drifting apart later.*
      *An aimed press at a project that is not waiting any more **changes nothing, and says so**.
      The menu is rebuilt four times a second, but an open menu is a snapshot, so a click can land
      after its project has gone. The tempting fallback — take the top instead — would raise a
      window nobody asked for, which is worse than doing nothing; principle 7 wants the refusal
      out loud, so it gets a line naming the project. `AimedTakesTheTop` is that mutant.*
      *`_aim` is a module-level function rather than a lambda built in the comprehension. Every row
      would otherwise close over the same variable and the whole list would attend whatever the
      last project was — the late-binding bug, which in a menu is indistinguishable from clicking
      the wrong line. Pinned by `every_line_attends_the_last`.*
      *Then the gestures swapped — **left click opens the menu, right click presses B** — asked for
      mid-task, against how task 12 built it, and right. Three reasons. The left click is what
      every other item on that strip answers with a menu, so an item that does something else on
      it is a trap rather than a shortcut. The list now goes everywhere the press goes and further,
      so the richer thing belongs on the commoner gesture. And a stray click on this item has
      already been a real B press that broke `check_daemon` mid-run (2026-09-22, in this file's
      learnings; `--no-menubar` exists because of it): an unwanted menu is dismissed with Escape,
      an unwanted press attends a signal and cannot be undone, so the recoverable one belongs on
      the gesture that happens by accident.
      `_Clicks.handler`/`secondary` became `press`/`open_menu` in the same change, because a field
      named after which gesture reaches it goes on describing the old arrangement while doing the
      new one.*
      *Five mutants, all caught, and one thing no mutant can reach: which gesture arrives is
      `NSApplication.currentEvent`, set by AppKit dispatching a real mouse. `check_macos_seam` can
      prove a plain click crosses the seam and opens the menu, that it is no longer B, and that B
      is the handler `on_click` was given waiting on the other branch — an NSEvent built in the
      check and handed to `clicked_` would only be the check agreeing with itself. The right-click
      leg is a hand on hardware, and it is written down as open.*

- [x] **25 — Five seconds between the hand that typed and the ball that answers.** Asked for at the
      desk 2026-09-23: "when I type a prompt and a cry follows right after, it is correct and
      working, but let's give it a 5s interval before the next one — not at the same moment?". The case
      is in that day's own log at 13:14:23–13:14:24 — a prompt typed in one project and a `done`
      from **another** crying a second later. Correct by every rule in the repo, and wrong in the
      room: the sound reads as a reply to the keystroke rather than as news from somewhere else.
      *Quiet-while-watching does not cover it and was never meant to. That rule is about the project
      whose window is in front; this one is about the hand. The two coincide often enough to look
      like one rule, and the log above is the case where they part — so `after_prompt.wait_s` is
      global: a prompt by a person holds whatever is at the top of the queue, whichever project it
      belongs to. 5.0 is a judgement and the config says so, in as many words — the same order as
      the cry's own quiet, long enough that the sound is plainly a second event and not an echo.*
      *It holds the **beat**, and the plan said the silent flash would carry on through it. That is
      true only of a signal that has already spoken: `next_pulse` with no last beat answers "now",
      so a `done` queued inside the window would have flashed before its own cry — the stutter of
      2026-09-22 (DESK-CHECKS Part D.2) coming back through a new door. A signal that has never
      beaten therefore stays dark for the whole hold, which the plan did not say and the code had to.
      Second correction of the same kind: a cry's quiet is now counted from when the beat **played**
      rather than from when it was due, because a beat held five seconds would otherwise arrive with
      its quiet already spent and hand the next flash a cry still sounding.*
      *It does not re-arm. The first keystroke of a burst starts the five seconds and the ones after
      it do not push them out — somebody typing steadily would otherwise never hear the ball at all,
      and an unbounded quiet is the silence principle 7 refuses. A bounded one still gets a line of
      its own (`holding … waits 5s before speaking`), said once per hold rather than once per poll,
      so the five seconds are never a ball that merely went quiet.*
      *What it cost the desk checks is the honest half of the story: three of them were asking their
      question from inside the new hold. `check_criteria` criterion 7 and task 20 each fired a prompt
      and then waited 2.5 s and 2.0 s for the signal underneath to come back — 8.0 now, with a new
      row apiece that weighs the gap instead of counting lines, because "it comes back" and "it does
      not come back into your hands" are two halves of one rule and only the first was written down.
      `check_daemon`'s tail went 10.0 → 16.0, and the arithmetic behind it is the product fact in
      one line: type, and a ball already waiting on you takes five seconds to speak and ten to start
      blinking. `check_ladder` pins the number, refuses a negative one, and accepts a config with no
      block at all as "no wait" rather than an error — and `_recast` had to learn to carry the field,
      or all four cadence mutants would have been "caught" by the new row instead of by the rule
      each exists to break.*
      *`check_watching` fails from inside a Claude Code session, and it is not this change: the
      window title moves mid-run, which the check's own guard names and calls "not a verdict about
      the daemon". Proved rather than assumed — the same two rows fail, for the same stated reason,
      against a tree with task 25 checked back out.*

- [x] **26 — The cry that came out as `pikkkkkkachu`.** Asked for at the desk 2026-09-23, in three
      words: "the Pikachu choking". Caught on tape the same afternoon — a recording filmed at the
      desk, 2026-09-23, carries the two spectrograms side by side. The broken one is *pika* as normal from 14:26:08.14
      to 14:26:08.34, and then flat horizontal bands around 4000–4600 Hz held for roughly half a
      second where the descending *chu* belongs. A sound that stops moving and holds one pitch is
      what the word describes.
      *The ball has one audio slot, and it is the same slot the sound comes out of.* Effect 213
      plays whatever was uploaded last, and an upload writes into the resource that is playing right
      now. `_session()` is a single task: after `_play` issues the effect frame it loops straight
      into the next beat, so a pulse's 2-frame mute could begin 0.9 s into a cry that was still
      sounding, and take the second half of it away.
      *Two halves, and neither makes the other redundant.* `Ball._wait_out_the_cry` holds any upload
      until a sounding cry has finished, whatever made that upload due. `Signaller.sounded` counts
      the quiet after a cry from the **sound** rather than from the decision, so the pulse is not
      due in the first place. The distance between those two moments is the whole defect: one tick
      when the cry is already in the slot, six to nine seconds when it has to be uploaded first —
      thirteen uploads measured that day, against a configured gap of 5 s. On more than half of the
      day's beats the quiet the cry was owed had already run out before the cry began.
      *The third thing found was not in the sound at all.* `play (beat)` is printed when a beat is
      **decided**. At 14:26:14 the log printed it clean and the ball did nothing for another 2.4 s,
      because `_play`'s slot test can only see the slot *now* — and by then the upload it had been
      queued behind had finished and left the slot correct, so there was nothing to warn about. A
      log that reports a sound nobody heard is the silence principle 7 refuses, wearing a line of
      output. So whoever waited now says so: `beat late` in the mirror, `quiet extended` in the
      daemon, and the guard naming the seconds it held. Both are thresholded at 0.5 s, because the
      poll tick and the BLE round trip push every single beat a little and a line for each of those
      is a line per beat.
      *What it does not do is read the ball.* Asked in as many words — "with this do we no longer
      need to guess, and will we know exactly what is in the ball?" — and the answer is no. Nothing in the
      protocol reads the slot back or empties it, so `self.slot` stays a belief and `UNKNOWN` stays
      a real state. What changed is that the belief can no longer contradict the wire: `_put` sets
      `writing` and drops the slot to `UNKNOWN` for the whole upload, so the window in which the
      mirror would have claimed to know is now the window in which it says it does not.
      *What is measured, and what is not.* The freeze beginning 14:26:08.52 and the mute upload
      logged at 14:26:09 are both measured. Which of them came first is **not**: `src/log.py` stamps
      to the second, and half a second is inside that. The collision is the best-supported
      explanation on the evidence rather than a demonstrated one — which is why the code now prints
      a line at the moment the ball is written to. `check_ball_mirror`, `check_ladder` and
      `check_criteria` all pass with every mutant caught, and two probes with a control leg apiece
      show the new code is reachable *and* correctly quiet where it should be — the guard stands
      down at 0.00 s once a cry is over, and a cry already in the slot buys 0.05 s of quiet and
      prints nothing. No check runs the loop with a ball attached, though, so the wiring from
      `Ball.spoke_at` into the daemon was read rather than run, and it stayed that way until the
      desk closed it.
      *The desk closed it the same day, 15:06–15:16, on tape and with sound
      (filmed at the desk, 2026-09-23).* The round forced the collision rather than waiting for it,
      because a daemon that has just started leaves a mute in the slot: a beat at 15:08:26 that had
      to upload its cry, a pulse decided at 15:08:31 **before** that cry had sounded, the cry
      arriving at 15:08:33 — and the guard holding that pulse's mute off the slot for 0.96 s. Which
      also settles that neither half is redundant: `quiet extended` could not arrive until the ball
      reported the sound, so it moved the *next* pulse and did nothing for the one already in
      flight.
      *The control leg is the half worth keeping.* The earlier beat, at 15:07:56, found its cry
      already in the slot, and the pulse four seconds later uploaded its mute with no guard line at
      all. A guard that had spoken there too would have passed the other leg for the wrong reason.
      *Both cries came out whole, measured by the defect's own signature* — the longest pitch held
      inside one 1.15× band — at 0.080 s and 0.064 s, against the source file's 0.080 s and a
      known-broken cry's 0.288 s. That last figure is the positive control, and without it the other
      three prove only that the instrument is blind. `var/desk/cry_shape.py`.
      *One number from that round was thrown away, and is written down anyway.* "Onset to last loud
      frame" made the guarded cry 1.26 s, twice the source, which reads alarming until you look: five
      frames of room noise at a tenth of the cry's energy, sitting just over a low gate. A single
      field is not a finding however dramatic it looks. Separately, three `went unacked in 5.0s`
      appeared across roughly forty consecutive pulses — new, unexplained, not this defect, and left
      in the doc rather than folded in here.
- [x] **27 — The link's account of itself was reaching nobody.** Followed on 2026-09-23 from the
      `went unacked` lines task 26 had set aside. The round's terminal capture holds 34 of them —
      `went unacked`, `acked on attempt N/3`, `never acked after 3 attempts`, `a reply for another
      command arrived` — and `var/logs/wobble-2026-09-23.log` holds **zero**. The counters those
      lines come from carry a comment telling whoever reads it that a link needing 40 retries this
      hour is a fact about the afternoon; the afternoon was being thrown away with the terminal
      window.
      *The mechanism, and the reference leg that proves it is the mechanism.* `src/log.py` attached
      its handler to `wobble.daemon` and set `propagate = False`; every other module logs to
      `__name__`, nothing was attached anywhere above them, and the daemon calls no `basicConfig` —
      all five in the tree are in the one-shot CLIs, which is why the same lines are perfectly
      visible from `cry.py` and vanish from the daemon. So those records were falling through to
      `logging.lastResort`: stderr, and WARNING or above. The leg that turns this from a story into
      a measurement is `opening replayed`, an INFO from the same module, which appears **0 times in
      either** — below `lastResort`'s floor. An absence in both places is what rules out "the lines
      simply did not fire".
      *The fix is a relay and not a second handler.* `log.start` now wires the root logger: a stderr
      handler, and a `Relay` that turns a record into one of `say`'s lines and puts it down `write`
      like everything else. One writer for the file, so `Daily` keeps its single promise — the
      string it is handed is the string in the file. `src` and `wobble` are set to INFO by name, so
      bleak and asyncio still reach the file at WARNING and above: a library's complaints, not its
      narration. The columns come from `daemon.shaped` rather than from a second copy of `COLUMN`
      here, because two copies of 22 are two numbers that drift.
      *The first attempt did it by reshaping inside `Daily`, and `check_log.py` caught it in one
      run* — three rows about the file being character for character what the terminal said. A
      handler that quietly rewrites some of its input by logger name is the kind of thing that
      passes review and fails a year later. `var/desk/check_link_log.py` is the new check, with a
      control leg that removes the wiring and requires every row to break.
      *What this does not fix.* Frame **16 of 17** of the cry upload failed three times (15:30:31,
      15:31:05, 15:35:25), always that frame, always preceded by the same foreign reply `04010011`,
      while the 2-frame mute — which has a `KIND_CLOSE` frame of its own — never fails. Three
      explanations were tested and all three are dead: the link degrading with age (the upload 13 s
      after the third failure took 6.8 s, the fastest since 15:08), a second daemon on the ball (the
      stray process was running `--no-ball`), and a concurrent write slipping past `Link.hold`
      through its link-wide `_held` flag (`beat()` does not block and the mirror has one worker, so
      the pulse lines interleaved in the log are the daemon talking, not the wire). Cause unknown,
      n=3. Noticed on the way past and also unfixed: during the 13 s that upload spent retrying,
      four pulses were dropped in silence, because `self._beat` is a single slot each one
      overwrote — reasoned about in `_wait_for_work`'s docstring, but nothing says it happened.
- [x] **28 — Seven beats in six seconds, and one sound out of the ball.** Reported from the desk on
      2026-09-23: the `needs` waves came with "the feeling of lots", the interval had grown, and it
      was nothing like the fixed tests. Both ends were measured before anything was touched. The
      daemon's decisions were exactly on time — 29 gaps of 1 s and 30 of 2 s in the day's file,
      which is a clean 1.5 s stamped to the second and nothing else. So the whole of the defect
      lives between deciding a beat and the ball making a sound.
      *The mechanism.* The mirror has one worker. `link.send` is `ATTEMPTS` 3 × `ACK_TIMEOUT` 5 s,
      so a single unanswered effect frame holds that worker for up to 15 s; `needs` beats every
      1.5 s, so ten beats fall due inside one stall. `Ball.beat` is one slot deep and newest wins —
      nine of those ten were overwritten and never felt, and nothing anywhere said so. That is
      principle 7 exactly: a signal going quiet for a reason nobody can see. It was reasoned about
      in `_wait_for_work`'s docstring and noticed again in passing at the end of task 27; what was
      missing was the ball admitting it out loud.
      *The one line that should have caught it was under-reporting by a factor of ten.* `beat late`
      printed 1.0 s where the worker had been blocked in `link.send` for over ten, because
      `_beat_at` was reset on every call and so measured from whichever beat had arrived last
      rather than from the one still waiting. An instrument that answers "how long has this been
      waiting" with "since the most recent arrival" cannot measure a stall by construction — and a
      comfortable 1.0 s is exactly the number nobody goes and checks.
      *Three changes, and the order was the point.* `_missed` counts the beats taken off the slot
      unplayed and `beat late` says how many; `_beat_at` is stamped only onto an empty slot, so it
      holds the first of a pile; and only then the effect frame gets a budget — `Voice.budget_s`,
      the beat's own gap in the rhythm, carried over from the config. Instruments first, so the
      before and after of the third change is measured rather than judged by ear against a log
      that was lying.
      *And the budget is spent as fewer attempts, not shorter ones — which is the opposite of how
      it was first written.* The draft divided the gap by `ATTEMPTS`: 1.5 s ÷ 3 = 0.50 s an
      attempt. `docs/PROTOCOL.md §9` measured five acks on an established link at **0.52–0.61 s**, and
      0.16 s on a fresh one; an earlier project settled on a 2 s deadline for the same reason. So that
      draft would have retried every healthy `needs` frame twice, written the effect three times,
      and ended on `BALL SILENT` for a beat the ball had played — a fix that reads perfectly and
      makes the reported defect worse. The rule instead: attempts = the gap ÷ `SLOWEST_ACK_S`
      (2.0 s, `docs/PROTOCOL.md §9` with headroom), at least one and never more than `ATTEMPTS`, with the deadline
      the gap ÷ that. `needs` 1.5 s → **1 × 1.5 s**; `done`'s pulse 3.0 s → 1 × 3.0 s; `done`
      itself 30 s → unchanged at 3 × 5 s. A beat that cannot afford a retry does not get one, and
      the next beat 1.5 s later is its retry — `docs/PROTOCOL.md §9` puts 85 % landing on the first try.
      Under `SLOWEST_ACK_S` the two rules stop being satisfiable at once — `MOTOR_FLOOR_S` allows a
      gap down to 0.6 s — and there the gap wins: such a beat is one the log should call silent
      rather than one the worker waits out. The loader cannot warn about it without `src/core`
      importing a fact about a radio, so the desk check is what holds the shipped config clear of
      that line.
      *What is deliberately not budgeted.* `_put` and `_colour` keep the full 5 s. A beat still
      being retried when the next one is due has stopped being a beat, and landing it late reads in
      a rhythm as a hole followed by a stumble — but a resource with a hole in it costs something
      other than a late flash, and there is no way to read the slot back or clear it. The core
      hands the number over and has no opinion about what a radio does with it (principle 1); how
      to spend it is the mirror's business.
      *The check is `var/desk/check_needs_rhythm.py`.* The gap reaching the voice; the timeout
      reaching the wire, picked out by frame label rather than by position, because `_colour` goes
      first and must stay unbudgeted; the count and the stamp under three beats arriving mid-send;
      the words the log actually uses; and a control leg that removes each rule in turn and
      requires the table to break — including the first draft's 0.50 s, kept as a control because
      it passed every other row in the table. `check_ladder` pins the three budgets against typed
      literals —
      a number read back off the same loader would agree for the wrong reason — plus a row that
      the voice's 1.5 is the same 1.5 the cadence is built from, two copies that must not drift.
      *What this does not fix, and what to watch.* The wire still loses frames; the budget only
      decides whether a lost beat is silent and on time or late and in the wrong place, so
      `BALL SILENT` will be said sooner and more often on `needs` — that is the honest version of
      what was already happening, not a regression. **The number to watch is how often.** `docs/PROTOCOL.md §9`'s
      85 %-first-try was measured on writes 10 s apart, not on a beat every 1.5 s, and if
      `BALL SILENT` turns out common on a `needs` wave then `SLOWEST_ACK_S` is too low or the gap
      is too tight for a single write, and that is the evidence to bring back here. Frame 16 of 17
      (task 27) is still unexplained. And none of it has been heard yet: the daemon has to be
      restarted, and the round that settles it is a `needs` wave judged by ear at the desk.

- [x] **29 — The count should stop counting the one you are already looking at.** Asked for at the
      desk on 2026-09-23, with the menu bar open on a pending `done`
      (`docs/menubar-count-2026-09-23.png`, where the title reads `1 · 75%` and the list under it
      reads `toolkit — done`): "when a done is pending and I click to dismiss the pulse
      or Pikachu (B pressed), the 1 should drop from need to resolve, because I am already there
      looking at it — but only the number should drop, the flow stays exactly as we already agreed."

      *What changes.* Pressing B attends a signal — it raises the window and stops that signal
      speaking — but the entry stays in the queue, so `render(pending=1, …)` still puts a `1` in
      the title. The ask is that the attended one drops out of the **count**, because a number
      asking you to deal with something you are already looking at is asking twice.

      *What deliberately does not change, and the phrase is the person's own — "the flow stays
      exactly as we already agreed".* The entry stays in the queue, in the place it had. The snooze still fires at
      `snooze.after_s` (300 s) and brings it back, because dismissing is a promise and a promise
      not kept returns the signal. A prompt is still the only thing that resolves it, and B never
      ends a signal (`src/core/attention.py`). So this is one number on one mirror, not a change to
      the attention state machine.

      *The thing to decide before building it.* `config/signals.json` says of the done pulse that
      "with no ball there is no LED, and what carries 'still pending' on the Mac is the count
      sitting in the menu bar". Take the attended one out of the count and, on a Mac with no ball,
      nothing is left saying it is pending — which is the silence principle 7 forbids. The way out
      is in the screenshot itself: the list under the icon still names the project, so the signal
      stays *visible* while it stops being *counted*. Decide whether that list is enough on its
      own, or whether the attended one needs a mark of its own in the title (the `○` that already
      means "nothing pending" is not it — it would say the opposite of the truth) before the number
      is allowed to drop it.

      *Where it lands.* `src/mirrors/menubar.py` `render()` is pure and is handed `pending` as an
      int, so the mirror is not where the rule goes: a mirror may only render what it is given
      (principle 1). `Attention` already knows which entry is being attended (`current()`), so what
      changes is the number the core hands over — "pending, not counting the attended one". No new
      state, and the menu's own list keeps being built from the queue as it is today.

      *Settled 2026-09-23: the decision at the desk on the question above was that the list is
      enough — no new mark. But checking that against the running daemon before writing anything found the
      task's own premise wrong, not just the open decision.* `dismiss()`'s own docstring already
      says why: "the new entry leaves the queue, because criterion 4 says the count drops to what
      is left" — `_take()` calls `queue.drop(nxt.project)` on every press, first one or not. Proven
      live, not just read: the shipped daemon, `--no-ball --no-menubar`, a synthetic `done` queued,
      Enter sent as B through a FIFO on its stdin. The log: `queued done (1 pending)`, then
      `B pressed attending done (0 left)`. The title already drops to `0` on the press itself — no
      code changes that.

      *The real gap was one line up in the same paragraph.* `queue.drop()` does not just uncount the
      attended entry, it removes it from `Queue` entirely, and `offer()` (`src/daemon.py`) built the
      menu's list from `queue.pending()` alone — so the held entry vanished from the **list** too,
      for the whole snooze. That is the silence open decision 8 was actually asking about: not the
      number (already right), but the project's name disappearing from view while you are still
      the one holding it. "The list is enough" answers that gap correctly even though it was asked about
      the wrong symptom.

      *The fix.* `offer()` now appends `attention.entry` (when held) after `queue.pending()`, so the
      list still names the project while it is attended, unchanged in every other way — same
      `line()` format as any pending row, no new mark. Clicking it is already safe with no new code:
      `attend()` on a project the queue no longer holds returns an empty `Taken()`, the same no-op a
      stale row already gets (task 21).

      *Verified against the real classes, not just read.* `Queue`, `Attention` and `menubar_items`
      built the same way `offer()` now does: before B, count 1 and the list shows `wobble — done`;
      after B, count 0 (already true) and the list **still** shows `wobble — done`; clicking that
      row calls `attend("wobble")` and changes nothing (count stays 0).

      *Looked at, on the real dropdown, 2026-09-23 21:53.* Four frames in order: `○ · no ball` with
      `Nothing waiting`; `● 1 · no ball` when this session's own `done` arrived; `○ · no ball` after
      a right-click; and the menu open on that same `○`, still offering **`wobble — done`**
      (`docs/menubar-held-in-list-2026-09-23.png`). That last frame is the whole task in one
      picture — the count says nothing is waiting and the thing you are dealing with is still on
      the list. The daemon's own account agrees: `21:53:59 B pressed attending done (0 left)`.

- [x] **30 — The beat that runs to catch up, and the poll tick it is exactly the size of.** Heard at
      the desk on 2026-09-23, minutes after task 28 landed and while calling that fix good: "there
      were two times the beats seemed a little faster, kind of 'let me run to keep up the rhythm',
      like someone following a score and straying very little from the metronome. 98% of the time,
      great, right on the beat."

      *The day's file cannot see it, and said so by being perfect.* That wave: 72 beats, stamps
      alternating 2/1 s, mean 1.507. A mean that good is the signature of the defect rather than
      its absence — `say()` stamps to the second and the wobble is a quarter of one. Reporting "no
      evidence in the log" off that would have been a claim about the stamp, not about the ball.

      *Measured instead, with a control leg.* `var/desk/probe_beat_jitter.py` takes the stamp when
      each `play (beat)` line arrives on the daemon's stdout pipe — the shipped daemon, its own
      events file, no ball and no menu bar, the isolation `check_rhythm.py` established. Leg A at
      the shipped `--poll 0.25`: 78 beats, mean 1.501, steady gap **1.53 s**, and **9 gaps of
      ~1.28 s**, one every 8-9 beats. Leg B is the control, at `--poll 0.4` — incommensurate with
      1.5 s, so an anchored schedule there CANNOT be even and the leg must come back dirty: 1.62 s
      steady, 8 gaps of ~1.22 s. It is in the probe because a clean leg A on its own would only
      have proved the probe was blind.

      *The mechanism, and the 0.25 is not a coincidence.* `src/daemon.py:255` records
      `self.last_beat = beat` — the time the beat was **due**, not the time it went out. The due
      times are therefore a perfect 1.5 s grid, while a beat can only actually leave on a poll
      tick, and the poll loop is `await asyncio.sleep(args.poll)` plus that tick's own work, so its
      period is 0.25 + ε and it drifts against the grid. Each beat goes out a few ms later than the
      one before until the lateness passes a whole tick — then one beat lands a tick early and the
      heard gap collapses by exactly one poll interval. 1.53 - 0.25 = 1.28. The average stays
      perfect (1.501) throughout, which is what an anchored schedule buys and precisely what a
      rhythm does not want: a rhythm is judged one gap at a time, never on its mean.

      *The proposed fix is one line, and its trade is explicit.* `self.last_beat = now` in place of
      `beat`, so the clock starts from when the beat actually went out: a gap can then never be
      shorter than `every_s` and the sawtooth cannot exist. The cost is that the cadence runs a few
      ms slow per beat and never repays it — a steady 1.53 s instead of 1.50 — and that is the
      cheap half of the trade, because 1.53 s is already the steady state the desk heard and called
      "great, right on the beat". Two things to settle first: `self.last_pulse = beat` on the next
      line is deliberate (the 2026-09-22 finding that the cry and the flash landed in the same
      tick) and must either move with it or be argued about; and `self.last_beat += spent` at
      line 245, which hands back the time spent watching, is written against the due-time meaning.

      *What not to do.* Lowering `--poll` shrinks the stumble without removing it — the sawtooth is
      one tick tall whatever the tick is — and pays a faster loop's CPU for a defect a one-line
      anchor change deletes outright.

      *Settled 2026-09-23, by asking rather than assuming.* Apply the fix — the desk's own reaction
      to 1.53 s stands. Move `self.last_pulse = beat` at line 261 to `now` alongside it, so the
      anchor means the same thing everywhere. And fix `self.last_pulse = pulse` at line 292 too:
      the pulse's own recurring cadence, never measured the way the beat's was, turned out to carry
      the identical due-time anchor. `self.last_beat += spent` at line 245 needed no change — it
      shifts the anchor forward by exactly the frozen duration, which is correct whatever the
      anchor means.

      *The probe's own guard fired, and earning the result took a reference leg.* Leg A came back
      exactly as predicted — 76 beats, mean 1.534, **zero** gaps under 1.45 s. But leg B, the
      control built to always come back dirty at an incommensurate poll, came back clean too (26
      beats, steady ~1.626 s) — which by the probe's own rule ("a clean leg B means the probe went
      blind") says leg A proved nothing. Rather than believe or dismiss that on the spot, the code
      was stashed back to its pre-fix state and the probe run again: leg B caught its 8 gaps and
      leg A its 13, both matching the numbers already on record above — the pipeline is not blind.
      The fix genuinely removes the sawtooth at **any** poll rate, because anchoring on the actual
      fire time resets the reference every beat instead of measuring drift against one grid fixed
      further and further in the past — there is no longer a grid to fall out of phase with. That
      makes the probe's control leg a check for the *bug class* rather than for this fix
      specifically: it will read clean against the shipped code from now on, and a regression back
      to due-time anchoring is what would turn it dirty again — worth a line in the probe itself
      next time it is touched, so a future clean leg B is not misread as blind.

      *Not yet done: a `needs` wave judged by ear at the desk.* Everything above is the daemon's
      own account of itself; nobody has listened to the fixed cadence yet.

- [x] **31 — One session, two projects, because the folder it is standing in is not the project.**
      Seen on screen 2026-09-23, at the desk: the menu offered `src-tauri — done`, a folder name
      that is not a project anybody here works on. It is the **same session** that had been filed
      under `editor` three minutes earlier — `18:32:32  editor  queued  done (1 pending)` and
      `18:35:56  src-tauri  queued  done (1 pending)`, both session `6e3e216e`, in today's log.

      *Where it comes from.* [hooks.py:134](../../src/hooks.py#L134) is `project = Path(cwd).name`,
      and an agent that `cd`s into a subfolder for one tool call changes the answer for every hook
      that fires afterwards. The comment directly above that line already says these are separate
      fields "because the day a hint has to be something else, this is the one line that changes" —
      this is that day, and it turned out to be the project rather than the hint that moved first.

      *It is not one session, and it is not one repo.* Sweeping the whole of `var/events` (592
      events that parse) for sessions whose `cwd` basename is not stable finds four real ones:
      `6e3e216e` (`editor` / `src-tauri`), `f027621d` and `4ad762cc` (both `toolkit` /
      `trends`), and `c62bd8fd` (`toolkit` / `70-decisions`). The other
      two the sweep returns are the hand-made fixtures from desk checks 25 and 12. In the same
      sweep, the number of sessions whose `transcript_path` folder is not stable is **zero** — the
      thing that moves is the cwd, not the session's idea of where it lives.

      *Three costs, and only the first one is cosmetic.* The name on screen is a folder nobody
      recognises across the room, which is what was reported. The count can be wrong for the right
      reason: two sessions of one repo, one in the root and one in a subfolder, are two `project`
      values and therefore two entries and a `● 2` for one window — exactly the thing task 20 was
      written to stop. And [hooks.py:135](../../src/hooks.py#L135) hands the same word to
      `window_hint`, where `Waiting.in_window` is a casefold substring test against the real window
      title ([signals.py:217](../../src/core/signals.py#L217)) — so both the raise on B and the
      rule that keeps a signal quiet while you are already looking at it are aiming at a word the
      title may not contain.

      *The shape of the fix.* Walk up from `cwd` to the nearest directory holding a `.git`, and use
      that directory's name; fall back to `Path(cwd).name` when there is none above, because a cwd
      under the scratchpad has no repo at all. `.exists()` and not `.is_dir()`: in a worktree
      `.git` is a file. Checked live rather than assumed — neither `editor/src-tauri` nor
      `toolkit/investigations/trends` holds one, so both land on the repo root,
      and a submodule would stop at the submodule, which is the right answer for a project name.

      *Not `git rev-parse --show-toplevel`.* `parse()` runs in the daemon, once per event line
      ([daemon.py:591](../../src/daemon.py#L591)), so that would be a process spawned per hook to
      learn what four `exists()` calls answer. It also makes `--replay` of an old events file cost
      a subprocess per line. Either way, resolving against the filesystem at read time means a
      replay answers with today's filesystem rather than that day's — acceptable, and worth one
      line of comment so it is not discovered as a surprise.

      *Still to measure, and it decides half the task: does `window_hint` follow the root too?*
      Because `in_window` is a substring test, the root name wins whenever the title carries the
      whole path and loses whenever the title is the cwd's basename alone — it is the terminal's
      choice, not ours. Today's `watching` lines cannot answer it: every one of them is a session
      whose folder already **is** the repo root (`In front right now: Tasks.md line 214 — wobble`).
      Owed at the desk: open a session in a subfolder, read what the daemon's own `watching` line
      says the title is, and only then decide whether line 135 follows line 134 or stays on `cwd`.

      *That desk pass is blocked on a permission, not on code.* Since 18:22:54 the daemon has been
      logging `CANNOT SEE FOCUS — macOS has not granted Accessibility to this process`, and every
      B press today answered `NOT FOCUSED`. It cannot read a window title at all in this state, so
      nothing about window matching can be measured until Accessibility is granted to the terminal
      hosting the daemon (it is granted per application) and the daemon restarted.

      *Where it lands.* `src/hooks.py`, one function. Nothing in the core, nothing in a mirror: the
      queue and the menu already render whatever project they are handed, and the whole point of
      this task is that they have been handed the wrong word.

      *Settled 2026-09-23: the name is fixed, the hint deliberately is not.* `hooks.project_of`
      walks up from `cwd` to the nearest `.git` and falls back to the folder's own name; line 135
      still hands that same word to `window_hint`, and the comment above it now records the one
      case that can pull them apart — a session started *inside* a subfolder keeps the subfolder in
      its terminal title while the project now says the repo. That case regresses where today it
      works, which is why it is written down rather than quietly accepted: it is the reading the
      desk pass owes, and `transcript_path` is the source to reach for if it turns out to matter
      (the sweep above found its folder stable in every session, which is precisely the property a
      window hint wants).

      *Verified against the real events file and then the real daemon, in that order.* Re-parsing
      all 596 usable lines of `var/events` through the shipped `parse()` leaves **zero** real
      sessions under two names. The two the sweep still reports are the hand-made fixtures from
      desk checks 25 and 12, whose paths do not exist on this disk at all — that is the control leg
      working, not a miss: a function that collapsed those too would be collapsing everything.
      Then the daemon itself, `--no-ball --no-menubar` on a scratch events file, fed one session in
      `editor` and one in `editor/src-tauri`:

          19:57:15  editor      queued    done (1 pending)
          19:57:15  editor      queued    done (1 pending)
          19:57:15  blind       queued    done (2 pending)

      One name, and — the part that was reasoned about rather than measured when the task was
      written — **one entry**: the count stays at 1 for two sessions of one repo, instead of the
      `● 2` for a single window that task 20 exists to prevent. The third line is a cwd with no
      repo above it, which keeps the folder's own name and is a project of its own, as intended.

- [x] **32 — Half the time, pressing the ball's button is pressing into nothing.** Reported at the
      desk 2026-09-23: "tried to wake the ball to use it, it didn't respond... stopped, sent again,
      and it worked", confirmed as the connection rather than the window ("the ball did not
      connect, then it connected").
      The log has it to the second: `21:57:20 no ball answered in 25s`, rescan at `21:57:42`, failed
      again `21:58:07`, rescan `21:58:30` — and `connecting…` on that same second, `connected
      21:58:35`. Roughly 55 s between the first press and the link.

      *It met its own specification, which is the actual defect.*
      [ball.py:86-91](../../src/mirrors/ball.py#L86-L91) sets `RETRY_S = 20.0` and the comment above
      it promises "fast enough that a press is noticed **within a minute**". It was. Nothing
      malfunctioned; the number was chosen against a claim that is false.

      *The claim it was chosen against.* That comment justifies the gap by saying a short retry
      "would be a scan running all afternoon". It already is one. With `SCAN_TIMEOUT = 25.0`
      ([link.py:30](../../src/ball/link.py#L30)) and a 20 s wait, today's log counts **149 scans
      started, 139 that found nothing and 8 that connected**, with measured gaps of 20-23 s — a
      ~46 s period that is listening 54% of it and deaf for the rest. 139 × 25 s is 58 minutes of
      active scanning across the afternoon. Going continuous is 1.9x that, not the difference
      between nothing and all afternoon.

      *And the ball gets no say in it.* The ball sleeps fast and stops advertising, so a press that
      lands in the deaf window is lost with no feedback anywhere: nothing on the ball, nothing in
      the log, nothing in the menu bar. The person cannot tell that apart from a dead battery, a
      daemon that stopped, or Bluetooth being off — four different facts wearing one silence, which
      is the shape principle 7 exists to forbid.

      *What the platform allows, checked rather than assumed.* macOS cannot scan passively at all —
      `bleak` raises `BleakError("macOS does not support passive scanning")` — so both sides of this
      choice are an active scan and only the duration differs. In its favour, `bleak` calls
      `scanForPeripheralsWithServices_options_(None, None)`: no `CBCentralManagerScanOptionAllow
      DuplicatesKey`, which is CoreBluetooth's cheap coalescing mode rather than the expensive one.

      *Measured, because the constant this replaces was justified by an unmeasured "cheap".* A
      continuous scan in this room costs **1.42% of one core** — 0.427 s of CPU per 30 s against
      0.001 s idle, 562 callbacks in that window, among 34 BLE devices in range. That is 51 s of CPU
      per hour of scanning; today's 54% duty already spends ~28 s of it, so the real price of this
      task is about **24 s of CPU per hour**. The radio's own cost is a different number and is
      still unmeasured: it needs `powermetrics` under sudo, and saying so is better than repeating
      "cheap" twice in one file.

      *The best practice is real, and it is refused here on purpose.* Every platform's answer to
      reconnecting a known device is to stop scanning and register a standing connection the
      controller holds: CoreBluetooth's `connectPeripheral:` on a peripheral from
      `retrievePeripheralsWithIdentifiers:` never times out, Android calls it
      `connectGatt(autoConnect=true)`, BlueZ an auto-connect list. `bleak` exposes none of it —
      `retrievePeripherals` appears nowhere in its CoreBluetooth backend — so taking that route
      means raw PyObjC inside `src/ball/`, a package whose whole justification for sitting outside
      `platform_seam/` is that `bleak` runs everywhere. Rejected by the seam rule, not by
      difficulty, and written down here so it is a decision rather than an oversight.

      *A backoff was considered and refused.* Scanning hard only while something is pending, or
      after recent activity, would cost less — but the one signal that matters is a thumb on the
      ball's button, and that is precisely what no backoff can see. Every such policy recreates this
      defect in a smaller window, tuned against the radio number nobody has measured, which is the
      same move that produced `RETRY_S = 20.0`.

      *A cheaper scan is available and is not part of this task.* `BleakScanner(service_uuids=[…])`
      filters in the controller instead of in Python, and `SVC_VENDOR`
      ([protocol.py:32](../../src/ball/protocol.py#L32)) is the obvious candidate — but `docs/PROTOCOL.md §2`
      records the GATT surface *after* connecting and says nothing about what the advertisement
      carries, so switching it on blind risks a scanner that never sees the ball at all. It is one
      desk reading, not a guess to ship.

      *The shape of the fix.* `find_ball(timeout=None)` keeps one scanner up until the ball
      advertises instead of tearing it down every 25 s; `Ball.run` races that against the link being
      given up, so "Stop looking for the ball" still returns at once. `RETRY_S` stops meaning "the
      gap between scans" and starts meaning "how long to wait after a link *error*", which is the
      only thing it is still needed for. Three things come with it: the deaf window goes to zero,
      the 149 `start()`/`stop()` cycles become one per away-period, and the 427 of 4070 log lines
      (10.5%) that are this loop announcing nothing collapse to one line per transition — a noise
      floor that hides real events is principle 7 failing from the other direction. It also makes
      the menu honest: it already offers **"Stop looking for the ball"**, a sentence that is true
      54% of the time today.

      *Done, and the give-up path measured before the window was believed.* The worry with a scan
      that never ends is the opposite of the one it fixes: a scanner left running after somebody
      chose *Stop looking for the ball*, which is a radio nobody switched off and a menu lying in
      the other direction. So that was checked first, by counting rather than by looking —
      `BleakScanner.start`/`stop` monkeypatched, three give-up legs run: **3 started, 3 stopped**,
      each returning in **2.00 s**. The first version of that check counted live scanner objects
      through `gc.get_objects()` and reported "1 alive", which proves nothing at all — a reference
      not yet collected looks exactly like a leak — and it was thrown away rather than reported.

      *And the window itself, from the live daemon.* Restarted 22:50:53 with the change in: **one**
      `scanning for 'Pokemon PBP'` line, and nothing at 22:52:13. The old code would have produced
      two of each by then plus a `no ball answered in 25s` warning between them. That is the 46%
      gone, read off the running process rather than off the diff.
- [x] **33 — One session, two lines, and a `needs` that had already been answered.** Seen on screen
      2026-09-23 22:11, reported as "a needs appeared, I resolved it, but it stayed listed — but
      it's actually just a done". The menu offered `restock-hunter — done` **and** `restock-hunter — needs` while the
      title beside it read `● 1 · 21%` — a count of one over a list of two, in the same frame.

      *The queue cannot produce that, so it is not the queue.* `Queue.pending` builds one entry per
      distinct project, and the whole of `var/events` holds exactly **one** restock-hunter session,
      `dc6e561f`. One session, one project, one row. The title was right.

      *Where the second line comes from.* [daemon.py:512-515](../../src/daemon.py#L512-L515) appends
      the held entry (task 29) to whatever the queue returned, unconditionally. Its docstring argues
      that clicking a held row is safe because "`attend()` on a project the queue no longer holds is
      the same no-op it is for any stale row" — true, and it quietly assumes the queue no longer
      holds it. Here the same session signalled again *while it was being attended*, so the project
      was back in the queue with a newer kind, and the held copy became a second row carrying a
      `needs` that no longer existed anywhere.

      *Clicking it does not clear it — it swaps it.* [attention.py:271](../../src/core/attention.py#L271)
      drops the project being taken **before** putting back the one being let go, and that order is
      load-bearing for criterion 7's skip. But `restore`'s guard is "a session that signalled again
      already has a newer row here, and that one wins"
      ([signals.py:277](../../src/core/signals.py#L277)) — and the drop has just deleted the very
      row that guard reads. When the held entry and the one being attended are the same project,
      the drop removes every row the guard could have seen, so the stale `needs` is refiled over
      the fresh `done`. The log shows the oscillation directly:

          22:07:01  restock-hunter  B pressed  attending needs (0 left)
          22:10:43  restock-hunter  queued     done (2 pending)
          22:11:34  restock-hunter  let go     back in the queue, where it was
          22:11:34  restock-hunter  B aimed    attending done (1 left)
          22:11:37  restock-hunter  let go     back in the queue, where it was
          22:11:37  restock-hunter  B aimed    attending needs (1 left)

      Each click trades which stale kind is sitting in the queue and the count never reaches zero.
      Three minutes later it was still there: `22:14:25 editor queued done (2 pending)` — two
      projects, one of which the person had already answered twice.

      *Two places, because they are two defects.* In the daemon, append the held entry only when its
      project is not already in `pending` — the justification for showing it is that the thing you
      are dealing with must not vanish from view, and a project that is back in the queue has not
      vanished. In `_take`, read which of the held sessions the queue already holds **before** the
      drop, and refuse to restore those — the rule `restore` already states, given the one fact the
      ordering takes away from it.

      *Not a retreat from task 29.* The held entry still stays on the dropdown for the whole snooze,
      which is what was asked for and confirmed by eye on the real menu. What stops is showing it a
      second time, under a kind it no longer has.

      *Done, and reproduced before it was fixed.* The sequence above, driven against the core with no
      hardware — one session signals `needs`, B takes it, the same session signals `done`, the line is
      clicked. Against the previous commit it prints the screenshot exactly, including the part that
      was only a suspicion until it ran:

          the menu now: ['restock-hunter — done', 'restock-hunter — needs']
          B aimed     attending done (1 left)  — and the hold went BACK in
          the menu now: ['restock-hunter — needs', 'restock-hunter — done']

      One project on two lines, and after the click the count is *still* 1 with the stale kind refiled
      — the swap, not a resolution. With both halves fixed the same run gives one line before the
      click, `0 left` after it, and the single line that remains is the held `done`, which is task 29
      working as intended. The two other `restore` callers were checked rather than assumed: the
      snooze has no drop in front of it, and `prompted` drops exactly the one session its restore
      already excludes, so neither destroys evidence and neither needed the new argument.

- [x] **34 — Mute mode: the same ball, with the sound taken out of it.** Asked for at the desk
      2026-09-23, in these words: *"the same way it works today, the ball's events, just without
      sound — a mute mode, where it only vibrates."* Everything the ball does stays — the rumble, the colour, the
      rhythm, the count, the queue — and only the noise goes.

      *There is exactly one route to a silent ball, and this project already drives it.* Every id in
      the firmware's sound bank carries its own sound, and there is no volume anywhere in the
      protocol: nothing in either capture turns one down or cuts one off, which is why
      [`ball.py`](../../src/mirrors/ball.py) says in its own words that B cannot stop a sound that
      has started. The single effect whose audio this project chooses is `213`, which plays whatever
      was last uploaded into the slot — and [`resource.silence()`](../../src/ball/resource.py) is a
      one-block MS ADPCM resource that decodes to zero. So mute is not a new capability being
      invented for it. It is the `done` pulse's own trick, which already runs four times a minute,
      applied to every voice instead of to one.

      *Which makes `needs` the whole of the work.* A `done` already speaks through the slot, so
      muting it is nothing more than leaving the mute resource where it is and never uploading the
      cry over it. A `needs` plays `199`, out of the firmware bank, where the slot cannot reach it —
      so muted, a `needs` stops being `199` and becomes `213` with silence behind it, like
      everything else. Two kinds, two different reasons, one destination.

      *The rumble is expected to survive, and that is measured for the effect but not yet for this
      exact case.* The rumble map (`docs/PROTOCOL.md §6.7`) scores every id against a floor
      taken in the same run, by the ball's own accelerometer:

          198 → 1.22x      199 → 6.22x      213 → 9.59x      214 → 0.70x

      Rumble is plainly a property of the firmware effect rather than of the slot: `198` and `199`
      are neighbours in the same bank and differ fivefold, `214` sits at the floor while `213` is
      nine times above it, and [`resource.py`](../../src/ball/resource.py) has no haptic channel to
      carry one anyway — the resource kinds are `OPEN`, `CONTINUE`, `CLOSE` and `LED`, and that is
      the whole list. Muted, the ball should therefore vibrate *harder* than a `needs` does today
      (9.59x against 6.22x). What nobody has measured is `213` **while the slot holds silence**,
      which is the one combination mute mode actually plays. The alternative reading — that the
      firmware drives the motor from the audio envelope, so a silent resource is also a still one —
      fits the same sweep, because the sweep had something in the slot the whole time.

      *Corrected at the desk 2026-09-24: it does not survive, and the number above was never a fact
      about `213` in the first place.* `var/desk/probe_mute_candidates.py` fired `213` in **1 of 8**
      rounds (median 1.73x its own floor) while `199`, on the same link in the same minute, fired
      **8 of 8** at a median of **21.9x** — the sweep's ordering, inverted, by a factor of twelve.
      The sweep plays every id exactly **once**, against a floor shared by twenty ids, scoring the
      *mean* sample-to-sample delta over 1.5 s: it ranks the map and confirms nothing about any
      single id, which is what `docs/PROTOCOL.md §6.7` already says of its own low
      end, where a 100 ms tick comes out diluted about fifteenfold. Four of those five numbers sit
      in that low end. So mute as shipped in `cd1564e` is silent **and** motionless — the branch
      this entry named and did not expect — and the lesson is the cheaper one: a ranking read as a
      measurement, load-bearing, in three files.

      *That measurement was attempted tonight and failed for a reason worth keeping.* The probe is
      written (`var/desk/probe_mute_rumble.py`: upload silence, play `213`, score the IMU; upload the
      cry, play `213` again; a floor in each phase, order shuffled). It needs the ball free, and the
      daemon was stopped to free it — at which point the ball went to sleep **instantly** and a 45 s
      scan found nothing. It only advertises on a press of its top button, and there was nobody
      awake to press it. That is the same fact task 32 is built on, arriving from the other side.

      *The code is identical either way, which is why this ships ahead of the measurement.* The
      muted voice is `213` + silence whichever answer comes back, because it is the only certainly
      silent thing the ball can be asked to do. The measurement does not choose between two
      implementations; it decides what may honestly be *claimed* — "silent, and it still buzzes" or
      "silent, colour and rhythm only". Shipping the second while believing the first is the failure
      to avoid, so until the probe runs, nothing in the code or the docs promises a buzz.

      *It mutes the Mac as well.* The request names the ball, but a mute mode that leaves the laptop
      chiming is not one, and the two surfaces are deliberately one notifier
      ([`signals.json`](../../config/signals.json) on `@cry`: "the ball and the Mac cannot be given
      different voices for the same signal"). A muted voice carries `mac_sound=None`, and
      [`menubar.beat`](../../src/mirrors/menubar.py) already refuses a voice that is `silent`, so
      this half needs no new branch — only the transformation to be honest about what it produces.

      *And it has to be visible, which is the one thing here that is not optional.* Principle 7:
      a notifier that stopped silently is worse than none. A mute somebody left on last night IS
      that notifier, and it would be indistinguishable from a broken daemon from across the room —
      which is the exact confusion the hollow dot exists to prevent. So the title says the word:

          ● 2 · muted · 87%

      Words and not a dimmer dot, for the reason the file already gives about "no ball": a quieter
      icon cannot be told from an icon you have stopped noticing. It is not persisted across a
      restart either, and that is a choice rather than an omission — a mute that survives a restart
      silently is the same defect with a longer fuse, and the banner prints the state every run.

      *What mute costs, written down rather than discovered later.* `needs` loses `199`, and with it
      the only thing that made `needs` and `done` physically different on the ball — they share
      `led` 138 today, so muted, the two kinds differ by **rhythm alone**: 1.5 s insistent against a
      cry-then-blink. The config already names the way out ("telling done from needs by colour is a
      choice waiting to be made"), and this is the first time it costs something real.

      *The shape of it.* The transformation belongs to the core, because a mirror that decided on
      its own to stay quiet would be a mirror inventing state (principle 1) — and because one
      transformation at the source is what keeps the ball and the menu bar from drifting into two
      different ideas of mute. [`Ladder`](../../src/core/ladder.py) grows `voice(kind, muted=False)`
      and `pulse(kind, muted=False)`, returning `replace(voice, effect=mute_effect, silent=True,
      mac_sound=None)` — `led`, `budget_s` and every rhythm number untouched. `mute_effect` comes
      from a new `"mute"` block in the config and not from a constant, for the same reason every
      other id lives there: if the probe comes back saying `213` is still, the answer is one number
      in a JSON file. [`Signaller`](../../src/daemon.py) carries the flag and reads it at its two
      call sites; `--mute` starts muted; the menu offers "Mute the sounds" / "Unmute the sounds"
      above the ball's own line.

      *Done, and the part that had no hardware in it was proved rather than reasoned about.*
      `var/desk/check_mute.py` is new and green: the core rows with three mutants behind them (a
      mute that leaves `needs` on `199`, one that quietens the ball and not the laptop, one that
      takes the colour and the rhythm with the sound — each must break the suite, and each does),
      the ladder proved to be read rather than rewritten, `mute.effect` proved to come from the
      config by moving it to `198` and watching the voice follow, the ball mirror's slot policy for
      all four combinations, and the Mac silent on the same voice with and without a ball — with
      the unmuted control beside it, because two rows saying "no sound" would pass on a mirror that
      never makes one.

      *The wiring was the part most likely to be wrong, so it is checked through the real daemon.*
      A flag read in all the right places and handed to neither surface passes every row above. So
      the check starts the daemon's own `run()` in-process with the null seam under it, takes the
      mute line **by position** out of the menu the daemon actually built — asking for it by label
      would agree with any wiring that spelled the word right and connected it to nothing — clicks
      it, and reads back: the title gains `muted`, the label turns into "Unmute the sounds", and
      the log says which way it went. `check_menubar.py` gained the menu-bar half, two new mutants
      with it (a mute the title never mentions; one label for both states, so the click reads
      backwards), and both are caught.

      *Two things the design gained on contact with the code.* The idle slot follows the flag, so
      the silence is loaded the moment the link goes idle rather than two seconds into the first
      muted signal — every signal was already correct without it, since a muted voice arrives
      `silent` and `wants()` already answered `MUTE`; what it buys is the latency. And the ball
      mirror is handed a **callable**, not a copy: `Ball(muted=lambda: signaller.muted)`. A flag
      stored at construction would be right exactly once, and the symptom would be a ball still
      crying while the menu bar says muted — two surfaces disagreeing about one switch, which is
      principle 1's failure wearing the costume of a caching bug.

      *What is owed is now a different question, and the easy answer to it is gone.* Nine ids buzz
      2 of 2 — `171`, `172`, `128`, `122`, `232`, `86`, `81`, `92`, `129` — but the desk heard a
      voice on every one except `171` and `172`, and those two are the `171..176` block `docs/PROTOCOL.md §6.7` scores
      at **566.7x**, four times stronger than anything else in the map: *"171 would maybe be a 9,
      and 172 a 10"*. The GO Plus `LED_VIBRATE_CTRL` packet would have replaced the ladder of ids with
      an `intensity` field, and it is dead — nine variants written to `…9aec`, including
      vibration-only at intensity 7, every one refused with `Application-specific Error 0x85`, first
      logged on 2026-08-21 and again here on 2026-09-24, independently, before that earlier log was
      read. `0x03` carries a u16 id and nothing else, so **the id is the dial**, and
      picking one is a re-sweep scoring **peak** instead of mean with a microphone beside the IMU —
      the IMU cannot tell a silent buzz from a loud one, and that is the half that decides this.
      Until it runs, `mute.effect` stays `213`: loudly wrong in the config rather than swapped for a
      guess, since a replacement nobody measured is the same mistake with a newer number.

- [x] **35 — Everything in the stroll slots, and the held light as the pulse.** Asked for 2026-09-25,
      once an earlier project had mapped the second set of slots: *"we already know everything we
      need, no workarounds"*. The ball keeps two sets of uploaded resources, told apart by the three bytes in
      front of an upload (`docs/PROTOCOL.md §7.2`): the **catch** set, `04 3e 00`
      for the cry and `01 fd 01` for the LED, which `213` plays; and the **stroll** set, `04 3c 00`
      and `01 fc 01`, which `129` and `9` play. Until now wobble lived in the catch set, and one
      audio slot was wanted for two things.

      *What the one slot had cost, listed so it is plain what went.* A silent flash every 3 s was
      an upload of silence over the cry (task 16), so the cry had to be put back before every beat;
      the mirror had to wait out a cry still sounding before uploading over it
      (`_wait_out_the_cry`, task 26); the config carried a 5 s `after_beat_s` to keep the blink off the
      voice, and the daemon raised it to the length of the `.wav` (`cry_seconds`); the mirror
      tracked which of the two resources the slot held (`wants`, `idle_slot`, `sounds_changed`);
      and a `done` that arrived during an upload waited for it. And mute (task 34) played `213`
      over silence, which the desk measured buzzing 1 time in 8. All of it is removed.

      *The map, settled at the desk the same day:*

      | signal | with sound | muted |
      |---|---|---|
      | `done` | `9` (the fc colour, held) then `129` (the cry in `04 3c 00`); `129` again at 30 s | `9` |
      | `needs` | `199` every 1.5 s | `4` every 1.5 s |
      | nothing pending | `180` | `180` |

      *The held light is the pulse.* `9` shows the colour in `01 fc 01`, gives a light buzz on every
      send, and then **stays on by itself** — tens of minutes in the sniffer capture, never seen
      to stop without `180`. So a pending `done` needs nothing sent between its beats: the light
      says "still waiting" the whole time, which is criterion 3 at no cost to the link. `9` is sent
      only when it is not already up, so the second beat is `129` alone. The pulse clock,
      `pulse.every_s` and `after_beat_s` are gone, and the loader refuses them, so an old config
      fails loudly instead of loading a blink the ball no longer does.

      *Why these ids, in the user's terms.* At a glance the light must say which kind it is: a
      `done` is the stroll Pokémon (`9` + `129`, both stroll ids) and a `needs` is the ball wobbling
      because something needs you (`199`, one of the catch-UI phases `198`–`200` whose colour the
      firmware fixes). `4` is `199`'s own colour and rumble without the sound, so a muted `needs`
      still reads as a `needs`; it buzzes on every send and stays pulsing. `213` is off limits from
      here on, and the catch slots are never written: they are kept for catching and for fast
      recording. The cry variants `110`–`128` of the same stroll slot are not used yet.

      *Light replaces light, and `180` is only for "nothing left".* A `needs` beating `199` takes
      the ball over; a `done` that gets the floor back sends `9` again. No `180` between kinds.
      `180` is sent when nothing is owed a light: the queue empty, B, a snooze, the signal's own
      window in front of you, a quit (menu, SIGINT or SIGTERM), and on every connect — so a light a
      crash left on does not outlive the next link.

      *The shape of it.* The daemon decides and the ball renders (principle 1): `Signaller.showing`
      answers which voice's light should be up now, or `None`, and the daemon hands it to
      `Ball.refresh` every tick. It is `None` with nothing pending, while watched, and before a
      signal's first beat, so a light never arrives ahead of its own cry (D.2). The mirror
      reconciles that against `lit`, its own record of which effect's light is up, because the ball
      cannot be asked: `None` with something lit is `180`; a `done` showing while dark gets its `9`
      back without a beat (after you look away, after a reconnect). The cry goes into `04 3c 00` on
      connect and nowhere else; the colour is one frame into `01 fc 01`
      ([`resource.fc_blob`](../../src/ball/resource.py), Pikachu's 138 in both halves, byte-checked
      against the sniffer capture). Mute is a per-kind `mute_effect` in the config and never
      touches the slot.

      *One defect found on the way out, and fixed with it.* Ctrl-C used to cancel the tasks
      mid-flight, which with a held light would leave `9` lit on the desk for tens of minutes. SIGINT
      and SIGTERM now take the same door as Quit, which sends `180` before letting go
      (`QUIT_GRACE_S` 2 → 3 s for that one try). Testing it showed every quit from a terminal hung
      after printing `stopped`: `asyncio.run` joins the default executor, and the B key's
      `readline` was blocked in it. It reads on a daemon thread now.

      *What is left to the desk* (DESK-CHECKS Part B step 18): the light held through a whole
      `done`, relighting after a look away (one extra buzz, by design), the kinds told apart by eye,
      and the ball dark after each way of quitting.
- [x] **36 — Each line in the menu says where it stands.** Asked for at the desk 2026-09-28, after
      a `done` stayed quiet behind one that was being attended: *"something to show it is ready, but
      it is waiting for me to finish something else"*. The list said `toolkit — done` and
      `wobble — done` the same way, while one was being signalled and the other was waiting its
      turn. The four words were agreed the same day:

      | status | when | says |
      |---|---|---|
      | signalling | the top of the queue, and you are not in its window | `· signalling` |
      | watched | the top of the queue, and its window is in front | `· quiet, you're looking at it` |
      | attending | B took it, and the snooze will bring it back | `· attending (back in Nm)` |
      | waiting | ready, and behind another one | `· waiting its turn` |

      - The core decides the status (`Attention.standing`), and the menu bar only words it
        (principle 1). `watched` is the daemon's per-poll answer from the seam, handed in the same
        way `Signaller.showing` already takes it.
      - "Signalling" covers the 5 s hold after a prompt and a `done` down to its light alone. Both
        are still the top of the queue speaking, and a fifth word for them would be noise.
      - The countdown is in whole minutes, rounded up, so the menu is rebuilt at most once a minute
        for it. Whether a rebuild with the menu open makes it flicker is for the desk to see.
      - A `menu` line goes in the log whenever a status changes, and the countdown is left out of it.
        Asked for the same day: *"the better the log is, the better"*. The log is what gets read to debug a
        run afterwards.
      - Reverses one half of task 29's "the list is enough": the held entry now carries a mark.
      - Verified by `var/desk/check_menubar.py` (the four words and the countdown), and by
        DESK-CHECKS Part B step 19 on the real menu.

- [x] **37 — Looking away waits 3 s before the signal comes back.** Asked for at the desk
      2026-09-28, after step 18's look-away passed: *"instead of it being instant, when leaving the
      screen, let's make it 3-5s after"*. The log that afternoon has four glances away and back inside 25 s
      (16:25:24-16:25:49), each one a `light back` with 9's buzz.

      - A window you leave still counts as looked at for `look_away.wait_s` (3.0 in
        `config/signals.json`; 5.0 shipped first and 3.0 was kept at the desk the same day): dark, nothing played, the clock still stopped. Coming back inside it
        is as if you never left.
      - It applies to the first cry too: a `done` that arrived while you watched cries 3 s after you
        leave, not at once. DESK-CHECKS step 14 says so now.
      - Per project (`daemon.LookAway`): a different signal at the top gets none of it.
      - The menu says `quiet, you're looking at it` for those 3 s. That is accepted: the menu only
        shows when opened.
      - Verified by `var/desk/check_watching.py` (the rows and three mutants) and
        `check_ladder.py` (the key, and a negative wait refused). At the desk: step 18's look-away
        bullet again.

- [x] **38 — Know which app a session runs in, not only which folder.** Seen at the desk
      2026-09-28, twice. (1) A needs from `otherproject` went quiet whenever this VS Code window was in
      front: its title was `Otherproject slots 9 and 10 wi… — wobble`, the conversation's name plus the
      folder, and `Entry.in_window` is a substring test ([signals.py:217](../../src/core/signals.py#L217)).
      Renaming the conversation made the needs keep playing here, which confirms the cause.
      (2) With a plain terminal open in the wobble folder, B on a wobble signal raised that terminal
      and not the VS Code window running the session. `Focus.window` walks every running app and
      raises the first window whose title contains the folder
      ([macos.py:333-344](../../src/platform_seam/macos.py#L333-L344)).
      (3) At 17:23:35-42, B alternated wobble and otherproject, and the otherproject window was titled
      `Wobble needs setup — otherproject`: the wobble raise could land on it, and at 17:23:57 wobble's
      done resolved "you were there". The log only says "its window came forward", never which
      window, so the desk could not tell — the `focused` line should name the title it raised.
      All three have one root: a folder name is the only thing a signal knows about where it came from,
      and a title is shared by every app that happens to show that word.

      *What the hook can already see* — measured from this VS Code session's own environment, which
      is what a hook it runs inherits:

      | fact | value here | what it gives |
      |---|---|---|
      | `__CFBundleIdentifier` | `com.microsoft.VSCode` | the app hosting the session |
      | `CLAUDE_CODE_ENTRYPOINT` | `claude-vscode` | which surface of Claude Code |
      | parent chain | claude 9301 → Code Helper 4808 → Code 4303 | the app's pid, the one to match |
      | window title | `<tab or conversation> — <folder>` | the folder, as the **last** segment |

      *The surfaces it has to work on.* Only the first row is measured; the rest is what has to be
      captured before it is built on (a declared value is not a running one).

      | surface | host facts | title | quiet while watched | B raises |
      |---|---|---|---|---|
      | VS Code extension | measured above | `… — <folder>` | the app matches AND the last segment is the folder | a window of that app whose last segment is the folder |
      | Terminal.app / iTerm | not yet captured | Claude Code may set it to the task's name — unverified | the app matches AND the folder is in the title; otherwise never quiet | a window of that app; the exact tab by its tty later, if wanted |
      | Warp | not yet captured | unverified | as above | as above |
      | Claude desktop app | not yet captured | likely `Claude`, with no folder — unverified | never quiet: it cannot tell two sessions apart | the app itself |

      *Proposed shape, in two steps, the first one measurement:*
      - **38a — record the host.** `hook_event.sh` adds a third field with the bundle id, the
        entrypoint, `TERM_PROGRAM` and the parent pid; the daemon parses it and logs it on `queued`.
        Run one real session on each surface and read what arrives. Nothing changes in behaviour.
      - **38b — use it.** The seam's `Frontmost` also answers the front app's bundle id. Watched means
        same app AND the title rule for that app. `Focus.window` only looks at windows of the
        session's app. A signal with no host (an old event, a surface not captured) keeps today's
        substring rule, so nothing that works now stops working.
      - Safety stays one way (principle 7): anything unknown is "not watched", which plays.

      *Built 2026-09-28, desk owed:* 38a's recording and 38b for VS Code together — the hook
      writes `__CFBundleIdentifier` as a third field, `Entry.in_window` refuses a front app that is
      not the session's, `Entry.names` takes the last ` — ` segment for `com.microsoft.VSCode` and
      the old substring everywhere else, `Focus.window` looks only in the session's app (the app
      itself when none of its windows fits), and `focused` names what came forward. Checked in
      check_focus, check_watching, check_hooks and check_daemon, each with a mutant for the old rule.

      *Open, for the desk:* whether the last-segment rule breaks a VS Code title setting you use;
      whether Warp and the terminals put the folder in the title at all while Claude Code runs.

      *Measured at the desk 2026-09-28, 17:49–17:51 — Terminal.app:* the host arrives as
      `com.apple.Terminal`. While Claude Code runs, the title reads
      `wobble — ✳ Claude Code — node ◂ claude — 120×30`, and its folder is stale: `wobble` is
      where the shell last drew a prompt, while the claude on that tab (`ttys000`) had its cwd in
      `~/dev/project-a`, because the run was `cd ~/dev/project-a && claude`. So in Terminal the title
      cannot say which session a window holds. Because of the app check, wobble's done still
      cried in that window, where the old substring rule would have kept it quiet. But project-a's
      B only brought Terminal forward "as it was". AppleScript does give each tab's `tty`, and
      `ps` gives claude's tty, so the Terminal rule to write is to match by tty, not by title.

      *Measured at the desk 2026-09-28, 17:54 — Warp:* the host arrives as `dev.warp.Warp-Stable`.
      While Claude Code runs, the title is only `✳ Claude Code`, and while it works a spinner
      glyph (`⠂`, `⠐`) takes the place of the `✳`. No folder is in it at all. That claude had tty
      `ttys001`, but Warp has no AppleScript that names a window's tty, so for Warp the title
      cannot say which session a window holds, and nothing else we can read says it either.
      Also seen: the Terminal session left idle sent Claude Code's 60 s `needs` at 17:51:39
      (its done came at 17:50:38). The Warp session then sent a done in the same folder, and the
      two were folded into one `project-a` entry. That entry's host is its first row's, Terminal's,
      so the queue keys on the folder, not the session. With two sessions of one folder open in
      two apps, the watched check and B follow whichever of them spoke first.

      *Measured at the desk 2026-09-28, 18:05–18:27 — a title we write:*
      - With `CLAUDE_CODE_DISABLE_TERMINAL_TITLE=1` (the name was found in the binary), Claude
        Code leaves the title alone and Warp shows the shell's `~/dev/project-a`.
      - A title written straight to the claude's tty (`printf '\033]2;project-a · 7d42\007' >
        /dev/ttys001`) arrived as `'project-a · 7d42'` and survived a whole turn. The done stayed
        quiet while that window was in front and cried 3 s after leaving it, as in VS Code. The
        screen was intact.
      - B found that window and macOS refused the activation, twice (18:25:47, 18:27:12), and
        Warp stayed behind. The same calls from a fresh process brought Warp forward every time,
        so the refusal is aimed at the daemon (macOS 14's cooperative activation).
      - `Focus._forward` now reads each way back from the window server and falls back to
        Accessibility's `kAXFrontmostAttribute`. `focused` says `via Accessibility` when that
        is what worked. Checked in check_focus with two mutants: the answer trusted, and no
        second way.
      - At 18:43:15, with the new code running, Warp came forward by plain activation, read back
        and confirmed. The refusals came right after typing in VS Code, and none has happened since,
        so the Accessibility fallback has not yet been seen doing the work at the desk.
      - Also seen, and left alone for now: pressing B again on the only entry in attention is
        criterion 7's "skip". It lets the entry go, the entry cries again at once, and the next B
        takes it back, so a B pressed again because the window did not come makes a beat every
        time (18:41:26–18:41:37). Proposed: with nothing else waiting, a second B retries the
        raise instead.

      *Closed 2026-09-28 with what was measured:*
      - VS Code: app plus last title segment, measured at the desk.
      - Warp: the app check, with B read back and a fallback when activation is refused.
      - Any host: the `in front` log line.
      - Terminal: the app check only, since its folder in the title is stale.
      Still open:
      - Telling one terminal window from another moved to task 40.
      - The Claude desktop app was not measured. With no host rule of its own it gets the app
        check plus today's substring match.

- [x] **39 — Claude Code's idle reminder is not a question.** Seen at the desk 2026-09-28,
      during task 38's Terminal and Warp runs: *"no needs had actually gone out — none of them
      asked a question"*. Two `needs` cried, at 17:51:39 and 17:55:25, each about 60 s after a done in
      a session left alone. Their payloads carry `notification_type: "idle_prompt"` and
      "Claude is waiting for your input". A real question carries `"permission_prompt"` (17 of
      them in `var/events` that day). No VS Code session ever sent an `idle_prompt`, which is
      why it only showed up once terminals were in the test.

      - `hooks.reminds` reads that one value, and `HookLine.reminder` carries it on a `needs`
        only. The daemon queues nothing for it and says `idle reminder` with a running count,
        the same way it says `injected turn`.
      - A `Notification` with no type (two older lines have none) or with a type not seen yet
        stays a `needs`. That is the loud failure, principle 7.
      - Verified by `var/desk/check_hooks.py` (the real payloads saved as `idle-*`/`asks-*`, plus
        two mutants) and `check_daemon.py` (a reminder fired through the real script is said
        once and queued never).

- [x] **40 — Know each session by its process, and notice when that process is gone.** From task
      38's desk runs, which could not tell two sessions of one folder apart, nor two apps showing
      one folder. Tasks 41–43 build on it; the measurements below are the case for all four.
      - The daemon looks a session up in Claude Code's registry (`~/.claude/sessions/<pid>.json`)
        the first time it signals, and keeps the pid, the kind of host, the name and the
        desktop's `local_` id. A session missing from the registry is kept as it is today.
      - From the pid, the seam tells whether that very process still runs: the pid exists and it
        started when the registry says. A session whose process is gone stops waiting, as a
        `SessionEnd` would, and the log says so. That is the claude killed before its hook ran.
      - The first four characters of the session id go in the log, next to the project.
      - First proposed as the hook writing `<project> · <id4>` to the tty, with
        `CLAUDE_CODE_DISABLE_TERMINAL_TITLE=1` in the settings `env`. That title is now task 43,
        and in Warp only. Measured by hand once: a title written to `/dev/ttys001` held through a
        turn in Warp.
      - Built: `hooks.running` reads the registry, `platform_seam.process.started` asks the kernel
        (one `sysctl`, a fifth port), and the daemon asks every 5 s for each waiting session. A
        null seam answers could-not-tell, which keeps the signal. Verified by
        `var/desk/check_sessions.py`, against the five live registry files and with legs that must
        come back empty. At the desk on 2026-09-28: a `claude` in Warp (project-a, `ab77`, pid 71414)
        finished and was queued (`session ab77 — cli, pid 71414`). `kill -9 71414` was run at the
        desk, and at 20:03:40 the daemon said `process gone … no SessionEnd said so` and took the done
        out. `ps` says it is dead, and `var/events` has no `end` from `ab77`.
      - **The Claude desktop app, measured 2026-09-28.** A Code session run Local reports
        `com.anthropic.claudefordesktop` as its host (the transcript says `entrypoint:
        claude-desktop`), and its window is titled `Claude` for every session. No title names the
        project, so a desktop session is never watched and its `done` always cries, which is the
        loud direction (principle 7). It has no tty for a title, so the id title does not reach it.
        The app does register a `claude://` URL scheme; whether that scheme opens a given session
        has not been measured.
        **Measured the same evening:** `claude://code/continue?session=local_<id>` opens that very
        session and brings the app forward (the handler is `claudeURLHandler` in the app's
        `app.asar`, which accepts `^local_[A-Za-z0-9-]{1,64}$`). Opened twice from VS Code, and both
        times it landed on project-a's `Oi`, confirmed at the desk. The `local_` id is not the hook's
        `session_id`. The app keeps one record per session in `~/Library/Application Support/Claude/
        claude-code-sessions/<account>/<org>/local_<id>.json`, whose `cliSessionId` is the hook's
        `session_id` (`fb3d1da5…` ↔ `local_6b701462…`). This is a private, undocumented format.
        Its `lastFocusedAt` does **not** say which session is on screen. Opening the link twice
        left it at creation (18:51:21). Clicking `CM-468` did not touch that file, and clicking
        back to `Oi` moved `Oi` to 18:58:28. So while `CM-468` was on screen, `Oi` still read as
        the latest focused.
      - **The fold bites across apps, seen the same run.** project-a in Warp (`7d42`) and project-a in
        the desktop app (`fb3d`) folded into one entry whose host is `rows[0]`, Warp's. B at
        18:53:14 raised `'project-a · 7d42'` for a `done` the desktop session had just sent. Matching
        by the id fixes this, and it is the case for doing so beyond telling Terminal windows apart.
      - **Claude Code's own registry joins the hook to a process** (checked here on 2026-09-28).
        `~/.claude/sessions/<pid>.json` has one file
        per live claude, and each carries `sessionId` (the hook's `session_id`), `entrypoint`,
        `name` (VS Code's tab name) and, for the desktop app, `hostSessionId` (the `local_` id the
        deep link takes). From the pid we get the tty and the environment.
      - **Warp selects a tab by URL, measured 2026-09-28.** Each Warp shell has
        `WARP_FOCUS_URL=warp://session/<uuid>` in its environment. `open` on it, with another Warp
        tab in front and VS Code frontmost, raised Warp on that very tab. Two sources agreed: the
        front title (`project-a · 7d42`) and the desk. Another app studied does not use it.

- [x] **41 — One entry per session, not per project.** Undoes task 20's fold now that two
      sessions of one folder can be told apart (task 40). It fixes the cross-app fold above: B
      raised Warp for a `done` the desktop app had sent. Check the `deduplicated()` case task 20
      closed before building.
      - Built: `Queue` builds one `Entry` per session, and the queue, `Attention`, the ladder's
        key, `LookAway` and the menu are all keyed by session. A prompt or an end in one session
        answers that session only, so the hold on its neighbour survives. The menu shows
        `<project> · <id4>` only when two lines share a folder. Verified by
        `var/desk/check_queue.py`, `check_attention.py`, `check_watching.py`,
        `check_menubar.py` and `check_criteria.py`, each with a mutant that folds by folder again.
        At the desk on 2026-09-28: project-a in Warp (`c431`) and project-a in the desktop app (`fb3d`)
        both finished, and the menu showed `project-a · c431` and `project-a · fb3d` as two lines. B at
        20:35:31 attended `c431` only (`attending done · c431 (2 left)`) and raised Warp, and
        `fb3d` stayed queued. The log and the desk agreed.
      - **The `deduplicated()` case stays closed.** The queue is keyed by the hook's
        `session_id`, not by a pid, so a resume that leaves two registry files for one session is
        still one entry, and `hooks.running` takes the newer file (883879d). A resume under a new
        id leaves the old entry behind only until its claude exits, and task 40 drops it then.
      - Watched is still per folder until task 43: two sessions of one folder in one app both
        read as watched, and B still raises the app, not the session, until task 42.

- [x] **42 — B raises the very session.** Desktop: `claude://code/continue?session=<local_ id>`.
      Warp: the `WARP_FOCUS_URL` read from the claude's environment. Terminal: the tab whose `tty`
      is the claude's, over AppleScript (a one-time Automation consent, and refusal is said in
      words, principle 7). VS Code: as today.
      - Built: the hook forwards `WARP_FOCUS_URL` as a fourth field, and `hooks.parse` keeps it
        only in Warp's own shape. `Running.deep_link` is built only for a `claude-desktop` entry
        with a `local_` id. `daemon.ways` lists the routes best first (link or Warp address, then
        Terminal's tab by tty, then the window, always last), and `daemon.reach` tries them in
        order and says every miss. The seam gained `Focus.url`, `Focus.tab` and `Process.tty`
        (libproc `e_tdev` at offset 108, checked against `ps` for six live claudes). Verified by
        `var/desk/check_raise.py` (five mutants, all caught) and `check_sessions.py`.
      - At the desk on 2026-09-28: the desktop app opened the exact session each time (21:05:51
        `Oi`, 21:09:53 `Teste`, then `workspace` beside it), and Warp came forward on project-a's
        tab by its address (21:11:24, `Warp opened warp://session/13c2…`). Confirmed at the desk
        that each one landed on the right session. VS Code still raised its window as before.
      - Terminal.app, at the desk the same evening: two tabs, a claude in each (`2031` on
        `ttys003`, `19f9` on `ttys002`, by `ps`). B selected each one's own tab
        (21:25:43 `ttys002`, 21:25:46 `ttys003`), and that was confirmed at the desk. The first two raises
        (21:25:33 and 21:25:38) came forward `via Accessibility`, which is task 38's fallback
        seen doing the work for the first time.

- [x] **43 — Watched means that session, not that folder.** VS Code: the title is
      `<name> — <folder>`, with the name from the registry. Terminal: the selected tab's `tty`.
      Warp: the daemon writes `<project> · <id4>` to the claude's tty, which holds only with
      `CLAUDE_CODE_DISABLE_TERMINAL_TITLE=1` set in Warp shells. That line goes in the desk's own
      `.zshrc`, added there directly. The desktop app stays never watched. Writing to a tty wobble
      does not own is a new surface, so read against `constitution.md` before building.
      - VS Code, built: a Claude tab in front (the title's segment before the last ` — `) is
        watched only for the session that owns it; a file in front keeps the folder rule, since
        Claude may sit beside it (`tasks.md — wobble`, measured 2026-09-28). A session owns its
        registry name and its transcript's latest `custom-title` and `ai-title`
        (`hooks.Titles`, read incrementally): the registry alone said `wobble-b8` for a tab that
        showed `Session planning`. B raises the window, then opens
        `vscode://anthropic.claude-code/open?session=<id>`, only once that window came forward,
        because the extension opens a second copy in a window that does not hold the tab.
        Verified by `check_watching.py`, `check_sessions.py` (the titles against a whole-file
        scan of the real transcripts) and `check_raise.py` (seven mutants, all caught).
      - VS Code, at the desk on 2026-09-28: two tabs in one window, `entendi - teste 19` (`4f6f`)
        and `Session planning` (`400a`). With the twin in front, `4f6f`'s done cried (22:06:58
        and 22:25:03); B at 22:25:07 stopped at VS Code's one-time "Allow … to open this URI?"
        prompt, and B at 22:25:24 selected `4f6f`'s own tab, with no second one opened (22:25:33
        `you were there`). Confirmed at the desk. Terminal and Warp are still owed.
      - Warp, built: the daemon names a Warp session's tab `<project> · <id4>` on its first
        hook line (`Process.title`: one OSC 2 on the claude's tty, non-blocking, refused for a
        control character or a tty not this user's), again after a resume, and says it or says
        why not. `Entry.in_window` applies the tab rule to Warp's whole title. It holds only with
        `CLAUDE_CODE_DISABLE_TERMINAL_TITLE=1` in Warp shells, now in the desk's own `.zshrc`.
        Verified by `check_watching.py`: Warp's twin rows, a mutant with VS Code's rule only
        (caught), and the real seam on a pty of its own, read back byte for byte.
      - Warp, at the desk on 2026-09-28: every Warp claude was named on its first line (`d711`,
        `4abf`, `1a1a`, `d17a`, 23:11:22–23:15:37), in split panes of one tab, and the window
        title followed the focused pane. B opened each pane's own address and landed on it.
        Confirmed at the desk. The `focused` line's title lagged one pane twice (23:16:17,
        23:16:26): it is read as Warp comes forward, before the pane switches.
      - Warp's twins, at the desk on 2026-09-29, with the daemon started after this session's
        last reply so no `4f6f` done sat on top: two panes in project-a, `5e82` asked for a short
        poem and `14d9` for a long one, with `14d9`'s pane in front. `5e82`'s done cried at
        08:48:43 with `project-a · 14d9` in front; on its own pane at 08:48:55 it was `not
        signalling`; back on the twin, `signalling` again at 08:49:12, 3 s after.
      - Warp, left as is on 2026-09-29: a tab with no claude in the same folder still counts
        as looking, by the folder rule, so a done stays quiet there (project-a's `~/dev/project-a`
        tab, 10:39:29). The choice at the desk was to live with it and change it only if it gets in the
        way. Making only the named tab count would make a shell pane beside a claude cry.
      - Terminal, built: `Frontmost.tab_tty` asks Terminal for `tty of selected tab of front
        window` (0.1 s, measured 2026-09-29) in a thread, at most once a second, only while
        Terminal is in front. Each `cli` claude's tty comes from `process.tty`. There a claude
        tab in front is that session only, whatever its title says. A tab with no claude, or
        a tty that could not be read, keeps the folder rule. Verified by
        `var/desk/check_watching.py`: nine rows, three mutants caught, and the real seam
        against Terminal (a tty that is one of its tabs, with `ps` finding processes on it).
        `check_criteria.py` caught a first build whose new `tabs` hid the daemon's own, which
        crashed B.
      - Terminal's twins, at the desk on 2026-09-29: two project-a claudes in two Terminal windows,
        `e7cd` on ttys000 and `a423` on ttys002. Their titles differed only in the running
        child (`caffeinate` / `node`), so the folder rule alone would have kept both quiet.
        `e7cd`'s done: `signalling` at 10:53:56 with ttys002 in front, 3 s after, and it cried.
        `not signalling` on ttys000 at 10:54:11. `signalling` again on ttys002 at 10:54:19.
        Quiet on ttys000 at 10:54:21. The first try was held behind this session's own `4f6f`
        done (principle 8), and the daemon was restarted at the desk to clear it.
      - Terminal and Warp from wobble.app (task 50), at the desk on 2026-09-30. Now it is
        *wobble* that asks Terminal for its tab. So macOS asked once for Automation of Terminal,
        the first time Terminal came in front (14:39:49), before any B. Until the answer came,
        the log said `CANNOT SEE TAB … a consent dialog may be waiting`. Once it was allowed,
        14:40:13 read `Terminal's tab on ttys001`. B on project-a's done (9a46) at 14:40:49 and
        14:40:52 `selected its tab on ttys001`. In Warp, `0688` got the tab name `dev · 0688`
        on its first line (14:41:14). B at 14:41:23 opened its `warp://session/…` and landed
        with `dev · 0688` in front, with no dialog. Both confirmed at the desk. Not seen this
        time: the done staying quiet on its own Terminal tab.

- [x] **44 — The next signal waits 3 s after a session closes.** Asked at the desk 2026-09-28, so
      the one closing a tab does not take the next cry for the tab they closed. Every close arms
      it (a `SessionEnd`, or a claude found gone), pending or not, and it re-arms on each one.
      - Built: `after_end.wait_s` in `config/signals.json`, loaded as `Ladder.after_end_s`. The
        daemon holds the beat until the later of this and the after-prompt hold, and the
        `holding` line names which one. Verified by `var/desk/check_ladder.py` (the value, and a
        negative one refused) and `check_criteria.py` (task 44's episode, which fails with the
        wait at 0).
      - At the desk on 2026-09-28: workspace's desktop session closed at 21:20:46, project-a's
        `done` said `holding … a session just closed, so it waits 3s`, and it cried at 21:20:49.
        Confirmed at the desk. `check_daemon.py` was not re-run: it refuses to judge while
        wobble's own window is in front, and it was.
- [x] **45 — A closed Warp tab stops signalling within seconds.** Seen at the desk on
      2026-09-29: after a Warp tab with a claude was closed, its session kept crying and held the
      queue for about 30 s. The cause is Warp, not the claude. Warp's `terminal-server` keeps a
      closed tab's shell alive for its undo-close grace period (`general.undo_close.grace_period`),
      then ends the shell and the claude together, and the `SessionEnd` comes that same second
      (09:16:20 for 6672). A first build treated a claude with no tty as closed (a1e2499). It
      never fired, because the tty stays for the whole grace period, so it was reverted. The fix
      is Warp's own setting: a short grace period, set at the desk in Warp's settings. It is not
      wobble code. Asking Warp whether the tab still exists (its `session.list` / `pane.list`
      API, found in the binary) is left for later.
      - At the desk on 2026-09-29: the grace period was set to 3 s in Warp's settings, which
        wrote `[general.undo_close] grace_period = 3` to `~/.warp/settings.toml`. project-a's a482
        had a `done` pending, the tab was closed, and `session ended` came at 10:40:05. The last
        `in front` line was at 10:39:59. Confirmed at the desk.

- [x] **46 — B again on a lone signal asks for its window, and makes no sound.** Seen at the desk
      2026-09-28, task 38 (18:41:26–18:41:37): with one entry and its window not come forward,
      pressing B again was criterion 7's skip. The signal was let go, cried at once, and the next B
      took it back, so every B pressed because the window did not come made a beat. Agreed at
      the desk 2026-09-29.
      - Built: `Attention.dismiss` with nothing else pending keeps the entry it holds and returns
        `Taken(again=True)`. The daemon says `raising … again — nothing else is waiting` and raises
        the window as on the first press. The hold keeps the first press's `since`, so the snooze
        is not pushed back. With another entry waiting, B skips exactly as before. Criterion 7's
        text in `spec.md` carries the change, dated.
      - Checked: check_attention's task 46 rows, with two mutants (the pre-46 skip, and a retry that
        restarts the snooze), both caught. check_criteria's episode: three presses on one `needs`,
        two `raising … again` lines, nothing let go, no beat after the first press, three raise
        attempts. Run against the old `dismiss` it fails four rows out of four: 1 let go, 1 beat,
        2 raises.
      - At the desk on 2026-09-29, with the ball: 4f6f's `done` beat at 11:48:48, and B took it at
        11:48:58, with VS Code coming forward. Three more presses at 11:49:04, 11:49:17 and
        11:49:22 each logged `raising done · 4f6f again — nothing else is waiting`, and each was
        followed by `focused`. There was no `let go` and no beat after 11:48:48. The prompt
        resolved it at 11:49:25. Confirmed at the desk ("it's working").

- [x] **47 — A restart brings back what was pending, quietly.** Found 2026-09-29 while working
      through the owed desk items. The daemon started at the end of `var/events`, so a quit threw
      away everything still pending, while the quit line promised the next run would bring it back.
      DESK-CHECKS Part B step 15 said the same. Measured in a sandbox: `done` pending, SIGTERM,
      restart, and `queue` came back empty. Only `--replay` brought it back, and it did that by
      playing the whole file. Agreed at the desk 2026-09-29: bring them back but play nothing.
      After a restart you go back to what matters yourself. It is fine if a few stay untouched
      all afternoon.
      - Built: the daemon reads the file from the top and replays it silently (`daemon.recall`).
        It keeps only sessions whose claude is still running in Claude Code's registry, and marks
        them quiet (`Queue.hush`, `Waiting.quiet`). A quiet entry has no sound and no light. It is
        not counted in the title (`Queue.live`). The menu lists it under a separator of its own,
        as `from before the restart` (`Status.QUIET`). B reaches it only after every live entry
        (`Queue.top(quiet=True)`, principle 2). A snooze puts it back still quiet. There is no
        expiry: a new event from that session makes it live, and a prompt or a close removes it.
        The log says `restored …` for each one, then `restart  N back from before it (quiet)`
        with how many were dropped. The quit line and step 15 now say what happens.
      - Checked: a third table in check_queue, with five mutants (quiet decided by kind, `top`
        handing out a quiet entry, quiet ones counted, `add` keeping the quiet flag, a snooze waking
        it). Task 47 rows in check_attention (B reaches the quiet one last, a snooze keeps it
        quiet, the standing says so), with three mutants. check_menubar's separator rows, with two
        mutants. check_criteria's episode: four sessions in the file, one kept, one answered, one
        whose claude is gone, and six rows. Run against the code before task 47 it fails four of
        the six, and it fails the same four with `hush` made a no-op.
      - At the desk on 2026-09-29: with four pending, the pre-47 daemon quit at 13:16:39, and the
        new one logged seven `restored` lines at 13:16:41, then `restart  7 back from before it
        (quiet)` and `10 dropped: their claude is not running`. Three of the seven (otherproject fd2d,
        wobble 400a, project-a a423) were pending from the morning, lost by the restarts before this
        task. Their claude was still open. The title showed no count, and the menu listed them all
        as `from before the restart`. The ball connected at 13:17:11 and played nothing. Only
        `lights off` on connect. 4f6f resolved at 13:16:45, `you were there`, because its window
        was in front. Looking still resolves a quiet entry.
      - Left open: a resolution by looking (`you were there`) is kept in memory only, never in
        `var/events`. So a `done` read and not answered comes back quiet after the next restart.
        Looking at it resolves it again. Not fixed.
- [x] **48 — Measure what a `.app` of its own changes, before building one.** Agreed at the desk
      2026-09-29, after the constitution's amendment of the same day (a locally built `.app` is not
      a release). Today every permission is filed under whatever launched the daemon: at this desk,
      VS Code's terminal (pid chain read 2026-09-29: daemon, zsh, Code Helper, Code). That is why
      Part B step 8 was deferred, and why a rebuilt venv can lose the grant (ROADMAP, "wobble as an
      app"). Three questions, answered by a probe run from a hand-built `/Applications/wobble.app`,
      with nothing in `src/` changed:
      1. Are Accessibility and Bluetooth filed under wobble, rather than VS Code or `python3.12`?
      2. Do they survive the bundle's Python changing, with the bundle itself byte for byte the same?
      3. Can the front window's title be read with no Accessibility at all (`Frontmost.title` is
         what "watched" rests on)?
      - Built: `var/desk/app_probe/` — `probe.py` writes one JSON line per run (who launched it,
        Accessibility, the front title read or not, window names, Bluetooth's authorization), and
        `build.py` writes `/Applications/wobble.app` (`local.wobble`, `LSUIElement`,
        `NSBluetoothAlwaysUsageDescription`, signed ad hoc). No title is ever recorded.
      - Reference leg, from VS Code's terminal (13:57:54): everything granted, as it must be.
      - Leg 1, a shell script as the bundle's executable (14:00:40): everything granted and nothing
        asked, which a fresh bundle cannot be. tccd's `AUTHREQ_ATTRIBUTION` (second source) says
        why: the script ran as `/bin/sh` (`com.apple.sh`), and the Python it started was held
        responsible for itself (`python3-5555…`, an identifier derived from Homebrew's binary),
        which already held every grant from earlier work. So a script is not enough, and a
        Python upgrade is what loses the grant today.
      - Leg 2, `launcher.c` compiled into the bundle, `posix_spawn` and wait (14:02:05): tccd
        names `responsible=local.wobble` 13 times. Bluetooth asked as "wobble", with the plist's
        sentence, and went 0 to 3 when it was allowed at the desk. Accessibility false, the front title
        unreadable, window names 0 of 14 (no Screen Recording). **Question 1: yes, with a Mach-O
        of the bundle's own.** **Question 3: no.** Without Accessibility the title cannot be read,
        and the only other road is Screen Recording, a heavier thing to ask for. wobble asks for
        Accessibility once.
      - Accessibility granted by hand at 14:07 (`--prompt`, the system's own dialog, as "wobble").
        14:09:09: trusted, and the title read. The same bundle with `/usr/bin/python3` (Xcode's
        3.9, another binary altogether): still trusted, and tccd says `accessing=com.apple.python3`,
        `responsible=local.wobble`. **Question 2: yes, the grant follows the bundle, not the
        Python.**
      - Found on the way, question 4: the ad hoc grant is pinned to the launcher's exact bytes.
        Rebuilt with `-O0` (14:09:38): Accessibility false. Rebuilt as before, the same bytes
        (clang is deterministic here, `8577ec390fdf` both times) (14:09:42): true again, with no
        prompt. So the launcher must stay small and rarely changed, with all of wobble outside
        the bundle, so that a `git pull` never touches a grant. The other way out is a stable
        signing identity, which would pin the grant to the certificate instead of the bytes.
- [x] **49 — A question answered where it was asked stops signalling.** Seen at the desk
      2026-09-29 13:55: toolkit's needs kept crying after the desk had answered its
      AskUserQuestion. A permission prompt or an AskUserQuestion is answered in place, with no
      `UserPromptSubmit` behind it, so until then only the next Stop, prompt or SessionEnd took the
      needs out. Now the tool's own `PostToolUse` (or `PostToolUseFailure`, for a Bash you allowed
      that exits 1) answers it, as the word `answered`.
      - Measured first, on a `claude -p` in the scratchpad with only its own hooks loaded
        (2.1.160): both hooks fire, a subagent's tool carries `agent_id` and the main thread's does
        not, and the keys run `session_id … agent_id … tool_name, tool_input`. The `Notification`
        carries no tool id, only "…permission to use AskUserQuestion" in its message (`Send
        Message` for `SendMessage`, in var/events), so the tool's name is the match.
      - Answered only by the same tool, from the main thread, and only a `needs` (`hooks.answers`,
        `Attention.replied`). A subagent's question looks like the main thread's, so its tools
        are not taken as answers. Left as before, waiting for the next Stop or prompt: an MCP tool
        whose shown name is not its `tool_name`, a subagent's own question, a refused permission,
        and a permission prompt that names no tool (`asks-04`). That is the loud direction.
      - `hook_event.sh` forwards three fields of an `answered`, not the payload. It carries the
        tool's whole output once per tool call (682 on 2026-09-28), which would be cut mid-JSON at
        8000 and said as an unreadable line. Only the text before `tool_input` is read.
      - A needs restored after a restart can still be answered (`recall` hands back what was
        asked).
      - Checked: `check_hooks` runs real payloads (`ran`, `failed`, `sub`, `asks-03..05`) through
        the real script in the sandbox, with five mutants caught, one the script reading past
        `tool_input`. `check_attention` has two mutants caught. `check_criteria` has two episodes,
        live and across a restart, and both daemon mutants (the answer ignored, the restart
        forgetting what was asked) fail them. All 14 checks pass.
      - Desk, 2026-09-29, after `tools/install_hooks.py`. Running sessions picked the new hooks up
        with no restart (4f6f, 9d03 and cbb4 wrote `answered` lines). VS Code passed: cbb4's needs
        at 15:11:28, B at 15:11:34, "answered where it asked" at 15:11:39. The Claude app passed:
        4961 (claude-desktop) needs at 15:19:29, B at 15:19:40, "answered where it asked" at
        15:19:42. Both times B was pressed before the answer, so the desk saw the held entry
        released. The queued entry dropped with no B is covered by `check_criteria` only.
      - Known limit, Warp: the CLI's `Notification` there says only "Claude needs your
        permission", 3 of 3 times, so `asked` is empty and nothing matches (session 0368 at the
        desk). It waits for the next Stop or prompt, as before. Warp is the least-used host.
        If it matters later, the registry's `status` field (`~/.claude/sessions/<pid>.json`,
        present on this Mac and checked here on 2026-09-29) is
        the lead to measure, not a looser match.
- [x] **50 — wobble as an app, built from the repo.** Asked at the desk 2026-09-29, after task
      48's measurement, and built while away from the desk ("do it from start to end"). Nothing was
      installed and the app was never launched: the probe of task 48 is still what sits in
      `/Applications/wobble.app`, with its grants.
      - The bundle (`tools/build_app.py`, `local.wobble`, `LSUIElement`, the Bluetooth and Apple
        events sentences, signed ad hoc). Its executable is `tools/app/launcher.c`, with only the
        repo's path baked in. It `posix_spawn`s `tools/app/start` (task 48: a Mach-O of the bundle's
        own is what macOS holds responsible), passes SIGTERM, SIGINT and SIGHUP on, and, when the
        daemon ends by itself (not 0, and not a signal it passed on) or cannot be started, puts up
        an alert naming `var/app.out` (principle 7: with no terminal, a silent stop looks like
        nothing to do). Everything that may change is in `tools/app/start`, a shell script in the
        repo, so a `git pull` changes no byte macOS checks. The Info.plist carries no build number
        for the same reason. `build_app.py` prints the code directory hash it signed and says
        whether it is the installed one's (grants carry over) or new (macOS asks again);
        `--reset-grants` clears the old entries with `tccutil`.
      - One daemon per events file (`claim` in `src/daemon.py`): an `flock` on `daemon.lock`
        beside the events file, which the kernel lets go of when the process dies. A second
        daemon says `ALREADY RUNNING`, with the first one's pid, and exits 1, so a Finder launch
        next to a terminal daemon ends in the launcher's alert rather than in two daemons
        answering every event (DESK-CHECKS Part D item 9, open since task 12). A lock that cannot
        be taken for another reason is said (`LOCK NOT HELD`) and the daemon runs.
      - `--ask-access` (`Focus.ask`, the macOS seam): at startup, `AXIsProcessTrustedWithOptions`
        with the prompt, so the system's own dialog appears once, under wobble. Only the app's
        start script passes it: from a terminal the dialog would be filed under the terminal.
      - Checked: `var/desk/check_app.py`, 28 rows. Two builds give the same hash, the plist keys.
        The launcher against a start script that only reports: arguments passed, its own child,
        SIGTERM reaching it, no alert on a clean exit or a passed-on signal (trapped or not), an
        alert naming the status on an exit of 3, and one on a missing start script. Four mutants
        of `launcher.c` (no passing on, never alerting, alerting on a clean quit, alerting after
        passing a signal on) are caught; the last one survived until a leg where the daemon dies
        of the signal instead of trapping it was added. The real start script and daemon through
        a launcher, in a sandbox: `var/app.out` fills, `--ask-access` answers, the lock file
        exists, a second one is refused and alerts, SIGTERM quits through the daemon's door, rc
        0. The lock on bare daemons, and a mutant that never refuses, caught. Attribution: the
        same launcher, shell and Python opened by the Finder (`open`) under `local.wobble.check`
        is not trusted, and tccd's `AUTHREQ_ATTRIBUTION` names `responsible=local.wobble.check`
        past the shell script; run from VS Code's terminal (the reference leg) it is trusted.
        No dialog is ever asked for in the check. All 19 checks pass.
      - Not done, and each one wants the desk: installing (`build_app.py --install`) and the
        first launch's two dialogs; starting at login (`SMAppService` or a LaunchAgent pointing at
        the bundle); saying a missing permission somewhere other than the log, now that there is
        no terminal (the menu bar is the one surface, principle 2).
      - Desk, 2026-09-30, DESK-CHECKS Part B step 20. Installed with `--reset-grants`. At the
        first launch (13:32:52) both dialogs named *wobble*, and both were allowed. From 13:34:13
        on, every relaunch said `accessibility granted` and asked nothing. With the app running,
        a terminal daemon was refused with `ALREADY RUNNING` and the app's pid, and the app kept
        running. The other way round, with the terminal daemon holding the lock, the app wrote
        `ALREADY RUNNING` at 13:37:18 and showed *wobble stopped*, `exit status 1`. *Quit wobble*
        from the menu gave no alert and left no launcher behind. A rebuild with nothing changed
        (13:37:06) kept cdhash `46712496…` and said `the same bytes as before`, and the next
        launch (13:38:53) asked nothing.
      - Desk, 2026-09-30, step 8, with *wobble* unticked. After the relaunch, 13:41:08 said
        `NO ACCESS YET` and `CANNOT SEE FOCUS`. B at 13:41:48 and at 13:41:50 aimed each time,
        wrote `NOT FOCUSED … so no window was raised`, and the queue and the menu went on
        working. Ticked again, 13:42:44 said `accessibility granted`.
- [x] **51 — Leaving the held one's window ends the hold.** *Its rule was replaced by task 52 the
      same day. What stays is `Entry.here` and `HeldAway`.* Seen at the desk 2026-09-29: B took
      workspace's `done` (4961, the Claude app) at 15:20:05, and the desk went back to VS Code.
      The hold was the whole snooze wherever the desk was, so project-b's `needs` (df6c, Warp), queued at
      15:20:47, stayed silent until B was pressed again at 15:22:52. By 15:22:11 four signals waited
      behind the held `done`. Agreed at the desk the same day: leaving the window ends the hold.
      - The rule (`Attention.left`, `Why.AWAY`): once the window B raised has been in front, being
        away from it for the look-away grace (`look_away.wait_s`, 3 s) puts the entry back where it
        was, as the snooze does (`queue.restore`), and the queue speaks again, a `needs` first. A
        session that signalled again while held is not restored: the newer entry stands. A glance
        away and back restarts the grace. A raise that never came forward ends nothing: the hold
        waits for the snooze, as before (`HeldAway` in `daemon.py`, which is reset on every B).
      - The desktop app counts at app level (`Entry.here`, `DESKTOP`, the bundle id from 21 hook
        lines in var/events): its window is titled `Claude`, never the folder, so `in_window`
        could never see it. This applies to a hold only. A signal in the queue is still never
        "watched" in the desktop app, which stays the loud choice.
      - Checked: `check_attention` (left with nothing held, the order after, a session that
        signalled again) with two mutants caught, leaving changing nothing and letting go without
        a restore. `check_watching` (`here` for the desktop app and VS Code, and `HeldAway`'s
        grace, glance and reset) with five mutants caught. `check_criteria` runs the real daemon
        with the front window scripted (`var/desk/scripted_front.py`, nothing on screen moves):
        a `done` from the desktop app held, a `needs` queued behind it and silent, a glance away,
        then a leave. One `left` 3 s after the leave, the `needs` beating first, the `done` back
        waiting its turn. Both launcher mutants (the desktop app never here, a hold nothing ends)
        fail it. All 18 checks pass (`check_daemon` run last, with another window in front, as it
        asks).
      - Desk, 2026-09-29, the daemon restarted at 15:48:47. The Claude app passed: workspace's
        `done` (00b5, claude-desktop), B at 15:52:27 with `Claude` in front, VS Code at 15:52:32,
        `left` at 15:52:35, and the ball beat the same second. VS Code passed before it, unasked:
        wobble's own `done` (4f6f) was left at 15:49:54 (for another app) and at 15:51:31 (for the
        Claude app), 3 s after each leave, and beat again both times.
- [x] **52 — A `needs` speaks over the hold; the held one keeps its snooze.** Asked at the desk
      2026-09-29, right after task 51 passed at the desk. That rule put the held signal back in
      the queue 3 s after its window was left, so the one already seen cried again:
      "the idea is not to hold anyone, only to warn". B means *seen, leave it with me*. The
      fault 51 was fixing (project-b's `needs` silent behind a held `done`, 15:20:47 to 15:22:52) was
      the hold gagging the whole queue, not the hold lasting.
      - The rule (`Attention.current`, `set_away`): while something is held, the top of the
        queue is signalled only if it is a `needs`. Over a held `done`, it speaks at once. Over a
        held `needs`, it speaks once you have been out of that window for the look-away grace
        (3 s), so an answer in progress is not interrupted. The `done`s behind stay quiet. The
        held one keeps its snooze wherever you are, and a B on the `needs` hands it back to the
        queue in its place (criterion 7, "the one before comes back without trouble," agreed at
        the desk the same day). The daemon says it once, as `over the hold`.
      - `Attention.left` and `Why.AWAY` are gone. `HeldAway` no longer waits for the window to
        have been in front: a raise that never landed is not somebody answering there.
        `Entry.here` stays, for the held `needs` in the desktop app.
      - Already true before this, and checked in the log: with nothing held, a `needs` takes
        the floor from a crying `done` the same second (13:28:58 on 2026-09-29, 17:35:10 on
        2026-09-28), because `pending()` puts a `needs` first.
      - Checked: `check_attention`, 11 rows with four mutants caught (a needs never over the
        hold, a done over it too, a needs over a held needs you are at, a new hold starting
        away). `check_watching`, `HeldAway`'s grace with or without a raise, with three mutants
        caught. `check_criteria` runs two scripted episodes on the real daemon, a held `done`
        and a held `needs` in the desktop app, and four launcher mutants fail them: pre-52,
        task 51's return, a needs over a held needs, the desktop app never here. All 18 checks
        pass (`check_daemon` run with another window in front).
      - Desk, 2026-09-29, the daemon restarted at 16:15:45. workspace's `done` (ac27, the Claude
        app) was taken at 16:21:26. The `needs` was this session's own AskUserQuestion (4f6f),
        queued at 16:21:55: `over the hold` at once, but quiet, since the desk stayed in its
        window. It beat 3 s after leaving (16:23:08) and went quiet again whenever the desk came back
        (16:23:47, then away at 16:23:50 and beating at 16:23:53). ac27 stayed `attending` all
        along and never cried. B took the `needs` and put ac27 back in its place. The answer at
        16:24:19 released it, and ac27 spoke next. "Right on," noted at the desk.
      - Seen on the way, and consistent with the rules: at 16:23:39 a B on the held `needs`
        skipped to ac27 (criterion 7), and the `needs` it put back beat over the `done` in the
        same second. A needs is never left behind a done, even one you skipped. Not seen at the
        desk: a second `needs` waiting over a held one. `check_criteria` covers it.
- [x] **53 — An answer given where it was asked holds the next beat, as a prompt does.** Seen at
      the desk 2026-09-29, right after task 52's run: this session's AskUserQuestion (4f6f) was
      answered at 16:24:19, and workspace's `done` (ac27), released by that answer, beat the same
      second. "now that typing finished, workspace played right after" (noted at the desk). Answering in
      place is a hand at the keyboard as much as a prompt is, but task 49's `answered` path never
      armed the five seconds after typing (task 25); only `prompt` did.
      - The rule: an `answered` line that answers the question arms `typed_at` exactly as a prompt
        does (`after_prompt.wait_s`, 5 s, with the same burst rule). A line that does not answer it
        arms nothing.
      - Checked: `check_criteria`, a `needs` answered in place with another repo's `done` behind
        it. The `done` says `holding … you just typed` and beats 4-7 s after the answer. The
        reference leg, the daemon without the fix, beats the same second, which is the desk fault,
        and fails both rows. All 18 checks pass (`check_daemon` run with Finder in
        front).
      - Desk, 2026-09-29, in use after the restart: "1 ok" (noted at the desk).
- [x] **54 — Out of the held window, the hold holds nothing back; what returns goes last.** Asked
      at the desk 2026-09-29, while testing task 53. From 16:47:53 project-a's `done` (cbb4) was held
      while a background run went on, with nothing to do in it, and project-b's `done` (da42) stayed
      "waiting its turn" behind it. B after B then swapped the two (16:48:08, 16:49:10, 16:49:29),
      because the one let go went back into the place it had, ahead of the other. The rule, as put
      at the desk: "B focuses, attention is given, then leaving, snooze 5 min, it does not hold up new dones / needs,
      it goes to the end of the queue". A deliberate "quiet until it speaks again", like the rows
      from before a restart, was discussed and left for later.
      - The rule (`Attention.current`): once you have been out of the held one's window for the
        look-away grace (3 s, `HeldAway`), the top of the queue speaks whatever its kind. At the
        window, task 52 stands: a `done` waits, and a `needs` speaks over a held `done`. The held
        one keeps its snooze. The daemon says `over the hold … so it holds nothing back`.
      - What comes back goes last (`Queue.restore(at=now)`): the snooze and a skip re-stamp the
        `since` it returns with, so it rejoins behind what waited meanwhile. `since` orders the
        queue and nothing else. A `needs` is still ahead of every `done`. The log says `let go
        back in the queue, at the back` and `snooze came back after Ns, at the back of the queue`.
      - Checked: `check_attention`, 6 new rows (away from a held `done` or `needs`, back again,
        the snooze and a skip going last, a `needs` at the back still first), with two mutants
        caught: task 52's rule, and returning where it was. Three rows that claimed "in the place
        it had" passed only because a `needs` sorts first, and now say that. `check_criteria`
        runs a scripted episode on the real daemon: a `done` held in the desktop app, another
        repo's `done` quiet while the app is in front, beating 2-4 s after the leave, the held one
        never crying. Launcher mutant `needs-only-when-away` fails it. 17 checks pass
        (`check_daemon` asks for another window in front). Two runs were disturbed from outside:
        `check_watching`'s isolation probe raced a live hook writing to `var/events` (no test line
        landed there, and it passed on the rerun), and a sandbox daemon was muted mid-run from its
        menu bar icon at 17:34:14 (rerun clean).
        `check_daemon` passed after, so all 18 do.
      - Desk, 2026-09-29, in use: B on project-b's `needs` (5df2) at 18:09:13, and project-c's
        `needs` (8662) spoke over it at 18:09:16, `holds nothing back`. At 18:09:46
        toolkit's `done` (9d03) did the same over a held `needs`. Working as built, and
        not what was wanted at the desk over a `needs`: "the ideal is that resolving one needs
        lets the other start; the only thing a needs waits for is another needs". Task 55.
- [x] **55 — A held `needs` holds everything until it is answered.** Asked at the desk
      2026-09-29, from the desk run of task 54 above: "B on a needs, the other one starts. The
      ideal is that resolving one needs lets the other start." Leaving a held `needs`'s window
      now frees nothing, `needs` or `done`. It ends as any hold does: answered where it asked or
      prompted (then the typed hold, 5 s), skipped with B, or the 5-minute snooze.
      - The rule (`Attention.current`): a held `needs` returns `None`. Over a held `done`, task 54
        stands: a `needs` speaks at once, and anything speaks after 3 s out of its window. So
        `set_away` now matters only for a held `done`, and the daemon never says `over the hold`
        over a `needs`.
      - Checked: `check_attention`, two rows flipped (a `needs` and a `done` away from a held
        `needs` now wait), the new-hold-starts-at-its-window row rebuilt on `done`s so it still
        catches `AwayLeaks`, and 5 new rows (silent at the window and away, the answer ends it and
        the next `needs` speaks, the snooze hands over). Mutant `AwayFreesAHeldNeeds` (task 54's
        rule) caught. `check_criteria`'s held-`needs` episode rewritten: a desktop-app question
        held, another repo's `needs` quiet at the window and for 4 s after leaving, then speaking
        5 s after the answer (the typed hold), and no `over the hold` line. Launcher mutants
        `away-frees-needs` and `needs-only-when-away` fail it. `desktop-never-here` moved to the
        held-`done` episode, whose leave is now 4.5 s after the other repo's `done` so it fails
        there too. All 18 checks pass (`check_watching` first ran with nothing readable in
        front and passed once `check_daemon` had put a window there).
      - Desk, 2026-09-30, in the app. toolkit's `needs` (9d03) was held from 13:43:51 to
        13:45:10, with the desk out of its window from 13:44:21. Nothing spoke in that time, and
        the answer handed on after the 5 s typed hold. project-b's `needs` (b0ab) was held from
        13:59:18, and the next 5 minutes were spent outside VS Code. Nothing played, not even
        pending `done`s, until the snooze at 14:04:18 sent it to the back and it spoke again.
        At 13:58:11, B on a held `needs` skipped it. Of the 11 `over the hold` lines in the run,
        every one was over a held `done`, none over a `needs`. "It worked," noted at the desk.
- [x] **56 — Answering a `needs` is a catch; walking away from one is a catch that failed.** Asked
      at the desk 2026-09-30: "answering a needs plays the green of a catch — going to a needs and
      not answering plays the red of a failed catch and brings the pulse back".
      - Answering a `needs` (in place, or by a prompt in its session) plays `201`, "caught!", once.
        Taking one with B, then leaving its window for the look-away grace without answering,
        plays `206`, "broke out", once, and then its own pulse comes back until you are in its
        window again. The rest of task 55 stands: the hold still holds everything else, and it
        still ends only by an answer, B or the snooze.
      - Colours: `201` lit the ball "capture-green" (`docs/PROTOCOL.md` §6.4).
        `206` is red, confirmed at the desk; both were measured for sound, rumble and LED by an
        earlier project.
      - Muted, the same two moments are `193` and `191`, the green and red single pulses with no
        rumble and no sound (`docs/PROTOCOL.md` §6.4, 191–193). With no ball, the Mac
        plays a sound for each.
      - Built: `outcomes` in `config/signals.json` (effect, mute, tint, `lasts_s`, Mac sound),
        read by `Ladder.outcome`. The break-out fires on the edge only, and only once its window
        had been in front (`HeldAway.seen`), so a raise that never came forward is not a walk-away.
        The ball mirror lets a catch play for `lasts_s` (2.0 s, a GUESS) before the next step's
        180, and the daemon holds the next beat for as long. The banner says `a catch`.
      - Checked: `check_attention` 16 rows and 10 subclass mutants, `check_ladder` 6 rows,
        `check_ladder_refusals` 9 refusals and 10 mutants, `check_ball_worker` the linger and
        2 mutants. `check_daemon_edges` has a `catch` scenario (answered in place, by a prompt,
        another tool's answer and a `done` catching nothing, a raise never in front not breaking
        out, the break-out once with its 2 s hold and no `over the hold` line), and the ball
        scenario gets the 201. 8 `src/daemon.py` line mutants, all caught. It also found the hold
        read the clock again and said "waits 3s" for a 2.0 s catch; it now uses the loop's `now`.
      - Open for the desk: a catch plays for every answered `needs`, including an approval made
        while you watched it and it never beat. The two tints are READINGS, not measurements.
- [x] **57 — A different Pikachu cry for each `done`.** Asked at the desk 2026-09-30: "different
      sounds for each call, so it is not always the same".
      - Each `done` picks one of the new ball's own Pikachu ids — `20`–`39`, `181`, `230`, `300` —
        and keeps it for both of its beats. They need no upload
        (`docs/PROTOCOL.md` §6.5).
      - `129`, the cry uploaded to `04 3c 00` on every connect, stays the fallback: on the old ball
        `20`–`39` are only a tap, read at the desk as a fault of that unit. `213` stays
        reserved for the catch.
      - Until the settings screen can ask which ball it is (ROADMAP), the fallback is chosen by
        hand: `--one-cry`, or `done.cries` taken out of `config/signals.json`. The Mac keeps
        playing the one uploaded `.wav`, since there is no recording of the built-in ones.
      - Built: `done.cries` in the config, read by `Ladder.cries` (a list of two or more ids,
        none twice). `Signaller` picks one when a signal comes to the top, from an `rng` it is
        handed, never the last one picked; both beats and the held light carry it, and muted it
        is not played. `--one-cry`, or any `--cry` other than Pikachu's, keeps `effect`. The
        banner line `cries` says which.
      - Checked: `check_cries` 14 rows and 7 mutants, with `--one-cry` as the reference leg.
        `check_ladder_refusals` 5 refusals, 1 row and 5 mutants. `check_daemon_edges` has a
        `cries` scenario (the banner and the first beat, by default, `--one-cry` and another
        `--cry`) and 3 mutants. `check_criteria` runs with `--one-cry`, since its rows count 129.
      - Open for the desk: whether the new ball plays all 23 at a volume worth hearing, and
        whether 129 plays on it at all (`docs/PROTOCOL.md` §6.5 found 110–129 silent on a
        fresh new ball, before any upload of ours).
- [x] **58 — The menu bar item is our own ball, and it does what the ball does.** Asked at the desk
      2026-09-30: "the same pulse that goes to the ball, the sound, goes to our own in the menu".
      - A ball drawn in code, never Nintendo's art: a ripped game asset for the 3D model
        stays out of this repo (CLAUDE.md). Its centre shows the colour the real ball shows, and
        pulses on the same beats: `needs`, `done`'s held light, `201` green, `206` red.
      - The top half is filled while a ball is connected and hollow while there is none, and the
        centre flashes white once when one connects. The words stay beside it: the count, `muted`,
        the battery, `no ball`.
      - People without a ball can see what having one is like. A floating ball, like other apps'
        floating menus, is for later (ROADMAP).
      - The constitution's non-goals say "no animation" under "no creature on screen". This reads
        that line as being about the creature: the pulse is the ball's own light, mirrored.
      - Built: `draw_ball` in `src/platform_seam/macos.py` draws it in `labelColor` at 18 pt, so
        it follows light and dark; `Status.icon(BallIcon)` puts it beside the title, and the null
        seam refuses in words. `Menubar.refresh` is handed the signal the ball is showing, lights
        white for `CONNECTED_S` 0.8 s on a connect edge, and pulses on each `beat` for the voice's
        `lasts_s` or `PULSE_S` 0.5 s, with a ball speaking or not; B cuts it. It draws only on a
        change, and the dot leaves the words only once the ball is drawn. A drawing that cannot
        be made is said once, as `MENU BALL`.
      - Checked: `check_menubar` 25 rows, a seam that cannot draw as the reference leg, and 11
        line mutants of `src/mirrors/menubar.py`, all caught. `check_seam` the `Status.icon`
        contract. The real drawing handler rendered offscreen in both appearances, not on the
        screen, into a scratch image that is not committed.
      - Open for the desk: the look at 18 pt next to the other items, the button's size, and the
        two durations, which are CHOICES; whether the white flash reads in light mode, where it is
        white on a white bar with only the outline around it.
- [x] **59 — The app icon is the same ball.** Asked at the desk 2026-09-30: "can it be the same as
      what will be used in the menu". Drawn by the same code as task 58 and committed as
      `tools/app/wobble.icns`. The icon changes the bundle's bytes, so macOS asks for Bluetooth and
      Accessibility once more after this build.
      - Built: `tools/make_icon.py` draws the ball, connected and unlit, in `#1F1F24` on white,
        at the ten `.iconset` sizes, and `iconutil` makes the `.icns`; twice gives the same bytes.
        `build_app.py` copies it into `Contents/Resources` before signing and names it in
        `CFBundleIconFile`. New cdhash `9bfb0364…`, from `46712496…`.
      - Checked: `check_build_app` 3 icon rows (the bytes, the key, the seal: the bundle with it
        removed fails `codesign --verify`) and 2 mutants, plus 3 rows that the committed `.icns`
        is what `make_icon.py` draws today, and 2 mutants of it. `NSWorkspace.iconForFile` on
        `var/build/wobble.app` returns the ball, with Calculator as the reference leg.
      - Open for the desk: macOS 26 sets the ball on a grey rounded plate, as it does for any icon
        that is not a full square; a white square behind the ball would take the plate away.
        Taken up by task 62, which found the rule is opacity, not squareness.
- [x] **60 — The menu ball's centre moves the way the ball's light does.** Asked at the desk
      2026-09-30, looking at a still yellow centre: "can you make it pulse? in the middle of the
      ball?", then "mirroring the done and needs, also the green and red of the needs when it
      fails, etc. it's meant to mirror the ball".
      - Every light is the centre's, where the real ball's button ring lights; task 58's pulse lit
        the whole ball. A `done` holds its colour and breathes in 9's shape with the stroll LED:
        20, 15, 0 and 9 units of ~52 ms, 2.27 s a cycle on camera (`docs/PROTOCOL.md` §8.2, 3h leg
        0) — `STROLL_BREATH`, MEASURED. A `needs` holds nothing, since 199 plays once per beat
        and is dark between; each beat flashes the centre. `201` green and `206` red flash for
        their `lasts_s`, a connect white.
      - Built: `BallIcon` carries `breath`, `pulse_s` and `beat`, a count so two beats alike
        are two flashes. The seam draws the shell as the image and the light as two
        `CAShapeLayer`s over it, the held one under the flash; Core Animation runs them, so the
        light moves smoothly while the daemon ticks at 4 Hz. A flash restarts only on a new beat,
        and never restarts the breath. If the layers cannot be made the light is drawn into the
        image, still, and said as `MENU BALL`; the "keeps its dot" sentence is now the mirror's,
        said only when the ball is not drawn. `pyobjc-framework-Quartz` is listed, since it is
        now imported by name.
      - Checked: `check_menubar` 31 drawn-ball rows and 19 line mutants of
        `src/mirrors/menubar.py`; new `check_menu_light` 27 rows on a real `NSButton` in no
        window, so nothing reaches the screen, and 13 line mutants of `macos.py`, all caught.
        `make_icon.py` still draws the same `.icns` bytes, so the app's grants carry over.
      - The constitution's "no animation" is read as in task 58: this is the ball's own light,
        mirrored, not a creature. It is not amended.
      - Open for the desk: the breath next to the real ball's; the flash's shape (full for 60% of
        it, then a fade) and `PULSE_S`, which are CHOICES; `201`/`206`'s 2.0 s, a GUESS; a muted
        `needs` is `4`, "a pulse that stays", on the ball, and only a flash per beat here, since
        its rhythm was never measured.
- [x] **61 — A mute is a mark beside the menu ball, not a word.** Asked at the desk 2026-09-30:
      "instead of 'muted', show the sound symbol when there is none, or some mark on our icon
      (maybe that's better)", then, on a small mark beside the ball rather than a strike over it:
      "ok, let's go with the small icon for now, just for now". PROVISIONAL: a stopgap until the
      ball itself can show a mute, and the word is what comes back if it is dropped.
      - Built: `BallIcon` carries `muted`. The seam draws SF Symbols' `speaker.slash.fill` at
        11 pt (12 x 14) 2 pt to the right of the ball, at run time and never saved, tinted in
        `labelColor`, so the image is 32 pt wide; the size and the gap are CHOICES. The light is
        placed on the ball's middle, not the image's. With the ball drawn, `render` drops "muted";
        with no ball drawn, or no such symbol on this macOS, the seam answers "not drawn" and the
        title keeps its dot and its word, and why is said once. `draw_ball` is untouched, so the
        app icon's bytes do not move.
      - Checked: `check_menubar` 37 drawn-ball rows and 22 line mutants of `menubar.py`, 3 of
        them new (the mute never handed over, the word kept beside the mark, the word dropped
        with no drawing); `check_menu_light` 35 rows and 20 line mutants of `macos.py`, 7 new
        (the mark not drawn, not tinted, given no room, the light on the image's middle, the mute
        dropped from the image, a missing symbol never checked or answered as drawn), all caught.
        The mark's ink is read in a light and a dark appearance.
      - The constitution is not touched: this replaces a word with a mark on the same surface.
      - Open for the desk: the mark's size and gap beside the real menu bar's other items, and
        whether it reads as "muted" at a glance.
- [x] **62 — The app icon without macOS 26's grey plate.** Asked at the desk 2026-09-30, on
      task 59's open note: "can both be done".
      - macOS 26 sets an app icon on a grey plate unless it is opaque across the system's icon
        shape. Measured on probe bundles, each under its own identifier, through
        `NSWorkspace.iconForFile`: task 59's ball alone is plated, and so is any body with the
        button's hole cleared through it; a full white square passes, and so does a solid body on
        Apple's app icon grid (824 of 1024, 100 in, corners 185.4), continuous or circular. The
        SDK the launcher is built with, the Info.plist's `DT*` keys and `CFBundleIconName` change
        nothing: VS Code's own `.icns` in one of our bundles escapes, ours in its keys does not.
      - Built: `ball_png` draws a solid white body on the grid with continuous corners, the
        system's own curve, through Core Animation, and the ball at 80% of its width on it with its
        paper, so the button is painted, not cleared. The 80% is a CHOICE. `make_icon.py` redraws
        the `.icns`; twice gives the same bytes. New cdhash `52d9a5dd…`, from `9bfb0364…`.
      - Checked: `check_build_app` a plate row, reading a 256 px render 40 px in (1.0 the icon's
        white, 0.82 the plate's grey), with task 59's icon from `d3fada6` as the reference leg
        (0.82), and 2 line mutants of `macos.py` (the hole cleared, the ball alone), both caught.
        `var/build/wobble.app` carries the new `.icns` byte for byte, and a copy of it under a new
        identifier renders with no plate.
      - Open for the desk: macOS 26 lays its own glass shading over the ink (a flat `#1F1F24`
        reads 0.15–0.22 in its render), which may look softer than the menu bar's ball. At
        `var/build`, `local.wobble` renders with a "prohibited" badge while the same bundle
        under another identifier does not: LaunchServices' state, not the bundle, which
        `codesign --verify --strict` passes. New bytes, so Bluetooth and Accessibility are asked
        again after `--install`.
- [x] **63 — The menu ball carries the link and the battery; no words in the title.** Asked at
      the desk 2026-09-30: "draw it white at the bottom when the ball is connected, and hollow
      like today when it isn't, so we can tell the battery", "lower it, only make the red part",
      "that's great, let's go with that"; and on how to tell looking from off, "we need
      something to say it's looking".
      - Built: connected, the top half is red (`#E3352D`) from the band up to the battery
        left, so it empties from the top down, and full with no reading; the bottom half is
        filled, white on a dark bar and black at 18% on a light one, picked by the drawing
        appearance. Looking for a ball, hollow; switched off or `--no-ball`, the whole ball at
        35% in a transparency layer, the mute mark outside it. Red, 18% and 35% are CHOICES.
        With the ball drawn the title is the count alone; the fallback keeps its words. The
        menu gains greyed state lines above the link's action: *Battery N%*, *Ball off*, *No
        ball — looking for one*. `draw_ball`'s default path is unchanged, so the app icon
        does not move.
      - Constitution: principle 7 amended, as asked at the desk — a lost link may be a drawing
        that cannot pass for a connected one, with the words one click away. Criteria 8 and
        9 rewritten to match, with a Changed note.
      - Checked: `check_menubar` rows for the drawing's inputs, the count-alone titles and
        the state lines, 9 new or reworked line mutants and 2 new controls (the battery
        never in the menu, the link said only by its action), all caught.
        `check_menu_light` 12 rows read as pixels at 2x in both bars, and 14 new line
        mutants, all caught. The full round, 2026-09-30: 28 of 29 green; `check_watching`
        failed on its front-window and Terminal-tab rows, twice, with the desk in use — task
        61's flake, and nothing this task touches. Owed a rerun on a quiet desk.
      - Seen at the desk 2026-10-01, all passed. Dark bar: two real balls at 75% and 21%,
        the red empty from the top by what each had spent, the bottom white. Light bar: the
        bottom at 18% and the red read beside black icons. Off (17:36:30) against looking
        (17:36:42–17:36:59) told apart at a glance — "that's fine as is," so 35% stays. On macOS
        26 the bar follows the wallpaper, not the Light/Dark setting: a light bar needed a
        light wallpaper, and the ball turned with the other icons, as the drawing appearance
        promised. `check_watching` rerun whole on a quiet desk the same day, green.
- [x] **64 — A `done` cries in a mood that answers what you did.** Asked at the desk
      2026-09-30: "the mood becomes a response to my actions, and we have random sounds for
      some of them, making it more dynamic"; on the lonely cry, "~5 min with no one answering";
      on the window left in front, "I just left and it stayed focused on this screen, but I
      didn't touch it or anything. Think it'd be nice to have some beat"; and "if I move the
      mouse or type something, it resets the time".
      - Labels: Pikachu's ids have none of their own, so each borrows Eevee's at the same place
        in the block — Pikachu N is Eevee N+29, and 230↔231, 300↔301 (from the sniffer
        capture). A CHOICE, "let's use Eevee's label for now ... we can improve this later".
        Left out: 23, 24, 30 and 31 (near-silent or weak), 25–28 and 35–39
        (handling sounds), and 300.
      - Pools for a `done`: *happy* 20, 32, 34, 230, 181 — the first beat by default; *proud*
        32, 34 — the first beat of a turn longer than 10 min, prompt to done; *sad* 21, 22 —
        the first beat of a turn ended by an API error (`StopFailure`); *call* 33 — the second
        beat, and the first of a done back from a snooze or a let-go; *soft* 230 — the first
        beat when its window is in front with no input for 60 s; *greet* 29 — once, see
        below; *lonely* 143 — a third beat 5 min after the first, nobody having come. 143 is a
        CHOICE, owed the desk. 10 min, 5 min and greet's 2 s are GUESSES.
      - Watched now means its window in front AND a key or the mouse moved in the last 60 s
        (`idle.after_s`), Claude Code's own 60 s for `idle_prompt` — a CHOICE. Any input
        resets the count. Past it, the window stops shielding the signal: a done that never
        cried cries *soft*; one that already did goes on to its next beat, its clock running
        again. An idle nobody can read counts as input, the old behaviour, said once as
        `CANNOT SEE IDLE`. The same rule for a `needs`.
      - Greet: a done that has called — its second beat played, or it came back — greets you
        once when you come back: on B, plain or aimed, or on the first input after 60 s idle
        while it is still the top. Played as a one-shot, like a catch.
      - A done back from a snooze or a let-go starts at *call* and gets no lonely beat: it has
        already been ignored once, and a third cry for it is the nagging task 35 removed.
      - `StopFailure` fires INSTEAD of `Stop` when an API error ends the turn — measured
        2026-09-30 on Claude Code 2.1.160 with a `claude -p` on a model that does not exist,
        isolated from the real hooks (`var/desk/payloads/stopfailure-01.json`). Unwired, such a
        turn ended in silence, which principle 7 forbids. It is wired as `failed`, a `done`.
      - Muted, every beat is 9 as before, and the greet plays nothing. `--one-cry` turns every
        pool off, the lonely beat and the greet with it: 129 for every done.
      - Out: an angry cry at a repeated let-go (idea E) — the constitution's "no affection"
        non-goal, and no amendment was asked for. The Mac cannot vary: it plays `@cry` for
        every pool, since none of the built-in cries is recorded. A limit, not a decision.
      - Future: moods for how a `needs` ends. Today a `needs` is the catch — green for caught,
        red for broke out — and that stays ("no futuro é legal a ideia, deixa anotado").
      - Built: `signals.json` gains `moods.done` (the pools, `long_turn_s` 600,
        `lonely_after_s` 300, `greet_lasts_s` 2.0) and `idle.after_s` 60, refused by the
        ladder when malformed. The Signaller picks each beat's pool and a cry from it, never
        the same twice running; the daemon times each turn from its prompt, reads idle through
        a new `Idle` port (Quartz on macOS, `None` with its reason on null), and plays the
        greet as a one-shot. Each beat's line names its mood. `StopFailure` is in `HOOK_FOR`.
      - Checked: `check_cries` 46 rows, 27 line mutants; `check_ladder_refusals` 46 rows, 40
        mutants; `check_hooks` 5 StopFailure rows on the real payload, 3 mutants;
        `check_seam` the `Idle` port; `check_daemon_edges` a moods scenario on a real daemon
        with a scripted idle, 15 new mutants; `check_watching` now says the idle at the end
        of its run. The full round, 2026-09-30: 29 of 29 green, `check_watching` included.
      - Open for the desk: each pool on the ball (`DESK-CHECKS.md` Part B step 21); whether
        143 reads as lonely; 10 min, 5 min and the greet's 2 s; the idle read inside
        wobble.app; a real `StopFailure` once `install_hooks.py` is rerun.
- [x] **65 — A Bash question is answered when its command starts, not when it ends.** Seen at
      the desk 2026-09-30 at 23:39: "bug: a needs got stuck (it was already answered)" —
      a permission `needs` for `make release` beat 199 for three minutes after the yes,
      until the command ended. "this needs to be fixed".
      - Why: task 49 lets only the tool's own `PostToolUse` answer a permission question, and
        that fires when the tool ENDS. No hook fires on the yes itself; the transcript gets
        nothing between `tool_use` (02:39:47Z) and `tool_result` (02:42:50Z) either.
      - What can be seen: Claude Code runs an approved Bash as a direct child of its own pid,
        `/bin/zsh -c source ~/.claude/shell-snapshots/snapshot-zsh-<ms>-<rand>.sh … && eval
        '<command>'`. Its hooks run as `/bin/sh -c <hook>` and its MCP servers as `npm exec …`,
        started with the session. Measured 2026-09-30 on claude-vscode 2.1.282 (pid 43732);
        the CLI 2.1.160 binary carries the same `snapshot-${shell}-${time}-${rand}.sh`, NOT
        measured live.
      - Rule: while a session's last line is a permission `needs` for Bash, its claude's
        children are read once a second; one that started after the question was read and
        sources a shell snapshot answers it, through the same path as an answer where it
        asked — resolved, released, caught. Said as `its Bash started (pid N), so it was
        approved`. Its later `PostToolUse` answers nothing more.
      - Loud by default (principle 7): children nobody can read keep the question, said once
        as `CANNOT SEE CHILDREN`; a child with no snapshot in its argv is not a Bash.
      - Limits: only Bash — an MCP tool or WebFetch runs inside claude, and still waits for
        its `PostToolUse`. A subagent's Bash starting while the main thread waits would be
        taken as the answer: the started-after check narrows it, it does not close it. A
        question restored after a restart has no read time, so only its `PostToolUse`
        answers it. A Bash approved before its `Notification` was read (the hook came 6 s
        after the `tool_use` here) started before it, so it waits for its `PostToolUse` too.
        A denied Bash starts nothing; a next allowed Bash does answer it, and a denial is an
        answer.
      - Built: `Process.children` (`proc_listchildpids`) and `Process.command`
        (`KERN_PROCARGS2`) in the seam, `None` with their reason on null; `hooks.runs_bash`
        and `BASH`; the daemon's poll beside the liveness one, and `replied`, the one answer
        path both share.
      - Checked: `check_seam` the two new null methods; `check_daemon_edges` an approved-Bash
        scenario (a Bash from before, a hook and an MCP server are not answers; a stale Bash
        question for a later Read is not answered; a blind child list is said once), 6
        mutants; `check_sessions` the seam live — run by Claude's Bash, its own shell is a
        child of the claude that reads as a Bash call, and the MCP servers beside it do not.
      - Open for the desk: `DESK-CHECKS.md` Part B step 22 — a real long Bash approved, its
        beat stopping within a second of the yes; and once from the CLI.
- [x] **66 — B mashed between two VS Code sessions opens no second copy of either.** Shown at
      the desk 2026-10-01 on video, every press deliberate and on purpose: B alternated `project-b` and
      `wobble` about once a second, and three tabs titled "Claude Code" appeared and stayed.
      "can this be adjusted?".
      - Why: every press got its own worker thread, so two raises ran at once. A VS Code raise
        is its window, then `vscode://anthropic.claude-code/open?session=<id>`, which VS Code
        hands to whichever window is in front — and one that does not hold the session opens a
        new copy (task 43). One raise's link landed in the window the other had just raised.
        The `focused` line said so beside another project's title: 0, 4, 12 and 21 such
        raises on 09-28, 09-29, 09-30 and 10-01.
      - Rule: one raise at a time (`daemon.Raises`, one worker). A press while another raise
        is waiting replaces it, and the replaced one says `NOT FOCUSED — never tried`. Just
        before the link, the window in front is read and checked by the watched check's own
        rule (`Entry.in_window`); another window means no link and `NOT FOCUSED` naming it.
        After the link, `focused` only when the session's own window is in front. Each read
        gives the window up to 0.5 s to settle (`daemon.SETTLE_S`): two VS Code windows are
        one app, so the app coming forward proves nothing about which window — not measured.
      - Loud by default (principle 7), and here that is the careful side: nothing readable in
        front opens no link (a copy left behind costs more than a tab not picked), and the
        window that came stays `focused` with the reason. A raise that throws says
        `NOT FOCUSED` with the error, and the worker goes on.
      - Limits: a raise already in flight is not stopped by a newer press; it ends first.
        A click landing after the check and before VS Code takes the link is still a gap,
        narrowed, not closed — and said afterwards, because the verdict reads the front again.
      - Checked: `check_raise` seven rows (another window, the folder in another app, nothing
        readable, before and after the link; a window that settles late; a way with no pick
        unjudged), 3 mutants;
        `check_daemon_edges` an alternating-B scenario with the front window moved under each
        raise — never two seam calls in flight, the replaced said, every link into its own
        window, a click before and after the link — 4 mutants.
      - Open for the desk: `DESK-CHECKS.md` Part B step 23.

- [x] **67 — One effect at a time: fewer sounds and buzzes on top of each other.** Asked
      at the desk 2026-10-01, after a done came back from its snooze at 10:11:04 with a
      call (33), B at 10:11:12 greeted it (29), and a light came back in between: "why did it
      play twice and buzz once just now?", then "so effects don't pile up, have just one" and
      "fewer sounds / buzzes at a time". Four rules, in the order given at the desk ("go in
      order"), one commit each.
      - Rule 1, no greet over a beat: a greet asked within `done.greet_quiet_s` (10 s, a GUESS)
        of the last beat — any signal's, the ball has one sound lane — is spent in silence, and
        the log says `no greet — effect 33 played 8s ago`. Spent, not kept: the call already said
        what the greet would have. With the key absent, the behaviour before it.
        `Signaller.greet` now answers `(voice, why_not)`. One-shots are not counted: a `needs`
        that ends in a catch took the floor, and the done behind it starts over with no beats,
        so there is no greet left for the catch to land under.
      - Checked: `check_cries` four rows (8 s after the call silent and said, not kept, 10 s
        plays, no key at once) and 4 mutants; `check_daemon_edges` the moods scenario, B right
        after the call says `no greet` and plays nothing, 1 mutant.
      - Rule 2, one greet per done: the greet is remembered per session as the done's kind and
        newest event (`Entry.at`), not reset when the done leaves the floor. A snooze or a let-go
        brings the same done back with the same `at`, so B on it again is not greeted twice —
        task 64 greeted it again "or it came back", which DESK-CHECKS' "never a second time for
        the same signal" already contradicted. A new done from that session greets as before.
      - Checked: `check_cries` four rows (the reference greet, back from a snooze silent, nor
        after another signal had the floor, a new done greets) and 4 more mutants;
        `check_daemon_edges` the moods scenario, snooze 3 s: B greets, the snooze brings it back
        with two calls, B again plays no second greet and says no `no greet` either.
      - Rule 3, a glance is not a look: a window counts as looked at only after
        `look_away.glance_s` (1.0 s, a GUESS) in front — at 10:11:05 the done's own window was in
        front under a second, and that alone was a 180 and, 3 s later, a 9 with its buzz. Timed
        from when the front window last changed (`front_since`), not from the signal: the first
        read after nothing was pending is not a change, so a done arriving in the window you are
        reading is quiet at once. A session already counted, watched or inside its `wait_s`, does
        not wait again, so a title changing under you costs nothing. The banner says it
        (`a glance`). `HeldAway` is not touched: leaving a held one is still timed from the first
        poll you are out.
      - Checked: `check_watching`'s glance rows, run on their own since the file as a whole
        moves windows (in front since before, a poll short of the glance, a pass with no grace
        after it, a title change, back inside the wait, zero as before, the light never out for
        half a second) and 3 mutants; `check_ladder` the shipped 1.0, `check_ladder_refusals` a
        zero refused and the key absent as 0; `check_daemon_edges` a new glance scenario and 3
        mutants.
      - Rule 4, coming back means a long time away: the greet for coming back to the keys
        waited for `idle.after_s`, the soft's minute — "it's only when away for a long while,
        ... when the computer slept, or 15 minutes". Now `done.greet_away_s` (900 s, a GUESS) with no key or
        mouse, or the Mac asleep that long (`daemon.Away`). A sleep is the wall clock running
        ahead of `time.monotonic`, which is mach_absolute_time on macOS and stops in sleep;
        whether HID idle counts through a sleep was not measured, so either is enough. The
        reason is latched until the first poll the idle drops, said once in the greet's line
        (`you are back: 912s with no key or mouse`), and forgotten while nothing is pending. B
        still greets at once. The banner says it (`back`). With the key absent, the minute as
        before; with `idle.after_s` at 0, never.
      - Checked: `check_watching`'s away rows (a minute is not back, 900 s is and says why,
        still away is not yet, an hour asleep is back at the first touch with or without idle
        counting through it, a short sleep is not) and 4 mutants; `check_ladder` the shipped
        900, `check_ladder_refusals` a zero refused and the key absent as `None`;
        `check_daemon_edges` the moods scenario, a minute and a bit away then a key greets
        nothing, and 3 mutants. `check_ladder`'s cadence controls now carry the moods through
        their recast, or the new row read a ladder with none.
      - Open for the desk: `DESK-CHECKS.md` Part B step 24.
      - The whole battery, 2026-10-01, on the task's last commit (85e0094): attention, menubar,
        seam, cries, ladder, ladder_refusals and check_daemon_edges all match, every mutant
        caught. Not run: `check_daemon` refused, as it does, with a wobble window in front;
        `check_criteria` (null) has the 3 environmental rows it had before the task.

- [x] **68 — A done you took stays quiet, and a session can be silenced.** Asked at
      the desk 2026-10-01, after several of wobble's own `done` beats came back over a snooze
      already pressed: "several done beats, focused here, but snooze was already pressed",
      then "done with B, snooze 5 minutes, doesn't play again, just stays in the queue; if
      something without a snooze shows up, it's priority, needs still keeps high priority" and
      "help me think of something for a total silence". Sketched and simulated in a drawing
      approved at the desk (local, gitignored), approved the same day: "liked the document,
      it's great".
      - Rule 1, a seen done comes back quiet: a `done` let go after B — the snooze, B again, or
        another menu line — comes back in task 47's quiet state (`Queue.restore` with `at`): listed
        under the separator, not counted, never signalled, and B still reaches it once nothing
        live is waiting. A `needs` comes back live, as before. A new event from the session builds
        a fresh, live row. The menu says `seen` rather than "from before the restart".
      - Rule 2, silence is per session: B held 2 s on the ball, or the ⌥ row "Silence <project>"
        in the menu. Held B silences the session being attended, else the top of the queue, quiet
        ones included (B's own question); a held one goes back into the queue quiet
        (`Why.SILENCE`). Every new event from that session arrives quiet; a new `needs` alone does
        not end it. The menu says `silenced`.
      - Rule 3, what ends a silence: a prompt typed in that session, or an `answered` that
        answers its own `needs` (`hooks.answers`, the task 49 path, and task 65's approved Bash).
        Any other tool line does not count: "the silenced one, if the prompt answers something
        or something is typed, it leaves the silence". Its session ending forgets it. Not kept across a
        restart, which hushes everything anyway (task 47).
      - Rule 4, the tap moves to the release: B fired on the press until now
        (`ball/button.py`), so a hold could not be told from a tap. A tap is now the release, or
        the assumed release a silence-stall makes (`SILENCE_S`); a hold fires once at
        `button.HOLD_S` (2.0 s, a GUESS, beside `SILENCE_S`) and no tap follows it.
      - The confirmation: blue 179 with the weak tick, effect 2, then 180 after 1 s, no sound on
        either surface (`outcomes.silenced`). A PROPOSAL owed the desk, like every first effect.
      - Wired in the daemon: B held (the ball's `on_hold`, or a stdin line `hold`) and the ⌥ row
        both go through `Attention.silence`; the sound is cut, the confirmation played, and a
        hold or a row that silenced nothing is said. `unsilenced` is said on the prompt and the
        answer that end one, `queued` says a silenced arrival waits quiet, and `let go` /
        `snooze` say when a row came back quiet. The banner gains `a silence`, and `a catch`
        stops listing it.
      - Checked: `check_attention` and `check_queue` the core rules; `fake_button` the tap on
        release and the hold at 2 s (a 3 s hold, 1.8 s not one, a hiccup inside one, a stall);
        `check_ball_mirror` a tap and a hold told apart and the confirmation's wire;
        `check_ladder` / `check_ladder_refusals` the silenced outcome and three refusals;
        `check_menubar` the ⌥ rows and 2 mutants; `check_daemon_edges` the moods' snooze row
        recast (back quiet, no more calls) and a silence scenario, 11 mutants. All match,
        every mutant caught; after the banner split, the catch and silence scenarios and
        their mutants were run again on their own. `check_daemon` works whole;
        `check_criteria` (null) the same 3 environmental rows; `check_watching`'s live leg
        read a window moved under it (Mensagens in front), which this task does not touch.
      - Open for the desk: `DESK-CHECKS.md` Part B step 25 — the 2 s hold, blue 179 and the
        tap on release are all GUESSES until then.
      - Broke at the desk 2026-10-01, 17:11:53: B held killed the daemon, `TypeError:
        'NoneType' object is not callable`. `run()`'s `hushed`, which says a silence, shared its
        name with task 67's greet reason in the same scope, so once a greet for coming back had
        run, `hushed` was `None`. The earlier holds that day came before any such greet. The
        greet's is `no_greet` now; `check_daemon_edges` holds B right after that greet in the
        moods scenario, and a mutant that brings the shared name back is caught.
      - Desk, 2026-10-01, step 25, all passed: blue 179 with the tick and no sound; the ⌥ menu
        row; B held 2 s; typing in it ends the silence; a let-go comes back quiet; a silenced
        session's new signal (an injected turn after a background `sleep 60`) arrives quiet and
        the ball stays still; answering its needs where it asked plays the catch, 201; the snooze
        brings a seen done back quiet (B at 17:17:32, `snooze … quiet — you had seen it` at
        17:22:28, nothing played or lit after). The tap on release was not felt as slow: "it's
        working". The 2 s hold and blue 179 stand as chosen.
      - Seen 2026-10-02: the menu bar's blue light sat off the ball's centre once a silence took
        the count away. `setTitle_` moves the button's image (x 10.2 → 8.5 when "1" became ""),
        and the light kept the old title's place. The seam's `Status.show` now places the lights
        again whenever the title changes. Desk the same day, after a restart: a silence at
        12:50:07 left the blue light centred.

- [x] **69 — B finds a session's window by the folder it started in, on any desktop.** Asked
      at the desk 2026-10-01: "why isn't the workspace one in the list?", then, at 14:48,
      "I clicked to go to documents, which is on desktop 1, it didn't go, actually it isn't
      switching desktop 1-2". Two causes, both measured that day.
      - Cause 1, the name: the window hint was the project, the git repo. VS Code titles its
        window after the folder it opened, and `workspace` has no `.git` while
        `workspace/documents` does, so the hint `documents` matched no window — neither B
        nor the quiet-when-looking rule (`Entry.names`) ever found it.
      - Rule 1: the hint is now the folder the session started in (`hooks.launched_in`), read
        from the transcript's folder, which Claude Code names after the launch folder with every
        character but a letter or a digit spelled `-`. That name cannot be decoded
        (`my-dev`), so it is matched against `cwd` and each folder above it. When none
        matches, or there is no transcript path, the hint is the project, as before. The menu
        label stays the project (task 31).
      - Cause 2, Spaces: Accessibility lists only the current desktop's windows, so a window on
        desktop 1 read as no window, and B brought VS Code forward as it was.
      - Rule 2: when no window of the session's app fits, and the session is VS Code's own
        extension (`daemon.folder_of`), the registry's `cwd` is opened in VS Code
        (`open -b <bundle> <folder>`), which switches desktop and puts that folder's window in
        front. Measured 14:49: `open -a` from desktop 2 went to desktop 1's window. The pick
        (task 43/66) then opens the session's link only once that window is in front. Not for
        a `cli` claude in VS Code's terminal — it may have started in a subfolder no window
        holds, and that would open a new window — nor for Warp or Terminal, where a folder is a
        new tab. A refused or stalled `open` falls back to the app as it was, and says why.
      - Checked: `check_hooks` six rows from a captured line (`launched-01.json`, stripped to
        four keys: the repo names it, the folder finds its window, cd'ed out, no transcript, at
        `/`, a repo opened as itself) and 3 mutants; `check_hooks_edges` the registry's `cwd`
        read and absent; `check_raise` six rows (VS Code with a folder, a registry without one,
        Warp, Terminal, not registered, a `cli` in VS Code's terminal) and 3 mutants. seam,
        focus, macos_seam, macos_edges, watching, sessions, menubar, queue and attention match.
        `check_daemon` refused, as it does, with a wobble window in front.
      - Not measured: how long the switch takes to put the window in front (`REOPEN_S`, 2 s,
        a GUESS). A known edge: a window opened from a `.code-workspace` file is titled after
        the workspace, so its session fits no window, and opening its folder makes a new window
        — none such at the desk on 2026-10-01.
      - Desk, 2026-10-01, step 26: B from desktop 2 switched to desktop 1 and picked the workspace
        session's tab (16:52:05, 16:54:29), "jumped from one desktop to the other, now working
        correctly"; the workspace window in front kept its done quiet (16:54:27 `not signalling`),
        which it never had; no new window or "Claude Code" tab. The session had `cd`ed back to
        `workspace` itself by then, so the menu said `workspace` — task 31's rule, no repo
        above it.
      - Seen there: the `focused` line said only the tab, as task 66 made it, so nothing in the
        log showed the desktop had switched. Now the window step's sentence is kept beside a
        picked tab when it names the folder, which the seam does only when it opened it
        (`ports.Focus`): `…was opened in it and '…' came forward; then Code opened …`.
        `check_raise` three more rows and 1 mutant. Seen live at 17:17:32: `no window of Code on
        this desktop names 'workspace', so … was opened in it and '…' came forward; then Code
        opened vscode://…`.

- [x] **70 — The Mac's own sounds for a needs and a catch, yours on top, and the ball kept to
      cries.** Asked at the desk 2026-10-02, after a video of *Pokémon: Let's Go*'s throw,
      wobbles and catch: the Mac's Tink and Hero should sound like the game. Then, on whether
      the game's own audio could ship: "for now we ship what causes no trouble and keep local
      what we chose", and "on the ball, only Pokémon sounds … thinking of the brand, Nintendo
      etc., nobody wants a Poké Ball tied to a moan, a war cry, a religion".
      - Rule 1, wobble's own: `sounds/needs.wav` (0.450 s) and `sounds/caught.wav` (0.220 s),
        drawn in code from two measurements of the game's wobble and click: third-octave levels
        and the 5 ms loudness curve. No sample of the game is in them; their waveforms correlate
        with the game's at +0.04 and −0.13. The tool reads game footage, so it stays out of the
        repo. `config/signals.json` names them by a relative path, which `ladder._mac_sound`
        reads against the checkout. `broke_out` keeps Basso until its sound is measured the same
        way.
      - Rule 2, yours: a file in `assets/sounds/` (gitignored) named `needs`, `done`, `caught` or
        `broke_out` replaces that one's Mac sound (`daemon.own_sounds`). Only `mac_sound`
        changes, so a mute still takes it out and the ball never hears of it. `silenced` is not
        a name (task 68). Used files are said as `your sounds`, and anything else in the folder
        as `NOT YOUR SOUNDS`.
      - Rule 3, the ball keeps to cries: `--cry` is refused unless it is in `assets/cries/`, a
        `..` walk out included, and `fetch_cry.py` loses `--from`, so a cry is a Pokémon's from
        PokeAPI's collection. Which one stays Pikachu until phase 05.
      - Checked: `check_own_sounds` (new) the shipped paths, the override, the names refused,
        the mute, the `--cry` gate, and 3 mutants; `check_ladder` the new paths;
        `check_daemon_edges` the "another --cry" leg on Pidgey's fetched cry; `check_mute`,
        `check_menubar`, `check_cries`, `check_ladder_refusals` match.
      - The menu picker went to the ROADMAP.
      - Desk, 2026-10-02, step 27: a real `needs` and its answer with no ball, after a restart
        that said `your sounds … caught caught.wav · needs needs.wav` (12:48:42); beats at
        12:49:12–17 and the catch at 12:49:20 played the game's cut from `assets/sounds/`. The
        shipped pair was heard by `afplay` alone. An earlier listen played Tink: the app had
        been running since 08:38, so it held the old config, which only a restart reloads.
- [x] **71 — A subagent's permission question is answered by that subagent's tool.** Seen at the
      desk 2026-10-02: "we have the same problem again, the needs waiting to finish: it is now,
      but it was already answered" — juno's `needs · attending` stayed after the yes.
      - Why: the question at 13:19:19 was a subagent's Bash. Task 49 takes only the main
        thread's tools as answers, because a `Notification` carries no `agent_id` (its input is
        built with no tool context, read in the 2.1.286 binary), and every `answered` line after
        it carried `agent_id a19180f4f5c89e0ed` (`var/logs/wobble-2026-10-02.log`).
      - What can be seen: `PermissionRequest` fires just before the prompt shows, with the tool's
        context, so a subagent's carries `agent_id` and `agent_type` and the main thread's carries
        neither. Measured 2026-10-02 with `claude -p` on 2.1.286: PreToolUse, PermissionRequest,
        PostToolUse per tool, `agent_id` before `tool_input`; the subagent's PostToolUse carried
        the same id (`var/desk/payloads/perm-main-01.json`, `perm-sub-01.json`). It has no
        `tool_use_id`.
      - Rule: `PermissionRequest` is wired as `asking`, trimmed by `hook_event.sh` to the same
        three fields as `answered`. The daemon holds a session's last `asking`; the `needs` after
        it takes its agent when both name the same tool (`hooks.asked_by`), and then only an
        `answered` from that agent with that tool answers it (`hooks.answers`). No `asking`, or
        one about another tool, is the main thread, as before — loud, not silent. Restored lines
        take the same path (`recall`).
      - Limits: only `asking` before `needs` is handled — the order VS Code fires them in
        (desk, below); another host firing them the other way round falls back to the main
        thread's rule. Task 65's Bash-start answer still cannot tell agents apart.
      - Checked: `check_hooks` both fixtures through the real script, the command kept out of the
        line, `answers` with an asker, `asked_by`, and 4 new mutants; `check_hooks_edges` its
        parse copy; `check_criteria` a task 71 episode (the main thread's and another subagent's
        Bash do not answer, the asker's does).
      - Desk, 2026-10-02, step 28: a `general-purpose` agent's `touch` in a VS Code session.
        `var/events` had `asking` (agent `a06127c3…`) then `needs`; the log said `queued needs ·
        65b7 … — a subagent asks it, so only its answer counts` (14:00:11), two beats, then
        `resolved … answered where it asked` and the catch at 14:00:14, on the yes.
