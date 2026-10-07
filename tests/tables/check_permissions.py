#!/usr/bin/env python3
"""Check the macOS `Permissions` port: what each answer reads as, and the panes it opens.

    venv/bin/python3 tests/tables/check_permissions.py

Every known answer comes from spec 03 task 01, measured on macOS 26.6.2
(`specs/03-permissions-in-the-menu/tasks.md`): `CBManager.authorization` answers
0 not asked, 1 restricted, 2 denied, 3 allowed; Automation answers 0, -1743
refused, -1744 not asked and -600 for an app that is not running; and the
classic `x-apple.systempreferences:` addresses land on the right pane.

**Nothing here opens System Settings or changes a grant.** Each leg hands the
port a fake CoreBluetooth manager, a fake Accessibility framework, a fake
Automation answer and a fake opener that records the address. Two rows ask the
real macOS, read only: the ctypes call for an app that is not there, and
Bluetooth's own answer.

**The control is mutants made from the source itself**, as in `check_login.py`:
one rule's text in `macos.py` replaced, the method recompiled, the table re-run.
A mutant whose text is gone is reported wrong.
"""
from __future__ import annotations

import __future__
import inspect
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.platform_seam import macos, ports                            # noqa: E402

TERMINAL = "automation:com.apple.Terminal"
PANE = "x-apple.systempreferences:com.apple.preference.security?Privacy_"


class Sheet:
    def __init__(self, quiet: bool = False) -> None:
        self.quiet, self.bad, self.rows = quiet, 0, 0

    def head(self, text: str) -> None:
        if not self.quiet:
            print(f"\n  {text}")

    def row(self, what: str, got, want) -> None:
        good = got == want
        self.bad += not good
        self.rows += 1
        if not self.quiet:
            print(f"    {what:<70} {'ok' if good else f'<-- WRONG: {got!r}, wanted {want!r}'}")


def attempt(call):
    """The answer, or what it raised: a seam that raises has broken principle 7."""
    try:
        return call()
    except Exception as exc:                                          # noqa: BLE001
        return f"raised {type(exc).__name__}: {exc}"


class Manager:
    """`CBManager`, answering whatever it is set to — or raising, for `None`."""

    def __init__(self, answer) -> None:
        self.answer = answer

    def authorization(self):
        if self.answer is None:
            raise RuntimeError("CoreBluetooth went away")
        return self.answer


class AX:
    def __init__(self, trusted) -> None:
        self.trusted = trusted

    def AXIsProcessTrusted(self):                                     # noqa: N802
        if self.trusted is None:
            raise RuntimeError("the AX server went away")
        return self.trusted


class Desk:
    """One port and everything it was asked."""

    def __init__(self, *, bluetooth=3, trusted=True, ax=True, automation=0, opens=True) -> None:
        self.ax_framework = AX(trusted)
        self.automation, self.opens = automation, opens
        self.asked: list[str] = []
        self.opened: list[str] = []
        self.port = macos.Permissions(
            manager=Manager(bluetooth),
            ax=(lambda: (self.ax_framework, None)) if ax else (lambda: (None, "gone")),
            automation=self._automation, opener=self._open)

    def _automation(self, bundle: str) -> int:
        self.asked.append(bundle)
        return self.automation

    def _open(self, url: str) -> bool:
        self.opened.append(url)
        if self.opens is None:
            raise RuntimeError("Launch Services went away")
        return self.opens


def state(**desk):
    return lambda kind: attempt(lambda: Desk(**desk).port.state(kind))


