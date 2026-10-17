/* CortexForge client — redesigned UI.
 *
 * Security notes:
 *  - All server data is inserted with textContent, never innerHTML, so a
 *    hostile source document cannot inject markup into the UI.
 *  - The API token is held in sessionStorage only and sent as a header.
 *  - No third-party scripts except Three.js (loaded from /static/lib/three.min.js).
 *  - No eval, no dynamic Function construction.
 */
'use strict';

/* ------------------------------------------------------------------ state */

const TOKEN_KEY = 'cortexforge_token';
const SESSION_KEY = 'cortexforge_session';
let TOKEN = '';
let SESSION_TOKEN = '';
let ACCOUNT = null;
let LEARNER = '';
let MANIFEST = null;
let SESSION = [];
let SESSION_INDEX = 0;
let SESSION_RESULTS = [];
let SELECTED_STYLES = new Set();
let TUTOR_STATE = null;

/* ------------------------------------------------------------ DOM helpers */

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

/* ------------------------------------------------------------- API client */

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

/* --------------------------------------------------------- reduced motion */

const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/* -------------------------------------------------- Three.js background */

(function initBackground() {
  if (REDUCED) return;
  const canvas = $('bg-canvas');
  if (!canvas || typeof THREE === 'undefined') return;

  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(window.innerWidth, window.innerHeight);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 100);
  camera.position.z = 5;

  const COUNT = 50;
  const positions = new Float32Array(COUNT * 3);
  const velocities = new Float32Array(COUNT * 3);
  for (let i = 0; i < COUNT; i++) {
    positions[i * 3]     = (Math.random() - 0.5) * 12;
    positions[i * 3 + 1] = (Math.random() - 0.5) * 8;
    positions[i * 3 + 2] = (Math.random() - 0.5) * 4;
    velocities[i * 3]     = (Math.random() - 0.5) * 0.002;
    velocities[i * 3 + 1] = (Math.random() - 0.5) * 0.002;
    velocities[i * 3 + 2] = (Math.random() - 0.5) * 0.001;
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  const mat = new THREE.PointsMaterial({
    color: 0x4f8cff, size: 0.05, transparent: true, opacity: 0.3,
    sizeAttenuation: true, depthWrite: false,
  });
  const points = new THREE.Points(geo, mat);
  scene.add(points);

  let rafId = null;
  let running = true;

  function tick() {
    if (!running) return;
    rafId = requestAnimationFrame(tick);
    const pos = geo.attributes.position.array;
    for (let i = 0; i < COUNT; i++) {
      pos[i * 3]     += velocities[i * 3];
      pos[i * 3 + 1] += velocities[i * 3 + 1];
      pos[i * 3 + 2] += velocities[i * 3 + 2];
      if (pos[i * 3] > 6) pos[i * 3] = -6; else if (pos[i * 3] < -6) pos[i * 3] = 6;
      if (pos[i * 3 + 1] > 4) pos[i * 3 + 1] = -4; else if (pos[i * 3 + 1] < -4) pos[i * 3 + 1] = 4;
    }
    geo.attributes.position.needsUpdate = true;
    renderer.render(scene, camera);
  }

  function start() { if (!running && !rafId) { running = true; tick(); } }
  function stop()  { running = false; if (rafId) { cancelAnimationFrame(rafId); rafId = null; } }

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) stop(); else start();
  });

  window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  });

  window.addEventListener('pagehide', () => {
    stop();
    geo.dispose(); mat.dispose(); renderer.dispose();
  });

  tick();
})();

/* ------------------------------------------------------ auth logic */

function switchAuthTab(tab) {
  document.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.auth-form').forEach(f => f.classList.add('hidden'));
  document.querySelector(`.auth-tab[data-auth="${tab}"]`).classList.add('active');
  $(`auth-form-${tab}`).classList.remove('hidden');
}

document.querySelectorAll('.auth-tab').forEach(tab => {
  tab.addEventListener('click', () => switchAuthTab(tab.dataset.auth));
});

$('forgot-link').addEventListener('click', (e) => {
  e.preventDefault();
  switchAuthTab('reset');
});

$('back-to-login').addEventListener('click', (e) => {
  e.preventDefault();
  switchAuthTab('login');
});

