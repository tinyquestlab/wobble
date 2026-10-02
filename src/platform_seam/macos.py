"""The macOS half of the seam — the one file in this project that names an OS.

All six ports are real. `Sound` and `Status` are what the menu bar mirror needs
(task 12); `Frontmost` and `Focus` are what B does with the signal it took
(task 14); `Process` is whether a session's claude still runs (task 40); `Idle`
is how long since a key or the mouse moved (task 64). Every
one of them answers `(ok, why not)` rather than raising: a
notifier that dies because a window would not come forward has become the
silence it exists to prevent (principle 7).

**Two frameworks, and only one of them can be refused.** AppKit is here at the
top and always works. The Accessibility API — reading window titles, raising one
— is granted per application in System Settings and can be taken away while the
process runs, so `Focus` asks every call and imports it lazily; the comment above
`_AX` says why that import is not up here with the rest.

**Who owns the run loop, the question `ports.py` left open for this task.** The
daemon does, and `Status.pump()` is how. Once per poll it asks AppKit for
whatever events have arrived, delivers them, and returns; nothing blocks and no
second thread exists.

The alternative is the usual PyObjC shape: `AppHelper.runEventLoop()` takes
the main thread and the asyncio work moves onto a worker, with every update
marshalled back by `AppHelper.callAfter`. That is the right shape for a process
whose job IS the UI, with the daemon in another process.
Here it is inside out: the queue, the attention machine and (at task 13) the BLE
link would move onto a background thread so that a status item with four
possible titles could have the main one, and every core call would need
marshalling for it. The price of pumping instead is latency — a click is seen up
to one poll interval (~0.25 s) late — and a quarter second is nothing to a
notification that has been waiting for somebody to walk back to the desk.

**Nothing is built at import.** `__init__.py` constructs all four singletons the
moment anything imports the seam, and a desk check that only wanted to play a
sound should not grow an icon in the menu bar. The status item appears on first
use.
"""
from __future__ import annotations

import ctypes
import os
import struct
import subprocess
import time
from typing import Callable

from AppKit import (NSAppearance, NSAppearanceNameAqua, NSAppearanceNameDarkAqua,
                    NSApplication, NSApplicationActivateIgnoringOtherApps,
                    NSApplicationActivationPolicyAccessory,
                    NSApplicationActivationPolicyRegular, NSBezierPath,
                    NSBitmapImageFileTypePNG, NSBitmapImageRep, NSColor,
                    NSCompositingOperationClear, NSCompositingOperationSourceAtop,
                    NSCompositingOperationSourceOver,
                    NSDeviceRGBColorSpace, NSEventMaskAny, NSEventMaskLeftMouseUp,
                    NSEventMaskRightMouseUp, NSEventModifierFlagControl,
                    NSEventModifierFlagOption,
                    NSEventTypeRightMouseUp, NSFontWeightRegular, NSGraphicsContext,
                    NSImage, NSImageLeft, NSImageSymbolConfiguration, NSMenu,
                    NSMenuItem, NSRectFillUsingOperation, NSRunningApplication,
                    NSStatusBar, NSVariableStatusItemLength, NSWorkspace)
from Foundation import (NSURL, NSAffineTransform, NSDate, NSDefaultRunLoopMode,
                        NSMakePoint, NSMakeRect, NSMakeSize, NSObject)
from Quartz import (CAKeyframeAnimation, CALayer, CAShapeLayer, CATransaction,
                    CGContextBeginTransparencyLayer, CGContextEndTransparencyLayer,
                    CGContextSetAlpha, CGPathCreateWithEllipseInRect, CGRectMake)

from .ports import Alternate, BallIcon


