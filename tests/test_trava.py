"""A trava (hooks/trava.py): o que passa direto e o que precisa da confirmação do dono."""
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO = RAIZ / "hooks" / "trava.py"
_spec = importlib.util.spec_from_file_location("trava", ARQUIVO)
trava = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(trava)
CASA = os.path.expanduser("~")


class TesteRegras(unittest.TestCase):
    PASTA = os.path.join(CASA, "segundo-cerebro")

    def test_escrever_na_pasta_do_usuario_passa(self):
        for caminho in (os.path.join(CASA, "Desktop", "lista.txt"), str(RAIZ / "web" / "index.html"),
                        os.path.join(self.PASTA, "tarefas.md"), "/c" + CASA[2:].replace("\\", "/") + "/Desktop/a.txt"):
            self.assertTrue(trava.pode_escrever(caminho, self.PASTA), caminho)

    def test_pastas_de_configuracao_e_do_windows_perguntam(self):
        for caminho in (os.path.join(CASA, "AppData", "Roaming", "x.txt"), os.path.join(CASA, ".claude", "settings.json"),
                        os.path.join(CASA, ".ssh", "config"), "C:/Windows/System32/drivers/etc/hosts", ""):
            self.assertFalse(trava.pode_escrever(caminho, self.PASTA), caminho)

    def test_busca_com_curl_passa_e_envio_pergunta(self):
        busca = 'curl -s -A "Mozilla/5.0 (ultron)" -G "https://en.wikipedia.org/w/api.php" --data-urlencode "titles=X"'
        self.assertFalse(trava.envia_dados(busca))
        self.assertFalse(trava.envia_dados("curl -s https://site.com/imagem.jpg -o foto.jpg"))
        self.assertFalse(trava.envia_dados("curl -X POST http://127.0.0.1:8790/api/mostrar -d '{}'"))
        self.assertTrue(trava.envia_dados("curl -X POST https://api.site.com/posts"))
        self.assertTrue(trava.envia_dados('curl -d "a=1" https://site.com/form'))
        self.assertTrue(trava.envia_dados("curl -F arquivo=@foto.jpg https://site.com/upload"))

    def test_comandos_de_terminal(self):
        def arriscado(cmd):
            return any(re.search(padrao, cmd) for padrao in trava.BASH_ARRISCADO)

        for cmd in ("rm -rf pasta", "del arquivo.txt", "taskkill /IM chrome.exe /F", "shutdown /s /t 0",
                    "git push origin main", "powershell -c Remove-Item x"):
            self.assertTrue(arriscado(cmd), cmd)
        for cmd in ("mv a.txt pasta/", "nvidia-smi --format=csv", "python atalhos/pc.py volume 30", "ls -la",
                    "git status", "tee nota.txt"):
            self.assertFalse(arriscado(cmd), cmd)


class TesteHook(unittest.TestCase):
    """Roda o hook de verdade, como o Claude roda (com um .estado de mentira)."""

    def rodar(self, ferramenta, entrada, confirmado=False):
        with tempfile.TemporaryDirectory() as estado:
            if confirmado:
                Path(estado, "confirmado").write_text("1")
            env = {**os.environ, "ULTRON_ESTADO": estado, "ULTRON_PASTA": os.path.join(CASA, "segundo-cerebro")}
            r = subprocess.run([sys.executable, str(ARQUIVO)], input=json.dumps({"tool_name": ferramenta, "tool_input": entrada}),
                               capture_output=True, text=True, encoding="utf-8", env=env, timeout=20)
            anotado = Path(estado, "trava.jsonl").exists()
        return r.returncode, anotado

    def test_passa_direto(self):
        self.assertEqual(self.rodar("Write", {"file_path": os.path.join(CASA, "Desktop", "x.txt")})[0], 0)
        self.assertEqual(self.rodar("Bash", {"command": "mv a.txt b.txt"})[0], 0)
        self.assertEqual(self.rodar("Read", {"file_path": "C:/Windows/win.ini"})[0], 0)

    def test_barra_e_anota(self):
        self.assertEqual(self.rodar("Write", {"file_path": "C:/Windows/x.txt"}), (2, True))
        self.assertEqual(self.rodar("Bash", {"command": "rm -rf /c/Users/x"}), (2, True))
        self.assertEqual(self.rodar("mcp__claude_ai_Gmail__send_message", {}), (2, True))

    def test_confirmado_passa_mas_a_trava_nunca(self):
        self.assertEqual(self.rodar("Bash", {"command": "rm nota.txt"}, confirmado=True)[0], 0)
        self.assertEqual(self.rodar("Edit", {"file_path": str(ARQUIVO)}, confirmado=True)[0], 2)


if __name__ == "__main__":
    unittest.main()
