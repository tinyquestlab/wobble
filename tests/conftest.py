"""What every table under `tests/tables/` is run inside (task 74).

Each table is its own process, as it is at the desk: the scripts patch module
globals freely, and a process per table is what keeps one table's patch from
becoming the next table's fixture. pytest only owns the outside — a silent
`afplay`, a private TMPDIR, the cries when the machine has none, and the verdict.
"""
from __future__ import annotations

import os
import re
import struct
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "tests" / "tables"

# A row's verdict is its last word (`Sheet.row` and every control list print it
# that way). Counting them is what tells "all rows passed" from "half of them
# never ran" — exit 0 alone cannot.
VERDICT = re.compile(r"(^|\s)(ok|caught)\s*$")

# The cries are Nintendo's and are never committed (CLAUDE.md); a clone has
# none until tools/install_hooks.py fetches them. These stand in with the same
# chunks, format and length as the ones fetched (docs/PROTOCOL.md §8.1): what the
# tables check is how a cry is cut and sent, never how it sounds.
FMT = bytes.fromhex("02000100803e00009e1f0000000204002000f403070000010000000200ff"
                    "00000000c0004000f0000000cc0130ff880118ff")
CRIES = {"pikachu.wav": (16, 15351), "pidgey.wav": (7, 6254)}   # blocks, samples


def silent_cry(blocks: int, samples: int) -> bytes:
    """An MS ADPCM file of silent 512-byte blocks: predictor 0, delta 16, no samples."""
    block = bytes([0]) + struct.pack("<hhh", 16, 0, 0) + bytes(512 - 7)
    chunks = (b"fmt " + struct.pack("<I", len(FMT)) + FMT
              + b"fact" + struct.pack("<II", 4, samples)
              + b"data" + struct.pack("<I", 512 * blocks) + block * blocks)
    return b"RIFF" + struct.pack("<I", len(chunks) + 4) + b"WAVE" + chunks


@pytest.fixture(scope="session", autouse=True)
def cries():
    """The cries a table reaches for, made only where missing and removed after."""
    folder = ROOT / "assets" / "cries"
    made = []
    for name, shape in CRIES.items():
        path = folder / name
        if not path.exists():
            folder.mkdir(parents=True, exist_ok=True)
            path.write_bytes(silent_cry(*shape))
            made.append(path)
    yield
    for path in made:
        path.unlink()


@pytest.fixture(scope="session")
def quiet(tmp_path_factory) -> Path:
    """A directory holding an `afplay` that plays nothing, to put first in PATH."""
    folder = tmp_path_factory.mktemp("quiet")
    shim = folder / "afplay"
    shim.write_text("#!/bin/sh\n# the suite only: stands in for afplay so a run is silent\n"
                    "exec sleep 0.3\n")
    shim.chmod(0o755)
    return folder


def pytest_collection_modifyitems(config, items):
    if sys.platform == "darwin":
        return
    skip = pytest.mark.skip(reason="a macOS table: it drives the real seam")
    for item in items:
        if "mac" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def run_table(quiet, tmp_path):
    """Run one table as the desk does, and fail with its own output if it fails.

    `parts` runs the table as slices side by side (each one a list of its argv)
    and adds their rows up — for a table whose time is all waiting (task 79).
    """
    def run(name: str, rows: int, *args: str, parts: list[list[str]] | None = None,
            timeout: float = 600) -> None:
        env = {**os.environ, "PATH": f"{quiet}{os.pathsep}{os.environ.get('PATH', '')}",
               "TMPDIR": str(tmp_path), "PYTHONUNBUFFERED": "1"}
        script = TABLES / f"check_{name}.py"
        procs = [subprocess.Popen([sys.executable, str(script), *argv], cwd=ROOT, env=env,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                 for argv in (parts or [list(args)])]
        deadline = time.monotonic() + timeout
        said, codes = [], []
        for proc in procs:
            try:
                out = proc.communicate(timeout=max(0.0, deadline - time.monotonic()))[0]
            except subprocess.TimeoutExpired:
                for other in procs:
                    other.kill()
                pytest.fail(f"check_{name} still running after {timeout:.0f}s\n"
                            f"{proc.communicate()[0]}")
            said.append(out)
            codes.append(proc.returncode)
        text = "\n".join(said)
        counted = sum(1 for line in text.splitlines() if VERDICT.search(line))
        assert codes == [0] * len(procs), f"check_{name} exited {codes}\n{text}"
        assert counted == rows, f"check_{name}: {counted} verdict rows, expected {rows}\n{text}"
    return run
