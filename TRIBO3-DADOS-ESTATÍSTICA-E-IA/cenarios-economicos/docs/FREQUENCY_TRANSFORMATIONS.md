# Politica de transformacoes de frequencia

Versao da politica: `0.1.0`

Status: implementada pelo
[builder do artefato de calibracao](CALIBRATION_ARTIFACT.md). Este documento nao
altera o contrato nem o gerador de cenarios `0.1.0`.

## Objetivo e fronteira

Esta politica define como observacoes preservadas pelos coletores devem ser
convertidas em medidas anuais comparaveis e em pontos de curva. Ela e aplicada
pelo artefato versionado de calibracao e orienta o futuro contrato de trajetorias.

Uma transformacao de frequencia nao transforma uma observacao historica em
previsao. Dados realizados, niveis de mercado e valores implicitos em uma curva
continuam identificados separadamente. Nenhuma saida descrita aqui deve alimentar
automaticamente o gerador atual, que ainda recebe taxas anuais constantes
fornecidas explicitamente na requisicao.

## Convencoes comuns

### Unidade, precisao e classificacao

- A unidade numerica canonica e fracao decimal, nunca percentual. Uma observacao
  `x` em porcentagem e convertida primeiro por `x / 100`.
- O calculo deve usar aritmetica decimal deterministica com pelo menos 34
  algarismos significativos. `float` binario nao deve participar do caminho de
  calculo.
- O valor publicado no artefato deve ter no maximo oito casas decimais,
  com arredondamento explicito `ROUND_HALF_EVEN` somente no fim do calculo.
- A unidade `annual_decimal` nao basta para descrever a semantica. Cada valor
  tambem deve declarar uma das medidas `effective_return`, `annual_rate_level`,
  `spot_rate`, `forward_rate` ou `level_change` e a base `nominal` ou `real`.
- Valores ausentes nunca sao convertidos em zero. Valores nao finitos, datas
  invalidas e observacoes duplicadas para a mesma serie e data sao rejeitados.

### Periodo e disponibilidade

Para historicos, o periodo anual canonico e o ano civil semiaberto:
`[AAAA-01-01, (AAAA+1)-01-01)`. Um ano incompleto nao e extrapolado nem
anualizado. Uma janela movel de 12 meses pode ser calculada como diagnostico,
mas deve ser identificada como tal e nao pode substituir um ano civil.

Series diferentes usadas na mesma calibracao devem compartilhar a mesma data de
corte e apenas periodos completos em comum. A implementacao deve registrar a
data de corte, o identificador do snapshot e o SHA-256 do arquivo-fonte.

Os snapshots atuais do SGS identificam a data de referencia da observacao, mas
nao preservam a historia de publicacoes e revisoes. Portanto, uma serie
reconstruida a partir deles representa a versao conhecida na data da coleta. Ela
nao pode ser chamada de conjunto *point-in-time* nem ser usada em backtest sem
risco de antecipacao ate existir uma politica de vintages.

### Calendario e ausencias

- IPCA e IGP-M exigem exatamente uma observacao para cada um dos 12 meses do ano.
- Selic efetiva e CDI exigem cobertura dos dias uteis aplicaveis. A implementacao
  produtiva deve usar um calendario brasileiro de liquidacao, identificado e
  versionado como `BR_SETTLEMENT_252`.
- Ate esse calendario ser incorporado, uma checagem baseada apenas na
  coincidencia de datas entre series pode produzir `source_consistent`, nunca
  `calendar_verified`.
- Series de nivel aceitam o ultimo valor disponivel anterior ao limite do
  periodo, desde que ele esteja a no maximo sete dias corridos desse limite.
- Nao ha interpolacao temporal nem preenchimento para buracos em historicos
  observados. Um periodo que nao satisfaz a regra de cobertura e marcado como
  incompleto e fica fora da calibracao principal.

## Regras por serie

### Selic efetiva e CDI diarios

