"""Cox/RSF no mesmo corte de calendário; sem promoção com métricas ausentes."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import joblib

from .avaliacao import (COVARIAVEIS, alvo, avaliar_subgrupos, c_index, calibracao_km,
                       curvas_calibracao, dividir_temporal, grade_comum, metricas_modelo, SUBGRUPOS)
from .cox_ph import ajustar_cox, verificar_multicolinearidade, verificar_proporcionalidade
from .survival_forest import treinar_rsf, importancia_variaveis, curva_sobrevivencia_exemplo
from .registro import ambiente, salvar_json, sha256, VERSAO_MODELO
from .diagnosticos import diagnosticar_covariaveis

LIMIAR_GANHO = .02
LIMIAR_CALIBRACAO = .005  # redução absoluta de 0,5 ponto percentual


def imprimir_veredito(cox, rsf, n_eventos, ic_ganhos=None):
    """Ganhos em discriminação E calibração, IBS não pior e bootstrap pareado."""
    result = dict(modelo_mantido='Cox PH', status='inconclusivo', motivo=None)
    keys = ['c_index', 'ibs', 'erro_calibracao_global']
    ausentes = [f'{nome}: {k}' for nome, m in [('Cox PH', cox), ('Random Survival Forest', rsf)]
                for k in keys if m.get(k) is None or not np.isfinite(m[k])]
    if ausentes:
        result['motivo'] = ('Comparação sem suporte: ' + '; '.join(ausentes) +
                            '. Cox permanece como baseline, sem superioridade declarada.')
    elif n_eventos < 10:
        result['motivo'] = 'Menos de 10 eventos no teste; métricas exploratórias, sem promoção'
    elif not (rsf['c_index']-cox['c_index'] > LIMIAR_GANHO and
              cox['erro_calibracao_global']-rsf['erro_calibracao_global'] > LIMIAR_CALIBRACAO and
              rsf['ibs'] <= cox['ibs']):
        result.update(status='sem_ganho_conjunto', motivo='RSF não atende simultaneamente aos critérios predefinidos')
    elif ic_ganhos is None or not ic_ganhos.get('suporte'):
        result['motivo'] = 'Ganho pontual sem suporte suficiente no bootstrap pareado'
    elif min(ic_ganhos['c_index'][0], ic_ganhos['calibracao'][0]) <= 0:
        result['motivo'] = 'Intervalos de ganho incluem zero; superioridade não demonstrada'
    else:
        result.update(modelo_mantido='Random Survival Forest', status='ganho_demonstrado_no_holdout',
                      motivo='Ganhos conjuntos com IC95% positivos; confirmação externa permanece necessária')
    print(json.dumps(result, ensure_ascii=False))
    return result


def bootstrap_ganhos(teste, riscos, probs, horizonte, seed=42, n=200):
    """IC percentil pareado no holdout; não inclui incerteza do ajuste no treino."""
    rng = np.random.default_rng(seed)
    gains = []
    for _ in range(n):
        idx = rng.integers(0, len(teste), len(teste))
        sample = teste.iloc[idx]
        cs = [c_index(sample, riscos[name][idx])[0] for name in ['Cox PH', 'Random Survival Forest']]
        es = [calibracao_km(sample, probs[name][idx], horizonte)['erro_calibracao_global']
              for name in ['Cox PH', 'Random Survival Forest']]
        if all(x is not None for x in cs+es):
            gains.append([cs[1]-cs[0], es[0]-es[1]])
    out = dict(n_solicitado=n, n_valido=len(gains), suporte=len(gains) >= .8*n)
    if gains:
        intervals = np.percentile(gains, [2.5, 97.5], axis=0)
        out.update(c_index=intervals[:, 0].tolist(), calibracao=intervals[:, 1].tolist())
    return out


def validacao_temporal(df, data_corte, horizonte=5., seed=42, saida_modelos=None):
    if saida_modelos is not None:
        Path(saida_modelos).mkdir(parents=True, exist_ok=True)
    treino, teste = dividir_temporal(df, data_corte)
    result = dict(data_corte=str(data_corte), horizonte_anos=horizonte, seed=seed,
        desenho='Ingresso por calendário; desfechos de treino limitados ao corte; snapshot cadastral atual',
        n_treino=len(treino), n_teste=len(teste), eventos_treino=int(treino.evento.sum()),
        eventos_teste=int(teste.evento.sum()), modelos={}, subgrupos=[], curvas_calibracao=[])
    split = pd.concat([treino.assign(conjunto='treino'), teste.assign(conjunto='teste')])[
        ['participante_id', 'conjunto', 'data_ingresso', 'data_fim', 'tempo_observado', 'evento']]
    result['dependencia_covariaveis'] = diagnosticar_covariaveis(treino)
    if treino.evento.sum() < 2:
        result['motivo'] = 'Menos de dois eventos no treino após censura no corte; ajuste não executado'
        result['veredito'] = imprimir_veredito({}, {}, int(teste.evento.sum()))
        return result, split
    covs = result['dependencia_covariaveis']['covariaveis']
    result['covariaveis'] = covs
    result['constantes_no_treino_removidas'] = sorted(set(COVARIAVEIS)-set(covs))
    if not covs:
        result['motivo'] = 'Todas as covariáveis são constantes no treino'
        result['veredito'] = imprimir_veredito({}, {}, int(teste.evento.sum()))
        return result, split
    _, pairs = verificar_multicolinearidade(treino, covs)
    result['correlacoes_altas_treino'] = [list(p) for p in pairs]
    # Mesma lista para os dois modelos, sem seleção por resultados do teste.
    models = {}
    try:
        models['Cox PH'] = ajustar_cox(treino, covs)
        ph = verificar_proporcionalidade(models['Cox PH'], treino, covs)
        result['schoenfeld_treino_p'] = ({str(k): float(v) if np.isfinite(v) else None
            for k, v in ph.summary['p'].items()} if ph is not None else None)
    except (ValueError, ArithmeticError) as exc:
        result['modelos']['Cox PH'] = {'erro_ajuste': str(exc)}
    try:
        models['Random Survival Forest'] = treinar_rsf(treino[covs].to_numpy(), alvo(treino), seed)
    except ValueError as exc:
        result['modelos']['Random Survival Forest'] = {'erro_ajuste': str(exc)}
    times = yt = None
    try:
        times, yt, tau = grade_comum(treino, teste, horizonte)
        result.update(grade_anos=times.tolist(), tau_brier=tau)
    except ValueError as exc:
        result['motivo_grade'] = str(exc)
    riscos, probs = {}, {}
    for name, model in models.items():
        if saida_modelos is not None:
            destino = Path(saida_modelos)
            destino.mkdir(parents=True, exist_ok=True)
            filename = 'cox.joblib' if name == 'Cox PH' else 'rsf.joblib'
            joblib.dump(dict(modelo=model, covariaveis=covs, versao_modelo=VERSAO_MODELO,
                            data_corte=str(data_corte), finalidade='modelo ajustado somente no treino'),
                        destino/filename, compress=3)
            result.setdefault('artefatos_modelos', {})[name] = dict(
                arquivo=filename, sha256=sha256(destino/filename), parametros=(
                {'penalizer': .01} if name == 'Cox PH' else model.get_params()))
        if name == 'Cox PH':
            risk = model.predict_partial_hazard(teste[covs]).to_numpy().ravel()
            train_risk = model.predict_partial_hazard(treino[covs]).to_numpy().ravel()
        else:
            risk = model.predict(teste[covs].to_numpy())
            train_risk = model.predict(treino[covs].to_numpy())
        riscos[name] = risk
        c, motivo = c_index(teste, risk)
        met = dict(c_index=c, c_index_motivo=motivo, ibs=None, brier=None,
                   erro_calibracao_global=None, brier_motivo=result.get('motivo_grade'))
        if times is not None:
            if name == 'Cox PH':
                surv = model.predict_survival_function(teste[covs], times=times).to_numpy().T
            else:
                surv = np.vstack([fn(times) for fn in model.predict_survival_function(teste[covs].to_numpy())])
            met.update(metricas_modelo(treino, teste, risk, surv, horizonte, times, yt))
            probs[name] = 1-surv[:, -1]
            met['erro_calibracao_global'] = met['calibracao']['erro_calibracao_global']
        elif horizonte <= treino.tempo_observado.max():
            # Estimar S(t) não depende da existência de pesos IPCW válidos para
            # Brier. Manter a previsão quando o modelo suporta o horizonte;
            # a impossibilidade de validar continua registrada separadamente.
            if name == 'Cox PH':
                sobrevivencia = model.predict_survival_function(teste[covs], times=[horizonte]).to_numpy().ravel()
            else:
                sobrevivencia = np.array([fn(horizonte) for fn in model.predict_survival_function(teste[covs].to_numpy())])
            probs[name] = 1-sobrevivencia
            met['calibracao'] = calibracao_km(teste, probs[name], horizonte)
            met['erro_calibracao_global'] = met['calibracao']['erro_calibracao_global']
        else:
            met['motivo_probabilidade'] = 'Horizonte excede acompanhamento do treino; nenhuma extrapolação'
        if name in probs:
            if not np.isfinite(probs[name]).all() or np.any((probs[name] < 0) | (probs[name] > 1)):
                raise ValueError(f'{name}: probabilidade impossível ou não finita')
            result['curvas_calibracao'].extend(dict(modelo=name, **r) for r in curvas_calibracao(teste, probs[name], horizonte))
            result['subgrupos'].extend(dict(modelo=name, **r) for r in avaliar_subgrupos(teste, risk, probs[name], horizonte))
        else:
            grupos = teste.copy()
            grupos['faixa_idade_ingresso'] = pd.cut(grupos.idade_ingresso, [0, 30, 45, np.inf],
                labels=['até 30', '30 a 45', 'acima de 45'], include_lowest=True)
            for factor, valores in SUBGRUPOS.items():
                for val in valores:
                    group = grupos.loc[grupos[factor].eq(val)]
                    ci, why = c_index(group, risk[group.index.to_numpy()])
                    result['subgrupos'].append(dict(modelo=name, fator=factor, grupo=str(val),
                        n=len(group), c_index=ci, c_index_motivo=why,
                        erro_calibracao_global=None, motivo=result.get('motivo_grade')))
        met['c_index_treino'], met['c_index_treino_motivo'] = c_index(treino, train_risk)
        result['modelos'][name] = met
    if saida_modelos is not None and 'Random Survival Forest' in models:
        pasta = Path(saida_modelos).parent/'rsf'
        pasta.mkdir(parents=True, exist_ok=True)
        rsf = models['Random Survival Forest']
        X = teste[covs].to_numpy()
        curva_sobrevivencia_exemplo(rsf, X, alvo(teste), str(pasta))
        try:
            if teste.evento.sum() < 2:
                raise ValueError('Menos de dois eventos no teste para permutation importance')
            importancia = importancia_variaveis(rsf, covs, X, alvo(teste), str(pasta))
            pd.DataFrame(importancia, columns=['covariavel', 'importancia']).to_csv(
                pasta/'importancia.csv', index=False)
            result['diagnosticos_rsf'] = {'motivo_importancia': None}
        except ValueError as exc:
            result['diagnosticos_rsf'] = {'motivo_importancia': str(exc)}
    if saida_modelos is not None:
        estimativas = teste[['participante_id']].copy()
        for name in riscos:
            prefixo = 'cox' if name == 'Cox PH' else 'rsf'
            estimativas[f'{prefixo}_risco'] = riscos[name]
            estimativas[f'{prefixo}_prob_obito'] = probs.get(name, np.full(len(teste), np.nan))
            estimativas[f'{prefixo}_prob_sobrevivencia'] = 1-estimativas[f'{prefixo}_prob_obito']
        estimativas['horizonte_anos'] = horizonte
        estimativas.to_csv(Path(saida_modelos)/'estimativas_teste.csv', index=False)
    if len(probs) == 2 and teste.evento.sum() >= 10:
        result['bootstrap'] = bootstrap_ganhos(teste, riscos, probs, horizonte, seed)
    result['veredito'] = imprimir_veredito(result['modelos'].get('Cox PH', {}),
        result['modelos'].get('Random Survival Forest', {}), int(teste.evento.sum()), result.get('bootstrap'))
    return result, split


def gerar_grafico_calibracao(rows, out):
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot([0, 1], [0, 1], '--', color='gray')
    for name in ['Cox PH', 'Random Survival Forest']:
        valid = [r for r in rows if r['modelo'] == name and r['observado'] is not None]
        if valid:
            ax.errorbar([r['previsto'] for r in valid], [r['observado'] for r in valid],
                yerr=[[max(0, r['observado']-r['observado_ic95_inferior']) for r in valid],
                      [max(0, r['observado_ic95_superior']-r['observado']) for r in valid]],
                fmt='o', label=name)
    if ax.get_legend_handles_labels()[0]:
        ax.legend()
    else:
        ax.text(.05, .8, 'Grupos com suporte insuficiente;\nconsulte os motivos no CSV.')
    ax.set(xlabel='Probabilidade média prevista de óbito', ylabel='Probabilidade observada por KM',
           title='Calibração no teste — grupos de risco (IC 95%)', xlim=(0, 1), ylim=(0, 1))
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)



def gerar_resultados_comparacao(df, procedencia, dataset, data_corte, horizonte, seed, saida):
    """Avalia e persiste ambos os modelos no mesmo holdout, sem nova CLI."""
    out = Path(saida)
    out.mkdir(parents=True, exist_ok=True)
    result, split = validacao_temporal(df, data_corte, horizonte, seed, out/'modelos')
    result.update(dataset_sha256=sha256(dataset), procedencia=procedencia, ambiente=ambiente(),
                  criterios=dict(ganho_c_index=LIMIAR_GANHO, reducao_erro_calibracao=LIMIAR_CALIBRACAO,
                                 ibs_nao_pior=True, min_eventos_teste=10, bootstrap_ic95_positivo=True))
    salvar_json(out/'resultado.json', result)
    salvar_json(out/'dependencia_covariaveis.json', result['dependencia_covariaveis'])
    treino, _ = dividir_temporal(df, data_corte)
    for metodo in ['pearson', 'spearman']:
        treino[COVARIAVEIS].corr(method=metodo).to_csv(out/f'correlacao_{metodo}.csv')
    pd.DataFrame(result['dependencia_covariaveis']['decisoes']).to_csv(out/'decisoes_covariaveis.csv', index=False)
    split.to_csv(out/'divisao_temporal.csv', index=False)
    # CSVs sem linhas mantêm cabeçalhos para os consumidores lerem uma rodada
    # inconclusiva sem tratar arquivo vazio como falha de execução.
    for nome, linhas, colunas in [
        ('metricas_subgrupos.csv', result['subgrupos'],
         ['modelo', 'fator', 'grupo', 'n', 'c_index', 'c_index_motivo', 'erro_calibracao_global', 'motivo']),
        ('calibracao.csv', result['curvas_calibracao'],
         ['modelo', 'grupo_risco', 'n', 'previsto', 'observado', 'erro_calibracao_global', 'motivo'])]:
        tabela = pd.DataFrame(linhas) if linhas else pd.DataFrame(columns=colunas)
        tabela.to_csv(out/nome, index=False)
    gerar_grafico_calibracao(result['curvas_calibracao'], out/'calibracao.png')
    print(f'Registro completo: {out / "resultado.json"}')

    return result
