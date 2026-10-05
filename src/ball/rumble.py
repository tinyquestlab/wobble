"""Measure the rumble — by the ball's own IMU, and by a person's leg.

    venv/bin/python3 -m src.ball.rumble                       # trace, on the desk
    venv/bin/python3 -m src.ball.rumble 198 199 200 241
    venv/bin/python3 -m src.ball.rumble --blind               # blind, in a pocket
    venv/bin/python3 -m src.ball.rumble --blind 198+199+200 241

Task 05's instrument, and it is deliberately two instruments, because the task
asks two questions that no single one can answer.

**`--trace` is the objective leg.** Ball still on the desk. It plays an id,
records `IN_E6`, and scores the sample-to-sample change in the IMU vector. That
is the rumble sweep's method (PROTOCOL.md §6.7) with the three things the sweep
lacked:

  * **the samples are kept.** The sweep stored one mean per id, so a peak
    statistic could not be recovered without sweeping again.
    A mean over 1.5 s dilutes a ~100 ms tick about fifteenfold, which is the
    stated reason eleven ids the ear called rumble read under 2x. Every trace
    is written out, so a metric nobody has thought of yet costs no hardware.
  * **the id order is shuffled every round.** That run's floor fell 84% across
    it. A drift measured in id order is a drift assigned to ids.
  * **each id is measured several times.** "Is 199 the same as 200?" is a
    question about two distributions. One reading each cannot answer it, and
    6.22 against 5.67 from single readings never could.

**`--blind` is the perceptual leg,** and it exists because the IMU cannot answer
the question the task actually asks. "Can it be felt through a pocket" is about
a person, and a person who knows which id is playing is not an instrument
(constitution principle 4). So the order is shuffled, the id is never printed
until the end, the buzz comes at a random delay after the keypress rather than
on it, and some trials **send nothing at all** — a "felt it" on one of those is
the run telling you to throw the run away.

It asks *felt* and *heard* separately, on purpose. These ids carry sound as well
as rumble (198/199/200 are light+rumble+sound, PROTOCOL.md §6.4), and
through a pocket an ear answers faster than a leg. Merged into one yes, that
confound would read as a rumble that carries.

Neither leg is the answer on its own. Both go in `learnings.md`, with the
disagreement intact if there is one.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import os
import random
import statistics
import sys
import time
from datetime import datetime
from typing import NamedTuple

from . import protocol
from .link import BallNotFound, open_ball

log = logging.getLogger("wobble.rumble")

# The four ids task 05 is about. 198/199/200 are the catch waves the sniffer
# capture plays — in the order 200, 199, 198, which is NOT the order plan.md
# has them in — and 241 is the loudest thing nearby in the old sweep (26.9x),
# carried as the reference leg: a run where 241 does not stand out is a run that
# measured something other than the motor.
DEFAULT_TRACE = ("198", "199", "200", "241")
DEFAULT_BLIND = ("198+199+200", "200+199+198", "241")
REFERENCE_ID = 241

# Below this many deltas a peak is one sample's worth of luck.
MIN_DELTAS = 8


# --- recording --------------------------------------------------------------

class Window(NamedTuple):
    """What arrived on `IN_E6` while one trial was being measured."""
    samples: list           # (t, x, y, z)
    seconds: float
    missed: int             # packets the counter says never arrived
    malformed: int          # notifications that were not the 17-byte shape
    odd_steps: int          # counter jumps that are not a multiple of 3


class Recorder:
    """Decodes every input packet; keeps the samples only while armed.

    It counts the losses whether armed or not, because a link dropping packets
    between trials is the same link that will drop them during one — and a
    window scored over half its samples is a quiet reading that means nothing.
    """

    def __init__(self):
        self.armed = False
        self.samples: list = []
        self.packets = 0
        self.missed = 0
        self.malformed = 0
        self.odd_steps = 0
        # Learned from the stream, not taken from the protocol notes. The first
        # link this ran against advanced the counter by 6 while the documented
        # figure was 3, and assuming the documented one turned a 1.9% loss rate
        # into a reported 100%.
        self.step: int | None = None
        self._learning: list[int] = []
        self._last_counter: int | None = None
        self._t0 = 0.0

    def __call__(self, t: float, raw: bytes) -> None:
        self.packets += 1
        packet = protocol.decode_input(raw)
        if packet is None:
            self.malformed += 1
            return
        if self.step is None:
            self._learning.append(packet.counter)
            self.step = protocol.infer_step(self._learning)
        elif self._last_counter is not None:
            missed = protocol.missed_packets(self._last_counter, packet.counter, self.step)
            if missed is None:
                self.odd_steps += 1
            else:
                self.missed += missed
        self._last_counter = packet.counter
        if self.armed:
            self.samples.append((t, *packet.accel))

    def arm(self) -> None:
        self.samples = []
        self.missed = self.malformed = self.odd_steps = 0
        self._t0 = time.perf_counter()
        self.armed = True

    def disarm(self) -> Window:
        self.armed = False
        return Window(samples=list(self.samples),
                      seconds=time.perf_counter() - self._t0,
                      missed=self.missed, malformed=self.malformed,
                      odd_steps=self.odd_steps)


def deltas(samples: list) -> list[float]:
    """Sample-to-sample magnitude of the IMU vector's change.

    The delta rather than the variance, for the reason the old probe gives: a
    slow tilt inflates variance while barely touching the delta, so a ball
    nudged once would otherwise read as a rumble. In a pocket that is not a
    hypothetical.
    """
    return [math.dist(a[1:], b[1:]) for a, b in zip(samples, samples[1:])]


def percentile(values: list[float], q: float) -> float:
    """Linear-interpolated percentile of an already-sorted list."""
    if not values:
        return 0.0
    k = (len(values) - 1) * q
    low, high = math.floor(k), math.ceil(k)
    if low == high:
        return values[int(k)]
    return values[low] * (high - k) + values[high] * (k - low)


def score(window: Window, threshold: float | None = None) -> dict | None:
    """Peak, mean and how long it was moving. `None` if too few samples.

    `mean` is kept because it is what the sweep recorded, and a number
    that cannot be compared to the reading it disputes settles nothing. `peak`
    is the one that was missing.
    """
    d = deltas(window.samples)
    if len(d) < MIN_DELTAS:
        return None
    ordered = sorted(d)
    t0 = window.samples[0][0]
    out = {
        # The whole trace, not a count. This is the one thing the old probe did
        # not do, and its own notes are what asks for it: "the probe stores only
        # the aggregate per id, not the samples, so a peak statistic cannot be
        # recovered without sweeping again". Milliseconds from the window's
        # start, then the three axes. A run is a few hundred rows.
        "trace": [[round((t - t0) * 1000), x, y, z] for t, x, y, z in window.samples],
        "samples": len(window.samples),
        "seconds": round(window.seconds, 3),
        "hz": round(len(window.samples) / window.seconds, 1) if window.seconds else None,
        "mean": round(statistics.fmean(d), 2),
        "median": round(statistics.median(d), 2),
        "p95": round(percentile(ordered, 0.95), 2),
        "peak": round(max(d), 2),
        "missed": window.missed,
        "malformed": window.malformed,
        "odd_steps": window.odd_steps,
    }
    if threshold is not None:
        above = sum(1 for x in d if x > threshold)
        out["active_pct"] = round(100.0 * above / len(d), 1)
        out["active_ms"] = round(1000.0 * window.seconds * above / len(d))
    return out


# --- driving the ball -------------------------------------------------------

async def measure(recorder: Recorder, seconds: float) -> Window:
    recorder.arm()
    await asyncio.sleep(seconds)
    return recorder.disarm()


async def play(link, ids: tuple[int, ...], beat: float) -> int:
    """Play one trial's ids in order. Returns how many went unacked."""
    lost = 0
    for n, effect_id in enumerate(ids):
        if n:
            await asyncio.sleep(beat)
        if await link.send(protocol.effect(effect_id), f"effect {effect_id}") is None:
            lost += 1
    return lost


