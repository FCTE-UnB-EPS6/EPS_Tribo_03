# Experiment Record — Tábuas Geracionais e Mortality Improvement

Registro de cada rodada de ajuste da tábua geracional: parâmetros utilizados, dados de entrada, resultados dos testes de hipótese e desempenho no backtest temporal.

---

## 1. Parâmetros Metodológicos Fixos

| Parâmetro | Valor Padrão | Localização no Código | Efeito Metodológico |
| :--- | :--- | :--- | :--- |
| `HORIZONTE_PROJECAO_ANOS` | 30 anos | `scripts/tabua_geracional.py` | Horizonte de projeção da matriz atuarial $q(x, t)$ |
| `LIMIAR_GANHO_COMPLEXIDADE` | 0.05 (5%) | `scripts/backtest_temporal.py` | Redução mínima de RMSE fora da amostra para adotar Lee-Carter sobre Baseline |
| `ALPHA` | 0.05 | `scripts/teste_mann_kendall.py` | Nível de significância dos testes de hipótese |
| `LIMITE_FX_MAX` | 0.035 (3.5% a.a.) | `scripts/modelo_baseline.py` | Trava de sanidade atuarial para evitar projeções de mortalidade zero/negativa |
| `PROPORCAO_HOLDOUT` | 0.25 (25%) | `scripts/backtest_temporal.py` | Fração dos anos mais recentes reservados para teste cego no backtest |

---

## 2. Histórico de Execuções

| Data | Origem dos Dados | Volume / Anos | Teste Mann-Kendall | Diagnóstico Estacionariedade | RMSE Baseline | RMSE Lee-Carter | Modelo Campeão | Veredito DoD |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 2026-09-14 | Série Histórica Sintética | 10 anos (2015-2024, 510 células) | S=-17, Z=-1.43, p=0.152 (tendência estável) | ADF=-2.307 (p=0.17), KPSS=0.225 (p>0.1) | 0.0104472 | 0.0135281 | **Baseline** (Lee-Carter -29.49%) | **APROVADO**: Baseline mantido por parcimônia (DoD §8) |

---

## 3. Notas de Rastreabilidade e Decisões Técnicas

- **Mann-Kendall:** Exigido pelo §3 e §8 do Definition of Done para certificar que o *improvement* não é ruído aleatório antes de qualquer projeção.
- **ADF & KPSS:** A constatação conjunta de não-estacionariedade e raiz unitária na série em nível dá suporte teórico à equação de *Random Walk with Drift* de $\kappa_t$ no modelo Lee-Carter.
- **Decomposição SVD:** Resolvida por SVD de posto 1 com normalizações $\sum \beta_x = 1.0$ e $\sum \kappa_t = 0.0$, garantindo reprodutibilidade matemática exata.
- **Gate de Decisão Champion-Challenger:** Em estrita aderência ao critério de governança da Tribo 3, se em alguma rodada o Lee-Carter não superar o Baseline por ao menos 5% de melhoria no RMSE, o modelo Baseline de taxa geométrica é automaticamente mantido como oficial.
