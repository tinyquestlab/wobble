#!/usr/bin/env python3
"""Check the ball's connection worker — `Ball.run()` and the session it holds — without a ball.

    venv/bin/python3 tests/tables/check_ball_worker.py

`check_ball_mirror.py` checks the mirror's POLICY by calling its methods one at
a time against a fake link. Nothing executed the worker itself: the loop that
looks for the ball, opens the link, says it is there, plays beats, notices it
went, forgets what it held and goes round again. That loop is where principle 7
lives for the radio — criterion 9, "the ball disconnects mid-session -> the menu
bar says so, in words" — so this file runs it, in-process, for real.

**Only `find_ball` and `open_ball` are faked** (`src/ball/link.py`), and the
link they hand over. The worker, the session, the upload loop, the framing and
the cutting of the real cry are the shipped ones. The fake world is scripted:
the ball advertises at a moment of the script's choosing, a disconnect callback
fires on cue, a scan raises `BallNotFound` or `RuntimeError`, a connect throws,
a frame is never acked. Every `say(label, text)` is recorded with its time, and
every frame the fake link receives is unframed into `("effect", id)`,
`("upload", index)`, `("led", index)` or `("battery", None)`.

**The real radio is fenced off before anything is imported.** `bleak` is
replaced in `sys.modules` by a stub whose `BleakScanner` and `BleakClient`
raise and record when constructed. The first rows run the REAL `find_ball` and
`open_ball` against that stub — the known-good reference leg that proves the
fence is armed — and the last row says nothing in any scenario reached it.

Every known answer comes from a docstring or comment in `src/mirrors/ball.py`
and is cited beside its row. The mutants are the same file with one rule taken
out as text, compiled as a sibling module, and the whole table run against it:
each one must turn at least one row wrong.
"""
from __future__ import annotations

import asyncio
import collections
import contextlib
import logging
import sys
import time
import types
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# --- the fence: no real bleak, ever -------------------------------------------
# Installed before `src` is imported, so `from bleak import ...` inside
# `find_ball` / `open_ball` (link.py:66, :312) can only ever find this stub.

TOUCHED: list[str] = []
BLEAK_WAS_LOADED = "bleak" in sys.modules


class _RealRadio:
    def __init__(self, *_a, **_kw):
        TOUCHED.append(type(self).__name__)
        raise RuntimeError(f"the real {type(self).__name__} was reached — this check "
                           f"must never touch the radio")


BLEAK_STUB = types.ModuleType("bleak")
BLEAK_STUB.BleakScanner = type("BleakScanner", (_RealRadio,), {})
BLEAK_STUB.BleakClient = type("BleakClient", (_RealRadio,), {})
sys.modules["bleak"] = BLEAK_STUB

from src.ball import link as link_mod                                  # noqa: E402
from src.ball import protocol, resource                                # noqa: E402
from src.ball.link import BallNotFound                                 # noqa: E402
from src.core.ladder import load as load_ladder                        # noqa: E402
from src.core.signals import Kind                                      # noqa: E402
from src.mirrors import ball as ball_mod                               # noqa: E402

# `cry.upload` logs every unacked frame at ERROR (cry.py:55). The lost frames
# here are lost on purpose and asserted on as state; without a handler Python's
# last-resort one would print them as if something had gone wrong.
logging.getLogger().addHandler(logging.NullHandler())

REAL_CRY = ROOT / "assets/cries/pikachu.wav"
ACK = b"\x01\x02\x00\x03\x00"
DEVICE = types.SimpleNamespace(name=protocol.NAME, address="FAKE-0000")
REAL_FIND, REAL_OPEN = link_mod.find_ball, link_mod.open_ball
# The index byte of every frame the real cry is cut into — what `_put` must
# send, in order, on every connect.
CRY_INDEXES = [p[1] for p in resource.cut(resource.normalise_wav(REAL_CRY.read_bytes()),
                                          resource.STROLL_CRY_PREFIX)]
WORLD: "World | None" = None


class BleakError(Exception):
    """Stands in for bleak's own family — ball.py:272 catches `Exception` for it."""


# --- the scripted world ---------------------------------------------------------

class World:
    """Everything the fakes do, and everything they saw, for one scenario."""

    def __init__(self):
        self.t0 = time.monotonic()
        self.said: list[tuple[float, str, str]] = []
        self.wire: list[tuple[float, str, int | None, dict]] = []
        self.scans: list[dict] = []
        self.active = 0                  # scans started and not yet stopped
        self.ad_at: float | None = None  # when the ball next advertises; None = asleep
        self.scan_faults: collections.deque = collections.deque()
        self.connect_faults: collections.deque = collections.deque()
        self.lose: set[str] = set()       # label fragments whose frame is never acked
        self.slow: dict[str, float] = {}  # label fragment -> seconds on the wire
        self.raise_on: dict[str, Exception] = {}
        self.battery: bytes | Exception = b"\x57"   # 0x57 == 87%
        self.opened: list = []
        self.link: FakeLink | None = None
        self.on_disconnect = None
        self.ball = None

    def now(self) -> float:
        return time.monotonic() - self.t0

    def say(self, label: str, text: str = "") -> None:
        self.said.append((self.now(), label, text))

    def labels(self, start: int = 0) -> list[str]:
        return [label for _t, label, _x in self.said[start:]]

    def said_at(self, label: str, start: int = 0) -> float | None:
        return next((t for t, lab, _x in self.said[start:] if lab == label), None)

    def log(self, what: str, n: int | None = None, kw: dict | None = None) -> None:
        self.wire.append((self.now(), what, n, kw or {}))

    def kinds(self, start: int = 0) -> list[tuple[str, int | None]]:
        return [(what, n) for _t, what, n, _k in self.wire[start:]]

    def effects(self, start: int = 0) -> list[int]:
        return [n for _t, what, n, _k in self.wire[start:] if what == "effect"]

    def advertise(self, after: float) -> None:
        self.ad_at = time.monotonic() + after

    def drop(self) -> None:
        """The ball going away by itself: bleak's disconnected callback, and a
        link nothing reaches any more."""
        self.link.gone = True
        self.log("drop")
        self.on_disconnect(self.link.client)

    def snapshot(self):
        b = self.ball
        return None if b is None else (b.connected, b.slot, b.colour, b.lit, b.battery)


