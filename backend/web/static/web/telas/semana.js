// Arrastar na tela Semana (D04, #81 e #101), no computador. Tudo vai às mesmas rotas dos botões e troca o
// #semana pela resposta, via HTMX.
// - Proposta: soltar uma tarefa em outro dia (ou em "Não couberam") move; em cima de outra tarefa, troca as duas.
// - Semana planejada: soltar um bloco num horário da grade move (de 15 em 15 min); em cima de outro bloco, troca.
(function () {
  "use strict";
  const PASSO_MIN = 15;
  const DESKTOP = globalThis.matchMedia("(min-width: 1024px)");
  let arrastada = null;
  let pegouEm = 0; // distância do ponteiro ao topo do bloco, para o bloco cair onde o topo está

  function semana() {
    return document.getElementById("semana");
  }

  function enviar(url, valores) {
    const raiz = semana();
    if (!raiz || !globalThis.htmx) return;
    valores.data = raiz.dataset.data;
    valores.visao = raiz.dataset.visao;
    globalThis.htmx.ajax("POST", url, { source: raiz, target: "#semana", swap: "outerHTML", values: valores });
  }

  function limparDestaque(exceto) {
    document.querySelectorAll(".solta-aqui").forEach(function (el) {
      if (el !== exceto) el.classList.remove("solta-aqui");
    });
  }

  function minutos(texto) {
    const [h, m] = texto.split(":").map(Number);
    return h * 60 + m;
  }

  function hora(total) {
    const h = Math.floor(total / 60), m = total % 60;
    return String(h).padStart(2, "0") + ":" + String(m).padStart(2, "0");
  }

  // Hora em que o topo do bloco cai na grade do dia; sem a grade (celular), fica a mesma hora.
  function horaNaGrade(dia, e) {
    const agenda = dia.querySelector(".dia__agenda");
    const grade = dia.closest(".grade");
    if (!DESKTOP.matches || !agenda || !grade) return arrastada.dataset.hora;
    const caixa = agenda.getBoundingClientRect();
    const total = Number(getComputedStyle(grade).getPropertyValue("--grade-min")) || 0;
    if (!caixa.height || !total) return arrastada.dataset.hora;
    const y = Math.min(Math.max(e.clientY - pegouEm - caixa.top, 0), caixa.height);
    const passo = Math.round((y / caixa.height) * total / PASSO_MIN) * PASSO_MIN;
    return hora(minutos(grade.dataset.gradeIni) + passo);
  }

  document.addEventListener("dragstart", function (e) {
    const item = e.target.closest?.(".tarefa-semana[data-tarefa], .tarefa-semana[data-bloco]");
    if (!item) return;
    arrastada = item;
    pegouEm = e.clientY - item.getBoundingClientRect().top;
    item.classList.add("arrastando");
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", item.dataset.tarefa || item.dataset.bloco);
  });

  document.addEventListener("dragend", function () {
    arrastada?.classList.remove("arrastando");
    arrastada = null;
    limparDestaque(null);
  });

  function destino(e) {
    if (!arrastada) return null;
    const seletor = arrastada.dataset.bloco ? "[data-bloco]" : "[data-tarefa]";
    const outro = e.target.closest?.(".tarefa-semana" + seletor);
    if (outro && outro !== arrastada) return outro;
    return e.target.closest?.("[data-dia]") || null;
  }

  document.addEventListener("dragover", function (e) {
    const alvo = destino(e);
    if (!alvo) return;
    e.preventDefault();
    limparDestaque(alvo);
    alvo.classList.add("solta-aqui");
  });

  document.addEventListener("drop", function (e) {
    const alvo = destino(e);
    const raiz = semana();
    if (!alvo || !raiz) return;
    e.preventDefault();
    if (arrastada.dataset.bloco) {
      if (alvo.dataset.bloco) {
        enviar(raiz.dataset.trocarBlocos, { a: arrastada.dataset.bloco, b: alvo.dataset.bloco });
        return;
      }
      const url = arrastada.querySelector("form")?.getAttribute("action");
      if (url) enviar(url, { dia: alvo.dataset.dia, hora: horaNaGrade(alvo, e) });
      return;
    }
    const de = arrastada.dataset.de;
    if (alvo.dataset.tarefa) {
      if (alvo.dataset.de === de) return;
      enviar(raiz.dataset.trocar, { a: arrastada.dataset.tarefa, de_a: de, b: alvo.dataset.tarefa, de_b: alvo.dataset.de });
      return;
    }
    if (de === alvo.dataset.dia) return;
    enviar(raiz.dataset.mover, { tarefa: arrastada.dataset.tarefa, de: de, para: alvo.dataset.dia });
  });
})();