class Sound:
    """`afplay`, spawned and never waited for.

    Waiting would stop the daemon for the length of its own sound: the queue
    would stand still while it speaks, and a `needs` beating every 1.5 s would
    spend most of its life blocked. So the process is launched and let go.

    The handle is kept for one reason — `stop()` has to be able to cut a sound
    that is already playing, because B means silence now (criterion 4).
    """

    def __init__(self) -> None:
        self._playing: subprocess.Popen | None = None

    def play(self, path: str, volume: float | None = None) -> tuple[bool, str | None]:
        # The existence check is not belt-and-braces: `afplay` on a path that is
        # not there exits non-zero a moment later, into a process nobody waits
        # for, and the only symptom is a notification that made no sound. That is
        # the failure this project exists to not have.
        if not os.path.exists(path):
            return False, f"there is no sound file at {path}, so nothing was played"
        args = ["afplay"]
        if volume is not None:
            args += ["-v", str(volume)]
        args.append(path)
        self.stop()
        try:
            self._playing = subprocess.Popen(
                args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as exc:
            return False, f"could not play {path}: {exc}"
        return True, None

    def stop(self) -> None:
        if self._playing is not None and self._playing.poll() is None:
            self._playing.terminate()
        self._playing = None


# The Accessibility API is imported on first use, not at the top of this file,
# and the reason is `__init__.py`: a `ModuleNotFoundError` raised while importing
# this module makes the whole seam fall back to `null`, which would take the menu
# bar and the Mac sound down with it. Reading window titles is the only thing
# that needs ApplicationServices, so it is the only thing that pays for it being
# missing — the menu bar, the Mac sound and the BLE link are untouched.
#
# Above `Frontmost` since 2026-09-22 rather than just above `Focus`: two classes
# read window titles now, and a lazy import that sits below its first caller is
# one an editor moves things past without noticing.
_AX = None
_AX_WHY: str | None = None
_AX_MISSING: str | None = None
_AX_TRIED = False

# How long one app is allowed to take to answer `Focus`'s sweep. An app that is
# wedged — beachballing, or stopped in a debugger — answers never rather than
# slowly. Without this the whole daemon waits on it.
_PER_APP_S = 0.3

# The same idea with a tighter number, for the one app in front. `Frontmost.title`
# says why they differ: this one is paid on every poll rather than once per B
# press, so it is bounded by what the daemon's loop can afford to lose and not by
# what an app deserves to be given.
_FRONT_APP_S = 0.1

NOT_TRUSTED = (
    "macOS has not granted Accessibility to this process, so no window was "
    "raised — grant it in System Settings › Privacy & Security › Accessibility "
    "and restart the daemon. The notification itself is unaffected."
)

NOT_TRUSTED_TO_LOOK = (
    "macOS has not granted Accessibility to this process, so there is no way to "
    "see which window is in front — grant it in System Settings › Privacy & "
    "Security › Accessibility and restart the daemon. Signals will be played "
    "even when you are already looking at the session that raised them."
)

# Phrased separately from `_AX_WHY` rather than shared, because the two callers
# are asking different questions and a sentence about raising a window is a
# false sentence to hand somebody who asked what is in front. `__init__.py` has
# the same rule and the same reason.
_CANNOT_LOOK = (
    "the Accessibility API is not available here ({why}), so there is no way to "
    "see which window is in front. Install pyobjc-framework-ApplicationServices. "
    "Signals will be played even when you are already looking at the session "
    "that raised them."
)

# `ask`'s own, for the same reason: nobody tried to raise a window, so `_AX_WHY`'s
# "no window was raised" would be a false sentence there.
_CANNOT_ASK = (
    "the Accessibility API is not available here ({why}), so there is nothing to "
    "ask macOS for. Install pyobjc-framework-ApplicationServices. Until then no "
    "window is raised, and a signal plays even while you look at its session."
)

LOCKED = (
    "the screen is locked, so nothing was raised — it will be where you left it "
    "when you unlock. Window titles are not readable while locked either, so "
    "looking would have reported that no window matched, which is a different "
    "and untrue thing."
)


def _ax() -> tuple[object | None, str | None]:
    """ApplicationServices, or the sentence saying why there is none.

    The sentence is `Focus`'s. A caller that is not raising a window takes
    `_AX_MISSING` — the bare cause — and phrases its own.
    """
    global _AX, _AX_WHY, _AX_MISSING, _AX_TRIED
    if not _AX_TRIED:
        _AX_TRIED = True
        try:
            import ApplicationServices  # noqa: PLC0415 — deliberately not at import time
        except ImportError as exc:
            _AX_MISSING = str(exc)
            _AX_WHY = (f"no window was raised: the Accessibility API is not "
                       f"available here ({exc}). Install "
                       f"pyobjc-framework-ApplicationServices. The notification "
                       f"itself is unaffected.")
        else:
            _AX = ApplicationServices
    return _AX, _AX_WHY


def _is_trusted(ax) -> bool:
    """Whether Accessibility is ours right now. See `Focus._trusted` for why now."""
    return bool(ax.AXIsProcessTrusted())


def _is_locked(ax) -> bool:
    """Whether the login session is locked. See `Focus._locked` for what it costs.

    One function and two callers rather than the rule written twice: `Focus`
    refuses to raise a window while locked and `Frontmost` refuses to believe a
    title read while locked, and those are the same fact about macOS answering
    every window title as its own app's name. Two copies of it is one copy
    quietly going out of date.
    """
    session = ax.CGSessionCopyCurrentDictionary()
    return bool(session and session.get("CGSSessionScreenIsLocked"))


class Frontmost:
    """What is in front: the app as three plain fields, and the window's title.

    `app()` is `NSWorkspace` and needs no Accessibility permission at all — it is
    ordinary public API, unlike `title()` and everything in `Focus` below.

    **`app()` is a cache, and `title()` deliberately does not use it.** Measured
    2026-09-22 with a probe that switched apps mid-run:
    `frontmostApplication()` is fed by notifications, so a process that never
    services its run loop holds whatever was in front when it started. It lagged
    a whole switch behind with no pump, and tracked correctly with one. The
    daemon does pump — but only when there is a menu bar item to pump for, and
    `--no-menubar` builds no NSApplication at all. A `title()` resting on that
    would freeze at the wrong window, look entirely plausible, and silence
    notifications for the rest of the day.

    So `title()` asks the window server instead: `CGWindowListCopyWindowInfo`
    returns the on-screen windows front to back and is a live query — no cache,
    no notification, no run loop. The alternative measured alongside it was to
    spin the run loop inside the read, and that was rejected rather than being
    the slower option: spinning it here would deliver the menu bar's own clicks
    in the middle of a read that is called four times a second, which is a B
    press arriving from inside a question about focus.

    The pid comes from the window server and the title comes from the
    Accessibility API, because `kCGWindowName` needs Screen Recording — a second
    permission to ask a person for, to learn something the permission we already
    have will tell us.
    """

    def app(self) -> dict | None:
        running = NSWorkspace.sharedWorkspace().frontmostApplication()
        if running is None:
            return None
        return {"name": str(running.localizedName() or ""),
                "bundle": str(running.bundleIdentifier() or ""),
                "pid": int(running.processIdentifier())}

    def title(self) -> tuple[str | None, str | None]:
        """The title of the window in front. See `ports.Frontmost` for the shape.

        `(None, None)` — nothing in front to name — covers three different
        things, and they are one answer on purpose because they have one
        consequence: the caller signals as it always would. A locked screen, an
        app with no focused window, and an app that will not say are all "this
        cannot tell you to be quiet", and being quiet is the only thing this
        answer is ever used for.
        """
        title, _, why = self.window()
        return title, why

    def window(self) -> tuple[str | None, str | None, str | None]:
        """`title()`, and the bundle id of the app owning that window (task 38).

        The pid is the window server's owner of the front window, the same one
        the title is read from, so the app named is the title's own — not
        `frontmostApplication()`, whose cache `title()`'s docstring warns off.
        """
        ax, why = _ax()
        if ax is None:
            return None, None, _CANNOT_LOOK.format(why=_AX_MISSING or "it is not available")
        if not self._trusted(ax):
            return None, None, NOT_TRUSTED_TO_LOOK
        # Load-bearing, not tidiness. macOS answers every window title as the
        # name of its own app while the screen is locked (see `Focus._locked`),
        # so without this a session in a folder called `Code` would read as the
        # window in front for as long as nobody was at the desk — and being
        # away is precisely when the notification matters.
        if self._locked(ax):
            return None, None, None
        pid = self._front_pid(ax)
        if pid is None:
            return None, None, None
        element = ax.AXUIElementCreateApplication(pid)
        # Shorter than `Focus`'s `_PER_APP_S`, and for a different job: that one
        # is a one-shot sweep on a worker thread after a B press, this one runs
        # on the daemon's own loop on every poll. A wedged app in front costs
        # this much of every tick, so the number is what the loop can afford to
        # lose rather than what an app deserves to answer in.
        ax.AXUIElementSetMessagingTimeout(element, _FRONT_APP_S)
        err, window = ax.AXUIElementCopyAttributeValue(
            element, ax.kAXFocusedWindowAttribute, None)
        if err or window is None:
            return None, None, None
        err, title = ax.AXUIElementCopyAttributeValue(
            window, ax.kAXTitleAttribute, None)
        if err or not title:
            return None, None, None
        return str(title), self._bundle(pid), None

    def tab_tty(self, app: str, *, timeout: float = 2.0) -> tuple[str | None, str | None]:
        """The tty of the selected tab in `app`'s front window. See `ports.Frontmost`.

        Terminal only, as `Focus.tab` (task 43): its tabs carry no claude's name
        in their title, but each says its tty, and a claude's tty is known. An
        Apple event to another app, so ~0.1 s (measured 2026-09-29) and never on
        the daemon's own loop. The caller checks the app is in front, and the
        app running is checked here, because `tell` would launch one that is not.
        """
        script = _FRONT_TTY_SCRIPTS.get(app)
        if script is None:
            return None, f"no way is known to read {app}'s tab, so its folder decides"
        home = next((running for running in
                     NSWorkspace.sharedWorkspace().runningApplications()
                     if running.bundleIdentifier() == app), None)
        if home is None:
            return None, None
        # Named as `Focus.tab` names it: "Terminal", not "com.apple.Terminal".
        name = str(home.localizedName() or app)
        try:
            out = subprocess.run(["osascript", "-e", script],
                                 capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return None, (f"{name} did not say its tab in {timeout:g}s — a consent dialog "
                          f"may be waiting — so its folder decides")
        except OSError as exc:
            return None, f"osascript could not run ({exc}), so {name}'s folder decides"
        if "-1743" in out.stderr:
            return None, (f"macOS has not let wobble ask {name} which tab is in front, so "
                          f"its folder decides — allow it in System Settings › Privacy & "
                          f"Security › Automation")
        if out.returncode != 0:
            # A front window with no tab (Terminal's Settings) is an answer too.
            return None, None
        tty = out.stdout.strip().removeprefix("/dev/")
        return (tty or None), None

    def _bundle(self, pid: int) -> str | None:
        running = NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
        bundle = running.bundleIdentifier() if running is not None else None
        return str(bundle) if bundle else None

    # Thin, and methods rather than the module functions called inline, for the
    # same reason `Focus` has its pair: a desk check subclasses this and takes
    # one rule away, and a table that does not break when the locked screen
    # stops being checked was never testing the locked screen.
    def _trusted(self, ax) -> bool:
        return _is_trusted(ax)

    def _locked(self, ax) -> bool:
        return _is_locked(ax)

    def _front_pid(self, ax) -> int | None:
        """Who owns the frontmost ordinary window, straight from the window server.

        Layer 0 is where application windows live; the menu bar, the Dock, and
        every floating overlay sit above it and would otherwise be read as the
        thing you are looking at. The list comes back front to back, so the
        first one at layer 0 is the answer and there is nothing to sort.
        """
        windows = ax.CGWindowListCopyWindowInfo(
            ax.kCGWindowListOptionOnScreenOnly
            | ax.kCGWindowListExcludeDesktopElements, ax.kCGNullWindowID) or []
        for window in windows:
            if window.get(ax.kCGWindowLayer, 1) != 0:
                continue
            return int(window.get(ax.kCGWindowOwnerPID, 0)) or None
        return None


class Focus:
    """Bring forward the window whose title carries `hint`.

    Two permissions, and only one of them can be refused. Listing the running
    apps is `NSWorkspace` and always works; reading their window titles and
    raising one is the Accessibility API, which the user grants per application
    and can take away at any time. `AXIsProcessTrusted()` is asked every call
    rather than once at startup, because the answer changes while the process
    runs — revoking it in System Settings takes effect immediately.

    **The refusal is the interesting path, not the error path.** Criterion 10
    asks that a refused permission be said in words while the notification still
    works, so nothing here raises and nothing here returns a bare `False`: every
    way out carries a sentence naming what did not happen and what to do.

    `timeout` is a budget for the whole scan, checked between apps. It is not a
    deadline the OS enforces — `_PER_APP_S` is what keeps any single app from
    running past it — so the worst case is one app's timeout over budget.
    """

    def window(self, hint: str, *, app: str | None = None,
               fits: Callable[[str], bool] | None = None,
               folder: str | None = None,
               timeout: float = 1.5) -> tuple[bool, str | None]:
        if not hint.strip():
            return False, ("this signal carries no window hint, so there was "
                           "nothing to look for")
        ax, why = _ax()
        if ax is None:
            return False, why
        if not self._trusted(ax):
            return False, NOT_TRUSTED
        if self._locked(ax):
            return False, LOCKED

        if fits is None:
            wanted = hint.casefold()

            def fits(title: str) -> bool:
                return wanted in title.casefold()
        deadline = time.monotonic() + timeout
        looked = 0
        home = None
        for running in NSWorkspace.sharedWorkspace().runningApplications():
            # Regular only: agents and accessory apps have no windows to raise,
            # and this daemon is one of them.
            if running.activationPolicy() != NSApplicationActivationPolicyRegular:
                continue
            # Only the session's own app, when it is known (task 38): a terminal
            # merely open in the same folder took the raise from the VS Code
            # window running the session, seen at the desk 2026-09-28.
            if app is not None and running.bundleIdentifier() != app:
                continue
            if time.monotonic() >= deadline:
                return False, (f"gave up looking for a window matching {hint!r} after "
                               f"{timeout:.1f}s and {looked} apps — nothing was raised")
            looked += 1
            home = home or running
            for window, title in self._windows(ax, running.processIdentifier()):
                if fits(title):
                    return self._raise(ax, running, window, title)
        if app is None:
            return False, (f"no window of the {looked} apps on screen has {hint!r} in its "
                           f"title — nothing was raised")
        if home is None:
            return False, (f"the app this session runs in ({app}) is not open — "
                           f"nothing was raised")
        if folder:
            return self._reopen(ax, home, hint, folder, fits)
        return self._bring(ax, home, hint)

    def url(self, url: str, *, app: str,
            timeout: float = 1.5) -> tuple[bool, str | None]:
        """Open `url` through Launch Services and read back who is in front.

        Launch Services and not an Apple event or `activate()`: opening a URL is
        the route macOS treats as a person's own act, and the one measured to
        land (`open warp://session/…` and `open claude://code/continue?…`, both
        2026-09-28). Which tab or session opened is the app's to show; what is
        checked here is only that its app came forward, and the title in front
        is said so a desk reading can tell the rest.
        """
        ax, why = _ax()
        if ax is None:
            return False, why
        if self._locked(ax):
            return False, LOCKED
        home = self._app(app)
        if home is None:
            return False, (f"the app this session runs in ({app}) is not open, so "
                           f"{url} was not opened — nothing came forward")
        address = NSURL.URLWithString_(url)
        if address is None or not NSWorkspace.sharedWorkspace().openURL_(address):
            return False, f"macOS would not open {url} — nothing came forward"
        return self._landed(ax, home, f"opened {url}", timeout)

    def tab(self, tty: str, *, app: str,
            timeout: float = 30.0) -> tuple[bool, str | None]:
        """Select the tab on `tty` in a terminal that names its tabs' ttys.

        Terminal only, the one measured here (`tty of selected tab`, task 38).
        An Apple event to another app costs a one-time Automation consent, and
        until someone answers it `osascript` waits, which is why this runs on
        the raise's worker thread and has a long `timeout`. A refusal is error
        -1743, said with where to change it (principle 7).
        """
        script = _TAB_SCRIPTS.get(app)
        if script is None:
            return False, f"no way is known to pick a tab in {app} — nothing was selected"
        ax, why = _ax()
        if ax is None:
            return False, why
        if self._locked(ax):
            return False, LOCKED
        home = self._app(app)
        if home is None:
            return False, (f"the app this session runs in ({app}) is not open — "
                           f"nothing was selected")
        name = str(home.localizedName() or app)
        try:
            out = subprocess.run(["osascript", "-e", script, f"/dev/{tty}"],
                                 capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return False, (f"{name} did not answer in {timeout:.0f}s — a consent dialog "
                           f"may be waiting on screen. Nothing was selected")
        except OSError as exc:
            return False, f"osascript could not run ({exc}) — nothing was selected"
        if "-1743" in out.stderr:
            return False, (f"macOS has not let wobble control {name}, so its tab was not "
                           f"selected — allow it in System Settings › Privacy & Security "
                           f"› Automation. The notification itself is unaffected.")
        if out.returncode != 0:
            return False, (f"{name} refused to select a tab ({out.stderr.strip()[:200]}) "
                           f"— nothing was selected")
        if out.stdout.strip() != "found":
            return False, f"no tab of {name} is on {tty} — nothing was selected"
        return self._landed(ax, home, f"selected its tab on {tty}", 0.5)

    def _app(self, bundle: str):
        """The running app with this bundle id, or `None`: nothing here launches one."""
        for running in NSWorkspace.sharedWorkspace().runningApplications():
            if running.bundleIdentifier() == bundle:
                return running
        return None

    def _landed(self, ax, home, did: str, wait: float) -> tuple[bool, str | None]:
        """After `did`, is `home` in front? Brought there if not, as `_raise` does."""
        name = str(home.localizedName() or home.bundleIdentifier() or "its app")
        how = "" if self._arrived(ax, home.processIdentifier(), wait) else self._forward(ax, home)
        if how is None:
            return False, (f"{name} {did}, but macOS kept it behind, both ways — "
                           f"nothing came forward")
        title, _ = Frontmost().title()
        return True, f"{name} {did} and came forward{how}" + (f", {title!r} in front"
                                                              if title else "")

    def ask(self) -> tuple[bool, str | None]:
        """Whether Accessibility is ours, and if not, the system's own dialog (task 50).

        `AXIsProcessTrustedWithOptions` with the prompt option shows macOS's
        dialog, filed under whoever is responsible for this process: `wobble`
        when the app started it, the terminal otherwise (task 48, tccd's
        `responsible=local.wobble`). It asks and returns at once; the grant
        lands later, when a person flips the switch, and `_trusted` sees it then.
        """
        ax, _ = _ax()
        if ax is None:
            return False, _CANNOT_ASK.format(why=_AX_MISSING or "it is not available")
        if _is_trusted(ax):
            return True, None
        ax.AXIsProcessTrustedWithOptions({ax.kAXTrustedCheckOptionPrompt: True})
        return False, ("macOS has not granted Accessibility yet, so its own dialog was "
                       "shown — allow wobble in System Settings › Privacy & Security › "
                       "Accessibility. Until then no window is raised, and a signal "
                       "plays even while you look at its session.")

    def _trusted(self, ax) -> bool:
        """Whether Accessibility is ours, asked fresh every single call.

        Not cached, because the answer changes under a running process: taking
        the permission away in System Settings takes effect at once, and a
        daemon that asked once at startup would go on believing it had a
        permission it lost hours ago.
        """
        return _is_trusted(ax)

    def _locked(self, ax) -> bool:
        """Whether the login session is locked, which is the normal case here.

        Found the first time this ran while nobody was at the desk, and it is
        not an edge case for a notifier — the screen being locked is exactly the
        state you are in when a notification matters. macOS answers every window
        title as the name of its own app while locked, so `Code`'s three windows
        all come back as `'Code'` and a search for a project reports, perfectly
        truthfully and completely uselessly, that no window matched.

        `CGSessionCopyCurrentDictionary` is in the same framework as the rest of
        this, not a new dependency, and it answers `None` in a session with no
        window server at all — which is not a locked screen, so it reads False.
        """
        return _is_locked(ax)

    def _windows(self, ax, pid: int):
        """Every window of `pid` that will tell us its title.

        An app can refuse any single question — a window mid-close, a sheet, an
        app that answers the list but not the titles. Those come back as AX error
        codes, never exceptions, and the only sane thing is to skip that window
        and keep going: one unreadable title is not a reason to stop looking.
        """
        element = ax.AXUIElementCreateApplication(pid)
        ax.AXUIElementSetMessagingTimeout(element, _PER_APP_S)
        err, windows = ax.AXUIElementCopyAttributeValue(
            element, ax.kAXWindowsAttribute, None)
        if err or not windows:
            return
        for window in windows:
            err, title = ax.AXUIElementCopyAttributeValue(
                window, ax.kAXTitleAttribute, None)
            if err or not title:
                continue
            yield window, str(title)

    def _raise(self, ax, running, window, title: str) -> tuple[bool, str | None]:
        """Two acts, and they are both needed.

        `kAXRaiseAction` puts the window in front of its own app's other
        windows; activating puts that app in front of every other app. Doing
        only one of them is the failure that looks like success — the right app
        comes forward showing the wrong window, or the right window rises behind
        whatever you were already looking at.
        """
        ax.AXUIElementSetAttributeValue(window, ax.kAXMainAttribute, True)
        raised = ax.AXUIElementPerformAction(window, ax.kAXRaiseAction)
        # Deprecated since macOS 14 in favour of `activate()`, which this PyObjC
        # does not expose on `NSRunningApplication` at all — asking for it raises
        # `AttributeError`. So the deprecated call is not a fallback here, it is
        # the only one there is, and it works: measured bringing another app
        # forward from this process, which has no activation policy of its own.
        how = self._forward(ax, running)
        if raised:
            return False, (f"found {title!r} but macOS refused to raise it "
                           f"(AX error {raised}) — nothing came forward")
        if how is None:
            return False, (f"raised {title!r} inside its own app, but macOS refused to "
                           f"bring that app forward, both ways — it is in front of its "
                           f"siblings and behind everything else")
        return True, f"{title!r} came forward{how}"

    def _bring(self, ax, running, hint: str) -> tuple[bool, str | None]:
        """The session's app itself, when none of its windows names the project.

        The Claude desktop app is the case this is for: its title is not
        expected to carry a folder (task 38, not measured yet), and the app
        coming forward is the most that can honestly be done. Said as such, so
        a desk reading can tell it apart from finding the window.
        """
        name = str(running.localizedName() or running.bundleIdentifier() or "its app")
        how = self._forward(ax, running)
        if how is None:
            return False, (f"no window of {name} names {hint!r}, and macOS refused "
                           f"to bring {name} forward, both ways — nothing came forward")
        return True, (f"{name} came forward as it was{how} — none of its windows "
                      f"names {hint!r}")

    # How long a desktop switch may take to put the folder's window in front.
    # Measured 2026-10-01: in front within 2 s; the switch itself is not timed.
    REOPEN_S = 2.0

    def _reopen(self, ax, running, hint: str, folder: str,
                fits: Callable[[str], bool]) -> tuple[bool, str | None]:
        """Open the session's folder in its app, when no window here names it (task 69).

        Accessibility lists only the windows on the current desktop, so a window
        on another one reads as no window at all, and B brought the app forward
        as it was. Measured 2026-10-01, 14:49: `open -a "Visual Studio Code"
        ~/dev/<a workspace>` from desktop 2 switched to desktop 1 and put
        that folder's window in front. `open -b` is the same Launch Services
        call by bundle id, so a renamed app still answers. Asked only for VS Code
        (`daemon.reach`): a folder it already has open is that window.
        """
        name = str(running.localizedName() or running.bundleIdentifier() or "its app")
        try:
            out = subprocess.run(["open", "-b", str(running.bundleIdentifier()), folder],
                                 capture_output=True, text=True, timeout=5)
        except subprocess.TimeoutExpired:
            ok, why = self._bring(ax, running, hint)
            return ok, f"open did not answer in 5s for {folder}, so {why}"
        if out.returncode:
            ok, why = self._bring(ax, running, hint)
            return ok, (f"open would not take {folder} ({out.stderr.strip() or out.returncode}),"
                        f" so {why}")
        deadline = time.monotonic() + self.REOPEN_S
        while True:
            title, _ = Frontmost().title()
            if (title and fits(title)) or time.monotonic() >= deadline:
                break
            time.sleep(0.05)
        if title and fits(title):
            return True, (f"no window of {name} on this desktop names {hint!r}, so "
                          f"{folder} was opened in it and {title!r} came forward")
        return True, (f"no window of {name} on this desktop names {hint!r}, so {folder} "
                      f"was opened in it, but after {self.REOPEN_S:g}s "
                      f"{title or 'nothing readable'!r} was in front")

    def _forward(self, ax, running) -> str | None:
        """Put `running` in front of every other app: how it got there, or `None`.

        Activation first, as before, and then Accessibility's own "frontmost"
        on the app element when that is refused — the permission the raise
        already holds. The refusal is real and it is the daemon's: seen twice at
        the desk 2026-09-28 (task 38), Warp's window raised and Warp left behind
        VS Code, while the very same calls from a fresh process brought Warp
        forward every time. macOS 14's cooperative activation lets the system
        decline a request from an app that is not active, which this daemon
        never is.

        Each way is read back from the window server rather than trusted: the
        return value is the thing that was in question.
        """
        pid = running.processIdentifier()
        if (running.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
                and self._arrived(ax, pid)):
            return ""
        element = ax.AXUIElementCreateApplication(pid)
        if (not ax.AXUIElementSetAttributeValue(element, ax.kAXFrontmostAttribute, True)
                and self._arrived(ax, pid)):
            return " via Accessibility"
        return None

    def _arrived(self, ax, pid: int, wait: float = 0.5) -> bool:
        """Whether `pid` owns the front window within `wait` seconds.

        Activation lands a moment after the call returns, so one read straight
        away would call a success a refusal. Polled briefly on the worker
        thread `Focus` already runs on, never on the daemon's loop.
        """
        deadline = time.monotonic() + wait
        while True:
            if Frontmost()._front_pid(ax) == pid:
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.05)


# `sysctl(CTL_KERN, KERN_PROC, KERN_PROC_PID, pid)` fills one `struct kinfo_proc`
# (648 bytes on arm64), and `kp_proc.p_starttime` — a `timeval` — is its first
# field. `sys/sysctl.h` and `sys/proc.h`; checked 2026-09-28 against `ps -o
# lstart` for five live claudes, and a pid with no process fills zero bytes.
_CTL_KERN, _KERN_PROC, _KERN_PROC_PID = 1, 14, 1
_KINFO_PROC_SIZE = 648

# `proc_pidinfo(pid, PROC_PIDTBSDINFO, …)` fills one `struct proc_bsdinfo` (136
# bytes), whose `e_tdev` is at 108 and reads `NODEV` with no terminal
# (`sys/proc_info.h`). Checked 2026-09-28 against `ps -o tty=` for six live
# claudes: Warp's read `ttys000` both ways, the five others none (task 42).
_PROC_PIDTBSDINFO, _BSDINFO_SIZE, _E_TDEV = 3, 136, 108
_NODEV, _S_IFCHR, _ESRCH = 0xFFFFFFFF, 0o020000, 3

# `proc_listchildpids(pid, buf, size)` answers a COUNT of pids, not bytes, and
# 0 for a pid that is gone; `sysctl(CTL_KERN, KERN_PROCARGS2, pid)` fills `int
# argc`, the exec path, NUL padding, then argc NUL-ended strings, and fails
# EINVAL alike for a gone pid and another user's. Measured 2026-09-30 on a
# claude's three children (task 65). `kern.argmax` bounds the second, 1 MiB here.
_KERN_PROCARGS2, _CHILDREN_MAX = 49, 256

# How to read the tty of the tab in front, per terminal (task 43). Nothing to
# splice in, and an empty answer when there is no window.
_FRONT_TTY_SCRIPTS = {
    "com.apple.Terminal": """
tell application id "com.apple.Terminal"
    if (count windows) is 0 then return ""
    return tty of selected tab of front window
end tell
""",
}

# How to pick a tab by its tty, per terminal, run with the tty as `argv`: never
# spliced into the text. `id` rather than a name, and the caller checks the app
# runs first, because `tell` would launch one that does not.
_TAB_SCRIPTS = {
    "com.apple.Terminal": """
on run argv
    tell application id "com.apple.Terminal"
        repeat with w in windows
            repeat with t in tabs of w
                if tty of t is (item 1 of argv) then
                    set selected of t to true
                    set index of w to 1
                    return "found"
                end if
            end repeat
        end repeat
    end tell
    return "none"
end run
""",
}


class Process:
    """Whether a pid runs, and since when — one `sysctl`, no subprocess. And
    which terminal it is on, one `proc_pidinfo` (task 42). And what it started,
    and with which command line, one call each (task 65).

    Asked every few seconds for each waiting session, so a `ps` per ask would
    be a process spawned four times a minute per session for a fact the kernel
    hands over in one call.
    """

    def __init__(self) -> None:
        self._libc = None
        self._proc = None
        self._args = None

    def _load(self) -> None:
        """libc and libproc, with the argument types of what is called on them."""
        if self._libc is None:
            self._libc = ctypes.CDLL(None, use_errno=True)
        if self._proc is None:
            proc = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
            proc.proc_pidinfo.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64,
                                          ctypes.c_void_p, ctypes.c_int]
            proc.proc_listchildpids.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_int]
            self._libc.devname.argtypes = [ctypes.c_uint32, ctypes.c_uint16]
            self._libc.devname.restype = ctypes.c_char_p
            self._proc = proc

    def started(self, pid: int) -> tuple[float | None, str | None]:
        try:
            if self._libc is None:
                self._libc = ctypes.CDLL(None, use_errno=True)
            mib = (ctypes.c_int * 4)(_CTL_KERN, _KERN_PROC, _KERN_PROC_PID, int(pid))
            buf = ctypes.create_string_buffer(_KINFO_PROC_SIZE)
            size = ctypes.c_size_t(_KINFO_PROC_SIZE)
            if self._libc.sysctl(mib, 4, buf, ctypes.byref(size), None, 0) != 0:
                return None, (f"sysctl could not read pid {pid} (errno "
                              f"{ctypes.get_errno()}), so whether it still runs is unknown")
        except (OSError, AttributeError, ValueError) as exc:
            return None, f"sysctl is out of reach ({exc}), so whether pid {pid} runs is unknown"
        if size.value == 0:
            return None, None
        sec, usec = struct.unpack_from("<qi", buf.raw, 0)
        return sec + usec / 1e6, None

    def tty(self, pid: int) -> tuple[str | None, str | None]:
        try:
            self._load()
            buf = ctypes.create_string_buffer(_BSDINFO_SIZE)
            filled = self._proc.proc_pidinfo(int(pid), _PROC_PIDTBSDINFO, 0, buf, _BSDINFO_SIZE)
        except (OSError, AttributeError, ValueError) as exc:
            return None, f"libproc is out of reach ({exc}), so pid {pid}'s terminal is unknown"
        if filled <= 0:
            errno = ctypes.get_errno()
            if errno == _ESRCH:
                return None, None
            return None, (f"proc_pidinfo could not read pid {pid} (errno {errno}), "
                          f"so its terminal is unknown")
        tdev, = struct.unpack_from("<I", buf.raw, _E_TDEV)
        if tdev == _NODEV:
            return None, None
        name = self._libc.devname(tdev, _S_IFCHR)
        if not name:
            return None, f"pid {pid}'s terminal (device {tdev:#x}) has no name in /dev"
        return name.decode(), None

    def children(self, pid: int) -> tuple[tuple[int, ...] | None, str | None]:
        """One `proc_listchildpids` (task 65): asked once a second while a
        permission question waits, so no `ps` here either."""
        try:
            self._load()
            buf = (ctypes.c_int * _CHILDREN_MAX)()
            count = self._proc.proc_listchildpids(int(pid), buf, ctypes.sizeof(buf))
        except (OSError, AttributeError, ValueError) as exc:
            return None, f"libproc is out of reach ({exc}), so what pid {pid} started is unknown"
        if count < 0:
            return None, (f"proc_listchildpids could not read pid {pid} (errno "
                          f"{ctypes.get_errno()}), so what it started is unknown")
        return tuple(buf[i] for i in range(min(count, _CHILDREN_MAX)) if buf[i] > 0), None

    def command(self, pid: int) -> tuple[tuple[str, ...] | None, str | None]:
        try:
            self._load()
            if self._args is None:
                most, size = ctypes.c_int(), ctypes.c_size_t(4)
                if self._libc.sysctlbyname(b"kern.argmax", ctypes.byref(most),
                                           ctypes.byref(size), None, 0) != 0:
                    return None, (f"kern.argmax is unreadable (errno {ctypes.get_errno()}), "
                                  f"so pid {pid}'s command line is unknown")
                self._args = ctypes.create_string_buffer(most.value)
            mib = (ctypes.c_int * 3)(_CTL_KERN, _KERN_PROCARGS2, int(pid))
            size = ctypes.c_size_t(len(self._args))
            failed = self._libc.sysctl(mib, 3, self._args, ctypes.byref(size), None, 0) != 0
        except (OSError, AttributeError, ValueError) as exc:
            return None, f"sysctl is out of reach ({exc}), so pid {pid}'s command line is unknown"
        if failed:
            errno = ctypes.get_errno()
            started, blind = self.started(pid)
            if started is None and blind is None:
                return None, None
            return None, (f"sysctl could not read pid {pid}'s arguments (errno {errno}), "
                          f"so its command line is unknown")
        raw = self._args.raw[:size.value]
        if len(raw) < 4:
            return None, f"pid {pid}'s arguments came back {len(raw)} bytes long, so unreadable"
        argc, = struct.unpack_from("<i", raw, 0)
        _, _, rest = raw[4:].partition(b"\0")
        args = rest.lstrip(b"\0").split(b"\0")[:max(argc, 0)]
        return tuple(arg.decode(errors="replace") for arg in args), None

    def title(self, pid: int, text: str) -> tuple[bool, str | None]:
        """One OSC 2 written to the pid's tty, as if it had printed it (task 43).

        Measured 2026-09-28: Warp took `myproject · d711` from outside and its
        window title followed 0.3 s later, with the claude's screen left clean.
        The text is refused if it holds a control character, since those are
        how a terminal is told to do anything else; the tty must be this
        user's; and the write does not block, so a terminal that stopped
        reading cannot stall the loop. One `write`, so it is not split up
        among the claude's own output.
        """
        if any(ord(c) < 0x20 or 0x7F <= ord(c) < 0xA0 for c in text):
            return False, f"{text!r} holds a control character, so no tab was named"
        tty, blind = self.tty(pid)
        if tty is None:
            return False, blind or f"pid {pid} is on no terminal, so no tab was named"
        path = f"/dev/{tty}"
        try:
            fd = os.open(path, os.O_WRONLY | os.O_NOCTTY | os.O_NONBLOCK)
        except OSError as exc:
            return False, f"{path} would not open ({exc.strerror}), so no tab was named"
        try:
            if os.fstat(fd).st_uid != os.getuid():
                return False, f"{path} is not this user's, so no tab was named"
            data = f"\033]2;{text}\007".encode()
            wrote = os.write(fd, data)
        except OSError as exc:
            return False, f"{path} refused the write ({exc.strerror}), so no tab was named"
        finally:
            os.close(fd)
        if wrote != len(data):
            return False, f"{path} took {wrote} of {len(data)} bytes, so the tab may be unnamed"
        return True, f"named {tty}'s tab {text!r}"