class FakeClient:
    """The GATT read the session makes (`2A19`), logged into the wire."""

    def __init__(self, world: World):
        self.world = world

    async def read_gatt_char(self, uuid):
        self.world.log("battery", None, {"uuid": str(uuid)})
        await asyncio.sleep(0)
        if isinstance(self.world.battery, Exception):
            raise self.world.battery
        return self.world.battery


class FakeLink:
    """The `Link` surface the mirror uses: `send`, `hold`, `client`, `input_sink`."""

    def __init__(self, world: World):
        self.world = world
        self.client = FakeClient(world)
        self.input_sink = None
        self.gone = False

    @contextlib.asynccontextmanager
    async def hold(self):
        yield self

    async def send(self, data: bytes, label: str = "", *,
                   timeout: float = link_mod.ACK_TIMEOUT,
                   attempts: int = link_mod.ATTEMPTS):
        w = self.world
        opcode, payload = protocol.unframe(data)
        if opcode == protocol.OP_RESOURCE:
            if payload[0] == resource.KIND_LED:
                # The falling half carries the plain index (check_ball_mirror.py:138-142).
                what, n = "led", int.from_bytes(payload[19:21], "little")
            else:
                what, n = "upload", payload[1]
        else:
            what, n = "effect", int.from_bytes(payload, "little")
        w.log(what, n, {"timeout": timeout, "attempts": attempts, "label": label})
        for fragment, exc in w.raise_on.items():
            if fragment in label:
                raise exc
        for fragment, seconds in w.slow.items():
            if fragment in label:
                await asyncio.sleep(seconds)
        await asyncio.sleep(0)
        if self.gone or any(fragment in label for fragment in w.lose):
            return None
        return ACK


async def fake_find_ball(timeout=link_mod.SCAN_TIMEOUT, name=protocol.NAME):
    """`find_ball` (link.py:47): the device once the ball advertises, `None` at
    a deadline, or whatever fault the script queued for this scan."""
    w = WORLD
    rec = {"timeout": timeout, "start": w.now(), "stop": None, "snapshot": w.snapshot()}
    w.scans.append(rec)
    w.active += 1
    try:
        await asyncio.sleep(0)
        if w.scan_faults:
            raise w.scan_faults.popleft()
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            t = time.monotonic()
            if w.ad_at is not None and t >= w.ad_at:
                w.ad_at = None          # connected: it stops advertising
                return DEVICE
            if deadline is not None and t >= deadline:
                return None
            await asyncio.sleep(0.005)
    finally:
        # The real one awaits `scanner.stop()` here (link.py:83-85) — which is
        # why a cancel nobody awaits leaves a scanner running (ball.py:345-347).
        await asyncio.sleep(0)
        rec["stop"] = w.now()
        w.active -= 1


@contextlib.asynccontextmanager
async def fake_open_ball(target=None, *, on_disconnect=None, **_kw):
    """`open_ball` (link.py:300): connect or raise, yield a link, close it."""
    w = WORLD
    w.log("open")
    w.opened.append(target)
    await asyncio.sleep(0)
    if w.connect_faults:
        raise w.connect_faults.popleft()
    link = FakeLink(w)
    w.link, w.on_disconnect = link, on_disconnect
    try:
        yield link
    finally:
        w.log("close")
        link.gone = True


# --- the table ------------------------------------------------------------------

class Sheet:
    def __init__(self, quiet: bool = False):
        self.quiet, self.bad, self.rows = quiet, 0, 0

    def row(self, what: str, got, want) -> None:
        good = got == want
        self.bad += not good
        self.rows += 1
        if not self.quiet:
            print(f"    {what:<66} {'ok' if good else f'<-- WRONG: {got!r}, wanted {want!r}'}")


def within(value: float | None, lo: float, hi: float) -> str:
    """A timing row's answer: "in range", or the number that was not."""
    if value is None:
        return "never happened"
    return "in range" if lo <= value <= hi else f"{value:.3f}s, outside {lo}-{hi}s"


async def until(pred, within_s: float = 1.0) -> bool:
    end = time.monotonic() + within_s
    while time.monotonic() < end:
        if pred():
            return True
        await asyncio.sleep(0.005)
    return bool(pred())


async def stop(task) -> bool:
    """Cancel the worker. `True` when ONE cancel ended it, cancelled."""
    task.cancel()
    await asyncio.wait([task], timeout=0.3)
    first = task.done() and task.cancelled()
    for _ in range(20):
        if task.done():
            break
        task.cancel()
        await asyncio.wait([task], timeout=0.2)
    return first


def fresh(m, retry: float) -> World:
    global WORLD
    WORLD = w = World()
    m.RETRY_S = retry
    w.ball = m.Ball(REAL_CRY, on_press=lambda: None, say=w.say)
    return w


async def up(w: World, start: int = 0, within_s: float = 1.0) -> bool:
    """Until this connect's upload has ended one way or the other, then a beat."""
    ok = await until(lambda: any(l in ("slot", "SLOT UNKNOWN", "NO CRY")
                                 for l in w.labels(start)), within_s)
    await asyncio.sleep(0.03)
    return ok


