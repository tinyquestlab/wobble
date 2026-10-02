"""The radio: find the ball, open a link, send a frame and wait for its ack.

Everything here needs hardware to exercise, which is why everything that does
not is in `protocol.py` instead.

**The retry is not optional.** The output characteristic is write-without-
response, so a lost frame raises nothing, anywhere — the write succeeds and the
ball simply never heard it. This link was measured at 85% on the first try,
degrading past twelve minutes, and a cry is eight writes: without a retry,
better than two runs in three lose a frame and the whole upload comes out
silent for a reason that has nothing to do with the protocol (PROTOCOL.md §9).
Three tries turn 85% into 99%.

**And every retry is logged, individually.** A retry loop that quietly succeeds
turns a measurable defect into folklore — "the ball is a bit flaky" instead of
"this link lost 15% of its frames this afternoon". The counters on `Link` are
there to be read, not to be decorative.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import time

from . import protocol

log = logging.getLogger(__name__)

SCAN_TIMEOUT = 25.0
CONNECT_TIMEOUT = 30.0
ACK_TIMEOUT = 5.0
ATTEMPTS = 3
# The slowest ack anyone has measured, with headroom — the floor under any
# deadline a caller shortens. PROTOCOL.md §9: five acks on an established link
# came back in 0.52-0.61s (0.16s on a fresh one), so 2 s leaves room. A deadline under that does not make the
# ball answer sooner; it retries a frame that was going to land, writes the
# effect again, and then reports a silence that never happened.
SLOWEST_ACK_S = 2.0


class BallNotFound(RuntimeError):
    """No ball answered the scan. Carries the sentence to show a person."""


async def find_ball(timeout: float | None = SCAN_TIMEOUT, name: str = protocol.NAME):
    """Scan for the ball by advertised name. Returns the device, or `None`.

    By name because on macOS there is no stable address to target. The ball
    sleeps quickly when it is not being handled and does not advertise while
    asleep, so `None` here usually means "asleep", not "absent" — the caller is
    the one that has to say so in words (principle 7), and every caller in this
    repo does.

    **`timeout=None` keeps one scanner up until the ball answers**, and then
    never returns `None` at all. That is what the daemon asks for (task 32): a
    scan that is torn down every 25 s and reopened 20 s later is deaf for 46% of
    the time, and the thing it is deaf to is a thumb on the button — the ball
    advertises for a few seconds after a press and is asleep again long before
    the next scan opens, so the press lands in the gap and nothing anywhere says
    it was missed. macOS cannot scan passively (bleak refuses it outright), so
    the only question is how long the active scan runs, and the answer is
    measured rather than guessed: continuous costs 1.42% of one core.
    """
    from bleak import BleakScanner

    loop = asyncio.get_running_loop()
    found: asyncio.Future = loop.create_future()

    def seen(device, advertisement):
        if (advertisement.local_name or device.name or "") == name and not found.done():
            found.set_result(device)

    log.info("scanning for %r — press the ball's top button so it advertises", name)
    scanner = BleakScanner(detection_callback=seen)
    await scanner.start()
    try:
        return await asyncio.wait_for(found, timeout)
    except asyncio.TimeoutError:
        log.warning("no ball answered in %.0fs — it sleeps fast; press its top button", timeout)
        return None
    finally:
        with contextlib.suppress(Exception):
            await scanner.stop()


class Link:
    """One framed write at a time, each one waited on until the ball answers.

    The ball replies to every command on `ACK_E8`, and the Switch waits for that
    reply — roughly 0.3 s per audio chunk — rather than streaming. Firing frames
    on a fixed sleep instead gets them dropped: the transfer completes on the
    wire and nothing plays.

    **Why a lock.** A single coroutine walking a list of frames would never need
    one. Here the daemon can be uploading a cry while a notification wants to
    play an effect, and two senders sharing one reply queue take each other's
    acks.

    Measured rather than assumed (2026-09-22, against a fake client with acks
    tagged by frame, one write dropped): without the lock the sender whose frame
    was DROPPED was handed the next sender's ack and reported success, while the
    retry fired on the wrong frame. A lost write reported as delivered is the
    silent failure principle 7 exists to forbid.

    Settled at the desk 2026-09-22: the ball's ack for effect 2 and for effect
    198 are byte-identical (`01 0200 0300`). It carries no id of the frame it
    answers, so for the one opcode this project sends most, the lock is not an
    optimisation — it is the only thing making an ack mean anything.

    The cost, accepted: one slow write blocks the next, so an effect can queue
    behind a cry upload. The wire is serial regardless, and the cry is uploaded
    on connect rather than on an event precisely so this never lands on a
    notification (plan.md).
    """

    def __init__(self, client):
        self.client = client
        self._replies: asyncio.Queue[bytes] = asyncio.Queue()
        self._wire = asyncio.Lock()
        self._held = False        # the wire is being kept across frames — see `hold`
        # Read these. They are the loss rate, and the loss rate is the reason
        # the retry exists — a link that needed 40 retries this hour is a fact
        # about the afternoon, not a shrug.
        self.frames_sent = 0      # framed writes asked for
        self.frames_acked = 0     # …that the ball answered, eventually
        self.frames_lost = 0      # …that it never did, after every attempt
        self.frames_retried = 0   # …that took more than one attempt
        self.writes = 0           # individual writes put on the wire
        self.input_packets = 0    # notifications seen on IN_E6
        self.foreign_replies = 0  # acks for somebody else's command, discarded
        # Set to a callable(t, raw) to also SEE the input stream rather than
        # only count it. Task 05's rumble desk check is the first reader: the
        # ball's own IMU is the instrument that says whether an effect moved it.
        # Left as a hook rather than a decode here because what the packets mean
        # belongs in `protocol`, and what to do with them belongs to the caller.
        self.input_sink = None

    # --- notifications ------------------------------------------------------

    def _on_reply(self, _sender, data: bytearray) -> None:
        self._replies.put_nowait(bytes(data))

    def _on_input(self, _sender, data: bytearray) -> None:
        # Counted here, decoded by whoever asked for it. A count alone is enough
        # to prove the subscription is live, which is what the opening claims;
        # `input_sink` is for the caller that needs the samples themselves.
        self.input_packets += 1
        if self.input_sink is not None:
            self.input_sink(time.perf_counter(), bytes(data))

    async def subscribe(self, char: str) -> None:
        handler = self._on_reply if char == protocol.ACK_E8 else self._on_input
        await self.client.start_notify(char, handler)
        log.debug("subscribed %s", char[-4:])

    # --- writing ------------------------------------------------------------

    async def send(self, data: bytes, label: str = "", *,
                   timeout: float = ACK_TIMEOUT,
                   attempts: int = ATTEMPTS) -> bytes | None:
        """Write one frame and return the ball's reply, or `None` once spent.

        What the retry buys is not free: replaying a chunk the ball has already
        accepted is unattested, and might append rather than replace. That is a
        better bet than a guaranteed hole — but it is a bet, so a retried frame
        says so in the log, and a later failure can be read as "possibly a
        duplicate" instead of a mystery.
        """
        label = label or (f"{data[0]:#04x}" if data else "empty")
        shown = data[:12].hex() + ("…" if len(data) > 12 else "")

        # `hold` already owns the lock; taking it again here would deadlock.
        async with (contextlib.nullcontext() if self._held else self._wire):
            self.frames_sent += 1
            for attempt in range(1, attempts + 1):
                while not self._replies.empty():   # drop anything left from before
                    self._replies.get_nowait()

                self.writes += 1
                try:
                    await self.client.write_gatt_char(protocol.OUT_E7, data, response=False)
                except Exception as exc:          # bleak raises its own family here
                    log.warning("%s: the write itself failed (%s) — attempt %d/%d",
                                label, exc, attempt, attempts)
                    continue

                reply = await self._wait_for_ack(data[0], label, timeout)
                if reply is None:
                    log.warning("%s: %s (%dB) went unacked in %.1fs — attempt %d/%d",
                                label, shown, len(data), timeout, attempt, attempts)
                    continue

                if attempt > 1:
                    self.frames_retried += 1
                    log.warning("%s: acked on attempt %d/%d — it landed, but the link "
                                "dropped %d frame(s) getting there",
                                label, attempt, attempts, attempt - 1)
                self.frames_acked += 1
                log.debug("%s: %s (%dB) <- %s", label, shown, len(data), reply.hex())
                return reply

        self.frames_lost += 1
        log.error("%s: %s (%dB) never acked after %d attempts", label, shown, len(data), attempts)
        return None

    async def _wait_for_ack(self, sent_opcode: int, label: str,
                            timeout: float) -> bytes | None:
        """The ack for THIS frame, within `timeout`, or `None`.

        Replies belonging to another command are dropped and the wait continues
        on what is left of the budget — accepting one would report a frame as
        delivered that the ball may never have seen. Every discard is counted,
        because "how often does a foreign notification land mid-send" is a real
        property of this link that nobody has measured.
        """
        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                return None
            try:
                reply = await asyncio.wait_for(self._replies.get(), remaining)
            except asyncio.TimeoutError:
                return None
            if protocol.matches_ack(sent_opcode, reply):
                return reply
            self.foreign_replies += 1
            log.warning("%s: a reply for another command arrived (%s) — ignoring it "
                        "and waiting for our own", label, reply.hex())

    async def send_frame(self, opcode: int, payload: bytes = b"", label: str = "") -> bytes | None:
        """`send`, but framing the opcode and payload for you."""
        return await self.send(protocol.frame(opcode, payload), label or f"{opcode:#04x}")

    @contextlib.asynccontextmanager
    async def hold(self):
        """Keep the wire for a whole sequence, instead of one frame at a time.

        A resource upload is eight frames that belong to each other: the ball
        reassembles them by the `index` byte in each one, so anything else
        written in the middle is at best a frame the ball answers out of turn,
        and at worst a cry with somebody else's bytes in it. `send` serialises
        one frame; this serialises a sequence.

        The daemon is where it earns its place — a signal loop and an upload
        share one link, and the upload runs on connect while the loop is already
        beating (plan.md). Nothing in the MVP sends concurrently yet, so today
        this is a guard against a bug that has not happened.

        `send` checks `_held` rather than re-entering the lock, because an
        `asyncio.Lock` is not reentrant and the deadlock would look exactly like
        a ball that stopped answering.
        """
        async with self._wire:
            self._held = True
            try:
                yield self
            finally:
                self._held = False

    async def play_opening(self) -> bool:
        """Replay the opening in the capture's exact order. `True` if all acked.

        Carrying on past a failure is deliberate: a half-opened ball is worth
        seeing at the desk, and stopping would hide which step is the one that
        fails. The caller decides what an incomplete opening means.
        """
        ok = True
        for step in protocol.OPENING:
            if step[0] == "sub":
                await self.subscribe(step[1])
            else:
                _, opcode, payload = step
                if await self.send_frame(opcode, payload) is None:
                    ok = False
        log.info("opening replayed%s — %d input packet(s) so far",
                 "" if ok else " WITH LOSSES", self.input_packets)
        return ok

    # --- what the link cost -------------------------------------------------

    def stats(self) -> dict:
        """The loss rate, as numbers somebody can read."""
        return {
            "frames_sent": self.frames_sent,
            "frames_acked": self.frames_acked,
            "frames_lost": self.frames_lost,
            "frames_retried": self.frames_retried,
            "writes": self.writes,
            "first_try_pct": (
                round(100.0 * (self.frames_acked - self.frames_retried) / self.frames_sent, 1)
                if self.frames_sent else None),
            "input_packets": self.input_packets,
            "foreign_replies": self.foreign_replies,
        }


@contextlib.asynccontextmanager
async def open_ball(target=None, *, opening: bool = True,
                    scan_timeout: float = SCAN_TIMEOUT,
                    connect_timeout: float = CONNECT_TIMEOUT,
                    on_disconnect=None):
    """Find the ball, connect, replay the opening, and yield the `Link`.

    `target` may be an address or a device already found; `None` scans. Raises
    `BallNotFound` rather than returning `None`, because every caller in this
    repo has to say something to a person when there is no ball, and a `None`
    that gets used as a link is the silence principle 7 forbids.
    """
    from bleak import BleakClient

    if target is None:
        target = await find_ball(scan_timeout)
        if target is None:
            raise BallNotFound(
                f"no ball answered a {scan_timeout:.0f}s scan for {protocol.NAME!r}. "
                f"It sleeps quickly when it is not handled — press its top button "
                f"and try again.")

    live: dict = {}

    def dropped(client):
        # Principle 7: the link going away is the one event that must never be
        # inferred from silence. Logged here so every caller gets it for free,
        # with the frame count at the moment it happened.
        link = live.get("link")
        if live.get("closing"):
            log.debug("link closed as asked")
        else:
            log.warning("THE BALL DISCONNECTED — link lost after %d frame(s)",
                        link.frames_sent if link else 0)
        if on_disconnect is not None:
            on_disconnect(client)

    log.info("connecting…")
    async with BleakClient(target, timeout=connect_timeout,
                           disconnected_callback=dropped) as client:
        log.info("connected")
        link = Link(client)
        live["link"] = link
        if opening:
            await link.play_opening()
        else:
            await link.subscribe(protocol.ACK_E8)
        try:
            yield link
        finally:
            live["closing"] = True
            log.info("link closing — %s", link.stats())
