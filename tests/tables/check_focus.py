#!/usr/bin/env python3
"""Check that B raises the right window — and that every way it can fail says so.

    venv/bin/python3 tests/tables/check_focus.py

Criterion 10 is the reason this file is mostly refusals: Accessibility can be
taken away, and when it is, focusing is skipped and the app says so in words
while the notification still works. "Skipped" is checked as skipped — not one
raise attempted, not one app activated — because a refusal that still pokes at
the window server is not a refusal, it is a failure that happened to return
False.

**The permission is refused on purpose, not assumed.** macOS will not revoke
Accessibility on request, so `AXIsProcessTrusted` answers False from a fake
ApplicationServices standing in for the whole framework. What that proves is our
branch; what it cannot prove is that macOS says False when you untick the box,
and that is a manual step in DESK-CHECKS.md rather than a claim made here. The
sibling refusal — the framework missing altogether — is real: the import is
blocked through `sys.meta_path`, so the ImportError comes from Python's own
machinery.

**The control is seven mutants**: one that never says why, one that ignores the
permission, one that ignores a locked screen, one that claims it raised a window
without looking, one that looks in every app when the session's is known, one
that trusts activation's answer, one that never falls back to Accessibility. Each must break the table, or the table is not testing what it
says it is.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.platform_seam import macos                                   # noqa: E402
from src.platform_seam import ports                                   # noqa: E402

REGULAR = macos.NSApplicationActivationPolicyRegular
ACCESSORY = macos.NSApplicationActivationPolicyAccessory

# The AX error codes this really does meet on a live desk, measured while the
# port was being written: -25212 (kAXErrorNoValue) from a window mid-close and
# -25200 (kAXErrorFailure) from an app that answers its window list and then
# refuses the titles.
NO_VALUE, FAILURE = -25212, -25200


class Sheet:
    def __init__(self, quiet: bool = False):
        self.quiet, self.bad = quiet, 0

    def row(self, what: str, got, want) -> None:
        good = got == want
        self.bad += not good
        if not self.quiet:
            print(f"    {what:<54} {'ok' if good else f'<-- WRONG: {got!r}, wanted {want!r}'}")

    def says(self, what: str, answer, *must_name: str) -> None:
        """It refused, and the sentence names every one of `must_name`.

        A refusal carrying `(False, None)` is the silence principle 7 forbids,
        and it is the shape a helper that only checked `ok is False` would wave
        through. So the sentence is checked for the words that make it useful —
        what was looked for, or what to go and do about it.
        """
        ok, why = answer
        if ok is not False:
            self._fail(what, f"it went through: {answer!r}")
            return
        if not why:
            self._fail(what, "refused with no reason at all")
            return
        missing = [name for name in must_name if name.casefold() not in why.casefold()]
        if missing:
            self._fail(what, f"refused without naming {missing}: {why}")
            return
        if not self.quiet:
            print(f"    {what:<54} refused, naming {list(must_name)}")

    def _fail(self, what: str, detail: str) -> None:
        self.bad += 1
        if not self.quiet:
            print(f"    {what:<54} <-- {detail}")

    def ok(self) -> bool:
        return not self.bad


class FakeApp:
    """One running application, as much of `NSRunningApplication` as is used."""

    def __init__(self, name, pid, titles, policy=REGULAR, activates=True, arrives=None):
        self.name, self.pid, self.titles = name, pid, titles
        self.policy, self.activates = policy, activates
        # What activation really does, when it is not what it says (task 38):
        # `arrives=False` is a call that answers True and moves nothing.
        self.arrives = activates if arrives is None else arrives
        self.activated = 0
        self.ax = None            # set by `install`, so activation can move the front

    def activationPolicy(self):
        return self.policy

    def processIdentifier(self):
        return self.pid

    def localizedName(self):
        return self.name

    def bundleIdentifier(self):
        return f"desk.{self.name.lower()}"

    def activateWithOptions_(self, _options):
        self.activated += 1
        if self.arrives and self.ax is not None:
            self.ax.front = self.pid
        return self.activates


class FakeWorkspace:
    """`NSWorkspace`, as a class with the one class method that gets called."""

    apps: list = []
    front = None

    @classmethod
    def sharedWorkspace(cls):
        return cls

    @classmethod
    def runningApplications(cls):
        return cls.apps

    @classmethod
    def frontmostApplication(cls):
        return cls.front


class FakeAX:
    """The whole Accessibility framework, standing in for ApplicationServices.

    A whole-module substitute rather than a patched method, so nothing of ours
    leaks into the thing our branch is being checked against. Every window it
    knows about comes from `FakeApp.titles`; a title given as an int is an AX
    error code instead of a string, which is how an unreadable window is spelt.
    """

    kAXWindowsAttribute = "AXWindows"
    kAXTitleAttribute = "AXTitle"
    kAXMainAttribute = "AXMain"
    kAXRaiseAction = "AXRaise"
    kAXFrontmostAttribute = "AXFrontmost"
    kCGWindowListOptionOnScreenOnly = 1
    kCGWindowListExcludeDesktopElements = 16
    kCGNullWindowID = 0
    kCGWindowLayer = "kCGWindowLayer"
    kCGWindowOwnerPID = "kCGWindowOwnerPID"

    def __init__(self, apps, trusted=True, locked=False, windows_err=0, raise_err=0,
                 frontmost_err=0):
        # The second way forward (task 38): Accessibility's "frontmost", which
        # moves the front unless it answers an error.
        self.frontmost_err = frontmost_err
        self.front = None
        self.by_pid = {app.pid: app for app in apps}
        self.trusted, self.windows_err, self.raise_err = trusted, windows_err, raise_err
        self.locked = locked
        self.timeouts: list = []
        self.raised: list = []
        self.made_main: list = []
        self.asked = 0

    def AXIsProcessTrusted(self):
        return self.trusted

    def CGSessionCopyCurrentDictionary(self):
        # `locked=None` is the third answer macOS gives: no window server
        # session at all, which is not a locked screen.
        if self.locked is None:
            return None
        return {"CGSSessionScreenIsLocked": self.locked}

    def AXUIElementCreateApplication(self, pid):
        return ("app", pid)

    def AXUIElementSetMessagingTimeout(self, element, seconds):
        self.timeouts.append((element, seconds))

    def AXUIElementCopyAttributeValue(self, element, attribute, _placeholder):
        self.asked += 1
        if attribute == self.kAXWindowsAttribute:
            if self.windows_err:
                return self.windows_err, None
            titles = self.by_pid[element[1]].titles
            return 0, [("win", element[1], i) for i in range(len(titles))]
        if attribute == self.kAXTitleAttribute:
            title = self.by_pid[element[1]].titles[element[2]]
            return (title, None) if isinstance(title, int) else (0, title)
        raise AssertionError(f"nothing asks for {attribute}")

    def AXUIElementSetAttributeValue(self, element, attribute, value):
        if attribute == self.kAXFrontmostAttribute:
            if not self.frontmost_err:
                self.front = element[1]
            return self.frontmost_err
        self.made_main.append((element, attribute, value))
        return 0

    def CGWindowListCopyWindowInfo(self, option, relative):
        if self.front is None:
            return []
        return [{self.kCGWindowLayer: 0, self.kCGWindowOwnerPID: self.front}]

    def AXUIElementPerformAction(self, element, action):
        self.raised.append((element, action))
        return self.raise_err


def install(apps, **kwargs) -> FakeAX:
    """Put a whole fake macOS behind `macos.Focus`, and hand back the AX half."""
    ax = FakeAX(apps, **kwargs)
    for app in apps:
        app.ax = ax
    macos._AX, macos._AX_WHY, macos._AX_TRIED = ax, None, True
    FakeWorkspace.apps = apps
    macos.NSWorkspace = FakeWorkspace
    return ax


def desk(**kwargs) -> tuple[FakeAX, list[FakeApp]]:
    """The desk this check pretends to be sitting at, three apps deep."""
    apps = [
        # An accessory app with a perfect title: it has no window to raise and
        # must be walked straight past. This daemon is one of these.
        FakeApp("wobble-daemon", 10, ["wobble — the daemon"], policy=ACCESSORY),
        FakeApp("Spotify", 20, ["Spotify Premium"]),
        # NO_VALUE first: an unreadable title must not stop the app being read.
        FakeApp("Code", 30, [NO_VALUE, "Install_hooks.py — wobble", "x — quarry"]),
        FakeApp("Finder", 40, ["wobble"]),
    ]
    return install(apps, **kwargs), apps


class NoApplicationServices:
    """A real ImportError for a real import, from Python's own machinery."""

    def find_spec(self, name, path=None, target=None):
        if name == "ApplicationServices":
            raise ImportError("blocked at the desk — pretending it was never installed")
        return None


