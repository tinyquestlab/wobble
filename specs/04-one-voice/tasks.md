# Tasks — S04

**6 of 7 done · next: 07 — close learnings.md and promote**

- [x] **01 — fetch both cries by name, and measure Eevee's.** `tools/fetch_cry.py --voice
  pikachu|eevee` writes `assets/cries/<voice>.wav` (`--dex` stays, for anything else);
  `install.sh` fetches both; NOTICE.md names Eevee's cry. Measure `eevee.wav`: seconds, bytes,
  frames (§7.3), and whether `after_beat_s` needs to move. Its check table, rows + mutants.

  Done 2026-10-07: Eevee (dex 133) is 0.822 s, 6746 B, 14 frames, against Pikachu's 1.012 s,
  8282 B, 17. `after_beat_s` is gone from the ladder since the held light, so nothing moves.
  `check_fetch_cry.py`: 21 rows, 6 mutants, no network.
- [x] **02 — the voices in the config and the ladder.** A `voices` block in `signals.json`
  (`cry`, `dex`, `led`, `tint`, `cries`) with the open questions' values and their sources;
  `ladder.load(voice=…)` lays it over `done`; an unknown voice is a load error that says which.
  Ladder table rows + mutants; Pikachu's ladder identical to today's.

  Done 2026-10-07: `voices` holds `led`, `tint`, `cries` only — no `cry`, no `dex` (learnings).
  Eevee is led 1180, tint #E6C89A, both GUESSES; every voice is checked at load, chosen or not.
  `Ladder.partner` / `.partners` name them. `check_voices.py`: 46 rows, 16 mutants;
  `check_ladder_refusals` rows moved from `done.cries` to `voices.pikachu.cries`.
- [x] **03 — the daemon keeps the voice and changes it live.** `var/voice` (allowlist; anything
  else is Pikachu, said); a change reloads the ladder, recomputes the moods' gate, re-points
  `@cry`, and marks the ball's slot and LED stale; said once; the startup `cries` line names the
  voice. Edge harness scenario + mutants.

  Done 2026-10-07: `var/voice` sits beside the events file and is read every 2 s, so a hand
  edit counts. Every partner's ladder is loaded at startup; a change is a lookup handed to the
  signaller and `Ball.revoice`. `--cry` given fixes the voice and `var/voice` is not read.
  `check_daemon_edges` "the voices": 24 rows, 11 mutants; `check_ball_worker`: 4 rows,
  3 mutants (a change mid-upload stays stale).
- [x] **04 — `Settings › Voice` in the menu.** A *Voice* header and two `Checked` lines under the
  permissions, login last; greyed with a reason for a cry not fetched or a custom `--cry`.
  `check_menubar` rows + mutants.

  Done 2026-10-07: a click writes `var/voice` aside and moves it in, then takes the voice at
  once rather than at the next 2 s read. A click is checked like a hand edit (`chosen_voice`).
  Under `--cry` neither line is checked. `check_menubar`: 9 rows, 6 mutants;
  `check_daemon_edges` "the voice menu": 10 rows, 9 mutants.
- [x] **05 — docs.** README (choosing the voice; install fetches both), ROADMAP phase 04 status,
  DESK-CHECKS Part B step 32 (Eevee by ear on the new ball, the beige, `129` after a switch, the
  choice across a restart).
  Done 2026-10-07: README gains "Pikachu or Eevee"; install fetches both cries; ROADMAP marks 04
  built with step 32 open; step 32 names the log lines and ids from the code, not from memory.
- [x] **06 — partner, not voice.** The choice is the whole partner, not its voice (his word,
  2026-10-07): `Settings › Partner`, `var/partner`, `fetch_cry.py --partner`, a `partners` block,
  the log's `partner` / `PARTNER NOT KEPT`, and spec 04's identifiers with them. The older
  `Voice` — a kind's sound and light, spec 01 — keeps its name, as does `Ball.revoice`, which
  changes only the uploaded cry. Done notes above keep the names they were written with.

  Done 2026-10-07: `check_voices.py` is `check_partners.py`; every table keeps its row count.
  The suite: 28 of 29, `check_raise` refused one leg because the screen was locked — it fails the
  same on the commit before, so it is the Mac's state, not the rename.
- [ ] **07 — close learnings.md and promote.**

---
