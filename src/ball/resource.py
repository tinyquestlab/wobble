"""Cut a file into the `0x08` resource frames the ball accepts.

No radio here, for the same reason `protocol.py` has none: the framing is a
fact, and a fact should be checkable without hardware in your hand. It was
checked by re-cutting the cry the Switch itself uploaded and comparing the
result, frame by frame, with the bytes in the sniffer capture.

**The shape is measured, not read off a spec** (PROTOCOL.md §7.1) — every
`0x08` frame in the captures, 45 of them across four resources and three
creatures:

    payload  = <kind:u8> <index:u8> <body>
    body    <= 498 bytes, and every frame but the last carries exactly 498
    kind      1 opens a resource, 0 continues it, 2 closes it
    index     counts from 0; the closing frame is the short one
    a first body carries three bytes, its slot (§7.2), before `RIFF`
    an LED resource is one frame on its own: kind 3, index 0

498 is the number the whole file turns on, and it is pinned twice over: the
captures show 45 bodies of exactly that size, and `pidgey-cry.wav`'s 3674 bytes
plus its 3-byte prefix come to 3677 = 7×498 + 191, which is the 8 chunks the
capture holds. It also reconciles with the 506-byte ATT write: 3 (ATT) +
3 (this device's envelope) + 2 (kind, index) + 498.

A captured cry uploaded back byte-identically got identical acks and played
nothing until the right effect was played after it: a resource is played by
an effect, never by its upload (PROTOCOL.md §7.2). So this file is the framing
and nothing else; which effect plays a slot is somebody else's problem.
"""
from __future__ import annotations

import struct

from . import protocol

# The framing (PROTOCOL.md §7.1).
MAX_BODY = 498
KIND_CONTINUE = 0
KIND_OPEN = 1
KIND_CLOSE = 2
KIND_LED = 3

# The three bytes a captured catch cry carries before its RIFF header: the
# catch cry's slot, which 213 plays (PROTOCOL.md §7.2). wobble never writes it.
CRY_PREFIX = bytes.fromhex("043e00")

# The same three bytes for the STROLL cry, which effect 129 plays and 213 never
# touches. They are a destination slot and not a constant: a captured Pidgey
# uploaded with `04 3c 00` in place of `04 3e 00`, nothing else changed, made
# 129 play Pidgey while 213 kept what it held (PROTOCOL.md §7.2). This is the
# slot wobble speaks from, so the catch slot stays free for catching (task 35).
STROLL_CRY_PREFIX = bytes.fromhex("043c00")

MAX_CHUNKS = 256                 # `index` is one byte, so 255 is the last one