class Idle:
    """Seconds since any key, click or mouse move, from the HID system state.

    `kCGAnyInputEventType` in one call, rather than keys and the mouse read
    apart: any input is what resets the count here. Needs no permission — measured 2026-09-30 from
    the venv, 0.08 s with the desk in use. Imported lazily, like `_AX`.
    """

    def seconds(self) -> tuple[float | None, str | None]:
        try:
            from Quartz import (CGEventSourceSecondsSinceLastEventType,
                                kCGAnyInputEventType, kCGEventSourceStateHIDSystemState)
            return float(CGEventSourceSecondsSinceLastEventType(
                kCGEventSourceStateHIDSystemState, kCGAnyInputEventType)), None
        except Exception as exc:          # a seam fault must not stop the loop
            return None, f"the HID idle time is out of reach ({exc!r})"


class _Clicks(NSObject):
    """The target half of a target/action pair.

    AppKit will only send an action to an Objective-C object, and a Python
    function is not one, so the click lands here and is handed on. Whoever holds
    an instance must keep holding it: a control's `target` is an unretained
    reference, so letting this be collected leaves AppKit sending to a pointer
    that is no longer there.
    """

    # Named for what they do, not for which gesture reaches them: which is
    # which changed once already (task 21), and a field called `secondary`
    # would have gone on saying the old arrangement while doing the new one.
    press = None
    open_menu = None

    def clicked_(self, _sender) -> None:
        """One action, two gestures, told apart by the event AppKit is holding.

        **Left opens the menu, right presses B — swapped at task 21**, when the
        menu grew the pending list and became something worth opening. Three
        reasons, and the third is the one that was paid for:

        - the left click is what every other item on the strip answers with a
          menu, and an item that does something else on the gesture people
          already use is a trap rather than a shortcut;
        - the menu now goes everywhere the press goes and further — the list
          picks a project, where B only ever takes the top of the queue;
        - a stray click on this item has already been a real B press once, and
          it broke a desk check mid-run (`specs/01-mvp/learnings.md`,
          2026-09-22 — `--no-menubar` exists because of it). An unwanted menu
          is dismissed with Escape and costs nothing; an unwanted press attends
          a signal and cannot be undone, so the recoverable thing belongs on
          the gesture that happens by accident.

        A control-click is a right click: it is the same intent from a
        one-button mouse or a trackpad. `currentEvent` is the event being
        delivered right now, which is the only place the distinction exists —
        the action itself is the same selector either way.
        """
        event = NSApplication.sharedApplication().currentEvent()
        right = event is not None and (
            event.type() == NSEventTypeRightMouseUp
            or bool(event.modifierFlags() & NSEventModifierFlagControl))
        if right and self.press is not None:
            self.press()
        elif not right and self.open_menu is not None:
            self.open_menu()


