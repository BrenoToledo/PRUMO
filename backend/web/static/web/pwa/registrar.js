// Registra o service worker do PWA (#10). O endereço vem do atributo data-service-worker do próprio <script>.
(function () {
  "use strict";

  const script = document.currentScript;
  const endereco = script && script.dataset.serviceWorker;
  if (!endereco || !("serviceWorker" in navigator)) return;

  window.addEventListener("load", function () {
    navigator.serviceWorker.register(endereco, { scope: "/" }).catch(function (erro) {
      // Sem service worker o site funciona igual; só não fica instalável.
      console.warn("Prumo: service worker não registrado", erro);
    });
  });
})();
