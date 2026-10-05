#!/usr/bin/env python3
"""Known-answer checks for the ball's pure protocol code — no radio in sight.

    venv/bin/python3 tests/tables/check_protocol.py

Covers `src/ball/protocol.py`, `src/ball/resource.py` and the import-only parts
of `src/ball/button.py`: nothing here opens a link, plays a sound or shows a
dialog. Every "want" below is a literal byte string or a number written by
hand from the docstring/comment that states it, or from
`~/dev/pokeball/research/REPORT.md` (read-only, cited by section) — never
obtained by calling the function under test and echoing its own answer back.

What is deliberately NOT re-tested here, because another check already owns it:
  - `tests/tables/fake_button.py` — the press/release/stall edge logic in
    `button.Button.feed`. This file only exercises what that one does not:
    `names()`, the `mask=0` refusal, the `.down` level, and the literal
    `MASKS`/`STEPS` tables.
  - `tests/tables/fake_cry.py` — `resource.cut()`/`protocol.frame()` used as upload
    fixtures against a fake BLE client.
  - `tools/check_framing.py` — `resource.cut()` and `normalise_wav()` diffed
    byte for byte against a real Switch capture. This file tests `cut()`'s pure
    boundary/error arithmetic with synthetic bytes, and `normalise_wav()`
    against a synthetic file with a deliberately wrong byte rate — not against
    the capture, which the tool above already owns.

Each rule below carries a mutant: the same rule, removed, run on the one input
that rule exists for. A mutant that still agrees with the real answer there is
a blind spot in this file, not a fact about the code, and prints `SURVIVED`.
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.ball import protocol, resource               # noqa: E402
from src.ball.button import B, MASKS, STEPS, Button, names  # noqa: E402


class Sheet:
    def __init__(self, quiet: bool = False):
        self.quiet, self.bad = quiet, 0

    def row(self, what: str, got, want) -> None:
        good = want(got) if callable(want) else got == want
        self.bad += not good
        if not self.quiet:
            print(f"    {what:<64} "
                  f"{'ok' if good else f'<-- WRONG: {got!r}'}")

    def raises(self, what: str, fn, exc=ValueError) -> None:
        try:
            fn()
            self.row(what, "no exception", f"a {exc.__name__}")
        except exc:
            self.row(what, "raised", "raised")
        except Exception as e:  # pragma: no cover - only on a real surprise
            self.row(what, f"raised {type(e).__name__}", f"a {exc.__name__}")

    def ok(self) -> bool:
        return not self.bad


# =====================================================================
# src/ball/protocol.py
# =====================================================================

def protocol_rows(sheet: Sheet) -> None:
    say = print
    say("\n  protocol.acked_opcode (lines 78-83)")
    # The two literal examples the ACK_OF comment (lines 56-63) gives, verbatim:
    # effect's ack `01 0200 0300` and an LED resource's `01 0200 0800`.
    sheet.row("effect's generic ack names 0x03",
              protocol.acked_opcode(bytes.fromhex("0102000300")), 0x03)
    sheet.row("an LED resource's generic ack names 0x08",
              protocol.acked_opcode(bytes.fromhex("0102000800")), 0x08)
    sheet.row("too short to unframe at all -> None",
              protocol.acked_opcode(b"\x01\x00"), None)
    sheet.row("a well-formed frame that is not opcode 0x01 -> None",
              protocol.acked_opcode(bytes.fromhex("02010001")), None)
    sheet.row("opcode 0x01 with an empty payload -> None (nothing to name)",
              protocol.acked_opcode(bytes.fromhex("010000")), None)

    say("\n  protocol.matches_ack (lines 86-116)")
    sheet.row("an opcode ACK_OF does not know is accepted outright",
              protocol.matches_ack(0x99, b""), True)
    sheet.row("a reply too short to unframe is rejected",
              protocol.matches_ack(protocol.OP_EFFECT, b"\x01\x00"), False)
    sheet.row("a well-formed reply on the wrong opcode is rejected",
              protocol.matches_ack(protocol.OP_EFFECT, bytes.fromhex("0202000300")),
              False)
    sheet.row("the generic 0x01 ack naming the sent opcode matches",
              protocol.matches_ack(protocol.OP_EFFECT, bytes.fromhex("0102000300")),
              True)
    # The exact desk scenario the docstring cites (2026-09-22): an effect's ack
    # picked up as if it were the resource upload's — rejected because the
    # payload names 0x03, not 0x08.
    sheet.row("…but the same ack does NOT match a different sent opcode",
              protocol.matches_ack(protocol.OP_RESOURCE, bytes.fromhex("0102000300")),
              False)
    # OP_COUNTER's ack (0x02) is not the generic 0x01 shape, so no subject byte
    # is checked — opcode match alone is enough.
    sheet.row("a non-generic ack (0x02) matches on opcode alone",
              protocol.matches_ack(protocol.OP_COUNTER, bytes.fromhex("02010001")),
              True)

    say("\n  protocol.frame (lines 145-153, bounds at 147-148/149-150)")
    sheet.row("opcode + length + payload, byte for byte",
              protocol.frame(0x03, bytes.fromhex("0200")),
              bytes.fromhex("0302000200"))
    sheet.raises("opcode -1 is out of the one-byte range", lambda: protocol.frame(-1, b""))
    sheet.raises("opcode 256 is out of the one-byte range", lambda: protocol.frame(256, b""))
    sheet.row("opcode 0 and 255 are the edges, and both are in range",
              (protocol.frame(0, b""), protocol.frame(255, b"")) and True, True)
    sheet.raises("a payload past the u16 length field is refused",
                 lambda: protocol.frame(0, bytes(0x10000)))
    sheet.row("exactly 0xFFFF bytes of payload is the edge, and fits",
              len(protocol.frame(0, bytes(0xFFFF))), 3 + 0xFFFF)

    say("\n  protocol.unframe (lines 156-172, bounds at 167-168/170-171)")
    sheet.row("fewer than 3 bytes can never be a frame",
              protocol.unframe(b"\x01\x00"), None)
    sheet.row("empty input",
              protocol.unframe(b""), None)
    sheet.row("length field says 2 but only 1 byte follows -> None",
              protocol.unframe(b"\x01\x02\x00\x03"), None)
    sheet.row("the minimal valid frame: opcode 1, zero-length payload",
              protocol.unframe(b"\x01\x00\x00"), (0x01, b""))
    sheet.row("round-trips frame()'s own output",
              protocol.unframe(bytes.fromhex("0302000200")),
              (0x03, bytes.fromhex("0200")))

    say("\n  protocol.effect (line 189-200, bound at 197-198)")
    sheet.row("SLOT_EFFECT (213) as a frame",
              protocol.effect(213), bytes.fromhex("030200d500"))
    sheet.row("LIGHTS_OFF (180) as a frame",
              protocol.effect(180), bytes.fromhex("030200b400"))
    sheet.raises("effect id -1 is outside the u16 space", lambda: protocol.effect(-1))
    sheet.raises("effect id 0x10000 is outside the u16 space",
                 lambda: protocol.effect(0x10000))

    say("\n  protocol.led_resource / led_frame (lines 225-238)")
    # LED_CONST (line 215) cited byte for byte; the two indices are
    # LED_KNOWN's pikachu (138) and pidgey (344, caught in two captures six
    # days apart — REPORT.md §8.18) with their u16-LE tails.
    led_const = "01fd014c4544000000000000000a02010100001e"
    sheet.row("led_resource(pikachu=138): constant + its captured index",
              protocol.led_resource(138), bytes.fromhex("0300" + led_const + "8a00"))
    sheet.row("led_resource(pidgey=344): constant + its captured index",
              protocol.led_resource(344), bytes.fromhex("0300" + led_const + "5801"))
    sheet.row("led_frame wraps it in a 0x08 frame, length 24",
              protocol.led_frame(138),
              bytes.fromhex("08" + "1800" + "0300" + led_const + "8a00"))
    sheet.raises("LED index -1 is outside the u16 space",
                 lambda: protocol.led_resource(-1))
    sheet.raises("LED index 0x10000 is outside the u16 space",
                 lambda: protocol.led_resource(0x10000))

    say("\n  protocol.Input.top / .stick_click (lines 278-284)")
    mk = lambda buttons: protocol.Input(counter=0, buttons=buttons, stick=b"\0\0\0",
                                        accel=(0, 0, 0), gyro=(0, 0, 0))
    sheet.row("bit 0x01 alone reads as top, not stick",
              (mk(0x01).top, mk(0x01).stick_click), (True, False))
    sheet.row("bit 0x02 alone reads as stick, not top",
              (mk(0x02).top, mk(0x02).stick_click), (False, True))
    sheet.row("both bits read as both",
              (mk(0x03).top, mk(0x03).stick_click), (True, True))
    sheet.row("no bits reads as neither",
              (mk(0x00).top, mk(0x00).stick_click), (False, False))

    say("\n  protocol.decode_input (lines 287-298, wrong length at 294-295)")
    # Hand-built 17-byte packet: counter=5, buttons=0x01 (top), stick=11 22 33,
    # then six int16 LE: accel (1, -2, 3), gyro (-4, 5, -6). Two's complement by
    # hand: -2 -> 0xfffe -> "feff", -4 -> 0xfffc -> "fcff", -6 -> 0xfffa -> "faff".
    raw = bytes.fromhex("0501112233" "0100feff0300fcff0500faff")
    sheet.row("a real 17-byte packet decodes field for field",
              protocol.decode_input(raw),
              protocol.Input(counter=5, buttons=1, stick=b"\x11\x22\x33",
                              accel=(1, -2, 3), gyro=(-4, 5, -6)))
    sheet.row("16 bytes (one short) -> None, never a padded guess",
              protocol.decode_input(bytes(16)), None)
    sheet.row("18 bytes (one long) -> None",
              protocol.decode_input(bytes(18)), None)
    sheet.row("empty -> None",
              protocol.decode_input(b""), None)

    say("\n  protocol.infer_step (lines 301-315)")
    sheet.row("fewer than 8 counters -> None, not a guess",
              protocol.infer_step([1, 2, 3]), None)
    sheet.row("a clean run of 7 steps of 6 -> mode is 6",
              protocol.infer_step([0, 6, 12, 18, 24, 30, 36, 42]), 6)
    sheet.row("a wrap through 256 is still a step of 6",
              protocol.infer_step([250, 0, 6, 12, 18, 24, 30, 36]), 6)
    sheet.row("one outlier diff (42) does not beat the mode (6, x7)",
              protocol.infer_step([0, 6, 12, 18, 24, 30, 36, 42, 84]), 6)
    sheet.row("every diff is 0 (repeats) -> filtered to nothing -> None",
              protocol.infer_step([5, 5, 5, 5, 5, 5, 5, 5]), None)

    say("\n  protocol.missed_packets (lines 318-338, step check at 333-334)")
    # The docstring's own worked example, line by line: "with a step of 3, 255
    # is followed by 2" — that is one normal advance, zero missed.
    sheet.row("the docstring's own example: 255 -> 2, step 3 -> 0 missed",
              protocol.missed_packets(255, 2, 3), 0)
    sheet.row("4 steps of 3 apart -> 3 packets missing in between",
              protocol.missed_packets(0, 12, 3), 3)
    sheet.row("an advance that is not a multiple of the step -> None",
              protocol.missed_packets(0, 10, 3), None)
    # The documented blind spot itself (lines 327-331): a full 256-count wrap
    # reads identically to no advance at all, and the formula does not know it.
    sheet.row("the documented blind spot: 0->0 reads as -1, not 'unknown'",
              protocol.missed_packets(0, 0, 3), -1)
    sheet.raises("step 0 is refused, not divided by",
                 lambda: protocol.missed_packets(0, 5, 0))
    sheet.raises("a negative step is refused the same way",
                 lambda: protocol.missed_packets(0, 5, -1))


# =====================================================================
# src/ball/resource.py
# =====================================================================

def resource_rows(sheet: Sheet) -> None:
    say = print
    say("\n  resource.cut (lines 62-91): boundaries and kind assignment")
    out2 = resource.cut(b"x" * 499)
    sheet.row("499 bytes is 2 frames: open (500B) then close (3B)",
              (len(out2), out2[0][:2], len(out2[0]), out2[1][:2], len(out2[1])),
              (2, b"\x01\x00", 500, b"\x02\x01", 3))
    out3 = resource.cut(b"y" * 997)
    sheet.row("997 bytes is 3 frames: open, continue, close",
              (len(out3), out3[0][:2], out3[1][:2], out3[2][:2]),
              (3, b"\x01\x00", b"\x00\x01", b"\x02\x02"))
    sheet.raises("a body of one frame cannot be both open and close (line 74-80)",
                 lambda: resource.cut(b"x" * 10))
    sheet.raises("one byte past 256 chunks would wrap the index (line 81-85)",
                 lambda: resource.cut(b"x" * (498 * 256 + 1)))
    out_max = resource.cut(b"x" * (498 * 256))
    sheet.row("exactly 256 chunks is the edge, and it is accepted",
              (len(out_max), out_max[255][:2]), (256, b"\x02\xff"))
    outp = resource.cut(b"x" * 497, prefix=b"AB")
    sheet.row("prefix sits in front of the blob, inside the first frame",
              outp[0][2:4], b"AB")

    say("\n  resource.led_blob / fc_blob / led_payload (lines 107-161)")
    led_const = "01fd014c4544000000000000000a02010100001e"
    sheet.row("led_blob(pikachu=138): the constant plus its index",
              resource.led_blob(138), bytes.fromhex(led_const + "8a00"))
    sheet.raises("led_blob(-1) is outside the u16 space (line 116-118)",
                 lambda: resource.led_blob(-1))
    sheet.raises("led_blob(0x10000) is outside the u16 space",
                 lambda: resource.led_blob(0x10000))
    # FC_PIKACHU is already pikachu's own capture, so patching in 138 again is
    # a no-op — the cleanest possible known answer for the patch formula
    # (bytes 17:19 = index LE, bytes 26:28 = (index | FC_FADE) LE).
    fc_pikachu = "01fc014c45440000000000000010041f148a000f0010000000098a10"
    sheet.row("fc_blob(138) reproduces FC_PIKACHU exactly (it IS pikachu's)",
              resource.fc_blob(138), bytes.fromhex(fc_pikachu))
    sheet.raises("fc_blob(-1) is refused (line 141-143)",
                 lambda: resource.fc_blob(-1))
    sheet.raises("fc_blob(FC_FADE) is refused: the fade bit is not a colour",
                 lambda: resource.fc_blob(0x1000))
    sheet.row("led_payload: kind 3, index 0, then the blob verbatim",
              resource.led_payload(b"\xaa\xbb"), bytes.fromhex("0300aabb"))
    sheet.raises("a blob past MAX_BODY does not fit one frame (line 158-160)",
                 lambda: resource.led_payload(bytes(499)))

    say("\n  resource.frames (line 164-166): cut(), wrapped in the wire envelope")
    fr = resource.frames(b"x" * 499)
    sheet.row("opcode 0x08, u16-LE length 500, then the same first chunk",
              (fr[0][0:1], fr[0][1:3], fr[0][3:5]),
              (b"\x08", b"\xf4\x01", b"\x01\x00"))

    say("\n  resource.silence (lines 199-211): RIFF geometry, checked independently")
    # Every number below comes from the chunk sizes the function assembles
    # (fmt 50B, fact 4B, one SILENT_BLOCK is 512B, 1012 samples/block) — not
    # from calling silence() and reading its own output back.
    for blocks in (1, 2, 3):
        s = resource.silence(blocks)
        want_total = 90 + 512 * blocks
        want_riff = 82 + 512 * blocks
        want_samples = 1012 * blocks
        want_data = 512 * blocks
        riff_magic, riff_size = struct.unpack_from("<4sI", s, 0)
        fmt_id, fmt_len = struct.unpack_from("<4sI", s, 12)
        fact_pos = 12 + 8 + 50
        fact_id, fact_len = struct.unpack_from("<4sI", s, fact_pos)
        got_samples = struct.unpack_from("<I", s, fact_pos + 8)[0]
        data_pos = fact_pos + 8 + fact_len
        data_id, data_len = struct.unpack_from("<4sI", s, data_pos)
        sheet.row(f"silence({blocks}): total/RIFF-size/chunk-ids/fact-count/data-size",
                  (len(s), riff_magic, riff_size, s[8:12], fmt_id, fmt_len,
                   fact_id, got_samples, data_id, data_len),
                  (want_total, b"RIFF", want_riff, b"WAVE", b"fmt ", 50,
                   b"fact", want_samples, b"data", want_data))
        # "and that resource's own wav trimming keeps it valid" — the silent
        # wav is already exactly the shape normalise_wav produces, so trimming
        # it must be a no-op.
        sheet.row(f"…and normalise_wav(silence({blocks})) is a no-op",
                  resource.normalise_wav(s), s)

    say("\n  resource.normalise_wav (lines 246-269): the RIFF check and the fix")
    sheet.raises("not RIFF/WAVE at all is refused (line 255-256)",
                 lambda: resource.normalise_wav(b"not a riff file at all!!"))
    sheet.raises("RIFF magic present but WAVE tag wrong is refused too",
                 lambda: resource.normalise_wav(b"RIFF\x00\x00\x00\x00XXXX"))
    # A synthetic file with the exact ffmpeg bug the module docstring names
    # (lines 222-224): nAvgBytesPerSec left at the sample rate (16000) instead
    # of rate*align/per_block (8094) — plus a LIST chunk, which must be
    # dropped (line 259) rather than kept.
    fmt_body = bytes.fromhex("0200" "0100" "803e0000" "803e0000" "0002" "0400" "0000" "f403")
    fact_body = struct.pack("<I", 1012)
    data_body = b"\x00\x00"
    list_body = b"junkjunk"
    body = (b"fmt " + struct.pack("<I", len(fmt_body)) + fmt_body
            + b"LIST" + struct.pack("<I", len(list_body)) + list_body
            + b"fact" + struct.pack("<I", len(fact_body)) + fact_body
            + b"data" + struct.pack("<I", len(data_body)) + data_body)
    synth = b"RIFF" + struct.pack("<I", len(body) + 4) + b"WAVE" + body
    fixed_fmt = fmt_body[:8] + struct.pack("<I", 16000 * 512 // 1012) + fmt_body[12:]
    want_body = (b"fmt " + struct.pack("<I", len(fixed_fmt)) + fixed_fmt
                 + b"fact" + struct.pack("<I", len(fact_body)) + fact_body
                 + b"data" + struct.pack("<I", len(data_body)) + data_body)
    want = b"RIFF" + struct.pack("<I", len(want_body) + 4) + b"WAVE" + want_body
    got = resource.normalise_wav(synth)
    sheet.row("byte rate recomputed to rate*align/per_block, LIST dropped",
              got, want)


# =====================================================================
# src/ball/button.py — the import-only parts. `fake_button.py` already owns
# `Button.feed`'s press/release/stall logic in full; this only covers what it
# does not touch.
# =====================================================================

def button_rows(sheet: Sheet) -> None:
    say = print
    say("\n  button.names (line 83-85)")
    sheet.row("no bits -> 'none'", names(0x00), "none")
    sheet.row("0x01 -> 'top'", names(0x01), "top")
    sheet.row("0x02 -> 'stick'", names(0x02), "stick")
    sheet.row("both -> 'top+stick'", names(0x03), "top+stick")

    say("\n  Button(mask=0) (line 101-103)")
    sheet.raises("a Button watching no bits would never fire",
                 lambda: Button(mask=0))

    say("\n  Button.down (line 126-129): a level, not an event")
    fresh = Button()
    sheet.row(".down starts at 0", fresh.down, 0)
    fresh.feed(0.0, bytes([0, 0x01, 0, 0, 0]) + bytes(12))
    sheet.row(".down reflects the last packet's bits, not a count", fresh.down, 0x01)

    say("\n  MASKS / STEPS (lines 212-219): the desk check's own literal data")
    sheet.row("MASKS names the three masks a run can choose",
              MASKS, {"b": B, "top": 0x01, "any": 0x03})
    sheet.row("STEPS has three steps, wanting 1, 1, 2 presses",
              tuple(s[2] for s in STEPS), (1, 1, 2))
    sheet.row("…and none of them ever wants 0",
              all(s[2] > 0 for s in STEPS), True)


# =====================================================================
# mutants — one rule removed at a time, run on the one input that rule exists
# for. `protocol.py`/`resource.py` are module functions, not a class, so each
# mutant here is a small standalone reimplementation rather than a subclass —
# the same idea `check_log.py` uses, one level down.
# =====================================================================

def mutant_rows() -> list[tuple[str, bool]]:
    results = []

    def check(name: str, real, mutant) -> None:
        results.append((name, real == mutant))  # True == unchanged == survived

    # 1. unframe that ignores the length field entirely.
    def unframe_ignores_length(data: bytes):
        if len(data) < 3:
            return None
        return data[0], data[3:]

    case = b"\x01\x02\x00\x03"  # length says 2, only 1 byte follows
    check("unframe ignoring the length field",
          protocol.unframe(case), unframe_ignores_length(case))

    # 2. ack_matches that accepts any 0x01 regardless of who it names.
    def matches_ack_any_0x01(sent_opcode: int, reply: bytes) -> bool:
        expected = protocol.ACK_OF.get(sent_opcode)
        if expected is None:
            return True
        parsed = protocol.unframe(reply)
        if parsed is None:
            return False
        opcode, _payload = parsed
        return opcode == expected  # dropped: does the payload name sent_opcode?

    foreign_ack = bytes.fromhex("0102000300")  # names OP_EFFECT (0x03)
    check("matches_ack accepting any 0x01 ack",
          protocol.matches_ack(protocol.OP_RESOURCE, foreign_ack),
          matches_ack_any_0x01(protocol.OP_RESOURCE, foreign_ack))

    # 3. frame without the opcode bound.
    def frame_no_opcode_bound(opcode: int, payload: bytes = b"") -> bytes:
        return bytes([opcode & 0xFF]) + struct.pack("<H", len(payload)) + payload

    def real_raises(fn) -> bool:
        try:
            fn()
            return False
        except ValueError:
            return True

    check("frame with no opcode bound",
          real_raises(lambda: protocol.frame(256, b"")),
          real_raises(lambda: frame_no_opcode_bound(256, b"")))

    # 4. decode_input that pads a short packet instead of refusing it.
    def decode_input_pads_short(data: bytes):
        if len(data) > protocol.INPUT_LEN:
            return None
        padded = data + bytes(protocol.INPUT_LEN - len(data))
        vals = struct.unpack_from("<6h", padded, 5)
        return protocol.Input(counter=padded[0], buttons=padded[1],
                               stick=bytes(padded[2:5]), accel=vals[0:3], gyro=vals[3:6])

    check("decode_input padding a short packet",
          protocol.decode_input(bytes(16)), decode_input_pads_short(bytes(16)))

    # 5. effect() with no id bound (wraps instead of refusing).
    def effect_no_bounds(effect_id: int) -> bytes:
        return protocol.frame(protocol.OP_EFFECT, (effect_id & 0xFFFF).to_bytes(2, "little"))

    check("effect() with no id bound",
          real_raises(lambda: protocol.effect(0x10000)),
          real_raises(lambda: effect_no_bounds(0x10000)))

    # 6. missed_packets that skips the step<=0 guard.
    def missed_packets_no_step_check(prev_counter: int, counter: int, step: int):
        advanced = (counter - prev_counter) % 256
        if advanced % step:  # ZeroDivisionError on step=0 — not the documented ValueError
            return None
        return advanced // step - 1

    def raises_value_error(fn) -> bool:
        try:
            fn()
            return False
        except ValueError:
            return True
        except ZeroDivisionError:
            return False  # it raised, but not the informative error the real one does

    check("missed_packets with no step check",
          raises_value_error(lambda: protocol.missed_packets(0, 5, 0)),
          raises_value_error(lambda: missed_packets_no_step_check(0, 5, 0)))

    # 7. cut() with no MAX_CHUNKS bound.
    def cut_no_max_chunks(blob: bytes, prefix: bytes = b""):
        body = prefix + blob
        total = -(-len(body) // resource.MAX_BODY)
        if total < 2:
            raise ValueError("too small")
        out = []
        for i in range(total):
            part = body[i * resource.MAX_BODY:(i + 1) * resource.MAX_BODY]
            kind = (resource.KIND_OPEN if i == 0 else
                    (resource.KIND_CLOSE if i == total - 1 else resource.KIND_CONTINUE))
            out.append(bytes((kind, i & 0xFF)) + part)
        return out

    big = b"x" * (498 * 256 + 1)
    check("cut() with no MAX_CHUNKS bound",
          real_raises(lambda: resource.cut(big)),
          real_raises(lambda: cut_no_max_chunks(big)))

    return results


def main() -> int:
    print(__doc__.strip().splitlines()[0])
    sheet = Sheet()
    protocol_rows(sheet)
    resource_rows(sheet)
    button_rows(sheet)
    ok = sheet.ok()

    print("\n  the control — each rule removed in turn, on the one input it exists for")
    for name, survived in mutant_rows():
        ok &= not survived
        print(f"    mutant: {name:<52} "
              f"{'<-- SURVIVED' if survived else 'caught'}")

    print("\n" + ("ALL CASES MATCH the known answer" if ok else
                  "SOMETHING DOES NOT MATCH — the rows above, not this line"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