async def trial(link, recorder: Recorder, ids: tuple[int, ...],
                window: float, beat: float, threshold: float | None) -> tuple[dict | None, int]:
    """Arm, play, hold the window open, and score what the IMU saw.

    The window starts before the first write and runs `window` seconds past the
    last one, so a group of ids is measured over the whole group rather than
    over its tail. That makes a group's `mean` lower than a single id's by
    construction — `peak` and `active_ms` are the ones that compare.
    """
    recorder.arm()
    lost = await play(link, ids, beat)
    await asyncio.sleep(window)
    return score(recorder.disarm(), threshold), lost


# --- the objective leg ------------------------------------------------------

def spread(values: list[float]) -> tuple[float, float]:
    return (min(values), max(values)) if values else (0.0, 0.0)


def summarise_trace(results: dict, floors: list[dict]) -> list[str]:
    """The table, plus the two verdicts the task asks for."""
    lines = []
    floor_peaks = [f["peak"] for f in floors]
    floor_means = [f["mean"] for f in floors]
    fp_lo, fp_hi = spread(floor_peaks)
    fm = statistics.median(floor_means) if floor_means else 0.0

    lines.append(f"floor across the run: mean {min(floor_means):.1f}..{max(floor_means):.1f}, "
                 f"peak {fp_lo:.1f}..{fp_hi:.1f}  ({len(floors)} measurements)")
    if floor_means and min(floor_means) and max(floor_means) / min(floor_means) > 2:
        lines.append("  ! the floor moved by more than 2x during the run — the ball was not "
                     "left alone, and every ratio below is against a moving target")
    lines.append("")
    lines.append(f"{'id':>14}  {'n':>2}  {'peak (x floor)':>16}  {'mean':>13}  "
                 f"{'active':>8}  verdict")

    for label, runs in results.items():
        peaks = [r["peak"] for r in runs]
        means = [r["mean"] for r in runs]
        actives = [r.get("active_ms", 0) for r in runs]
        p_lo, p_hi = spread(peaks)
        p_med = statistics.median(peaks)
        # Keyed on the spread BETWEEN measurements, never on a single ratio:
        # neighbours in time share conditions, a floor from four minutes ago
        # does not. An id whose weakest reading still beats the floor's
        # strongest is moving the ball; anything overlapping the floor is, to
        # this instrument, not distinguishable from a ball sitting still.
        if p_lo > fp_hi:
            verdict = "MOVES the ball"
        elif p_hi < fp_lo:
            verdict = "quieter than the floor — suspect the run"
        else:
            verdict = "overlaps the floor — not distinguishable"
        lines.append(
            f"{label:>14}  {len(runs):>2}  "
            f"{p_med:>7.1f} ({p_med / fp_hi if fp_hi else 0:.1f}x) {p_lo:.0f}-{p_hi:.0f}  "
            f"{statistics.median(means):>6.1f} ({statistics.median(means) / fm if fm else 0:.1f}x)  "
            f"{statistics.median(actives):>6.0f}ms  {verdict}")

    lines.append("")
    labels = list(results)
    for i, a in enumerate(labels):
        for b in labels[i + 1:]:
            a_lo, a_hi = spread([r["peak"] for r in results[a]])
            b_lo, b_hi = spread([r["peak"] for r in results[b]])
            same = not (a_hi < b_lo or b_hi < a_lo)
            lines.append(f"  {a} vs {b}: peak ranges {a_lo:.0f}-{a_hi:.0f} and "
                         f"{b_lo:.0f}-{b_hi:.0f} — "
                         f"{'OVERLAP, so this instrument cannot tell them apart' if same else 'separate'}")
    lines.append("")
    lines.append("`active` is time spent above the floor's OWN 95th percentile, so a still")
    lines.append("ball scores about 5% of the window — roughly "
                 f"{round(50 * statistics.median([f['seconds'] for f in floors]))}ms here — by")
    lines.append("construction. Read it against that, not against zero.")
    lines.append("")
    lines.append("A quiet reading means the MOTOR did not run. It never means the id did")
    lines.append("nothing: the ball has no light sensor and no microphone, and the old")
    lines.append("project confirmed at the desk that floor-reading ids were audibly")
    lines.append("playing sounds and visibly lighting the LED.")
    return lines


