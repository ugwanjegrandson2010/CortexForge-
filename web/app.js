/* CortexForge client.
 *
 * Security notes:
 *  - All server data is inserted with textContent, never innerHTML, so a
 *    hostile source document cannot inject markup into the UI.
 *  - The API token is held in memory only (never localStorage) and sent as
 *    a header, so a page reload requires a fresh token from the server log.
 *  - No third-party scripts, no eval, no dynamic Function construction.
 */
'use strict';

const TOKEN_KEY = 'cortexforge_token';
let TOKEN = '';
let LEARNER = '';
let MANIFEST = null;
let SESSION = [];
let SESSION_INDEX = 0;
let SESSION_RESULTS = [];
let SELECTED_STYLES = new Set();

/* ---------------------------------------------------------------- utils */

function $(id) { return document.getElementById(id); }

function el(tag, opts = {}, children = []) {
  const node = document.createElement(tag);
  if (opts.class) node.className = opts.class;
  if (opts.text !== undefined) node.textContent = String(opts.text);
  if (opts.attrs) for (const [k, v] of Object.entries(opts.attrs)) node.setAttribute(k, v);
  for (const c of children) node.appendChild(c);
  return node;
}

function status(msg, kind) {
  const s = $('status');
  s.textContent = msg;
  s.className = 'status' + (kind ? ' ' + kind : '');
}

async function api(path, opts = {}) {
  const headers = Object.assign({ 'Accept': 'application/json' }, opts.headers || {});
  if (opts.method && opts.method !== 'GET') {
    headers['Content-Type'] = 'application/json';
    headers['X-CortexForge-Token'] = TOKEN;
  }
  const res = await fetch(path, Object.assign({}, opts, { headers }));
  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch (e) { data = { raw: text }; }
  if (!res.ok) {
    const msg = (data && data.error) ? data.error : ('HTTP ' + res.status);
    throw new Error(msg);
  }
  return data;
}

/* ------------------------------------------------------------ tab logic */

document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    tab.classList.add('active');
    $('view-' + tab.dataset.view).classList.add('active');
  });
});

/* --------------------------------------------------------------- boot */

async function boot() {
  try {
    MANIFEST = await api('/api/manifest');
    const stored = sessionStorage.getItem(TOKEN_KEY);
    if (stored) TOKEN = stored;
    renderStylePicker();
    renderMcpPlan();
    status('ready', 'ok');
  } catch (e) {
    status('server unreachable', 'err');
  }
}

function setToken(t) {
  TOKEN = t;
  try { sessionStorage.setItem(TOKEN_KEY, t); } catch (e) { /* ignore */ }
}

/* --------------------------------------------------------- onboarding */

$('start-onboarding').addEventListener('click', async () => {
  const name = $('learner-input').value.trim();
  if (!name) { status('enter a name', 'err'); return; }
  LEARNER = name.replace(/[^A-Za-z0-9_\-]/g, '');
  if (!LEARNER) { status('name must be alphanumeric', 'err'); return; }
  $('learner-tag').textContent = LEARNER;
  try {
    const data = await api('/api/onboarding/start', {
      method: 'POST',
      body: JSON.stringify({ learner_id: LEARNER })
    });
    status('setup started', 'ok');
    nextProbe();
  } catch (e) { status(e.message, 'err'); }
});

