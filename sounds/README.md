# sounds

What the Mac plays when there is no ball. Each one replaces a stock macOS sound
(`config/signals.json`).

| file | plays for | replaced |
|---|---|---|
| `needs.wav` | a session waiting on you, every 1.5 s | Tink |
| `caught.wav` | you answered it | Hero |

**Drawn in code, not recorded.** Each is noise and a few sine tones, given only
two measurements of the matching moment in *Pokémon: Let's Go* (the wobble, the
catch's click): how loud it is in each third of an octave, and how its loudness
moves every 5 ms. No sample of the game is in them, and their waveforms do not
correlate with the game's. The tool that measures and draws is kept out of this
repository, because its input is game footage.

**Your own sounds** go in `assets/sounds/`, which git ignores, and are for this
Mac only: the ball always plays its own effects and a Pokémon's cry. See
[Your own sounds](../README.md#your-own-sounds).
