# Tasks — S03

**4 of 7 done · next: 05 — the daemon: read each refresh, say each change, wire the clicks**

- [x] **01 — measure the three reads and the panes.** By hand, before any code, from wobble.app
  and from a terminal. Questions to answer:
  - What do `AXIsProcessTrusted` and `CBManager.authorization` answer, with each permission
    granted and refused?
  - Can Automation for Terminal be read without a prompt?
  - Do the `x-apple.systempreferences:` URLs for Accessibility, Bluetooth and Automation land on
    the right pane?

  Answers open questions 1–3.

  Done 2026-10-07, from a terminal (macOS 26.6.2, 25G83); the app's own answers come from Part B,
  after task 05 says them in the log:
  - `CBManager.authorization()` answered 3 (allowed always), with no prompt.
  - `AXIsProcessTrusted()` answered True.
  - `AEDeterminePermissionToAutomateTarget(..., askUserIfNeeded=False)` through ctypes, no
    prompt: Finder 0 (granted), Warp -1744 (not asked), Terminal -600 (not running).
  - Both URL forms open the right pane; the classic one
    (`com.apple.preference.security?Privacy_<Pane>`) is kept.
- [x] **02 — the seam's menu: a submenu and a checkmark.** `Checked` and `Submenu` in
  `ports.py`, drawn by `macos.Status.menu`, recorded by null. One click table across the nested
  lists. Rows in `check_seam.py`, and a table for the AppKit side.

  Done 2026-10-07: `check_menu_shapes.py` builds a real, unshown `NSMenu` and clicks it through
  AppKit's dispatch; the `Settings` line takes a tag slot of its own, pinned by quit's tag.
- [x] **03 — the `Permissions` port: macOS reads and opens, null refuses.** Plus
  `check_permissions.py`, run against a fake framework, with mutants.

  Done 2026-10-07: 45 rows, 14 mutants; two rows read the real macOS, read only.
- [x] **04 — the menu: alert lines, `⚠`, `Settings ›`, login moved in.** Rows in
  `check_menubar.py`; S02's login rows rewritten for the new home.

  Done 2026-10-07: 212 rows (178 before). "Open…" is part of the alert's label, not
  right-aligned: see learnings.md.
- [ ] **05 — the daemon: read each refresh, say each change, wire the clicks.** Rows in
  `check_daemon_edges.py`.
- [ ] **06 — docs.**
  - README: the menu and `Settings ›`.
  - ROADMAP: item 1 decided not to do, with why; item 2 built.
  - `docs/DESK-CHECKS.md` Part B: revoke Accessibility in the app and watch the line appear; grant
    it and watch the line go.
- [ ] **07 — close learnings.md and promote**

---
