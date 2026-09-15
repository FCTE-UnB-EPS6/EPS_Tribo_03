"""
Passo 6 — Backtesting Temporal e Decisão Champion-Challenger

Divide o histórico em Treino e Holdout (anos mais recentes fora da amostra).
Compara o desempenho preditivo do modelo Baseline contra o modelo Lee-Carter.

Exigência estrita do Definition of Done (§3/§8 DoD):
"O baseline simples não foi superado apenas por complexidade, e o ganho está
justificado."

Uso:
    python scripts/backtest/backtest_temporal.py
"""

from datetime import date
from pathlib import Path
import csv
import sys
import numpy as np

# Adiciona scripts/ ao sys.path para imports limpos
PASTA_SCRIPTS = Path(__file__).resolve().parents[1]
if str(PASTA_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(PASTA_SCRIPTS))

from config import PASTA_BACKTEST, LIMIAR_GANHO_COMPLEXIDADE, PROPORCAO_HOLDOUT
from dados.series_temporais import carregar_dados
from modelos.baseline import treinar_baseline, projetar_baseline
from modelos.lee_carter import treinar_lee_carter, projetar_lee_carter


def separar_treino_holdout(linhas, proporcao_holdout=PROPORCAO_HOLDOUT):
    """Separa os anos mais recentes como conjunto de teste/holdout."""
    anos = sorted({l["ano"] for l in linhas})
    n_holdout = max(1, int(round(len(anos) * proporcao_holdout)))

    anos_treino = anos[:-n_holdout]
    anos_holdout = anos[-n_holdout:]

    treino = [l for l in linhas if l["ano"] in anos_treino]
    holdout = [l for l in linhas if l["ano"] in anos_holdout]

    return anos_treino, anos_holdout, treino, holdout


def avaliar_previsoes(previsoes, observados):
    """Calcula RMSE, MAE, MAPE e Qui-quadrado sobre óbitos esperados vs observados."""
    erros = []
    erros_abs = []
    erros_pct = []
    chi2_obitos = 0.0

    for p in previsoes:
        q_prev = p["q_previsto"]
        q_obs = p["q_observado"]
        obitos_obs = p["obitos"]
        exposicao = p["exposicao"]

        erros.append((q_prev - q_obs) ** 2)
        erros_abs.append(abs(q_prev - q_obs))
        if q_obs > 1e-6:
            erros_pct.append(abs(q_prev - q_obs) / q_obs)

        # Qui-quadrado atuarial sobre óbitos esperados vs observados
        obitos_esperados = exposicao * q_prev
        if obitos_esperados > 0:
            chi2_obitos += ((obitos_obs - obitos_esperados) ** 2) / obitos_esperados

    rmse = float(np.sqrt(np.mean(erros))) if erros else 0.0
    mae = float(np.mean(erros_abs)) if erros_abs else 0.0
    mape = float(np.mean(erros_pct)) if erros_pct else 0.0

    return {
        "rmse": round(rmse, 7),
        "mae": round(mae, 7),
        "mape": round(mape, 4),
        "chi2_obitos": round(float(chi2_obitos), 2),
        "n_celulas": len(previsoes),
    }


