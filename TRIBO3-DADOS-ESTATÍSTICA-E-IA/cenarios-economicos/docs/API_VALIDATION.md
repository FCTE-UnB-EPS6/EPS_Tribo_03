# Validação da API HTTP

Data: 2026-09-13. Contrato e núcleo: `0.1.0`.
Ambiente: Python 3.12.14, FastAPI 0.141.1, Uvicorn 0.52.4, HTTPX 0.28.1,
Psycopg 3.3.5 e PostgreSQL 16 em container temporário dedicado `esg_test`.

## Suíte executada

Com `requirements-dev.txt` instalado e `ESG_TEST_DATABASE_URL` apontando para o
banco descartável, dentro de `cenarios-economicos/`:

```bash
python -m unittest discover -s tests -v
```

**45 testes passaram, sem testes ignorados**: 18 do núcleo, 14 da persistência,
8 do contrato HTTP e 5 de HTTP com PostgreSQL real.

Cobertura acrescentada:

- Parsing/serialização decimal exatos e geração 201 com `Location`.
- Consultas de execução/cenário iguais ao conteúdo persistido.
- Repetição de POST criando outra execução e conflito retornando 409.
- JSON malformado, UTF-8 inválido, NaN, infinito e chaves duplicadas retornando 400.
- Content-Type incorreto retornando 415 e campos inválidos retornando 422 sem gravação.
- UUID inválido, recurso/regra inexistente, falhas de banco e exceções internas.
- Health check independente do banco, códigos de rota/método e OpenAPI/documentação.

Erros de infraestrutura são simulados nos testes específicos de indisponibilidade;
a geração e as consultas dos testes de integração usam transações PostgreSQL reais.
O ambiente emitiu avisos de depreciação do TestClient/HTTPX e BlockingPortal em
dependências; eles não impediram a execução. Revisar o cliente de testes em uma
futura atualização dessas dependências.

## Verificação por HTTP real

Além do TestClient, foi iniciado `uvicorn app.main:create_app --factory` em um
socket temporário ligado a `127.0.0.1`. Um cliente HTTP da biblioteca padrão
verificou health 200, geração 201 com a entrada demonstrativa e consultas 200
por execução e cenário. O conteúdo consultado coincidiu com o resultado da geração.
O processo Uvicorn foi encerrado após a verificação.

## Limites

A API foi validada localmente. Não houve implantação no servidor, containerização
do backend, autenticação ou calibração atuarial. As premissas continuam sintéticas
e os alinhamentos entre consumidores permanecem pendentes.
