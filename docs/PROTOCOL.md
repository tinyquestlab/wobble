# The Poké Ball Plus over BLE — protocol notes

What wobble knows about talking to the ball, and how each fact is known. The code in `src/ball/`
cites this file by section (`PROTOCOL.md §6.3`), so the section numbers are stable: a new fact
goes into the section it belongs to, or into a new section at the end.

For a plain-language introduction, read [HOW-THE-BALL-WORKS.md](HOW-THE-BALL-WORKS.md) first.

**How these facts were found.** Every fact here comes from one of three places:

- **capture:** a BLE sniffer recording of a real Nintendo Switch talking to the ball, during a
  catch and during several strolls;
- **desk:** the ball played by hand, watched, listened to and felt;
- **sweep:** a script that played every id while recording the ball's own accelerometer.

They were measured on **two units**, called the *old ball* and the *new ball* below. One of them
is an aftermarket unit that implements the original protocol. The two do not always play the same
id the same way (§6.5). One reading is a lead, not a fact (constitution, principle 4): where a
fact rests on a single run, it says so.

Earlier public work found the GATT layout and the button bitmask first; see [NOTICE.md](../NOTICE.md).

## 1. The device

- It advertises as **`Pokemon PBP`**. macOS hides the MAC address behind a per-host UUID, so the
  name is the only stable handle to scan for.
- **No bonding, no encryption.** The capture followed the link for 61 s and saw no pairing and no
  `LL_ENC_REQ`. Any central can connect and write.
- **Only one central at a time.** While wobble holds the link, nothing else can talk to the ball,
  and the other way round: a second daemon, or a Switch, keeps wobble out. For the same reason,
  run only one daemon during a desk check, or stray effects from the other one land in the run.
- The ball does not come back by itself when the host goes away. To reconnect, **press its top
  button** so it advertises again.

## 2. The GATT map

| UUID | what |
|---|---|
| `6675e16c-f36d-4567-bb55-6b51e27a23e5` | the vendor service everything goes through |
| `…23e6` | **input**, notify: buttons, stick, motion (§5) |
| `…23e7` | **output**, write-without-response only: every command (§3) |
| `…23e8` | **replies**, notify: the ball's ack to each command (§3) |
| `00002a19-0000-1000-8000-00805f9b34fb` | battery level, standard, read as a percentage |
| `2bbe7f7c-7304-4466-8407-8eaf89f8ce45` | an unnamed service; the Switch subscribes to `…ce46` and `…ce47` during the opening (§4). Neither ever notified |
| `21c50462-67cb-63a3-5c4c-82b5b9939aeb` | the Pokémon GO Plus LED/button service. Not used on a Mac |
| `bbe87709-5b89-4433-ab7f-8b8eef0d8e37` | the Pokémon GO certificate handshake. Not used on a Mac |

## 3. Frames, opcodes and acks

Every command written to `…23e7`, and every reply on `…23e8`, is one frame:

    <opcode:u8> <length:u16 little-endian> <payload>

**capture:** all 36 command writes in the first capture fit this shape, with no exception.
**desk:** every ack of a session parsed.

Commands the Switch sends:

| opcode | payload | what |
|---|---|---|
| `0x03` | u16 effect id, little-endian | play a built-in effect (§6) |
| `0x04` | 1-byte counter | part of the opening |
| `0x08` | `<kind><index><body>` | upload a resource: a sound or a light (§7) |
| `0x0c` | 4 bytes, `0f000000` | part of the opening |
| `0x10` | empty | part of the opening |

The ball answers each command with **its own reply opcode**, not a copy of the command's:

| command | reply | the reply's payload |
|---|---|---|
| `0x03` effect | `0x01` | the opcode answered: `03 00` |
| `0x08` resource | `0x01` | the opcode answered: `08 00` |
| `0x04` counter | `0x02` | echoes the counter |
| `0x0c` | `0x07` | echoes the payload |
| `0x10` | `0x09` | — |

