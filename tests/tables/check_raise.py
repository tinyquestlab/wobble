#!/usr/bin/env python3
"""Which way B takes to a session, and what it says when a way fails.

    venv/bin/python3 tests/tables/check_raise.py

Task 42. The table is run against the real `hooks.parse`, `Running.deep_link`,
`daemon.ways` and `daemon.reach`, with the seam swapped for a fake that records
what was asked and answers as told, and then against each mutant below, each of
which drops one rule and must break a row. The last section asks the real macOS
seam the questions that must come back refused (an app that is not open, a
terminal with no known tab script, a pid that just exited), so a refusal here
says something about the seam before it says anything about the session. Off
macOS that section is not run: there is no real seam to ask (task 80).

Whether the right tab or session came forward is not checked here and cannot
be: that is the desk's (docs/DESK-CHECKS.md, task 42).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src import daemon, hooks, platform_seam                          # noqa: E402
from src.core.signals import Event, Kind, Queue                       # noqa: E402

WARP, TERMINAL, DESKTOP, VSCODE = ("dev.warp.Warp-Stable", "com.apple.Terminal",
                                   "com.anthropic.claudefordesktop", "com.microsoft.VSCode")
TAB = "warp://session/" + "4de8df8f" * 4
LINK = "claude://code/continue?session=local_6b701462-aaaa"
SID = "4f6f4de9-1215-4123-a8f5-24b88942cabd"
PICK = "vscode://anthropic.claude-code/open?session=" + SID


def line(what: str, session: str, host: str = "", focus: str | None = None) -> str:
    payload = json.dumps({"session_id": session, "cwd": "/Users/x/dev/quarry"})
    fields = [what, payload, host] + ([] if focus is None else [focus])
    return "\t".join(fields) + "\n"


def entry(session: str, host: str):
    return Queue().add(Event(session=session, kind=Kind.DONE, project="quarry", at=0.0,
                             window_hint="quarry", host=host))


def run(entrypoint: str, host_session: str = "", pid: int = 4242,
        session: str = "s", cwd: str = "") -> hooks.Running:
    return hooks.Running(session=session, pid=pid, entrypoint=entrypoint,
                         host_session=host_session, cwd=cwd)


class Fake:
    """The seam's `focus` and `process`, answering from `answers` and keeping
    the order they were asked in."""

    def __init__(self, **answers) -> None:
        self.asked: list[str] = []
        self.answers = answers

    def url(self, url, *, app, timeout=1.5):
        self.asked.append(f"url {url[:14]}")
        return self.answers.get("pick" if url.startswith("vscode:") else "url",
                                (True, f"{app} opened it"))

    def tab(self, tty, *, app, timeout=30.0):
        self.asked.append(f"tab {tty}")
        return self.answers.get("tab", (True, f"selected {tty}"))

    def window(self, hint, *, app=None, fits=None, folder=None, timeout=1.5):
        self.asked.append(f"window {hint}" + (f" or open {folder}" if folder else ""))
        return self.answers.get("window", (True, f"{hint!r} came forward"))

    def tty(self, pid):
        self.asked.append(f"tty {pid}")
        return self.answers.get("tty", ("ttys003", None))

    def started(self, pid):
        return 0.0, None


OWN = ("Claude Code — quarry", VSCODE, None)


class Front:
    """`frontmost.window()`, one scripted answer per call, the last one kept (task 66)."""

    def __init__(self, *answers) -> None:
        self.answers = list(answers) or [OWN]

    def window(self):
        return self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]


def reached(fake: Fake, *args, front: Front | None = None) -> tuple:
    focus, process, frontmost = (platform_seam.focus, platform_seam.process,
                                 platform_seam.frontmost)
    platform_seam.focus = platform_seam.process = fake
    platform_seam.frontmost = front or Front()
    try:
        ok, said = daemon.reach(*args)
    finally:
        platform_seam.focus, platform_seam.process, platform_seam.frontmost = (
            focus, process, frontmost)
    return ok, said, fake.asked


def table(out) -> int:
    """Every row; returns how many were wrong."""
    bad = 0

    def row(what: str, got, want) -> None:
        nonlocal bad
        good = got == want
        bad += not good
        out(f"    {what:<66} {'ok' if good else f'<-- WRONG: {got!r}, wanted {want!r}'}")

    out("\n  the hook line's fourth field")
    row("a Warp line carries its tab's address",
        hooks.parse(line("done", "a", WARP, TAB)).focus_url, TAB)
    row("…and the host stays the host",
        hooks.parse(line("done", "a", WARP, TAB)).host, WARP)
    row("an empty fourth field leaves the host clean",
        hooks.parse(line("done", "a", VSCODE, "")).host, VSCODE)
    row("a line from before task 42 has no address, and its host",
        (hooks.parse(line("done", "a", VSCODE)).focus_url,
         hooks.parse(line("done", "a", VSCODE)).host), ("", VSCODE))
    # The address is opened, so anything that is not Warp's own shape is not one.
    for odd in ("https://example.com/x", TAB + "; open -a Calculator",
                "warp://session/../../x", "file:///etc/hosts"):
        row(f"not Warp's shape, so not an address: {odd[:34]}",
            hooks.parse(line("done", "a", WARP, odd)).focus_url, "")

    out("\n  the desktop app's link")
    row("a desktop session links to itself",
        run("claude-desktop", "local_6b701462-aaaa").deep_link, LINK)
    row("a cli session has no desktop link, whatever it carries",
        run("cli", "local_6b701462-aaaa").deep_link, "")
    row("an id the app's handler would refuse is no link",
        run("claude-desktop", "local_6b70&x=1").deep_link, "")
    row("no id, no link", run("claude-desktop").deep_link, "")

    out("\n  VS Code's link to a session's tab (task 43)")
    row("a VS Code session links to its tab",
        run("claude-vscode", session=SID).vscode_link, PICK)
    row("a cli session has no VS Code link",
        run("cli", session=SID).vscode_link, "")
    row("an id that is not a session id is no link",
        run("claude-vscode", session=SID + "&prompt=x").vscode_link, "")

    out("\n  the ways, best first")
    row("desktop: its link, then its window",
        daemon.ways(entry("d", DESKTOP), run("claude-desktop", "local_6b701462-aaaa"), ""),
        [("url", LINK), ("window", "quarry")])
    row("Warp: its tab's address, then its window",
        daemon.ways(entry("w", WARP), run("cli"), TAB), [("url", TAB), ("window", "quarry")])
    row("Terminal: the tab on its claude's tty, then its window",
        daemon.ways(entry("t", TERMINAL), run("cli", pid=81827), ""),
        [("tab", 81827), ("window", "quarry")])
    row("VS Code's extension: its window, then its tab in that window",
        daemon.ways(entry("v", VSCODE), run("claude-vscode", session=SID), ""),
        [("window", "quarry"), ("pick", PICK)])
    row("VS Code with no session id to link: its window alone",
        daemon.ways(entry("v", VSCODE), run("claude-vscode"), ""), [("window", "quarry")])
    row("not in the registry: its window",
        daemon.ways(entry("n", TERMINAL), None, ""), [("window", "quarry")])
    row("no host, so nothing to check a url against: its window",
        daemon.ways(entry("h", ""), run("claude-desktop", "local_6b701462-aaaa"), TAB),
        [("window", "quarry")])

    out("\n  trying them")
    ok, said, asked = reached(Fake(), entry("w", WARP), run("cli"), TAB)
    row("the first way that works is the last one tried",
        (ok, asked), (True, [f"url {TAB[:14]}"]))
    ok, said, asked = reached(Fake(url=(False, "Warp stayed behind")),
                              entry("w", WARP), run("cli"), TAB)
    row("a way that fails falls back to the window",
        (ok, asked), (True, [f"url {TAB[:14]}", "window quarry"]))
    row("…and the sentence says why it did not land nearer",
        said, "'quarry' came forward (first: Warp stayed behind)")
    ok, said, asked = reached(Fake(tty=(None, None)), entry("t", TERMINAL), run("cli"), "")
    row("a claude on no terminal is not asked for a tab",
        (ok, asked), (True, ["tty 4242", "window quarry"]))
    ok, said, asked = reached(Fake(tab=(False, "not allowed to control Terminal"),
                                   window=(False, "no window of Terminal names 'quarry'")),
                              entry("t", TERMINAL), run("cli"), "")
    row("every way failing says every reason, in order",
        (ok, said), (False, "not allowed to control Terminal; then "
                            "no window of Terminal names 'quarry'"))
    ok, said, asked = reached(Fake(pick=(True, "opened its tab")),
                              entry("v", VSCODE), run("claude-vscode", session=SID), "")
    row("VS Code: the window, then the tab, and the tab is what it says",
        (ok, said, asked), (True, "opened its tab", ["window quarry", "url vscode://anthr"]))
    ok, said, asked = reached(Fake(window=(False, "no window of Code names 'quarry'")),
                              entry("v", VSCODE), run("claude-vscode", session=SID), "")
    row("VS Code: no window, so no link to open a copy in the wrong one",
        (ok, asked), (False, ["window quarry"]))
    ok, said, asked = reached(Fake(pick=(False, "Code stayed behind")),
                              entry("v", VSCODE), run("claude-vscode", session=SID), "")
    row("VS Code: a tab not picked is said beside the window that came",
        (ok, said), (True, "'quarry' came forward, but its own tab was not picked: "
                           "Code stayed behind"))

    out("\n  VS Code's link only into its own window (task 66)")
    vs = (entry("v", VSCODE), run("claude-vscode", session=SID), "")
    ok, said, asked = reached(Fake(), *vs, front=Front(("Specs — juno", VSCODE, None)))
    row("another window in front by the pick: no link, NOT FOCUSED, and what was there",
        (ok, said, asked), (False, "'quarry' came forward, but by then 'Specs — juno' was "
                                   "in front, so its own tab was not picked — there it "
                                   "would open a second copy", ["window quarry"]))
    ok, said, asked = reached(Fake(), *vs, front=Front(("zsh — quarry", TERMINAL, None)))
    row("its folder's name in another app is not its window: no link",
        (ok, asked), (False, ["window quarry"]))
    ok, said, asked = reached(Fake(), *vs, front=Front((None, None, "nobody can look")))
    row("nothing readable in front: no link, and the window that came stands",
        (ok, said, asked), (True, "'quarry' came forward, but its own tab was not "
                                  "picked: nobody can look", ["window quarry"]))
    ok, said, asked = reached(Fake(pick=(True, "opened its tab")), *vs,
                              front=Front(OWN, ("Specs — juno", VSCODE, None)))
    row("the link opened but another window is in front after: NOT FOCUSED",
        (ok, said), (False, "opened its tab, but 'Specs — juno' is in front, not its "
                            "own window"))
    ok, said, asked = reached(Fake(pick=(True, "opened its tab")), *vs,
                              front=Front(OWN, (None, None, "nobody can look")))
    row("…and nothing readable after: the link stands, and why it is unchecked",
        (ok, said), (True, "opened its tab (nobody can look)"))
    ok, said, asked = reached(Fake(pick=(True, "opened its tab")), *vs,
                              front=Front(("Specs — juno", VSCODE, None),
                                          ("Specs — juno", VSCODE, None), OWN))
    row("its window read as focused a moment after the raise: still picked",
        (ok, said, asked), (True, "opened its tab", ["window quarry", "url vscode://anthr"]))
    ok, said, asked = reached(Fake(), entry("w", WARP), run("cli"), TAB,
                              front=Front(("Specs — juno", VSCODE, None)))
    row("a way with no pick is not judged by what is in front",
        (ok, asked), (True, [f"url {TAB[:14]}"]))

    out("\n  its folder, for a window on another desktop (task 69)")
    home = "/Users/x/dev-clients/quarry"
    ok, said, asked = reached(Fake(), entry("v", VSCODE),
                              run("claude-vscode", session=SID, cwd=home), "")
    row("VS Code: the window asked with its folder to open",
        asked, [f"window quarry or open {home}", "url vscode://anthr"])
    ok, said, asked = reached(Fake(), entry("v", VSCODE), run("claude-vscode", session=SID), "")
    row("…a registry with no folder: the window alone, as before",
        asked, ["window quarry", "url vscode://anthr"])
    ok, said, asked = reached(Fake(url=(False, "Warp stayed behind")), entry("w", WARP),
                              run("cli", cwd=home), TAB)
    row("Warp: never a folder, where opening one is a new tab",
        asked, [f"url {TAB[:14]}", "window quarry"])
    ok, said, asked = reached(Fake(tty=(None, None)), entry("t", TERMINAL),
                              run("cli", cwd=home), "")
    row("Terminal: never a folder either",
        asked, ["tty 4242", "window quarry"])
    ok, said, asked = reached(Fake(), entry("v", VSCODE), None, "")
    row("not in the registry: no folder to open",
        asked, ["window quarry"])
    switched = f"no window of Code on this desktop names 'quarry', so {home} was opened in it"
    ok, said, asked = reached(Fake(window=(True, switched), pick=(True, "opened its tab")),
                              entry("v", VSCODE), run("claude-vscode", session=SID, cwd=home), "")
    row("…opened by its folder, then picked: both said, the desktop switch first",
        (ok, said), (True, f"{switched}; then opened its tab"))
    ok, said, asked = reached(Fake(pick=(True, "opened its tab")), entry("v", VSCODE),
                              run("claude-vscode", session=SID, cwd=home), "")
    row("…found on this desktop with a folder in hand: the tab alone, as before",
        (ok, said), (True, "opened its tab"))
    ok, said, asked = reached(Fake(window=(True, switched)),
                              entry("v", VSCODE), run("claude-vscode", session=SID, cwd=home), "",
                              front=Front(("Specs — juno", VSCODE, None)))
    row("…opened by its folder, but another window by the pick: said once",
        said.count(home), 1)
    ok, said, asked = reached(Fake(tty=(None, None)), entry("v", VSCODE),
                              run("cli", cwd=home + "/src"), "")
    row("claude in VS Code's terminal: no folder, it may be one no window holds",
        asked, ["tty 4242", "window quarry"])
    return bad


# --- the mutants --------------------------------------------------------------
# Each drops exactly one rule. A table that still passes against one of them was
# not testing that rule.

def any_address(apply: bool):
    """Opens whatever the fourth field says."""
    hooks.WARP_URL = __import__("re").compile(".*") if apply else ORIGINAL["WARP_URL"]


def link_for_anyone(apply: bool):
    """Hands every session a desktop link, whatever started it."""
    hooks.Running.deep_link = (property(lambda self: f"claude://code/continue?session="
                                                     f"{self.host_session}"
                                                     if self.host_session else "")
                               if apply else ORIGINAL["deep_link"])


def no_fallback(apply: bool):
    """The session's own way, and nothing after it: a refused url raises nothing."""
    daemon.ways = ((lambda *a: ORIGINAL["ways"](*a)[:-1] or ORIGINAL["ways"](*a))
                   if apply else ORIGINAL["ways"])