CONNECT_WIRE = ([("open", None), ("battery", None), ("effect", protocol.LIGHTS_OFF)]
                + [("upload", i) for i in CRY_INDEXES])
CONNECT_SAID = ["battery", "lights off", "slot"]


# --- the scenarios ----------------------------------------------------------------
# Each takes the module under test (the real one, or a mutant of it), a sheet and
# the voices, and runs in its own event loop.

async def s_first_connect(m, sheet, v):
    w = fresh(m, retry=0.3)
    ball = w.ball
    w.advertise(0.5)
    task = asyncio.ensure_future(ball.run())
    await up(w, within_s=1.5)
    # ball.py:330-333 — said once per search; link.py:56 — `None` keeps one scanner up.
    sheet.row("the search is one scanner with no deadline (task 32)",
              [s["timeout"] for s in w.scans], [None])
    sheet.row("…announced once for a half-second wait, not once a cycle",
              w.labels().count("no ball"), 1)
    sheet.row("the link opens on the very device the scan returned",
              [o is DEVICE for o in w.opened], [True])
    # ball.py:364 "ball connected" if first; :367-382 battery, then 180, then the cry.
    sheet.row("said: searching, connected, battery, lights off, cry in",
              w.labels(), ["no ball", "ball connected"] + CONNECT_SAID)
    sheet.row("wire: battery read, 180, then every frame of the cry, in order",
              w.kinds(), CONNECT_WIRE)
    sheet.row("…and the 180 is the full-budget one, not the let-go try",
              [k["attempts"] for _t, what, n, k in w.wire if what == "effect"],
              [link_mod.ATTEMPTS])
    sheet.row("connected, 87% from the byte the ball sent, cry in, dark",
              (ball.connected, ball.battery, ball.slot, ball.lit),
              (True, 87, ball_mod.CRY, None))
    sheet.row("the link's input stream feeds the B button (ball.py:362)",
              w.link.input_sink == ball._button.feed, True)
    mark = len(w.wire)
    ball.refresh(v["done"])
    ball.beat(v["done"])
    await until(lambda: v["done"].effect in w.effects(mark))
    await asyncio.sleep(0.03)
    sheet.row("the first beat comes after the cry: colour, held light, cry",
              w.kinds(mark), [("led", v["done"].led), ("effect", v["done"].light),
                              ("effect", v["done"].effect)])
    await stop(task)


async def s_drop_and_back(m, sheet, v):
    w = fresh(m, retry=0.3)
    ball = w.ball
    w.advertise(0.02)
    task = asyncio.ensure_future(ball.run())
    await up(w)
    ball.refresh(v["done"])
    ball.beat(v["done"])
    await until(lambda: v["done"].effect in w.effects())
    await asyncio.sleep(0.03)
    sheet.row("before the drop: connected, 87%, colour and held light up",
              (ball.connected, ball.battery, ball.colour, ball.lit),
              (True, 87, v["done"].led, v["done"].light))
    said, wired = len(w.said), len(w.wire)
    t_drop = w.now()
    w.drop()
    w.advertise(0.15)
    await until(lambda: "ball back" in w.labels(said))
    await up(w, said + 3)
    await until(lambda: "light back" in w.labels(said), 0.5)
    await asyncio.sleep(0.03)
    # ball.py:286-292 — said when the link went away by itself; :364 "ball back";
    # :42-45 and :375 — a done still showing gets its light back once the cry is in.
    sheet.row("said: disconnected once, searching, back, connect, light back",
              w.labels(said), ["ball disconnected", "no ball", "ball back"] + CONNECT_SAID
              + ["light back"])
    reopened = max(i for i, (_t, what, _n, _k) in enumerate(w.wire) if what == "open")
    sheet.row("…the pending done's colour and 9 go up after the cry, not before",
              w.kinds(reopened), CONNECT_WIRE + [("led", v["done"].led),
                                                 ("effect", v["done"].light)])
    after = w.kinds(wired)
    closed = after.index(("close", None)) + 1 if ("close", None) in after else len(after)
    sheet.row("nothing is written to a link that went away — it just closes",
              after[:closed], [("drop", None), ("close", None)])
    second = w.scans[1] if len(w.scans) > 1 else {}
    # ball.py:242-247, :294-298 — a clean drop goes straight back to looking.
    sheet.row("the next search opens at once — no RETRY_S after a clean drop",
              within(second.get("start", 1e9) - t_drop, 0.0, 0.1), "in range")
    # ball.py:277-285 — connected, slot, colour, lit and battery all forgotten.
    sheet.row("…and by then the old link's state is all forgotten",
              second.get("snapshot"), (False, ball_mod.UNKNOWN, None, None, None))
    sheet.row("…and it is one deadline-free scanner again",
              second.get("timeout", "no scan"), None)
    await stop(task)