Three consequences, all measured at the desk:

1. **`0x01` is a generic ack, and it names the opcode, not the effect.** Effect 2 and effect 198
   came back identical. Two effects in flight cannot be told apart by their replies, so the wire
   must carry one command at a time.
2. **An ack is not proof that anything played.** The ball acks an effect whatever it does with
   it, and acks an LED resource whether or not the light changes. Only the ball itself, seen or
   heard, proves what played.
3. **A reply can belong to someone else.** The opening ends with an effect, and the ball can
   notify more than once for it, so a later command can receive that stale `01 … 03 00`. Matching
   a reply to its command by opcode (an `0x08` expects `01 … 08 00`) is what keeps a foreign
   notification from being taken as an ack.

## 4. The opening

The Switch opens every session with the same sequence, and wobble replays it in exactly this
order, because it is the only order known to end with a ball that plays:

1. subscribe to `…23e8` (replies);
2. `0x04 01`, then `0x10`, then `0x04 02`, `0x04 03`, `0x04 04`;
3. subscribe to `…ce46` and `…ce47`;
4. `0x0c 0f000000`;
5. subscribe to `…23e6` (input);
6. effect `2`, a weak tick that says the link is up.

The opening is **not a reset**. A ball left in a strange state (§6.1) stays in it after this
sequence.

## 5. The input packet

While the link is up, `…23e6` notifies 17 bytes about 33 times a second (one packet every 30 ms):

| bytes | what |
|---|---|
| 0 | a counter |
| 1 | buttons, as a bitmask of what is held **right now**: `0x01` the top button, `0x02` the stick click |
| 2–4 | the stick position |
| 5–16 | six int16 little-endian values: the motion sensor (accelerometer and gyroscope) |

- **The counter's step differs between units.** The documented step was 3; the ball wobble was
  built on steps by 6, with a flat 30 ms between packets. A step taken on trust reported every
  packet as lost. Measure it from a live stream, as the most common difference between counters.
- **Byte 1 is a level, not an event.** A press held for a fifth of a second is seven packets that
  all say "down". A press is the 0→1 change, and the next one needs a release first.
- **The release can be lost.** When packets stop, the last level they reported stays true, so a
  button can read as held after the person let go. wobble assumes a release after a short silence.
  A second flavour exists, seen once: the button read "down" for 43 s while packets kept arriving.
  wobble does not cover that one.
- **Rumble shows up in the motion data.** A running motor is visible as a jump in the
  sample-to-sample change of the accelerometer. The sweep in §6.7 uses this.

## 6. Built-in effects (`0x03`)

`0x03` with a u16 id plays an effect from the ball's firmware: a light, a rumble, a sound, or a
mix of them.

### 6.1 What an id is

- **The table ends at 302.** Every id from 0 to 600 was played at the desk; 303–600 do nothing.
- Most ids play once and end. Some leave a **light on** until something replaces it (§6.3).
- **Disconnecting does not stop an effect.** A long effect plays to its end with no host, and a
  light left on stays on.
- **There is no reset command.** Once, after a sweep of 255 ids, the ball was left breathing its
  light with nothing connected, and neither id 0, nor disconnecting, nor the opening cleared it.
  A real catch on a Switch did. Which id caused it is unknown. Nothing wobble plays has done it.

### 6.2 Two lanes, and no queue

**desk, one recorded run plus listening:**

- **Light layers over rumble and sound.** A light that stays on keeps going through a cry, and a
  rumble keeps its length while a light pulses inside it.
- **Rumble and sound are one lane.** A later id replaces the earlier one, even when one only
  rumbles and the other only sounds.
- **Light and light are one lane.** A later light replaces the earlier one.
- **The ball does not queue.** A second id plays at once and cuts the first one if they share a
  lane. Nothing is held back to play later.

So a sequence is spaced by the length of each effect, or each one cuts the one before.

