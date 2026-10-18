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
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') {
        QM.toast('Notifications are blocked. Allow them in your browser settings to get alarms.', 'warning');
        return false;
      }
      const reg = await QM.swReady;
      let sub = await reg.pushManager.getSubscription();
      if (!sub) {
        sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlBase64ToUint8Array(pushKey) });
      }
      const res = await QM.post('/api/push/subscribe/', sub.toJSON());
      if (!res.ok) { QM.toast('Could not turn on alarms. Try again.', 'error'); return false; }
      return true;
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
        badge: '/static/tasks/icons/icon-96x96.png',
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

    play(tone) {
      if (tone && (tone.startsWith('/') || tone.startsWith('http'))) {
        this.isPlaying = true;
        const audio = new Audio(tone);
        audio.volume = 0.8;
        audio.onended = () => { this.isPlaying = false; };
        audio.play().catch(() => { this.isPlaying = false; this.play('classic'); });
        return;
      }
      if (!this.audioContext) this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
      const ctx = this.audioContext;
      if (ctx.state === 'suspended') ctx.resume().catch(() => {});
      this.isPlaying = true;
      const beep = (freq, start, dur, type, vol) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain); gain.connect(ctx.destination);
        osc.type = type; osc.frequency.value = freq;
        gain.gain.setValueAtTime(vol, ctx.currentTime + start);
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + start + dur);
        osc.start(ctx.currentTime + start); osc.stop(ctx.currentTime + start + dur);
      };
      let length = 2000;
      if (tone === 'chime') {
        [523.25, 659.25, 783.99].forEach((f, i) => beep(f, i * 0.12, 1, 'sine', 0.22));
        length = 1500;
      } else if (tone === 'urgent') {
        for (let i = 0; i < 8; i++) beep(i % 2 ? 660 : 880, i * 0.3, 0.25, 'sawtooth', 0.25);
        length = 2600;
      } else {
        [0, 0.3, 0.6, 1.2, 1.5, 1.8].forEach((t) => beep(800, t, 0.2, 'square', 0.25));
      }
      setTimeout(() => { this.isPlaying = false; }, length);
    }

    modal(task) {
      const el = document.createElement('div');
      el.className = 'alarm-overlay';
      el.dataset.taskId = task.id;
      el.setAttribute('role', 'alertdialog');
      el.setAttribute('aria-modal', 'true');
      el.setAttribute('aria-labelledby', `alarm-title-${task.id}`);
      const due = task.due_date ? new Date(task.due_date).toLocaleString([], { weekday: 'short', hour: 'numeric', minute: '2-digit' }) : '';
      el.innerHTML = `<div class="alarm-card">
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
        setTimeout(() => el.remove(), 250);
      });
    }
  }
  QM.AlarmSystem = AlarmSystem;
  if (loggedIn) window.alarmSystem = new AlarmSystem();

  // Tone preview buttons (create / edit task)
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-preview-tone]');
    if (!btn) return;
    e.preventDefault();
    if (window.alarmSystem) window.alarmSystem.play(btn.dataset.previewTone);
  });

  // ------------------------------------------------------------------
  // Tell the server the user's timezone (for times and morning emails)
  // ------------------------------------------------------------------
  try {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (tz && getCookie('tz') !== tz) document.cookie = `tz=${encodeURIComponent(tz)}; path=/; max-age=31536000; SameSite=Lax`;
  } catch (e) { /* old browser */ }
})();
