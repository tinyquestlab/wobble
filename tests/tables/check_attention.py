#!/usr/bin/env python3
"""Walk the attention state machine through the spec's own stories. No waiting.

    venv/bin/python3 tests/tables/check_attention.py

Five minutes pass by writing `400.0` instead of `100.0`, because nothing in the
core reads a clock. Each row is one claim from `spec.md` — criteria 4, 5, 6 and
7 — checked against an answer worked out from the story, not from the code.

**Then the same suite runs against deliberately broken versions**, each with
one rule removed, and every one must fail — the list is at the bottom, one line
each. A suite that passes against a machine with its rules removed was never
testing the rules.

Most of the stories below give every session a project of its own, because that
is what they were written against and it is still the common case. The task 41
section is the one where a folder has two sessions, and it is the only place
the difference between *that session* and *its folder* can show. From task 20
until task 41 the folder was the unit; four of the mutants are that rule.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.core.attention import (Answered, Attention, Ended, Release,        # noqa: E402
                                Standing, Status, Taken, Why)
from src.core.signals import Event, Kind, Queue                            # noqa: E402

DONE, NEEDS = Kind.DONE, Kind.NEEDS


class Sheet:
    def __init__(self, quiet: bool = False):
        self.quiet, self.bad = quiet, 0

    def row(self, what: str, got, want) -> None:
        good = got == want
        self.bad += not good
        if not self.quiet:
            print(f"    {what:<52} {'ok' if good else f'<-- WRONG: {got!r}, wanted {want!r}'}")

    def ok(self) -> bool:
        return not self.bad


def queue_of(*script: tuple[str, Kind, float]) -> Queue:
    q = Queue()
    for session, kind, at in script:
        q.add(Event(session=session, kind=kind, project=f"proj-{session}",
                    at=at, window_hint=f"win-{session}"))
    return q


def who(entry) -> str | None:
    return entry.session if entry is not None else None


def two_in_wobble() -> Queue:
    """Two sessions in one folder, blocked and finished, and one elsewhere (task 41)."""
    q = Queue()
    for session, kind, project, at in (("A", NEEDS, "wobble", 0.0),
                                       ("B", DONE, "wobble", 1.0),
                                       ("C", DONE, "work", 2.0)):
        q.add(Event(session=session, kind=kind, project=project, at=at,
                    window_hint=project))
    return q


def run_all(make, quiet: bool = False) -> bool:
    sheet = Sheet(quiet)
    say = (lambda _: None) if quiet else (lambda line: print(line))

    say("\n  nothing pending — B does nothing, and says so by doing nothing")
    att = make(Queue())
    sheet.row("dismissing an empty queue attends nobody",
              att.dismiss(0.0).attending, None)
    sheet.row("…and does not freeze anything", att.frozen(), False)

    say("\n  criteria 4 and 5 — dismiss, freeze, and the prompt that resolves")
    q = queue_of(("A", DONE, 0.0), ("B", NEEDS, 1.0))
    att = make(q)
    sheet.row("needs is what surfaces first", who(att.current()), "B")
    sheet.row("dismissing hands back the one to focus",
              who(att.dismiss(2.0).attending), "B")
    sheet.row("…and the count drops to what is left", len(q), 1)
    sheet.row("…and the queue goes quiet", att.current(), None)
    q.add(Event(session="C", kind=NEEDS, project="proj-C", at=3.0, window_hint="win-C"))
    sheet.row("an event during the freeze is kept", len(q), 2)
    sheet.row("…and still does not surface", att.current(), None)
    sheet.row("a prompt in a session nobody signalled changes nothing",
              bool(att.prompted("Z", "proj-Z", 4.0)), False)
    sheet.row("…so the hold survives it", att.frozen(), True)

    say("\n  going to a session you were only queued for resolves it")
    answered = att.prompted("A", "proj-A", 4.5)
    sheet.row("its pending entry is dropped", who(answered.dropped), "A")
    sheet.row("…without releasing the hold on somebody else", answered.released, None)
    sheet.row("…and the count falls", len(q), 1)
    sheet.row("…and the hold is still the hold", att.frozen(), True)

    answered = att.prompted("B", "proj-B", 5.0)
    sheet.row("the held session's own prompt releases it", answered.released,
              Release(session="B", project="proj-B", why=Why.PROMPT, waited=3.0))
    sheet.row("…and it is not put back — it is resolved", "B" in q, False)
    sheet.row("…and the next pending surfaces", who(att.current()), "C")

    say("\n  criterion 6 — the snooze brings back what you promised to look at")
    q = queue_of(("A", NEEDS, 0.0), ("B", DONE, 1.0))
    att = make(q)
    att.dismiss(100.0)
    sheet.row("a second before the snooze, nothing happens", att.tick(399.0), None)
    sheet.row("…and the queue is still held", att.current(), None)
    fired = att.tick(400.0)
    sheet.row("at five minutes it comes back, and says why", fired,
              Release(session="A", project="proj-A", why=Why.SNOOZE, waited=300.0,
                      returned=True))
    sheet.row("…it is in the queue again", len(q), 2)
    sheet.row("…a needs, so ahead of the done even at the back", who(att.current()), "A")
    sheet.row("…and it does not fire twice", att.tick(9999.0), None)

    say("\n  the snooze does not clobber a session that signalled again")
    q = queue_of(("A", DONE, 0.0))
    att = make(q)
    att.dismiss(10.0)
    q.add(Event(session="A", kind=NEEDS, project="proj-A", at=20.0, window_hint="win-A"))
    fired = att.tick(400.0)
    # getattr, because a mutant whose snooze never fires hands back None here —
    # and a control that dies with a traceback stops the other three from running.
    sheet.row("the snooze reports that it did not go back",
              getattr(fired, "returned", "no release at all"), False)
    sheet.row("…because the newer entry is already there", len(q), 1)
    sheet.row("…and the newer kind is the one that survives",
              att.current().kind if att.current() else None, NEEDS)

    say("\n  criterion 7 — pressing B again skips, and puts back what it skipped")
    q = queue_of(("A", DONE, 0.0), ("B", NEEDS, 1.0))
    att = make(q)
    sheet.row("the first press takes the needs", who(att.dismiss(5.0).attending), "B")
    sheet.row("…and the count drops to what is left", len(q), 1)
    taken = att.dismiss(6.0)
    sheet.row("the second press moves to the done", who(taken.attending), "A")
    sheet.row("…and says what it stepped away from", taken.released,
              Release(session="B", project="proj-B", why=Why.SKIP, waited=1.0,
                      returned=True))
    sheet.row("…which is back in the queue, a needs ahead of the done", who(q.top()), "B")
    sheet.row("…so the count does not drop for a skip", len(q), 1)
    taken = att.dismiss(7.0)
    sheet.row("a third press hands back the one just put down",
              who(taken.attending), "B")
    # A done put down comes back quiet since task 68: listed, not signalled.
    sheet.row("…and puts down the one it was on, quiet", (who(q.top(quiet=True)), q.live()),
              ("A", 0))

    # Task 46, 2026-09-29: until then this press skipped anyway, handed the
    # signal straight back, and it cried at once — a beat for every B pressed
    # because the window did not come (tasks.md 38, 18:41:26–18:41:37).
    say("\n  task 46 — with nothing to skip to, B asks for the window again")
    q = queue_of(("A", DONE, 0.0))
    att = make(q)
    att.dismiss(1.0)
    taken = att.dismiss(2.0)
    sheet.row("a second press on a lone signal keeps it",
              who(taken.attending), "A")
    sheet.row("…and says it is asking for the window again",
              getattr(taken, "again", "no such field"), True)
    sheet.row("…with nothing let go", taken.released, None)
    sheet.row("…so it is still held, and quiet", att.frozen(), True)
    sheet.row("…and nothing went back into the queue", len(q), 0)
    sheet.row("the snooze still counts from the first press",
              getattr(att.tick(1.0 + att.snooze), "session", None), "A")
    q = queue_of(("A", DONE, 0.0))
    att = make(q)
    att.dismiss(1.0)
    att.dismiss(2.0)
    q.add(Event(session="B", kind=DONE, project="proj-B", at=3.0, window_hint="win-B"))
    taken = att.dismiss(4.0)
    sheet.row("once another is waiting, B skips to it again",
              who(taken.attending), "B")
    sheet.row("…and puts back the one it was on, as any skip does",
              getattr(taken.released, "returned", "no release at all"), True)

    say("\n  a skip does not clobber a session that signalled again either")
    q = queue_of(("A", NEEDS, 0.0), ("B", DONE, 1.0))
    att = make(q)
    att.dismiss(5.0)                                   # takes the needs, A
    q.add(Event(session="A", kind=DONE, project="proj-A", at=6.0, window_hint="win-A"))
    taken = att.dismiss(7.0)
    # getattr, because a mutant that drops what it skips hands back no release
    # here — and a control that dies with a traceback stops the others running.
    sheet.row("the skip reports that it did not go back",
              getattr(taken.released, "returned", "no release at all"), False)
    sheet.row("…because the newer entry is already there", len(q), 1)
    sheet.row("…and the newer kind is the one that survives",
              q.top().kind if q.top() else None, DONE)

    say("\n  task 41 — two sessions in one folder are two things to deal with")
    att = make(two_in_wobble())
    answered = att.prompted("A", "wobble", 3.0)
    sheet.row("a prompt answers the session you typed in",
              who(answered.dropped), "A")
    # Answering one must not finish the other, which had already finished —
    # a notifier going quiet about something nobody was told (principle 7).
    sheet.row("…and the other one in its folder is still waiting",
              ("B" in att.queue, len(att.queue)), (True, 2))

    q = two_in_wobble()
    att = make(q)
    taken = att.dismiss(5.0)
    sheet.row("B takes that session, not its folder",
              (att.session, len(taken.attending or ())), ("A", 1))
    sheet.row("…leaving the other session in the folder waiting",
              ("B" in q, len(q)), (True, 2))
    # The row task 41 exists for: Warp and the desktop app open on one folder
    # are two places, and typing in one is no answer to the other.
    answered = att.prompted("B", "wobble", 6.0)
    sheet.row("a prompt in the other session answers only that one",
              (who(answered.dropped), answered.released), ("B", None))
    sheet.row("…and the hold on this one survives it", att.session, "A")
    answered = att.prompted("A", "wobble", 7.0)
    sheet.row("its own prompt ends the hold",
              answered.released,
              Release(session="A", project="wobble", why=Why.PROMPT, waited=2.0))
    sheet.row("…and the other folder is next", who(att.current()), "C")

    say("\n  task 21 — the same press, aimed at the session you chose")
    q = queue_of(("A", DONE, 0.0), ("B", NEEDS, 1.0))
    att = make(q)
    taken = att.attend("A", 5.0)
    sheet.row("attending a named session takes that one", who(taken.attending), "A")
    sheet.row("…and not the one at the top, which is the whole point",
              who(q.top()), "B")
    sheet.row("…it leaves the queue like any other take", len(q), 1)
    sheet.row("…and nothing was let go, because nothing was held",
              taken.released, None)
    taken = att.attend("B", 6.0)
    sheet.row("choosing another moves to it", who(taken.attending), "B")
    sheet.row("…handing back the one it was on, exactly as a skip does",
              taken.released,
              Release(session="A", project="proj-A", why=Why.SKIP, waited=1.0,
                      returned=True))
    sheet.row("…which is back in the queue, quiet (task 68)",
              who(q.top(quiet=True)), "A")
    sheet.row("…so the count does not drop for an aimed press either", len(q), 1)

    say("\n  …and a line chosen after its session stopped waiting does nothing")
    q = queue_of(("A", DONE, 0.0), ("B", NEEDS, 1.0))
    att = make(q)
    att.attend("B", 5.0)               # held, so no longer in the queue at all
    taken = att.attend("B", 6.0)
    # The menu is rebuilt from the queue every refresh, but a click still races
    # a poll. Falling back to the top would be the tempting fix and it is the
    # wrong one: it raises a window nobody asked for, which is worse than the
    # nothing it was trying to avoid.
    sheet.row("choosing what is already held attends nobody",
              taken.attending, None)
    sheet.row("…and lets go of nothing", taken.released, None)
    # `current()` is None while frozen, so what is checked is the hold itself:
    # it survived, and the session it holds was not handed back to the queue.
    sheet.row("…so the hold you were already in is still yours", att.frozen(), True)
    sheet.row("…and it did not put itself back in the queue", "B" in q, False)
    taken = att.attend("never", 7.0)
    sheet.row("a session that was never in the queue changes nothing either",
              (taken.attending, taken.released), (None, None))
    sheet.row("…and what is waiting is still waiting", len(q), 1)

    say("\n  task 22 — a session that closes stops waiting")
    q = queue_of(("A", DONE, 0.0), ("B", NEEDS, 1.0))
    att = make(q)
    over = att.ended("A", "proj-A", 2.0)
    sheet.row("a queued session closing takes its entry out", who(over.dropped), "A")
    sheet.row("…and the count drops", len(q), 1)
    sheet.row("…with no hold to end", over.released, None)
    sheet.row("an end for a session nobody signalled changes nothing",
              bool(att.ended("Z", "proj-Z", 3.0)), False)

    say("\n  …and it is not an answer: the folder keeps its other session")
    q = two_in_wobble()
    att = make(q)
    over = att.ended("A", "wobble", 3.0)
    sheet.row("closing the blocked session takes that session out",
              who(over.dropped), "A")
    # Closing one tab says nothing about the session that had finished beside
    # it, and a version that took the folder down would throw that away silently.
    sheet.row("…and the other one in the folder is still waiting",
              ("B" in q, len(q)), (True, 2))

    say("\n  the hold survives another session closing, and ends when its own does")
    q = two_in_wobble()
    att = make(q)
    att.dismiss(5.0)                                  # attends A
    over = att.ended("B", "wobble", 6.0)
    sheet.row("the other session in the folder closing takes that one out",
              (who(over.dropped), over.released), ("B", None))
    sheet.row("…and the hold survives it", att.session, "A")
    over = att.ended("A", "wobble", 7.0)
    # 2.0 and not 1.0: the hold started at 5.0 and a session closing beside it
    # did not restart the clock.
    sheet.row("its own closing ends the hold, and says how long it was",
              over.released,
              Release(session="A", project="wobble", why=Why.END, waited=2.0))
    sheet.row("…and nothing went back in — it is not a snooze", "A" in q, False)
    sheet.row("…so the other folder surfaces", who(att.current()), "C")

    say("\n  a session that signalled again while held goes from both places")
    q = queue_of(("A", DONE, 0.0))
    att = make(q)
    att.dismiss(1.0)
    q.add(Event(session="A", kind=NEEDS, project="proj-A", at=2.0, window_hint="win-A"))
    over = att.ended("A", "proj-A", 3.0)
    sheet.row("the newer copy in the queue goes", len(q), 0)
    sheet.row("…and the held one goes with it", att.frozen(), False)
    sheet.row("…leaving nothing pending at all", att.current(), None)

    # Task 36: where each row of the menu stands. The top speaks, or is quiet
    # because you are looking at it; B's one counts down to its snooze; the rest
    # wait their turn — including the top, while something else is held.
    say("\n  where each one stands, for the menu's list")
    q = queue_of(("A", DONE, 0.0), ("B", DONE, 1.0))
    att = make(q)
    a, b = q.get("A"), q.get("B")
    sheet.row("the top one is signalling",
              att.standing(a, 2.0).status, Status.SIGNALLING)
    sheet.row("…quiet while you are looking at its window",
              att.standing(a, 2.0, watching="A").status, Status.WATCHED)
    sheet.row("…and the one behind it is waiting its turn",
              att.standing(b, 2.0).status, Status.WAITING)
    sheet.row("…even when it is its window you are looking at",
              att.standing(b, 2.0, watching="B").status, Status.WAITING)
    att.dismiss(10.0)
    held = att.entry
    sheet.row("B's one is attending",
              att.standing(held, 70.0).status, Status.ATTENDING)
    sheet.row("…with the snooze's own time left on it",
              att.standing(held, 70.0).back_in, 300.0 - 60.0)
    sheet.row("…and the rest wait, since nothing speaks while it is held",
              att.standing(b, 70.0).status, Status.WAITING)

    # Task 47, 2026-09-29: A was pending before a restart and came back quiet;
    # B arrived after it. B speaks, A never does, and B reaches A after B.
    say("\n  task 47 — back from before a restart: listed, reachable, never signalled")
    q = queue_of(("A", DONE, 0.0))
    q.hush()
    q.add(Event(session="B", kind=DONE, project="proj-B", at=5.0, window_hint="win-B"))
    att = make(q)
    a = q.get("A")
    sheet.row("the live one is what signals", who(att.current()), "B")
    sheet.row("…and the quiet one stands as quiet",
              att.standing(a, 6.0).status, Status.QUIET)
    sheet.row("B takes the live one first", who(att.dismiss(10.0).attending), "B")
    taken = att.dismiss(20.0)
    sheet.row("…and B again reaches the quiet one", who(taken.attending), "A")
    sheet.row("…putting the live one back, as any skip does",
              getattr(taken.released, "returned", "no release at all"), True)
    att.tick(20.0 + att.snooze)
    sheet.row("its snooze brings it back still quiet",
              getattr(q.get("A"), "quiet", "not back at all"), True)
    att.prompted("B", "proj-B", 400.0)
    sheet.row("with nothing live left, nothing signals", att.current(), None)
    back = q.get("A")
    sheet.row("…and now stands as seen: B took it (task 68)",
              att.standing(back, 400.0).status if back else "not back at all", Status.SEEN)
    sheet.row("…and B still reaches it", who(att.dismiss(401.0).attending), "A")

    say("\n  task 49 — a question answered where it was asked")
    q = queue_of(("A", NEEDS, 0.0), ("B", DONE, 1.0), ("C", NEEDS, 2.0))
    att = make(q)
    answered = att.replied("A", 3.0)
    sheet.row("its needs is dropped", who(answered.dropped), "A")
    sheet.row("…and nothing was held, so nothing released", answered.released, None)
    sheet.row("a done is not a question, so it stays",
              (bool(att.replied("B", 3.5)), "B" in q), (False, True))
    sheet.row("the held needs is released as a prompt would",
              (who(att.dismiss(4.0).attending), getattr(att.replied("C", 6.0), "released", None)),
              ("C", Release(session="C", project="proj-C", why=Why.PROMPT, waited=2.0)))
    sheet.row("…and not put back", "C" in q, False)
    q = queue_of(("D", DONE, 0.0))
    att = make(q)
    att.dismiss(1.0)
    sheet.row("a held done is not released by an answer",
              (bool(att.replied("D", 2.0)), att.frozen()), (False, True))

    say("\n  task 52 — a needs speaks over the hold; the held one keeps its snooze")
    q = queue_of(("A", DONE, 0.0), ("B", DONE, 1.0))
    att = make(q)
    att.dismiss(2.0)
    sheet.row("a done behind a held done stays quiet while you are at it",
              att.current(), None)
    q.add(Event(session="C", kind=NEEDS, project="proj-C", at=3.0, window_hint="win-C"))
    sheet.row("a needs speaks over a held done at once", who(att.current()), "C")
    sheet.row("…and the hold stands", (att.frozen(), att.session), (True, "A"))
    sheet.row("…the needs reads as signalling, the done as attending",
              (att.standing(q.get("C"), 3.0).status, att.standing(att.entry, 3.0).status),
              (Status.SIGNALLING, Status.ATTENDING))
    sheet.row("…being away changes nothing for a held done",
              (att.set_away(True), who(att.current()))[1], "C")
    att.set_away(False)
    taken = att.dismiss(4.0)
    sheet.row("B takes the needs, and the done goes to the back",
              (who(taken.attending), getattr(taken.released, "returned", None),
               [e.session for e in q.pending()]),
              ("C", True, ["B", "A"]))
    q = queue_of(("A", DONE, 0.0))
    att = make(q)
    att.dismiss(1.0)
    q.add(Event(session="C", kind=NEEDS, project="proj-C", at=2.0, window_hint="win-C"))
    sheet.row("the snooze still returns a held done a needs spoke over",
              att.tick(301.0),
              Release(session="A", project="proj-A", why=Why.SNOOZE, waited=300.0,
                      returned=True))
    q = queue_of(("N", NEEDS, 0.0))
    att = make(q)
    att.dismiss(1.0)
    q.add(Event(session="M", kind=NEEDS, project="proj-M", at=2.0, window_hint="win-M"))
    sheet.row("over a held needs, a needs waits while you are at it", att.current(), None)
    att.set_away(True)
    sheet.row("…and still waits once you are away (task 55)", att.current(), None)
    q = queue_of(("A", DONE, 0.0), ("B", DONE, 1.0), ("C", DONE, 2.0))
    att = make(q)
    att.dismiss(3.0)
    att.set_away(True)
    att.dismiss(4.0)
    sheet.row("a new hold starts at its window, not away",
              (att.session, att.current()), ("B", None))

    # 2026-09-29 16:47:53: a done held for a background run, nothing to do in
    # it, kept juno's done quiet while the user was elsewhere.
    say("\n  task 54 — away from the hold, it holds nothing back; what returns goes last")
    q = queue_of(("A", DONE, 0.0), ("B", DONE, 1.0))
    att = make(q)
    att.dismiss(2.0)
    att.set_away(True)
    sheet.row("away from a held done, a done behind it speaks", who(att.current()), "B")
    att.set_away(False)
    sheet.row("…and is quiet again when you come back", att.current(), None)
    q = queue_of(("N", NEEDS, 0.0), ("D", DONE, 1.0))
    att = make(q)
    att.dismiss(2.0)
    att.set_away(True)
    sheet.row("away from a held needs, a done still waits (task 55)", att.current(), None)
    q = queue_of(("A", DONE, 0.0), ("B", DONE, 1.0))
    att = make(q)
    att.dismiss(2.0)
    q.add(Event(session="C", kind=DONE, project="proj-C", at=3.0, window_hint="win-C"))
    att.tick(302.0)
    sheet.row("the snooze returns it behind what waited meanwhile",
              [e.session for e in q.pending()], ["B", "C", "A"])
    q = queue_of(("A", DONE, 0.0), ("B", DONE, 1.0), ("C", DONE, 2.0))
    att = make(q)
    att.dismiss(3.0)
    att.dismiss(4.0)
    sheet.row("a skip puts the one it left behind the rest",
              [e.session for e in q.pending()], ["C", "A"])
    q = queue_of(("N", NEEDS, 0.0), ("D", DONE, 1.0))
    att = make(q)
    att.dismiss(2.0)
    att.tick(302.0)
    sheet.row("…and a needs at the back is still ahead of a done",
              [e.session for e in q.pending()], ["N", "D"])

    # 2026-09-29 18:09:13: B on juno's needs, and escriba-bot's needs spoke over
    # it 3 s later; "the only thing a needs waits for is another needs".
    say("\n  task 55 — a held needs holds everything until it is answered")
    q = queue_of(("N", NEEDS, 0.0), ("M", NEEDS, 1.0), ("D", DONE, 2.0))
    att = make(q)
    att.dismiss(3.0)
    sheet.row("at its window, nothing speaks over a held needs", att.current(), None)
    att.set_away(True)
    sheet.row("…nor once you are away", att.current(), None)
    answered = att.replied("N", 10.0)
    sheet.row("answered where it asked, the hold ends",
              (getattr(answered.released, "why", None), att.frozen()), (Why.PROMPT, False))
    sheet.row("…and the next needs speaks", who(att.current()), "M")
    q = queue_of(("N", NEEDS, 0.0), ("M", NEEDS, 1.0))
    att = make(q)
    att.dismiss(2.0)
    att.set_away(True)
    att.tick(302.0)
    sheet.row("its snooze hands the floor to the one that waited",
              who(att.current()), "M")

    # the user, 2026-09-30: "ir pro needs e nao responder, faz vermelho de falha
    # de captura e volta o pulse".
    say("\n  task 56 — a held needs you walk away from breaks out")
    q = queue_of(("N", NEEDS, 0.0), ("M", NEEDS, 1.0), ("D", DONE, 2.0))
    att = make(q)
    att.dismiss(3.0)
    sheet.row("away from a window never in front: no break-out",
              (att.set_away(True, seen=False), att.current()), (False, None))
    att.set_away(False, seen=True)
    sheet.row("seen, then left past the grace: it breaks out, once",
              att.set_away(True, seen=True), True)
    sheet.row("…and its own pulse comes back — not the next needs",
              (who(att.current()), att.broken), ("N", True))
    sheet.row("…still the one being attended", att.session, "N")
    sheet.row("the next poll, still away, is not a second break-out",
              (att.set_away(True, seen=True), who(att.current())), (False, "N"))
    att.set_away(False, seen=True)
    sheet.row("back in its window, it is held again", (att.current(), att.broken),
              (None, False))
    sheet.row("…and leaving again breaks it out again",
              (att.set_away(True, seen=True), who(att.current())), (True, "N"))
    taken = att.dismiss(10.0)
    sheet.row("B from a broken-out one skips on, and the new hold is not broken",
              (who(taken.attending), att.current(), att.broken), ("M", None, False))
    q = queue_of(("D", DONE, 0.0), ("N", NEEDS, 1.0))
    att = make(q)
    att.attend("D", 2.0)
    sheet.row("a held done never breaks out",
              (att.set_away(False, seen=True), att.set_away(True, seen=True), att.broken),
              (False, False, False))
    q = queue_of(("N", NEEDS, 0.0), ("M", NEEDS, 1.0))
    att = make(q)
    att.dismiss(2.0)
    att.set_away(False, seen=True)
    att.set_away(True, seen=True)
    att.tick(302.0)
    sheet.row("a snooze ends the break-out with the hold",
              (who(att.current()), att.broken), ("M", False))

    say("\n  task 56 — answering a needs is the catch")
    q = queue_of(("N", NEEDS, 0.0), ("D", DONE, 1.0), ("M", NEEDS, 2.0))
    att = make(q)
    att.dismiss(3.0)
    sheet.row("the held needs answered where it asked: caught",
              att.replied("N", 4.0).caught, True)
    sheet.row("a queued needs answered by a prompt: caught",
              att.prompted("M", "", 5.0).caught, True)
    sheet.row("a done cleared by a prompt: not a catch",
              att.prompted("D", "", 6.0).caught, False)
    q = queue_of(("D", DONE, 0.0))
    att = make(q)
    att.dismiss(1.0)
    sheet.row("a held done ended by a prompt: not a catch",
              att.prompted("D", "", 2.0).caught, False)
    q = queue_of(("D", DONE, 0.0))
    att = make(q)
    sheet.row("an answer in a session with only a done: nothing, no catch",
              (bool(att.replied("D", 1.0)), att.replied("D", 1.0).caught), (False, False))
    q = queue_of(("N", NEEDS, 0.0))
    att = make(q)
    att.dismiss(1.0)
    sheet.row("the held needs ended by a prompt: caught",
              att.prompted("N", "", 2.0).caught, True)

    return sheet.ok()


def seen_and_silenced(make, make_q=Queue, quiet: bool = False) -> bool:
    """Task 68: a done you took comes back quiet, and a session can be silenced.

    the user, 2026-10-01: "done com B, snooze 5 minutos, nao volta a tocar, só
    fica na fila", and of the silenced one: "caso o prompt responda algo ou eu
    digite algo, ele sai do silencio". Its own table because half its mutants
    are the queue's, and `run_all` builds plain queues.
    """
    sheet = Sheet(quiet)
    say = (lambda _: None) if quiet else (lambda line: print(line))

    def queue(*script):
        q = make_q()
        for session, kind, at in script:
            q.add(Event(session=session, kind=kind, project=f"proj-{session}",
                        at=at, window_hint=f"win-{session}"))
        return q

    def add(q, session, kind, at):
        q.add(Event(session=session, kind=kind, project=f"proj-{session}",
                    at=at, window_hint=f"win-{session}"))

    def quiet_of(q, session):
        entry = q.get(session)
        return entry.quiet if entry is not None else "not waiting"

    say("\n  task 68 — a done you took with B comes back quiet")
    q = queue(("A", DONE, 0.0))
    att = make(q)
    att.dismiss(1.0)
    att.tick(301.0)
    sheet.row("back from its snooze: listed, quiet, not counted",
              (quiet_of(q, "A"), att.current(), q.live()), (True, None, 0))
    sheet.row("…and it stands as seen", att.standing(q.get("A"), 302.0).status
              if q.get("A") else "not waiting", Status.SEEN)
    sheet.row("…and B still reaches it", who(att.dismiss(303.0).attending), "A")
    q = queue(("N", NEEDS, 0.0))
    att = make(q)
    att.dismiss(1.0)
    att.tick(301.0)
    sheet.row("a needs back from its snooze is live", who(att.current()), "N")
    q = queue(("A", DONE, 0.0), ("C", DONE, 1.0))
    att = make(q)
    att.dismiss(2.0)
    att.dismiss(3.0)
    sheet.row("a done skipped by B again comes back quiet",
              (quiet_of(q, "A"), att.session), (True, "C"))
    q = queue(("A", DONE, 0.0), ("C", DONE, 1.0))
    att = make(q)
    att.attend("A", 2.0)
    att.attend("C", 3.0)
    sheet.row("…and so does one let go by another menu line", quiet_of(q, "A"), True)
    add(q, "A", DONE, 10.0)
    sheet.row("a new done from it is live again", (quiet_of(q, "A"), q.live()), (False, 1))

    say("\n  task 68 — silenced by hand, until you type in it or answer it")
    q = queue(("A", NEEDS, 0.0), ("B", DONE, 1.0))
    att = make(q)
    hushed = att.silence(2.0)
    sheet.row("B held with nothing attended silences the top",
              (hushed.session, hushed.released, who(att.current())), ("A", None, "B"))
    sheet.row("…its row stands as silenced", att.standing(q.get("A"), 2.0).status
              if q.get("A") else "not waiting", Status.SILENCED)
    add(q, "A", NEEDS, 3.0)
    sheet.row("…a new needs from it arrives quiet, and ends nothing",
              (quiet_of(q, "A"), who(att.current()), q.silenced("A")), (True, "B", True))
    answered = att.prompted("A", "proj-A", 4.0)
    sheet.row("a prompt in it ends the silence", (answered.unsilenced, q.silenced("A")),
              (True, False))
    add(q, "A", DONE, 5.0)
    sheet.row("…and its next event is live", quiet_of(q, "A"), False)

    q = queue(("A", DONE, 0.0), ("B", DONE, 1.0))
    att = make(q)
    att.dismiss(2.0)
    hushed = att.silence(5.0)
    sheet.row("B held while attending silences the held one",
              (hushed.session, getattr(hushed.released, "why", None), att.frozen()),
              ("A", Why.SILENCE, False))
    sheet.row("…and lets it go into the queue, quiet",
              (getattr(hushed.released, "returned", None), quiet_of(q, "A"),
               who(att.current())), (True, True, "B"))
    q = queue(("N", NEEDS, 0.0), ("M", NEEDS, 1.0))
    att = make(q)
    att.dismiss(2.0)
    att.silence(3.0)
    sheet.row("a held needs silenced goes back quiet, not live",
              (quiet_of(q, "N"), who(att.current())), (True, "M"))
    q = queue(("N", NEEDS, 0.0))
    att = make(q)
    att.dismiss(1.0)
    add(q, "N", NEEDS, 2.0)
    hushed = att.silence(3.0)
    sheet.row("one that signalled while held: its newer row goes quiet",
              (getattr(hushed.released, "returned", None), quiet_of(q, "N"), len(q)),
              (False, True, 1))
    taken = att.dismiss(4.0)
    att.tick(4.0 + att.snooze)
    sheet.row("B reaches a silenced needs, and its snooze keeps it quiet",
              (who(taken.attending), quiet_of(q, "N")), ("N", True))

    q = queue(("A", DONE, 0.0), ("B", DONE, 1.0))
    att = make(q)
    att.dismiss(2.0)
    hushed = att.silence(3.0, "B")
    sheet.row("the menu's row silences that one, and the hold stands",
              (hushed.session, att.session, quiet_of(q, "B")), ("B", "A", True))
    sheet.row("a row no longer waiting silences nothing",
              (bool(att.silence(4.0, "nobody")), q.silenced("nobody")), (False, False))
    sheet.row("nothing waiting and nothing held: nothing silenced",
              bool(make(make_q()).silence(0.0)), False)

    q = queue(("A", NEEDS, 0.0))
    att = make(q)
    att.silence(1.0)
    answered = att.replied("A", 2.0)
    sheet.row("its question answered where it asked ends the silence",
              (answered.unsilenced, q.silenced("A"), "A" in q), (True, False, False))
    q = queue(("A", DONE, 0.0))
    att = make(q)
    att.silence(1.0)
    answered = att.replied("A", 2.0)
    sheet.row("a tool that answers nothing does not",
              (answered.unsilenced, q.silenced("A"), quiet_of(q, "A")), (False, True, True))
    att.ended("A", "proj-A", 3.0)
    sheet.row("its session closing forgets the silence", q.silenced("A"), False)

    q = two_in_wobble() if make_q is Queue else queue()
    if make_q is Queue:
        att = make(q)
        att.silence(3.0, "A")
        sheet.row("a twin in the same folder keeps signalling",
                  (quiet_of(q, "A"), quiet_of(q, "B")), (True, False))
    return sheet.ok()


# --- the mutants ---------------------------------------------------------------
# Each removes exactly one rule. If the suite still passes against one of them,
# it was not testing that rule.

class NoFreeze(Attention):
    def current(self):
        return self.queue.top()


class NeverSnoozes(Attention):
    def tick(self, now):
        return None


class LosesTheDismissed(Attention):
    """Releases on time, but moves on instead of bringing it back."""

    def tick(self, now):
        if self._entry is None or now - self._since < self.snooze:
            return None
        return self._release(Why.SNOOZE, now)


class DropsTheSkipped(Attention):
    """Skips to the next, but lets go of the one it stepped away from.

    This is what `dismiss` did until 2026-09-22: a signal left the queue on the
    press and nothing ever put it back, so pressing B twice lost one for good.
    """

    def dismiss(self, now):
        nxt = self.queue.top()
        if nxt is not None:
            self.queue.drop(nxt.session)
        self._entry, self._since = nxt, (now if nxt is not None else 0.0)
        return Taken(attending=nxt)


class PromptKeepsThePending(Attention):
    """Releases the hold, but leaves the entry it answered in the queue."""

    def prompted(self, session, project, now):
        if self._entry is not None and session == self._entry.session:
            return Answered(released=self._release(Why.PROMPT, now))
        return Answered()


def drop_folder(queue, project) -> None:
    """Take every queued session of `project` out — what the folder mutants share."""
    for entry in [e for e in queue.pending() if e.project == project]:
        queue.drop(entry.session)


class PromptFinishesTheProject(Attention):
    """Answers one session and takes the whole folder down with it.

    The simple collapse rejected on 2026-09-23. It reads as the tidy version —
    you went to that window, so the window is dealt with — and the thing it
    throws away is a session that had already finished beside the blocked one,
    with nothing ever said about it. That is the silence principle 7 forbids.
    """

    def prompted(self, session, project, now):
        answered = super().prompted(session, project, now)
        drop_folder(self.queue, project)
        return answered


class PromptEndsTheFoldersHold(Attention):
    """Task 20's rule: a prompt anywhere in the held folder ends the hold."""

    def prompted(self, session, project, now):
        held = self._entry
        if held is not None and held.project == project and held.session != session:
            return Answered(released=self._release(Why.PROMPT, now),
                            dropped=self.queue.drop_session(session))
        return super().prompted(session, project, now)