// Password strength meter
$('reg-password').addEventListener('input', (e) => {
  const pw = e.target.value;
  const bar = $('pw-strength');
  let strength = 0;
  if (pw.length >= 8) strength++;
  if (pw.length >= 12) strength++;
  if (/[A-Z]/.test(pw)) strength++;
  if (/[0-9]/.test(pw)) strength++;
  if (/[^A-Za-z0-9]/.test(pw)) strength++;
  const colors = ['#f87171', '#fbbf24', '#34d399', '#4f8cff', '#a78bfa'];
  const widths = ['20%', '40%', '60%', '80%', '100%'];
  bar.innerHTML = '';
  if (pw.length > 0) {
    const fill = el('div', { class: 'pw-strength-bar' });
    fill.style.width = widths[strength - 1] || '0%';
    fill.style.background = colors[strength - 1] || 'transparent';
    bar.appendChild(fill);
  }
});

async function doLogin() {
  const email = $('login-email').value.trim();
  const password = $('login-password').value;
  if (!email || !password) { status('enter email and password', 'err'); return; }
  const btn = $('login-btn');
  btn.disabled = true;
  btn.textContent = 'Signing in…';
  try {
    const data = await api('/api/account/login', {
      method: 'POST',
      body: JSON.stringify({ email, password })
    });
    SESSION_TOKEN = data.session_token;
    LEARNER = data.learner_id;
    ACCOUNT = { account_id: data.account_id, email: data.email, display_name: data.display_name };
    try { sessionStorage.setItem(SESSION_KEY, SESSION_TOKEN); } catch (e) {}
    showMainApp();
    status('signed in', 'ok');
  } catch (e) { status(e.message, 'err'); }
  finally { btn.disabled = false; btn.textContent = 'Sign In'; }
}

async function doRegister() {
  const name = $('reg-name').value.trim();
  const email = $('reg-email').value.trim();
  const password = $('reg-password').value;
  if (!email || !password) { status('enter email and password', 'err'); return; }
  const btn = $('register-btn');
  btn.disabled = true;
  btn.textContent = 'Creating…';
  try {
    const data = await api('/api/account/create', {
      method: 'POST',
      body: JSON.stringify({ email, password, display_name: name })
    });
    status('account created — check your email', 'ok');
    switchAuthTab('login');
  } catch (e) { status(e.message, 'err'); }
  finally { btn.disabled = false; btn.textContent = 'Create Account'; }
}

async function doReset() {
  const email = $('reset-email').value.trim();
  if (!email) { status('enter your email', 'err'); return; }
  const btn = $('reset-btn');
  btn.disabled = true;
  btn.textContent = 'Sending…';
  try {
    await api('/api/account/reset-request', {
      method: 'POST',
      body: JSON.stringify({ email })
    });
    status('reset link sent if email exists', 'ok');
    switchAuthTab('login');
  } catch (e) { status(e.message, 'err'); }
  finally { btn.disabled = false; btn.textContent = 'Send Reset Link'; }
}

async function doLogout() {
  if (SESSION_TOKEN) {
    try { await api('/api/account/logout', { method: 'POST', body: JSON.stringify({ session_token: SESSION_TOKEN }) }); } catch (e) {}
  }
  SESSION_TOKEN = '';
  ACCOUNT = null;
  LEARNER = '';
  try { sessionStorage.removeItem(SESSION_KEY); } catch (e) {}
  $('view-main').classList.remove('active');
  $('view-auth').classList.add('active');
  status('signed out');
}

$('login-btn').addEventListener('click', doLogin);
$('register-btn').addEventListener('click', doRegister);
$('reset-btn').addEventListener('click', doReset);
$('logout-btn').addEventListener('click', doLogout);

/* --------------------------------------------------------- main app */

function showMainApp() {
  $('view-auth').classList.remove('active');
  $('view-main').classList.add('active');
  $('learner-tag').textContent = ACCOUNT?.display_name || LEARNER;
  boot();
}

/* --------------------------------------------------------------- tabs */

document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    tab.classList.add('active');
    const viewName = 'view-' + tab.dataset.view;
    const viewEl = $(viewName);
    if (viewEl) viewEl.classList.add('active');
  });
});

/* --------------------------------------------------------------- boot */

