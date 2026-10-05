#!/usr/bin/env python3
"""The menu ball's light, in its layers (task 60) — offscreen, nothing on screen.

    venv/bin/python3 tests/tables/check_menu_light.py

`Status.icon` is handed a real `NSButton` that is never put in a window, in a
status item of the check's own, so no menu bar item appears. The rows read the
button's image and the two layers over it:

  - the image is the shell alone; every light is a layer
  - a held light is the centre's colour, breathing in the shape it is handed
  - a flash plays for its length, once; a new beat restarts it, the same
    one does not, and a flash leaves the breath where it was
  - no flash cuts the one playing — B's refresh
  - the light sits inside the ring, in the middle of the image
  - a layer that cannot be made falls back to the light drawn still, drawn
    and said
  - muted, the image is wider by a mark in the menu bar's ink, the light
    stays on the ball, and a macOS with no mark answers "not drawn" (task 61)
  - connected, the top half is red from the band up to the battery left, and
    the bottom half is filled, white on a dark bar and black at 18% on a light
    one; looking for a ball, both are clear; off, the whole ball is at 35% and
    the mark beside it is not; each reading and each fade is its own image
    (task 63). Read as pixels at 2x, in a light and a dark appearance.

Its mutants are lines of `src/platform_seam/macos.py` replaced one at a time,
each of which must turn a row wrong. The reference leg is the unpatched seam.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from AppKit import (NSAppearance, NSBitmapImageRep, NSButton,          # noqa: E402
                    NSGraphicsContext)
from Foundation import NSMakeRect                                      # noqa: E402
from Quartz import CGPathGetBoundingBox                                # noqa: E402

from src.platform_seam.ports import BallIcon                           # noqa: E402

MACOS = ROOT / "src" / "platform_seam" / "macos.py"
BREATH = (1.04, 0.78, 0.47)          # menubar.STROLL_BREATH, written out: not read from it
DONE = BallIcon(True, "#FFE14D", None, BREATH)
LOADS = 0


class Sheet:
    def __init__(self, quiet: bool) -> None:
        self.quiet, self.bad = quiet, 0

    def row(self, what: str, got, want) -> None:
        ok = got == want
        self.bad += not ok
        if not self.quiet:
            print(f"    {'ok ' if ok else 'BAD'} {what:<62} {got!r}"
                  + ("" if ok else f"   want {want!r}"))


def load(patch: tuple[str, str] | None = None):
    text = MACOS.read_text()
    if patch is not None:
        if text.count(patch[0]) != 1:
            return None
        text = text.replace(*patch)
    # An Objective-C class registers once per process: each load names its own.
    global LOADS
    LOADS += 1
    for name in re.findall(r"^class (\w+)\(NSObject\):", text, re.M):
        text = text.replace(f"class {name}(NSObject):", f"class {name}{LOADS}(NSObject):")
        text += f"\n{name} = {name}{LOADS}\n"
    spec = importlib.util.spec_from_file_location("src.platform_seam.macos_under_check", MACOS)
    module = importlib.util.module_from_spec(spec)
    module.__package__ = "src.platform_seam"
    sys.modules[spec.name] = module
    exec(compile(text, str(MACOS), "exec"), module.__dict__)
    return module


class Item:
    def __init__(self) -> None:
        self._button = NSButton.alloc().initWithFrame_(NSMakeRect(0, 0, 60, 22))

    def button(self):
        return self._button


def status(mod):
    s = mod.Status()
    s._item = Item()                  # `_ensure` sees an item and makes no real one
    return s


def colour(layer) -> str | None:
    fill = layer.fillColor()
    if fill is None:
        return None
    from Quartz import CGColorGetComponents, CGColorGetNumberOfComponents
    n = CGColorGetNumberOfComponents(fill)
    rgb = [round(c * 255) for c in CGColorGetComponents(fill)[:n][:3]]
    return "#" + "".join(f"{c:02X}" for c in rgb)


def mark_ink(image, dark: bool) -> tuple[int, float | None]:
    """(pixels inked right of the ball, their mean brightness), at 2x, in a light or dark bar."""
    w, h = int(image.size().width * 2), int(image.size().height * 2)
    rep = NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, w, h, 8, 4, True, False, "NSDeviceRGBColorSpace", 0, 0)
    NSGraphicsContext.saveGraphicsState()
    try:
        NSGraphicsContext.setCurrentContext_(NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep))
        name = "NSAppearanceNameDarkAqua" if dark else "NSAppearanceNameAqua"
        NSAppearance.appearanceNamed_(name).performAsCurrentDrawingAppearance_(
            lambda: image.drawInRect_(NSMakeRect(0, 0, w, h)))
    finally:
        NSGraphicsContext.restoreGraphicsState()
    inked = [rep.colorAtX_y_(x, y) for x in range(38, w) for y in range(h)]
    inked = [c for c in inked if c.alphaComponent() > 0.9]
    return len(inked), (round(sum(c.redComponent() for c in inked) / len(inked), 1)
                        if inked else None)


def bitmap(image, dark: bool):
    """The image drawn at 2x into a bitmap of its own, in a light or dark bar."""
    w, h = int(image.size().width * 2), int(image.size().height * 2)
    rep = NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, w, h, 8, 4, True, False, "NSDeviceRGBColorSpace", 0, 0)
    NSGraphicsContext.saveGraphicsState()
    try:
        NSGraphicsContext.setCurrentContext_(NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep))
        name = "NSAppearanceNameDarkAqua" if dark else "NSAppearanceNameAqua"
        NSAppearance.appearanceNamed_(name).performAsCurrentDrawingAppearance_(
            lambda: image.drawInRect_(NSMakeRect(0, 0, w, h)))
    finally:
        NSGraphicsContext.restoreGraphicsState()
    return rep


def pixel(rep, x: float, y: float) -> tuple[float, float, float, float]:
    """(r, g, b, a) at a point of the 18 pt ball, y up — the bitmap's rows run down."""
    c = rep.colorAtX_y_(int(x * 2), int((18 - y) * 2))
    return tuple(round(v, 2) for v in (c.redComponent(), c.greenComponent(),
                                       c.blueComponent(), c.alphaComponent()))


