#!/usr/bin/env bash
set -euo pipefail

export env=aliyun
export LUOYUN_PLATFORM=x

export ALIYUN_AK_ID="${ALIYUN_AK_ID:-ALIYUN_AK_ID}"
export ALIYUN_AK_SECRET="${ALIYUN_AK_SECRET:-ALIYUN_AK_SECRET}"
export ALIYUN_AK_SECRET_ASR="${ALIYUN_AK_SECRET_ASR:-ALIYUN_AK_SECRET_ASR}"
export OSS_ACCESS_KEY_ID="${OSS_ACCESS_KEY_ID:-OSS_ACCESS_KEY_ID}"
export OSS_ACCESS_KEY_SECRET="${OSS_ACCESS_KEY_SECRET:-OSS_ACCESS_KEY_SECRET}"
export DASHSCOPE_API_KEY="${DASHSCOPE_API_KEY:-DASHSCOPE_API_KEY}"
export ARK_API_KEY="${ARK_API_KEY:-ARK_API_KEY}"
export MINIMAX_API_KEY="${MINIMAX_API_KEY:-MINIMAX_API_KEY}"
export MINIMAX_GROUP_ID="${MINIMAX_GROUP_ID:-MINIMAX_GROUP_ID}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

target_dir="$ROOT_DIR/myenv/bin"
if [[ ":$PATH:" != *":$target_dir:"* ]]; then
  export PATH="$target_dir:$PATH"
fi

PID_FILE="$ROOT_DIR/qiaoyun/runner/qiaoyun_runner_x.pid"
if [[ -f "$PID_FILE" ]]; then
  old_pid="$(cat "$PID_FILE" || true)"
  if [[ -n "${old_pid:-}" ]]; then
    kill "$old_pid" 2>/dev/null || true
    sleep 1
  fi
fi

nohup env LUOYUN_PLATFORM=x python3 qiaoyun/runner/qiaoyun_runner.py > qiaoyun/runner/qiaoyun_runner_x.log 2>&1 &
echo $! > "$PID_FILE"
tail -f qiaoyun/runner/qiaoyun_runner_x.log