async def s_let_go(m, sheet, v):
    w = fresh(m, retry=0.3)
    ball = w.ball
    w.advertise(0.02)
    task = asyncio.ensure_future(ball.run())
    await up(w)
    ball.refresh(v["done"])
    ball.beat(v["done"])
    await until(lambda: v["done"].effect in w.effects())
    await asyncio.sleep(0.03)
    said, wired = len(w.said), len(w.wire)
    ball.set_wanted(False)
    await until(lambda: ("close", None) in w.kinds(wired))
    await asyncio.sleep(0.4)          # past RETRY_S: a scan here is a radio nobody asked for
    # ball.py:286-289 — "a second sentence for one decision reads as two events".
    sheet.row("said: 'ball off', then the light ended — no 'ball disconnected'",
              w.labels(said), ["ball off", "lights off"])
    # ball.py:407-414 — the link is still here to end the light with.
    sheet.row("the last frame before letting go is 180, then the link closes",
              w.kinds(wired), [("effect", protocol.LIGHTS_OFF), ("close", None)])
    last = next((k for _t, what, n, k in reversed(w.wire)
                 if what == "effect" and n == protocol.LIGHTS_OFF), {})
    sheet.row("…one short try, 1.5s and one attempt, as a quit can wait for",
              (last.get("timeout"), last.get("attempts")), (1.5, 1))
    sheet.row("after: not connected, no battery, dark, slot and colour unknown",
              (ball.connected, ball.battery, ball.lit, ball.slot, ball.colour),
              (False, None, None, ball_mod.UNKNOWN, None))
    # ball.py:251-257 — waiting, not scanning.
    sheet.row("no search while it is not wanted, for longer than RETRY_S",
              len(w.scans), 1)
    said = len(w.said)
    t_on = w.now()
    w.advertise(0.05)
    ball.set_wanted(True)
    await until(lambda: "ball back" in w.labels(said))
    await up(w, said + 3)
    await until(lambda: "light back" in w.labels(said), 0.5)
    await asyncio.sleep(0.03)
    sheet.row("'Connect' opens a search at once (ball.py:166-169)",
              within(w.scans[1]["start"] - t_on if len(w.scans) > 1 else None, 0.0, 0.05),
              "in range")
    # The done is still showing, so its light comes back after the cry (ball.py:375).
    sheet.row("…said as wanted, searching, back, and the done's light back",
              w.labels(said), ["ball wanted", "no ball", "ball back"] + CONNECT_SAID
              + ["light back"])
    await stop(task)


async def s_off_from_the_start(m, sheet, v):
    w = fresh(m, retry=0.1)
    w.ball.set_wanted(False)
    w.advertise(0.0)
    task = asyncio.ensure_future(w.ball.run())
    await asyncio.sleep(0.3)
    sheet.row("switched off before it ever ran: no scan, only its own sentence",
              (len(w.scans), w.labels()), (0, ["ball off"]))
    await stop(task)


async def s_not_found(m, sheet, v):
    w = fresh(m, retry=0.3)
    why = f"no ball answered a 25s scan for {protocol.NAME!r}."
    w.scan_faults.append(BallNotFound(why))
    w.advertise(0.0)
    task = asyncio.ensure_future(w.ball.run())
    await until(lambda: len(w.scans) >= 2)
    fail = next(((t, x) for t, lab, x in w.said[1:] if lab == "no ball"), (None, ""))
    # ball.py:261-269 — not an error, it backs off, and it says why.
    sheet.row("BallNotFound is said as 'no ball', carrying the exception's words",
              (w.labels()[:2], why in fail[1] and "Retrying every" in fail[1]),
              (["no ball", "no ball"], True))
    sheet.row("…never as BALL LINK FAILED", "BALL LINK FAILED" in w.labels(), False)
    sheet.row("…and the next search waits RETRY_S (ball.py:294-304)",
              within(w.scans[1]["start"] - fail[0] if len(w.scans) > 1 and fail[0] else None,
                     0.29, 0.45), "in range")
    await up(w, 2)
    sheet.row("nothing was ever connected, so nothing is said as disconnected",
              "ball disconnected" in w.labels(), False)
    await stop(task)


async def s_scan_failed(m, sheet, v):
    w = fresh(m, retry=0.3)
    w.scan_faults.append(RuntimeError("Bluetooth is powered off"))
    w.advertise(0.0)
    task = asyncio.ensure_future(w.ball.run())
    await until(lambda: len(w.scans) >= 2)
    t_fail = w.said_at("BALL LINK FAILED")
    text = next((x for _t, lab, x in w.said if lab == "BALL LINK FAILED"), "")
    # ball.py:272-275 — any other exception, named by type, and a back-off.
    sheet.row("a scan that raised RuntimeError is BALL LINK FAILED, type and words",
              (w.labels()[:2], "RuntimeError: Bluetooth is powered off" in text),
              (["no ball", "BALL LINK FAILED"], True))
    sheet.row("…and the next search waits RETRY_S, not a tight loop",
              within(w.scans[1]["start"] - t_fail if len(w.scans) > 1 and t_fail else None,
                     0.29, 0.45), "in range")
    sheet.row("…the scan that threw was stopped", w.scans[0]["stop"] is not None, True)
    await up(w, 2)
    # ball.py:280-282 — a failed first scan is not a link, so the first real one
    # is "connected", never "back" from somewhere it never was.
    sheet.row("…the first link after a failed scan is 'ball connected', not 'back'",
              ("ball connected" in w.labels(), "ball back" in w.labels()), (True, False))
    await stop(task)


async def s_connect_failed(m, sheet, v):
    w = fresh(m, retry=0.3)
    w.connect_faults.append(BleakError("device disconnected during connect"))
    w.advertise(0.0)
    task = asyncio.ensure_future(w.ball.run())
    await until(lambda: "BALL LINK FAILED" in w.labels())
    t_fail = w.said_at("BALL LINK FAILED")
    text = next((x for _t, lab, x in w.said if lab == "BALL LINK FAILED"), "")
    sheet.row("a connect that threw is BALL LINK FAILED, named as bleak's error",
              "BleakError: device disconnected during connect" in text, True)
    w.advertise(0.0)
    await until(lambda: len(w.scans) >= 2)
    sheet.row("…never connected, so not disconnected either; retried after RETRY_S",
              (w.labels()[:3], within(w.scans[1]["start"] - t_fail
                                      if len(w.scans) > 1 and t_fail else None, 0.29, 0.45)),
              (["no ball", "BALL LINK FAILED", "no ball"], "in range"))
    await stop(task)


