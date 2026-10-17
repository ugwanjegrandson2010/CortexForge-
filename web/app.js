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
  initTheme();
  initSettings();
  boot();
}

/* --------------------------------------------------------------- nav */

document.querySelectorAll('.nav-item').forEach(item => {
  item.addEventListener('click', () => {
    document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    item.classList.add('active');
    const viewName = 'view-' + item.dataset.view;
    const viewEl = $(viewName);
    if (viewEl) viewEl.classList.add('active');
    // Close sidebar on mobile after selection
    if (window.innerWidth <= 768) {
      document.querySelector('.sidebar')?.classList.remove('open');
    }
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
        // Check if onboarding is complete
        const profile = await api('/api/profile?learner_id=' + encodeURIComponent(LEARNER));
        if (!profile.profile || !profile.profile.observations || profile.profile.observations.length === 0) {
          // New user - show onboarding
          $('view-main').classList.remove('active');
          $('view-onboarding').classList.add('active');
          startOnboarding();
          return;
        }
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

    // Streak counter (placeholder - would be computed from session history)
    $('streak-count').textContent = '0';

    // Mastery map
    renderMasteryMap(p);

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

    // Progress rings
    const circumference = 2 * Math.PI * 34; // ~213.6
    const dailyPct = Math.min(s.n / 20, 1); // goal: 20 attempts/day
    const weeklyPct = Math.min(s.n / 100, 1); // goal: 100 attempts/week
    const masteredPct = (p.observations || []).length > 0
      ? (p.observations || []).filter(o => o.confidence === 'high').length / (p.observations || []).length
      : 0;
    setRing('ring-daily', dailyPct, circumference);
    setRing('ring-weekly', weeklyPct, circumference);
    setRing('ring-mastered', masteredPct, circumference);

    // Recent sessions
    const sessionsEl = $('dash-sessions');
    sessionsEl.replaceChildren();
    const recentText = el('div', { class: 'meta', text: 'No sessions yet. Start your first session to see progress here.' });
    sessionsEl.appendChild(recentText);
  } catch (e) { /* silent */ }
}

function setRing(id, pct, circumference) {
  const ring = $(id);
  if (!ring) return;
  const offset = circumference * (1 - pct);
  ring.style.strokeDashoffset = String(offset);
}

function renderMasteryMap(profile) {
  const map = $('dash-mastery-map');
  map.replaceChildren();
  // Derive skills from observations
  const skills = (profile.observations || []).slice(0, 12);
  if (skills.length === 0) {
    map.appendChild(el('div', { class: 'meta', text: 'No skills tracked yet. Complete onboarding and study sessions to build your mastery map.' }));
    return;
  }
  skills.forEach((obs, i) => {
    const level = obs.confidence === 'high' ? 'mastered' : (obs.confidence === 'moderate' ? 'learning' : 'new');
    const pct = level === 'mastered' ? 80 + Math.floor(Math.random() * 20) : (level === 'learning' ? 40 + Math.floor(Math.random() * 30) : Math.floor(Math.random() * 30));
    const node = el('div', { class: 'mastery-node ' + level });
    node.appendChild(el('div', { class: 'node-name', text: obs.label }));
    const bar = el('div', { class: 'node-bar' });
    const fill = el('div', { class: 'node-fill' });
    fill.style.width = pct + '%';
    bar.appendChild(fill);
    node.appendChild(bar);
    map.appendChild(node);
  });
}

$('dash-start-session').addEventListener('click', () => {
  document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.querySelector('.nav-item[data-view="study"]').classList.add('active');
  $('view-study').classList.add('active');
});

$('dash-add-source').addEventListener('click', () => {
  document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.querySelector('.nav-item[data-view="sources"]').classList.add('active');
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

const STAGES = [
  { id: 'launch', label: 'Launch' },
  { id: 'retrieval', label: 'Retrieval' },
  { id: 'hook', label: 'Hook' },
  { id: 'construction', label: 'Construct' },
  { id: 'testing', label: 'Testing' },
  { id: 'close', label: 'Close' },
];

function renderStageIndicators(currentStage) {
  const wrap = $('session-stages');
  wrap.replaceChildren();
  const dots = el('div', { class: 'stage-indicators' });
  const labels = el('div', { class: 'stage-labels' });
  STAGES.forEach((s, i) => {
    const dot = el('div', { class: 'stage-dot' });
    if (i < currentStage) dot.classList.add('completed');
    else if (i === currentStage) dot.classList.add('active');
    dots.appendChild(dot);
    const label = el('div', { class: 'stage-label', text: s.label });
    if (i < currentStage) label.classList.add('completed');
    else if (i === currentStage) label.classList.add('active');
    labels.appendChild(label);
  });
  wrap.appendChild(dots);
  wrap.appendChild(labels);
}

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
    renderStageIndicators(0);
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

  // 4-button FSRS grading (Anki-style)
  const gradeRow = el('div', { class: 'grade-row' });
  const grades = [
    { label: 'Again', time: '<1d', value: 1, cls: 'again' },
    { label: 'Hard', time: '2d', value: 2, cls: 'hard' },
    { label: 'Good', time: '4d', value: 3, cls: 'good' },
    { label: 'Easy', time: '7d', value: 4, cls: 'easy' },
  ];
  let answered = false;
  grades.forEach(g => {
    const btn = el('button', { class: 'grade-btn ' + g.cls });
    btn.appendChild(el('span', { class: 'grade-label', text: g.label }));
    btn.appendChild(el('span', { class: 'grade-time', text: g.time }));
    btn.addEventListener('click', async () => {
      if (answered) return;
      answered = true;
      const started = performance.now();
      const answer = ta.value;
      const latency = Math.round(performance.now() - started);
      const correct = g.value >= 3;
      try {
        await api('/api/attempt', {
          method: 'POST',
          body: JSON.stringify({
            learner_id: LEARNER, qid: q.qid, skill_id: q.skill_id,
            correct, grade: g.value, latency_ms: latency,
            confidence: Number(range.value) / 100, response: answer
          })
        });
        SESSION_RESULTS.push({ verdict: correct ? 'correct' : 'incorrect', correct, latency_ms: latency });
        showBottomBanner(correct ? 'correct' : 'incorrect', correct ? 'Correct! Well done.' : 'Incorrect. The correct answer is: ' + q.answer);
        setTimeout(() => { SESSION_INDEX++; renderQuestion(); }, 1200);
      } catch (e) { status(e.message, 'err'); answered = false; }
    });
    gradeRow.appendChild(btn);
  });
  card.appendChild(gradeRow);

  return card;
}

function showBottomBanner(type, text) {
  // Remove existing banner
  const existing = document.querySelector('.bottom-banner');
  if (existing) existing.remove();
  const banner = el('div', { class: 'bottom-banner ' + type });
  banner.appendChild(el('div', { class: 'banner-text', text }));
  const btn = el('button', { class: 'banner-btn', text: 'Next' });
  btn.addEventListener('click', () => {
    banner.classList.remove('show');
    setTimeout(() => banner.remove(), 300);
  });
  banner.appendChild(btn);
  document.body.appendChild(banner);
  requestAnimationFrame(() => banner.classList.add('show'));
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

/* ------------------------------------------------------- command palette */

const COMMANDS = [
  { id: 'start-session', label: 'Start Study Session', icon: 'S', shortcut: 'Ctrl+S', action: () => switchView('study') },
  { id: 'add-source', label: 'Add Source Material', icon: 'M', shortcut: 'Ctrl+M', action: () => switchView('sources') },
  { id: 'load-profile', label: 'View Profile', icon: 'P', shortcut: 'Ctrl+P', action: () => switchView('profile') },
  { id: 'start-tutor', label: 'Start Tutoring', icon: 'T', shortcut: 'Ctrl+T', action: () => switchView('tutor') },
  { id: 'view-integrations', label: 'View Integrations', icon: 'I', shortcut: 'Ctrl+I', action: () => switchView('integrations') },
  { id: 'load-dashboard', label: 'Go to Dashboard', icon: 'D', shortcut: 'Ctrl+D', action: () => switchView('dashboard') },
];

let paletteOpen = false;
let paletteResults = [];
let paletteIndex = 0;

function switchView(view) {
  document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.querySelector(`.nav-item[data-view="${view}"]`)?.classList.add('active');
  $('view-' + view)?.classList.add('active');
}

function openPalette() {
  if (paletteOpen) return;
  paletteOpen = true;
  paletteResults = COMMANDS;
  paletteIndex = 0;
  const overlay = el('div', { class: 'command-palette-overlay' });
  overlay.id = 'cmd-overlay';
  const palette = el('div', { class: 'command-palette' });
  const input = el('input', { class: 'command-palette-input', attrs: { type: 'text', placeholder: 'Type a command…', autocomplete: 'off' } });
  const results = el('div', { class: 'command-palette-results' });
  results.id = 'cmd-results';
  palette.appendChild(input);
  palette.appendChild(results);
  overlay.appendChild(palette);
  document.body.appendChild(overlay);
  input.focus();
  renderPaletteResults();
  overlay.addEventListener('click', (e) => { if (e.target === overlay) closePalette(); });
  input.addEventListener('input', (e) => {
    const q = e.target.value.toLowerCase();
    paletteResults = COMMANDS.filter(c => c.label.toLowerCase().includes(q));
    paletteIndex = 0;
    renderPaletteResults();
  });
  input.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); paletteIndex = Math.min(paletteIndex + 1, paletteResults.length - 1); renderPaletteResults(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); paletteIndex = Math.max(paletteIndex - 1, 0); renderPaletteResults(); }
    else if (e.key === 'Enter') { e.preventDefault(); if (paletteResults[paletteIndex]) { closePalette(); paletteResults[paletteIndex].action(); } }
    else if (e.key === 'Escape') { closePalette(); }
  });
  requestAnimationFrame(() => overlay.classList.add('show'));
}

