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

## Investigação adicional (30/set/2026) — o padrão do vazio, e uma alternativa testada

Reproduzido o problema ao vivo com `curl` direto no endpoint `CZ-down.asp`,
variando a data de referência sistematicamente (não só o dia único de
2024-12-30 já registrado acima):

- **Funcionou** (XML completo, 8,2 KB): 15, 23, 25, 28, 29 e 30 de
  setembro de 2026 (dias úteis).
- **Vazio** (`<CURVAZERO></CURVAZERO>`, 27 bytes): toda a semana de
  08 a 12/set/2026 (dias úteis, sem feriado nacional nessa janela),
  20/set/2026 (domingo, esperado), e todas as datas de anos anteriores
  testadas (30/12/2024, 02/01/2025, 30/06/2025, 30/09/2025, 30/12/2025,
  30/06/2024, 29/12/2023).

**Conclusão**: não é um problema pontual de uma data isolada, nem um erro
de formato do lado do cliente — é uma limitação de profundidade
histórica do próprio formulário legado da ANBIMA (só serve uma janela
recente, e mesmo dentro dela houve um buraco de uma semana inteira sem
explicação de feriado). Isso confirma a suspeita original do spike e
fecha a investigação: **este endpoint não deve ser usado pra série
histórica**, só, na melhor das hipóteses, pra curva do dia mais recente.

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

### Atualização (30/set/2026) — a auditoria acima está desatualizada

Reinstalei `pyettj==0.4.2` do PyPI hoje e inspecionei o código de fato: a
função pública se chama `get_ettj` (não `get_ettj_anbima`), e ela **não
consulta o endpoint da ANBIMA**. `pyettj._montar_url` monta uma URL para
`b3.com.br/pesquisapregao/download` (arquivo `TS{aammdd}.ex_`) — é a curva
de futuros de DI da B3, uma fonte diferente da ETTJ ajustada por Svensson
da ANBIMA que este spike investigou. Não sei se a auditoria original viu
uma versão diferente do pacote ou se houve engano; de qualquer forma, o
código publicado agora é outro.

Testei `get_ettj()` ao vivo, com `cache=False`, nas quatro datas mais
relevantes desta investigação — incluindo as duas que retornaram vazio no
endpoint da ANBIMA:

| Data | ANBIMA (`CZ-down.asp`) | `pyettj.get_ettj()` (B3) |
| --- | --- | --- |
| 2026-09-29 | OK | OK (280 linhas) |
| 2026-09-10 | **vazio** | OK (278 linhas) |
| 2025-12-30 | **vazio** | OK (279 linhas) |
| 2024-12-30 | **vazio** | OK (254 linhas) |

`pyettj` respondeu nas quatro, incluindo as três que a ANBIMA não serviu.
Não é a mesma curva (DI x Pré-fixado da B3, curva `PRE`, mais a `DIC` para
DI x IPCA — via futuros negociados, não via ajuste Svensson da ANBIMA),
mas cobre o mesmo propósito do plano de dados reais: ancorar o cenário
determinístico numa curva a termo real do mercado brasileiro. Como
subproduto, isso também resolve a limitação de profundidade histórica
registrada acima, porque a B3 aparentemente mantém o arquivo diário por
mais tempo que o formulário legado da ANBIMA.

**Recomendação para o Carlos e o Paulo, com a decisão em aberto pra
vocês**: dado que o pacote não passa mais pelo endpoint problemático,
vale reavaliar a objeção original (dependências extras) — `pandas` já
entra no grupo `requirements-data.txt` via `yfinance`, então o custo
marginal de adicionar `pyettj` é menor do que quando a auditoria foi
escrita. Se decidirem seguir esse caminho, ainda vale envolver o pacote
num coletor auditável próprio (snapshot com hash, sem cache do pyettj em
produção) em vez de chamar `get_ettj()` direto — pelos mesmos motivos que
já levaram ao desenho de `bacen.py`/`ibovespa.py`.

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