async function boot() {
  try {
    MANIFEST = await api('/api/manifest');
    const stored = sessionStorage.getItem(TOKEN_KEY);
    if (stored) { TOKEN = stored; }
    const storedSession = sessionStorage.getItem(SESSION_KEY);
    if (storedSession) {
      SESSION_TOKEN = storedSession;
      try {
        const sess = await api('/api/account/session', {
          method: 'POST',
          body: JSON.stringify({ session_token: SESSION_TOKEN })
        });
        ACCOUNT = sess;
        LEARNER = sess.learner_id;
        $('learner-tag').textContent = sess.display_name || sess.email;
      } catch (e) {
        SESSION_TOKEN = '';
        try { sessionStorage.removeItem(SESSION_KEY); } catch (e2) {}
      }
    }
    renderStylePicker();
    renderMcpPlan();
    loadDashboard();
    status('ready', 'ok');
  } catch (e) {
    status('server unreachable', 'err');
  }
}

/* --------------------------------------------------------- dashboard */

async function loadDashboard() {
  if (!LEARNER) return;
  try {
    const data = await api('/api/profile?learner_id=' + encodeURIComponent(LEARNER));
    const p = data.profile;
    const s = data.session;
    $('dash-greeting').textContent = `Welcome back, ${ACCOUNT?.display_name || LEARNER}`;
    $('dash-summary').textContent =
      `${s.n} total attempts · ${s.correct} correct · ` +
      (s.accuracy > 0 ? Math.round(s.accuracy * 100) + '% accuracy' : 'no data yet');

    // Progress grid
    const progressEl = $('dash-progress');
    progressEl.replaceChildren();
    const metrics = [
      { label: 'Total Attempts', value: s.n },
      { label: 'Accuracy', value: s.accuracy > 0 ? Math.round(s.accuracy * 100) + '%' : '—' },
      { label: 'Skills Tracked', value: (p.observations || []).length },
      { label: 'Questions', value: (p.unmeasured || []).length > 0 ? 'Active' : 'None' },
    ];
    metrics.forEach(m => {
      const card = el('div', { class: 'progress-card' });
      card.appendChild(el('div', { class: 'progress-value', text: String(m.value) }));
      card.appendChild(el('div', { class: 'progress-label', text: m.label }));
      progressEl.appendChild(card);
    });

    // Recent sessions
    const sessionsEl = $('dash-sessions');
    sessionsEl.replaceChildren();
    const recentText = el('div', { class: 'meta', text: 'No sessions yet. Start your first session to see progress here.' });
    sessionsEl.appendChild(recentText);
  } catch (e) { /* silent */ }
}

$('dash-start-session').addEventListener('click', () => {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.querySelector('.tab[data-view="study"]').classList.add('active');
  $('view-study').classList.add('active');
});

$('dash-add-source').addEventListener('click', () => {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.querySelector('.tab[data-view="sources"]').classList.add('active');
  $('view-sources').classList.add('active');
});

/* -------------------------------------------------------------- sources */

$('add-source').addEventListener('click', async () => {
  const text = $('source-text').value;
  if (!text.trim()) { status('paste some text', 'err'); return; }
  const btn = $('add-source');
  btn.disabled = true;
  btn.textContent = 'Adding…';
  try {
    await api('/api/source', {
      method: 'POST',
      body: JSON.stringify({ learner_id: LEARNER, title: $('source-title').value, text })
    });
    status('source added', 'ok');
    $('source-text').value = '';
    $('source-title').value = '';
    refreshSources();
  } catch (e) { status(e.message, 'err'); }
  finally { btn.disabled = false; btn.textContent = 'Add Source'; }
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
  const btn = $('generate');
  btn.disabled = true;
  btn.textContent = 'Generating…';
  try {
    const body = { learner_id: LEARNER, source_id: sid, max_per_style: 3 };
    if (SELECTED_STYLES.size) body.styles = Array.from(SELECTED_STYLES);
    const data = await api('/api/generate', { method: 'POST', body: JSON.stringify(body) });
    renderGenerated(data);
    status(data.generated + ' questions', 'ok');
  } catch (e) { status(e.message, 'err'); }
  finally { btn.disabled = false; btn.textContent = 'Generate'; }
});

function renderGenerated(data) {
  const area = $('gen-result');
  area.replaceChildren();
  const card = el('div', { class: 'card' });
  card.appendChild(el('h2', { text: data.generated + ' questions generated' }));
  area.appendChild(card);
  data.questions.slice(0, 12).forEach(q => area.appendChild(questionCard(q, false)));
}

/* ---------------------------------------------------------------- study */

$('load-session').addEventListener('click', async () => {
  if (!LEARNER) { status('sign in first', 'err'); return; }
  const btn = $('load-session');
  btn.disabled = true;
  btn.textContent = 'Loading…';
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
  finally { btn.disabled = false; btn.textContent = 'Load Session'; }
});

