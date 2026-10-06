# Evidências: Passo 7 / SL-07

> Toda afirmação do PR ("os testes passam", "o relatório foi gerado") aponta para uma linha desta tabela. Cada evidência traz o comando, o resultado e o **commit** em que foi produzida (CTR-004, GOV-005).
> **CI:** o `EPS_Tribo_03` ainda não tem CI (pendente com a líder da tribo). Até lá, a evidência é a execução local reproduzível, com comando e saída.

## Etapa 1: Lee-Carter (Passo 6)

| # | O que prova | Comando (de dentro de `explicabilidade-model-risk/`) | Resultado | Commit |
|---|---|---|---|---|
| EVD-1 | Testes unitários e de integração passam | `python -m pytest -v` | `PREENCHER: ex. 24 passed in X s` | `PREENCHER SHA` |
| EVD-2 | Script gera o relatório APROVADO a partir do contrato real do Passo 6 | `python scripts/explicar_lee_carter.py; echo "código de saída: $?"` | `PREENCHER: status APROVADO, código 0` | `PREENCHER SHA` |
| EVD-3 | Relatório segue o contrato v1.0.0 | validação automática dentro do script (`validar_relatorio`) e testes `test_schema_*` | `PREENCHER` | `PREENCHER SHA` |
| EVD-4 | Artefatos versionados | `docs/lee_carter/` (JSON + 6 PNG) | arquivos no commit | `PREENCHER SHA` |

### Saída completa do pytest (EVD-1)

```text
PREENCHER: colar aqui a saída completa de `python -m pytest -v`
```

### Saída do script (EVD-2)

```text
PREENCHER: colar aqui a saída de `python scripts/explicar_lee_carter.py`
```

## Observações

- O `rodada.commit` gravado no JSON é o commit do **código** no momento da rodada. Por isso a ordem é: (1) commitar o código, (2) rodar o script, (3) commitar as saídas e este arquivo. O JSON deve mostrar `commit_com_alteracoes_locais: false`.
- **Testes com modelo de brinquedo** (fixture `params_brinquedo`) verificam a lógica, mas **não** comprovam a integração. A integração é comprovada pelos testes `test_integracao_*` e pela EVD-2, que usam o contrato real.
