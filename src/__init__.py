"""wobble — a Poké Ball Plus that tells you when Claude Code finished or is stuck.

The layout is the architecture, and it is the one thing this package asserts:

    core/           decides WHAT is being said — signals, the queue, attention
    ball/           the Poké Ball Plus over BLE — protocol only
    mirrors/        decides HOW to say it, one file per surface
    platform_seam/  the only place an operating system is named

`core` never imports a mirror and never imports the seam's platform file. A
mirror renders only what the core handed it. See `constitution.md` principles
1 and 6 — both are about this diagram, and neither is a preference.
"""
