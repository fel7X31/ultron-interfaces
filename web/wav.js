// Prepara a fala pro reconhecimento: mono, 16 kHz e com o volume normalizado (o microfone grava baixo).
const WAV_TAXA = 16000;
const WAV_PICO_ALVO = 0.9;
const WAV_GANHO_MAX = 30;

async function amostrasMono(blob, contexto) {
  const audio = await contexto.decodeAudioData(await blob.arrayBuffer());
  const offline = new OfflineAudioContext(1, Math.ceil(audio.duration * WAV_TAXA), WAV_TAXA);
  const fonte = offline.createBufferSource();
  fonte.buffer = audio;
  fonte.connect(offline.destination);
  fonte.start();
  return (await offline.startRendering()).getChannelData(0);
}

function normalizarVolume(amostras) {
  let pico = 0;
  for (const a of amostras) pico = Math.max(pico, Math.abs(a));
  const ganho = pico ? Math.min(WAV_GANHO_MAX, WAV_PICO_ALVO / pico) : 1;
  return amostras.map((a) => a * ganho);
}

function wavPcm16(amostras) {
  const dados = new DataView(new ArrayBuffer(44 + amostras.length * 2));
  const texto = (pos, s) => { for (let i = 0; i < s.length; i++) dados.setUint8(pos + i, s.charCodeAt(i)); };
  texto(0, "RIFF"); dados.setUint32(4, 36 + amostras.length * 2, true); texto(8, "WAVEfmt ");
  dados.setUint32(16, 16, true); dados.setUint16(20, 1, true); dados.setUint16(22, 1, true);
  dados.setUint32(24, WAV_TAXA, true); dados.setUint32(28, WAV_TAXA * 2, true);
  dados.setUint16(32, 2, true); dados.setUint16(34, 16, true);
  texto(36, "data"); dados.setUint32(40, amostras.length * 2, true);
  amostras.forEach((a, i) => dados.setInt16(44 + i * 2, Math.max(-1, Math.min(1, a)) * 32767, true));
  return new Blob([dados.buffer], { type: "audio/wav" });
}

async function falaParaEnviar(blob, contexto) {
  try {
    return wavPcm16(normalizarVolume(await amostrasMono(blob, contexto)));
  } catch (erro) {
    return blob;  // não deu pra converter: manda como gravou
  }
}
