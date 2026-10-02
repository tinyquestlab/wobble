# S01 — Learnings

Dated, with how it was measured. Desk-check answers land here too (tasks 04, 05).

## Task 01 — Skeleton

- **2026-09-22 — `from . import macos` lies when the file is missing.** Inside a package's own
  `__init__.py`, importing a sibling that does not exist raises *"cannot import name 'macos' from
  partially initialized module ... (most likely due to a circular import)"*. There is no circular
  import; the file simply is not written yet. A true-sounding, wrong sentence is worse than no
  sentence (principle 7), so the seam uses `importlib.import_module` and branches on
  `ModuleNotFoundError.name`: the seam file absent, and something the seam file imports absent,
  are different facts and get different words. Measured by creating two throwaway seam files —
  one importing a package that does not exist, one that loads — and reading what each printed.

- **2026-09-22 — the reference leg matters even here.** "PLATFORM is null" on a Mac is also what a
  broken selector would print. The second probe file (a seam that loads cleanly) was selected and
  reported its own name, which is what makes the null result evidence about the missing file
  rather than about the selector.

- **2026-09-22 — `python3` on this machine is 3.9.6.** `python3.12` is at
  `/opt/homebrew/bin/python3.12`. CLAUDE.md's venv line said `python3` and would have built a 3.9
  venv, below bleak's own floor of 3.10. Fixed to name the version.

- **2026-09-22 — the bleak floor is read, not guessed.** `bleak>=0.22` was a guess; the protocol
  layer task 02 ports was proven against `bleak>=3.0`, verified against 3.0.2 on Python 3.12.14
  before this rewrite. This venv resolves to the same 3.0.2. The floor is now the proven major.

## Task 02 — The ball's protocol layer

- **2026-09-22 — the reply queue has no attribution, and the lock is what supplies it.** Two
  coroutines sharing one `ACK_E8` queue take each other's acks. Measured with a fake client whose
  acks echo the frame's effect id and one write dropped: without the lock, the sender whose frame
  was *dropped* was handed the next sender's ack and reported success — a lost write reported as
  delivered, which is the exact silent failure principle 7 forbids. With the lock, the retry fired
  on the right frame. The first two probes both passed with and without the lock and proved
  nothing: identical ack bytes make misattribution invisible. **Open, and it matters:** if the real
  ball's ack carries nothing identifying the frame it answers, the lock is not an optimisation, it
  is the only thing making an ack mean anything. Task 03 reads a real ack and settles it.

- **2026-09-22 — `unframe` is an inherited claim, not a measured one.** Earlier notes say
  the ball replies "in the same framing" and that code never parsed a reply to check. So `unframe`
  returns `None` instead of raising, and callers log raw hex either way. Task 03 is where a real
  ack either parses or does not.

- **2026-09-22 — the CCCD bytes in `OPENING` are documentation, not configuration.** The capture
  shows the Switch writing `0x0002` (indicate) for CE46/CE47, but bleak writes the descriptor
  itself from the characteristic's properties, so that column configures nothing. Earlier code
  carried the values and silently ignored them too. Kept as the captured fact, labelled as inert.

