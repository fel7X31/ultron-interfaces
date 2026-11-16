// O rosto do Ultron: um robô prata de olhos vermelhos. Todo <span class="rosto"> da página vira um.
// Ele pisca sozinho, os olhos acendem quando ele ouve, a boca mexe quando ele fala e um arco vermelho gira em volta
// quando ele pensa (tudo pelo data-estado do body, em CSS: nada roda em JS depois de desenhar).
(() => {
  const CSS = `
    .rosto { display: inline-block; flex: none; }
    .rosto svg { display: block; width: 100%; height: 100%; overflow: visible; }
    .rosto .anel { fill: none; stroke: rgba(150, 155, 162, .55); stroke-width: 1.5; }
    .rosto .giro { fill: none; stroke: #e3141d; stroke-width: 2.2; stroke-linecap: round; stroke-dasharray: 26 163;
      opacity: 0; transform-origin: 32px 32px; transition: opacity .3s; }
    .rosto .crista { fill: #8f959d; stroke: #353a41; stroke-width: .8; stroke-linejoin: round; }
    .rosto .traco { fill: none; stroke: #353a41; stroke-width: 1.3; stroke-linecap: round; stroke-linejoin: round; }
    .rosto .olho, .rosto .boca { fill: #ff2a1f; transform-box: fill-box; transform-origin: center;
      filter: drop-shadow(0 0 2px rgba(255, 35, 30, .9)); }
    .rosto .olho { animation: rostoOlhar 4s ease-in-out infinite, rostoPiscar 7s linear infinite; }
    .rosto .boca { opacity: .7; }
    body[data-estado="ouvindo"] .rosto .olho { animation: rostoOlhar .5s ease-in-out infinite;
      filter: drop-shadow(0 0 4px #ff2a1f); }
    body[data-estado="falando"] .rosto .boca { opacity: 1; animation: rostoFalar .16s ease-in-out infinite alternate; }
    body[data-estado="pensando"] .rosto .giro, body[data-estado="transcrevendo"] .rosto .giro,
    body[data-estado="aquecendo"] .rosto .giro { opacity: 1; animation: rostoGirar 1.1s linear infinite; }
    @keyframes rostoOlhar { 0%, 100% { opacity: .75; } 50% { opacity: 1; } }
    @keyframes rostoPiscar { 0%, 95%, 100% { transform: scaleY(1); } 97% { transform: scaleY(.12); } }
    @keyframes rostoFalar { from { transform: scaleY(.55); } to { transform: scaleY(1.9); } }
    @keyframes rostoGirar { to { transform: rotate(360deg); } }
  `;
  // Cada rosto tem o próprio degradê (id único): um degradê dentro de algo escondido não pinta os outros.
  const desenho = (n) => `<svg viewBox="0 0 64 64" aria-hidden="true">
    <defs><linearGradient id="prata${n}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#f5f7f9"/><stop offset=".55" stop-color="#b8bdc5"/><stop offset="1" stop-color="#666c75"/>
    </linearGradient></defs>
    <circle class="anel" cx="32" cy="32" r="30"/>
    <circle class="giro" cx="32" cy="32" r="30"/>
    <path fill="url(#prata${n})" stroke="#353a41" stroke-width="1.4" stroke-linejoin="round"
      d="M32 7C44 7 51 15 51 27C51 38 45 48 38 55L32 58L26 55C19 48 13 38 13 27C13 15 20 7 32 7Z"/>
    <path class="crista" d="M28.5 8.5H35.5L34 25H30Z"/>
    <path class="olho" d="M16 28L28 31.5L27 35.5L18 33Z"/>
    <path class="olho" d="M48 28L36 31.5L37 35.5L46 33Z"/>
    <path class="traco" d="M19 39L27 43V52M45 39L37 43V52"/>
    <path class="boca" d="M27 46.5H37L36 49.5H28Z"/>
  </svg>`;
  const estilo = document.createElement("style");
  estilo.textContent = CSS;
  document.head.appendChild(estilo);
  document.querySelectorAll(".rosto").forEach((lugar, n) => { lugar.innerHTML = desenho(n); });
})();
