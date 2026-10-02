#!/bin/sh
# One Claude Code hook, appending one line to var/events. Nothing else.
#
#     hook_event.sh done      <- the Stop hook
#     hook_event.sh failed    <- the StopFailure hook: a turn an API error ended (task 64)
#     hook_event.sh needs     <- the Notification hook
#     hook_event.sh prompt    <- the UserPromptSubmit hook
#     hook_event.sh end       <- the SessionEnd hook
#     hook_event.sh answered  <- PostToolUse and PostToolUseFailure (task 49)
#     hook_event.sh asking    <- PermissionRequest: who asks the needs behind it (task 71)
#
# WHICH Claude Code hook passes which word is not this script's business:
# `src/hooks.py` owns that mapping and `tools/install_hooks.py` asks it. This
# file forwards $1.
#
# **It is /bin/sh and not python, and that is not a style choice.** As a python
# entry point it would pay for it: the venv's
# Homebrew-Framework python makes macOS LaunchServices bounce a Dock icon for
# ANY invocation of that binary, whatever it does once running — once per
# prompt and once per reply, forever. Nothing inside the script could fix it;
# only not spawning it could.
#
# Reads the hook's own JSON on stdin and appends exactly one line:
#
#     <what>\t<raw json, or empty>\t<host bundle id, or empty>\t<Warp focus URL, or empty>\n
#
# The third field is the app this session runs in (task 38): macOS sets
# __CFBundleIdentifier for whatever an app launches, and a hook is a child of
# claude, so it inherits it — `com.microsoft.VSCode` from the VS Code extension,
# measured 2026-09-28. A title alone cannot tell a terminal open in a folder
# from the editor running a session in it; the app can.
#
# The fourth is Warp's address for this session's own tab (task 42): every Warp
# shell carries `WARP_FOCUS_URL=warp://session/<id>`, and opening it selects that
# tab (measured 2026-09-28). Only that one variable is
# forwarded; the rest of claude's environment, tokens included, stays here.
#
# No field is picked apart here. This payload can carry a whole typed prompt,
# and hand-parsing arbitrary human text out of JSON with shell expansion is how
# you corrupt somebody's words rather than just a tool name. The daemon has a
# real JSON parser and is the process that is always running anyway.
#
# **Except `answered`, and only three fields of it.** That payload carries the
# tool's whole output (`tool_response`: a file read, a test run), once per tool
# call — 682 calls on 2026-09-28 — so forwarded raw it would be megabytes a day,
# cut mid-JSON at 8000 and said as an unreadable line. What the daemon needs is
# ids and a tool name, never somebody's words, and all three come before
# `tool_input` in Claude Code's key order (`session_id` first, `agent_id` only
# in a subagent, then `tool_name`; measured 2026-09-29, 2.1.160) — so only the
# text before `tool_input` is looked at, and nothing the tool said can be read
# as one of them.
#
# `asking` gets the same three and nothing else (task 71): its `tool_input` is the
# command or the file about to be written, and `agent_id` comes before it there
# too (measured 2026-10-02, 2.1.286).
#
# Always exits 0: a hook that can fail is a hook that can block a prompt.

what="$1"

# A manual run from a terminal has no writer on the other end of stdin, and
# `cat` would sit there forever. A real hook invocation's stdin is a pipe
# Claude Code writes and closes.
if [ -t 0 ]; then
    printf 'hook_event.sh is run by Claude Code, not by hand. Nothing written.\n' >&2
    exit 0
fi

payload=$(cat)

# JSON has no literal tab or newline outside \t/\n escapes, so a well-formed
# compact payload is already one line — this strips only what should not be
# there, and caps the length: a payload this big is not a real hook call, and an
# unbounded append is not a queue.
payload=$(printf '%s' "$payload" | tr -d '\n\r\t' | cut -c1-8000)

if [ "$what" = answered ] || [ "$what" = asking ]; then
    head=${payload%%\"tool_input\"*}
    sid=$(printf '%s\n' "$head" | sed -n 's/^{"session_id":"\([A-Za-z0-9_-]*\)".*/\1/p')
    tool=$(printf '%s\n' "$head" | sed -n 's/.*"tool_name":"\([A-Za-z0-9_.-]*\)".*/\1/p')
    agent=$(printf '%s\n' "$head" | sed -n 's/.*"agent_id":"\([A-Za-z0-9_-]*\)".*/\1/p')
    # No session, no line the daemon can use: `{}` is refused and counted there.
    if [ -n "$sid" ]; then
        payload="{\"session_id\":\"$sid\",\"tool_name\":\"$tool\",\"agent_id\":\"$agent\"}"
    else
        payload='{}'
    fi
fi

# var/ from this script's own path: tools/hook_event.sh is always one level
# under the repo root.
here=$(cd -- "${0%/*}" 2>/dev/null && pwd -P) || here=${0%/*}
var_dir="${here%/tools}/var"
[ -d "$var_dir" ] || mkdir -p "$var_dir" 2>/dev/null

host=$(printf '%s' "${__CFBundleIdentifier:-}" | tr -d '\n\r\t' | cut -c1-200)
focus=$(printf '%s' "${WARP_FOCUS_URL:-}" | tr -d '\n\r\t' | cut -c1-200)

printf '%s\t%s\t%s\t%s\n' "$what" "$payload" "$host" "$focus" >> "$var_dir/events" 2>/dev/null

exit 0