As series SGS 11 e 12 sao fluxos diarios em percentual ao dia. Para cada
observacao valida:

```text
r_d = x_d / 100
```

O retorno efetivo do ano e a composicao dos fatores diarios:

```text
R_ano = produto(1 + r_d) - 1
```

O resultado e `annual_decimal`, medida `effective_return`, base `nominal`.
Somar ou tirar a media aritmetica das taxas e incorreto. Tambem e incorreto
elevar novamente o retorno anual a 252 depois de todos os dias do ano ja terem
sido compostos. Cada fator deve ser maior que zero.

Exemplo reduzido, com dois dias de 0,04% e 0,05%:

```text
(1,0004 * 1,0005) - 1 = 0,00090020
```

### Meta Selic

A serie SGS 432 e um estado da meta definida pelo Copom, expresso em percentual
ao ano. Ela nao e o retorno diario realizado da Selic.

Para um ano completo, a medida canonica e o ultimo nivel valido conhecido antes
do fim exclusivo do periodo:

```text
meta_fim_ano = ultima_meta_antes_de((AAAA+1)-01-01) / 100
```

O resultado e `annual_decimal`, medida `annual_rate_level`, base `nominal`.
Metas repetidas ao longo dos dias nao sao compostas e niveis anuais nao sao
promediados. Essa medida serve como estado de politica monetaria e nao substitui
o `effective_return` calculado da serie SGS 11.

Uma simulacao futura pode converter uma meta anual em fator diario por
`(1 + meta)^(1/252)`, mas isso seria uma hipotese modelada separada, nao uma
transformacao de dado realizado, e nao faz parte da saida canonica desta versao.

### IPCA e IGP-M mensais

As series SGS 433 e 189 sao fluxos mensais em percentual ao mes. Para cada mes:

```text
m_i = x_i / 100
inflacao_ano = produto(i=jan..dez, 1 + m_i) - 1
```

O resultado e `annual_decimal`, medida `effective_return`, base `nominal`.
Cada fator mensal deve ser maior que zero. A soma e a media das variacoes
mensais nao preservam composicao e nao devem ser usadas.

Exemplo reduzido, com dois meses de 0,5% e -0,2%:

```text
(1,005 * 0,998) - 1 = 0,00299000
```

O IPCA e a referencia primaria de inflacao do modulo. O IGP-M e uma serie de
sensibilidade ou comparacao: seus valores nao sao combinados com os do IPCA.

### Cambio USD/BRL

A serie SGS 1 e um nivel em reais por dolar dos Estados Unidos, nao uma taxa de
retorno. Para o ano civil:

```text
L_inicio = ultimo nivel valido estritamente anterior a AAAA-01-01
L_fim    = ultimo nivel valido estritamente anterior a (AAAA+1)-01-01
R_ano    = L_fim / L_inicio - 1
```

Os dois niveis precisam ser positivos e respeitar a tolerancia de sete dias
corridos. O resultado e `annual_decimal`, medida `level_change`, base `nominal`.
Um valor positivo significa apreciacao do dolar e depreciacao do real. Cambio e
um fator de risco auxiliar; nao existe mapeamento direto dele para uma premissa
do gerador atual.

Exemplo, para um nivel que passa de 100 para 110:

```text
110 / 100 - 1 = 0,10000000
```

### Ibovespa

O ticker `^BVSP` coletado por Yahoo Finance/yfinance tambem e uma serie de nivel.
Aplica-se a mesma regra de pontos inicial e final e a mesma tolerancia de sete
dias do cambio.

A coluna escolhida e `Close`, nao `Adj Close`. O Ibovespa e definido pela B3
como indice de retorno total, enquanto o eventual ajuste adicional do provedor
nao possui, neste projeto, proveniencia oficial da B3 suficiente para compor a
regra. A saida e `annual_decimal`, medida `level_change`, base `nominal`.