def window_first(apply: bool):
    """Task 38's raise before the session's own way, so the tab is never picked."""
    daemon.ways = ((lambda *a: sorted(ORIGINAL["ways"](*a), key=lambda w: w[0] != "window"))
                   if apply else ORIGINAL["ways"])


def silent_misses(apply: bool):
    """Falls back and says only where it landed."""
    def reach(entry, run, focus_url):
        for way, what in daemon.ways(entry, run, focus_url):
            if way == "url":
                ok, why = platform_seam.focus.url(str(what), app=entry.host)
            elif way == "tab":
                tty, _ = platform_seam.process.tty(int(what))
                if tty is None:
                    continue
                ok, why = platform_seam.focus.tab(tty, app=entry.host)
            else:
                ok, why = platform_seam.focus.window(str(what), app=entry.host or None,
                                                     fits=entry.names)
            if ok:
                return True, why
        return False, "nothing came forward"
    daemon.reach = reach if apply else ORIGINAL["reach"]


def pick_first(apply: bool):
    """VS Code's tab link before its window, into whichever window is focused."""
    daemon.ways = ((lambda *a: sorted(ORIGINAL["ways"](*a), key=lambda w: w[0] != "pick"))
                   if apply else ORIGINAL["ways"])


def pick_unguarded(apply: bool):
    """Opens VS Code's link whatever window is in front, and trusts it (before task 66)."""
    def picked(entry, pick, said):
        opened, how = platform_seam.focus.url(pick, app=entry.host)
        return True, (how or f"opened {pick}") if opened else \
            f"{said}, but its own tab was not picked: {how}"
    daemon.picked = picked if apply else ORIGINAL["picked"]


