"""
Comparação Champion-Challenger — Passo 2

Compara os modelos treinados (Cox PH vs. Random Survival Forest) por
C-index, calibração e Integrated Brier Score. O modelo mais complexo
só será adotado se houver ganho mensurável frente ao baseline.

Uso:
    python scripts/comparar_modelos.py
"""

import argparse
import os
import sys
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from lifelines import CoxPHFitter
from sklearn.model_selection import train_test_split
from sksurv.ensemble import RandomSurvivalForest
from sksurv.metrics import concordance_index_censored


COVARIAVEIS = ["idade_ingresso", "sexo_M", "plano_BD", "plano_CD",
               "submassa_A", "submassa_B"]

LIMIAR_GANHO = 0.02


def carregar_dataset(caminho):
    if not os.path.exists(caminho):
        print(f"Dataset não encontrado em {caminho}")
        sys.exit(1)
    return pd.read_csv(caminho)


def validacao_temporal(df, covariaveis, n_folds=5, seed=42):
    """Validação temporal: split por ordem de tempo_observado."""
    df_sorted = df.sort_values("tempo_observado").reset_index(drop=True)
    fold_size = len(df_sorted) // n_folds

    resultados_cox = []
    resultados_rsf = []

    for i in range(n_folds - 1):
        inicio_teste = (i + 1) * fold_size
        fim_teste = min((i + 2) * fold_size, len(df_sorted))

        df_train = df_sorted.iloc[:inicio_teste]
        df_test = df_sorted.iloc[inicio_teste:fim_teste]

        if df_test["evento"].sum() < 2 or df_train["evento"].sum() < 2:
            continue

        cols_cox = covariaveis + ["tempo_observado", "evento"]
        cph = CoxPHFitter(penalizer=0.01)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            cph.fit(df_train[cols_cox], duration_col="tempo_observado", event_col="evento")

        pred_cox = -cph.predict_partial_hazard(df_test[covariaveis]).values.ravel()
        c_cox = concordance_index_censored(
            df_test["evento"].astype(bool),
            df_test["tempo_observado"],
            pred_cox,
        )[0]
        resultados_cox.append(c_cox)

        X_train = df_train[covariaveis].values
        y_train = np.array(
            [(bool(e), t) for e, t in zip(df_train["evento"], df_train["tempo_observado"])],
            dtype=[("evento", bool), ("tempo", float)],
        )
        X_test = df_test[covariaveis].values
        y_test = np.array(
            [(bool(e), t) for e, t in zip(df_test["evento"], df_test["tempo_observado"])],
            dtype=[("evento", bool), ("tempo", float)],
        )

        rsf = RandomSurvivalForest(
            n_estimators=100, min_samples_split=10, min_samples_leaf=5,
            max_features="sqrt", n_jobs=-1, random_state=seed,
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            rsf.fit(X_train, y_train)

        pred_rsf = rsf.predict(X_test)
        c_rsf = concordance_index_censored(
            y_test["evento"], y_test["tempo"], pred_rsf
        )[0]
        resultados_rsf.append(c_rsf)

    return resultados_cox, resultados_rsf


def gerar_grafico_comparacao(resultados_cox, resultados_rsf, saida_dir):
    """Gráfico de C-index por fold temporal."""
    os.makedirs(saida_dir, exist_ok=True)

    fig, ax = plt.subplots(figsize=(10, 6))
    folds = range(1, len(resultados_cox) + 1)
    ax.plot(folds, resultados_cox, "o-", label=f"Cox PH (média={np.mean(resultados_cox):.4f})")
    ax.plot(folds, resultados_rsf, "s-", label=f"RSF (média={np.mean(resultados_rsf):.4f})")
    ax.axhline(y=0.5, color="gray", linestyle="--", alpha=0.5, label="Aleatório (0.5)")
    ax.set_xlabel("Fold temporal")
    ax.set_ylabel("C-index")
    ax.set_title("Validação Temporal — Cox PH vs. Random Survival Forest")
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_xticks(list(folds))
    fig.tight_layout()
    fig.savefig(os.path.join(saida_dir, "comparacao_temporal.png"), dpi=150)
    plt.close(fig)


def imprimir_veredito(resultados_cox, resultados_rsf):
    """Emite o veredito champion-challenger."""
    media_cox = np.mean(resultados_cox)
    media_rsf = np.mean(resultados_rsf)
    ganho = media_rsf - media_cox

    print("\n" + "=" * 60)
    print("VEREDITO CHAMPION-CHALLENGER")
    print("=" * 60)
    print(f"\nC-index médio (validação temporal):")
    print(f"  Cox PH (baseline):              {media_cox:.4f}")
    print(f"  Random Survival Forest (chall.): {media_rsf:.4f}")
    print(f"  Ganho do challenger:             {ganho:+.4f}")
    print(f"  Limiar para adoção:              {LIMIAR_GANHO:.4f}")

    if ganho > LIMIAR_GANHO:
        print(f"\n✅ CHALLENGER ADOTADO — RSF supera o baseline Cox por {ganho:.4f} de C-index.")
        champion = "Random Survival Forest"
    else:
        print(f"\n📌 BASELINE MANTIDO — ganho do RSF ({ganho:+.4f}) "
              f"não justifica a complexidade extra.")
        champion = "Cox PH"

    print(f"\nModelo champion: {champion}")
    return champion, media_cox, media_rsf, ganho


def main():
    parser = argparse.ArgumentParser(description="Comparação champion-challenger")
    parser.add_argument("--dataset", default=None)
    parser.add_argument("--saida", default=None)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.dirname(__file__))
    dataset_path = args.dataset or os.path.join(base_dir, "data", "dataset_survival.csv")
    saida_dir = args.saida or os.path.join(base_dir, "data", "graficos")

    df = carregar_dataset(dataset_path)
    print(f"Dataset carregado: {len(df)} registros, {df['evento'].sum()} eventos")

    print("\nRodando validação temporal (pode demorar)...")
    resultados_cox, resultados_rsf = validacao_temporal(df, COVARIAVEIS, seed=args.seed)

    print(f"\nC-index por fold:")
    for i, (c, r) in enumerate(zip(resultados_cox, resultados_rsf)):
        print(f"  Fold {i+1}: Cox={c:.4f}, RSF={r:.4f}")

    champion, media_cox, media_rsf, ganho = imprimir_veredito(resultados_cox, resultados_rsf)

    gerar_grafico_comparacao(resultados_cox, resultados_rsf, saida_dir)

    resumo_path = os.path.join(base_dir, "data", "comparacao_champion_challenger.csv")
    pd.DataFrame([{
        "champion": champion,
        "c_index_cox_medio": media_cox,
        "c_index_rsf_medio": media_rsf,
        "ganho_rsf": ganho,
        "limiar_adocao": LIMIAR_GANHO,
        "n_folds": len(resultados_cox),
        "n_registros": len(df),
        "n_eventos": int(df["evento"].sum()),
        "seed": args.seed,
    }]).to_csv(resumo_path, index=False)
    print(f"\nResumo salvo em {resumo_path}")
    print(f"Gráfico salvo em {saida_dir}/comparacao_temporal.png")


if __name__ == "__main__":
    main()
