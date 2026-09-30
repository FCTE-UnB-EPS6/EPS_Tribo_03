# Integração do contrato de trajetória 0.2.0

Data: 2026-09-22.

## Escopo entregue

A Fase 7 conecta o contrato criado na Fase 6 às camadas existentes sem remover o
contrato `0.1.0`:

- despacho explícito por `contract_version` no gerador;
- geração determinística dos três cenários por período;
- catálogo de regras separado para a trajetória demonstrativa;
- aplicação comum para IDs, horário UTC, commit e consultas;
- OpenAPI com requisições e respostas `oneOf` para as duas versões;
- armazenamento imutável de trajetórias em `trajectory_set`;
- vínculo da execução com exatamente uma entrada: premissas `0.1.0` ou
  trajetória `0.2.0`;
- conflito e rollback para reutilização de identidade/versionamento com conteúdo
  diferente.

O gerador continua puro e não consulta artefatos, rede ou banco. O
`request_snapshot` guarda a calibração e a proveniência completas. Os valores de
saída de cada cenário permanecem escalares por período para compatibilidade com
os consumidores do formato `values`.

## Regra de cenário

Para cada variável e período:

```text
taxa_do_cenario = valor_da_trajetoria + ajuste_do_ruleset
```

Base exige ajuste zero. Adverso e Favorável usam o ajuste aditivo constante
declarado no ruleset `demo-trajectory-rules@0.1.0`. O cálculo usa escala inteira
de oito casas decimais, rejeita resultado menor ou igual a `-1` e não altera a
entrada.

## Migração

`002_trajectory_contract.sql` é aplicada depois da migração inicial. Ela mantém
as tabelas existentes, torna a referência a `assumption_set` opcional, adiciona
a referência alternativa a `trajectory_set` e restringe cada execução ao tipo
correto de entrada. A nova tabela recebe a mesma proteção contra `UPDATE` e
`DELETE` das tabelas originais.

## Validação local

Executado localmente sem dependências opcionais:

```bash
python3 -m unittest discover -s tests
python3 -m unittest discover -s spikes/anbima_ettj/tests -v
python3 -m compileall -q app tests scripts spikes/anbima_ettj
git diff --check
```

Os testes de núcleo, contrato, geração, schemas, coletores e calibração são
offline. Essa execução encontrou 88 testes, com 59 aprovados e 29 condicionais
ignorados por ausência das dependências HTTP/PostgreSQL no host.

A suíte completa também foi executada em Docker com FastAPI, HTTPX, Psycopg e
PostgreSQL 16 reais. Os 88 testes passaram sem ignorados, incluindo
OpenAPI, geração `0.2.0` por HTTP, migração idempotente, roundtrip da trajetória,
imutabilidade e conflito de versão. O ambiente temporário foi removido depois da
execução.

## Limites

As regras permanecem demonstrativas e não representam calibração ou aprovação
atuarial. A API recebe a trajetória pronta e verificável, mas não abre o arquivo
de calibração indicado pelo hash. Fixtures reais versionadas e integrações ao
vivo opcionais pertencem à Fase 8.
