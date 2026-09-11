"""
Kaplan-Meier — Baseline não paramétrico (Passo 2)

Estima curvas de sobrevivência por subgrupo (sexo, plano, submassa)
e gera gráficos comparativos. Primeiro baseline do pipeline: nenhum
modelo mais complexo entra antes deste estar validado.

Uso:
    python scripts/kaplan_meier.py
    python scripts/kaplan_meier.py --dataset data/dataset_survival.csv
"""

import argparse
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from lifelines import KaplanMeierFitter
from lifelines.statistics import logrank_test


def carregar_dataset(caminho):
    if not os.path.exists(caminho):
        print(f"Dataset não encontrado em {caminho}")
        print("Rode primeiro: python scripts/construir_dataset.py")
        sys.exit(1)
    return pd.read_csv(caminho)


def ajustar_km_global(df):
    """Ajusta KM para toda a população."""
    kmf = KaplanMeierFitter()
    kmf.fit(df["tempo_observado"], event_observed=df["evento"], label="Global")
    return kmf


def ajustar_km_por_grupo(df, coluna, labels):
    """Ajusta KM separado para cada valor da coluna."""
    resultados = {}
    for valor, label in labels.items():
        mask = df[coluna] == valor
        if mask.sum() < 5:
            continue
        kmf = KaplanMeierFitter()
        kmf.fit(df.loc[mask, "tempo_observado"],
                event_observed=df.loc[mask, "evento"],
                label=label)
        resultados[valor] = kmf
    return resultados


def teste_logrank(df, coluna, valor_a, valor_b):
    """Log-rank test entre dois grupos."""
    mask_a = df[coluna] == valor_a
    mask_b = df[coluna] == valor_b
    if mask_a.sum() < 5 or mask_b.sum() < 5:
        return None
    resultado = logrank_test(
        df.loc[mask_a, "tempo_observado"], df.loc[mask_b, "tempo_observado"],
        event_observed_A=df.loc[mask_a, "evento"],
        event_observed_B=df.loc[mask_b, "evento"],
    )
    return resultado


def gerar_graficos(km_global, km_sexo, km_plano, saida_dir):
    """Gera gráficos das curvas KM."""
    os.makedirs(saida_dir, exist_ok=True)

    fig, ax = plt.subplots(figsize=(10, 6))
    km_global.plot_survival_function(ax=ax)
    ax.set_title("Kaplan-Meier — Sobrevivência Global")
    ax.set_xlabel("Tempo (anos)")
    ax.set_ylabel("Probabilidade de sobrevivência")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(saida_dir, "km_global.png"), dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 6))
    for kmf in km_sexo.values():
        kmf.plot_survival_function(ax=ax)
    ax.set_title("Kaplan-Meier — Sobrevivência por Sexo")
    ax.set_xlabel("Tempo (anos)")
    ax.set_ylabel("Probabilidade de sobrevivência")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(saida_dir, "km_sexo.png"), dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 6))
    for kmf in km_plano.values():
        kmf.plot_survival_function(ax=ax)
    ax.set_title("Kaplan-Meier — Sobrevivência por Tipo de Plano")
    ax.set_xlabel("Tempo (anos)")
    ax.set_ylabel("Probabilidade de sobrevivência")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(saida_dir, "km_plano.png"), dpi=150)
    plt.close(fig)


def imprimir_resumo(km_global, km_sexo, testes, df):
    """Imprime resumo das estimativas e testes."""
    print("=" * 60)
    print("KAPLAN-MEIER — RESUMO")
    print("=" * 60)

    mediana = km_global.median_survival_time_
    print(f"\nSobrevivência mediana global: {mediana:.2f} anos")
    print(f"Sobrevivência em 5 anos: {km_global.predict(5):.4f}")
    print(f"Sobrevivência em 10 anos: {km_global.predict(10):.4f}")

    print(f"\nPor sexo:")
    for valor, kmf in km_sexo.items():
        label = "Masculino" if valor == 1 else "Feminino"
        n = (df["sexo_M"] == valor).sum()
        eventos = df.loc[df["sexo_M"] == valor, "evento"].sum()
        print(f"  {label}: n={n}, eventos={eventos}, mediana={kmf.median_survival_time_:.2f} anos")

    if testes.get("sexo"):
        t = testes["sexo"]
        print(f"\nLog-rank test (sexo): estatística={t.test_statistic:.4f}, p={t.p_value:.4f}")
        if t.p_value < 0.05:
            print("  → Diferença estatisticamente significativa (p < 0.05)")
        else:
            print("  → Sem diferença significativa (p >= 0.05)")


def main():
    parser = argparse.ArgumentParser(description="Kaplan-Meier baseline")
    parser.add_argument("--dataset", default=None)
    parser.add_argument("--saida", default=None, help="Diretório para gráficos")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.dirname(__file__))
    dataset_path = args.dataset or os.path.join(base_dir, "data", "dataset_survival.csv")
    saida_dir = args.saida or os.path.join(base_dir, "data", "graficos")

    df = carregar_dataset(dataset_path)
    print(f"Dataset carregado: {len(df)} registros, {df['evento'].sum()} eventos\n")

    km_global = ajustar_km_global(df)

    km_sexo = ajustar_km_por_grupo(df, "sexo_M", {1: "Masculino", 0: "Feminino"})
    km_plano = ajustar_km_por_grupo(df, "plano_BD", {1: "BD", 0: "CD/CV"})

    testes = {}
    t_sexo = teste_logrank(df, "sexo_M", 1, 0)
    if t_sexo:
        testes["sexo"] = t_sexo

    gerar_graficos(km_global, km_sexo, km_plano, saida_dir)
    imprimir_resumo(km_global, km_sexo, testes, df)

    metricas_path = os.path.join(base_dir, "data", "metricas_km.csv")
    metricas = pd.DataFrame([{
        "modelo": "Kaplan-Meier",
        "mediana_global": km_global.median_survival_time_,
        "sobrev_5_anos": km_global.predict(5),
        "sobrev_10_anos": km_global.predict(10),
        "logrank_sexo_p": testes.get("sexo", type("", (), {"p_value": None})).p_value,
        "n_registros": len(df),
        "n_eventos": int(df["evento"].sum()),
    }])
    metricas.to_csv(metricas_path, index=False)
    print(f"\nMétricas salvas em {metricas_path}")
    print(f"Gráficos salvos em {saida_dir}/")


if __name__ == "__main__":
    main()
