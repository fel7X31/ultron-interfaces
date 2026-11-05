export type Estado = "iniciando" | "aquecendo" | "parado" | "ouvindo" | "transcrevendo" | "pensando" | "falando";

export type Evento = { tipo: string; estado?: Estado };

export type Voz = { id: string; nome: string; genero: string; descricao: string; provedor?: string };

export type Config = {
  nome: string;
  voz: string;
  velocidade: number;
  vozes: Voz[];
  modo_texto: boolean;
  modo_prova: boolean;
};

export async function lerConfig(): Promise<Config> {
  const resposta = await fetch("/api/config");
  return resposta.json();
}

export function ouvirEventos(aoReceber: (evento: Evento) => void): () => void {
  const fonte = new EventSource("/api/eventos");
  fonte.onmessage = (mensagem) => aoReceber(JSON.parse(mensagem.data));
  return () => fonte.close();
}