class SkipsTheLone(Attention):
    """A lone signal skipped anyway: what `dismiss` did until task 46."""

    def dismiss(self, now):
        return self._take(self.queue.top(), now)


class RetryRestartsTheSnooze(Attention):
    """The retry is right, but each press pushes the snooze back."""

    def dismiss(self, now):
        taken = super().dismiss(now)
        if taken.again:
            self._since = now
        return taken


class DismissSkipsTheQuiet(Attention):
    """B asking the signal's question, so a restored one is never reached."""

    def dismiss(self, now):
        nxt = self.queue.top()
        if self._entry is not None and nxt is None:
            return Taken(attending=self._entry, again=True)
        return self._take(nxt, now)


class CurrentSignalsTheQuiet(Attention):
    """A restored one signalled once nothing live is waiting."""

    def current(self):
        return None if self._entry else self.queue.top(quiet=True)


class StandingIgnoresTheQuiet(Attention):
    """A restored row read as waiting its turn, like any other."""

    def standing(self, entry, now, *, watching=None):
        got = super().standing(entry, now, watching=watching)
        return Standing(Status.WAITING) if got.status is Status.QUIET else got


class AimedTakesTheTop(Attention):
    """A chosen project that is no longer waiting falls back to the top.

    The tempting fix for the race, and the expensive one: the click missed, so
    something else is attended and its window comes forward — a notifier moving
    you somewhere you did not ask to go. Doing nothing and saying so is the
    honest answer (principle 7).
    """

    def attend(self, session, now):
        return self._take(self.queue.get(session) or self.queue.top(), now)


