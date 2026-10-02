#!/usr/bin/env python3
"""Build wobble.app from this repo, for this Mac (task 50).

    venv/bin/python3 tools/build_app.py                  # var/build/wobble.app, to look at
    venv/bin/python3 tools/build_app.py --install        # /Applications/wobble.app
    venv/bin/python3 tools/build_app.py --install --reset-grants

Not a release (constitution, amended 2026-09-29): no installer, no signing
identity, no notarization, no updates. The bundle holds no Python and none of
wobble's code. Its executable is `tools/app/launcher.c`, which starts
`tools/app/start` in this repo, so the bundle is filed under wobble by macOS
while the code it runs stays here, and a `git pull` changes nothing macOS
checks (task 48).

**An ad hoc grant is pinned to the bundle's exact bytes** (task 48: the
launcher rebuilt with -O0 lost Accessibility, rebuilt as before got it back).
So the Info.plist below never carries a build number, the compiler flags never
change, and this prints the code directory hash it signed: the same hash as the
installed one means the grants carry over, a new one means macOS asks again.

`--reset-grants` clears the Accessibility and Bluetooth entries filed under
`local.wobble` (`tccutil reset`), for when the hash changed: an entry left from
other bytes can show as switched on in System Settings without granting
anything. That is macOS's usual behaviour, and not measured here yet.

The icon is `tools/app/wobble.icns`, committed (task 59): it is sealed into the
signature like everything else in the bundle, so it is copied, never drawn at
build time. `tools/make_icon.py` redraws it, and a new icon is new bytes.

Moving the repo means a rebuild: the launcher knows where it lives.
"""
from __future__ import annotations

import argparse
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "var" / "build" / "wobble.app"
INSTALLED = Path("/Applications/wobble.app")
IDENTIFIER = "local.wobble"
ICON = ROOT / "tools" / "app" / "wobble.icns"

# /Applications and nowhere else: it is the only place macOS will start an app
# at login from (SMAppService, ROADMAP "wobble as an app"), the step after this.


def info(identifier: str) -> dict:
    """The Info.plist. Nothing in it changes from one build to the next."""
    return {
        "CFBundleIdentifier": identifier,
        "CFBundleName": "wobble",
        "CFBundleDisplayName": "wobble",
        "CFBundleExecutable": "wobble",
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": "1",
        "CFBundleVersion": "1",
        # The ball the menu bar draws, as the Finder's icon (task 59).
        "CFBundleIconFile": ICON.stem,
        # No Dock icon: the menu bar item is wobble's only surface (principle 2).
        "LSUIElement": True,
        # Without this, macOS ends the process on its first touch of Bluetooth.
        "NSBluetoothAlwaysUsageDescription":
            "wobble talks to the ball over Bluetooth to tell you when Claude Code "
            "is waiting.",
        # Terminal's tabs are read and selected by Apple event (tasks 42, 43).
        "NSAppleEventsUsageDescription":
            "wobble asks Terminal which tab a session runs in, so that B brings "
            "that tab forward.",
    }


def cdhash(app: Path) -> str | None:
    """The code directory hash codesign signed, which is what a grant is pinned to."""
    out = subprocess.run(["codesign", "-dvvv", str(app)], capture_output=True, text=True)
    for line in out.stderr.splitlines():
        if line.startswith("CDHash="):
            return line.split("=", 1)[1]
    return None


def build(app: Path, *, root: Path = ROOT, identifier: str = IDENTIFIER,
          alert: str | None = None, source: Path | None = None) -> str:
    """Write `app` and sign it ad hoc; returns its code directory hash.

    `root`, `alert` and `source` are for `var/desk/check_app.py`, which builds
    copies that start something else, alert nobody, or are a mutant.
    """
    if app.exists():
        shutil.rmtree(app)
    macos = app / "Contents" / "MacOS"
    macos.mkdir(parents=True)
    (app / "Contents" / "Info.plist").write_bytes(plistlib.dumps(info(identifier)))
    resources = app / "Contents" / "Resources"
    resources.mkdir()
    shutil.copyfile(ICON, resources / ICON.name)
    flags = ["clang", "-O2", "-Wall", "-Wextra", "-o", str(macos / "wobble"),
             str(source or ROOT / "tools" / "app" / "launcher.c"), f'-DROOT="{root}"']
    if alert:
        flags.append(f'-DALERT="{alert}"')
    subprocess.run(flags, check=True)
    subprocess.run(["codesign", "--force", "--sign", "-", "--identifier", identifier,
                    str(app)], check=True, capture_output=True)
    subprocess.run(["codesign", "--verify", "--strict", str(app)], check=True)
    found = cdhash(app)
    if found is None:
        sys.exit(f"build_app: {app} was signed, but codesign reports no CDHash for it")
    return found


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--install", action="store_true",
                    help=f"build into {INSTALLED} instead of {BUILD.relative_to(ROOT)}")
    ap.add_argument("--reset-grants", action="store_true",
                    help=f"with --install: clear Accessibility and Bluetooth for "
                         f"{IDENTIFIER}, so the next launch asks cleanly")
    args = ap.parse_args(argv)
    if args.reset_grants and not args.install:
        ap.error("--reset-grants only makes sense with --install")

    if not (ROOT / "venv" / "bin" / "python3").exists():
        sys.exit(f"build_app: there is no venv at {ROOT / 'venv'}, and the app runs "
                 f"wobble from it — make it first (README)")
    target = INSTALLED if args.install else BUILD
    before = cdhash(target) if target.exists() else None
    if args.install and subprocess.run(["pgrep", "-f", f"{target}/Contents/MacOS/wobble"],
                                       capture_output=True).returncode == 0:
        sys.exit(f"build_app: {target} is running — quit it from its menu first")
    after = build(target)
    print(f"built   {target}")
    print(f"cdhash  {after}")
    print(f"runs    {ROOT / 'tools' / 'app' / 'start'}")
    if before is None:
        print("grants  none yet — the first launch asks for Bluetooth and Accessibility")
    elif before == after:
        print("grants  the same bytes as before, so what was granted still is")
    else:
        print(f"grants  new bytes (was {before}), so macOS asks again"
              + ("" if args.reset_grants or not args.install
                 else " — --reset-grants clears the old entries first"))
    if args.reset_grants:
        for service in ("Accessibility", "BluetoothAlways"):
            out = subprocess.run(["tccutil", "reset", service, IDENTIFIER],
                                 capture_output=True, text=True)
            print(f"reset   {service}: "
                  f"{(out.stdout or out.stderr).strip() or f'exit {out.returncode}'}")
    if args.install:
        print("next    open /Applications/wobble.app (quit any daemon started from a "
              "terminal first: only one runs per events file)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
