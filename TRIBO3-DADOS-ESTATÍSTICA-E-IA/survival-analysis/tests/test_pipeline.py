"""Fluxo inteiro com conexão substituída, sem simular resultados dos modelos.

Os dados são controlados de teste, não representam o lote calibrado do Passo 1.
Só a extração é mockada; KM/Cox/RSF, métricas, gráficos e persistência são reais.
"""
import ast
from contextlib import redirect_stdout
from datetime import date
from io import StringIO
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import joblib
import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
import main as aplicacao
from scripts.avaliacao import COVARIAVEIS
from scripts.registro import NOTA_USO, sha256


def dados_controlados(n=700):
    """Hazard PH com idade e sexo, datas consistentes e censura administrativa."""
    rng = np.random.default_rng(73)
    ref = pd.Timestamp('2026-08-31')
    idade = rng.uniform(20, 55, n)
    sexo = rng.integers(0, 2, n)
    ingresso = pd.Timestamp('1996-01-01') + pd.to_timedelta(rng.integers(0, 30*365, n), unit='D')
    # Tempos além de 100 anos já estão fora do acompanhamento (máximo ~30).
    # Limitá-los evita overflow de Timestamp, sem alterar eventos observáveis.
    dias_evento = np.clip(rng.exponential(
        1/(.025*np.exp(.07*(idade-30)+.6*sexo)))*365.25, 1, 100*365).astype(int)
    morte = ingresso + pd.to_timedelta(dias_evento, unit='D')
    evento = morte <= ref
    fim = pd.DatetimeIndex(np.where(evento, morte, ref))
    return pd.DataFrame(dict(participante_id=[f'MOCK-{i}' for i in range(n)],
        sexo=np.where(sexo, 'M', 'F'), plano_tipo=rng.choice(['BD', 'CD', 'CV'], n),
        submassa=rng.choice(['Plano A', 'Plano B', 'Plano C'], n),
        data_nascimento=ingresso-pd.to_timedelta((idade*365.25).astype(int), unit='D'),
        data_ingresso=ingresso, data_desligamento=pd.NaT,
        data_obito=pd.DatetimeIndex(np.where(evento, morte, pd.NaT)),
        status_atual=np.where(evento, 'obito', 'ativo'),
        exposicao_oficial_anos=(fim-ingresso).days/365.25,
        n_exposicoes=1, exposicao_data_fim=fim))


