# S01 — Tasks

**Status:** 01–73 built and desk-checked (2026-09-22 → 2026-10-02). 74–85 close the spec: the
automated suite, CI, the docs and a clean history.

Each task is told in one to three lines: what it built, and what proved it. The full account of
each — the desk logs, the measurements, the mutants — is in `learnings.md`, and code cites these
numbers ("task 46"), so they never change. Several tasks undid or narrowed earlier ones; where that
happened the later task says so.

## The ball, the core and the first desk pass (2026-09-22)

- [x] **01 — Skeleton.** The package layout, `requirements.txt`, and the seam's `ports.py`
      (Protocols) with `null.py`. Nothing else.
- [x] **02 — The ball's protocol layer.** Scan by name (`Pokemon PBP`), connect, the opening
      sequence, `<opcode:u8><len:u16 LE><payload>` framing, ack on `…e8`, and a three-try retry that
      logs every retry. Ported from an earlier project and judged line by line.
- [x] **03 — Play an effect from the CLI.** `python -m src.ball.effect <id>`, non-zero when a
      write went unacked. The first proof against the hardware, and the desk's tool since.
- [x] **04 — Desk check: the LED.** An LED resource alone lights nothing; followed by an effect it
      lights the ball, and the light goes out by itself. No index "reads as dark".
- [x] **05 — Desk check: the rumble, through a pocket.** The capture waves are felt through a
      pocket. `198` is heard every time and almost never felt; a `needs` plays `199`.
- [x] **06 — Pikachu's voice in the slot.** The cry uploaded over the `0x08` chunked transfer, on
      connect and never on an event (it takes ~1.66 s).
- [x] **07 — Input, and B as an edge.** The 17-byte packet decoded. B counts on 0→1, needs the
      release, and assumes one when packets stop. B is `0x01`, measured; this said `0x02`.
- [x] **08 — The core: signals and the queue.** `done` and `needs`, `needs` always on top, age
      within a kind. No BLE, AppKit or osascript in it.
- [x] **09 — Attention.** B attends a session and holds the queue quiet; its next prompt resolves
      it; a 5 min snooze brings it back otherwise. A prompt in any session drops its own entry.
- [x] **10 — The signal vocabulary.** `config/signals.json` holds every effect, beat, colour and
      interval, so a number changes without a code edit. Its rhythm was reshaped by 16 and 35.
- [x] **11 — Claude Code hooks.** An installer, an append-only `var/events`, and the daemon that
      tails it. Missing hooks are said in words.
- [x] **12 — The menu bar mirror.** A dot and the pending count, a "no ball" state, a click as B,
      and the Mac's own sound with no ball.
- [x] **13 — The ball mirror.** Signals out and B in, on the same core; connect, disconnect and
      reconnect are said. The colour is a second resource and is uploaded too.
- [x] **14 — Focus the window.** Activate the app and `kAXRaiseAction` the window, off the loop's
      thread. With Accessibility refused, skipped and said in words.
- [x] **15 — The desk-check pass.** `docs/DESK-CHECKS.md` over every criterion: nine scripts, each
      with its mutants. It found two defects: a locked screen read as absence, and a skip lost a
      signal.

## Using it (2026-09-22 → 2026-09-23)

- [x] **16 — The rhythm a person can see, and the prompt nobody typed.** A `done` went dark after
      its cry (fixed for good by 35). `hooks.by_person` tells a typed turn from an injected one, and
      fails toward speaking.
- [x] **17 — Quiet while you are looking at it.** The front window's title (`Entry.in_window`)
      keeps a signal quiet. Quiet is not resolved: it stays pending and counted.
- [x] **18 — Quit in the menu.** It stops the daemon the way a person puts the ball down.
- [x] **19 — A log of its own.** One file per day in `var/logs/`; `say()` is the one door, and
      stdout is unchanged.
- [x] **20 — One entry per project.** Two sessions in one folder were one place to look. Undone by
      41, once sessions could be told apart.
- [x] **21 — The queue in the menu.** One line per entry in the queue's order; choosing one attends
      it. Left click opens the menu, right click is B.
