import type { Estado } from "./api";

export function Topo({ estado }: { estado: Estado }) {
  return (
    <header className="topo">
      <span className="marca">Ultron</span>
      <span className="estado">
        <span className="ponto" />
        {estado}
      </span>
    </header>
  );
}
