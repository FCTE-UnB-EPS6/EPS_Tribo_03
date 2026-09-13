# Validação da aplicação e persistência

Data: 2026-09-13. Contrato e núcleo: `0.1.0`.
Ambiente de teste: Python 3.12.14, Psycopg 3.3.5 e PostgreSQL 16 em container
isolado, com banco descartável `esg_test`. Não foi utilizado o banco do Passo 1.

## Execução e resultado

Com `ESG_TEST_DATABASE_URL` configurada para o banco de teste, dentro de
`cenarios-economicos/`:

```bash
python -m unittest discover -s tests -v
```

Resultado: **32 testes passaram, sem testes ignorados**: 18 do núcleo e 14 da
aplicação/persistência. A conexão PostgreSQL foi real; a indisponibilidade foi
simulada em um teste específico para conferir o tratamento seguro do erro.

Foram verificados:

- Geração com UUIDs e horário UTC, consulta por execução e cenário e leitura por uma nova instância do repositório.
- Preservação decimal no JSONB e equivalência entre números com zeros finais e objetos com chaves em outra ordem.
- Novas execuções para a mesma entrada e reutilização de premissas ao variar data-base/horizonte.
- Rejeição de mudança de valor ou fonte sob o mesmo ID/versão, aceitação de nova versão e rejeição de regras alteradas.
- Duas gerações simultâneas com conteúdo igual e duas com conteúdo conflitante.
- Rollback de todas as quatro tabelas após falha injetada no terceiro cenário.
- Rejeição de UPDATE/DELETE e reaplicação da migration sem perda de registros.
- Erros estruturados para UUID inválido, registros/regras inexistentes e armazenamento indisponível.
- Cliente de linha de comando: inicializar, gerar, recuperar execução/cenário e rejeitar UUID inválido.

## Limites e próxima etapa

O sucesso só retorna após commit. O armazenamento implementa imutabilidade
operacional, sem impedir intervenções administrativas de um dono do banco.
Não houve implementação/teste de API HTTP, container do backend ou implantação
no servidor. A próxima etapa é expor esta aplicação pelos endpoints do contrato.
Os valores continuam sintéticos; esta validação não comprova adequação atuarial.
