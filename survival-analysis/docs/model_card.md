# Model Card — Modelo Individual de Sobrevivência

## Propósito

Estimar, para cada participante do fundo de pensão, a probabilidade de transição do estado "ativo" para outros estados (óbito, invalidez, aposentadoria, desligamento) ao longo do tempo. As estimativas servem como insumo analítico para gestão de risco coletivo.

**A estimativa individual é insumo analítico para gestão de risco coletivo, nunca decisão automática sobre direitos individuais.**

## População

Participantes sintéticos gerados pelo Passo 1, representando a massa segurada de um fundo de pensão com planos BD, CD e CV.

## Dados de entrada

| Campo | Descrição | Tipo |
|-------|-----------|------|
| tempo_observado | Tempo entre ingresso e evento/censura (anos) | float |
| evento | 1 = óbito, 0 = censurado | int |
| idade_ingresso | Idade em anos na data de ingresso | float |
| sexo_M | 1 = masculino, 0 = feminino | int |
| plano_BD | 1 se plano BD | int |
| plano_CD | 1 se plano CD | int |
| submassa_A | 1 se Plano A | int |
| submassa_B | 1 se Plano B | int |

**Referência para one-hot**: plano_CV e submassa_C são as categorias de referência (omitidas para evitar multicolinearidade).

## Modelos

### Baseline: Cox Proportional Hazards

- **Método**: regressão semi-paramétrica de Cox
- **Regularização**: penalizer=0.01 (ridge)
- **Hipótese**: riscos proporcionais — testada com resíduos de Schoenfeld
- **Métrica principal**: Concordance Index (C-index)

### Challenger: Random Survival Forest

- **Método**: ensemble de árvores de sobrevivência (scikit-survival)
- **Hiperparâmetros**: n_estimators=100, min_samples_split=10, min_samples_leaf=5, max_features=sqrt
- **Métrica principal**: C-index no conjunto de teste (split 70/30 estratificado)
- **Critério de adoção**: ganho de C-index > 0.02 sobre o Cox na validação temporal

## Validação

- **Validação temporal**: split por ordem cronológica de tempo_observado, 5 folds
- **Verificação de multicolinearidade**: correlação Pearson e Spearman entre covariáveis antes do ajuste
- **Teste de riscos proporcionais**: resíduos de Schoenfeld para o Cox
- **Monitoramento de overfitting**: comparação C-index treino vs. teste para o RSF

## Métricas

| Métrica | Descrição |
|---------|-----------|
| C-index | Discriminação: probabilidade de o modelo ordenar corretamente dois indivíduos |
| AIC parcial | Qualidade de ajuste do Cox (menor = melhor) |
| Integrated Brier Score | Calibração do RSF ao longo do tempo (menor = melhor) |
| Log-rank test | Significância da diferença entre curvas KM por subgrupo |

## Limitações

- **Dados sintéticos**: o modelo foi treinado e validado com dados gerados, não observados. As distribuições refletem os parâmetros do gerador do Passo 1.
- **Evento único**: o MVP modela apenas óbito como evento terminal. Invalidez, aposentadoria e desligamento são tratados como censura, não como riscos competitivos — a extensão para competing risks é evolução futura.
- **Covariáveis limitadas**: apenas idade, sexo, plano e submassa. Variáveis clínicas, socioeconômicas e comportamentais não estão disponíveis no dataset sintético.
- **Sem atualização dinâmica**: o modelo é estático — não incorpora novos eventos ao longo do tempo sem retreinamento.

## Versão e rastreabilidade

| Campo | Valor |
|-------|-------|
| Versão | 1.0 |
| Data | 2026-09-10 |
| Dados | Massa sintética Passo 1, seed=42 |
| Autores | Caio Brandão Santos, Pedro Lucas Figueiredo Santana |
