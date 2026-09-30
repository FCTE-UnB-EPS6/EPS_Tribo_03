# Coleta do Ibovespa por yfinance

Uma fixture real pequena do extrato, mantendo a declaração de fonte não oficial
da B3, e o teste opt-in estão descritos em
[Fixtures reais e integrações ao vivo](PHASE8_REAL_DATA_TESTS.md).

Versao do coletor: `0.1.0`

O coletor obtem o historico diario do ticker `^BVSP` por meio do `yfinance`,
preserva o extrato resultante em CSV e registra um manifesto auditavel. Ele nao
calcula retornos, nao ajusta precos e nao alimenta automaticamente o gerador de
cenarios.

## Proveniencia e limite da fonte

A B3 administra o Ibovespa e publica sua metodologia oficial. Entretanto, os
dados coletados por este componente nao sao obtidos de uma API oficial da B3:

```text
B3 administra o indice
        |
        | nao fornece os dados deste coletor
        v
Yahoo Finance fornece o historico de ^BVSP
        |
        v
yfinance, cliente terceiro, acessa e transforma a resposta
        |
        v
coletor serializa o DataFrame como CSV e gera o manifesto
```

O proprio projeto `yfinance` declara que nao e afiliado, endossado ou aprovado
pelo Yahoo e que usa APIs publicamente disponiveis do Yahoo Finance. Portanto:

- `yfinance` nao e uma fonte oficial da B3;
- Yahoo Finance tambem nao deve ser descrito como fonte oficial da B3;
- o CSV salvo nao contem os bytes brutos de uma resposta da B3;
- o manifesto classifica o arquivo como `provider-extract-not-raw-b3-data`;
- resultados reportaveis devem declarar B3 como administradora do indice e
  Yahoo Finance/yfinance como cadeia efetiva de fornecimento e acesso.

O projeto `yfinance` tambem orienta consultar os termos do Yahoo e descreve o uso
da API como pessoal. Antes de redistribuir snapshots ou usar a coleta fora do
contexto de pesquisa e ensino, os termos aplicaveis precisam ser revisados.

Referencias:

- B3, Ibovespa: <https://www.b3.com.br/pt_br/market-data-e-indices/indices/indices-amplos/ibovespa.htm>
- Metodologia oficial: <https://www.b3.com.br/data/files/9C/15/76/F6/3F6947102255C247AC094EA8/IBOV-Metodologia-pt-br__Novo_.pdf>
- `yfinance`: <https://pypi.org/project/yfinance/>
- API `download`: <https://ranaroussi.github.io/yfinance/reference/api/yfinance.download.html>

## Dependencia isolada

O servidor HTTP de cenarios nao precisa de `yfinance`. Para evitar adicionar a
pilha numerica do pacote a imagem da API, a dependencia fica em arquivo separado:

```bash
python3 -m pip install -r requirements-data.txt
```

A versao esta fixada porque o formato e os valores padrao de `download()` podem
mudar entre versoes. O manifesto registra a versao efetivamente carregada.

## Execucao

Dentro de `cenarios-economicos/`:

```bash
python3 scripts/collect_ibovespa.py \
  --start 2015-01-01 \
  --end 2026-09-17 \
  --output data/raw/ibovespa
```

O inicio e inclusivo. Como o fim de `yfinance.download()` e exclusivo, o coletor
envia ao provedor o dia seguinte ao `--end`; o manifesto registra tanto o periodo
solicitado quanto os parametros efetivos da chamada.

O coletor fixa explicitamente:

- intervalo diario;
- `auto_adjust=False`, `back_adjust=False` e `repair=False`;
- `rounding=False`;
- execucao sem threads e sem barra de progresso;
- exclusao das linhas inteiramente vazias feita pelo proprio `yfinance`;
- colunas `Open`, `High`, `Low`, `Close`, `Adj Close` e `Volume`.

Uma execucao bem-sucedida cria:

```text
data/raw/ibovespa/ibovespa-yahoo-AAAAMMDDTHHMMSSZ-identificador/
|-- manifest.json
`-- provider/
    `-- ibovespa_AAAA-MM-DD_AAAA-MM-DD.csv
```

O CSV preserva o extrato produzido pelo cliente depois de ordenar as colunas e
formatar datas em ISO-8601. O SHA-256 se refere exatamente aos bytes desse CSV.
O diretorio so e publicado depois da validacao integral do arquivo. A saida
padrao esta ignorada pelo Git para reduzir o risco de redistribuir os dados sem
uma revisao previa dos termos aplicaveis.

## Testes

Os testes offline nao acessam o Yahoo Finance:

```bash
python3 -m unittest tests.test_ibovespa_collector -v
```

Eles cobrem periodo inclusivo, parametros que evitam ajuste implicito, validacao
de schema e numeros, preservacao do CSV, manifesto, hash e atomicidade. Antes de
publicar uma versao do coletor, execute tambem uma consulta curta real.

## Transformacao posterior

Esta implementacao preserva niveis observados. A
[politica de transformacoes de frequencia](FREQUENCY_TRANSFORMATIONS.md) define o
uso de `Close`, os pontos inicial e final, a tolerancia para ausencias e o
calculo da variacao anual. O coletor continua sem interpretar `Close` como
retorno nem preencher dias sem negociacao; a transformacao e executada somente
pelo [artefato de calibracao](CALIBRATION_ARTIFACT.md).
