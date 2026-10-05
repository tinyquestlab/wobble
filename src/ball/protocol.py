"""Everything true about the wire, with no radio in sight.

The split from `link.py` is deliberate: what can be checked without a ball in
your hand should be checkable without one. The
GATT map, the frame format and the opening script are all facts — they can be
read, diffed against the capture, and argued about at a desk. `link.py` is the
half that needs hardware.

The frame format came out of a sniffer capture of a real catch, validated
against all 36 command writes in it with zero exceptions:

    <opcode:u8> <length:u16 LE> <payload>

Source: `docs/PROTOCOL.md`, cited by section. Every claim below says which part
of it is measured and which is inherited.
"""
from __future__ import annotations

import struct
from typing import NamedTuple

# The ball advertises under this name. On macOS there is no stable MAC address
# to target instead, so the name is the only handle — see `link.find_ball`.
NAME = "Pokemon PBP"

# --- the GATT surface -------------------------------------------------------
# The vendor "gamepad" service is the one everything works through. The GO Plus
# LED/button service exists on the device and is deliberately absent here:
# nothing wobble does needs it (PROTOCOL.md §2).
SVC_VENDOR = "6675e16c-f36d-4567-bb55-6b51e27a23e5"
IN_E6 = "6675e16c-f36d-4567-bb55-6b51e27a23e6"   # input notify: button + stick + IMU
OUT_E7 = "6675e16c-f36d-4567-bb55-6b51e27a23e7"  # output, write-without-response
ACK_E8 = "6675e16c-f36d-4567-bb55-6b51e27a23e8"  # the ball's reply to every command

BATTERY = "00002a19-0000-1000-8000-00805f9b34fb"

# A service with no name, which the Switch subscribes to during the opening and
# which never notified once in the capture. Kept because the opening is replayed
# in the capture's exact order and this is part of that order — not because
# anything is expected to arrive on them.
SVC_2BBE = "2bbe7f7c-7304-4466-8407-8eaf89f8ce45"
CE46 = "2bbe7f7c-7304-4466-8407-8eaf89f8ce46"
CE47 = "2bbe7f7c-7304-4466-8407-8eaf89f8ce47"

# --- opcodes ----------------------------------------------------------------
# The five the capture holds (PROTOCOL.md §3). Named so a log line reads as
# something rather than as a number, and so the ones the MVP never sends are
# still visible as known.
OP_EFFECT = 0x03    # play an effect: 2-byte id, also sent constantly while handled
OP_COUNTER = 0x04   # 1-byte counter, opening only
OP_RESOURCE = 0x08  # chunked transfer: audio, and an LED resource
OP_0C = 0x0C        # 4 bytes, opening only
OP_0F = 0x10        # empty, opening only

# The opcode the ball answers each command with, measured at the desk 2026-09-22.
#
# `0x01` is a GENERIC ack, and its payload names the opcode it is answering:
# effect (0x03) came back `01 0200 0300`, an LED resource (0x08) came back
# `01 0200 0800`. Reading that payload as a constant was the first guess and the
# second data point killed it — which is why the byte is named here rather than
# left as folklore.
#
# **It is attribution by opcode, and for effects that is not enough.** A 0x04 ack
# echoes the counter it answers and a 0x0c ack echoes its payload byte for byte,
# but effect 2 and effect 198 both came back `01 0200 0300`, identical. Two
# effect frames in flight cannot be told apart by their replies, which is why
# `link.Link` serialises the wire.
ACK_OF = {
    OP_EFFECT: 0x01,
    OP_RESOURCE: 0x01,
    OP_COUNTER: 0x02,
    OP_0C: 0x07,
    OP_0F: 0x09,
}


def acked_opcode(reply: bytes) -> int | None:
    """Which opcode a `0x01` ack is answering, or `None` if it is not one."""
    parsed = unframe(reply)
    if parsed is None or parsed[0] != 0x01 or len(parsed[1]) < 1:
        return None
    return parsed[1][0]


def matches_ack(sent_opcode: int, reply: bytes) -> bool:
    """Whether `reply` is the ack for a command of `sent_opcode`.

    Why this has to exist, measured at the desk 2026-09-22: the same `0x08` LED
    frame came back `01 0200 0800` in one session and `01 0200 0300` in the next
    — and the person watching reported a faint vibration on the first and
    nothing on the second. So the second reply was not an inconsistent ack, it
    was somebody ELSE'S notification picked up as one: the opening ends with an
    effect (`0x03`), and the ball appears to notify more than once for it.

    Taking a foreign notification as your ack is worse than losing one. It
    reports a frame as delivered that the ball may never have processed, and the
    retry that should have fired does not — the exact silent failure principle 7
    forbids, arriving through the front door.

    An opcode this does not know the ack shape of is accepted rather than
    refused: a wrong guess here would drop real acks and retry frames that
    landed, which is a worse failure than the one being fixed.
    """
    expected = ACK_OF.get(sent_opcode)
    if expected is None:
        return True
    parsed = unframe(reply)
    if parsed is None:
        return False
    opcode, payload = parsed
    if opcode != expected:
        return False
    if expected == 0x01:                      # the generic ack names its subject
        return bool(payload) and payload[0] == sent_opcode
    return True

