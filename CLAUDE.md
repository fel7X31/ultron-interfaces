# Ultron (pasta ultron)

Assistente de voz do Miguel. Backend em `ultron/` (camadas: nucleo → voz/recursos → assistente → http → app),
`server.py` só chama `ultron/app.py`. Mais: `palmas.py` (liga com duas palmas), `web/` (tela), `persona.md`
(personalidade), `hooks/` (trava e registro), `tests/`.

**Leia `docs/ARQUITETURA.md` antes de criar algo novo** e siga o padrão: regra em `ultron/recursos/<assunto>.py`,
rotas em `ultron/http/rotas/<assunto>.py` com `@rota`, comando de voz em `ultron/assistente/comandos.py` com
`@comando`. Uma camada só importa das de baixo. Use o que já existe no `nucleo/` (`ler_json`/`salvar_json`,
`log_erro`, `claude_json`, `EVENTOS`, `CFG`) em vez de reescrever. Depois de mudar, rode
`python -m unittest discover -s tests`.

## Coisas a saber
- Mudança em `.py` só vale depois de religar o servidor (o `palmas.py` liga com `server.py --sem-abrir`;
  `.estado/servidor.pid` tem o PID). Em `web/`, basta recarregar a tela.
- A trava (`hooks/trava.py`) e o `.env` o Ultron nunca pode mudar — só o Claude Code.
- O Miguel pode estar com mais de uma sessão do Claude Code mexendo aqui ao mesmo tempo: leia o trecho de novo
  antes de editar.