class _MenuClicks(NSObject):
    """The same target/action trick for the items inside the menu.

    One object for the whole menu rather than one per item, with the item's
    `tag` as the index into a list. The list is replaced wholesale every time
    the menu is rebuilt, so a handler can never outlive the item that named it.
    """

    handlers = None

    def chose_(self, sender) -> None:
        handler = (self.handlers or [])[sender.tag()]
        if handler is not None:
            handler()


# --- the ball, drawn (task 58) -----------------------------------------------
# Drawn in code and never traced from anything: no game asset is ever in
# this repo (CLAUDE.md). The proportions are
# a CHOICE made on a contact sheet at 18 pt, light and dark, 2026-09-30.

_MENU_PT = 18


def _colour(hex_: str):
    r, g, b = (int(hex_[n:n + 2], 16) / 255 for n in (1, 3, 5))
    return NSColor.colorWithSRGBRed_green_blue_alpha_(r, g, b, 1.0)


def _disc(cx: float, cy: float, r: float):
    return NSBezierPath.bezierPathWithOvalInRect_(NSMakeRect(cx - r, cy - r, 2 * r, 2 * r))


def _top_half(cx: float, cy: float, r: float):
    path = NSBezierPath.bezierPath()
    path.moveToPoint_(NSMakePoint(cx - r, cy))
    # Clockwise from 180 to 0 is over the top: y points up in AppKit.
    path.appendBezierPathWithArcWithCenter_radius_startAngle_endAngle_clockwise_(
        NSMakePoint(cx, cy), r, 180, 0, True)
    path.closePath()
    return path


