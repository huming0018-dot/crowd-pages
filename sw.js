const DB_NAME = "crowd-share-db";
const STORE = "pending";

function openDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(STORE, { autoIncrement: true });
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function stashShare(payload) {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    tx.objectStore(STORE).add(payload);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

self.addEventListener("install", (e) => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(clients.claim()));

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "POST") return;

  event.respondWith((async () => {
    try {
      const fd = await req.formData();
      const text = [fd.get("title"), fd.get("text"), fd.get("url")]
        .filter(Boolean).join(" ").slice(0, 2000);
      await stashShare({ text, at: Date.now() });
      return Response.redirect("submit.html?share=1", 303);
    } catch (e) {
      return Response.redirect("submit.html?share=err", 303);
    }
  })());
});