class PipelineTest(unittest.TestCase):
    def comparar_registros(self, primeiro, segundo):
        """Reduções paralelas da forest podem variar no último bit do float."""
        if isinstance(primeiro, dict):
            self.assertEqual(set(primeiro), set(segundo))
            for chave in primeiro:
                self.comparar_registros(primeiro[chave], segundo[chave])
        elif isinstance(primeiro, list):
            self.assertEqual(len(primeiro), len(segundo))
            for a, b in zip(primeiro, segundo):
                self.comparar_registros(a, b)
        elif isinstance(primeiro, float):
            np.testing.assert_allclose(primeiro, segundo, rtol=1e-12, atol=1e-12)
        else:
            self.assertEqual(primeiro, segundo)

    def test_fluxo_completo_pela_unica_entrada(self):
        bruto = dados_controlados()
        with TemporaryDirectory() as temp, redirect_stdout(StringIO()), patch(
            'scripts.construir_dataset.extrair_do_banco', return_value=bruto) as consulta:
            out = Path(temp)/'primeira'
            codigo = aplicacao.main(['--data-referencia', '2026-08-31',
                '--identificacao-fonte', 'MOCK_SOMENTE_TESTE_NAO_CALIBRADO',
                '--data-corte', '2016-01-01', '--horizonte', '5', '--saida', str(out)])
            self.assertIn(codigo, [0, 2])
            consulta.assert_called_once_with()
            fechamento = json.loads((out/'fechamento.json').read_text())
            self.assertEqual(len(fechamento['etapas']), 5)
            self.assertEqual(fechamento['status_execucao'], 'concluida')
            self.assertEqual(len(fechamento['criterios_issue34']), 5)
            self.assertTrue(all(e['status'] == 'concluida' for e in fechamento['etapas']))
            self.assertEqual(codigo, 2 if fechamento['pendencias'] else 0)
            self.assertFalse((out/'falha_execucao.json').exists())
            self.assertFalse(list(out.rglob('*.log')))
            self.assertEqual(fechamento['ambiente']['scripts_sha256']['main.py'], sha256(BASE/'main.py'))
            resultado = json.loads((out/'avaliacao/resultado.json').read_text())
            self.assertEqual(set(resultado['modelos']), {'Cox PH', 'Random Survival Forest'})
            self.assertEqual(resultado['n_treino']+resultado['n_teste'], len(bruto))
            for met in resultado['modelos'].values():
                self.assertIsNotNone(met['c_index'])
                self.assertIsNotNone(met['brier'])
                self.assertIsNotNone(met['ibs'])
                self.assertIsNotNone(met['erro_calibracao_global'])
            self.assertEqual(len(resultado['subgrupos']), 22)
            self.assertEqual(len(resultado['dependencia_covariaveis']['decisoes']), len(COVARIAVEIS))
            padrao = json.loads((out/'padrao_mortalidade.json').read_text())
            self.assertTrue(padrao['recupera_direcoes'], padrao['verificacoes'])
            split = pd.read_csv(out/'avaliacao/divisao_temporal.csv')
            treino = split.loc[split.conjunto.eq('treino')]
            self.assertTrue(pd.to_datetime(treino.data_fim).le('2016-01-01').all())
            self.assertFalse(split.participante_id.duplicated().any())
            self.assertEqual(len(split.loc[split.conjunto.eq('teste')]), resultado['n_teste'])
            estimativas = pd.read_csv(out/'avaliacao/modelos/estimativas_teste.csv')
            dados = pd.read_csv(out/'dataset_survival.csv').set_index('participante_id').loc[estimativas.participante_id]
            for nome, artefato in resultado['artefatos_modelos'].items():
                modelo = joblib.load(out/'avaliacao/modelos'/artefato['arquivo'])
                X = dados[modelo['covariaveis']]
                riscos = (modelo['modelo'].predict_partial_hazard(X).to_numpy().ravel()
                    if nome == 'Cox PH' else modelo['modelo'].predict(X.to_numpy()))
                coluna = 'cox_risco' if nome == 'Cox PH' else 'rsf_risco'
                np.testing.assert_allclose(riscos, estimativas[coluna])
                prefixo = 'cox' if nome == 'Cox PH' else 'rsf'
                sobrevivencia = (modelo['modelo'].predict_survival_function(X, times=[5.]).to_numpy().ravel()
                    if prefixo == 'cox' else np.array([fn(5.) for fn in
                        modelo['modelo'].predict_survival_function(X.to_numpy())]))
                np.testing.assert_allclose(sobrevivencia, estimativas[f'{prefixo}_prob_sobrevivencia'])
                np.testing.assert_allclose(estimativas[f'{prefixo}_prob_obito']+sobrevivencia, 1.)
            for nome in ['km/km_global.png', 'km/km_sexo.png', 'km/km_plano_tipo.png',
                'km/km_submassa.png', 'km/km_faixa_idade_ingresso.png',
                'cox_descritivo/coeficientes.csv', 'cox_descritivo/schoenfeld.csv',
                'avaliacao/calibracao.png', 'avaliacao/rsf/rsf_curvas_individuais.png',
                'avaliacao/rsf/importancia.csv', 'avaliacao/rsf/rsf_importancia.png']:
                self.assertTrue((out/nome).is_file(), nome)
            for nome in ['model_card.md', 'experiment_record.md']:
                self.assertIn(NOTA_USO, (out/nome).read_text())
            manifesto = json.loads((out/'manifesto_artefatos.json').read_text())
            arquivos = {str(p.relative_to(out)) for p in out.rglob('*') if p.is_file()
                        and p.name != 'manifesto_artefatos.json'}
            self.assertEqual(set(manifesto['arquivos']), arquivos)
            for nome, digest in manifesto['arquivos'].items():
                self.assertEqual(sha256(out/nome), digest, nome)
            # Reusar um snapshot íntegro deve passar pelo MESMO fluxo, sem consultar o DB.
            segunda = Path(temp)/'segunda'
            codigo2 = aplicacao.main(['--dataset', str(out/'dataset_survival.csv'),
                '--data-corte', '2016-01-01', '--horizonte', '5', '--saida', str(segunda)])
            consulta.assert_called_once_with()
            self.assertEqual(codigo2, codigo)
            resultado2 = json.loads((segunda/'avaliacao/resultado.json').read_text())
            self.comparar_registros(resultado['modelos'], resultado2['modelos'])
            for chave in ['n_solicitado', 'n_valido', 'suporte']:
                self.assertEqual(resultado['bootstrap'][chave], resultado2['bootstrap'][chave])
            for chave in ['c_index', 'calibracao']:
                np.testing.assert_allclose(resultado['bootstrap'][chave], resultado2['bootstrap'][chave],
                                           rtol=1e-12, atol=1e-12)
            # Substituição explícita mantém uma única pasta e consulta novamente o banco.
            codigo3 = aplicacao.main(['--data-referencia', '2026-08-31',
                '--identificacao-fonte', 'MOCK_SOMENTE_TESTE_NAO_CALIBRADO',
                '--data-corte', '2016-01-01', '--horizonte', '5',
                '--saida', str(out), '--sobrescrever'])
            self.assertEqual(consulta.call_count, 2)
            self.assertEqual(codigo3, codigo)
            resultado3 = json.loads((out/'avaliacao/resultado.json').read_text())
            self.comparar_registros(resultado['modelos'], resultado3['modelos'])

    def test_sobrescrever_preserva_entrada_e_arquivos_do_usuario(self):
        with TemporaryDirectory() as temp, patch('scripts.construir_dataset.extrair_do_banco') as consulta:
            out = Path(temp)
            arquivo = out/'anotacao.txt'
            arquivo.write_text('não apagar', encoding='utf-8')
            opcoes = dict(saida=out, data_corte='2016-01-01',
                data_referencia='2026-08-31', identificacao_fonte='MOCK', sobrescrever=True)
            with self.assertRaisesRegex(ValueError, 'manifesto'):
                aplicacao.executar_pipeline(**opcoes)
            (out/'manifesto_artefatos.json').write_text(json.dumps(
                dict(fonte='banco', arquivos={})), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'externos'):
                aplicacao.executar_pipeline(**opcoes)
            with self.assertRaisesRegex(ValueError, 'snapshot de entrada'):
                aplicacao.executar_pipeline(**opcoes, dataset=out/'dataset_survival.csv')
            self.assertEqual(arquivo.read_text(), 'não apagar')
            consulta.assert_not_called()

    def test_fluxo_sem_eventos_registra_pendencia_sem_inventar_modelos(self):
        bruto = dados_controlados(120)
        bruto['data_obito'] = pd.NaT
        bruto['status_atual'] = 'ativo'
        bruto['exposicao_oficial_anos'] = (pd.Timestamp('2026-08-31')-bruto.data_ingresso).dt.days/365.25
        with TemporaryDirectory() as temp, redirect_stdout(StringIO()), patch(
            'scripts.construir_dataset.extrair_do_banco', return_value=bruto):
            codigo = aplicacao.main(['--data-referencia', '2026-08-31',
                '--identificacao-fonte', 'MOCK_SEM_EVENTOS', '--data-corte', '2016-01-01', '--saida', temp])
            self.assertEqual(codigo, 2)
            out = Path(temp)
            resultado = json.loads((out/'avaliacao/resultado.json').read_text())
            self.assertEqual(resultado['modelos'], {})
            self.assertEqual(resultado['veredito']['status'], 'inconclusivo')
            self.assertTrue(pd.read_csv(out/'avaliacao/metricas_subgrupos.csv').empty)
            self.assertTrue(pd.read_csv(out/'avaliacao/calibracao.csv').empty)
            self.assertFalse(list((out/'avaliacao/modelos').glob('*.joblib')))
            self.assertTrue((out/'model_card.md').is_file())
            self.assertFalse((out/'falha_execucao.json').exists())

    def test_falha_intermediaria_nao_emite_fechamento(self):
        with TemporaryDirectory() as temp, redirect_stdout(StringIO()), patch(
            'scripts.construir_dataset.extrair_do_banco', return_value=dados_controlados(100)), patch(
            'main.gerar_resultados_km', side_effect=OSError('falha injetada')):
            codigo = aplicacao.main(['--data-referencia', '2026-08-31',
                '--identificacao-fonte', 'MOCK', '--data-corte', '2016-01-01', '--saida', temp])
            self.assertEqual(codigo, 1)
            self.assertFalse((Path(temp)/'fechamento.json').exists())
            self.assertFalse((Path(temp)/'model_card.md').exists())
            erro = json.loads((Path(temp)/'falha_execucao.json').read_text())
            self.assertEqual(erro['etapas'][-1]['etapa'], 'kaplan_meier')

    def test_falha_nos_cards_nao_emite_fechamento(self):
        bruto = dados_controlados(100)
        bruto['data_obito'] = pd.NaT
        bruto['status_atual'] = 'ativo'
        with TemporaryDirectory() as temp, redirect_stdout(StringIO()), patch(
            'scripts.construir_dataset.extrair_do_banco', return_value=bruto), patch(
            'main.escrever_cards', side_effect=OSError('falha injetada nos cards')):
            codigo = aplicacao.main(['--data-referencia', '2026-08-31',
                '--identificacao-fonte', 'MOCK', '--data-corte', '2016-01-01', '--saida', temp])
            self.assertEqual(codigo, 1)
            self.assertFalse((Path(temp)/'fechamento.json').exists())
            self.assertFalse((Path(temp)/'manifesto_artefatos.json').exists())
            erro = json.loads((Path(temp)/'falha_execucao.json').read_text())
            self.assertEqual(erro['etapas'][-1]['etapa'], 'relatorios')

    def test_parametros_invalidos_nao_consultam_banco(self):
        with TemporaryDirectory() as temp, patch('scripts.construir_dataset.extrair_do_banco') as consulta:
            for overrides in [dict(horizonte=float('nan')), dict(horizonte=0),
                              dict(data_corte='2026-08-31'), dict(identificacao_fonte=' ')]:
                opcoes = dict(saida=temp, data_corte='2016-01-01', data_referencia='2026-08-31',
                              identificacao_fonte='MOCK', horizonte=5.)
                opcoes.update(overrides)
                with self.assertRaises(ValueError):
                    aplicacao.executar_pipeline(**opcoes)
            consulta.assert_not_called()

    def test_corte_sem_holdout_falha_antes_dos_modelos(self):
        with TemporaryDirectory() as temp, redirect_stdout(StringIO()), patch(
            'scripts.construir_dataset.extrair_do_banco', return_value=dados_controlados(100)), patch(
            'main.gerar_resultados_comparacao') as comparar:
            codigo = aplicacao.main(['--data-referencia', '2026-08-31',
                '--identificacao-fonte', 'MOCK', '--data-corte', '1990-01-01', '--saida', temp])
            self.assertEqual(codigo, 1)
            comparar.assert_not_called()
            self.assertFalse((Path(temp)/'km').exists())

    def test_modulos_nao_possuem_outros_executores(self):
        for arquivo in (BASE/'scripts').glob('*.py'):
            tree = ast.parse(arquivo.read_text())
            self.assertFalse(any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                and n.name == 'main' for n in tree.body), arquivo.name)
            self.assertNotIn('__main__', arquivo.read_text(), arquivo.name)
        self.assertFalse((BASE/'scripts/rodar_passo2.py').exists())
