# Contrato econômico — Economic Scenario Generator

Versão: `0.1.0`

Data: 2026-09-13

Status: proposta inicial para implementação; alinhamento entre consumidores pendente.

Responsáveis: Carlos Henrique de Souza Bispo e Paulo Henrique Virgilio Cerqueira.

## 1. Propósito e limites

Definir entradas e saídas do gerador determinístico de cenários Base, Adverso e
Favorável. O núcleo, a camada de aplicação e a persistência PostgreSQL estão implementados.
A API HTTP também está implementada e validada localmente; implantação no servidor pendente.
Os cenários fornecem hipóteses para projeções; não calculam reservas, benefícios,
solvência ou ALM e não representam previsão econômica nem premissa aprovada para uso atuarial.

O consumidor acessará diretamente a API HTTP. A geração inicial não exige dados
individuais, acesso ao dataset sintético ou conclusão dos Passos 2, 5 e 6.

## 2. Convenções econômicas

- Todas as taxas são **efetivas anuais, nominais, em fração decimal**: `0.04`
  significa 4% ao ano. Não enviar `4` para representar 4%.
- Unidade fixa: `annual_decimal`; base fixa: `nominal`. Outra unidade ou base
  deve ser rejeitada, sem conversão implícita.
- O MVP recebe uma taxa constante por variável e a repete por período anual.
  Não há entrada mensal, curva de juros por vencimento ou trajetória variável nesta versão.
- Cada período começa na data-base ou em seu aniversário e termina no aniversário
  seguinte: intervalo `[period_start, period_end)`. Para data-base em 29/02,
  o aniversário em ano não bissexto será 28/02; calcular cada aniversário a partir
  da data-base original. `period` começa em 1 e termina em `horizon_years`.
- Taxas se aplicam ao período inteiro. Não há proporcionalização diária.
- Taxas reais, quando necessárias, exigirão extensão explícita do contrato.

## 3. Dicionário de variáveis

| Campo | Significado | Obrigatoriedade | Domínio técnico |
|---|---|---|---|
| `inflation` | Variação anual do índice de preços identificado na origem da premissa | Obrigatório | Número finito maior que -1 |
| `discount_rate` | Taxa anual constante para desconto de fluxos nominais pelo consumidor; não é retorno de carteira | Obrigatório | Número finito maior que -1 |
| `salary_growth` | Crescimento nominal total do salário, já incluindo a componente inflacionária; não somar inflação novamente | Opcional | Número finito maior que -1 |
| `asset_return` | Retorno nominal total da carteira representada; declarar na origem se é bruto ou líquido e quais custos contempla | Opcional | Número finito maior que -1 |

Todas usam a unidade e a base da seção 2. O domínio é uma restrição técnica deste
MVP, não uma faixa de plausibilidade econômica. Limites de plausibilidade e valores
centrais serão definidos em `ASSUMPTIONS.md` na próxima etapa.

Ausência de variável opcional significa **não fornecida**, nunca zero. Ela deve
ser omitida em todos os cenários e períodos. `null` não é aceito. O consumidor
que precisar dela deverá exigir sua presença antes de executar sua projeção.
Nenhuma variável de reajuste de benefício é inferida automaticamente da inflação:
a regra do plano pertence ao consumidor.

## 4. Entrada de geração

`POST /api/v1/scenarios/generate`, com `Content-Type: application/json`, corpo
JSON em UTF-8 e os seguintes campos:

| Campo | Tipo e regra |
|---|---|
| `contract_version` | String; exatamente `0.1.0` nesta versão |
| `base_date` | String de data válida `YYYY-MM-DD` |
| `horizon_years` | Inteiro entre 1 e 120; limite operacional inicial, sujeito a alinhamento |
| `unit` | String `annual_decimal` |
| `rate_basis` | String `nominal` |
| `assumption_set_id` | String não vazia que identifica o conjunto de premissas |
| `assumption_version` | String de versão `MAJOR.MINOR.PATCH` |
| `ruleset_id` | String não vazia que identifica regras disponíveis no backend |
| `ruleset_version` | String de versão `MAJOR.MINOR.PATCH`; sem alias `latest` |
| `assumptions` | Objeto com as variáveis da seção 3 |
| `sources` | Objeto com exatamente uma entrada por variável fornecida |

Cada entrada em `sources` contém strings não vazias: `kind` (`synthetic` ou
`external`), `reference` (identificador de documento/arquivo ou URL),
`reference_version`, `description`, `rationale`, `responsible`, além de
`reference_date` em `YYYY-MM-DD`. A data identifica a referência utilizada e
não substitui a data-base da projeção. Origem sintética deve declarar essa condição.
O registro de fonte não significa aprovação da premissa.

