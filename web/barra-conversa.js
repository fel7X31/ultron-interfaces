// Início e Conversa: a saudação, o pedido (escrito ou falado) e a conversa recente em bolhas.
(() => {
  const B = window.Barra;
  let turnos = [];  // [{voce, resposta, quando}], do mais velho pro mais novo

  function saudar() {
    const hora = new Date().getHours();
    const oi = hora < 5 ? "Boa noite" : hora < 12 ? "Bom dia" : hora < 18 ? "Boa tarde" : "Boa noite";
    B.el("saudacao").textContent = oi + (B.dados.nome ? ", " + B.dados.nome : "") + "!";
  }

  async function carregarConversa() {
    try {
      turnos = (await B.pegar("/api/conversa")).turnos;
      desenhar();
    } catch (erro) { /* sem Ultron: fica o que já estava */ }
  }

  function bolha(texto, quem, quando) {
    const b = document.createElement("div");
    b.className = "bolha " + quem;
    b.textContent = texto;
    if (quando) {
      const hora = document.createElement("small");
      hora.textContent = B.hora(quando);
      b.appendChild(hora);
    }
    return b;
  }

  function desenhar() {
    document.querySelectorAll("[data-bolhas]").forEach((caixa) => {
      const bolhas = [];
      turnos.forEach((t) => {
        if (t.voce) bolhas.push(bolha(t.voce, "voce", t.quando));
        if (t.resposta) bolhas.push(bolha(t.resposta, t.aviso ? "aviso" : "ultron"));
      });
      caixa.replaceChildren(...bolhas.slice(-Number(caixa.dataset.bolhas)));
      caixa.scrollTop = caixa.scrollHeight;
    });
  }

  function evento(e) {
    const ultimo = turnos[turnos.length - 1];
    if (e.tipo === "voce") turnos.push({ voce: e.texto, resposta: "" });
    else if (e.tipo === "resposta" && ultimo && !ultimo.resposta) ultimo.resposta = e.texto;
    else if (e.tipo === "resposta") turnos.push({ voce: "", resposta: e.texto });
    else if (e.tipo === "alarme") turnos.push({ voce: "", resposta: e.texto, aviso: true });
    else if (e.tipo === "conectou") { saudar(); carregarConversa(); return; }
    else return;
    desenhar();
  }

  async function pedir(ev) {
    ev.preventDefault();
    const campo = ev.target.querySelector("input");
    const texto = campo.value.trim();
    if (!texto) return;
    campo.value = "";
    try { await B.mandar("/api/texto", { texto }); } catch (erro) { B.toast(erro.message); }
  }

  async function falar() {
    try {
      await B.mandar("/api/chamar");
      B.toast("Pode falar...");
    } catch (erro) { B.toast(erro.message); }
  }

  B.secao("inicio", {
    titulo: "Início",
    iniciar() {
      document.querySelectorAll("[data-pedido]").forEach((f) => f.addEventListener("submit", pedir));
      document.querySelectorAll("[data-falar]").forEach((b) => b.addEventListener("click", falar));
      saudar();
    },
    abrir() { saudar(); carregarConversa(); },
    evento,
  });
  B.secao("conversa", {
    titulo: "Conversa",
    abrir() { carregarConversa(); B.detalhe("hoje e ontem"); },
  });
})();
