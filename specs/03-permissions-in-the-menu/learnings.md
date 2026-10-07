# Learnings — S03

## Learned

- 2026-10-07: Automation can be read without a prompt, but only for a running target:
  `AEDeterminePermissionToAutomateTarget` answers -600 (procNotFound) when the app is not
  running, whatever TCC holds. A read of "not running" says nothing about the grant.
- 2026-10-07: The drawing's right-aligned "Open…" became " · Open…" at the end of the alert's
  label: a plain `NSMenuItem` has one title and no right-aligned second column (that is a key
  equivalent's place). A custom view would do it, at the cost of AppKit's own highlight and
  keyboard handling, so the label carries it.
- 2026-10-07: AppKit gives a line with a submenu its own action, `submenuAction:`, the moment
  `setSubmenu_` is called. A row asserting "no action" on it is wrong; assert it is not ours.
- 2026-10-07: A mutant that drops the submenu line's slot in the handler list survives every
  click row, because it is consistent with itself. Only a row pinning one tag to its index in the
  flattened list tells the two conventions apart.
- 2026-10-07: `CBManager.authorization()` costs ~12 ms a read here; `AXIsProcessTrusted` and the
  Automation read cost nothing measurable. At four refreshes a second that is the daemon's loop
  paying ~5% for an answer that changes once a month, so the daemon reads every 2 s
  (`PERMISSIONS_EVERY_S`). Criterion 1's "within one menu refresh" became "within 2 s".
- 2026-10-07: the `⚠` for the title is computed after `offer()` has read, by placing `alert=`
  after `menu=offer(...)` in the same call: Python evaluates keyword arguments left to right.
  Swapping them would lag the title one refresh behind the menu, which no table can see.

## Concepts learned

## Promoted

- "Not running" says nothing about the grant → NOTES.md (Learnings).
- "Open…" in the label, not right-aligned → NOTES.md (History).
- `submenuAction:` on a submenu line → stays here (one table's row).
- A consistent mutant needs a row pinning the convention → stays here; the same lesson is already
  in S01's learnings for the flat menu.
- Bluetooth's read costs ~12 ms, read every 2 s → NOTES.md (Learnings).
- Keyword-argument order computes the `⚠` → stays here (a comment in `daemon.py` says it).