class AimedLosesWhatItHeld(Attention):
    """Goes to the chosen project and drops the one it stepped away from.

    Written out as its own copy of `_take`, which is the point: the two doors
    agree today because they share one, and this is what the first edit to one
    of two copies looks like. `dismiss` still passes every row above it.
    """

    def attend(self, session, now):
        wanted = self.queue.get(session)
        if wanted is None:
            return Taken()
        self.queue.drop(wanted.session)
        held, since = self._entry, self._since
        self._entry, self._since = wanted, now
        if held is None:
            return Taken(attending=wanted)
        return Taken(attending=wanted,
                     released=Release(session=held.session, project=held.project,
                                      why=Why.SKIP, waited=now - since,
                                      returned=False))


class NeverEnds(Attention):
    """The defect as it shipped: a closing session changes nothing.

    This is what happened until task 22, because no `SessionEnd` hook was wired
    at all — a tab whose output you read and then closed left an entry that only
    that same session's next prompt could take out, and it was never going to
    write one. It queued, it beat, and it sat there until the snooze or a
    restart.
    """

    def ended(self, session, project, now):
        return Ended()


class EndFinishesTheProject(Attention):
    """One session closes and the whole folder goes down with it.

    The same tempting collapse as `PromptFinishesTheProject`, arriving by the
    other door — and more tempting here, because closing a tab really does feel
    like being finished. What it throws away is the session that had finished
    behind the one you closed, with nothing ever said about it (principle 7).
    """

    def ended(self, session, project, now):
        over = super().ended(session, project, now)
        drop_folder(self.queue, project)
        return over