function renderPaletteResults() {
  const results = $('cmd-results');
  if (!results) return;
  results.replaceChildren();
  if (paletteResults.length === 0) {
    results.appendChild(el('div', { class: 'command-palette-empty', text: 'No commands found' }));
    return;
  }
  paletteResults.forEach((cmd, i) => {
    const item = el('div', { class: 'command-palette-item' + (i === paletteIndex ? ' selected' : '') });
    item.appendChild(el('div', { class: 'cmd-icon', text: cmd.icon }));
    item.appendChild(el('div', { class: 'cmd-label', text: cmd.label }));
    item.appendChild(el('div', { class: 'cmd-shortcut', text: cmd.shortcut }));
    item.addEventListener('click', () => { closePalette(); cmd.action(); });
    results.appendChild(item);
  });
}

function closePalette() {
  paletteOpen = false;
  const overlay = $('cmd-overlay');
  if (overlay) {
    overlay.classList.remove('show');
    setTimeout(() => overlay.remove(), 200);
  }
}

document.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault();
    if (paletteOpen) closePalette(); else openPalette();
  }
});

/* --------------------------------------------------------- onboarding */

async function startOnboarding() {
  if (!LEARNER) { status('sign in first', 'err'); return; }
  try {
    await api('/api/onboarding/start', {
      method: 'POST',
      body: JSON.stringify({ learner_id: LEARNER })
    });
    status('onboarding started', 'ok');
    renderNextProbe();
  } catch (e) { status(e.message, 'err'); }
}

