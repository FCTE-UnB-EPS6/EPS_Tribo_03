"""Contrato de extração com Postgres real, opcional e somente leitura.

PASSO2_TESTAR_POSTGRES=1 DATA_REFERENCIA=AAAA-MM-DD python -m unittest discover -s tests -v
"""
from datetime import date
from contextlib import redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import sys
import unittest
from tempfile import TemporaryDirectory

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.construir_dataset import construir_dataset_analitico, extrair_do_banco
from scripts.registro import sha256
from main import executar_pipeline


@unittest.skipUnless(os.environ.get('PASSO2_TESTAR_POSTGRES') == '1',
                     'Requer Postgres curado; ativar PASSO2_TESTAR_POSTGRES=1')
class PostgresTest(unittest.TestCase):
    def test_contrato_curado_uma_linha_por_pessoa_sem_cpf(self):
        ref = date.fromisoformat(os.environ['DATA_REFERENCIA'])
        raw = extrair_do_banco()
        self.assertGreater(len(raw), 0, 'Passo 1 ainda não carregado')
        self.assertFalse(raw.participante_id.duplicated().any())
        self.assertNotIn('cpf_sintetico', raw.columns)
        df, exclusoes = construir_dataset_analitico(raw, ref, retornar_exclusoes=True)
        self.assertGreater(len(df), 0)
        self.assertEqual(len(raw), len(df)+len(exclusoes))
        self.assertFalse(df.exposicao_oficial_anos.isna().any(), 'Pessoa analítica sem exposição oficial')
        self.assertTrue(df.exposicao_oficial_anos.gt(0).all())
        sem_exposicao = set(raw.loc[raw.exposicao_oficial_anos.isna(), 'participante_id'])
        auditados = set(exclusoes.loc[exclusoes.motivos.str.contains('exposicao_oficial_ausente'),
                                     'participante_id'])
        self.assertTrue(sem_exposicao.issubset(auditados), 'Ausência de exposição não auditada')

    def test_pipeline_completo_no_postgres_sem_modificar_a_fonte(self):
        antes = extrair_do_banco()
        with TemporaryDirectory() as temp, redirect_stdout(StringIO()):
            codigo = executar_pipeline(saida=temp,
                data_referencia=os.environ['DATA_REFERENCIA'],
                identificacao_fonte='Teste de integração no Postgres curado',
                data_corte=os.environ.get('DATA_CORTE', '2016-01-01'), horizonte=5.)
            self.assertIn(codigo, [0, 2])
            out = Path(temp)
            fechamento = json.loads((out/'fechamento.json').read_text())
            self.assertEqual(fechamento['status_execucao'], 'concluida')
            self.assertTrue(all(e['status'] == 'concluida' for e in fechamento['etapas']))
            for nome in ['cox.joblib', 'rsf.joblib', 'estimativas_teste.csv']:
                self.assertTrue((out/'avaliacao/modelos'/nome).is_file(), nome)
            estimativas = pd.read_csv(out/'avaliacao/modelos/estimativas_teste.csv')
            self.assertFalse(estimativas.empty)
            for prefixo in ['cox', 'rsf']:
                probabilidades = estimativas[f'{prefixo}_prob_sobrevivencia']
                self.assertTrue(probabilidades.notna().all())
                self.assertTrue(probabilidades.between(0, 1).all())
            manifesto = json.loads((out/'manifesto_artefatos.json').read_text())
            for nome, digest in manifesto['arquivos'].items():
                self.assertEqual(sha256(out/nome), digest, nome)
        pd.testing.assert_frame_equal(antes, extrair_do_banco())


if __name__ == '__main__':
    unittest.main()
