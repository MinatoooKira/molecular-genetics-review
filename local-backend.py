#!/usr/bin/env python3
"""本机问答后端：API 密钥只从 OPENAI_API_KEY 环境变量读取。"""
import json
import os
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = os.environ.get("MOLECULAR_CHAT_HOST", "127.0.0.1")
PORT = int(os.environ.get("MOLECULAR_CHAT_PORT", "8765"))
OPENAI_URL = "https://api.openai.com/v1/responses"
MODEL = "gpt-6.1-sol"
MAX_BODY = 1_000_000

SYSTEM_PROMPT = """你是分子生物学与遗传学课程的中文助教。你正在帮助学生理解当前页面。只使用用户提供的当前页面资料和对话历史来回答，不要把页面之外的猜测说成事实。如果资料不足，直接说明不足，并给出需要补充的内容。回答使用简体中文，先给结论，再分层解释机制、图示和术语；必要时指出常见误区。不要重复整页原文，优先帮助学生建立因果链和可检验的理解。"""


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


def extract_text(data):
    chunks = []
    for item in data.get("output", []) or []:
        for content in item.get("content", []) or []:
            if content.get("type") in ("output_text", "text") and content.get("text"):
                chunks.append(content["text"])
    if chunks:
        return "\n".join(chunks).strip()
    return str(data.get("output_text") or "").strip()


class Handler(BaseHTTPRequestHandler):
    server_version = "MolecularReviewLocal/1.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("[local-backend] " + (fmt % args) + "\n")

    def do_OPTIONS(self):
        response(self, 204, {})

    def do_GET(self):
        response(self, 200, {"ok": True, "model": MODEL, "message": "本机问答服务已启动"})

    def do_POST(self):
        if self.path.rstrip("/") != "/api/chat":
            response(self, 404, {"error": "路径不存在"})
            return
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            response(self, 503, {"error": "本机未配置 OPENAI_API_KEY。请在启动服务前设置环境变量；不要把密钥写进网页或提交到 GitHub。"})
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
        request_body = {
            "model": MODEL,
            "reasoning": {"effort": "medium"},
            "instructions": SYSTEM_PROMPT,
            "input": input_text,
            "max_output_tokens": 1400,
        }
        req = urllib.request.Request(
            OPENAI_URL,
            data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
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
            response(self, error.code, {"error": f"OpenAI API：{detail}"})
            return
        except Exception as error:
            response(self, 502, {"error": f"连接 OpenAI API 失败：{error}"})
            return
        answer = extract_text(data)
        if not answer:
            response(self, 502, {"error": "OpenAI API 没有返回文字答案"})
            return
        response(self, 200, {"answer": answer, "model": MODEL})


if __name__ == "__main__":
    print(f"本机问答后端：http://{HOST}:{PORT}/api/chat")
    print("API 密钥读取自 OPENAI_API_KEY；按 Ctrl+C 停止。")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