# Points of the 18 pt ball (centre 9, radius 7.56, line 1.35, hole 3.87): high in
# the top half, just above the band, low in the bottom half, on the rim, and
# outside the ball beside each half.
TOP, MID, LOW, RIM = (9, 15.5), (5, 11), (5, 6.5), (9, 16.56)
BESIDE_TOP, BESIDE_LOW = (0.25, 12), (0.25, 5)


def red(c) -> bool:
    return c[3] > 0.9 and c[0] > 0.8 and c[1] < 0.35


def clear(c) -> bool:
    return c[3] < 0.05


def rows(mod, quiet: bool = False) -> bool:
    sheet = Sheet(quiet)
    say = (lambda _: None) if quiet else print
    try:
        s = status(mod)
        button = s._item.button()

        say("\n  the reference leg: a hollow ball with nothing lit")
        sheet.row("drawn, and nothing to say", s.icon(BallIcon(False)), (True, None))
        sheet.row("the image is the hollow shell", list(s._balls), [BallIcon(False)])
        held, flash = s._lights
        sheet.row("both lights are dark", (held.opacity(), flash.opacity()), (0.0, 0.0))

        say("\n  a done: the held light, breathing")
        sheet.row("drawn, and nothing to say", s.icon(DONE), (True, None))
        sheet.row("the image is still only the shell, now filled on top",
                  sorted(s._balls, key=repr), sorted([BallIcon(False), BallIcon(True)], key=repr))
        sheet.row("the held light is the centre's colour", colour(held), "#FFE14D")
        sheet.row("…at full, between breaths", held.opacity(), 1.0)
        breath = held.animationForKey_("breath")
        sheet.row("…and it breathes", breath is not None, True)
        sheet.row("…in 9's shape: 1.04 s held, 0.78 s down, 0.47 s up",
                  ([round(v, 2) for v in breath.values()],
                   [round(k, 3) for k in breath.keyTimes()], round(breath.duration(), 2)),
                  ([1.0, 1.0, 0.0, 1.0], [0.0, 0.454, 0.795, 1.0], 2.29))
        sheet.row("…for ever", breath.repeatCount(), float("inf"))
        sheet.row("no flash yet", flash.animationForKey_("flash"), None)

        say("\n  a beat over it")
        beat = DONE._replace(pulse="#FFB000", pulse_s=0.5, beat=1)
        s.icon(beat)
        first = flash.animationForKey_("flash")
        sheet.row("the flash is the beat's colour", colour(flash), "#FFB000")
        sheet.row("…plays at full then fades, over the beat's 0.5 s",
                  ([round(v, 2) for v in first.values()], round(first.duration(), 2)),
                  ([1.0, 1.0, 0.0], 0.5))
        sheet.row("…once", first.repeatCount(), 0.0)
        sheet.row("…and dark once it has played", flash.opacity(), 0.0)
        sheet.row("the breath goes on untouched", held.animationForKey_("breath") is breath, True)
        s.icon(beat)
        sheet.row("the same beat again does not restart it",
                  flash.animationForKey_("flash") is first, True)
        s.icon(beat._replace(beat=2))
        sheet.row("the next beat alike does", flash.animationForKey_("flash") is first, False)

        say("\n  a catch, and B")
        s.icon(BallIcon(True, None, "#3CC85A", None, 2.0, 3))
        sheet.row("a catch flashes green for its 2.0 s",
                  (colour(flash), round(flash.animationForKey_("flash").duration(), 2)),
                  ("#3CC85A", 2.0))
        sheet.row("…with no held light under it",
                  (held.opacity(), held.animationForKey_("breath")), (0.0, None))
        s.icon(BallIcon(True, None, None, None, 0.0, 4))
        sheet.row("no flash cuts the one playing", flash.animationForKey_("flash"), None)

        say("\n  where the light sits")
        box = CGPathGetBoundingBox(held.path())
        image = button.cell().imageRectForBounds_(button.bounds())
        sheet.row("inside the ring: 3.69 pt across", round(box.size.width, 2), 3.69)
        sheet.row("…in the middle of the image",
                  (round(box.origin.x + box.size.width / 2, 2),
                   round(box.origin.y + box.size.height / 2, 2)),
                  (round(image.origin.x + image.size.width / 2, 2),
                   round(image.origin.y + image.size.height / 2, 2)))
        sheet.row("…both lights in the same place", flash.path() == held.path(), True)
        sheet.row("…at the Retina scale when no window says otherwise",
                  held.contentsScale(), 2.0)

        say("\n  a layer that cannot be made")
        broken = status(mod)
        real = mod.CAShapeLayer
        try:
            mod.CAShapeLayer = None
            got = broken.icon(DONE._replace(pulse="#FFB000", pulse_s=0.5, beat=1))
        finally:
            mod.CAShapeLayer = real
        sheet.row("still drawn, and why is said",
                  (got[0], (got[1] or "").startswith("could not light the ball's centre")),
                  (True, True))
        sheet.row("…the light drawn into the image, still",
                  broken._item.button().image() is broken._balls.get(
                      BallIcon(True, "#FFE14D", "#FFB000")), True)

        say("\n  muted: the mark beside the ball (task 61)")
        m = status(mod)
        sheet.row("drawn, and nothing to say", m.icon(DONE._replace(muted=True)), (True, None))
        muted = m._item.button()
        image = muted.image()
        sheet.row("the image is wider by the mark: 18 + 2 + 12 pt, 18 high",
                  (image.size().width, image.size().height), (32.0, 18.0))
        light, dark = mark_ink(image, False), mark_ink(image, True)
        sheet.row("…the mark is inked right of the ball", (light[0] > 40, dark[0] > 40), (True, True))
        sheet.row("…in the menu bar's ink: dark on a light bar, light on a dark one",
                  (light[1] < 0.3, dark[1] > 0.7), (True, True))
        box = CGPathGetBoundingBox(m._lights[0].path())
        rect = muted.cell().imageRectForBounds_(muted.bounds())
        sheet.row("…and the light stays on the ball's middle, not the image's",
                  round(box.origin.x + box.size.width / 2, 2), round(rect.origin.x + 9, 2))
        m.icon(DONE)
        sheet.row("unmuted, the image is the ball alone again",
                  (m._item.button().image().size().width, mark_ink(m._item.button().image(), False)[0]),
                  (18.0, 0))

        bare = status(mod)
        real = mod._mute_mark
        try:
            mod._mute_mark = lambda: None
            got = bare.icon(DONE._replace(muted=True))
        finally:
            mod._mute_mark = real
        sheet.row("no mark on this macOS: answered as not drawn, and why is said",
                  (got[0], (got[1] or "").startswith("could not draw the mute mark")), (False, True))
        sheet.row("…the ball still drawn, without room for a mark, its light still breathing",
                  (bare._item.button().image().size().width,
                   bare._lights[0].animationForKey_("breath") is not None), (18.0, True))

        say("\n  the battery, the bottom half, and off (task 63)")
        b = status(mod)

        def drawn(ball, dark: bool):
            b.icon(ball)
            return bitmap(b._item.button().image(), dark)
        full = [drawn(BallIcon(True), dark) for dark in (False, True)]
        sheet.row("no reading yet: the top half red to the top, in both bars",
                  [red(pixel(r, *TOP)) for r in full], [True, True])
        sheet.row("…and at 100% the same",
                  red(pixel(drawn(BallIcon(True, battery=100), False), *TOP)), True)
        half = drawn(BallIcon(True, battery=50), False)
        sheet.row("at 50%: red from the band up, gone from the top down",
                  (red(pixel(half, *MID)), clear(pixel(half, *TOP))), (True, True))
        sheet.row("…and none of it outside the ball", clear(pixel(half, *BESIDE_TOP)), True)
        empty = drawn(BallIcon(True, battery=0), True)
        sheet.row("at 0%: no red left, and the bottom still filled, so never hollow",
                  (clear(pixel(empty, *MID)), pixel(empty, *LOW)[3] > 0.9), (True, True))
        light, dark = pixel(full[0], *LOW), pixel(full[1], *LOW)
        sheet.row("the bottom half white on a dark bar",
                  dark[0] > 0.95 and dark[3] > 0.95, True)
        sheet.row("…and black at 18% on a light one, where white is lost",
                  light[0] < 0.05 and 0.15 < light[3] < 0.21, True)
        sheet.row("…and none of it outside the ball", clear(pixel(full[1], *BESIDE_LOW)), True)
        looking = drawn(BallIcon(False), False)
        sheet.row("looking for a ball: both halves clear, the rim in full ink",
                  (clear(pixel(looking, *TOP)), clear(pixel(looking, *LOW)),
                   pixel(looking, *RIM)[3] > 0.8), (True, True, True))
        off = drawn(BallIcon(False, off=True), False)
        sheet.row("off: the whole ball at 35% of its ink",
                  0.25 < pixel(off, *RIM)[3] < 0.33, True)
        b.icon(BallIcon(False, off=True, muted=True))
        # Both bars: NSImage draws the symbol at its own alpha whatever the
        # context's, so a fade left on shows only in the tint, light on dark.
        (count, light), (_, dark) = (mark_ink(b._item.button().image(), d) for d in (False, True))
        sheet.row("…and the mute mark beside it in full ink, not faded",
                  (count > 40, light is not None and light < 0.3, dark is not None and dark > 0.7),
                  (True, True, True))
        sheet.row("each reading and each fade its own image",
                  all(key in b._balls for key in (BallIcon(True, battery=50),
                                                  BallIcon(True, battery=0),
                                                  BallIcon(False, off=True))), True)
    except Exception as exc:              # a mutant that crashes is a wrong row
        sheet.row("the rows ran to the end", f"raised {exc!r}", "ran")
    return not sheet.bad