def table(sheet: Sheet) -> None:
    sheet.head("kinds: worst loss first, one Automation line per app wobble scripts")
    sheet.row("bluetooth, accessibility, then Terminal's automation",
              Desk().port.kinds(), ("bluetooth", "accessibility", TERMINAL))

    sheet.head("bluetooth, as CBManager.authorization answers (task 01)")
    sheet.row("3 is granted", state(bluetooth=3)("bluetooth"), ("granted", None))
    sheet.row("0 is not asked, which is not missing", state(bluetooth=0)("bluetooth")[0],
              "not asked")
    sheet.row("2 is refused, and says the ball cannot connect",
              state(bluetooth=2)("bluetooth"),
              ("refused", "Bluetooth is switched off in Privacy & Security: the ball cannot connect"))
    sheet.row("1, restricted by a profile, is refused too, and says it is a profile",
              state(bluetooth=1)("bluetooth"),
              ("refused", "Bluetooth is restricted on this Mac, by a profile or Screen Time: "
                          "the ball cannot connect"))
    sheet.row("an answer wobble does not know is never granted",
              state(bluetooth=7)("bluetooth"),
              (None, "Bluetooth answered 7, which wobble does not know"))
    sheet.row("a manager that raises is unreadable, never a raise",
              state(bluetooth=None)("bluetooth"),
              (None, "whether bluetooth is granted could not be read "
                     "(RuntimeError('CoreBluetooth went away'))"))

    sheet.head("accessibility, as AXIsProcessTrusted answers")
    sheet.row("trusted is granted", state(trusted=True)("accessibility"), ("granted", None))
    sheet.row("untrusted is refused, and says B raises no window",
              state(trusted=False)("accessibility"),
              ("refused", "Accessibility is switched off in Privacy & Security: B raises no "
                          "window, and a signal plays even while you look at its session"))
    sheet.row("no Accessibility API is unreadable, said as that",
              state(ax=False)("accessibility"),
              (None, "the Accessibility API is not available here, so whether it is granted "
                     "cannot be read"))
    sheet.row("a framework that raises is unreadable, never a raise",
              state(trusted=None)("accessibility")[0], None)
    desk = Desk(trusted=True)
    first = desk.port.state("accessibility")[0]
    desk.ax_framework.trusted = False
    sheet.row("read fresh: revoked between two reads, the second says so",
              (first, desk.port.state("accessibility")[0]), ("granted", "refused"))

    sheet.head("automation, as AEDeterminePermissionToAutomateTarget answers (task 01)")
    sheet.row("0 is granted", state(automation=0)(TERMINAL), ("granted", None))
    sheet.row("-1743 is refused, and says B cannot pick the tab",
              state(automation=-1743)(TERMINAL),
              ("refused", "Automation of Terminal is switched off in Privacy & Security: "
                          "B cannot pick the tab a session is in"))
    sheet.row("-1744 is not asked", state(automation=-1744)(TERMINAL)[0], "not asked")
    sheet.row("-600 is not running: macOS answers nothing then",
              state(automation=-600)(TERMINAL),
              ("not running", "Terminal is not running, so macOS answers nothing about automating it"))
    sheet.row("any other answer is unreadable, with the number said",
              state(automation=-50)(TERMINAL),
              (None, "whether wobble may automate Terminal could not be read (OSStatus -50)"))
    desk = Desk()
    desk.port.state(TERMINAL)
    sheet.row("it asks about the app named in the kind, by bundle id",
              desk.asked, ["com.apple.Terminal"])

    sheet.head("anything else")
    sheet.row("a kind nobody knows is unreadable, never granted",
              state()("camera"), (None, "there is no permission called 'camera'"))

    sheet.head("settings: the pane, by its classic address (task 01)")
    for kind, pane in (("accessibility", "Accessibility"), ("bluetooth", "Bluetooth"),
                       (TERMINAL, "Automation")):
        desk = Desk()
        said = attempt(lambda: desk.port.settings(kind))
        sheet.row(f"{kind} opens Privacy_{pane}", desk.opened, [PANE + pane])
        sheet.row("…and says which pane it opened",
                  said, (True, f"System Settings opened at Privacy & Security › {pane}"))
    desk = Desk(opens=False)
    sheet.row("an address macOS refuses is said, not claimed as opened",
              attempt(lambda: desk.port.settings("accessibility")),
              (False, "System Settings did not open at Privacy & Security › Accessibility: "
                      "macOS refused the address"))
    desk = Desk(opens=None)
    sheet.row("an opener that raises is said, never a raise",
              attempt(lambda: desk.port.settings("accessibility"))[0], False)
    desk = Desk()
    sheet.row("a kind with no pane opens nothing",
              (attempt(lambda: desk.port.settings("camera")), desk.opened),
              ((False, "there is no System Settings pane for 'camera'"), []))

    sheet.head("the real macOS, read only")
    sheet.row("the ctypes Automation call answers -600 for an app that is not there",
              attempt(lambda: macos._automation_status("local.wobble.nosuch")), -600)
    sheet.row("the real Bluetooth read answers, and never raises",
              attempt(lambda: macos.Permissions().state("bluetooth")[0])
              in ("granted", "not asked", "refused"), True)
    sheet.row("the port is the Protocol", isinstance(macos.Permissions(), ports.Permissions),
              True)


