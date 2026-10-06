# Model Card de Explicabilidade e Model Risk: Lee-Carter (Passo 6)

> **Versão do card:** 1.0.0 · **Slice:** SL-07, Etapa 1 · **Dupla:** D3.7 (Leticia e Victor)
> **Card original do modelo:** [`tabuas-geracionais-improvement/docs/model_card.md`](../../tabuas-geracionais-improvement/docs/model_card.md), da dupla do Passo 6 (Danielle e Maria Eduarda).
>
> Este card **não substitui** o card original. O card original descreve como o modelo foi construído e validado. Este card descreve **como o modelo se comporta** (explicabilidade) e **onde ele pode errar** (model risk).

Os números citados vêm da rodada registrada em [`experiment_record_lee_carter.md`](experiment_record_lee_carter.md) e do relatório `lee_carter/relatorio_explicabilidade_lee_carter.json`.

---

## 1. Propósito

| | |
|---|---|
| **O que o modelo faz** | Projeta a probabilidade de morte q(x,t) por idade (*x*) e ano (*t*), incorporando a queda da mortalidade ao longo do tempo (*mortality improvement*). |
| **Para que serve** | Candidato à base da tábua geracional usada no cálculo de passivos de fundos de pensão (risco de longevidade). |
| **Atenção: não é o modelo de produção** | No backtest do Passo 6 (`tabuas-geracionais-improvement/docs/backtest/backtest_temporal_2026-09-30.md`) o modelo campeão foi o **Baseline**, e é ele que vira a tábua geracional. O contrato `obter_parametros_para_passo7()` entrega o Lee-Carter de propósito, por ser a decomposição interpretável disponível. Esta explicação descreve o **padrão de mortalidade** que o Lee-Carter captura, e não o número exato que vai para a tábua de produção. |
| **Para que esta explicação serve** | Mostrar à Tribo 1 (dashboards), à Tribo 6 (auditoria) e à SL-08 o que move as projeções e quais riscos elas carregam. |
| **Uso proibido** | Decisão automática sobre pessoas. É uma estimativa **populacional**, insumo de risco coletivo. |

## 2. Dados e origem

| | |
|---|---|
| **Fonte** | Série histórica real do IBGE, 2015-2024, por idade simples (rótulo `origem_dados` do contrato: "Passo 1 — IBGE real, série histórica (serie_historica_qx.csv, 2015-2024)"). |
| **Natureza** | Dado público **agregado** por idade e ano. Nenhum dado pessoal. |
| **Cobertura** | 51 idades (20 a 70 anos) × 10 anos (2015 a 2024). Projeção: 2025 a 2054 (30 anos, horizonte do Passo 6). |
| **Como chega aqui** | Contrato `obter_parametros_para_passo7()`, que treina o Lee-Carter sobre toda a série e devolve os parâmetros. Não alteramos o contrato. |

## 3. Método de explicação

| Técnica | O que responde | Como foi feita |
|---|---|---|
| **Leitura dos parâmetros** | Como a mortalidade se divide entre "efeito da idade" (alpha_x), "efeito do tempo" (kappa_t) e "sensibilidade de cada idade ao tempo" (beta_x). | Gráficos `alpha_x.png`, `beta_x.png`, `kappa_t.png`. |
| **ALE** (*Accumulated Local Effects*) | "Em média, quanto q muda quando só a idade (ou só o ano) muda?" | Biblioteca `PyALE` 1.2.0, 20 faixas, sobre a grade completa idade × ano (2015-2054). Como a grade tem todas as combinações, idade e ano são independentes e o ALE fica praticamente igual a um gráfico de dependência parcial (PDP). A vantagem usual do ALE (não usar combinações que não existem nos dados) não se aplica aqui. Ele foi mantido por ser o pedido da SL-07 e por servir também às Etapas 2 e 3, em que as entradas são correlacionadas. Gráficos `ale_idade.png`, `ale_ano.png`. |
| **SHAP** (valores de Shapley) | "Para esta idade e este ano, quanto da diferença entre q e a média veio da idade e quanto veio do ano?" A soma das contribuições mais o valor base dá exatamente o q. | Fórmula exata para 2 entradas, com fundo = grade histórica (2015-2024), conferida contra `shap.explainers.Exact` nos testes. Gráfico `shap_dependencia.png`: a cor de cada ponto é a outra entrada, o que mostra a interação idade × ano. |
| **Checagens de plausibilidade** | O modelo faz sentido atuarial? Se não, nada é publicado. | Ver seção 5. |

**Por que não só SHAP?** O Lee-Carter já é interpretável por construção: os próprios parâmetros são a explicação. ALE e SHAP entram para traduzir os parâmetros em efeito sobre q(x,t), que é o número que o dashboard mostra. Ver [`decisoes.md`](decisoes.md), D1.

## 4. O que a explicação mostra

### 4.1 A idade é o que mais pesa

- **SHAP:** importância média (|SHAP| médio) da **idade = 0,00433** contra **ano = 0,00085**. A idade pesa cerca de **5 vezes mais** que o ano calendário. Valor base (q médio do período 2015-2024): **0,00610**. A média de |SHAP| é tomada sobre todas as células idade × ano de 2015 a 2054, das quais 30 dos 40 anos são projeção; o peso do ano reflete sobretudo a tendência projetada pelo drift.
- **ALE de idade:** cresce de forma contínua a partir dos 30 anos e acelera depois dos 50: −0,0038 aos 30, −0,0009 aos 50, +0,0038 aos 60, +0,0147 aos 70 (diferença em relação à média).
- **alpha_x** sobe de −6,61 (20 anos) para −3,77 (70 anos), que é o padrão esperado de mortalidade adulta (lei de Gompertz).

