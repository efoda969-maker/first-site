/* ALL STAR BURGERS
   Scroll-driven image sequence + synced copy, menu filters and a small cart. */
(() => {
  'use strict';

  // Número do WhatsApp da loja (DDI + DDD + número, só dígitos). Vazio = o
  // WhatsApp abre para o cliente escolher o contato.
  const WHATSAPP_NUMBER = '';

  const SEQ = 'assets/seq/';
  const doc = document.documentElement;
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
  const smooth = (t) => { t = clamp(t); return t * t * (3 - 2 * t); };
  const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ------------------------------------------------------------ elements */
  const scrolly = $('#experiencia');
  const stage = $('#stage');
  const canvas = $('#seq');
  const ctx = canvas.getContext('2d', { alpha: false });
  const shade = $('#shade');
  const labelsEl = $('#labels');
  const steps = $$('.step', stage).map((el) => ({
    el, a: parseFloat(el.dataset.in), b: parseFloat(el.dataset.out), visible: null,
  }));
  const progressItems = $$('#progress li');
  const progressEl = $('#progress');
  const stageBar = $('#stageBar');
  progressItems.forEach((li) => { li.innerHTML = `<span>${li.textContent}</span>`; });

  /* ------------------------------------------------------------ state */
  let meta = null;
  let sets = {};          // name -> { frames: Image[], loaded: bool[], count, info }
  let activeSet = null;
  let view = { w: 0, h: 0, dpr: 1 };
  let targetP = 0;
  let currentP = 0;
  let rafId = 0;
  let lastFrameDrawn = -1;
  let labelNodes = [];

  /* ------------------------------------------------------------ helpers */
  const hexToRgb = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const rgba = (rgb, a) => `rgba(${rgb[0]},${rgb[1]},${rgb[2]},${a})`;
  const lum = (rgb) => (0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]) / 255;

  function chooseSet() {
    return innerWidth / innerHeight >= 1 ? 'desktop' : 'mobile';
  }

  function scrollProgress() {
    const r = scrolly.getBoundingClientRect();
    const total = scrolly.offsetHeight - stage.offsetHeight;
    return total > 0 ? clamp(-r.top / total) : 0;
  }

  /* ------------------------------------------------------------ loading */
  function loadOrder(n) {
    // coarse-to-fine so the whole story is scrubbable early
    const order = [];
    const seen = new Set();
    for (const stride of [16, 8, 4, 2, 1]) {
      for (let i = 0; i < n; i += stride) if (!seen.has(i)) { seen.add(i); order.push(i); }
    }
    if (!seen.has(n - 1)) order.splice(1, 0, n - 1);
    return order;
  }

  function loadSet(name, onProgress) {
    if (sets[name]) return sets[name].promise;
    const info = meta[name];
    const n = meta.frames;
    const set = { name, info, frames: new Array(n), loaded: new Array(n).fill(false), count: 0 };
    sets[name] = set;
    const order = loadOrder(n);
    let next = 0;
    set.promise = new Promise((resolve) => {
      const worker = async () => {
        while (next < order.length) {
          const i = order[next++];
          const img = new Image();
          img.decoding = 'async';
          // ?v= changes on every asset build, so the frames can be cached forever
          img.src = `${SEQ}${name}/${String(i).padStart(4, '0')}.${info.ext}?v=${meta.version || 1}`;
          try {
            if (img.decode) await img.decode(); else await new Promise((r, j) => { img.onload = r; img.onerror = j; });
            set.frames[i] = img;
            set.loaded[i] = true;
          } catch (e) { /* skip broken frame, nearest one is used instead */ }
          set.count++;
          onProgress && onProgress(set.count / n, set);
          if (set === activeSet) requestDraw(true);
        }
      };
      const lanes = Array.from({ length: 6 }, worker);
      Promise.all(lanes).then(() => resolve(set));
    });
    return set.promise;
  }

  function nearest(set, i) {
    if (!set) return -1;
    if (set.loaded[i]) return i;
    for (let d = 1; d < meta.frames; d++) {
      if (i - d >= 0 && set.loaded[i - d]) return i - d;
      if (i + d < meta.frames && set.loaded[i + d]) return i + d;
    }
    return -1;
  }

  /* ------------------------------------------------------------ layout */
  function resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const w = stage.clientWidth;
    const h = stage.clientHeight;
    view = { w, h, dpr };
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    if (meta) {
      const want = chooseSet();
      if (!activeSet || activeSet.name !== want) {
        loadSet(want);
        activeSet = sets[want];
      }
    }
    if (activeSet) {
      const e = activeSet.info.edges;
      doc.style.setProperty('--seq-end', e[e.length - 1][3]);
    }
    lastFrameDrawn = -1;
    requestDraw(true);
  }

  // On landscape screens the product slides away from the side the copy is on.
  // [progress, shift as a fraction of the stage width]; + = product to the right.
  const SHIFT = [[0, 0.12], [0.25, 0.12], [0.31, 0.02], [0.45, 0.02], [0.5, 0.16], [0.64, 0.16],
    [0.7, -0.12], [0.88, -0.12], [0.93, 0.12], [1, 0.12]];
  function shiftAt(p) {
    for (let i = 0; i < SHIFT.length - 1; i++) {
      const [a, va] = SHIFT[i];
      const [b, vb] = SHIFT[i + 1];
      if (p >= a && p <= b) return va + (vb - va) * smooth((p - a) / (b - a));
    }
    return SHIFT[SHIFT.length - 1][1];
  }

  // How a frame of a given set maps onto the stage (CSS px).
  function fit(set) {
    const { w: fw, h: fh, safe } = set.info;
    const { w, h } = view;
    let s = Math.max(w / fw, h / fh);                 // cover
    // never crop past the safe zone that holds the products
    s = Math.min(s, w / (fw * safe[0]), h / (fh * safe[1]));
    const dw = fw * s;
    const dh = fh * s;
    const shift = set.name === 'desktop' && w > 640 ? shiftAt(currentP) * w : 0;
    return { s, dx: (w - dw) / 2 + shift, dy: (h - dh) / 2, dw, dh };
  }

  /* ------------------------------------------------------------ drawing */
  function requestDraw(force) {
    if (force) lastFrameDrawn = -1;
    if (!rafId) rafId = requestAnimationFrame(tick);
  }

  let lastT = 0;
  function tick(t) {
    rafId = 0;
    const dt = lastT ? Math.min(0.1, (t - lastT) / 1000) : 1 / 60;
    lastT = t;
    targetP = scrollProgress();
    const k = reduceMotion ? 1 : 1 - Math.exp(-dt * 9);
    currentP += (targetP - currentP) * k;
    if (Math.abs(targetP - currentP) < 0.00005) currentP = targetP;
    render(currentP);
    if (currentP !== targetP) rafId = requestAnimationFrame(tick);
    else lastT = 0;
  }

  function render(p) {
    if (!meta || !activeSet) return;
    const set = activeSet;
    const n = meta.frames;
    const fpos = p * (n - 1);
    const key = Math.round(fpos * 100);
    if (key !== lastFrameDrawn) {
      lastFrameDrawn = key;
      drawFrame(set, fpos);
    }
    updateCopy(p);
    updateLabels(set, fpos, p);
  }

  function drawFrame(set, fpos) {
    const n = meta.frames;
    const i0 = Math.floor(fpos);
    const i1 = Math.min(n - 1, i0 + 1);
    const a = reduceMotion ? 0 : fpos - i0;
    const j0 = nearest(set, i0);
    if (j0 < 0) return;
    const j1 = nearest(set, i1);
    const { dpr } = view;
    const f = fit(set);
    const edge = set.info.edges[Math.round(fpos)] || set.info.edges[j0];
    const avg = hexToRgb(edge[4]);

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.globalAlpha = 1;
    ctx.fillStyle = edge[4];
    ctx.fillRect(0, 0, view.w, view.h);
    ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(set.frames[j0], f.dx, f.dy, f.dw, f.dh);
    if (j1 !== j0 && a > 0.02) {
      ctx.globalAlpha = a;
      ctx.drawImage(set.frames[j1], f.dx, f.dy, f.dw, f.dh);
      ctx.globalAlpha = 1;
    }
    // feather the image into the fill colour when it does not cover the stage
    const feather = (x0, y0, x1, y1, col, rx, ry, rw, rh) => {
      const g = ctx.createLinearGradient(x0, y0, x1, y1);
      g.addColorStop(0, rgba(col, 1));
      g.addColorStop(1, rgba(col, 0));
      ctx.fillStyle = g;
      ctx.fillRect(rx, ry, rw, rh);
    };
    const fw = f.dw * 0.1;
    if (f.dx > 0.5) {
      const L = hexToRgb(edge[0]);
      ctx.fillStyle = edge[0]; ctx.fillRect(0, 0, f.dx + 1, view.h);
      feather(f.dx, 0, f.dx + fw, 0, L, f.dx, 0, fw, view.h);
    }
    if (f.dx + f.dw < view.w - 0.5) {
      const R = hexToRgb(edge[1]);
      ctx.fillStyle = edge[1]; ctx.fillRect(f.dx + f.dw - 1, 0, view.w, view.h);
      feather(f.dx + f.dw, 0, f.dx + f.dw - fw, 0, R, f.dx + f.dw - fw, 0, fw, view.h);
    }
    if (f.dy > 0.5) {
      const T = hexToRgb(edge[2]); const B = hexToRgb(edge[3]);
      ctx.fillStyle = edge[2]; ctx.fillRect(0, 0, view.w, f.dy + 1);
      ctx.fillStyle = edge[3]; ctx.fillRect(0, f.dy + f.dh - 1, view.w, view.h);
      const fh = f.dh * 0.08;
      feather(0, f.dy, 0, f.dy + fh, T, 0, f.dy, view.w, fh);
      feather(0, f.dy + f.dh, 0, f.dy + f.dh - fh, B, 0, f.dy + f.dh - fh, view.w, fh);
    }

    // background + legibility shade follow the frame
    const bg = edge[4];
    if (stage.style.getPropertyValue('--seq-bg') !== bg) {
      scrolly.style.setProperty('--seq-bg', bg);
      stage.style.setProperty('--seq-bg', bg);
    }
    // legibility scrim on the copy side (dark during the intro, cream later)
    const portrait = set.name === 'mobile';
    const p = fpos / (meta.frames - 1);
    // intro and kitchen are dark scenes: dark scrim; cream scenes: cream scrim
    const sc = p < 0.15 || p > 0.655 ? [8, 7, 6] : avg;
    const sh = shiftAt(p);
    // copy colour follows what is actually behind it (scrim over the frame edge)
    const sideEdge = hexToRgb(portrait ? edge[2] : (sh >= 0 ? edge[0] : edge[1]));
    const behind = sideEdge.map((c, i) => c * 0.25 + sc[i] * 0.75);
    stage.classList.toggle('on-dark', lum(behind) < 0.5);
    if (portrait) {
      shade.style.background = `linear-gradient(180deg, ${rgba(sc, 0.88)} 0%, ${rgba(sc, 0)} 27%, ${rgba(sc, 0)} 68%, ${rgba(sc, 0.92)} 100%)`;
    } else {
      const k = Math.min(1, Math.abs(sh) / 0.12);
      const dir = sh >= 0 ? 90 : 270;
      shade.style.background = `linear-gradient(${dir}deg, ${rgba(sc, 0.82 * k)} 0%, ${rgba(sc, 0.5 * k)} 24%, ${rgba(sc, 0)} 48%)`;
    }
    progressEl.style.setProperty('--prog-ink', lum(avg) > 0.5 ? '#0d0b0a' : '#f3e9d2');
  }

  /* ------------------------------------------------------------ synced copy */
  const FADE = 0.028;
  function updateCopy(p) {
    for (const s of steps) {
      const tin = s.a < 0 ? 1 : smooth((p - s.a) / FADE);
      const tout = smooth((s.b - p) / FADE);
      const o = Math.min(tin, tout);
      const vis = o > 0.001;
      if (vis !== s.visible) {
        s.el.style.visibility = vis ? 'visible' : 'hidden';
        s.el.setAttribute('aria-hidden', String(!vis));
        s.visible = vis;
      }
      if (!vis) continue;
      const y = (1 - tin) * 48 - (1 - tout) * 48;
      s.el.style.opacity = o.toFixed(3);
      const base = s.el.classList.contains('step--corner') || innerWidth / innerHeight < 1 ? '' : 'translateY(-50%) ';
      s.el.style.transform = `${base}translate3d(0, ${y.toFixed(1)}px, 0)`;
    }
    let on = 0;
    progressItems.forEach((li, i) => { if (p >= parseFloat(li.dataset.at) - 0.001) on = i; });
    progressItems.forEach((li, i) => li.classList.toggle('is-on', i === on));
    progressEl.classList.toggle('is-hidden', p > 0.995);
    stageBar.style.transform = `scaleX(${p.toFixed(4)})`;
  }

  /* ------------------------------------------------------------ ingredient labels */
  const LABEL_COPY = {
    crown: ['Pão brioche', 'Tostado na manteiga'],
    sauce: ['Molho da casa', 'Receita secreta'],
    onions: ['Cebola caramelizada', 'Na chapa, sem pressa'],
    pattycheese: ['Smash + cheddar', '2 × 90g, crosta crocante'],
    heel: ['Pão tostado', 'Base que segura o jogo'],
  };
  function buildLabels() {
    labelsEl.innerHTML = '';
    labelNodes = Object.keys(LABEL_COPY).map((key) => {
      const el = document.createElement('div');
      el.className = 'label';
      el.innerHTML = `<i class="label__dot"></i><i class="label__line"></i><span class="label__txt"><b>${LABEL_COPY[key][0]}</b><small>${LABEL_COPY[key][1]}</small></span>`;
      labelsEl.appendChild(el);
      return { key, el, side: 0 };
    });
  }

  function anchorsAt(fi) {
    const L = meta.labels;
    return L[fi] || null;
  }

  function updateLabels(set, fpos, p) {
    const o = Math.min(smooth((p - 0.315) / 0.025), smooth((0.435 - p) / 0.025));
    labelsEl.style.opacity = o.toFixed(3);
    if (o <= 0.001) return;
    const i0 = Math.floor(fpos);
    const a0 = anchorsAt(i0);
    const a1 = anchorsAt(Math.min(meta.frames - 1, i0 + 1)) || a0;
    if (!a0) return;
    const t = fpos - i0;
    const f = fit(set);
    const S = meta.size;
    const crop = set.info.crop;
    const k = set.info.w / crop[2];
    const toScreen = (nx, ny) => [
      f.dx + (nx * S - crop[0]) * k * f.s,
      f.dy + (ny * S - crop[1]) * k * f.s,
    ];
    const portrait = set.name === 'mobile';
    for (const node of labelNodes) {
      const A = a0.find((q) => q.key === node.key);
      const B = a1.find((q) => q.key === node.key) || A;
      if (!A) continue;
      const ex = A.ex + (B.ex - A.ex) * t;
      const ey = A.ey + (B.ey - A.ey) * t;
      const [sx, sy] = toScreen(ex, ey);
      const side = A.side;
      if (node.side !== side) {
        node.el.classList.toggle('label--left', side < 0);
        node.side = side;
      }
      // keep the line length so the text clears the layer and stays on screen
      const len = portrait ? Math.max(14, Math.min(40, view.w * 0.06)) : Math.max(40, Math.min(110, view.w * 0.06));
      node.el.style.setProperty('--len', `${len}px`);
      const wEl = node.el.offsetWidth;
      const x = clamp(side > 0 ? sx : sx - wEl, 6, view.w - wEl - 6);
      node.el.style.transform = `translate3d(${x.toFixed(1)}px, ${(sy - node.el.offsetHeight / 2).toFixed(1)}px, 0)`;
    }
  }

  /* ------------------------------------------------------------ boot sequence */
  const loader = $('#loader');
  const loaderBar = $('#loaderBar');
  const loaderPct = $('#loaderPct');
  let entered = false;

  function enter() {
    if (entered) return;
    entered = true;
    loader.classList.add('is-done');
    doc.classList.remove('is-loading');
    requestDraw(true);
  }

  async function boot() {
    doc.classList.add('is-loading');
    buildLabels();
    try {
      meta = await (await fetch(`${SEQ}meta.json`, { cache: 'no-cache' })).json();
    } catch (e) {
      enter();
      return;
    }
    const want = chooseSet();
    const started = performance.now();
    const progressCb = (r) => {
      const pct = Math.round(r * 100);
      loaderBar.style.width = `${pct}%`;
      loaderPct.textContent = pct;
      // all frames ready -> enter; slow network -> enter once half (coarse to fine) is in
      if (r >= 1 || (r >= 0.5 && performance.now() - started > 9000)) enter();
    };
    loadSet(want, progressCb);
    const set = sets[want];
    resize();
    set.promise.then(() => progressCb(1));
    setTimeout(() => { if (!entered && set.count / meta.frames >= 0.25) enter(); }, 20000);
  }

  addEventListener('scroll', () => requestDraw(false), { passive: true });
  addEventListener('resize', () => { resize(); });
  boot();

  /* ------------------------------------------------------------ header */
  const menuToggle = $('#menuToggle');
  const nav = $('#nav');
  menuToggle.addEventListener('click', () => {
    const open = menuToggle.getAttribute('aria-expanded') !== 'true';
    menuToggle.setAttribute('aria-expanded', String(open));
    nav.classList.toggle('is-open', open);
  });
  $$('a', nav).forEach((a) => a.addEventListener('click', () => {
    menuToggle.setAttribute('aria-expanded', 'false');
    nav.classList.remove('is-open');
  }));
  const navLinks = $$('a', nav);
  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (!e.isIntersecting) return;
      navLinks.forEach((a) => a.classList.toggle('is-active', a.getAttribute('href') === `#${e.target.id}`));
    });
  }, { rootMargin: '-45% 0px -50% 0px' });
  ['experiencia', 'cardapio', 'sobre', 'contato'].forEach((id) => { const el = document.getElementById(id); if (el) io.observe(el); });

  /* ------------------------------------------------------------ menu tabs */
  const tabs = $$('.tabs button');
  const cards = $$('#menuGrid .card');
  tabs.forEach((tab) => tab.addEventListener('click', () => {
    tabs.forEach((t) => t.setAttribute('aria-pressed', String(t === tab)));
    const f = tab.dataset.filter;
    cards.forEach((c) => { c.hidden = !(f === 'all' || c.dataset.cat === f); });
  }));

  /* ------------------------------------------------------------ cart */
  const CATALOG = {
    box: { name: 'Combo Dia de Jogo', price: 69.9 },
    enterrada: { name: 'Enterrada', price: 38.9 },
    lance: { name: 'Lance Livre', price: 29.9 },
    bandeja: { name: 'Bandeja', price: 42.9 },
    gancho: { name: 'Gancho', price: 34.9 },
    fries: { name: 'Batata Tempo Técnico', price: 16.9 },
    sauces: { name: 'Molhos do Garrafão', price: 9.9 },
    shake: { name: 'Shake Prorrogação', price: 22.9 },
  };
  const brl = (v) => v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
  let cart = {};
  try { cart = JSON.parse(localStorage.getItem('asb-cart') || '{}') || {}; } catch (e) { cart = {}; }
  const drawer = $('#drawer');
  const cartList = $('#cartList');
  const cartEmpty = $('#cartEmpty');
  const cartTotal = $('#cartTotal');
  const cartCount = $('#cartCount');
  const cartBtn = $('#cartOpen');
  const checkout = $('#checkout');
  const toast = $('#toast');
  let toastTimer = 0;

  function save() { try { localStorage.setItem('asb-cart', JSON.stringify(cart)); } catch (e) { /* private mode */ } }

  function renderCart() {
    const ids = Object.keys(cart).filter((id) => CATALOG[id] && cart[id] > 0);
    let total = 0;
    let count = 0;
    cartList.innerHTML = ids.map((id) => {
      const it = CATALOG[id];
      const q = cart[id];
      total += it.price * q;
      count += q;
      return `<li><span class="n">${it.name}</span><span class="p">${brl(it.price * q)}</span>
        <span class="qty"><button type="button" data-dec="${id}" aria-label="Remover um ${it.name}">−</button><output>${q}</output><button type="button" data-inc="${id}" aria-label="Adicionar um ${it.name}">+</button></span></li>`;
    }).join('');
    cartEmpty.hidden = ids.length > 0;
    cartTotal.textContent = brl(total);
    cartCount.textContent = count;
    cartCount.classList.toggle('has-items', count > 0);
    const lines = ids.map((id) => `${cart[id]}x ${CATALOG[id].name} — ${brl(CATALOG[id].price * cart[id])}`);
    const msg = `Olá, ALL STAR BURGERS! Quero fazer um pedido:\n\n${lines.join('\n')}\n\nTotal: ${brl(total)}`;
    checkout.href = `https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent(msg)}`;
    checkout.setAttribute('aria-disabled', String(ids.length === 0));
  }

  let lastFocus = null;
  function openCart(open) {
    drawer.classList.toggle('is-open', open);
    drawer.setAttribute('aria-hidden', String(!open));
    drawer.inert = !open;
    if (open) {
      toast.classList.remove('is-on');
      lastFocus = document.activeElement;
      $('.drawer__close', drawer).focus();
    }
    else if (lastFocus) { lastFocus.focus(); lastFocus = null; }
  }
  drawer.inert = true;

  function add(id) {
    if (!CATALOG[id]) return;
    cart[id] = (cart[id] || 0) + 1;
    save();
    renderCart();
    cartBtn.classList.remove('bump');
    void cartBtn.offsetWidth;
    cartBtn.classList.add('bump');
    toast.textContent = `${CATALOG[id].name} na sacola`;
    toast.classList.add('is-on');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('is-on'), 2200);
  }

  document.addEventListener('click', (e) => {
    const addBtn = e.target.closest('[data-add]');
    if (addBtn) { add(addBtn.dataset.add); return; }
    const inc = e.target.closest('[data-inc]');
    if (inc) { cart[inc.dataset.inc]++; save(); renderCart(); return; }
    const dec = e.target.closest('[data-dec]');
    if (dec) { cart[dec.dataset.dec]--; if (cart[dec.dataset.dec] <= 0) delete cart[dec.dataset.dec]; save(); renderCart(); return; }
    if (e.target.closest('[data-close]')) openCart(false);
  });
  cartBtn.addEventListener('click', () => openCart(true));
  addEventListener('keydown', (e) => { if (e.key === 'Escape' && drawer.classList.contains('is-open')) openCart(false); });
  renderCart();

  const year = $('#year');
  if (year) year.textContent = new Date().getFullYear();
})();
