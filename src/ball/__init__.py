"""The Poké Ball Plus over BLE — framing, effects, uploads, input decode.

Protocol only: this package knows how to make the device do a thing, never
which thing is worth doing. That decision belongs to `core`, and the wiring
between them is `mirrors/ball.py`.

Every protocol fact it relies on is in `docs/PROTOCOL.md`, cited by section.
Filled by tasks 02, 03, 06 and 07.
"""