async def s_failed_while_connected(m, sheet, v):
    w = fresh(m, retry=0.3)
    ball = w.ball
    w.advertise(0.02)
    task = asyncio.ensure_future(ball.run())
    await up(w)
    ball.refresh(v["done"])
    ball.beat(v["done"])
    await until(lambda: v["done"].effect in w.effects())
    await asyncio.sleep(0.03)
    said, wired = len(w.said), len(w.wire)
    w.raise_on[f"effect {v['done'].effect}"] = OSError("the write went nowhere")
    ball.beat(v["done"])
    await until(lambda: len(w.scans) >= 2)
    t_fail = w.said_at("BALL LINK FAILED", said)
    # ball.py:272-275 then :277-292: the failure, then the drop it caused.
    sheet.row("a link that throws mid-session: FAILED, then 'ball disconnected'",
              w.labels(said)[:2], ["BALL LINK FAILED", "ball disconnected"])
    sheet.row("…the link was closed on the way out", ("close", None) in w.kinds(wired), True)
    sheet.row("…the next search waits RETRY_S after a failure",
              within(w.scans[1]["start"] - t_fail if len(w.scans) > 1 and t_fail else None,
                     0.29, 0.45), "in range")
    sheet.row("…and finds the failed link's state forgotten, battery included",
              w.scans[1]["snapshot"] if len(w.scans) > 1 else None,
              (False, ball_mod.UNKNOWN, None, None, None))
    await stop(task)


async def s_connect_cuts_the_wait(m, sheet, v):
    w = fresh(m, retry=3.0)
    w.scan_faults.append(RuntimeError("Bluetooth is powered off"))
    task = asyncio.ensure_future(w.ball.run())
    await until(lambda: "BALL LINK FAILED" in w.labels())
    await asyncio.sleep(0.1)
    w.ball.set_wanted(False)
    await asyncio.sleep(0.1)
    t_on = w.now()
    w.advertise(0.05)
    w.ball.set_wanted(True)
    await until(lambda: len(w.scans) >= 2, 1.0)
    # ball.py:300-304 — "Connect" does not sit out the rest of a 3 s retry.
    sheet.row("'Connect' chosen during a 3s retry wait: a search within 50 ms",
              within(w.scans[1]["start"] - t_on if len(w.scans) > 1 else None, 0.0, 0.05),
              "in range")
    sheet.row("…said: failed, off, wanted, searching",
              w.labels()[:5], ["no ball", "BALL LINK FAILED", "ball off", "ball wanted",
                               "no ball"])
    await stop(task)


async def s_given_up_via_run(m, sheet, v):
    w = fresh(m, retry=0.1)
    task = asyncio.ensure_future(w.ball.run())
    await until(lambda: len(w.scans) >= 1)
    await asyncio.sleep(0.1)
    w.ball.set_wanted(False)
    await asyncio.sleep(0.3)
    # ball.py:357-359 — given up on while looking is a clean return, not a failure.
    sheet.row("switched off mid-search: 'ball off', nothing else said",
              w.labels(), ["no ball", "ball off"])
    sheet.row("…the scan is stopped and no other one opens",
              (w.active, len(w.scans)), (0, 1))
    await stop(task)


async def s_look_directly(m, sheet, v):
    w = fresh(m, retry=0.1)
    ball = w.ball
    ball._dropped.clear()
    search = asyncio.ensure_future(ball._look_for_ball())
    await until(lambda: len(w.scans) >= 1)
    ball._dropped.set()
    got = await search
    # Checked the instant the search returns, before the loop turns again: an
    # un-awaited cancel has not reached the scanner yet (ball.py:345-352).
    stopped, active = w.scans[0]["stop"] is not None, w.active
    sheet.row("given up on: the search returns None", got, None)
    sheet.row("…with its scanner already stopped when it returns",
              (stopped, active), (True, 0))
    ball._dropped.clear()
    w.advertise(0.05)
    got = await ball._look_for_ball()
    waiting = len(ball._dropped._waiters)
    sheet.row("found: the search returns the device", got is DEVICE, True)
    sheet.row("…and nothing is left waiting on the give-up when it returns",
              waiting, 0)
    w.scan_faults.append(RuntimeError("scanner refused"))
    try:
        await ball._look_for_ball()
        got = "returned"
    except RuntimeError as exc:
        got = str(exc)
    sheet.row("a scan that threw re-raises out of the search (ball.py:341-343)",
              got, "scanner refused")
    sheet.row("…one 'no ball' per search: three searches, three sentences",
              w.labels(), ["no ball"] * 3)


async def s_play_loop(m, sheet, v):
    done, needs = v["done"], v["needs"]
    w = fresh(m, retry=0.3)
    ball = w.ball
    w.advertise(0.02)
    task = asyncio.ensure_future(ball.run())
    await up(w)
    ball.refresh(done)
    await until(lambda: done.light in w.effects())
    await asyncio.sleep(0.03)
    wired = len(w.wire)
    ball.beat(done)
    ball.quiet()
    await asyncio.sleep(0.1)
    # ball.py:222-230 — drop a beat that has not gone out yet.
    sheet.row("B pressed before the worker took the beat: it never goes out",
              w.kinds(wired), [])
    ball.beat(done)
    await until(lambda: done.effect in w.effects(wired))
    await asyncio.sleep(0.03)
    sheet.row("…and the next beat does, the cry alone over the held 9",
              w.kinds(wired), [("effect", done.effect)])
    wired = len(w.wire)
    ball.refresh(needs)
    ball.refresh(done)
    await asyncio.sleep(0.1)
    # ball.py:476-491 — a voice whose held light is already up is left alone.
    sheet.row("a wake that finds the held light already up sends nothing",
              w.kinds(wired), [])
    ball.refresh(needs)
    await asyncio.sleep(0.1)
    sheet.row("a voice with no held light is left to its own beat — nothing sent",
              w.kinds(wired), [])
    ball.refresh(done)
    await asyncio.sleep(0.05)
    wired = len(w.wire)
    w.slow[f"effect {done.effect}"] = 0.2
    ball.beat(done)
    await until(lambda: done.effect in w.effects(wired))
    ball.refresh(needs)
    ball.beat(needs)
    await until(lambda: needs.effect in w.effects(wired), 0.8)
    # ball.py:452-458 — cleared after the wait, so nothing handed over mid-send is lost.
    sheet.row("a beat handed over while the last was on the wire is still played",
              w.effects(wired), [done.effect, needs.effect])
    sheet.row("…and neither was late enough to be called late",
              "beat late" in w.labels(), False)
    await stop(task)


