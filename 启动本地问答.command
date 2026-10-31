#!/bin/zsh
set -u

cd "$(dirname "$0")"

if ! curl -fsS --max-time 2 http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  echo "正在启动 Ollama…"
  open -a Ollama 2>/dev/null || true
  for _ in {1..20}; do
    if curl -fsS --max-time 2 http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then break; fi
    sleep 1
  done
fi

if ! ollama list 2>/dev/null | awk 'NR > 1 {print $1}' | grep -qx 'deepseek-r1:14b'; then
  echo "还没有找到 deepseek-r1:14b。请先在终端运行："
  echo "  ollama pull deepseek-r1:14b"
  echo
  read -r "?按回车关闭窗口…"
  exit 1
fi

echo "本页问答已启动： http://127.0.0.1:8765/api/chat"
echo "保持此窗口打开，然后刷新课程网页即可。"
echo
./start-local-backend.sh
