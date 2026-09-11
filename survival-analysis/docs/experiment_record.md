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
| Mediana de sobrevivência global | Não atingida (taxa de eventos baixa: 3%) |
| Sobrevivência em 5 anos | 0.9800 |
| Sobrevivência em 10 anos | 0.9744 |
| Log-rank test (sexo) p-valor | 0.9244 (sem diferença significativa) |

Observação: a mediana não foi atingida porque a taxa de eventos (óbito) é de apenas 3% na massa sintética com seed=42. Os 9 eventos em 300 participantes refletem os pesos do gerador (status_obito = 0.05). A curva KM por sexo não mostra diferença significativa (p=0.92), o que é esperado dado que o gerador não condiciona mortalidade ao sexo.

### Cox PH

| Parâmetro | Valor |
|-----------|-------|
| Covariáveis | idade_ingresso, sexo_M, plano_BD, plano_CD, submassa_A, submassa_B |
| Regularização | penalizer=0.01 (ridge) |

| Métrica | Valor |
|---------|-------|
| C-index | 0.7389 |
| AIC parcial | 98.77 |
| Covariáveis significativas (p<0.05) | 0 de 6 |
| Teste de Schoenfeld — violações | 0 (hipótese PH não violada) |

Hazard ratios estimados (nenhum significativo a 5%):

| Covariável | HR | p |
|------------|-----|-------|
| idade_ingresso | 0.94 | 0.22 |
| sexo_M | 1.16 | 0.80 |
| plano_BD | 0.88 | 0.86 |
| plano_CD | 1.93 | 0.30 |
| submassa_A | 2.79 | 0.10 |
| submassa_B | 0.73 | 0.70 |

Observação: nenhuma covariável atingiu significância a 5%, mas submassa_A (HR=2.79, p=0.10) está próxima. Com poucos eventos (n=9), o poder estatístico é limitado. O C-index de 0.74 indica discriminação razoável apesar da não-significância individual dos coeficientes. Teste de Schoenfeld confirmou que a hipótese de riscos proporcionais não é violada para nenhuma covariável.

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
| Split treino/teste | 70/30, estratificado (210 treino, 90 teste) |

| Métrica | Valor |
|---------|-------|
| C-index (teste) | 0.5660 |
| C-index (treino) | 0.9881 |
| Integrated Brier Score | 0.0227 |
| Overfitting (diff treino-teste) | 0.4221 |

Importância das variáveis (permutation importance):

| Covariável | Importância |
|------------|-------------|
| submassa_A | 0.1946 |
| plano_CD | 0.0494 |
| idade_ingresso | 0.0328 |
| sexo_M | -0.0047 |
| plano_BD | -0.0095 |
| submassa_B | -0.0233 |

Observação: overfitting severo — C-index no treino (0.99) vs. teste (0.57). Com apenas 6 eventos no treino e 3 no teste, o RSF memoriza os poucos eventos em vez de generalizar. O IBS baixo (0.023) reflete que a maioria das previsões são "sobrevive", o que é trivialmente correto quando 97% da amostra é censurada.

---

## Experimento 3: Comparação Champion-Challenger

| Campo | Valor |
|-------|-------|
| Data | 2026-09-10 |
| Método | Validação temporal, 3 folds efetivos (2 folds excluídos por eventos insuficientes) |
| Limiar de adoção | ganho de C-index > 0.02 |

| Fold | Cox PH | RSF |
|------|--------|-----|
| 1 | 0.3778 | 0.4926 |
| 2 | 0.5417 | 0.3750 |
| 3 | 0.2903 | 0.5968 |

| Métrica | Cox PH | RSF |
|---------|--------|-----|
| C-index médio (temporal) | 0.4033 | 0.4881 |
| Ganho do challenger | — | +0.0849 |

### Veredito

Numericamente o RSF apresentou ganho de +0.085 sobre o Cox na validação temporal, superando o limiar de 0.02. Porém, esse resultado não é confiável por três motivos:

1. **Poucos eventos** (9 total, distribuídos em 3 folds) — qualquer fold com 1-2 eventos tem variância altíssima no C-index.
2. **Ambos abaixo de 0.5 em alguns folds** — indicando que nem Cox nem RSF discriminam de forma consistente com tão poucos dados.
3. **Overfitting severo do RSF** (0.99 treino vs. 0.57 teste no split fixo).

**Decisão: manter o Cox PH como champion.** A simplicidade e interpretabilidade do Cox são preferíveis quando o challenger não demonstra superioridade robusta. O RSF será reavaliado quando a massa sintética for gerada com mais participantes ou com maior taxa de eventos.

---

## Registro de decisões

1. **Evento de interesse**: óbito — evento terminal mais claro para previdência. Competing risks (invalidez, aposentadoria) ficam para evolução futura.
2. **Censura**: participantes ativos ou desligados por motivo diferente de óbito são censurados na data de saída ou na data de referência.
3. **Categorias de referência**: plano_CV e submassa_C omitidas do modelo (evitar multicolinearidade perfeita no one-hot).
4. **Baseline antes de complexidade**: Cox PH mantido como champion. O RSF apresentou overfitting e instabilidade na validação temporal com poucos eventos. A complexidade extra não se justifica neste cenário.
5. **Restrição ética**: estimativa individual é insumo analítico para risco coletivo, nunca para decisão automática sobre direitos individuais.
6. **Limitação da massa sintética**: 300 participantes com taxa de óbito de 5% resultam em apenas 9 eventos, insuficientes para discriminação robusta. Recomenda-se gerar com n >= 1000 ou ajustar os pesos do gerador para avaliação mais rigorosa dos modelos.
