// Captura por áudio (M03): grava com MediaRecorder e envia ao servidor; a resposta (processando ou itens) entra na tela.
// Toque para gravar e toque para terminar, ou segure e solte. Sem microfone, fica o envio de arquivo.
(function () {
  "use strict";

  const SEGURAR_MS = 600;
  const MAXIMO_MS = 120000;

  function relogio(ms) {
    const s = Math.floor(ms / 1000);
    return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
  }

  function csrf() {
    const campo = document.querySelector("input[name=csrfmiddlewaretoken]");
    return campo ? campo.value : "";
  }

  function iniciar(painel) {
    const mic = painel.querySelector("[data-mic]");
    const rotulo = painel.querySelector("[data-mic-rotulo]");
    const estado = painel.querySelector("[data-estado]");
    const dica = painel.querySelector("[data-dica]");
    const barras = Array.from(painel.querySelectorAll("[data-onda] span"));
    const destino = document.getElementById("audio-resultado");
    let gravador = null;
    let partes = [];
    let inicio = 0;
    let relogioId = null;
    let limiteId = null;
    let analisador = null;
    let segurando = false;

    if (!navigator.mediaDevices || !window.MediaRecorder) return; // fica o envio de arquivo
    painel.setAttribute("data-com-microfone", "");

    function onda() {
      if (!analisador || !gravador) return;
      const dados = new Uint8Array(analisador.frequencyBinCount);
      analisador.getByteFrequencyData(dados);
      const passo = Math.floor(dados.length / barras.length) || 1;
      barras.forEach(function (barra, i) {
        barra.style.height = Math.max(15, Math.min(100, (dados[i * passo] / 255) * 140)) + "%";
      });
      requestAnimationFrame(onda);
    }

    function mostrar(html) {
      destino.innerHTML = html;
      if (window.htmx) window.htmx.process(destino);
    }

    function enviar(blob) {
      estado.textContent = "Enviando…";
      const dados = new FormData();
      const tipo = (blob.type || "audio/webm").split(";")[0];
      dados.append("audio", blob, "audio." + (tipo.split("/")[1] || "webm"));
      fetch(painel.dataset.enviar, {
        method: "POST",
        body: dados,
        headers: { "X-CSRFToken": csrf(), "HX-Request": "true" },
        credentials: "same-origin",
      })
        .then(function (resposta) { return resposta.text(); })
        .then(function (html) {
          painel.hidden = true;
          mostrar(html);
        })
        .catch(function () {
          estado.textContent = "Não deu para enviar. Toque para gravar de novo";
        });
    }

    function parar() {
      if (!gravador || gravador.state === "inactive") return;
      gravador.stop();
    }

    function comecar() {
      navigator.mediaDevices.getUserMedia({ audio: true }).then(function (fluxo) {
        partes = [];
        gravador = new MediaRecorder(fluxo);
        gravador.addEventListener("dataavailable", function (e) { if (e.data.size) partes.push(e.data); });
        gravador.addEventListener("stop", function () {
          fluxo.getTracks().forEach(function (t) { t.stop(); });
          clearInterval(relogioId);
          clearTimeout(limiteId);
          painel.removeAttribute("data-gravando");
          mic.setAttribute("aria-pressed", "false");
          rotulo.textContent = "Gravar";
          const blob = new Blob(partes, { type: gravador.mimeType || "audio/webm" });
          gravador = null;
          analisador = null;
          if (blob.size) enviar(blob);
        });
        const Contexto = window.AudioContext || window.webkitAudioContext;
        if (Contexto) {
          const contexto = new Contexto();
          analisador = contexto.createAnalyser();
          analisador.fftSize = 64;
          contexto.createMediaStreamSource(fluxo).connect(analisador);
        }
        gravador.start();
        inicio = Date.now();
        painel.setAttribute("data-gravando", "");
        mic.setAttribute("aria-pressed", "true");
        rotulo.textContent = "Terminar";
        estado.textContent = "Gravando · 0:00";
        dica.textContent = segurando ? "Solte para terminar" : "Toque para terminar";
        relogioId = setInterval(function () { estado.textContent = "Gravando · " + relogio(Date.now() - inicio); }, 250);
        limiteId = setTimeout(parar, MAXIMO_MS);
        onda();
      }).catch(function () {
        estado.textContent = "Sem acesso ao microfone";
        dica.textContent = "Libere o microfone no navegador ou envie um arquivo de áudio.";
        painel.removeAttribute("data-com-microfone");
      });
    }

    // Segurar: pointerdown começa e soltar depois de SEGURAR_MS termina. Toque curto alterna (e o teclado também).
    mic.addEventListener("pointerdown", function (e) {
      if (gravador) return;
      e.preventDefault();
      segurando = true;
      comecar();
    });
    mic.addEventListener("pointerup", function () {
      if (!segurando) return;
      segurando = false;
      if (gravador && Date.now() - inicio > SEGURAR_MS) parar();
      else dica.textContent = "Toque para terminar";
    });
    mic.addEventListener("click", function (e) {
      if (e.detail !== 0) {
        // clique de ponteiro: o pointerdown já começou; um segundo toque termina
        if (gravador && !segurando && Date.now() - inicio > 300) parar();
        return;
      }
      if (gravador) parar();
      else comecar();
    });
  }

  document.querySelectorAll("[data-gravador]").forEach(iniciar);
})();
