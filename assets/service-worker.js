/**
 * Fantasy Sports Auction — Service Worker
 *
 * Strategy: NETWORK-FIRST for everything.
 *
 * Goal: installability + future push notification capability.
 * NOT offline-first. The Reflex app uses live Firebase data and the
 * JS bundle changes on every redeploy, so serving a stale cache would
 * silently break the app. We never precache JS bundles.
 *
 * What the cache IS used for:
 *   - Fallback when the network request fails (shows cached page rather
 *     than a browser error screen, which is better UX on a shaky
 *     connection during a live auction).
 *   - Static assets that never change (icons, manifest) get a short cache
 *     so repeated installs are fast.
 *
 * skipWaiting + clients.claim ensures a new SW activates immediately on
 * redeploy — users never get stuck on an old version.
 */

const CACHE_NAME = "fantasy-auction-v1";

// Only these static assets are ever written to the cache.
// Deliberately excludes /_event, /_next/*, /chunk-*, *.js, *.mjs —
// those are Reflex's runtime bundles and MUST always come from the network.
const STATIC_ASSETS = [
  "/manifest.json",
  "/icon-192.png",
  "/icon-512.png",
  "/icon-maskable-512.png",
  "/apple-touch-icon.png",
];

// Paths whose responses we should NEVER cache — Reflex internals.
const NEVER_CACHE = [
  "/_event",
  "/ping",
  "/_upload",
  "/_health",
  "/backend",
  "/socket.io",
];

function shouldNeverCache(url) {
  const path = new URL(url).pathname;
  return NEVER_CACHE.some((prefix) => path.startsWith(prefix));
}

function isStaticAsset(url) {
  const path = new URL(url).pathname;
  return STATIC_ASSETS.includes(path);
}

// ── Install ──────────────────────────────────────────────────────────────────

self.addEventListener("install", (event) => {
  // Pre-cache only the tiny static asset list; skip JS bundles entirely.
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) =>
      // Use { cache: "reload" } so we always fetch fresh during install.
      Promise.allSettled(
        STATIC_ASSETS.map((path) =>
          fetch(path, { cache: "reload" })
            .then((res) => {
              if (res.ok) cache.put(path, res);
            })
            .catch(() => {
              // Icon/manifest not yet deployed — silently skip.
            })
        )
      )
    )
  );
  // Activate immediately — don't wait for old tabs to close.
  self.skipWaiting();
});

// ── Activate ─────────────────────────────────────────────────────────────────

self.addEventListener("activate", (event) => {
  // Delete any cache from a previous SW version.
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key !== CACHE_NAME)
            .map((key) => caches.delete(key))
        )
      )
      .then(() => self.clients.claim()) // Take control of all open tabs immediately.
  );
});

// ── Fetch ─────────────────────────────────────────────────────────────────────

self.addEventListener("fetch", (event) => {
  const { request } = event;

  // Only handle GET requests.
  if (request.method !== "GET") return;

  // Let Reflex backend paths (WebSocket upgrades, events, etc.) pass through
  // untouched — the browser handles them natively.
  if (shouldNeverCache(request.url)) return;

  if (isStaticAsset(request.url)) {
    // Static assets: cache-first with network revalidation in the background.
    event.respondWith(
      caches.match(request).then((cached) => {
        const networkFetch = fetch(request)
          .then((res) => {
            if (res.ok) {
              caches.open(CACHE_NAME).then((c) => c.put(request, res.clone()));
            }
            return res;
          })
          .catch(() => cached); // network failed → fall back to cache
        return cached || networkFetch;
      })
    );
    return;
  }

  // Everything else (HTML pages, API responses): NETWORK-FIRST.
  // Try the network; fall back to cache only on failure.
  event.respondWith(
    fetch(request)
      .then((res) => {
        // Only cache successful same-origin HTML responses.
        if (
          res.ok &&
          res.type === "basic" &&
          res.headers.get("content-type")?.includes("text/html")
        ) {
          caches
            .open(CACHE_NAME)
            .then((c) => c.put(request, res.clone()))
            .catch(() => {});
        }
        return res;
      })
      .catch(() =>
        // Network completely unavailable → serve cached page if we have one.
        caches.match(request).then(
          (cached) =>
            cached ||
            new Response(
              "<h1>You are offline</h1><p>The Fantasy Auction app requires a live connection.</p>",
              { headers: { "Content-Type": "text/html" } }
            )
        )
      )
  );
});

// ── Push notifications (placeholder — no-op until backend sends pushes) ──────

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