O resultado representa apenas o benchmark da parcela de renda variavel. Ele nao
pode ser copiado para `asset_return`, que representa a carteira inteira, sem uma
politica explicita de alocacao, outros benchmarks, custos e rebalanceamento.
Yahoo Finance e yfinance continuam sendo a cadeia efetiva dessa coleta, nao uma
fonte oficial da B3.

### ETTJ da ANBIMA

A ETTJ nao exige agregacao de observacoes no tempo. Ela exige normalizacao de
unidade e transformacao entre vertices da mesma curva, cuja data de referencia
permanece identificada.

Para uma taxa spot `x(d)` publicada em percentual ao ano, base 252 dias uteis,
no vertice `d`:

```text
z(d)  = x(d) / 100
t(d)  = d / 252
DF(d) = (1 + z(d))^(-d/252)
```

`DF(0) = 1`. Entre dois vertices observados, a interpolacao deve ser linear no
logaritmo dos fatores de desconto, usando os dias uteis como eixo. Taxas nao sao
interpoladas diretamente e nao ha extrapolacao depois do ultimo vertice nao
vazio de cada curva.

A taxa forward anual efetiva entre `d1` e `d2`, com `d2 > d1`, e:

```text
f(d1,d2) = (DF(d1) / DF(d2))^(252 / (d2 - d1)) - 1
```

Os vertices normalizados sao `spot_rate`; os pontos anuais candidatos para uma
trajetoria sao forwards entre `d = 252 * (k - 1)` e `d = 252 * k`, limitados ao
dominio observado da curva. A mesma convencao se aplica a curva nominal
PREFIXADOS e a curva real IPCA.

Em um mesmo vertice, a inflacao implicita spot e recalculada por Fisher para
controle de qualidade do valor publicado pela ANBIMA:

```text
inflacao_spot(d) = (1 + z_nominal(d)) / (1 + z_real(d)) - 1
```

A inflacao implicita forward de cada periodo da trajetoria usa a mesma identidade
sobre as taxas forward correspondentes:

```text
inflacao_forward(d1,d2) = (1 + f_nominal(d1,d2)) / (1 + f_real(d1,d2)) - 1
```

A inflacao implicita spot publicada pela ANBIMA deve ser preservada. O valor
spot recalculado e um controle de qualidade e nao deve sobrescrever
silenciosamente o valor da fonte. Campos vazios na cauda continuam ausentes.

Vertices da ETTJ sao `spot_rate` e taxas derivadas entre vertices sao
`forward_rate`, sempre com base `nominal` ou `real` e status `market_implied`.
Elas expressam precos e expectativas incorporadas na curva da data de
referencia; nao sao valores futuros realizados.

## Mapeamento para as premissas economicas

| Premissa ou fator | Fonte candidata | Regra e limite |
|---|---|---|
| `inflation` | IPCA historico | Composicao mensal; referencia primaria realizada |
| `inflation` | ETTJ implicita | Forward `market_implied`; exige politica de calibracao antes do contrato |
| comparacao de inflacao | IGP-M | Sensibilidade separada; nunca combinado ao IPCA |
| `discount_rate` | ETTJ prefixada | Forward nominal candidato; ainda requer politica de calibracao |
| contexto monetario | Selic efetiva, CDI e meta Selic | Medidas distintas; nenhuma substitui automaticamente `discount_rate` |
| parcela de renda variavel | Ibovespa | Benchmark parcial; nao representa o retorno da carteira inteira |
| risco cambial | USD/BRL | Fator auxiliar, sem mapeamento direto nesta versao |
| `salary_growth` | nenhuma das fontes atuais | Nao pode ser inferido apenas da inflacao |

O artefato versionado preserva esses candidatos sem aprova-los automaticamente.
Pesos, horizonte historico, tratamento de extremos e reconciliacao entre
observado e implicito continuam sendo decisoes de governanca posteriores.

