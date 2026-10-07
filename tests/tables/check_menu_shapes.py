#!/usr/bin/env python3
"""The menu's two shapes, a submenu and a checkmark (spec 03, task 02) — offscreen.

    venv/bin/python3 tests/tables/check_menu_shapes.py

`Status.menu` is handed a list with a `Submenu` and `Checked` lines in it, and
builds a real `NSMenu` that is never shown: the status item is the check's own
(`check_menu_light.py`'s), so nothing appears in the menu bar. The rows read the
built menu and click it through `performActionForItemAtIndex_`, AppKit's own
dispatch, so the selector, the target and the tag are all under test:

  - the submenu hangs off its line, which has no action of its own
  - a checked line has the checkmark, a plain one has not
  - a click inside the submenu runs its own handler, and a click below the
    submenu still runs the right one: the tags count across the nested lists
  - an `Alternate` still swaps with the line above it

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

from AppKit import (NSApplication, NSApplicationActivationPolicyAccessory,  # noqa: E402
                    NSButton)
from Foundation import NSMakeRect                                      # noqa: E402

from src.platform_seam.ports import Alternate, Checked, Submenu        # noqa: E402

MACOS = ROOT / "src" / "platform_seam" / "macos.py"
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
    """`check_menu_light.py`'s loader: the seam's text, patched, under its own classes."""
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
    # AppKit's dispatch goes through the application, which `_ensure` would have
    # made: with none, `performActionForItemAtIndex_` runs nothing at all.
    NSApplication.sharedApplication().setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    s = mod.Status()
    s._item = Item()                  # `_ensure` sees an item and makes no real one
    # …so it makes no click target either: the one `_ensure` would have made.
    s._menu_clicks = mod._MenuClicks.alloc().init()
    return s


def titles(menu) -> list:
    return [None if menu.itemAtIndex_(i).isSeparatorItem() else str(menu.itemAtIndex_(i).title())
            for i in range(menu.numberOfItems())]


def rows(mod, quiet: bool = False) -> bool:
    sheet = Sheet(quiet)
    say = (lambda *_: None) if quiet else print
    chose: list = []
    s = status(mod)
    settings = [("Permissions", None),
                (Checked("Accessibility — B raises the window"), lambda: chose.append("ax")),
                ("⚠ Bluetooth off — the ball cannot connect", lambda: chose.append("bt")),
                (None, None),
                (Checked("Open wobble at login"), lambda: chose.append("login"))]
    offered = [("Go to wobble", lambda: chose.append("go")),
               (Alternate("Silence wobble"), lambda: chose.append("silence")),
               (None, None),
               (Submenu("Settings"), settings),
               (None, None),
               ("Quit wobble", lambda: chose.append("quit"))]
    s.menu(offered)
    menu = s._menu

    say("\n  the submenu")
    sheet.row("every top line reaches the menu, the submenu's not among them",
              titles(menu), ["Go to wobble", "Silence wobble", None, "Settings", None,
                             "Quit wobble"])
    line = menu.itemAtIndex_(3)
    sub = line.submenu()
    sheet.row("the Settings line opens a menu of its own", sub is not None, True)
    sheet.row("…with every line handed over, separator included",
              titles(sub) if sub is not None else None,
              ["Permissions", "Accessibility — B raises the window",
               "⚠ Bluetooth off — the ball cannot connect", None, "Open wobble at login"])
    # AppKit's own action, set by `setSubmenu_`: never `chose:`, so a click on
    # the line opens the submenu and runs nothing of ours.
    sheet.row("the Settings line opens on hover, AppKit's own action",
              str(line.action()), "submenuAction:")
    sheet.row("…aimed at the submenu, not at our clicks",
              line.target() is s._menu_clicks, False)
    sheet.row("…and stays usable, or the submenu would never open", line.isEnabled(), True)
    if sub is None:
        return False
    sheet.row("a line only to be read is greyed in the submenu too",
              sub.itemAtIndex_(0).isEnabled(), False)

    say("\n  the checkmark")
    sheet.row("a Checked line has the checkmark", sub.itemAtIndex_(1).state(), 1)
    sheet.row("a plain line has none", sub.itemAtIndex_(2).state(), 0)
    sheet.row("the last Checked line has it too", sub.itemAtIndex_(4).state(), 1)
    sheet.row("a top line has none", menu.itemAtIndex_(0).state(), 0)

    say("\n  clicks, counted across the nested lists")
    # Pins the convention, as `check_macos_seam.py` does for a flat list: a seam
    # that gives the Settings line no place is consistent and clicks right, and
    # only this row tells it from one that does.
    sheet.row("the quit line's tag is its place across every list, Settings counted",
              menu.itemAtIndex_(5).tag(), 10)
    for where, index, want in ((sub, 1, ["ax"]), (sub, 2, ["bt"]), (sub, 4, ["login"]),
                               (menu, 5, ["quit"]), (menu, 0, ["go"]), (menu, 1, ["silence"])):
        chose.clear()
        where.performActionForItemAtIndex_(index)
        name = "the submenu's" if where is sub else "the menu's"
        sheet.row(f"choosing {name} line {index} runs its own handler, and only it",
                  chose, want)

    say("\n  the alternate still swaps with the line above it")
    sheet.row("the Silence line is the alternate", menu.itemAtIndex_(1).isAlternate(), True)
    sheet.row("…and the Go line above it is not", menu.itemAtIndex_(0).isAlternate(), False)

    say("\n  a rebuild")
    s.menu([(Submenu("Settings"), [("Open wobble at login", lambda: chose.append("on"))]),
            ("Quit wobble", lambda: chose.append("quit"))])
    sub = s._menu.itemAtIndex_(0).submenu()
    sheet.row("a rebuild replaces the submenu too",
              titles(sub) if sub is not None else None, ["Open wobble at login"])
    sheet.row("…and its line is unchecked when handed plain",
              sub.itemAtIndex_(0).state() if sub is not None else None, 0)
    chose.clear()
    s._menu.performActionForItemAtIndex_(1)
    sheet.row("…and the tags start over: quit runs quit", chose, ["quit"])
    return not sheet.bad


MUTANTS = [
    ("the submenu never attached",
     ("item.setSubmenu_(self._build(handler, handlers))", "self._build(handler, handlers)")),
    ("the Settings line takes no place in the handlers",
     ("                handlers.append(None)\n                item.setSubmenu_(",
      "                item.setSubmenu_(")),
    ("the tags counted per list",
     ("item.setTag_(len(handlers))", "item.setTag_(menu.numberOfItems() - 1)")),
    ("the Settings line given an action",
     ('addItemWithTitle_action_keyEquivalent_(label, None, "")',
      'addItemWithTitle_action_keyEquivalent_(label, "chose:", "")')),
    ("no checkmark", ("item.setState_(NSControlStateValueOn)", "pass")),
    ("every line checked", ("if isinstance(label, Checked):", "if True:")),
    ("an alternate never swapped",
     ("if isinstance(label, Alternate) and menu.numberOfItems() > 1:", "if False:")),
    ("handlers not shared with the submenu",
     ("item.setSubmenu_(self._build(handler, handlers))",
      "item.setSubmenu_(self._build(handler, []))")),
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