function renderQuestion() {
  const area = $('question-area');
  area.replaceChildren();
  if (SESSION_INDEX >= SESSION.length) { renderSummary(); return; }
  const q = SESSION[SESSION_INDEX];
  area.appendChild(questionCard(q, true));
}

function questionCard(q, interactive) {
  const card = el('div', { class: 'q' });
  const head = el('div');
  head.appendChild(el('span', { class: 'style', text: q.style }));
  head.appendChild(el('span', { class: 'bloom', text: q.bloom }));
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
  const submitBtn = el('button', { class: 'primary', text: 'Submit' });
  btnRow.appendChild(submitBtn);
  card.appendChild(btnRow);

  submitBtn.addEventListener('click', async () => {
    const started = performance.now();
    const answer = ta.value;
    submitBtn.disabled = true;
    submitBtn.textContent = 'Checking…';
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
      await api('/api/attempt', {
        method: 'POST',
        body: JSON.stringify({
          learner_id: LEARNER, qid: q.qid, skill_id: q.skill_id,
          correct: verdict === 'correct', grade,
          latency_ms: latency, confidence: Number(range.value) / 100,
          response: answer
        })
      });
      SESSION_RESULTS.push({ verdict, correct: verdict === 'correct', latency_ms: latency });
      renderFeedback(card, verdict, q);
      const nextBtn = el('button', { class: 'primary', text: 'Next question' });
      nextBtn.addEventListener('click', () => { SESSION_INDEX++; renderQuestion(); });
      card.appendChild(nextBtn);
    } catch (e) { status(e.message, 'err'); submitBtn.disabled = false; submitBtn.textContent = 'Submit'; }
  });

  return card;
}

function renderFeedback(card, verdict, q) {
  const fb = el('div', { class: 'fb ' + verdict });
  const lines = [];
  if (verdict === 'correct') {
    lines.push(['Result', 'Correct.']);
    lines.push(['What it means', 'This is evidence the skill is available at this difficulty.']);
  } else if (verdict === 'partial') {
    lines.push(['Result', 'Partly correct. Full answer: ' + q.answer]);
    lines.push(['What it means', 'You have part of the structure; the missing part is what was tested.']);
  } else {
    lines.push(['Result', 'Incorrect. Correct answer: ' + q.answer]);
    lines.push(['What it means', 'Your answer did not match the target. Check whether you answered the question asked.']);
  }
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
  if (acc >= 0.9) { verdict = 'under-challenged'; stmt = 'This set was too easy; difficulty will increase.'; }
  else if (acc >= 0.75) { verdict = 'in the productive band'; stmt = 'This is the band where learning is fastest.'; }
  else if (acc >= 0.5) { verdict = 'struggling productively'; stmt = 'Below the optimal band; load will be reduced.'; }
  else { verdict = 'over-loaded'; stmt = 'The material is beyond reach; prerequisites will be re-taught.'; }
  const card = el('div', { class: 'card' });
  card.appendChild(el('h2', { text: 'Session Summary — ' + verdict }));
  card.appendChild(el('p', { class: 'lede', text: stmt }));
  area.appendChild(card);
}

/* -------------------------------------------------------------- profile */

$('load-profile').addEventListener('click', async () => {
  if (!LEARNER) { status('sign in first', 'err'); return; }
  const btn = $('load-profile');
  btn.disabled = true;
  btn.textContent = 'Loading…';
  try {
    const data = await api('/api/profile?learner_id=' + encodeURIComponent(LEARNER));
    renderProfile(data);
    status('profile loaded', 'ok');
  } catch (e) { status(e.message, 'err'); }
  finally { btn.disabled = false; btn.textContent = 'Load Profile'; }
});

function renderProfile(data) {
  const area = $('profile-area');
  area.replaceChildren();
  const p = data.profile;
  const head = el('div', { class: 'card' });
  head.appendChild(el('h2', { text: 'Group Role' }));
  head.appendChild(el('div', { class: 'role', text: p.social_role }));
  area.appendChild(head);

  const obsCard = el('div', { class: 'card' });
  obsCard.appendChild(el('h2', { text: 'Observations' }));
  (p.observations || []).forEach(o => {
    const box = el('div', { class: 'obs' });
    const h = el('div', { class: 'head' });
    h.appendChild(el('span', { class: 'label', text: o.label }));
    h.appendChild(el('span', { class: 'conf-badge ' + o.confidence, text: o.confidence }));
    box.appendChild(h);
    box.appendChild(el('div', { class: 'stmt', text: o.statement }));
    obsCard.appendChild(box);
  });
  area.appendChild(obsCard);
}

