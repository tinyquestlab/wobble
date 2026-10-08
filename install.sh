#!/bin/sh
# Set wobble up on this Mac: a Python 3.12 venv, its dependencies, the
# partners' cries, and the Claude Code hooks. Safe to run again; each step skips
# what is already done. README.md walks through what each step is for.
#
#     ./install.sh
#
# It changes one file outside this folder, ~/.claude/settings.json, and only
# after showing the exact block and asking (tools/install_hooks.py).
set -eu

cd "$(dirname "$0")"

say() { printf '\n== %s\n' "$*"; }

if [ "$(uname -s)" != "Darwin" ]; then
    echo "install.sh: wobble runs on macOS only for now." >&2
    exit 1
fi

# By name: bleak needs 3.10 or newer, and the python3 macOS ships is 3.9.
PY=$(command -v python3.12 || true)
if [ -z "$PY" ]; then
    echo "install.sh: python3.12 not found. Install it (brew install python@3.12) and run this again." >&2
    exit 1
fi

say "Python environment (venv/)"
if [ ! -x venv/bin/python3 ]; then
    "$PY" -m venv venv
fi
venv/bin/pip install --quiet --upgrade pip
venv/bin/pip install --quiet -r requirements.txt
echo "ok: $(venv/bin/python3 --version), requirements installed"

say "The partners' cries (assets/cries/, never committed — NOTICE.md)"
# Optional: without them the ball still plays its built-in sounds, so a missing
# ffmpeg or network is reported and the install goes on. One per partner (spec 04).
for partner in pikachu eevee; do
    venv/bin/python3 tools/fetch_cry.py --partner "$partner" || echo "skipped: $partner's cry can be fetched later with venv/bin/python3 tools/fetch_cry.py --partner $partner"
done

say "Claude Code hooks (~/.claude/settings.json)"
if ! venv/bin/python3 tools/install_hooks.py; then
    echo "Hooks not written. wobble hears nothing from Claude Code without them;"
    echo "add them later with venv/bin/python3 tools/install_hooks.py"
fi

say "Done"
cat <<'EOF'
Restart Claude Code so it reads the hooks, then start wobble:

    venv/bin/python3 -m src.daemon

or build it as an app you can keep in the Dock:

    venv/bin/python3 tools/build_app.py --install

The first run asks for Bluetooth; README.md has the rest.
EOF
