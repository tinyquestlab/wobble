"""Play an effect on the ball from the command line.

    venv/bin/python3 -m src.ball.effect 199
    venv/bin/python3 -m src.ball.effect 198 199 200 --gap 1.5
    venv/bin/python3 -m src.ball.effect 241 --repeat 3

The first proof against real hardware, and the tool the desk checks in tasks 04
and 05 are run with. It prints the ball's ack rather than summarising it: what
an ack actually contains was an open question when it was written, and the desk
is where it got answered (PROTOCOL.md §3).

Exits non-zero when any write went unacked, so a run that lost a frame cannot
be mistaken for a quiet one.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from . import protocol
from .link import BallNotFound, open_ball

log = logging.getLogger("wobble.effect")


def _describe(reply: bytes | None) -> str:
    """The ack, as raw bytes and as whatever structure it turns out to have."""
    if reply is None:
        return "no ack"
    parsed = protocol.unframe(reply)
    if parsed is None:
        return f"{reply.hex()} ({len(reply)}B, does not parse as a frame)"
    opcode, payload = parsed
    return f"{reply.hex()} -> opcode {opcode:#04x}, payload {payload.hex() or '(empty)'}"


async def run(args) -> int:
    lost = 0
    try:
        async with open_ball(args.addr, opening=not args.no_opening, scan_timeout=args.scan) as link:
            for round_no in range(1, args.repeat + 1):
                for effect_id in args.ids:
                    label = f"effect {effect_id}"
                    if args.repeat > 1:
                        label += f" (round {round_no}/{args.repeat})"
                    reply = await link.send(protocol.effect(effect_id), label)
                    print(f"{label}: {_describe(reply)}")
                    if reply is None:
                        lost += 1
                    # The ack comes back before the sound has played, so the
                    # link has to outlive it — a disconnect mid-cry is silence
                    # that says nothing about the protocol.
                    await asyncio.sleep(args.gap)

            stats = link.stats()
            print(f"\nlink: {stats['frames_acked']}/{stats['frames_sent']} frames acked, "
                  f"{stats['frames_retried']} needed a retry, {stats['frames_lost']} lost "
                  f"({stats['writes']} writes on the wire, "
                  f"{stats['first_try_pct']}% landed first try)")
            print(f"input packets seen: {stats['input_packets']}")
    except BallNotFound as exc:
        print(exc, file=sys.stderr)
        return 2
    return 1 if lost else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m src.ball.effect", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ids", nargs="+", type=int, metavar="ID",
                    help="effect id(s) to play, in order. 213 plays whatever "
                         "resource was uploaded last, rather than a fixed cry")
    ap.add_argument("--gap", type=float, default=2.0, metavar="S",
                    help="seconds to wait after each effect, so the link outlives "
                         "the sound (default: 2.0)")
    ap.add_argument("--repeat", type=int, default=1, metavar="N",
                    help="play the whole sequence N times (default: 1)")
    ap.add_argument("--scan", type=float, default=45.0, metavar="S",
                    help="how long to scan for the ball. The default is long "
                         "because it sleeps fast and a desk check needs time "
                         "to press its button (default: 45)")
    ap.add_argument("--addr", default=None,
                    help="BLE address, skipping the scan")
    ap.add_argument("--no-opening", action="store_true",
                    help="skip the opening sequence — subscribe to the ack and "
                         "nothing else")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="log every frame, not just the retries")
    args = ap.parse_args(argv)

    for effect_id in args.ids:
        if not 0 <= effect_id <= 0xFFFF:
            ap.error(f"effect id {effect_id} is outside the u16 space the ball accepts")
    if args.repeat < 1:
        ap.error("--repeat must be at least 1")

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)-7s %(message)s")
    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main())
