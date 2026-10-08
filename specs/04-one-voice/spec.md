# S04 — wobble speaks with Pikachu or Eevee

**Source branch:** main · **Working branch:** main
**Repo(s):** wobble
**Renamed 2026-10-07 (task 06):** the choice is the partner, not its voice — `Settings ›
Partner`, `var/partner`, `fetch_cry.py --partner`, a `partners` block. Below keeps the words it
was approved with.

## Context

`ROADMAP.md`, phase 04 — More voices. Narrowed on 2026-10-07 to what one ball can do: one voice for
everything, changed the way a stroll changes it. There is one ball and one stroll slot, so a voice
per session would re-upload on every signal. That waits for a second ball, which is not coming soon.

Pikachu and Eevee are the partners: on the new ball each has its own sounds built in, `20`–`39`,
`181`, `230`, `300` and `49`–`69`, `231`, `301` (`docs/PROTOCOL.md` §6.5), and needs no upload.
The uploaded cry in `04 3c 00`, played by `129`, is what a non-partner speaks with. It is also the
fallback when the ball does not play a partner's sound: the old ball, `--one-cry`, a custom `--cry`
(§7.2, `config/signals.json` `_source_cries`).

Today the voice is Pikachu, fixed. It is chosen only by passing `--cry <file>`, and any other file
turns the moods off. `tools/fetch_cry.py` already takes `--dex`, but always writes `pikachu.wav`.

## What to build

- **`Settings › Voice`**: two lines, *Pikachu* and *Eevee*, with a ✓ on the one in use. They go
  under the permissions, and the login line stays last. Only those two, for now (2026-10-07).
- **The choice drives everything a voice touches:**
  - the moods a `done` cries in, from that partner's own ids;
  - the cry uploaded to `04 3c 00` for `129`, re-sent at once if the ball is connected, or on
    the next connect;
  - the colour of the `done` light (`01 fc 01`);
  - the menu bar's yellow for a `done`;
  - the Mac's `done` sound (`@cry`).
- **The choice survives a restart.** It is a file under `var/`, like the rest of wobble's state.
- **Both cries are fetched at install**, from PokeAPI as today. Nothing Nintendo's is committed.
- **Each change is said once in the log.**

## Acceptance criteria

- [ ] 1. `Settings ›` lists *Pikachu* and *Eevee*, with a ✓ on the voice in use. The choice
  survives a restart.
- [ ] 2. With Eevee chosen, a `done` cries by mood from Eevee's ids, and `129` holds Eevee's
  cry. It is re-uploaded at once if the ball is connected, or else on the next connect. The
  `done` light and the menu bar's colour are beige, and the Mac's `done` sound is `eevee.wav`.
- [ ] 3. Choosing Pikachu again gives back exactly today's behaviour: ids, `led 138`, tint,
  `pikachu.wav`.
- [ ] 4. A voice whose cry was not fetched is greyed, and says how to fetch it. Clicking it
  changes nothing.
- [ ] 5. Under a custom `--cry`, both lines are greyed and say why, and the run behaves as today:
  one cry, no moods.
- [ ] 6. Each change is said once in the log, and the startup `cries` line names the voice.
- [ ] 7. The cries are still fetched at install, from PokeAPI. No cry is in git.
- [ ] 8. The suite is green, and a new Part B step covers the ball.

## Approach

- **Config.** The per-voice part of `done` moves into a `voices` block in `config/signals.json`:
  `cry`, `dex`, `led`, `tint` and `cries` for each of `pikachu` and `eevee`.
  `ladder.load(voice=…)` lays the chosen one over `done`, so the rest of the core sees the same
  `Ladder` shape as today.
- **Daemon.** It keeps the choice in `var/voice`. On a change it reloads the ladder and hands it
  to the signaller. The ball mirror marks its slot stale, and `_put` and `_colour` re-send what
  differs. The ball mirror already writes the LED only when it is not there.
- **Fetching.** `tools/fetch_cry.py --voice eevee` writes `eevee.wav`, and `install.sh` fetches
  both.
- **Menu.** The menu reuses spec 03's shapes: a header line, then `Checked` lines inside
  `Settings ›`. It needs no nested submenu.

## Edge cases

- The ball disconnects in the middle of the re-upload. The slot stays stale, and the next connect
  sends it again, as `_put` does today.
- A change while a `done` is playing. The next beat uses the new voice, and a light already held
  is re-coloured only when the mirror next writes it. This is a choice, to be confirmed at the desk.
- `var/voice` is unreadable or names a voice no longer listed. Then the voice is Pikachu, and the
  log says why (allowlist: only a listed name is kept).
- `eevee.wav` is deleted while Eevee is chosen. That falls under criterion 4: the run says so and
  keeps Pikachu.
- The old ball. Eevee's moods are a tap there, exactly as Pikachu's are, and `--one-cry` plays
  Eevee's upload on `129`.
- Eevee's cry is longer than Pikachu's. The DESK-CHECKS note on `after_beat_s` reopens with it,
  so task 01 measures its length.

## Glossary & concepts (learning)

- **Partner.** Pikachu or Eevee, the two whose sounds the new ball holds built in. Any other
  Pokémon speaks only through the uploaded slot.
- **`129` / `04 3c 00`.** The stroll cry, and the ball's one writable cry slot. Whatever was last
  uploaded plays there.
- **4-4-4 RGB.** The LED colour is a u16 holding `r | g<<4 | b<<8`, with each value 0–15
  (§8.3). Pikachu's `138` is r10 g8 b0.

## Open questions

1. **Eevee's moods.** They are Pikachu's pools shifted by +29: happy `49 61 63 231`, proud
   `61 63`, sad `50 51`, call `62`, soft `231`, greet `58`. Lonely stays `143`, a generic long
   rumble (pokeball `docs/EFFECTS.md`). `181` has no Eevee pair and is dropped. The mapping is
   a CHOICE, to be checked at the desk by ear.
2. **Eevee's beige.** It is `1180` (r12 g9 b4), a GUESS. No Eevee LED was ever captured
   (pokeball `research/STROLL-SLOTS.md` §6). The desk picks the final value.
3. **Does `129` play the upload on a new ball that has never been on a stroll?** This is
   §10's open question. It matters only for the fallback.

## Outcome

| # | Criterion | Result |
|---|---|---|

---
