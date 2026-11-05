# Ultron (pasta ultron)

Assistente de voz do Miguel. Backend em `ultron/` (camadas: nucleo → voz/recursos → assistente → http → app),
`server.py` só chama `ultron/app.py`. Mais: `palmas.py` (liga com duas palmas), `web/` (tela), `persona.md`
(personalidade), `hooks/` (trava e registro), `tests/`.

**Leia `docs/ARQUITETURA.md` antes de criar algo novo** e siga o padrão: regra em `ultron/recursos/<assunto>.py`,
rotas em `ultron/http/rotas/<assunto>.py` com `@rota`, comando de voz em `ultron/assistente/comandos.py` com
`@comando`. Uma camada só importa das de baixo. Use o que já existe no `nucleo/` (`ler_json`/`salvar_json`,
`log_erro`, `claude_json`, `EVENTOS`, `CFG`) em vez de reescrever. Depois de mudar, rode
`python -m unittest discover -s tests`.

## Antes de mexer em qualquer coisa: revise o que o Ultron mudou

O próprio Ultron pode editar o código dele (com confirmação do Miguel). Toda mudança fica em `MUDANCAS-ULTRON.md`,
escrita automaticamente pelo `hooks/registro.py`: pedido do Miguel, arquivo, trecho antes/depois, backup em
`.estado/backups/` e, em seguida, o resumo do Ultron.

No começo de qualquer tarefa nesta pasta:
1. Leia as entradas de `MUDANCAS-ULTRON.md` que ainda não têm a linha `Revisado pelo Claude Code`.
2. Para cada uma, confira no arquivo atual se a mudança está certa e coerente com o resto do código. Atenção
   especial a função nova, lógica mais complicada, algo que mexa em trava, confirmação, tempo de resposta, voz ou
   no que outras partes usam. Veja se o "Resumo do Ultron" bate com o que o trecho faz.
3. Se estiver ok, acrescente abaixo da entrada: `Revisado pelo Claude Code (AAAA-MM-DD): ok` (com uma observação
   curta, se houver). Se tiver problema, corrija (ou volte o backup) e anote:
   `Revisado pelo Claude Code (AAAA-MM-DD): corrigido — o que estava errado e o que foi feito`.
4. Conte pro Miguel, em poucas linhas, o que o Ultron mudou desde a última revisão e o que você achou.

Se não houver entrada nova, siga direto com a tarefa.

## Coisas a saber
- Mudança em `.py` só vale depois de religar o servidor (o `palmas.py` liga com `server.py --sem-abrir`;
  `.estado/servidor.pid` tem o PID). Em `web/`, basta recarregar a tela.
- A trava (`hooks/trava.py`) e o `.env` o Ultron nunca pode mudar — só o Claude Code.
- O Miguel pode estar com mais de uma sessão do Claude Code mexendo aqui ao mesmo tempo: leia o trecho de novo
  antes de editar.
