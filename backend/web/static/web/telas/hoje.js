// Hoje no desktop (D01): a tecla F inicia o foco no próximo bloco, como o botão "Iniciar foco · F".
(function () {
  "use strict";

  function digitando(alvo) {
    if (!alvo) return false;
    return alvo.isContentEditable || alvo.tagName === "INPUT" || alvo.tagName === "TEXTAREA" || alvo.tagName === "SELECT";
  }

  document.addEventListener("keydown", function (e) {
    if (e.key !== "f" && e.key !== "F") return;
    if (e.ctrlKey || e.metaKey || e.altKey || e.isComposing || e.repeat || digitando(e.target)) return;
    if (document.querySelector("dialog[open]")) return; // captura aberta: a tecla é texto
    const form = document.getElementById("iniciar-proximo");
    if (!form || form.offsetParent === null) return; // só quando o botão está visível (desktop)
    e.preventDefault();
    form.requestSubmit();
  });
})();
