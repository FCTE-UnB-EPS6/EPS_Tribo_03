# Cenários econômicos — API, geração e persistência

Núcleo econômico `0.1.0` em Python 3.10 ou superior, com camada de aplicação
e persistência PostgreSQL. O núcleo usa apenas a biblioteca padrão; a API usa
FastAPI/Uvicorn e a persistência usa Psycopg, listados em `requirements.txt`. Gera Base, Adverso e Favorável a partir das premissas
e regras versionadas. As configurações fornecidas são exclusivamente sintéticas.

## Executar com Docker Compose

Na raiz do repositório:

```bash
cd cenarios-economicos
docker compose up --build --wait
```

A API ficará em `http://127.0.0.1:8000` e a documentação em
`http://127.0.0.1:8000/docs`. O Compose inicia PostgreSQL, espera sua disponibilidade,
executa `python -m app init-db` no serviço `migrate` e só então inicia a API.
Uma falha na migração impede a subida da API.

O [Dockerfile](Dockerfile) tem estágio `runtime` e estágio `test`. O backend usa
UID/GID 10001, filesystem somente leitura e `/tmp` temporário. O arquivo
[.dockerignore](.dockerignore) limita o conteúdo enviado ao build; `.env` e arquivos
locais não entram na imagem. O serviço PostgreSQL não publica portas e está na
rede interna do projeto. A API participa também de uma rede de acesso e publica
somente no loopback do host.

Para alterar a porta ou a senha da demonstração, copie [.env.example](.env.example)
para `.env` e edite antes da primeira subida. Os padrões são porta 8000 e senha
`esg_local_demo`, exclusivos para demonstração local. O banco e o usuário são
`esg`. A senha é passada por `PGPASSWORD`, sem interpolação em URI. Mudar o valor
no `.env` não altera a senha de um banco já inicializado.

Demonstre o fluxo completo sem instalar Python no host:

```bash
docker compose exec -T economic-scenario-api python scripts/smoke_http.py
```

O comando gera uma execução, consulta o resultado e os três cenários, e imprime
seu `run_id`. Para consultar novamente, inclusive após reiniciar os containers:

```bash
docker compose exec -T economic-scenario-api python scripts/smoke_http.py --run-id UUID_DA_EXECUCAO
```

Para acompanhar ou parar o ambiente:

```bash
docker compose ps
docker compose logs economic-scenario-api migrate
docker compose down
```

O volume `esg_pgdata`, prefixado pelo nome do projeto Compose, preserva os dados
entre recriações e `down`. O comando `down --volumes` também apaga esse volume.
O banco deste componente é separado do ambiente de dados do Passo 1.

## Testar dentro dos containers

O arquivo [docker-compose.test.yml](docker-compose.test.yml) é independente do
Compose de demonstração. Ele cria outro PostgreSQL, com banco `esg_test` em
`tmpfs`, sem portas publicadas ou volume persistente.

```bash
docker compose -p esg-tests -f docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from tests
docker compose -p esg-tests -f docker-compose.test.yml down
```

O primeiro comando retorna o código de saída da suíte. Os testes não acessam o
volume da demonstração. O estágio de testes instala `requirements-dev.txt`;
a imagem de execução não contém a suíte nem o cliente HTTP de testes.

## Executar os testes

Na raiz do repositório:

```bash
cd cenarios-economicos
python -m unittest discover -s tests -p test_scenario_generator.py -v
```

## Gerar conteúdo econômico localmente

Dentro de `cenarios-economicos/`:

```python
from pathlib import Path
from app.services.scenario_generator import (
    generate_scenarios, loads_decimal, dumps_decimal,
)

request = loads_decimal(Path("examples/generate.demo.v0.1.0.json").read_text())
rules = loads_decimal(Path("config/scenario_rules.demo.v0.1.0.json").read_text())
result = generate_scenarios(request, rules)
print(dumps_decimal(result))
```

Use `loads_decimal` para preservar os números fracionários do JSON. Na chamada
Python direta, taxas e ajustes aceitam `Decimal` ou `int`, nunca `float`, strings
numéricas ou booleanos. O cálculo usa inteiros na escala de oito casas decimais,
sem depender da precisão global de `Decimal`. `dumps_decimal` produz números JSON
exatos, sem conversão para ponto flutuante binário.

## Saída e limites da implementação

`generate_scenarios(request, rules)` é uma função sem efeitos externos. Retorna:

- versões do contrato e do gerador;
- cópias independentes da entrada e das regras;
- três cenários ordenados, com versões e trajetórias anuais.

A mesma entrada e configuração produz o mesmo conteúdo. Todas as entradas,
configurações e taxas ajustadas são validadas antes da entrega do resultado.
Erros lançam `ScenarioError`, com `code`, `field`, `message` e `as_dict()`.
As fontes são preservadas como metadados; nenhum arquivo de referência ou URL
é acessado pelo núcleo.

Esta função continua independente do banco. A camada `ScenarioApplication`
acrescenta `run_id`, `scenario_id`, `created_at` em UTC e `status`, seleciona regras
por ID/versão no catálogo local e só retorna sucesso após o commit no PostgreSQL.

## Instalação e demonstração com PostgreSQL

Dentro de `cenarios-economicos/`, em um ambiente virtual Python:

