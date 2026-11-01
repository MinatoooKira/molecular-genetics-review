# 公网问答说明

当前网页按你的要求固定连接本机 Ollama 的 `deepseek-r1:14b`。GitHub Pages 本身只能提供静态文件，因此通过 SakuraFrp TCP 隧道把 `/api/chat` 转发到本机后端，让其他访客也可以使用本机模型。

当前 SakuraFrp 地址为 `https://api.u261625.nyat.app:30689/api/chat`，电脑必须保持开机、联网并运行 Ollama、`start-local-backend.sh` 和 SakuraFrp 的 `frpc` 隧道。隧道只转发本机 `8765` 端口；本机后端只允许 GitHub Pages 来源，并限制请求频率、请求体大小和同时运行的推理数；Ollama 的 `11434` 端口没有直接暴露。

多人访问时，后端一次生成一条回答，另外最多 3 条请求进入等待队列；队列满后才会暂时拒绝新请求。

长期使用时，建议让这台 Mac 保持持续在线，并为 SakuraFrp 客户端设置开机启动。不要把 Ollama 端口直接暴露到公网，也不要把任何密钥写进网页源码。

## 带 API key 的纯净接口

本机后端另提供 OpenAI 兼容的 `/v1/chat/completions` 和 `/v1/models`。这两个接口要求 `Authorization: Bearer <API key>`，只处理调用者自己提交的消息，不附加课件上下文。用法见 [LOCAL_API.md](LOCAL_API.md)。

纯净 API 的公网基础地址是 `https://api.u261625.nyat.app:30689/v1`。

API key 不应写入 GitHub Pages 的 JavaScript；网页端继续使用 `/api/chat`，由后端按当前页面组装上下文。
