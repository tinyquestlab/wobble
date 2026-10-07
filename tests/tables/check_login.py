#!/usr/bin/env python3
"""Check the macOS `Login` port: the agent it writes, and the four answers it reads.

    venv/bin/python3 tests/tables/check_login.py

Every known answer comes from spec 02 task 01, measured at a real login
(`specs/02-open-at-login/learnings.md`): the file is whether it was asked for,
`SMAppService.statusForLegacyURL_` is whether macOS allows it, `2` is switched
off in System Settings, and `3` is what a write reads for ~2 s after it.

**Nothing here touches the real `~/Library/LaunchAgents` or System Settings.**
Each leg points the port at a temporary folder and a fake SMAppService that
records what it was asked. The written file is checked twice: read back by
`plistlib`, and by `plutil -lint`, which is macOS's own reader (principle 4).

**The control is mutants made from the source itself**, as in
`check_macos_edges.py`: one rule's text in `macos.py` replaced, the method
recompiled, the table re-run. A mutant whose text is gone is reported wrong.
"""
from __future__ import annotations

import __future__
import inspect
import plistlib
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.platform_seam import macos, ports                            # noqa: E402

ENABLED, REQUIRES_APPROVAL, NOT_FOUND, NOT_REGISTERED = 1, 2, 3, 0


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


class FakeService:
    """SMAppService's two class methods the port calls, answering as told."""

    def __init__(self, verdict=ENABLED, *, fails: bool = False) -> None:
        self.verdict, self.fails, self.asked, self.opened = verdict, fails, [], 0

    def statusForLegacyURL_(self, url):
        if self.fails:
            raise RuntimeError("no ServiceManagement here")
        self.asked.append(url.path())
        return self.verdict

    def openSystemSettingsLoginItems(self):
        if self.fails:
            raise RuntimeError("no ServiceManagement here")
        self.opened += 1


def desk(root: Path, *, app: bool = True, agent: bool = False, verdict=ENABLED,
         fails: bool = False) -> tuple[macos.Login, FakeService]:
    """A port over `root`: an app there or not, an agent file there or not."""
    for folder in (p for p in root.rglob("*") if p.is_dir()):        # the refusing legs' 0o555
        folder.chmod(0o755)
    for path in sorted(root.rglob("*"), reverse=True):
        path.rmdir() if path.is_dir() else path.unlink()
    where = root / "Applications" / "wobble.app"
    if app:
        where.mkdir(parents=True)
    service = FakeService(verdict, fails=fails)
    login = macos.Login(app=where, agent=root / "LaunchAgents" / "local.wobble.login.plist",
                        service=service)
    if agent:
        login.agent.parent.mkdir(parents=True, exist_ok=True)
        login.agent.write_bytes(plistlib.dumps(macos.agent_plist(where)))
    return login, service


