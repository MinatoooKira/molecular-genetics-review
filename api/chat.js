// 可选的公网转发模板：把请求转发到一台受保护的 Ollama 服务器。
// 默认模型仍固定为 deepseek-r1:14b；本机使用不需要部署这个文件。
const MODEL = 'deepseek-r1:14b';
const ALLOWED_ORIGIN = process.env.ALLOWED_ORIGIN || 'https://minatoookira.github.io';
const rateMap = new Map();

const SYSTEM_PROMPT = `你是分子生物学与遗传学课程的中文助教。用户提供的资料只对应当前可见的一页课件。回答必须以资料中的当前页编号和标题为准，不得把其他页或课程的一般知识冒充当前页内容。用户问“这一页”时，先用一句话明确当前页编号和标题，再回答问题；如果问题与当前页无关，先指出当前页是什么。只使用用户提供的当前页资料和对话历史，不要编造。资料中已经明确写出的碱基、方向、数值、因果关系必须原样保留；不要用相关但不同的概念替换它们（例如不能把页面明确写的“5mC 脱氨产生 T”改写成“产生 U”）。如果资料不足或资料之间有冲突，明确指出，不要猜。回答使用简体中文，先给结论，再分层解释机制、图示和术语；必要时指出常见误区。`;

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
  const pageHeader = `课程：${String(pageContext.course || '未提供')}\n课件当前页：第 ${String(pageContext.page || pageContext.pageNumber || '未知')} / ${String(pageContext.pageCount || '未知')} 页\n当前页标题：${String(pageContext.title || '未提供').slice(0, 300)}`;
  const input = `【当前页唯一资料】\n${pageHeader}\n${pageText}\n\n【对话历史】\n${history.join('\n')}`;
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