async function renderNextProbe() {
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

  // Progress
  const progress = data.progress;
  const pct = Math.round((progress.completed / progress.total) * 100);
  $('onboarding-progress-fill').style.width = pct + '%';
  $('onboarding-progress-text').textContent = `Step ${progress.completed + 1} of ${progress.total}`;

  const inputWrap = el('div', { class: 'field' });
  if (p.kind === 'interview' && p.options && p.options.length) {
    const sel = el('select');
    p.options.forEach(o => sel.appendChild(el('option', { text: o, attrs: { value: o } })));
    inputWrap.appendChild(sel);
  } else if (p.kind === 'interview' || p.kind === 'source') {
    inputWrap.appendChild(el('textarea', { attrs: { rows: '4', placeholder: 'Type your answer…' } }));
  } else if (p.kind === 'calibration') {
    inputWrap.appendChild(el('p', { class: 'lede', text: 'Answer each on a 0–4 scale.' }));
    const dims = ['holding a thought', 'finding a word', 'following a conversation',
                  'remembering why you walked into a room', 'reading the same paragraph twice'];
    dims.forEach(d => {
      const row = el('div', { class: 'row' });
      row.appendChild(el('span', { text: d, attrs: { style: 'flex:1' } }));
      row.appendChild(el('input', { attrs: { type: 'number', min: '0', max: '4', value: '0', style: 'width:70px' } }));
      inputWrap.appendChild(row);
    });
  } else if (p.kind === 'task') {
    inputWrap.appendChild(el('p', { class: 'lede', text: 'This task runs in your browser. Click "Start task" to begin.' }));
    const startBtn = el('button', { class: 'primary', text: 'Start task' });
    inputWrap.appendChild(startBtn);
    startBtn.addEventListener('click', async () => {
      startBtn.disabled = true;
      try {
        if (typeof TaskEngine !== 'undefined' && TaskEngine.has(p.task_id)) {
          const trials = await TaskEngine.run(p.task_id, inputWrap, { trials: p.trials || 40 });
          inputWrap.appendChild(el('p', { class: 'lede', text: `Task complete. ${trials.length} trials recorded.` }));
        }
      } catch (e) {
        inputWrap.appendChild(el('p', { class: 'lede', text: 'Task error: ' + e.message }));
        startBtn.disabled = false;
      }
    });
  }

  card.appendChild(inputWrap);
  const row = el('div', { class: 'row' });
  const nextBtn = el('button', { class: 'primary', text: 'Continue' });
  const skipBtn = el('button', { text: 'Skip this' });
  row.appendChild(nextBtn);
  row.appendChild(skipBtn);
  card.appendChild(row);
  area.appendChild(card);

  nextBtn.addEventListener('click', async () => {
    nextBtn.disabled = true;
    try {
      await api('/api/onboarding/record', {
        method: 'POST',
        body: JSON.stringify({ learner_id: LEARNER, probe_id: p.probe_id, answer: null })
      });
      renderNextProbe();
    } catch (e) { status(e.message, 'err'); nextBtn.disabled = false; }
  });

  skipBtn.addEventListener('click', async () => {
    skipBtn.disabled = true;
    try {
      await api('/api/onboarding/record', {
        method: 'POST',
        body: JSON.stringify({ learner_id: LEARNER, probe_id: p.probe_id, answer: null })
      });
      renderNextProbe();
    } catch (e) { status(e.message, 'err'); skipBtn.disabled = false; }
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
    card.appendChild(el('pre', { class: 'code', text: data.summary }));
    area.appendChild(card);
    status('onboarding complete', 'ok');
    // Switch to main app after a delay
    setTimeout(() => {
      $('view-onboarding').classList.remove('active');
      $('view-main').classList.add('active');
    }, 3000);
  } catch (e) { status(e.message, 'err'); }
}

/* ------------------------------------------------------------- theme */

function initTheme() {
  const stored = localStorage.getItem('cortexforge_theme');
  if (stored) {
    document.documentElement.setAttribute('data-theme', stored);
  }
  $('theme-toggle').addEventListener('click', () => {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', next);
    try { localStorage.setItem('cortexforge_theme', next); } catch (e) {}
  });
}

/* ----------------------------------------------------------- settings */

function initSettings() {
  // Load saved preferences
  const prefs = JSON.parse(localStorage.getItem('cortexforge_prefs') || '{}');
  if (prefs.session_min) $('pref-session-min').value = prefs.session_min;
  if (prefs.days_week) $('pref-days-week').value = prefs.days_week;
  if (prefs.success_rate) $('pref-success-rate').value = prefs.success_rate;
  if (prefs.difficulty) $('pref-difficulty').value = prefs.difficulty;

  // Save on change
  ['pref-session-min', 'pref-days-week', 'pref-success-rate', 'pref-difficulty'].forEach(id => {
    $(id).addEventListener('change', () => {
      const prefs = {
        session_min: Number($('pref-session-min').value),
        days_week: Number($('pref-days-week').value),
        success_rate: Number($('pref-success-rate').value),
        difficulty: $('pref-difficulty').value,
      };
      try { localStorage.setItem('cortexforge_prefs', JSON.stringify(prefs)); } catch (e) {}
      status('preferences saved', 'ok');
    });
  });

  // Export data
  $('export-data').addEventListener('click', async () => {
    if (!LEARNER) { status('sign in first', 'err'); return; }
    try {
      const data = await api('/api/export?learner_id=' + encodeURIComponent(LEARNER));
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = el('a', { attrs: { href: url, download: 'cortexforge-export.json' } });
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      status('data exported', 'ok');
    } catch (e) { status(e.message, 'err'); }
  });

  // Erase data
  $('erase-data').addEventListener('click', async () => {
    if (!LEARNER) { status('sign in first', 'err'); return; }
    const confirmText = 'ERASE';
    const input = prompt(`This will permanently delete all your learning data. Type ${confirmText} to confirm:`);
    if (input !== confirmText) { status('erase cancelled'); return; }
    try {
      await api('/api/erase', { method: 'POST', body: JSON.stringify({ learner_id: LEARNER, confirm: confirmText }) });
      status('data erased', 'ok');
    } catch (e) { status(e.message, 'err'); }
  });
}

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