Exemplo completo de entrada, com valores exclusivamente demonstrativos:

```json
{
  "contract_version": "0.1.0",
  "base_date": "2026-09-13",
  "horizon_years": 1,
  "unit": "annual_decimal",
  "rate_basis": "nominal",
  "assumption_set_id": "demo",
  "assumption_version": "0.1.0",
  "ruleset_id": "demo-additive",
  "ruleset_version": "0.1.0",
  "assumptions": {"inflation": 0.04, "discount_rate": 0.08},
  "sources": {
    "inflation": {
      "kind": "synthetic",
      "reference": "demo-contract",
      "reference_version": "0.1.0",
      "reference_date": "2026-09-13",
      "description": "Índice de preços fictício para demonstração",
      "rationale": "Exercitar o contrato, sem calibração econômica",
      "responsible": "Dupla do Passo 4"
    },
    "discount_rate": {
      "kind": "synthetic",
      "reference": "demo-contract",
      "reference_version": "0.1.0",
      "reference_date": "2026-09-13",
      "description": "Taxa de desconto fictícia",
      "rationale": "Exercitar o contrato, sem calibração econômica",
      "responsible": "Dupla do Passo 4"
    }
  }
}
```

## 5. Contrato das regras determinísticas

As regras serão configuração versionada, preservada junto da execução. O conjunto
deve conter `ruleset_id`, `ruleset_version`, `description`, `responsible`,
`reference` e `scenarios`, com exatamente as chaves `base`, `adverse`, `favorable`.
Cada cenário contém `label`, `rationale`, `target_metric` e `adjustments`.
`target_metric` documenta o resultado que se pretende estressar; usar
`illustrative_only` enquanto não houver consumidor e métrica acordados.

`adjustments` mapeia cada variável configurada para um número finito em fração
decimal anual. Todos os ajustes são **aditivos**:

`taxa_do_cenario = taxa_base + ajuste`

Um ajuste de `0.01` adiciona 1 ponto percentual: `0.04` passa a `0.05`.
Não representa aumento proporcional de 1%. Ajuste zero significa manutenção.
O cenário Base exige ajustes zero. Para toda variável fornecida na entrada deve
existir ajuste explícito nos três cenários; não assumir zero se faltar configuração.
Regras para opcionais ausentes são ignoradas e não criam valores de saída.
Variáveis desconhecidas são rejeitadas também na configuração.

Os nomes Adverso e Favorável expressam a intenção das regras. Não garantem uma
ordenação de déficit ou solvência, que deve ser verificada pelo consumidor.
Choques são hipóteses determinísticas; não têm probabilidades associadas.

## 6. Saída e consulta

Geração bem-sucedida retorna HTTP `201`, somente após persistência completa da
execução, com `Location: /api/v1/runs/{run_id}`.

| Campo | Conteúdo |
|---|---|
| `run_id` | UUID atribuído pelo backend |
| `status` | `completed` |
| `created_at` | Data/hora UTC em RFC 3339, terminada em `Z` |
| `contract_version` | Versão deste contrato |
| `generator_version` | Versão da implementação efetivamente executada |
| `request_snapshot` | Entrada completa aceita, incluindo fontes e versões |
| `ruleset_snapshot` | Configuração completa usada, conforme seção 5 |
| `scenarios` | Lista com exatamente três cenários, em ordem Base, Adverso, Favorável |

Cada cenário contém `scenario_id` (UUID), `scenario_key` (`base`, `adverse` ou
`favorable`), `label`, `scenario_version` (inicialmente `0.1.0`), `base_date`,
`horizon_years`, `unit`, `rate_basis` e `values`. Versão e conteúdo de um cenário
persistido são imutáveis; nova geração produz novos identificadores.

`values` contém exatamente `horizon_years` objetos ordenados, com `period`,
`period_start`, `period_end` e `variables`. `variables` tem exatamente as mesmas
chaves presentes em `assumptions`, com as taxas resultantes do cenário.

Exemplo de um item de `values` do cenário Base para a entrada acima:

```json
{
  "period": 1,
  "period_start": "2026-09-13",
  "period_end": "2027-09-13",
  "variables": {"inflation": 0.04, "discount_rate": 0.08}
}
```

- `GET /api/v1/runs/{run_id}`: HTTP `200` com o mesmo registro persistido da geração.
- `GET /api/v1/scenarios/{scenario_id}`: HTTP `200` com `run_id` e `scenario`
  (o objeto de cenário completo), permitindo recuperar as evidências pela execução.
- Identificador UUID válido inexistente: HTTP `404`.
- `GET /health`: HTTP `200`, `{"status":"ok"}`, para verificar o processo.
  Não comprova disponibilidade do banco nem validação econômica.