async def run_trace(args, out_path: str) -> int:
    recorder = Recorder()
    results: dict[str, list[dict]] = {label: [] for label in args.labels}
    floors: list[dict] = []
    raw: list[dict] = []
    lost = 0

    print("\nPut the ball ON THE DESK and leave it alone for the whole run.")
    print("Every reading below is about the motor, and a hand is louder than the motor.\n")

    async with open_ball(args.addr, scan_timeout=args.scan) as link:
        link.input_sink = recorder

        # The opening ends by playing effect 2, and the ball has just been woken
        # by hand. The first rumble sweep's floor fell 84% across its run for
        # exactly that reason (PROTOCOL.md §6.7).
        print(f"settling {args.settle:.0f}s — the opening ends by playing effect 2\n")
        await asyncio.sleep(args.settle)

        probe = score(await measure(recorder, args.window))
        if probe is None:
            print("no usable input packets — the ball is not streaming IN_E6, so there "
                  "is nothing to measure with.", file=sys.stderr)
            return 3
        print(f"input stream: {probe['hz']} Hz, {probe['samples']} samples in "
              f"{probe['seconds']:.1f}s, {probe['missed']} missed, "
              f"counter step {recorder.step}")
        if probe["hz"] and probe["hz"] * args.window < 20:
            print(f"  ! {probe['hz']:.0f} Hz over a {args.window:.1f}s window is under 20 "
                  f"samples — raise --window, or a peak is one sample's luck")

        for round_no in range(1, args.rounds + 1):
            floor = score(await measure(recorder, args.window))
            if floor is None:
                print("  ! the input stream dried up mid-run", file=sys.stderr)
                break
            floors.append(floor)
            print(f"\nround {round_no}/{args.rounds}  floor: mean {floor['mean']:.1f}, "
                  f"peak {floor['peak']:.1f}")

            order = list(args.specs)
            random.shuffle(order)          # a drifting floor must not land on one id
            for label, ids in order:
                got, unacked = await trial(link, recorder, ids, args.window,
                                           args.beat, floor["p95"])
                lost += unacked
                if got is None:
                    print(f"  {label:>14}: too few samples to score")
                    continue
                results[label].append(got)
                raw.append({"round": round_no, "label": label, "ids": list(ids),
                            "floor_mean": floor["mean"], "floor_p95": floor["p95"],
                            "floor_peak": floor["peak"], "unacked": unacked, **got})
                print(f"  {label:>14}: peak {got['peak']:>7.1f}  mean {got['mean']:>6.1f}  "
                      f"active {got.get('active_ms', 0):>4}ms"
                      + ("  UNACKED WRITE" if unacked else ""))
                _write(out_path, {"mode": "trace", "trials": raw, "floors": floors})
                await asyncio.sleep(args.rest)

        floor = score(await measure(recorder, args.window))
        if floor is not None:
            floors.append(floor)
        print(f"\nlink: {link.stats()}")

    results = {k: v for k, v in results.items() if v}
    if not results or not floors:
        print("nothing measured", file=sys.stderr)
        return 3
    print()
    for line in summarise_trace(results, floors):
        print(line)
    _write(out_path, {"mode": "trace", "trials": raw, "floors": floors})
    print(f"\ntraces -> {out_path}")
    return 1 if lost else 0


