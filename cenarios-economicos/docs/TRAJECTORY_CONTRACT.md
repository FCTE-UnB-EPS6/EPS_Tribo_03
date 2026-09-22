# Contrato de trajetória econômica

Versão: `0.2.0`

Status: contrato integrado ao gerador, API e persistência.

## Finalidade e compatibilidade

O contrato `0.2.0` representa uma trajetória anual variável, rastreável até um
artefato de calibração ou um modelo versionado. Ele foi introduzido sem remover
o contrato `0.1.0`: o mesmo endpoint seleciona explicitamente o fluxo pelo campo
`contract_version`, sem atualização automática de versão.

O validador puro está em `app/contracts/trajectory.py`. Ele não lê arquivos, não
consulta rede ou banco e devolve uma cópia independente do payload validado. O
exemplo completo está em `examples/trajectory.demo.v0.2.0.json` e deve ser lido
com `loads_decimal`, para preservar números JSON como `Decimal`.

## Estrutura

O objeto raiz possui somente estes campos:

| Campo | Regra |
|---|---|
| `contract_version` | valor fixo `0.2.0` |
| `purpose` | `projection` ou `backtest` |
| `base_date` | data ISO `YYYY-MM-DD` |
| `horizon_years` | inteiro entre 1 e 120 |
| `unit` | valor fixo `annual_decimal` |
| `rate_basis` | valor fixo `nominal` |
| `ruleset_id`, `ruleset_version` | identidade da regra que produzirá os cenários |
| `calibration` | referência imutável ao artefato usado |
| `trajectory` | identidade, versão e períodos anuais |

`calibration` registra `artifact_id`, `calibration_id`,
`calibration_version`, `artifact_schema_version`,
`transformation_policy_version`, `cutoff_date`, `sha256` e `scope`. O
`artifact_id` deve ser exatamente `<calibration_id>@<calibration_version>`. Esta
versão aceita schema de artefato `1.0.0` e política de transformação `0.1.0`.
O escopo é `historical_only` ou `historical_and_market_implied`.

`trajectory` registra `trajectory_id`, `trajectory_version` e `periods`. A
quantidade de períodos deve ser igual ao horizonte. Os períodos são contíguos,
numerados a partir de 1, e suas datas seguem os aniversários da data-base. Para
29 de fevereiro, o aniversário em ano não bissexto é 28 de fevereiro.

## Variáveis e valores

`inflation` e `discount_rate` são obrigatórias. `salary_growth` e
`asset_return` são opcionais, mas cada uma deve aparecer em todos os períodos ou
em nenhum. Variáveis desconhecidas e `null` são rejeitados.

Cada variável contém:

| Campo | Significado |
|---|---|
| `value` | taxa anual nominal em fração decimal |
| `status` | natureza do valor: `observed`, `market_implied` ou `modeled` |
| `measure` | classificação matemática da medida |
| `source_metric` | métrica exata de origem ou saída do modelo |
| `method` | método versionável que produziu o valor |
| `source` | proveniência uniforme e verificável |

Taxas aceitam apenas `int` ou `Decimal`, devem ser finitas, maiores que `-1` e
ter no máximo oito casas decimais significativas após remover zeros finais.
`float`, booleano, string numérica e valores não finitos são rejeitados.

As combinações válidas são:

| Status | Medida | Origem | Restrições |
|---|---|---|---|
| `observed` | `effective_return` | `calibration_artifact` | somente inflação IPCA em `backtest` e período concluído até o corte |
| `market_implied` | `forward_rate` | `calibration_artifact` | somente inflação implícita ETTJ ou desconto nominal ETTJ, com escopo de mercado |
| `modeled` | `modeled_rate` | `model` | permitido para todas as variáveis |

`discount_rate` nunca recebe status `observed`. `salary_growth` e
`asset_return` são sempre modeladas. O contrato não promove Ibovespa a retorno
da carteira e não inventa crescimento salarial ausente no artefato.

## Proveniência

Toda fonte informa `kind`, `reference`, `reference_version`, `reference_date` e
`path`. `path` é um JSON Pointer absoluto. Fontes do artefato devem coincidir
com seu ID e versão declarados; fontes modeladas devem identificar um modelo
versionado.

Para `market_implied`, inflação usa
`ettj_implied_inflation_forward` e desconto usa `ettj_nominal_forward`. A data
da curva deve estar entre zero e sete dias antes do corte. Uma calibração
`historical_only` não pode sustentar esses valores.

## Projeção e backtest

Em `projection`, o corte deve estar entre zero e sete dias antes da data-base.
Valores futuros nunca podem ser rotulados como observados.

Em `backtest`, inflação observada é permitida apenas em períodos encerrados e o
corte deve ser igual ou posterior ao fim da trajetória. Essa separação impede
que informação futura seja apresentada como disponível na data-base.

## Geração, API e persistência

O gerador aplica a cada período os choques aditivos do ruleset selecionado. O
cenário Base exige ajustes zero e reproduz os valores da trajetória. Adverso e
Favorável usam ajustes constantes por variável; nenhum status ou proveniência é
alterado, pois a trajetória completa permanece preservada em `request_snapshot`.
O resultado contém os três cenários, `trajectory_id` e `trajectory_version` em
cada cenário e taxas escalares por variável em `values` para manter o formato de
consumo já usado no contrato anterior.

O endpoint `POST /api/v1/scenarios/generate` documenta os contratos `0.1.0` e
`0.2.0` com `oneOf` no OpenAPI. Consultas de execução e cenário também expõem
as duas formas de resposta.

A migração `002_trajectory_contract.sql` cria `trajectory_set`, registra no
`run` qual contrato e identidade de entrada foram usados e mantém premissas
`0.1.0` e trajetórias `0.2.0` em tabelas distintas. Conteúdo associado ao mesmo
`trajectory_id` e `trajectory_version` é imutável; divergência gera
`TRAJECTORY_VERSION_CONFLICT` e rollback da execução inteira.

## Erros

Falhas geram `TrajectoryContractError` com `code`, `field`, `message` e
`as_dict()`. Os códigos distinguem estrutura da requisição, versão não
suportada, referência de calibração, estrutura da trajetória e valor econômico.

Os erros específicos de trajetória retornam HTTP 422. Conflito de identidade e
versão retorna HTTP 409. Erros de regras continuam sendo tratados antes da
persistência e falhas do PostgreSQL retornam o envelope sanitizado já existente.
