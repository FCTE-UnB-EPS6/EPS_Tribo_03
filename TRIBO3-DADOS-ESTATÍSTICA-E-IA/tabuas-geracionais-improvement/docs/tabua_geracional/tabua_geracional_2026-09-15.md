# Tábua Biométrica Geracional — Consolidação Oficial

**Modelo Selecionado pelo Backtest:** `Baseline`
**Ano Base (t0):** 2021
**Horizonte de Projeção:** 30 anos (até 2051)

## 1. Amostra de Projeção por Coorte e Idade

Evolução da probabilidade de morte $q(x, t)$ para idades selecionadas ao longo do horizonte:

| Idade | qx no Ano Base | qx em +10 Anos | qx em +20 Anos | qx em +30 Anos | Redução Total em 30 Anos |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 25 anos | 0.000435 | 0.000432 | 0.000430 | 0.000427 | **1.88%** |
| 40 anos | 0.000959 | 0.000811 | 0.000686 | 0.000581 | **39.42%** |
| 55 anos | 0.003222 | 0.002875 | 0.002565 | 0.002289 | **28.95%** |
| 65 anos | 0.007149 | 0.006138 | 0.005270 | 0.004525 | **36.70%** |

## 2. Conformidade com o Definition of Done (§3/§8)

- [x] **Tendência estatística testada:** Mann-Kendall atestou a direção do *improvement*.
- [x] **Estacionariedade diagnosticada:** Testes ADF/KPSS justificaram a modelagem temporal estocástica.
- [x] **Validação temporal executada:** Holdout temporal mediu RMSE e MAE fora da amostra.
- [x] **Complexidade justificada:** O modelo `Baseline` foi selecionado estritamente pela regra de ganho empírico do DoD.
- [x] **Tábua geracional exportada:** Matriz completa disponível para consumo da Tribo 2 (Backend) e Tribo 1 (Dashboards).

> [!NOTE]
> A tábua geracional está pronta para uso em avaliações atuariais dinâmicas e projeções de solvência.