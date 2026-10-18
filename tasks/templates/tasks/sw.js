/*
 * Quantum Manager service worker.
 *
 * Served from /sw.js (the site root) so it controls every page.
 * Strategy:
 *   - Pages (HTML): network first. Fresh tasks always win; the cached
 *     offline page only shows when there is no connection.
 *   - /api/..., POSTs, admin, auth pages: never cached, always network.
 *   - Static files (/static/...): cache first. They have hashed names in
 *     production, so a new deploy means new URLs.
 */
const CACHE_VERSION = 'qm-v4';
const STATIC_CACHE = `${CACHE_VERSION}-static`;
const OFFLINE_URL = '/offline/';

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

self.addEventListener('fetch', (event) => {
    const request = event.request;
    if (request.method !== 'GET') return;

    const url = new URL(request.url);
    if (url.origin !== self.location.origin) return;
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

    // Pages: network first, offline page as the fallback
    if (request.mode === 'navigate') {
        event.respondWith(
            fetch(request).catch(() => caches.match(OFFLINE_URL).then((cached) => cached || new Response(
                '<h1>Offline</h1><p>Check your internet connection and try again.</p>',
                { headers: { 'Content-Type': 'text/html' } }
            )))
        );
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
        badge: '/static/tasks/icons/icon-96x96.png',
        tag: data.tag || undefined,
        renotify: !!data.tag,
        requireInteraction: !!data.requireInteraction,
        vibrate: [300, 120, 300, 120, 500],
        data: { url: data.url || '/', token: data.actionToken || '' },
    };
    if (data.actionToken) {
        options.actions = [
            { action: 'snooze', title: 'Snooze 10 min' },
            { action: 'dismiss', title: 'Got it' },
        ];
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