- [x] **22 — An ended session stops waiting.** `SessionEnd` drops its entry.
- [x] **23 — The project gets a column in the log.**
- [x] **24 — The Mac says what the ball says.** `done.mac_sound` is `@cry`: the same cry on both
      surfaces.
- [x] **25 — Five seconds after a prompt.** No beat within `after_prompt.wait_s` of typing, so a
      sound is never read as an answer to your keystroke.
- [x] **26 — The choking cry.** An upload over a cry still playing garbled it; the mirror waited the
      cry out. Removed by 35, which stopped uploading at all.
- [x] **27 — The link's account of itself reaches the log.** Retry lines went only to the terminal;
      a `Relay` sends them to the file.
- [x] **28 — Seven beats in six seconds.** Beats queued behind a slow link played in a burst. Each
      beat gets a budget, spent as fewer attempts (`SLOWEST_ACK_S` 2.0).
- [x] **29 — The one you are looking at is not counted.** An attended entry leaves the count and
      stays in the menu's list.
- [x] **30 — The beat that ran to catch up.** Beats are anchored on when they were due, not on the
      poll tick.
- [x] **31 — The project is the repo, not the folder.** `project_of` walks up to `.git`.
- [x] **32 — The scan never gives up.** `find_ball(timeout=None)`; half of all presses had landed
      in the gap between two scans.
- [x] **33 — One session, two lines.** The held entry is not listed again when its session is back
      in the queue, and a click no longer swaps a stale kind in.
- [x] **34 — Mute.** `--mute` and a menu item; the sound goes and the rest stays, and the title says
      it. Its ball half was redone by 35.

## The ball's own light, and knowing which session (2026-09-25 → 2026-09-29)

- [x] **35 — Everything in the stroll slots, and the held light as the pulse.** `done` is `9` then
      cry `129`, `129` again at 30 s, the light held until someone comes; `needs` is `199` every
      1.5 s; muted, `9` and `4`; `180` when nothing is owed. `213` is reserved for catching.
- [x] **36 — Each menu line says where it stands.** Signalling, quiet while watched, attending
      (back in N min), waiting its turn. The core decides; the menu words it.
- [x] **37 — Looking away waits 3 s** (`look_away.wait_s`) before the signal comes back.
- [x] **38 — Know which app a session runs in.** The hook records the host's bundle id; watched
      and B look only at that app. Measured in VS Code, Terminal and Warp.
- [x] **39 — The idle reminder is not a question.** `idle_prompt` queues nothing.
- [x] **40 — Know each session by its process.** Claude Code's registry gives the pid; a session
      whose process is gone stops waiting, as a `SessionEnd` would.
- [x] **41 — One entry per session.** Undoes 20: two sessions in one folder are two lines.
- [x] **42 — B raises the very session.** The desktop app by its `claude://` link, Warp by its
      session URL, Terminal by the tab's tty, VS Code by its window.
- [x] **43 — Watched means that session, not that folder.** VS Code by the tab's name, Terminal by
      the selected tab's tty, Warp by a tab title the daemon writes.
- [x] **44 — Three seconds after a session closes** (`after_end.wait_s`) before the next beat.
- [x] **45 — A closed Warp tab stops signalling.** Warp's undo-close grace kept the claude alive;
      the fix is Warp's own setting, not wobble code.
- [x] **46 — B again on a lone signal asks for its window, with no sound.** Criterion 7's skip had
      cost a beat per press.
- [x] **47 — A restart brings back what was pending, quietly.** Restored entries are listed, not
      counted, and never signalled.
- [x] **48 — Measure what a `.app` changes, before building one.** A Mach-O launcher makes wobble
      the responsible app; grants follow the bundle, pinned to the launcher's bytes.
- [x] **49 — A question answered where it was asked stops signalling.** The same tool's
      `PostToolUse`, from the main thread, answers its `needs`.
- [x] **50 — wobble as an app, built from the repo.** `tools/build_app.py`, a launcher that alerts
      when the daemon dies, one daemon per events file (`flock`), and `--ask-access`.
- [x] **51 — Leaving the held window ends the hold.** Replaced by 52 the same day; `Entry.here`
      and `HeldAway` remain.
