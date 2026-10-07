# Learnings — S04

## Learned

- 2026-10-07: `--dex N` used to write `assets/cries/pikachu.wav` whatever N was, so fetching
  another Pokémon replaced Pikachu's cry. Now a dex goes to `<N>.wav`; a voice to `<voice>.wav`.
- 2026-10-07: Eevee's cry is 0.822 s, 6746 B, 14 upload frames; Pikachu's 1.012 s, 8282 B, 17.
  Both far under the 256-frame ceiling (§7.1). No timing depends on the cry's length any more:
  `after_beat_s` went with the held light.
- 2026-10-07: `fetch_cry.VOICES` holds the dex numbers for now. Task 02's `voices` block in
  `signals.json` carries `dex` too; if both stay, one should read the other.

## Concepts learned

## Promoted
