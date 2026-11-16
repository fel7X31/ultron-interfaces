"""Configuração: caminhos do projeto, .env, preferências da tela, vozes e persona.

CFG é um dicionário único e vivo: quem importa enxerga as mudanças (voz, nome, modos) na hora.
Ordem de prioridade: preferências da tela (.estado/preferencias.json) > variável de ambiente > .env.
"""
import os
from pathlib import Path

from .arquivos import ler_json, salvar_json

RAIZ = Path(__file__).resolve().parents[2]   # a pasta do projeto (jarvis/, ou o nome que ela tiver)
WEB = RAIZ / "web"                            # a tela (HTML/CSS/JS)
ESTADO = RAIZ / ".estado"                     # tudo que é gerado rodando: logs, caches, backups (fora do git)
ATALHOS = RAIZ / "atalhos"                    # scripts que o Ultron roda (mercado, tela, abrir...)
PREFS = ESTADO / "preferencias.json"
PREFIXOS = ("ULTRON_", "JARVIS_", "ELEVENLABS_", "WHISPER_", "FISH_", "OPENAI_", "GEMINI_", "XAI_")
TEMAS = ("prata", "escuro")


def ler_env(caminho):
    valores = {}
    try:
        for linha in Path(caminho).expanduser().read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            k, v = linha.split("=", 1)
            valores[k.strip()] = v.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return valores


def ler_ambiente():
    """As variáveis do Ultron: as do .env, com as do sistema (que tenham um dos PREFIXOS) por cima."""
    base = ler_env("~/.config/vortex-marketing/.env")
    base.update(ler_env(RAIZ / ".env"))
    base.update({k: v for k, v in os.environ.items() if k.startswith(PREFIXOS)})
    for k in [k for k in base if k.startswith("JARVIS_")]:  # nome antigo das variáveis: ainda vale
        base.setdefault("ULTRON_" + k[7:], base[k])
    return base


def variavel(nome, padrao=""):
    """Uma variável do .env ou do sistema (ex.: a chave de outra IA), ou o padrão."""
    return AMBIENTE.get(nome) or padrao


def carregar_config(base):
    return {
        "pasta": Path(base.get("ULTRON_PASTA") or Path.home()).expanduser(),
        "porta": int(base.get("ULTRON_PORTA", "8790")),
        "modelo": base.get("ULTRON_MODELO", "sonnet"),
        "esforco": base.get("ULTRON_ESFORCO", "low"),
        # leve: o Claude abre numa pasta vazia com a sua pasta anexada (responde em ~1 s);
        # completo: abre direto na sua pasta, carregando o CLAUDE.md e a memória dela (bem mais lento)
        "contexto": base.get("ULTRON_CONTEXTO", "leve"),
        "persona": base.get("ULTRON_PERSONA", "persona.md"),
        "eleven_key": base.get("ELEVENLABS_API_KEY", ""),
        "voz": base.get("ULTRON_VOZ", "xHUwLsLfyqiYOIVTzLRW"),
        "modelo_voz": base.get("ULTRON_MODELO_VOZ", "eleven_multilingual_v2"),
        "velocidade_voz": float(base.get("ULTRON_VELOCIDADE_VOZ", "1.0")),
        "fish_key": base.get("FISH_API_KEY", ""),        # vozes com "provedor": "fish" no vozes.json
        "fish_modelo": base.get("FISH_MODELO", "s1"),
        "fish_tom": base.get("FISH_TOM", "").strip(),     # ex.: (confident) (sarcastic)
        "paineis_min": int(base.get("ULTRON_PAINEIS_MIN", "15")),  # e-mails/agenda a cada N min (0 = desliga)
        "transcricao": base.get("ULTRON_TRANSCRICAO", "auto"),
        "whisper_url": base.get("WHISPER_URL", "http://127.0.0.1:8178").rstrip("/"),
        "bloquear": base.get("ULTRON_BLOQUEAR_FERRAMENTAS", ""),
        "aquecer": base.get("ULTRON_AQUECER", "1") == "1",
        "aquecer_atalhos": base.get("ULTRON_AQUECER_ATALHOS", ""),
        "nome": base.get("ULTRON_NOME", "Chefe"),  # como ele te chama (muda no perfil da tela)
        "modo_texto": False,   # responde só escrito, sem voz
        "modo_prova": False,   # revisão dupla, correções guardadas, silêncio com "ok"
        "ia": "claude",        # quem responde: o Claude (com ferramentas) ou outra IA (veja recursos/ias.py)
        "tema": "prata",       # a tela avisa quando muda; a barra do topo acompanha
        "barra": base.get("ULTRON_BARRA", "1") == "1",  # a barra do topo da tela (barra.py)
        "chamado": base.get("ULTRON_CHAMADO", "1") == "1",  # dizer "Ultron" faz ele ouvir o pedido (palmas.py)
    }


def carregar_preferencias():
    p = ler_json(PREFS, {}) or {}
    if p.get("voz"):
        CFG["voz"] = p["voz"]
    if p.get("velocidade"):
        CFG["velocidade_voz"] = float(p["velocidade"])
    if p.get("nome"):
        CFG["nome"] = p["nome"]
    CFG["modo_texto"] = bool(p.get("modo_texto"))
    CFG["modo_prova"] = bool(p.get("modo_prova"))
    for chave in ("ia", "modelo"):
        if p.get(chave):
            CFG[chave] = p[chave]
    if p.get("tema") in TEMAS:
        CFG["tema"] = p["tema"]
    if "chamado" in p:
        CFG["chamado"] = bool(p["chamado"])


def salvar_preferencias():
    salvar_json(PREFS, {"voz": CFG["voz"], "velocidade": CFG["velocidade_voz"], "nome": CFG["nome"],
                        "modo_texto": CFG["modo_texto"], "modo_prova": CFG["modo_prova"],
                        "ia": CFG["ia"], "modelo": CFG["modelo"], "tema": CFG["tema"], "chamado": CFG["chamado"]})


def persona():
    """O texto da personalidade (persona.md, ou o exemplo), com {NOME} trocado pelo nome do dono."""
    for nome in (CFG.get("persona") or "persona.md", "persona.md", "persona.example.md"):
        p = RAIZ / nome
        if p.exists():
            return p.read_text(encoding="utf-8").replace("{NOME}", CFG["nome"])
    return ""


def config_publica():
    """O que a tela pode ver e mudar (sem chaves)."""
    return {"voz": CFG["voz"], "velocidade": CFG["velocidade_voz"], "vozes": VOZES,
            "nome": CFG["nome"], "modo_texto": CFG["modo_texto"], "modo_prova": CFG["modo_prova"],
            "ia": CFG["ia"], "modelo": CFG["modelo"], "tema": CFG["tema"], "chamado": CFG["chamado"]}


def voz_ligada():
    """Responde falando? (tem chave de voz e não está no modo texto)"""
    return bool(CFG["eleven_key"]) and not CFG["modo_texto"]


AMBIENTE = ler_ambiente()
CFG = carregar_config(AMBIENTE)
VOZES = ler_json(RAIZ / "vozes.json", []) or []
carregar_preferencias()
