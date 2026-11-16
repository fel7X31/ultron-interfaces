// As listas do painel: Tarefas (o tarefas.md), Lembretes (o lembretes.md), Timers e Copiados. Cada uma também
// atualiza o seu número no menu e o seu cartão no Início.
(() => {
  const B = window.Barra;
  let timers = [], relogioDosTimers = null;

  const resumo = (nome, texto) => {
    const alvo = document.querySelector(`[data-resumo="${nome}"]`);
    if (alvo) alvo.textContent = texto;
  };

  function item({ classe = "", texto, quando = "", antes = null, depois = [] }) {
    const li = document.createElement("li");
    li.className = classe;
    if (antes) li.appendChild(antes);
    const t = document.createElement("span");
    t.className = "texto";
    t.textContent = texto;
    li.appendChild(t);
    if (quando) {
      const q = document.createElement("span");
      q.className = "quando";
      q.textContent = quando;
      li.appendChild(q);
    }
    depois.forEach((d) => li.appendChild(d));
    return li;
  }

  function botaoX(titulo, aoClicar) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "mini x";
    b.title = titulo;
    b.innerHTML = '<svg viewBox="0 0 24 24"><path d="M18 6L6 18M6 6l12 12"/></svg>';
    b.addEventListener("click", (ev) => { ev.stopPropagation(); aoClicar(); });
    return b;
  }

  async function tentar(promessa, depois) {
    try {
      const d = await promessa;
      if (depois) depois(d);
    } catch (erro) { B.toast(erro.message); }
  }

  // ---------------------------------------------------------- Tarefas
  async function carregarTarefas() {
    try {
      desenharTarefas((await B.pegar("/api/paineis")).tarefas || []);
    } catch (erro) { /* sem Ultron */ }
  }

  function desenharTarefas(tarefas) {
    const comIndice = tarefas.map((t, indice) => ({ ...t, indice }));
    const pendentes = comIndice.filter((t) => !t.feita);
    const lista = B.el("listaTarefas");
    lista.dataset.vazio = "Nenhuma tarefa. Escreva uma acima.";
    lista.replaceChildren(...[...pendentes, ...comIndice.filter((t) => t.feita)].map(itemDeTarefa));
    B.contar("tarefas", pendentes.length);
    resumo("tarefas", String(pendentes.length));
    resumo("tarefa", pendentes[0] ? pendentes[0].texto : "tudo feito");
    if (B.atual() === "tarefas") B.detalhe(`${pendentes.length} pendentes · ${tarefas.length - pendentes.length} feitas`);
  }

  function itemDeTarefa(t) {
    const marcar = document.createElement("button");
    marcar.type = "button";
    marcar.className = "marcador";
    marcar.title = t.feita ? "Desmarcar" : "Marcar como feita";
    marcar.addEventListener("click", () => mexerNaTarefa({ acao: "marcar", indice: t.indice }));
    const selos = [];
    if (t.prio) selos.push(selo("prioridade " + ({ media: "média" }[t.prio] || t.prio), t.prio === "alta" ? "alta" : ""));
    if (t.prazo) selos.push(selo("até " + t.prazo.split("-").reverse().slice(0, 2).join("/")));
    selos.push(botaoX("Apagar", () => mexerNaTarefa({ acao: "apagar", indice: t.indice })));
    return item({ classe: t.feita ? "feito" : "", texto: t.texto, antes: marcar, depois: selos });
  }

  function selo(texto, classe = "") {
    const s = document.createElement("span");
    s.className = "selo " + classe;
    s.textContent = texto;
    return s;
  }

  function mexerNaTarefa(pedido) {
    tentar(B.mandar("/api/tarefa", pedido), carregarTarefas);
  }

  // ---------------------------------------------------------- Lembretes e Timers (vêm juntos de /api/lembretes)
  async function carregarLembretes() {
    try {
      const d = await B.pegar("/api/lembretes");
      desenharLembretes(d.lembretes);
      timers = d.timers;
      desenharTimers();
    } catch (erro) { /* sem Ultron */ }
  }

  function quandoFalado(iso) {
    const [dia, hora] = iso.split(" ");
    const hoje = new Date(), amanha = new Date(Date.now() + 86400000);
    const ymd = (d) => d.toLocaleDateString("sv-SE");
    if (dia === ymd(hoje)) return "hoje " + hora;
    if (dia === ymd(amanha)) return "amanhã " + hora;
    return dia.split("-").reverse().slice(0, 2).join("/") + " " + hora;
  }

  function desenharLembretes(lembretes) {
    const pendentes = lembretes.filter((x) => !x.feito);
    const lista = B.el("listaLembretes");
    lista.dataset.vazio = "Nenhum lembrete marcado.";
    lista.replaceChildren(...lembretes.map((x) => item({
      classe: x.feito ? "feito" : "", texto: x.texto, quando: x.feito ? "avisado" : quandoFalado(x.quando),
      depois: [botaoX("Apagar", () => tentar(B.mandar("/api/lembretes/apagar", { id: x.id }), carregarLembretes))],
    })));
    B.el("limparLembretes").hidden = pendentes.length === lembretes.length;
    B.contar("lembretes", pendentes.length);
    resumo("lembretes", String(pendentes.length));
    resumo("proximo", pendentes[0] ? quandoFalado(pendentes[0].quando) + " · " + pendentes[0].texto : "nenhum marcado");
    if (B.atual() === "lembretes") B.detalhe(pendentes.length === 1 ? "1 marcado" : pendentes.length + " marcados");
  }

  function sugerirHora() {
    const d = new Date(Date.now() + 3600000);
    d.setMinutes(Math.ceil(d.getMinutes() / 5) * 5, 0, 0);
    const doisDigitos = (n) => String(n).padStart(2, "0");
    B.el("horaLembrete").value = `${d.toLocaleDateString("sv-SE")}T${doisDigitos(d.getHours())}:${doisDigitos(d.getMinutes())}`;
  }

  function criarLembrete(ev) {
    ev.preventDefault();
    const texto = B.el("textoLembrete").value.trim(), quando = B.el("horaLembrete").value;
    if (!texto || !quando) return B.toast("Escreva o que lembrar e quando.");
    tentar(B.mandar("/api/lembretes", { texto, quando }), () => {
      B.el("textoLembrete").value = "";
      B.toast("Lembrete marcado: " + quandoFalado(quando.replace("T", " ")) + ".");
      carregarLembretes();
    });
  }

  function falta(t) { return Math.max(0, Math.round(t.fim - Date.now() / 1000)); }

  function relogio(segundos) {
    const h = Math.floor(segundos / 3600), m = Math.floor((segundos % 3600) / 60), s = segundos % 60;
    const doisDigitos = (n) => String(n).padStart(2, "0");
    return (h ? h + ":" + doisDigitos(m) : m) + ":" + doisDigitos(s);
  }

  function desenharTimers() {
    const lista = B.el("listaTimers");
    lista.dataset.vazio = "Nenhum timer rodando.";
    lista.replaceChildren(...timers.map((t) => {
      const grande = document.createElement("span");
      grande.className = "relogio-grande";
      grande.dataset.timer = t.id;
      const barra = document.createElement("span");
      barra.className = "progresso";
      barra.innerHTML = "<i></i>";
      barra.dataset.timerBarra = t.id;
      const li = item({ texto: "", antes: grande,
        depois: [barra, botaoX("Cancelar", () => tentar(B.mandar("/api/timers/cancelar", { id: t.id }), carregarLembretes))] });
      li.querySelector(".texto").className = "nome";
      li.querySelector(".nome").textContent = t.rotulo;
      return li;
    }));
    B.contar("timers", timers.length);
    clearInterval(relogioDosTimers);
    relogioDosTimers = timers.length ? setInterval(atualizarTimers, 1000) : null;
    atualizarTimers();
    if (B.atual() === "timers") B.detalhe(timers.length ? timers.length + " rodando" : "");
  }

  function atualizarTimers() {
    timers.forEach((t) => {
      const grande = document.querySelector(`[data-timer="${t.id}"]`);
      const barra = document.querySelector(`[data-timer-barra="${t.id}"] i`);
      if (grande) grande.textContent = relogio(falta(t));
      if (barra) barra.style.width = (100 * falta(t) / t.segundos).toFixed(1) + "%";
    });
    resumo("timer", timers[0] ? relogio(falta(timers[0])) : "—");
    resumo("timerNome", timers[0] ? timers[0].rotulo : "nenhum rodando");
  }

  function criarTimer(segundos, nome = "") {
    if (!(segundos > 0)) return B.toast("Quantos minutos?");
    tentar(B.mandar("/api/timers", { segundos, nome }), (t) => { B.toast(t.rotulo + " começando."); carregarLembretes(); });
  }

  // ---------------------------------------------------------- Copiados
  async function carregarCopiados() {
    try {
      const itens = (await B.pegar("/api/copiados")).itens;
      const lista = B.el("listaCopiados");
      lista.dataset.vazio = "Nada copiado desde que o Ultron ligou.";
      lista.replaceChildren(...itens.map((c) => {
        const li = item({ texto: c.texto, quando: c.quando,
          depois: [botaoX("Tirar da lista", () => tentar(B.mandar("/api/copiados/apagar", { id: c.id }), carregarCopiados))] });
        li.title = "Clique pra copiar de novo";
        li.addEventListener("click", () => tentar(B.mandar("/api/copiados/copiar", { id: c.id }), () => B.toast("Copiado.")));
        return li;
      }));
      B.el("limparCopiados").hidden = !itens.length;
      B.contar("copiados", itens.length);
      if (B.atual() === "copiados") B.detalhe(itens.length ? itens.length + " textos" : "");
    } catch (erro) { /* sem Ultron */ }
  }

  // ---------------------------------------------------------- registro das seções
  B.secao("tarefas", {
    titulo: "Tarefas",
    iniciar() {
      B.el("formTarefa").addEventListener("submit", (ev) => {
        ev.preventDefault();
        const campo = B.el("novaTarefa"), texto = campo.value.trim();
        if (!texto) return;
        campo.value = "";
        mexerNaTarefa({ acao: "adicionar", texto });
      });
    },
    abrir: carregarTarefas,
    evento(e) { if (e.tipo === "paineis" || e.tipo === "conectou") carregarTarefas(); },
  });

  B.secao("lembretes", {
    titulo: "Lembretes",
    iniciar() {
      B.el("formLembrete").addEventListener("submit", criarLembrete);
      B.el("limparLembretes").addEventListener("click", () => tentar(B.mandar("/api/lembretes/limpar"), carregarLembretes));
      sugerirHora();
    },
    abrir() { sugerirHora(); carregarLembretes(); },
    evento(e) { if (e.tipo === "lembretes" || e.tipo === "conectou") carregarLembretes(); },
  });

  B.secao("timers", {
    titulo: "Timers",
    iniciar() {
      document.querySelectorAll("[data-minutos]").forEach((b) => b.addEventListener("click", () => criarTimer(b.dataset.minutos * 60)));
      B.el("formTimer").addEventListener("submit", (ev) => {
        ev.preventDefault();
        criarTimer(Math.round(Number(B.el("minutosTimer").value) * 60), B.el("nomeTimer").value.trim());
        B.el("minutosTimer").value = B.el("nomeTimer").value = "";
      });
    },
    abrir: carregarLembretes,
  });

  B.secao("copiados", {
    titulo: "Copiados",
    iniciar() {
      B.el("limparCopiados").addEventListener("click", () => tentar(B.mandar("/api/copiados/apagar", { id: "" }), carregarCopiados));
    },
    abrir: carregarCopiados,
    evento(e) { if (e.tipo === "copiados" || e.tipo === "conectou") carregarCopiados(); },
  });
})();
