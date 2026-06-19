#!/usr/bin/env bash
set -euo pipefail

export env="${env:-aliyun}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if [[ -f "$ROOT_DIR/myenv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT_DIR/myenv/bin/activate"
fi

mkdir -p connector/x

INPUT_MODE="$(python3 - <<'PY'
import json
with open("conf/config.json", "r", encoding="utf-8") as f:
    conf = json.load(f)
print(conf.get("x", {}).get("input_mode", "webhook"))
PY
)"

ENABLE_POLL_FALLBACK="$(python3 - <<'PY'
import json
with open("conf/config.json", "r", encoding="utf-8") as f:
    conf = json.load(f)
print("true" if conf.get("x", {}).get("enable_poll_fallback", True) else "false")
PY
)"

WEBHOOK_PID_FILE="$ROOT_DIR/connector/x/x_webhook.pid"
POLL_PID_FILE="$ROOT_DIR/connector/x/x_input.pid"
OUTPUT_PID_FILE="$ROOT_DIR/connector/x/x_output.pid"

for pid_file in "$WEBHOOK_PID_FILE" "$POLL_PID_FILE" "$OUTPUT_PID_FILE"; do
  if [[ -f "$pid_file" ]]; then
    kill "$(cat "$pid_file")" 2>/dev/null || true
  fi
done
sleep 1

start_webhook=false
start_poll=false

case "$INPUT_MODE" in
  webhook)
    start_webhook=true
    if [[ "$ENABLE_POLL_FALLBACK" == "true" ]]; then
      start_poll=true
    fi
    ;;
  poll)
    start_poll=true
    ;;
  both)
    start_webhook=true
    start_poll=true
    ;;
  *)
    echo "unknown x.input_mode: $INPUT_MODE" >&2
    exit 1
    ;;
esac

if [[ "$start_webhook" == "true" ]]; then
  nohup python3 connector/x/x_webhook.py > connector/x/x_webhook.log 2>&1 &
  echo $! > "$WEBHOOK_PID_FILE"
fi

if [[ "$start_poll" == "true" ]]; then
  nohup python3 connector/x/x_input.py > connector/x/x_input.log 2>&1 &
  echo $! > "$POLL_PID_FILE"
fi

nohup python3 connector/x/x_output.py >> connector/x/x_output.log 2>&1 &
echo $! > "$OUTPUT_PID_FILE"

echo "x connector started (input_mode=$INPUT_MODE)"
if [[ "$start_webhook" == "true" ]]; then
  echo "  webhook log: connector/x/x_webhook.log"
fi
if [[ "$start_poll" == "true" ]]; then
  echo "  poll log:    connector/x/x_input.log"
fi
echo "  output log:  connector/x/x_output.log"

if [[ "$start_webhook" == "true" ]]; then
  tail -f connector/x/x_webhook.log
else
  tail -f connector/x/x_output.log
fi
