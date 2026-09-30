"""Regressões de datas, censura, métricas e critérios de promoção."""
from datetime import date
from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from construir_dataset import construir_dataset_analitico, gerar_dados_locais
from avaliacao import (alvo, c_index, calibracao_km, dividir_temporal, grade_comum,
                       metricas_modelo)
from comparar_modelos import imprimir_veredito, validacao_temporal
from kaplan_meier import resumo_grupos


def pessoa(**changes):
    row = dict(participante_id='p1', data_nascimento='1980-01-01',
        data_ingresso='2000-01-01', data_desligamento=None, data_obito=None,
        status_atual='ativo', sexo='M', plano_tipo='BD', submassa='Plano A')
    row.update(changes)
    return row


class DatasetTest(unittest.TestCase):
    def build(self, **changes):
        return construir_dataset_analitico(pd.DataFrame([pessoa(**changes)]), date(2026, 8, 31), True)

    def test_future_death_is_censored_at_reference(self):
        df, ex = self.build(status_atual='obito', data_obito='2027-01-01', data_desligamento='2027-01-01')
        self.assertEqual(len(ex), 0)
        self.assertEqual(df.evento.iloc[0], 0)
        self.assertEqual(df.data_fim.iloc[0], pd.Timestamp('2026-08-31'))

    def test_invalid_and_missing_death_are_not_imputed(self):
        for changes, reason in [({'data_obito':'1999-01-01'}, 'data_obito_anterior_ingresso'),
                                ({'status_atual':'obito'}, 'obito_sem_data'),
                                ({'data_obito':'garbage'}, 'data_obito_invalida'),
                                ({'data_obito':'2000-01-01'}, 'duracao_nao_positiva')]:
            df, ex = self.build(**changes)
            self.assertTrue(df.empty)
            self.assertIn(reason, ex.motivos.iloc[0])

    def test_death_on_reference_and_tied_exit_counts(self):
        df, _ = self.build(data_obito='2026-08-31', data_desligamento='2026-08-31')
        self.assertEqual(df.evento.iloc[0], 1)

    def test_exit_precedes_death(self):
        df, _ = self.build(data_obito='2020-01-01', data_desligamento='2010-01-01')
        self.assertEqual(df.evento.iloc[0], 0)
        self.assertEqual(df.data_fim.iloc[0], pd.Timestamp('2010-01-01'))

    def test_retirement_continues_and_input_is_unchanged(self):
        raw = pd.DataFrame([pessoa(status_atual='aposentado')])
        old = raw.copy(deep=True)
        df = construir_dataset_analitico(raw)
        pd.testing.assert_frame_equal(raw, old)
        self.assertEqual(df.data_fim.iloc[0], pd.Timestamp('2026-08-31'))
        self.assertEqual(df.plano_tipo.iloc[0], 'BD')
        self.assertEqual(df.submassa.iloc[0], 'Plano A')

    def test_duplicates_fail_instead_of_multiplying_people(self):
        with self.assertRaisesRegex(ValueError, 'duplicados'):
            construir_dataset_analitico(pd.DataFrame([pessoa(), pessoa()]))

    def test_invalid_category_not_encoded_as_reference(self):
        df, ex = self.build(plano_tipo='XX')
        self.assertTrue(df.empty)
        self.assertIn('plano_tipo_fora_dominio', ex.motivos.iloc[0])

    def test_local_fixture_reference_and_reproducibility(self):
        a = gerar_dados_locais(30, 42, date(2020, 1, 1))
        b = gerar_dados_locais(30, 42, date(2020, 1, 1))
        pd.testing.assert_frame_equal(a, b)
        self.assertTrue((pd.to_datetime(a.data_ingresso) < pd.Timestamp('2020-01-01')).all())
        self.assertTrue(a.participante_id.str.startswith('local-').all())