class StandingIgnoresTheHold(Attention):
    """Task 36: reads the attended one as just another row waiting."""

    def standing(self, entry, now, *, watching=None):
        top = self.queue.top()
        if top is not None and entry.session == top.session:
            return Standing(Status.WATCHED if top.session == watching else Status.SIGNALLING)
        return Standing(Status.WAITING)


class StandingWatchesAnyRow(Attention):
    """Task 36: marks whichever row's window is in front, top of the queue or not."""

    def standing(self, entry, now, *, watching=None):
        if entry.session == watching:
            return Standing(Status.WATCHED)
        return super().standing(entry, now)


class EndEndsTheFoldersHold(Attention):
    """Task 20's rule, by the other door: any session of the held folder closing ends it."""

    def ended(self, session, project, now):
        held = self._entry
        if held is not None and held.project == project and held.session != session:
            return Ended(released=self._release(Why.END, now),
                         dropped=self.queue.drop_session(session))
        return super().ended(session, project, now)


class RepliedAsPrompted(Attention):
    """Task 49 with the kind unread: an answer taken as a prompt, done and all."""

    def replied(self, session, now):
        return self.prompted(session, "", now)


class ReplyChangesNothing(Attention):
    """Task 49 undone: the stale needs of 2026-09-29 13:55."""

    def replied(self, session, now):
        return Answered()