def table(sheet: Sheet) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        sheet.head("the port's shape")
        login, _ = desk(root)
        sheet.row("macos.Login satisfies ports.Login", isinstance(login, ports.Login), True)

        sheet.head("the agent written by set(True) — what task 01 measured at a login")
        login, service = desk(root)
        got = attempt(lambda: login.set(True))
        sheet.row("set(True) answers ok, naming the file and macOS's notice",
                  got, (True, f"wobble opens at login from now on ({login.agent}); "
                              f"macOS says \"Background Items Added\""))
        written = plistlib.loads(login.agent.read_bytes()) if login.agent.exists() else None
        sheet.row("the file opens the app through `open`, once, at login",
                  written, {"Label": "local.wobble.login",
                            "ProgramArguments": ["/usr/bin/open", str(login.app)],
                            "RunAtLoad": True, "LimitLoadToSessionType": "Aqua",
                            "AssociatedBundleIdentifiers": ["local.wobble"]})
        sheet.row("no KeepAlive: Quit stays quit until the next login",
                  "KeepAlive" in (written or {}), False)
        lint = subprocess.run(["plutil", "-lint", str(login.agent)], capture_output=True, text=True)
        sheet.row("plutil -lint reads it as a valid plist (second source)", lint.returncode, 0)
        sheet.row("writing asks macOS nothing", service.asked, [])

        sheet.head("state() — four answers, read fresh")
        login, service = desk(root)
        sheet.row("no file: off", attempt(login.state), ("off", None))
        sheet.row("no file: macOS is not asked", service.asked, [])
        for verdict, name in ((ENABLED, "enabled"), (NOT_FOUND, "notFound, ~2 s after a write"),
                              (NOT_REGISTERED, "notRegistered")):
            login, service = desk(root, agent=True, verdict=verdict)
            sheet.row(f"file, {name}: on", attempt(login.state), ("on", None))
        sheet.row("macOS is asked about the agent's own path", service.asked, [str(login.agent)])
        login, _ = desk(root, agent=True, verdict=REQUIRES_APPROVAL)
        sheet.row("file, requiresApproval: disabled, saying where to switch it on",
                  attempt(login.state), ("disabled", macos.SWITCHED_OFF))
        login, _ = desk(root, agent=True, fails=True)
        got = attempt(login.state)
        sheet.row("file, macOS cannot be asked: on, with the doubt said",
                  (got[0], got[1].startswith("macOS could not be asked whether it allows it")),
                  ("on", True))
        login, service = desk(root, agent=False, verdict=REQUIRES_APPROVAL)
        sheet.row("macOS's remembered off with no file: off", attempt(login.state), ("off", None))
        sheet.row("read again after the file appears: disabled",
                  (login.set(True)[0], login.state()[0]), (True, "disabled"))

        sheet.head("no wobble.app in /Applications")
        login, _ = desk(root, app=False)
        got = attempt(login.state)
        sheet.row("state: cannot be set, saying how to build it",
                  (got[0], "tools/build_app.py --install" in got[1]), (None, True))
        login, _ = desk(root, app=False, agent=True)
        got = attempt(login.state)
        sheet.row("state with an agent left behind: names the app it would open",
                  (got[0], f"opens {login.app}, which is not there" in got[1]), (None, True))
        login, _ = desk(root, app=False)
        got = attempt(lambda: login.set(True))
        sheet.row("set(True) refuses, saying why", (got[0], "nothing to open" in got[1]), (False, True))
        sheet.row("…and writes no file", login.agent.exists(), False)

        sheet.head("set(False)")
        login, _ = desk(root, agent=True)
        sheet.row("removes the file", (attempt(lambda: login.set(False)), login.agent.exists()),
                  ((True, f"wobble no longer opens at login ({login.agent} removed)"), False))
        sheet.row("again: already off, still ok", attempt(lambda: login.set(False)),
                  (True, "wobble already did not open at login"))
        sheet.row("then state: off", attempt(login.state), ("off", None))

        sheet.head("a folder that refuses — said, never raised")
        login, _ = desk(root, agent=True)
        login.agent.parent.chmod(0o555)
        got = attempt(lambda: login.set(False))
        sheet.row("cannot remove: not ok, and still opens at login",
                  (got[0], got[1].endswith("so wobble still opens at login")), (False, True))
        login, _ = desk(root)
        login.agent.parent.mkdir(parents=True)
        login.agent.parent.chmod(0o555)
        got = attempt(lambda: login.set(True))
        sheet.row("cannot write: not ok, and does not open at login",
                  (got[0], got[1].endswith("so wobble does not open at login")), (False, True))

        sheet.head("settings()")
        login, service = desk(root)
        sheet.row("opens Login Items, naming the section",
                  (attempt(login.settings), service.opened),
                  ((True, "System Settings opened at Login Items — wobble is under App "
                          "Background Activity"), 1))
        login, _ = desk(root, fails=True)
        got = attempt(login.settings)
        sheet.row("cannot open: said, not raised",
                  (got[0], got[1].startswith("System Settings could not be opened")), (False, True))
        desk(root)


# --- the mutants ----------------------------------------------------------------

MUTANTS = [
    ("state trusting the file alone", "state",
     "if verdict == _REQUIRES_APPROVAL:", "if False:"),
    ("state calling anything but enabled off, the ~2 s lag after a write too", "state",
     "if verdict == _REQUIRES_APPROVAL:", "if verdict != 1:"),
    ("state not checking the app is there", "state",
     "if not self.app.is_dir():", "if False:"),
    ("state raising when macOS cannot be asked", "state",
     "except Exception as exc:", "except ZeroDivisionError as exc:"),
    ("set(True) writing with no app to open", "set",
     "if not self.app.is_dir():", "if False:"),
    ("set(False) calling a missing file a failure", "set",
     "except FileNotFoundError:", "except ZeroDivisionError:"),
    ("set(True) raising on a folder that refuses", "set",
     "except OSError as exc:\n        return False, f\"{self.agent} could not be written",
     "except ZeroDivisionError as exc:\n        return False, f\"{self.agent} could not be written"),
    ("settings raising when it cannot open", "settings",
     "except Exception as exc:", "except ZeroDivisionError as exc:"),
]


def mutate(method: str, old: str, new: str):
    """`method` recompiled with `old` replaced, in macos's own globals; None if stale."""
    source = textwrap.dedent(inspect.getsource(getattr(macos.Login, method)))
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
        original = macos.Login.__dict__[method]
        broken = mutate(method, old, new)
        if broken is None:
            sheet.row(f"mutant: {name}", "stale: its text is not in macos.py once", "caught")
            continue
        setattr(macos.Login, method, broken)
        quiet = Sheet(quiet=True)
        try:
            table(quiet)
        except Exception:                                             # noqa: BLE001
            quiet.bad += 1
        finally:
            setattr(macos.Login, method, original)
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
