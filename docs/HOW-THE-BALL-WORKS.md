# How the Poké Ball Plus works

A plain-language introduction to driving the ball from a computer. It assumes no Bluetooth
knowledge and a little Python. Every fact here is stated in full, with how it was found, in
[PROTOCOL.md](PROTOCOL.md); the section numbers below (§5) point there.

## What is inside the ball

The Poké Ball Plus is the controller Nintendo made for *Pokémon: Let's Go* on the Switch. Inside
it are:

- a **Bluetooth Low Energy radio**, the way it talks to anything;
- a **top button**, and a small **stick** that can also be clicked;
- a **motion sensor** (accelerometer and gyroscope);
- a **ring light** around the button that can show colours;
- a **vibration motor**, for the rumble;
- a small **speaker**;
- a little **memory**, where a game can leave a sound and a light pattern for it to play later.

Everything wobble does comes down to two things: **listening** to the button, and **asking** the
ball to light up, rumble or make a sound.

## Bluetooth Low Energy in five minutes

Bluetooth Low Energy (BLE) is the low-power kind of Bluetooth used by fitness bands, sensors and
controllers. Four ideas are enough to follow the rest of this page.

**1. Central and peripheral.** Your Mac is the *central*: it looks for devices and connects to
them. The ball is a *peripheral*: it waits to be found. A peripheral talks to one central at a
time, which is why the ball cannot be connected to wobble and a Switch at once (§1).

**2. Advertising.** A peripheral announces itself by broadcasting its name a few times a second.
The ball advertises as `Pokemon PBP`, but only for a few seconds after you press its top button;
then it goes back to sleep to save the battery. Finding the ball means listening for that name
while somebody presses the button.

**3. Characteristics.** Once connected, a BLE device is a set of small mailboxes called
*characteristics*, each with a long ID (a UUID). You can *write* bytes into some of them, and
*subscribe* to others so the device sends you bytes whenever it has news (a *notification*).

**4. No pairing.** Many devices ask for a code or a pairing step. The ball does not: no pairing,
no encryption. Any computer that finds it can connect and talk to it (§1).

The ball uses three mailboxes for everything that matters (§2):

| mailbox | ends in | direction | what goes through it |
|---|---|---|---|
| **input** | `…23e6` | ball → computer | the button, the stick and the motion sensor, about 33 times a second |
| **output** | `…23e7` | computer → ball | every command |
| **replies** | `…23e8` | ball → computer | the ball's "got it" (*ack*) for each command |

## Connecting

1. **Scan** for a device named `Pokemon PBP`, while somebody presses the top button.
2. **Connect** to it.
3. **Say hello** the way the Switch does. The Switch sends the same short sequence every time it
   connects: a few numbered messages and a few subscriptions, in a fixed order (§4). wobble
   copies it exactly, because it is the only order known to leave the ball ready to play. It ends
   with a weak tick on the ball, which is how you know the link is up.

## Listening to the button

Once connected, the input mailbox sends a 17-byte message about every 30 ms (§5). The second byte
says which buttons are held **right now**: `0x01` is the top button, `0x02` is the stick click.

That "right now" is the catch. A press lasting a fifth of a second arrives as seven messages in a
row that all say "held". To count presses, look for the moment the value changes from 0 to 1,
not at the value itself. And if the connection hiccups, the "let go" can be lost, so wobble
assumes the button was released after a short silence (`src/ball/button.py`).

## Making it do things

Every command written to the output mailbox has the same shape (§3):

    <what to do: 1 byte> <length of what follows: 2 bytes> <the details>

Two kinds of command are all wobble needs.

### Play a built-in effect

The ball's firmware has about 300 numbered effects built in: lights, rumbles, sounds, and mixes
of them (§6). Command `0x03` followed by a number plays one. To play effect 199 (one of the
wobbles from a catch), the computer writes five bytes:

    03 02 00 c7 00
    │  └─┬─┘ └─┬─┘
    │    │     └─ 199, as two bytes, low byte first
    │    └─ two bytes of details follow
    └─ "play an effect"

A few effects worth knowing (§6.3–§6.6):