class NeedsNeverThrough(Attention):
    """Task 52 undone: the hold of 2026-09-29 15:20, gagging a needs for the whole snooze."""

    def current(self):
        return None if self._entry else self.queue.top()


class DoneThrough(Attention):
    """Anything behind the hold speaks over it, a done too."""

    def current(self):
        top = self.queue.top()
        if self._entry is None or top is None:
            return top
        return top if self._entry.kind is DONE or self._away else None


class NeedsAlwaysThrough(Attention):
    """Over a held needs too, while you are still answering it."""

    def current(self):
        top = self.queue.top()
        if self._entry is None:
            return top
        return top if top is not None and top.kind is NEEDS else None


class NeedsOnlyWhenAway(Attention):
    """Task 54 undone: away from a hold, only a needs speaks (task 52's rule)."""

    def current(self):
        top = self.queue.top()
        if self._entry is None:
            return top
        if top is not None and top.kind is NEEDS and (
                self._entry.kind is DONE or self._away):
            return top
        return None


class AwayFreesAHeldNeeds(Attention):
    """Task 55 undone: away from a held needs, the queue speaks (task 54's rule)."""

    def current(self):
        top = self.queue.top()
        if self._entry is None or self._away:
            return top
        if top is not None and top.kind is NEEDS and self._entry.kind is DONE:
            return top
        return None


