(() => {
  'use strict';

  const LOCAL_ENDPOINT = 'http://127.0.0.1:8765/api/chat';
  const ENDPOINT = (window.MOLECULAR_CHAT_ENDPOINT || localStorage.getItem('molecular-chat-endpoint') || LOCAL_ENDPOINT).trim();
  const MODEL_LABEL = 'gpt-6.1-sol · medium';
  const MAX_STORED_MESSAGES = 24;
  const MAX_CONTEXT_CHARS = 18000;
  const $ = (selector, root = document) => root.querySelector(selector);
  const esc = (value) => String(value ?? '');

  function pageNumberFromHash() {
    const match = location.hash.match(/(?:^|[?&#])p=(\d+)/);
    return match ? Math.max(1, Number(match[1])) : 1;
  }

  function flatten(value) {
    if (value == null) return '';
    if (typeof value === 'string' || typeof value === 'number') return String(value);
    if (Array.isArray(value)) return value.map(flatten).filter(Boolean).join('\n');
    if (typeof value === 'object') return Object.entries(value).map(([key, val]) => `${key}: ${flatten(val)}`).join('\n');
    return '';
  }

  function makePageContext() {
    const lessonNode = document.getElementById('lesson-data');
    let page = null;
    let pageNo = pageNumberFromHash();
    let pageCount = null;
    let courseType = document.title.includes('遗传学') ? '遗传学' : '分子生物学';
    if (lessonNode) {
      try {
        const pages = JSON.parse(lessonNode.textContent);
        pageCount = pages.length;
        page = pages[pageNo - 1] || pages[0];
      } catch (error) {
        page = null;
      }
    }
    const mainText = flatten(document.querySelector('main')?.innerText || document.body.innerText || '').replace(/\s+/g, ' ').trim();
    if (page) {
      const parts = [
        `课程：${courseType}`,
        `课件：${document.title}`,
        `当前页：第 ${pageNo} / ${pageCount} 页`,
        `标题：${flatten(page.title)}`,
        `导语：${flatten(page.lead)}`,
        `中文翻译与页内文字：${flatten(page.translation || page.text)}`,
        `逐步讲解：${flatten(page.steps)}`,
        `图示说明：${flatten(page.figure)}`,
        `易错点：${flatten(page.pitfall)}`,
        `自测题：${flatten(page.q)}`,
        `参考答案：${flatten(page.a)}`,
        `原始课件文字：${flatten(page.sourceText)}`
      ];
      return { kind: 'lecture', course: courseType, page: pageNo, pageCount, title: flatten(page.title) || document.title, text: parts.join('\n\n').slice(0, MAX_CONTEXT_CHARS) };
    }
    const visible = mainText.slice(0, 8000);
    return { kind: 'index', course: courseType, page: null, pageCount: null, title: document.title, text: `页面标题：${document.title}\n页面内容摘要：${visible}`.slice(0, MAX_CONTEXT_CHARS) };
  }

  function makeContextKey() { return `molecular-chat:${location.pathname}#p=${pageNumberFromHash()}`; }
  let contextKey = makeContextKey();
  function loadMessages() {
    try {
      const raw = localStorage.getItem(contextKey);
      const messages = JSON.parse(raw || '[]');
      return Array.isArray(messages) ? messages.filter(m => m && (m.role === 'user' || m.role === 'assistant') && typeof m.content === 'string').slice(-MAX_STORED_MESSAGES) : [];
    } catch (error) {
      return [];
    }
  }

  let context = makePageContext();
  let messages = loadMessages();
  let waiting = false;
  let widget;

  function saveMessages() {
    try { localStorage.setItem(contextKey, JSON.stringify(messages.slice(-MAX_STORED_MESSAGES))); } catch (error) { /* local storage may be disabled */ }
  }

  function buildWidget() {
    widget = document.createElement('section');
    widget.className = 'mg-chat-window';
    widget.setAttribute('aria-label', '当前页问答');
    widget.innerHTML = `
      <header class="mg-chat-header">
        <div><strong>当前页问答</strong><span class="mg-chat-meta" data-chat-title></span><span class="mg-chat-meta">默认模型：${MODEL_LABEL}</span></div>
        <div class="mg-chat-header-actions"><button type="button" data-chat-settings title="设置接口" aria-label="设置接口">⚙</button><button type="button" data-chat-close title="关闭" aria-label="关闭">×</button></div>
      </header>
      <div class="mg-chat-messages" data-chat-messages></div>
      <div class="mg-chat-compose">
        <form class="mg-chat-form" data-chat-form><label class="mg-chat-sr-only" for="mg-chat-input">输入关于当前页的问题</label><textarea id="mg-chat-input" data-chat-input rows="2" placeholder="问问这一页的概念、图示、推理或易错点…"></textarea><button class="mg-chat-send" type="submit" data-chat-send>发送</button></form>
        <div class="mg-chat-tools"><button type="button" data-chat-clear>清除本页对话</button><span class="mg-chat-status" data-chat-status></span><button type="button" data-chat-copy>复制提问提示词</button></div>
      </div>`;
    document.body.appendChild(widget);
    const launcher = document.createElement('button');
    launcher.className = 'mg-chat-launcher';
    launcher.type = 'button';
    launcher.setAttribute('aria-expanded', 'false');
    launcher.innerHTML = '<span class="mg-chat-icon">🧬</span><span>本页问答</span>';
    document.body.appendChild(launcher);

    $('[data-chat-close]', widget).addEventListener('click', () => setOpen(false));
    launcher.addEventListener('click', () => setOpen(!widget.classList.contains('open')));
    $('[data-chat-form]', widget).addEventListener('submit', sendQuestion);
    $('[data-chat-input]', widget).addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); $('[data-chat-form]', widget).requestSubmit(); }
    });
    $('[data-chat-clear]', widget).addEventListener('click', () => {
      if (!messages.length || window.confirm('清除这一页的问答记录？')) { messages = []; saveMessages(); renderMessages(); }
    });
    $('[data-chat-copy]', widget).addEventListener('click', copyPrompt);
    $('[data-chat-settings]', widget).addEventListener('click', configureEndpoint);
    renderMessages();
    updateTitle();
  }

  function setOpen(open) {
    widget.classList.toggle('open', open);
    const launcher = $('.mg-chat-launcher');
    launcher.setAttribute('aria-expanded', String(open));
    if (open) setTimeout(() => $('[data-chat-input]', widget).focus(), 50);
  }

  function updateTitle() {
    if (!widget) return;
    $('[data-chat-title]', widget).textContent = context.kind === 'lecture' ? `第 ${context.page} 页 · ${context.title}` : context.title;
  }

  function renderMessages() {
    if (!widget) return;
    const box = $('[data-chat-messages]', widget);
    box.innerHTML = '';
    if (!messages.length) {
      const empty = document.createElement('div');
      empty.className = 'mg-chat-empty';
      empty.textContent = '我会只围绕当前页面回答。你可以问：这张图怎么读？这个机制为什么这样发生？哪些概念容易混淆？';
      box.appendChild(empty);
    }
    for (const message of messages) {
      const bubble = document.createElement('div');
      bubble.className = `mg-chat-bubble ${message.role}`;
      bubble.textContent = message.content;
      box.appendChild(bubble);
    }
    box.scrollTop = box.scrollHeight;
  }

  function setStatus(html = '') {
    if (widget) $('[data-chat-status]', widget).innerHTML = html;
  }

  function setWaiting(value) {
    waiting = value;
    const send = $('[data-chat-send]', widget);
    const input = $('[data-chat-input]', widget);
    send.disabled = value;
    input.disabled = value;
    setStatus(value ? '<span class="mg-chat-typing">思考中 <i></i><i></i><i></i></span>' : '');
  }

  function explainUnavailable(message) {
    const bubble = document.createElement('div');
    bubble.className = 'mg-chat-bubble system';
    bubble.textContent = message;
    $('[data-chat-messages]', widget).appendChild(bubble);
    $('[data-chat-messages]', widget).scrollTop = $('[data-chat-messages]', widget).scrollHeight;
  }

  async function sendQuestion(event) {
    event.preventDefault();
    if (waiting) return;
    const input = $('[data-chat-input]', widget);
    const question = input.value.trim();
    if (!question) return;
    input.value = '';
    messages.push({ role: 'user', content: question });
    saveMessages();
    renderMessages();
    setWaiting(true);
    try {
      const response = await fetch(ENDPOINT, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ messages: messages.slice(-12), pageContext: context }) });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.error || `接口返回 ${response.status}`);
      const answer = String(payload.answer || payload.output_text || '').trim();
      if (!answer) throw new Error('接口没有返回文字答案');
      messages.push({ role: 'assistant', content: answer });
      saveMessages();
      renderMessages();
    } catch (error) {
      const detail = String(error?.message || error);
      const hint = detail.includes('Failed to fetch') || detail.includes('NetworkError') || detail.includes('fetch')
        ? '本机问答服务没有连接上。请先启动 local-backend.py；如果你要让其他用户也能使用，需要把同一个接口部署到云端。'
        : `问答接口暂时不可用：${detail}`;
      explainUnavailable(hint);
    } finally {
      setWaiting(false);
    }
  }

  function getPromptText(question = '') {
    return `你是这门课程的中文助教。请只根据下面“当前页面资料”回答问题；如果资料不足，请明确说不足，不要编造。回答要先给结论，再解释关键机制，必要时指出容易混淆的概念。\n\n【当前页面资料】\n${context.text}\n\n【用户问题】\n${question || '请概括本页最重要的三个知识点，并说明它们之间的关系。'}`;
  }

  async function copyPrompt() {
    const question = $('[data-chat-input]', widget).value.trim();
    const prompt = getPromptText(question);
    try {
      await navigator.clipboard.writeText(prompt);
      setStatus('提示词已复制');
      setTimeout(() => setStatus(''), 1800);
    } catch (error) {
      window.prompt('复制下面的提示词到你的 Codex 后端窗口：', prompt);
    }
  }

  function configureEndpoint() {
    const current = ENDPOINT;
    const next = window.prompt('输入问答接口地址。默认使用本机：http://127.0.0.1:8765/api/chat', current);
    if (next == null) return;
    const value = next.trim();
    if (!value) { localStorage.removeItem('molecular-chat-endpoint'); window.location.reload(); return; }
    localStorage.setItem('molecular-chat-endpoint', value);
    window.alert('接口地址已保存，刷新页面后生效。');
  }

  function refreshContext() {
    context = makePageContext();
    const nextKey = makeContextKey();
    if (nextKey !== contextKey) {
      contextKey = nextKey;
      messages = loadMessages();
      renderMessages();
    }
    updateTitle();
  }

  buildWidget();
  window.addEventListener('hashchange', () => { refreshContext(); });
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape' && widget?.classList.contains('open')) setOpen(false); });
})();
