import { useEffect, useState } from "react";
import { lerConfig, type Config } from "./api";
import { Topo } from "./Topo";
import { useEstado } from "./useEstado";

export function App() {
  const estado = useEstado();
  const [config, setConfig] = useState<Config | null>(null);

  useEffect(() => {
    lerConfig().then(setConfig).catch(() => setConfig(null));
  }, []);

  return (
    <main className="tela" data-estado={estado}>
      <Topo estado={estado} />
      <p className="saudacao">{config ? `Olá, ${config.nome}.` : "Conectando..."}</p>
    </main>
  );
}