def pick_trusted(apply: bool):
    """Checks before the link, but not after it: `focused` because it opened."""
    def picked(entry, pick, said):
        title, app, _ = daemon.settled(entry)
        if not entry.in_window(title, app):
            return ORIGINAL["picked"](entry, pick, said)
        opened, how = platform_seam.focus.url(pick, app=entry.host)
        return True, (how or f"opened {pick}") if opened else \
            f"{said}, but its own tab was not picked: {how}"
    daemon.picked = picked if apply else ORIGINAL["picked"]


def no_settle(apply: bool):
    """One read of the window in front, straight after the raise."""
    daemon.SETTLE_S = 0.0 if apply else ORIGINAL["SETTLE_S"]


def folder_to_warp(apply: bool):
    """The folder handed to the wrong app: Warp opens it as a new tab."""
    daemon.VSCODE = WARP if apply else ORIGINAL["VSCODE"]


def folder_never(apply: bool):
    """No folder ever given: a window on another desktop stays out of reach."""
    daemon.VSCODE = "nobody" if apply else ORIGINAL["VSCODE"]


def folder_for_cli(apply: bool):
    """A folder for any session VS Code hosts, its terminal's claude too."""
    daemon.folder_of = ((lambda entry, run: run.cwd or None
                         if run is not None and entry.host == ORIGINAL["VSCODE"] else None)
                        if apply else ORIGINAL["folder_of"])


