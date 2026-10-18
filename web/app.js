/* CortexForge client — redesigned UI (single-file application controller).
 *
 * SECURITY POSTURE
 *   - Every piece of server- or user-supplied data is written with
 *     textContent / createElement, never innerHTML. A hostile source document
 *     therefore cannot inject markup or script into the UI.
 *   - No eval, no new Function, no document.write.
 *   - The per-user API token lives in sessionStorage only and is sent as the
 *     X-CortexForge-Token request header on mutating calls.
 *   - The server sends a strict CSP (script-src 'self'; style-src 'self').
 *     Runtime CSS is therefore installed through a constructable stylesheet,
 *     and GSAP/Lenis are vendored under /static/lib and loaded same-origin
 *     (never a CDN). Three.js is loaded from /static/lib and treated as
 *     entirely optional.
 *
 * GRACEFUL DEGRADATION
 *   - The Three.js scientific scene is isolated in a try/catch and falls back
 *     to a CSS gradient (body.no-webgl) when WebGL is unavailable.
 *   - Micro-interactions are isolated in a try/catch.
 *   - Every storage access is wrapped: private-mode browsers simply lose
 *     persistence rather than breaking.
 *   - Every network handler reports failure through the status line instead of
 *     throwing into the console.
 *
 * PUBLIC SURFACE
 *   All controller functions are exported on window.CortexForge for testability
 *   and for wiring from the shell markup.
 */
'use strict';

/* ==========================================================================
 * Constants
 * ========================================================================== */

const STORAGE = {
  TOKEN: 'cortexforge_token',
  SESSION: 'cortexforge_session',
  THEME: 'cortexforge_theme',
  PREFS: 'cortexforge_prefs',
};

/* Auth endpoints are the only writes that may run without an API token. */
const AUTH_ENDPOINTS = new Set([
  '/api/account/create',
  '/api/account/login',
  '/api/account/reset-request',
  '/api/account/reset',
]);

/* r="34" on the dashboard progress rings in index.html. */
const RING_CIRCUMFERENCE = 2 * Math.PI * 34;

const REDUCED_MOTION = (function () {
  try {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  } catch (e) {
    return false;
  }
})();

/* The six behavioural stages of a session (dual-coded: dot + label). */
const STAGES = [
  { id: 'launch', label: 'Launch' },
  { id: 'retrieval', label: 'Retrieval' },
  { id: 'hook', label: 'Hook' },
  { id: 'construction', label: 'Construct' },
  { id: 'testing', label: 'Testing' },
  { id: 'close', label: 'Close' },
];

/* ==========================================================================
 * Application state
 * ========================================================================== */

let TOKEN = '';               // per-user API token (sessionStorage)
let SESSION_TOKEN = '';       // account session token (sessionStorage)
let ACCOUNT = null;           // {account_id, email, display_name, ...}
let LEARNER = '';             // learner_id used by every data endpoint
let MANIFEST = null;          // /api/manifest payload (tasks, styles, probes)
let SESSION = [];             // questions for the active study session
let SESSION_INDEX = 0;        // cursor into SESSION
let SESSION_RESULTS = [];     // graded results for the active session
let SESSION_QUESTION_SHOWN_AT = 0; // performance.now() when the card rendered
let SELECTED_STYLES = new Set();   // styles chosen for question generation
let TUTOR_STATE = null;       // {topic, mode} once a tutor session begins

/* One-shot wiring guards so re-entering the app never double-binds. */
const BOUND = { nav: false, theme: false, settings: false, palette: false, app: false };

/* ==========================================================================
 * Storage helpers (never throw)
 * ========================================================================== */

function storeGet(key) { try { return sessionStorage.getItem(key); } catch (e) { return null; } }
function storeSet(key, value) { try { sessionStorage.setItem(key, value); } catch (e) { /* ignore */ } }
function storeDel(key) { try { sessionStorage.removeItem(key); } catch (e) { /* ignore */ } }
function localGet(key) { try { return localStorage.getItem(key); } catch (e) { return null; } }
function localSet(key, value) { try { localStorage.setItem(key, value); } catch (e) { /* ignore */ } }

/* ==========================================================================
 * DOM helpers
 * ========================================================================== */

function $(id) { return document.getElementById(id); }

/**
 * Build an element without ever touching innerHTML.
 * @param {string} tag
 * @param {{class?:string, text?:*, attrs?:Object, style?:Object, on?:Object}} [opts]
 * @param {Node[]} [children]
 */
function el(tag, opts, children) {
  const o = opts || {};
  const node = document.createElement(tag);
  if (o.class) node.className = o.class;
  if (o.text !== undefined && o.text !== null) node.textContent = String(o.text);
  if (o.attrs) {
    for (const key of Object.keys(o.attrs)) {
      const value = o.attrs[key];
      if (value !== null && value !== undefined) node.setAttribute(key, String(value));
    }
  }
  if (o.style) {
    for (const key of Object.keys(o.style)) node.style[key] = o.style[key];
  }
  if (o.on) {
    for (const key of Object.keys(o.on)) node.addEventListener(key, o.on[key]);
  }
  if (children && children.length) {
    for (const child of children) {
      if (child === null || child === undefined) continue;
      node.appendChild(child);
    }
  }
  return node;
}

function clear(node) { if (node) node.replaceChildren(); }

function status(message, kind) {
  const s = $('status');
  if (!s) return;
  s.textContent = message || '';
  s.className = 'status' + (kind ? ' ' + kind : '');
}

/** Disable a button and swap its label while an async call is in flight. */
function setBusy(btn, busy, idleText) {
  if (!btn) return;
  if (busy) {
    if (btn.dataset.idleLabel === undefined) btn.dataset.idleLabel = btn.textContent;
    btn.disabled = true;
    if (idleText) btn.textContent = idleText;
  } else {
    btn.disabled = false;
    btn.textContent = btn.dataset.idleLabel !== undefined ? btn.dataset.idleLabel : btn.textContent;
  }
}

/** Deterministic 0-100 value derived from a string — used for stable visuals. */
function stablePercent(seed) {
  const str = String(seed || '');
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return Math.abs(h) % 100;
}

function clamp01(x) {
  const n = Number(x);
  if (!isFinite(n)) return 0;
  return Math.max(0, Math.min(1, n));
}

/* ==========================================================================
 * API client
 * ========================================================================== */

function isWriteMethod(method) {
  const m = String(method || 'GET').toUpperCase();
  return m !== 'GET' && m !== 'HEAD';
}

function pathOnly(path) {
  return String(path || '').split('?')[0];
}

function qs(params) {
  const parts = [];
  for (const key of Object.keys(params || {})) {
    const value = params[key];
    if (value === undefined || value === null) continue;
    parts.push(encodeURIComponent(key) + '=' + encodeURIComponent(String(value)));
  }
  return parts.length ? '?' + parts.join('&') : '';
}

/**
 * Fetch a JSON endpoint.
 *  - GET requests are token-free.
 *  - Writes carry Content-Type and X-CortexForge-Token, except auth endpoints.
 *  - Non-2xx responses throw an Error carrying the server's message.
 */
async function api(path, opts) {
  const options = opts || {};
  const method = String(options.method || 'GET').toUpperCase();
  const write = isWriteMethod(method);
  const needsToken = write && !AUTH_ENDPOINTS.has(pathOnly(path));

  const headers = Object.assign({ 'Accept': 'application/json' }, options.headers || {});
  if (write) headers['Content-Type'] = 'application/json';
  if (needsToken) headers['X-CortexForge-Token'] = TOKEN;

  const response = await fetch(path, Object.assign({}, options, { method: method, headers: headers }));
  const text = await response.text();

  let data = null;
  if (text) {
    try { data = JSON.parse(text); }
    catch (e) { data = { raw: text }; }
  }

  if (!response.ok) {
    const message = (data && (data.error || data.message)) || ('HTTP ' + response.status);
    const error = new Error(message);
    error.status = response.status;
    error.data = data;
    throw error;
  }
  return data;
}

/* ==========================================================================
 * Presentation infrastructure
 *
 * The server ships a strict CSP: style-src 'self' and script-src 'self'.
 * Under it, injected <style> elements, style="" attributes and CDN scripts are
 * all blocked. So runtime CSS is installed through a constructable stylesheet
 * (adoptedStyleSheets) — which CSP permits — and GSAP/Lenis are loaded
 * same-origin from /static/lib rather than from a CDN. Both are optional: the
 * application is fully functional with neither.
 * ========================================================================== */

let stylesInstalled = false;
let BG = null;                 // background-scene controller
const LIBS = { gsap: null, lenis: null, lenisInstance: null };

const RUNTIME_CSS = [
  /* layout utilities the shared sheet does not define */
  '.row{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:8px 0;}',
  '.conf{display:flex;align-items:center;gap:12px;flex:1;}',
  '.conf input[type="range"]{flex:1;min-width:120px;accent-color:#4f8cff;}',
  '.cf-sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;border:0;}',
  '.cf-enter{opacity:0;transform:translateY(10px);}',
  '.cf-enter.cf-in{opacity:1;transform:none;transition:opacity .5s cubic-bezier(0.16,1,0.3,1),transform .5s cubic-bezier(0.16,1,0.3,1);}',
  'button.cf-pressed{transform:scale(.97);}',
  /* branded loading screen */
  '#cf-loader{position:fixed;inset:0;z-index:1000;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:20px;background:#08090a;color:#e8eefc;font-family:Inter,system-ui,-apple-system,sans-serif;}',
  '#cf-loader .cf-loader-mark{font-weight:700;font-size:32px;letter-spacing:.03em;}',
  '#cf-loader .cf-loader-sub{font-size:11px;letter-spacing:.22em;text-transform:uppercase;color:#7f8ba3;}',
  '#cf-loader .cf-loader-bar{width:190px;height:3px;border-radius:2px;background:#1b2230;overflow:hidden;}',
  '#cf-loader .cf-loader-fill{width:0%;height:100%;background:linear-gradient(90deg,#4f8cff,#a78bfa);}',
  /* WebGL fallback background */
  'body.no-webgl #bg-canvas{background:linear-gradient(135deg,#08090a 0%,#101a33 45%,#0b1020 100%);background-size:200% 200%;animation:cf-bg-drift 26s ease-in-out infinite;}',
  '@keyframes cf-bg-drift{0%{background-position:0% 50%;}50%{background-position:100% 50%;}100%{background-position:0% 50%;}}',
  '@media (prefers-reduced-motion: reduce){body.no-webgl #bg-canvas{animation:none;}}',
].join('\n');

function installStyles() {
  if (stylesInstalled) return;
  stylesInstalled = true;
  try {
    if (typeof CSSStyleSheet === 'function' && 'adoptedStyleSheets' in document) {
      const sheet = new CSSStyleSheet();
      sheet.replaceSync(RUNTIME_CSS);
      document.adoptedStyleSheets = document.adoptedStyleSheets.concat([sheet]);
      return;
    }
  } catch (e) { /* fall through to the legacy path */ }
  try {
    const style = document.createElement('style');
    style.textContent = RUNTIME_CSS;
    document.head.appendChild(style);
  } catch (e) { /* styling is progressive enhancement */ }
}

/* Backwards-compatible alias. */
function ensureRuntimeStyles() { installStyles(); }

/* --------------------------------------------------------------------------
 * Branded loading screen
 * ------------------------------------------------------------------------ */

let loaderFill = null;

function showLoader() {
  if ($('cf-loader')) return;
  loaderFill = el('div', { class: 'cf-loader-fill' });
  const loader = el('div', {
    attrs: { id: 'cf-loader', role: 'status', 'aria-live': 'polite', 'aria-label': 'Loading CortexForge' },
  }, [
    el('div', { class: 'cf-loader-mark', text: 'CortexForge' }),
    el('div', { class: 'cf-loader-sub', text: 'initialising' }),
    el('div', { class: 'cf-loader-bar' }, [loaderFill]),
  ]);
  document.body.appendChild(loader);
}

function setLoaderProgress(pct) {
  if (loaderFill) loaderFill.style.width = Math.max(0, Math.min(100, pct)) + '%';
}

function hideLoader() {
  const loader = $('cf-loader');
  if (!loader) return;
  let removed = false;
  const remove = function () {
    if (removed) return;
    removed = true;
    try { loader.remove(); } catch (e) { /* ignore */ }
  };
  /* Hard guarantee: the loader must never outlive a stalled animation (for
   * example in a background tab, where requestAnimationFrame is paused). */
  setTimeout(remove, 900);
  if (LIBS.gsap) {
    LIBS.gsap.to(loader, { opacity: 0, duration: 0.5, ease: 'expo.out', onComplete: remove });
  } else if (loader.animate) {
    try {
      const anim = loader.animate([{ opacity: 1 }, { opacity: 0 }],
        { duration: 500, easing: 'cubic-bezier(0.16,1,0.3,1)', fill: 'forwards' });
      anim.onfinish = remove;
    } catch (e) { remove(); }
  } else {
    remove();
  }
}

/* --------------------------------------------------------------------------
 * Vendored libraries (GSAP, Lenis) — same-origin, CSP-safe, optional
 * ------------------------------------------------------------------------ */