| effect | what it does |
|---|---|
| `199` | a wobble: a light, a rumble and a sound, the way a catch in progress feels |
| `201` | caught: green, with a sound |
| `206` | the Pokémon broke out: red |
| `177`, `178`, `179` | a red, green or blue light that stays on |
| `180` | **turns every light off**: the only effect that does |
| `9` | the light from the ball's memory (see below), which stays on |
| `2` | a weak tick, no light |
| `20`–`39` | Pikachu's own sounds, on newer balls (§6.5) |

Things that surprise people (§6.1, §6.2):

- **Some lights stay on by themselves**, even after the computer disconnects. Only effect `180`
  turns them off.
- **The ball does not queue.** A new sound cuts the one playing; a new light replaces the one
  showing. Lights and sounds do not cut each other. To play two sounds in a row, wait for the
  first to end.
- **Not every ball plays every effect the same way.** On one of the two units tested, Pikachu's
  sounds are only a light tap (§6.5).

### Send it a sound or a light to keep

Command `0x08` uploads a sound or a light pattern into the ball's memory (§7). The upload
starts with an address saying where it goes, and an effect then plays what is there. wobble uses
two places:

| address | holds | played by |
|---|---|---|
| `04 3c 00` | a sound | effect `129` |
| `01 fc 01` | a light pattern, with its colour | effect `9` |

A sound is several kilobytes, so it travels in pieces of up to 498 bytes, each one acknowledged
before the next is sent. That takes one to three seconds (§7.3), which is why wobble uploads its
sound once, when the ball connects, and not each time it needs it. What you upload **stays in the
ball**, even across restarts, until something overwrites it: wobble, or a Switch during a game.

**The sound must be in exactly the ball's format** (§8.1): a WAV file, Microsoft ADPCM, 16 kHz,
mono, in 512-byte blocks. A file that is almost right does not cause an error: the ball just stays
silent. `tools/fetch_cry.py` shows the conversion, from any audio file, with `ffmpeg`.

**A colour is three numbers from 0 to 15**, red, green and blue, packed into two bytes as
`red + green × 16 + blue × 256` (§8.3). Pikachu's yellow is red 10, green 8, blue 0, which is 138.

## What can go wrong

- **A command can vanish without an error** (§9). The output mailbox does not confirm delivery,
  so a write can simply be lost when the radio is busy. The ball's ack is the only proof it
  arrived, and sending again is the only fix. In one run of 100 commands, 85 arrived first time,
  14 needed a second try, and 1 was lost.
- **An ack is not proof that anything happened** (§3). The ball says "got it" to any effect,
  even one that does nothing. Only your eyes, ears and hand can tell what really played.
- **There is no reset** (§6.1). If the ball gets into a strange state, the reliable fix found so
  far is to let a Switch use it.
- **Only one computer at a time.** If the ball will not connect, check that nothing else holds it.

## Try it

With wobble installed (see the [README](../README.md)) and the ball nearby, these commands talk
to the ball directly. Press the top button when they say they are scanning.

```bash
venv/bin/python3 -m src.ball.effect 199                  # one wobble
venv/bin/python3 -m src.ball.effect 177 --gap 3          # a red light that stays on...
venv/bin/python3 -m src.ball.effect 180                  # ...and off again
venv/bin/python3 -m src.ball.cry assets/cries/pikachu.wav --play   # upload the cry, play it
```

And the same thing from your own Python, using wobble's ball package:

```python
import asyncio
from src.ball import protocol
from src.ball.link import open_ball

async def main():
    async with open_ball() as link:            # scan, connect, say hello
        await link.send(protocol.effect(199))  # write `03 02 00 c7 00`, wait for the ack
        await asyncio.sleep(2)                 # let it play before disconnecting

asyncio.run(main())
```

Save it in the `wobble` folder and run it with `venv/bin/python3`. `src/ball/` is only about
the ball: it knows how to make it do a thing, never which thing is worth doing, so it is a
reasonable place to start your own project.

## Where to go next

- [PROTOCOL.md](PROTOCOL.md): every fact on this page, byte by byte, with how it was found and
  what is still unknown (§10).
- [NOTICE.md](../NOTICE.md): the earlier public work on this ball, which is worth reading too.
