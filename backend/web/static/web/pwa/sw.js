// Service worker mínimo do Prumo (#10): guarda só os arquivos estáticos (CSS, JS, fonte, ícones).
// Páginas e API vão sempre à rede: nada de dado do usuário fica em cache.
// Servido em /sw.js por web/telas/pwa.py, que troca __STATIC_URL__ pelo STATIC_URL do Django.
"use strict";

const CACHE = "prumo-estaticos-v1";
const PREFIXO_ESTATICOS = "__STATIC_URL__";

self.addEventListener("install", function () {
  self.skipWaiting();
});

self.addEventListener("activate", function (evento) {
  evento.waitUntil(
    caches.keys()
      .then(function (nomes) {
        const antigos = nomes.filter(function (nome) {
          return nome.startsWith("prumo-estaticos-") && nome !== CACHE;
        });
        return Promise.all(antigos.map(function (nome) { return caches.delete(nome); }));
      })
      .then(function () { return self.clients.claim(); })
  );
});

// Responde do cache na hora e atualiza em segundo plano (em produção os nomes têm hash e quase nunca mudam).
self.addEventListener("fetch", function (evento) {
  const pedido = evento.request;
  if (pedido.method !== "GET") return;
  const url = new URL(pedido.url);
  if (url.origin !== self.location.origin || !url.pathname.startsWith(PREFIXO_ESTATICOS)) return;

  evento.respondWith(
    caches.open(CACHE).then(function (cache) {
      return cache.match(pedido).then(function (guardada) {
        const daRede = fetch(pedido).then(function (resposta) {
          if (resposta.ok) cache.put(pedido, resposta.clone());
          return resposta;
        });
        if (guardada) {
          evento.waitUntil(daRede.catch(function () { return undefined; }));
          return guardada;
        }
        return daRede;
      });
    })
  );
});