def draw_ball(ball, size: float, ink, paper=None, *, top=None, bottom=None) -> None:
    """The ball into the current graphics context, `size` wide from the origin.

    `ink` draws the outline, the band and a connected ball's top half; `paper`
    is the body behind them, or `None` to leave it clear so the menu bar shows
    through. A light is the centre only, where the real ball's button ring
    lights (task 60), and here it is still: the menu bar moves it in layers.

    `top` colours the top half in place of `ink`, filled from the band up to
    the battery left, so it empties from the top down; `bottom` fills a
    connected ball's lower half, or leaves it clear when `None` (task 63).
    """
    c, r = size / 2, size * 0.42
    line = max(size * 0.075, 1.0)
    button = size * 0.14
    if paper is not None:
        paper.setFill()
        _disc(c, c, r).fill()
    if ball.connected:
        if bottom is not None:
            NSGraphicsContext.saveGraphicsState()
            _disc(c, c, r).addClip()
            bottom.setFill()
            NSBezierPath.fillRect_(NSMakeRect(0, 0, size, c))
            NSGraphicsContext.restoreGraphicsState()
        level = 1.0 if ball.battery is None else min(max(ball.battery, 0), 100) / 100
        (top or ink).setFill()
        if level == 1.0:
            _top_half(c, c, r).fill()
        else:
            NSGraphicsContext.saveGraphicsState()
            _top_half(c, c, r).addClip()
            NSBezierPath.fillRect_(NSMakeRect(0, c, size, r * level))
            NSGraphicsContext.restoreGraphicsState()
    ink.setStroke()
    outline = _disc(c, c, r)
    band = NSBezierPath.bezierPath()
    band.moveToPoint_(NSMakePoint(c - r, c))
    band.lineToPoint_(NSMakePoint(c + r, c))
    for path in (outline, band):
        path.setLineWidth_(line)
        path.stroke()
    # The button cuts through the band and the top half: with no paper behind
    # it that is a hole, cleared rather than painted over.
    context = NSGraphicsContext.currentContext()
    if paper is None:
        context.setCompositingOperation_(NSCompositingOperationClear)
        _disc(c, c, button + line).fill()
        context.setCompositingOperation_(NSCompositingOperationSourceOver)
    else:
        paper.setFill()
        _disc(c, c, button + line).fill()
    lit = ball.pulse or ball.centre
    if lit is not None:
        _colour(lit).setFill()
        _disc(c, c, button).fill()
    ring = _disc(c, c, button)
    ring.setLineWidth_(line)
    ring.stroke()