- [x] **52 — A `needs` speaks over the hold.** The held one keeps its snooze.
- [x] **53 — An answer in place holds the next beat, as a prompt does** (the 5 s of task 25).
- [x] **54 — Out of the held window, the hold holds nothing back.** What returns goes to the back of
      the queue.
- [x] **55 — A held `needs` holds everything until it is answered.** Narrows 54.

## The catch, the menu ball and the moods (2026-09-30 → 2026-10-02)

- [x] **56 — Answering a `needs` is a catch.** `201` green when answered, `206` red when you went
      to it and left; muted, `193` and `191`.
- [x] **57 — A different Pikachu cry for each `done`.** The new ball's own ids; `129` stays the
      fallback (`--one-cry`).
- [x] **58 — The menu bar item is a ball of our own.** Drawn in code, never Nintendo's art, lit
      with the ball's colour on the ball's beats.
- [x] **59 — The app icon is the same ball.** `tools/make_icon.py`, the same bytes every time.
- [x] **60 — The menu ball's centre breathes as the ball's light does.** The stroll LED's shape,
      measured on camera, run by Core Animation.
- [x] **61 — Mute is a mark beside the menu ball.** Provisional; the word comes back if it goes.
- [x] **62 — The app icon without macOS 26's grey plate.** An opaque body on Apple's icon grid.
- [x] **63 — The menu ball carries the link and the battery.** Filled when connected, hollow while
      looking, faded when off; the words moved into the menu. Principle 7 amended.
- [x] **64 — A `done` cries in a mood.** Happy, proud, sad, calling, soft, greeting, lonely, each a
      pool of ids; watched now needs input within 60 s. `StopFailure` is wired as a `done`.
- [x] **65 — An approved Bash answers its question when it starts.** Its shell, a child of the
      claude, is the yes.
- [x] **66 — B mashed between two VS Code sessions opens no second copy.** One raise at a time, and
      the link only into the session's own window.
- [x] **67 — One effect at a time.** No greet over a beat, one greet per `done`, a glance is not a
      look, and coming back means a long time away.
- [x] **68 — A `done` you took stays quiet, and a session can be silenced.** B held 2 s, or ⌥ in the
      menu; blue `179`. The tap moved to the release.
- [x] **69 — B finds a window by the folder the session started in, on any desktop.**
- [x] **70 — The Mac's own sounds, yours on top, and the ball kept to cries.** `sounds/` drawn in
      code; `assets/sounds/` overrides; `--cry` only from `assets/cries/`.
- [x] **71 — A subagent's permission question is answered by that subagent's tool.**
      `PermissionRequest` names the asker.
- [x] **72 — A permission question beats as it shows, not 6 s later.** The `asking` line is the
      `needs`; the later Notification is its notice.
- [x] **73 — A `done` ends its session's question.** A denial runs no tool, so the turn's end
      answers it.

## Closing the spec: the suite, CI and a clean history (2026-10-05)

The desk checks in `var/desk/` were the gate while the MVP was built (constitution principle 3).
These tasks port the ones that need no radio into a pytest suite, keeping each script's rows and
mutants word for word, so the gate runs on any machine and on every push. The radio, the camera
and the person stay at the desk.

- [x] **74 — The harness.** `tests/`, `pytest.ini` (markers `mac` and `slow`),
      `requirements-dev.txt` (pytest only), and a `conftest.py` that runs each table in its own
      process with `sys.executable` (so no patched global reaches the next table), a silent
      `afplay` first in PATH and TMPDIR in `tmp_path`, and asserts exit 0 **and** the table's
      verdict-row count. Each script finds the repo from its own path; `mac` is skipped off macOS.
- [x] **75 — The core.** attention, queue, ladder, ladder_refusals, cries, mute: each table a test,
      each mutant still run by its own table, where a survivor fails it. Row counts recorded before
      the port and asserted after.
- [x] **76 — The hooks.** hooks, hooks_edges and install_hooks, on payloads scrubbed into
      `tests/fixtures/payloads/` (no real path or name), through the real `hook_event.sh`.
