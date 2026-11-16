// Configurações: tema, ícone, ouvir o nome "Ultron", responder só por escrito e quem responde (o Claude ou outra IA).
// O nome de quem responde também fica no topo do menu, embaixo do Ultron.
(() => {
  const B = window.Barra;

  function desenharChaves() {
    const c = B.dados.config;
    B.el("chaveChamado").classList.toggle("ligada", c.chamado !== false);
    B.el("chaveTexto").classList.toggle("ligada", !!c.modo_texto);
    document.querySelectorAll("[data-tema]").forEach((b) => b.classList.toggle("ativo", b.dataset.tema === (c.tema || "prata")));
  }

  async function mudar(chave) {
    try {
      B.dados.config = await B.mandar("/api/config", { [chave]: !B.dados.config[chave] });
      desenharChaves();
    } catch (erro) { B.toast(erro.message); }
  }

  async function mudarTema(tema) {
    try { await B.mandar("/api/tema", { tema }); } catch (erro) { B.toast(erro.message); }
  }

  // ---------------------------------------------------------- ícone
  async function enviarIcone(arquivo) {
    if (!arquivo) return;
    try {
      const r = await fetch("/api/icone", { method: "POST", headers: { "Content-Type": arquivo.type }, body: arquivo });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(d.erro || "Não deu certo.");
      desenharIcone(d);
      B.toast("Ícone trocado.");
    } catch (erro) { B.toast(erro.message); }
  }

  async function voltarIcone() {
    try { desenharIcone(await B.mandar("/api/icone/apagar")); B.toast("Voltei pro robô."); }
    catch (erro) { B.toast(erro.message); }
  }

  function desenharIcone(s) { B.el("voltarIcone").hidden = !s.personalizado; }

  // ---------------------------------------------------------- quem responde
  async function carregarIas() {
    try {
      const d = await B.pegar("/api/ias");
      B.el("modeloAtual").textContent = d.nome;
      desenharIas(d);
    } catch (erro) { /* sem Ultron */ }
  }

  function desenharIas(d) {
    const linhas = [grupo("Claude (com ferramentas: mexe no PC, arquivos, e-mail)")];
    d.opcoes.forEach((o, i) => {
      if (i > 0 && o.ia !== "claude" && d.opcoes[i - 1].ia === "claude") linhas.push(grupo("Outras IAs (só conversa)"));
      linhas.push(opcaoDeIa(o, o.ia === d.ia && (o.ia !== "claude" || o.modelo === d.modelo)));
    });
    B.el("listaIas").replaceChildren(...linhas);
  }

  function grupo(texto) {
    const li = document.createElement("li");
    li.className = "grupo";
    li.textContent = texto;
    return li;
  }

  function opcaoDeIa(o, escolhida) {
    const li = document.createElement("li");
    li.className = (escolhida ? "escolhida-ia" : "") + (o.ligada ? "" : " desligada");
    const nome = document.createElement("span");
    nome.className = "texto";
    nome.textContent = o.nome;
    li.appendChild(nome);
    const nota = document.createElement("span");
    nota.className = "quando";
    nota.textContent = escolhida ? "respondendo agora"
      : o.limite || (o.ligada || o.entrar ? "" : "falta a chave no .env");  // "sem limite, volta às 15:00"
    li.appendChild(nota);
    if (!o.ligada && o.entrar) li.appendChild(botaoDeEntrar(o));
    if (o.ligada) li.addEventListener("click", () => escolher(o));
    return li;
  }

  function botaoDeEntrar(o) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "entrar";
    b.textContent = "Entrar com " + o.entrar;
    b.addEventListener("click", async (ev) => {
      ev.stopPropagation();
      try {
        await B.mandar("/api/ias/entrar", { ia: o.ia });
        B.toast("Abri o login numa janela do terminal. Depois de entrar, volte aqui.");
      } catch (erro) { B.toast(erro.message); }
    });
    return b;
  }

  async function escolher(o) {
    try {
      const d = await B.mandar("/api/ias", { ia: o.ia, modelo: o.ia === "claude" ? o.modelo : "" });
      B.toast("Agora quem responde é o " + d.nome + ".");
      B.el("modeloAtual").textContent = d.nome;
      desenharIas(d);
    } catch (erro) { B.toast(erro.message); }
  }

  B.secao("config", {
    titulo: "Configurações",
    iniciar() {
      B.el("chaveChamado").addEventListener("click", () => mudar("chamado"));
      B.el("chaveTexto").addEventListener("click", () => mudar("modo_texto"));
      document.querySelectorAll("[data-tema]").forEach((b) => b.addEventListener("click", () => mudarTema(b.dataset.tema)));
      B.el("enviarIcone").addEventListener("click", () => B.el("arquivoIcone").click());
      B.el("arquivoIcone").addEventListener("change", (ev) => { enviarIcone(ev.target.files[0]); ev.target.value = ""; });
      B.el("voltarIcone").addEventListener("click", voltarIcone);
    },
    abrir() { desenharChaves(); carregarIas(); B.pegar("/api/icone").then(desenharIcone).catch(() => {}); },
    evento(e) {
      if (e.tipo === "conectou" || e.tipo === "ia") carregarIas();
      if (e.tipo === "conectou" || e.tipo === "tema_local") desenharChaves();
      if (e.tipo === "icone") desenharIcone(e);
    },
  });
})();