MUTANTS = [
    ("an unknown Bluetooth answer read as granted", "_bluetooth",
     "state = _BLUETOOTH.get(answer)", 'state = _BLUETOOTH.get(answer, "granted")'),
    ("restricted said as switched off", "_bluetooth",
     "if answer == 1:", "if False:"),
    ("untrusted read as granted", "_accessibility",
     "if _is_trusted(ax):", "if True:"),
    ("no Accessibility API left to the catch-all", "_accessibility",
     "if ax is None:", "if False:"),
    ("refused read as not asked", "_automation_of",
     "if status == _AE_REFUSED:", "if status == _AE_NOT_ASKED - 1:"),
    ("not running read as refused", "_automation_of",
     'return "not running", ', 'return "refused", '),
    ("any answer but the three read as granted", "_automation_of",
     "if status == 0:", "if status not in (_AE_REFUSED, _AE_NOT_ASKED, _AE_NOT_RUNNING):"),
    ("Terminal asked by its name, not its bundle id", "_automation_of",
     "status = self._automation(bundle)", "status = self._automation(name)"),
    ("state raising on a seam fault", "state",
     "except Exception as exc:", "except ZeroDivisionError as exc:"),
    ("an unknown kind left to fall through", "state",
     'return None, f"there is no permission called {kind!r}"', "pass"),
    ("settings raising when it cannot open", "settings",
     "except Exception as exc:", "except ZeroDivisionError as exc:"),
    ("a refused address said as opened", "settings",
     "if not opened:", "if False:"),
    ("every kind opening Accessibility", "settings",
     "self._open(_PANE_URL.format(pane))", 'self._open(_PANE_URL.format("Accessibility"))'),
    ("Automation not listed", "kinds",
     ', *(f"automation:{app}" for app in _TAB_SCRIPTS)', ""),
]


def mutate(method: str, old: str, new: str):
    """`method` recompiled with `old` replaced, in macos's own globals; None if stale."""
    source = textwrap.dedent(inspect.getsource(getattr(macos.Permissions, method)))
    if source.count(old) != 1:
        return None
    local: dict = {}
    code = compile(source.replace(old, new), macos.__file__, "exec",
                   flags=__future__.annotations.compiler_flag, dont_inherit=True)
    exec(code, macos.__dict__, local)                                 # noqa: S102
    return local[method]


def mutants(sheet: Sheet) -> None:
    sheet.head("mutants — each rule removed in turn must make a row wrong")
    for name, method, old, new in MUTANTS:
        original = macos.Permissions.__dict__[method]
        broken = mutate(method, old, new)
        if broken is None:
            sheet.row(f"mutant: {name}", "stale: its text is not in macos.py once", "caught")
            continue
        setattr(macos.Permissions, method, broken)
        quiet = Sheet(quiet=True)
        try:
            table(quiet)
        except Exception:                                             # noqa: BLE001
            quiet.bad += 1
        finally:
            setattr(macos.Permissions, method, original)
        verdict = "caught" if quiet.bad else "survived"
        sheet.rows += 1
        sheet.bad += verdict != "caught"
        print(f"    {'mutant: ' + name:<70} {verdict}"
              + ("" if verdict == "caught" else "  <-- the table does not test it"))


def main() -> int:
    print(__doc__.strip().splitlines()[0])
    sheet = Sheet()
    table(sheet)
    mutants(sheet)
    print(f"\n{sheet.rows} rows, " + ("ALL CASES MATCH the known answer" if not sheet.bad else
                                       f"{sheet.bad} WRONG — the rows above, not this line"))
    return 0 if not sheet.bad else 1


if __name__ == "__main__":
    sys.exit(main())
