"""The notification core: which signal, what is pending, whose turn it is.

Nothing here may import `bleak`, AppKit, `osascript`, or a mirror. If something
in this package needs to know an operating system exists, the seam was drawn in
the wrong place. Filled by tasks 08 (the queue), 09 (attention) and 10 (the
repeat ladder).
"""
