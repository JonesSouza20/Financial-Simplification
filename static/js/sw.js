// Service worker mínimo: permite instalar o sistema como aplicativo.
// Não guarda páginas nem dados financeiros em cache (funcionamento offline fora do escopo).
self.addEventListener("install", function () { self.skipWaiting(); });
self.addEventListener("activate", function (event) { event.waitUntil(self.clients.claim()); });
self.addEventListener("fetch", function () { /* sempre a rede */ });
