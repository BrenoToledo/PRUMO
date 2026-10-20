// Modo foco (M08): timer regressivo no navegador, anotar distração (M09) e sair do bloco (M12).
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

  // Diálogos do foco: sair do bloco (M12) e anotar distração (M09). Sem JS, abrem pela URL (?sair=1, ?anotar=1).
  function iniciarDialogo(dialogo) {
    if (typeof dialogo.showModal !== "function") return;
    if (dialogo.open) {
      // Veio aberto pela URL; com JS vira modal de verdade.
      dialogo.close();
      dialogo.showModal();
    }
    document.querySelectorAll('[data-abrir="' + dialogo.id + '"]').forEach(function (link) {
      link.addEventListener("click", function (e) {
        e.preventDefault();
        dialogo.showModal();
      });
    });
    dialogo.addEventListener("click", function (e) {
      if (e.target === dialogo) dialogo.close(); // toque fora do diálogo
    });
  }

  // Distração anotada (resposta do HTMX): fecha o campo e volta ao foco; o timer nunca parou.
  document.body.addEventListener("distracao-anotada", function () {
    const dialogo = document.getElementById("dialogo-distracao");
    if (dialogo && dialogo.open) dialogo.close();
  });

  // Fim do bloco (M11): botões − e + dos blocos restantes. Delegado no documento porque o formulário
  // pode ser trocado pelo HTMX (erro de validação).
  document.addEventListener("click", function (e) {
    const botao = e.target.closest("[data-passo]");
    if (!botao) return;
    const campo = botao.closest("[data-contador]").querySelector("input");
    const minimo = Number(campo.min || 0);
    const maximo = Number(campo.max || 20);
    const valor = Number(campo.value || 0) + Number(botao.dataset.passo);
    campo.value = String(Math.min(maximo, Math.max(minimo, valor)));
  });

  document.addEventListener("DOMContentLoaded", function () {
    const timer = document.querySelector("[data-timer]");
    if (timer) iniciarTimer(timer);
    document.querySelectorAll("dialog[id^=dialogo-]").forEach(iniciarDialogo);
  });
})();
