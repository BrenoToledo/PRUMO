// Tema do Prumo: Automático (segue o sistema, padrão), Claro ou Escuro. A escolha fica no navegador.
(function () {
  const CHAVE = "prumo-tema";
  const VALORES = ["auto", "claro", "escuro"];

  function ler() {
    try {
      const valor = localStorage.getItem(CHAVE);
      return VALORES.includes(valor) ? valor : "auto";
    } catch (erro) {
      return "auto"; // aba privada ou armazenamento bloqueado: segue o sistema
    }
  }

  function aplicar(valor) {
    if (valor === "claro" || valor === "escuro") {
      document.documentElement.dataset.tema = valor;
    } else {
      delete document.documentElement.dataset.tema;
    }
  }

  function gravar(valor) {
    try {
      localStorage.setItem(CHAVE, valor);
    } catch (erro) {
      // sem armazenamento, a escolha vale só nesta página
    }
  }

  aplicar(ler());

  document.addEventListener("DOMContentLoaded", function () {
    const seletor = document.querySelector("select[data-tema-seletor]");
    if (!seletor) return;
    seletor.value = ler();
    seletor.addEventListener("change", function () {
      gravar(seletor.value);
      aplicar(seletor.value);
    });
  });
})();
