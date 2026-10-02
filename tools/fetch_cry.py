#!/usr/bin/env python3
"""Fetch Pikachu's cry and convert it into the format the ball plays.

    venv/bin/python3 tools/fetch_cry.py                 # Pikachu, into assets/cries/
    venv/bin/python3 tools/fetch_cry.py --force         # replace a cry already there
    venv/bin/python3 tools/fetch_cry.py --from my.ogg   # convert a local file instead

**The cry is never in this repository** (NOTICE.md). It is downloaded from
PokeAPI's cries collection onto the machine doing the install and written to
`assets/cries/`, which git ignores.

The ball plays one format only — MS ADPCM, 16 kHz, mono, 512-byte blocks — and
a file that is nearly right comes out of it as silence, not as an error
(PROTOCOL.md §8.1). So the ffmpeg line is written down here rather than
remembered, `resource.normalise_wav` repairs the two things ffmpeg gets wrong,
and the result is checked field by field before it is kept.

Needs `ffmpeg` (`brew install ffmpeg`). Nothing else in wobble does.
"""
from __future__ import annotations

import argparse
import shutil
import struct
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.ball import resource                 # noqa: E402

SOURCE = "https://raw.githubusercontent.com/PokeAPI/cries/main/cries/pokemon/latest/{dex}.ogg"
PIKACHU = 25
OUT = ROOT / "assets" / "cries" / "pikachu.wav"

# The ball's own numbers, from a cry the Switch sent it (PROTOCOL.md §8.1).
CODEC_MS_ADPCM = 2
RATE = 16000
# The most an upload can carry: 256 frames of 498 bytes, less the 3-byte slot
# address in front (PROTOCOL.md §7.1, §7.2). About 30 s of audio; a cry is ~1 s.
MAX_BYTES = resource.MAX_CHUNKS * resource.MAX_BODY - len(resource.STROLL_CRY_PREFIX)


def download(dex: int, into: Path) -> Path:
    """The cry as PokeAPI serves it (Ogg Vorbis), saved under `into`."""
    url = SOURCE.format(dex=dex)
    path = into / f"{dex}.ogg"
    try:
        with urllib.request.urlopen(url, timeout=30) as reply:
            path.write_bytes(reply.read())
    except (urllib.error.URLError, OSError) as exc:
        sys.exit(f"fetch_cry: could not download {url} — {exc}. Check the network, or "
                 f"convert a file you already have with --from.")
    return path


def convert(source: Path, ffmpeg: str, into: Path) -> bytes:
    """`source` in the ball's format, or exit saying why not."""
    raw = into / "ffmpeg.wav"
    # -fflags +bitexact keeps the encoder's version out of the header; the LIST
    # chunk it still writes is dropped by normalise_wav (PROTOCOL.md §8.1).
    run = subprocess.run([ffmpeg, "-v", "error", "-y", "-i", str(source),
                          "-acodec", "adpcm_ms", "-ar", str(RATE), "-ac", "1",
                          "-block_size", str(resource.BLOCK_ALIGN),
                          "-fflags", "+bitexact", str(raw)],
                         capture_output=True, text=True)
    if run.returncode != 0:
        sys.exit(f"fetch_cry: ffmpeg could not convert {source.name} — "
                 f"{run.stderr.strip()[:200]}")
    return resource.normalise_wav(raw.read_bytes())


def problem(wav: bytes) -> str | None:
    """What would make the ball stay silent with this file, or `None`."""
    found = resource._wav_chunks(wav)
    if tuple(cid for cid, _ in found) != resource.WAV_CHUNKS_KEPT:
        return "its chunks are not exactly fmt, fact, data"
    chunks = dict(found)
    codec, channels, rate, _bps, align = struct.unpack_from("<HHIIH", chunks[b"fmt "], 0)
    if (codec, channels, rate) != (CODEC_MS_ADPCM, 1, RATE):
        return f"it is codec {codec}, {channels} channel(s), {rate} Hz — not MS ADPCM mono 16 kHz"
    if align != resource.BLOCK_ALIGN:
        # The one field that fails as silence rather than as an error.
        return f"its block size is {align}, and the ball plays {resource.BLOCK_ALIGN}"
    if len(wav) > MAX_BYTES:
        return f"it is {len(wav)} bytes, and one upload carries at most {MAX_BYTES}"
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dex", type=int, default=PIKACHU,
                    help="which Pokémon's cry, by National Dex number (default: 25, Pikachu)")
    ap.add_argument("--from", dest="source", type=Path,
                    help="convert this local audio file instead of downloading")
    ap.add_argument("--out", type=Path, default=OUT,
                    help=f"where to write it (default: {OUT.relative_to(ROOT)})")
    ap.add_argument("--force", action="store_true", help="replace a cry already there")
    args = ap.parse_args()

    if args.out.exists() and not args.force:
        print(f"fetch_cry: {args.out} is already there — kept. --force replaces it.")
        return 0
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        sys.exit("fetch_cry: ffmpeg not found. Install it (brew install ffmpeg) and run "
                 "this again; wobble works without a cry, using the ball's built-in sounds.")
    if args.source is not None and not args.source.is_file():
        sys.exit(f"fetch_cry: {args.source} is not a file")

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        source = args.source or download(args.dex, work)
        wav = convert(source, ffmpeg, work)
    why = problem(wav)
    if why:
        sys.exit(f"fetch_cry: the converted cry would not play on the ball — {why}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(wav)
    print(f"fetch_cry: {args.out} — {len(wav)} bytes, MS ADPCM 16 kHz mono, ready for the ball")
    return 0


if __name__ == "__main__":
    sys.exit(main())
