"""Tamanho e cor marcados num trecho do currículo: o que fica ao salvar e o que vai pro Word."""
import unittest

from ultron.recursos import curriculo


class TesteTrecho(unittest.TestCase):
    def test_trecho_mantem_tamanho_e_cor(self):
        limpo = curriculo.sanear_html('<p><span class="trecho" style="font-size: 16pt; color: rgb(255, 0, 0);">oi</span></p>')[0]
        self.assertEqual(limpo, '<p><span class="trecho" style="font-size:16pt;color:#ff0000">oi</span></p>')

    def test_salvar_de_novo_nao_muda(self):
        limpo = curriculo.sanear_html('<p><span class="trecho" style="color:#00ff00">oi</span></p>')[0]
        self.assertEqual(curriculo.sanear_html(limpo)[0], limpo)

    def test_estilo_colado_some(self):
        limpo = curriculo.sanear_html('<p><span style="font-size: 40pt; color: red">oi</span></p>')[0]
        self.assertEqual(limpo, "<p>oi</p>")

    def test_so_passa_tamanho_e_cor_validos(self):
        bruto = '<p><span class="trecho" style="background-color: #123456; font-size: 900pt; position: fixed">oi</span></p>'
        self.assertEqual(curriculo.sanear_html(bruto)[0], '<p><span class="trecho" style="font-size:40pt">oi</span></p>')

    def test_word_recebe_tamanho_e_cor_do_trecho(self):
        bruto = '<p>normal <span class="trecho" style="font-size:16pt;color:#ff0000">grande</span></p>'
        estilo = curriculo.normalizar_estilo(None)
        xml = "".join(curriculo._corpo_docx_html(curriculo.sanear_html(bruto)[1], estilo))
        self.assertIn('<w:color w:val="FF0000"/><w:sz w:val="32"/><w:szCs w:val="32"/></w:rPr><w:t xml:space="preserve">grande', xml)
        self.assertNotIn('<w:color w:val="FF0000"/></w:rPr><w:t xml:space="preserve">normal', xml)

    def test_trecho_dentro_de_trecho_vale_o_de_dentro(self):
        bruto = ('<p><span class="trecho" style="font-size:16pt"><span class="trecho" style="font-size:20pt;color:#0000ff">x</span></span></p>')
        estilo = curriculo.normalizar_estilo(None)
        xml = "".join(curriculo._corpo_docx_html(curriculo.sanear_html(bruto)[1], estilo))
        self.assertIn('<w:color w:val="0000FF"/><w:sz w:val="40"/>', xml)


if __name__ == "__main__":
    unittest.main()
