"""Regressões de procedência, dependência, padrões e evidências de rodada."""
from contextlib import redirect_stdout
from datetime import date
from io import StringIO
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import joblib
import numpy as np
import pandas as pd

SCRIPTS = Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0, str(SCRIPTS.parent))
from scripts.construir_dataset import construir_dataset_analitico, gerar_dados_locais
from scripts.cox_ph import ajustar_cox, gerar_graficos
from scripts.avaliacao import COVARIAVEIS, avaliar_subgrupos
from scripts.comparar_modelos import validacao_temporal
from scripts.diagnosticos import diagnosticar_covariaveis, verificar_padrao_mortalidade, status_direcao
from scripts.registro import NOTA_USO, sha256, salvar_json, validar_procedencia
from scripts.relatorios import criterios_issue34, escrever_cards, verificar_pendencias


def fixture_com_padrao(n=1200):
    """DGP de teste com efeito conhecido; NÃO é lote IBGE/Postgres."""
    rng = np.random.default_rng(72)
    idade = rng.uniform(20, 55, n)
    sexo = rng.integers(0, 2, n)
    tempo_evento = rng.exponential(1/(.02*np.exp(.08*(idade-30)+.6*sexo)))
    tempo = np.minimum(tempo_evento, 12.)
    dados = construir_dataset_analitico(gerar_dados_locais(n, 42, date(2026, 8, 31)))
    dados['idade_ingresso'] = idade
    dados['sexo_M'] = sexo
    dados['sexo'] = np.where(sexo, 'M', 'F')
    dados['tempo_observado'] = tempo
    dados['evento'] = (tempo_evento <= 12).astype(int)
    return dados


