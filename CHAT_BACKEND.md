# 本页问答后端

网页端已经在每一个主页、课程目录和逐页课件页加入“本页问答”。默认接口是本机 `http://127.0.0.1:8765/api/chat`。后端现在会优先调用本地 Ollama/DeepSeek；本地模型不可用时，才尝试回退到 OpenAI API。

## 推荐：本地 DeepSeek

这台 Mac 是 Apple Silicon，适合用 Ollama 运行小型模型。当前默认模型是 `deepseek-r1:1.5b`，占用空间约 1.1 GB；如果电脑有足够磁盘空间，可以改用质量更好的 `deepseek-r1:8b` 或 `deepseek-r1:14b`。

1. 从 [Ollama 官方下载页](https://ollama.com/download) 安装 Ollama。
2. 安装后在终端下载模型：

   ```sh
   ollama pull deepseek-r1:1.5b
   ```

3. 启动本页问答后端：

   ```sh
   ./start-local-backend.sh
   ```

4. 保持终端和 Ollama 运行，然后打开 GitHub Pages。网页右下角的“本页问答”会调用本机 DeepSeek。

如果想切换模型，可以在启动前设置：

```sh
export LOCAL_MODEL='deepseek-r1:8b'
./start-local-backend.sh
```

也可以强制只使用本地模型：

```sh
export CHAT_BACKEND='ollama'
./start-local-backend.sh
```

本机服务绑定在 `127.0.0.1`，其他电脑无法直接使用你的本地模型。若浏览器阻止 GitHub Pages 访问本机接口，可以在本机打开一份课程页面，或把接口迁移到云端。

## OpenAI 回退

如果不想使用本地模型，可以设置 API key；不要把 key 粘贴到聊天窗口，也不要写入仓库：

```sh
export CHAT_BACKEND='openai'
export OPENAI_API_KEY='在 API 平台创建的密钥'
./start-local-backend.sh
```

Pro 100 是否有可用 API 额度，要先在 ChatGPT 的设置 → Billing 或 API Platform Billing 中领取/确认对应的 API credits，并在 API organization/project 中创建密钥；ChatGPT 订阅额度和 API 额度是两套独立的计费系统。

## 模型设置

本地模式默认使用 `deepseek-r1:1.5b`。OpenAI 回退模式使用 `gpt-6.1-sol`，推理强度为 `medium`。网页只提交当前页的标题、翻译、讲解、图示、易错点、自测题和最近对话，不提交整套课件。

## 如果暂时不用 API：单独 Codex 窗口提示词

网页问答框右下角的“复制提问提示词”会把当前页资料和问题整理成一段中文提示词。可以把它粘贴到另一个 Codex 窗口，使用下面的工作方式：

```text
你是分子生物学与遗传学课程的中文助教。请只依据我随后提供的“当前页面资料”回答，不要编造页面外事实。先给结论，再按机制、图示、术语和易错点解释；如果资料不足，请明确指出。默认用简体中文，回答要帮助学生理解因果链，而不是复述整页原文。每次回答最后给出一个可以自测的问题。
```

这条路径是人工复制粘贴的备用方案；网页自动对话需要运行本机后端或部署云端接口。
