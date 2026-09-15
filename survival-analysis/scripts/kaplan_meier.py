"""KM descritivo por sexo, BD/CD/CV e submassa; log-rank global por fator."""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from lifelines import KaplanMeierFitter
from lifelines.statistics import multivariate_logrank_test

GRUPOS = {'sexo': ['M', 'F'], 'plano_tipo': ['BD', 'CD', 'CV'],
          'submassa': ['Plano A', 'Plano B', 'Plano C']}


def ajustar_km_global(df):
    return KaplanMeierFitter().fit(df.tempo_observado, df.evento, label='Global')


def resumo_grupos(df):
    rows, testes = [], []
    for fator, valores in GRUPOS.items():
        for valor in valores:
            group = df.loc[df[fator].eq(valor)]
            rows.append(dict(fator=fator, grupo=valor, n=len(group), eventos=int(group.evento.sum())))
        counts = [r['n'] for r in rows if r['fator'] == fator]
        why = None
        p = stat = None
        if min(counts) < 5 or df.evento.sum() < 2:
            why = 'Log-rank não avaliado: alguma categoria com n<5 ou menos de 2 eventos totais'
        else:
            test = multivariate_logrank_test(df.tempo_observado, df[fator], df.evento)
            if np.isfinite(test.p_value):
                p, stat = float(test.p_value), float(test.test_statistic)
            else:
                why = 'Log-rank não finito; suporte insuficiente'
        testes.append(dict(fator=fator, p_valor=p, estatistica=stat, motivo=why))
    return rows, testes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=Path(__file__).resolve().parents[1]/'data/dataset_survival.csv')
    parser.add_argument('--saida', type=Path)
    args = parser.parse_args()
    df = pd.read_csv(args.dataset)
    if df.empty:
        raise ValueError('Dataset vazio')
    out = args.saida or args.dataset.parent/'graficos'
    out.mkdir(parents=True, exist_ok=True)
    rows, testes = resumo_grupos(df)
    for fator in ['global', *GRUPOS]:
        fig, ax = plt.subplots(figsize=(8, 5))
        groups = [('Global', df)] if fator == 'global' else list(df.groupby(fator))
        for value, group in groups:
            km = KaplanMeierFitter().fit(group.tempo_observado, group.evento,
                  label=f'{value} (n={len(group)}, óbitos={group.evento.sum()})')
            km.plot_survival_function(ax=ax)
        ax.set(title=f'Kaplan-Meier — {fator}', xlabel='Tempo desde ingresso (anos)', ylabel='Sobrevivência')
        fig.tight_layout()
        fig.savefig(out/f'km_{fator}.png', dpi=150)
        plt.close(fig)
    km = ajustar_km_global(df)
    met = dict(modelo='Kaplan-Meier', n=len(df), eventos=int(df.evento.sum()),
               mediana=km.median_survival_time_)
    for h in [5, 10]:
        supported = df.tempo_observado.ge(h).sum() >= 5
        met[f'sobrevivencia_{h}_anos'] = float(km.predict(h)) if supported else None
        met[f'motivo_{h}_anos'] = None if supported else 'Menos de 5 pessoas acompanhadas até horizonte'
    pd.DataFrame([met]).to_csv(out/'metricas_km.csv', index=False)
    pd.DataFrame(rows).to_csv(out/'km_subgrupos.csv', index=False)
    pd.DataFrame(testes).to_csv(out/'logrank.csv', index=False)
    print(pd.DataFrame(rows).to_string(index=False))
    print(pd.DataFrame(testes).to_string(index=False))
    print('KM/log-rank são descritivos; não substituem calibração/discriminação do Cox por grupo.')


if __name__ == '__main__':
    main()
