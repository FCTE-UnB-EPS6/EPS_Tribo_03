# Model Card — Modelagem Geracional e Mortality Improvement (Passo 6)

## Visão Geral do Modelo

- **Finalidade:** Projeção atuarial da evolução temporal da mortalidade $q(x, t)$ para planos de benefícios de previdência fechada.
- **Abordagem Metodológica:** Estrutura *Champion-Challenger* comparando um modelo **Baseline** interpretável (extrapolação geométrica de tendência anual) contra o modelo **Lee-Carter (1992)** via SVD e Random Walk with Drift.
- **Critério de Decisão (DoD §8):** Princípio de baseline antes de complexidade. O modelo Lee-Carter só é adotado como *Champion* se demonstrar ganho superior a 5% no RMSE fora da amostra no backtesting temporal.

---

## Formulação Matemática

### 1. Modelo Baseline (Extrapolação de Tendência)
Para cada idade $x$, ajusta-se a trajetória temporal do logaritmo da taxa de mortalidade:
$$\ln(q_{x,t}) = a_x - b_x \cdot (t - t_0)$$
O fator anual de melhoria de mortalidade é dado por:
$$f_x = 1 - e^{-b_x}, \quad \text{com restrição } f_x \in [0.00, 0.035]$$
A probabilidade de morte no horizonte projetado é:
$$q_{x, t_0 + h} = q_{x, t_0} \times (1 - f_x)^h$$

### 2. Modelo Lee-Carter (1992)
O modelo estocástico de Lee-Carter decompõe a taxa central de mortalidade $m_{x,t}$ em:
$$\ln(m_{x,t}) = \alpha_x + \beta_x \kappa_t + \epsilon_{x,t}$$

- $\alpha_x = \frac{1}{T} \sum_{t=1}^T \ln(m_{x,t})$: perfil etário básico da mortalidade.
- $\kappa_t$: índice geral do nível de mortalidade no ano de calendário $t$.
- $\beta_x$: padrão etário da resposta a variações em $\kappa_t$.
- **Condições Canônicas de Identificabilidade:**
  $$\sum_x \beta_x = 1.0, \quad \sum_t \kappa_t = 0.0$$
- **Solução Numérica:** Decomposição em Valores Singulares (SVD) de posto 1 da matriz centralizada $Z_{x,t} = \ln(m_{x,t}) - \alpha_x$.
- **Dinâmica Temporal:** $\kappa_t$ é projetado como um Passeio Aleatório com *Drift* (Random Walk with Drift):
  $$\kappa_t = \kappa_{t-1} + d + e_t, \quad d = \frac{\kappa_T - \kappa_1}{T - 1}$$
  $$\hat{\kappa}_{T + h} = \kappa_T + h \cdot d$$
- **Taxa Projetada:**
  $$\hat{q}_{x, T + h} = 1 - \exp\left(-\exp(\alpha_x + \beta_x \hat{\kappa}_{T + h})\right)$$

---

## Validação Temporal e Métricas de Erro

A calibração e a seleção são realizadas via partição temporal estrita:
- **Treino:** $75\%$ dos anos mais antigos.
- **Holdout (Teste Cego):** $25\%$ dos anos mais recentes.
- **Métricas:**
  - $\text{RMSE} = \sqrt{\frac{1}{N}\sum (q_{\text{prev}} - q_{\text{obs}})^2}$
  - $\text{MAE} = \frac{1}{N}\sum |q_{\text{prev}} - q_{\text{obs}}|$
  - Estatística de aderência $\chi^2$ sobre os óbitos observados vs esperados.

---

## Restrição de Uso e Governança Ética

> [!IMPORTANT]
> **RESTRIÇÃO EXPLÍCITA DO ESCOPO:**
> As estimativas geracionais de sobrevivência são instrumentos técnicos e analíticos exclusivamente destinados à gestão coletiva de risco atuarial, solvência de planos e cálculo de reservas matemáticas coletivas.
> **Nunca devem ser utilizadas para decisões individuais automatizadas, concessão ou negação discriminatória de direitos previdenciários.**