def executar_backtest(linhas):
    """Executa o protocolo completo de backtest temporal Champion-Challenger."""
    anos_treino, anos_holdout, treino, holdout = separar_treino_holdout(linhas)

    # 1. Ajuste dos dois modelos no conjunto de treino
    modelo_base = treinar_baseline(treino)
    modelo_lc = treinar_lee_carter(treino)

    # 2. Geração de previsões para as células do Holdout (teste cego)
    prev_base = []
    prev_lc = []

    for reg in holdout:
        idade = reg["idade"]
        ano = reg["ano"]
        q_obs = reg["qx"]
        obitos = reg["obitos"]
        exp = reg["exposicao_central"]

        q_hat_base = projetar_baseline(modelo_base, idade, ano)
        q_hat_lc = projetar_lee_carter(modelo_lc, idade, ano)

        item_base = {
            "idade": idade, "ano": ano, "q_observado": q_obs,
            "q_previsto": q_hat_base, "obitos": obitos, "exposicao": exp
        }
        item_lc = {
            "idade": idade, "ano": ano, "q_observado": q_obs,
            "q_previsto": q_hat_lc, "obitos": obitos, "exposicao": exp
        }

        prev_base.append(item_base)
        prev_lc.append(item_lc)

    # 3. Cálculo das métricas comparativas
    met_base = avaliar_previsoes(prev_base, holdout)
    met_lc = avaliar_previsoes(prev_lc, holdout)

    # 4. Decisão formal segundo o critério do DoD:
    # Lee-Carter só é adotado se obtiver ganho mensurável sobre o baseline (>= 5% redução de RMSE)
    rmse_base = met_base["rmse"]
    rmse_lc = met_lc["rmse"]
    ganho_rmse = (rmse_base - rmse_lc) / rmse_base if rmse_base > 0 else 0.0

    if ganho_rmse >= LIMIAR_GANHO_COMPLEXIDADE:
        campeao = "Lee-Carter"
        justificativa = (
            f"Lee-Carter superou o Baseline com redução de {ganho_rmse*100:.2f}% no RMSE "
            f"fora da amostra (superando o limiar de {LIMIAR_GANHO_COMPLEXIDADE*100:.0f}% exigido pelo DoD)."
        )
    else:
        campeao = "Baseline"
        justificativa = (
            f"Lee-Carter não obteve ganho expressivo sobre o Baseline (ganho de {ganho_rmse*100:.2f}% "
            f"vs limiar de {LIMIAR_GANHO_COMPLEXIDADE*100:.0f}%). Conforme o DoD, a complexidade não se justifica "
            f"e o Baseline é mantido."
        )

    return {
        "anos_treino": anos_treino,
        "anos_holdout": anos_holdout,
        "baseline": met_base,
        "lee_carter": met_lc,
        "ganho_rmse": round(float(ganho_rmse), 4),
        "modelo_campeao": campeao,
        "justificativa": justificativa,
    }


def montar_relatorio(resultado):
    base = resultado["baseline"]
    lc = resultado["lee_carter"]
    ganho = resultado["ganho_rmse"] * 100

    return f"""# Backtesting Temporal — Comparação Champion-Challenger (§3/§8 DoD)

**Objetivo:** Avaliar a acurácia de projeção fora da amostra e decidir formalmente se a complexidade do modelo Lee-Carter se justifica frente ao Baseline simples.

- **Período de Treino:** {resultado['anos_treino'][0]} a {resultado['anos_treino'][-1]} ({len(resultado['anos_treino'])} anos)
- **Período Holdout (Teste cego):** {resultado['anos_holdout'][0]} a {resultado['anos_holdout'][-1]} ({len(resultado['anos_holdout'])} anos)
- **Células avaliadas no Holdout:** {base['n_celulas']}

## 1. Comparativo de Métricas Fora da Amostra

| Métrica de Desempenho | Baseline (Extrapolação) | Challenger (Lee-Carter) | Diferença (Ganho LC) |
| :--- | :--- | :--- | :--- |
| **RMSE (Erro Médio Quadrático)** | {base['rmse']:.7f} | {lc['rmse']:.7f} | {ganho:+.2f}% |
| **MAE (Erro Médio Absoluto)** | {base['mae']:.7f} | {lc['mae']:.7f} | {((base['mae'] - lc['mae'])/base['mae'])*100:+.2f}% |
| **MAPE (Erro Percentual Médio)** | {base['mape']*100:.2f}% | {lc['mape']*100:.2f}% | {(base['mape'] - lc['mape'])*100:+.2f} p.p. |
| **Estatística Qui-quadrado Óbitos** | {base['chi2_obitos']:.2f} | {lc['chi2_obitos']:.2f} | — |

## 2. Veredito de Promoção do Modelo (Critério DoD)

**Modelo Campeão Selecionado:** **{resultado['modelo_campeao']}**

> [!NOTE]
> **Justificativa da Decisão:**
> {resultado['justificativa']}
"""


def gravar_relatorio(conteudo, caminho):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(conteudo)


def main():
    linhas, origem = carregar_dados()
    res = executar_backtest(linhas)
    relatorio = montar_relatorio(res)

    caminho = PASTA_BACKTEST / f"backtest_temporal_{date.today().isoformat()}.md"
    gravar_relatorio(relatorio, caminho)

    print("Backtesting temporal executado com sucesso!")
    print(f"  Treino: {res['anos_treino'][0]}-{res['anos_treino'][-1]} | Holdout: {res['anos_holdout'][0]}-{res['anos_holdout'][-1]}")
    print(f"  RMSE Baseline: {res['baseline']['rmse']:.6f} | RMSE Lee-Carter: {res['lee_carter']['rmse']:.6f}")
    print(f"  Veredito Oficial: Campeão = {res['modelo_campeao']}")
    print(f"  Relatório salvo em: {caminho}")


if __name__ == "__main__":
    main()
