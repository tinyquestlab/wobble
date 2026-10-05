#!/usr/bin/env python3
"""Draw tools/app/wobble.icns, the app's icon, from the menu bar's ball (task 59).

    venv/bin/python3 tools/make_icon.py

The same drawing as the menu bar item (`draw_ball` in src/platform_seam/macos.py,
task 58), connected and with nothing lit, in fixed colours. Drawn in code: never
Nintendo's art (CLAUDE.md). The .icns is committed, so a build copies bytes that
do not move and the grants pinned to them carry over (task 48); run this again
only when the drawing changes, and expect macOS to ask for the grants once more.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.platform_seam.macos import ball_png                          # noqa: E402
from src.platform_seam.ports import BallIcon                           # noqa: E402

ICNS = ROOT / "tools" / "app" / "wobble.icns"
INK, PAPER = "#1F1F24", "#FFFFFF"
# The sizes an .iconset holds, each once and once @2x (`man iconutil`).
POINTS = (16, 32, 128, 256, 512)


def main() -> int:
    with tempfile.TemporaryDirectory() as box:
        iconset = Path(box) / "wobble.iconset"
        iconset.mkdir()
        for points in POINTS:
            for scale, suffix in ((1, ""), (2, "@2x")):
                path = iconset / f"icon_{points}x{points}{suffix}.png"
                ok, why = ball_png(BallIcon(connected=True), points * scale, str(path),
                                   ink=INK, paper=PAPER)
                if not ok:
                    sys.exit(f"make_icon: {why}")
        out = subprocess.run(["iconutil", "-c", "icns", "-o", str(ICNS), str(iconset)],
                             capture_output=True, text=True)
        if out.returncode != 0:
            sys.exit(f"make_icon: iconutil could not make {ICNS} from {iconset} "
                     f"({out.stderr.strip() or f'exit {out.returncode}'})")
    print(f"drew    {ICNS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