async def s_linger(m, sheet, v):
    """A catch plays out before 180 ends it, and a beat still cuts it (task 56)."""
    caught, needs = v["caught"], v["needs"]
    w = fresh(m, retry=0.3)
    ball = w.ball
    w.advertise(0.02)
    task = asyncio.ensure_future(ball.run())
    await up(w)
    wired = len(w.wire)
    ball.beat(replace(caught, lasts_s=0.4))
    await until(lambda: protocol.LIGHTS_OFF in w.effects(wired), 1.5)
    at = {n: t for t, what, n, _k in w.wire[wired:] if what == "effect"}
    sheet.row("a catch goes out, and then 180 — nothing is showing",
              w.effects(wired), [caught.effect, protocol.LIGHTS_OFF])
    gap = (at[protocol.LIGHTS_OFF] - at[caught.effect]
           if caught.effect in at and protocol.LIGHTS_OFF in at else None)
    sheet.row("…and the 180 waits out its lasts_s (0.4s)", within(gap, 0.38, 0.7), "in range")
    wired = len(w.wire)
    ball.beat(replace(caught, lasts_s=3.0))
    await until(lambda: caught.effect in w.effects(wired))
    started = w.now()
    await asyncio.sleep(0.1)
    ball.beat(needs)
    await until(lambda: needs.effect in w.effects(wired), 1.5)
    landed = next((t for t, what, n, _k in w.wire[wired:]
                   if what == "effect" and n == needs.effect), None)
    sheet.row("a beat during it is played at once — a later id replaces it",
              within(None if landed is None else landed - started, 0.05, 0.5), "in range")
    await stop(task)


async def s_losses(m, sheet, v):
    done = v["done"]
    w = fresh(m, retry=0.3)
    ball = w.ball
    w.advertise(0.02)
    task = asyncio.ensure_future(ball.run())
    await up(w)
    said, wired = len(w.said), len(w.wire)
    w.lose |= {"led", f"light {done.light}", f"effect {done.effect}"}
    ball.beat(done)
    await until(lambda: "BALL SILENT" in w.labels(said))
    await asyncio.sleep(0.03)
    # ball.py:610-616, :546-548, :583-589 — three unacked frames, three sentences.
    sheet.row("colour, light and cry all unacked: NO COLOUR, NO LIGHT, BALL SILENT",
              w.labels(said), ["NO COLOUR", "NO LIGHT", "BALL SILENT"])
    sheet.row("…every frame still went out, in order",
              w.kinds(wired), [("led", done.led), ("effect", done.light),
                               ("effect", done.effect)])
    sheet.row("…and none of them is claimed: colour and light still unknown",
              (ball.colour, ball.lit), (None, None))
    silent = next((x for _t, lab, x in w.said if lab == "BALL SILENT"), "")
    budget = next((k["attempts"] for _t, what, n, k in reversed(w.wire)
                   if what == "effect" and n == done.effect), None)
    sheet.row("BALL SILENT names the attempts that send was actually given",
              f"after {budget} attempt(s)" in silent, True)
    sheet.row("an unacked frame is a sentence, not a lost link",
              (ball.connected, "BALL LINK FAILED" in w.labels(), len(w.scans)), (True, False, 1))
    await stop(task)


async def s_reput(m, sheet, v):
    needs = v["needs"]
    w = fresh(m, retry=0.3)
    ball = w.ball
    w.lose.add("cry frame 1 (")
    w.advertise(0.02)
    task = asyncio.ensure_future(ball.run())
    await up(w)
    sheet.row("a connect upload that lost a frame leaves the slot UNKNOWN",
              (w.labels()[-1], ball.slot), ("SLOT UNKNOWN", ball_mod.UNKNOWN))
    w.lose.clear()
    wired = len(w.wire)
    ball.refresh(needs)
    ball.beat(needs)
    await until(lambda: needs.effect in w.effects(wired))
    await asyncio.sleep(0.05)
    # ball.py:392-400 — the beat first; an upload never rides a beat's wake.
    sheet.row("a wake with a beat waiting plays it, and uploads nothing",
              w.kinds(wired), [("effect", needs.effect)])
    said, wired = len(w.said), len(w.wire)
    ball.refresh(None)
    await until(lambda: "lights off" in w.labels(said))
    await asyncio.sleep(0.03)
    reput = next((x for _t, lab, x in w.said[said:] if lab == "slot"), "")
    sheet.row("the next idle wake puts the cry up again, said before and after",
              (w.labels(said), "not in the slot" in reput),
              (["slot", "slot", "lights off"], True))
    sheet.row("…every frame of it, and the slot is the cry again",
              (w.kinds(wired), ball.slot),
              ([("upload", i) for i in CRY_INDEXES] + [("effect", protocol.LIGHTS_OFF)],
               ball_mod.CRY))
    await stop(task)