# The opening, in the capture's exact order. The subscriptions are interleaved
# with the commands rather than done up front, and that order is reproduced
# because it is the only one known to end with a ball that plays.
#
# The CCCD bytes are recorded for what they are — what the Switch wrote — and
# are NOT used: bleak writes the descriptor itself and picks notify or indicate
# from the characteristic's own properties. So `b"\x02\x00"` here documents the
# capture, it does not configure anything. Those two characteristics never
# notified in the capture either way.
#
#   ("sub", char, cccd)      subscribe
#   ("cmd", opcode, payload) command frame
OPENING: tuple[tuple, ...] = (
    ("sub", ACK_E8, b"\x01\x00"),
    ("cmd", OP_COUNTER, b"\x01"),
    ("cmd", OP_0F, b""),
    ("cmd", OP_COUNTER, b"\x02"),
    ("cmd", OP_COUNTER, b"\x03"),
    ("cmd", OP_COUNTER, b"\x04"),
    ("sub", CE46, b"\x02\x00"),
    ("sub", CE47, b"\x02\x00"),
    ("cmd", OP_0C, bytes.fromhex("0f000000")),
    ("sub", IN_E6, b"\x01\x00"),
    ("cmd", OP_EFFECT, bytes.fromhex("0200")),
)


def frame(opcode: int, payload: bytes = b"") -> bytes:
    """One wire frame: opcode, little-endian length, payload."""
    if not 0 <= opcode <= 0xFF:
        raise ValueError(f"opcode {opcode} does not fit in one byte")
    if len(payload) > 0xFFFF:
        raise ValueError(
            f"payload is {len(payload)} bytes; the length field is u16, so "
            f"{0xFFFF} is the most one frame can carry — chunk it instead")
    return bytes([opcode]) + struct.pack("<H", len(payload)) + payload


def unframe(data: bytes) -> tuple[int, bytes] | None:
    """`(opcode, payload)` if `data` is one well-formed frame, else `None`.

    Measured 2026-09-22 against the ball: all 8 acks of a session parsed, so the
    inherited claim holds (PROTOCOL.md §3). It still returns `None` rather than
    raising, and callers log the raw hex either way — a reply that does not
    parse is a fact worth seeing at the desk, not an exception that hides it.

    The ack carries its OWN opcode, paired with the command's, not a copy of it:
    0x04 -> 0x02, 0x10 -> 0x09, 0x0c -> 0x07, 0x03 -> 0x01. See `ACK_OF`.
    """
    if len(data) < 3:
        return None
    length = struct.unpack_from("<H", data, 1)[0]
    if len(data) != 3 + length:
        return None
    return data[0], data[3:]


# The catch slot's effect: it plays whatever was last uploaded to the catch
# slots (PROTOCOL.md §7.2). wobble never plays it, so catching stays free for
# the Switch; the cry CLI names it only to say so.
SLOT_EFFECT = 213

# The stroll cry's effect: it plays the upload in `04 3c 00`, with a strong
# rumble (PROTOCOL.md §6.6, §7.2). This is the slot wobble speaks from.
STROLL_EFFECT = 129

# The one id that turns every light off, 9's held blink included — the only one
# of 170-189 that does (PROTOCOL.md §6.3, filmed twice). A protocol fact rather
# than a signal, which is why it is here and not in the config: nothing ends a
# held light by itself, and 9 has been seen still on tens of minutes later.
LIGHTS_OFF = 180


def effect(effect_id: int) -> bytes:
    """The frame that plays effect `effect_id`.

    A slot id (`129`, `213`) does not play a fixed cry, it plays whatever was
    uploaded to its slot (PROTOCOL.md §7.2). That is why the cry is uploaded on
    connect and never on an event — the transfer takes ~1.66 s and a
    notification cannot wait for it (PROTOCOL.md §7.3).
    """
    if not 0 <= effect_id <= 0xFFFF:
        raise ValueError(
            f"effect id {effect_id} is outside the u16 space the ball accepts")
    return frame(OP_EFFECT, effect_id.to_bytes(2, "little"))


# --- the LED resource -------------------------------------------------------
# An LED is not a command, it is a RESOURCE: a 0x08 transfer like the audio,
# carrying the ASCII tag "LED". These twenty bytes are identical in all six
# catch LEDs the sniffer captures hold, and only the u16 after them differs
# (PROTOCOL.md §8.4). That u16 is a 4-4-4 RGB colour (§8.3).
#
# This is the CATCH LED, which 213 plays. wobble does not write it (§7.2); the
# stroll LED it does write is `resource.fc_blob`. Kept as the record of the
# captured bytes, which the desk checks hold the framing to.
LED_CONST = bytes.fromhex("01fd014c4544000000000000000a02010100001e")

