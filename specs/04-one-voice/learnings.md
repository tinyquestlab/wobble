# Learnings — S04

## Learned

- 2026-10-07: `--dex N` used to write `assets/cries/pikachu.wav` whatever N was, so fetching
  another Pokémon replaced Pikachu's cry. Now a dex goes to `<N>.wav`; a voice to `<voice>.wav`.
- 2026-10-07: Eevee's cry is 0.822 s, 6746 B, 14 upload frames; Pikachu's 1.012 s, 8282 B, 17.
  Both far under the 256-frame ceiling (§7.1). No timing depends on the cry's length any more:
  `after_beat_s` went with the held light.
- 2026-10-07: `fetch_cry.VOICES` holds the dex numbers for now. Task 02's `voices` block in
  `signals.json` carries `dex` too; if both stay, one should read the other.
- 2026-10-07: task 02 resolved it the other way: the `voices` block holds no `cry` and no `dex`,
  against spec.md's Approach. The cry's path is `ladder.cry_of(name)`, the file fetch_cry writes,
  and the dex stays in `fetch_cry.VOICES`; `check_voices` asserts the two name the same voices.
  Two copies of a path or a number are two things to drift apart (task 24's reason for `@cry`).
- 2026-10-07: a dataclass field named `voice` replaced the `Ladder.voice()` method — with
  `slots=True` the field wins silently and every caller got "'str' object is not callable". The
  field is `partner`.
- 2026-10-07: `_voices` first reused the names `given` and `entry`, which made two of
  `check_ladder_refusals`' mutants match twice; they reported NOT APPLIED, not survived. The
  exactly-once rule caught new code shadowing old guards' text.
- 2026-10-07: task 03 loads every partner's ladder at startup instead of reloading on a change.
  A reload reads `signals.json` again, so a config edited mid-run would fail with nobody at the
  terminal, or change the waits halfway. A lookup cannot fail.
- 2026-10-07: the LED needed no stale mark. `_colour` sends only when the index differs, so
  Eevee's `1180` goes out on the next write. Only the cry slot is marked stale (`Ball.revoice`).
- 2026-10-07: a change during an upload was a race: `_put` set the slot to CRY after uploading
  the old cry. `_put` now keeps the path it started with and leaves the slot stale if the voice
  moved.
- 2026-10-07: `--cry` now defaults to None, because the daemon must tell "not given" from
  "given as pikachu.wav". Given, it fixes the voice for the run.
- 2026-10-07: task 04's click goes through the same `chosen_voice` as a hand edit, so a greyed
  line clicked anyway (or a cry deleted between the menu and the click) is refused, not kept.
  The file is written aside and moved in, so the 2 s read never sees half a name.
- 2026-10-07: the edge harness reads `WOBBLE_VOICE_EVERY_S`. At 0.2 s a click left for the
  next read looked the same as one taken at once; at 30 s only the click can make the change.
- 2026-10-07: under `--cry` neither voice line is checked, even for `--cry pikachu.wav`. A CHOICE:
  the run's cry is the flag's, and a ✓ would say the menu could change it.
- 2026-10-07: step 32's first draft quoted the `voice` log line and Eevee's ids from memory; both
  were wrong (the line ends `— {cries()}`; the ids stop at 63, plus 143). A desk step's quoted
  text is read from the code and config, since the desk is where a wrong quote costs a re-run.

## Concepts learned

## Promoted
