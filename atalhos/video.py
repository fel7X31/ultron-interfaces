"""Abre um vídeo do YouTube direto (o primeiro resultado da busca), nunca a página de busca.

Se já tiver uma página do YouTube aberta no navegador, abre o vídeo nela mesma (troca o endereço daquela aba);
senão, abre numa aba nova.
  python atalhos/video.py "trailer do filme x"
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ultron.recursos import musica  # noqa: E402
from ultron.recursos.pc import janelas, programas, teclado  # noqa: E402

CONTROL, ENTER = 0x11, 0x0D


def aba_do_youtube():
    """A janela de navegador que está mostrando o YouTube (não a tela do Ultron), ou None."""
    return next((j for j in janelas.listar()
                 if "youtube" in j.titulo.lower() and not j.titulo.startswith(janelas.TELA_DO_ULTRON)), None)


def abrir_na_aba(janela, endereco):
    """Traz a aba pra frente e troca o endereço dela (Ctrl+L, digita, Enter)."""
    janelas.trazer_pra_frente(janela.numero)
    time.sleep(0.25)
    teclado.apertar(CONTROL, ord("L"))
    time.sleep(0.1)
    teclado.digitar(endereco)
    teclado.apertar(ENTER)


def main():
    pedido = " ".join(sys.argv[1:]).strip().strip('"')
    if not pedido:
        return print("Falta dizer qual vídeo.")
    achados = musica.buscar(pedido, limite=1)
    if not achados:
        return print(f"Não achei vídeo de {pedido} no YouTube.")
    video = achados[0]
    endereco = f"https://www.youtube.com/watch?v={video['id']}"
    aba = aba_do_youtube()
    if aba:
        abrir_na_aba(aba, endereco)
        return print(f"Abri na página do YouTube que já estava aberta: {video['titulo']}")
    programas.abrir(endereco)
    print(f"Abri: {video['titulo']}")


if __name__ == "__main__":
    main()
