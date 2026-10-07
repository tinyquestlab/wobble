"""Picks one implementation of `ports.py` and re-exports it as eight singletons:
`sound`, `frontmost`, `focus`, `process`, `idle`, `login`, `permissions`, `status`.

**Not named `platform`.** A package importable as `platform` would shadow the
standard library module of that name for the whole process, silently. One
directory, one importable name, no shim.

**Singletons, not a factory.** `from src import platform_seam` then
`platform_seam.sound.play(path)` is the entire interface; a factory would make
every call site invent somewhere to keep what it built.

Selection order: `WOBBLE_PLATFORM` (an explicit override — `null` on a Mac is how
a run proves it touched no PyObjC), else `macos` on Darwin, else `null`. Chosen
once, at import time; nothing here runs on two platforms in one process.

**The fallback says so, out loud, and says the true thing.** `macos.py` does not
exist yet (it arrives with tasks 12 and 14), and once it does it will import
PyObjC, which can be missing. Those are different facts and get different
sentences: `from . import macos` was tried first and reported a missing file as
"most likely due to a circular import", which is a false sentence about a real
failure — worse than none. Falling back quietly would be worse still: a ball
that never rings and a Mac that never makes a sound, with silence as the only
symptom. Principle 7 is written about exactly this.
"""
from __future__ import annotations

import importlib
import os
import sys

_WANTED = os.environ.get("WOBBLE_PLATFORM") or ("macos" if sys.platform == "darwin" else "null")

_impl = None
_REASON: str | None = None

if _WANTED != "null":
    _dotted = f"{__name__}.{_WANTED}"
    try:
        _impl = importlib.import_module(f".{_WANTED}", __name__)
    except ModuleNotFoundError as exc:
        # The seam file itself is absent, vs. something it imports being absent.
        if exc.name == _dotted:
            _REASON = f"there is no {_WANTED} seam file yet — running with no platform"
        else:
            _REASON = f"the {_WANTED} seam needs {exc.name}, which is not installed — running with no platform"
    except ImportError as exc:
        _REASON = f"the {_WANTED} seam failed to load ({exc}) — running with no platform"

if _impl is None:
    from . import null as _impl  # type: ignore[no-redef]
    if _REASON:
        print(f"wobble: {_REASON}", file=sys.stderr)

PLATFORM = _impl.__name__.rsplit(".", 1)[-1]
UNAVAILABLE = _REASON

sound = _impl.Sound()
frontmost = _impl.Frontmost()
focus = _impl.Focus()
process = _impl.Process()
idle = _impl.Idle()
login = _impl.Login()
permissions = _impl.Permissions()
status = _impl.Status()
