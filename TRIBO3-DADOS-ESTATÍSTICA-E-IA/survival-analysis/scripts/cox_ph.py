"""Baseline Cox PH: ajuste, Schoenfeld e gráficos; chamado por main.py."""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from lifelines import CoxPHFitter
from lifelines.statistics import proportional_hazard_test


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


def selecionar_covariaveis():
    """Lista fixa por domínio; CV e Plano C são referências.

    Pearson/Spearman são diagnósticos, não seleção automática. Em avaliação,
    constantes são removidas usando somente o treino (comparar_modelos.py).
    """
    return ["idade_ingresso", "sexo_M", "plano_BD", "plano_CD", "submassa_A", "submassa_B"]


def ajustar_cox(df, covariaveis):
    """Ajusta modelo de Cox PH e retorna o fitter."""
    cols = covariaveis + ["tempo_observado", "evento"]
    df_cox = df[cols].copy()

    cph = CoxPHFitter(penalizer=0.01)
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
            print("\nTeste não detectou evidência de violação; poucos eventos limitam seu poder.")
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
    print(f"\nConcordance Index APARENTE (treino, não validação): {c_index:.4f}")
    print(f"  (0.5 = aleatório, 1.0 = discriminação perfeita)")

    aic = cph.AIC_partial_
    print(f"AIC parcial: {aic:.2f}")

    coefs = cph.summary
    significativos = coefs[coefs["p"] < 0.05]
    print(f"\nCovariáveis significativas (p < 0.05): {len(significativos)}/{len(coefs)}")
    for idx, row in significativos.iterrows():
        direcao = "aumenta risco" if row["exp(coef)"] > 1 else "reduz risco"
        print(f"  {idx}: HR={row['exp(coef)']:.3f} ({direcao}), p={row['p']:.4f}")


def gerar_graficos(cph, saida_dir):
    """Gera gráficos do modelo de Cox."""
    os.makedirs(saida_dir, exist_ok=True)

    fig, ax = plt.subplots(figsize=(10, 6))
    cph.plot(ax=ax)
    ax.set_title("Cox PH — Log hazard ratios (IC 95%)")
    ax.axvline(x=0, color="gray", linestyle="--", alpha=0.5)
    fig.tight_layout()
    fig.savefig(os.path.join(saida_dir, "cox_hazard_ratios.png"), dpi=150)
    plt.close(fig)

    if 'idade_ingresso' not in cph.params_.index:
        return  # Idade constante foi removida; não inventar um efeito estimado.

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
