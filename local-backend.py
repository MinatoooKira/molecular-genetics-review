#!/usr/bin/env python3
"""本机问答后端：优先调用本地 Ollama/DeepSeek，必要时回退到 OpenAI API。"""
import json
import os
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = os.environ.get("MOLECULAR_CHAT_HOST", "127.0.0.1")
PORT = int(os.environ.get("MOLECULAR_CHAT_PORT", "8765"))
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
LOCAL_MODEL = os.environ.get("LOCAL_MODEL", "deepseek-r1:1.5b")
OPENAI_URL = "https://api.openai.com/v1/responses"
OPENAI_MODEL = "gpt-6.1-sol"
BACKEND_MODE = os.environ.get("CHAT_BACKEND", "auto").lower()
MAX_BODY = 1_000_000

SYSTEM_PROMPT = """你是分子生物学与遗传学课程的中文助教。你正在帮助学生理解当前页面。只使用用户提供的当前页面资料和对话历史来回答，不要把页面之外的猜测说成事实。如果资料不足，直接说明不足，并给出需要补充的内容。回答使用简体中文，先给结论，再分层解释机制、图示和术语；必要时指出常见误区。不要重复整页原文，优先帮助学生建立因果链和可检验的理解。"""


class BackendError(Exception):
    pass


def response(handler, status, payload):
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(raw)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
    handler.end_headers()
    handler.wfile.write(raw)


def extract_openai_text(data):
    chunks = []
    for item in data.get("output", []) or []:
        for content in item.get("content", []) or []:
            if content.get("type") in ("output_text", "text") and content.get("text"):
                chunks.append(content["text"])
    if chunks:
        return "\n".join(chunks).strip()
    return str(data.get("output_text") or "").strip()


def call_ollama(input_text):
    body = {
        "model": LOCAL_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": input_text},
        ],
        "stream": False,
        "options": {"temperature": 0.2},
    }
    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as upstream:
            data = json.loads(upstream.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(detail).get("error", detail)
        except json.JSONDecodeError:
            pass
        raise BackendError(f"Ollama：{detail}") from error
    except Exception as error:
        raise BackendError(f"本地 Ollama 未连接：{error}") from error
    answer = str((data.get("message") or {}).get("content") or "").strip()
    if not answer:
        raise BackendError("Ollama 没有返回文字答案")
    return answer


def call_openai(input_text, api_key):
    body = {
        "model": OPENAI_MODEL,
        "reasoning": {"effort": "medium"},
        "instructions": SYSTEM_PROMPT,
        "input": input_text,
        "max_output_tokens": 1400,
    }
    req = urllib.request.Request(
        OPENAI_URL,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as upstream:
            data = json.loads(upstream.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(detail).get("error", {}).get("message", detail)
        except json.JSONDecodeError:
            pass
        raise BackendError(f"OpenAI API：{detail}") from error
    except Exception as error:
        raise BackendError(f"连接 OpenAI API 失败：{error}") from error
    answer = extract_openai_text(data)
    if not answer:
        raise BackendError("OpenAI API 没有返回文字答案")
    return answer


def ollama_is_reachable():
    tags_url = OLLAMA_URL.rsplit("/api/chat", 1)[0] + "/api/tags"
    try:
        with urllib.request.urlopen(tags_url, timeout=2) as upstream:
            return upstream.status == 200
    except Exception:
        return False


class Handler(BaseHTTPRequestHandler):
    server_version = "MolecularReviewLocal/2.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("[local-backend] " + (fmt % args) + "\n")

    def do_OPTIONS(self):
        response(self, 204, {})

    def do_GET(self):
        response(self, 200, {
            "ok": True,
            "backend_mode": BACKEND_MODE,
            "local_model": LOCAL_MODEL,
            "ollama_reachable": ollama_is_reachable(),
            "openai_configured": bool(os.environ.get("OPENAI_API_KEY", "").strip()),
            "message": "本机问答服务已启动",
        })

    def do_POST(self):
        if self.path.rstrip("/") != "/api/chat":
            response(self, 404, {"error": "路径不存在"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BODY:
            response(self, 413, {"error": "请求体过大或为空"})
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            response(self, 400, {"error": "请求不是有效 JSON"})
            return
        context = payload.get("pageContext") or {}
        messages = payload.get("messages") or []
        if not isinstance(context, dict) or not isinstance(messages, list):
            response(self, 400, {"error": "请求字段格式不正确"})
            return
        clean = []
        for item in messages[-12:]:
            if not isinstance(item, dict) or item.get("role") not in ("user", "assistant"):
                continue
            text = str(item.get("content") or "").strip()
            if text:
                clean.append(f"{'用户' if item['role'] == 'user' else '助教'}：{text[:4000]}")
        if not clean:
            response(self, 400, {"error": "没有可回答的问题"})
            return
        page_text = str(context.get("text") or "")[:18000]
        input_text = "【当前页面资料】\n" + page_text + "\n\n【对话历史】\n" + "\n".join(clean)

        local_error = None
        if BACKEND_MODE in ("auto", "ollama", "local"):
            try:
                answer = call_ollama(input_text)
                response(self, 200, {"answer": answer, "model": LOCAL_MODEL, "backend": "ollama"})
                return
            except BackendError as error:
                local_error = str(error)
                if BACKEND_MODE in ("ollama", "local"):
                    response(self, 503, {"error": local_error})
                    return

        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            hint = "本机未配置 OPENAI_API_KEY，且本地 Ollama/DeepSeek 不可用。请先安装并启动 Ollama，再运行 ollama pull " + LOCAL_MODEL + "。"
            if local_error:
                hint += f"（{local_error}）"
            response(self, 503, {"error": hint})
            return
        try:
            answer = call_openai(input_text, api_key)
        except BackendError as error:
            response(self, 502, {"error": str(error)})
            return
        response(self, 200, {"answer": answer, "model": OPENAI_MODEL, "backend": "openai"})


if __name__ == "__main__":
    print(f"本机问答后端：http://{HOST}:{PORT}/api/chat")
    print(f"优先本地模型：{LOCAL_MODEL}（模式：{BACKEND_MODE}）")
    print("按 Ctrl+C 停止。")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