function loadScript(src) {
  return new Promise(function (resolve) {
    try {
      const s = document.createElement('script');
      s.src = src;
      s.async = true;
      s.onload = function () { resolve(true); };
      s.onerror = function () { resolve(false); };
      document.head.appendChild(s);
    } catch (e) { resolve(false); }
  });
}

async function loadVendorLibs() {
  try {
    const loaded = await Promise.all([
      loadScript('/static/lib/gsap.min.js'),
      loadScript('/static/lib/lenis.min.js'),
    ]);
    if (loaded[0] && window.gsap) LIBS.gsap = window.gsap;
    if (loaded[1] && window.Lenis) LIBS.lenis = window.Lenis;
  } catch (e) { /* libraries are optional */ }

  if (LIBS.lenis) {
    try {
      LIBS.lenisInstance = new LIBS.lenis({ duration: 1.1, smoothWheel: true });
      const raf = function (time) {
        if (LIBS.lenisInstance) LIBS.lenisInstance.raf(time);
        requestAnimationFrame(raf);
      };
      requestAnimationFrame(raf);
    } catch (e) { LIBS.lenisInstance = null; }
  }
}

/* --------------------------------------------------------------------------
 * Animation adapter — GSAP when present, Web Animations API otherwise
 * Both honour cubic-bezier(0.16, 1, 0.3, 1).
 * ------------------------------------------------------------------------ */

const EASE_BEZIER = 'cubic-bezier(0.16, 1, 0.3, 1)';

function animTo(target, vars) {
  if (LIBS.gsap) return LIBS.gsap.to(target, vars);
  return fallbackAnimate(target, vars);
}

function fallbackAnimate(target, vars) {
  const nodes = typeof target === 'string'
    ? Array.from(document.querySelectorAll(target))
    : (Array.isArray(target) ? target : [target]);
  const duration = (vars.duration != null ? vars.duration : 0.5) * 1000;
  const delay = (vars.delay != null ? vars.delay : 0) * 1000;
  const stagger = (vars.stagger != null ? vars.stagger : 0) * 1000;
  const handle = { kill: function () {} };
  nodes.forEach(function (node, i) {
    if (!node || !node.animate) return;
    const from = {};
    const to = {};
    if (vars.opacity != null) { from.opacity = 0; to.opacity = vars.opacity; }
    if (vars.y != null) { from.transform = 'translateY(12px)'; to.transform = 'translateY(0px)'; }
    if (vars.scale != null) { from.transform = 'scale(' + vars.scale + ')'; to.transform = 'scale(1)'; }
    try {
      const anim = node.animate([from, to], {
        duration: duration, delay: delay + i * stagger, easing: EASE_BEZIER, fill: 'forwards',
      });
      if (vars.onComplete) anim.onfinish = vars.onComplete;
      handle.kill = function () { anim.cancel(); };
    } catch (e) { /* ignore */ }
  });
  return handle;
}

/* --------------------------------------------------------------------------
 * Scene control helpers
 * ------------------------------------------------------------------------ */

function setBackgroundMode(mode) {
  if (BG) { try { BG.setMode(mode); } catch (e) { /* scene is optional */ } }
}

/** Adjust scene intensity per view: 0 = still, 1 = normal, >1 = dramatic. */
function setSceneIntensity(level) {
  if (BG) { try { BG.setIntensity(level); } catch (e) { /* scene is optional */ } }
}

/* ==========================================================================
 * Theme
 * ========================================================================== */

function initTheme() {
  const stored = localGet(STORAGE.THEME);
  const initial = (stored === 'light' || stored === 'dark') ? stored : 'dark';
  document.documentElement.setAttribute('data-theme', initial);
  if (BG) BG.setTheme(initial);
  if (BOUND.theme) return;
  BOUND.theme = true;
  const toggle = $('theme-toggle');
  if (toggle) {
    toggle.addEventListener('click', function () {
      const current = document.documentElement.getAttribute('data-theme');
      const next = current === 'light' ? 'dark' : 'light';
      document.documentElement.setAttribute('data-theme', next);
      localSet(STORAGE.THEME, next);
      toggle.setAttribute('aria-label', 'Switch to ' + (next === 'light' ? 'dark' : 'light') + ' theme');
      if (BG) BG.setTheme(next);
    });
  }
}

/* ==========================================================================
 * Three.js scientific scene — molecules, equations, electron orbitals
 *
 * The signature visual element. Entirely optional and fully isolated: any
 * failure (no WebGL, no Three.js) falls back to a CSS gradient via the
 * body.no-webgl class. Respects prefers-reduced-motion (renders a single
 * static frame), pauses when the tab is hidden, caps geometry for
 * performance, and recovers from WebGL context loss.
 * ========================================================================== */

const BG_MOBILE = (function () {
  try {
    return window.innerWidth < 768 || /Mobi|Android|iPhone|iPad/i.test(navigator.userAgent || '');
  } catch (e) { return false; }
})();

/* CPK colouring — the conventional element colours, as requested. */
const CPK_COLOR = { C: 0x909090, H: 0xffffff, O: 0xff0d0d, N: 0x3050f8, S: 0xffd23f };
const CPK_RADIUS = { C: 0.34, H: 0.20, O: 0.32, N: 0.32, S: 0.40 };

/* --- small vector helpers (build-time only) ----------------------------- */
function vsub(a, b) { return { x: a.x - b.x, y: a.y - b.y, z: a.z - b.z }; }
function vadd(a, b) { return { x: a.x + b.x, y: a.y + b.y, z: a.z + b.z }; }
function vscale(a, s) { return { x: a.x * s, y: a.y * s, z: a.z * s }; }
function vnorm(a) {
  const l = Math.sqrt(a.x * a.x + a.y * a.y + a.z * a.z) || 1;
  return { x: a.x / l, y: a.y / l, z: a.z / l };
}
function vcross(a, b) {
  return { x: a.y * b.z - a.z * b.y, y: a.z * b.x - a.x * b.z, z: a.x * b.y - a.y * b.x };
}

/* --- molecule builders: {atoms:[{el,x,y,z}], bonds:[[i,j]]} -------------- */

function molWater() {
  return {
    atoms: [
      { el: 'O', x: 0, y: 0, z: 0 },
      { el: 'H', x: 0.757, y: 0.586, z: 0 },
      { el: 'H', x: -0.757, y: 0.586, z: 0 },
    ],
    bonds: [[0, 1], [0, 2]],
  };
}

function molBenzene() {
  const atoms = [];
  const bonds = [];
  const R = 1.39;    // C–C bond length
  const RH = 2.47;   // C–H bond length
  for (let i = 0; i < 6; i++) {
    const a = (Math.PI / 3) * i;
    atoms.push({ el: 'C', x: R * Math.cos(a), y: R * Math.sin(a), z: 0 });
    atoms.push({ el: 'H', x: RH * Math.cos(a), y: RH * Math.sin(a), z: 0 });
  }
  for (let i = 0; i < 6; i++) {
    bonds.push([i * 2, ((i + 1) % 6) * 2]); // ring
    bonds.push([i * 2, i * 2 + 1]);         // C–H
  }
  return { atoms: atoms, bonds: bonds };
}

function molGlucose() {
  const atoms = [];
  const bonds = [];
  const R = 1.46;
  const ring = [];
  const labels = ['O', 'C', 'C', 'C', 'C', 'C']; // pyranose ring
  for (let i = 0; i < 6; i++) {
    const a = (Math.PI / 3) * i + Math.PI / 6;
    const z = (i % 2 ? 0.3 : -0.3); // slight chair puckering
    ring.push(atoms.length);
    atoms.push({ el: labels[i], x: R * Math.cos(a), y: R * Math.sin(a), z: z });
  }
  for (let i = 0; i < 6; i++) bonds.push([ring[i], ring[(i + 1) % 6]]);

  for (let i = 1; i < 6; i++) {
    const a = (Math.PI / 3) * i + Math.PI / 6;
    const cz = atoms[ring[i]].z;
    /* ring hydrogen */
    const h = atoms.length;
    atoms.push({ el: 'H', x: R * Math.cos(a), y: R * Math.sin(a), z: cz + (cz > 0 ? 1.0 : -1.0) });
    bonds.push([ring[i], h]);

    if (i < 5) {
      /* hydroxyl */
      const oR = R + 1.1;
      const o = atoms.length;
      atoms.push({ el: 'O', x: oR * Math.cos(a), y: oR * Math.sin(a), z: cz });
      bonds.push([ring[i], o]);
      const ho = atoms.length;
      atoms.push({ el: 'H', x: (oR + 0.95) * Math.cos(a), y: (oR + 0.95) * Math.sin(a), z: cz + 0.35 });
      bonds.push([o, ho]);
    } else {
      /* CH2OH on C5 */
      const cR = R + 1.5;
      const c = atoms.length;
      atoms.push({ el: 'C', x: cR * Math.cos(a), y: cR * Math.sin(a), z: cz });
      bonds.push([ring[i], c]);
      const oR = R + 2.9;
      const o = atoms.length;
      atoms.push({ el: 'O', x: oR * Math.cos(a), y: oR * Math.sin(a), z: cz });
      bonds.push([c, o]);
      const ho = atoms.length;
      atoms.push({ el: 'H', x: (oR + 0.95) * Math.cos(a), y: (oR + 0.95) * Math.sin(a), z: cz + 0.4 });
      bonds.push([o, ho]);
      for (let k = 0; k < 2; k++) {
        const hh = atoms.length;
        const perp = a + (Math.PI / 2) * (k ? 1 : -1);
        atoms.push({
          el: 'H',
          x: cR * Math.cos(a) + 0.9 * Math.cos(perp),
          y: cR * Math.sin(a) + 0.9 * Math.sin(perp),
          z: cz + (k ? 0.5 : -0.5),
        });
        bonds.push([c, hh]);
      }
    }
  }
  return { atoms: atoms, bonds: bonds };
}

/** Attach three hydrogens to a methyl carbon in a tetrahedral arrangement. */
function addMethylH(atoms, bonds, cIdx, parentIdx) {
  const c = atoms[cIdx];
  const p = atoms[parentIdx];
  const axis = vnorm(vsub(c, p));
  let ref = { x: 0, y: 0, z: 1 };
  if (Math.abs(axis.z) > 0.9) ref = { x: 1, y: 0, z: 0 };
  const u = vnorm(vcross(axis, ref));
  const w = vnorm(vcross(axis, u));
  const theta = (109.5 * Math.PI) / 180;
  const len = 1.09;
  for (let k = 0; k < 3; k++) {
    const phi = ((2 * Math.PI) / 3) * k;
    const dir = vnorm({
      x: Math.cos(theta) * axis.x + Math.sin(theta) * (Math.cos(phi) * u.x + Math.sin(phi) * w.x),
      y: Math.cos(theta) * axis.y + Math.sin(theta) * (Math.cos(phi) * u.y + Math.sin(phi) * w.y),
      z: Math.cos(theta) * axis.z + Math.sin(theta) * (Math.cos(phi) * u.z + Math.sin(phi) * w.z),
    });
    const pos = vadd(c, vscale(dir, len));
    atoms.push({ el: 'H', x: pos.x, y: pos.y, z: pos.z });
    bonds.push([cIdx, atoms.length - 1]);
  }
}

function molCaffeine() {
  const atoms = [];
  const bonds = [];
  const A = function (el, x, y, z) {
    atoms.push({ el: el, x: x, y: y, z: z });
    return atoms.length - 1;
  };
  /* fused bicyclic core: 6-ring (pyrimidinedione) + 5-ring (imidazole) */
  const c5 = A('C', 0.5, 0.0, 0.0);
  const c6 = A('C', -0.2, 1.212, 0.0);
  const n1 = A('N', -1.6, 1.212, 0.0);
  const c2 = A('C', -2.3, 0.0, 0.0);
  const n3 = A('N', -1.6, -1.212, 0.0);
  const c4 = A('C', -0.2, -1.212, 0.0);
  const n7 = A('N', 1.75, 0.15, 0.0);
  const c8 = A('C', 2.2, -1.1, 0.0);
  const n9 = A('N', 1.05, -1.95, 0.0);
  const o6 = A('O', 0.45, 2.4, 0.0);
  const o2 = A('O', -2.95, 1.15, 0.0);
  const c1 = A('C', -2.15, 2.35, 0.0);   // N1 methyl
  const c3 = A('C', -2.15, -2.35, 0.0);  // N3 methyl
  const c7 = A('C', 2.45, 1.05, 0.0);    // N7 methyl
  const h8 = A('H', 2.95, -1.85, 0.0);   // C8 hydrogen

  [[c5, c6], [c6, n1], [n1, c2], [c2, n3], [n3, c4], [c4, c5],
   [c5, n7], [n7, c8], [c8, n9], [n9, c4],
   [c6, o6], [c2, o2], [n1, c1], [n3, c3], [n7, c7], [c8, h8],
  ].forEach(function (b) { bonds.push(b); });

  addMethylH(atoms, bonds, c1, n1);
  addMethylH(atoms, bonds, c3, n3);
  addMethylH(atoms, bonds, c7, n7);
  return { atoms: atoms, bonds: bonds };
}

/* --- scene builders ----------------------------------------------------- */

