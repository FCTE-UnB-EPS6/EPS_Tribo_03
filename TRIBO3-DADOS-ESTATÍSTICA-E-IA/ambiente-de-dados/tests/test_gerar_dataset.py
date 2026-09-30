# -*- coding: utf-8 -*-
"""Testes de simular_trajetoria() -- o núcleo da reforma do gerador.

Só a função pura é testada aqui (sem banco): simular_trajetoria recebe
participante+tábua+rng e devolve status/data/exposições, sem tocar o
Postgres. A escrita em staging (inserir_staging, main()) continua
precisando do ambiente Docker da equipe -- não dá para testar de forma
isolada sem reimplementar o schema.

Rodar de dentro de ambiente-de-dados/:
    python -m unittest discover -s tests -v
"""

import random
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import gerar_dataset as gd  # noqa: E402


def participante(nascimento, ingresso, sexo="M", submassa="geral"):
    return {
        "participante_id": "p-teste",
        "submassa": submassa,
        "sexo": sexo,
        "data_nascimento": nascimento,
        "data_ingresso": ingresso,
    }


class TestSimularTrajetoria(unittest.TestCase):
    def setUp(self):
        gd.DATA_REFERENCIA = date(2026, 6, 30)
        # Guarda os originais -- os testes de isolamento zeram
        # desligamento/invalidez/aposentadoria para testar só a
        # mortalidade (ou só um decremento por vez), e precisam
        # devolver os valores reais no final para não vazar entre testes.
        self._taxa_desligamento_orig = gd.TAXA_DESLIGAMENTO_ANUAL
        self._taxa_invalidez_orig = gd.TAXA_INVALIDEZ_ANUAL
        self._taxa_aposentadoria_orig = gd.TAXA_APOSENTADORIA_ANUAL
        self._idade_aposentadoria_orig = dict(gd.IDADE_APOSENTADORIA)

    def tearDown(self):
        gd.TAXA_DESLIGAMENTO_ANUAL = self._taxa_desligamento_orig
        gd.TAXA_INVALIDEZ_ANUAL = self._taxa_invalidez_orig
        gd.TAXA_APOSENTADORIA_ANUAL = self._taxa_aposentadoria_orig
        gd.IDADE_APOSENTADORIA.clear()
        gd.IDADE_APOSENTADORIA.update(self._idade_aposentadoria_orig)

    def test_qx_zero_produz_sempre_ativo_ate_a_data_referencia(self):
        # tábua degenerada: ninguém morre. Zera também desligamento e
        # invalidez -- sem isso o teste "sempre ativo" é falso: com ~36
        # anos de simulação e 3%/ano de desligamento, a chance de NUNCA
        # desligar é baixa, e foi isso que a primeira rodada deste teste
        # pegou (status saiu "desligado", não "ativo") antes deste fix.
        gd.TAXA_DESLIGAMENTO_ANUAL = 0.0
        gd.TAXA_INVALIDEZ_ANUAL = 0.0
        tabua = {"M": {i: 0.0 for i in range(0, 121)}, "F": {i: 0.0 for i in range(0, 121)}}
        rng = random.Random(1)
        p = participante(date(1990, 3, 10), date(2015, 1, 1))
        status, data_mudanca, linhas = gd.simular_trajetoria(p, tabua, rng)
        self.assertEqual(status, "ativo")
        self.assertIsNone(data_mudanca)
        # um ano civil por ano entre ingresso e referência, inclusive
        anos_esperados = gd.DATA_REFERENCIA.year - p["data_ingresso"].year + 1
        self.assertEqual(len(linhas), anos_esperados)
        for linha in linhas:
            self.assertEqual(linha["tipo_saida"], "censura")

    def test_qx_um_mata_no_primeiro_ano_e_trunca_exposicao(self):
        # tábua degenerada: morte certa -- confirma que óbito interrompe
        # o loop (break) e que a exposição do ano de óbito é truncada na
        # data do evento, não no fim do ano civil.
        tabua = {"M": {i: 1.0 for i in range(0, 121)}, "F": {i: 1.0 for i in range(0, 121)}}
        rng = random.Random(1)
        p = participante(date(1990, 3, 10), date(2020, 1, 1))
        status, data_mudanca, linhas = gd.simular_trajetoria(p, tabua, rng)
        self.assertEqual(status, "obito")
        self.assertIsNotNone(data_mudanca)
        self.assertEqual(len(linhas), 1)  # break assim que morre
        self.assertEqual(linhas[0]["tipo_saida"], "obito")
        # exposição do ano de óbito não pode passar de 1 ano cheio
        self.assertLessEqual(linhas[0]["tempo_exposto"], 1.0)
        self.assertEqual(linhas[0]["data_base"], data_mudanca)

    def test_aposentado_continua_exposto_apos_a_data_de_mudanca(self):
        # qx=0 (ninguém morre) e taxa de aposentadoria=100% força
        # aposentadoria assim que elegível -- confirma que a simulação
        # NÃO para no ano da aposentadoria (status != STATUS_QUE_DESLIGAM).
        tabua = {"M": {i: 0.0 for i in range(0, 121)}, "F": {i: 0.0 for i in range(0, 121)}}
        # Isola só o mecanismo de aposentadoria: sem isso, desligamento
        # (3%/ano por padrão) compete e às vezes vence antes dos 30 anos.
        gd.TAXA_DESLIGAMENTO_ANUAL = 0.0
        gd.TAXA_INVALIDEZ_ANUAL = 0.0
        gd.TAXA_APOSENTADORIA_ANUAL = 1.0
        gd.IDADE_APOSENTADORIA["M"] = 30
        rng = random.Random(1)
        p = participante(date(1990, 1, 1), date(2015, 1, 1))  # 25 anos no ingresso
        status, data_mudanca, linhas = gd.simular_trajetoria(p, tabua, rng)
        self.assertEqual(status, "aposentado")
        # simulação continua até DATA_REFERENCIA mesmo após aposentar
        anos_esperados = gd.DATA_REFERENCIA.year - p["data_ingresso"].year + 1
        self.assertEqual(len(linhas), anos_esperados)

    def test_ingresso_no_meio_do_ano_gera_fracao_parcial_no_primeiro_ano(self):
        tabua = {"M": {i: 0.0 for i in range(0, 121)}, "F": {i: 0.0 for i in range(0, 121)}}
        rng = random.Random(1)
        p = participante(date(1990, 1, 1), date(2024, 7, 1))  # entra em jul/2024
        status, data_mudanca, linhas = gd.simular_trajetoria(p, tabua, rng)
        primeiro_ano = linhas[0]
        self.assertEqual(primeiro_ano["ano_calendario"], 2024)
        # de 1/jul a 31/dez é menos de um ano inteiro
        self.assertLess(primeiro_ano["tempo_exposto"], 1.0)
        self.assertGreater(primeiro_ano["tempo_exposto"], 0.4)

    def test_ano_corrente_tambem_e_parcial_ate_a_data_referencia(self):
        gd.TAXA_DESLIGAMENTO_ANUAL = 0.0
        gd.TAXA_INVALIDEZ_ANUAL = 0.0
        tabua = {"M": {i: 0.0 for i in range(0, 121)}, "F": {i: 0.0 for i in range(0, 121)}}
        rng = random.Random(1)
        p = participante(date(1990, 1, 1), date(2010, 1, 1))
        status, data_mudanca, linhas = gd.simular_trajetoria(p, tabua, rng)
        ultimo_ano = linhas[-1]
        self.assertEqual(ultimo_ano["ano_calendario"], 2026)
        # DATA_REFERENCIA = 30/jun/2026 -> só ~metade do ano exposta
        self.assertLess(ultimo_ano["tempo_exposto"], 0.6)

    def test_ingresso_no_mesmo_ano_da_referencia_nao_gera_janela_invertida(self):
        # ingresso em dezembro do próprio ano de referência: janela_fim
        # (30/jun) < janela_inicio (1/dez) só se o loop não filtrasse
        # isso -- o guard `if janela_fim < janela_inicio: continue` cobre
        # exatamente esse caso.
        tabua = {"M": {i: 0.0 for i in range(0, 121)}, "F": {i: 0.0 for i in range(0, 121)}}
        rng = random.Random(1)
        p = participante(date(2000, 1, 1), date(2026, 12, 1))
        status, data_mudanca, linhas = gd.simular_trajetoria(p, tabua, rng)
        self.assertEqual(linhas, [])
        self.assertEqual(status, "ativo")


if __name__ == "__main__":
    unittest.main()
