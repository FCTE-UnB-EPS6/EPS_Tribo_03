# Fixtures reais e integrações ao vivo

Data: 2026-09-22.

## Separação dos testes

A Fase 8 separa duas finalidades que não devem ser confundidas:

- fixtures reais versionadas exercitam contratos e transformações de maneira
  determinística, offline e adequada para CI;
- testes ao vivo detectam mudanças de transporte ou formato nos provedores, mas
  são opt-in e nunca definem o resultado esperado da suíte reproduzível.

Uma falha ao vivo não altera automaticamente nenhuma fixture. Atualizações
exigem inspeção, nova versão do conjunto e revisão dos hashes e da proveniência.

## Fixtures versionadas

O conjunto `tests/fixtures/real/v1` possui manifesto próprio com ID, versão,
período, instante da coleta, coletor, provedor, tamanho e SHA-256 de cada arquivo.
Os testes recalculam os hashes antes de interpretar os dados.

O conteúdo inclui:

- as doze observações mensais reais do IPCA/SGS em 2024;
- cinco observações reais do extrato `^BVSP` obtido para 2024 por Yahoo
  Finance/yfinance.

A fixture IPCA também verifica a transformação anual composta, cujo resultado
para os registros preservados é `0.04831296`. Isso testa a política implementada
sem consultar a rede.

O arquivo do Bacen recebeu somente um `LF` terminal para a representação no
repositório. O manifesto registra o hash anterior e o hash versionado. A fixture
do Ibovespa é um subconjunto ordenado do extrato coletado, sem recálculo de
preços. Yahoo Finance e yfinance não são fontes oficiais da B3.

Não foi criada fixture ANBIMA: a resposta ao vivo observada durante esta fase
não satisfez o contrato do spike para 2024-12-30. Promover essa resposta como
dado válido ocultaria um possível drift do formulário legado.

## Suíte offline

Executar normalmente:

```bash
python3 -m unittest discover -s tests -v
```

`test_real_data_fixtures.py` não acessa a rede. `test_live_data_sources.py` é
descoberto, mas seus casos são ignorados enquanto o opt-in estiver ausente.

## Integrações ao vivo opcionais

Instalar a dependência de mercado em ambiente isolado:

```bash
python3 -m pip install -r requirements-data.txt
```

Executar Bacen e Ibovespa:

```bash
ESG_RUN_LIVE_DATA_TESTS=1 \
python3 -m unittest tests.test_live_data_sources -v
```

Configurações:

| Variável | Finalidade |
|---|---|
| `ESG_RUN_LIVE_DATA_TESTS=1` | autorização explícita para acessar a rede |
| `ESG_LIVE_DATA_TIMEOUT` | timeout por operação; padrão `30` segundos |
| `ESG_LIVE_ANBIMA_DATE` | data `YYYY-MM-DD` escolhida para o teste experimental |

ANBIMA só é consultada quando as duas variáveis correspondentes são fornecidas:

```bash
ESG_RUN_LIVE_DATA_TESTS=1 \
ESG_LIVE_ANBIMA_DATE=AAAA-MM-DD \
python3 -m unittest tests.test_live_data_sources.LivePublicDataTests.test_anbima_experimental_live_contract -v
```

Os testes gravam apenas em diretórios temporários, validam o snapshot publicado
e não atualizam `tests/fixtures`. O teste do Ibovespa é ignorado se `yfinance`
não estiver instalado.

## Resultado da verificação inicial

As fixtures offline, seus hashes e a composição anual do IPCA passaram. Com o
opt-in habilitado, Bacen e Ibovespa também passaram contra os provedores. O teste
ANBIMA permaneceu sem execução válida por causa do drift observado e continua
classificado como experimental.

## Limites

Fixtures capturam a versão conhecida na data da coleta, não uma base
point-in-time de vintages. Elas não aprovam premissas atuariais, não tornam o
Yahoo fonte oficial da B3 e não substituem monitoramento de disponibilidade ou
contratos formais com provedores.
