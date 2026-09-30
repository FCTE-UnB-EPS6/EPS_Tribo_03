# Tábua Biométrica Geracional — Consolidação Oficial

**Modelo Selecionado pelo Backtest:** `Baseline`
**Ano Base (t0):** 2024
**Horizonte de Projeção:** 30 anos (até 2054)

## 1. Amostra de Projeção por Coorte e Idade

Evolução da probabilidade de morte $q(x, t)$ para idades selecionadas ao longo do horizonte:

| Idade | qx no Ano Base | qx em +10 Anos | qx em +20 Anos | qx em +30 Anos | Redução Total em 30 Anos |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 25 anos | 0.001522 | 0.001521 | 0.001520 | 0.001520 | **0.12%** |
| 40 anos | 0.002366 | 0.002207 | 0.002060 | 0.001922 | **18.78%** |
| 55 anos | 0.006680 | 0.005777 | 0.004996 | 0.004320 | **35.32%** |
| 65 anos | 0.014788 | 0.013902 | 0.013069 | 0.012286 | **16.92%** |

## 2. Conformidade com o Definition of Done (§3/§8)

- [x] **Tendência estatística testada:** Mann-Kendall atestou a direção do *improvement*.
- [x] **Estacionariedade diagnosticada:** Testes ADF/KPSS justificaram a modelagem temporal estocástica.
- [x] **Validação temporal executada:** Holdout temporal mediu RMSE e MAE fora da amostra.
- [x] **Complexidade justificada:** O modelo `Baseline` foi selecionado estritamente pela regra de ganho empírico do DoD.
- [x] **Tábua geracional exportada:** Matriz completa disponível para consumo da Tribo 2 (Backend) e Tribo 1 (Dashboards).

> [!NOTE]
> A tábua geracional está pronta para uso em avaliações atuariais dinâmicas e projeções de solvência.