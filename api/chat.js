// 可选的公网转发模板：把请求转发到一台受保护的 Ollama 服务器。
// 默认模型仍固定为 deepseek-r1:14b；本机使用不需要部署这个文件。
const MODEL = 'deepseek-r1:14b';
const ALLOWED_ORIGIN = process.env.ALLOWED_ORIGIN || 'https://minatoookira.github.io';
const rateMap = new Map();

const SYSTEM_PROMPT = `你是分子生物学与遗传学课程的中文助教。你正在帮助学生理解当前页面。只使用用户提供的当前页面资料和对话历史来回答，不要把页面之外的猜测说成事实。如果资料不足，直接说明不足。回答使用简体中文，先给结论，再分层解释机制、图示和术语；必要时指出常见误区。不要重复整页原文，优先帮助学生建立因果链和可检验的理解。`;

function cleanMessages(messages) {
  return (Array.isArray(messages) ? messages : []).slice(-12).flatMap((item) => {
    if (!item || !['user', 'assistant'].includes(item.role)) return [];
    const text = String(item.content || '').trim().slice(0, 4000);
    return text ? [`${item.role === 'user' ? '用户' : '助教'}：${text}`] : [];
  });
}

function send(res, status, body, origin = ALLOWED_ORIGIN) {
  res.statusCode = status;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Access-Control-Allow-Origin', origin);
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.end(JSON.stringify(body));
}

function allowedRequest(req) {
  const origin = req.headers.origin || '';
  return !origin || origin === ALLOWED_ORIGIN;
}

function rateLimited(req) {
  const ip = String(req.headers['x-forwarded-for'] || req.socket?.remoteAddress || 'unknown').split(',')[0].trim();
  const now = Date.now();
  const recent = (rateMap.get(ip) || []).filter((t) => now - t < 60_000);
  recent.push(now);
  rateMap.set(ip, recent);
  return recent.length > 12;
}

module.exports = async function handler(req, res) {
  const origin = req.headers.origin || ALLOWED_ORIGIN;
  if (req.method === 'OPTIONS') return send(res, 204, {}, origin);
  if (req.method !== 'POST') return send(res, 405, { error: '只支持 POST' }, origin);
  if (!allowedRequest(req)) return send(res, 403, { error: '来源未获允许' }, ALLOWED_ORIGIN);
  if (rateLimited(req)) return send(res, 429, { error: '请求过于频繁，请稍后再试' }, origin);
  const base = String(process.env.OLLAMA_PUBLIC_URL || '').replace(/\/$/, '');
  if (!base) return send(res, 503, { error: '服务端尚未配置 OLLAMA_PUBLIC_URL' }, origin);

  const payload = typeof req.body === 'string' ? JSON.parse(req.body || '{}') : (req.body || {});
  const pageContext = payload.pageContext || {};
  const history = cleanMessages(payload.messages);
  if (!history.length) return send(res, 400, { error: '没有可回答的问题' }, origin);
  const pageText = String(pageContext.text || '').slice(0, 18000);
  const input = `【当前页面资料】\n${pageText}\n\n【对话历史】\n${history.join('\n')}`;
  const headers = { 'Content-Type': 'application/json' };
  if (process.env.OLLAMA_SHARED_SECRET) headers.Authorization = `Bearer ${process.env.OLLAMA_SHARED_SECRET}`;

  try {
    const upstream = await fetch(`${base}/api/chat`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        model: MODEL,
        messages: [{ role: 'system', content: SYSTEM_PROMPT }, { role: 'user', content: input }],
        stream: false,
        options: { temperature: 0.2 },
      }),
    });
    const data = await upstream.json();
    if (!upstream.ok) return send(res, upstream.status, { error: data?.error || 'Ollama 请求失败' }, origin);
    const answer = String(data?.message?.content || '').trim();
    if (!answer) return send(res, 502, { error: '模型没有返回文字答案' }, origin);
    return send(res, 200, { answer, model: MODEL, backend: 'ollama-relay' }, origin);
  } catch (error) {
    return send(res, 502, { error: `连接 Ollama 失败：${error.message}` }, origin);
  }
};
