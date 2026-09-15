# Backtesting Temporal — Comparação Champion-Challenger (§3/§8 DoD)

**Objetivo:** Avaliar a acurácia de projeção fora da amostra e decidir formalmente se a complexidade do modelo Lee-Carter se justifica frente ao Baseline simples.

- **Período de Treino:** 2012 a 2019 (8 anos)
- **Período Holdout (Teste cego):** 2020 a 2021 (2 anos)
- **Células avaliadas no Holdout:** 102

## 1. Comparativo de Métricas Fora da Amostra

| Métrica de Desempenho | Baseline (Extrapolação) | Challenger (Lee-Carter) | Diferença (Ganho LC) |
| :--- | :--- | :--- | :--- |
| **RMSE (Erro Médio Quadrático)** | 0.0001669 | 0.0002630 | -57.58% |
| **MAE (Erro Médio Absoluto)** | 0.0001155 | 0.0001709 | -47.97% |
| **MAPE (Erro Percentual Médio)** | 6.19% | 7.29% | -1.10 p.p. |
| **Estatística Qui-quadrado Óbitos** | 79.61 | 116.20 | — |

## 2. Veredito de Promoção do Modelo (Critério DoD)

**Modelo Campeão Selecionado:** **Baseline**

> [!NOTE]
> **Justificativa da Decisão:**
> Lee-Carter não obteve ganho expressivo sobre o Baseline (ganho de -57.58% vs limiar de 5%). Conforme o DoD, a complexidade não se justifica e o Baseline é mantido.