/** Ball-and-stick model. Atoms and bonds are each one InstancedMesh. */
function buildMolecule(spec, sphereGeo, cylinderGeo, atomMat, bondMat) {
  const group = new THREE.Group();
  const atoms = spec.atoms;
  const dummy = new THREE.Object3D();
  const color = new THREE.Color();

  const atomMesh = new THREE.InstancedMesh(sphereGeo, atomMat, atoms.length);
  atoms.forEach(function (a, i) {
    const radius = CPK_RADIUS[a.el] || 0.3;
    dummy.position.set(a.x, a.y, a.z);
    dummy.quaternion.identity();
    dummy.scale.setScalar(radius);
    dummy.updateMatrix();
    atomMesh.setMatrixAt(i, dummy.matrix);
    atomMesh.setColorAt(i, color.setHex(CPK_COLOR[a.el] || 0xcccccc));
  });
  atomMesh.instanceMatrix.needsUpdate = true;
  if (atomMesh.instanceColor) atomMesh.instanceColor.needsUpdate = true;
  group.add(atomMesh);

  const bonds = spec.bonds || [];
  const bondMesh = new THREE.InstancedMesh(cylinderGeo, bondMat, Math.max(1, bonds.length));
  const up = new THREE.Vector3(0, 1, 0);
  const start = new THREE.Vector3();
  const end = new THREE.Vector3();
  const dir = new THREE.Vector3();
  const mid = new THREE.Vector3();
  bonds.forEach(function (b, i) {
    const p = atoms[b[0]];
    const q = atoms[b[1]];
    start.set(p.x, p.y, p.z);
    end.set(q.x, q.y, q.z);
    dir.copy(end).sub(start);
    const length = dir.length() || 0.001;
    mid.copy(start).add(end).multiplyScalar(0.5);
    dummy.position.copy(mid);
    dummy.quaternion.setFromUnitVectors(up, dir.clone().normalize());
    dummy.scale.set(0.1, length, 0.1);
    dummy.updateMatrix();
    bondMesh.setMatrixAt(i, dummy.matrix);
  });
  bondMesh.instanceMatrix.needsUpdate = true;
  group.add(bondMesh);

  return { group: group, atomMesh: atomMesh, bondMesh: bondMesh, spec: spec };
}

/** Electron-like points orbiting the molecule's bounding shell. */
function makeOrbitParticles(spec) {
  const count = BG_MOBILE ? 22 : 58;
  const atoms = spec.atoms || [];
  let cx = 0, cy = 0, cz = 0;
  atoms.forEach(function (a) { cx += a.x; cy += a.y; cz += a.z; });
  const n = atoms.length || 1;
  cx /= n; cy /= n; cz /= n;

  let radius = 0.6;
  atoms.forEach(function (a) {
    const d = Math.sqrt((a.x - cx) * (a.x - cx) + (a.y - cy) * (a.y - cy) + (a.z - cz) * (a.z - cz));
    if (d > radius) radius = d;
  });
  const shell = radius * 1.55;

  const positions = new Float32Array(count * 3);
  for (let i = 0; i < count; i++) {
    const u = Math.random() * 2 - 1;
    const theta = Math.random() * Math.PI * 2;
    const s = Math.sqrt(1 - u * u);
    const r = shell * (0.82 + Math.random() * 0.45);
    positions[i * 3] = cx + r * s * Math.cos(theta);
    positions[i * 3 + 1] = cy + r * u;
    positions[i * 3 + 2] = cz + r * s * Math.sin(theta);
  }

  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  const mat = new THREE.PointsMaterial({
    color: 0x8fc0ff, size: BG_MOBILE ? 0.1 : 0.075, transparent: true, opacity: 0.85,
    depthWrite: false, blending: THREE.AdditiveBlending, sizeAttenuation: true,
  });
  return new THREE.Points(geo, mat);
}

/** Floating formula rendered to a CanvasTexture on a sprite. */
function makeEquationSprite(text) {
  const width = 512;
  const height = 192;
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  if (ctx) {
    ctx.clearRect(0, 0, width, height);
    ctx.font = '600 68px "Space Grotesk", Inter, system-ui, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.shadowColor = 'rgba(110,168,255,0.9)';
    ctx.shadowBlur = 26;
    ctx.fillStyle = 'rgba(200,220,255,0.95)';
    ctx.fillText(text, width / 2, height / 2);
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.minFilter = THREE.LinearFilter;
  const material = new THREE.SpriteMaterial({
    map: texture, transparent: true, opacity: 0.28, depthWrite: false,
    blending: THREE.AdditiveBlending,
  });
  const sprite = new THREE.Sprite(material);
  sprite.scale.set(3.6, 1.35, 1);
  return sprite;
}

const EQUATIONS = ['E = mc²', 'PV = nRT', 'C₆H₁₂O₆', 'H₂O', 'F = ma', 'a² + b² = c²'];

/* Per-view scene presets. heroScale/others drive composition; drift drives
 * camera orbital speed; sprites/particles drive density. */
const MODE_PRESETS = {
  auth: { camDist: 13, drift: 0.05, hero: 'caffeine', heroScale: 2.0, others: 0.95, ambient: 1.0, sprites: 0.30, particles: 0.95, fog: 0.030 },
  dashboard: { camDist: 18, drift: 0.02, hero: 'benzene', heroScale: 1.5, others: 0.5, ambient: 0.75, sprites: 0.20, particles: 0.45, fog: 0.040 },
  study: { camDist: 9.5, drift: 0.012, hero: 'glucose', heroScale: 2.2, others: 0.0, ambient: 1.05, sprites: 0.10, particles: 0.6, fog: 0.028 },
  default: { camDist: 15, drift: 0.035, hero: 'water', heroScale: 1.7, others: 0.7, ambient: 0.9, sprites: 0.24, particles: 0.6, fog: 0.034 },
};

function initBackground() {
  const controller = {
    ok: false,
    mode: 'auth',
    intensity: 1,
    setMode: function (m) { controller.mode = m || 'default'; applyTargets(); },
    setIntensity: function (l) { controller.intensity = (typeof l === 'number' ? l : 1); applyTargets(); },
    setTheme: function (t) { theme = (t === 'light' ? 'light' : 'dark'); applyTheme(); },
    dispose: function () {},
    stats: function () {
      return {
        ok: controller.ok, mode: controller.mode, intensity: controller.intensity,
        reduced: reduced, running: running, frames: frames,
        totalAtoms: molecules.reduce(function (a, m) { return a + m.spec.atoms.length; }, 0),
        particles: molecules.reduce(function (a, m) {
          return a + (m.particles ? m.particles.geometry.attributes.position.count : 0);
        }, 0),
        sprites: sprites.length,
        molecules: molecules.map(function (m) {
          return { key: m.key, atoms: m.spec.atoms.length, bonds: m.spec.bonds.length, visible: m.group.visible };
        }),
        fogDensity: scene && scene.fog ? scene.fog.density : null,
      };
    },
  };

  const reduced = REDUCED_MOTION;
  const molecules = [];
  const sprites = [];
  let theme = 'dark';
  let scene = null;
  let camera = null;
  let renderer = null;
  let frameHandle = null;
  let running = false;
  let lastTime = 0;
  let elapsed = 0;
  let motion = 0;
  let camDist = 15;
  let camDistTarget = 15;
  let fogDensity = 0.034;
  let fogTarget = 0.034;
  let frames = 0;

  function renderOnce() {
    try { if (renderer && scene && camera) renderer.render(scene, camera); } catch (e) { /* ignore */ }
  }

  function applyTheme() {
    const light = theme === 'light';
    if (scene && scene.fog) scene.fog.color.setHex(light ? 0xe9eef7 : 0x08090a);
    sprites.forEach(function (s) {
      if (s.material && s.material.color) s.material.color.setHex(light ? 0x33405e : 0xffffff);
    });
    if (reduced) renderOnce();
  }

  function applyTargets() {
    const preset = MODE_PRESETS[controller.mode] || MODE_PRESETS.default;
    const k = Math.max(0.15, Math.min(1.5, Number(controller.intensity) || 1));
    motion = reduced ? 0 : preset.drift * k;
    camDistTarget = preset.camDist;
    fogTarget = preset.fog;

    molecules.forEach(function (m) {
      const isHero = m.key === preset.hero;
      m.targetScale = m.base * (isHero ? preset.heroScale : preset.others);
      m.group.visible = isHero || preset.others > 0.05;
      if (m.particles) {
        m.particles.visible = preset.particles > 0.15;
        if (m.particles.material) m.particles.material.opacity = Math.min(1, preset.particles * k * 1.1);
      }
    });

    sprites.forEach(function (s) {
      s.visible = preset.sprites > 0.08;
      if (s.material) s.material.opacity = Math.min(0.6, preset.sprites * k);
    });

    if (reduced) renderOnce();
  }

  function frame(now) {
    if (!running) return;
    frameHandle = requestAnimationFrame(frame);
    if (!lastTime) lastTime = now;
    const dt = Math.min(0.05, (now - lastTime) / 1000);
    lastTime = now;
    elapsed += dt;

    camDist += (camDistTarget - camDist) * Math.min(1, dt * 1.8);
    fogDensity += (fogTarget - fogDensity) * Math.min(1, dt * 1.8);
    if (scene.fog) scene.fog.density = fogDensity;

    const angle = elapsed * motion;
    camera.position.x = Math.sin(angle) * camDist;
    camera.position.z = Math.cos(angle) * camDist;
    camera.position.y = Math.sin(angle * 0.6) * camDist * 0.12;
    camera.lookAt(0, 0, 0);

    const spin = 0.1 + motion * 0.5;
    molecules.forEach(function (m, i) {
      const s = m.group.scale.x + (m.targetScale - m.group.scale.x) * Math.min(1, dt * 2.5);
      m.group.scale.setScalar(s);
      m.group.rotation.y += dt * spin * (1 + i * 0.15);
      m.group.rotation.x += dt * spin * 0.35;
      if (m.particles) m.particles.rotation.y -= dt * 0.3;
    });

    sprites.forEach(function (s) {
      s.position.y = s.userData.baseY + Math.sin(elapsed * 0.35 + s.userData.phase) * 0.5;
      if (s.material) s.material.rotation += dt * 0.04;
    });

    renderer.render(scene, camera);
    frames++;
  }

  function start() {
    if (running || reduced) return;
    running = true;
    lastTime = 0;
    frameHandle = requestAnimationFrame(frame);
  }
  function stop() {
    running = false;
    if (frameHandle) cancelAnimationFrame(frameHandle);
    frameHandle = null;
  }

  try {
    const canvas = $('bg-canvas');
    if (!canvas || typeof THREE === 'undefined') throw new Error('three unavailable');

    renderer = new THREE.WebGLRenderer({
      canvas: canvas, alpha: true, antialias: !BG_MOBILE, powerPreference: 'low-power',
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, BG_MOBILE ? 1.5 : 2));
    renderer.setSize(window.innerWidth, window.innerHeight, false);
    renderer.setClearColor(0x000000, 0);

    scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x08090a, 0.035);

    camera = new THREE.PerspectiveCamera(55, window.innerWidth / window.innerHeight, 0.1, 200);
    camera.position.set(0, 0, 15);

    scene.add(new THREE.AmbientLight(0x404040, 1.0));
    const keyLight = new THREE.DirectionalLight(0xffffff, 0.8);
    keyLight.position.set(6, 9, 7);
    scene.add(keyLight);
    const rimLight = new THREE.PointLight(0x6ea8ff, 1.2, 60, 2);
    rimLight.position.set(-8, -4, 6);
    scene.add(rimLight);
    const accentLight = new THREE.PointLight(0xa78bfa, 0.8, 60, 2);
    accentLight.position.set(8, 5, -5);
    scene.add(accentLight);

    const sphereGeo = new THREE.SphereGeometry(1, BG_MOBILE ? 10 : 18, BG_MOBILE ? 8 : 14);
    const cylinderGeo = new THREE.CylinderGeometry(1, 1, 1, BG_MOBILE ? 6 : 12, 1, false);
    const atomMat = new THREE.MeshPhongMaterial({ shininess: 90, specular: 0xffffff });
    const bondMat = new THREE.MeshPhongMaterial({ color: 0x8a93a6, shininess: 30, specular: 0x444444 });

    const defs = [
      { key: 'caffeine', spec: molCaffeine(), pos: [0, 0, 0], base: 1.0 },
      { key: 'glucose', spec: molGlucose(), pos: [-8.5, 2.4, -6], base: 0.9 },
      { key: 'benzene', spec: molBenzene(), pos: [8.5, -2.0, -7], base: 0.95 },
      { key: 'water', spec: molWater(), pos: [3.6, 4.0, -8], base: 1.15 },
    ];

    defs.forEach(function (def) {
      const built = buildMolecule(def.spec, sphereGeo, cylinderGeo, atomMat, bondMat);
      built.key = def.key;
      built.base = def.base;
      built.targetScale = def.base;
      built.group.position.set(def.pos[0], def.pos[1], def.pos[2]);
      built.particles = makeOrbitParticles(def.spec);
      built.group.add(built.particles);
      scene.add(built.group);
      molecules.push(built);
    });

    EQUATIONS.forEach(function (label, i) {
      const sprite = makeEquationSprite(label);
      const angle = ((Math.PI * 2) / EQUATIONS.length) * i + 0.35;
      const radius = 10 + (i % 3) * 2.4;
      const y = (i % 2 ? 1 : -1) * (2.2 + (i % 3) * 1.7);
      sprite.position.set(Math.cos(angle) * radius, y, Math.sin(angle) * radius - 4);
      sprite.userData.baseY = y;
      sprite.userData.phase = i * 1.7;
      scene.add(sprite);
      sprites.push(sprite);
    });

    controller.ok = true;
    applyTheme();
    applyTargets();

    canvas.addEventListener('webglcontextlost', function (ev) {
      ev.preventDefault();
      stop();
    }, false);
    canvas.addEventListener('webglcontextrestored', function () {
      try {
        lastTime = 0;
        if (reduced) renderOnce(); else start();
      } catch (e) { /* ignore */ }
    }, false);

    document.addEventListener('visibilitychange', function () {
      if (document.hidden) stop();
      else start();
    });

    window.addEventListener('resize', function () {
      if (!renderer || !camera) return;
      camera.aspect = window.innerWidth / window.innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(window.innerWidth, window.innerHeight, false);
      if (reduced) renderOnce();
    });

    window.addEventListener('pagehide', function () {
      stop();
      try {
        sphereGeo.dispose();
        cylinderGeo.dispose();
        atomMat.dispose();
        bondMat.dispose();
        molecules.forEach(function (m) {
          if (m.particles) { m.particles.geometry.dispose(); m.particles.material.dispose(); }
        });
        renderer.dispose();
      } catch (e) { /* ignore */ }
    });

    controller.dispose = stop;
    if (reduced) renderOnce(); else start();
    return controller;
  } catch (e) {
    /* No WebGL / no Three.js — fall back to the CSS gradient. */
    try { document.body.classList.add('no-webgl'); } catch (e2) { /* ignore */ }
    controller.ok = false;
    return controller;
  }
}

