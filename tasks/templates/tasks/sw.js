{% load static %}/*
 * Quantum Manager service worker.
 *
 * Served from /sw.js (the site root) so it controls every page.
 * Strategy:
 *   - Pages (HTML): network first, and a copy is saved. With no connection
 *     the saved copy shows instead, so the app still opens offline.
 *   - Forms sent with no connection (add / edit / delete a task, notes):
 *     saved in the outbox (outbox.js) and sent later, in order.
 *   - /api/..., admin, auth pages: never cached, always network.
 *   - Static files (/static/...): cache first. They have hashed names in
 *     production, so a new deploy means new URLs.
 */
importScripts('{% static "tasks/outbox.js" %}');

const CACHE_VERSION = 'qm-v12';
const STATIC_CACHE = `${CACHE_VERSION}-static`;
const PAGES_CACHE = `${CACHE_VERSION}-pages`;
const OFFLINE_URL = '/offline/';
const SYNC_TAG = 'qm-outbox';

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(STATIC_CACHE)
            .then((cache) => cache.add(new Request(OFFLINE_URL, { cache: 'reload' })))
            .catch((err) => console.warn('Could not pre-cache offline page', err))
    );
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) => Promise.all(
            keys.filter((key) => !key.startsWith(CACHE_VERSION)).map((key) => caches.delete(key))
        )).then(() => self.clients.claim())
    );
});

function isNeverCached(url) {
    return url.pathname.startsWith('/api/')
        || url.pathname.startsWith('/admin/')
        || url.pathname.startsWith('/api-auth/')
        || url.pathname.startsWith('/media/');
}

// Pages that are about logging in or one-time links: never saved for offline
const NO_SAVE = /^\/(login|logout|register|verify-email|verification-sent|resend-verification|forgot-password|reset-password|reset-link-sent|share|offline)\b/;

// Forms that can be sent later, and where to land after saving one offline
const QUEUEABLE = [
    { path: /^\/$/, label: 'New task', land: '/' },
    { path: /^\/create\/$/, label: 'New task', land: '/' },
    { path: /^\/update\/\d+\/$/, label: 'Task edit', land: '/' },
    { path: /^\/delete\/\d+\/$/, label: 'Delete task', land: '/' },
    { path: /^\/notes\/create\/$/, label: 'New note', land: '/notes/' },
    { path: /^\/notes\/\d+\/update\/$/, label: 'Note edit', land: '/notes/' },
];

function savePage(request, response) {
    // Only real pages (not a bounce to the login page, not someone else's redirect)
    const finalUrl = new URL(response.url || request.url);
    // Calendar files (.ics) are downloads, not pages
    if (!response.ok || response.type !== 'basic' || NO_SAVE.test(finalUrl.pathname) || finalUrl.pathname.endsWith('.ics')) return;
    const copy = response.clone();
    caches.open(PAGES_CACHE).then((cache) => cache.put(request.url, copy));
}

async function offlinePage(request) {
    const cache = await caches.open(PAGES_CACHE);
    // The exact page first, then the same page without filters (?category=...)
    return (await cache.match(request.url))
        || (await cache.match(request.url, { ignoreSearch: true }))
        || (await caches.match(OFFLINE_URL))
        || new Response('<h1>Offline</h1><p>Check your internet connection and try again.</p>',
            { headers: { 'Content-Type': 'text/html' } });
}

async function queueForm(request, rule) {
    const form = await request.formData();
    const body = [];
    form.forEach((value, name) => {
        // An empty file box isn't worth saving
        if (value instanceof File && !value.size) return;
        body.push([name, value]);
    });
    const title = form.get('title');
    await self.QMOutbox.add({
        url: request.url,
        kind: 'form',
        body,
        csrf: form.get('csrfmiddlewaretoken') || '',
        label: title ? `${rule.label}: ${String(title).slice(0, 60)}` : rule.label,
    });
    if (self.registration.sync) {
        try { await self.registration.sync.register(SYNC_TAG); } catch (e) { /* the page will sync instead */ }
    }
    return Response.redirect(new URL(`${rule.land}?queued=1`, self.location.origin).href, 303);
}