# The mute mark beside the ball (task 61): an SF Symbol drawn at run time, never
# saved into the repo. Its size and gap are CHOICES, 12 x 14 pt at 11.
_MARK_PT, _MARK_GAP = 11, 2

# The menu ball's own colours (task 63), all CHOICES made on mockups at 18 pt,
# 2026-09-30: the top half's red, the bottom's black share on a light bar
# (white is lost on it), and how much of the ball is left when it is off.
_MENU_RED = "#E3352D"
_LIGHT_BOTTOM, _OFF_ALPHA = 0.18, 0.35


def _menu_bottom():
    """The bottom half's fill for the bar it is being drawn on: white on a dark one."""
    name = NSAppearance.currentDrawingAppearance().bestMatchFromAppearancesWithNames_(
        [NSAppearanceNameAqua, NSAppearanceNameDarkAqua])
    if name == NSAppearanceNameDarkAqua:
        return NSColor.whiteColor()
    return NSColor.blackColor().colorWithAlphaComponent_(_LIGHT_BOTTOM)


def _mute_mark():
    """`speaker.slash.fill` at the menu's size, or `None` where this macOS has none."""
    symbol = NSImage.imageWithSystemSymbolName_accessibilityDescription_(
        "speaker.slash.fill", "muted")
    if symbol is None:
        return None
    return symbol.imageWithSymbolConfiguration_(
        NSImageSymbolConfiguration.configurationWithPointSize_weight_(
            _MARK_PT, NSFontWeightRegular))


