/* Quantum Manager: shared behaviour for every page. */
(function () {
  'use strict';

  const QM = (window.QM = window.QM || {});
  const body = document.body;
  const loggedIn = body.dataset.auth === '1';

  // ------------------------------------------------------------------
  // Helpers
  // ------------------------------------------------------------------
  function getCookie(name) {
    const match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
    return match ? decodeURIComponent(match[1]) : '';
  }
  QM.csrf = function () {
    const input = document.querySelector('[name=csrfmiddlewaretoken]');
    return (input && input.value) || getCookie('csrftoken');
  };
  QM.post = function (url, data) {
    return fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': QM.csrf(), Accept: 'application/json' },
      body: JSON.stringify(data || {}),
    });
  };
  function icon(name, cls) {
    return `<svg class="icon ${cls || ''}" aria-hidden="true"><use href="#i-${name}"></use></svg>`;
  }
  QM.icon = icon;
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text == null ? '' : String(text);
    return div.innerHTML;
  }
  QM.escape = escapeHtml;
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private mode */ } },
  };
  QM.store = store;

  // ------------------------------------------------------------------
  // Toasts
  // ------------------------------------------------------------------
  const TOAST_ICONS = { success: 'check-circle', error: 'alert', warning: 'alert', info: 'info' };
  QM.toast = function (message, type) {
    type = type === 'danger' ? 'error' : (type || 'info');
    const box = document.getElementById('toasts');
    if (!box) return;
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.setAttribute('role', type === 'error' ? 'alert' : 'status');
    el.innerHTML = `${icon(TOAST_ICONS[type] || 'info')}<div class="msg">${escapeHtml(message)}</div>
      <button class="close" type="button" aria-label="Close">${icon('x', 'icon-sm')}</button>`;
    const remove = () => { el.classList.add('out'); setTimeout(() => el.remove(), 250); };
    el.querySelector('.close').addEventListener('click', remove);
    box.appendChild(el);
    setTimeout(remove, type === 'error' ? 7000 : 4500);
  };
  // Server messages rendered into the page
  document.querySelectorAll('#toasts .toast').forEach((el) => {
    const remove = () => { el.classList.add('out'); setTimeout(() => el.remove(), 250); };
    el.querySelector('.close')?.addEventListener('click', remove);
    setTimeout(remove, el.classList.contains('error') ? 7000 : 5000);
  });

  // ------------------------------------------------------------------
  // Sidebar drawer (mobile)
  // ------------------------------------------------------------------
  const sidebar = document.getElementById('sidebar');
  const scrim = document.getElementById('sidebarScrim');
  function setSidebar(open) {
    if (!sidebar) return;
    sidebar.classList.toggle('open', open);
    scrim?.classList.toggle('open', open);
    document.querySelectorAll('[data-sidebar-open]').forEach((b) => b.setAttribute('aria-expanded', String(open)));
    body.style.overflow = open && window.innerWidth < 960 ? 'hidden' : '';
    if (open) sidebar.querySelector('a, button')?.focus({ preventScroll: true });
  }
  document.querySelectorAll('[data-sidebar-open]').forEach((b) => b.addEventListener('click', () => setSidebar(true)));
  document.querySelectorAll('[data-sidebar-close]').forEach((b) => b.addEventListener('click', () => setSidebar(false)));
  scrim?.addEventListener('click', () => setSidebar(false));
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (sidebar?.classList.contains('open')) setSidebar(false);
      document.querySelectorAll('details.menu[open]').forEach((d) => d.removeAttribute('open'));
    }
    // "/" focuses search
    if (e.key === '/' && !/input|textarea|select/i.test(document.activeElement.tagName)) {
      const s = document.querySelector('[data-search]');
      if (s) { e.preventDefault(); s.focus(); }
    }
  });

  // Close dropdown menus when clicking elsewhere
  document.addEventListener('click', (e) => {
    document.querySelectorAll('details.menu[open]').forEach((d) => { if (!d.contains(e.target)) d.removeAttribute('open'); });
  });

  // Top bar border once scrolled
  const topbar = document.querySelector('.topbar');
  if (topbar) {
    const onScroll = () => topbar.classList.toggle('scrolled', window.scrollY > 4);
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

  // ------------------------------------------------------------------
  // Themes: blue (default), light, dark, auto
  // ------------------------------------------------------------------
  const THEME_COLORS = { blue: '#070D1F', light: '#F7F7F5', dark: '#0A0A0A' };
  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    document.querySelectorAll('[data-set-theme]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.setTheme === theme)));
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) {
      const dark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      meta.content = THEME_COLORS[theme] || (dark ? THEME_COLORS.dark : THEME_COLORS.light);
    }
  }
  QM.setTheme = function (theme, save) {
    applyTheme(theme);
    store.set('qm-theme', theme);
    if (save !== false && loggedIn) QM.post('/api/update-theme/', { theme }).catch(() => {});
  };
  document.querySelectorAll('[data-set-theme]').forEach((b) => {
    b.addEventListener('click', () => QM.setTheme(b.dataset.setTheme));
  });
  applyTheme(document.documentElement.getAttribute('data-theme') || 'blue');

  // ------------------------------------------------------------------
  // Forms: loading state, confirmations
  // ------------------------------------------------------------------
  document.addEventListener('submit', (e) => {
    const form = e.target;
    if (form.dataset.confirm && !window.confirm(form.dataset.confirm)) {
      e.preventDefault();
      return;
    }
    if (e.defaultPrevented) return;
    const btn = e.submitter || form.querySelector('button[type="submit"]');
    if (btn && !btn.classList.contains('no-loading')) {
      btn.classList.add('loading');
      setTimeout(() => { btn.classList.remove('loading'); }, 8000);
    }
  });

  // Password show/hide buttons
  document.querySelectorAll('[data-reveal]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const input = document.getElementById(btn.dataset.reveal);
      if (!input) return;
      const show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      btn.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
      btn.innerHTML = icon(show ? 'eye-off' : 'eye');
    });
  });

  // Tabs
  document.querySelectorAll('[data-tabs]').forEach((tablist) => {
    const tabs = tablist.querySelectorAll('[role="tab"]');
    tabs.forEach((tab) => {
      tab.addEventListener('click', () => {
        tabs.forEach((t) => {
          const on = t === tab;
          t.setAttribute('aria-selected', String(on));
          document.getElementById(t.getAttribute('aria-controls'))?.classList.toggle('active', on);
        });
        const url = new URL(window.location);
        url.searchParams.set('tab', tab.dataset.tab);
        history.replaceState({}, '', url);
      });
    });
  });

  // Emoji pickers (templates)
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-emoji]');
    if (!btn) return;
    const input = document.getElementById(btn.dataset.target);
    if (input) { input.value = btn.dataset.emoji; input.dispatchEvent(new Event('input')); }
  });

  // ------------------------------------------------------------------
  // Sharing (tasks, notes, templates, streaks, achievements)
  // ------------------------------------------------------------------
  QM.share = async function (title, text, path) {
    const url = window.location.origin + (path || '/');
    try {
      if (navigator.share) {
        await navigator.share({ title, text, url });
      } else {
        await navigator.clipboard.writeText(`${text}\n\n${url}`);
        QM.toast('Copied to your clipboard', 'success');
      }
    } catch (err) {
      if (err.name !== 'AbortError') QM.toast('Could not share that', 'error');
    }
  };
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-share-text]');
    if (!btn) return;
    e.preventDefault();
    QM.share(btn.dataset.shareTitle || 'Quantum Manager', btn.dataset.shareText, btn.dataset.sharePath);
  });

  // ------------------------------------------------------------------
  // Achievements popup
  // ------------------------------------------------------------------
  QM.achievements = function (list) {
    (list || []).forEach((a, i) => {
      setTimeout(() => {
        const el = document.createElement('div');
        el.className = 'achv-pop';
        el.setAttribute('role', 'status');
        el.innerHTML = `<div class="emoji">${escapeHtml(a.icon)}</div>
          <div><div class="kicker">Achievement unlocked</div><div class="name">${escapeHtml(a.name)}</div>
          ${a.description ? `<div class="desc">${escapeHtml(a.description)}</div>` : ''}</div>
          <div class="pts">+${Number(a.points) || 0}</div>`;
        document.body.appendChild(el);
        requestAnimationFrame(() => requestAnimationFrame(() => el.classList.add('show')));
        setTimeout(() => { el.classList.remove('show'); setTimeout(() => el.remove(), 600); }, 4800);
      }, i * 700);
    });
  };

  // ------------------------------------------------------------------
  // Install the app (PWA)
  // ------------------------------------------------------------------
  let deferredPrompt = null;
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    document.querySelectorAll('[data-install]').forEach((el) => { el.hidden = false; });
  });
  document.addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-install-btn]');
    if (!btn || !deferredPrompt) return;
    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    deferredPrompt = null;
    if (outcome === 'accepted') document.querySelectorAll('[data-install]').forEach((el) => { el.hidden = true; });
  });
  window.addEventListener('appinstalled', () => {
    document.querySelectorAll('[data-install]').forEach((el) => { el.hidden = true; });
    QM.toast('Installed! Open Quantum Manager from your home screen.', 'success');
  });

  // ------------------------------------------------------------------
  // Service worker
  // ------------------------------------------------------------------
  QM.swReady = null;
  if ('serviceWorker' in navigator) {
    QM.swReady = navigator.serviceWorker.register('/sw.js', { scope: '/' })
      .then(() => navigator.serviceWorker.ready)
      .catch((err) => { console.warn('Service worker failed', err); return null; });
  }

  // ------------------------------------------------------------------
  // Push alarms (ring even when the app is closed)
  // ------------------------------------------------------------------
  function urlBase64ToUint8Array(base64) {
    const padding = '='.repeat((4 - (base64.length % 4)) % 4);
    const raw = atob((base64 + padding).replace(/-/g, '+').replace(/_/g, '/'));
    return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
  }
  const pushKey = body.dataset.pushKey || '';
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  function sameKey(sub, key) {
    const current = sub.options && sub.options.applicationServerKey;
    if (!current) return true; // browser doesn't say, assume fine
    const a = new Uint8Array(current);
    return a.length === key.length && a.every((v, i) => v === key[i]);
  }
  // Wait until the service worker is active (not just registered)
  async function activeWorker() {
    if (!('serviceWorker' in navigator)) return null;
    let reg = await QM.swReady;
    if (!reg) {
      // Registration failed earlier (bad network?): try once more
      reg = await navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(() => null);
      if (!reg) return null;
    }
    const ready = await Promise.race([navigator.serviceWorker.ready, wait(10000).then(() => null)]);
    if (ready && ready.active) return ready;
    return reg.active ? reg : null;
  }
  QM.push = {
    supported: !!(pushKey && 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window),
    async status() {
      if (!this.supported) return 'unsupported';
      if (Notification.permission === 'denied') return 'blocked';
      const reg = await QM.swReady;
      const sub = reg && (await reg.pushManager.getSubscription());
      return sub && Notification.permission === 'granted' ? 'on' : 'off';
    },
    async enable() {
      if (!this.supported) {
        QM.toast('This browser can\'t get alarms while closed. On iPhone, add the app to your Home Screen first.', 'warning');
        return false;
      }
      // 1. Ask for permission (must happen straight after the tap)
      let permission = Notification.permission;
      if (permission === 'default') permission = await Notification.requestPermission();
      if (permission !== 'granted') {
        QM.toast('Notifications are blocked. Allow them for this site in your browser settings, then try again.', 'warning');
        return false;
      }
      // 2. Make sure the service worker is installed AND active.
      //    On a fresh visit it is often still installing, which is why
      //    the first few taps used to fail.
      const reg = await activeWorker();
      if (!reg) { QM.toast('The app is still loading. Give it a few seconds and try again.', 'warning'); return false; }

      // 3. Subscribe, with a few retries (push servers sometimes say no once)
      const key = urlBase64ToUint8Array(pushKey);
      let sub = null;
      let lastErr = null;
      for (let attempt = 0; attempt < 4 && !sub; attempt++) {
        try {
          sub = await reg.pushManager.getSubscription();
          // Old subscription made with different keys? Throw it away.
          if (sub && !sameKey(sub, key)) { await sub.unsubscribe().catch(() => {}); sub = null; }
          if (!sub) sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key });
        } catch (err) {
          lastErr = err;
          sub = null;
          // A stuck old subscription causes InvalidStateError: clear it and retry
          const stale = await reg.pushManager.getSubscription().catch(() => null);
          if (stale) await stale.unsubscribe().catch(() => {});
          await wait(600 * (attempt + 1));
        }
      }
      if (!sub) {
        console.error('Push subscribe failed', lastErr);
        const name = lastErr && lastErr.name;
        if (name === 'NotAllowedError') QM.toast('Notifications are blocked for this site. Allow them in your browser settings.', 'warning');
        else if (name === 'AbortError') QM.toast('Your browser\'s push service didn\'t answer. Check your internet (and that Chrome isn\'t in data saver), then try again.', 'error');
        else QM.toast('Could not turn on alarms on this browser. Try again in a minute.', 'error');
        return false;
      }

      // 4. Tell the server. Render's free plan can take ~30s to wake up,
      //    so retry a few times instead of giving up on the first timeout.
      for (let attempt = 0; attempt < 4; attempt++) {
        try {
          const res = await QM.post('/api/push/subscribe/', sub.toJSON());
          if (res.ok) return true;
          if (res.status === 403 || res.status === 401) { QM.toast('Please log in again, then turn alarms on.', 'warning'); return false; }
        } catch (err) { /* network hiccup: retry */ }
        await wait(1500 * (attempt + 1));
      }
      QM.toast('The server is waking up. Wait a moment and tap again.', 'error');
      return false;
    },
    async disable() {
      const reg = await QM.swReady;
      const sub = reg && (await reg.pushManager.getSubscription());
      if (sub) {
        await QM.post('/api/push/unsubscribe/', { endpoint: sub.endpoint }).catch(() => {});
        await sub.unsubscribe();
      }
    },
  };
  async function refreshPushUi() {
    const status = await QM.push.status();
    document.querySelectorAll('[data-push-status]').forEach((el) => { el.dataset.state = status; });
    document.querySelectorAll('[data-push-show]').forEach((el) => {
      el.hidden = !el.dataset.pushShow.split(' ').includes(status);
    });
    document.querySelectorAll('[data-push-toggle]').forEach((el) => { el.checked = status === 'on'; el.disabled = status === 'unsupported'; });
    // Keep the server copy fresh (keys can rotate)
    if (status === 'on' && !store.get('qm-push-synced-' + new Date().toDateString())) {
      const reg = await QM.swReady;
      const sub = reg && (await reg.pushManager.getSubscription());
      if (sub) QM.post('/api/push/subscribe/', sub.toJSON()).then(() => store.set('qm-push-synced-' + new Date().toDateString(), '1'));
    }
  }
  QM.refreshPushUi = refreshPushUi;
  if (loggedIn) {
    refreshPushUi();
    document.addEventListener('click', async (e) => {
      const btn = e.target.closest('[data-push-enable]');
      if (!btn) return;
      btn.classList.add('loading');
      const ok = await QM.push.enable().catch((err) => { console.error(err); QM.toast('Could not turn on alarms', 'error'); return false; });
      btn.classList.remove('loading');
      if (ok) QM.toast('Alarms are on for this device. They\'ll ring even when the app is closed.', 'success');
      refreshPushUi();
    });
    document.querySelectorAll('[data-push-toggle]').forEach((input) => {
      input.addEventListener('change', async () => {
        if (input.checked) {
          const ok = await QM.push.enable().catch(() => false);
          if (ok) QM.toast('Alarms are on for this device', 'success');
        } else {
          await QM.push.disable();
          QM.toast('Alarms are off for this device', 'info');
        }
        refreshPushUi();
      });
    });
  }

  // ------------------------------------------------------------------
  // Alarm sounds: catalog, player and the dropdown picker
  // ------------------------------------------------------------------
  let toneCatalog = {};
  try { toneCatalog = JSON.parse((document.getElementById('qm-tones') || {}).textContent || '{}'); } catch (e) { toneCatalog = {}; }
  QM.tones = {
    catalog: toneCatalog,
    current: null,
    timers: [],
    owner: null,
    url(tone) {
      if (!tone) tone = 'classic';
      if (tone.startsWith('/') || tone.startsWith('http') || tone.startsWith('blob:')) return tone;
      const t = toneCatalog[tone] || toneCatalog.classic;
      return t ? t.url : '';
    },
    name(tone) {
      if (toneCatalog[tone]) return toneCatalog[tone].name;
      return tone && tone !== 'custom' ? 'Your own sound' : 'Upload your own sound';
    },
    stop() {
      this.timers.forEach(clearInterval); this.timers.forEach(clearTimeout); this.timers = [];
      if (this.current) { try { this.current.pause(); } catch (e) { /* ignore */ } this.current = null; }
      if (this.owner) { this.owner.classList.remove('playing'); this.owner.setAttribute('aria-pressed', 'false'); this.owner = null; }
    },
    // loop: keep going; rampSeconds: fade from quiet to full over that time
    play(tone, opts = {}) {
      this.stop();
      const src = this.url(tone);
      if (!src) { if (opts.fallback) opts.fallback(); return Promise.resolve(false); }
      const audio = new Audio(src);
      audio.loop = !!opts.loop;
      audio.preload = 'auto';
      const ramp = opts.rampSeconds || 0;
      audio.volume = ramp ? 0.35 : 0.9;
      this.current = audio;
      if (ramp) {
        const started = Date.now();
        this.timers.push(setInterval(() => {
          const k = Math.min(1, (Date.now() - started) / (ramp * 1000));
          try { audio.volume = 0.35 + 0.65 * k; } catch (e) { /* iOS ignores volume */ }
        }, 500));
      }
      if (opts.maxSeconds) this.timers.push(setTimeout(() => this.stop(), opts.maxSeconds * 1000));
      audio.addEventListener('ended', () => { if (!audio.loop && this.current === audio) this.stop(); });
      return audio.play().then(() => true).catch(() => {
        if (this.current === audio) this.stop();
        if (opts.fallback) opts.fallback();
        return false;
      });
    },
    // Preview: play once, tap the same button again to stop
    toggle(tone, btn) {
      if (btn && this.owner === btn) { this.stop(); return; }
      this.play(tone).then((ok) => {
        if (ok && btn) { this.owner = btn; btn.classList.add('playing'); btn.setAttribute('aria-pressed', 'true'); }
        if (!ok) QM.toast('Could not play that sound', 'warning');
      });
    },
  };

  // Turns <select data-tone-select> into a sleek dropdown with previews.
  // The real <select> stays in the form (hidden), so saving works the same.
  // data-upload="<file input id>" adds "Upload your own sound".
  QM.tonePicker = function (select) {
    if (select.dataset.enhanced) return;
    select.dataset.enhanced = '1';
    const upload = select.dataset.upload ? document.getElementById(select.dataset.upload) : null;
    let uploadedName = '';
    const wrap = document.createElement('div');
    wrap.className = 'tp';
    select.parentNode.insertBefore(wrap, select);
    wrap.appendChild(select);
    select.classList.add('sr-only');
    select.tabIndex = -1;
    select.setAttribute('aria-hidden', 'true');

    const listId = `tp-list-${select.id || Math.random().toString(36).slice(2)}`;
    const row = document.createElement('div');
    row.className = 'tp-row';
    row.innerHTML = `<button type="button" class="tp-trigger" aria-haspopup="listbox" aria-expanded="false" aria-controls="${listId}">
        <span class="tp-ico">${icon('bell', 'icon-sm')}</span>
        <span class="tp-text"><span class="tp-name"></span><span class="tp-sub"></span></span>
        ${icon('chevron-down', 'icon-sm tp-chev')}
      </button>
      <button type="button" class="tp-play" aria-label="Play this sound" aria-pressed="false">${icon('play', 'icon-sm')}${icon('stop', 'icon-sm')}</button>`;
    wrap.appendChild(row);
    const trigger = row.querySelector('.tp-trigger');
    const playBtn = row.querySelector('.tp-play');

    const panel = document.createElement('div');
    panel.className = 'tp-panel';
    panel.id = listId;
    panel.setAttribute('role', 'listbox');
    panel.hidden = true;
    const groups = [];
    Array.from(select.children).forEach((node) => {
      if (node.tagName === 'OPTGROUP') groups.push({ label: node.label, options: Array.from(node.children) });
      else groups.push({ label: '', options: [node] });
    });
    panel.innerHTML = groups.map((g) => `${g.label ? `<div class="tp-group">${escapeHtml(g.label)}</div>` : ''}${g.options.map((o) => {
      const info = toneCatalog[o.value] || {};
      const isCustom = o.value === 'custom';
      const desc = o.dataset.desc || info.desc || (isCustom ? 'MP3, WAV or M4A, up to 25 MB' : (o.value.startsWith('/') || o.value.startsWith('http') ? 'Uploaded earlier' : ''));
      return `<div class="tp-opt" role="option" tabindex="-1" data-value="${escapeHtml(o.value)}" aria-selected="false">
          <span class="tp-check">${icon('check', 'icon-sm')}</span>
          <span class="tp-text"><span class="tp-name">${escapeHtml(o.textContent.trim())}</span>${desc ? `<span class="tp-sub">${escapeHtml(desc)}</span>` : ''}</span>
          ${isCustom ? `<span class="tp-chip">${icon('upload', 'icon-xs')}Choose</span>` : `<button type="button" class="tp-mini" data-preview-tone="${escapeHtml(o.value)}" aria-label="Play ${escapeHtml(o.textContent.trim())}">${icon('play', 'icon-xs')}${icon('stop', 'icon-xs')}</button>`}
        </div>`;
    }).join('')}`).join('');
    wrap.appendChild(panel);
    const opts = () => Array.from(panel.querySelectorAll('.tp-opt'));

    function render() {
      const v = select.value;
      const isCustom = v === 'custom';
      const opt = select.selectedOptions[0];
      const info = toneCatalog[v];
      trigger.querySelector('.tp-name').textContent = isCustom && uploadedName ? uploadedName : (opt ? opt.textContent.trim() : QM.tones.name(v));
      trigger.querySelector('.tp-sub').textContent = info ? `${info.group} · ${info.desc}` : (isCustom ? (uploadedName ? 'New upload, saves with the task' : 'Pick a file from your phone') : 'Your uploaded sound');
      playBtn.hidden = isCustom && !uploadedName;
      opts().forEach((el) => el.setAttribute('aria-selected', String(el.dataset.value === v)));
    }
    function open() {
      panel.hidden = false;
      wrap.classList.add('open');
      trigger.setAttribute('aria-expanded', 'true');
      const sel = panel.querySelector('[aria-selected="true"]') || opts()[0];
      if (sel) { sel.focus({ preventScroll: true }); sel.scrollIntoView({ block: 'nearest' }); }
    }
    function close(focus) {
      if (panel.hidden) return;
      panel.hidden = true;
      wrap.classList.remove('open');
      trigger.setAttribute('aria-expanded', 'false');
      if (QM.tones.owner && panel.contains(QM.tones.owner)) QM.tones.stop();
      if (focus) trigger.focus();
    }
    function choose(value) {
      if (value === 'custom' && upload) {
        close(true);
        upload.click();
        return;
      }
      select.value = value;
      select.dispatchEvent(new Event('change', { bubbles: true }));
      render();
      close(true);
    }

    trigger.addEventListener('click', () => (panel.hidden ? open() : close(true)));
    trigger.addEventListener('keydown', (e) => { if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); open(); } });
    playBtn.addEventListener('click', () => {
      const v = select.value === 'custom' && upload && upload.files[0] ? (upload._qmUrl || '') : select.value;
      QM.tones.toggle(v, playBtn);
    });
    panel.addEventListener('click', (e) => {
      if (e.target.closest('[data-preview-tone]')) return; // preview only
      const el = e.target.closest('.tp-opt');
      if (el) choose(el.dataset.value);
    });
    panel.addEventListener('keydown', (e) => {
      const list = opts();
      const i = list.indexOf(document.activeElement);
      if (e.key === 'ArrowDown') { e.preventDefault(); (list[i + 1] || list[0]).focus(); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); (list[i - 1] || list[list.length - 1]).focus(); }
      else if (e.key === 'Enter' || e.key === ' ') { if (i >= 0) { e.preventDefault(); choose(list[i].dataset.value); } }
      else if (e.key === 'Escape' || e.key === 'Tab') { close(e.key === 'Escape'); }
      else if (e.key.toLowerCase() === 'p' && i >= 0) { const b = list[i].querySelector('[data-preview-tone]'); if (b) b.click(); }
    });
    document.addEventListener('click', (e) => { if (!wrap.contains(e.target)) close(false); });

    if (upload) {
      upload.addEventListener('change', () => {
        const f = upload.files && upload.files[0];
        if (!f) return;
        if (f.type && !f.type.startsWith('audio/') && !/\.(mp3|wav|ogg|m4a|aac|webm)$/i.test(f.name)) { QM.toast('Please choose an audio file', 'warning'); upload.value = ''; return; }
        if (f.size > 25 * 1024 * 1024) { QM.toast('That file is bigger than 25 MB. Try a shorter clip.', 'warning'); upload.value = ''; return; }
        if (upload._qmUrl) URL.revokeObjectURL(upload._qmUrl);
        upload._qmUrl = URL.createObjectURL(f);
        uploadedName = f.name;
        select.value = 'custom';
        render();
        QM.toast(`"${f.name}" will be your alarm`, 'success');
      });
    }
    render();
  };

  // ------------------------------------------------------------------
  // In-app alarm (while the app is open): sound, popup, notification
  // ------------------------------------------------------------------
  class AlarmSystem {
    constructor() {
      this.audioContext = null;
      this.isPlaying = false;
      const unlock = async () => {
        try {
          if (!this.audioContext) this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
          if (this.audioContext.state === 'suspended') await this.audioContext.resume();
        } catch (e) { /* no audio */ }
      };
      document.addEventListener('pointerdown', unlock, { once: true });
      document.addEventListener('keydown', unlock, { once: true });
      this.check();
      this.timer = setInterval(() => this.check(), 30000);
      document.addEventListener('visibilitychange', () => { if (!document.hidden) this.check(); });
    }

    async check() {
      try {
        const res = await fetch('/api/check-due-tasks/', { cache: 'no-store', credentials: 'same-origin', headers: { Accept: 'application/json' } });
        if (!res.ok || !(res.headers.get('content-type') || '').includes('application/json')) return;
        const data = await res.json();
        (data.due_tasks || []).forEach((t) => this.trigger(t));
      } catch (e) { /* offline */ }
    }

    trigger(task) {
      if (document.querySelector(`.alarm-overlay[data-task-id="${task.id}"]`)) return;
      let seen = {};
      try { seen = JSON.parse(store.get('notifiedTasks') || '{}'); } catch (e) { seen = {}; }
      const key = `task_${task.id}_${task.ring_at || task.alarm_time}`;
      const now = Date.now();
      if (seen[key] && now - seen[key] < 300000) return; // re-ring every 5 min until dismissed
      seen[key] = now;
      Object.keys(seen).forEach((k) => { if (now - seen[k] > 86400000) delete seen[k]; });
      store.set('notifiedTasks', JSON.stringify(seen));

      try { this.notify(task); } catch (e) { /* ignore */ }
      try { if (!this.isPlaying) this.play(task.alarm_tone || 'classic'); } catch (e) { /* ignore */ }
      this.modal(task);
    }

    notify(task) {
      if (!('Notification' in window) || Notification.permission !== 'granted') return;
      const title = `⏰ ${task.title}`;
      const options = {
        body: task.description || 'Your reminder is ringing',
        icon: '/static/tasks/icons/icon-192x192.png',
        badge: '/static/tasks/icons/logo-mark.png',
        tag: `task-${task.id}`,
        renotify: true,
        requireInteraction: true,
        data: { url: `/update/${task.id}/` },
      };
      // Android only allows notifications from the service worker
      if (QM.swReady) {
        QM.swReady.then((reg) => reg && reg.showNotification(title, options)).catch(() => {});
      } else {
        try { new Notification(title, options); } catch (e) { /* not allowed */ }
      }
    }

    // Loops the sound and slowly gets louder until Snooze / Got it
    play(tone) {
      this.isPlaying = true;
      QM.tones.play(tone, { loop: true, rampSeconds: 25, maxSeconds: 180, fallback: () => this.beep() })
        .finally(() => { /* keeps ringing until stop() */ });
    }

    stop() {
      this.isPlaying = false;
      QM.tones.stop();
    }

    // Last resort when the browser won't play the mp3 (e.g. no tap yet)
    beep() {
      try {
        if (!this.audioContext) this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const ctx = this.audioContext;
        if (ctx.state === 'suspended') ctx.resume().catch(() => {});
        [0, 0.3, 0.6, 1.2, 1.5, 1.8].forEach((t) => {
          const osc = ctx.createOscillator();
          const gain = ctx.createGain();
          osc.connect(gain); gain.connect(ctx.destination);
          osc.type = 'square'; osc.frequency.value = 800;
          gain.gain.setValueAtTime(0.25, ctx.currentTime + t);
          gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + t + 0.2);
          osc.start(ctx.currentTime + t); osc.stop(ctx.currentTime + t + 0.2);
        });
      } catch (e) { /* no audio at all */ }
    }

    modal(task) {
      const el = document.createElement('div');
      el.className = 'alarm-overlay';
      el.dataset.taskId = task.id;
      el.setAttribute('role', 'alertdialog');
      el.setAttribute('aria-modal', 'true');
      el.setAttribute('aria-labelledby', `alarm-title-${task.id}`);
      const due = task.due_date ? new Date(task.due_date).toLocaleString([], { weekday: 'short', hour: 'numeric', minute: '2-digit' }) : '';
      el.innerHTML = `<div class="alarm-card glass">
          <div class="alarm-bell">${icon('bell')}</div>
          <div class="alarm-kicker">Reminder</div>
          <h2 class="alarm-title" id="alarm-title-${task.id}">${escapeHtml(task.title)}</h2>
          ${task.description ? `<p class="alarm-desc">${escapeHtml(task.description)}</p>` : ''}
          <div class="alarm-meta">
            <span class="pill"><span class="pdot ${escapeHtml(task.priority)}"></span>${escapeHtml(task.priority.charAt(0).toUpperCase() + task.priority.slice(1))}</span>
            ${due ? `<span class="pill accent">${icon('clock', 'icon-xs')}${escapeHtml(due)}</span>` : ''}
          </div>
          <div class="alarm-actions">
            <button class="btn" data-a="snooze">${icon('snooze', 'icon-sm')}Snooze 10 min</button>
            <button class="btn" data-a="view">${icon('edit', 'icon-sm')}Open task</button>
            <button class="btn btn-primary full" data-a="dismiss">${icon('check', 'icon-sm')}Got it</button>
          </div>
        </div>`;
      document.body.appendChild(el);
      requestAnimationFrame(() => el.classList.add('show'));
      el.querySelector('[data-a="dismiss"]').focus();
      el.addEventListener('click', async (e) => {
        const a = e.target.closest('[data-a]')?.dataset.a;
        if (!a) return;
        if (a === 'snooze') {
          const res = await QM.post(`/api/snooze-alarm/${task.id}/`, { minutes: 10 }).catch(() => null);
          if (res && res.ok) QM.toast('Snoozed for 10 minutes', 'info');
        } else {
          await QM.post(`/api/dismiss-alarm/${task.id}/`).catch(() => {});
          if (a === 'view') window.location.href = `/update/${task.id}/`;
        }
        this.close(task.id);
      });
    }

    close(taskId) {
      document.querySelectorAll(`.alarm-overlay[data-task-id="${taskId}"]`).forEach((el) => {
        el.classList.remove('show');
        el.removeAttribute('data-task-id');
        setTimeout(() => el.remove(), 250);
      });
      // Stop the sound once no alarm is left on screen
      if (!document.querySelector('.alarm-overlay[data-task-id]')) this.stop();
    }
  }
  QM.AlarmSystem = AlarmSystem;
  if (loggedIn) window.alarmSystem = new AlarmSystem();

  // Any [data-preview-tone] button plays a sound once (tap again to stop)
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-preview-tone]');
    if (!btn) return;
    e.preventDefault();
    QM.tones.toggle(btn.dataset.previewTone, btn);
  });
  document.querySelectorAll('select[data-tone-select]').forEach((sel) => QM.tonePicker(sel));

  // ------------------------------------------------------------------
  // 3D depth: cards lean toward the mouse. Mouse only (on touch they
  // press in with CSS instead) and never with "reduce motion" on.
  // ------------------------------------------------------------------
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  QM.depth = function (root) {
    if (reduceMotion || !window.matchMedia('(hover: hover) and (pointer: fine)').matches) return;
    const MAX = 6; // degrees
    (root || document).querySelectorAll('.stat, .kpi, .tpl, .achv, .note, .progress-card, .onboard').forEach((el) => {
      if (el.dataset.tilt) return;
      el.dataset.tilt = '1';
      el.classList.add('tilt');
      let frame = 0;
      el.addEventListener('pointermove', (e) => {
        if (frame) return;
        frame = requestAnimationFrame(() => {
          frame = 0;
          const r = el.getBoundingClientRect();
          const x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
          el.style.setProperty('--ry', `${((x - 0.5) * 2 * MAX).toFixed(2)}deg`);
          el.style.setProperty('--rx', `${((0.5 - y) * 2 * MAX).toFixed(2)}deg`);
          el.style.setProperty('--mx', `${(x * 100).toFixed(1)}%`);
          el.style.setProperty('--my', `${(y * 100).toFixed(1)}%`);
          el.classList.add('tilting');
        });
      });
      el.addEventListener('pointerleave', () => {
        el.classList.remove('tilting');
        el.style.setProperty('--rx', '0deg');
        el.style.setProperty('--ry', '0deg');
      });
    });
  };
  QM.depth();

  // ------------------------------------------------------------------
  // Real 3D background: a slow, folding colour field drawn by the GPU,
  // like shadergradient, but hand-written WebGL (no React, no library).
  // Only on pages with body.hero-3d. It renders small and scales up,
  // runs at 30fps, pauses when the tab is hidden, and is skipped on
  // data saver, old phones and "reduce motion" (one still frame instead).
  // ------------------------------------------------------------------
  QM.shader = function () {
    if (!body.classList.contains('hero-3d')) return;
    const conn = navigator.connection;
    if (conn && conn.saveData) return; // keep the CSS gradient
    const canvas = document.createElement('canvas');
    canvas.className = 'qm-shader';
    canvas.setAttribute('aria-hidden', 'true');
    const gl = canvas.getContext('webgl', { antialias: false, alpha: false, powerPreference: 'low-power' });
    if (!gl) return;

    const vert = 'attribute vec2 p; void main(){ gl_Position = vec4(p, 0.0, 1.0); }';
    const frag = `precision mediump float;
      uniform vec2 u_res; uniform float u_time, u_amt;
      uniform vec3 u_bg, u_c1, u_c2, u_c3;
      float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
      float noise(vec2 p){
        vec2 i = floor(p), f = fract(p); vec2 u = f * f * (3.0 - 2.0 * f);
        return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
      }
      float fbm(vec2 p){ float v = 0.0, a = 0.5; for (int i = 0; i < 4; i++) { v += a * noise(p); p *= 2.0; a *= 0.5; } return v; }
      void main(){
        vec2 uv = gl_FragCoord.xy / u_res;
        vec2 p = uv * vec2(u_res.x / u_res.y, 1.0) * 1.5;
        float t = u_time * 0.045;
        // Warp the noise through itself: gives the soft folded-fabric shapes
        vec2 q = vec2(fbm(p + t), fbm(p + vec2(5.2, 1.3) - t));
        vec2 r = vec2(fbm(p + 2.0 * q + vec2(1.7, 9.2) + 0.7 * t), fbm(p + 2.0 * q + vec2(8.3, 2.8) - 0.6 * t));
        float f = fbm(p + 2.0 * r);
        vec3 col = mix(u_bg, u_c1, smoothstep(0.25, 0.85, f));
        col = mix(col, u_c2, smoothstep(0.45, 1.0, length(q)) * 0.75);
        col = mix(col, u_c3, smoothstep(0.5, 1.0, r.y) * 0.5);
        // Fake light: brighter on the "ridges" so it reads as 3D folds
        col *= 0.5 + 1.5 * f * f;
        gl_FragColor = vec4(mix(u_bg, col, u_amt), 1.0);
      }`;
    function compile(type, src) {
      const s = gl.createShader(type);
      gl.shaderSource(s, src);
      gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
      return s;
    }
    let prog;
    try {
      prog = gl.createProgram();
      gl.attachShader(prog, compile(gl.VERTEX_SHADER, vert));
      gl.attachShader(prog, compile(gl.FRAGMENT_SHADER, frag));
      gl.linkProgram(prog);
      if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(prog));
    } catch (err) {
      console.warn('3D background off:', err);
      return; // the CSS gradient is still there
    }
    gl.useProgram(prog);
    const buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    const loc = gl.getAttribLocation(prog, 'p');
    gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    const u = (n) => gl.getUniformLocation(prog, n);
    const U = { res: u('u_res'), time: u('u_time'), amt: u('u_amt'), bg: u('u_bg'), c1: u('u_c1'), c2: u('u_c2'), c3: u('u_c3') };

    // Theme colours come from the CSS variables, so all 3 themes keep their palette
    const probe = document.createElement('canvas').getContext('2d');
    function rgb(css) {
      probe.fillStyle = '#000';
      probe.fillStyle = css.trim() || '#000';
      const v = probe.fillStyle;
      if (v[0] === '#') return [1, 3, 5].map((i) => parseInt(v.slice(i, i + 2), 16) / 255);
      return (v.match(/[\d.]+/g) || [0, 0, 0]).slice(0, 3).map((n) => Number(n) / 255);
    }
    function applyColours() {
      const cs = getComputedStyle(document.documentElement);
      const bg = rgb(cs.getPropertyValue('--bg'));
      const light = (bg[0] + bg[1] + bg[2]) / 3 > 0.6;
      gl.uniform3fv(U.bg, bg);
      gl.uniform3fv(U.c1, rgb(cs.getPropertyValue('--accent')));
      gl.uniform3fv(U.c2, rgb(cs.getPropertyValue('--glow')));
      gl.uniform3fv(U.c3, rgb('#FF5E8A'));
      gl.uniform1f(U.amt, light ? 0.4 : 1.0);
    }
    const SCALE = 0.35; // draw small, let CSS stretch it: blurry is fine for a gradient
    function resize() {
      canvas.width = Math.max(1, Math.round(window.innerWidth * SCALE));
      canvas.height = Math.max(1, Math.round(window.innerHeight * SCALE));
      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.uniform2f(U.res, canvas.width, canvas.height);
    }
    const start = performance.now() - Math.random() * 60000;
    function draw(now) {
      gl.uniform1f(U.time, (now - start) / 1000);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    }

    body.prepend(canvas);
    resize();
    applyColours();
    draw(performance.now());
    requestAnimationFrame(() => canvas.classList.add('on'));

    const still = reduceMotion || (navigator.hardwareConcurrency || 4) <= 2;
    let last = 0, raf = 0;
    function loop(now) {
      raf = requestAnimationFrame(loop);
      if (now - last < 33) return; // ~30fps is plenty for something this slow
      last = now;
      draw(now);
    }
    function play() { if (!still && !raf && !document.hidden) raf = requestAnimationFrame(loop); }
    function pause() { cancelAnimationFrame(raf); raf = 0; }
    play();
    document.addEventListener('visibilitychange', () => (document.hidden ? pause() : play()));
    window.addEventListener('resize', () => { resize(); draw(performance.now()); });
    new MutationObserver(() => { applyColours(); draw(performance.now()); })
      .observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    canvas.addEventListener('webglcontextlost', () => { pause(); canvas.remove(); });
  };
  try { QM.shader(); } catch (err) { console.warn('3D background off:', err); }

  // ------------------------------------------------------------------
  // Tell the server the user's timezone (for times and morning emails)
  // ------------------------------------------------------------------
  try {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (tz && getCookie('tz') !== tz) document.cookie = `tz=${encodeURIComponent(tz)}; path=/; max-age=31536000; SameSite=Lax`;
  } catch (e) { /* old browser */ }
})();
