# -*- coding: utf-8 -*-
"""Testes de contracts/tabua_geracional.schema.json contra um CSV real.

Não valida um objeto fabricado à mão -- lê o último
docs/tabua_geracional/tabua_geracional_*.csv gerado pela pipeline de
verdade e valida linha a linha. Pula se a pipeline ainda não rodou (mesmo
padrão de ambiente-de-dados/tests/test_extrator_ibge_historico.py).

Rodar de dentro de tabuas-geracionais-improvement/:
    python -m unittest discover -s tests -v
"""

import csv
import json
import sys
import unittest
from pathlib import Path

from jsonschema import validate, ValidationError

PASTA_RAIZ = Path(__file__).resolve().parent.parent
SCHEMA_PATH = PASTA_RAIZ / "contracts" / "tabua_geracional.schema.json"
PASTA_SAIDA = PASTA_RAIZ / "docs" / "tabua_geracional"


def _ultimo_csv():
    arquivos = sorted(PASTA_SAIDA.glob("tabua_geracional_*.csv"))
    return arquivos[-1] if arquivos else None


def _linha_para_objeto(row):
    return {
        "ano_calendario": int(row["ano_calendario"]),
        "idade": int(row["idade"]),
        "coorte_nascimento": int(row["coorte_nascimento"]),
        "qx_projetado": float(row["qx_projetado"]),
        "improvement_anual_pct": float(row["improvement_anual_pct"]),
        "improvement_acumulado_pct": float(row["improvement_acumulado_pct"]),
        "modelo_origem": row["modelo_origem"],
    }


class TestSchemaEstaValido(unittest.TestCase):
    def test_schema_e_json_valido_e_tem_os_sete_campos(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(set(schema["required"]), {
            "ano_calendario", "idade", "coorte_nascimento", "qx_projetado",
            "improvement_anual_pct", "improvement_acumulado_pct", "modelo_origem",
        })


class TestSchemaContraCsvReal(unittest.TestCase):
    def test_todas_as_linhas_do_ultimo_csv_validam(self):
        csv_path = _ultimo_csv()
        if csv_path is None:
            self.skipTest(
                "Nenhum docs/tabua_geracional/tabua_geracional_*.csv ainda -- "
                "rode scripts/pipeline.py antes deste teste."
            )
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        with open(csv_path, encoding="utf-8") as f:
            linhas = list(csv.DictReader(f))
        self.assertGreater(len(linhas), 0)
        for row in linhas:
            obj = _linha_para_objeto(row)
            try:
                validate(instance=obj, schema=schema)
            except ValidationError as erro:
                self.fail(f"Linha inválida {obj}: {erro.message}")


if __name__ == "__main__":
    unittest.main()