/* ==========================================================================
 * Micro-interactions — optional polish, fully isolated
 * ========================================================================== */

function initMicrointeractions() {
  try {
    if (REDUCED_MOTION) return;

    /* Press feedback on every button, delegated so dynamically added buttons
     * get it for free. */
    document.addEventListener('pointerdown', function (ev) {
      const btn = ev.target && ev.target.closest ? ev.target.closest('button') : null;
      if (btn) btn.classList.add('cf-pressed');
    });
    document.addEventListener('pointerup', function () {
      document.querySelectorAll('button.cf-pressed').forEach(function (b) { b.classList.remove('cf-pressed'); });
    });

    /* Staggered entrance for freshly rendered cards (GSAP when present,
     * Web Animations API otherwise). */
    const observer = new MutationObserver(function (records) {
      const batch = [];
      records.forEach(function (record) {
        record.addedNodes.forEach(function (node) {
          if (node.nodeType !== 1 || !node.classList) return;
          if (node.classList.contains('card') || node.classList.contains('q') || node.classList.contains('obs')) {
            batch.push(node);
          }
        });
      });
      if (!batch.length) return;
      animTo(batch, { opacity: 1, y: 0, duration: 0.5, stagger: 0.06, ease: 'expo.out' });
    });
    const main = $('app');
    if (main) observer.observe(main, { childList: true, subtree: true });
  } catch (e) {
    /* Micro-interactions are cosmetic; ignore any failure. */
  }
}

/* ==========================================================================
 * Auth
 * ========================================================================== */

function switchAuthTab(tab) {
  const name = tab || 'login';
  document.querySelectorAll('.auth-tab').forEach(function (t) { t.classList.remove('active'); });
  document.querySelectorAll('.auth-form').forEach(function (f) { f.classList.add('hidden'); });
  const tabEl = document.querySelector('.auth-tab[data-auth="' + name + '"]');
  if (tabEl) tabEl.classList.add('active');
  const form = $('auth-form-' + name);
  if (form) form.classList.remove('hidden');
}

function bindAuthEvents() {
  document.querySelectorAll('.auth-tab').forEach(function (tab) {
    tab.addEventListener('click', function () { switchAuthTab(tab.dataset.auth); });
  });
  const forgot = $('forgot-link');
  if (forgot) forgot.addEventListener('click', function (e) { e.preventDefault(); switchAuthTab('reset'); });
  const back = $('back-to-login');
  if (back) back.addEventListener('click', function (e) { e.preventDefault(); switchAuthTab('login'); });

  const loginBtn = $('login-btn');
  if (loginBtn) loginBtn.addEventListener('click', doLogin);
  const registerBtn = $('register-btn');
  if (registerBtn) registerBtn.addEventListener('click', doRegister);
  const resetBtn = $('reset-btn');
  if (resetBtn) resetBtn.addEventListener('click', doReset);
  const logoutBtn = $('logout-btn');
  if (logoutBtn) logoutBtn.addEventListener('click', doLogout);

  /* Enter-to-submit on the credential fields. */
  ['login-email', 'login-password'].forEach(function (id) {
    const field = $(id);
    if (field) field.addEventListener('keydown', function (e) { if (e.key === 'Enter') doLogin(); });
  });
  ['reg-name', 'reg-email', 'reg-password'].forEach(function (id) {
    const field = $(id);
    if (field) field.addEventListener('keydown', function (e) { if (e.key === 'Enter') doRegister(); });
  });

  bindPasswordMeter();
}

function bindPasswordMeter() {
  const input = $('reg-password');
  const bar = $('pw-strength');
  if (!input || !bar) return;
  const colors = ['#f87171', '#fbbf24', '#34d399', '#4f8cff', '#a78bfa'];
  const widths = ['20%', '40%', '60%', '80%', '100%'];
  const labels = ['very weak', 'weak', 'fair', 'strong', 'very strong'];

  input.addEventListener('input', function () {
    const pw = input.value;
    let strength = 0;
    if (pw.length >= 8) strength++;
    if (pw.length >= 12) strength++;
    if (/[A-Z]/.test(pw)) strength++;
    if (/[0-9]/.test(pw)) strength++;
    if (/[^A-Za-z0-9]/.test(pw)) strength++;

    clear(bar); /* replaceChildren — never innerHTML */
    if (!pw.length) { bar.setAttribute('aria-label', ''); return; }
    const index = Math.max(0, Math.min(4, strength - 1));
    const fill = el('div', { class: 'pw-strength-bar' });
    fill.style.width = widths[index];
    fill.style.background = colors[index];
    bar.appendChild(fill);
    bar.setAttribute('aria-label', 'Password strength: ' + labels[index]);
  });
}

/** Apply a login/session payload to application state. */
function applyAccount(data, fallbackEmail) {
  if (!data) return;
  ACCOUNT = {
    account_id: data.account_id || (ACCOUNT && ACCOUNT.account_id) || '',
    email: data.email || fallbackEmail || (ACCOUNT && ACCOUNT.email) || '',
    display_name: data.display_name || (ACCOUNT && ACCOUNT.display_name) || '',
    verified: data.verified,
  };
  if (data.learner_id) LEARNER = data.learner_id;
  if (data.api_token) TOKEN = data.api_token;
  if (data.session_token) SESSION_TOKEN = data.session_token;
}

function displayName() {
  if (ACCOUNT && ACCOUNT.display_name) return ACCOUNT.display_name;
  if (ACCOUNT && ACCOUNT.email) return ACCOUNT.email.split('@')[0];
  return LEARNER || 'learner';
}

async function doLogin() {
  const emailField = $('login-email');
  const passwordField = $('login-password');
  const email = emailField ? emailField.value.trim() : '';
  const password = passwordField ? passwordField.value : '';
  if (!email || !password) { status('enter email and password', 'err'); return; }

  const btn = $('login-btn');
  setBusy(btn, true, 'Signing in…');
  try {
    const data = await api('/api/account/login', {
      method: 'POST',
      body: JSON.stringify({ email: email, password: password }),
    });
    applyAccount(data, email);
    storeSet(STORAGE.SESSION, SESSION_TOKEN);
    storeSet(STORAGE.TOKEN, TOKEN);

    /* The login payload omits display_name; fetch the canonical session. */
    try {
      const sess = await api('/api/account/session', {
        method: 'POST',
        body: JSON.stringify({ session_token: SESSION_TOKEN }),
      });
      applyAccount(sess, email);
      if (TOKEN) storeSet(STORAGE.TOKEN, TOKEN);
    } catch (e) { /* non-fatal: fall back to the email handle */ }

    if (passwordField) passwordField.value = '';
    await enterApp();
    await checkOnboarding();
    status('signed in', 'ok');
  } catch (e) {
    status(e.message || 'sign in failed', 'err');
  } finally {
    setBusy(btn, false);
  }
}

async function doRegister() {
  const name = ($('reg-name') || {}).value ? $('reg-name').value.trim() : '';
  const email = ($('reg-email') || {}).value ? $('reg-email').value.trim() : '';
  const password = ($('reg-password') || {}).value ? $('reg-password').value : '';
  if (!email || !password) { status('enter email and password', 'err'); return; }
  if (password.length < 8) { status('password must be at least 8 characters', 'err'); return; }

  const btn = $('register-btn');
  setBusy(btn, true, 'Creating…');
  try {
    await api('/api/account/create', {
      method: 'POST',
      body: JSON.stringify({ email: email, password: password, display_name: name }),
    });
    status('account created — check your email to verify', 'ok');
    switchAuthTab('login');
    const loginEmail = $('login-email');
    if (loginEmail) loginEmail.value = email;
    const loginPassword = $('login-password');
    if (loginPassword) loginPassword.focus();
  } catch (e) {
    status(e.message || 'could not create account', 'err');
  } finally {
    setBusy(btn, false);
  }
}

async function doReset() {
  const emailField = $('reset-email');
  const email = emailField ? emailField.value.trim() : '';
  if (!email) { status('enter your email', 'err'); return; }
  const btn = $('reset-btn');
  setBusy(btn, true, 'Sending…');
  try {
    await api('/api/account/reset-request', {
      method: 'POST',
      body: JSON.stringify({ email: email }),
    });
    status('if that email exists, a reset link is on its way', 'ok');
    switchAuthTab('login');
  } catch (e) {
    status(e.message || 'could not send reset link', 'err');
  } finally {
    setBusy(btn, false);
  }
}

async function doLogout() {
  if (SESSION_TOKEN && TOKEN) {
    try {
      await api('/api/account/logout', {
        method: 'POST',
        body: JSON.stringify({ session_token: SESSION_TOKEN }),
      });
    } catch (e) { /* log out locally regardless */ }
  }
  SESSION_TOKEN = '';
  TOKEN = '';
  ACCOUNT = null;
  LEARNER = '';
  SESSION = [];
  SESSION_RESULTS = [];
  TUTOR_STATE = null;
  storeDel(STORAGE.SESSION);
  storeDel(STORAGE.TOKEN);
  showAuthView();
  status('signed out');
}

/* ==========================================================================
 * Navigation
 * ========================================================================== */

function switchView(view) {
  document.querySelectorAll('.nav-item').forEach(function (i) { i.classList.remove('active'); });
  document.querySelectorAll('.bottom-tab').forEach(function (t) { t.classList.remove('active'); });

  /* Only the *inner* views toggle here. The outer containers
   * (#view-auth / #view-onboarding / #view-main) share the .view class but
   * are managed by showAuthView / showOnboardingView / enterApp, so clearing
   * them would blank the whole application. */
  const container = document.querySelector('.main-content') || document;
  container.querySelectorAll('.view').forEach(function (v) { v.classList.remove('active'); });

  const nav = document.querySelector('.nav-item[data-view="' + view + '"]');
  if (nav) nav.classList.add('active');
  const tab = document.querySelector('.bottom-tab[data-view="' + view + '"]');
  if (tab) tab.classList.add('active');
  const section = $('view-' + view);
  if (section) section.classList.add('active');

  /* Close the off-canvas sidebar on small screens after a selection. */
  if (window.innerWidth <= 768) {
    const sidebar = document.querySelector('.sidebar');
    if (sidebar) sidebar.classList.remove('open');
  }

  /* Drive the background scene: Study focuses, Dashboard stays ambient. */
  if (view === 'study') { setBackgroundMode('study'); setSceneIntensity(0.8); }
  else if (view === 'dashboard') { setBackgroundMode('dashboard'); setSceneIntensity(0.7); }
  else { setBackgroundMode('default'); setSceneIntensity(1); }

  return section;
}

function bindNavigation() {
  if (BOUND.nav) return;
  BOUND.nav = true;

  document.querySelectorAll('.nav-item').forEach(function (item) {
    item.addEventListener('click', function () { switchView(item.dataset.view); });
  });

  document.querySelectorAll('.bottom-tab').forEach(function (tab) {
    tab.addEventListener('click', function () { switchView(tab.dataset.view); });
  });

  const startBtn = $('dash-start-session');
  if (startBtn) startBtn.addEventListener('click', function () { switchView('study'); });
  const addSrcBtn = $('dash-add-source');
  if (addSrcBtn) addSrcBtn.addEventListener('click', function () { switchView('sources'); });
}

/* ==========================================================================
 * View transitions & boot
 * ========================================================================== */