async def s_empty_battery(m, sheet, v):
    w = fresh(m, retry=0.3)
    w.battery = b""
    w.advertise(0.02)
    task = asyncio.ensure_future(w.ball.run())
    await up(w)
    # ball.py:443-444 — an empty answer leaves `battery` as it was, and says nothing.
    sheet.row("an empty battery read: no percentage, nothing said, link up",
              (w.ball.battery, w.labels(), w.ball.connected),
              (None, ["no ball", "ball connected", "lights off", "slot"], True))
    sheet.row("…and the connect still went battery, 180, cry", w.kinds(), CONNECT_WIRE)
    await stop(task)


async def s_cancel(m, sheet, v):
    w = fresh(m, retry=0.3)
    w.advertise(0.02)
    task = asyncio.ensure_future(w.ball.run())
    await up(w)
    wired = len(w.wire)
    first = await stop(task)
    # ball.py:270-271 — a cancel is re-raised, never taken for a link failure.
    sheet.row("cancelled while connected: one cancel ends it, and the link closes",
              (first, ("close", None) in w.kinds(wired), "BALL LINK FAILED" in w.labels()),
              (True, True, False))
    w = fresh(m, retry=3.0)
    w.scan_faults.append(RuntimeError("Bluetooth is powered off"))
    task = asyncio.ensure_future(w.ball.run())
    await until(lambda: "BALL LINK FAILED" in w.labels())
    sheet.row("cancelled inside a retry wait: one cancel ends it", await stop(task), True)
    w = fresh(m, retry=0.3)
    task = asyncio.ensure_future(w.ball.run())
    await until(lambda: len(w.scans) >= 1)
    await asyncio.sleep(0.05)
    first = await stop(task)
    sheet.row("cancelled mid-search: one cancel ends it, and the scanner stops",
              (first, w.active, w.labels()), (True, 0, ["no ball"]))


SCENARIOS = (
    ("the first connect, in the order ball.py gives it", s_first_connect),
    ("the ball goes away by itself, and comes back", s_drop_and_back),
    ("let go on purpose, then asked for again", s_let_go),
    ("switched off before the worker ever runs", s_off_from_the_start),
    ("a scan that ends in BallNotFound", s_not_found),
    ("a scan that raises anything else", s_scan_failed),
    ("a connect that throws", s_connect_failed),
    ("the link throws while connected", s_failed_while_connected),
    ("'Connect' during a retry wait", s_connect_cuts_the_wait),
    ("given up on in the middle of a search", s_given_up_via_run),
    ("_look_for_ball on its own: cancelled and awaited", s_look_directly),
    ("the play loop: quiet, wakes, a beat mid-send", s_play_loop),
    ("a catch plays out before the light goes off", s_linger),
    ("frames that are never acked", s_losses),
    ("a cry that did not go up goes up on the next idle wake", s_reput),
    ("a battery that answers with nothing", s_empty_battery),
    ("a cancel is a cancel", s_cancel),
)


def run_all(m, quiet: bool = False) -> Sheet:
    sheet = Sheet(quiet)
    ladder = load_ladder()
    voices = {"done": ladder.voice(Kind.DONE), "needs": ladder.voice(Kind.NEEDS),
              "caught": ladder.outcome("caught")}
    for title, scenario in SCENARIOS:
        if not quiet:
            print(f"\n  {title}")
        try:
            asyncio.run(asyncio.wait_for(scenario(m, sheet, voices), 10.0))
        except Exception as exc:                    # a mutant may crash; that is a wrong row
            sheet.row(f"{scenario.__name__} ran to the end", f"{type(exc).__name__}: {exc}",
                      "no exception")
    m.RETRY_S = 20.0
    return sheet


# --- the mutants: ball.py with one rule taken out, as text --------------------------

