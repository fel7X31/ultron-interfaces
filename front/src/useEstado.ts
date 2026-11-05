import { useEffect, useState } from "react";
import { ouvirEventos, type Estado } from "./api";

export function useEstado(): Estado {
  const [estado, setEstado] = useState<Estado>("iniciando");
  useEffect(() => ouvirEventos((evento) => {
    if (evento.tipo === "estado" && evento.estado) setEstado(evento.estado);
  }), []);
  return estado;
}