- **2026-09-22 — bleak 3.0.2's API is the one earlier code was written against.** `BleakScanner(
  detection_callback=…)`, `BleakClient(target, disconnected_callback=…, timeout=…)`,
  `write_gatt_char(char, data, response=False)`, `start_notify(char, cb)` — all four checked by
  introspection before porting, rather than after a failure. `find_ball` did need one change:
  `asyncio.get_event_loop()` inside a coroutine became `get_running_loop()`.

## Task 03 — Play an effect from the CLI

First contact with the hardware. Two sessions, both clean: 8/8 frames acked, 0 retries, 100% first
try, ~70 input packets on IN_E6 during the opening alone.

- **2026-09-22 — the ack framing is now measured, not inherited.** All 8 acks of a session parse as
  `<opcode:u8><len:u16 LE><payload>`. Earlier notes asserted this in prose and never parsed one.

- **2026-09-22 — the ack has its own opcode, paired with the command's.** `0x04`→`0x02`,
  `0x10`→`0x09`, `0x0c`→`0x07`, `0x03`→`0x01`. Recorded as `protocol.ACK_OF`. One session for three
  of them; `0x03`→`0x01` seen in two separate sessions.

- **2026-09-22 — and for effects the ack identifies nothing.** This is the one that mattered.
  `0x04` echoes the counter it answers (`…01`→payload `01…`, `…04`→payload `04…`) and `0x0c` echoes
  its payload byte for byte — but effect 2 and effect 198 both came back `01 0200 0300`, identical.
  So the frame the MVP sends most often is the one whose ack cannot be attributed, and the wire
  lock in `link.Link` is load-bearing rather than defensive. The task 02 open question is closed.

- **2026-09-22 — `0300` in an effect ack is not decoded and does not need to be yet.** Constant
  across both effects and both sessions. Guessing it is a status would be a single-source claim
  about a field nothing depends on.

- **2026-09-22 — an ack is acceptance, not sound.** Recorded here because the numbers above are
  seductive: 100% first try says the ball received every frame, and says nothing about whether
  anything was heard or felt. That is a separate observation, by a person, and §8.13 is what a run
  that conflated the two cost.

## Task 04 — Desk check: the LED

- **2026-09-22 — an LED resource alone does NOT light the ball.** Index 344 (pidgey's, captured)
  sent over `0x08`, acked, link held up for a full 8 s window, observed by eye: nothing. The ack is
  acceptance of a transfer, not evidence of light. plan.md question 1, half answered.

- **2026-09-22 — the faint vibration was never the LED at all: it is the ball connecting.** Worth
  the space because of how it was nearly written down as a finding. Two sessions sending the same
  `led 344` came back with different acks — `01 0200 0800` once and `01 0200 0300` the next — and a
  faint vibration was felt on the first and not the second. The theory built on that was that
  `0300` was another command's notification taken as ours, and that matching the ack to the opcode
  sent would make the vibration consistent. It did not: two `led 344` sends in one session both
  acked `0800` with `foreign_replies: 0`, and only the FIRST vibrated. The next run vibrated on no
  send at all, and the person holding the ball named the real cause — **it vibrates when it
  connects**, and the first send of every session simply follows a connect.

  Both of my observations were attributed to the wrong object, and the one thing that caught it was
  a person with the ball in their hand. Constitution principle 4 is written about exactly this: the
  first reading agreed with what I already suspected, and that made it the cheapest possible way to
  be wrong. **An LED resource alone produces nothing observable — no light, no vibration.**

- **2026-09-22 — the ack-matching stays anyway, on its own merits.** It was written for the wrong
  reason and is right for a different one: accepting another command's notification reports a frame
  as delivered that the ball may never have processed, and suppresses the retry that should have
  fired. `foreign_replies` counts how often it actually happens, which nobody has measured.

- **2026-09-22 — the ball stops advertising and it is not the scanner.** Two 45 s scans found
  nothing; a reference scan in the same minute saw 41 other devices, so Bluetooth and the scanner
  were fine and the ball simply was not advertising. `--scan` now defaults to 45 s, and a desk check
  needs the person to press the top button *while* the scan runs — running the command themselves
  removes the coordination problem entirely.

- **2026-09-22 — the index alone does nothing; the index followed by an effect does everything.**
  `led 344 --then 213` produced light, sound and vibration together. `213` plays the most recently
  uploaded resource, and an LED arrives over the same `0x08` path the audio does, so the resource
  is what `213` fires. plan.md question 2 — "never run" until now — is answered: **an index needs
  an effect played after it.**

- **2026-09-22 — and the LED does not stay on. It lights and goes out by itself.** Observed across
  all six windows of the alternating sweep. This is bigger than the question that was asked: the
  hunt was for an index that reads as dark, and there is no persistent state to clear — every index
  is a transient animation. **Acceptance criterion 3 of `spec.md` ("The LED stays on") may be
  unimplementable on this hardware**, and the spec's own edge case anticipated the shape of this
  without anticipating the cause.

- **2026-09-22 — index 700 lit nothing, and that result is not usable.** In a sweep where every
  other index lit and went out, 700 produced no light. But "an index that does nothing" and "an
  index that lights too briefly to see" are indistinguishable to an eye once the LED
  self-extinguishes, so the alternating reset — designed to separate exactly this — cannot separate
  it either. Recording the ball on video beside the terminal is what would, and that is the cheap
  half of the capture rig worth building.

- **2026-09-22 — re-triggering `213` gives an abrupt repeated flash with sound, not a soft pulse.**
  Ten triggers 0.6 s apart, watched on a screen recording during the session and reported by the person holding the ball. All ten sounded. (The recording is not in the repo.) The idea of holding a
  gentle pulse instead of a steady light does not survive contact with the hardware by this route:
  each trigger is an abrupt event and the sound is welded to it. A quiet light is not available
  from the resource + `213` path, so the LED cannot carry "pending" without also making noise.

- **2026-09-22 — the video analysis was a wrong turn, and the person watching was the instrument.**
  Measuring the LED as "cyan above red" in a fixed crop produced four confident lit runs, including
  one spanning 0.00–2.43 s, before any command had run. The control region moved as much as the
  LED region, which was the signal that the crop was tracking a moving hand and a camera changing
  its own exposure — and the answer, from the person holding the ball, was that the LED never
  changed at all and the camera's brightness did. **A control region that does not stay flat has
  already told you the measurement is void; continuing to tune the threshold after that is how an
  artefact becomes a finding.** The cheap capture rig is still worth building, but it needs a fixed
  camera and fixed exposure, or it produces exactly this.

- **2026-09-22 — the silent pulse works. A mute cry in the slot gives light with no sound.** A
  0.5 s MS ADPCM 16 kHz mono silence, cut into 9 `0x08` chunks, then the LED resource, then `213`
  five times 1.2 s apart: the LED flashed each time and nothing was audible. So `213` fires the
  most recently uploaded resource SET, not just the last frame, and the sound is separable from the
  light after all. **This is the mechanism "the LED pulses while pending" runs on**, and it makes
  the upload path (task 06) a dependency of the LED ladder rather than only of the cry.

  The framing was verified offline before the radio was touched — kinds `1,0,0,0,0,0,0,0,2`,
  indexes 0-8, bodies 498 except the last — against the shape measured from 45 captured frames.
  ffmpeg adds a `LIST` chunk the ball's own files do not have; it is stripped, keeping only
  `fmt `/`fact`/`data`.

- **2026-09-22 — the ball has a soft amber breathing glow of its own, and we did not make it.**
  Pressing the stick puts the ball into play mode (it has a creature in it), which is entirely
  ball-local — no Switch, no BLE. Watched on a recording: a warm amber ring around the centre
  button, fading gently in and out, no sound, and it keeps going after the hand lets go. That is
  the feel the pending pulse wants, and it is nothing like the abrupt cyan flash an LED resource
  gives. **Worth trying, later, and the lead is specific:** the genuine GO Plus `LED_BUTTON`
  service (`21c50462-67cb-63a3-5c4c-82b5b9939aec`) takes a packet with explicit RGB nibbles, a
  duration, a vibration intensity and an `interpolate` flag — a smooth fade, by construction,
  rather than an index into a firmware animation. That packet has already been built, and the
  service was probed once with a generic `0x85` and never followed up. Deliberately NOT started
  here: it is a different service and a different packet format, so it is a fresh thread, not a
  tweak to this one.

## Task 05 — Desk check: the rumble, through a pocket

Two legs, because the task asks two questions and no one instrument answers both. The objective
leg is the ball's own IMU with the ball still on the desk; the perceptual leg is a blind trial with
the ball in a pocket. Both ran clean: 0 unacked writes across 32 trials.

- **2026-09-22 — the input counter steps by 6 on this link, not 3, and believing the inherited 3
  reported a 100% loss rate on a link losing 1.9%.** `missed` came back equal to the sample count,
  exactly one lost packet per packet received — a round factor of 2, which is a step mismatch and
  never a constant to re-tune. The second source that settled it is structurally different from the
  first: the inter-packet timestamps. Across 2749 gaps in 38 windows the mode is **30 ms** (33.3 Hz)
  and only 51 exceed 45 ms, so the stream is uniform and nothing is being dropped at the rate the
  counter implied. The real loss is **1.9%**. The step is now inferred from the stream and passed
  in, rather than being a module constant asserting something about every link that ever connects.
  The `missed` column of both runs saved on this date is wrong by that construction; the peaks and
  means are not, because they come from the samples and never from the counter.

- **2026-09-22 — both sources were partly wrong about 198/199/200, and each was wrong in its own
  characteristic way.** Five measurements per id, id order shuffled every round, floor re-measured
  six times and stable at mean 15.2–17.7 / peak 26.2–40.0.

  | id | peak (median) | peak range | mean | mean ×floor | motor ran |
  |---|---|---|---|---|---|
  | 198 | 239.5 | 233–348 | 29.8 | 1.8× | 241 ms |
  | 199 | 1197.6 | 469–1500 | 116.4 | 6.9× | 571 ms |
  | 200 | 1138.6 | 1047–1695 | 124.0 | 7.4× | 600 ms |
  | 241 | 1989.0 | 1716–2313 | 310.5 | 18.5× | 1202 ms |

  **The accelerometer sweep was wrong that 198 does not vibrate.** It reads 1.22× there and its
  weakest peak here is 233 against a floor whose strongest peak is 40 — the motor runs, for about
  241 ms. The old sweep's own notes predicted this exact miss and named the cause: a mean over a
  1.5 s window dilutes a short tick about fifteenfold. Measured here rather than argued: 198's
  **mean** says 1.8× (indistinguishable from the floor by eye) while its **peak** says roughly 6×
  the floor's peak. That gap between the two statistics IS the dilution, and it is why the traces
  are now written out per trial instead of one aggregate per id.

  **The by-ear catalogue was wrong that 198 is the same as 199 and 200.** It is about five times
  weaker at peak and runs for less than half as long. 199 and 200 *are* each other: their peak
  ranges overlap heavily and this instrument cannot separate them, which is the one part of the
  catalogue that survives.

  Neither source was simply the bad one. plan.md question 4 is answered: **198 rumbles, and it is
  a different, much weaker beat than 199/200; 199 ≡ 200.**

- **2026-09-22 — the capture waves ARE felt through a pocket, and the id that rumbles nearly twice
  as hard on the desk is felt LESS.** Blind trial, 12 trials, order shuffled, ids never shown, the
  buzz delayed a random 0.4–1.8 s after the keypress so its timing could not be the answer.

  | trial | felt (0–3) | median | heard |
  |---|---|---|---|
  | **nothing sent** | 0, 0, 0 | 0 | 0/3 |
  | `198+199+200` | 3, 3, 2 | 3 | 3/3 |
  | `200+199+198` | 2, 2, 3 | 2 | 3/3 |
  | `241` | 1, 1, 2 | 1 | 2/3 |

  **The controls are what make the rest readable.** Three trials sent nothing at all and all three
  came back as nothing felt and nothing heard, so the answers above are about the ball and not
  about expectation. Had one of them been felt, the run would have been thrown away instead of
  tabulated.

  `241` was carried into this run as the reference leg — 26.9× the floor in the old sweep, 18.5×
  here, the loudest thing nearby — and **it lost to the waves in the pocket.** That kills the
  premise of the open thread that wanted `needs` swapped for something that rumbles harder: harder
  on a desk is not the same measurement as noticeable on a leg. The likely reason, offered as a
  hypothesis and not as a finding: `241` is one continuous 1202 ms buzz while the waves are three
  separate onsets, and three onsets are harder to mistake for the body's own movement. **n is 3 per
  condition, so the direction is the result and the size of it is not.**

- **2026-09-22 — the signal reaches a pocket on two channels, not one, and asking one question
  would have hidden that.** Both wave groups were *heard* 3/3 through the pocket as well as felt.
  Had the trial asked a single "did you notice it", a rumble that carries and a sound that carries
  would have been recorded as the same fact. They are separable and both work, which makes the
  `needs` signal more robust than the rumble alone — and it is only visible because the question
  was split before the data existed, not after.

- **2026-09-22 — plan.md's wave order is not the capture's, and it is the better one anyway.** The
  sniffer capture plays `200, 199, 198` (all four catches end `… 198 201 213`), while plan.md has
  `needs` as `198→199→200`. The pocket trial ran both: plan.md's order read median 3 and the
  capture's order median 2. Consistent with ending on the strongest beat rather than on the weakest
  — 198 is the weak one — but n is 3, so this is a reason to keep what is already written, not a
  reason to claim a difference was measured.

- **2026-09-22 — what the instrument does that the one it replaces did not**, recorded because the
  changes are what produced the two corrections above and not incidental to them: every trial's
  per-sample trace is kept (the old probe stored one aggregate per id and its notes say a peak
  statistic "cannot be recovered without sweeping again"); the id order is shuffled every round, so
  a drifting floor cannot land on one id as the old run's 84% drift did; and every id is measured
  five times, because "is 199 the same as 200" is a question about two distributions and single
  readings of 6.22 against 5.67 could never have answered it.

- **2026-09-22 — verified against a synthetic ball before the real one was touched.** The fake gave
  241 a long strong buzz, 199/200 a 300 ms tick, and 198 nothing at all. The instrument had to
  report MOVES for the first two and "overlaps the floor" for the third, and did — a run where
  everything reads as moving is an instrument measuring its own optimism. The blind controls were
  exercised in both directions too: a null answered as felt must void the run, and a reference id
  answered as unfelt must say the ball is sitting badly. Both fired.

### Task 05, after the run — the person's ranking, and what the IMU cannot see

- **2026-09-22 — the person felt 198 > 199 > 200, which is the opposite of what the IMU measured,
  and the instrument cannot referee this.** The IMU puts 198 about five times below 199/200 at
  peak. Reported from the pocket, in the person's own words: the waves were heard and felt easily
  in every order sent, and felt strongest to weakest 198, 199, 200.

  **The IMU is blind to the dimension that most plausibly explains it.** It samples at 33.3 Hz,
  so Nyquist is 16.7 Hz, while the motor was measured from audio at a spectral centroid of
  450–745 Hz (`docs/PROTOCOL.md` §6.7's rumble class). Everything the motor does is far above the sampling
  rate, so what the accelerometer scores is an aliased envelope — roughly *how much* the ball is
  thrown around — and it carries no information at all about *how fast* it is shaking. Human
  vibrotactile sensitivity peaks in the low hundreds of Hz and falls away on either side, so an id
  running at a frequency closer to that peak can feel stronger while reading lower here. The two
  results are not necessarily in contradiction; they are two different quantities, and this was
  not known when the instrument was designed.

  So the old sweep's motto needs a second clause. It said a quiet reading means "does not vibrate",
  never "does nothing". It also has to mean: **a loud reading is not a claim about how it feels.**

- **2026-09-22 — and the run cannot attribute a beat to an id, which has to be settled before the
  ranking is believed either.** The blind trials played the three ids as one group, so a ranking
  formed inside a group is a ranking of *positions* — first, second, third — and 198 is the first
  position of `198+199+200` exactly as reported. If the same descending pattern was felt in
  `200+199+198` too, then the finding is "the first beat is the most noticeable", which is about
  onsets against a quiet background and says nothing about the ids. If it reversed with the order,
  the finding is about the ids and the IMU's amplitude reading is the misleading one.

  **The decisive run is cheap and has not been done:** the same blind mode with the three ids
  played individually rather than grouped — `--blind 198 199 200` — which separates id from
  position completely. Until then the ranking is recorded, not concluded.

- **2026-09-22 — what does survive both readings, unchanged.** `198+199+200` is felt and heard
  through a pocket, in every order tried, with three null trials confirming that nothing is felt
  when nothing is sent. That is plan.md question 3, and it does not depend on which of the three
  beats is the strongest.

### Task 05, the decisive run — id separated from position

Fifteen blind trials, the three ids played individually rather than grouped, ball in a pocket,
0 unacked writes. Controls clean again: three trials sent nothing, all three felt 0 and heard
0/3, IMU peak 31–40 against a pocket floor of mean 16.1 / p95 42.2.

**What the felt column is, and is not.** It is a person reporting a feeling, in a pocket, in a
room with sound in it, with the ball sitting somewhere slightly different every time and a body
that moves. Nothing in that was held constant and nothing in it could have been. So a gap of two
or three points, repeated, is a real difference in what arrives; a gap of one point is inside the
noise of the method and is not promoted to a result here no matter how consistently it appears.
The table below is read with that line drawn through it.

| id | felt (0–3) | median | heard | pocket IMU peak | desk IMU peak |
|---|---|---|---|---|---|
| 198 | 0, 0, 1, 0 | 0 | 4/4 | 96–152 | 233–348 |
| 199 | 2, 2, 2, 2 | 2 | 4/4 | 256–1010 | 469–1500 |
| 200 | 2, 3, 3, 3 | 3 | 4/4 | 453–1607 | 1047–1695 |
| nothing sent | 0, 0, 0 | 0 | 0/3 | 31–40 | — |

- **2026-09-22 — the ranking reverses once the ids are played one at a time: it was a position
  effect, not an id effect.** Grouped, the report was 198 > 199 > 200 — which is also exactly
  first, second, third of `198+199+200`. Played individually, **199 and 200 are both clearly felt
  and 198 is essentially not** — which is the side the IMU was on. The first beat against a quiet background is the most noticeable
  one, and inside a group that is indistinguishable from "this id is the strongest". Naming both
  readings *before* the run is the only reason the run could tell them apart; had the ranking been
  written down as an id fact, it would have contradicted the trace for good and the trace would
  probably have been the one thrown away.

- **2026-09-22 — 198 is HEARD every time and FELT essentially never.** 4/4 heard, felt 0 in three
  trials of four and 1 in the fourth. Its motor does run — 96–152 against nulls at 31–40 — so the
  desk finding stands, and it still does not reach a leg through cloth. The by-ear catalogue files
  198 as light+rumble+sound and every one of those words is defensible; what none of them says is
  that the rumble does not survive a pocket. **A channel that exists is not a channel that
  arrives**, and only the pocket could say which.

- **2026-09-22 — 200 leaned one point above 199, and that is texture, not a finding.** 199 came
  back 2, 2, 2, 2 and 200 came back 2, 3, 3, 3: four trials in the same direction, which is exactly
  the shape that invites being written down as a result. It does not clear the noise it was
  measured in — the ball was not replaced in the same spot between trials, the room was not quiet,
  and the leg it sat against moved. One point on a four-point subjective scale lives inside all of
  that. The IMU cannot separate them either, on the desk (469–1500 against 1047–1695) or in the
  pocket (256–1010 against 453–1607). **`199 ≡ 200` stands**, and the lean toward 200 is recorded
  as something to notice if it keeps turning up, not as a difference that was measured.

- **2026-09-22 — and the frequency hypothesis is withdrawn as an explanation, kept as a limit.**
  It was invented to explain a contradiction that turned out not to exist. The IMU really is blind
  above 16.7 Hz while the motor runs at 450–745 Hz, so "loud here" still cannot mean "strong on
  skin" — but nothing in this data needs that to be explained, and a mechanism kept around after
  the thing it explained evaporated is how a plausible story becomes a believed one.

- **2026-09-22 — so plan.md's `198→199→200` is a crescendo, and that is why it won.** The order
  runs from the beat that is only heard, through the middle one, to the strongest — while the
  capture's `200→199→198` ends on the one that a pocket cannot feel. That is the mechanism behind
  the grouped run's 3 against 2, and it is a reason to keep what plan.md already says rather than
  to follow the capture. **198 earns its place as sound, not as rumble**, which is a choice of feel
  and belongs to the person at the desk, not to this file.

## The episode shape — task 10 pulled forward for one question

- **2026-09-22 — the capture's rhythm was always in the pcapng and had never been read.**
  `read_capture.py` unpacks the Enhanced Packet Block's `ts_high`/`ts_low` into `_` and yields the
  body alone, so the captures could say which effects a catch plays and in what order, and never
  when. A one-off desk instrument, since removed, kept the timestamp (and read `if_tsresol` rather
  than assuming microseconds). This closes the spec's open question on the beat: **the beat is measured now, not a
  guess.** Its own guard came for free — `check_offset` covers 100% of all three files, and
  capture 01 comes back at exactly the 11235 packets `read_capture.py`'s docstring recorded.

- **2026-09-22 — a real catch is three SINGLE beats about 1.2 s apart, and all three captures
  agree to within 15 ms.**

  | step | 01 | 02 | pikachu-catch |
  |---|---|---|---|
  | `200` → `199` | 1.140 | 1.140 | 1.140 |
  | `199` → `198` | 1.231 | 1.230 | 1.230 |
  | `198` → `201` (the click) | 1.289 | 1.260 | 1.275 |
  | `201` → `213` (the cry) | 2.041 | 2.085 | 2.070 |

  Before the wobble, the throw: `203`, `+0.06 208`, `+0.21 204`, `+0.69 205`, then `211` three
  times at +0.54, +0.24, +0.15 — an accelerating triple — and then **0.55 s of silence** before the
  first wobble. So the game does the tightening *before* the wobble and then releases into three
  slow, isolated beats. The wobble is not a burst and never was.

- **2026-09-22 — a fourth source, structurally different, lands on the same numbers.**
  `docs/capture-pidgey-scene.mp4` is the real ball filmed on the desk during a catch, and its audio
  onsets — a microphone, not a sniffer — fall 1.14 / 1.24 / 1.26 s apart, then 2.08 s to the cry.
  Four legs agreeing is what turns 1.2 s from a number in one file into the cadence of the thing.
  Worth keeping because the mp4 also shows what no capture can: the ring lights per wobble
  (white / amber, then green at the catch), which is the next knob if the wobble needs more.

- **2026-09-22 — a two-act ramp was built and then set aside, and the second act is the part that
  went.** The wobble held the cycle fixed at 4.3 s and grew what was said (`198`, `198 199`, the
  capture's three, those three tightened); the alarm then held the content fixed and shrank the
  cycle to 2.3 s. Read back on the page it was two ideas where one was wanted, and the call was
  made before the desk run rather than after — so this is a judgement about complexity, not a
  measurement about feel. Kept written down because the ramp is where rung 2 came from, and
  because the reason to reach for it again (more beats, closer together, is the only escalation
  cloth respects) has not gone away.

- **2026-09-22 — the wobble climbs `198→199→200` where the game descends `200→199→198`, on
  purpose.** Through cloth the game's order fades out: 198 is heard 4/4 and felt 0/4. Copying the
  capture exactly would make the opening end on the beat a pocket cannot feel — the opposite of an
  opening that grows. The cadence is inherited, the direction is not.

- **2026-09-22 — 0.65 s inside a rung is a measurement, not a round number.** The motors run
  241 / 571 / 600 ms, so at the alarm's 0.35 s beat `200` starts ~220 ms before `199` has finished:
  two clean beats and a smear. At 0.65 s all three are separable. The alarm wants the smear and
  the wobble wants the beats, which is why the same three ids can serve as the last gentle rung and
  the first insistent burst.

- **2026-09-22 — the `needs` signal is one beat on one interval: `199` every 1.5 s, until
  dismissed. The interval was chosen at the desk.** Two shapes were built and set aside before it
  — a four-rung capture wobble growing into an accelerating alarm, then `198 199` paired on a
  4.3 s cycle — and what survived both is a single number to turn. The starting point was the
  capture's measured 1.14 s and the desk moved it to 1.5 s, which is a judgement about feel and
  the only number here that is one. It lives as `INTERVAL` at the top of `var/desk/episode.py`
  today and belongs in `config/signals.json` at task 10, where it can change without touching
  code.

  **Not measured, and still owed: the time to the press.** That was the run's other question and
  no number came back from it, so the repeat ladder is still built on `plan.md`'s 2/5 minute
  guess.

- **2026-09-22 — the interval has a floor of ~0.6 s and it is the motor, not the radio.** `199`
  runs for 571 ms, so anything shorter sends the next beat into a motor that never stopped: one
  continuous buzz, with the wire lock serialising the writes behind it. The number on the flag
  would stop being the number felt, which is why the script says so instead of obeying quietly.

## Task 06 — Pikachu's voice in the slot

- **2026-09-22 — the framing port is proved against the bytes a real Switch sent, not against a
  shape.** A one-off desk instrument, since removed, cut `assets/cries/pidgey.wav` with our own
  `resource.cut()` and compared it frame by frame with the `0x08` payloads in
  `pbp-pareamento-01.pcapng`: 8 frames, `498×7 + 191`, **byte for byte identical**, kinds 1/0/2 and
  the index counting from 0. The LED resource (kind 3, 22 B) is in the capture too and is
  deliberately not part of a cry. This matters because `docs/PROTOCOL.md` §8.1 notes three files of
  exactly the size the RIFF header declares with corrupt audio inside — **a size that matches is
  not evidence**, so nothing here asserts a length.

- **2026-09-22 — `normalise_wav` is a no-op on a file the ball itself sent, and that is the check
  that says it matches the device rather than an idea of it.** It exists for ffmpeg output, whose
  three differences from a real cry (1024-byte blocks, the sample rate written into
  `nAvgBytesPerSec`, a `LIST` chunk) all come out of the ball as the same silence.

- **2026-09-22 — `Link.hold()`: a resource upload holds the wire for all eight frames, not one at
  a time.** The ball reassembles by the `index` byte, so a frame written in between belongs to
  nobody. `send` checks a `_held` flag instead of re-entering the lock, because `asyncio.Lock` is
  not reentrant and that deadlock would look exactly like a ball that stopped answering.

- **2026-09-22 — the interleaving test was worthless until a negative control was run, and the
  first attempt at that control silently did not run at all.** `var/desk/fake_cry.py` ended in
  `sys.exit(asyncio.run(main()))` at module level, so importing it to reuse its fake *ran the whole
  suite and exited* — and the output that scrolled past was the suite's own "PASSED 3/3", which is
  exactly what the control was expected to print. **A broken probe produces the failure a wrong
  theory predicts, and a passing one produces the success.** With the `__main__` guard added, the
  control says what it should: without `hold()`, **7 effects land inside the upload**; with it, 0.
  The leg is a real test, and it is only known to be one because it was run against a version that
  must fail.

- **2026-09-22 — a partial upload is refused rather than played.** If any frame goes unacked the
  slot holds a resource with a hole, and `213` would then play half a cry, the previous creature,
  or silence — three different facts with one symptom. `src/ball/cry.py` skips the trigger, says
  the slot is in an unknown state, and exits non-zero.

- **2026-09-22 — Ctrl-Z does not release the ball, and the symptom is a ball that will not
  connect.** A suspended process (`STAT T`) keeps the BLE link open while running no code:
  `system_profiler SPBluetoothDataType` listed `Pokemon PBP` under **Connected** with nothing
  driving it. The fix is `kill -CONT <pid> && kill -INT <pid>` — SIGCONT first, because a stopped
  process cannot handle the interrupt, and SIGINT rather than SIGTERM so the `open_ball` context
  manager unwinds and disconnects cleanly. Ctrl-C at the desk, never Ctrl-Z. A run suspended
  mid-episode is also spoiled for timing: `perf_counter` keeps moving while the beats stop.

- **2026-09-22 — the cry uploads and plays at the desk, and it does NOT need the LED resource.**
  `python -m src.ball.cry assets/cries/pidgey.wav --play` sends the 8 cry frames and then `213`
  once — nothing else, no `kind 3` frame — and the ball flashed and cried. The flash is `213`'s
  own: the by-ear catalogue files it as light+sound, and task 04 already saw a mute resource in the
  slot give a flash with no sound. **This closes a question carried over from before this
  rewrite**, left as "whether the cry commits without the LED resource is untested": it commits. The
  22-byte `kind 3` blob is per creature and is now a colour question, not a correctness one.
  `resource.led_payload()` builds one; nothing sends it yet.

## Task 07 — Input, and B as an edge

- **2026-09-22 — the assumed release is a choice between forging a press and losing one, and the
  careful-looking third option is the same thing as having no rule.** The spec asks for an assumed
  release when packets stop, and the obvious refinement — after a silence, require a real release
  before counting a press, so nothing is forged — turns out to be byte-for-byte identical to doing
  nothing at all: keeping the stale `down` level also requires a real release before the next
  press. The two stall stories, "held right through the dark" and "released and pressed again in
  the dark", deliver **exactly the same packets**, so no reader can tell them apart and the rule is
  a decision about which error to make. It is written down because the first draft of
  `var/desk/fake_button.py` had them as two rows with different expected numbers, which is a
  reading no stream could ever produce.

  **What the rule costs is bounded at one forged press per stall**, because the level is re-read
  from the very packet that forged the edge — a latch bug seen before forged one every latch
  window instead, for as long as the latch lasted, and the fix was to NOT clear the level.
  `Button.assumed_releases` counts them so the trade stays countable rather than becoming folklore.

- **2026-09-22 — the silence window is 0.5 s, and it is the measured stream that sets it, not a
  guess.** The link's gaps are mode 30 ms with only 51 of 2749 past 45 ms (task 05), so 0.5 s is
  ~17 consecutive packets missing — nothing this link has ever done — while a disconnect or a
  sleeping ball is seconds. The fake-episode run puts a further number on the headroom: driving the
  sink through a loaded asyncio loop, the biggest gap seen was 61 ms.

- **2026-09-22 — the spec's own cited failure is NOT the one the spec's remedy covers.** The edge
  case names a button observed reading `down` for 43 s before this rewrite, and that happened with
  the stream still flowing — a latched level, which no silence rule can see. What this task
  implements is the flavour the spec asks for, silence. The latched one is still open, and it needs
  a second rule with its own forged-edge cost; `src/ball/button.py` says so where somebody reading
  the file will meet it.

- **2026-09-22 — a desk check may not set the pace; the person holding the hardware does.** The
  guided check first counted "3… 2… 1… GO" into each step and it was not followable with a ball in
  one hand: a step missed by half a second reads as a button that does not work, which is a finding
  about the script and would have been written down as a finding about the ball. It now waits for a
  keypress before opening each window, and the key is read on a thread — a blocking `input()` would
  stall the event loop, and a stall past `SILENCE_S` is precisely what makes this module assume a
  release, so the lazy version would have manufactured the one event the module exists to handle.

- **2026-09-22 — B is `0x01`, and `tasks.md` had it written down as `0x02`.** The guided check
  watched BOTH bits while the person pressed only B, through all three steps, and every press came
  back on `0x01`. So the spec work's stick click was a wrong assignment on paper — not a hand
  reaching for the wrong button — and dismissing on this same bit, as earlier code did, was right. It
  agrees with the other thing known about the stick: pressing it starts the ball's own play-mode
  glow, which a dismissal has no business doing. Corrected in `button.py`, `tasks.md` and `plan.md`.

  **The check could only say this because it listened to both bits.** Defaulting it to the bit the
  spec already believed in would have produced three green rows and the wrong constant.

- **2026-09-22 — B reads as an edge on this ball, and here is the run.** Three guided steps, all
  green: one tap -> 1 press, a held button -> 1 press, two quick taps -> 2. 762 packets in 22.9 s
  is **33.2 Hz**, matching task 05's 33.3 Hz from a different instrument; 0 malformed; biggest gap
  **61 ms**, so the 500 ms silence window has roughly eight times the headroom it needs and fired
  zero times. The opening's 7 frames all acked first try.

  The link counted 766 input packets and the watcher 762. The four are not loss: `input_sink` is
  attached after `open_ball` returns, and the opening subscribes to `IN_E6` a couple of commands
  before it does. Worth knowing before somebody reads that gap as a defect.

- **2026-09-22 — a press can be swallowed, and the floor is one packet.** Step 3 was pressed three
  times and the middle one produced nothing anywhere — not a late edge, not an edge outside the
  window: 4 presses recorded in total, which is exactly the 1+1+2 the steps accounted for. Two
  candidates, both sitting at the same floor, and this run cannot separate them: a tap whose whole
  down-and-up fell between two samples 30 ms apart is invisible by construction, and a single lost
  packet at exactly the wrong moment does the same thing (the 61 ms gap says one packet went
  missing somewhere in the run, and this link loses ~1.9%).

  **It is a resolution limit, not a bug, and there is no fix on our side** — the ball reports a
  level 33 times a second and says nothing between samples. `Button.press_lengths` now records how
  many packets each press stayed down, and the summary prints the shortest, so the next run says
  how close to the floor a real thumb gets instead of leaving this as a story. What it costs the
  MVP is small: a dismissal is one press and the signal keeps repeating, so a swallowed one is
  pressed again. Task 09's "press again to skip to the next" is where it could be felt.

## Task 08 — The core: signals and the queue

- **2026-09-22 — a case that tests a rule has to disagree with a world where the rule is gone, and
  one of ours did not.** `check_queue.py` prints a **kind-blind** control beside every case: the
  same entries ordered by age alone, priority thrown away. "A done replaces a pending needs" came
  back green with a control that agreed with it — so it would have passed with the priority rule
  deleted. The fix was to the case, not the code: the newer `needs` now arrives *last*, so nothing
  but its kind can put it on top. Second time in one session that a control earned its keep; the
  first was task 07's silence rule.

  Both mutations were then run against the finished table — ordering by age alone, and restarting
  the wait on every event — and both came back red. A table nobody has broken on purpose is a
  table nobody has tested.

- **2026-09-22 — `since` and `at` are two different facts and the queue needs both.** `since` is
  when a session entered its CURRENT kind, `at` is its newest event. A session blocked ten minutes
  ago that signals `needs` again is still blocked since ten minutes ago, so repeating must not send
  it to the back of its own kind — that is `since` holding. A session that finished at 12:00 and
  blocks at 12:10 has been blocking for nothing, not for ten minutes — that is `since` restarting
  on a kind change. One timestamp cannot say both, and picking either one alone gets a real case
  wrong.

- **2026-09-22 — the seam rule is now mechanical rather than written down.** `check_queue.py` parses
  every file in `src/core/` and fails on an import of `bleak`, AppKit/Foundation/Cocoa/objc, `rumps`,
  `subprocess`, anything under `src.ball`/`src.mirrors`/`src.platform_seam.macos` — **and `time`**,
  because the core takes `now` as an argument. Proved by planting a file that imports `time` and
  `src.mirrors` and watching the check go red. Prose loses to a convenient import at 11pm; a gate
  does not.

## Task 09 — Attention

- **2026-09-22 — a state machine gets its control by deleting one rule at a time, not by being
  read carefully.** `check_attention.py` runs the same stories against three mutants: one that
  never freezes the queue, one whose safety net never fires, one where anybody's prompt releases
  the hold. All three were caught, which is what makes the green run above them mean something.
  Reading the rows and agreeing with them would have proved nothing — the rows were written by the
  same head that wrote the machine.

- **2026-09-22 — `current()` is pure and `tick()` is the only thing that moves time, and that is a
  decision, not a style.** The obvious shape is a `current()` that checks the clock while it
  answers, and it hides the exact bug this machine can have: a freeze that ends because somebody
  looked at it rather than because a rule said so. Splitting them also means the stories run a
  ten-minute net by writing `700.0`, with no sleep anywhere.

- **2026-09-22 — the core says WHY an attention ended; it does not say it in words.** `tick` and
  `prompted` return a `Release` carrying the session, the project, the reason and how long it was
  held. Building an English sentence in the core would be the core deciding *how* a surface talks,
  which principle 1 gives to the mirror. What principle 7 requires is that every release be
  reportable, and a record is reportable — a silent safety net would be the same defect as the
  silence it exists to prevent.

- **2026-09-22 — the safety net is a net, not a schedule.** If ~10 min is ever what releases the
  queue in normal use, the release that should have happened — a prompt in the session you
  dismissed — is not arriving, and that is a fact about the hooks (task 11), not a number to
  re-tune. Written into the constant so the next person to reach for it reads that first.

## Task 10 — The repeat ladder

- **2026-09-22 — a check whose first candidate always matches is not a check.** The refusal helper
  in `check_ladder.py` walked a list of tokens and stopped at the first one found in the message.
  The first was `".json"` — the path, present in every single error — so all six refusal rows
  printed "refused, and named ..." while proving nothing about the key. It now takes the key each
  case must name, separately from the file, and every message has to carry both. This is the same
  shape as task 09's mutants and task 08's kind-blind control, arriving from a third direction: a
  test that cannot fail is indistinguishable from one that passed.

- **2026-09-22 — every number in `config/signals.json` carries a `_source`, including the ones that
  are guesses.** `needs` = `199` every 1.5 s is measured then judged at the desk. `done` playing
  once is a CHOICE. The pending pulse's 30 s is **not measured at all** and says so. JSON has no
  comments, so the provenance is a sibling key — ugly, greppable, and the alternative is a guess
  that becomes a measurement in about a week because nobody wrote down which it was.

- **2026-09-22 — the loader warns rather than refuses on two things, and hands the warnings back
  instead of printing them.** An interval under the ~0.6 s the motor runs for, and a pending pulse
  with `silent` false, are both legal and both mean the number written is not the thing felt. The
  core does not print (principle 1 gives *how to say it* to the mirror) and does not swallow
  (principle 7), so `Ladder.warnings` is the third thing in this core with that shape, after
  `Release` and the `Entry` a mirror renders.

- **2026-09-22 — criterion 3 was a guess written before anything had been felt, and is now
  amended in place.** "Repeats at ~2 min and ~5 min, then stops" became "keeps speaking until it is
  dismissed", because a signal that stops on its own is a notification lost on purpose. Criterion 2
  lost "with a growing gap" for the same reason. Criterion 6 was settled later the same day — see
  the task 09 entries below.

- **2026-09-22 — the silent pulse belongs to `done` alone, and that follows from the cadence.** A
  `needs` beats every 1.5 s until somebody dismisses it, so it never falls silent and there is
  nothing for a pulse to carry. A `done` says its cry once and goes quiet — the flash is what keeps
  saying "still waiting". The pulse moved from a top-level `pending_pulse` to a per-kind `pulse`,
  `null` for `needs`, and the loader now warns when a kind plays once AND has no pulse, because on
  the ball that combination says nothing at all after the first beat.

### Criterion 6, settled — and it moved the machine (2026-09-22)

- **The safety net became a snooze, and "unfreeze and move on" turns out to be how the dismissed
  one gets lost.** The spec said a ~10 min net unfroze the queue and the next signal surfaced. What
  was settled: **~5 min, and the same signal comes back**, into the place it had in the queue —
  dismissing is a promise to look, and a promise not kept returns the thing rather than replacing
  it. `Queue.restore` puts it back with its original `since`, so it lands where it was instead of
  at the end, which is the whole point of something you ignored coming back.

  It does not go back if that session signalled again while it was being attended: the newer entry
  is already there and wins. `Release.returned` says which happened, so the difference is visible
  rather than inferred.

- **A prompt in ANY session drops that session's pending entry — a rule that did not exist before
  and is not the same as releasing the hold.** Going to a session resolves its notification: you
  were there. Releasing the hold is separate and only happens for the session actually being held.
  `Answered(released, dropped)` carries both, and is falsy when a prompt changed nothing.

  **The only signal the MVP has for "you went to it" is a prompt.** Merely looking at the window is
  invisible from the core — the `Frontmost` port says which app, not which window, and mapping a
  window to a session is task 14's problem.

- **The mutants found the seam again.** Two of the four in `check_attention.py` exist only because
  of this change — one that lets the dismissed signal go instead of returning it, one whose prompt
  leaves the answered entry in the queue — and both were caught. A third, whose snooze never fires,
  crashed the suite on an attribute of `None` instead of failing a row; a control that dies with a
  traceback stops the controls after it from running, so the row now reads the attribute defensively.

## Task 11 — Claude Code hooks

- **2026-09-22 — the hook is `/bin/sh` and never python, and that is a measurement, not a taste.**
  A python hook paid for this before: the venv's Homebrew-Framework python makes macOS
  LaunchServices bounce a Dock icon for ANY invocation of that binary, whatever it does once
  running — once per prompt and once per reply, forever. Nothing inside the script could fix it;
  only not spawning it could. `tools/hook_event.sh` carries forward three other hard-won rules:
  always exit 0 (a hook that can fail can
  block a prompt), guard `[ -t 0 ]` (a hand-run has no writer and `cat` would hang forever), and
  parse **no** fields in shell — the payload can carry a whole typed prompt, and hand-parsing human
  text with shell expansion corrupts somebody's words rather than just a tool name.

- **2026-09-22 — the hook mapping was verified against a live configuration, not remembered.**
  `Stop` -> done, `Notification` -> needs, `UserPromptSubmit` -> prompt. A previous hook's own
  wiring is still installed in `~/.claude/settings.json` and says exactly that, which is a second
  source for a thing that would otherwise have been written from memory and been wrong quietly.

- **2026-09-22 — the end-to-end check found a defect none of the unit-shaped checks could.**
  `check_daemon.py` runs the real hook script into the real daemon, and the transcript showed `done`
  playing its cry AND its silent flash in the same tick: the pulse had no `last`, and "no last"
  means "due now". The cry had already flashed. The pulse now starts one interval after the final
  beat. Every piece was correct on its own; what was wrong was the join, which is the only thing a
  per-piece check cannot see.

- **2026-09-22 — a check that pins column padding fails on a cosmetic change and passes on a real
  one.** Three rows of the first `check_daemon.py` matched `"play (beat)    effect 199"` with the
  spacing guessed, and reported `0` against a transcript full of beats. The lines are normalised
  before matching now. The same run also counted a token that appears on both sides of the
  dismissal, which let "it beats before the press" be satisfied by beats that happened after it —
  the counts are split at the press.

- **2026-09-22 — the installer treats `~/.claude/settings.json` as the person's file, not the
  project's.** It prints the exact block first, never touches a hook it did not write (there are
  other hooks in there already, left from before), backs the file up, and writes
  through a temporary file with `os.replace` so a half-written `settings.json` cannot exist — that
  one would break Claude Code itself rather than only this. It refuses outright on a settings file
  that does not parse, because rewriting what we cannot read loses whatever is in it.

- **2026-09-22 — two daemons on one `var/events` say nothing about each other, and the log you are
  reading may not belong to the process you are watching.** Task 12's by-hand check ran with a
  daemon already up from before the edits. The clicks worked perfectly and the transcript being
  read showed no sign of them, because that transcript belonged to the older process — which had
  no menu bar at all, kept tailing the same file, and kept playing the same sound. Both processes
  answered the same events, and nothing anywhere said there were two. The menu bar half-fixes this
  by accident (two daemons are two identical items in the bar, which is at least visible), but
  `var/events` has no ownership and the daemon does not check for a sibling. Worth a task of its
  own; it is not task 12's.

- **2026-09-22 — a desk check driven by `null` proves what the mirror ASKED FOR and nothing about
  the OS.** Every assertion in `check_menubar.py` would still pass if `macos.py` were a file full
  of `pass`, because the fake records the call either way. So `check_macos_seam.py` reads each
  answer back out of AppKit's own object: the title off the real `NSStatusButton`, the click via
  `performClick_` rather than by calling the Python handler (a misspelled selector passes the
  direct call and never fires in the menu bar), and `afplay` confirmed running and then confirmed
  dead after `stop()`.

- **2026-09-22 — the slot swap costs 0.7 s, the cry 1.5 s, and the policy holds at the desk.**
  Task 13 walked end to end against the ball: connect at 18:49:03, the cry in the slot one second
  later (16 frames, 1.5 s — inside the 1.3-2.6 s `docs/PROTOCOL.md` §7.3 measured), a `done` at 18:49:13
  firing `213` with **no upload on its path**, the first silent pulse at 18:49:43 uploading the mute
  (2 frames, 0.7 s) and skipping its own flash, the second pulse at 18:50:13 free, B on the ball
  dismissing at 18:50:37, and the cry going back in 1.6 s while nothing waited. The mute being two
  frames is why the skipped flash is cheap: a swap the other way costs twice as long as the beat it
  would delay.

- **2026-09-22 — `asyncio.Event.clear()` before the wait, not after, silently eats a beat.**
  `Ball._wait_for_work` cleared its wake flag and then waited, so anything set while the previous
  beat was still on the wire was thrown away — and a beat is not instant, since `link.send` retries
  three times at five seconds apiece. The symptom is the worst kind: the daemon logs `play (beat)`,
  the ball does nothing, and no line anywhere says a beat was lost. Worse for the cry restore,
  which is woken by the queue emptying and has no later beat coming to wake it again. Clearing
  *after* the wait costs an occasional spurious wake, which finds no beat and a slot already right.
  Found by re-reading the worker, not by any check — the fake-link table passes either way, because
  nothing in it is slow enough to overlap.

- **2026-09-22 — the ball played the cry in the dark, and nothing in the log said so.** Task 13
  went to the desk with the audio slot perfect and no LED resource ever uploaded. The cry was
  heard; the ball never lit. The silent pulse was then a resource of silence with no colour behind
  it — literally nothing — while the daemon printed `play (pulse)` on schedule. Colour is a
  **separate resource of kind 3** riding the same `0x08` opcode, told apart by the kind byte, and
  it is **one frame** against the cry's seventeen. So it is the one write that may sit on a beat's
  path, and it must go **before** the effect: an LED resource is not state that can be read back,
  so a colour written after its effect dresses the next beat instead of this one. On a config where
  every kind shares one colour that mistake is perfectly invisible, which is why `ColoursAfterTheEffect`
  is a mutant in `check_ball_mirror.py` and not a comment.

- **2026-09-22 — the strongest row in any of these checks is the one whose answer this repo did not
  write.** `resource.led_blob(index)` rebuilds all six LED resources that three sniffer
  captures hold, byte for byte, from the index alone. That is what makes 138 Pikachu's colour rather
  than a number someone liked: the twenty constant bytes, the little-endian field and the index are
  confirmed against artefacts nobody here can edit. A separate sweep covered
  145 more and records what each reads as to the eye — 7 green, 45 red, 17 yellow — so telling
  `done` from `needs` by colour is a choice, not a thing still to be built.

- **2026-09-22 — the cry was the right creature and the wrong recording.** `assets/cries/pikachu.wav`
  was PokeAPI's game cry converted locally. The ball's own file had already been captured, as
  `var/cries-local/pikachu.wav`, byte-identical to `var/captures/pikachu-cry.wav` — lifted
  out of the sniffer capture, so it is the file the Switch uploaded, and it is the one that says
  *"Pika-chu"* aloud. 8282 bytes, 17 frames, and `normalise_wav` is a no-op on it, which is the
  check that it really is the ball's own.

- **2026-09-22 — the probe said activation was broken, and the probe was the broken thing.**
  Raising a window is two acts: `kAXRaiseAction` puts it in front of its own app's other windows,
  and activating puts that app in front of every other app. The first worked immediately; the
  second appeared not to — `focus("Spotify")` returned `True` and `NSWorkspace.frontmostApplication()`
  still said `Code`, three ways of activating in a row. All three were working. `NSWorkspace`
  refreshes that property off notifications, and a script with no run loop never spins one, so it
  answers with whatever it knew at launch forever. Spinning the run loop for 0.8 s after each
  attempt made every one of them correct. The daemon is unaffected — it pumps AppKit every 0.25 s
  for the menu bar already — but the near-miss is the lesson: the failure a wrong theory predicts
  is exactly what a blind probe produces, and "it returned True but nothing moved" is a claim about
  two things, only one of which had been checked.

- **2026-09-22 — `activate()` is not on `NSRunningApplication` here, and `hasattr` hid it.** The
  written-for-the-future branch `if hasattr(running, "activate")` looked like forward compatibility
  and was dead code: PyObjC 12.2.2 raises `AttributeError` for it, so every call took the
  deprecated `activateWithOptions_` path. Which works — measured, from a process with no activation
  policy of its own, on Darwin 25.6. The branch was removed rather than kept: an untested path that
  is never taken is not compatibility, it is a second implementation nobody has ever run.

- **2026-09-22 — the first Accessibility call in a process costs half a second.** Measured on this
  desk: 450 ms for the first sweep, then 4–8 ms for every one after it, across fourteen apps with
  windows. The raise itself is about a second from a worker thread against ~200 ms on the main one.
  It runs on the worker anyway: on the loop, a wedged app costs `timeout` plus one app's messaging
  timeout with no beat, no menu bar and nothing read from the events file, and a notifier that goes
  quiet in order to raise a window has it backwards. A desk check that pins a cold number pins the
  framework waking up, so `check_focus.py` prints the cold one and holds only the warm one.

- **2026-09-22 — macOS will not revoke a permission on request, so half of criterion 10 is manual.**
  `AXIsProcessTrusted` answering `False` is faked by a whole stand-in ApplicationServices, which
  proves our branch and nothing about what macOS says when the box is unticked. Its sibling refusal
  — the framework missing altogether — is real, blocked through `sys.meta_path` so the `ImportError`
  comes from Python's own import machinery. The part that cannot be faked is written down as a
  manual step in `docs/DESK-CHECKS.md` rather than quietly counted as covered.

## Task 15 — The desk-check pass

- **2026-09-22 — a locked screen is the ordinary case for a notifier, not an edge case.** It is the
  state you are in when a notification matters at all: you walked away. And macOS answers every
  window title as its own app's name while locked — `Code` reports `['Code','Code','Code']` — so
  the sweep found nothing and said, accurately, that no window carried the project. True, useless,
  and about the wrong thing: it described what the process could read, not what was on the desk.
  `CGSessionCopyCurrentDictionary()['CGSSessionScreenIsLocked']` is the one that answers the real
  question, it lives in ApplicationServices already, and the refusal now says the window will be
  where you left it. The near-miss worth keeping: the false answer was *plausible*, which is what
  makes it dangerous — a wrong absence looks exactly like a right one.

- **2026-09-22 — a signal disappeared and no line anywhere said so, in the feature whose whole
  point is that nothing disappears quietly.** Pressing B while already attending skips to the next
  (criterion 7), and the entry you were on is dropped from the queue, not restored by the snooze,
  not mentioned by any mirror. Nine desk checks were green and none of them could see it, because
  every one of them asks "did the right thing happen" and this was a thing that *stopped*
  happening. Only a transcript read end to end as prose showed a `needs · wobble` that was there
  and then was not. Settled the same evening, and it settled a principle rather than a case:
  **finishing something is closing its session.** No press of B ends a signal — B chooses what you
  are dealing with, and a prompt is what says you dealt with it. So the skipped one goes back into
  the queue through the same `Queue.restore` the snooze uses, into the place it had, and a second
  press on a lone signal hands it straight back rather than making it go away. `spec.md` criterion
  7 said only "skips to the next pending"; what happened to the one skipped was never written, and
  unwritten is how it came to be dropped.

- **2026-09-22 — order matters inside `dismiss`, and getting it wrong is an infinite B.** The next
  entry is read from the queue *before* the skipped one is put back. Restoring first can make the
  one just let go the top again, and B would hand you the same signal forever — a bug that would
  look exactly like a stuck button, which is the failure this project already knows how to
  misread (task 07).

- **2026-09-22 — the menu bar item a desk-check daemon puts up is a real item, and a real click on
  it is a real B press.** `check_daemon.py` failed one row with `2` where it wanted `1`: a second
  press arrived mid-run from the menu bar while somebody was back at the desk. The row was pinning
  the script's arithmetic — "exactly one focus verdict" — rather than the daemon's rule, which is
  "every press that took something says what became of its window". Counted against the presses,
  a stray click changes both sides and the row still means what it says. The near-miss: the first
  reading was "a regression from the skip change", and it was not.

- **2026-09-22 — one end-to-end run cannot reach a criterion that needs a different episode.**
  `check_daemon.py` drives a single episode, so it sees exactly one of the snooze's two endings,
  never the silent pulse (30 s behind the cry it follows), and never a press into an empty queue —
  a shape no episode with work in it produces. Adding assertions to the one run would not have
  helped; what was missing was other runs. `check_criteria.py` is five separate daemons, each with
  a fresh events file, because the queue lives in the process and a leftover entry from the run
  before is the contamination that makes a green row mean nothing.

- **2026-09-22 — a desk check that scans for a ball is a hazard next to a live link, and
  `check_daemon.py` is the one that does it.** Every other script is `--no-ball`. Running the
  check-all while a session is holding the ball starts a second CoreBluetooth scan against hardware
  someone is mid-measurement on; it happened once during this pass and the link survived, which is
  luck and not a result. New desk scripts default to `--no-ball` and say why in their docstring.

- **2026-09-22 — the hook costs 10 ms, so criterion 1's ~2 s is not spent where it looks.** Timed
  five times through the real `tools/hook_event.sh`. With the daemon's 250 ms poll and a `done`
  beat that carries no upload on its path, the whole Mac-side path is under a third of a second.
  Whatever the ~2 s is eventually spent on, it is the radio and not us — which also means the
  budget is there to be spent, and a future change that puts an upload back on a beat's path would
  not show up as a slow number anywhere until it was felt.

## Task 16 — The pulse that was never seen, and the prompt nobody typed

- **2026-09-22 — watching the daemon's own log from inside a Claude Code session made the log an
  event source, and it resolved a real signal.** A file-watcher was armed on `var/daemon.log`; each
  new line woke the session, each wake was a `UserPromptSubmit`, each `UserPromptSubmit` was a
  wobble event appended to `var/events`, which the daemon read, which produced another log line.
  Eighteen of that file's thirty lines were the loop. One of them did damage —
  `resolved done · wobble — you were there` — a pending signal marked attended because something
  was *reading about it*. The fix is not "do not tail the log": that is the shape the defect
  happened to take. Any background task finishing in any session was resolving that session's
  signal, and always had been. Criterion 5 reads `UserPromptSubmit` as a person arriving, and it
  is not only that.

- **2026-09-22 — the two payloads are identical, so the text is the only evidence there is.** The
  tempting move was to look for a flag. Dumped side by side, a turn a person typed and a turn the
  agent started carry exactly the same eight keys — `cwd`, `session_id`, `prompt_id`,
  `permission_mode`, `prompt`, `transcript_path`, `scratchpad_dir`, `hook_event_name` — and differ
  only in what `prompt` says. An injected one opens with a lone wrapper tag on its own line. So
  `hooks.by_person` matches a whole first line against `<tag>` and nothing cleverer, and the edge
  it gets wrong is written into the desk check rather than left to be discovered: a person whose
  entire message is `<hello>` is read as machinery, their signal stays pending and keeps speaking.
  That direction is deliberate — a lost notification is the silent failure, a stubborn one is the
  loud one.

- **2026-09-22 — a fixture for this could not be written by hand, and writing one would have
  proved nothing.** The shape a payload is imagined to have is the same shape the heuristic is
  written against, so a hand-made table agrees with the code for the same wrong reason.
  `check_hooks.py` reads real payloads captured out of `var/events` into `var/desk/payloads/`, and
  which file is typed and which is injected is decided by reading the transcript — never by asking
  the function under test. The injected one was caught live: a background recording finished and
  its notification wrote the payload the check now runs on.

- **2026-09-22 — the ball was not dark, it was blinking sixty seconds apart, and only a camera
  could tell the difference.** Filmed with a webcam in a dark room, brightness of the ball's centre
  button measured per frame. Three flashes: the cry at 5.8 s, then **60.1 s of nothing**, then two
  blinks 29.9 s apart. The 30 s pulse due after the cry had been spent uploading the mute and
  dropped, so the first blink was always the second one. "Heard the cry, but saw no ball blinking" was
  a precise description of a real defect, and every desk check was green through all of it because
  none of them ran for a minute.

- **2026-09-22 — the flash is 1.5 s long whatever is in the slot, which is a fact about the LED and
  not about the audio.** Measured 1.47 s, 1.50 s, 1.47 s across the three flashes. The cry is
  seventeen frames and the mute is two, so the effect's animation is plainly not driven by the
  resource behind it. It is the number that decides what a pulse interval means: at `every_s: 3.0`
  the ball is lit about half the time. Nobody had measured it because nothing had needed it — the
  old pulse was 30 s apart, where a second and a half of light is a blink either way.

- **2026-09-22 — the audio told a different story than the video, and the audio was wrong.** A
  broadband RMS check put the third flash 15 dB over the room and read as a cry, which would have
  meant the mute had fallen out of the slot. Split into bands it falls apart: the real cry peaks at
  2 kHz with energy up to 3.5 kHz, the third flash peaks at 125 Hz with nothing above 1 kHz, and its
  spectrum is indistinguishable from a stretch of tape with no flash in it at all. It was somebody
  moving in the room. One number from one field, and it disagreed with the picture — the picture was
  right.

- **2026-09-22 — a rhythm cannot be checked by a table, because it only exists over time.**
  `check_ladder.py` proves the arithmetic in microseconds and `check_daemon.py` runs for twelve
  seconds; the shape of a `done` takes seventy. `check_rhythm.py` spends them, against its own
  events file so nothing reaches a live daemon, and `--no-ball` so nothing reaches a live radio.
  The two things it guards — the first blink following the cry by 3 s and not 60, and a beat not
  being joined by a pulse in the same breath — both passed every check that was faster than they
  were.

- **2026-09-22 — the running daemon is the old code, and no edit reaches it.** Everything here was
  written while a daemon started eleven minutes earlier held the ball. Python read its modules and
  its config at startup, so the fix exists in the repo and not in the process, and the only way to
  see it on the ball is a restart. That restart was not taken: reconnecting usually needs a press of
  the ball's top button, which is not something to leave somebody to come back to. Worth saying
  plainly because the log is convincing and shows the old behaviour perfectly — a daemon is not a
  version of the code, it is a version of the code *from when it started*.

- **2026-09-22 — a check wrote its own arithmetic into a row, twice, and the row was the thing that
  was wrong.** `check_rhythm.py` first asserted "every gap between blinks is 3 s" and failed with
  `[3, 6]`. The 6 s hole is the second cry: a beat wins the tick it shares with a pulse, because it
  flashes as well and a pulse beside it would be a second flash nobody asked for. The ball was lit
  right through the gap the row called a defect. The same mistake a second time in one hour, in
  `check_daemon.py`: a row asking that the silent pulse fire at all, in an episode that ended one
  second after the `done` got the floor. Both rows were written before the behaviour was watched,
  and both were describing what I expected the arithmetic to be. What fixed them is the same move
  each time — ask the question a person would ask (is the ball ever dark for more than 3 s?)
  instead of the question the implementation suggests (are the pulse timestamps evenly spaced?).

- **2026-09-22 — a row that cannot fail is worse than no row.** Fixing the one above left
  `check_daemon.py` asserting that no cry and no flash share a timestamp — in a transcript with
  zero flashes in it. It passed, it read as meaningful, and it was asking a question about an empty
  list. Found only by looking at *why* it went green. Two guards now: the episode is long enough to
  produce a flash, and there is a row asserting one exists, so the emptiness cannot come back
  quietly. The same reasoning killed a `sandbox.py` check comparing a copied script against the
  original it had been copied from a millisecond earlier.

- **2026-09-22 — the desk checks had been writing into the live daemon's events file all along.**
  `check_daemon.py` and `check_criteria.py` open by unlinking `var/events`, then fire real signals
  through the real hook script — so any daemon holding a ball counts a restart it never mentions
  and plays every phantom `done` the check invents. Nothing fails: `hooks.Tail` opens by path and
  handles the file shrinking, which is exactly why nine passes never noticed. It surfaced only
  because a live hardware session made it unsafe to run them. The fix needed no change to the
  shipped code: `tools/hook_event.sh` takes its path from its own location, so a *copy* of it one
  level under a temp directory writes there instead (a symlink will not do — it resolves its own
  path with `pwd -P`). Each run now proves the isolation rather than claiming it: fire one event,
  check the temp file grew and `var/events` did not.

- **2026-09-22 — the probe that found the bug cannot confirm the fix, and it took a reference leg
  to notice.** The camera is what caught the pulse waiting for the beats to run out, so it was the
  obvious instrument for checking the new rhythm on hardware. Both of its legs turned out to be
  blind. Luma, in a lit room: baseline 54.6 ± 1.2, the LED lifts a tight crop by 1.4–1.8, and a
  detrended 4σ search finds 0 events — the flash is inside the noise. Audio: a spectral matcher
  (hand-rolled Goertzel, nine bands; numpy is not in the venv) built from the real
  `assets/cries/pikachu.wav`, which is ADPCM and needs decoding before `wave` will open it. Slid
  across the recording it found nothing cry-shaped at either predicted second, and the temptation
  was to report that the ball had gone quiet. The reference leg said otherwise. Injecting the
  template into that same room noise at 0.35× the room peak, the matcher finds it 3.1σ clear in the
  top three windows — so it looked sensitive. Run against the *earlier* film, where the ball
  demonstrably cried, its best match is 8.59 — no better than the 7.97 in the take being judged.
  It cannot see a real ball cry at all. The injected reference shared the probe's own assumption
  (that what reaches the microphone resembles the source `.wav`); a small band-limited speaker
  playing ADPCM across a desk does not. Two rules, both of which already existed and neither of
  which I applied in the right order: calibrate on a real artifact, not a fixture you made, and an
  empty result is a claim about the query first. Had the reference leg been run first it would have
  cost one command and saved the whole audio detour. Recorded in `docs/DESK-CHECKS.md` as a table
  of what this camera can and cannot see, because the next person will reach for it for the same
  reason I did.

- **2026-09-22 — two numbers that share one resource were never independent, and the config had
  them in separate lines.** The fix for the dark ball set the blink interval to 3 s. Pikachu's cry
  sounds for 0.96 s but reaches the ball as a 17-frame upload, so the first blink after it — itself
  an upload of the mute, over the same single audio slot — landed while the cry was still coming
  out. Heard at the desk as a cry that comes out fast and chokes. Nothing else could see it:
  `check_rhythm` measures when a beat is *due* and has no way to know what an upload does to a
  sound already playing, and every other table finishes in a millisecond. `pulse.every_s` and the
  length of the cry had been chosen in different sessions for different reasons, and the one audio
  slot ties them together — so they are one decision wearing two names. Fixed with
  `pulse.after_beat_s`, a quiet the cry keeps to itself, which is a third number and therefore the
  same trap one step out: the daemon reads the length of whatever `--cry` points at and takes the
  longer of the two, so a bigger `.wav` cannot walk back into this silently. The general form is
  worth keeping: when a fix picks a number, ask what else is contending for the thing that number
  is spending.

- **2026-09-22 — the desk check was measuring the person running it.** `check_rhythm.py` puts a
  real item in the real menu bar for 70 seconds, and a click on it is a real B press: the signal
  gets attended and the beats stop. It happened twice — one stray press, then six inside five
  seconds — and both times nine rows confidently described a schedule that a finger had ended. I
  never established the cause and did not pretend to: `--no-menubar` removes the item, so there is
  nothing to click, and a first row counts B presses so that any future interference is named
  instead of being laundered into a verdict about the code. The move that mattered was refusing to
  explain the number. A check sharing a surface with its operator is measuring the operator too,
  and the fix is to take the surface away rather than to reason about who touched what.

- **2026-09-22 — a row that asks two questions fails for the wrong one.** After the cry was given
  five seconds, one row went red: "never flashes twice in one breath", with a 1 s gap in the
  series. The tempting reading was that the blinking had sped up, and the tempting fix was to widen
  the bound until it passed — which would have been tuning a constant to silence a measurement. It
  had not sped up. Blinks run on a 3 s grid and the cry now pushes that grid 5 s clear, so the grid
  no longer coincides with the next cry 30 s later: the last blink lands at 29 s and the cry at 30.
  The row had been asking "does the blinking stay slow?" and "does a blink crowd a cry?" at once,
  against one merged series and one bound, and those have different answers. Split into two rows
  with two bounds and two reasons, both green. The second one's bound is a measurement rather than
  a preference — the LED is lit 1.47–1.50 s per flash, so a blink within a flash of a cry is still
  lit when the cry lights up (one continuous light) and what actually needs ruling out is the
  middle: a blink ~2 s ahead, which goes dark for half a second and then fires, and reads as a
  fault. When a green row goes red after an unrelated change, check whether it was one rule or two
  before touching its number.

- **2026-09-22 — the branch that only matters while nobody is at the desk, and the only way to find
  it was to go and look.** "Stay quiet while I am looking at that session" turns on reading the
  title of the window in front. The obvious implementation is right all day and wrong at night: with
  the screen locked, the window server still reports a layer-0 window, and the accessibility read of
  its focused window's title comes back as `'Code'` — the *application's* name, not the window's.
  Read live off this Mac, not reasoned about. So a project in a folder called `Code`, `Finder` or
  `Terminal` would have read as the window you are looking at for exactly as long as nobody was at
  the keyboard, silencing the notification during the only stretch where a notification is the whole
  point, and failing in a way indistinguishable from a quiet afternoon. No fixture could have found
  this: any fake I wrote would have answered whatever I thought macOS answers. The general rule is
  the one already in `approach.md` about real artifacts, in the shape it takes for platform code —
  **a fake is an encoding of your belief about the platform, so the branches worth the most are
  exactly the ones a fake cannot testify about.** `check_watching.py` now asks the real framework
  whether this desk is locked and, when it is, turns that into a row: macOS would have said `'Code'`
  and the seam refused it. It runs whenever the desk happens to be in that state, which is free.

- **2026-09-22 — the second time the obvious way to ask "what is in front" would have been stale
  forever.** `NSWorkspace.frontmostApplication()` refreshes off notifications, so in a process with
  no run loop it answers with whatever it knew at launch — measured earlier in this spec, where it
  made three working window activations look broken. It would have been the natural call here too,
  and the daemon has no AppKit run loop under `--no-menubar`. Reading the front window off
  `CGWindowListCopyWindowInfo` instead costs a measured 0.5–2.1 ms warm (median 1.0, n=20) against
  ~154 ms for the first call in a process, and that cold cost is paid once, before the loop, by the
  startup line that prints the title it can actually see. The rejected alternative was spinning a
  run loop to keep the cache warm: a background thread and a lifetime to manage, to make a wrong
  call right, when a right call was one function away. **A cached accessor that never invalidates
  does not look broken — it looks confident**, and that is twice now in one spec.

- **2026-09-22 — a broken probe produced exactly the failure the wrong theory predicted, in a check
  written to catch broken probes.** A row in `check_watching.py` asserted that the "cannot see what
  is in front" sentence does not borrow `Focus`'s sentence about raising a window, and it did it by
  searching for the word `"raised"`. The sentence it was checking legitimately ends "…the session
  that **raised** them" — the signal, not a window — so the row went red against correct text. Thirty
  seconds from editing the production string to make a test pass. The fix was to match the phrase
  that actually belongs to the other layer (`"no window was raised"`), plus a second row asserting
  that *that phrase still exists in `macos._AX_WHY`* — because a guard written against wording is a
  guard that passes forever once the wording it guards against is reworded, and passing forever is
  not the same as being satisfied. **When a probe matches on prose, check the prose is still there,
  or the probe retires without telling you.**

- **2026-09-22 — quiet is not resolved, and the difference is a clock nobody can see.** The ask was
  "if I am still focused on the terminal, no need to notify", and the cheap reading of it is "skip
  the beat". That reading is wrong in a way that costs you the notification: a `done` watched as it
  arrives would spend both its cries in silence while you read the output, and then never speak.
  What the feature actually is: the entry stays pending, both mirrors keep the count, and the
  signaller's **clock stops** — so looking away plays the cry at that second rather than one
  interval later, and a glance away and back does not produce a second one. None of that is visible
  at the desk; it is a difference between two timelines that both look like "it went quiet". Which
  is why `check_watching.py` spends nine rows taking the timeline apart second by second against the
  real ladder, and why three of its ten mutants (`NeverFreezes`, `SpendsTheTime`, `ForgetsTheBeats`)
  exist only to break those rows. The layering fell out of the same question: the seam answers the
  plain fact (the title of the window in front) and the *match* is a substring — ordinary string
  work with no operating system in it — so it lives in the core as `Entry.in_window`, checkable
  with no Mac in the room and inherited by a second platform rather than reimplemented. Not knowing
  what is in front always falls to "signal", which is principle 7 written as a direction rather than
  as a wish.

- **2026-09-23 — a fixture that names the repo it lives in stops being a fixture the moment a rule
  starts reading the room.** Task 17 made a signal stay quiet while the window it belongs to is in
  front. Every desk check that drives the daemon fires signals for the project `wobble`, because
  that is this repo — so from the moment the rule landed, three of them had a verdict that depended
  on which window was last clicked. It did not show up for two days because the screen was locked
  for every run in between, which is the one state where there is no window in front at all: the
  environment was hiding the defect in one direction and then revealed it in the other, and neither
  day's result was a fact about the daemon. Worse than the failing rows was the run *before* them,
  where `check_daemon` passed first and failed second — its own B press raises the `wobble` window,
  so it poisons its own precondition and the second run measures a different desk. **A check that
  passes or fails on the order you run it in is not a known-answer check, and nothing in a
  known-answer table can say so.** The two fixes are different on purpose: a check that does not
  care which project it is should name one no window can be titled after (and a *longer* hint
  cannot be a substring of a shorter title, which is the direction that makes it safe), while a
  check that genuinely needs the real name reads the desk first and refuses with the reason — using
  the daemon's own `Entry.in_window`, because a guard that made its own judgement could disagree
  with the thing it is guarding.

- **2026-09-23 — the mutant that proves a convention is not the mutant that breaks the code.** The
  seam tags each menu item with its index in the list the mirror handed over, and a separator takes
  a slot in the handler list so the two stay aligned. The obvious way to check that is to choose
  *Quit wobble* and see the quit handler run. It does not work: a seam that re-tags from zero *and*
  drops the separator from the handler list is internally consistent and behaves perfectly — every
  behavioural row passes against it, because it is not a defect, it is a different convention. What
  actually bites is half that edit, deleting `handlers.append(None)` and leaving the tag as the
  mirror's index, and it bites as an `IndexError` raised inside a menu handler, which is inside
  `pump()`, which is inside the daemon's tick. Both were run before the comment above the row was
  written; the first draft of that comment said choosing Quit "would do nothing at all, silently",
  which is what I believed and not what either mutant did. **A row that pins a convention rather
  than a behaviour has to say so, or the next person deletes it as redundant with the rows below
  it** — which are the ones that cannot catch this.

## Task 19 — What it did while you were out

- **2026-09-23 — the log file everybody referred to was nobody's.** `var/daemon.log` is cited in
  DESK-CHECKS, in this file and in `src/mirrors/ball.py`, and it was read all session as though the
  daemon wrote it. Nothing in the repo writes it: it is the residue of one `> var/daemon.log` typed
  by hand on 2026-09-22 at 20:39, and it had been frozen since 20:40. The daemon has only ever
  printed to a terminal. **A file that three documents describe is one nobody checks the provenance
  of** — `grep -rn daemon.log --include='*.py'` was the whole investigation and it took a second,
  after a day of quoting the thing.

- **2026-09-23 — a second copy of the evidence is a second version of events unless it is byte for
  byte the first.** Five desk checks parse the daemon's stdout, matching tokens and counting lines.
  The tempting shape for a log is `logging`'s own — a level, a logger name, its own timestamp — and
  it is readable and completely wrong here, because the moment the file and the screen differ, a
  disagreement between them has no resolution and both stop being evidence. So `say()` builds one
  string and hands the same string to both, `Daily`'s formatter is `%(message)s`, and the
  end-to-end row in `check_log.py` compares the file to the process's own stdout line for line
  rather than checking that the lines "look right".

- **2026-09-23 — `TimedRotatingFileHandler` rotates the wrong way round for this.** The stdlib's
  daily handler keeps a live `wobble.log` and renames it to `wobble.log.2026-09-22` on rollover, so
  today's lines — the ones you want — are in the file whose name tells you nothing, and yesterday's
  move after the fact. Monolog's `daily` driver, which is what was actually asked for, picks the
  name from the date as each line is written. Writing that is about forty lines and the stdlib's is
  one, and the one is still the wrong answer: **"use the standard handler" is a claim about effort,
  not about behaviour**, and the behaviours differ in the only place a person interacts with a log.

- **2026-09-23 — a sweep that deletes by mtime empties the directory the first time it is
  restored.** Retention needs an age, and the age on disk is free while the age in the filename
  needs parsing. Every mtime in a directory that has been copied, restored from a backup or synced
  is the copy's, so a by-mtime sweep either keeps everything forever or takes the lot, depending on
  which side of the window the restore lands. The check plants both confusions — an old name with a
  fresh mtime, a fresh name with a 400-day-old mtime — because a test that only plants files that
  agree with themselves cannot tell the two rules apart.

- **2026-09-23 — the interesting decision in a logging change is where the file goes, not how it is
  written.** Pinned at `var/logs`, every desk check in this repo would have written thirty lines
  into the real record on every run, which is precisely the defect already paid for once on
  `var/events` and written up under task 16. The log follows `--events` instead: a check whose
  daemon reads a throwaway events file logs into that throwaway tree, automatically, and not one
  desk check needed a line adding to it. **The second time a mistake shows up it is a class, and
  the fix belongs in the mechanism rather than in a rule telling people to remember.**

- **2026-09-23 — the count on the bar was answering a different question from the one being read.**
  It said `2` with one terminal open and both entries were real: a signal fired by hand for a desk
  check and the session doing the work, in the same folder. Nothing was broken. The queue was
  counting *signals waiting* and the bar is read as *places to go and look*, and those are the same
  number only by accident. The fix was not a filter — it was noticing that `Entry.in_window` had
  already conceded the point, because it matches on the folder name and so cannot tell two sessions
  in one folder apart either. **A count is a sentence; when it looks wrong, check the noun before
  checking the arithmetic.**

- **2026-09-23 — the tidy version of a merge is the one that loses something quietly.** Collapsing
  a project to a single row reads as obviously right and costs one line of code; what it throws
  away is the session that finished *underneath* the blocked one, with nothing ever said about it.
  A merge that loses nothing and a merge that loses everything look identical in the diff, so the
  rule is to **name what is on the losing side before agreeing to it** — here, that answer was "a
  `done` you never hear about", which decided the design in one sentence. The entry keeps its
  sessions and falls back; `queue.sessions()` exists for no other reason than to let a check prove
  the view collapsed and the contents did not.

- **2026-09-23 — a sentence in a config that reads like a measurement is worth less than no
  sentence at all.** `needs.mac_sound` carried a note saying Sosumi was chosen because it was
  "short enough not to run into the next beat 1.5 s later, which Submarine and Hero are not". It
  has the shape of evidence — three named files, a threshold, a comparison — and `afinfo` refutes
  every clause of it: Sosumi 1.539 s, Submarine 1.492 s, Hero 1.056 s. The one it named as safe was
  the only one over the beat, and both it ruled out were shorter than it. This repo asks every
  number to cite its source precisely so that provenance is not folklore; **a citation to a
  measurement nobody made is worse than an admitted judgement**, because a judgement invites a desk
  check and a false measurement closes the question. The replacement says which numbers came from
  `afinfo`, which came from the ear, and that the whole sound is a stand-in.

- **2026-09-23 — when two surfaces have to agree, the config names the other one rather than
  repeating it.** A `done` had to sound the same on the Mac as on the ball. The obvious write-up is
  the cry's path in `config/signals.json` beside the ball's, and it works until someone passes
  `--cry` and gets Pikachu in the ball with a stock chime on the speakers — no error, no symptom
  except the notifier saying two different things about one event. `"@cry"` is a token resolved at
  load, so there is one fact and one place holding it. **The test for this shape is not "are the two
  values equal today" but "can they be made unequal by editing one of them".** The desk check asks
  the second question: it loads the config twice with different cries, and the mutant that answers
  the token from the shipped path is caught by exactly the rows that are about the override.

- **2026-09-23 — the mutant worth writing first is the code as it shipped.** Task 22's controls are
  three versions of `Attention.ended`, and the one that earns its place is `NeverEnds`: a closing
  session that changes nothing. That is not an imagined defect, it is what the daemon did for four
  days, and nobody noticed because the symptom — an entry that will not go away — looks exactly
  like a signal you have not dealt with yet. **A mutant that reproduces the bug you just fixed is
  the only one guaranteed to be reachable**, and the row it breaks is the row that proves the fix
  is load-bearing rather than incidental. The other two here are near misses invented afterwards,
  and both are cheaper to trust because the first one is in the list beside them.

- **2026-09-23 — two hooks that mean similar things are the place a shortcut costs most.** A prompt
  and a session ending both take an entry out of the queue, and `ended` delegating to `prompted`
  would have passed every row about one session in one project. What it would have broken is the
  folder holding two: a prompt ends the hold because you demonstrably went to that window, and
  closing one tab proves nothing about the `done` still waiting behind it. The rule that separated
  them is that **the hold is about where you are, not about what is left** — so it survives a close
  and ends only when the entry it was holding has emptied. The mutant `EndReleasesTheHold` is that
  shortcut, kept so the next person to notice the two functions look alike finds out why they are not.

- **2026-09-23 — the quiet-while-you-watch feature leaks a cry, and the seam is not the reason.**
  Found while running the Part A checks after task 22: `check_watching` failed one run in four, on
  one row — "…and the leg you are looking at plays nothing", with a beat one second before the
  `not signalling` line. Measured rather than guessed, and the first two theories died:
  - the seam is solid. `macos.Frontmost().title()` read 85,608 times in 60 s from a standalone
    process returned the same title every time, none blind, slowest 201 ms. So a transient
    `(None, None)` — which by design lets a signal speak (principle 7) — is not what happened.
  - it is not one unlucky poll either. Firing 20 watched signals at a daemon by hand, **6 escaped**,
    clustered inside one 8-second window rather than spread out. Immediately afterwards, with a
    different window in front, the same probe scored **20 quiet, 0 escaped**.
  So it depends on WHICH window is in front — a video-call window leaked, a chat window did not —
  and a standalone read of that same window's title cannot see the difference. What has not been
  tried: sampling the title from *inside* the daemon at the moment it decides, which is the only
  place the two readings can be compared. Left open on purpose rather than half-fixed; the probe is
  `var/desk/` material and the theory to kill next is that the daemon's own process is a window
  server client (it pumps a status item) and the standalone probe is not.

## Task 21 — The queue in the menu

- **2026-09-23 — a module you patched for somebody else is patched for you.** The smoke script ran
  the real daemon in process and needed its coroutine rather than its event loop, so it replaced
  `asyncio.run` — and `daemon.asyncio` is not a copy of `asyncio`, it is the same module object, so
  the script's own `asyncio.run(go())` a few lines later hit the stub, did nothing, and the run
  exited 0 with no output at all. A silent success is the worst shape for this: nothing said the
  daemon never started. The fix is one line — put the real function back the moment the coroutine
  is captured — and the general rule is that **monkeypatching a shared module is not scoped to the
  code you were aiming at**, so the window between patch and restore has to be as short as the
  thing you actually wanted.

- **2026-09-23 — a race you cannot provoke may be one the code cannot have.** The plan was to
  demonstrate the stale click live: open the menu, let the queue move underneath it, choose a line
  that no longer exists. It could not be made to happen, and the reason turned out to be
  `Status.menu()` — it mutates the same `NSMenu` object every rebuild rather than making a new one,
  so a reference held by an open menu is never stale in the way a Python list would be. That is a
  property of the seam, not luck, and the failure it *can* still have (a click delivered after the
  core has moved on) is covered by rows and a mutant in `check_attention` instead. Worth the hour:
  "I could not reproduce it" and "it cannot happen here, and this is why" are different answers,
  and only one of them survives the next refactor.

- **2026-09-23 — which mouse button arrived is the one thing the checks cannot tell you.** After
  the gestures swapped, the obvious next move was a row proving a right-click presses B. There
  isn't one to write: the branch reads `NSApplication.currentEvent`, which AppKit sets while
  dispatching a real mouse, so any `NSEvent` built in the check and handed to `clicked_` is the
  check agreeing with its own idea of the event. What a check *can* hold is everything around it —
  a plain click really crosses the seam via `performClick_`, it opens the menu, it is no longer B,
  and B is the handler `on_click` was given sitting on the other branch. The rest is a hand on
  hardware, and the honest thing was to put it in `DESK-CHECKS.md`'s open threads rather than to
  write a row that would pass whatever the wiring did. The old screenshot does not close it either:
  it proves the seam tells the two gestures apart, and the swap exchanged exactly the two branches
  it was evidence about.

## The hardware round — the rhythm on a real ball (2026-09-23)

- **2026-09-23 — the rhythm rewritten on 2026-09-22 ran on the ball, and what came back from the
  room was the config.** `12:57:56` the cry, five seconds of quiet, a silent flash every three
  seconds, the second cry at `12:58:26` — thirty seconds to the second — five seconds again, then
  flashing to B at `12:58:46`. Reported without the transcript in sight as *"pikachu first, then
  the pulse, pikachu again, pulse, and the B button brought it forward here"*. It matters that this is the **first**
  daemon in front of an eye that was started *after* the change: the 60.1 s film (task 16) was shot
  against a process still running the code it was launched with, so every sighting before this one
  was of the old shape wearing the new config's name.

- **2026-09-23 — the 5 s cry gap held, and the log cannot say by how much.** The second cry found
  the mute in the slot, waited `1.7 s` for its seventeen frames and sounded at `12:58:28` against a
  beat scheduled for `:26`; the next pulse came at `:31`, five seconds after the **scheduled** beat
  and not after the sound — which is exactly the arithmetic `_source_gap` was written from, seen on
  a live link for the first time. The quiet the cry got to itself was therefore about three
  seconds, against an effect lasting 1.5 s. **The flash and the voice are one effect and run
  together** — 0.96 s of audio *inside* 1.47–1.50 s of light, not after it — so adding them is the
  easy mistake here, and it was made once in this session before the film's own measurement caught
  it. What the round proves is a gap with room in it and no choke; what it cannot prove is the size
  of that room. `src/log.py` stamps to the second and every quantity in this paragraph is one to
  three seconds long, so the instrument is coarser than the thing measured. A number wants the
  camera that produced the 1.47–1.50 s in the first place.

- **2026-09-23 — a new field on the ladder nearly turned four mutant controls green for the wrong
  reason.** `check_ladder` ends by recasting the shipped ladder into four classes with one cadence
  rule removed, and every one must break the table. `_recast` rebuilds the dataclass field by field,
  so `after_prompt_s` — added with a default, unlike `snooze_s` — silently arrived as `0.0` in all
  four. The new row pinning it at 5.0 would then have failed in every mutant run, printing `caught`
  four times while the rules each mutant exists to break went unexamined. The shape of this is
  general and worth keeping: **a control that checks "something broke" is defeated by anything that
  always breaks**, and a field with a default is exactly the kind of thing that arrives everywhere
  at once. The same file already warns about it in another register — the `refuses()` helper whose
  first candidate token was `.json`, present in every message.

- **2026-09-23 — two look-aways in the same log, and only one of them is a measurement.** At
  `13:07:45` a `done` that had been watched for 4 min 42 s cried in the same second as the eye
  moving away, and nothing at all happened in between: with two beats 30 s apart, a clock left
  running would have spent both inside those 282 seconds, so the same-second cry is the freeze and
  not a coincidence. At `13:14:33` the transcript reads identically — `signalling … you looked
  away`, then the beat, same second — and proves nothing, because B had attended and let go of that
  entry four seconds earlier, and a let-go changes the signaller's key, which makes the next beat
  due at once for reasons that have nothing to do with watching. Two indistinguishable pairs of
  lines, one load-bearing. **The evidence is what did not happen during the gap, and that is the
  part a grep for the interesting line never shows you.**

- **2026-09-23 — the fix for a stall was one line of earlier measurement away from making the stall
  louder.** A `needs` beat falls every 1.5 s and the wire's send is 3 attempts of a 5 s ack
  deadline, so one unanswered frame held the mirror's only worker through ten beats. The obvious
  repair is to give each beat its own gap as a budget, and the obvious way to spend a budget is to
  divide it by the attempts: 1.5 ÷ 3 = 0.50 s. It was written, the checks were green, and the
  number was wrong — `docs/PROTOCOL.md` §9 measured the ack itself at **0.52–0.61 s** on an established
  link, so every healthy frame would have been retried twice, the effect written three times, and
  the beat reported as `BALL SILENT` after the ball had played it. A fix that reads perfectly and
  makes the reported defect worse. Two things worth keeping. **A deadline is only ever shortened
  against a measured latency, never against a schedule** — the schedule says what you can afford,
  the measurement says what is possible, and a budget under the measurement buys nothing at all.
  And when there is no room for both, spend the budget as **fewer attempts rather than shorter
  ones**: `needs` now gets one write and no retry, because the next beat 1.5 s later is a better
  retry than a second write inside a deadline the ball cannot meet. The measurement that settled
  it — link reliability and timing — had been on record the whole time: the cost here was not that
  the number was unknown, it was that a timeout was chosen from arithmetic when a measurement
  existed.

- **2026-09-23 — `check_rhythm` fails under load, and the failure looks exactly like a regression.**
  Twice in one session it reported *the blinking never speeds up — WRONG: 2* while four other desk
  daemons were running; four runs on a quiet machine, two with the change and two with it stashed,
  came back **byte-identical and clean**. The failing series is the tell rather than the verdict:
  same 21 pulses, same 5→68 span, same 3.15 s mean, differing only in which side of a second
  boundary each stamp fell on — `src/log.py` stamps to the second and a 3.0 s cadence sampled at
  1 s reads as 4, 2, 4, 2 whenever its phase sits on the boundary. Worth keeping twice over. **A
  check that times a schedule is measuring the machine as much as the code**, so a red row from one
  belongs in a reference leg before it belongs in a diagnosis. And the structural argument was
  available before any of the reruns: `--no-ball` never constructs the `Ball` mirror, so no change
  inside `_play` can reach this check at all — cheaper than four minutes of daemons, and it was the
  reason to suspect the instrument first.

## Task 35 — the stroll slots (2026-09-25)

- **2026-09-25 — what the desk answered about the stroll ids, which is what the map was built on.**
  `9` and `10` buzz once at the start of each send, `9` lighter and `10` a little stronger; `10`
  reads as the ball asking for attention when it has been left still. `213` is the LED plus the
  *captured* Pokémon's cry, and `129` is the *stroll* Pokémon's. In play mode (the stick held down
  with a Pokémon on a stroll) `9` keeps blinking, and every interaction plays from the stroll slots:
  "playing" is the normal cry, "enjoy" and "enjoy very much" are cry variants, and the rainbow goes
  back to `9`'s pulse afterwards. `9`'s blink has never been seen to stop without `180`; the old
  project's records have it running tens of minutes. `198`–`200` are fixed UI for catching, the
  phases while a Pokémon is inside the ball, so their colour is not ours to choose.

- **2026-09-25 — the fix for one slot wanted twice was never a cleverer swap; it was the other
  slot.** Tasks 16, 26 and 34 each added machinery to share `04 3e 00` between a cry and a silence:
  a swap on every beat, a wait for a cry still sounding, a gap in the config and a floor on that gap
  read from the `.wav`. Every piece was correct against its own defect, and the whole was a
  workaround for a fact nobody had yet: that the ball has a second set of resources, addressed by
  the bytes in front of the upload, and an effect (`9`) whose light holds on its own. Once that was
  known the entire pulse disappeared rather than being improved. **When each fix adds a guard for
  the last fix, the next question is about the device, not the code.**

- **2026-09-25 — "the light replaces the light" is a desk fact, and it removed a design step.** The
  first draft sent `180` between kinds, so a `needs` taking the floor from a lit `done` would go
  dark first. The desk said one light simply replaces the other, and `4` looks like `199` on
  purpose: muted, the colour is what still says which kind it is. The rule that came out of it —
  `180` only when nothing is owed a light — is simpler than the draft and has one fewer send per
  change of lead.

- **2026-09-25 — a quit that sends a last frame exposed a quit that never finished.** Making SIGTERM
  go through the Quit path, so `180` goes out before the link is let go, was tested by sending
  SIGTERM with stdin held open: the daemon printed `stopped` and was still alive 15 s later.
  `asyncio.run` joins the default executor on exit, and `keys()` had a `readline` blocked in it.
  That hang was always there for a menu Quit started from a terminal; nobody had timed the exit,
  because "stopped" in the log reads like the end. **The last line a process prints is not
  evidence that it exited.** B's reader is a daemon thread now, and both signals exit in under a
  second.

- 2026-09-28 — **A desktop session that leaves no trace was not a local session.** The first run
  in the Claude desktop app wrote no event and no transcript under `~/.claude/projects`; it ran
  outside this Mac's Claude Code (Cowork or cloud), where `~/.claude/settings.json` hooks never
  fire. Only the Code tab, run **Local**, loads the hooks. So an empty `var/events` after a desktop
  run says where the session ran, not that the hook is broken.

- 2026-09-28 — **Claude Code's registry outlives a killed claude.** After `kill -9`,
  `~/.claude/sessions/71414.json` was still there, with nothing running at that pid. So a
  registry file is not evidence that its session runs. The kernel's start time is what separates
  a live claude from a stale file whose pid has since gone to someone else (task 40). For the
  five live sessions it sat 0.3–3.7 s before the registry's `startedAt`.

- 2026-09-28 — **A mutant swapped in and out within a second can outlive its revert.** Task 40's
  hand mutant ran `sed` to turn `max(found` into `min(found` in `src/hooks.py`, ran the check, and
  copied the file back, all in one second. `min` and `max` are the same length, so the file's
  size and its whole-second mtime matched the `.pyc` built from the mutant, and Python kept
  loading the mutant. check_sessions then failed against the correct source. `dis` showed `min`
  where the file said `max`. So after hand-mutating a source file, delete its `__pycache__`
  (`find src -name '*.pyc' -delete`), and when a check disagrees with the source you read,
  suspect the bytecode before the logic.
- 2026-09-29 (task 45): closing a Warp tab does not close its terminal. Warp's `terminal-server`
  keeps the shell and the claude alive on the same tty for the undo-close grace period
  (`general.undo_close.grace_period`), then ends both at once, and the `SessionEnd` lands in that
  same second (09:16:20 for 6672). The "orphan with no tty" seen at 08:50:58 was only the last
  instant of that. The pty check passed because its fixture was built on the same wrong
  assumption: a shell that dies when its tab closes. Before building a rule on a desk
  observation, watch the whole sequence live, from the close to the end.
- 2026-09-30 (task 60): `check_criteria` fires its first event a fixed 0.8 s after spawning the
  daemon, and the daemon takes 0.40–0.75 s to read its events file, with or without task 60's
  Quartz import (measured side by side against HEAD). On a slow start the event lands before the
  file is read, counts as backlog from a dead claude and is dropped — criterion 6 failed once
  that way and passed on the rerun. Waiting for the `restart` line instead of sleeping would take
  the race away; not done here.
- 2026-09-30 (task 60, desk): the menu ball's light walked against the ball, step by step, and it
  matched in every moment: connect white, `done` breathing with 9, `needs` flashing with 199, 201
  green and 206 red loud, and 193/191 muted with no rumble (log 19:03:42 and 19:04:02). One
  gotcha on the way: the muted red first failed to fire because a second menu click after taking
  the `needs` moved the attending to another entry and let the `needs` go, so leaving its window
  was not a walk-away. That is task 56's rule working, not a fault. To test a break-out, take it
  with B and touch nothing else before leaving.
- 2026-09-30 (task 62): macOS 26's grey plate under an app icon is about opacity, not shape: an
  icon that leaves any pixel clear inside the system's squircle is plated, whatever its outline.
  The probing chased shape, SDK and Info.plist keys first, because the probe's "Apple grid"
  icon carried the ball's button hole cleared through it, so every variant of it was plated. What found it was
  swapping halves with an icon that escapes — VS Code's `.icns` in our bundle escaped, so the
  bundle was cleared; its shape painted all white escaped, ours did not. Probe bundles need a
  real executable (`/usr/bin/true`), a signature, and an identifier of their own each time, or
  LaunchServices answers from what it saw before.

- 2026-09-30 (task 61): criterion 6's startup race (the task 60 bullet above) failed twice in a
  row — once inside the full round, once run alone — and passed on a third run alone. Both
  failures say `1 dropped: their claude is not running` at the restart: the race, not the change.
  Startup measured side by side against HEAD: 0.49–0.66 s there, 0.48–0.61 s with task 61. Two in
  a row means the race is not rare, which makes waiting for the `restart` line worth doing.
- 2026-09-30 (task 63): `NSImage.drawInRect_` ignores the context's `CGContextSetAlpha` —
  measured, an image drawn after `CGContextSetAlpha(.35)` came out at alpha 1.0 while a path
  filled after it came out at 0.35. So a fade left on past the ball showed only in the mute
  mark's SourceAtop tint, and only on a dark bar, and its mutant survived until the row read
  the mark in both appearances. A pixel check of anything appearance-picked reads both bars.

## Close of the spec (2026-10-01)

- 2026-10-01 (task 68): a tuple-unpack named like a function in the same scope killed the daemon.
  Task 67's `greeting, hushed = signaller.greet(...)` and task 68's `def hushed(...)` live in one
  `run()`, so after the first greet the next B held called `None(...)` and the daemon died
  (17:11:53). No check saw it because none held B after a greet. In a function this long, a new
  local name is a global search first (`grep -n "\bname\b"` over the enclosing def), not a guess.
- 2026-10-01 (task 63, desk): on macOS 26 the menu bar follows the wallpaper, not the Light/Dark
  setting. Switching to Light left the bar dark and every icon white; a light bar needed a light
  wallpaper. A desk step about "the light bar" has to say how to get one.
- 2026-10-01 (close): a full-round mutant survived once — `back after a minute, as before task
  67` — and was caught 3/3 alone. The row slept 1.2 s after the second beat while the lonely cry
  was due at +3 s; on a busy desk the lonely landed first and spent the greet in silence. The row
  now waits for the third beat, then sleeps. A row that sleeps past one event while another is
  scheduled is a race the reference usually wins.
- 2026-10-01 (close): two gate failures were the runner, not the code. `check_sessions` asserts
  its shell is a child of claude, and a loop script put a bash between them — run directly, green.
  `check_raise`'s real-seam row expected "not open" and got "the screen is locked", the seam's
  correct answer while the Mac was locked. Run the round from the Bash tool itself, unlocked.

## Sorted at the close (2026-10-01)

Every entry above was sorted once, by destination. 26 still-true decisions and gotchas went to
`NOTES.md` at the repo root, rewritten short; entries the spec itself superseded (the silent
pulse, "two daemons take no lock", the ~10 min unfreeze, a skipped signal back in its place) were
not carried. Seven went to a personal lessons file, approved 2026-10-02: the close's timing margin,
the void control region (task 04), the last printed line (task 35), `Event.clear()` before
the wait (task 11), the run-loop cache (tasks 11, 16), the retry deadline (hardware round)
and the prose probe (task 16). One line went to `CLAUDE.md`: Ctrl-C, never Ctrl-Z (task 06). Everything else is journal: true of its task, and kept here.