self.addEventListener('fetch', (event) => {
    const request = event.request;
    const url = new URL(request.url);
    if (url.origin !== self.location.origin) return;

    // A form sent with no connection: keep it and send it later
    if (request.method === 'POST' && request.mode === 'navigate') {
        const rule = QUEUEABLE.find((r) => r.path.test(url.pathname));
        if (!rule) return;
        const copy = request.clone();
        event.respondWith(fetch(request).catch(() => queueForm(copy, rule)));
        return;
    }

    if (request.method !== 'GET') return;
    if (isNeverCached(url)) return;

    // Static assets: cache first
    if (url.pathname.startsWith('/static/')) {
        event.respondWith(
            caches.match(request).then((cached) => cached || fetch(request).then((response) => {
                if (response.ok) {
                    const copy = response.clone();
                    caches.open(STATIC_CACHE).then((cache) => cache.put(request, copy));
                }
                return response;
            }))
        );
        return;
    }

    if (request.mode === 'navigate') {
        // Shared from another app while offline: open the saved New task page with the text
        if (url.pathname === '/share/') {
            event.respondWith(fetch(request).catch(() => {
                const text = url.searchParams.get('text') || '';
                const title = url.searchParams.get('title') || text.split('\n')[0] || url.searchParams.get('url') || '';
                return Response.redirect(new URL(`/create/?${new URLSearchParams({ title, notes: text })}`, self.location.origin).href, 303);
            }));
            return;
        }
        // Pages: network first (and save a copy), the saved copy when offline
        event.respondWith(
            fetch(request).then((response) => { savePage(request, response); return response; })
                .catch(() => offlinePage(request))
        );
    }
});

// Background Sync (Chrome / Edge / Android): send the outbox when the
// connection comes back, even if the app was closed by then.
self.addEventListener('sync', (event) => {
    if (event.tag !== SYNC_TAG) return;
    event.waitUntil(self.QMOutbox.replay().then(async (report) => {
        const windows = await self.clients.matchAll({ type: 'window' });
        windows.forEach((win) => win.postMessage({ type: 'OUTBOX_SYNCED', report }));
        // Still no connection: throwing asks the browser to try again later
        if (report.stopped === 'offline' || report.stopped === 'server') throw new Error('retry later');
    }));
});

// Pages talk to the worker: save pages for offline use, or wipe them on log out
self.addEventListener('message', (event) => {
    const data = event.data || {};
    if (data.type === 'WARM_PAGES' && Array.isArray(data.urls)) {
        event.waitUntil(Promise.all(data.urls.map((path) => {
            const request = new Request(new URL(path, self.location.origin).href, { credentials: 'same-origin' });
            return fetch(request).then((response) => savePage(request, response)).catch(() => {});
        })));
    }
    if (data.type === 'CLEAR_PAGES') {
        event.waitUntil(caches.delete(PAGES_CACHE));
    }
});

// The page asks the worker to show alarms, because Android Chrome does not
// allow `new Notification()` from a page.
self.addEventListener('message', (event) => {
    const data = event.data || {};
    if (data.type === 'SHOW_ALARM') {
        event.waitUntil(self.registration.showNotification(data.title, data.options));
    }
});

self.addEventListener('push', (event) => {
    let data = {};
    try { data = event.data ? event.data.json() : {}; } catch (e) { data = { body: event.data && event.data.text() }; }
    const options = {
        body: data.body || '',
        icon: '/static/tasks/icons/icon-192x192.png',
        badge: '/static/tasks/icons/logo-mark.png',
        tag: data.tag || undefined,
        renotify: !!data.tag,
        requireInteraction: !!data.requireInteraction,
        vibrate: [300, 120, 300, 120, 500],
        data: { url: data.url || '/', token: data.actionToken || '' },
    };
    if (data.actionToken) {
        options.actions = data.wakeCheck
            ? [{ action: 'snooze', title: 'Snooze 10 min' }] // must be stopped in the app
            : [
                { action: 'snooze', title: 'Snooze 10 min' },
                { action: 'dismiss', title: 'Got it' },
            ];
        if (data.wakeCheck) options.body = `${options.body} · Open Quantum to stop it`;
    }
    event.waitUntil(self.registration.showNotification(data.title || 'Quantum Manager', options));
});

function openPage(target) {
    return self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windows) => {
        for (const win of windows) {
            if ('focus' in win) {
                if ('navigate' in win) win.navigate(target);
                return win.focus();
            }
        }
        return self.clients.openWindow(target);
    });
}

self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    const data = event.notification.data || {};
    const target = data.url || '/';
    if ((event.action === 'snooze' || event.action === 'dismiss') && data.token) {
        // Buttons on the notification work without opening the app
        event.waitUntil(
            fetch('/api/alarm-action/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token: data.token, action: event.action }),
            }).catch(() => openPage(target))
        );
        return;
    }
    event.waitUntil(openPage(target));
});