def run_all(make, quiet: bool = False) -> bool:
    sheet = Sheet(quiet)

    if not quiet:
        print("\n  the window comes forward, and the right one")
    ax, apps = desk()
    focus = make(macos.Focus())
    sheet.row("a hint in a window title is found", focus.window("wobble"), (True, "'Install_hooks.py — wobble' came forward"))
    sheet.row("…and it is Code that was brought forward",
              [app.activated for app in apps], [0, 0, 1, 0])
    sheet.row("…the window itself was raised",
              ax.raised, [(("win", 30, 1), "AXRaise")])
    sheet.row("…and made its app's main one",
              ax.made_main, [(("win", 30, 1), "AXMain", True)])

    ax, apps = desk()
    sheet.row("the hint does not have to match case",
              make(macos.Focus()).window("WOBBLE"), (True, "'Install_hooks.py — wobble' came forward"))
    sheet.row("…still Code, not the accessory app whose title fits better",
              [app.activated for app in apps], [0, 0, 1, 0])

    ax, apps = desk()
    sheet.row("a title in another app is found too",
              make(macos.Focus()).window("Spotify"),
              (True, "'Spotify Premium' came forward"))
    sheet.row("…and only that app was touched",
              [app.activated for app in apps], [0, 1, 0, 0])

    ax, _ = desk()
    make(macos.Focus()).window("quarry")
    sheet.row("an unreadable title is skipped, not the app with it",
              ax.raised, [(("win", 30, 2), "AXRaise")])

    ax, _ = desk()
    make(macos.Focus()).window("wobble")
    # Two, not four: the accessory app is never asked and Finder is never
    # reached. A wedged app costs this timeout and not the whole daemon.
    # This is also the spec's "two sessions in the same project folder" edge
    # case: Code and Finder both carry `wobble` and are indistinguishable by
    # title, so the sweep takes the first it meets and stops — the second is
    # never asked, never raised, and never claimed to be the one.
    sheet.row("every app asked is asked with a timeout set first",
              [seconds for _, seconds in ax.timeouts], [macos._PER_APP_S] * 2)

    if not quiet:
        print("\n  only the session's own app is looked in (task 38)")
    # Finder carries a window titled exactly `wobble` and sits after Code; a
    # session known to run in Finder must get Finder's, not the first match.
    ax, apps = desk()
    sheet.row("the app named is the only one looked in",
              make(macos.Focus()).window("wobble", app="desk.finder"),
              (True, "'wobble' came forward"))
    sheet.row("…and Code, which fits first, was never touched",
              ([a.activated for a in apps], ax.raised), ([0, 0, 0, 1], [(("win", 40, 0), "AXRaise")]))

    ax, apps = desk()
    sheet.row("the core's rule decides, not a substring",
              make(macos.Focus()).window("wobble", fits=lambda t: t == "x — quarry"),
              (True, "'x — quarry' came forward"))

    ax, apps = desk()
    sheet.row("none of its windows fits: the app itself comes forward",
              make(macos.Focus()).window("pokeball", app="desk.code"),
              (True, "Code came forward as it was — none of its windows names 'pokeball'"))
    sheet.row("…raising no window, and touching only Code",
              (ax.raised, [a.activated for a in apps]), ([], [0, 0, 1, 0]))

    ax, apps = desk()
    answer = make(macos.Focus()).window("wobble", app="desk.warp")
    sheet.says("the session's app is not open", answer, "desk.warp", "not open")
    sheet.row("…and it did not fall back to any other app's window",
              (answer[0], ax.raised, [a.activated for a in apps]), (False, [], [0, 0, 0, 0]))

    if not quiet:
        print("\n  refusals — every one of them says what did not happen")
    ax, apps = desk(trusted=False)
    answer = make(macos.Focus()).window("wobble")
    sheet.says("Accessibility refused", answer, "Accessibility", "System Settings")
    sheet.row("…and the refusal touched nothing at all",
              (ax.asked, ax.raised, [a.activated for a in apps]), (0, [], [0, 0, 0, 0]))

    # The screen being locked is the ordinary case for a notifier, not an edge:
    # it is the state you are in when a notification matters. macOS answers every
    # window title as its own app's name while locked, so looking would report
    # that nothing matched — true, useless, and about the wrong thing.
    ax, apps = desk(locked=True)
    answer = make(macos.Focus()).window("wobble")
    sheet.says("the screen is locked", answer, "locked", "when you unlock")
    sheet.row("…and it did not go looking at unreadable titles",
              (ax.asked, ax.raised, [a.activated for a in apps]), (0, [], [0, 0, 0, 0]))

    ax, _ = desk(locked=None)
    sheet.row("no window server session at all is not a locked screen",
              make(macos.Focus()).window("wobble"), (True, "'Install_hooks.py — wobble' came forward"))

    ax, _ = desk()
    sheet.says("a signal carrying no hint", make(macos.Focus()).window(""), "no window hint")
    sheet.says("a hint that is only spaces", make(macos.Focus()).window("   "),
               "no window hint")
    sheet.row("…and neither of them went looking", ax.asked, 0)

    sheet.says("no window on screen matches",
               make(macos.Focus()).window("no-such-project"), "no-such-project")

    ax, apps = desk(raise_err=FAILURE)
    sheet.says("macOS refuses to raise the window",
               make(macos.Focus()).window("wobble"), "Install_hooks.py", str(FAILURE))

    apps = [FakeApp("Code", 30, ["x — wobble"], activates=False)]
    install(apps, frontmost_err=-25200)
    sheet.says("macOS refuses to bring the app forward, both ways",
               make(macos.Focus()).window("wobble"), "x — wobble", "behind everything else")

    if not quiet:
        print("\n  activation refused, and Accessibility brings it instead (task 38)")
    apps = [FakeApp("Warp", 50, ["quarry · 7d42"], activates=False)]
    install(apps)
    sheet.row("refused activation falls back to Accessibility's frontmost",
              make(macos.Focus()).window("quarry"),
              (True, "'quarry · 7d42' came forward via Accessibility"))
    apps = [FakeApp("Warp", 50, ["quarry · 7d42"], arrives=False)]
    install(apps)
    sheet.row("an activation that says yes and moves nothing is not believed",
              make(macos.Focus()).window("quarry"),
              (True, "'quarry · 7d42' came forward via Accessibility"))
    apps = [FakeApp("Warp", 50, ["✳ Claude Code"], activates=False)]
    install(apps)
    sheet.row("the app itself falls back the same way",
              make(macos.Focus()).window("quarry", app="desk.warp"),
              (True, "Warp came forward as it was via Accessibility — none of its "
                     "windows names 'quarry'"))
    apps = [FakeApp("Warp", 50, ["✳ Claude Code"], activates=False)]
    install(apps, frontmost_err=-25200)
    sheet.says("…and says so when both are refused",
               make(macos.Focus()).window("quarry", app="desk.warp"), "Warp", "both ways")

    # A budget of zero rather than a fake that sleeps: the thing being checked is
    # that the deadline is looked at between apps, and a sleep would make that a
    # question about how fast this machine is.
    ax, _ = desk()
    sheet.says("the scan runs out of its budget",
               make(macos.Focus()).window("wobble", timeout=0.0), "0.0s")
    sheet.row("…before asking a single app anything", ax.asked, 0)

    ax, _ = desk(windows_err=FAILURE)
    sheet.says("no app will list its windows",
               make(macos.Focus()).window("wobble"), "wobble")
    sheet.row("…and all three were asked before giving up", ax.asked, 3)

    return sheet.ok()


