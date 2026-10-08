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

## Concepts learned

## Promoted