class ProcedenciaTest(unittest.TestCase):
    def preparar(self, raiz, fonte='local'):
        path = Path(raiz)/'dataset.csv'
        df = construir_dataset_analitico(gerar_dados_locais(30))
        df['fonte_dados'] = fonte
        df.to_csv(path, index=False)
        meta = dict(fonte=fonte, identificacao_fonte='lote-de-teste',
            dataset_sha256=sha256(path), data_referencia='2026-08-31',
            n_analitico=len(df), n_obitos=int(df.evento.sum()))
        salvar_json(path.with_suffix('.metadata.json'), meta)
        return path, meta

    def test_fixture_exige_opt_in_em_todos_os_relatorios(self):
        with TemporaryDirectory() as temp:
            path, _ = self.preparar(temp)
            with self.assertRaisesRegex(ValueError, 'fonte banco'):
                validar_procedencia(path)
            df, meta = validar_procedencia(path, permitir_fixture=True)
            self.assertEqual(meta['fonte'], 'local')
            self.assertEqual(len(df), 30)
            result = subprocess.run([sys.executable, str(SCRIPTS.parent/'main.py'),
                '--dataset', str(path), '--data-corte', '2016-01-01',
                '--saida', str(Path(temp)/'rodada')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn('construir_dataset falhou', result.stderr)
            erro = json.loads((Path(temp)/'rodada/falha_execucao.json').read_text())
            self.assertEqual(erro['tipo_erro'], 'ValueError')
            self.assertFalse(list((Path(temp)/'rodada').glob('*.log')))
            self.assertFalse((Path(temp)/'rodada/model_card.md').exists())

    def test_hash_alterado_e_manifesto_ausente_falham(self):
        with TemporaryDirectory() as temp:
            path, _ = self.preparar(temp)
            path.write_text(path.read_text()+'\n')
            with self.assertRaisesRegex(ValueError, 'Hash'):
                validar_procedencia(path, True)
            path.with_suffix('.metadata.json').unlink()
            with self.assertRaisesRegex(ValueError, 'Manifesto ausente'):
                validar_procedencia(path, True)

    def test_referencia_e_origem_linhas_divergentes_falham(self):
        with TemporaryDirectory() as temp:
            path, meta = self.preparar(temp)
            meta['data_referencia'] = '2025-01-01'
            salvar_json(path.with_suffix('.metadata.json'), meta)
            with self.assertRaisesRegex(ValueError, 'Referência'):
                validar_procedencia(path, True)
            meta['fonte'] = 'banco'
            salvar_json(path.with_suffix('.metadata.json'), meta)
            with self.assertRaisesRegex(ValueError, 'fonte das linhas'):
                validar_procedencia(path)

    def test_hash_valido_nao_aceita_alvo_covariavel_ou_data_incoerente(self):
        with TemporaryDirectory() as temp:
            for coluna, valor in [('evento', 2), ('tempo_observado', -1),
                                  ('sexo_M', float('inf')), ('idade_ingresso', 999),
                                  ('data_fim', '2020-01-01')]:
                with self.subTest(coluna=coluna):
                    path, meta = self.preparar(temp, 'banco')
                    df = pd.read_csv(path)
                    df.loc[0, coluna] = valor
                    df.to_csv(path, index=False)
                    meta['dataset_sha256'] = sha256(path)
                    meta['n_obitos'] = int(df.evento.sum())
                    salvar_json(path.with_suffix('.metadata.json'), meta)
                    with self.assertRaisesRegex(ValueError, 'inconsistente'):
                        validar_procedencia(path)

    def test_hash_bruto_e_exclusoes_sao_conferidos(self):
        with TemporaryDirectory() as temp:
            for sufixo, campo in [('.bruto.csv', 'bruto_sha256'), ('.exclusoes.csv', 'exclusoes_sha256')]:
                with self.subTest(sufixo=sufixo):
                    path, meta = self.preparar(temp, 'banco')
                    bruto = path.with_suffix(sufixo)
                    bruto.write_text('participante_id,motivos\n')
                    meta[campo] = sha256(bruto)
                    salvar_json(path.with_suffix('.metadata.json'), meta)
                    validar_procedencia(path)
                    bruto.write_text(bruto.read_text()+'adulterado\n')
                    with self.assertRaisesRegex(ValueError, 'Hash/arquivo'):
                        validar_procedencia(path)
                    bruto.unlink()
                    with self.assertRaisesRegex(ValueError, 'Hash/arquivo'):
                        validar_procedencia(path)


class DiagnosticosTest(unittest.TestCase):
    def test_dois_registros_nao_serializam_nan(self):
        df = construir_dataset_analitico(gerar_dados_locais(2))
        df['idade_ingresso'] = [20., 40.]
        df['sexo_M'] = [0, 1]
        diag = diagnosticar_covariaveis(df)
        json.dumps(diag, allow_nan=False)

    def test_dependencia_conhecida_e_constante_documentadas(self):
        df = construir_dataset_analitico(gerar_dados_locais(150))
        df['plano_CD'] = df.plano_BD  # dependência perfeita injetada no teste
        df['submassa_B'] = 0
        diag = diagnosticar_covariaveis(df)
        self.assertTrue(any({p['a'], p['b']} == {'plano_CD', 'plano_BD'} for p in diag['alertas']))
        self.assertNotIn('submassa_B', diag['covariaveis'])
        self.assertEqual(len(diag['decisoes']), len(COVARIAVEIS))
        self.assertTrue(all(d['justificativa'] for d in diag['decisoes']))
        self.assertEqual(len(diag['categoricas']), 3)

    def test_km_e_cox_recuperam_sinal_conhecido(self):
        df = fixture_com_padrao()
        cox = ajustar_cox(df, COVARIAVEIS)
        padrao = verificar_padrao_mortalidade(df, cox, 5.)
        self.assertTrue(padrao['recupera_direcoes'], padrao['verificacoes'])
        self.assertTrue(all(c['evidencia_ic95'] for c in padrao['verificacoes'] if c['modelo']=='Cox PH'))

    def test_inversao_e_poucos_eventos_nao_passam(self):
        df = fixture_com_padrao()
        df['sexo_M'] = 1-df.sexo_M
        df['sexo'] = np.where(df.sexo_M, 'M', 'F')
        padrao = verificar_padrao_mortalidade(df, ajustar_cox(df, COVARIAVEIS), 5.)
        self.assertFalse(padrao['recupera_direcoes'])
        self.assertTrue(any(c['status']=='direcao_divergente' for c in padrao['verificacoes']))
        pequeno = df.head(4)
        padrao = verificar_padrao_mortalidade(pequeno, None, 5.)
        self.assertFalse(padrao['recupera_direcoes'])
        self.assertTrue(all(c['status']=='inconclusivo' for c in padrao['verificacoes']))
        self.assertEqual(status_direcao(float('nan')), 'inconclusivo')

    def test_subgrupo_ausente_permanece_na_tabela(self):
        df = fixture_com_padrao(50)
        df['sexo'] = 'F'
        rows = avaliar_subgrupos(df, np.ones(50), np.full(50, .1), 5.)
        ausente = next(r for r in rows if r['fator']=='sexo' and r['grupo']=='M')
        self.assertEqual(ausente['n'], 0)
        self.assertIsNone(ausente['c_index'])
        self.assertIsNotNone(ausente['motivo'])


class EvidenciasTest(unittest.TestCase):
    def test_previsoes_sobrevivencia_nao_dependem_de_grade_brier(self):
        df = construir_dataset_analitico(gerar_dados_locais(700))
        with TemporaryDirectory() as temp, redirect_stdout(StringIO()), patch(
                'scripts.comparar_modelos.grade_comum', side_effect=ValueError('IPCW sem suporte')):
            result, _ = validacao_temporal(df, '2016-01-01', 5., 42, temp)
            csv = pd.read_csv(Path(temp)/'estimativas_teste.csv')
            teste = df.set_index('participante_id').loc[csv.participante_id]
            for nome, prefixo, arquivo in [('Cox PH', 'cox', 'cox.joblib'),
                                         ('Random Survival Forest', 'rsf', 'rsf.joblib')]:
                met = result['modelos'][nome]
                self.assertIsNone(met['brier'])
                self.assertEqual(met['brier_motivo'], 'IPCW sem suporte')
                bundle = joblib.load(Path(temp)/arquivo)
                X = teste[bundle['covariaveis']]
                esperado = (bundle['modelo'].predict_survival_function(X, times=[5.]).to_numpy().ravel()
                    if prefixo == 'cox' else np.array([fn(5.) for fn in
                        bundle['modelo'].predict_survival_function(X.to_numpy())]))
                np.testing.assert_allclose(csv[f'{prefixo}_prob_sobrevivencia'], esperado)
                np.testing.assert_allclose(csv[f'{prefixo}_prob_obito']+esperado, 1.)
            self.assertEqual(len(result['subgrupos']), 22)

    def test_criterio_executado_com_limite_nao_e_teste_ausente(self):
        avaliacao = dict(modelos={}, subgrupos=[dict(c_index=None, erro_calibracao_global=None)],
                        dependencia_covariaveis=dict(decisoes=[dict(covariavel='idade_ingresso')]))
        criterios = criterios_issue34(avaliacao)
        self.assertEqual(criterios[2]['status'], 'executado_com_limitacoes')
        self.assertEqual(criterios[3]['status'], 'executado')
        self.assertEqual(criterios[0]['status'], 'sem_suporte')
    def test_falha_dos_dois_ajustes_preserva_registro_inconclusivo(self):
        df = construir_dataset_analitico(gerar_dados_locais(700))
        with TemporaryDirectory() as temp, redirect_stdout(StringIO()), \
             patch('scripts.comparar_modelos.ajustar_cox', side_effect=ValueError('teste ajuste')), \
             patch('scripts.comparar_modelos.treinar_rsf', side_effect=ValueError('teste ajuste')):
            result, _ = validacao_temporal(df, '2016-01-01', 5., 42, Path(temp)/'modelos')
            self.assertEqual(result['veredito']['status'], 'inconclusivo')
            self.assertEqual(len(result['modelos']), 2)
            self.assertTrue((Path(temp)/'modelos/estimativas_teste.csv').exists())

    def test_idade_constante_nao_quebra_grafico_descritivo(self):
        df = fixture_com_padrao(150)
        df['idade_ingresso'] = 35.
        cox = ajustar_cox(df, [c for c in COVARIAVEIS if df[c].nunique() > 1])
        with TemporaryDirectory() as temp:
            gerar_graficos(cox, temp)
            self.assertTrue((Path(temp)/'cox_hazard_ratios.png').exists())
            self.assertFalse((Path(temp)/'cox_efeito_idade.png').exists())

    def test_rodada_sem_banco_nao_gera_fixture_ou_cards(self):
        with TemporaryDirectory() as temp:
            out = Path(temp)/'rodada'
            env = dict(os.environ, PGHOST='127.0.0.1', PGPORT='1')
            cmd = [sys.executable, str(SCRIPTS.parent/'main.py'),
                   '--data-referencia', '2026-08-31', '--identificacao-fonte', 'TESTE_CONEXAO',
                   '--data-corte', '2016-01-01', '--saida', str(out)]
            result = subprocess.run(cmd, capture_output=True, text=True, env=env)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((out/'dataset_survival.csv').exists())
            self.assertFalse((out/'model_card.md').exists())
            self.assertTrue((out/'falha_execucao.json').exists())
            self.assertFalse(list(out.glob('*.log')))

    def test_rodada_nao_sobrescreve_evidencias(self):
        with TemporaryDirectory() as temp:
            marker = Path(temp)/'anterior.txt'
            marker.write_text('preservar')
            result = subprocess.run([sys.executable, str(SCRIPTS.parent/'main.py'),
                '--data-referencia', '2026-08-31', '--identificacao-fonte', 'TESTE',
                '--data-corte', '2016-01-01', '--saida', temp], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(marker.read_text(), 'preservar')
            self.assertIn('pasta nova ou vazia', result.stderr)

    def test_modelos_persistidos_reproduzem_previsoes(self):
        df = construir_dataset_analitico(gerar_dados_locais(700))
        with TemporaryDirectory() as temp, redirect_stdout(StringIO()):
            result, split = validacao_temporal(df, '2016-01-01', 5., 42, temp)
            for nome, artefato in result['artefatos_modelos'].items():
                path = Path(temp)/artefato['arquivo']
                self.assertEqual(artefato['sha256'], sha256(path))
                bundle = joblib.load(path)
                teste = df.set_index('participante_id').loc[split.loc[
                    split.conjunto.eq('teste'), 'participante_id']]
                X = teste[bundle['covariaveis']]
                risco = (bundle['modelo'].predict_partial_hazard(X).to_numpy().ravel()
                         if nome == 'Cox PH' else bundle['modelo'].predict(X.to_numpy()))
                csv = pd.read_csv(Path(temp)/'estimativas_teste.csv')
                col = 'cox_risco' if nome == 'Cox PH' else 'rsf_risco'
                np.testing.assert_allclose(risco, csv[col])

    def test_fechamento_nao_aprova_fixture_ou_metricas_ausentes(self):
        motivos = verificar_pendencias({'fonte':'local'}, {'modelos':{}, 'subgrupos':[]}, {})
        self.assertTrue(any('fixture' in m for m in motivos))
        self.assertTrue(any('subgrupo' in m for m in motivos))
        self.assertTrue(any('métricas' in m for m in motivos))
        avaliacao = {'modelos': {nome: dict(c_index=.6, brier=.01, ibs=.01,
                     erro_calibracao_global=None)
                     for nome in ['Cox PH', 'Random Survival Forest']}}
        motivos = verificar_pendencias({'fonte':'banco'}, avaliacao, {})
        metricas = [m for m in motivos if 'métricas indisponíveis' in m]
        self.assertEqual(len(metricas), 2)
        self.assertTrue(all('erro de calibração global' in m for m in metricas))
        self.assertFalse(any('Brier' in m or 'IBS' in m or 'C-index' in m for m in metricas))

    def test_cards_incluem_nota_e_pendencias(self):
        meta = dict(data_referencia='2026-08-31', identificacao_fonte='teste MOCK',
            dataset_sha256='a'*64, n_bruto=30, n_analitico=30, n_excluidos=0, n_obitos=2)
        avaliacao = dict(data_corte='2016-01-01', horizonte_anos=5, n_treino=20, n_teste=10,
            eventos_treino=1, eventos_teste=1, modelos={}, veredito=dict(modelo_mantido='Cox PH',
            status='inconclusivo', motivo='suporte insuficiente'))
        fechamento = dict(status='revisao_necessaria', executado_em='teste', pendencias=['Falta suporte.'])
        with TemporaryDirectory() as temp:
            escrever_cards(Path(temp), meta, avaliacao, {}, fechamento)
            for name in ['model_card.md', 'experiment_record.md']:
                conteudo = (Path(temp)/name).read_text()
                self.assertIn(NOTA_USO, conteudo)
                self.assertIn('Falta suporte.', conteudo)
                self.assertNotIn('Fonte: Postgres curado', conteudo)
                if name == 'model_card.md':
                    self.assertIn('não prova que essa versão gerou', conteudo)


if __name__ == '__main__':
    unittest.main()