# --- the perceptual leg -----------------------------------------------------

async def ask(prompt: str) -> str:
    """Read an answer without blocking the event loop, so the link stays alive."""
    try:
        return (await asyncio.to_thread(input, prompt)).strip().lower()
    except (EOFError, KeyboardInterrupt):
        return "q"


async def ask_felt() -> int | None:
    while True:
        answer = await ask("      felt it?  0 nothing · 1 faint · 2 clear · 3 strong  > ")
        if answer == "q":
            return None
        if answer in {"0", "1", "2", "3"}:
            return int(answer)
        print("      0, 1, 2, 3 — or q to stop")


async def ask_heard() -> bool | None:
    while True:
        answer = await ask("      heard it? y/n  > ")
        if answer == "q":
            return None
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("      y or n — or q to stop")


def summarise_blind(answers: list[dict]) -> list[str]:
    """The reveal, controls first, because the controls decide if the rest counts."""
    lines = []
    nulls = [a for a in answers if a["label"] == "(nothing sent)"]
    real = [a for a in answers if a["label"] != "(nothing sent)"]

    lines.append("CONTROLS")
    if not nulls:
        lines.append("  no null trials were run — nothing checked whether a 'felt it' needs")
        lines.append("  an effect. Re-run with --nulls for this leg to mean anything.")
    else:
        false_positives = [a for a in nulls if a["felt"] > 0]
        lines.append(f"  {len(nulls)} trial(s) sent NOTHING. "
                     f"felt: {[a['felt'] for a in nulls]}  heard: {[a['heard'] for a in nulls]}")
        if false_positives:
            lines.append(f"  ! {len(false_positives)} of them were reported as felt. This run's")
            lines.append("    perceptual answers cannot be separated from expectation. Throw")
            lines.append("    the run away rather than reading the table below.")
        else:
            lines.append("  clean — nothing was felt when nothing was sent.")

    by_label: dict[str, list[dict]] = {}
    for a in real:
        by_label.setdefault(a["label"], []).append(a)

    reference = next((lbl for lbl in by_label if lbl == str(REFERENCE_ID)), None)
    if reference:
        felt = [a["felt"] for a in by_label[reference]]
        median = statistics.median(felt)
        lines.append(f"  reference {reference} (26.9x the floor in the old sweep): "
                     f"felt {felt}, median {median}")
        if median < 2:
            lines.append("  ! the loudest id available did not read as clearly felt. The ball")
            lines.append("    is probably sitting badly in the pocket — fix that before")
            lines.append("    concluding anything about the quieter ids.")

    lines.append("")
    lines.append(f"{'trial':>14}  {'n':>2}  {'felt':>12}  {'med':>3}  {'heard':>5}  "
                 f"{'imu peak':>9}")
    for label, group in by_label.items():
        felt = [a["felt"] for a in group]
        heard = sum(1 for a in group if a["heard"])
        peaks = [a["peak"] for a in group if a["peak"] is not None]
        lines.append(f"{label:>14}  {len(group):>2}  {str(felt):>12}  "
                     f"{statistics.median(felt):>3.0f}  {heard:>2}/{len(group):<2}  "
                     f"{statistics.median(peaks) if peaks else 0:>9.1f}")

    lines.append("")
    lines.append("`heard` is not a failure — it is a separate channel that also reaches a")
    lines.append("pocket. It is asked apart from `felt` so that an id which only sounds")
    lines.append("cannot be written down as an id that carries a rumble.")
    return lines