class EvaluationTest(unittest.TestCase):
    def test_calendar_split_censors_training_future_outcomes(self):
        rows = [pessoa(participante_id='old', data_obito='2025-01-01'),
                pessoa(participante_id='new', data_ingresso='2020-01-01', data_obito='2021-01-01'),
                pessoa(participante_id='tie', data_ingresso='2020-01-01')]
        df = construir_dataset_analitico(pd.DataFrame(rows))
        train, test = dividir_temporal(df, '2020-01-01')
        self.assertEqual(train.participante_id.tolist(), ['old'])
        self.assertEqual(set(test.participante_id), {'new', 'tie'})
        self.assertEqual(train.evento.sum(), 0)
        self.assertEqual(train.data_fim.iloc[0], pd.Timestamp('2020-01-01'))
        self.assertAlmostEqual(train.tempo_observado.iloc[0], 20, places=2)

    def test_risk_direction(self):
        df = pd.DataFrame({'tempo_observado':[1., 2., 3.], 'evento':[1, 1, 1]})
        self.assertEqual(c_index(df, [3., 2., 1.])[0], 1.)
        self.assertEqual(c_index(df, [-3., -2., -1.])[0], 0.)

    def test_brier_and_calibration_known_uncensored_answer(self):
        df = pd.DataFrame({'tempo_observado':np.arange(1., 41.), 'evento':np.ones(40, dtype=int)})
        times, yt, _ = grade_comum(df, df, 10.)
        surv = np.full((40, len(times)), .75)
        met = metricas_modelo(df, df, -df.tempo_observado, surv, 10., times, yt)
        # 10 deaths, 30 alive at 10 years: constant p(death)=.25 is calibrated.
        self.assertAlmostEqual(met['brier'], .1875)
        self.assertAlmostEqual(met['calibracao']['erro_calibracao_global'], 0.)
        self.assertIsNotNone(met['ibs'])

    def test_censored_people_are_not_assumed_alive(self):
        df = pd.DataFrame({'tempo_observado':[1]*20 + [2]*10 + [10]*20,
                           'evento':[0]*20 + [1]*10 + [0]*20})
        met = calibracao_km(df, np.full(50, 1/3), 5)
        self.assertAlmostEqual(met['observado'], 1/3)
        self.assertAlmostEqual(met['erro_calibracao_global'], 0.)

    def test_metric_support_failures_are_explicit(self):
        df = pd.DataFrame({'tempo_observado':[1., 2., 3.], 'evento':[0, 0, 0]})
        self.assertIsNotNone(c_index(df, [1., 1., 1.])[1])
        self.assertIsNotNone(calibracao_km(df, [.1]*3, 5)['motivo'])
        with self.assertRaisesRegex(ValueError, 'suporte'):
            grade_comum(df, df, 5.)

    def test_joint_decision_does_not_promote_worse_calibration(self):
        cox = dict(c_index=.6, ibs=.1, erro_calibracao_global=.02)
        rsf = dict(c_index=.7, ibs=.09, erro_calibracao_global=.03)
        self.assertEqual(imprimir_veredito(cox, rsf, 20)['modelo_mantido'], 'Cox PH')
        self.assertEqual(imprimir_veredito(cox, {}, 20)['status'], 'inconclusivo')
        rsf['erro_calibracao_global'] = .01
        self.assertEqual(imprimir_veredito(cox, rsf, 20)['status'], 'inconclusivo')
        ci = {'suporte':True, 'c_index':[.03, .2], 'calibracao':[.002, .02]}
        self.assertEqual(imprimir_veredito(cox, rsf, 20, ci)['modelo_mantido'], 'Random Survival Forest')
        self.assertEqual(imprimir_veredito(cox, rsf, 2, ci)['status'], 'inconclusivo')

    def test_empty_training_events_returns_record(self):
        df = construir_dataset_analitico(pd.DataFrame([pessoa(),
            pessoa(participante_id='new', data_ingresso='2020-01-01')]))
        result, split = validacao_temporal(df, '2015-01-01')
        self.assertEqual(result['veredito']['status'], 'inconclusivo')
        self.assertEqual(len(split), 2)

    def test_km_retains_all_real_categories(self):
        df = construir_dataset_analitico(gerar_dados_locais(300, 42))
        rows, tests = resumo_grupos(df)
        self.assertEqual({r['grupo'] for r in rows if r['fator']=='plano_tipo'}, {'BD', 'CD', 'CV'})
        self.assertEqual({r['grupo'] for r in rows if r['fator']=='submassa'}, {'Plano A', 'Plano B', 'Plano C'})
        self.assertEqual({r['fator'] for r in tests}, {'sexo', 'plano_tipo', 'submassa'})


if __name__ == '__main__':
    unittest.main()