class BackWhereItWas(Attention):
    """Task 54 undone: what comes back lands where it was."""

    def __init__(self, queue, **kw):
        super().__init__(queue, **kw)
        restore = queue.restore
        queue.restore = (lambda entry, superseded=frozenset(), *, at=None:
                         restore(entry, superseded))


class AwayLeaks(Attention):
    """A new hold inherits being away from the last one."""

    def _take(self, nxt, now):
        away = self._away
        taken = super()._take(nxt, now)
        self._away = away
        return taken


class NeverBreaksOut(Attention):
    """Task 56 undone: walking away from a held needs changes nothing."""

    def set_away(self, away, *, seen=False):
        return super().set_away(away, seen=False)


class BreaksOutUnseen(Attention):
    """A raise that never came forward read as a catch you walked away from."""

    def set_away(self, away, *, seen=False):
        return super().set_away(away, seen=True)


class BreaksOutEveryPoll(Attention):
    """The break-out said on every poll away, not on the edge."""

    def set_away(self, away, *, seen=False):
        super().set_away(away, seen=seen)
        return self._broken and away


class StaysBroken(Attention):
    """Back in its window, the broken-out one keeps speaking."""

    def set_away(self, away, *, seen=False):
        was = self._broken
        broke = super().set_away(away, seen=seen)
        self._broken = self._broken or was
        return broke


