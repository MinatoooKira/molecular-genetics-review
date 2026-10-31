#!/bin/sh
set -eu
export LOCAL_MODEL='deepseek-r1:14b'
export CHAT_BACKEND='ollama'
exec python3 "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/local-backend.py"