```bash
python -m pip install -r requirements.txt
export ESG_DATABASE_URL='postgresql://usuario:senha@localhost:5432/banco'
python -m app init-db
python -m app generate examples/generate.demo.v0.1.0.json
python -m app get-run UUID_DA_EXECUCAO
python -m app get-scenario UUID_DO_CENARIO
```

Substitua a conexão e os UUIDs pelos valores do ambiente e da geração. A conexão
é lida somente de `ESG_DATABASE_URL`. `init-db` aplica explicitamente a migration
idempotente em [migrations/001_execution_store.sql](migrations/001_execution_store.sql).
O banco de destino deve existir; a migration cria o schema `economic_scenarios`.
Não altera as tabelas do Passo 1. A instalação do schema exige permissões de DDL;
a aplicação usa SELECT e INSERT nas quatro tabelas, além de USAGE no schema.

O catálogo padrão carrega `config/scenario_rules.*.json`. Para usar outra pasta:
`python -m app --rules-dir CAMINHO generate ARQUIVO.json`. IDs recebidos não são
interpretados como caminhos e as consultas não dependem da disponibilidade do
arquivo original de regras.

Cada geração salva premissas, regras, execução e três cenários em uma transação.
Repetir a entrada cria outra execução; mudar data-base/horizonte é permitido sob a
mesma versão de premissas. Alterar valores ou fontes sob o mesmo ID/versão gera
`ASSUMPTION_VERSION_CONFLICT`. Alterar regras já registradas gera `INVALID_RULESET`.
Esses conflitos são verificados também sob concorrência. As tabelas rejeitam
UPDATE e DELETE por triggers; o mecanismo não substitui permissões e backups do
banco contra operações administrativas.

O conteúdo JSONB preserva números decimais exatos; ordem de chaves e zeros finais
podem mudar na consulta, sem alterar o valor. A API HTTP e a containerização estão implementadas e validadas localmente.
A implantação no servidor está adiada e fora da etapa atual, conforme decisão do grupo.

## Executar a API HTTP

Após instalar `requirements.txt`, configurar `ESG_DATABASE_URL` e executar
`python -m app init-db`, inicie dentro de `cenarios-economicos/`:

```bash
python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

O catálogo usa a pasta `config/` do componente. `ESG_RULES_DIR` permite selecionar
outra pasta no início do processo. A API não aplica migrations automaticamente.

| Método | Caminho | Resultado |
|---|---|---|
| GET | `/health` | HTTP 200 se o processo responde; não verifica o banco |
| POST | `/api/v1/scenarios/generate` | HTTP 201 após commit, com header `Location` |
| GET | `/api/v1/runs/{run_id}` | Execução completa e snapshots |
| GET | `/api/v1/scenarios/{scenario_id}` | Cenário e seu `run_id` |
| GET | `/docs` | Documentação interativa |
| GET | `/openapi.json` | Especificação OpenAPI |

Exemplo de geração, em outro terminal dentro da mesma pasta:

```bash
curl -i http://127.0.0.1:8000/api/v1/scenarios/generate \
  -H 'Content-Type: application/json' \
  --data-binary @examples/generate.demo.v0.1.0.json
```

Use o caminho do header `Location` para recuperar o registro:

```bash
curl http://127.0.0.1:8000/api/v1/runs/UUID_DA_EXECUCAO
```

Taxas são lidas e escritas sem conversão intermediária para `float`. As operações
síncronas de geração e banco executam fora do event loop. Erros seguem o envelope
`error.code/field/message` do contrato, incluindo conflito 409 e indisponibilidade
503. JSON inválido retorna 400; Content-Type diferente de `application/json`
retorna 415. O JSON enviado deve usar UTF-8.

A demonstração usa acesso local. Autenticação e publicação externa não fazem
parte desta entrega; o comando acima mantém o serviço ligado a `127.0.0.1`.

## Testes de integração

Use **um banco descartável dedicado cujo nome termine em `_test`**. Os testes
limpam as quatro tabelas do schema `economic_scenarios` entre casos.

```bash
python -m pip install -r requirements-dev.txt
export ESG_TEST_DATABASE_URL='postgresql://usuario:senha@localhost:5432/esg_test'
python -m unittest discover -s tests -v
```

Com a variável definida, falha de conexão faz a suíte falhar. Sem ela, os testes
com PostgreSQL são explicitamente ignorados; os testes do núcleo e do contrato
HTTP (quando as dependências estão instaladas) executam.
A suíte de integração cobre ida e volta decimal, consultas por novos clientes,
rollback após falha no terceiro cenário, conflitos e concorrência, imutabilidade,
migration reaplicável e demonstração pelo cliente de linha de comando.

## Documentação e verificação

- [Contrato econômico](docs/SCENARIO_CONTRACT.md).
- [Premissas, regras e gabarito](docs/ASSUMPTIONS.md).
- [Registro de validação do núcleo](docs/CORE_VALIDATION.md).
- [Registro de validação da persistência](docs/PERSISTENCE_VALIDATION.md).
- [Registro de validação da API](docs/API_VALIDATION.md).
- [Registro de validação dos containers](docs/CONTAINER_VALIDATION.md).

Os testes cobrem o gabarito dos três cenários, períodos, reprodução, isolamento
dos snapshots, ausência de opcionais, precisão e serialização decimal, datas
bissextas, limites do horizonte, entradas e configurações inválidas e rejeição
de resultados fora do domínio. Essa verificação é técnica; não valida premissas
para utilização atuarial.
