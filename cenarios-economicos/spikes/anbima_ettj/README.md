# Spike ANBIMA ETTJ

## Verificação ao vivo da Fase 8

Em 2026-09-22, uma consulta para a data de referência 2024-12-30 retornou XML
que não continha o elemento `DATA_REFERENCIA` esperado pelo contrato observado.
Nenhuma fixture real foi criada a partir dessa resposta. O comportamento pode
representar indisponibilidade histórica, resposta de erro ou mudança do
formulário legado e precisa ser investigado antes de promover o spike.

O teste ao vivo permanece opcional e exige `ESG_RUN_LIVE_DATA_TESTS=1` e
`ESG_LIVE_ANBIMA_DATE`. Consulte
[Fixtures reais e integrações ao vivo](../../docs/PHASE8_REAL_DATA_TESTS.md).

Este spike valida, de forma isolada, se a Estrutura a Termo das Taxas de Juros
da ANBIMA pode ser coletada com rastreabilidade suficiente para o Plano de Dados
Reais. Ele nao integra a fonte ao gerador, nao normaliza taxas e nao altera as
premissas economicas da aplicacao.

## Resultado

A coleta e tecnicamente viavel por meio do formulario da pagina oficial. O
download observado usa `POST` em `CZ-down.asp`, com os campos `Idioma=PT`,
`Dt_Ref=DD/MM/AAAA` e `saida=xml`.

O XML observado contem:

- a data de referencia;
- seis parametros de Svensson para as curvas PREFIXADOS e IPCA;
- vertices da ETTJ IPCA, ETTJ prefixada e inflacao implicita;
- taxas prefixadas nos vertices da Circular 3316;
- erros de ajuste por titulo publico.

Os parametros do XML possuem mais casas decimais que a tabela HTML. Os vertices
usam dias uteis e separador de milhar brasileiro, como `1.008`. As taxas da
tabela ETTJ sao publicadas como percentual anual na base de 252 dias uteis.
Campos de taxa podem vir vazios no fim de uma curva; isso foi observado na fonte
e nao e tratado como zero.

O endpoint e uma interface web ASP legada, nao uma API publica versionada. Esse
fato deve ser tratado como risco operacional antes da promocao para producao. O
servidor entrega o XML com `Content-Type: application/download`, portanto o
formato deve ser validado pelo conteudo, e nao apenas pelo cabecalho HTTP.

## Decisao sobre `pyettj`

A versao 0.4.2 foi auditada no artefato publicado no PyPI. Ela contem
`get_ettj_anbima` e consulta o mesmo endpoint XML. O pacote e util para analise
interativa, mas nao foi incorporado neste spike porque a funcao transforma a
resposta diretamente em `DataFrame`, nao preserva os bytes recebidos, nao gera
manifesto ou hash e nao define timeout HTTP. O pacote tambem adicionaria pandas,
NumPy, SciPy, matplotlib e outras dependencias a uma coleta que pode ser
comprovada apenas com a biblioteca padrao.

Essa decisao e limitada ao coletor auditavel. Ela nao descarta o uso futuro das
funcoes matematicas do pacote depois de uma avaliacao separada.

## Executar

A data precisa ser explicita e corresponder a um dia publicado pela ANBIMA:

```bash
cd cenarios-economicos
python3 -m spikes.anbima_ettj.probe \
  --date 2026-09-16 \
  --output /tmp/anbima-ettj-spike
```

Cada execucao bem-sucedida cria um diretorio imutavel por convencao, contendo:

```text
anbima-ettj-AAAA-MM-DD-COLETA-IDENTIFICADOR/
|-- manifest.json
`-- raw/
    `-- ettj_AAAA-MM-DD.xml
```

O manifesto registra fonte, formulario, instante UTC, contagens observadas,
tamanho e SHA-256. A publicacao e atomica: XML vazio, malformado, de outra data
ou sem as duas curvas esperadas nao deixa snapshot parcial.

## Testes

Os testes sao offline e usam uma amostra minima representativa do contrato:

```bash
cd cenarios-economicos
python3 -m unittest discover \
  -s spikes/anbima_ettj/tests \
  -p 'test_*.py' -v
```

## Pendencias antes da implementacao produtiva

- confirmar formalmente os termos de uso e a politica de redistribuicao dos
  arquivos brutos;
- observar amostras de um periodo historico maior e registrar mudancas de schema;
- definir calendario, repeticao e politica para dias sem publicacao;
- definir retentativas, limite de requisicoes e monitoramento de indisponibilidade;
- promover a coleta experimental a integracao produtiva; a unidade, precisao e
  conversao ja estao implementadas no
  [artefato de calibracao](../../docs/CALIBRATION_ARTIFACT.md), com autorizacao
  explicita e sem transformar vazio em zero;
- definir na calibracao como os forwards `market_implied` da ETTJ ancoram a
  trajetoria modelada sem chama-los de dados futuros realizados.

## Fontes consultadas

- Pagina oficial: <https://www.anbima.com.br/informacoes/est-termo/CZ.asp>
- Metodologia da ETTJ: <https://www.anbima.com.br/data/files/9A/F4/E3/1F/4805B710B0F024B7882BA2A8/est-termo_metodologia_v2021.pdf>
- Pacote avaliado: <https://pypi.org/project/pyettj/>
