# Validação da containerização

Data: 2026-09-13. Núcleo e contrato: `0.1.0`.
Imagens-base: `python:3.12-slim` e `postgres:16`.

## Artefatos

- `Dockerfile`: estágios runtime e test, usuário UID/GID 10001.
- `docker-compose.yml`: PostgreSQL, migração e API, volume persistente e health checks.
- `docker-compose.test.yml`: banco descartável em tmpfs e suíte em container separado.
- `.dockerignore`: seleção explícita dos arquivos enviados ao build.
- `.env.example`: configuração local de porta e senha.
- `scripts/smoke_http.py`: geração/consulta e recuperação de uma execução existente.

## Verificações executadas

Os dois arquivos Compose passaram em `docker compose config --quiet`.
O projeto isolado `tribo3-esg-container-check` foi iniciado com:

```bash
ESG_API_PORT=18083 docker compose -p tribo3-esg-container-check up --build --wait --wait-timeout 180
```

O PostgreSQL ficou saudável, a migração encerrou com código 0 e só então a API
iniciou e ficou saudável. O usuário efetivo da API foi conferido: UID/GID 10001.

A suíte foi executada em outro projeto:

```bash
docker compose -p tribo3-esg-container-tests -f docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from tests
```

**45 testes passaram dentro do container, sem testes ignorados**, com código de
saída 0. O banco de teste foi separado do volume da demonstração e do Passo 1.

O script de demonstração gerou a execução
`64dbcaf5-24ed-4e01-8d67-2d9a206da354`, consultou seu registro e os três cenários.
API, migração e PostgreSQL foram recriados com `up --force-recreate --wait`,
preservando o volume. A mesma execução foi recuperada depois pela porta do host
`127.0.0.1:18083`, com os três cenários intactos.

A rede exclusivamente interna não publicou a porta no Docker deste ambiente.
O Compose final mantém PostgreSQL e migração na rede interna e conecta somente
a API a uma segunda rede de acesso. A publicação continua restrita ao loopback.
O acesso externo ao container foi validado após esse ajuste.

Os projetos e o volume temporário de validação foram removidos ao final. A
execução acima é uma referência da verificação realizada, não um registro que
permanecerá disponível no ambiente do usuário.

## Limites

Containerização e persistência foram verificadas localmente. A implantação no
servidor e a demonstração nesse ambiente continuam pendentes. As tags das
imagens-base e dependências transitivas podem evoluir; este build não pretende
ser reproduzível byte a byte. As premissas continuam sintéticas.
