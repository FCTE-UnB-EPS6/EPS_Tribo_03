# -*- coding: utf-8 -*-
"""Testes de comparacao_ae.py -- sem banco.

calcular_ae() é lógica pura (recebe os três dicionários já carregados);
só ela é testada aqui, com dados fabricados de propósito para os casos
de borda. carregar_brems()/carregar_ibge() são testados contra os
arquivos reais em ambiente-de-dados/docs/referencias/ -- sem eles, este
módulo não tem como rodar de verdade (não existe mock de tábua real).

Rodar de dentro de tabua-biometrica-propria/:
    python -m unittest discover -s tests -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import comparacao_ae as cae  # noqa: E402


class TestCarregarReferenciasReais(unittest.TestCase):
    """Contra os arquivos reais do Passo 3 -- pula se não estiverem lá."""

    def setUp(self):
        if not cae.ARQUIVO_BREMS.exists():
            self.skipTest(f"{cae.ARQUIVO_BREMS} não encontrado -- Passo 3 já baixou?")

    def test_brems_tem_as_duas_abas_e_qx_crescente_com_idade(self):
        m = cae.carregar_brems("BR-EMSsb-2026-m")
        f = cae.carregar_brems("BR-EMSsb-2026-f")
        self.assertGreater(len(m), 50)
        self.assertGreater(len(f), 50)
        self.assertLess(m[30], m[80])  # qx aos 30 < qx aos 80

    def test_ibge_e_brems_discordam_o_bastante_pra_nao_serem_a_mesma_fonte(self):
        # Checagem de sanidade do Risco 02: se as duas referências dessem
        # exatamente o mesmo número, usar uma ou outra como "principal"
        # não faria diferença nenhuma -- e faz, porque são tábuas
        # independentes (população geral vs. experiência de previdência).
        ibge = cae.carregar_ibge("ibge_2024_homens.xlsx")
        brems = cae.carregar_brems("BR-EMSsb-2026-m")
        idade = 60
        self.assertIn(idade, ibge)
        self.assertIn(idade, brems)
        self.assertNotAlmostEqual(ibge[idade], brems[idade], places=4)


class TestCalcularAe(unittest.TestCase):
    def test_brems_e_ibge_sao_calculados_em_paralelo_e_independentes(self):
        brutas = [{"idade": 60, "sexo": "M", "obitos": 2, "exposicao_central": 100.0}]
        brems = {"M": {60: 0.01}, "F": {}}
        ibge = {"M": {60: 0.02}, "F": {}, "Ambos": {60: 0.018}}
        linhas = cae.calcular_ae(brutas, brems, ibge)
        linha_m = next(l for l in linhas if l["categoria"] == "M")
        # esperado BR-EMS = 0.01 * 100 = 1.0 -> razão = 2/1.0 = 2.0
        self.assertAlmostEqual(linha_m["razao_ae_brems"], 2.0)
        # esperado IBGE = 0.02 * 100 = 2.0 -> razão = 2/2.0 = 1.0
        self.assertAlmostEqual(linha_m["razao_ae_ibge_diagnostico"], 1.0)
        # as duas razões têm que ser diferentes -- é o ponto inteiro da
        # mudança: cada referência responde uma pergunta diferente.
        self.assertNotEqual(linha_m["razao_ae_brems"], linha_m["razao_ae_ibge_diagnostico"])

    def test_categoria_ambos_so_existe_no_diagnostico_ibge(self):
        brutas = [
            {"idade": 60, "sexo": "M", "obitos": 1, "exposicao_central": 50.0},
            {"idade": 60, "sexo": "F", "obitos": 1, "exposicao_central": 50.0},
        ]
        brems = {"M": {60: 0.01}, "F": {60: 0.008}}
        ibge = {"M": {60: 0.02}, "F": {60: 0.015}, "Ambos": {60: 0.0175}}
        linhas = cae.calcular_ae(brutas, brems, ibge)
        linha_ambos = next(l for l in linhas if l["categoria"] == "Ambos")
        self.assertIsNone(linha_ambos["razao_ae_brems"])
        self.assertIsNone(linha_ambos["qx_brems"])
        self.assertIsNotNone(linha_ambos["razao_ae_ibge_diagnostico"])

    def test_idade_sem_referencia_em_nenhuma_tabua_e_descartada(self):
        brutas = [{"idade": 150, "sexo": "M", "obitos": 0, "exposicao_central": 5.0}]
        linhas = cae.calcular_ae(brutas, {"M": {}, "F": {}}, {"M": {}, "F": {}, "Ambos": {}})
        self.assertEqual([l for l in linhas if l["categoria"] == "M"], [])

    def test_exposicao_zero_nao_gera_divisao_por_zero(self):
        brutas = [{"idade": 60, "sexo": "M", "obitos": 0, "exposicao_central": 0.0}]
        brems = {"M": {60: 0.01}, "F": {}}
        ibge = {"M": {60: 0.02}, "F": {}, "Ambos": {60: 0.018}}
        linhas = cae.calcular_ae(brutas, brems, ibge)
        self.assertEqual([l for l in linhas if l["categoria"] == "M"], [])

    def test_falta_so_brems_mantem_linha_com_diagnostico_ibge(self):
        # idade coberta pelo IBGE mas fora da tábua BR-EMS (ex.: acima
        # dos ~116 anos que a BR-EMS cobre) -- a linha não deve
        # desaparecer inteira, só o lado BR-EMS fica None.
        brutas = [{"idade": 60, "sexo": "M", "obitos": 1, "exposicao_central": 10.0}]
        brems = {"M": {}, "F": {}}  # BR-EMS não cobre essa idade
        ibge = {"M": {60: 0.02}, "F": {}, "Ambos": {60: 0.02}}
        linhas = cae.calcular_ae(brutas, brems, ibge)
        linha_m = next(l for l in linhas if l["categoria"] == "M")
        self.assertIsNone(linha_m["razao_ae_brems"])
        self.assertIsNotNone(linha_m["razao_ae_ibge_diagnostico"])


class TestRelatorio(unittest.TestCase):
    def test_relatorio_rotula_ibge_como_diagnostico_e_brems_como_principal(self):
        brutas = [{"idade": 60, "sexo": "M", "obitos": 2, "exposicao_central": 100.0}]
        brems = {"M": {60: 0.01}, "F": {}}
        ibge = {"M": {60: 0.02}, "F": {}, "Ambos": {60: 0.02}}
        linhas = cae.calcular_ae(brutas, brems, ibge)
        texto = cae.montar_relatorio(linhas)
        self.assertIn("BR-EMS (principal)", texto)
        self.assertIn("IBGE (diagnóstico", texto)
        self.assertIn("não use a razão", texto.lower())


if __name__ == "__main__":
    unittest.main()
