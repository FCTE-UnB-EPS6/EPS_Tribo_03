# -*- coding: utf-8 -*-
"""Testes de extrator_ibge_historico.py.

test_carregar_tabua_contra_arquivos_reais só roda se a extração já foi
executada pelo menos uma vez (docs/referencias/ibge_historico/ existe) --
ela não baixa nada sozinha, para não acoplar a suíte de testes padrão à
rede. Os demais testes são de lógica pura (URL, validação de ano).
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import extrator_ibge_historico as ext  # noqa: E402


class TestUrlEValidacaoDeAno(unittest.TestCase):
    def test_url_usa_xls_ate_2020_e_xlsx_de_2021_em_diante(self):
        self.assertTrue(ext._url_arquivo(2020, "M").endswith(".xls"))
        self.assertTrue(ext._url_arquivo(2021, "M").endswith(".xlsx"))

    def test_ano_fora_do_intervalo_levanta_valueerror_claro(self):
        with self.assertRaises(ValueError):
            ext._url_arquivo(2014, "M")
        with self.assertRaises(ValueError):
            ext._url_arquivo(2025, "M")

    def test_url_contem_o_ano_e_a_categoria_certos(self):
        url = ext._url_arquivo(2024, "F")
        self.assertIn("2024", url)
        self.assertIn("mulheres.xlsx", url)


class TestCarregarTabuaContraArquivosReais(unittest.TestCase):
    """Só roda se a extração real já populou docs/referencias/ibge_historico/."""

    def test_carrega_2015_e_2024_com_mesmo_layout(self):
        pasta = ext.PASTA_RAIZ
        caminho_2015 = pasta / "2015" / "homens.xls"
        caminho_2024 = pasta / "2024" / "homens.xlsx"
        if not (caminho_2015.exists() and caminho_2024.exists()):
            self.skipTest(
                "docs/referencias/ibge_historico/ ainda não foi gerado -- "
                "rode extrator_ibge_historico.py antes deste teste."
            )
        df_2015 = ext.carregar_tabua(caminho_2015)
        df_2024 = ext.carregar_tabua(caminho_2024)
        self.assertIn("idade", df_2015.columns)
        self.assertIn("qx", df_2015.columns)
        self.assertGreater(len(df_2015), 50)
        self.assertGreater(len(df_2024), 50)
        # mortalidade infantil (idade 0) deve ter melhorado de 2015 pra 2024
        qx0_2015 = df_2015.loc[df_2015["idade"] == 0, "qx"].iloc[0]
        qx0_2024 = df_2024.loc[df_2024["idade"] == 0, "qx"].iloc[0]
        self.assertLess(qx0_2024, qx0_2015)


if __name__ == "__main__":
    unittest.main()