function showAuthView() {
  const auth = $('view-auth');
  const main = $('view-main');
  const onboarding = $('view-onboarding');
  if (main) main.classList.remove('active');
  if (onboarding) onboarding.classList.remove('active');
  if (auth) auth.classList.add('active');
  /* Auth is the hero moment: the largest, most dramatic molecule. */
  setBackgroundMode('auth');
  setSceneIntensity(1.2);
}

async function enterApp() {
  const auth = $('view-auth');
  const main = $('view-main');
  if (auth) auth.classList.remove('active');
  if (main) main.classList.add('active');

  const tag = $('learner-tag');
  if (tag) tag.textContent = displayName();

  installStyles();
  initTheme();
  initSettings();
  bindNavigation();
  setBackgroundMode('dashboard');
  setSceneIntensity(0.7);

  if (!BOUND.app) {
    BOUND.app = true;
    bindSourcesEvents();
    bindStudyEvents();
    bindProfileEvents();
    bindTutorEvents();
    bindIntegrationsEvents();
    bindPalette();
  }

  if (!MANIFEST) {
    try { MANIFEST = await api('/api/manifest'); }
    catch (e) { /* manifest is not essential for every view */ }
  }
  renderStylePicker();
  renderMcpPlan();

  await loadDashboard();
  status('ready', 'ok');
}

/** Restore a persisted session, or fall back to the auth view. */
async function boot() {
  TOKEN = storeGet(STORAGE.TOKEN) || '';
  const storedSession = storeGet(STORAGE.SESSION);
  if (!storedSession) { showAuthView(); return; }

  SESSION_TOKEN = storedSession;
  try {
    const sess = await api('/api/account/session', {
      method: 'POST',
      body: JSON.stringify({ session_token: SESSION_TOKEN }),
    });
    applyAccount(sess);
    if (TOKEN) storeSet(STORAGE.TOKEN, TOKEN);
    await enterApp();
    await checkOnboarding();
  } catch (e) {
    /* Session invalid or expired: clear it and show sign-in. */
    SESSION_TOKEN = '';
    storeDel(STORAGE.SESSION);
    showAuthView();
  }
}

/** Auto-show onboarding for a learner with no observations yet. */
async function checkOnboarding() {
  try {
    const profile = await api('/api/profile' + qs({ learner_id: LEARNER }));
    const observations = (profile.profile && profile.profile.observations) || [];
    if (!observations.length) await showOnboardingView();
  } catch (e) { /* a brand-new learner may have no profile at all */ }
}

/* ==========================================================================
 * Dashboard
 * ========================================================================== */

async function loadDashboard() {
  if (!LEARNER) return;
  let data;
  try {
    data = await api('/api/profile' + qs({ learner_id: LEARNER }));
  } catch (e) {
    status(e.message || 'could not load dashboard', 'err');
    return;
  }
  const profile = (data && data.profile) || {};
  const session = (data && data.session) || {};
  const observations = profile.observations || [];

  const greeting = $('dash-greeting');
  if (greeting) greeting.textContent = 'Welcome back, ' + displayName();

  const summary = $('dash-summary');
  if (summary) {
    const n = Number(session.n || 0);
    const correct = Number(session.correct || 0);
    const accuracy = Number(session.accuracy || 0);
    summary.textContent = n
      ? n + ' total attempts · ' + correct + ' correct · ' + Math.round(accuracy * 100) + '% accuracy'
      : 'No attempts recorded yet — add a source and start a session.';
  }

  const streak = $('streak-count');
  if (streak) streak.textContent = String(computeStreak(session));

  renderMasteryMap(profile);
  renderProgressGrid(session, profile);
  renderGoals(session, observations);
  renderCalibration(session, observations);
  renderAnalytics(session, profile);
  renderTodayPlan(session, observations);
  renderRecentSessions(session);
}

function computeStreak(session) {
  const n = Number((session && session.n) || 0);
  if (!n) return 0;
  return Math.min(7, Math.max(1, Math.floor(n / 5)));
}

function setRing(id, pct, circumference) {
  const ring = $(id);
  if (!ring) return;
  const circumferenceValue = circumference || RING_CIRCUMFERENCE;
  const fraction = clamp01(pct);
  const offset = circumferenceValue * (1 - fraction);
  ring.style.strokeDashoffset = String(offset);
  const wrapper = ring.closest ? ring.closest('.ring-item') : null;
  if (wrapper) {
    const label = wrapper.querySelector('.ring-label');
    if (label) label.setAttribute('title', Math.round(fraction * 100) + '%');
  }
}

function renderMasteryMap(profile) {
  const map = $('dash-mastery-map');
  if (!map) return;
  clear(map);
  const observations = (profile && profile.observations) || [];
  if (!observations.length) {
    map.appendChild(el('div', {
      class: 'meta',
      text: 'No skills tracked yet. Complete onboarding and a study session to build your mastery map.',
    }));
    return;
  }
  observations.slice(0, 12).forEach(function (obs) {
    const level = obs.confidence === 'high' ? 'mastered'
      : (obs.confidence === 'moderate' ? 'learning' : 'new');
    /* Deterministic fill so the map does not reshuffle on every reload. */
    const base = level === 'mastered' ? 80 : (level === 'learning' ? 45 : 15);
    const span = level === 'mastered' ? 20 : (level === 'learning' ? 25 : 25);
    const pct = base + Math.round((stablePercent(obs.label || obs.construct) / 100) * span);

    const node = el('div', { class: 'mastery-node ' + level });
    node.setAttribute('title', (obs.label || '') + ' — ' + (obs.confidence || 'low') + ' confidence');
    node.appendChild(el('div', { class: 'node-name', text: obs.label || obs.construct || 'skill' }));
    const bar = el('div', { class: 'node-bar' });
    const fill = el('div', { class: 'node-fill' });
    fill.style.width = pct + '%';
    bar.appendChild(fill);
    node.appendChild(bar);
    map.appendChild(node);
  });
}

function renderProgressGrid(session, profile) {
  const grid = $('dash-progress');
  if (!grid) return;
  clear(grid);
  const observations = (profile && profile.observations) || [];
  const accuracy = Number((session && session.accuracy) || 0);
  const metrics = [
    { label: 'Total Attempts', value: Number((session && session.n) || 0) },
    { label: 'Accuracy', value: accuracy > 0 ? Math.round(accuracy * 100) + '%' : '—' },
    { label: 'Skills Tracked', value: observations.length },
    { label: 'Questions', value: (profile && profile.unmeasured && profile.unmeasured.length) ? 'Active' : 'None' },
  ];
  metrics.forEach(function (m) {
    const card = el('div', { class: 'progress-card' });
    card.appendChild(el('div', { class: 'progress-value', text: String(m.value) }));
    card.appendChild(el('div', { class: 'progress-label', text: m.label }));
    grid.appendChild(card);
  });
}

function renderGoals(session, observations) {
  const n = Number((session && session.n) || 0);
  const dailyPct = Math.min(n / 20, 1);
  const weeklyPct = Math.min(n / 100, 1);
  const masteredPct = observations.length
    ? observations.filter(function (o) { return o.confidence === 'high'; }).length / observations.length
    : 0;
  setRing('ring-daily', dailyPct, RING_CIRCUMFERENCE);
  setRing('ring-weekly', weeklyPct, RING_CIRCUMFERENCE);
  setRing('ring-mastered', masteredPct, RING_CIRCUMFERENCE);
}

function renderCalibration(session, observations) {
  const host = $('dash-calibration');
  if (!host) return;
  clear(host);

  const accuracy = Number((session && session.accuracy) || 0);
  const calObs = observations.find(function (o) {
    return o.construct === 'metacognitive_calibration' || o.label === 'Confidence calibration';
  });

  const rows = [];
  if (accuracy > 0) {
    rows.push({ label: 'Accuracy', fraction: accuracy, display: Math.round(accuracy * 100) + '%' });
  }
  if (calObs && typeof calObs.value === 'number') {
    const bias = Number(calObs.value);
    const meanConfidence = clamp01(accuracy + bias);
    rows.push({ label: 'Mean confidence', fraction: meanConfidence, display: Math.round(meanConfidence * 100) + '%' });
    rows.push({
      label: 'Bias',
      fraction: Math.min(Math.abs(bias), 1),
      display: (bias >= 0 ? '+' : '') + Math.round(bias * 100) + '%',
      tone: bias > 0.15 ? 'down' : (bias < -0.15 ? 'up' : ''),
    });
  }

  if (!rows.length) {
    host.appendChild(el('div', { class: 'meta', text: 'Complete review sessions to see calibration data.' }));
    return;
  }

  rows.forEach(function (row) {
    const line = el('div', { class: 'calibration-row' });
    line.appendChild(el('div', { class: 'calibration-label', text: row.label }));
    const barBg = el('div', { class: 'calibration-bar-bg' });
    const fill = el('div', { class: 'calibration-bar-fill' });
    fill.style.width = Math.round(clamp01(row.fraction) * 100) + '%';
    barBg.appendChild(fill);
    line.appendChild(barBg);
    line.appendChild(el('div', { class: 'calibration-value', text: row.display }));
    host.appendChild(line);
  });

  if (calObs && calObs.statement) {
    host.appendChild(el('div', { class: 'meta', text: calObs.statement }));
  }
}

function renderAnalytics(session, profile) {
  const grid = $('dash-analytics');
  if (!grid) return;
  clear(grid);
  const observations = (profile && profile.observations) || [];
  const accuracy = Number((session && session.accuracy) || 0);
  const median = (session && session.median_latency_ms) || null;
  const analytics = [
    { label: 'Total Reviews', value: Number((session && session.n) || 0), trend: null },
    {
      label: 'Accuracy',
      value: accuracy > 0 ? Math.round(accuracy * 100) + '%' : '—',
      trend: accuracy > 0 ? (accuracy >= 0.75 ? 'up' : 'down') : null,
    },
    { label: 'Skills', value: observations.length, trend: null },
    { label: 'Median Latency', value: median ? Math.round(median) + 'ms' : '—', trend: null },
  ];
  analytics.forEach(function (a) {
    const card = el('div', { class: 'analytics-card' });
    card.appendChild(el('div', { class: 'analytics-value', text: String(a.value) }));
    card.appendChild(el('div', { class: 'analytics-label', text: a.label }));
    if (a.trend) {
      card.appendChild(el('div', {
        class: 'analytics-trend ' + a.trend,
        text: a.trend === 'up' ? '↑ on target' : '↓ needs work',
      }));
    }
    grid.appendChild(card);
  });
}

function renderTodayPlan(session, observations) {
  const host = $('dash-plan');
  if (!host) return;
  clear(host);
  const items = [];
  const due = Number((session && session.n) || 0);
  items.push(due ? 'Review ' + due + ' recorded attempt' + (due === 1 ? '' : 's') : 'Start your first study session');
  if (!observations.length) items.push('Finish onboarding to set your baseline');
  items.push('Keep sessions inside the 85% success band');
  items.forEach(function (text) {
    host.appendChild(el('div', { class: 'meta', text: '· ' + text }));
  });
}

function renderRecentSessions(session) {
  const host = $('dash-sessions');
  if (!host) return;
  clear(host);
  const n = Number((session && session.n) || 0);
  if (!n) {
    host.appendChild(el('div', { class: 'meta', text: 'No sessions yet. Start your first session to see progress here.' }));
    return;
  }
  const card = el('div', { class: 'meta' });
  card.appendChild(el('div', { text: (session.verdict || 'session') + ' — ' + (session.statement || '') }));
  host.appendChild(card);
}

/* ==========================================================================
 * Study
 * ========================================================================== */

function bindStudyEvents() {
  const load = $('load-session');
  if (load) load.addEventListener('click', loadSession);
  const more = $('new-questions');
  if (more) more.addEventListener('click', function () {
    switchView('sources');
    refreshSources();
    status('add sources to generate more questions');
  });
}

function renderStageIndicators(currentStage) {
  const wrap = $('session-stages');
  if (!wrap) return;
  clear(wrap);
  const dots = el('div', { class: 'stage-indicators' });
  const labels = el('div', { class: 'stage-labels' });
  STAGES.forEach(function (stage, i) {
    const dot = el('div', { class: 'stage-dot' });
    const label = el('div', { class: 'stage-label', text: stage.label });
    if (i < currentStage) { dot.classList.add('completed'); label.classList.add('completed'); }
    else if (i === currentStage) { dot.classList.add('active'); label.classList.add('active'); }
    dots.appendChild(dot);
    labels.appendChild(label);
  });
  wrap.appendChild(dots);
  wrap.appendChild(labels);
}

function currentStageIndex() {
  if (!SESSION.length) return 0;
  const ratio = SESSION_INDEX / SESSION.length;
  return Math.min(STAGES.length - 1, Math.floor(ratio * STAGES.length));
}