class NeverSaysWhy(macos.Focus):
    def window(self, hint, *, app=None, fits=None, folder=None, timeout=1.5):
        ok, _ = super().window(hint, app=app, fits=fits, timeout=timeout)
        return ok, None


class AlwaysTrusted(macos.Focus):
    def _trusted(self, ax):
        return True


class IgnoresTheLock(macos.Focus):
    def _locked(self, ax):
        return False


class IgnoresTheApp(macos.Focus):
    def window(self, hint, *, app=None, fits=None, folder=None, timeout=1.5):
        return super().window(hint, fits=fits, timeout=timeout)


class ClaimsItRaised(macos.Focus):
    def _raise(self, ax, running, window, title):
        return True, None


class TrustsActivation(macos.Focus):
    """The seam before task 38's fallback: activation's answer taken as the truth."""
    def _forward(self, ax, running):
        ok = running.activateWithOptions_(macos.NSApplicationActivateIgnoringOtherApps)
        return "" if ok else None


class NeverFallsBack(macos.Focus):
    """Read back, but with no second way forward."""
    def _forward(self, ax, running):
        pid = running.processIdentifier()
        ok = running.activateWithOptions_(macos.NSApplicationActivateIgnoringOtherApps)
        return "" if ok and self._arrived(ax, pid, wait=0.0) else None