async def run_blind(args, out_path: str) -> int:
    recorder = Recorder()
    order = [spec for spec in args.specs for _ in range(args.rounds)]
    order += [("(nothing sent)", ())] * args.nulls
    random.shuffle(order)

    answers: list[dict] = []
    print(f"\n{len(order)} trials, {args.nulls} of which send nothing at all.")
    print("You will not be told which is which until the end. Answer what you felt,")
    print("not what you expected — a run that agrees with a guess proves the guess.\n")

    async with open_ball(args.addr, scan_timeout=args.scan) as link:
        link.input_sink = recorder
        if await ask("Put the ball IN YOUR POCKET now, then press enter > ") == "q":
            return 0
        await asyncio.sleep(args.settle)

        floor = score(await measure(recorder, args.window))
        if floor is None:
            print("no usable input packets — the ball is not streaming IN_E6.", file=sys.stderr)
            return 3
        print(f"\npocket floor: mean {floor['mean']:.1f}, peak {floor['peak']:.1f}, "
              f"{floor['hz']} Hz, counter step {recorder.step} — a body is not a "
              f"desk, and this is how much of one\n")

        for n, (label, ids) in enumerate(order, 1):
            if await ask(f"  trial {n}/{len(order)} — press enter when you are ready > ") == "q":
                break
            # The buzz must not land on the keypress, or its timing is the answer.
            await asyncio.sleep(random.uniform(0.4, 1.8))
            got, unacked = await trial(link, recorder, ids, args.window, args.beat,
                                       floor["p95"])
            felt = await ask_felt()
            if felt is None:
                break
            heard = await ask_heard()
            if heard is None:
                break
            answers.append({"label": label, "ids": list(ids), "felt": felt,
                            "heard": heard, "unacked": unacked,
                            "peak": got["peak"] if got else None,
                            "imu": got})
            _write(out_path, {"mode": "blind", "floor": floor, "answers": answers})
            if unacked:
                print(f"      ! {unacked} write(s) went unacked — the ball may not have "
                      f"heard this one, so this trial is about the link, not your leg")

        print(f"\nlink: {link.stats()}")

    if not answers:
        print("nothing answered", file=sys.stderr)
        return 3
    print()
    for line in summarise_blind(answers):
        print(line)
    _write(out_path, {"mode": "blind", "floor": floor, "answers": answers})
    print(f"\nanswers -> {out_path}")
    return 0