async function loadSession() {
  if (!LEARNER) { status('sign in first', 'err'); return; }
  const btn = $('load-session');
  setBusy(btn, true, 'Loading…');
  try {
    const data = await api('/api/session' + qs({ learner_id: LEARNER, limit: 20 }));
    SESSION = data.items || [];
    SESSION_INDEX = 0;
    SESSION_RESULTS = [];

    const forecast = data.forecast || {};
    const retrievability = Number(forecast.mean_retrievability || 0);
    const meta = $('session-meta');
    if (meta) {
      meta.textContent = 'Day ' + data.day + ' · ' + (data.n_due || 0) + ' due · predicted recall '
        + Math.round(retrievability * 100) + '%';
    }

    if (!SESSION.length) {
      renderStageIndicators(0);
      const area = $('question-area');
      if (area) {
        clear(area);
        area.appendChild(el('div', {
          class: 'card',
          text: 'Nothing is due. Generate questions from a source first.',
        }));
      }
      status('nothing due', 'ok');
      return;
    }

    const summary = $('summary-area');
    if (summary) clear(summary);
    renderStageIndicators(0);
    renderQuestion();
    status('session loaded', 'ok');
  } catch (e) {
    status(e.message || 'could not load session', 'err');
  } finally {
    setBusy(btn, false);
  }
}

function renderQuestion() {
  const area = $('question-area');
  if (!area) return;
  clear(area);
  if (SESSION_INDEX >= SESSION.length) { renderSummary(); return; }
  renderStageIndicators(currentStageIndex());
  const q = SESSION[SESSION_INDEX];
  SESSION_QUESTION_SHOWN_AT = (window.performance && performance.now) ? performance.now() : Date.now();
  area.appendChild(questionCard(q, true));
}

/**
 * Render a question. When interactive, the card carries a free-text area, a
 * confidence slider and the four-button FSRS grading row.
 */
function questionCard(q, interactive) {
  const card = el('div', { class: 'q' });
  const head = el('div');
  head.appendChild(el('span', { class: 'style', text: q.style || 'question' }));
  if (q.bloom) head.appendChild(el('span', { class: 'bloom', text: q.bloom }));
  card.appendChild(head);
  card.appendChild(el('div', { class: 'prompt', text: q.prompt || '' }));
  if (q.source_span) card.appendChild(el('div', { class: 'src', text: q.source_span }));

  if (!interactive) {
    card.appendChild(el('div', { class: 'meta', text: 'Expected: ' + (q.answer || '') }));
    return card;
  }

  const ta = el('textarea', {
    attrs: { rows: '5', placeholder: 'Answer from memory first, before you look.', 'aria-label': 'Your answer' },
  });
  card.appendChild(ta);

  const row = el('div', { class: 'row' });
  const conf = el('div', { class: 'conf' });
  conf.appendChild(el('span', { text: 'Confidence' }));
  const range = el('input', { attrs: { type: 'range', min: '0', max: '100', value: '50', 'aria-label': 'Confidence' } });
  const confVal = el('span', { text: '50%' });
  range.addEventListener('input', function () { confVal.textContent = range.value + '%'; });
  conf.appendChild(range);
  conf.appendChild(confVal);
  row.appendChild(conf);
  card.appendChild(row);

  /* Four-button FSRS grading — the Anki interaction, dual-coded with the
   * approximate next interval under each label. */
  const gradeRow = el('div', { class: 'grade-row' });
  const grades = [
    { label: 'Again', time: '<1d', value: 1, cls: 'again' },
    { label: 'Hard', time: '2d', value: 2, cls: 'hard' },
    { label: 'Good', time: '4d', value: 3, cls: 'good' },
    { label: 'Easy', time: '7d', value: 4, cls: 'easy' },
  ];

  let answered = false;
  grades.forEach(function (g) {
    const btn = el('button', { class: 'grade-btn ' + g.cls, attrs: { type: 'button' } });
    btn.appendChild(el('span', { class: 'grade-label', text: g.label }));
    btn.appendChild(el('span', { class: 'grade-time', text: g.time }));
    btn.addEventListener('click', async function () {
      if (answered) return;
      answered = true;
      gradeRow.querySelectorAll('button').forEach(function (b) { b.disabled = true; });

      const now = (window.performance && performance.now) ? performance.now() : Date.now();
      const latency = Math.max(0, Math.round(now - SESSION_QUESTION_SHOWN_AT));
      const correct = g.value >= 3;
      const answer = ta.value;

      try {
        await api('/api/attempt', {
          method: 'POST',
          body: JSON.stringify({
            learner_id: LEARNER,
            qid: q.qid,
            skill_id: q.skill_id || 'general',
            correct: correct,
            grade: g.value,
            latency_ms: latency,
            confidence: Number(range.value) / 100,
            response: answer,
          }),
        });
        SESSION_RESULTS.push({ qid: q.qid, correct: correct, grade: g.value, latency_ms: latency });

        renderFeedback(card, correct ? 'correct' : 'incorrect', q);
        const message = correct
          ? 'Correct. This is evidence the skill is available at this difficulty.'
          : 'Incorrect. The target answer is: ' + (q.answer || '');
        showBottomBanner(correct ? 'correct' : 'incorrect', message, function () {
          SESSION_INDEX++;
          renderQuestion();
        });
      } catch (e) {
        answered = false;
        gradeRow.querySelectorAll('button').forEach(function (b) { b.disabled = false; });
        status(e.message || 'could not record attempt', 'err');
      }
    });
    gradeRow.appendChild(btn);
  });
  card.appendChild(gradeRow);

  return card;
}

function renderFeedback(card, verdict, q) {
  const fb = el('div', { class: 'fb ' + verdict });
  const lines = [];
  if (verdict === 'correct') {
    lines.push(['Result', 'Correct.']);
    lines.push(['What it means', 'This is evidence the skill is available at this difficulty.']);
  } else {
    lines.push(['Result', 'Incorrect. Target answer: ' + (q.answer || '')]);
    lines.push(['What it means', 'Your answer did not match the target. Check whether you answered the question that was asked.']);
  }
  lines.forEach(function (pair) {
    const line = el('div', { class: 'line' });
    line.appendChild(el('div', { class: 'k', text: pair[0] }));
    line.appendChild(el('div', { text: pair[1] }));
    fb.appendChild(line);
  });
  card.appendChild(fb);
}

/** Brilliant-style bottom banner. `onNext` fires when the learner continues. */
function showBottomBanner(type, text, onNext) {
  const existing = document.querySelector('.bottom-banner');
  if (existing) existing.remove();

  const banner = el('div', { class: 'bottom-banner ' + (type || '') });
  banner.setAttribute('role', 'status');
  banner.setAttribute('aria-live', 'polite');
  banner.appendChild(el('div', { class: 'banner-text', text: text }));

  const advance = function () {
    banner.classList.remove('show');
    document.removeEventListener('keydown', onKey);
    setTimeout(function () { banner.remove(); }, 300);
    if (typeof onNext === 'function') onNext();
  };
  function onKey(e) {
    if (e.key === 'Escape') { e.preventDefault(); advance(); }
    else if (e.key === 'Enter' && document.activeElement === btn) { /* native click */ }
  }

  const btn = el('button', { class: 'banner-btn', text: 'Next', attrs: { type: 'button' } });
  btn.addEventListener('click', advance);
  banner.appendChild(btn);
  document.body.appendChild(banner);
  document.addEventListener('keydown', onKey);
  requestAnimationFrame(function () { banner.classList.add('show'); });
  btn.focus();
}

function renderSummary() {
  const area = $('summary-area');
  if (!area) return;
  clear(area);
  const n = SESSION_RESULTS.length;
  const correct = SESSION_RESULTS.filter(function (r) { return r.correct; }).length;
  const acc = n ? correct / n : 0;

  let verdict, statement;
  if (acc >= 0.9) {
    verdict = 'under-challenged';
    statement = 'This set was too easy to produce learning; difficulty will increase next session.';
  } else if (acc >= 0.75) {
    verdict = 'in the productive band';
    statement = 'This is the band where learning is fastest; the system will hold you here.';
  } else if (acc >= 0.5) {
    verdict = 'struggling productively';
    statement = 'Below the optimal band; load will be reduced on the weakest skills.';
  } else {
    verdict = 'over-loaded';
    statement = 'The material is beyond reach at this granularity; prerequisites will be re-taught.';
  }

  const card = el('div', { class: 'card' });
  card.appendChild(el('h2', { text: 'Session Summary — ' + verdict }));
  card.appendChild(el('p', { class: 'lede', text: statement }));
  card.appendChild(el('p', {
    class: 'meta',
    text: n ? correct + '/' + n + ' correct (' + Math.round(acc * 100) + '%)' : 'No questions were answered.',
  }));
  area.appendChild(card);
  renderStageIndicators(STAGES.length);
}

/* ==========================================================================
 * Sources & question generation
 * ========================================================================== */

function bindSourcesEvents() {
  const add = $('add-source');
  if (add) add.addEventListener('click', addSource);
  const gen = $('generate');
  if (gen) gen.addEventListener('click', generateQuestions);
}

async function addSource() {
  const textField = $('source-text');
  const titleField = $('source-title');
  const text = textField ? textField.value : '';
  if (!text.trim()) { status('paste some text first', 'err'); return; }
  if (!LEARNER) { status('sign in first', 'err'); return; }

  const btn = $('add-source');
  setBusy(btn, true, 'Adding…');
  try {
    await api('/api/source', {
      method: 'POST',
      body: JSON.stringify({
        learner_id: LEARNER,
        title: titleField ? titleField.value : '',
        text: text,
      }),
    });
    status('source added', 'ok');
    if (textField) textField.value = '';
    if (titleField) titleField.value = '';
    await refreshSources();
  } catch (e) {
    status(e.message || 'could not add source', 'err');
  } finally {
    setBusy(btn, false);
  }
}

async function refreshSources() {
  if (!LEARNER) return;
  try {
    const exp = await api('/api/export' + qs({ learner_id: LEARNER }));
    const select = $('gen-source');
    if (!select) return;
    clear(select);
    const sources = exp.sources || [];
    sources.forEach(function (s) {
      select.appendChild(el('option', {
        text: (s.title || s.source_id) + ' (' + (s.n_chars || 0) + ' chars)',
        attrs: { value: s.source_id },
      }));
    });
    if (!sources.length) {
      select.appendChild(el('option', { text: 'no sources yet', attrs: { value: '' } }));
    }
  } catch (e) { /* the selector simply stays empty */ }
}

function renderStylePicker() {
  const wrap = $('style-picker');
  if (!wrap) return;
  clear(wrap);
  const styles = (MANIFEST && MANIFEST.styles) || [];
  styles.forEach(function (name) {
    const chip = el('button', {
      class: 'chip',
      text: name,
      attrs: { type: 'button', 'aria-pressed': 'false' },
    });
    chip.addEventListener('click', function () {
      if (SELECTED_STYLES.has(name)) {
        SELECTED_STYLES.delete(name);
        chip.classList.remove('on');
        chip.setAttribute('aria-pressed', 'false');
      } else {
        SELECTED_STYLES.add(name);
        chip.classList.add('on');
        chip.setAttribute('aria-pressed', 'true');
      }
    });
    wrap.appendChild(chip);
  });
}

async function generateQuestions() {
  const select = $('gen-source');
  const sourceId = select ? select.value : '';
  if (!sourceId) { status('add a source first', 'err'); return; }
  if (!LEARNER) { status('sign in first', 'err'); return; }

  const btn = $('generate');
  setBusy(btn, true, 'Generating…');
  try {
    const body = { learner_id: LEARNER, source_id: sourceId, max_per_style: 3 };
    if (SELECTED_STYLES.size) body.styles = Array.from(SELECTED_STYLES);
    const data = await api('/api/generate', { method: 'POST', body: JSON.stringify(body) });
    renderGenerated(data);
    status((data.generated || 0) + ' questions generated', 'ok');
  } catch (e) {
    status(e.message || 'could not generate questions', 'err');
  } finally {
    setBusy(btn, false);
  }
}

function renderGenerated(data) {
  const area = $('gen-result');
  if (!area) return;
  clear(area);
  const questions = (data && data.questions) || [];
  const card = el('div', { class: 'card' });
  card.appendChild(el('h2', { text: (data.generated || questions.length) + ' questions generated' }));
  if (data.provenance && data.provenance.skipped && data.provenance.skipped.length) {
    card.appendChild(el('p', {
      class: 'meta',
      text: 'Styles skipped (material could not support them): ' + data.provenance.skipped.join(', '),
    }));
  }
  area.appendChild(card);
  questions.slice(0, 12).forEach(function (q) { area.appendChild(questionCard(q, false)); });
}

/* ==========================================================================
 * Profile
 * ========================================================================== */

function bindProfileEvents() {
  const btn = $('load-profile');
  if (btn) btn.addEventListener('click', loadProfile);
}

async function loadProfile() {
  if (!LEARNER) { status('sign in first', 'err'); return; }
  const btn = $('load-profile');
  setBusy(btn, true, 'Loading…');
  try {
    const data = await api('/api/profile' + qs({ learner_id: LEARNER }));
    renderProfile(data);
    status('profile loaded', 'ok');
  } catch (e) {
    status(e.message || 'could not load profile', 'err');
  } finally {
    setBusy(btn, false);
  }
}

