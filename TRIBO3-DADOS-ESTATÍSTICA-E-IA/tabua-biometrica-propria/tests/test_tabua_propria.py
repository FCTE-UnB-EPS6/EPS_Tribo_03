# -*- coding: utf-8 -*-
"""Testes de tabua_propria.py -- sem banco."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import tabua_propria as tp  # noqa: E402


class TestGateAe(unittest.TestCase):
    @patch.object(tp, "carregar_taxas_brutas_por_sexo")
    @patch.object(tp, "carregar_ibge")
    @patch.object(tp, "carregar_brems")
    def test_gate_ae_usa_brems_e_agrega_m_f(
        self,
        mock_carregar_brems,
        mock_carregar_ibge,
        mock_carregar_brutas,
    ):
        mock_carregar_brutas.return_value = [
            {"idade": 60, "sexo": "M", "obitos": 1, "exposicao_central": 100.0},
            {"idade": 60, "sexo": "F", "obitos": 1, "exposicao_central": 100.0},
        ]

        mock_carregar_brems.side_effect = [
            {60: 0.01},
            {60: 0.01},
        ]

        mock_carregar_ibge.return_value = {60: 0.50}

        passou, texto = tp.gate_ae(object())

        # BR-EMS: observado = 2; esperado = 1 + 1 = 2; A/E = 1.
        # O valor absurdo do IBGE serve para garantir que ele não decide o gate.
        self.assertTrue(passou)
        self.assertIn("BR-EMS", texto)
        self.assertIn("1.000", texto)

    @patch.object(tp, "carregar_taxas_brutas_por_sexo", return_value=[])
    @patch.object(tp, "carregar_ibge")
    @patch.object(tp, "carregar_brems")
    def test_gate_ae_sem_exposicao_retorna_none(
        self,
        mock_carregar_brems,
        mock_carregar_ibge,
        mock_carregar_brutas,
    ):
        resultado, texto = tp.gate_ae(object())

        self.assertIsNone(resultado)
        self.assertIn("não calculável", texto)


class TestRelatorio(unittest.TestCase):
    def test_gate_inconclusivo_nao_oficializa(self):
        relatorio = tp.montar_relatorio(
            linhas=[],
            gate_aderencia_resultado=(None, "aderência não calculável"),
            gate_ae_resultado=(True, "A/E BR-EMS OK"),
        )

        self.assertIn("REVISAR ANTES DE OFICIALIZAR", relatorio)
        self.assertNotIn("## Veredito: PRONTA PARA OFICIALIZAR", relatorio)

    def test_relatorio_identifica_brems_como_referencia_principal(self):
        relatorio = tp.montar_relatorio(
            linhas=[],
            gate_aderencia_resultado=(True, "aderência OK"),
            gate_ae_resultado=(True, "A/E BR-EMS OK"),
        )

        self.assertIn("BR-EMS", relatorio)
        self.assertIn("referência principal", relatorio)


if __name__ == "__main__":
    unittest.main()`n