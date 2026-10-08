# Tasks — S04

**2 of 6 done · next: 03 — the daemon keeps the voice and changes it live**

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
- [ ] **03 — the daemon keeps the voice and changes it live.** `var/voice` (allowlist; anything
  else is Pikachu, said); a change reloads the ladder, recomputes the moods' gate, re-points
  `@cry`, and marks the ball's slot and LED stale; said once; the startup `cries` line names the
  voice. Edge harness scenario + mutants.
- [ ] **04 — `Settings › Voice` in the menu.** A *Voice* header and two `Checked` lines under the
  permissions, login last; greyed with a reason for a cry not fetched or a custom `--cry`.
  `check_menubar` rows + mutants.
- [ ] **05 — docs.** README (choosing the voice; install fetches both), ROADMAP phase 04 status,
  DESK-CHECKS Part B step 32 (Eevee by ear on the new ball, the beige, `129` after a switch, the
  choice across a restart).
- [ ] **06 — close learnings.md and promote.**

---
