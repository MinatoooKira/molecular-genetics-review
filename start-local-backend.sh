#!/bin/sh
set -eu
if [ -z "${OPENAI_API_KEY:-}" ]; then
  echo "请先在当前终端设置 OPENAI_API_KEY，再运行此脚本。不要把密钥写进网页或提交到 GitHub。" >&2
  exit 1
fi
exec python3 "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/local-backend.py"