- [x] **77 — The ball without a radio.** protocol, link_log, needs_rhythm, ball_mirror and
      ball_worker, with bleak never imported and a silent cry `.wav` generated at test time where
      none is installed — never a Nintendo asset. The captured LEDs are inlined, not imported.
- [x] **78 — The mirrors and the seam.** menubar, own_sounds, seam, and the table half of raise.
- [x] **79 — The daemon in a scripted world.** daemon_edges, marked `slow` and run in five
      slices side by side (`--part`), and log; a startup that times out fails loudly instead of
      passing.
- [x] **80 — The Mac tier.** focus, macos_edges, menu_light and watching's scripted parts under
      `-m mac` (`--scripted` leaves the legs that read the screen to the desk); a real skip off
      macOS instead of `sys.exit(0)`.
- [x] **81 — CI.** `.github/workflows/tests.yml`: Ubuntu runs everything but `mac`, macOS runs it
      all.
- [x] **82 — Prove it.** Every row count matches its script, every mutant still fails, and the
      suite is green five runs in a row, locally and on CI.
- [x] **83 — One copy.** The ported scripts move to the archive; `DESK-CHECKS.md` Part A points at
      `pytest`, and what stays at the desk is listed.
- [x] **84 — The docs.** Principle 3 amended (the suite closes the MVP), CLAUDE.md's run/test,
      README's tests line, ROADMAP's phases renumbered with 01 done; `learnings.md` closed.
- [x] **85 — A clean history.** The repo rewritten as a few commits by layer, `v0.1.0-beta`
      re-tagged on the last, force-pushed with lease, and the release re-pointed.

## Usage capture (2026-10-06)

From `docs/usage-baseline-2026-10-06.md`: the logs hold nearly everything, but every timing needs
pairing by hand, away looks like ignoring, and nothing outlives 14 days. Each task adds its own row
to `check_daemon_edges` (or `check_log`) before it is ticked.

- [x] **86 — How long, and how many beats.** Every line that ends a signal (`resolved`, `session
      ended`, its turn ended) adds `after 4m12s · 9 beats (3 heard)`. Waited from the entry's
      `since` (monotonic; one recalled after a restart counts from the restart). Beats counted per
      session where `play (beat)` is said, not by the Signaller, whose count resets when another
      signal takes the floor. Heard is a beat that is not silent and went to the ball or that the
      Mac played (no `NO SOUND`). The count starts with a new wait (a kind that changes) and ends
      with the signal.
- [x] **87 — Away and back.** `away` on the poll `Away` latches (no key or mouse for `away_s`, or
      the Mac asleep that long), `back` with how long when it ends. Read only while something is
      pending, which is when idle is read at all — and the only time a wait needs splitting.
- [x] **88 — A re-queue says so.** A `queued` for a session already waiting on the same kind adds
      `again, waiting 4m`, and `while you are on it` or `quiet until now` when that is where the
      earlier one stood. Every `play (beat)` ends `· beat N`, the ladder's own count, so a ladder
      that starts over is a `beat 1` after an `again`, read off the log rather than claimed: a
      quiet row made live by a new event can take the floor afresh. Left as it is: the greet keys
      on (kind, at), so a re-queued done can be greeted again (learnings.md).
- [x] **89 — Kept past the 14 days.** `var/logs/signals.tsv`, one row per ended signal: date, time,
      kind, waited s, beats, heard, how (a fixed set: there, answered, approved, turn ended,
      closed, gone; anything else filed as `other`). No session, project or title. A file it
      cannot write is said once as `SIGNALS NOT KEPT`, and the daemon carries on. `Daily.sweep` only removes `wobble-*.log`, so it stays.
      A row per signal rather than a line per day: it survives a daemon that is down at midnight,
      and any day's summary is a group-by.
- [x] **90 — Prove it on a real day.** The suite green, then a day of use read back: every end
      carries its life, and `signals.tsv` agrees with the day's log. Read back 2026-10-06 over 20
      minutes of real sessions, the daemon silent (`--no-ball`, `afplay` stood in): both ends said
      their life and both rows matched it (648 s, 23 s); no `SIGNALS NOT KEPT`. The app runs the
      new code from then on, so the rest of the day lands in the same two files.
- [x] **91 — Close learnings.md and promote.**