def _menu_ball(ball):
    """An 18 pt image that draws itself in the menu bar's own ink.

    Drawn on demand rather than once, so `labelColor` is read at draw time and
    the ball follows the menu bar from light to dark without being asked. A
    muted ball is wider: the mark sits to its right. A ball that is `off` is
    drawn into a layer of its own and faded as one, so the button's hole is
    still cleared inside it; the mark is not faded (task 63).
    """
    mark = _mute_mark() if ball.muted else None
    width = _MENU_PT if mark is None else _MENU_PT + _MARK_GAP + mark.size().width

    def paint(rect) -> bool:
        NSGraphicsContext.saveGraphicsState()
        cg = NSGraphicsContext.currentContext().CGContext()
        CGContextSetAlpha(cg, _OFF_ALPHA if ball.off else 1.0)
        CGContextBeginTransparencyLayer(cg, None)
        draw_ball(ball, _MENU_PT, NSColor.labelColor(),
                  top=_colour(_MENU_RED), bottom=_menu_bottom())
        CGContextEndTransparencyLayer(cg)
        NSGraphicsContext.restoreGraphicsState()
        if mark is not None:
            size = mark.size()
            box = NSMakeRect(_MENU_PT + _MARK_GAP, (_MENU_PT - size.height) / 2,
                             size.width, size.height)
            mark.drawInRect_(box)
            # A symbol is a template: filled over its own pixels, it takes the ink.
            NSColor.labelColor().set()
            NSRectFillUsingOperation(box, NSCompositingOperationSourceAtop)
        return True
    image = NSImage.imageWithSize_flipped_drawingHandler_(
        NSMakeSize(width, _MENU_PT), False, paint)
    image.setTemplate_(False)            # it has colours, so it is not a template
    return image


def _light_path(rect):
    """The centre of an 18 pt ball drawn at the left of `rect`: inside its ring, as `draw_ball` fills it."""
    line = max(_MENU_PT * 0.075, 1.0)
    r = _MENU_PT * 0.14 - line / 2
    x = rect.origin.x + _MENU_PT / 2           # the ball's middle, not the image's: a mark widens it
    y = rect.origin.y + rect.size.height / 2
    return CGPathCreateWithEllipseInRect(CGRectMake(x - r, y - r, 2 * r, 2 * r), None)


def _breathing(hold: float, fall: float, rise: float):
    """Full for `hold`, down to dark over `fall`, back up over `rise`, for ever."""
    period = hold + fall + rise
    breath = CAKeyframeAnimation.animationWithKeyPath_("opacity")
    breath.setValues_([1.0, 1.0, 0.0, 1.0])
    breath.setKeyTimes_([0.0, hold / period, (hold + fall) / period, 1.0])
    breath.setDuration_(period)
    breath.setRepeatCount_(float("inf"))
    return breath


# How much of a flash is at full before it fades out — a CHOICE: the ball's
# beats were never filmed closely enough to give them a shape (task 60).
_FLASH_HOLD = 0.6


def _flashing(seconds: float):
    """Full at once, held, then faded out: the layer's own opacity is 0 after."""
    flash = CAKeyframeAnimation.animationWithKeyPath_("opacity")
    flash.setValues_([1.0, 1.0, 0.0])
    flash.setKeyTimes_([0.0, _FLASH_HOLD, 1.0])
    flash.setDuration_(seconds)
    return flash


# macOS 26 sets an app icon on a grey plate unless it is opaque across the
# system's icon shape: task 59's ball alone is plated, and so is a body with the
# button's hole cleared through it; a full square passes, and so does a solid
# body on Apple's app icon grid — 824 of 1024 wide, 100 in, corners of 185.4.
# Measured on probe bundles through NSWorkspace.iconForFile, 2026-09-30 (task 62).
# The corner is drawn continuous, the system's own curve; circular passed too.
_ICON_INSET, _ICON_CORNER = 100 / 1024, 185.4 / 1024
# The ball's width as a share of the body's — a CHOICE, on a sheet at 256 px.
_ICON_BALL = 0.8


def _icon_body(pixels: int, paper) -> None:
    """The icon's body, drawn by Core Animation: its continuous corner is not AppKit's."""
    inset = pixels * _ICON_INSET
    body = CALayer.layer()
    body.setFrame_(CGRectMake(inset, inset, pixels - 2 * inset, pixels - 2 * inset))
    body.setCornerRadius_(pixels * _ICON_CORNER)
    body.setCornerCurve_("continuous")
    body.setBackgroundColor_(paper.CGColor())
    root = CALayer.layer()
    root.setFrame_(CGRectMake(0, 0, pixels, pixels))
    root.addSublayer_(body)
    root.renderInContext_(NSGraphicsContext.currentContext().CGContext())


def ball_png(ball, pixels: int, path: str, *, ink: str,
             paper: str | None = None) -> tuple[bool, str | None]:
    """The ball as a square PNG, `pixels` wide — the app icon's source (task 59).

    Fixed colours rather than the menu bar's: an icon is drawn once, in a
    build, and has no appearance to follow. With `paper` the ball sits on a
    body of that colour in the system's icon shape (task 62); without, alone.
    """
    rep = NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, pixels, pixels, 8, 4, True, False, NSDeviceRGBColorSpace, 0, 0)
    NSGraphicsContext.saveGraphicsState()
    try:
        NSGraphicsContext.setCurrentContext_(
            NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep))
        if paper is None:
            draw_ball(ball, pixels, _colour(ink))
        else:
            _icon_body(pixels, _colour(paper))
            size = pixels * (1 - 2 * _ICON_INSET) * _ICON_BALL
            shift = NSAffineTransform.transform()
            shift.translateXBy_yBy_((pixels - size) / 2, (pixels - size) / 2)
            shift.concat()
            draw_ball(ball, size, _colour(ink), _colour(paper))
    finally:
        NSGraphicsContext.restoreGraphicsState()
    data = rep.representationUsingType_properties_(NSBitmapImageFileTypePNG, {})
    if data is None or not data.writeToFile_atomically_(path, True):
        return False, f"could not write the ball to {path}"
    return True, None


