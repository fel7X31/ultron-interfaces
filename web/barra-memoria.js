// Memória: o que o Ultron guarda sobre você, num grafo como o do Obsidian. Você no meio, os assuntos em volta, cada
// lembrança ligada ao assunto dela e aos nomes que cita. Arraste os pontos ou o fundo, role pra dar zoom, clique numa
// lembrança pra ver inteira (e esquecer). As lembranças ficam no memoria.md da sua pasta.
(() => {
  const B = window.Barra;
  const RAIOS = { centro: 10, assunto: 7, nome: 5, lembranca: 4 };
  const MOLA = { centro: 140, assunto: 80, lembranca: 65, nome: 65 };  // distância de cada ligação, pelo tipo da ponta
  const ZOOM_MIN = 0.4, ZOOM_MAX = 3, MARGEM = 24;
  let nos = [], ligacoes = [], porId = {}, cores = {};
  let canvas, ctx, largura = 0, altura = 0, dpr = 1, zoom = 1, centro = { x: 0, y: 0 };
  let calor = 0, quadro = null, sobre = null, escolhido = null, filtro = "";
  let pegou = null;  // {no, x, y, moveu} ou {fundo, x, y}
  let seguirVista = true;  // o zoom acompanha o grafo até você mexer nele (arrastar o fundo ou rolar)

  const sem_acento = (t) => t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

  // ---------------------------------------------------------- os dados
  async function carregar() {
    try {
      const d = await B.pegar("/api/memoria");
      montar(d.grafo);
      B.contar("memoria", d.total);
      if (B.atual() === "memoria") B.detalhe(d.total === 1 ? "1 lembrança" : d.total + " lembranças");
      B.el("vazioMemoria").hidden = d.total > 0;
      if (escolhido && !porId[escolhido.id]) escolher(null);
    } catch (erro) { /* sem Ultron: fica o grafo que já estava */ }
  }

  function montar(grafo) {
    const antes = porId;
    porId = {};
    nos = grafo.nos.map((n) => (porId[n.id] = { ...n, ...posicaoInicial(n, antes), vx: 0, vy: 0, vizinhos: new Set() }));
    ligacoes = grafo.ligacoes.map(([a, b]) => ({ a: porId[a], b: porId[b] })).filter((l) => l.a && l.b);
    ligacoes.forEach(({ a, b }) => { a.vizinhos.add(b); b.vizinhos.add(a); });
    if (porId.voce) Object.assign(porId.voce, { x: 0, y: 0, fixo: true });
    if (nos.some((n) => !antes[n.id])) seguirVista = true;
    aquecer(1);
  }

  function posicaoInicial(n, antes) {
    if (antes[n.id]) return { x: antes[n.id].x, y: antes[n.id].y };
    const pai = n.assunto && antes["assunto:" + n.assunto];
    const angulo = Math.random() * Math.PI * 2, raio = pai ? 30 : n.tipo === "assunto" ? 100 : 150;
    return { x: (pai ? pai.x : 0) + Math.cos(angulo) * raio, y: (pai ? pai.y : 0) + Math.sin(angulo) * raio };
  }

  // ---------------------------------------------------------- a física (empurra todos, puxa os ligados)
  function passo() {
    for (let i = 0; i < nos.length; i++) {
      for (let j = i + 1; j < nos.length; j++) empurrar(nos[i], nos[j]);
    }
    ligacoes.forEach(puxar);
    nos.forEach((n) => {
      if (n.fixo || (pegou && pegou.no === n)) { n.vx = n.vy = 0; return; }
      n.vx = (n.vx - n.x * 0.0025) * 0.8;
      n.vy = (n.vy - n.y * 0.0025) * 0.8;
      n.x += n.vx * calor;
      n.y += n.vy * calor;
    });
    calor = Math.max(0, calor - 0.005);
  }

  function empurrar(a, b) {
    let dx = b.x - a.x, dy = b.y - a.y;
    const d2 = Math.max(dx * dx + dy * dy, 1), d = Math.sqrt(d2), forca = Math.min(2600 / d2, 30);
    dx /= d; dy /= d;
    a.vx -= dx * forca; a.vy -= dy * forca;
    b.vx += dx * forca; b.vy += dy * forca;
  }

  function puxar({ a, b }) {
    let dx = b.x - a.x, dy = b.y - a.y;
    const d = Math.max(Math.hypot(dx, dy), 0.01), forca = (d - (MOLA[a.tipo] || 55)) * 0.035;
    dx /= d; dy /= d;
    a.vx += dx * forca; a.vy += dy * forca;
    b.vx -= dx * forca; b.vy -= dy * forca;
  }

  function aquecer(quanto) {
    calor = Math.max(calor, quanto);
    if (!quadro) quadro = requestAnimationFrame(animar);
  }

  function animar() {
    quadro = null;
    if (B.atual() !== "memoria" || !B.aberta()) return;
    for (let i = 0; i < 2 && calor > 0.01; i++) passo();
    if (seguirVista) enquadrar(calor > 0.01 ? 0.15 : 1);
    desenhar();
    if (calor > 0.01) quadro = requestAnimationFrame(animar);
  }

  // Zoom e posição pra caber o grafo todo na caixa (com folga pros nomes embaixo dos pontos)
  function enquadrar(suave) {
    if (!nos.length || !largura) return;
    const xs = nos.flatMap((n) => [n.x - (n.tipo === "lembranca" ? 80 : 45), n.x + (n.tipo === "lembranca" ? 80 : 45)]);
    const ys = nos.flatMap((n) => [n.y - 12, n.y + 24]);
    const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
    const alvo = Math.min(1.6, Math.max(ZOOM_MIN, Math.min((largura - MARGEM * 2) / (x1 - x0), (altura - MARGEM * 2) / (y1 - y0))));
    zoom += (alvo - zoom) * suave;
    centro.x += (-(x0 + x1) / 2 * zoom - centro.x) * suave;
    centro.y += (-(y0 + y1) / 2 * zoom - centro.y) * suave;
  }

  // ---------------------------------------------------------- o desenho
  function lerCores() {
    const css = getComputedStyle(document.body);
    const cor = (nome) => css.getPropertyValue(nome).trim();
    cores = { texto: cor("--texto"), suave: cor("--suave"), linha: cor("--linha"), fundo: cor("--fundo"), vermelho: "#d7141e", nome: "#e8657c" };
  }

  function apagado(n) {
    return !!filtro && (n.tipo === "lembranca" || n.tipo === "nome") && !sem_acento(n.nome).includes(filtro);
  }

  function desenhar() {
    if (!ctx || !largura) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, largura, altura);
    ctx.translate(largura / 2 + centro.x, altura / 2 + centro.y);
    ctx.scale(zoom, zoom);
    const foco = sobre || escolhido;
    ligacoes.forEach((l) => desenharLigacao(l, foco));
    nos.forEach((n) => desenharNo(n, foco));
    ctx.globalAlpha = 1;
  }

  function desenharLigacao({ a, b }, foco) {
    const acesa = foco && (a === foco || b === foco);
    ctx.globalAlpha = apagado(a) || apagado(b) ? 0.2 : 1;
    ctx.strokeStyle = acesa ? cores.vermelho : cores.linha;
    ctx.lineWidth = (acesa ? 1.6 : 1) / zoom;
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
    ctx.stroke();
  }

  function desenharNo(n, foco) {
    const perto = foco && (n === foco || foco.vizinhos.has(n));
    ctx.globalAlpha = apagado(n) ? 0.18 : foco && !perto ? 0.45 : 1;
    const raio = RAIOS[n.tipo] + (n === foco ? 2 : 0);
    ctx.fillStyle = { centro: cores.texto, assunto: cores.vermelho, nome: cores.nome }[n.tipo] || cores.suave;
    ctx.shadowColor = n.tipo === "assunto" || n === foco ? cores.vermelho : "transparent";
    ctx.shadowBlur = n.tipo === "lembranca" && n !== foco ? 0 : 12;
    ctx.beginPath();
    ctx.arc(n.x, n.y, raio, 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowBlur = 0;
    const grande = n.tipo === "centro" || n.tipo === "assunto";
    ctx.font = `${grande ? 600 : 400} ${n.tipo === "centro" ? 12.5 : grande ? 11 : 10}px Inter, "Segoe UI", sans-serif`;
    ctx.textAlign = "center";
    ctx.fillStyle = grande || perto ? cores.texto : cores.suave;
    const texto = n.tipo === "lembranca" && n !== foco && n.nome.length > 34 ? n.nome.slice(0, 32) + "…" : n.nome;
    ctx.fillText(texto, n.x, n.y + raio + 12);
  }

  // ---------------------------------------------------------- mouse: passar por cima, arrastar, zoom e clicar
  function noMundo(ev) {
    const r = canvas.getBoundingClientRect();
    return { x: (ev.clientX - r.left - largura / 2 - centro.x) / zoom, y: (ev.clientY - r.top - altura / 2 - centro.y) / zoom };
  }

  function noEm(p) {
    let achou = null, melhor = Infinity;
    nos.forEach((n) => {
      const d = Math.hypot(n.x - p.x, n.y - p.y);
      if (d <= RAIOS[n.tipo] + 6 / zoom && d < melhor) { achou = n; melhor = d; }
    });
    return achou;
  }

  function mostrarDica(n, ev) {
    const dica = B.el("dicaGrafo");
    dica.hidden = !n || n.tipo === "centro" || n.tipo === "assunto";
    if (dica.hidden) return;
    const r = canvas.getBoundingClientRect();
    dica.textContent = n.nome + (n.tipo === "lembranca" ? "" : " · " + n.vizinhos.size + " lembranças");
    dica.style.left = ev.clientX - r.left + "px";
    dica.style.top = ev.clientY - r.top + "px";
  }

  function aoMover(ev) {
    const p = noMundo(ev);
    if (pegou && pegou.no) {
      Object.assign(pegou.no, { x: p.x, y: p.y });
      pegou.moveu = pegou.moveu || Math.hypot(ev.clientX - pegou.x, ev.clientY - pegou.y) > 3;
      aquecer(0.3);
      return;
    }
    if (pegou) {
      seguirVista = false;
      centro.x += ev.clientX - pegou.x;
      centro.y += ev.clientY - pegou.y;
      Object.assign(pegou, { x: ev.clientX, y: ev.clientY, moveu: true });
      desenhar();
      return;
    }
    const n = noEm(p);
    if (n !== sobre) { sobre = n; desenhar(); }
    canvas.style.cursor = n ? "pointer" : "";
    mostrarDica(n, ev);
  }

  function aoApertar(ev) {
    const n = noEm(noMundo(ev));
    pegou = { no: n && !n.fixo ? n : null, fundo: !n, x: ev.clientX, y: ev.clientY, moveu: false, clicado: n };
    canvas.classList.add("arrastando");
  }

  function aoSoltar() {
    if (pegou && !pegou.moveu) escolher(pegou.clicado && pegou.clicado.tipo === "lembranca" ? pegou.clicado : null);
    pegou = null;
    canvas.classList.remove("arrastando");
  }

  function aoRolar(ev) {
    ev.preventDefault();
    seguirVista = false;
    const antes = noMundo(ev);
    zoom = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, zoom * Math.exp(-ev.deltaY * 0.0015)));
    const depois = noMundo(ev);
    centro.x += (depois.x - antes.x) * zoom;
    centro.y += (depois.y - antes.y) * zoom;
    desenhar();
  }

  function escolher(n) {
    escolhido = n;
    const caixa = B.el("lembrancaEscolhida");
    caixa.hidden = !n;
    if (n) {
      caixa.querySelector("p").textContent = n.nome;
      caixa.querySelector("small").textContent = n.assunto;
    }
    desenhar();
  }

  async function esquecer() {
    if (!escolhido) return;
    try {
      await B.mandar("/api/memoria/apagar", { id: escolhido.id });
      B.toast("Esqueci.");
      escolher(null);
      carregar();
    } catch (erro) { B.toast(erro.message); }
  }

  async function guardar(ev) {
    ev.preventDefault();
    const campo = B.el("novaMemoria"), texto = campo.value.trim();
    if (!texto) return;
    try {
      const nova = await B.mandar("/api/memoria", { texto });
      campo.value = "";
      B.toast("Guardado em " + nova.assunto.toLowerCase() + ".");
      carregar();
    } catch (erro) { B.toast(erro.message); }
  }

  function redimensionar() {
    const caixa = canvas.parentElement.getBoundingClientRect();
    dpr = window.devicePixelRatio || 1;
    largura = caixa.width;
    altura = caixa.height;
    canvas.width = Math.round(largura * dpr);
    canvas.height = Math.round(altura * dpr);
    desenhar();
  }

  B.secao("memoria", {
    titulo: "Memória",
    iniciar() {
      canvas = B.el("grafo");
      ctx = canvas.getContext("2d");
      lerCores();
      canvas.addEventListener("mousemove", aoMover);
      canvas.addEventListener("mousedown", aoApertar);
      addEventListener("mouseup", aoSoltar);
      canvas.addEventListener("mouseleave", () => { sobre = null; B.el("dicaGrafo").hidden = true; desenhar(); });
      canvas.addEventListener("wheel", aoRolar, { passive: false });
      canvas.addEventListener("dblclick", () => { seguirVista = true; enquadrar(1); desenhar(); });
      new ResizeObserver(redimensionar).observe(canvas.parentElement);
      B.el("formMemoria").addEventListener("submit", guardar);
      B.el("esquecerLembranca").addEventListener("click", esquecer);
      B.el("procurarMemoria").addEventListener("input", (ev) => { filtro = sem_acento(ev.target.value.trim()); desenhar(); });
    },
    abrir() { carregar(); redimensionar(); seguirVista = true; aquecer(0.4); },
    evento(e) {
      if (e.tipo === "memoria" || e.tipo === "conectou") carregar();
      else if (e.tipo === "tema_local") { lerCores(); desenhar(); }
    },
  });
})();