### 4.2 O tempo reduz a mortalidade, mas a série tem uma quebra

- **ALE de ano:** cai de +0,0011 (2015) para −0,0010 (2054). É o *mortality improvement* projetado. Nos anos históricos a curva usa o kappa_t ajustado de cada ano, então também reflete o salto de 2022 (MR1); ver `ale_ano.png`.
- **kappa_t** cai de forma quase linear de 2015 (+3,10) a 2021 (−3,03), **salta para +3,24 em 2022** e volta para −1,04 (2023) e −2,07 (2024). Ver o alerta da seção 6.
- Efeito prático do salto: o q de 60 anos em 2022 (0,01082) volta ao nível de 2015 (0,01079).

### 4.3 Quem melhora mais

- **beta_x** é maior nas idades jovens (0,0246 aos 20) do que nas maduras (0,0177 aos 40 e aos 60, 0,0183 aos 70). As idades jovens são as que mais respondem à tendência de queda.

### 4.4 Exemplo de leitura para o dashboard (Tribo 1)

> "Na população brasileira de 60 anos, a taxa estimada de mortalidade em um ano é de cerca de 1,0% hoje (2024) e cai para cerca de 0,7% em 2054. Quase toda a diferença entre faixas etárias vem da idade; o ano calendário reduz a mortalidade aos poucos."

Valores do modelo: q(60, 2024) = 0,00985 e q(60, 2054) = 0,00727.

## 5. Checagens de plausibilidade (bloqueiam a publicação)

| Checagem | Regra | Resultado |
|---|---|---|
| `estrutura_consistente` | tamanhos de alpha_x, beta_x e kappa_t batem com idades e anos; idades crescentes; anos consecutivos. Se falhar, as demais checagens não são calculadas | aprovado |
| `valores_finitos` | parâmetros e q(x,t) sem NaN ou infinito | aprovado (q de 0,000839 a 0,024217) |
| `q_cresce_com_idade` | q cresce com a idade **a partir dos 30 anos**, em todos os anos de 2015 a 2054 | aprovado |
| `kappa_em_queda` | drift < 0 **e** reta ajustada a kappa_t com inclinação < 0 | aprovado (−0,5752 e −0,4035) |
| `restricoes_canonicas` | soma(beta_x) = 1 e média(kappa_t) = 0 | aprovado |

**Status da rodada: APROVADO.**

## 6. Model risk: alertas (não bloqueiam, mas precisam de resposta)

| # | Alerta | O que foi visto | Por que importa | Encaminhamento |
|---|---|---|---|---|
| MR1 | `salto_kappa` | kappa_t +6,27 de 2021 para 2022 e −4,29 de 2022 para 2023 (limite: 3 × \|drift\| = 1,73) | Pode ser uma quebra na série (hipótese, não confirmada: revisão da tábua do IBGE com o Censo 2022). Além disso, 2020-2021 (COVID) **não** mostram alta de mortalidade, o que sugere que as tábuas desses anos são projeções e não o observado. | Avisar a dupla do Passo 6 (Danielle e Maria Eduarda) |
| MR2 | `drift_sensivel_aos_extremos` | O drift do Passo 6 usa só o primeiro e o último ano (−0,5752). A reta ajustada a todos os anos dá −0,4035, um ritmo de queda cerca de 30% menor (limite do alerta: 25%). | O drift define toda a projeção de 30 anos. O drift atual projeta uma queda de mortalidade **mais rápida** que a reta ajustada. Num fundo de pensão (risco de longevidade), mortalidade menor significa pessoas vivendo mais e passivo **maior**: a escolha atual tende a **superestimar** o passivo (lado conservador). O risco é o inverso para produtos com pagamento por morte. De qualquer forma, o resultado depende de 2 pontos da série, um deles vizinho do salto de 2022. | Levar à dupla do Passo 6 e à SL-08 (análise de cauda/CVaR) |
| MR3 | `corcova_de_acidentes` | 7 casos em que q não cresce com a idade abaixo dos 30 anos (idades 25-26 em 2015-2018 e 2022) | Comportamento conhecido (mortes por causas externas em adultos jovens), não erro. Por isso a checagem de monotonia começa nos 30. | Registrado; sem ação |

O script também gera o alerta `beta_negativo` (beta_x < 0 em alguma idade, ou seja, mortalidade projetada subindo naquela idade). Esse alerta foi criado depois da rodada 1; o resultado dele entra na próxima rodada registrada.

Outros riscos e limitações: [`limitacoes-e-vieses.md`](limitacoes-e-vieses.md).

## 7. Vieses por subgrupo

O contrato do Passo 6 entrega dados **agregados por idade e ano**, sem sexo, região ou outro subgrupo. **Não é possível** medir diferença de erro entre subgrupos nesta etapa. Isso está registrado como limitação (critério de aceitação da SL-07: "ou registra por que não foi possível calcular"). A principal consequência é que a série combina homens e mulheres, que têm mortalidade e ritmo de melhora diferentes.

## 8. Reidentificação

Risco **baixo**: dado público agregado, sem registro individual. Ver [`reidentificacao.md`](reidentificacao.md).

## 9. Versão e rastreabilidade

| | |
|---|---|
| Card | 1.0.0 |
| Contrato do relatório | `schemas/relatorio_explicabilidade.schema.json` v1.0.0 |
| Modelo de origem | Lee-Carter do Passo 6, commit registrado em cada rodada (`rodada.commit` no JSON) |
| Rodadas | [`experiment_record_lee_carter.md`](experiment_record_lee_carter.md) |
