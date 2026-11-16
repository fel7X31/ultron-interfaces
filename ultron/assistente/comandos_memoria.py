"""Comandos de voz da memória: "lembra que minha namorada se chama Ana", "guarda que eu odeio cebola",
"esquece que eu odeio cebola". Perguntas ("o que você lembra de mim?") vão pro Claude, que recebe a memória toda."""
import re

from ..recursos import memoria
from .comandos import comando

MEMORIA = r"mem[oó]ria"
GUARDAR = re.compile(r"^\W*(?:(?:ei|[oô])\s+)?(?:ultron\W+)?(?:por favor\W+)?"
                     r"(?:lembr[ae]|guard[ae]|grav[ae]|memoriz[ae]|(?:anot[ae]|salv[ae]|coloc[ae]|bot[ae]) na " + MEMORIA +
                     r")(?:\s+(?:a[ií]|isso|pra mim|para mim))?\s+(?:que|de que)\s+(.+)$", re.I | re.S)
ESQUECER = re.compile(r"^\W*(?:ultron\W+)?(?:esque[cç][ae]|(?:apag[ae]|tir[ae]) da " + MEMORIA + r")\s+"
                      r"(?:que\s+|de que\s+|o que\s+)?(.+)$", re.I | re.S)
MENOR_LEMBRANCA = 3  # palavras: "lembra que horas são" não é pra guardar


@comando
def guardar_na_memoria(fala):
    achou = GUARDAR.match(fala.texto.strip())
    if not achou or fala.texto.strip().endswith("?") or len(achou.group(1).split()) < MENOR_LEMBRANCA:
        return None
    antes = memoria.ler()
    nova = memoria.guardar(achou.group(1))
    fala.registro["memoria"] = nova["id"]
    if any(i["id"] == nova["id"] for i in antes):
        return "Isso eu já sabia."
    return f"Guardado na memória, em {nova['assunto'].lower()}."


@comando
def esquecer(fala):
    achou = ESQUECER.match(fala.texto.strip())
    if not achou or not fala.curta(25):
        return None
    parecidas = memoria.procurar(achou.group(1).strip(" .!"))
    if not parecidas:
        return "Não achei isso na memória."
    if len(parecidas) > 1:
        return f"Achei {len(parecidas)} lembranças parecidas. Apague a certa pela barra, em Memória."
    memoria.apagar(parecidas[0]["id"])
    fala.registro["memoria_apagada"] = parecidas[0]["id"]
    return "Pronto, esqueci."