def main() -> int:
    print(__doc__.strip().splitlines()[0])
    real_workspace = macos.NSWorkspace
    ok = run_all(lambda f: f)

    print("\n  the port is the port")
    sheet = Sheet()
    sheet.row("Focus satisfies its Protocol", isinstance(macos.Focus(), ports.Focus), True)
    sheet.row("Frontmost satisfies its Protocol",
              isinstance(macos.Frontmost(), ports.Frontmost), True)

    print("\n  frontmost — plain data, and None is not the same as nothing in front")
    FakeWorkspace.front = FakeApp("Code", 30, [])
    sheet.row("the three fields, and nothing else", macos.Frontmost().app(),
              {"name": "Code", "bundle": "desk.code", "pid": 30})
    FakeWorkspace.front = None
    sheet.row("nothing in front answers None", macos.Frontmost().app(), None)
    ok &= sheet.ok()

    print("\n  the framework missing — a real ImportError, not a pretend one")
    macos.NSWorkspace = real_workspace
    macos._AX, macos._AX_WHY, macos._AX_TRIED = None, None, False
    saved = sys.modules.pop("ApplicationServices", None)
    blocker = NoApplicationServices()
    sys.meta_path.insert(0, blocker)
    try:
        sheet = Sheet()
        sheet.says("the Accessibility framework is not installed",
                   macos.Focus().window("wobble"), "pyobjc-framework-ApplicationServices")
        sheet.says("…and it says it again on the next press, not once",
                   macos.Focus().window("wobble"), "pyobjc-framework-ApplicationServices")
        ok &= sheet.ok()
    finally:
        sys.meta_path.remove(blocker)
        if saved is not None:
            sys.modules["ApplicationServices"] = saved
        macos._AX, macos._AX_WHY, macos._AX_TRIED = None, None, False

    print("\n  against the real macOS on this desk — no window is raised here")
    sheet = Sheet()
    ax, why = macos._ax()
    sheet.row("ApplicationServices loads", ax is not None and why is None, True)
    if ax is not None:
        sheet.row("this process has Accessibility", ax.AXIsProcessTrusted(), True)
        # Twice, and both numbers printed, because the first sweep in a process
        # is not the sweep — it is the Accessibility framework waking up, and it
        # costs around half a second once. The daemon pays that on its first B
        # press and never again, so the number worth holding to is the second.
        started = time.monotonic()
        answer = macos.Focus().window("wobble-no-window-is-called-this")
        cold = time.monotonic() - started
        started = time.monotonic()
        macos.Focus().window("wobble-no-window-is-called-this")
        warm = time.monotonic() - started
        # Whether this desk is locked right now is not something to pin, but the
        # answer has to match it: unlocked it must have swept and found nothing,
        # locked it must say so instead of reporting an absence it never looked
        # for. Run it both ways to see both.
        locked = macos.Focus()._locked(ax)
        print(f"    {'…this desk is':<54} {'locked' if locked else 'unlocked'} right now")
        sheet.says("a hint nothing can match", answer,
                   "locked" if locked else "nothing was raised")
        print(f"    {'…the first sweep of the process costs':<54} {cold * 1000:.0f} ms")
        sheet.row("…and every one after it is under 50 ms", warm < 0.05, True)
        front = macos.Frontmost().app()
        sheet.row("something real is in front",
                  front is not None and set(front) == {"name", "bundle", "pid"}, True)
    ok &= sheet.ok()

    print("\n  the control — seven rules removed, each must break the table")
    for label, cls in (("the reason never given", NeverSaysWhy),
                       ("the permission ignored", AlwaysTrusted),
                       ("the locked screen ignored", IgnoresTheLock),
                       ("success claimed without looking", ClaimsItRaised),
                       ("any app's window taken", IgnoresTheApp),
                       ("activation's answer trusted", TrustsActivation),
                       ("no second way forward", NeverFallsBack)):
        survived = run_all(lambda _f, c=cls: c(), quiet=True)
        ok &= not survived
        print(f"    {label:<54} "
              f"{'<-- SURVIVED, so the table does not test it' if survived else 'caught'}")

    macos.NSWorkspace = real_workspace
    print("\n" + ("ALL CASES MATCH the known answer" if ok
                  else "SOMETHING DOES NOT MATCH — the rows above, not this line"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
