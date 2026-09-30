# Artefato versionado de calibracao economica

Versao do builder: `0.1.0`

Versao do schema do artefato: `1.0.0`

Versao da politica de transformacao: `0.1.0`

## Finalidade e fronteira

O builder transforma snapshots ja coletados e verificados em medidas historicas
anuais e, opcionalmente, em uma trajetoria de mercado derivada da ETTJ. Ele e uma
etapa offline: nao consulta a rede, nao acessa o PostgreSQL e nao modifica o
gerador durante uma requisicao HTTP.

O resultado não é aceito pelo contrato de cenários `0.1.0`. O
[contrato de trajetória `0.2.0`](TRAJECTORY_CONTRACT.md) define como referenciar
este artefato e já é consumido pelo gerador, API e persistência. A construção do
payload de trajetória a partir do conteúdo calibrado permanece uma etapa
explícita e offline; a API não lê artefatos nem consulta fontes externas.

## Entradas

O builder exige:

- um snapshot Bacen com Selic efetiva, meta Selic, CDI, IPCA, IGP-M e USD/BRL;
- um snapshot do Ibovespa produzido pelo coletor Yahoo Finance/yfinance;
- uma data de corte contida nos dois snapshots;
- identificador, versao semantica e responsavel pela calibracao.

O snapshot experimental da ANBIMA e opcional. Quando informado, seu uso precisa
ser autorizado explicitamente por `--allow-experimental-anbima`. Essa opcao nao
promove o spike a coletor produtivo: o artefato registra
`source_status: experimental-spike` e `status: market_implied`.

Antes de calcular, o builder confere:

- schema, identidade e versao dos coletores;
- byte count e SHA-256 de cada arquivo contra seu manifesto;
- caminhos relativos, schema das linhas, datas, duplicidades e numeros finitos;
- codigos, frequencias e unidades do catalogo Bacen;
- ticker, intervalo diario e parametros sem ajuste do Ibovespa;
- declaracao de que Yahoo Finance/yfinance nao e fonte oficial da B3;
- data, vertices e limite de sete dias da curva ANBIMA em relacao ao corte.

Qualquer divergencia interrompe a operacao antes da publicacao.
Os hashes comprovam consistencia entre arquivos e manifestos fornecidos, mas nao
substituem assinatura digital, controle de acesso ou um registro externo contra a
alteracao conjunta do dado e do manifesto.

## Execucao

Dentro de `cenarios-economicos/`:

```bash
python3 scripts/build_calibration.py \
  --bacen-snapshot data/raw/bacen/ID_DO_SNAPSHOT \
  --ibovespa-snapshot data/raw/ibovespa/ID_DO_SNAPSHOT \
  --anbima-snapshot /caminho/para/ID_DO_SNAPSHOT_EXPERIMENTAL \
  --allow-experimental-anbima \
  --cutoff 2025-12-31 \
  --calibration-id tribo3-base \
  --calibration-version 1.0.0 \
  --responsible "Equipe de cenarios economicos" \
  --output data/calibrated/economic
```

Sem `--anbima-snapshot`, o resultado e explicitamente classificado como
`historical_only`. Com a curva, recebe `historical_and_market_implied`.

## Estrutura publicada

Uma execucao bem-sucedida cria atomicamente:

```text
data/calibrated/economic/calibration-tribo3-base-v1.0.0/
|-- calibration.json
`-- manifest.json
```

`calibration.json` contem:

- identidade e versoes do schema, builder e politica;
- data de corte, responsavel e convencoes numericas;
- snapshots-fonte, hashes dos manifestos e hashes dos arquivos;
- anos disponiveis por metrica e a intersecao de anos elegiveis;
- observacoes historicas anuais normalizadas;
- vertices spot e forwards anuais da ETTJ, quando fornecida;
- mapeamentos candidatos para o futuro contrato;
- limitacoes metodologicas que precisam acompanhar o uso.

`manifest.json` registra o instante da geracao e o SHA-256 exato de
`calibration.json`. O instante operacional fica fora do arquivo calibrado; assim,
os mesmos snapshots e parametros produzem os mesmos bytes e o mesmo hash para o
conteudo de calibracao.

O diretorio final so aparece depois da validacao e escrita completas. Um par
`calibration_id` e `calibration_version` existente nunca e sobrescrito. Mudanca
de fonte, data de corte, metodo, mapeamento ou valor exige nova versao.

## Conteudo historico

Somente anos civis elegiveis em todas as sete metricas sao publicados em
`historical.observations`. Isso impede que uma mesma calibracao compare janelas
desalinhadas.

| Metrica | Medida | Metodo |
|---|---|---|
| `selic_effective` | `effective_return` | composicao dos fatores diarios |
| `selic_target` | `annual_rate_level` | ultimo nivel antes do fim do ano |
| `cdi` | `effective_return` | composicao dos fatores diarios |
| `ipca` | `effective_return` | composicao de janeiro a dezembro |
| `igpm` | `effective_return` | composicao de janeiro a dezembro |
| `usd_brl` | `level_change` | razao entre niveis de fechamento anual |
| `ibovespa` | `level_change` | razao entre niveis `Close` de fechamento anual |

Cada registro traz periodo, valor decimal anual, classificacao da medida,
metodo, cobertura, contagem de observacoes, snapshot, serie e hashes dos arquivos.
As formulas completas estao na
[politica de transformacoes de frequencia](FREQUENCY_TRANSFORMATIONS.md).

Selic e CDI diarios sao comparados pela coincidencia das datas, pelos limites do
ano e pela ausencia de intervalos superiores a sete dias. A cobertura resultante
e `source_consistent`, nao `calendar_verified`: a lista versionada de feriados de
`BR_SETTLEMENT_252` ainda precisa ser incorporada antes de uma classificacao mais
forte.

## Curva e candidatos para o futuro contrato

Os vertices da ETTJ preservam separadamente:

- taxa spot nominal;
- taxa spot real;
- inflacao implicita spot publicada pela ANBIMA;
- inflacao spot recalculada para controle;
- diferenca entre o valor publicado e o recalculado.

O valor publicado nunca e substituido pelo controle. Os forwards anuais sao
calculados nos intervalos `0-252`, `252-504` e seguintes, apenas ate o ultimo
vertice comum das curvas nominal e real. A interpolacao ocorre no logaritmo dos
fatores de desconto e nunca extrapola a curva.

O mapeamento e deliberadamente marcado como `candidate_not_approved`:

- IPCA e o historico candidato para `inflation`;
- inflacao implicita forward e o candidato para sua trajetoria;
- ETTJ prefixada forward e candidata para `discount_rate`;
- Selic, CDI e meta Selic permanecem contexto monetario;
- Ibovespa permanece benchmark parcial, nao `asset_return` da carteira inteira;
- `salary_growth` permanece indisponivel.

O artefato nao inventa os dois ultimos valores nem converte uma curva implicita
em futuro observado.

## Testes

Os testes constroem snapshots completos em diretorio temporario, sem rede:

```bash
python3 -m unittest tests.test_calibration_artifact -v
```

Eles verificam formulas, precisao decimal, ETTJ spot e forward, proveniencia,
reproducibilidade do conteudo, escopo historico, autorizacao experimental,
imutabilidade, rejeicao de fonte adulterada e ausencia de publicacao parcial.
