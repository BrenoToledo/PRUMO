// Pausa (M10): timer regressivo no navegador. Ao terminar, avisa e destaca "Voltar ao foco" (M08) e "Encerrar bloco" (M11).
// Nada é gravado: o término vem do servidor e o desvio de relógio do aparelho é compensado.
(function () {
  "use strict";

  function relogio(segundos) {
    const s = Math.max(0, Math.ceil(segundos));
    return String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0");
  }

  function avisarFim() {
    if (navigator.vibrate) navigator.vibrate([200, 100, 200]);
    if ("Notification" in window && Notification.permission === "granted") {
      new Notification("Fim da pausa", { body: "Hora de voltar ao foco." });
    }
  }

  function iniciar(timer) {
    const termino = Date.parse(timer.dataset.termino);
    const desvio = Date.parse(timer.dataset.agora) - Date.now();
    const tempo = timer.querySelector("[data-tempo]");
    const legenda = timer.querySelector("[data-legenda]");
    let intervalo = null;

    function atualizar() {
      const restante = Math.max(0, termino - (Date.now() + desvio));
      const texto = relogio(restante / 1000);
      tempo.textContent = texto;
      document.title = texto + " · Pausa · Prumo";
      if (restante === 0 && intervalo !== null) {
        clearInterval(intervalo);
        intervalo = null;
        timer.classList.add("pausa__timer--fim");
        legenda.textContent = "Fim da pausa: volte ao foco ou encerre o bloco";
        document.title = "Fim da pausa · Prumo";
        avisarFim();
      }
    }

    intervalo = setInterval(atualizar, 1000);
    atualizar();
    document.addEventListener("visibilitychange", function () {
      if (!document.hidden && intervalo !== null) atualizar();
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    const timer = document.querySelector("[data-pausa]");
    if (timer) iniciar(timer);
  });
})();
