"""
Suíte de Testes Automatizados — Passo 6 (Tábuas Geracionais)

Valida as propriedades matemáticas, estatísticas e atuariais de cada módulo:
    - Agregação de séries temporais
    - Teste de tendência de Mann-Kendall
    - Testes de raiz unitária ADF e KPSS
    - Modelo Baseline de Mortality Improvement
    - Modelo Lee-Carter (SVD, normalizações canônicas e Random Walk com Drift)
    - Backtesting temporal e gate de promoção do DoD
    - Projeção da Tábua Geracional

Uso:
    python -m unittest tests/test_passo6.py
"""

import sys
from pathlib import Path
import unittest
import numpy as np

# Adiciona scripts ao sys.path
PASTA_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(PASTA_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(PASTA_SCRIPTS))

from ingestao_passos import (
    carregar_historico_mortalidade,
    carregar_tabua_base_passo5,
    carregar_premissas_passo4,
)
from teste_mann_kendall import calcular_mann_kendall
from teste_estacionariedade import testar_adf, testar_kpss, interpretar_estacionariedade
from modelo_baseline import treinar_baseline, projetar_baseline
from modelo_lee_carter import (
    montar_matriz_mortalidade,
    ajustar_lee_carter,
    treinar_lee_carter,
    projetar_lee_carter,
)
from backtest_temporal import separar_treino_holdout, avaliar_previsoes, executar_backtest
from tabua_geracional import gerar_projecao