class DoneBreaksOut(Attention):
    """A held done breaks out as a needs does."""

    def set_away(self, away, *, seen=False):
        broke = (away and not self._away and seen and not self._broken
                 and self._entry is not None)
        super().set_away(away, seen=seen)
        if broke:
            self._broken = True
        return broke


class BrokenLeaks(Attention):
    """A new hold inherits the last one's break-out."""

    def _take(self, nxt, now):
        broken = self._broken
        taken = super()._take(nxt, now)
        self._broken = broken
        return taken


class BrokenOutlivesSnooze(Attention):
    """The snooze ends the hold and leaves the break-out standing."""

    def _release(self, why, now):
        broken = self._broken
        release = super()._release(why, now)
        self._broken = broken
        return release


class BrokenFreesTheQueue(Attention):
    """Broken out, the top of the queue speaks instead of the held one."""

    def current(self):
        if self._entry is not None and self._broken:
            return self.queue.top()
        return super().current()


class NoCatch(Attention):
    """Task 56 undone: an answer is never a catch."""

    def replied(self, session, now):
        got = super().replied(session, now)
        return Answered(released=got.released, dropped=got.dropped)

    def prompted(self, session, project, now):
        got = super().prompted(session, project, now)
        return Answered(released=got.released, dropped=got.dropped)


class EveryPromptCatches(Attention):
    """A prompt that clears a done is called a catch too."""

    def prompted(self, session, project, now):
        got = super().prompted(session, project, now)
        return Answered(released=got.released, dropped=got.dropped,
                        caught=got.dropped is not None)


class RestoreWakesTheDone(Queue):
    """A done let go comes back live and calls again: what it did until task 68."""

    def restore(self, entry, superseded=frozenset(), *, at=None):
        from dataclasses import replace
        back = super().restore(entry, superseded, at=at)
        for waiting in entry.waiting:
            row = self._waiting.get(waiting.session)
            if (at is not None and row is not None and row.kind is DONE
                    and not self.silenced(waiting.session) and not waiting.quiet):
                self._waiting[waiting.session] = replace(row, quiet=False)
        return back


class AddIgnoresSilence(Queue):
    """A silenced session's new event arrives live."""

    def add(self, event):
        from dataclasses import replace
        entry = super().add(event)
        self._waiting[event.session] = replace(self._waiting[event.session], quiet=False)
        return self.get(event.session)


class SilenceLeavesTheRow(Queue):
    """Silencing marks the session but leaves what is waiting live."""

    def silence(self, session):
        self._silenced.add(session)


class RestoreIgnoresSilence(Queue):
    """A silenced one let go comes back as its kind says: a needs live."""

    def restore(self, entry, superseded=frozenset(), *, at=None):
        from dataclasses import replace
        back = super().restore(entry, superseded, at=at)
        for waiting in entry.waiting:
            row = self._waiting.get(waiting.session)
            if row is not None and row.kind is NEEDS and not waiting.quiet:
                self._waiting[waiting.session] = replace(row, quiet=False)
        return back


class NeedsEndsTheSilence(Queue):
    """A new needs from a silenced session ends its silence (the end the user did not pick)."""

    def add(self, event):
        if event.kind is NEEDS:
            self.unsilence(event.session)
        return super().add(event)


class SilenceKeepsTheHold(Attention):
    """The held one is silenced and stays held."""

    def silence(self, now, session=None):
        held = self._entry
        if held is not None and session in (None, held.session):
            self.queue.silence(held.session)
            from src.core.attention import Silenced
            return Silenced(session=held.session, project=held.project)
        return super().silence(now, session)


class SilenceTakesTheTop(Attention):
    """B held silences the top of the queue even while attending another."""

    def silence(self, now, session=None):
        if session is None:
            top = self.queue.top(quiet=True)
            session = top.session if top is not None else None
            if session is None:
                from src.core.attention import Silenced
                return Silenced()
        return super().silence(now, session)


class StaleSilenceTakesTheTop(Attention):
    """A menu row no longer waiting silences the top instead."""

    def silence(self, now, session=None):
        if session is not None and self.queue.get(session) is None and (
                self._entry is None or self._entry.session != session):
            session = None
        return super().silence(now, session)


class PromptKeepsTheSilence(Attention):
    """A prompt resolves the session and leaves it silenced."""

    def prompted(self, session, project, now):
        was = self.queue.silenced(session)
        got = super().prompted(session, project, now)
        if was:
            self.queue.silence(session)
        return Answered(released=got.released, dropped=got.dropped, caught=got.caught)