## 7. Precisão, validação e erros

Taxas e ajustes são números JSON, com no máximo oito casas decimais significativas
após a vírgula decimal (zeros finais não contam). A implementação deve usar
aritmética decimal, sem arredondamento silencioso ou cálculo em ponto flutuante
binário. Resultados são números JSON com até oito casas decimais; `0.04` e
`0.04000000` representam o mesmo valor. Não retornar strings percentuais.

Rejeitar booleanos usados como números, strings numéricas, `null`, NaN, infinito,
campos desconhecidos, fontes faltantes ou extras, datas inválidas, horizonte fora
do limite, data final além do ano 9999 e taxas fora do domínio. Validar também os valores após os ajustes.
Se qualquer cenário for inválido, falhar a geração inteira, sem resultado parcial.

Erros usam o envelope abaixo, com `code`, `field` (caminho com pontos ou `null`
para erro geral) e `message`. Nenhum erro deve expor credenciais ou stack trace.

```json
{
  "error": {
    "code": "INVALID_ASSUMPTION",
    "field": "assumptions.inflation",
    "message": "A taxa deve ser um número finito maior que -1."
  }
}
```

| HTTP | Códigos previstos |
|---|---|
| `400` | `INVALID_JSON` |
| `415` | `UNSUPPORTED_MEDIA_TYPE`: enviar `Content-Type: application/json` |
| `422` | `INVALID_ASSUMPTION`, `INVALID_REQUEST`, `UNSUPPORTED_CONTRACT_VERSION`, `RULESET_NOT_FOUND`, `INVALID_SCENARIO` |
| `404` | `RUN_NOT_FOUND`, `SCENARIO_NOT_FOUND`, `ROUTE_NOT_FOUND` |
| `405` | `METHOD_NOT_ALLOWED` |
| `409` | `ASSUMPTION_VERSION_CONFLICT`: mesmo conjunto/versão com conteúdo econômico ou fontes diferentes |
| `500` | `INVALID_RULESET`, `INTERNAL_ERROR` |
| `503` | `STORAGE_UNAVAILABLE` |

Os números de versão identificam conteúdo imutável. O conjunto de premissas
identificado por ID/versão compreende `unit`, `rate_basis`, `assumptions` e
`sources`; data-base e horizonte pertencem à execução. Uma correção de conteúdo
exige nova versão. O backend não busca arquivos ou URLs enviados em `reference`.

## 8. Rastreabilidade e reprodução

Preservar os snapshots completos e a versão do gerador. Mesma entrada econômica,
mesmas regras e mesma versão do gerador devem produzir os mesmos valores, períodos
e ordem de cenários. `run_id`, `scenario_id` e `created_at` podem mudar.
Repetir um POST cria nova execução; não há deduplicação implícita nesta versão.

Alterações incompatíveis exigem nova versão do contrato e migração explícita dos
consumidores. O caminho `/api/v1` identifica a família da API e não substitui
`contract_version`. Não selecionar automaticamente a versão mais recente.

## 9. Alinhamentos antes da estabilização

| Tema | Interlocutor e decisão pendente |
|---|---|
| Uso de `qx` e `qx,t` | Passos 5 e 6: confirmar se consomem cenários diretamente ou se o encontro ocorre na projeção |
| Calendário e horizonte | Passos 5 e 6 e consumidor de projeção: validar aniversários, limite de 120 anos e periodicidade anual |
| Taxa de desconto | Responsável pela avaliação/projeção: confirmar adequação do baseline nominal constante |
| Variáveis opcionais | Consumidores de CD/CV e demais modalidades: indicar necessidade de salário e retorno e sua semântica |
| Cenários | Consumidor de risco/ALM: definir métrica-alvo e justificar os ajustes |
| Premissas | Dupla do Passo 4 e responsáveis do projeto: definir fontes, plausibilidade e processo de aprovação |

Esses alinhamentos não foram realizados neste documento. É possível implementar
o baseline com exemplos sintéticos enquanto o contrato permanece em versão inicial.

## 10. Critérios para a implementação posterior

- Aceitar o exemplo completo quando existir a configuração indicada.
- Gerar três trajetórias com períodos contíguos e Base igual às premissas.
- Preservar a ausência de opcionais e rejeitar configurações incompletas.
- Demonstrar que ajuste de `0.01` em `0.04` resulta em `0.05`.
- Rejeitar taxas inválidas antes e depois dos ajustes, sem persistência parcial.
- Reproduzir conteúdo econômico e recuperar snapshots pela consulta de execução.
- Verificar caso de data-base 29/02 e serialização decimal.

O contrato estará estabilizado após registrar as decisões da seção 9 e atualizar
os exemplos e a versão conforme necessário.
