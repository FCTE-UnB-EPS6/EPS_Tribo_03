"""Avaliação comum ao Cox/RSF: calendário, IPCW e calibração observada por KM."""
import numpy as np
import pandas as pd
from lifelines import KaplanMeierFitter
from sksurv.metrics import brier_score, concordance_index_censored, integrated_brier_score
from sksurv.nonparametric import CensoringDistributionEstimator

COVARIAVEIS = ['idade_ingresso', 'sexo_M', 'plano_BD', 'plano_CD', 'submassa_A', 'submassa_B']


def dividir_temporal(df, data_corte):
    """Treino: ingresso anterior ao corte, desfechos censurados no corte.

    Teste: ingresso no corte ou depois. Não reconstrói snapshots disponíveis na
    época: é uma simulação por datas de ocorrência com cadastro extraído hoje.
    """
    df = df.copy()
    for col in ['data_ingresso', 'data_fim', 'data_referencia']:
        df[col] = pd.to_datetime(df[col], errors='raise')
        if df[col].isna().any():
            raise ValueError(f'{col} ausente')
    corte = pd.Timestamp(data_corte)
    if df.participante_id.duplicated().any():
        raise ValueError('Participante duplicado na divisão')
    if df.data_referencia.nunique() != 1 or corte >= df.data_referencia.iloc[0]:
        raise ValueError('Corte deve anteceder a referência única do dataset')
    treino = df.loc[df.data_ingresso < corte].copy()
    teste = df.loc[df.data_ingresso >= corte].copy()
    if treino.empty or teste.empty:
        raise ValueError('Corte precisa produzir treino e teste não vazios')
    depois = treino.data_fim > corte
    treino.loc[depois, 'evento'] = 0
    treino.loc[depois, 'data_fim'] = corte
    treino['tempo_observado'] = (treino.data_fim - treino.data_ingresso).dt.days / 365.25
    return treino.reset_index(drop=True), teste.reset_index(drop=True)


def alvo(df):
    return np.array(list(zip(df.evento.astype(bool), df.tempo_observado.astype(float))),
                    dtype=[('evento', bool), ('tempo', float)])


def c_index(df, risco):
    """scikit-survival espera MAIOR escore para MAIOR risco (inclusive Cox)."""
    if len(df) < 2 or df.evento.sum() < 2:
        return None, 'Menos de dois eventos/participantes para discriminação exploratória'
    try:
        value = float(concordance_index_censored(df.evento.astype(bool),
                                                df.tempo_observado, risco)[0])
        if not np.isfinite(value):
            return None, 'Sem pares comparáveis'
        return value, None
    except ValueError as exc:
        return None, str(exc)


def calibracao_km(df, probabilidades_obito, horizonte, min_n=20, min_eventos=2, min_risco=5):
    """Calibração global: |média P(óbito até t) - (1-KM(t))|.

    Considera censura independente. Não é ICI e pode esconder erros que se
    compensam entre pessoas; complementar com curvas por grupos de risco.
    """
    eventos = int((df.evento.eq(1) & df.tempo_observado.le(horizonte)).sum())
    em_risco = int(df.tempo_observado.ge(horizonte).sum())
    row = dict(n=len(df), eventos_ate_horizonte=eventos, em_risco_horizonte=em_risco,
               previsto=float(np.mean(probabilidades_obito)) if len(df) else None,
               observado=None, observado_ic95_inferior=None, observado_ic95_superior=None,
               erro_calibracao_global=None, motivo=None)
    if len(df) < min_n or eventos < min_eventos or em_risco < min_risco:
        row['motivo'] = f'Suporte insuficiente: exige n>={min_n}, eventos até horizonte>={min_eventos}, em risco>={min_risco}'
        return row
    km = KaplanMeierFitter().fit(df.tempo_observado, df.evento)
    observado = float(1 - km.predict(horizonte))
    ci = km.confidence_interval_survival_function_.loc[:horizonte].iloc[-1]
    row.update(observado=observado, observado_ic95_inferior=float(1-ci.iloc[1]),
               observado_ic95_superior=float(1-ci.iloc[0]),
               erro_calibracao_global=abs(row['previsto']-observado))
    return row


def grade_comum(treino, teste, horizonte):
    """Grade fixa até horizonte declarado, sem extrapolação de IPCW/RSF.

    Censura administrativamente tempos do teste acima de tau para a chamada
    Brier; tau > horizonte, portanto não altera os desfechos nesse horizonte.
    """
    if not np.isfinite(horizonte) or horizonte <= 0:
        raise ValueError('Horizonte deve ser positivo e finito')
    upper = min(treino.tempo_observado.max(), teste.tempo_observado.max())
    tau = np.nextafter(float(upper), -np.inf)
    inicio = max(.01, float(teste.tempo_observado.min()))
    if horizonte >= tau or inicio >= horizonte:
        raise ValueError('Horizonte fora do suporte comum de acompanhamento; nenhuma extrapolação realizada')
    yt = alvo(teste)
    beyond = yt['tempo'] > tau
    yt['evento'][beyond] = False
    yt['tempo'][beyond] = tau
    times = np.linspace(inicio, horizonte, 30)
    censoring = CensoringDistributionEstimator().fit(alvo(treino))
    if np.any(censoring.predict_proba(times) <= 0):
        raise ValueError('Probabilidade de não censura nula na grade IPCW')
    return times, yt, tau


def metricas_modelo(treino, teste, risco, sobrev, horizonte, times, yt):
    c, motivo = c_index(teste, risco)
    result = dict(c_index=c, c_index_motivo=motivo, brier=None, ibs=None, brier_motivo=None)
    try:
        _, bs = brier_score(alvo(treino), yt, sobrev, times)
        ibs = integrated_brier_score(alvo(treino), yt, sobrev, times)
        if not np.isfinite(bs).all() or not np.isfinite(ibs):
            raise ValueError('Brier/IBS não finito')
        result.update(brier=float(bs[-1]), ibs=float(ibs))
    except ValueError as exc:
        result['brier_motivo'] = str(exc)
    result['calibracao'] = calibracao_km(teste, 1-sobrev[:, -1], horizonte)
    return result


def curvas_calibracao(teste, prob, horizonte):
    """Tercis de risco previstos, somente diagnóstico (não ajusta o modelo)."""
    if np.unique(prob).size < 2:
        bins = np.zeros(len(prob), dtype=int)
    else:
        bins = pd.qcut(prob, 3, labels=False, duplicates='drop')
    rows = []
    for label in sorted(set(bins)):
        mask = bins == label
        rows.append(dict(grupo_risco=int(label)+1,
                         **calibracao_km(teste.loc[mask], prob[mask], horizonte)))
    return rows


def avaliar_subgrupos(teste, risco, prob, horizonte):
    frame = teste.copy()
    frame['faixa_idade_ingresso'] = pd.cut(frame.idade_ingresso, [0, 30, 45, np.inf],
        labels=['até 30', '30 a 45', 'acima de 45'], include_lowest=True)
    rows = []
    for col in ['sexo', 'plano_tipo', 'submassa', 'faixa_idade_ingresso']:
        for val, grupo in frame.groupby(col, observed=True):
            pos = frame.index.get_indexer(grupo.index)
            c, motivo = c_index(grupo, risco[pos])
            rows.append(dict(fator=col, grupo=str(val), c_index=c, c_index_motivo=motivo,
                             **calibracao_km(grupo, prob[pos], horizonte)))
    return rows
