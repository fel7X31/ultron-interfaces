// O rosto do Ultron: um robô prata de visor escuro e olhos vermelhos (ou a imagem que você mandou).
// Todo <span class="rosto"> da página vira um.
// Ele pisca sozinho, os olhos acendem quando ele ouve, a boca mexe quando ele fala e um arco vermelho gira em volta
// quando ele pensa (tudo pelo data-estado do body, em CSS: nada roda em JS depois de desenhar).
(() => {
  const CSS = `
    .rosto { display: inline-block; flex: none; }
    .rosto svg { display: block; width: 100%; height: 100%; overflow: visible; }
    .rosto .giro { fill: none; stroke: #e3141d; stroke-width: 3; stroke-linecap: round; stroke-dasharray: 30 160;
      opacity: 0; transform-origin: 32px 32px; transition: opacity .3s; }
    .rosto .visor { fill: #121418; }
    .rosto .olho, .rosto .boca { fill: #ff2a1f; transform-box: fill-box; transform-origin: center;
      filter: drop-shadow(0 0 2px rgba(255, 35, 30, .9)); }
    .rosto .olho { animation: rostoOlhar 4s ease-in-out infinite, rostoPiscar 7s linear infinite; }
    .rosto .boca { opacity: .6; }
    body[data-estado="ouvindo"] .rosto .olho { animation: rostoOlhar .5s ease-in-out infinite;
      filter: drop-shadow(0 0 4px #ff2a1f); }
    body[data-estado="falando"] .rosto .boca { opacity: 1; animation: rostoFalar .16s ease-in-out infinite alternate; }
    body[data-estado="pensando"] .rosto .giro, body[data-estado="transcrevendo"] .rosto .giro,
    body[data-estado="aquecendo"] .rosto .giro { opacity: 1; animation: rostoGirar 1.1s linear infinite; }
    @keyframes rostoOlhar { 0%, 100% { opacity: .8; } 50% { opacity: 1; } }
    @keyframes rostoPiscar { 0%, 95%, 100% { transform: scaleY(1); } 97% { transform: scaleY(.15); } }
    @keyframes rostoFalar { from { transform: scaleX(.6); } to { transform: scaleX(1.15); } }
    @keyframes rostoGirar { to { transform: rotate(360deg); } }
    .rosto .foto { transform-origin: 32px 32px; transition: filter .2s; }
    body[data-estado="ouvindo"] .rosto .foto { filter: drop-shadow(0 0 3px #ff2a1f); }
    body[data-estado="falando"] .rosto .foto { animation: rostoPulsar .3s ease-in-out infinite alternate; }
    @keyframes rostoPulsar { to { transform: scale(1.06); } }
  `;
  // Formas grandes e chapadas, sem traço fino: no entalhe ele tem só 22 px.
  // Cada rosto tem o próprio degradê (id único): um degradê dentro de algo escondido não pinta os outros.
  const desenho = (n) => `<svg viewBox="0 0 64 64" aria-hidden="true">
    <defs><linearGradient id="prata${n}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#f4f6f8"/><stop offset="1" stop-color="#9da3ab"/>
    </linearGradient></defs>
    <circle class="giro" cx="32" cy="32" r="30"/>
    <path fill="url(#prata${n})" d="M12 26C12 13 21 6 32 6C43 6 52 13 52 26V36C52 49 43 57 32 57C21 57 12 49 12 36Z"/>
    <rect class="visor" x="15" y="23" width="34" height="14" rx="7"/>
    <rect class="olho" x="20" y="27.5" width="9" height="5" rx="2.5"/>
    <rect class="olho" x="35" y="27.5" width="9" height="5" rx="2.5"/>
    <rect class="boca" x="25" y="45" width="14" height="3.5" rx="1.75"/>
  </svg>`;
  // A imagem que você mandou (Configurações, na barra), cortada em círculo. Ela brilha quando ele ouve e pulsa
  // quando ele fala; o arco de pensar continua igual.
  const foto = (n, url) => `<svg viewBox="0 0 64 64" aria-hidden="true">
    <defs><clipPath id="corte${n}"><circle cx="32" cy="32" r="28"/></clipPath></defs>
    <circle class="giro" cx="32" cy="32" r="30"/>
    <image class="foto" href="${url}" x="4" y="4" width="56" height="56" preserveAspectRatio="xMidYMid slice"
      clip-path="url(#corte${n})"/>
  </svg>`;

  function desenhar(s) {
    const url = s.personalizado ? "/icone.svg?v=" + s.versao : null;
    document.querySelectorAll(".rosto").forEach((lugar, n) => { lugar.innerHTML = url ? foto(n, url) : desenho(n); });
    const aba = document.querySelector('link[rel="icon"]');
    if (aba) { aba.type = ""; aba.href = "/icone.svg?v=" + s.versao; }
  }

  async function atualizar(s) {
    if (!s) s = await fetch("/api/icone").then((r) => r.json()).catch(() => ({ personalizado: false, versao: 0 }));
    desenhar(s);
  }

  const estilo = document.createElement("style");
  estilo.textContent = CSS;
  document.head.appendChild(estilo);
  window.Rosto = { atualizar };  // a tela e a barra chamam quando chega o evento "icone"
  atualizar();
})();