MUTANTS = [
    ("the light drawn into the image as well",
     ("self._image(button, BallIcon(ball.connected, muted=marked,\n"
      "                                         battery=ball.battery, off=ball.off))",
      "self._image(button, ball)")),
    ("the breath's hold and fall swapped",
     ("[0.0, hold / period, (hold + fall) / period, 1.0]",
      "[0.0, fall / period, (hold + fall) / period, 1.0]")),
    ("a breath that stops after one", ('breath.setRepeatCount_(float("inf"))',
                                       "breath.setRepeatCount_(1.0)")),
    ("a flash restarts the breath",
     ("if (ball.centre, ball.breath) != self._held:", "if True:")),
    ("a beat alike never restarted",
     ("if (ball.pulse, ball.beat) != self._flashed:",
      "if ball.pulse != (self._flashed or (None,))[0]:")),
    ("a flash that lingers", ("flash.removeAllAnimations()", "pass")),
    ("a flash of a fixed length", ("_flashing(ball.pulse_s)", "_flashing(0.5)")),
    ("a flash that stays lit", ("flash.setValues_([1.0, 1.0, 0.0])",
                                "flash.setValues_([1.0, 1.0, 1.0])")),
    ("the held colour never set",
     ("held.setFillColor_(_colour(ball.centre).CGColor())", "pass")),
    ("lit with nothing held",
     ("held.setOpacity_(0.0 if ball.centre is None else 1.0)", "held.setOpacity_(1.0)")),
    ("the light across the whole ball",
     ("r = _MENU_PT * 0.14 - line / 2", "r = _MENU_PT * 0.42")),
    ("no fallback",
     ("self._image(button, BallIcon(ball.connected, ball.centre, ball.pulse,\n"
      "                                             muted=marked, battery=ball.battery,\n"
      "                                             off=ball.off))", "pass")),
    ("the fallback said as a failure to draw", ("        return True, why", "        return False, why")),
    ("the mark never drawn", ("            mark.drawInRect_(box)\n", "")),
    ("the mark in black, not the ink",
     ("NSRectFillUsingOperation(box, NSCompositingOperationSourceAtop)", "pass")),
    ("no room for the mark",
     ("width = _MENU_PT if mark is None else _MENU_PT + _MARK_GAP + mark.size().width",
      "width = _MENU_PT")),
    ("the light on the image's middle",
     ("x = rect.origin.x + _MENU_PT / 2", "x = rect.origin.x + rect.size.width / 2")),
    ("the mute dropped from the image",
     ("self._image(button, BallIcon(ball.connected, muted=marked,\n",
      "self._image(button, BallIcon(ball.connected,\n")),
    ("a missing mark never checked",
     ("marked = ball.muted and _mute_mark() is not None", "marked = ball.muted")),
    ("a missing mark answered as drawn",
     ("            return False, unmarked if why", "            return True, unmarked if why")),
    # task 63
    ("the top never red", ("top=_colour(_MENU_RED), bottom=_menu_bottom())",
                           "bottom=_menu_bottom())")),
    ("the battery ignored",
     ("level = 1.0 if ball.battery is None else min(max(ball.battery, 0), 100) / 100",
      "level = 1.0")),
    ("the red drained from the band up",
     ("NSBezierPath.fillRect_(NSMakeRect(0, c, size, r * level))",
      "NSBezierPath.fillRect_(NSMakeRect(0, c + r * (1 - level), size, r * level))")),
    ("the red not kept to the top half", ("            _top_half(c, c, r).addClip()\n", "")),
    ("the bottom never filled", ("        if bottom is not None:\n", "        if False:\n")),
    ("the bottom not kept to the ball", ("            _disc(c, c, r).addClip()\n", "")),
    ("a white bottom on a light bar",
     ("    if name == NSAppearanceNameDarkAqua:\n", "    if True:\n")),
    ("a solid black bottom on a light bar",
     ("colorWithAlphaComponent_(_LIGHT_BOTTOM)", "colorWithAlphaComponent_(1.0)")),
    ("off never faded", ("_OFF_ALPHA if ball.off else 1.0", "1.0")),
    ("every ball faded", ("_OFF_ALPHA if ball.off else 1.0", "_OFF_ALPHA")),
    ("the fade left on for the mark",
     ("        CGContextEndTransparencyLayer(cg)\n        NSGraphicsContext.restoreGraphicsState()\n",
      "        CGContextEndTransparencyLayer(cg)\n")),
    ("the layer never closed, the mark inside it",
     ("        CGContextEndTransparencyLayer(cg)\n        NSGraphicsContext.restoreGraphicsState()\n"
      "        if mark is not None:\n",
      "        if mark is not None:\n")),
    ("the battery dropped from the image",
     ("battery=ball.battery, off=ball.off))", "off=ball.off))")),
    ("off dropped from the image",
     ("                                         battery=ball.battery, off=ball.off))",
      "                                         battery=ball.battery))")),
]


def main() -> int:
    print(__doc__.strip().splitlines()[0])
    ok = rows(load())
    print("\n  mutants — lines of macos.py, each must break a row")
    for label, patch in MUTANTS:
        mod = load(patch)
        got = "NOT APPLIED" if mod is None else ("caught" if not rows(mod, quiet=True)
                                                 else "SURVIVED")
        ok &= got == "caught"
        print(f"    {label:<52} {'caught' if got == 'caught' else '<-- ' + got}")
    print("\nALL CASES MATCH the known answer" if ok else "\nSOME CASES DO NOT MATCH")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