MUTANTS = (
    ("sleeps RETRY_S after a clean drop too",
     [("            if failed:\n                # Only after a failure (task 32).",
       "            if True:\n                # Only after a failure (task 32).")]),
    ("keeps the battery after the link is gone",
     [("                    self.battery = None\n", "                    pass\n")]),
    ("keeps the held light after the link is gone",
     [("                    self.lit = None\n", "                    pass\n")]),
    ("stays 'connected' after the link is gone",
     [("                    self.connected = False\n", "                    pass\n")]),
    ("says 'ball disconnected' after an asked-for drop",
     [("                    if self.wanted:\n                        self.say(\"ball disconnected\",",
       "                    if True:\n                        self.say(\"ball disconnected\",")]),
    ("never says 'ball disconnected' at all",
     [("self.say(\"ball disconnected\",", "(lambda *a: None)(\"ball disconnected\",")]),
    ("never says 'ball back'",
     [("\"ball connected\" if first else \"ball back\"", "\"ball connected\"")]),
    ("a failed first scan counts as a link (the old ball.py:293)",
     [("            if failed:\n                # Only after a failure",
       "            first = False\n            if failed:\n                # Only after a failure")]),
    ("does not cancel the scan when given up",
     [("            for task in (scan, given_up):", "            for task in (given_up,):")]),
    ("cancels the scan without awaiting it",
     [("                    task.cancel()\n"
       "                    with contextlib.suppress(asyncio.CancelledError):\n"
       "                        await task\n",
       "                    task.cancel()\n")]),
    ("a scan with a deadline, 'no ball' every cycle",
     [("link_mod.find_ball(timeout=None)", "link_mod.find_ball(timeout=0.2)")]),
    ("scans while switched off",
     [("            if not self.wanted:\n                # Waiting, not scanning.",
       "            if False:\n                # Waiting, not scanning.")]),
    ("no back-off after BallNotFound",
     [("                failed = True\n                self.say(\"no ball\",",
       "                self.say(\"no ball\",")]),
    ("no back-off after a link failure",
     [("                failed = True\n                self.say(\"BALL LINK FAILED\",",
       "                self.say(\"BALL LINK FAILED\",")]),
    ("BallNotFound said as BALL LINK FAILED",
     [("            except link_mod.BallNotFound as exc:",
       "            except ZeroDivisionError as exc:")]),
    ("'Connect' does not cut the retry wait short",
     [("await asyncio.wait_for(self._asked.wait(), RETRY_S)", "await asyncio.sleep(RETRY_S)")]),
    ("a cancel swallowed as a link failure",
     [("            except asyncio.CancelledError:\n                raise\n"
       "            except Exception as exc:",
       "            except BaseException as exc:")]),
    ("battery read after the upload, not before",
     [("            await self._read_battery(link, announce=True)\n", ""),
      ("            await self._put(link)\n\n            while not",
       "            await self._put(link)\n"
       "            await self._read_battery(link, announce=True)\n\n            while not")]),
    ("no lights-off on connect",
     [("            await self._lights_off(link, \"on connect, so",
       "            (lambda *a: None)(link, \"on connect, so")]),
    ("no cry uploaded on connect",
     [("            await self._put(link)\n\n            while not",
       "\n            while not")]),
    ("a cry that failed is never put up again",
     [("                elif self.slot != CRY:", "                elif False:")]),
    ("lights left on when letting go",
     [("            if not self.wanted:\n                # Let go on purpose",
       "            if False:\n                # Let go on purpose")]),
    ("the wake cleared before waiting, not after",
     # The waiter has not run yet when this clears, so it is the same mutant as
     # clearing first; anchored on the `try` because `_linger` has the line above it.
     [("        try:\n            await asyncio.wait(waiters, return_when=asyncio.FIRST_COMPLETED)",
       "        self._woken.clear()\n        try:\n            await asyncio.wait(waiters, return_when=asyncio.FIRST_COMPLETED)")]),
    ("a catch cut short by the next 180",
     [("                    if voice.lasts_s is not None:\n", "                    if False:\n")]),
    ("a catch that a new beat cannot cut",
     [("        while self._beat is None and not self._dropped.is_set():",
       "        while not self._dropped.is_set():")]),
    ("B drops nothing",
     [("        self._beat = self._beat_at = None", "        pass")]),
    ("an empty battery byte crashes the link",
     [("        if not raw:\n            return\n", "")]),
    ("a lit held light re-sent on every wake",
     [("        if want.light is None or self.lit == want.light:",
       "        if want.light is None:")]),
    ("an unacked held light in a beat, said nowhere",
     [("self.say(\"NO LIGHT\", f\"effect {voice.light} went unacked — this \"",
       "(lambda *a: None)(\"NO LIGHT\", f\"effect {voice.light} went unacked — this \"")]),
    ("BALL SILENT said nowhere",
     [("self.say(\"BALL SILENT\",", "(lambda *a: None)(\"BALL SILENT\",")]),
    ("NO COLOUR said nowhere",
     [("self.say(\"NO COLOUR\",", "(lambda *a: None)(\"NO COLOUR\",")]),
)


def mutant_module(name: str, edits) -> types.ModuleType | str:
    """ball.py with `edits` applied, as a sibling module — or why it could not be."""
    text = Path(ball_mod.__file__).read_text()
    for old, new in edits:
        if text.count(old) != 1:
            return f"its target is in ball.py {text.count(old)} times, not once"
        text = text.replace(old, new)
    mod = types.ModuleType(f"src.mirrors._mutant_ball")
    mod.__package__ = "src.mirrors"
    exec(compile(text, f"<mutant: {name}>", "exec"), mod.__dict__)
    return mod


def main() -> int:
    print(__doc__.strip().splitlines()[0])
    fence = Sheet()
    print("\n  the radio is fenced off before anything runs")
    fence.row("bleak was not loaded before the stub went in", BLEAK_WAS_LOADED, False)

    async def reference_leg():
        try:
            await REAL_FIND(timeout=0.01)
        except RuntimeError:
            pass
        try:
            async with REAL_OPEN(DEVICE):
                pass
        except RuntimeError:
            pass

    asyncio.run(reference_leg())
    # The known-good leg: the REAL find_ball and open_ball must trip the fence,
    # or a green table below would prove nothing about the radio staying shut.
    fence.row("reference: the real find_ball and open_ball hit the stub",
              TOUCHED, ["BleakScanner", "BleakClient"])
    TOUCHED.clear()
    link_mod.find_ball, link_mod.open_ball = fake_find_ball, fake_open_ball
    fence.row("…and the mirror's link module now hands out the fakes",
              (ball_mod.link_mod.find_ball, ball_mod.link_mod.open_ball),
              (fake_find_ball, fake_open_ball))

    sheet = run_all(ball_mod)
    rows, bad = fence.rows + sheet.rows, fence.bad + sheet.bad

    print("\n  the control — every rule removed in turn, each must break the table")
    for name, edits in MUTANTS:
        mod = mutant_module(name, edits)
        if isinstance(mod, str):
            verdict, wrong = f"NOT APPLIED — {mod}", True
        else:
            wrong = run_all(mod, quiet=True).bad == 0
            verdict = "survived" if wrong else "caught"
        bad += wrong
        rows += 1
        print(f"    mutant: {name:<58} {verdict}")

    end = Sheet()
    print("\n  after every scenario and every mutant")
    end.row("nothing reached the real BleakScanner or BleakClient", TOUCHED, [])
    rows, bad = rows + end.rows, bad + end.bad

    print(f"\n  {rows} rows")
    print("ALL CASES MATCH the known answer" if not bad else f"{bad} WRONG — the rows above")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
