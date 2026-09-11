"""
Random Survival Forest — Challenger (Passo 2)

Treina um Random Survival Forest (scikit-survival) como modelo challenger
para comparação com o baseline Cox PH. Só será adotado se apresentar
ganho mensurável de C-index frente ao Cox.

Uso:
    python scripts/survival_forest.py
    python scripts/survival_forest.py --dataset data/dataset_survival.csv
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
from sksurv.ensemble import RandomSurvivalForest
from sksurv.metrics import concordance_index_censored, integrated_brier_score
from sklearn.model_selection import train_test_split


def carregar_dataset(caminho):
    if not os.path.exists(caminho):
        print(f"Dataset não encontrado em {caminho}")
        print("Rode primeiro: python scripts/construir_dataset.py")
        sys.exit(1)
    return pd.read_csv(caminho)


def preparar_dados(df, covariaveis, seed=42):
    """Prepara dados no formato exigido pelo scikit-survival."""
    X = df[covariaveis].values
    y = np.array(
        [(bool(e), t) for e, t in zip(df["evento"], df["tempo_observado"])],
        dtype=[("evento", bool), ("tempo", float)],
    )

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, random_state=seed, stratify=df["evento"]
    )

    return X_train, X_test, y_train, y_test


def treinar_rsf(X_train, y_train, seed=42):
    """Treina o Random Survival Forest."""
    rsf = RandomSurvivalForest(
        n_estimators=100,
        min_samples_split=10,
        min_samples_leaf=5,
        max_features="sqrt",
        n_jobs=-1,
        random_state=seed,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        rsf.fit(X_train, y_train)
    return rsf


def calcular_metricas(rsf, X_train, X_test, y_train, y_test):
    """Calcula C-index e Integrated Brier Score."""
    pred_test = rsf.predict(X_test)
    c_index = concordance_index_censored(
        y_test["evento"], y_test["tempo"], pred_test
    )[0]

    pred_train = rsf.predict(X_train)
    c_index_train = concordance_index_censored(
        y_train["evento"], y_train["tempo"], pred_train
    )[0]

    ibs = None
    try:
        tempos_eval = np.percentile(
            y_test["tempo"][y_test["evento"]], np.arange(10, 91, 10)
        )
        if len(tempos_eval) >= 2:
            surv_funcs = rsf.predict_survival_function(X_test)
            preds = np.row_stack([fn(tempos_eval) for fn in surv_funcs])
            ibs = integrated_brier_score(y_train, y_test, preds, tempos_eval)
    except Exception:
        pass

    return {
        "c_index_test": c_index,
        "c_index_train": c_index_train,
        "ibs": ibs,
    }


def importancia_variaveis(rsf, covariaveis, saida_dir):
    """Plota importância das variáveis (permutation importance)."""
    importancias = rsf.feature_importances_
    ordem = np.argsort(importancias)[::-1]

    fig, ax = plt.subplots(figsize=(10, 6))
    nomes = [covariaveis[i] for i in ordem]
    valores = [importancias[i] for i in ordem]
    ax.barh(range(len(nomes)), valores[::-1])
    ax.set_yticks(range(len(nomes)))
    ax.set_yticklabels(nomes[::-1])
    ax.set_xlabel("Importância")
    ax.set_title("Random Survival Forest — Importância das Variáveis")
    ax.grid(True, alpha=0.3, axis="x")
    fig.tight_layout()
    fig.savefig(os.path.join(saida_dir, "rsf_importancia.png"), dpi=150)
    plt.close(fig)

    return list(zip(nomes, valores))


def curva_sobrevivencia_exemplo(rsf, X_test, y_test, saida_dir):
    """Plota curvas de sobrevivência para alguns indivíduos do teste."""
    surv_funcs = rsf.predict_survival_function(X_test[:5])

    fig, ax = plt.subplots(figsize=(10, 6))
    for i, fn in enumerate(surv_funcs):
        status = "evento" if y_test[i]["evento"] else "censurado"
        ax.step(fn.x, fn(fn.x), where="post",
                label=f"Indivíduo {i+1} ({status}, t={y_test[i]['tempo']:.1f})")
    ax.set_xlabel("Tempo (anos)")
    ax.set_ylabel("Probabilidade de sobrevivência")
    ax.set_title("Random Survival Forest — Curvas Individuais (amostra)")
    ax.legend(loc="lower left", fontsize=8)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(saida_dir, "rsf_curvas_individuais.png"), dpi=150)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Random Survival Forest challenger")
    parser.add_argument("--dataset", default=None)
    parser.add_argument("--saida", default=None)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.dirname(__file__))
    dataset_path = args.dataset or os.path.join(base_dir, "data", "dataset_survival.csv")
    saida_dir = args.saida or os.path.join(base_dir, "data", "graficos")
    os.makedirs(saida_dir, exist_ok=True)

    df = carregar_dataset(dataset_path)
    print(f"Dataset carregado: {len(df)} registros, {df['evento'].sum()} eventos\n")

    covariaveis = ["idade_ingresso", "sexo_M", "plano_BD", "plano_CD",
                    "submassa_A", "submassa_B"]

    X_train, X_test, y_train, y_test = preparar_dados(df, covariaveis, args.seed)
    print(f"Treino: {len(X_train)} | Teste: {len(X_test)}")
    print(f"Eventos treino: {y_train['evento'].sum()} | Eventos teste: {y_test['evento'].sum()}")

    print("\nTreinando Random Survival Forest...")
    rsf = treinar_rsf(X_train, y_train, args.seed)

    metricas = calcular_metricas(rsf, X_train, X_test, y_train, y_test)

    print("\n" + "=" * 60)
    print("RANDOM SURVIVAL FOREST — RESUMO")
    print("=" * 60)
    print(f"C-index (teste):  {metricas['c_index_test']:.4f}")
    print(f"C-index (treino): {metricas['c_index_train']:.4f}")
    if metricas["ibs"] is not None:
        print(f"Integrated Brier Score: {metricas['ibs']:.4f}")

    overfit = metricas["c_index_train"] - metricas["c_index_test"]
    if overfit > 0.05:
        print(f"\n⚠️  Possível overfitting: diferença treino-teste = {overfit:.4f}")
    else:
        print(f"\n✅ Diferença treino-teste aceitável: {overfit:.4f}")

    print("\nImportância das variáveis:")
    imp = importancia_variaveis(rsf, covariaveis, saida_dir)
    for nome, valor in imp:
        print(f"  {nome}: {valor:.4f}")

    curva_sobrevivencia_exemplo(rsf, X_test, y_test, saida_dir)

    metricas_path = os.path.join(base_dir, "data", "metricas_rsf.csv")
    pd.DataFrame([{
        "modelo": "Random Survival Forest",
        "c_index_test": metricas["c_index_test"],
        "c_index_train": metricas["c_index_train"],
        "ibs": metricas["ibs"],
        "n_estimators": 100,
        "n_covariaveis": len(covariaveis),
        "n_treino": len(X_train),
        "n_teste": len(X_test),
        "n_eventos_teste": int(y_test["evento"].sum()),
    }]).to_csv(metricas_path, index=False)
    print(f"\nMétricas salvas em {metricas_path}")
    print(f"Gráficos salvos em {saida_dir}/")


if __name__ == "__main__":
    main()
