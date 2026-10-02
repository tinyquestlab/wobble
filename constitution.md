# Constitution — wobble

## Vision

You leave Claude Code working, walk away from the desk with a Poké Ball Plus in your hand, and the
ball tells you when it finished or when it is blocked on you — by sound, by light and by rumble.
You press the ball's B button, the ball goes quiet, and the window that was waiting comes to the
front. That is the whole product. Everything else — a creature on screen, gamification, other
agents, other platforms — is a later phase that must not be allowed to arrive early.

This project starts from an answered question — how to drive this device's sound, LED and rumble
over Bluetooth from a Mac (`docs/PROTOCOL.md`) — and from a lesson: a project that answers it
and then grows past what anybody decided it should be stops being finished. What is known about
the ball is written down once and cited; everything built on it is judged before it arrives.

## Principles

1. **One core, many mirrors.** The core decides *what is being said*: which signal, what is
   pending, which one has your attention. A mirror decides only *how to say it* on its own
   surface. The ball is a mirror. The menu bar is a mirror. Buddy will be a mirror plus a game,
   and anything else that shows up is a mirror too. A mirror may never invent state the core did
   not give it, and may never express something the core cannot say — that rule is what keeps the
   menu bar from becoming Buddy through the back door.

2. **The ball is the product; the screen is its mirror.** The MVP must work with no ball attached,
   because that is how it gets developed and how anyone without the hardware meets it. But the
   vocabulary is the ball's: same states, same queue, same dismissal. The screen never gets a
   feature the ball cannot have.

3. **The desk check is the gate.** Nothing is done because it worked once. The MVP ships no
   automated test suite on purpose: the output is physical, the shape is still moving, and a suite
   written now would pin decisions that have not been made. `docs/DESK-CHECKS.md` is the gate
   until the MVP is concluded; the suite is phase 02, over everything that is not the radio.

4. **Two sources, or it is not a fact.** A by-hand catalogue and an accelerometer sweep disagree
   about effect ids 198–200. Either could be the wrong one. A single reading that
   confirms what we already believed is the cheapest way to be wrong here, and the device gives no
   error when a command does nothing.

5. **Prior work is a study base, not a parts bin.** Take what is proven at the protocol level —
   framing, upload, the GATT map, the input decode — and write everything above it here. A file
   arrives because it was read and judged, never because it existed.

6. **Platform-specific code lives behind the seam, from the first commit.** The MVP runs on macOS
   only. Windows and Linux must each add one file, never provoke a rewrite. Nothing macOS-specific
   may leak into the core, and the seam is not allowed to be added "later".

7. **A notifier that stopped silently is worse than none.** Silence is indistinguishable from
   "still working", and that is the failure this product cannot have. Every refusal and every
   missing permission says so in words, where the person can see it. A lost link may say so in a
   drawing instead, if the drawing cannot be mistaken for a connected one at a glance; the words
   are then one click away, in the menu (task 63).

8. **One attention at a time.** Several sessions can be pending; you are dealing with exactly one.
   Dismissing means "I am handling this now", not "show me the next one".

9. **Everything written here is in English.** Code, identifiers, comments, docs, commits. The
   conversation's language never decides the artifact's language.

## Non-goals (MVP)

Explicitly out of scope, so that scope creep has to argue with this file:

- No creature on screen. No pet, no window, no animation, no poses.
- No gamification: no levels, no affection, no quests, no experience.
- No agent other than Claude Code.
- No gestures, no motion input, no controller emulation.
- No Windows or Linux implementation — the seam only.
- No automated test suite.
- No PR flow. Commits pushed when I choose. A release is the source, tagged, with notes on GitHub —
  nothing built ships with it: no installer, no signing, no notarization, no updates. A `.app` is
  built on each Mac from the repo, for that Mac.

## Amendment

This file is edited only on my explicit ask, and every amendment is dated. A change here is a
change of direction, not a refactor.

- 2026-09-22 — written.
- 2026-09-29 — a `.app` built locally from the repo is not a release. It is how the permissions
  get filed under wobble instead of under the terminal that started it (ROADMAP, "wobble as an
  app").
- 2026-10-02 — the repository may have a remote and be public, free and non-commercial
  (`LICENSE`, `NOTICE.md`). Publishing the source is not a release: still no installer, no
  signing, no notarization, no updates.
- 2026-10-02 — wobble has releases, starting at 0.1.0 beta: a git tag `vX.Y.Z` (with `-beta`
  while it is one) and a GitHub Release of the source with notes. Still no installer, no signing,
  no notarization, no updates, and no `.app` attached: a permission grant is pinned to the
  launcher's bytes (`tools/build_app.py`), so the app is built on the Mac that runs it.