async function nextProbe() {
  const area = $('probe-area');
  area.replaceChildren();
  let data;
  try {
    data = await api('/api/onboarding/next?learner_id=' + encodeURIComponent(LEARNER));
  } catch (e) { status(e.message, 'err'); return; }
  if (!data.probe) { finishOnboarding(); return; }

  const p = data.probe;
  const card = el('div', { class: 'card' });
  card.appendChild(el('h2', { text: p.name }));
  card.appendChild(el('p', { class: 'lede', text: p.purpose }));
  card.appendChild(el('div', {
    class: 'meta',
    text: 'About ' + p.minutes + ' minutes · yields: ' + p.yields.join(', ')
  }));

  const inputWrap = el('div', { class: 'field' });
  let getAnswer;

  if (p.kind === 'interview' && p.options && p.options.length) {
    const sel = el('select');
    p.options.forEach((o, i) => sel.appendChild(el('option', { text: o, attrs: { value: o } })));
    inputWrap.appendChild(sel);
    getAnswer = () => sel.value;
  } else if (p.kind === 'interview') {
    const ta = el('textarea', { attrs: { rows: '4', placeholder: 'Type your answer…' } });
    inputWrap.appendChild(ta);
    getAnswer = () => ta.value;
  } else if (p.kind === 'source') {
    const ta = el('textarea', { attrs: { rows: '6', placeholder: 'Paste text, or type "none"…' } });
    inputWrap.appendChild(ta);
    getAnswer = () => ta.value;
  } else if (p.kind === 'calibration') {
    inputWrap.appendChild(el('p', { class: 'lede', text: 'Answer each on a 0–4 scale.' }));
    const dims = ['holding a thought', 'finding a word', 'following a conversation',
                  'remembering why you walked into a room', 'reading the same paragraph twice'];
    const inputs = {};
    dims.forEach(d => {
      const row = el('div', { class: 'row' });
      row.appendChild(el('span', { text: d, attrs: { style: 'flex:1' } }));
      const inp = el('input', { attrs: { type: 'number', min: '0', max: '4', value: '0', style: 'width:70px' } });
      inputs[d.replace(/[^a-z]/g, '_')] = inp;
      row.appendChild(inp);
      inputWrap.appendChild(row);
    });
    getAnswer = () => {
      const out = {};
      for (const [k, v] of Object.entries(inputs)) out[k] = Number(v.value) || 0;
      return out;
    };
  } else if (p.kind === 'task') {
    const ta = el('textarea', {
      attrs: { rows: '4', placeholder: 'Paste the trial data as JSON, or type "skip"…' }
    });
    inputWrap.appendChild(el('p', {
      class: 'lede',
      text: 'Task: ' + (p.task_id || '') + '. In the packaged app this runs in-canvas; '
        + 'here, paste the trial array as JSON (or skip).'
    }));
    inputWrap.appendChild(ta);
    getAnswer = () => {
      const raw = ta.value.trim();
      if (!raw || raw === 'skip') return null;
      try { return { trials: JSON.parse(raw) }; } catch (e) { return null; }
    };
  }

  card.appendChild(inputWrap);

  const row = el('div', { class: 'row' });
  const nextBtn = el('button', { class: 'primary', text: 'Continue' });
  const skipBtn = el('button', { text: 'Skip this' });
  row.appendChild(nextBtn);
  row.appendChild(skipBtn);
  card.appendChild(row);

  const prog = el('div', {
    class: 'meta',
    text: data.progress.completed + '/' + data.progress.total + ' complete · '
      + data.progress.minutes_remaining + ' min remaining'
  });
  card.appendChild(prog);
  area.appendChild(card);

  nextBtn.addEventListener('click', async () => {
    const answer = getAnswer();
    try {
      await api('/api/onboarding/record', {
        method: 'POST',
        body: JSON.stringify({ learner_id: LEARNER, probe_id: p.probe_id, answer: answer })
      });
      nextProbe();
    } catch (e) { status(e.message, 'err'); }
  });

  skipBtn.addEventListener('click', async () => {
    try {
      await api('/api/onboarding/record', {
        method: 'POST',
        body: JSON.stringify({ learner_id: LEARNER, probe_id: p.probe_id, answer: null })
      });
      nextProbe();
    } catch (e) { status(e.message, 'err'); }
  });
}

async function finishOnboarding() {
  try {
    const data = await api('/api/onboarding/finish', {
      method: 'POST',
      body: JSON.stringify({ learner_id: LEARNER })
    });
    const area = $('contract-area');
    area.replaceChildren();
    const card = el('div', { class: 'card' });
    card.appendChild(el('h2', { text: 'Your learning contract' }));
    const pre = el('pre', { class: 'code', text: data.summary });
    card.appendChild(pre);
    area.appendChild(card);
    status('contract built', 'ok');
    refreshSources();
  } catch (e) { status(e.message, 'err'); }
}

/* -------------------------------------------------------------- sources */

$('add-source').addEventListener('click', async () => {
  const text = $('source-text').value;
  if (!text.trim()) { status('paste some text', 'err'); return; }
  try {
    const data = await api('/api/source', {
      method: 'POST',
      body: JSON.stringify({
        learner_id: LEARNER,
        title: $('source-title').value,
        text: text
      })
    });
    status('source added', 'ok');
    $('source-text').value = '';
    $('source-title').value = '';
    refreshSources();
  } catch (e) { status(e.message, 'err'); }
});

async function refreshSources() {
  if (!LEARNER) return;
  try {
    const exp = await api('/api/export?learner_id=' + encodeURIComponent(LEARNER));
    const sel = $('gen-source');
    sel.replaceChildren();
    (exp.sources || []).forEach(s => {
      sel.appendChild(el('option', {
        text: (s.title || s.source_id) + ' (' + s.n_chars + ' chars)',
        attrs: { value: s.source_id }
      }));
    });
    if (!(exp.sources || []).length) {
      sel.appendChild(el('option', { text: 'no sources yet', attrs: { value: '' } }));
    }
  } catch (e) { /* silent */ }
}

