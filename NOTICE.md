# Notices

`LICENSE` (PolyForm Noncommercial 1.0.0) covers the **code**. This file covers everything else:
whose names these are, what this repository refuses to carry, and whose work it stands on.

## Not official, not for sale

Pokémon, Poké Ball, Poké Ball Plus, Pikachu, Eevee and every Pokémon name are trademarks of
**Nintendo**, **Creatures Inc.**, **GAME FREAK inc.** and **The Pokémon Company**. wobble is an
unofficial, unaffiliated, non-commercial fan project. It is not endorsed by, sponsored by or
connected to any of them, and it is not for sale: not the code, not a build, not a service
around it.

If a rights holder wants any part of this taken down, open an issue on the repository and it
comes down. No argument.

## No Nintendo asset is in this repository

- **The cries.** The ball can play a sound you upload to it. wobble uploads Pikachu's cry, or
  Eevee's when that is the voice chosen, and neither cry is here: `tools/fetch_cry.py` downloads
  each from [PokeAPI](https://pokeapi.co/)'s [cries](https://github.com/PokeAPI/cries)
  collection onto the machine doing the install, converts it to the ball's format, and keeps it
  in `assets/cries/`, which git ignores. The audio
  belongs to its rights holders; it never leaves your machine.
- **The ball's built-in sounds and lights** are the ball's own. wobble sends a number and the ball
  plays what its firmware already holds; nothing is copied from it.
- **The Mac's sounds** in `sounds/` are drawn in code from noise and sine tones, given only two
  measurements of the matching moment in the game: how loud it is per third of an octave, and how
  its loudness moves every 5 ms. No sample of the game is in them (`sounds/README.md`). A sound
  you add yourself goes in `assets/sounds/`, which git ignores, and plays on your Mac only.
- **The menu bar's ball** is drawn in code (`src/platform_seam/macos.py`), not traced from any
  game asset.
- **The sniffer capture** that settled the protocol is a recording of a real Switch talking to a
  real ball, so it is Nintendo's traffic. It is not in this repository. `docs/PROTOCOL.md` records
  what was learned from it, in our own words.

## Earlier work this stands on

The output side of the ball (sound, light, rumble) had no public description that we could find;
it was worked out from the sniffer capture and at the desk (`docs/PROTOCOL.md`). The rest was
found first by others, and `docs/PROTOCOL.md` was checked against their work:

| | what it gave |
|---|---|
| [emericg/Lighthouse](https://github.com/emericg/Lighthouse), [`docs/porygon2.md`](https://github.com/emericg/Lighthouse/blob/master/docs/porygon2.md) | the ball's GATT map and UUIDs, the input packet, and the button byte as a bitmask |
| [yohanes/pgpemu](https://github.com/yohanes/pgpemu) | a Pokémon GO Plus GATT server reimplementation, which named the LED/button and certificate services |
| [tinyhack.com — Reverse Engineering Pokémon GO Plus](https://tinyhack.com/2018/11/21/reverse-engineering-pokemon-go-plus/) and [part 2](https://tinyhack.com/2019/05/01/reverse-engineering-pokemon-go-plus-part-2-ota-signature-bypass/) | how the GO Plus family authenticates, and why that is a dead end for driving the ball |
| [rna0/pokeball-plus-4-windows](https://github.com/rna0/pokeball-plus-4-windows) | the ball as a controller on Windows, and a clear list of what was still unknown |
| [PokeAPI](https://pokeapi.co/) | the cry, fetched at install |

## Third-party code

| | licence |
|---|---|
| [bleak](https://github.com/hbldh/bleak) | MIT |
| [PyObjC](https://github.com/ronaldoussoren/pyobjc) | MIT |

Both are installed by `pip` from `requirements.txt`; neither is vendored here.
