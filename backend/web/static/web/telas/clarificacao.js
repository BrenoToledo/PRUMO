// Pessoas no clarificar (M16): remover um chip e limpar a busca depois de escolher alguém.
(function () {
  "use strict";
  document.addEventListener("click", function (evento) {
    var remover = evento.target.closest("[data-remover-pessoa]");
    if (remover) {
      remover.closest(".chip-pessoa").remove();
      document.getElementById("busca-pessoa")?.focus();
      return;
    }
    if (!evento.target.closest("[data-escolher-pessoa]")) return;
    var campo = document.getElementById("busca-pessoa");
    if (campo) campo.value = "";
    globalThis.setTimeout(function () {
      document.getElementById("resultado-pessoas")?.replaceChildren();
    }, 0);
  });
})();
