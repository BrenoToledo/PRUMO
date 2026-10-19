// Modo foco (M08): timer regressivo no navegador e diálogo de sair do bloco (M12).
// O término vem do servidor, calculado a partir do início real; recarregar a página não zera o tempo.
(function () {
  "use strict";

  function relogio(segundos) {
    const s = Math.max(0, Math.ceil(segundos));
    return String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0");
  }

  function iniciarTimer(timer) {
    const termino = Date.parse(timer.dataset.termino);
    const duracao = Number(timer.dataset.duracao) * 1000;
    // Diferença entre o relógio do servidor e o do aparelho, para o tempo não depender do relógio local.
    const desvio = Date.parse(timer.dataset.agora) - Date.now();
    const tempo = timer.querySelector("[data-tempo]");
    const legenda = timer.querySelector("[data-legenda]");
    const arco = timer.querySelector("[data-arco]");
    let intervalo = null;

    function atualizar() {
      const restante = Math.max(0, termino - (Date.now() + desvio));
      const texto = relogio(restante / 1000);
      tempo.textContent = texto;
      arco.setAttribute("stroke-dashoffset", (100 - (100 * restante) / duracao).toFixed(2));
      document.title = texto + " · Foco · Prumo";
      if (restante === 0) {
        timer.classList.add("foco__timer--fim");
        legenda.textContent = "tempo do bloco esgotado";
        if (intervalo) clearInterval(intervalo);
        intervalo = null;
      }
    }

    atualizar();
    if (!timer.classList.contains("foco__timer--fim")) intervalo = setInterval(atualizar, 1000);
    // Ao voltar para a aba, o navegador pode ter atrasado os intervalos: recalcula na hora.
    document.addEventListener("visibilitychange", function () {
      if (!document.hidden && intervalo) atualizar();
    });
  }

  function iniciarDialogoSair() {
    const dialogo = document.getElementById("dialogo-sair");
    if (!dialogo || typeof dialogo.showModal !== "function") return;
    if (dialogo.open) {
      // Sem JS o diálogo vem aberto pela URL (?sair=1); com JS vira modal de verdade.
      dialogo.close();
      dialogo.showModal();
    }
    document.querySelectorAll("[data-abrir-sair]").forEach(function (link) {
      link.addEventListener("click", function (e) {
        e.preventDefault();
        dialogo.showModal();
      });
    });
    dialogo.addEventListener("click", function (e) {
      if (e.target === dialogo) dialogo.close(); // toque fora do diálogo
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    const timer = document.querySelector("[data-timer]");
    if (timer) iniciarTimer(timer);
    iniciarDialogoSair();
  });
})();
