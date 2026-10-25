// Pessoas no clarificar (M16): remover um chip e limpar a busca depois de escolher alguém.
(function () {
  "use strict";
  document.addEventListener("click", function (evento) {
    var remover = evento.target.closest("[data-remover-pessoa]");
    if (remover) {
      var busca = document.getElementById("busca-pessoa");
      remover.closest(".chip-pessoa").remove();
      if (busca) busca.focus();
      return;
    }
    var escolher = evento.target.closest("[data-escolher-pessoa]");
    if (escolher) {
      var campo = document.getElementById("busca-pessoa");
      var resultado = document.getElementById("resultado-pessoas");
      if (campo) campo.value = "";
      if (resultado) {
        window.setTimeout(function () { resultado.replaceChildren(); }, 0);
      }
    }
  });
})();
