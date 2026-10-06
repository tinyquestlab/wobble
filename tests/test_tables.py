"""The suite: every table that runs without the ball, and how many rows it has (task 74).

The count is the one each table printed at the desk before it moved here. A table
that exits 0 with fewer rows has stopped asking something, which is a failure.
"""
import sys

import pytest

slow, mac = pytest.mark.slow, pytest.mark.mac

TABLES = [
    ("attention", 216),
    ("queue", 27),
    ("ladder", 47),
    ("ladder_refusals", 92),
    ("cries", 88),
    ("mute", 35),
    ("hooks", 109),
    ("hooks_edges", 48),
    ("install_hooks", 85),
    ("protocol", 91),
    ("needs_rhythm", 24),
    ("link_log", 11),
    ("ball_mirror", 72),
    pytest.param("ball_worker", 106, marks=slow),
    ("menubar", 163),
    ("own_sounds", 18),
    ("seam", 53),
    pytest.param("raise", 63 if sys.platform == "darwin" else 60, marks=slow),   # 3 real-seam legs
    ("log", 34),
    pytest.param("focus", 40, marks=mac),
    pytest.param("macos_edges", 124, marks=mac),
    pytest.param("menu_light", 34, marks=mac),
]


@pytest.mark.parametrize("name, rows", TABLES)
def test_table(run_table, name, rows):
    run_table(name, rows)


@mac
def test_watching(run_table):
    """Only the scripted parts; what reads this desk's screen stays at the desk."""
    run_table("watching", 164, "--scripted")


@slow
def test_daemon_edges(run_table):
    """Its scenarios and its seventy mutants, in five slices side by side (task 79)."""
    run_table("daemon_edges", 221, parts=[["--part", "scenarios"]]
              + [["--part", f"mutants:{i}/4"] for i in range(4)],
              timeout=900)   # ~385 s here; a CI runner is slower
