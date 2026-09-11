# Experiment Record — Modelo Individual de Sobrevivência

## Experimento 1: Baseline (Kaplan-Meier + Cox PH)

| Campo | Valor |
|-------|-------|
| Data | 2026-09-10 |
| Objetivo | Estabelecer baseline de sobrevivência para a massa sintética |
| Dados | dataset_survival.csv (Passo 1, seed=42, n=300) |
| Versão dos dados | Gerador v1, data_referencia=2026-08-31 |

### Kaplan-Meier

| Métrica | Valor |
|---------|-------|
| Mediana de sobrevivência global | *(preencher após execução)* |
| Sobrevivência em 5 anos | *(preencher após execução)* |
| Sobrevivência em 10 anos | *(preencher após execução)* |
| Log-rank test (sexo) p-valor | *(preencher após execução)* |

### Cox PH

| Parâmetro | Valor |
|-----------|-------|
| Covariáveis | idade_ingresso, sexo_M, plano_BD, plano_CD, submassa_A, submassa_B |
| Regularização | penalizer=0.01 |

| Métrica | Valor |
|---------|-------|
| C-index | *(preencher após execução)* |
| AIC parcial | *(preencher após execução)* |
| Covariáveis significativas (p<0.05) | *(preencher após execução)* |
| Teste de Schoenfeld — violações | *(preencher após execução)* |

---

## Experimento 2: Challenger (Random Survival Forest)

| Campo | Valor |
|-------|-------|
| Data | 2026-09-10 |
| Objetivo | Testar se um modelo ensemble supera o baseline Cox |
| Dados | dataset_survival.csv (mesmo do Exp. 1) |

| Parâmetro | Valor |
|-----------|-------|
| n_estimators | 100 |
| min_samples_split | 10 |
| min_samples_leaf | 5 |
| max_features | sqrt |
| Split treino/teste | 70/30, estratificado |

| Métrica | Valor |
|---------|-------|
| C-index (teste) | *(preencher após execução)* |
| C-index (treino) | *(preencher após execução)* |
| Integrated Brier Score | *(preencher após execução)* |
| Overfitting (diff treino-teste) | *(preencher após execução)* |

---

## Experimento 3: Comparação Champion-Challenger

| Campo | Valor |
|-------|-------|
| Data | 2026-09-10 |
| Método | Validação temporal, 5 folds |
| Limiar de adoção | ganho de C-index > 0.02 |

| Métrica | Cox PH | RSF |
|---------|--------|-----|
| C-index médio (temporal) | *(preencher)* | *(preencher)* |
| Ganho do challenger | — | *(preencher)* |

### Veredito

*(preencher após execução: BASELINE MANTIDO ou CHALLENGER ADOTADO, com justificativa)*

---

## Registro de decisões

1. **Evento de interesse**: óbito — evento terminal mais claro para previdência. Competing risks (invalidez, aposentadoria) ficam para evolução futura.
2. **Censura**: participantes ativos ou desligados por motivo ≠ óbito são censurados na data de saída ou na data de referência.
3. **Categorias de referência**: plano_CV e submassa_C omitidas do modelo (evitar multicolinearidade perfeita no one-hot).
4. **Baseline antes de complexidade**: Cox PH é o champion até que o RSF demonstre ganho mensurável (C-index > 0.02 na validação temporal).
5. **Restrição ética**: estimativa individual é insumo analítico para risco coletivo, nunca para decisão automática sobre direitos individuais.
