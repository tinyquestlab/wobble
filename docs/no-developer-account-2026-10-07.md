# Shipping a Mac app with no paid Apple Developer account — 2026-10-07

Spec 02, task 05. Asked on 2026-10-07: wobble shows in System Settings as *Item from unidentified
developer*, and the $99/year Apple Developer Program is not an option. What do other open-source
Mac apps on GitHub do, and what are wobble's options?

## The answer

**wobble already sits on the road that needs no account.** `constitution.md` (amendments of
2026-09-29 and 2026-10-02) ships the source only and builds `wobble.app` on the Mac that runs it.
An app built locally is never downloaded, so it carries no `com.apple.quarantine` attribute, and
Gatekeeper never assesses it. Measured here: `xattr -l /Applications/wobble.app` shows only
`com.apple.provenance`, and `codesign -dv` says `Signature=adhoc`, `TeamIdentifier=not set`.
*Unidentified developer* in Login Items is that ad-hoc signature described in words. It is a
label, not a block: task 01 started the app at a real login with its grants.

## What the facts are

- **Apple silicon runs no native code without a signature**, but an ad-hoc one (`codesign -s -`)
  counts. "Unsigned" on an arm64 Mac always means ad-hoc signed.
- **Downloaded apps are where the cost is.** A browser sets `com.apple.quarantine`. Since macOS 15
  (Sequoia), Control-click › Open no longer bypasses Gatekeeper. The person has to try to open
  the app, then go to System Settings › Privacy & Security and click **Open Anyway**, or run
  `xattr -dr com.apple.quarantine` on the app.
- **Developer ID signing and notarization both need the paid program.** A free Apple ID in Xcode
  ("Personal Team") signs for your own machine only, and cannot notarize.
- **Homebrew is closing its own door.** Homebrew 5.0.0 deprecated casks without codesigning and
  the `--no-quarantine` flag. Casks in `Homebrew/homebrew-cask` that fail Gatekeeper are disabled
  in September 2026, and 6.0.0 confirmed that timeline. Third-party taps are outside that rule, but
  since 6.0.0 a person must trust a tap explicitly before its code runs.
- **TCC pins an ad-hoc app's grants to its cdhash**, so new bytes mean every grant is asked again.
  That is why `tools/build_app.py` says whether the launcher's bytes moved. A certificate,
  self-signed included, gives the app a stable designated requirement, and the grants survive a
  rebuild.

## What other open-source apps do

| Project | How it ships | Cost to the person |
|---|---|---|
| AeroSpace (`nikitabobko/AeroSpace`) | not notarized; its own Homebrew tap, whose install script deletes `com.apple.quarantine` | trusts the tap; the README says "By using AeroSpace, you acknowledge that it's not notarized" |
| Many smaller projects | an ad-hoc-signed `.app` or zip on GitHub Releases | `xattr -dr com.apple.quarantine`, or Open Anyway, per download |
| Godot exports, games | the same, documented in their manuals | the same |
| Projects with a sponsor | notarized under a paid account | none, but someone pays $99/year |

## wobble's options

| | Option | Cost | Needs |
|---|---|---|---|
| **A** | **Keep it: source release, `.app` built on each Mac** (now) | Xcode command line tools and a clone, once; the *unidentified developer* label | nothing |
| B | A self-signed certificate made by `build_app.py` in the person's keychain | a keychain prompt and more code; grants survive a launcher change, which is rare | a constitution amendment ("no signing") |
| C | A prebuilt ad-hoc `.app` on GitHub Releases | Open Anyway or `xattr` per download; and the app runs code from the repo folder, so it needs the clone anyway | a constitution amendment ("no `.app` attached") |
| D | A Homebrew tap, AeroSpace's way | packaging Python and five libraries; tap trust; quarantine removed by script | a constitution amendment ("no installer") |
| E | The paid program, $99/year | money, every year | ruled out |

**Recommendation: A.** It is the only option with no download, so it is the only one Gatekeeper
never sees. It is also what the constitution already says. B is the one worth keeping in mind, if
launcher changes ever become frequent enough that re-granting hurts. Nothing here is built.

## Sources

- [Homebrew 5.0.0](https://brew.sh/2025/11/12/homebrew-5.0.0) — casks without codesigning
  deprecated, disabled in September 2026; `--no-quarantine` deprecated
- [Homebrew 6.0.0](https://brew.sh/2026/06/11/homebrew-6.0.0/) — the timeline kept; tap trust
- [Homebrew, Acceptable Casks](https://docs.brew.sh/Acceptable-Casks) — must pass Gatekeeper
- [AeroSpace README](https://github.com/nikitabobko/AeroSpace) — not notarized, quarantine removed
  by its tap
- [AppleInsider, runtime protection in Sequoia](https://appleinsider.com/inside/macos-sequoia/tips/whats-changed-in-runtime-protection-for-macos-sequoia)
  — Control-click bypass removed
- [OSnews on macOS 15.1](https://www.osnews.com/story/141055/bug-or-intentional-macos-15-1-completely-removes-ability-to-launch-unsigned-applications/)
  — reports of Open Anyway missing for unsigned apps
- [Apple Developer Forums 767774](https://developer.apple.com/forums/thread/767774) — "unsigned"
  arm64 code is ad-hoc signed code
- [Running unsigned applications on Sequoia](https://christiantietze.de/posts/tags/gatekeeper/) —
  Open Anyway in Privacy & Security
- [OpenClaw, mac signing](https://docs2.openclaw.ai/platforms/mac/signing) — ad-hoc grants pinned
  to the cdhash; a certificate keeps them across rebuilds
