// Mensagem de follow-up (M24): o botão diz em qual app abre e o "Copiar" do Teams.
(function () {
  "use strict";
  var abrir = document.querySelector("[data-abrir]");
  document.querySelectorAll('input[name="canal"]').forEach(function (radio) {
    radio.addEventListener("change", function () {
      if (abrir && radio.checked) abrir.textContent = "Abrir no " + radio.dataset.rotulo;
    });
  });
  document.querySelectorAll("[data-copiar]").forEach(function (botao) {
    botao.addEventListener("click", function () {
      var campo = document.querySelector(botao.dataset.copiar);
      if (!campo || !navigator.clipboard) return;
      navigator.clipboard.writeText(campo.value).then(
        function () { botao.textContent = "Copiado"; },
        function () { campo.select(); }
      );
    });
  });
})();
