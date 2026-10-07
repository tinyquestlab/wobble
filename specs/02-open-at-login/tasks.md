# Tasks — S02

**6 of 6 done**

- [x] **01 — measure the LaunchAgent at a real login.** By hand, before any code: write the plist,
  log out and in. Does wobble start, with its grants (B raises a window)? What does Login Items
  show, and does `SMAppService.statusForLegacyURL` read BTM's verdict, on and switched off?
  Answers open question 1 and fixes criterion 4. *Done 2026-10-07: started at login with its
  grants, B raised a window; BTM readable, and its "off" survives a rewrite (`learnings.md`).*
- [x] **02 — the `Login` port: macOS writes the agent, null refuses.** Plus `check_login.py`.
  *Done 2026-10-07: `check_login.py` 35 rows over a temporary folder and a fake SMAppService, eight
  mutants caught; `check_seam.py` 53 → 59 rows for the null side.*
- [x] **03 — the menu line and the log lines**, wired in the daemon; rows in `check_menubar.py`.
  *Done 2026-10-07: `menubar.login_line`, the last line above Quit's separator; the daemon reads
  the state each refresh and says it when it changes, a click in its own words. `check_menubar.py`
  163 → 178 rows, five mutants caught; full suite green, slow tables included.*
- [x] **04 — docs**: README (switching it, Background Items, uninstall), `DESK-CHECKS.md` Part B
  step, `ROADMAP.md`'s item ticked. *Done 2026-10-07: README's Start it, menu, Uninstall and
  Troubleshooting; Part B step 30; ROADMAP says it is built.*
- [x] **05 — no paid Apple Developer account: what other open-source Mac apps do.** Asked on
  2026-10-07, to come last: how projects on GitHub ship an unsigned or ad-hoc-signed app (Gatekeeper,
  "unidentified developer", Homebrew casks, a self-signed certificate…), and the options for wobble,
  each with its cost to the grants. Research and a recommendation only; nothing is built here.
  *Done 2026-10-07: `docs/no-developer-account-2026-10-07.md`. wobble is already on the road that
  needs no account — built on each Mac, never quarantined; recommendation: keep it.*
- [x] **06 — close learnings.md and promote** *Done 2026-10-07: five entries to `NOTES.md`; the
  Outcome table in `spec.md`.*

---