def switch_unsaid(apply: bool):
    """A desktop switch dropped from the line once the tab was picked."""
    daemon.reach = ((lambda *a: (lambda ok, said: (ok, said.split("; then ")[-1]))(
                         *ORIGINAL["reach"](*a)))
                    if apply else ORIGINAL["reach"])


def vscode_link_unchecked(apply: bool):
    """Links whatever the session id says."""
    hooks.Running.vscode_link = (property(lambda self: "vscode://anthropic.claude-code/open?"
                                                       f"session={self.session}"
                                                       if self.entrypoint == "claude-vscode"
                                                       else "")
                                 if apply else ORIGINAL["vscode_link"])


ORIGINAL = {"WARP_URL": hooks.WARP_URL, "deep_link": hooks.Running.deep_link,
            "vscode_link": hooks.Running.vscode_link,
            "ways": daemon.ways, "reach": daemon.reach, "picked": daemon.picked,
            "SETTLE_S": daemon.SETTLE_S, "VSCODE": daemon.VSCODE,
            "folder_of": daemon.folder_of}
MUTANTS = [any_address, link_for_anyone, no_fallback, window_first, silent_misses,
           pick_first, vscode_link_unchecked, pick_unguarded, pick_trusted,
           no_settle, folder_never, folder_to_warp, folder_for_cli,
           switch_unsaid]


