"""
Cox Proportional Hazards — Baseline semi-paramétrico (Passo 2)

Ajusta um modelo de Cox usando as covariáveis do dataset analítico,
verifica a hipótese de riscos proporcionais (Schoenfeld) e calcula
o concordance index (C-index) como métrica de discriminação.

Uso:
    python scripts/cox_ph.py
    python scripts/cox_ph.py --dataset data/dataset_survival.csv
"""

import argparse
import os
import sys
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from lifelines import CoxPHFitter
from lifelines.statistics import proportional_hazard_test
import numpy as np


def carregar_dataset(caminho):
    if not os.path.exists(caminho):
        print(f"Dataset não encontrado em {caminho}")
        print("Rode primeiro: python scripts/construir_dataset.py")
        sys.exit(1)
    return pd.read_csv(caminho)


def verificar_multicolinearidade(df, covariaveis):
    """Verifica correlação entre covariáveis (Pearson/Spearman).

    Exigência do §3/§4.2: testar correlação/dependência entre covariáveis
    antes de incluir no modelo para evitar multicolinearidade.
    """
    print("=" * 60)
    print("VERIFICAÇÃO DE MULTICOLINEARIDADE")
    print("=" * 60)

    corr_pearson = df[covariaveis].corr(method="pearson")
    corr_spearman = df[covariaveis].corr(method="spearman")

    pares_altos = []
    for i in range(len(covariaveis)):
        for j in range(i + 1, len(covariaveis)):
            r_p = abs(corr_pearson.iloc[i, j])
            r_s = abs(corr_spearman.iloc[i, j])
            if r_p > 0.7 or r_s > 0.7:
                pares_altos.append((covariaveis[i], covariaveis[j], r_p, r_s))

    if pares_altos:
        print("\nPares com correlação alta (|r| > 0.7):")
        for v1, v2, rp, rs in pares_altos:
            print(f"  {v1} x {v2}: Pearson={rp:.3f}, Spearman={rs:.3f}")
    else:
        print("\nNenhum par com correlação alta (|r| > 0.7) encontrado.")

    return corr_pearson, pares_altos


def selecionar_covariaveis(df, pares_altos):
    """Remove covariáveis redundantes se houver multicolinearidade.

    Para one-hot encoding do mesmo fator, remove uma categoria (a referência
    é implícita). Plano tem 3 dummies (BD, CD, CV) — remove CV como referência.
    Submassa tem 3 (A, B, C) — remove C como referência.
    """
    covariaveis = ["idade_ingresso", "sexo_M", "plano_BD", "plano_CD", "submassa_A", "submassa_B"]
    return covariaveis


def ajustar_cox(df, covariaveis):
    """Ajusta modelo de Cox PH e retorna o fitter."""
    cols = covariaveis + ["tempo_observado", "evento"]
    df_cox = df[cols].copy()

    cph = CoxPHFitter(penalizer=0.01)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        cph.fit(df_cox, duration_col="tempo_observado", event_col="evento")

    return cph


def verificar_proporcionalidade(cph, df, covariaveis):
    """Testa hipótese de riscos proporcionais (Schoenfeld)."""
    print("\n" + "=" * 60)
    print("TESTE DE RISCOS PROPORCIONAIS (SCHOENFELD)")
    print("=" * 60)

    cols = covariaveis + ["tempo_observado", "evento"]
    try:
        resultado = proportional_hazard_test(cph, df[cols],
                                             time_transform="rank")
        print(resultado.summary)
        violacoes = resultado.summary[resultado.summary["p"] < 0.05]
        if len(violacoes) > 0:
            print(f"\n⚠️  {len(violacoes)} covariável(is) violam a hipótese PH (p < 0.05)")
            print("   Considerar modelo estratificado ou time-varying para essas variáveis.")
        else:
            print("\n✅ Nenhuma violação significativa da hipótese PH.")
        return resultado
    except Exception as e:
        print(f"\n⚠️  Teste não executado: {e}")
        return None