/* ---------------------------------------------------------------- tutor */

$('tutor-begin').addEventListener('click', async () => {
  const topic = $('tutor-topic').value.trim();
  if (!topic) { status('enter a topic', 'err'); return; }
  const mode = $('tutor-mode').value;
  const btn = $('tutor-begin');
  btn.disabled = true;
  btn.textContent = 'Starting…';
  try {
    await api('/api/tutor/begin', {
      method: 'POST',
      body: JSON.stringify({ learner_id: LEARNER, topic, mode })
    });
    TUTOR_STATE = { topic, mode };
    $('tutor-chat').replaceChildren();
    addTutorMessage(`Let's work on ${topic}. What do you already know about this?`);
    status('tutor ready', 'ok');
  } catch (e) { status(e.message, 'err'); }
  finally { btn.disabled = false; btn.textContent = 'Begin Tutoring'; }
});

function addTutorMessage(text) {
  const chat = $('tutor-chat');
  const msg = el('div', { class: 'chat-msg tutor' });
  msg.appendChild(el('div', { class: 'chat-meta', text: 'Tutor' }));
  msg.appendChild(el('div', { text }));
  chat.appendChild(msg);
  chat.scrollTop = chat.scrollHeight;
}

function addLearnerMessage(text) {
  const chat = $('tutor-chat');
  const msg = el('div', { class: 'chat-msg learner' });
  msg.appendChild(el('div', { class: 'chat-meta', text: 'You' }));
  msg.appendChild(el('div', { text }));
  chat.appendChild(msg);
  chat.scrollTop = chat.scrollHeight;
}

// Tutor chat input
const chatInput = el('input', { attrs: { type: 'text', placeholder: 'Type your response…', id: 'chat-input' } });
const chatSend = el('button', { class: 'primary', text: 'Send', id: 'chat-send' });
const chatRow = el('div', { class: 'chat-input-area' }, [chatInput, chatSend]);
$('tutor-chat').parentNode.insertBefore(chatRow, $('tutor-chat').nextSibling);

chatSend.addEventListener('click', async () => {
  const text = chatInput.value.trim();
  if (!text || !TUTOR_STATE) return;
  chatInput.value = '';
  addLearnerMessage(text);
  try {
    const data = await api('/api/tutor/respond', {
      method: 'POST',
      body: JSON.stringify({ learner_id: LEARNER, message: text })
    });
    addTutorMessage(data.text);
  } catch (e) { status(e.message, 'err'); }
});

chatInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') chatSend.click();
});

/* ------------------------------------------------------------------ MCP */

function renderMcpPlan() {
  const area = $('mcp-plan');
  if (!area) return;
  area.replaceChildren();
  api('/api/mcp/plan').then(plan => {
    area.appendChild(el('h3', { text: 'Authorise these (OAuth only)' }));
    plan.oauth_required.forEach(o => {
      const row = el('div', { class: 'row' });
      row.appendChild(el('span', { class: 'pill oauth', text: o.name }));
      row.appendChild(el('span', { text: o.url, attrs: { style: 'flex:1;font-size:var(--text-sm)' } }));
      area.appendChild(row);
    });
  }).catch(() => {});
}

$('write-mcp').addEventListener('click', async () => {
  const btn = $('write-mcp');
  btn.disabled = true;
  btn.textContent = 'Writing…';
  try {
    const data = await api('/api/mcp/config', { method: 'POST', body: JSON.stringify({}) });
    $('mcp-out').textContent = 'Written to ' + data.written;
    status('mcp.json written', 'ok');
  } catch (e) { status(e.message, 'err'); }
  finally { btn.disabled = false; btn.textContent = 'Write mcp.json'; }
});

/* ------------------------------------------------------------------ go */

// Check for existing session on load
(async () => {
  const storedSession = sessionStorage.getItem(SESSION_KEY);
  if (storedSession) {
    SESSION_TOKEN = storedSession;
    try {
      const sess = await api('/api/account/session', {
        method: 'POST',
        body: JSON.stringify({ session_token: SESSION_TOKEN })
      });
      ACCOUNT = sess;
      LEARNER = sess.learner_id;
      showMainApp();
      return;
    } catch (e) {
      SESSION_TOKEN = '';
      try { sessionStorage.removeItem(SESSION_KEY); } catch (e2) {}
    }
  }
  // Show auth view (already active by default)
})();