### 6.3 Lights

| id | what |
|---|---|
| `180` | **turns every light off**, and plays nothing else. The only id that does: 181–189, `0` and disconnecting do not |
| `9` | blinks **the colour in the stroll LED slot** (§8.2), with a light buzz, and **stays on** until `180`. Never seen to stop by itself, even tens of minutes later |
| `10` | the same light as `9`, with a stronger buzz |
| `3` | blinks yellow and stays on, weak rumble |
| `4` | like `3`, medium rumble: the light and rumble of `199` with no sound |
| `11` | white, stays on (the connection light) |
| `177`, `178`, `179` | red, green, blue; each stays on |
| `194`, `195` | blue, white; each stays on |
| `191`, `192`, `193` | red, yellow, green: **one pulse**, no rumble, no sound |
| `1` | white blink, "waiting for a connection" |

A light that stays on is the one way to hold a state on the ball without sending anything: wobble's
`done` light is `9`, held until `180`.

### 6.4 The catch

The Switch plays this sequence during a catch:
`202, 202, 264, 203, 207, 204, 205, 211, 211, 211, 200, 199, 198, 201, 213`.

| id | what |
|---|---|
| `198`, `199`, `200` | the wobbles, while the Pokémon is inside: light, rumble and sound, with fixed colours. Each one's motor runs about 0.6 s |
| `201` | caught: the capture green, then a rumble, with its own sound |
| `206` | the catch failed, the Pokémon broke out: red, with sound and rumble |
| `202` | the ball is thrown |
| `211` | the ball bounces on the floor |
| `213` | plays the **catch slot**: the uploaded catch cry and catch LED (§7.2) |

In the capture the catch beats are single beats about 1.2 s apart, and the motor sets a floor of
about 0.6 s between rumbles.

### 6.5 The partner's sounds, and the two units

- **On the new ball**, `20`–`39`, `181`, `230` and `300` are **Pikachu's own sounds**, and
  `49`–`69`, `231` and `301` are **Eevee's**. They need no upload. `40`–`48` do nothing.
- **On the old ball**, the same `20`–`69` are only a light rumble tap, "like a finger tapping the
  glass", and `181`, `230`, `231`, `300`, `301` do nothing.
- **desk, by ear, one source.** Whether the old unit is faulty or simply a different firmware is
  not known. What matters: **which unit is connected changes what an id does**, and the ball cannot
  be asked which one it is.

### 6.6 Strolls, play mode and the rest

| ids | what |
|---|---|
| `110`–`128` | variants of the cry of the Pokémon on a stroll (§7.2). Silent on a ball nobody has walked yet |
| `129` | plays the **stroll cry slot** (§7.2), with a strong rumble |
| `302` | plays a second stroll voice slot (§7.2) |
| `80`–`99`, `232`, `233` | Mew's cry, in variants |
| `140`, `141`, `142` | play mode's three reactions; `142` is the rainbow |
| `143`, `144` | a strong, long rumble |
| `170` | red three times, fast, with a rumble: "no Pokémon on a stroll" |
| `171`–`176` | rumbles (171–173) and tones (174–176) |
| `245` | a weak tick; what the Switch plays when you pet the Pokémon |
| `260`–`270` | move sounds; `264` is played during a catch |
| `2` | a weak tick, no light. The last command of the opening |

Ids not listed either do nothing or were not useful to wobble.

### 6.7 The rumble map

**sweep, ids 1–255:** 105 ids vibrate, at two times the sensor's noise floor or more. They fall
into 21 contiguous blocks, which is the shape of a firmware table and not of noise. The strongest
blocks are `171`–`176` (by far), `80`–`100`, `110`–`129` and `199`–`213`; `129` alone is the
strongest single cry id.

The sweep measures **the motor only**. A low reading means "does not vibrate", never "does
nothing": several quiet ids lit the LED or made a sound. It also averages over 1.5 s, so a tick of
0.1 s reads weak. The person holding the ball is the instrument for what can be felt in a pocket.