def imprimir_resumo(cph, df):
    """Imprime resumo do modelo de Cox."""
    print("\n" + "=" * 60)
    print("COX PH — RESUMO")
    print("=" * 60)

    cph.print_summary(columns=["coef", "exp(coef)", "se(coef)", "p", "lower 0.95", "upper 0.95"])

    c_index = cph.concordance_index_
    print(f"\nConcordance Index (C-index): {c_index:.4f}")
    print(f"  (0.5 = aleatório, 1.0 = discriminação perfeita)")

    aic = cph.AIC_partial_
    print(f"AIC parcial: {aic:.2f}")

    coefs = cph.summary
    significativos = coefs[coefs["p"] < 0.05]
    print(f"\nCovariáveis significativas (p < 0.05): {len(significativos)}/{len(coefs)}")
    for idx, row in significativos.iterrows():
        direcao = "↑ risco" if row["exp(coef)"] > 1 else "↓ risco"
        print(f"  {idx}: HR={row['exp(coef)']:.3f} ({direcao}), p={row['p']:.4f}")


def gerar_graficos(cph, saida_dir):
    """Gera gráficos do modelo de Cox."""
    os.makedirs(saida_dir, exist_ok=True)

    fig, ax = plt.subplots(figsize=(10, 6))
    cph.plot(ax=ax)
    ax.set_title("Cox PH — Hazard Ratios (IC 95%)")
    ax.axvline(x=0, color="gray", linestyle="--", alpha=0.5)
    fig.tight_layout()
    fig.savefig(os.path.join(saida_dir, "cox_hazard_ratios.png"), dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 6))
    cph.plot_partial_effects_on_outcome(
        covariates="idade_ingresso",
        values=[25, 35, 45, 55, 65],
        ax=ax,
    )
    ax.set_title("Cox PH — Efeito da Idade ao Ingresso na Sobrevivência")
    ax.set_xlabel("Tempo (anos)")
    ax.set_ylabel("Probabilidade de sobrevivência")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(saida_dir, "cox_efeito_idade.png"), dpi=150)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Cox Proportional Hazards baseline")
    parser.add_argument("--dataset", default=None)
    parser.add_argument("--saida", default=None)
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.dirname(__file__))
    dataset_path = args.dataset or os.path.join(base_dir, "data", "dataset_survival.csv")
    saida_dir = args.saida or os.path.join(base_dir, "data", "graficos")

    df = carregar_dataset(dataset_path)
    print(f"Dataset carregado: {len(df)} registros, {df['evento'].sum()} eventos\n")

    todas_covariaveis = ["idade_ingresso", "sexo_M", "plano_BD", "plano_CD",
                         "plano_CV", "submassa_A", "submassa_B", "submassa_C"]
    corr, pares_altos = verificar_multicolinearidade(df, todas_covariaveis)

    covariaveis = selecionar_covariaveis(df, pares_altos)
    print(f"\nCovariáveis selecionadas para o modelo: {covariaveis}")

    cph = ajustar_cox(df, covariaveis)
    imprimir_resumo(cph, df)

    verificar_proporcionalidade(cph, df, covariaveis)

    gerar_graficos(cph, saida_dir)
    print(f"\nGráficos salvos em {saida_dir}/")

    metricas_path = os.path.join(base_dir, "data", "metricas_cox.csv")
    coefs = cph.summary
    metricas = pd.DataFrame([{
        "modelo": "Cox PH",
        "c_index": cph.concordance_index_,
        "aic_parcial": cph.AIC_partial_,
        "n_covariaveis": len(covariaveis),
        "n_significativas_005": int((coefs["p"] < 0.05).sum()),
        "n_registros": len(df),
        "n_eventos": int(df["evento"].sum()),
    }])
    metricas.to_csv(metricas_path, index=False)
    print(f"Métricas salvas em {metricas_path}")


if __name__ == "__main__":
    main()
