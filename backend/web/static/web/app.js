// Comportamentos pequenos da interface: folha de captura (e Ctrl+K), Enter para salvar e aviso temporário.
(function () {
  "use strict";

  function aviso(texto) {
    const el = document.getElementById("aviso");
    if (!el) return;
    el.textContent = texto;
    el.hidden = false;
    clearTimeout(el._timer);
    el._timer = setTimeout(function () { el.hidden = true; }, 2500);
  }

  function campo() {
    return document.getElementById("id_texto");
  }

  document.addEventListener("DOMContentLoaded", function () {
    const folha = document.getElementById("folha-captura");
    function abrirCaptura() {
      if (!folha.open) folha.showModal();
      const c = campo();
      if (c) c.focus();
    }
    if (folha) {
      document.querySelectorAll("#abrir-captura, [data-abrir-captura]").forEach(function (botao) {
        botao.addEventListener("click", abrirCaptura);
      });
      folha.addEventListener("click", function (e) {
        if (e.target === folha) folha.close(); // toque fora da folha
      });
      // Ctrl+K (⌘K no Mac) abre a captura em qualquer tela (D01).
      document.addEventListener("keydown", function (e) {
        if ((e.ctrlKey || e.metaKey) && !e.altKey && e.key.toLowerCase() === "k") {
          e.preventDefault();
          abrirCaptura();
        }
      });
    }

    // Enter salva; Shift+Enter quebra a linha.
    document.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing && e.target === campo()) {
        e.preventDefault();
        e.target.form.requestSubmit();
      }
    });

    document.body.addEventListener("capturado", function (e) {
      if (folha) folha.close();
      aviso(e.detail.mensagem);
    });

    const inicial = document.getElementById("aviso");
    if (inicial && inicial.textContent.trim()) aviso(inicial.textContent.trim());
  });

  // Avisos temporários na lista (ex.: "Item descartado · Desfazer") somem sozinhos.
  document.addEventListener("htmx:load", function (e) {
    const el = e.detail.elt;
    if (el && el.dataset && el.dataset.someEm) {
      setTimeout(function () {
        if (el.isConnected) el.remove();
      }, Number(el.dataset.someEm));
    }
  });

  // Erro de validação (422) também troca o formulário, para mostrar a mensagem.
  document.addEventListener("htmx:beforeSwap", function (e) {
    if (e.detail.xhr.status === 422) {
      e.detail.shouldSwap = true;
      e.detail.isError = false;
    }
  });
  document.addEventListener("htmx:afterSwap", function () {
    const folha = document.getElementById("folha-captura");
    const c = campo();
    if (folha && folha.open && c) c.focus();
  });
})();