def cut(blob: bytes, prefix: bytes = b"") -> list[bytes]:
    """The `0x08` payloads for one multi-chunk resource, in order.

    `prefix` goes in front of the blob inside the first frame and is NOT part of
    the file — for a cry it is `CRY_PREFIX`.

    Returns payloads, not writes: the `<opcode><length:u16>` envelope around each
    one belongs to whoever sends them, and payloads are what compare directly
    with a capture.
    """
    body = prefix + blob
    total = -(-len(body) // MAX_BODY)                  # ceil, without importing math
    if total < 2:
        raise ValueError(
            f"{len(body)} bytes is one frame, and no capture shows how a resource "
            f"that small is framed — an opening frame is kind {KIND_OPEN} and a "
            f"closing one kind {KIND_CLOSE}, and a single frame cannot be both. "
            f"The LED resource is the only short one seen and it has its own kind; "
            f"use led_payload() for that.")
    if total > MAX_CHUNKS:
        raise ValueError(
            f"{len(body)} bytes is {total} frames and the index is one byte, so "
            f"anything past {MAX_CHUNKS} would restart the count at 0 and overwrite "
            f"the front of the resource. Send something shorter.")
    out = []
    for i in range(total):
        part = body[i * MAX_BODY:(i + 1) * MAX_BODY]
        kind = KIND_OPEN if i == 0 else (KIND_CLOSE if i == total - 1 else KIND_CONTINUE)
        out.append(bytes((kind, i)) + part)
    return out


# The catch LED's captured constant (PROTOCOL.md §8.4), the same bytes as
# `protocol.LED_CONST`. wobble does not write the catch slot; `led_blob` is kept
# because the desk checks rebuild the six captured catch LEDs with it.
LED_CONST = protocol.LED_CONST


def led_blob(index: int) -> bytes:
    """One LED resource body, for `led_payload`. 22 bytes: the constant, then `index`.

    `index` is a 4-4-4 RGB colour (PROTOCOL.md §8.3): `138` is Pikachu's, as
    captured.
    """
    if not 0 <= index <= 0xFFFF:
        raise ValueError(f"{index} is not a u16 — an LED index is the two bytes "
                         f"after {len(LED_CONST)} captured ones, nothing wider")
    return LED_CONST + index.to_bytes(2, "little")


# The stroll LED, the one effect 9 lights from: 28 bytes that open `01 fc 01`,
# captured from a real Pikachu stroll (PROTOCOL.md §8.2). The tail from byte 16
# is four `[duration][colour u16]` steps, and only two of the colours are ours
# to change: step A at 17-18 (the falling half) and step D at 26-27 (the rising
# half, carrying the `0x1000` fade bit, which is not part of the colour). The
# colour is 4-4-4 RGB (§8.3) — Pikachu is 138, the same as in the catch LED.
FC_PIKACHU = bytes.fromhex("01fc014c45440000000000000010041f148a000f00100000"
                           "00098a10")
FC_FADE = 0x1000


def fc_blob(index: int) -> bytes:
    """The stroll LED for one colour: Pikachu's own body with `index` in both halves.

    One colour on both halves because that is what a creature's own colour is;
    the capture rebuilt from 138 is byte for byte the capture, which is what
    `check_ball_mirror.py` holds this to.
    """
    if not 0 <= index < FC_FADE:
        raise ValueError(f"{index} does not fit the stroll LED — a colour there is "
                         f"4-4-4 RGB under {FC_FADE:#x}, whose bit means fade")
    body = bytearray(FC_PIKACHU)
    body[17:19] = index.to_bytes(2, "little")
    body[26:28] = (index | FC_FADE).to_bytes(2, "little")
    return bytes(body)


def led_payload(blob: bytes) -> bytes:
    """The LED resource: one frame, its own kind, never closed by a `kind 2`.

    Kept as a payload the caller chooses to send rather than something `cut`
    folds in: a light and a cry are separate resources on one opcode, told
    apart by the kind byte (PROTOCOL.md §7.1).
    """
    if len(blob) > MAX_BODY:
        raise ValueError(f"{len(blob)} bytes will not fit one frame, and no "
                         f"capture shows a kind {KIND_LED} resource spanning two.")
    return bytes((KIND_LED, 0)) + blob


def frames(blob: bytes, prefix: bytes = b"") -> list[bytes]:
    """`cut`, already wrapped in this device's `<opcode><len><payload>` envelope."""
    return [protocol.frame(protocol.OP_RESOURCE, payload) for payload in cut(blob, prefix)]


# --- the mute resource ------------------------------------------------------
# No longer uploaded by the mirror (task 35): mute is its own effect id per kind
# now. Kept as the one way to put a silent cry in a slot, which is how task 04
# measured what a light without a sound looks like. There is no Nintendo asset
# in any of this and nothing to fetch: the bytes are built here.
#
# `SILENT_FMT` is the `fmt ` chunk of the cries themselves — byte-identical in
# `pidgey.wav` and `pikachu.wav`, and pidgey is the file the ball itself sent.
# Copied verbatim rather than composed so that a mute resource differs from a
# real cry in its audio and in nothing else, which is the same reason
# `normalise_wav` exists: when the ball answers with silence, there should be
# one suspect.
#
#   MS ADPCM (2), mono, 16000 Hz, 8094 B/s, 512-byte blocks, 1012 samples each
SILENT_FMT = bytes.fromhex(
    "02000100803e00009e1f0000000204002000f403070000010000000200ff000000"
    "00c0004000f0000000cc0130ff880118ff")
BLOCK_ALIGN = 512
SAMPLES_PER_BLOCK = 1012

# One MS ADPCM block that decodes to zero: predictor 0, the minimum delta (16),
# both initial samples 0, and every nibble after them 0. Not reasoned out from
# the codec — it is the first seven bytes of `pidgey.wav`'s own data, which
# opens on silence, so this block is a slice of a file the ball played.
SILENT_BLOCK = bytes((0, 0x10, 0, 0, 0, 0, 0)) + bytes(BLOCK_ALIGN - 7)


def silence(blocks: int = 1) -> bytes:
    """A WAV of nothing, in the ball's own format. One block is ~63 ms.

    The default is the smallest file `cut` will take: 602 bytes, which is two
    frames with `CRY_PREFIX` in front. Shorter would be one frame, and no
    capture shows how a single-frame resource is framed (`cut` says so itself).
    """
    data = SILENT_BLOCK * blocks
    body = (b"fmt " + struct.pack("<I", len(SILENT_FMT)) + SILENT_FMT
            + b"fact" + struct.pack("<I", 4)
            + struct.pack("<I", SAMPLES_PER_BLOCK * blocks)
            + b"data" + struct.pack("<I", len(data)) + data)
    return b"RIFF" + struct.pack("<I", len(body) + 4) + b"WAVE" + body


# --- the file, before it reaches the wire -----------------------------------
# `ffmpeg -acodec adpcm_ms` gets the codec right and the container subtly wrong,
# and every one of those differences would come out of the ball as the same
# silence. Measured against the captured `pidgey-cry.wav`, which the Switch
# itself sent (PROTOCOL.md §8.1):
#
#   * **block size.** ffmpeg defaults to 1024 bytes per block (2036 samples);
#     the ball's own files use 512 (1012). `-block_size 512` fixes it.
#   * **byte rate.** ffmpeg writes the SAMPLE rate into `nAvgBytesPerSec` —
#     16000 where the real file says 8094, which is rate x blockalign /
#     samplesPerBlock. `-block_size` does not fix this one; nothing does.
#   * **a `LIST` chunk** carrying the encoder's name, which survives
#     `-fflags +bitexact` and which no file the ball has ever received contains.
#
# So the last two are repaired here rather than argued with. The point is not
# tidiness: it is that a converted cry should differ from a captured one in its
# audio and in nothing else, so that a silence at the desk has one suspect.
WAV_CHUNKS_KEPT = (b"fmt ", b"fact", b"data")


def _wav_chunks(data: bytes) -> list[tuple[bytes, bytes]]:
    """Every top-level RIFF chunk as `(id, body)`, in file order."""
    out, pos = [], 12
    while pos + 8 <= len(data):
        cid, size = struct.unpack_from("<4sI", data, pos)
        if pos + 8 + size > len(data):
            break
        out.append((cid, data[pos + 8:pos + 8 + size]))
        pos += 8 + size + (size & 1)                 # chunks are word-aligned
    return out


def normalise_wav(data: bytes) -> bytes:
    """An ffmpeg MS ADPCM file, made structurally identical to the ball's own.

    Keeps only the chunks a captured cry has, in that order, and recomputes the
    byte rate from the block size the way the real file does. Byte-identical
    input to output for a file that is already right, which was checked against
    the captured `pidgey.wav` — that is what says this matches the device rather
    than matching an idea of it.
    """
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError("not a RIFF/WAVE file")
    kept = []
    for cid, body in _wav_chunks(data):
        if cid not in WAV_CHUNKS_KEPT:
            continue
        if cid == b"fmt " and len(body) >= 20:
            _codec, _ch, rate, _bps, align, _bits = struct.unpack_from("<HHIIHH", body, 0)
            per_block = struct.unpack_from("<H", body, 18)[0]
            if per_block:
                body = body[:8] + struct.pack("<I", rate * align // per_block) + body[12:]
        kept.append((cid, body))
    out = b"".join(cid + struct.pack("<I", len(body)) + body + (b"\0" * (len(body) & 1))
                   for cid, body in kept)
    return b"RIFF" + struct.pack("<I", len(out) + 4) + b"WAVE" + out
