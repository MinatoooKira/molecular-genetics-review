# 本页问答：本机 DeepSeek R1 14B

网页中的“本页问答”固定使用你自己电脑上的 `deepseek-r1:14b`。网页仍然托管在 GitHub Pages，但回答请求会发给本机 `127.0.0.1` 上运行的 Ollama；不会把 API key 放进网页，也不会把页面内容上传到第三方模型服务。

## 第一次安装

1. 从 [Ollama 官方下载页](https://ollama.com/download) 安装并打开 Ollama。
2. 在终端下载 14B 模型：

   ```sh
   ollama pull deepseek-r1:14b
   ```

   该模型约占 9 GB，首次下载需要一些时间。下载完成后可用下面的命令确认：

   ```sh
   ollama list
   ```

3. 在本项目目录启动问答接口：

   ```sh
   ./start-local-backend.sh
   ```

   看到 `本机问答后端：http://127.0.0.1:8765/api/chat` 就表示接口已经启动。保持这个终端窗口运行。

4. 打开课程网页，点击右下角“本页问答”。页面会自动连接本机接口。首次提问时 14B 可能需要几秒到几十秒加载模型。

## 每次使用

打开 Ollama，然后在项目目录执行：

```sh
./start-local-backend.sh
```

不需要配置 OpenAI API key，也不会使用 `gpt-6.1-sol`。本机后端始终把模型固定为 `deepseek-r1:14b`。

## 检查是否正常

在浏览器打开 [http://127.0.0.1:8765/](http://127.0.0.1:8765/)，应看到 JSON 状态，其中 `ollama_reachable` 为 `true`、`local_model` 为 `deepseek-r1:14b`。如果网页提示无法连接，通常是 Ollama 或 `start-local-backend.sh` 没有运行。

## 重要边界

这个连接方式只对正在运行后端的这台电脑生效。GitHub Pages 是静态网页，不能替你的电脑运行 14B；其他用户打开网页时不会自动使用你的本机模型。若以后需要让其他用户也能问，需要另行准备一台持续在线的模型服务器或安全的公网转发服务。

## 不想启动后端时

问答框中的“复制提问提示词”仍然可用。它会把当前页资料和问题整理成一段中文提示词，方便复制到另一个助教窗口。
