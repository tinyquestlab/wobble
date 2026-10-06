# Usage baseline — 2026-10-06

A one-off read of the daemon's daily logs (`var/logs/`, `src/log.py`), to see what they can
already answer about real use and what is worth capturing next. Read by a throwaway script, not
by anything in the repo. No window title, project name of anyone else's work, or session id
appears here: the logs hold them, this page only counts.

**Span.** 2026-09-23 → 2026-10-06, 12 day files. A session id on every signal line only from
2026-09-28, so the timings below cover the 8 days since. 84 daemon starts from a terminal; none
since 2026-10-03, when the app took over.

**Whose lines.** The suite never writes here — each table's daemon logs into its own sandbox
(`src/daemon.py`, the log follows the events file). The desk checks by hand did: they ran on real
sessions, by design. This repo's own sessions are 29% of the signals and 63% of the audible beats,
nearly all from one needs (finding 2). Without them and the `probe*` sessions, the medians below
move by seconds, not minutes.

## What a signal's life looks like

| | done | needs |
|---|---|---|
| signals with an end in the log | 955 | 137 |
| queued → resolved, median | 72 s | 25 s |
| p75 / p90 | 3.7 min / 15.1 min | 77 s / 8.5 min |
| beats before it ended, median / p90 | 0 / 2 | 7 / 167 |
| over 30 min (done) / over 10 min (needs) | 62 | 12 |

How they ended:

| done | | needs | |
|---|---|---|---|
| you were there | 854 (89%) | answered where it asked | 99 (72%) |
| its session closed | 101 (11%) | approved (its Bash started) | 28 (20%) |
| | | you were there / session closed / turn ended | 10 |

B: 1 063 presses that reached a window, 943 focused and 120 NOT FOCUSED. All 120 are on or before
2026-10-01 — Accessibility not yet granted to the app (61), no window titled for the project (65,
mostly the 2026-09-23 desk round), macOS refusing to bring the app forward (10). Since 2026-10-02:
128 presses answered, 0 NOT FOCUSED.

## Findings

1. **A done mostly ends itself; a needs is the one that waits.** 89% of dones end because you
   were already in their window, before the second beat. The long tail is needs: 12 over ten
   minutes, the longest flashing 5 029 times over 2.2 h before it was approved.
2. **One needs rang for 106 minutes.** 2026-10-05, 19:45 → 21:31, in this repo's session: 3 829
   audible beats (effect 199) while the ball was switched off and the Mac had the sounds, and
   `holding — you just typed` 60 times — you were at the keyboard, in other windows. Either
   the Mac did not play it, or it played and was tuned out. The log cannot say which.
3. **The same done is queued again while still pending — 724 times.** Most on 2026-10-05, the
   day Claude re-invoked itself 783 times (background tasks finishing, `injected turn`). The log
   does not say whether a re-queue restarts the ladder.
4. **A window change is logged only while something is waiting.** Today 917 changes, every one
   with a signal live or held (`src/daemon.py`: `in front` is said only with a target). A first
   count said 249 with nothing pending; that was the reading script forgetting, at midnight,
   what was still waiting from the day before.
5. **Away and ignoring look the same.** The 9 h done was a night. Nothing marks when you left the
   keys and came back, except the greet, so a long wait cannot be split into "away" and "seen and
   left".
6. **The questions need pairing by hand.** No line states a signal's life; it takes matching
   `queued` to `resolved` by kind and session, keeping the first `queued` of a re-queue.
7. **Fourteen days is the whole memory.** The 2026-09-23 file goes tomorrow; no summary outlives
   the files.

## What would be worth capturing

| | Line or file | Answers |
|---|---|---|
| a | On resolve: `after 4m12s · 9 beats (3 audible) · answered where it asked` | every timing above, with no pairing |
| b | `away` / `back` when the keys go idle past a threshold and return | finding 5 |
| c | ~~Window title only while something is pending~~ — already so | finding 4 |
| d | A summary line per day into a file kept longer than the logs | finding 7 |
| e | On a re-queue: whether the ladder restarted | finding 3 |

## Adjustments to consider (none applied)

- A needs past N minutes unanswered: one louder reminder, or stop the sound and only flash. The
  106-minute needs is the case either way.
- The ladder for done: the data says almost nobody needs past beat 2. No change suggested until
  (b) separates away from ignoring.