class TestPasso6(unittest.TestCase):

    def setUp(self):
        self.dados_teste, self.origem = carregar_historico_mortalidade()

    def test_series_temporais_estrutura_e_limites(self):
        """Verifica se os dados contêm todas as colunas e probabilidades válidas."""
        self.assertGreater(len(self.dados_teste), 100)
        for d in self.dados_teste:
            self.assertIn("ano", d)
            self.assertIn("idade", d)
            self.assertIn("exposicao_central", d)
            self.assertIn("mx", d)
            self.assertIn("qx", d)
            self.assertGreaterEqual(d["qx"], 0.0)
            self.assertLess(d["qx"], 1.0)
            self.assertGreaterEqual(d["exposicao_central"], 0.0)

    def test_mann_kendall_deteccao_tendencia(self):
        """Mortalidade estritamente decrescente deve acusar S < 0 e p-valor significativo."""
        serie_queda = [0.05, 0.045, 0.040, 0.035, 0.030, 0.026, 0.022, 0.019]
        res = calcular_mann_kendall(serie_queda)
        self.assertLess(res["S"], 0)
        self.assertLess(res["p_valor"], 0.05)
        self.assertTrue(res["improvement_confirmado"])

        # Série constante: S deve ser 0
        serie_constante = [0.02, 0.02, 0.02, 0.02, 0.02]
        res_const = calcular_mann_kendall(serie_constante)
        self.assertEqual(res_const["S"], 0)
        self.assertFalse(res_const["improvement_confirmado"])

    def test_estacionariedade_adf_kpss(self):
        """Verifica se os testes ADF e KPSS executam e retornam chaves esperadas."""
        serie = [np.log(0.01 + 0.001 * t) for t in range(15)]
        res_adf = testar_adf(serie)
        res_kpss = testar_kpss(serie)
        diag, exp = interpretar_estacionariedade(res_adf, res_kpss)

        self.assertIn("p_valor", res_adf)
        self.assertIn("stat", res_adf)
        self.assertIn("p_valor", res_kpss)
        self.assertIn("stat", res_kpss)
        self.assertIsInstance(diag, str)

    def test_modelo_baseline_ajuste_e_projecao(self):
        """Verifica se o baseline estima fx não negativo e projeta taxas coerentes."""
        modelo = treinar_baseline(self.dados_teste)
        self.assertIn("por_idade", modelo)
        self.assertGreater(len(modelo["por_idade"]), 20)

        for idade, par in modelo["por_idade"].items():
            self.assertGreaterEqual(par["fx"], 0.0, f"fx negativo na idade {idade}")
            self.assertLessEqual(par["fx"], 0.035, f"fx estourou limite atuarial na idade {idade}")

        # Projeção no futuro deve ser menor ou igual à do ano base
        q_t0 = projetar_baseline(modelo, 40, modelo["ano_base"])
        q_t10 = projetar_baseline(modelo, 40, modelo["ano_base"] + 10)
        self.assertLessEqual(q_t10, q_t0)

    def test_modelo_lee_carter_restricoes_canonicas(self):
        """Lee-Carter canônico exige sum(bx) = 1.0 e sum(kt) = 0.0."""
        modelo = treinar_lee_carter(self.dados_teste)

        soma_bx = float(np.sum(modelo["bx"]))
        self.assertAlmostEqual(soma_bx, 1.0, places=4, msg="sum(bx) deve ser 1.0")

        media_kt = float(np.mean(modelo["kt"]))
        self.assertAlmostEqual(media_kt, 0.0, places=4, msg="mean(kt) deve ser 0.0")

        self.assertGreater(modelo["variancia_explicada"], 0.10, "SVD deve explicar proporção positiva e expressiva da variância")

        # Projeção futura
        ano_ultimo = modelo["anos"][-1]
        q_lc_t0 = projetar_lee_carter(modelo, 50, ano_ultimo)
        q_lc_t10 = projetar_lee_carter(modelo, 50, ano_ultimo + 10)
        self.assertGreater(q_lc_t0, 0.0)
        self.assertLess(q_lc_t0, 1.0)
        self.assertGreater(q_lc_t10, 0.0)
        self.assertLess(q_lc_t10, 1.0)

    def test_backtest_temporal_e_gate_dod(self):
        """Valida a separação de treino/holdout e o cálculo das métricas de erro."""
        anos_treino, anos_holdout, treino, holdout = separar_treino_holdout(self.dados_teste)
        self.assertGreater(len(anos_treino), 0)
        self.assertGreater(len(anos_holdout), 0)
        self.assertEqual(len(anos_treino) + len(anos_holdout), len(sorted({l['ano'] for l in self.dados_teste})))

        resultado = executar_backtest(self.dados_teste)
        self.assertIn("baseline", resultado)
        self.assertIn("lee_carter", resultado)
        self.assertIn("modelo_campeao", resultado)
        self.assertIn(resultado["modelo_campeao"], ["Baseline", "Lee-Carter"])
        self.assertGreaterEqual(resultado["baseline"]["rmse"], 0.0)
        self.assertGreaterEqual(resultado["lee_carter"]["rmse"], 0.0)

    def test_tabua_geracional_consolidacao_completa(self):
        """Garante que a projeção final atenda ao horizonte atuarial de 30 anos."""
        resultado = gerar_projecao(self.dados_teste, horizonte=30)
        self.assertEqual(resultado["horizonte"], 30)
        self.assertGreater(len(resultado["linhas"]), 500)

        for l in resultado["linhas"]:
            self.assertIn("ano_calendario", l)
            self.assertIn("idade", l)
            self.assertIn("coorte_nascimento", l)
            self.assertIn("qx_projetado", l)
            self.assertEqual(l["coorte_nascimento"], l["ano_calendario"] - l["idade"])
            self.assertGreater(l["qx_projetado"], 0.0)
            self.assertLess(l["qx_projetado"], 1.0)

    def test_estrutura_simplificada_e_config(self):
        """Valida a importação direta através dos scripts e config.py."""
        import config
        from db import conectar
        from series_temporais import carregar_dados
        from teste_mann_kendall import calcular_mann_kendall as mk
        from teste_estacionariedade import testar_adf as adf
        from modelo_baseline import treinar_baseline as tb
        from modelo_lee_carter import treinar_lee_carter as tlc
        from backtest_temporal import executar_backtest as eb
        from tabua_geracional import gerar_projecao as gp

        self.assertEqual(config.HORIZONTE_PROJECAO_ANOS, 30)
        self.assertEqual(config.LIMIAR_GANHO_COMPLEXIDADE, 0.05)
        self.assertTrue(callable(conectar))
        self.assertTrue(callable(carregar_dados))
        self.assertTrue(callable(mk))
        self.assertTrue(callable(adf))
        self.assertTrue(callable(tb))
        self.assertTrue(callable(tlc))
        self.assertTrue(callable(eb))
        self.assertTrue(callable(gp))

    def test_ingestao_passos_comunicacao_direta(self):
        """Valida que os dados vêm diretamente dos Passos 1/3, 4 e 5 sem invenção de dados."""
        # 1. Histórico dos Passos 1 ou 3
        dados_h, origem_h = carregar_historico_mortalidade()
        self.assertGreater(len(dados_h), 50)
        self.assertTrue("Passo 1" in origem_h or "Passo 3" in origem_h)

        # 2. Tábua base dos Passos 5 ou 3
        tabua_b, origem_b = carregar_tabua_base_passo5()
        self.assertGreater(len(tabua_b), 40)
        self.assertTrue("Passo 5" in origem_b or "Passo 3" in origem_b)

        # 3. Premissas do Passo 4
        premissas_p4 = carregar_premissas_passo4()
        self.assertEqual(premissas_p4["horizonte_anos"], 30)
        self.assertIn("Passo 4", premissas_p4["origem"])


if __name__ == "__main__":
    unittest.main()