# --- plumbing ---------------------------------------------------------------

def _write(path: str, payload: dict) -> None:
    """Write after every trial, not at the end.

    The first rumble sweep died at id 181 of 255 and kept the 180 only because
    they were written as they came. A desk check that loses its run to a
    dropped link has cost the hardware twice.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")


def parse_spec(text: str) -> tuple[str, tuple[int, ...]]:
    """`"241"` or `"198+199+200"` — one trial, one or several ids in order."""
    ids = []
    for part in text.split("+"):
        part = part.strip()
        if not part.isdigit():
            raise ValueError(f"{text!r}: {part!r} is not an effect id")
        value = int(part)
        if not 0 <= value <= 0xFFFF:
            raise ValueError(f"effect id {value} is outside the u16 space the ball accepts")
        ids.append(value)
    return "+".join(str(i) for i in ids), tuple(ids)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m src.ball.rumble", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("specs", nargs="*", metavar="SPEC",
                    help="effect ids to measure. `198` is one id; `198+199+200` is "
                         "one trial that plays three in order, which is what a "
                         "`needs` signal actually is")
    ap.add_argument("--blind", action="store_true",
                    help="the perceptual leg: ball in a pocket, order shuffled, ids "
                         "hidden until the end, some trials sending nothing")
    ap.add_argument("--rounds", type=int, default=3, metavar="N",
                    help="measurements per id. Two readings cannot be compared "
                         "without a spread (default: 3)")
    ap.add_argument("--nulls", type=int, default=3, metavar="N",
                    help="--blind only: trials that send nothing. The control that "
                         "decides whether the run counts (default: 3)")
    ap.add_argument("--window", type=float, default=1.5, metavar="S",
                    help="seconds of IMU recorded per trial, after the last write. "
                         "1.5 is the old sweep's window, kept so the `mean` column "
                         "is directly comparable with the numbers this run disputes "
                         "(default: 1.5)")
    ap.add_argument("--beat", type=float, default=0.35, metavar="S",
                    help="gap between the ids of one grouped trial. A GUESS, not the "
                         "capture's timing — the sniffer file's per-packet timestamps "
                         "would settle it and have not been read (default: 0.35)")
    ap.add_argument("--rest", type=float, default=0.8, metavar="S",
                    help="--trace only: quiet time between trials (default: 0.8)")
    ap.add_argument("--settle", type=float, default=5.0, metavar="S",
                    help="quiet time before the first measurement. The opening ends "
                         "by playing effect 2 and the ball was just woken by hand "
                         "(default: 5.0)")
    ap.add_argument("--scan", type=float, default=45.0, metavar="S",
                    help="how long to scan. Long because the ball sleeps fast and "
                         "you have to press its top button (default: 45)")
    ap.add_argument("--addr", default=None, help="BLE address, skipping the scan")
    ap.add_argument("--out", default=None, metavar="PATH",
                    help="where to write the run (default: var/desk/rumble-<mode>-<stamp>.json)")
    ap.add_argument("--seed", type=int, default=None,
                    help="seed the shuffle, to replay an order exactly")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    chosen = args.specs or (DEFAULT_BLIND if args.blind else DEFAULT_TRACE)
    try:
        args.specs = [parse_spec(text) for text in chosen]
    except ValueError as exc:
        ap.error(str(exc))
    args.labels = [label for label, _ in args.specs]
    if args.rounds < 1:
        ap.error("--rounds must be at least 1")
    if args.nulls < 0:
        ap.error("--nulls cannot be negative")
    if args.seed is not None:
        random.seed(args.seed)

    mode = "blind" if args.blind else "trace"
    out_path = args.out or os.path.join(
        "var", "desk", f"rumble-{mode}-{datetime.now():%Y-%m-%dT%H-%M-%S}.json")

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)-7s %(message)s")
    try:
        return asyncio.run((run_blind if args.blind else run_trace)(args, out_path))
    except BallNotFound as exc:
        print(exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
