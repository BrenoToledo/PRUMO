// Planejamento da semana no desktop (D04, #81): arrastar uma tarefa para outro dia ou para "Não couberam".
// Usa a mesma rota do botão "Mover" (web:mover_na_semana) e troca o #semana pela resposta, via HTMX.
(function () {
  "use strict";
  let arrastada = null;

  function alvo(el) {
    return el && el.closest ? el.closest("[data-dia]") : null;
  }

  document.addEventListener("dragstart", function (e) {
    const item = e.target.closest && e.target.closest(".tarefa-semana[data-tarefa]");
    if (!item) return;
    arrastada = item;
    item.classList.add("arrastando");
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", item.dataset.tarefa);
  });

  document.addEventListener("dragend", function () {
    if (arrastada) arrastada.classList.remove("arrastando");
    arrastada = null;
    document.querySelectorAll(".solta-aqui").forEach(function (el) { el.classList.remove("solta-aqui"); });
  });

  document.addEventListener("dragover", function (e) {
    const destino = alvo(e.target);
    if (!arrastada || !destino) return;
    e.preventDefault();
    document.querySelectorAll(".solta-aqui").forEach(function (el) { if (el !== destino) el.classList.remove("solta-aqui"); });
    destino.classList.add("solta-aqui");
  });

  document.addEventListener("drop", function (e) {
    const destino = alvo(e.target);
    const semana = document.getElementById("semana");
    if (!arrastada || !destino || !semana || !window.htmx) return;
    e.preventDefault();
    const de = arrastada.dataset.de, para = destino.dataset.dia;
    if (de === para) return;
    window.htmx.ajax("POST", semana.dataset.mover, {
      source: semana,
      target: "#semana",
      swap: "outerHTML",
      values: { tarefa: arrastada.dataset.tarefa, de: de, para: para },
    });
  });
})();
