// A esfera do Ultron em miniatura (a mesma rede vermelha da tela): gira devagar, acelera quando ele pensa e pulsa
// quando ouve ou fala (lê o data-estado do body). Todo <canvas class="esfera-mini"> da página vira uma.
// Leve: 40 pontos, 30 quadros por segundo e nada quando a página está escondida.
(() => {
  const PONTOS = 40, VIZINHOS = 3, INCLINACAO = 0.42, QUADRO_MS = 33;
  const RAPIDEZ = { ouvindo: 1.9, falando: 1.6, pensando: 1.2, transcrevendo: 1.2, aquecendo: 1 };  // voltas por s
  const pontos = Array.from({ length: PONTOS }, (_, i) => {  // espalhados por igual na esfera (espiral de Fibonacci)
    const y = 1 - (2 * (i + 0.5)) / PONTOS, r = Math.sqrt(1 - y * y), a = i * 2.39996;
    return [Math.cos(a) * r, y, Math.sin(a) * r];
  });
  const distancia = (p, q) => (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2;
  const ligacoes = new Set();
  pontos.forEach((p, i) => pontos
    .map((q, j) => [j, distancia(p, q)]).filter(([j]) => j !== i).sort((a, b) => a[1] - b[1]).slice(0, VIZINHOS)
    .forEach(([j]) => ligacoes.add(i < j ? `${i}-${j}` : `${j}-${i}`)));
  const linhas = [...ligacoes].map((k) => k.split("-").map(Number));
  const telas = [...document.querySelectorAll("canvas.esfera-mini")];
  let giro = 0, antes = 0;

  function projetar(tamanho, raio) {
    const cos = Math.cos(giro), sin = Math.sin(giro), ci = Math.cos(INCLINACAO), si = Math.sin(INCLINACAO);
    return pontos.map(([x, y, z]) => {
      const x1 = x * cos + z * sin, z1 = z * cos - x * sin;
      return [tamanho / 2 + x1 * raio, tamanho / 2 + (y * ci - z1 * si) * raio, (y * si + z1 * ci + 1) / 2];  // frente = 1
    });
  }

  function desenhar(tela, pulso) {
    const tamanho = Math.round(tela.clientWidth * (window.devicePixelRatio || 1));
    if (tela.width !== tamanho) tela.width = tela.height = tamanho;
    const c = tela.getContext("2d"), p = projetar(tamanho, tamanho * 0.4 * pulso);
    c.clearRect(0, 0, tamanho, tamanho);
    c.lineWidth = Math.max(0.6, tamanho / 64);
    for (const [a, b] of linhas) {
      c.strokeStyle = `rgba(215, 20, 30, ${0.15 + 0.6 * (p[a][2] + p[b][2]) / 2})`;
      c.beginPath();
      c.moveTo(p[a][0], p[a][1]);
      c.lineTo(p[b][0], p[b][1]);
      c.stroke();
    }
    for (const [x, y, frente] of p) {
      c.fillStyle = `rgba(235, 35, 45, ${0.3 + 0.7 * frente})`;
      c.beginPath();
      c.arc(x, y, Math.max(0.6, tamanho / 40) * (0.6 + 0.5 * frente), 0, Math.PI * 2);
      c.fill();
    }
  }

  function quadro(agora) {
    requestAnimationFrame(quadro);
    if (document.hidden || agora - antes < QUADRO_MS) return;
    const estado = document.body.dataset.estado || "";
    giro += Math.min(0.1, (agora - antes) / 1000) * (RAPIDEZ[estado] || 0.35);
    antes = agora;
    const pulso = estado === "ouvindo" || estado === "falando" ? 1 + 0.08 * Math.sin(agora / 120) : 1;
    telas.forEach((tela) => { if (tela.clientWidth) desenhar(tela, pulso); });
  }

  if (telas.length) requestAnimationFrame(quadro);
})();
