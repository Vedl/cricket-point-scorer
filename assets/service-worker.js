/**
 * Fantasy Sports Auction — Service Worker (minimal, non-caching).
 *
 * This app is LIVE-DATA and its JS bundles are content-hashed and change on every
 * redeploy, so caching responses is pure risk: a stale HTML shell points at bundle
 * filenames that no longer exist, and (worse) a network hiccup during a Render free-tier
 * cold start could make us answer a *script* request with an offline *HTML* page —
 * which the browser then fails to parse, leaving a black screen.
 *
 * So we deliberately do NOT cache anything. The SW exists only to:
 *   1. satisfy PWA installability (a fetch handler must be present), and
 *   2. receive Web Push + handle notification clicks.
 *
 * Assets, scripts, styles and API calls are NOT intercepted at all — they go straight
 * to the network via the browser's default handling. Only top-level navigations are
 * handled, and only to provide a tiny offline message on total network failure (never a
 * cached, possibly-stale shell).
 *
 * skipWaiting + clients.claim + deleting ALL old caches on activate means deploying this
 * version self-heals any device still holding the previous caching SW: on the next
 * navigation the browser fetches this script, activates it immediately, and purges the
 * poisoned caches.
 */

const SW_VERSION = "v2-nocache";

// ── Install: take over as soon as possible, precache nothing. ────────────────────────
self.addEventListener("install", () => {
  self.skipWaiting();
});

// ── Activate: purge EVERY cache from any previous SW, then claim open tabs. ──────────
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

// ── Fetch: never cache. Only handle top-level navigations (for an offline fallback);
//    everything else (scripts, styles, assets, /_event, API) is left to the browser. ──
self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;
  if (request.mode !== "navigate") return; // do NOT touch assets/scripts/styles/APIs

  event.respondWith(
    fetch(request).catch(
      () =>
        new Response(
          "<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>" +
            "<body style='background:#08080c;color:#f4f5fb;font-family:Inter,system-ui,sans-serif;" +
            "display:flex;min-height:100vh;align-items:center;justify-content:center;text-align:center;padding:2rem'>" +
            "<div><h1 style='font-weight:700'>You're offline</h1>" +
            "<p style='color:#9aa0b8'>The Fantasy Auction needs a live connection. Reconnect and reload.</p></div>",
          { headers: { "Content-Type": "text/html; charset=utf-8" } }
        )
    )
  );
});

// ── Web Push ─────────────────────────────────────────────────────────────────────────
self.addEventListener("push", (event) => {
  const data = event.data?.json() ?? {};
  const title = data.title ?? "Fantasy Auction";
  const options = {
    body: data.body ?? "Something happened in your auction room.",
    icon: "/icon-192.png",
    badge: "/icon-192.png",
    data: { url: data.url ?? "/" },
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = event.notification.data?.url ?? "/";
  event.waitUntil(clients.openWindow(url));
});