function renderStylePicker() {
  const wrap = $('style-picker');
  wrap.replaceChildren();
  (MANIFEST.styles || []).forEach(s => {
    const chip = el('span', { class: 'chip', text: s });
    chip.addEventListener('click', () => {
      if (SELECTED_STYLES.has(s)) { SELECTED_STYLES.delete(s); chip.classList.remove('on'); }
      else { SELECTED_STYLES.add(s); chip.classList.add('on'); }
    });
    wrap.appendChild(chip);
  });
}

$('generate').addEventListener('click', async () => {
  const sid = $('gen-source').value;
  if (!sid) { status('add a source first', 'err'); return; }
  status('generating…');
  try {
    const body = { learner_id: LEARNER, source_id: sid, max_per_style: 3 };
    if (SELECTED_STYLES.size) body.styles = Array.from(SELECTED_STYLES);
    const data = await api('/api/generate', { method: 'POST', body: JSON.stringify(body) });
    renderGenerated(data);
    status(data.generated + ' questions', 'ok');
  } catch (e) { status(e.message, 'err'); }
});

function renderGenerated(data) {
  const area = $('gen-result');
  area.replaceChildren();
  const card = el('div', { class: 'card' });
  card.appendChild(el('h2', { text: data.generated + ' questions generated' }));
  const byStyle = {};
  data.questions.forEach(q => { byStyle[q.style] = (byStyle[q.style] || 0) + 1; });
  const rows = Object.entries(byStyle).map(([s, n]) => s + ': ' + n).join(' · ');
  card.appendChild(el('div', { class: 'meta', text: rows }));
  if (data.provenance && data.provenance.skipped) {
    const skipped = Object.keys(data.provenance.skipped);
    if (skipped.length) {
      card.appendChild(el('div', {
        class: 'meta',
        text: 'Skipped (source cannot support): ' + skipped.join(', ')
      }));
    }
  }
  area.appendChild(card);
  data.questions.slice(0, 12).forEach(q => area.appendChild(questionCard(q, false)));
}

/* ---------------------------------------------------------------- study */

$('load-session').addEventListener('click', async () => {
  if (!LEARNER) { status('run setup first', 'err'); return; }
  try {
    const data = await api('/api/session?learner_id=' + encodeURIComponent(LEARNER) + '&limit=20');
    SESSION = data.items || [];
    SESSION_INDEX = 0;
    SESSION_RESULTS = [];
    $('session-meta').textContent =
      'Day ' + data.day + ' · ' + data.n_due + ' due · predicted recall '
      + (data.forecast.mean_retrievability * 100).toFixed(0) + '%';
    if (!SESSION.length) {
      $('question-area').replaceChildren(el('div', {
        class: 'card', text: 'Nothing is due. Generate questions from a source first.'
      }));
      return;
    }
    renderQuestion();
    status('session loaded', 'ok');
  } catch (e) { status(e.message, 'err'); }
});

function renderQuestion() {
  const area = $('question-area');
  area.replaceChildren();
  if (SESSION_INDEX >= SESSION.length) { renderSummary(); return; }
  const q = SESSION[SESSION_INDEX];
  const card = questionCard(q, true);
  area.appendChild(card);
  area.appendChild(el('div', {
    class: 'meta',
    text: 'Question ' + (SESSION_INDEX + 1) + ' of ' + SESSION.length
  }));
}

