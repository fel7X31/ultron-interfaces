// Música e Meu PC: os players (Início e Música), o volume, o uso do PC e os atalhos. Enquanto o painel está aberto
// numa dessas seções, pergunta ao Ultron a cada 2 s; a música também chega ao vivo pelo evento "tocando".
(() => {
  const B = window.Barra;
  const ATUALIZAR_MS = 2000;
  const SECOES_COM_PC = ["inicio", "musica", "pc"];
  let arrastandoVolume = false;

  function montarPecas() {
    document.querySelectorAll("[data-player]").forEach((p) => p.appendChild(B.el("modeloPlayer").content.cloneNode(true)));
    document.querySelectorAll("[data-volume]").forEach((v) => v.appendChild(B.el("modeloVolume").content.cloneNode(true)));
    document.querySelectorAll(".painel [data-acao]").forEach((b) => b.addEventListener("click", () => B.acao(b.dataset.acao, b.dataset.alvo)));
    document.querySelectorAll("[data-texto]").forEach((b) => b.addEventListener("click", () => pedir(b.dataset.texto)));
    document.querySelectorAll("[data-mudo]").forEach((b) => b.addEventListener("click", () => B.acao(B.dados.volume.mudo ? "som" : "mudo")));
    document.querySelectorAll("[data-volume] input").forEach((barra) => {
      barra.addEventListener("input", () => { arrastandoVolume = true; mostrarVolume({ nivel: Number(barra.value), mudo: false }); });
      barra.addEventListener("change", () => { arrastandoVolume = false; B.acao("volume", barra.value); });
    });
  }

  async function pedir(texto) {
    try { await B.mandar("/api/texto", { texto }); } catch (erro) { B.toast(erro.message); }
  }

  async function atualizar() {
    try {
      const d = await B.pegar("/api/pc");
      desenharUso(d.uso);
      mostrarVolume(d.volume);
      desenharPlayers(d.tocando);
    } catch (erro) { /* o Ultron caiu: a conexão ao vivo cuida disso */ }
  }

  // ---------------------------------------------------------- música
  function desenharPlayers(tocando) {
    const tem = !!(tocando && tocando.titulo);
    document.querySelectorAll("[data-player]").forEach((p) => {
      p.querySelector("[data-faixa]").textContent = tem ? tocando.titulo : "Nada tocando agora";
      p.querySelector("[data-quem]").textContent = tem ? [tocando.artista, tocando.app].filter(Boolean).join(" · ") : "Spotify, YouTube ou o player do Ultron";
    });
  }

  function mostrarVolume(volume) {
    if (!volume) return;
    B.dados.volume = volume;
    document.querySelectorAll("[data-volume]").forEach((v) => {
      if (!arrastandoVolume) v.querySelector("input").value = volume.nivel;
      v.querySelector(".volume-valor").textContent = volume.mudo ? "mudo" : volume.nivel;
    });
    B.corpo.classList.toggle("mudo", !!volume.mudo);
  }

  // ---------------------------------------------------------- uso do PC
  function numero(n) { return Number(n).toLocaleString("pt-BR"); }

  function desenharUso(uso) {
    if (!uso) return;
    const linhas = [
      ["Processador", uso.processador, "", uso.processador >= 85],
      ["Memória", uso.memoria.pct, numero(uso.memoria.usada_gb) + " GB", uso.memoria.pct >= 85],
      ["Disco C:", uso.disco.pct, numero(uso.disco.livre_gb) + " GB livres", uso.disco.pct >= 90],
    ];
    const video = uso.placa_de_video, bateria = uso.bateria;
    if (video) linhas.push(["Placa de vídeo", video.pct, video.temperatura + "°", video.temperatura >= 85]);
    if (bateria) linhas.push(["Bateria", bateria.pct, bateria.carregando ? "carregando" : "", bateria.pct <= 20 && !bateria.carregando]);
    B.el("medidores").replaceChildren(...linhas.map((l) => medidor(...l)));
    const cpu = document.querySelector('[data-resumo="cpu"]'), mem = document.querySelector('[data-resumo="memoria"]');
    if (cpu) cpu.textContent = uso.processador + "%";
    if (mem) mem.textContent = "memória " + uso.memoria.pct + "%";
  }

  function medidor(nome, pct, detalhe, alerta) {
    const linha = document.createElement("div");
    linha.className = "medidor" + (alerta ? " alerta" : "");
    linha.innerHTML = '<span class="nome"></span><span class="trilho"><span class="barra"></span></span><span class="valor"><small></small><b></b></span>';
    linha.querySelector(".nome").textContent = nome;
    linha.querySelector(".barra").style.width = Math.max(0, Math.min(100, pct)) + "%";
    linha.querySelector("small").textContent = detalhe;
    linha.querySelector("b").textContent = pct + "%";
    return linha;
  }

  setInterval(() => { if (B.aberta() && SECOES_COM_PC.includes(B.atual())) atualizar(); }, ATUALIZAR_MS);

  const evento = (e) => {
    if (e.tipo === "tocando") desenharPlayers(e.tocando);
    else if (e.tipo === "pc_mexeu") setTimeout(atualizar, 400);
    else if (e.tipo === "conectou") atualizar();
  };

  B.secao("musica", {
    titulo: "Música",
    iniciar() {
      montarPecas();
      B.el("formMusica").addEventListener("submit", (ev) => {
        ev.preventDefault();
        const busca = B.el("buscaMusica").value.trim();
        if (!busca) return;
        B.el("buscaMusica").value = "";
        B.toast("Procurando no YouTube...");
        pedir("toca " + busca);
      });
    },
    abrir: atualizar,
    evento,
  });
  B.secao("pc", { titulo: "Meu PC", abrir: atualizar });
})();
