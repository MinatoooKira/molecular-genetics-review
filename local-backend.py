#!/usr/bin/env python3
"""本机问答后端：固定调用本地 Ollama 中的 DeepSeek R1 14B。"""
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = os.environ.get("MOLECULAR_CHAT_HOST", "127.0.0.1")
PORT = int(os.environ.get("MOLECULAR_CHAT_PORT", "8765"))
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
LOCAL_MODEL = os.environ.get("LOCAL_MODEL", "deepseek-r1:14b")
BACKEND_MODE = os.environ.get("CHAT_BACKEND", "ollama").lower()
MAX_BODY = 1_000_000
ALLOWED_ORIGIN = os.environ.get("MOLECULAR_CHAT_ALLOWED_ORIGIN", "https://minatoookira.github.io")
RATE_WINDOW_SECONDS = 60
RATE_LIMIT = 8
rate_lock = threading.Lock()
rate_buckets = {}
inference_slot = threading.BoundedSemaphore(1)

SYSTEM_PROMPT = """你是分子生物学与遗传学课程的中文助教。用户提供的资料只对应当前可见的一页课件。回答必须以资料中的“当前页定位”和“标题”为准，不得把其他页或课程的一般知识冒充当前页内容。用户问“这一页”时，先用一句话明确当前页编号和标题，再回答问题；如果用户的问题与当前页无关，先指出当前页是什么，并说明需要切换页面后再问。只使用用户提供的当前页资料和对话历史，不要编造。资料中已经明确写出的碱基、方向、数值、因果关系必须原样保留；不要用相关但不同的概念替换它们（例如不能把页面明确写的“5mC 脱氨产生 T”改写成“产生 U”）。如果资料不足或资料之间有冲突，明确指出，不要猜。回答使用简体中文，先给结论，再分层解释机制、图示和术语；必要时指出常见误区。"""


class BackendError(Exception):
    pass


def request_origin(handler):
    origin = handler.headers.get("Origin", "").strip()
    return origin if origin == ALLOWED_ORIGIN or origin in ("", "null", "http://localhost", "http://127.0.0.1") else None


def client_identity(handler):
    forwarded = handler.headers.get("CF-Connecting-IP") or handler.headers.get("X-Forwarded-For")
    return (forwarded or handler.client_address[0] or "unknown").split(",", 1)[0].strip()


def is_rate_limited(handler):
    now = time.monotonic()
    identity = client_identity(handler)
    with rate_lock:
        recent = [stamp for stamp in rate_buckets.get(identity, []) if now - stamp < RATE_WINDOW_SECONDS]
        recent.append(now)
        rate_buckets[identity] = recent
        return len(recent) > RATE_LIMIT


def response(handler, status, payload):
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    origin = request_origin(handler) or ALLOWED_ORIGIN
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(raw)))
    handler.send_header("Access-Control-Allow-Origin", origin)
    handler.send_header("Vary", "Origin")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
    handler.end_headers()
    handler.wfile.write(raw)


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
        if request_origin(self) is None:
            response(self, 403, {"error": "来源未获允许"})
            return
        response(self, 204, {})

    def do_GET(self):
        response(self, 200, {
            "ok": True,
            "backend_mode": BACKEND_MODE,
            "local_model": LOCAL_MODEL,
            "ollama_reachable": ollama_is_reachable(),
            "message": "本机问答服务已启动",
        })

    def do_POST(self):
        if self.path.rstrip("/") != "/api/chat":
            response(self, 404, {"error": "路径不存在"})
            return
        if request_origin(self) is None:
            response(self, 403, {"error": "来源未获允许"})
            return
        if is_rate_limited(self):
            response(self, 429, {"error": "请求过于频繁，请稍后再试"})
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
        page_no = context.get("page") or context.get("pageNumber") or "未知"
        page_count = context.get("pageCount") or "未知"
        page_title = str(context.get("title") or "未提供")[:300]
        page_header = f"课程：{context.get('course') or '未提供'}\n课件当前页：第 {page_no} / {page_count} 页\n当前页标题：{page_title}"
        input_text = "【当前页唯一资料】\n" + page_header + "\n" + page_text + "\n\n【对话历史】\n" + "\n".join(clean)

        if not inference_slot.acquire(blocking=False):
            response(self, 429, {"error": "当前正在回答另一条问题，请稍后再试"})
            return
        try:
            try:
                answer = call_ollama(input_text)
            except BackendError as error:
                response(self, 503, {"error": str(error) + f"。请确认已运行 ollama pull {LOCAL_MODEL}。"})
                return
        finally:
            inference_slot.release()
        response(self, 200, {"answer": answer, "model": LOCAL_MODEL, "backend": "ollama"})


if __name__ == "__main__":
    print(f"本机问答后端：http://{HOST}:{PORT}/api/chat")
    print(f"优先本地模型：{LOCAL_MODEL}（模式：{BACKEND_MODE}）")
    print("按 Ctrl+C 停止。")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