Tambem permanecem fora desta politica as decisoes sobre choques aditivos ou por
prazo e sobre aceitar premissas livres no `POST` ou somente calibracoes
aprovadas por identificador e versao. Essas escolhas mudam o contrato e as
regras de cenario, nao a frequencia dos dados, e serao tratadas nas etapas do
novo contrato e do gerador.

## Contrato implementado pelo artefato de calibracao

Cada medida derivada carrega valor e evidencia suficientes para ser reproduzida.
O formato abaixo representa os campos centrais implementados, mas ainda nao e
aceito pelo gerador:

```json
{
  "metric": "ipca",
  "period_start": "2025-01-01",
  "period_end": "2026-01-01",
  "value": 0.04830000,
  "unit": "annual_decimal",
  "measure": "effective_return",
  "basis": "nominal",
  "status": "observed",
  "method": "compound_monthly_factors",
  "transformation_policy_version": "0.1.0",
  "source_snapshot_id": "identificador-do-snapshot",
  "source_file_sha256": "sha256-do-arquivo",
  "observation_count": 12,
  "coverage": "complete"
}
```

Valores ETTJ futuros usam `status: market_implied`; hipoteses adicionais usam
`status: modeled`. O futuro schema deve impedir que esses estados sejam
confundidos com `observed`.

Uma alteracao em formula, calendario, limites de ausencia, regra de ponto de
corte, arredondamento ou classificacao semantica exige nova versao desta
politica. Mudar apenas texto explicativo, sem alterar resultado ou interpretacao,
pode manter a versao.

## Transformacoes proibidas

- somar ou tirar media de taxas de fluxo para obter o ano;
- calcular retorno pela media dos niveis de cambio ou de indice;
- misturar percentuais com fracoes decimais;
- preencher meses de inflacao ou dias de mercado ausentes com zero;
- anualizar um ano civil parcial e apresenta-lo como observado;
- tratar a meta Selic como retorno realizado;
- tratar um forward da ETTJ como futuro conhecido;
- usar Ibovespa como retorno total da carteira sem modelo de alocacao;
- combinar IPCA e IGP-M na mesma serie de inflacao;
- comparar series com datas de corte ou coberturas incompativeis.

## Referencias metodologicas e de fonte

- BCB, SGS 11, Selic efetiva: <https://dadosabertos.bcb.gov.br/dataset/11-taxa-de-juros---selic>
- BCB, SGS 432, meta Selic: <https://dadosabertos.bcb.gov.br/dataset/432-taxa-de-juros---meta-selic-definida-pelo-copom>
- BCB, SGS 1, cambio USD/BRL: <https://dadosabertos.bcb.gov.br/dataset/1-taxa-de-cambio---livre---dolar-americano-venda---diario>
- BCB, API SGS 12, CDI: <https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados?formato=json&dataInicial=01/01/2025&dataFinal=31/01/2025>
- BCB, API SGS 433, IPCA: <https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados?formato=json&dataInicial=01/01/2025&dataFinal=31/12/2025>
- BCB, API SGS 189, IGP-M: <https://api.bcb.gov.br/dados/serie/bcdata.sgs.189/dados?formato=json&dataInicial=01/01/2025&dataFinal=31/12/2025>
- BCB, servico SGS: <https://dadosabertos.bcb.gov.br/dataset/11-taxa-de-juros---selic/resource/b64e3e6f-3c76-4b2a-9e68-9f0e743aa8ac>
- ANBIMA, pagina da ETTJ: <https://www.anbima.com.br/informacoes/est-termo/CZ.asp>
- ANBIMA, metodologia da ETTJ: <https://www.anbima.com.br/data/files/9A/F4/E3/1F/4805B710B0F024B7882BA2A8/est-termo_metodologia_v2021.pdf>
- B3, Ibovespa: <https://www.b3.com.br/pt_br/market-data-e-indices/indices/indices-amplos/ibovespa.htm>
