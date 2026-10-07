"""Challenger RSF e diagnósticos do holdout temporal, chamados por main.py."""
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from sksurv.ensemble import RandomSurvivalForest
from sklearn.inspection import permutation_importance


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
    rsf.fit(X_train, y_train)
    return rsf


def importancia_variaveis(rsf, covariaveis, X_test, y_test, saida_dir):
    """Plota importância das variáveis via permutation importance."""
    result = permutation_importance(rsf, X_test, y_test, n_repeats=15, random_state=42)
    importancias = result.importances_mean
    ordem = np.argsort(importancias)[::-1]

    fig, ax = plt.subplots(figsize=(10, 6))
    nomes = [covariaveis[i] for i in ordem]
    valores = [importancias[i] for i in ordem]
    ax.barh(range(len(nomes)), valores[::-1])
    ax.set_yticks(range(len(nomes)))
    ax.set_yticklabels(nomes[::-1])
    ax.set_xlabel("Importância (permutation)")
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
