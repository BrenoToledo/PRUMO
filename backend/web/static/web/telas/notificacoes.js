// Web Push na M34 (#106): pede permissão, inscreve o service worker com a chave VAPID e avisa o servidor.
"use strict";

(function () {
  const caixa = document.getElementById("push");
  if (!caixa) return;
  const estado = document.getElementById("push-estado");
  const ativar = document.getElementById("push-ativar");
  const desativar = document.getElementById("push-desativar");
  const csrf = JSON.parse(document.body.getAttribute("hx-headers") || "{}")["X-CSRFToken"];

  function mostrar(texto, inscrito) {
    estado.textContent = texto;
    ativar.hidden = inscrito;
    desativar.hidden = !inscrito;
  }

  function chaveEmBytes(base64url) {
    const base64 = (base64url + "=".repeat((4 - (base64url.length % 4)) % 4)).replaceAll("-", "+").replaceAll("_", "/");
    return Uint8Array.from(atob(base64), function (c) { return c.codePointAt(0); });
  }

  function enviar(url, corpo) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
      body: JSON.stringify(corpo),
    }).then(function (resposta) {
      if (!resposta.ok) throw new Error("O servidor recusou a inscrição.");
    });
  }

  if (!("serviceWorker" in navigator) || !("PushManager" in globalThis)) {
    mostrar("Este navegador não recebe notificações. No iPhone, instale o Prumo na tela de início primeiro.", false);
    ativar.disabled = true;
    return;
  }

  navigator.serviceWorker.ready.then(function (registro) {
    return registro.pushManager.getSubscription();
  }).then(function (inscricao) {
    if (inscricao) mostrar("Ativadas neste aparelho.", true);
    else if (Notification.permission === "denied") mostrar("As notificações estão bloqueadas nas configurações do navegador.", false);
  });

  ativar.addEventListener("click", async function () {
    ativar.disabled = true;
    try {
      if (await Notification.requestPermission() !== "granted") {
        mostrar("Sem permissão, os avisos ficam só na central.", false);
        return;
      }
      const registro = await navigator.serviceWorker.ready;
      const inscricao = await registro.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: chaveEmBytes(caixa.dataset.chavePush),
      });
      await enviar(caixa.dataset.inscrever, inscricao.toJSON());
      mostrar("Ativadas neste aparelho.", true);
    } catch (erro) {
      mostrar("Não deu para ativar agora. " + erro.message, false);
    } finally {
      ativar.disabled = false;
    }
  });

  desativar.addEventListener("click", async function () {
    const registro = await navigator.serviceWorker.ready;
    const inscricao = await registro.pushManager.getSubscription();
    if (inscricao) {
      await enviar(caixa.dataset.cancelar, { endpoint: inscricao.endpoint });
      await inscricao.unsubscribe();
    }
    mostrar("Desativadas neste aparelho.", false);
  });
})();