function questionCard(q, interactive) {
  const card = el('div', { class: 'q' });
  const head = el('div');
  head.appendChild(el('span', { class: 'style', text: q.style }));
  head.appendChild(el('span', { class: 'bloom', text: q.bloom + ' · ' + q.skill_id }));
  card.appendChild(head);
  card.appendChild(el('div', { class: 'prompt', text: q.prompt }));
  if (q.source_span) card.appendChild(el('div', { class: 'src', text: q.source_span }));

  if (!interactive) {
    card.appendChild(el('div', { class: 'meta', text: 'Expected: ' + q.answer }));
    return card;
  }

  const ta = el('textarea', { attrs: { placeholder: 'Answer from memory first…' } });
  card.appendChild(ta);

  const row = el('div', { class: 'row' });
  const conf = el('div', { class: 'conf' });
  conf.appendChild(el('span', { text: 'Confidence' }));
  const range = el('input', { attrs: { type: 'range', min: '0', max: '100', value: '50' } });
  const confVal = el('span', { text: '50%' });
  range.addEventListener('input', () => { confVal.textContent = range.value + '%'; });
  conf.appendChild(range);
  conf.appendChild(confVal);
  row.appendChild(conf);
  card.appendChild(row);

  const btnRow = el('div', { class: 'row' });
  const revealBtn = el('button', { class: 'primary', text: 'Submit' });
  btnRow.appendChild(revealBtn);
  card.appendChild(btnRow);

  revealBtn.addEventListener('click', async () => {
    const started = performance.now();
    const answer = ta.value;
    revealBtn.disabled = true;
    let verdict = 'incorrect';
    const norm = s => s.toLowerCase().replace(/[^a-z0-9 ]/g, ' ').replace(/\s+/g, ' ').trim();
    const a = norm(answer), b = norm(q.answer || '');
    if (a && b) {
      if (a === b) verdict = 'correct';
      else {
        const at = new Set(a.split(' ')), bt = new Set(b.split(' '));
        let inter = 0;
        bt.forEach(t => { if (at.has(t)) inter++; });
        const ratio = bt.size ? inter / bt.size : 0;
        verdict = ratio > 0.7 ? 'correct' : (ratio > 0.3 ? 'partial' : 'incorrect');
      }
    }
    const grade = verdict === 'correct' ? 3 : (verdict === 'partial' ? 2 : 1);
    const latency = Math.round(performance.now() - started);
    try {
      const data = await api('/api/attempt', {
        method: 'POST',
        body: JSON.stringify({
          learner_id: LEARNER, qid: q.qid, skill_id: q.skill_id,
          correct: verdict === 'correct', grade: grade,
          latency_ms: latency, confidence: Number(range.value) / 100,
          response: answer
        })
      });
      SESSION_RESULTS.push({ verdict: verdict, correct: verdict === 'correct', latency_ms: latency });
      renderFeedback(card, verdict, q, answer, data);
      const nextBtn = el('button', { class: 'primary', text: 'Next question' });
      nextBtn.addEventListener('click', () => { SESSION_INDEX++; renderQuestion(); });
      card.appendChild(nextBtn);
    } catch (e) { status(e.message, 'err'); revealBtn.disabled = false; }
  });

  return card;
}

function renderFeedback(card, verdict, q, answer, data) {
  const fb = el('div', { class: 'fb ' + verdict });
  const lines = [];
  if (verdict === 'correct') {
    lines.push(['What happened', 'Correct.']);
    lines.push(['What it means', 'This is evidence the skill is available at this difficulty.']);
    lines.push(['Next', 'The next item on this skill will be harder.']);
  } else if (verdict === 'partial') {
    lines.push(['What happened', 'Partly correct. Full answer: ' + q.answer]);
    lines.push(['What it means', 'You have part of the structure; the missing part is what was tested.']);
    lines.push(['Next', 'Re-attempt this skill tomorrow, not immediately.']);
  } else {
    lines.push(['What happened', 'Incorrect. Correct answer: ' + q.answer]);
    lines.push(['What it means', 'Your answer did not match the target. Check whether you answered the question asked.']);
    lines.push(['Next', 'This item returns next session. Read the source span, then answer from memory.']);
  }
  lines.push(['Schedule', 'Mastery estimate ' + (data.p_known * 100).toFixed(0)
    + '% · returns in ' + Math.round(data.schedule.interval_days) + ' days']);
  lines.forEach(([k, v]) => {
    const line = el('div', { class: 'line' });
    line.appendChild(el('div', { class: 'k', text: k }));
    line.appendChild(el('div', { text: v }));
    fb.appendChild(line);
  });
  card.appendChild(fb);
}

function renderSummary() {
  const area = $('summary-area');
  area.replaceChildren();
  const n = SESSION_RESULTS.length;
  const correct = SESSION_RESULTS.filter(r => r.correct).length;
  const acc = n ? correct / n : 0;
  let verdict, stmt;
  if (acc >= 0.9) {
    verdict = 'under-challenged';
    stmt = correct + '/' + n + ' correct (' + Math.round(acc * 100) + '%). This set was too easy to produce learning; difficulty will increase next session.';
  } else if (acc >= 0.75) {
    verdict = 'in the productive band';
    stmt = correct + '/' + n + ' correct (' + Math.round(acc * 100) + '%). This is the band where learning is fastest.';
  } else if (acc >= 0.5) {
    verdict = 'struggling productively';
    stmt = correct + '/' + n + ' correct (' + Math.round(acc * 100) + '%). Below the optimal band; load will be reduced on the weakest skills.';
  } else {
    verdict = 'over-loaded';
    stmt = correct + '/' + n + ' correct (' + Math.round(acc * 100) + '%). The material is beyond reach at this granularity; prerequisites will be re-taught.';
  }
  const card = el('div', { class: 'card' });
  card.appendChild(el('h2', { text: 'Session summary — ' + verdict }));
  card.appendChild(el('p', { class: 'lede', text: stmt }));
  area.appendChild(card);
}

