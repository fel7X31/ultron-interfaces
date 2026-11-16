// A barra do topo da tela. Fechada: o entalhe (o Ultron, o que está acontecendo, a música e o botão que abre a
// interface). Aberta: o painel com o menu do lado. A janela em si (tamanho, aparecer, sumir) é do barra.py, que a
// página chama por window.pywebview.api; aberta direto no navegador, funciona só como página.
// Este arquivo é o miolo: cada seção mora no seu barra-*.js e se registra com Barra.secao(nome, {...}).
(() => {
  // O entalhe é compacto (só o rosto e a hora) quando nada toca, nada foi dito agora e ele está parado; senão, largo.
  const LARGURA_COMPACTA = 132, LARGURA_LARGA = 470, LARGURA_ABERTA = 900, ALTURA_ABERTA = 548;
  const FALA_NO_ENTALHE_MS = 25000;     // a última coisa dita fica no entalhe por esse tempo
  const DESISTIR_SEM_ULTRON_MS = 20000; // o Ultron foi desligado: a barra fecha junto
  const NOMES = {
    iniciando: "iniciando", aquecendo: "conectando", parado: "pronto", ouvindo: "ouvindo",
    transcrevendo: "entendendo", pensando: "trabalhando", falando: "falando",
  };
  const el = (id) => document.getElementById(id);
  const corpo = document.body;
  const secoes = {};
  let aberta = false, secaoAtual = "inicio", semConexaoDesde = 0, telasAbertas = 0, apagarFala = null;

  const Barra = window.Barra = {
    el, corpo,
    dados: { nome: "", tocando: null, volume: { nivel: 0, mudo: false }, config: {} },
    secao(nome, definicao) { secoes[nome] = definicao; },
    aberta: () => aberta,
    atual: () => secaoAtual,
    janela(metodo, ...args) {  // termina quando o barra.py termina (a animação de abrir ou minimizar, por exemplo)
      const api = window.pywebview && window.pywebview.api;
      return api && api[metodo] ? Promise.resolve(api[metodo](...args)).catch(() => {}) : Promise.resolve();
    },
    async pegar(caminho) {
      const r = await fetch(caminho);
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(d.erro || "O Ultron não respondeu.");
      return d;
    },
    async mandar(caminho, dados = {}) {
      const r = await fetch(caminho, { method: "POST", body: JSON.stringify(dados) });
      const d = await r.json().catch(() => ({}));
      if (r.status === 409) throw new Error("Ainda estou no pedido anterior.");
      if (!r.ok) throw new Error(d.erro || "Não deu certo.");
      return d;
    },
    async acao(nome, alvo = "") {  // controle do PC (volume, mídia, atalhos...)
      try {
        const d = await Barra.mandar("/api/pc/acao", { acao: nome, alvo });
        if (nome === "janelas" || nome === "tocando") Barra.toast(d.texto);
      } catch (erro) { Barra.toast(erro.message); }
      Barra.avisarSecoes({ tipo: "pc_mexeu" });
    },
    contar(nome, quantos) {
      const conta = document.querySelector(`[data-conta="${nome}"]`);
      if (conta) conta.textContent = quantos ? String(quantos) : "";
    },
    detalhe(texto) { if (secoes[secaoAtual]) el("detalheSecao").textContent = texto || ""; },
    toast(texto) {
      const t = el("toast");
      t.textContent = texto;
      t.classList.add("visivel");
      clearTimeout(t.relogio);
      t.relogio = setTimeout(() => t.classList.remove("visivel"), 2600);
    },
    hora(iso) { return iso ? iso.slice(11, 16) : ""; },
    avisarSecoes(e) { Object.values(secoes).forEach((s) => s.evento && s.evento(e)); },
    ir,
  };

  // ---------------------------------------------------------- abrir, fechar e trocar de seção
  // Abrir: o painel aparece crescendo do entalhe (o barra.py recorta a janela). Minimizar: encolhe de volta pra ele.
  function abrir(secao) {
    if (!aberta) {
      aberta = true;
      corpo.classList.add("aberta", "abrindo");
      Barra.janela("expandir", LARGURA_ABERTA, ALTURA_ABERTA).then(() => corpo.classList.remove("abrindo"));
    }
    ir(secao || secaoAtual);
  }

  function fechar() {
    if (!aberta || corpo.classList.contains("fechando")) return;
    corpo.classList.add("fechando");
    larguraDoEntalhe = larguraCerta();
    corpo.classList.toggle("compacta", larguraDoEntalhe === LARGURA_COMPACTA);
    corpo.style.setProperty("--largura-entalhe", larguraDoEntalhe + "px");
    Barra.janela("recolher", larguraDoEntalhe).then(() => {
      aberta = false;
      corpo.classList.remove("aberta", "fechando");
    });
  }

  let larguraDoEntalhe = LARGURA_COMPACTA;
  function larguraCerta() {
    const ativo = corpo.classList.contains("com-musica") || corpo.classList.contains("com-fala") ||
      (corpo.dataset.estado && corpo.dataset.estado !== "parado");
    return ativo ? LARGURA_LARGA : LARGURA_COMPACTA;
  }

  function ajustarEntalhe() {  // fechado: cresce quando toca música, ele fala ou trabalha; volta a ser compacto depois
    const largura = larguraCerta();
    if (aberta || largura === larguraDoEntalhe) return;
    larguraDoEntalhe = largura;
    corpo.style.setProperty("--largura-entalhe", largura + "px");
    mostrarRelogio();
    if (largura === LARGURA_COMPACTA) {  // encolhendo: o conteúdo sai antes, a janela encolhe depois
      corpo.classList.add("compacta");
      Barra.janela("recolher", largura);
    } else {  // crescendo: a janela cresce antes, o conteúdo aparece depois
      Barra.janela("recolher", largura).then(() => corpo.classList.remove("compacta"));
    }
  }

  function ir(nome) {
    if (!secoes[nome]) return;
    secaoAtual = nome;
    document.querySelectorAll(".menu button").forEach((b) => b.classList.toggle("ativo", b.dataset.secao === nome));
    document.querySelectorAll(".secao").forEach((s) => s.classList.toggle("ativa", s.dataset.secao === nome));
    el("tituloSecao").textContent = secoes[nome].titulo;
    el("detalheSecao").textContent = "";
    if (secoes[nome].abrir) secoes[nome].abrir();
    const campo = document.querySelector(`.secao[data-secao="${nome}"] input[type="text"]`);
    if (campo && aberta) setTimeout(() => campo.focus(), 30);
  }

  // ---------------------------------------------------------- o entalhe
  function mudarEstado(estado) {
    corpo.dataset.estado = estado;
    ajustarEntalhe();
    mostrarRelogio();
    el("status").textContent = el("statusAberto").textContent = NOMES[estado] || estado;
  }

  function aplicarTema(tema) {
    corpo.classList.toggle("escuro", tema === "escuro");
    Barra.dados.config.tema = tema;
    Barra.avisarSecoes({ tipo: "tema_local", tema });
  }

  function mostrarRelogio() {
    const agora = new Date();
    const dia = agora.toLocaleDateString("pt-BR", { weekday: "short", day: "2-digit", month: "short" }).replace(/\./g, "");
    const hora = agora.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
    const curto = larguraDoEntalhe === LARGURA_COMPACTA || (corpo.dataset.estado || "parado") !== "parado";
    el("relogio").textContent = curto ? hora : hora + " · " + dia;  // com o status do lado, só a hora cabe
  }

  function falaNoEntalhe(texto, deQuem) {
    const fala = el("falaCurta");
    fala.textContent = deQuem === "voce" ? "“" + texto + "”" : texto;
    fala.className = "fala-curta " + deQuem;
    corpo.classList.add("com-fala");
    ajustarEntalhe();
    clearTimeout(apagarFala);
    apagarFala = setTimeout(() => { corpo.classList.remove("com-fala"); ajustarEntalhe(); }, FALA_NO_ENTALHE_MS);
  }

  function nivelDaVoz(nivel) {
    document.querySelector(".ouvindo-curto").style.setProperty("--nivel", Math.max(0.15, Math.min(1, nivel * 1.6)).toFixed(2));
  }

  // A música: no entalhe (sempre) e nos players das seções (barra-pc.js desenha os grandes)
  function desenharMusica(tocando) {
    Barra.dados.tocando = tocando || null;
    const tem = !!(tocando && tocando.titulo);
    el("faixaFechada").textContent = tem ? [tocando.titulo, tocando.artista].filter(Boolean).join(" · ") : "Nada tocando";
    corpo.classList.toggle("com-musica", tem);
    corpo.classList.toggle("tocando", tem && !!tocando.tocando);
    ajustarEntalhe();
    document.querySelectorAll("[data-capa]").forEach((capa) => {
      const url = tem && tocando.capa ? "/api/pc/capa?v=" + encodeURIComponent(tocando.capa) : "";
      capa.style.backgroundImage = url ? `url("${url}")` : "";
      capa.classList.toggle("com-capa", !!url);
    });
  }

  function aparecer(mostrar, telas) {
    telasAbertas = telas || 0;
    if (!mostrar) fechar();
    Barra.janela("aparecer", mostrar);
  }

  // ---------------------------------------------------------- a voz (sem a tela do Ultron aberta, quem fala é a barra)
  const filaDeFalas = [];
  let falando = false;
  function falar(audio) {
    if (!audio || telasAbertas > 0) return;
    filaDeFalas.push(audio);
    if (!falando) proximaFala();
  }
  function proximaFala() {
    const audio = filaDeFalas.shift();
    falando = !!audio;
    if (!audio) return;
    const som = new Audio(audio);
    som.onended = som.onerror = proximaFala;
    som.play().catch(proximaFala);
  }

  function tocarAlarme() {  // dois toques curtos quando um lembrete ou timer vence
    try {
      const ctx = new AudioContext();
      [0, 0.28].forEach((quando) => {
        const osc = ctx.createOscillator(), vol = ctx.createGain();
        osc.frequency.value = 880;
        vol.gain.setValueAtTime(0.0001, ctx.currentTime + quando);
        vol.gain.exponentialRampToValueAtTime(0.25, ctx.currentTime + quando + 0.02);
        vol.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + quando + 0.22);
        osc.connect(vol).connect(ctx.destination);
        osc.start(ctx.currentTime + quando);
        osc.stop(ctx.currentTime + quando + 0.25);
      });
    } catch (erro) { /* sem som, fica só o aviso */ }
  }

  // ---------------------------------------------------------- ao vivo com o Ultron
  async function carregarEstado() {
    const d = await Barra.pegar("/api/barra");
    aplicarTema(d.tema);
    mudarEstado(d.estado);
    aparecer(d.mostrar, d.telas);
    Barra.dados.config = await Barra.pegar("/api/config");
    Barra.dados.nome = Barra.dados.config.nome || "";
    desenharMusica((await Barra.pegar("/api/pc/tocando")).tocando);
    Barra.avisarSecoes({ tipo: "conectou" });
  }

  function tratar(e) {
    if (e.tipo === "estado") mudarEstado(e.estado);
    else if (e.tipo === "tema") aplicarTema(e.tema);
    else if (e.tipo === "barra") aparecer(e.mostrar, e.telas);
    else if (e.tipo === "tocando") desenharMusica(e.tocando);
    else if (e.tipo === "voce") falaNoEntalhe(e.texto, "voce");
    else if (e.tipo === "resposta") { falaNoEntalhe(e.texto, "ultron"); falar(e.audio); }
    else if (e.tipo === "fala") falar(e.audio);
    else if (e.tipo === "aviso") falaNoEntalhe(e.texto, "ultron");
    else if (e.tipo === "alarme") { tocarAlarme(); Barra.toast(e.texto); }
    else if (e.tipo === "atalho") {
      if (e.estado === "ouvindo") mudarEstado("ouvindo");
      else if (e.estado === "cancelado") mudarEstado("parado");
      else if (e.estado === "parado") mudarEstado("transcrevendo");
      if (e.nivel !== undefined) nivelDaVoz(e.nivel);
    }
    Barra.avisarSecoes(e);
  }

  function conectar() {
    const fonte = new EventSource("/api/eventos?quem=barra");
    fonte.onopen = () => { semConexaoDesde = 0; carregarEstado().catch(() => {}); };
    fonte.onmessage = (ev) => tratar(JSON.parse(ev.data));
    fonte.onerror = () => {
      semConexaoDesde = semConexaoDesde || Date.now();
      if (Date.now() - semConexaoDesde > DESISTIR_SEM_ULTRON_MS) { fonte.close(); Barra.janela("sair"); }
    };
  }

  // ---------------------------------------------------------- cliques e teclas
  function abrirUltron(ev) {
    ev.stopPropagation();
    fechar();
    Barra.janela("abrir_ultron");
  }

  el("entalhe").addEventListener("click", (ev) => { if (!ev.target.closest("button")) abrir(); });
  el("entalhe").addEventListener("keydown", (ev) => { if (ev.key === "Enter") abrir(); });
  el("recolher").addEventListener("click", fechar);
  el("modeloAtual").addEventListener("click", () => ir("config"));
  document.querySelectorAll("[data-abrir-ultron]").forEach((b) => b.addEventListener("click", abrirUltron));
  document.querySelectorAll(".menu button").forEach((b) => b.addEventListener("click", () => ir(b.dataset.secao)));
  document.querySelectorAll("[data-ir]").forEach((b) => b.addEventListener("click", () => ir(b.dataset.ir)));
  document.querySelectorAll(".entalhe [data-acao]").forEach((b) => b.addEventListener("click", (ev) => {
    ev.stopPropagation();
    Barra.acao(b.dataset.acao);
  }));
  addEventListener("keydown", (ev) => { if (ev.key === "Escape") fechar(); });
  // Clicou fora (outra janela ficou na frente): fecha, como um menu.
  addEventListener("blur", () => setTimeout(() => { if (!document.hasFocus()) fechar(); }, 150));
  addEventListener("pywebviewready", () => carregarEstado().catch(() => {}));
  addEventListener("load", () => {
    Object.values(secoes).forEach((s) => s.iniciar && s.iniciar());
    ir("inicio");
    corpo.classList.add("compacta");  // começa compacto (o barra.py abre a janela desse tamanho)
    corpo.style.setProperty("--largura-entalhe", LARGURA_COMPACTA + "px");
    mostrarRelogio();
    setInterval(mostrarRelogio, 15000);
    conectar();
  });
})();
