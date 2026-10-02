"""Upload a resource into the ball's slot, and optionally play it.

    venv/bin/python3 -m src.ball.cry assets/cries/pikachu.wav
    venv/bin/python3 -m src.ball.cry assets/cries/pikachu.wav --play
    venv/bin/python3 -m src.ball.cry assets/cries/pikachu.wav --raw    # send it unchanged

`129` does not play a fixed cry — it plays **whatever was uploaded to the
stroll cry slot** (PROTOCOL.md §7.2), which is why the same id reads as one
creature one morning and another the next. So the slot is state. The daemon
uploads on connect, never on an event: the transfer costs ~1.7 s and a
notification cannot wait for it (PROTOCOL.md §7.3). This CLI is the manual
half, and `upload` is the function the daemon calls too.

It writes the stroll slot, the one wobble speaks from. The catch slot that 213
plays is left alone, so catching stays free for the Switch (task 35).

**A partial upload is refused, not played.** If any frame goes unacked the slot
holds a resource with a hole in it, and `213` would then play something — half
a cry, or the previous one, or silence — and none of those says which happened.
Principle 7: a failure gets said in words. So the exit is non-zero, `--play` is
skipped, and the line explains that the slot is now in an unknown state.

The framing lives in `resource.py` and is checkable without a ball.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

from . import protocol, resource
from .link import BallNotFound, open_ball

log = logging.getLogger("wobble.cry")

CRY_EFFECT = protocol.STROLL_EFFECT


async def upload(link, payloads: list[bytes], label: str = "cry") -> int:
    """Send one resource's frames, holding the wire for all of them.

    Returns how many went unacked. The wire is held because the ball reassembles
    by the `index` byte and a frame written in between belongs to nobody — see
    `Link.hold`.
    """
    lost = 0
    async with link.hold():
        for i, payload in enumerate(payloads):
            kind, index = payload[0], payload[1]
            reply = await link.send(protocol.frame(protocol.OP_RESOURCE, payload),
                                    f"{label} frame {i} (kind {kind}, index {index})")
            if reply is None:
                lost += 1
                log.error("%s frame %d of %d never acked — the slot now holds a "
                          "resource with a hole in it", label, i, len(payloads))
    return lost


async def run(args) -> int:
    blob = open(args.wav, "rb").read()
    if not args.raw:
        try:
            blob = resource.normalise_wav(blob)
        except ValueError as exc:
            print(f"{args.wav}: {exc} — use --raw to send it unchanged anyway",
                  file=sys.stderr)
            return 2

    try:
        payloads = resource.cut(blob, b"" if args.no_prefix else resource.STROLL_CRY_PREFIX)
    except ValueError as exc:
        print(f"{args.wav}: {exc}", file=sys.stderr)
        return 2

    print(f"{os.path.basename(args.wav)}: {len(blob)} bytes -> {len(payloads)} frame(s) "
          f"({', '.join(str(len(p) - 2) for p in payloads)} bytes of body)")

    try:
        async with open_ball(args.addr, scan_timeout=args.scan) as link:
            lost = await upload(link, payloads)

            if lost:
                print(f"\n{lost} of {len(payloads)} frame(s) never acked. The slot is in an "
                      f"UNKNOWN state — not playing it, because what came out would not say "
                      f"whether the upload or the trigger was the thing that failed.")
            else:
                print(f"\nall {len(payloads)} frame(s) acked — the slot holds this resource")
                if args.play:
                    reply = await link.send(protocol.effect(CRY_EFFECT), f"effect {CRY_EFFECT}")
                    print(f"effect {CRY_EFFECT}: {'no ack' if reply is None else reply.hex()}")
                    # The ack comes back before the sound has played, so the link
                    # has to outlive it — a disconnect mid-cry is silence that
                    # says nothing about the protocol.
                    await asyncio.sleep(args.linger)

            stats = link.stats()
            print(f"\nlink: {stats['frames_acked']}/{stats['frames_sent']} frames acked, "
                  f"{stats['frames_retried']} needed a retry, {stats['frames_lost']} lost "
                  f"({stats['writes']} writes on the wire, "
                  f"{stats['first_try_pct']}% landed first try)")
    except BallNotFound as exc:
        print(exc, file=sys.stderr)
        return 2
    return 1 if lost else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m src.ball.cry", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("wav", help="the file to put in the slot. Nintendo assets are never "
                                "committed — assets/cries/ is gitignored and filled at "
                                "install time")
    ap.add_argument("--play", action="store_true",
                    help=f"play effect {CRY_EFFECT} once the upload is acked")
    ap.add_argument("--raw", action="store_true",
                    help="skip normalise_wav and send the file exactly as it is on disk")
    ap.add_argument("--no-prefix", action="store_true",
                    help=f"omit the {resource.STROLL_CRY_PREFIX.hex()} slot address in front "
                         f"of the RIFF header — for a resource that is not a cry")
    ap.add_argument("--linger", type=float, default=3.0, metavar="S",
                    help="seconds to keep the link open after triggering (default: 3.0)")
    ap.add_argument("--scan", type=float, default=45.0, metavar="S",
                    help="how long to scan for the ball (default: 45)")
    ap.add_argument("--addr", default=None, help="BLE address, skipping the scan")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="log every frame, not just the retries")
    args = ap.parse_args(argv)

    if not os.path.exists(args.wav):
        ap.error(f"no such file: {args.wav}")

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)-7s %(message)s")
    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main())