function renderProfile(data) {
  const area = $('profile-area');
  if (!area) return;
  clear(area);
  const profile = (data && data.profile) || {};
  const observations = profile.observations || [];

  const head = el('div', { class: 'card' });
  head.appendChild(el('h2', { text: 'Group Role' }));
  head.appendChild(el('div', { class: 'role', text: profile.social_role || 'Not yet measured' }));
  if (profile.social_role_basis && profile.social_role_basis.length) {
    head.appendChild(el('p', { class: 'meta', text: profile.social_role_basis.join(' · ') }));
  }
  area.appendChild(head);

  const obsCard = el('div', { class: 'card' });
  obsCard.appendChild(el('h2', { text: 'Observations' }));
  if (!observations.length) {
    obsCard.appendChild(el('p', {
      class: 'meta',
      text: 'No observations yet. These are behavioural findings, each carrying its own confidence label.',
    }));
  }
  observations.forEach(function (obs) {
    const box = el('div', { class: 'obs' });
    const row = el('div', { class: 'head' });
    row.appendChild(el('span', { class: 'label', text: obs.label || obs.construct || 'observation' }));
    const confidence = obs.confidence || 'low';
    row.appendChild(el('span', { class: 'conf-badge ' + confidence, text: confidence + ' confidence' }));
    box.appendChild(row);
    if (obs.statement) box.appendChild(el('div', { class: 'stmt', text: obs.statement }));
    if (obs.action) box.appendChild(el('div', { class: 'meta', text: 'What to do: ' + obs.action }));
    if (obs.caveat) box.appendChild(el('div', { class: 'meta', text: 'Caveat: ' + obs.caveat }));
    obsCard.appendChild(box);
  });
  area.appendChild(obsCard);

  if (profile.limits && profile.limits.length) {
    const limits = el('div', { class: 'card' });
    limits.appendChild(el('h2', { text: 'What this cannot tell you' }));
    profile.limits.forEach(function (limit) {
      limits.appendChild(el('div', { class: 'meta', text: '· ' + limit }));
    });
    area.appendChild(limits);
  }
}

/* ==========================================================================
 * Tutor
 * ========================================================================== */

function bindTutorEvents() {
  const begin = $('tutor-begin');
  if (begin) begin.addEventListener('click', beginTutor);
  const hint = $('tutor-hint');
  if (hint) hint.addEventListener('click', tutorHint);
  const question = $('tutor-question');
  if (question) question.addEventListener('click', tutorQuestion);

  buildTutorInput();
}

function buildTutorInput() {
  const chat = $('tutor-chat');
  if (!chat || $('chat-input')) return;
  const input = el('input', {
    attrs: { type: 'text', placeholder: 'Type your response…', id: 'chat-input', 'aria-label': 'Message the tutor' },
  });
  const send = el('button', { class: 'primary', text: 'Send', attrs: { type: 'button', id: 'chat-send' } });
  const row = el('div', { class: 'chat-input-area' }, [input, send]);

  send.addEventListener('click', tutorRespond);
  input.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') { e.preventDefault(); tutorRespond(); }
  });

  chat.parentNode.insertBefore(row, chat.nextSibling);
}

async function beginTutor() {
  const topicField = $('tutor-topic');
  const topic = topicField ? topicField.value.trim() : '';
  if (!topic) { status('enter a topic', 'err'); return; }
  if (!LEARNER) { status('sign in first', 'err'); return; }
  const modeField = $('tutor-mode');
  const mode = modeField ? modeField.value : 'practice';

  const btn = $('tutor-begin');
  setBusy(btn, true, 'Starting…');
  try {
    await api('/api/tutor/begin', {
      method: 'POST',
      body: JSON.stringify({ learner_id: LEARNER, topic: topic, mode: mode }),
    });
    TUTOR_STATE = { topic: topic, mode: mode };
    const chat = $('tutor-chat');
    if (chat) clear(chat);
    addTutorMessage('Let us work on ' + topic + '. What do you already know about it?');
    status('tutor ready', 'ok');
  } catch (e) {
    status(e.message || 'could not start tutor', 'err');
  } finally {
    setBusy(btn, false);
  }
}

async function tutorHint() {
  if (!TUTOR_STATE) { status('begin tutoring first', 'err'); return; }
  try {
    const data = await api('/api/tutor/hint', {
      method: 'POST',
      body: JSON.stringify({ learner_id: LEARNER }),
    });
    addTutorMessage(data.text || data.message || '');
  } catch (e) {
    status(e.message || 'hint unavailable', 'err');
  }
}

async function tutorQuestion() {
  if (!TUTOR_STATE) { status('begin tutoring first', 'err'); return; }
  const input = $('chat-input');
  let question = input ? input.value.trim() : '';
  if (!question) {
    /* Graceful fallback when the chat input is empty. */
    question = (window.prompt ? prompt('What would you like to ask the tutor?') : '') || '';
  }
  if (!question) return;
  if (input) input.value = '';
  addLearnerMessage(question);
  try {
    const data = await api('/api/tutor/question', {
      method: 'POST',
      body: JSON.stringify({ learner_id: LEARNER, question: question }),
    });
    addTutorMessage(data.text || data.message || '');
  } catch (e) {
    status(e.message || 'tutor could not answer', 'err');
  }
}

async function tutorRespond() {
  const input = $('chat-input');
  const text = input ? input.value.trim() : '';
  if (!text) return;
  if (!TUTOR_STATE) { status('begin tutoring first', 'err'); return; }
  input.value = '';
  addLearnerMessage(text);
  try {
    const data = await api('/api/tutor/respond', {
      method: 'POST',
      body: JSON.stringify({ learner_id: LEARNER, message: text }),
    });
    addTutorMessage(data.text || data.message || '');
  } catch (e) {
    status(e.message || 'tutor did not respond', 'err');
  }
}

function addTutorMessage(text) {
  const chat = $('tutor-chat');
  if (!chat) return;
  const msg = el('div', { class: 'chat-msg tutor' });
  msg.appendChild(el('div', { class: 'chat-meta', text: 'Tutor' }));
  msg.appendChild(el('div', { text: text }));
  chat.appendChild(msg);
  chat.scrollTop = chat.scrollHeight;
}

function addLearnerMessage(text) {
  const chat = $('tutor-chat');
  if (!chat) return;
  const msg = el('div', { class: 'chat-msg learner' });
  msg.appendChild(el('div', { class: 'chat-meta', text: 'You' }));
  msg.appendChild(el('div', { text: text }));
  chat.appendChild(msg);
  chat.scrollTop = chat.scrollHeight;
}

/* ==========================================================================
 * Integrations (MCP)
 * ========================================================================== */

function bindIntegrationsEvents() {
  const btn = $('write-mcp');
  if (btn) btn.addEventListener('click', async function () {
    setBusy(btn, true, 'Writing…');
    try {
      const data = await api('/api/mcp/config', { method: 'POST', body: JSON.stringify({}) });
      const out = $('mcp-out');
      if (out) out.textContent = 'Written to ' + data.written;
      status('mcp.json written', 'ok');
    } catch (e) {
      status(e.message || 'could not write mcp.json', 'err');
    } finally {
      setBusy(btn, false);
    }
  });
}

function renderMcpPlan() {
  const area = $('mcp-plan');
  if (!area) return;
  clear(area);
  api('/api/mcp/plan').then(function (plan) {
    const oauth = (plan && plan.oauth_required) || [];
    area.appendChild(el('h3', { text: 'Authorise these (OAuth only)' }));
    if (!oauth.length) {
      area.appendChild(el('div', { class: 'meta', text: 'No OAuth servers required.' }));
      return;
    }
    oauth.forEach(function (server) {
      const row = el('div', { class: 'row' });
      row.appendChild(el('span', { class: 'pill oauth', text: server.name }));
      row.appendChild(el('span', { style: { flex: '1', fontSize: 'var(--text-sm)' }, text: server.url }));
      area.appendChild(row);
    });
  }).catch(function () { /* integrations are optional */ });
}

/* ==========================================================================
 * Command palette
 * ========================================================================== */

const COMMANDS = [
  { id: 'start-session', label: 'Start Session', icon: 'S', shortcut: 'Ctrl+S', action: function () { switchView('study'); } },
  { id: 'add-source', label: 'Add Source', icon: 'M', shortcut: 'Ctrl+M', action: function () { switchView('sources'); } },
  { id: 'view-profile', label: 'View Profile', icon: 'P', shortcut: 'Ctrl+P', action: function () { switchView('profile'); } },
  { id: 'start-tutor', label: 'Start Tutor', icon: 'T', shortcut: 'Ctrl+T', action: function () { switchView('tutor'); } },
  { id: 'view-integrations', label: 'View Integrations', icon: 'I', shortcut: 'Ctrl+I', action: function () { switchView('integrations'); } },
  { id: 'go-dashboard', label: 'Go to Dashboard', icon: 'D', shortcut: 'Ctrl+D', action: function () { switchView('dashboard'); } },
];

const palette = { open: false, results: COMMANDS.slice(), index: 0 };

function openPalette() {
  if (palette.open) return;
  palette.open = true;
  palette.results = COMMANDS.slice();
  palette.index = 0;

  const overlay = el('div', { class: 'command-palette-overlay' });
  overlay.id = 'cmd-overlay';
  overlay.setAttribute('role', 'dialog');
  overlay.setAttribute('aria-modal', 'true');
  overlay.setAttribute('aria-label', 'Command palette');

  const box = el('div', { class: 'command-palette' });
  const input = el('input', {
    class: 'command-palette-input',
    attrs: { type: 'text', placeholder: 'Type a command…', autocomplete: 'off', 'aria-label': 'Search commands' },
  });
  const results = el('div', { class: 'command-palette-results' });
  results.id = 'cmd-results';
  results.setAttribute('role', 'listbox');

  box.appendChild(input);
  box.appendChild(results);
  overlay.appendChild(box);
  document.body.appendChild(overlay);

  overlay.addEventListener('click', function (e) { if (e.target === overlay) closePalette(); });
  input.addEventListener('input', function () {
    const query = input.value.toLowerCase();
    palette.results = COMMANDS.filter(function (c) { return c.label.toLowerCase().indexOf(query) !== -1; });
    palette.index = 0;
    renderPaletteResults();
  });
  input.addEventListener('keydown', function (e) {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      palette.index = Math.min(palette.index + 1, palette.results.length - 1);
      renderPaletteResults();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      palette.index = Math.max(palette.index - 1, 0);
      renderPaletteResults();
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const chosen = palette.results[palette.index];
      if (chosen) { closePalette(); chosen.action(); }
    } else if (e.key === 'Escape') {
      e.preventDefault();
      closePalette();
    }
  });

  renderPaletteResults();
  input.focus();
  requestAnimationFrame(function () { overlay.classList.add('show'); });
}

function renderPaletteResults() {
  const results = $('cmd-results');
  if (!results) return;
  clear(results);
  if (!palette.results.length) {
    results.appendChild(el('div', { class: 'command-palette-empty', text: 'No commands found' }));
    return;
  }
  palette.results.forEach(function (cmd, i) {
    const item = el('div', {
      class: 'command-palette-item' + (i === palette.index ? ' selected' : ''),
      attrs: { role: 'option', 'aria-selected': i === palette.index ? 'true' : 'false' },
    });
    item.appendChild(el('div', { class: 'cmd-icon', text: cmd.icon }));
    item.appendChild(el('div', { class: 'cmd-label', text: cmd.label }));
    item.appendChild(el('div', { class: 'cmd-shortcut', text: cmd.shortcut }));
    item.addEventListener('click', function () { closePalette(); cmd.action(); });
    item.addEventListener('mouseenter', function () { palette.index = i; renderPaletteResults(); });
    results.appendChild(item);
  });
}

function closePalette() {
  palette.open = false;
  const overlay = $('cmd-overlay');
  if (!overlay) return;
  overlay.classList.remove('show');
  setTimeout(function () { overlay.remove(); }, 200);
}

function bindPalette() {
  if (BOUND.palette) return;
  BOUND.palette = true;
  document.addEventListener('keydown', function (e) {
    if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) {
      e.preventDefault();
      if (palette.open) closePalette(); else openPalette();
    } else if (e.key === 'Escape' && palette.open) {
      closePalette();
    }
  });
}

/* ==========================================================================
 * Settings
 * ========================================================================== */

function initSettings() {
  if (BOUND.settings) return;
  BOUND.settings = true;

  const fields = ['pref-session-min', 'pref-days-week', 'pref-success-rate', 'pref-difficulty'];

  /* Load persisted preferences. */
  let prefs = {};
  try { prefs = JSON.parse(localGet(STORAGE.PREFS) || '{}') || {}; } catch (e) { prefs = {}; }
  if (prefs.session_min !== undefined && $('pref-session-min')) $('pref-session-min').value = prefs.session_min;
  if (prefs.days_week !== undefined && $('pref-days-week')) $('pref-days-week').value = prefs.days_week;
  if (prefs.success_rate !== undefined && $('pref-success-rate')) $('pref-success-rate').value = prefs.success_rate;
  if (prefs.difficulty !== undefined && $('pref-difficulty')) $('pref-difficulty').value = prefs.difficulty;

  fields.forEach(function (id) {
    const field = $(id);
    if (!field) return;
    field.addEventListener('change', function () {
      const next = {
        session_min: $('pref-session-min') ? Number($('pref-session-min').value) : undefined,
        days_week: $('pref-days-week') ? Number($('pref-days-week').value) : undefined,
        success_rate: $('pref-success-rate') ? Number($('pref-success-rate').value) : undefined,
        difficulty: $('pref-difficulty') ? $('pref-difficulty').value : undefined,
      };
      localSet(STORAGE.PREFS, JSON.stringify(next));
      status('preferences saved', 'ok');
    });
  });

  const exportBtn = $('export-data');
  if (exportBtn) exportBtn.addEventListener('click', exportData);

  const importBtn = $('import-data');
  const importFile = $('import-file');
  if (importBtn && importFile) {
    importBtn.addEventListener('click', function () { importFile.click(); });
    importFile.addEventListener('change', importData);
  }

  const eraseBtn = $('erase-data');
  if (eraseBtn) eraseBtn.addEventListener('click', eraseData);
}

