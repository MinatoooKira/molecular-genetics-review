# 本机 DeepSeek API（纯净版）

本项目的本机后端提供一个带 API key 的 OpenAI 兼容接口。它固定调用 `deepseek-r1:14b`，不会自动附加课程页面、课件翻译或本地学习记录。

## 地址

```text
https://你的稳定公网域名/v1
```

本机直连测试时使用：

```text
http://127.0.0.1:8765/v1
```

## API key

首次运行 `start-local-backend.sh` 时，会自动生成一个只保存在本机的 key：

```sh
cat ~/.molecular-review-api-key
```

不要把 key 提交到 GitHub，也不要把它写进公开网页。把它分享给使用者后，对方才能调用纯净 API。

## curl 示例

```sh
API_KEY='粘贴你的 key'
curl https://你的稳定公网域名/v1/chat/completions \
  -H "Authorization: Bearer $API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "messages": [
      {"role": "user", "content": "请解释DNA为什么采用半保留复制。"}
    ]
  }'
```

## OpenAI SDK 示例

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://你的稳定公网域名/v1",
    api_key="你的 API key",
)

answer = client.chat.completions.create(
    model="deepseek-r1:14b",
    messages=[
        {"role": "user", "content": "请解释DNA为什么采用半保留复制。"}
    ],
)
print(answer.choices[0].message.content)
```

## 与网页问答的区别

网页问答使用 `/api/chat`，由网页自动提交当前页资料，因此适合课程复习。纯净 API 使用 `/v1/chat/completions`，只处理调用者发送的 messages。网页不直接放 API key；否则 key 会暴露给所有访客。
