#!/usr/bin/env bash
# The whole argument in three acts. Needs python 3.10+ and, once, the network
# (to install `cryptography`). Nothing else: no account, no server, no model.
#
#   ./demo.sh            run it
#   DEMO_PAUSE=1 ./demo.sh   pause between acts, for showing it to people
set -euo pipefail
cd "$(dirname "$0")"

if [ -t 1 ]; then BOLD=$'\033[1m'; DIM=$'\033[2m'; OFF=$'\033[0m';
else BOLD=""; DIM=""; OFF=""; fi
act() { printf '\n%s\n%s── %s %s\n\n' "" "$BOLD" "$*" "$OFF"; }
run() {
  local shown=() arg
  for arg in "$@"; do case "$arg" in *\ *) shown+=("\"$arg\"");; *) shown+=("$arg");; esac; done
  printf '%s$ %s%s\n' "$DIM" "${shown[*]}" "$OFF"
  "$@" || true
}
beat() { [ "${DEMO_PAUSE:-}" = "1" ] && read -r -p "$(printf '%s   ↵ %s' "$DIM" "$OFF")" _ || true; }

if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
  printf 'This needs python 3.10 or newer; python3 here is %s\n' \
    "$(python3 -V 2>&1 || echo 'not installed')" >&2
  exit 1
fi

VENV="${VENV:-.venv}"
if [ ! -x "$VENV/bin/python" ]; then
  printf '%ssetting up %s (once)…%s\n' "$DIM" "$VENV" "$OFF"
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install --quiet --disable-pip-version-check -e ../python
fi
DEMO="$VENV/bin/python demo.py"

$DEMO reset >/dev/null

act "Act 1 — the agent proposes. It cannot send."
run $DEMO propose "send the offer to studio orange"
beat
run $DEMO execute go-0001 --consume
beat

act "Act 2 — a human countersigns. Now it can run, once."
run $DEMO sign go-0001
beat
run $DEMO verify go-0001
run $DEMO execute go-0001 --consume
printf '\n%s   …and a second time:%s\n' "$DIM" "$OFF"
run $DEMO execute go-0001 --consume
beat

act "Act 3 — someone edits the file after it was signed."
ACTIONS=workspace/app/state/actions.json
printf '%s$ sed s/studio-orange/competitor/ %s%s\n' "$DIM" "$ACTIONS" "$OFF"
# Not `sed -i`: BSD wants an argument after it, GNU does not. This works on both.
sed 's/studio-orange@example.com/competitor@example.com/' "$ACTIONS" > "$ACTIONS.tmp"
mv "$ACTIONS.tmp" "$ACTIONS"
run $DEMO verify go-0001
beat

printf '\n%s   And an action that was never approved, but shows up as sent:%s\n' "$DIM" "$OFF"
$VENV/bin/python - <<'PY'
import json, pathlib
state = pathlib.Path("workspace/app/state")
actions = json.loads((state / "actions.json").read_text())
actions.append({"id": "go-0002", "typ": "email", "an": "press@example.com",
                "betreff": "Statement", "anhang": [], "text": "No comment.",
                "status": "open", "erstellt": "2026-09-06T09:00:00+00:00",
                "vorschlag_von": "agent"})
(state / "actions.json").write_text(json.dumps(actions, indent=1, ensure_ascii=False))
log = json.loads((state / "send-log.json").read_text())
log["go-0002"] = "2026-09-06T09:04:00+00:00"
(state / "send-log.json").write_text(json.dumps(log, indent=1, ensure_ascii=False))
PY
run $DEMO audit

printf '\n%sThe state is plain JSON in ./workspace — read it, break it, run audit again.%s\n' \
  "$DIM" "$OFF"
