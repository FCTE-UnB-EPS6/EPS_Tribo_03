# -*- coding: utf-8 -*-
"""Testes de contracts/api_modelos.py -- a interface que interfaces_interpassos.md
promete para os Passos 7/8, construída nesta rodada (antes só existia no papel).

Roda contra a série real do IBGE (mesma fonte que scripts/main.py usa por
padrão, ver dados/ingestao_passos.py) -- não é fixture fabricada.

Rodar de dentro de tabuas-geracionais-improvement/:
    python -m unittest discover -s tests -v
"""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contracts.api_modelos import (  # noqa: E402
    obter_parametros_para_passo7, obter_dados_para_passo8,
)


class TestObterParametrosParaPasso7(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p7 = obter_parametros_para_passo7()

    def test_listas_alinhadas_por_idade(self):
        n = len(self.p7["idades"])
        self.assertEqual(len(self.p7["alpha_x"]), n)
        self.assertEqual(len(self.p7["beta_x"]), n)
        self.assertGreater(n, 0)

    def test_kappa_t_alinhado_com_anos_historicos(self):
        self.assertEqual(len(self.p7["kappa_t"]), len(self.p7["anos_historicos"]))

    def test_restricoes_canonicas_de_lee_carter(self):
        # sum(beta_x) = 1 e mean(kappa_t) = 0 -- a mesma garantia que
        # tests/test_passo6.py já cobre em modelos/lee_carter.py
        # diretamente; conferido de novo aqui porque este módulo é quem
        # devolve o valor pro consumidor externo, e um erro de
        # serialização (arredondamento, tipo errado) não apareceria no
        # teste do módulo original.
        self.assertAlmostEqual(sum(self.p7["beta_x"]), 1.0, places=6)
        media_kt = sum(self.p7["kappa_t"]) / len(self.p7["kappa_t"])
        self.assertAlmostEqual(media_kt, 0.0, places=6)

    def test_tipos_sao_nativos_e_serializaveis_em_json(self):
        # O ponto inteiro deste contrato é servir Passo 7/8 (e, no futuro,
        # uma API HTTP) -- um numpy.float64 ou numpy.ndarray escapando
        # daqui quebraria json.dumps silenciosamente em produção.
        texto = json.dumps(self.p7)
        de_volta = json.loads(texto)
        self.assertEqual(de_volta["idades"], self.p7["idades"])

    def test_drift_negativo_reflete_melhora_de_mortalidade(self):
        # Consistente com o resultado real já documentado (Mann-Kendall
        # confirmou queda estatisticamente significante nesta mesma
        # série) -- drift positivo aqui seria uma bandeira de que algo
        # mudou na fonte ou na convenção de sinal do modelo.
        self.assertLess(self.p7["drift"], 0)

    def test_origem_dados_e_string_nao_vazia(self):
        self.assertIsInstance(self.p7["origem_dados"], str)
        self.assertGreater(len(self.p7["origem_dados"]), 0)


class TestObterDadosParaPasso8(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p8 = obter_dados_para_passo8()

    def test_campeao_e_um_dos_dois_modelos_validos(self):
        self.assertIn(self.p8["modelo_campeao"], ("Baseline", "Lee-Carter"))

    def test_metricas_tem_as_quatro_chaves_pedidas_pelo_contrato(self):
        # RMSE, MAE, MAPE, Chi2 -- exatamente o que
        # docs/interfaces_interpassos.md §3.2 promete para o Passo 8.
        for bloco in (self.p8["metricas_baseline"], self.p8["metricas_lee_carter"]):
            for chave in ("rmse", "mae", "mape", "chi2_obitos", "n_celulas"):
                self.assertIn(chave, bloco)

    def test_previsoes_holdout_cobrem_todas_as_celulas_do_holdout(self):
        self.assertEqual(
            len(self.p8["previsoes_holdout_campeao"]), self.p8["metricas_baseline"]["n_celulas"]
        )

    def test_previsoes_tem_os_seis_campos_por_celula(self):
        linha = self.p8["previsoes_holdout_campeao"][0]
        for campo in ("idade", "ano", "q_observado", "q_previsto", "obitos", "exposicao"):
            self.assertIn(campo, linha)

    def test_json_serializavel(self):
        texto = json.dumps(self.p8)
        de_volta = json.loads(texto)
        self.assertEqual(de_volta["modelo_campeao"], self.p8["modelo_campeao"])

    def test_anos_holdout_vem_depois_dos_anos_treino(self):
        self.assertLess(max(self.p8["anos_treino"]), min(self.p8["anos_holdout"]))


if __name__ == "__main__":
    unittest.main()
