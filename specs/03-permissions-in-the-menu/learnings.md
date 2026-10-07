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

## Concepts learned

## Promoted