## 7. Uploading resources (`0x08`)

The ball can be sent a sound or a light pattern to keep and play later.

### 7.1 The framing

**capture: 45 frames, four resources, three Pokémon.**

    payload = <kind:u8> <index:u8> <body>

| kind | meaning |
|---|---|
| `1` | opens a resource (its first frame) |
| `0` | continues it |
| `2` | closes it (its last frame) |
| `3` | an LED resource: one frame on its own, never closed |

- `body` is at most **498 bytes**, and every frame but the last carries exactly 498. With the
  3-byte frame header, 2 bytes of kind and index, and 3 bytes of the ATT write itself, that is the
  506-byte write seen in the capture.
- `index` counts from 0 and is one byte, so a resource is at most 256 frames.
- A resource that fits in one frame has no known framing: the open frame and the close frame
  cannot be the same frame. Only the LED kind is a single frame.
- **The frames of one resource must not be interleaved with anything else.** The ball reassembles
  by index; a command written in between belongs to nobody.

### 7.2 Slots: the first three bytes are an address

The first three bytes of every uploaded body say **where it goes**:
`<type:u8> <slot:u16 little-endian>`.

| header | slot | played by |
|---|---|---|
| `04 3e 00` | the catch cry | `213` |
| `01 fd 01` | the catch LED, 22 bytes | `213` |
| `04 3c 00` | the stroll cry | `129`, and `110`–`128` |
| `04 3d 00` | a second stroll voice | `302` |
| `01 fc 01` | the stroll LED, 28 bytes | `9` and `10` |

**desk:** a captured Pidgey cry, uploaded with `04 3c 00` in place of `04 3e 00` and nothing else
changed, made `129` and `110` play Pidgey while `213` kept what it held. The same was done for
`3d` (→ `302`) and `fc` (→ `9`).

- **An upload persists.** It stays in the ball's flash across a disconnect, a reconnect, and a
  restart.
- **Nothing can be read back.** There is no known way to ask the ball what a slot holds, or to
  empty one. A partial upload leaves a slot holding something with a hole in it.
- **A Switch overwrites the slots.** A catch writes the catch slots; sending a Pokémon on a stroll
  writes the stroll slots. A partner (Pikachu or Eevee) on a stroll is sent no cry at all: its
  sounds are built in (§6.5).
- **A resource alone does nothing.** It is the next effect that plays it. A light written after
  its effect dresses the next beat, not this one, so the order is always resource, then effect.

wobble writes only `04 3c 00` and `01 fc 01`, and never plays `213`, so the catch slots stay
whatever the Switch last put there.

### 7.3 What an upload costs

- **desk:** 1.3 to 2.6 s for a cry, about 1.66 s typical, on a fresh link. A cry is 8 to 27
  frames, each waiting for its ack. Later in a long session the same upload takes longer (§9).
- **An LED is one frame**, under one ack.
- So **an upload never sits on a notification's path**: a notification queued behind a transfer
  arrives after the thing it announced. wobble uploads the cry when the ball connects, and the LED
  only when the colour changes.

## 8. Sounds and lights, byte by byte

### 8.1 The cry format

The ball plays **RIFF/WAVE, Microsoft ADPCM, 16 kHz, mono, 4 bits**, in 512-byte blocks of 1012
samples, with exactly three chunks: `fmt `, `fact` and `data`. A cry of about a second is around
8 KB.

`ffmpeg -acodec adpcm_ms -ar 16000 -ac 1 -block_size 512` gets the audio right and the container
slightly wrong. Its file differs from the ball's own in two ways that `resource.normalise_wav`
repairs:

- **the byte rate**: ffmpeg writes 16000 into `nAvgBytesPerSec`, where the ball's own files say
  8094 (sample rate × block size ÷ samples per block);
- **an extra `LIST` chunk** with the encoder's name, which survives `-fflags +bitexact`.

