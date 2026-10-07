"""Diagnósticos auditáveis: dependência no treino e direção idade/sexo.

Não seleciona covariáveis/horizontes usando resultados do teste. Os diagnósticos
da massa completa são descritivos e não provam validade externa.
"""
from itertools import combinations

import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency, pearsonr, spearmanr

from .avaliacao import COVARIAVEIS, calibracao_km

JUSTIFICATIVAS = {
    'idade_ingresso': 'Idade conhecida ao ingresso; risco de mortalidade depende da idade.',
    'sexo_M': 'M versus F; a calibração IBGE distingue mortalidade por sexo.',
    'plano_BD': 'Contraste BD versus CV; controle de composição da massa.',
    'plano_CD': 'Contraste CD versus CV; controle de composição da massa.',
    'submassa_A': 'Contraste Plano A versus Plano C; controle de heterogeneidade.',
    'submassa_B': 'Contraste Plano B versus Plano C; controle de heterogeneidade.',
}


def numero_finito(valor):
    return float(valor) if np.isfinite(valor) else None


def diagnosticar_covariaveis(treino):
    selecionadas = [c for c in COVARIAVEIS if treino[c].nunique() > 1]
    pares = []
    for a, b in combinations(selecionadas, 2):
        rp, pp = pearsonr(treino[a], treino[b])
        rs, ps = spearmanr(treino[a], treino[b])
        pares.append(dict(a=a, b=b, pearson=numero_finito(rp), pearson_p=numero_finito(pp),
                          spearman=numero_finito(rs), spearman_p=numero_finito(ps),
                          correlacao_alta=bool(max(abs(rp), abs(rs)) > .7)))
    categoricas = []
    for a, b in combinations(['sexo', 'plano_tipo', 'submassa'], 2):
        tabela = pd.crosstab(treino[a], treino[b])
        if min(tabela.shape) < 2:
            categoricas.append(dict(a=a, b=b, cramers_v=None, p=None,
                                     motivo='Categoria constante no treino'))
            continue
        chi, p, _, esperadas = chi2_contingency(tabela, correction=False)
        categoricas.append(dict(a=a, b=b, cramers_v=float(np.sqrt(
            chi / (tabela.to_numpy().sum() * (min(tabela.shape)-1)))),
            p=float(p), celulas_esperadas_menor_5=int((esperadas < 5).sum()),
            motivo='p assintótico exploratório; conferir células esperadas'))
    alertas = [p for p in pares if p['correlacao_alta']]
    decisoes = []
    for c in COVARIAVEIS:
        relacionados = [f"{p['a']} x {p['b']}" for p in alertas if c in (p['a'], p['b'])]
        decisoes.append(dict(covariavel=c, incluida=c in selecionadas,
            decisao='incluir' if c in selecionadas else 'remover_constante_no_treino',
            justificativa=JUSTIFICATIVAS[c] if c in selecionadas else 'Sem variação no treino.',
            pares_altos=relacionados, requer_revisao=bool(relacionados)))
    return dict(covariaveis=selecionadas, decisoes=decisoes, pares=pares,
                categoricas=categoricas, alertas=alertas,
                copulas='Não usadas: Cox/RSF não pressupõem distribuição conjunta paramétrica; '
                        'correlações e Cramér V são diagnósticos, não prova de independência.',
                limite='p-valores exploratórios, sem ajuste de multiplicidade; '
                       'não removem variáveis automaticamente.')


def status_direcao(contraste, suporte=True):
    if not suporte or contraste is None or not np.isfinite(contraste):
        return 'inconclusivo'
    return 'direcao_esperada' if contraste > 0 else 'direcao_divergente'


def verificar_padrao_mortalidade(df, cox, horizonte):
    """KM por idade AO INGRESSO e sexo; HR Cox ajustados na massa completa.

    Compara extremos predefinidos de idade e M/F. Não exige que todas as
    faixas intermediárias sejam monotônicas numa realização aleatória pequena.
    """
    grupos = df.copy()
    grupos['faixa_idade_ingresso'] = pd.cut(grupos.idade_ingresso,
        [0, 30, 45, np.inf], labels=['ate_30', '30_a_45', 'acima_45'], include_lowest=True)
    linhas = []
    for fator, valores in [('sexo', ['F', 'M']),
                          ('faixa_idade_ingresso', ['ate_30', '30_a_45', 'acima_45'])]:
        for valor in valores:
            parte = grupos.loc[grupos[fator].eq(valor)]
            linhas.append(dict(fator=fator, grupo=valor,
                **calibracao_km(parte, np.zeros(len(parte)), horizonte)))
    # A coluna "previsto" não é uma previsão: aqui só interessa KM observado.
    for linha in linhas:
        linha.pop('previsto')
        linha.pop('erro_calibracao_global')
    checks = []
    for fator, baixo, alto in [('sexo', 'F', 'M'),
                             ('faixa_idade_ingresso', 'ate_30', 'acima_45')]:
        a = next(r for r in linhas if r['fator'] == fator and r['grupo'] == baixo)
        b = next(r for r in linhas if r['fator'] == fator and r['grupo'] == alto)
        delta = b['observado']-a['observado'] if all(
            r['observado'] is not None for r in [a, b]) else None
        checks.append(dict(modelo='KM', fator=fator, contraste=f'{alto} menos {baixo}',
            diferenca_prob_obito=delta, status=status_direcao(delta),
            motivo='Suporte insuficiente em um contraste' if delta is None else
                   'Comparação marginal descritiva; não ajusta composição/idade/sexo.'))
    for cov in ['idade_ingresso', 'sexo_M']:
        if cox is None or cov not in cox.summary.index:
            checks.append(dict(modelo='Cox PH', fator=cov, status='inconclusivo',
                               motivo='Modelo/covariável indisponível'))
            continue
        row = cox.summary.loc[cov]
        hr = float(row['exp(coef)'])
        checks.append(dict(modelo='Cox PH', fator=cov, hr=hr,
            hr_ic95_inferior=float(row['exp(coef) lower 95%']),
            hr_ic95_superior=float(row['exp(coef) upper 95%']), p=float(row['p']),
            status=status_direcao(hr-1),
            evidencia_ic95=bool(row['exp(coef) lower 95%'] > 1),
            motivo='HR > 1: efeito de um ano de idade ou M versus F; '
                   'direção pontual e IC95% registrados separadamente.'))
    return dict(horizonte_anos=horizonte, km_grupos=linhas, verificacoes=checks,
                recupera_direcoes=all(c['status'] == 'direcao_esperada' for c in checks),
                limite='Verifica a direção introduzida pela simulação IBGE; '
                       'não valida qx exato nem população real. Idade é ao ingresso, '
                       'não idade atingida. Contraste sem suporte é inconclusivo.')