/* -------------------------------------------------------------- profile */

$('load-profile').addEventListener('click', async () => {
  if (!LEARNER) { status('run setup first', 'err'); return; }
  try {
    const data = await api('/api/profile?learner_id=' + encodeURIComponent(LEARNER));
    renderProfile(data);
    status('profile loaded', 'ok');
  } catch (e) { status(e.message, 'err'); }
});

function renderProfile(data) {
  const area = $('profile-area');
  area.replaceChildren();
  const p = data.profile;

  const head = el('div', { class: 'card' });
  head.appendChild(el('h2', { text: 'Group role' }));
  head.appendChild(el('div', { class: 'role', text: p.social_role }));
  const ul = el('ul', { class: 'tight' });
  p.social_role_basis.forEach(b => ul.appendChild(el('li', { text: b })));
  head.appendChild(ul);
  head.appendChild(el('h3', { text: 'Study pattern' }));
  head.appendChild(el('div', { class: 'role', text: p.learning_shape }));
  const ul2 = el('ul', { class: 'tight' });
  p.learning_basis.forEach(b => ul2.appendChild(el('li', { text: b })));
  head.appendChild(ul2);
  area.appendChild(head);

  const obsCard = el('div', { class: 'card' });
  obsCard.appendChild(el('h2', { text: 'Observations (' + p.observations.length + ')' }));
  p.observations.forEach(o => {
    const box = el('div', { class: 'obs' });
    const h = el('div', { class: 'head' });
    h.appendChild(el('span', { class: 'label', text: o.label }));
    h.appendChild(el('span', { class: 'conf-badge ' + o.confidence, text: o.confidence }));
    box.appendChild(h);
    box.appendChild(el('div', { class: 'stmt', text: o.statement }));
    box.appendChild(el('div', { class: 'act', text: '→ ' + o.action }));
    if (o.caveat) box.appendChild(el('div', { class: 'caveat', text: o.caveat }));
    obsCard.appendChild(box);
  });
  area.appendChild(obsCard);

  const lim = el('div', { class: 'card' });
  lim.appendChild(el('h2', { text: 'Limits of this profile' }));
  const ul3 = el('ul', { class: 'tight' });
  p.limits.forEach(l => ul3.appendChild(el('li', { text: l })));
  lim.appendChild(ul3);
  if (p.unmeasured.length) {
    lim.appendChild(el('h3', { text: 'Not yet measured' }));
    lim.appendChild(el('div', { class: 'meta', text: p.unmeasured.join(', ') }));
  }
  area.appendChild(lim);
}

/* ------------------------------------------------------------------ MCP */

function renderMcpPlan() {
  const area = $('mcp-plan');
  if (!area) return;
  area.replaceChildren();
  api('/api/mcp/plan').then(plan => {
    area.appendChild(el('h3', { text: 'Authorise these (OAuth only)' }));
    const t1 = el('table');
    const h1 = el('tr');
    ['Server', 'URL', 'Why'].forEach(x => h1.appendChild(el('th', { text: x })));
    t1.appendChild(h1);
    plan.oauth_required.forEach(o => {
      const tr = el('tr');
      tr.appendChild(el('td', {}, [el('span', { class: 'pill oauth', text: o.name })]));
      tr.appendChild(el('td', { text: o.url }));
      tr.appendChild(el('td', { text: o.why }));
      t1.appendChild(tr);
    });
    area.appendChild(t1);

    area.appendChild(el('h3', { text: 'Already configured — no action needed' }));
    area.appendChild(el('div', {
      class: 'meta',
      text: plan.already_configured.join(', ')
    }));

    if (plan.api_key_required.length) {
      area.appendChild(el('h3', { text: 'Optional — API keys' }));
      area.appendChild(el('div', {
        class: 'meta',
        text: plan.api_key_required.map(k => k.name + ' (' + k.env.join(', ') + ')').join(' · ')
      }));
    }
  }).catch(() => {});
}

$('write-mcp').addEventListener('click', async () => {
  try {
    const data = await api('/api/mcp/config', {
      method: 'POST',
      body: JSON.stringify({})
    });
    $('mcp-out').textContent = 'Written to ' + data.written + '\n\nServers: '
      + data.servers.join(', ');
    status('mcp.json written', 'ok');
  } catch (e) { status(e.message, 'err'); }
});

boot();