class AnyToolEndsTheSilence(Attention):
    """Every answered line ends the silence, whether it answered a needs or not."""

    def replied(self, session, now):
        got = super().replied(session, now)
        return Answered(released=got.released, dropped=got.dropped, caught=got.caught,
                        unsilenced=self.queue.unsilence(session) or got.unsilenced)


class AnswerKeepsTheSilence(Attention):
    """An answer to its own needs leaves the session silenced."""

    def replied(self, session, now):
        was = self.queue.silenced(session)
        got = super().replied(session, now)
        if was:
            self.queue.silence(session)
        return Answered(released=got.released, dropped=got.dropped, caught=got.caught)


class EndKeepsTheSilence(Attention):
    """A closed session stays in the silenced set for good."""

    def ended(self, session, project, now):
        was = self.queue.silenced(session)
        got = super().ended(session, project, now)
        if was:
            self.queue.silence(session)
        return got


class StandingSilencedAsQuiet(Attention):
    """A silenced row read as one from before the restart."""

    def standing(self, entry, now, *, watching=None):
        got = super().standing(entry, now, watching=watching)
        return Standing(Status.QUIET) if got.status is Status.SILENCED else got


class StandingSeenAsQuiet(Attention):
    """A done back from its snooze read as one from before the restart."""

    def standing(self, entry, now, *, watching=None):
        got = super().standing(entry, now, watching=watching)
        return Standing(Status.QUIET) if got.status is Status.SEEN else got


SILENCE_MUTANTS = (
    ("a done let go comes back live (pre-68)", Attention, RestoreWakesTheDone),
    ("a silenced session's new event arrives live", Attention, AddIgnoresSilence),
    ("silencing leaves what is waiting live", Attention, SilenceLeavesTheRow),
    ("a silenced needs let go comes back live", Attention, RestoreIgnoresSilence),
    ("a new needs ends the silence", Attention, NeedsEndsTheSilence),
    ("the held one silenced stays held", SilenceKeepsTheHold, Queue),
    ("B held silences the top over the held one", SilenceTakesTheTop, Queue),
    ("a stale menu row silences the top", StaleSilenceTakesTheTop, Queue),
    ("a prompt keeps the silence", PromptKeepsTheSilence, Queue),
    ("any tool line ends the silence", AnyToolEndsTheSilence, Queue),
    ("an answer to its needs keeps the silence", AnswerKeepsTheSilence, Queue),
    ("a closed session stays silenced", EndKeepsTheSilence, Queue),
    ("a silenced row read as from before the restart", StandingSilencedAsQuiet, Queue),
    ("a seen done read as from before the restart", StandingSeenAsQuiet, Queue),
)


def refuses(what: str, call, exc) -> bool:
    try:
        call()
    except exc:
        print(f"    {what:<52} refused, as it should")
        return True
    print(f"    {what:<52} <-- WENT THROUGH, and must not have")
    return False


def main() -> int:
    print(__doc__.strip().splitlines()[0])
    ok = run_all(lambda q: Attention(q))

    ok &= seen_and_silenced(lambda q: Attention(q))

    print("\n  refusals")
    ok &= refuses("a snooze of zero seconds",
                  lambda: Attention(Queue(), snooze=0), ValueError)

    print("\n  the control — every rule removed in turn, each must break the suite")
    for label, cls in (("no freeze at all", NoFreeze),
                       ("a snooze that never fires", NeverSnoozes),
                       ("the dismissed one let go instead of returned", LosesTheDismissed),
                       ("a skip that drops what it stepped away from", DropsTheSkipped),
                       ("a prompt that leaves its entry queued", PromptKeepsThePending),
                       ("a prompt that finishes the whole folder",
                        PromptFinishesTheProject),
                       ("a prompt beside the held one ending its hold",
                        PromptEndsTheFoldersHold),
                       ("a closing session that changes nothing", NeverEnds),
                       ("a closing session that finishes its folder",
                        EndFinishesTheProject),
                       ("a session closing beside the held one ending its hold",
                        EndEndsTheFoldersHold),
                       ("a lone signal skipped anyway, crying again (pre-46)",
                        SkipsTheLone),
                       ("a retry that pushes the snooze back", RetryRestartsTheSnooze),
                       ("B never reaching a restored one (task 47)", DismissSkipsTheQuiet),
                       ("a restored one signalled when nothing live waits",
                        CurrentSignalsTheQuiet),
                       ("a restored row read as waiting its turn", StandingIgnoresTheQuiet),
                       ("an aimed press falling back to the top of the queue",
                        AimedTakesTheTop),
                       ("an aimed press dropping what it stepped away from",
                        AimedLosesWhatItHeld),
                       ("a held one read as waiting, not attending",
                        StandingIgnoresTheHold),
                       ("a row marked watched without being the top one",
                        StandingWatchesAnyRow),
                       ("an answer that clears a done too (task 49)", RepliedAsPrompted),
                       ("an answer that clears nothing (task 49)", ReplyChangesNothing),
                       ("a needs never over the hold (pre-52)", NeedsNeverThrough),
                       ("a done over the hold too (task 52)", DoneThrough),
                       ("a needs over a held needs you are at (task 52)",
                        NeedsAlwaysThrough),
                       ("a new hold starting away (task 52)", AwayLeaks),
                       ("away from the hold, only a needs speaks (pre-54)",
                        NeedsOnlyWhenAway),
                       ("what comes back lands where it was (pre-54)",
                        BackWhereItWas),
                       ("away from a held needs, the queue speaks (pre-55)",
                        AwayFreesAHeldNeeds),
                       ("walking away from a held needs changes nothing (pre-56)",
                        NeverBreaksOut),
                       ("a raise that never came forward breaks out", BreaksOutUnseen),
                       ("a break-out said on every poll", BreaksOutEveryPoll),
                       ("back in its window, it keeps speaking", StaysBroken),
                       ("a held done breaks out too", DoneBreaksOut),
                       ("a new hold inherits the break-out", BrokenLeaks),
                       ("the snooze leaves the break-out standing", BrokenOutlivesSnooze),
                       ("broken out, the queue speaks instead", BrokenFreesTheQueue),
                       ("an answer never a catch (pre-56)", NoCatch),
                       ("a prompt over a done called a catch", EveryPromptCatches)):
        survived = run_all(lambda q, c=cls: c(q), quiet=True)
        ok &= not survived
        print(f"    {label:<52} "
              f"{'<-- SURVIVED, so the suite does not test it' if survived else 'caught'}")
    for label, cls, make_q in SILENCE_MUTANTS:
        survived = seen_and_silenced(lambda q, c=cls: c(q), make_q, quiet=True)
        ok &= not survived
        print(f"    {label:<52} "
              f"{'<-- SURVIVED, so the suite does not test it' if survived else 'caught'}")

    print("\n" + ("ALL CASES MATCH the known answer" if ok
                  else "SOMETHING DOES NOT MATCH — the rows above, not this line"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