def seam_legs(out) -> int:
    """The real macOS seam, asked only what must come back refused."""
    bad = 0

    def row(what: str, got, want, why: str | None = None) -> None:
        nonlocal bad
        good = got == want
        bad += not good
        out(f"    {what:<66} {'ok' if good else f'<-- WRONG: {got!r}, wanted {want!r}'}")
        if not good and why:        # a locked screen fails these rows, and says so here
            out(f"      the seam said: {why}")

    out("\n  the real seam, legs that must refuse")
    focus, process = platform_seam.focus, platform_seam.process
    ok, why = focus.url(TAB, app="com.example.not-running")
    row("an app that is not open: nothing opened, and it says so",
        (ok, bool(why) and "not open" in why), (False, True), why)
    ok, why = focus.tab("ttys000", app=VSCODE)
    row("a terminal with no tab script: refused in words",
        (ok, bool(why) and "no way is known" in why), (False, True), why)
    gone = subprocess.Popen(["/usr/bin/true"])
    gone.wait()
    row("a pid that just exited is on no terminal: (None, None)",
        process.tty(gone.pid), (None, None))
    return bad


def main() -> int:
    print("  tasks 42 and 66 — the way B takes to a session")
    bad = table(print)
    print("\n  mutants — each must break a row")
    for mutant in MUTANTS:
        mutant(True)
        try:
            broke = table(lambda _: None)
        finally:
            mutant(False)
        bad += not broke
        print(f"    {mutant.__name__:<66} {'caught' if broke else '<-- NOT CAUGHT'}")
    if sys.platform == "darwin":
        bad += seam_legs(print)
    else:                           # the null seam refuses everything, in other words (task 80)
        print("\n  the real seam: not run, it is macOS's")
    print("\n" + ("ALL CASES MATCH the known answer" if not bad else
                  "SOMETHING DOES NOT MATCH — the rows above, not this line"))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
