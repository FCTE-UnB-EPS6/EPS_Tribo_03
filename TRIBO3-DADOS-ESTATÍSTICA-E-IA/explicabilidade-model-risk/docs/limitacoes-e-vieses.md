# Limitações, Vieses e Model Risk: Passo 7 / SL-07

> Etapa 1 (Lee-Carter do Passo 6). As Etapas 2 e 3 acrescentam seções próprias quando forem entregues.

## 1. Achados de model risk do Lee-Carter

Detalhes e números no [model card, seção 6](model_card_lee_carter.md#6-model-risk-alertas-não-bloqueiam-mas-precisam-de-resposta).

| # | Achado | Impacto possível | Quem precisa saber |
|---|---|---|---|
| MR1 | Salto do kappa_t em 2022 (+6,27) e volta em 2023 (−4,29) | Se for quebra de série, o modelo mistura duas metodologias de tábua | Dupla do Passo 6 |
| MR2 | Drift calculado só pelos extremos (−0,575) contra a reta ajustada a todos os anos (−0,404) | Projeção de 30 anos com queda de mortalidade possivelmente exagerada, o que pode **subestimar o passivo** | Dupla do Passo 6; SL-08 (CVaR) |
| MR3 | Anos de COVID (2020-2021) sem alta de mortalidade | Indica que a série pode ser de tábuas projetadas e não observadas; choques reais ficam invisíveis | Dupla do Passo 6 / Passo 1 |
| MR4 | Variância explicada pelo 1º componente = 76% | Cerca de um quarto da variação da série não é capturado pela forma "uma tendência só para todas as idades" | Registro |

## 2. Limitações da explicação

- **A explicação só é tão boa quanto o modelo de origem.** Erros nos dados ou no ajuste do Passo 6 aparecem aqui, mas são corrigidos lá.
- **Série curta:** 10 anos (2015-2024). Qualquer tendência estimada tem muita incerteza.
- **Projeção sem incerteza nesta etapa:** o q projetado usa kappa_T + h × drift, sem simular choques. Intervalos e risco de cauda (CVaR) são escopo da SL-08.
- **Faixa de idades:** só 20 a 70 anos. Nada se pode dizer sobre idades fora dessa faixa, justamente as mais relevantes para aposentados muito idosos.
- **ALE e SHAP com entradas fixas:** idade e ano são as únicas entradas; a explicação não diz nada sobre *causas* da mortalidade.

## 3. Vieses por subgrupo

**Não foi possível calcular nesta etapa.** O contrato do Passo 6 entrega só dados agregados por idade e ano, sem sexo, região, renda ou tipo de plano. Consequências:

- A série combina homens e mulheres. As mulheres vivem mais e o ritmo de melhora pode ser diferente. Um fundo com mais homens ou mais mulheres que a população brasileira terá mortalidade real diferente da projetada.
- A população do IBGE não é a população de um fundo de pensão (que costuma ter renda maior e mortalidade menor).

A análise de vieses por subgrupo (sexo, plano, submassa) entra na **Etapa 3** (Passo 2), que tem dados individuais sintéticos com essas variáveis.

## 4. O que fica para depois

- Etapa 2 (Passo 5) e Etapa 3 (Passo 2), quando os modelos de origem estiverem prontos.
- Resposta da dupla do Passo 6 sobre MR1, MR2 e MR3.
- Limite de tempo de execução (RNF02), a definir com base nas rodadas registradas.