class Status:
    """The menu bar item — created here, held here, handed out never.

    `ports.py` says why: an `NSStatusItem` living in `mirrors/menubar.py` would
    be an OS object outside the seam, and CLAUDE.md puts every one of those in
    this package. The mirror passes a string in and gets clicks back out; it
    never learns that a status item is a thing.
    """

    def __init__(self) -> None:
        self._app = None
        self._item = None
        self._clicks = None
        self._menu_clicks = None
        self._menu = None
        # One image per ball ever asked for — a handful: two halves, and a few
        # tints and pulses when the light cannot move — so none is drawn twice.
        self._balls: dict = {}
        # The centre's two lights (task 60), the held one under the flash, and
        # what each was last set to, so a flash does not restart the breath.
        self._lights = None
        self._held = self._flashed = None

    def _ensure(self) -> None:
        if self._item is not None:
            return
        self._app = NSApplication.sharedApplication()
        # Accessory: a menu bar item, no Dock icon, no main window. The daemon is
        # something that runs, not something you switch to.
        self._app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
        self._item = NSStatusBar.systemStatusBar().statusItemWithLength_(
            NSVariableStatusItemLength)
        # Held for the life of this object, deliberately — see `_Clicks`.
        self._clicks = _Clicks.alloc().init()
        self._clicks.press = None
        self._menu_clicks = _MenuClicks.alloc().init()
        self._menu_clicks.handlers = []
        button = self._item.button()
        button.setTarget_(self._clicks)
        button.setAction_("clicked:")
        # Without this the action fires on left mouse up only, and the right
        # click never reaches `clicked:` at all — which is the B button since
        # task 21. `setMenu_` is the other way to get a menu onto a status item
        # and is deliberately not used: it hands the click to AppKit before this
        # object sees it, and telling the two gestures apart is the whole job.
        button.sendActionOn_(NSEventMaskLeftMouseUp | NSEventMaskRightMouseUp)
        self._clicks.open_menu = self._popup

    def show(self, title: str) -> None:
        self._ensure()
        self._item.button().setTitle_(title)

    def icon(self, ball) -> tuple[bool, str | None]:
        """The shell as an image, and the centre's light as two layers over it.

        The layers are what let the light move while this process sleeps
        between ticks: Core Animation runs an animation once it is handed
        over, so the breath is as smooth at four refreshes a second as at
        sixty. If they cannot be made the light is drawn into the image
        instead, still, and why is said. A mute with no mark to draw it (task
        61) is said too, and answered as not drawn, so the title keeps its word.
        """
        self._ensure()
        marked = ball.muted and _mute_mark() is not None
        try:
            button = self._item.button()
            self._image(button, BallIcon(ball.connected, muted=marked,
                                         battery=ball.battery, off=ball.off))
        except Exception as exc:             # a drawing fault must not end the loop
            return False, f"could not draw the ball in the menu bar ({type(exc).__name__}: {exc})"
        why = None
        try:
            self._light(button, ball)
        except Exception as exc:
            try:
                self._image(button, BallIcon(ball.connected, ball.centre, ball.pulse,
                                             muted=marked, battery=ball.battery,
                                             off=ball.off))
            except Exception:
                pass
            why = (f"could not light the ball's centre in the menu bar "
                   f"({type(exc).__name__}: {exc}), so its light is drawn still")
        if ball.muted and not marked:
            unmarked = ("could not draw the mute mark beside the ball in the menu bar "
                        "(no speaker.slash.fill on this macOS)")
            return False, unmarked if why is None else f"{unmarked}; {why}"
        return True, why

    def _image(self, button, ball) -> None:
        image = self._balls.get(ball)
        if image is None:
            image = self._balls[ball] = _menu_ball(ball)
        button.setImage_(image)
        button.setImagePosition_(NSImageLeft)

    def _light(self, button, ball) -> None:
        if self._lights is None:
            button.setWantsLayer_(True)
            self._lights = (CAShapeLayer.layer(), CAShapeLayer.layer())
            for layer in self._lights:
                layer.setOpacity_(0.0)
                button.layer().addSublayer_(layer)
        held, flash = self._lights
        window = button.window()
        scale = window.backingScaleFactor() if window is not None else 2.0
        path = _light_path(button.cell().imageRectForBounds_(button.bounds()))
        CATransaction.begin()
        CATransaction.setDisableActions_(True)   # no implicit fades: only ours
        try:
            for layer in self._lights:
                layer.setPath_(path)
                layer.setContentsScale_(scale)
            if (ball.centre, ball.breath) != self._held:
                self._held = (ball.centre, ball.breath)
                held.removeAllAnimations()
                if ball.centre is not None:
                    held.setFillColor_(_colour(ball.centre).CGColor())
                    if ball.breath is not None:
                        held.addAnimation_forKey_(_breathing(*ball.breath), "breath")
                held.setOpacity_(0.0 if ball.centre is None else 1.0)
            if (ball.pulse, ball.beat) != self._flashed:
                self._flashed = (ball.pulse, ball.beat)
                flash.removeAllAnimations()
                flash.setOpacity_(0.0)
                if ball.pulse is not None:
                    flash.setFillColor_(_colour(ball.pulse).CGColor())
                    flash.addAnimation_forKey_(_flashing(ball.pulse_s), "flash")
        finally:
            CATransaction.commit()

    def on_click(self, handler: Callable[[], None]) -> None:
        self._ensure()
        self._clicks.press = handler

    def menu(self, items: list[tuple[str | None, Callable[[], None] | None]]) -> None:
        """Rebuild the menu from scratch.

        Built here and never shown here: an `NSMenu` handed out would be an OS
        object outside the seam, and rebuilding rather than editing is what
        makes the mirror's list the only copy of what the menu says.

        An item with no handler is disabled — `setEnabled_(False)` rather than
        omitted, because some of these lines exist to be read (which ball, how
        much battery) and a greyed line reads as information while a missing one
        reads as nothing at all.

        A `None` label is a separator (`menubar.SEPARATOR`). It still takes a
        place in `handlers`, because the tag carried by every other item is its
        index in the list the mirror handed over — a separator skipped there
        would shift every handler below it onto the wrong line, which is the
        kind of defect that only shows up as the wrong thing happening.

        An `Alternate` label is the line above it while ⌥ is held (task 68):
        AppKit swaps two adjacent items whose key equivalents match and whose
        modifier masks differ, so both get the empty key and the line above
        loses the ⌘ mask `addItemWithTitle` gives it.
        """
        self._ensure()
        menu = NSMenu.alloc().init()
        # Off, or every rebuild would fight AppKit over which items are usable:
        # with automatic enabling on, an item with no validated target is greyed
        # whatever `setEnabled_` was told.
        menu.setAutoenablesItems_(False)
        handlers = []
        for index, (label, handler) in enumerate(items):
            if label is None:
                menu.addItem_(NSMenuItem.separatorItem())
                handlers.append(None)
                continue
            item = menu.addItemWithTitle_action_keyEquivalent_(label, "chose:", "")
            item.setTarget_(self._menu_clicks)
            item.setTag_(index)
            item.setEnabled_(handler is not None)
            if isinstance(label, Alternate) and index > 0:
                menu.itemAtIndex_(menu.numberOfItems() - 2).setKeyEquivalentModifierMask_(0)
                item.setKeyEquivalentModifierMask_(NSEventModifierFlagOption)
                item.setAlternate_(True)
            handlers.append(handler)
        self._menu_clicks.handlers = handlers
        self._menu = menu

    def _popup(self) -> None:
        """Open the menu under the item. Blocks until it is dismissed.

        `ports.py` says why that is accepted. `popUpMenuPositioningItem_` with
        no item positions the menu by its top-left corner, and the height of the
        button puts that just below the menu bar rather than on top of it.
        """
        if self._menu is None or self._menu.numberOfItems() == 0:
            return
        button = self._item.button()
        below = NSMakePoint(0, button.frame().size.height + 4)
        self._menu.popUpMenuPositioningItem_atLocation_inView_(None, below, button)

    def pump(self) -> None:
        """Deliver what AppKit is holding, then come straight back.

        `distantPast` is what makes it non-blocking: take an event if one is
        already queued, otherwise answer `None` at once. The loop drains rather
        than taking one per call, so a handful of clicks in the same quarter
        second cannot build a backlog that arrives a tick at a time.

        With nothing built, there is nothing of ours holding events, and asking
        for the shared application here would create one as a side effect of a
        heartbeat.
        """
        if self._app is None:
            return
        while True:
            event = self._app.nextEventMatchingMask_untilDate_inMode_dequeue_(
                NSEventMaskAny, NSDate.distantPast(), NSDefaultRunLoopMode, True)
            if event is None:
                return
            self._app.sendEvent_(event)
