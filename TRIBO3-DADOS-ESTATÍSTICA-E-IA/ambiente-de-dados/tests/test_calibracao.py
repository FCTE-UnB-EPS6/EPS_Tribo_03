# -*- coding: utf-8 -*-
"""Testes de calibracao.py -- casos de borda que o pipeline de qualidade
não cobre porque eles nunca tocam o banco (são lógica pura do gerador).

Rodar de dentro de ambiente-de-dados/:
    python -m unittest discover -s tests -v

Precisa dos arquivos reais do IBGE em docs/referencias/ (já versionados
pelo Passo 3) -- carregar_tabua_qx() lê o arquivo de verdade, não um
mock, porque o risco que mais importa aqui (layout do xlsx mudar) só
aparece contra o arquivo real.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import calibracao  # noqa: E402


class TestCarregarTabuaQx(unittest.TestCase):
    """Contra o arquivo real do IBGE -- não um fixture fabricado."""

    @classmethod
    def setUpClass(cls):
        cls.tabua = calibracao.carregar_tabua_qx()

    def test_tem_as_duas_chaves_de_sexo(self):
        self.assertEqual(set(self.tabua.keys()), {"M", "F"})

    def test_idades_jovens_tem_qx_baixo_e_idades_avancadas_alto(self):
        # Não é um valor exato (a tábua pode ser reemitida) -- é a
        # ordem de grandeza que carregar_tabua_qx() promete manter.
        jovem = self.tabua["M"][25]
        idoso = self.tabua["M"][80]
        self.assertLess(jovem, 0.01)
        self.assertGreater(idoso, 0.05)
        self.assertLess(jovem, idoso)

    def test_arquivo_ausente_levanta_erro_claro(self):
        tabua_falsa = dict(calibracao.ARQUIVOS_QX)
        calibracao.ARQUIVOS_QX["M"] = "arquivo_que_nao_existe.xlsx"
        try:
            with self.assertRaises(FileNotFoundError):
                calibracao.carregar_tabua_qx()
        finally:
            calibracao.ARQUIVOS_QX.clear()
            calibracao.ARQUIVOS_QX.update(tabua_falsa)


class TestQxAnual(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tabua = calibracao.carregar_tabua_qx()

    def test_aplica_fator_de_selecao(self):
        idade = 60
        qx_bruto = self.tabua["F"][idade]
        esperado = qx_bruto * calibracao.FATOR_SELECAO
        self.assertAlmostEqual(calibracao.qx_anual(self.tabua, idade, "F"), esperado)

    def test_idade_negativa_ou_fracionaria_usa_int(self):
        # idade_exata é float em todo o resto do gerador (dias/365.25);
        # qx_anual precisa aceitar isso sem lançar KeyError.
        a = calibracao.qx_anual(self.tabua, 47.8, "M")
        b = calibracao.qx_anual(self.tabua, 47, "M")
        self.assertAlmostEqual(a, b)

    def test_idade_acima_do_topo_da_tabua_reusa_a_ponta(self):
        topo = max(self.tabua["M"])
        no_topo = calibracao.qx_anual(self.tabua, topo, "M")
        acima = calibracao.qx_anual(self.tabua, topo + 50, "M")
        self.assertAlmostEqual(no_topo, acima)

    def test_idade_abaixo_do_piso_da_tabua_reusa_a_ponta(self):
        piso = min(self.tabua["M"])
        no_piso = calibracao.qx_anual(self.tabua, piso, "M")
        abaixo = calibracao.qx_anual(self.tabua, piso - 10, "M")
        self.assertAlmostEqual(no_piso, abaixo)

    def test_qx_nunca_atinge_ou_passa_de_um(self):
        # Garantia de que um fator de seleção > 1 (se alguém mudar a
        # constante no futuro) não quebra a simulação com morte certa.
        tabua_extrema = {"M": {50: 5.0}, "F": {50: 5.0}}
        self.assertLess(calibracao.qx_anual(tabua_extrema, 50, "M"), 1.0)
        self.assertEqual(calibracao.qx_anual(tabua_extrema, 50, "M"), 0.999999)


class TestDescreverCalibracao(unittest.TestCase):
    def test_nao_lanca_e_contem_o_aviso_de_circularidade(self):
        texto = calibracao.descrever_calibracao()
        self.assertIn("BR-EMS", texto)
        self.assertIn(calibracao.VERSAO_TABUA, texto)


if __name__ == "__main__":
    unittest.main()