# The six colours ever caught in front of a sniffer (PROTOCOL.md §8.3). Here as
# known-good values — NOT as a creature palette, which is a non-goal. Pidgey
# is the one caught in two captures six days apart, both giving 344, which is
# what makes these read as stable rather than per-catch.
LED_KNOWN = {"bellsprout": 84, "pikachu": 138, "pidgey": 344,
             "caterpie": 386, "kakuna": 428, "rattata": 1077}


def led_resource(index: int) -> bytes:
    """One LED resource for `index`: the captured constant, then the u16.

    What is ours here is exactly two bytes wide. Everything around them is the
    capture, unaltered.
    """
    if not 0 <= index <= 0xFFFF:
        raise ValueError(f"LED index {index} is outside the u16 space")
    return bytes((3, 0)) + LED_CONST + index.to_bytes(2, "little")


def led_frame(index: int) -> bytes:
    """The 0x08 frame that carries `led_resource(index)`."""
    return frame(OP_RESOURCE, led_resource(index))


# --- the input packet -------------------------------------------------------
# Seventeen bytes, notified on IN_E6 while the link is up (PROTOCOL.md §5):
#
#   0      counter, whose step is measured per link (see below)
#   1      buttons: 0x01 top, 0x02 stick click
#   2..4   stick / d-pad position
#   5..16  six int16 LE — the IMU
#
# **The accel/gyro split is inherited, not measured.** One description says
# "accel X,Y,Z then gyro X,Y,Z", another calls the same characteristic "button +
# stick + gyroscope". Nothing here depends on which triple is which — a running
# vibration motor shows up in both — and the first triple is the one the rumble
# sweep scored (PROTOCOL.md §6.7). Named `accel` to match the more specific
# source, with this note attached.
INPUT_LEN = 17
BTN_TOP = 0x01
BTN_STICK = 0x02

# How much the counter advances per packet — **measured per link, never assumed.**
# The documented step is 3, and the first run against this ball
# stepped by 6 with a dead-flat 30 ms between packets and no doubled gaps
# anywhere: 33.3 Hz, stepping 6. Taking the inherited 3 as truth reported every
# single packet as "one lost" — a 100% loss rate on a link that was losing 1.9%,
# which is the loudest possible way to be silently wrong about a healthy link.
# So the step is an argument, and `infer_step` is how a caller gets one.
COUNTER_STEP_SEEN = (3, 6)


class Input(NamedTuple):
    """One decoded input packet."""
    counter: int
    buttons: int
    stick: bytes
    accel: tuple[int, int, int]
    gyro: tuple[int, int, int]

    @property
    def top(self) -> bool:
        return bool(self.buttons & BTN_TOP)

    @property
    def stick_click(self) -> bool:
        return bool(self.buttons & BTN_STICK)


def decode_input(data: bytes) -> Input | None:
    """One `IN_E6` notification, or `None` if it is not the 17-byte shape.

    `None` rather than a padded best effort: a packet of another length is a
    fact about the link worth counting at the desk, and a decode that quietly
    invents zeros for the missing half would read as a still ball.
    """
    if len(data) != INPUT_LEN:
        return None
    vals = struct.unpack_from("<6h", data, 5)
    return Input(counter=data[0], buttons=data[1], stick=bytes(data[2:5]),
                 accel=vals[0:3], gyro=vals[3:6])


def infer_step(counters: list[int]) -> int | None:
    """The counter's advance per packet, taken as the most common difference.

    The mode rather than the minimum or the mean: a lost packet shows up as a
    double step and would drag a mean, while a burst of two notifications
    delivered in one callback can show a difference of zero and would drag a
    minimum. `None` when there is not enough to be sure.
    """
    if len(counters) < 8:
        return None
    steps = [(b - a) % 256 for a, b in zip(counters, counters[1:])]
    steps = [s for s in steps if s]
    if not steps:
        return None
    return max(set(steps), key=steps.count)


def missed_packets(prev_counter: int, counter: int, step: int) -> int | None:
    """How many packets went missing between two counters, or `None` if unclear.

    The counter is `step * n mod 256`, so the difference between two consecutive
    packets is `step` regardless of the wrap — with a step of 3, 255 is followed
    by 2, and `(2 - 255) % 256` is still 3. A difference that is not a multiple
    of the step means the step itself is wrong here, which is a different fact
    from a loss and is reported as such rather than rounded into one.

    The blind spot is stated because the caller cannot see it: 256 counts is a
    full cycle, so losing exactly `256 / gcd(step, 256)` packets is
    indistinguishable from losing none. At the rates this link runs that is
    seconds of silence, which the window's own sample count catches long before
    this does.
    """
    if step <= 0:
        raise ValueError(f"counter step {step} must be positive")
    advanced = (counter - prev_counter) % 256
    if advanced % step:
        return None
    return advanced // step - 1
