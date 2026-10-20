/*
 * Quantum Manager outbox: changes made while offline wait here, then get
 * sent to the server in order once there's a connection again.
 *
 * Used by both the pages (window) and the service worker (self), so it only
 * relies on things both have: IndexedDB, fetch and (optionally) Web Locks.
 *
 * Each change is stored as:
 *   { id, opId, url, kind: 'form' | 'json', body, csrf, label, created }
 * - form: body is a list of [name, value] pairs (values can be Files)
 * - json: body is a plain object
 * opId is sent as the X-QM-Op header, so the server never applies it twice.
 */
(function (scope) {
  'use strict';

  const DB_NAME = 'qm';
  const STORE = 'outbox';
  let dbPromise = null;

  function openDb() {
    if (!dbPromise) {
      dbPromise = new Promise((resolve, reject) => {
        const req = indexedDB.open(DB_NAME, 1);
        req.onupgradeneeded = () => req.result.createObjectStore(STORE, { keyPath: 'id', autoIncrement: true });
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => { dbPromise = null; reject(req.error); };
      });
    }
    return dbPromise;
  }

  function run(mode, fn) {
    return openDb().then((db) => new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, mode);
      const result = fn(tx.objectStore(STORE));
      tx.oncomplete = () => resolve(result && 'result' in result ? result.result : undefined);
      tx.onerror = () => reject(tx.error);
      tx.onabort = () => reject(tx.error);
    }));
  }

  function newId() {
    if (scope.crypto && scope.crypto.randomUUID) return scope.crypto.randomUUID();
    return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
  }

  const Outbox = {
    add(op) {
      const item = Object.assign({ opId: newId(), created: Date.now(), kind: 'json', label: 'A change' }, op);
      return run('readwrite', (store) => store.add(item));
    },
    all() {
      return run('readonly', (store) => store.getAll()).then((items) => items || []);
    },
    count() {
      return run('readonly', (store) => store.count()).catch(() => 0);
    },
    remove(id) {
      return run('readwrite', (store) => store.delete(id));
    },
    clear() {
      return run('readwrite', (store) => store.clear());
    },

    /*
     * Send everything, oldest first. Stops at the first change that can't be
     * sent right now (no internet, logged out, server asleep) and keeps it.
     * Changes the server refuses for good (e.g. the task was deleted on
     * another device) are dropped and reported back.
     *
     * Returns { synced, failed: [{label, error}], left, stopped }
     * stopped: '' | 'offline' | 'auth' | 'server'
     */
    replay(options) {
      const csrf = options && options.csrf;
      const work = () => Outbox.all().then(async (items) => {
        const report = { synced: 0, failed: [], left: 0, stopped: '' };
        for (let i = 0; i < items.length; i++) {
          const op = items[i];
          const outcome = await send(op, csrf);
          if (outcome.keep) {
            report.stopped = outcome.reason;
            report.left = items.length - i;
            break;
          }
          await Outbox.remove(op.id);
          if (outcome.ok) report.synced += 1;
          else report.failed.push({ label: op.label, error: outcome.error });
        }
        return report;
      });
      // Only one tab (or the service worker) replays at a time
      const locks = scope.navigator && scope.navigator.locks;
      return locks ? locks.request('qm-outbox', work) : work();
    },
  };

  async function send(op, freshCsrf) {
    const token = freshCsrf || op.csrf || '';
    const headers = { 'X-QM-Op': op.opId, 'X-CSRFToken': token, Accept: 'application/json, text/html' };
    let body;
    if (op.kind === 'form') {
      body = new FormData();
      (op.body || []).forEach(([name, value]) => {
        // A newer token beats the one saved with the form
        body.append(name, name === 'csrfmiddlewaretoken' && freshCsrf ? freshCsrf : value);
      });
    } else {
      headers['Content-Type'] = 'application/json';
      body = JSON.stringify(op.body || {});
    }

    let res;
    try {
      res = await fetch(op.url, { method: 'POST', body, headers, credentials: 'same-origin', redirect: 'follow' });
    } catch (err) {
      return { keep: true, reason: 'offline' };
    }

    // Sent to the login page: the session ended. Keep it until they log in again.
    if (new URL(res.url, scope.location.href).pathname.startsWith('/login')) return { keep: true, reason: 'auth' };
    if (res.status === 403) return { keep: true, reason: 'auth' };
    if (res.status >= 500 || res.status === 429) return { keep: true, reason: 'server' };
    if (res.status === 404) return { ok: false, error: 'It was deleted somewhere else.' };

    const type = res.headers.get('Content-Type') || '';
    if (type.includes('application/json')) {
      const data = await res.json().catch(() => ({}));
      if (res.ok && data.success !== false) return { ok: true };
      return { ok: false, error: data.error || 'The server said no.' };
    }
    // A form that worked redirects (e.g. back to the task list)
    if (res.ok && res.redirected) return { ok: true };
    return { ok: false, error: 'Some details need fixing. Please try it again.' };
  }

  scope.QMOutbox = Outbox;
})(typeof self !== 'undefined' ? self : window);