The goal is that a converted cry differs from one the Switch sent only in its audio, so a silence
at the desk has one suspect. macOS's `afplay` plays this format directly.

### 8.2 The stroll LED (`01 fc 01`), 28 bytes

    01fc014c45440000000000000010041f148a000f0010000000098a10

| bytes | what |
|---|---|
| 0–2 | the slot address, `01 fc 01` |
| 3–5 | the ASCII tag `LED` |
| 6–15 | constant in every capture; not decoded |
| 16–27 | four steps of `[duration:u8][colour:u16 LE]` |

The four steps, as captured for Pikachu:

| step | at | duration | colour | what |
|---|---|---|---|---|
| A | 16 | `0x14` (20) | `0x008a` | the falling half, in the colour |
| B | 19 | `0x0f` (15) | `0x1000` | dark, with fade |
| C | 22 | `0` | `0` | off |
| D | 25 | `0x09` (9) | `0x108a` | the rising half, in the colour, with fade |

- **One duration unit is about 50 ms** (48–52 ms on camera across six speeds). Scaling the four
  durations changes the blink speed without changing the colour.
- **Bit 12 (`0x1000`) is fade versus cut**, not part of the colour.
- The two colour fields (bytes 17–18 and 26–27) can differ; wobble writes the same colour in both.
- **desk, one run:** a written stroll LED survived a ball restart.

### 8.3 The colour is 4-4-4 RGB

The colour u16 is **`r | g << 4 | b << 8`**, each nibble 0–15 (×17 for 0–255).

- Pikachu is `138` = `0x08a`: red 10, green 8, blue 0, a warm yellow.
- A shiny Pokémon is just another value: shiny Pikachu is `125` = `0x07d`.
- **desk + fit:** seven primaries written and looked at, and 206 measured indexes fit with a
  median hue error of 16°. Hue is reliable; brightness per nibble was never measured.

An earlier reading called this value "not a colour, an index into the firmware", because it does
not decode as RGB565. It is a colour, in a different layout.

Indexes captured from real catches: Bellsprout 84, Pikachu 138, Pidgey 344, Caterpie 386,
Kakuna 428, Rattata 1077. Pidgey's was caught twice, six days apart, with the same value.

### 8.4 The catch LED (`01 fd 01`), 22 bytes

    01fd014c4544000000000000000a02010100001e <colour:u16 LE>

The 20-byte constant is identical in all six captured catch LEDs; only the colour differs. wobble
does not write this slot (§7.2).

## 9. The link: reliability and timing

- **Writes to `…23e7` can vanish without an error.** It is write-without-response, and for that
  kind of write CoreBluetooth reports neither success nor failure; a frame handed over while the
  radio's buffer is busy is simply dropped. The ack on `…23e8` is the only evidence, and a retry
  the only remedy. wobble tries each frame up to three times and logs every retry.
- **desk, one run of 100 writes, 10 s apart:** 85 landed on the first try, 14 after a retry, 1 was
  lost.
- **The link gets worse with age:** retries ran about four times as often after twelve minutes on
  the same link. Why is unknown; a connection interval that relaxes after connecting is a guess.
- **Ack times:** 0.52–0.61 s on an established link, 0.16 s on a fresh one. A deadline under that
  retries frames that were about to land; wobble waits at least 2 s.
- **From Claude Code's hook to the ball:** about 0.9 s median.
- **Battery:** read from `2A19` on connect and again every two minutes.

## 10. Open questions

- What, if anything, resets the ball from the computer (§6.1).
- Bytes 6–15 of the stroll LED, and what the four steps can express beyond one colour.
- Whether a stroll LED survives a power cycle, measured more than once.
- Why the link degrades after twelve minutes, and how much per minute over a long wait.
- Whether `129` plays wobble's upload on a new ball that has never been on a stroll.
- The colours of `198`–`200`, which are fixed by the firmware and were never written down.
