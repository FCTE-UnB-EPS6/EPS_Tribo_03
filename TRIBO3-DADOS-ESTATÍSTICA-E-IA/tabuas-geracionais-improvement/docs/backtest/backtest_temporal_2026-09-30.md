# Backtesting Temporal — Comparação Champion-Challenger (§3/§8 DoD)

**Objetivo:** Avaliar a acurácia de projeção fora da amostra e decidir formalmente se a complexidade do modelo Lee-Carter se justifica frente ao Baseline simples.

- **Período de Treino:** 2015 a 2022 (8 anos)
- **Período Holdout (Teste cego):** 2023 a 2024 (2 anos)
- **Células avaliadas no Holdout:** 102

## 1. Comparativo de Métricas Fora da Amostra

| Métrica de Desempenho | Baseline (Extrapolação) | Challenger (Lee-Carter) | Diferença (Ganho LC) |
| :--- | :--- | :--- | :--- |
| **RMSE (Erro Médio Quadrático)** | 0.0002341 | 0.0009316 | -297.95% |
| **MAE (Erro Médio Absoluto)** | 0.0001347 | 0.0006675 | -395.55% |
| **MAPE (Erro Percentual Médio)** | 2.47% | 11.10% | -8.63 p.p. |
| **Estatística Qui-quadrado Óbitos** | 46.34 | 735.83 | — |

## 2. Veredito de Promoção do Modelo (Critério DoD)

**Modelo Campeão Selecionado:** **Baseline**

> [!NOTE]
> **Justificativa da Decisão:**
> Lee-Carter não obteve ganho expressivo sobre o Baseline (ganho de -297.95% vs limiar de 5%). Conforme o DoD, a complexidade não se justifica e o Baseline é mantido.
