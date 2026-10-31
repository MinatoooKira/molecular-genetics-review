# 公网问答接口

GitHub Pages 只负责静态网页，不能安全地保存 API key，也不能执行后端代码。要让所有访客都能使用“本页问答”，需要把 `api/chat.js` 部署到 Vercel、Cloudflare Worker 或其他云端函数。

## Vercel 部署方式

1. 在 Vercel 中导入 GitHub 仓库 `MinatoooKira/molecular-genetics-review`。
2. 在项目 Settings → Environment Variables 添加：
   - `OPENAI_API_KEY`：你的 API key（只放 Vercel，不要提交到 GitHub）
   - `ALLOWED_ORIGIN`：`https://minatoookira.github.io`
3. 部署后得到接口地址，例如：
   `https://你的项目名.vercel.app/api/chat`
4. 将这个接口地址写入 `chat-widget.js` 的 `window.MOLECULAR_CHAT_ENDPOINT` 配置并重新推送 GitHub Pages。

接口默认使用 `gpt-6.1-sol` 与 `medium` 推理强度，并有简单的来源校验和 IP 频率限制。

## 本机 DeepSeek 的位置

本机 Ollama/DeepSeek 仍可用于你自己的测试，但不会被公网访客调用。若要把本机模型暴露到公网，需要隧道、长期运行的电脑和额外的访问控制；这不适合作为公开课程站点的默认后端。