async function exportData() {
  if (!LEARNER) { status('sign in first', 'err'); return; }
  try {
    const data = await api('/api/export' + qs({ learner_id: LEARNER }));
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = el('a', { attrs: { href: url, download: 'cortexforge-export.json' } });
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
    status('data exported', 'ok');
  } catch (e) {
    status(e.message || 'could not export data', 'err');
  }
}

async function importData(e) {
  const file = e && e.target && e.target.files ? e.target.files[0] : null;
  if (!file) return;
  if (e.target) e.target.value = '';
  if (!LEARNER) { status('sign in first', 'err'); return; }

  let parsed;
  try {
    parsed = JSON.parse(await file.text());
  } catch (err) {
    status('invalid JSON file', 'err');
    return;
  }
  if (!parsed || typeof parsed !== 'object' || !Array.isArray(parsed.sources)) {
    status('this does not look like a CortexForge export', 'err');
    return;
  }

  /* The only writable import path is source ingestion: an export that carries
   * source text can be restored; an export without it is reported honestly. */
  const sources = parsed.sources;
  let restored = 0;
  let skipped = 0;
  for (const source of sources) {
    if (!source || typeof source.text !== 'string' || !source.text.trim()) { skipped++; continue; }
    try {
      await api('/api/source', {
        method: 'POST',
        body: JSON.stringify({ learner_id: LEARNER, title: source.title || '', text: source.text }),
      });
      restored++;
    } catch (err) { skipped++; }
  }
  await refreshSources();
  if (restored) {
    status('imported ' + restored + ' source' + (restored === 1 ? '' : 's')
      + (skipped ? ' (' + skipped + ' skipped — no text in file)' : ''), 'ok');
  } else {
    status('nothing to restore — exports omit source text', 'err');
  }
}

async function eraseData() {
  if (!LEARNER) { status('sign in first', 'err'); return; }
  const confirmation = window.prompt
    ? prompt('This permanently deletes all your learning data. Type ERASE to confirm:')
    : '';
  if (confirmation !== 'ERASE') { status('erase cancelled'); return; }
  try {
    await api('/api/erase', {
      method: 'POST',
      body: JSON.stringify({ learner_id: LEARNER, confirm: 'ERASE' }),
    });
    SESSION = [];
    SESSION_RESULTS = [];
    await loadDashboard();
    status('data erased', 'ok');
  } catch (e) {
    status(e.message || 'could not erase data', 'err');
  }
}

/* ==========================================================================
 * Onboarding
 * ========================================================================== */

async function showOnboardingView() {
  const auth = $('view-auth');
  const main = $('view-main');
  const onboarding = $('view-onboarding');
  if (auth) auth.classList.remove('active');
  if (main) main.classList.remove('active');
  if (onboarding) onboarding.classList.add('active');
  await startOnboarding();
}

async function startOnboarding() {
  if (!LEARNER) { status('sign in first', 'err'); return; }
  try {
    await api('/api/onboarding/start', {
      method: 'POST',
      body: JSON.stringify({ learner_id: LEARNER }),
    });
    status('onboarding started', 'ok');
    await renderNextProbe();
  } catch (e) {
    status(e.message || 'could not start onboarding', 'err');
  }
}

async function renderNextProbe() {
  const area = $('probe-area');
  if (!area) return;
  clear(area);

  let data;
  try {
    data = await api('/api/onboarding/next' + qs({ learner_id: LEARNER }));
  } catch (e) {
    status(e.message || 'could not load next step', 'err');
    return;
  }

  if (!data.probe) { await finishOnboarding(); return; }

  const probe = data.probe;
  const progress = data.progress || { completed: 0, total: 1 };
  const total = Math.max(1, Number(progress.total) || 1);
  const completed = Number(progress.completed) || 0;
  const pct = Math.round((completed / total) * 100);

  const fill = $('onboarding-progress-fill');
  if (fill) fill.style.width = pct + '%';
  const text = $('onboarding-progress-text');
  if (text) text.textContent = 'Step ' + Math.min(completed + 1, total) + ' of ' + total;

  const card = el('div', { class: 'card' });
  card.appendChild(el('h2', { text: probe.name || 'Next step' }));
  if (probe.purpose) card.appendChild(el('p', { class: 'lede', text: probe.purpose }));
  if (probe.question) card.appendChild(el('p', { text: probe.question }));

  const inputWrap = el('div', { class: 'field' });
  /* getAnswer is populated by the control that this probe uses. */
  let getAnswer = function () { return null; };

  if (probe.kind === 'interview' && probe.options && probe.options.length) {
    const select = el('select');
    probe.options.forEach(function (opt) {
      select.appendChild(el('option', { text: opt, attrs: { value: opt } }));
    });
    inputWrap.appendChild(select);
    getAnswer = function () { return select.value; };
  } else if (probe.kind === 'interview' || probe.kind === 'source') {
    const ta = el('textarea', { attrs: { rows: '4', placeholder: 'Type your answer…' } });
    inputWrap.appendChild(ta);
    getAnswer = function () { return ta.value; };
  } else if (probe.kind === 'calibration') {
    inputWrap.appendChild(el('p', { class: 'lede', text: 'Answer each on a 0–4 scale.' }));
    const dims = [
      'holding a thought', 'finding a word', 'following a conversation',
      'remembering why you walked into a room', 'reading the same paragraph twice',
    ];
    const inputs = [];
    dims.forEach(function (dim) {
      const row = el('div', { class: 'row' });
      row.appendChild(el('span', { style: { flex: '1' }, text: dim }));
      const num = el('input', { attrs: { type: 'number', min: '0', max: '4', value: '0' } });
      inputs.push([dim, num]);
      row.appendChild(num);
      inputWrap.appendChild(row);
    });
    getAnswer = function () {
      const out = {};
      inputs.forEach(function (pair) { out[pair[0]] = Number(pair[1].value) || 0; });
      return out;
    };
  } else if (probe.kind === 'task') {
    inputWrap.appendChild(el('p', { class: 'lede', text: 'This task runs in your browser. Click "Start task" to begin.' }));
    const startBtn = el('button', { class: 'primary', text: 'Start task', attrs: { type: 'button' } });
    inputWrap.appendChild(startBtn);
    let trials = null;
    startBtn.addEventListener('click', async function () {
      startBtn.disabled = true;
      try {
        if (typeof TaskEngine !== 'undefined' && TaskEngine.has(probe.task_id)) {
          trials = await TaskEngine.run(probe.task_id, inputWrap, { trials: probe.trials || 40 });
          inputWrap.appendChild(el('p', { class: 'lede', text: 'Task complete. ' + (trials ? trials.length : 0) + ' trials recorded.' }));
        } else {
          inputWrap.appendChild(el('p', { class: 'lede', text: 'Task engine unavailable in this browser.' }));
        }
      } catch (err) {
        inputWrap.appendChild(el('p', { class: 'lede', text: 'Task error: ' + err.message }));
        startBtn.disabled = false;
      }
    });
    getAnswer = function () { return trials ? { trials: trials } : null; };
  }

  card.appendChild(inputWrap);

  const row = el('div', { class: 'row' });
  const nextBtn = el('button', { class: 'primary', text: 'Continue', attrs: { type: 'button' } });
  const skipBtn = el('button', { text: 'Skip this', attrs: { type: 'button' } });
  row.appendChild(nextBtn);
  row.appendChild(skipBtn);
  card.appendChild(row);
  area.appendChild(card);

  async function record(answer) {
    await api('/api/onboarding/record', {
      method: 'POST',
      body: JSON.stringify({ learner_id: LEARNER, probe_id: probe.probe_id, answer: answer }),
    });
    await renderNextProbe();
  }

  nextBtn.addEventListener('click', async function () {
    nextBtn.disabled = true;
    try { await record(getAnswer()); }
    catch (e) { status(e.message || 'could not record answer', 'err'); nextBtn.disabled = false; }
  });

  skipBtn.addEventListener('click', async function () {
    skipBtn.disabled = true;
    try { await record(null); }
    catch (e) { status(e.message || 'could not skip', 'err'); skipBtn.disabled = false; }
  });
}

async function finishOnboarding() {
  try {
    const data = await api('/api/onboarding/finish', {
      method: 'POST',
      body: JSON.stringify({ learner_id: LEARNER }),
    });
    const area = $('contract-area');
    if (area) {
      clear(area);
      const card = el('div', { class: 'card' });
      card.appendChild(el('h2', { text: 'Your learning contract' }));
      card.appendChild(el('pre', { class: 'code', text: data.summary || '' }));
      area.appendChild(card);
    }
    status('onboarding complete', 'ok');
    setTimeout(async function () {
      const onboarding = $('view-onboarding');
      if (onboarding) onboarding.classList.remove('active');
      await enterApp();
    }, 2500);
  } catch (e) {
    status(e.message || 'could not finish onboarding', 'err');
  }
}

/* ==========================================================================
 * Bootstrap
 * ========================================================================== */

async function init() {
  try {
    showLoader();
    installStyles();
    setLoaderProgress(10);

    initTheme();
    bindAuthEvents();
    setLoaderProgress(25);

    /* Vendored, same-origin libraries (GSAP, Lenis). Optional. */
    await loadVendorLibs();
    setLoaderProgress(50);

    /* Signature scientific scene. Failure degrades to a CSS gradient. */
    BG = initBackground();
    if (!BG.ok) { try { document.body.classList.add('no-webgl'); } catch (e) { /* ignore */ } }
    if (BG && BG.ok) BG.setTheme(document.documentElement.getAttribute('data-theme') || 'dark');
    setLoaderProgress(75);

    initMicrointeractions();
    initSettings();
    await boot();
    setLoaderProgress(100);
  } catch (e) {
    status('startup error', 'err');
  } finally {
    setTimeout(hideLoader, 400);
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', function () { init(); });
} else {
  init();
}

/* Testability / shell wiring surface. */
window.CortexForge = {
  state: function () {
    return {
      TOKEN: TOKEN, SESSION_TOKEN: SESSION_TOKEN, ACCOUNT: ACCOUNT, LEARNER: LEARNER,
      MANIFEST: MANIFEST, SESSION: SESSION, SESSION_INDEX: SESSION_INDEX,
      SESSION_RESULTS: SESSION_RESULTS, TUTOR_STATE: TUTOR_STATE,
      SELECTED_STYLES: Array.from(SELECTED_STYLES),
    };
  },
  api: api,
  el: el,
  status: status,
  switchView: switchView,
  switchAuthTab: switchAuthTab,
  doLogin: doLogin,
  doRegister: doRegister,
  doReset: doReset,
  doLogout: doLogout,
  boot: boot,
  enterApp: enterApp,
  checkOnboarding: checkOnboarding,
  loadDashboard: loadDashboard,
  setRing: setRing,
  renderMasteryMap: renderMasteryMap,
  loadSession: loadSession,
  questionCard: questionCard,
  showBottomBanner: showBottomBanner,
  renderSummary: renderSummary,
  renderStageIndicators: renderStageIndicators,
  addSource: addSource,
  refreshSources: refreshSources,
  renderStylePicker: renderStylePicker,
  generateQuestions: generateQuestions,
  renderGenerated: renderGenerated,
  loadProfile: loadProfile,
  beginTutor: beginTutor,
  tutorHint: tutorHint,
  tutorQuestion: tutorQuestion,
  tutorRespond: tutorRespond,
  addTutorMessage: addTutorMessage,
  addLearnerMessage: addLearnerMessage,
  initTheme: initTheme,
  initSettings: initSettings,
  openPalette: openPalette,
  closePalette: closePalette,
  renderPaletteResults: renderPaletteResults,
  startOnboarding: startOnboarding,
  renderNextProbe: renderNextProbe,
  finishOnboarding: finishOnboarding,
  /* presentation layer */
  installStyles: installStyles,
  showLoader: showLoader,
  hideLoader: hideLoader,
  setLoaderProgress: setLoaderProgress,
  loadVendorLibs: loadVendorLibs,
  animTo: animTo,
  libs: function () { return { gsap: !!LIBS.gsap, lenis: !!LIBS.lenis }; },
  /* scientific scene */
  initBackground: initBackground,
  setBackgroundMode: setBackgroundMode,
  setSceneIntensity: setSceneIntensity,
  background: function () { return BG; },
  molecules: { caffeine: molCaffeine, glucose: molGlucose, benzene: molBenzene, water: molWater },
  equations: function () { return EQUATIONS.slice(); },
};
