# Evidências: Passo 7 / SL-07

> Toda afirmação do PR ("os testes passam", "o relatório foi gerado") aponta para uma linha desta tabela. Cada evidência traz o comando, o resultado e o **commit** em que foi produzida (CTR-004, GOV-005).
> **CI:** o `EPS_Tribo_03` ainda não tem CI (pendente com a líder da tribo). Até lá, a evidência é a execução local reproduzível, com comando e saída.

## Etapa 1: Lee-Carter (Passo 6)

Rodada `20261006T125901Z`, executada por Leticia Arisa Kobayashi Higa em 06/10/2026 (Linux, Python 3.12.3), no commit `c1b08de`.

| # | O que prova | Comando (de dentro de `explicabilidade-model-risk/`) | Resultado | Commit |
|---|---|---|---|---|
| EVD-1 | Testes unitários e de integração passam | `python -m pytest -v` | 40 passed in 14.74s | `c1b08de` |
| EVD-2 | Script gera o relatório APROVADO a partir do contrato real do Passo 6 | bash: `python scripts/explicar_lee_carter.py; echo "código de saída: $?"` · PowerShell: `python scripts/explicar_lee_carter.py; echo "código de saída: $LASTEXITCODE"` | status APROVADO, código de saída 0, `commit_com_alteracoes_locais: false` (1,07 s) | `c1b08de` |
| EVD-3 | Relatório segue o contrato v1.0.0 | validação automática dentro do script (`validar_relatorio`) e testes `test_schema_*` | relatório validado contra `schemas/relatorio_explicabilidade.schema.json` v1.0.0 (o script grava só se a validação passar); `test_schema_*` passaram | `c1b08de` |
| EVD-4 | Artefatos versionados | `docs/lee_carter/` (JSON + 6 PNG) | JSON + 6 PNG gerados na rodada `20261006T125901Z` | código: `c1b08de`; artefatos: commit seguinte, que os adiciona |

### Saída completa do pytest (EVD-1)

```text
platform linux -- Python 3.12.3, pytest-9.1.1, pluggy-1.6.0
rootdir: .../TRIBO3-DADOS-ESTATÍSTICA-E-IA/explicabilidade-model-risk
collected 40 items

tests/test_explicar_lee_carter.py::test_qx_historico_usa_kappa_do_ano PASSED
tests/test_explicar_lee_carter.py::test_qx_futuro_usa_drift PASSED
tests/test_explicar_lee_carter.py::test_qx_igual_a_formula_do_passo6 PASSED
tests/test_explicar_lee_carter.py::test_qx_historico_difere_do_passo6_de_proposito PASSED
tests/test_explicar_lee_carter.py::test_ano_antes_da_serie_e_rejeitado PASSED
tests/test_explicar_lee_carter.py::test_idade_fora_do_modelo_e_rejeitada PASSED
tests/test_explicar_lee_carter.py::test_anos_analisados_inclui_horizonte PASSED
tests/test_explicar_lee_carter.py::test_brinquedo_passa_em_todas_as_checagens PASSED
tests/test_explicar_lee_carter.py::test_drift_positivo_bloqueia PASSED
tests/test_explicar_lee_carter.py::test_q_caindo_com_idade_adulta_bloqueia PASSED
tests/test_explicar_lee_carter.py::test_queda_abaixo_da_idade_minima_nao_bloqueia_e_vira_alerta PASSED
tests/test_explicar_lee_carter.py::test_valor_nao_finito_bloqueia PASSED
tests/test_explicar_lee_carter.py::test_estrutura_inconsistente_bloqueia_sem_quebrar PASSED
tests/test_explicar_lee_carter.py::test_variancia_explicada_invalida_gera_bloqueado_sem_quebrar[1.5] PASSED
tests/test_explicar_lee_carter.py::test_variancia_explicada_invalida_gera_bloqueado_sem_quebrar[-0.1] PASSED
tests/test_explicar_lee_carter.py::test_variancia_explicada_invalida_gera_bloqueado_sem_quebrar[nan] PASSED
tests/test_explicar_lee_carter.py::test_bloqueado_com_nan_grava_json_valido[alpha_x-0] PASSED
tests/test_explicar_lee_carter.py::test_bloqueado_com_nan_grava_json_valido[kappa_t-2] PASSED
tests/test_explicar_lee_carter.py::test_bloqueado_com_nan_grava_json_valido[drift-None] PASSED
tests/test_explicar_lee_carter.py::test_schema_rejeita_aprovado_com_parametro_null PASSED
tests/test_explicar_lee_carter.py::test_entrada_vazia_ou_curta_gera_bloqueado_sem_quebrar[entrada0] PASSED
tests/test_explicar_lee_carter.py::test_entrada_vazia_ou_curta_gera_bloqueado_sem_quebrar[entrada1] PASSED
tests/test_explicar_lee_carter.py::test_entrada_vazia_ou_curta_gera_bloqueado_sem_quebrar[entrada2] PASSED
tests/test_explicar_lee_carter.py::test_anos_com_lacuna_bloqueiam PASSED
tests/test_explicar_lee_carter.py::test_beta_negativo_vira_alerta PASSED
tests/test_explicar_lee_carter.py::test_salto_de_kappa_e_detectado PASSED
tests/test_explicar_lee_carter.py::test_q_no_limite_de_corte_vira_alerta PASSED
tests/test_explicar_lee_carter.py::test_sem_salto_sem_alerta PASSED
tests/test_explicar_lee_carter.py::test_ale_idade_crescente_e_ano_decrescente PASSED
tests/test_explicar_lee_carter.py::test_shap_soma_reconstroi_q PASSED
tests/test_explicar_lee_carter.py::test_shap_igual_a_biblioteca_shap PASSED
tests/test_explicar_lee_carter.py::test_execucao_brinquedo_gera_relatorio_valido PASSED
tests/test_explicar_lee_carter.py::test_execucao_implausivel_e_bloqueada PASSED
tests/test_explicar_lee_carter.py::test_bloqueado_apaga_graficos_da_rodada_anterior PASSED
tests/test_explicar_lee_carter.py::test_graficos_gerados_sao_os_esperados PASSED
tests/test_explicar_lee_carter.py::test_schema_rejeita_relatorio_sem_campo PASSED
tests/test_explicar_lee_carter.py::test_schema_rejeita_aprovado_com_checagem_falha PASSED
tests/test_explicar_lee_carter.py::test_integracao_contrato_real_gera_relatorio_aprovado PASSED
tests/test_explicar_lee_carter.py::test_integracao_idade_explica_mais_que_ano PASSED
tests/test_explicar_lee_carter.py::test_integracao_ale_idade_cresce_a_partir_da_idade_minima PASSED

40 passed in 14.74s
```

### Saída do script (EVD-2)

```text
INFO Contrato do Passo 6 lido: 51 idades, anos 2015-2024, origem: Passo 1 — IBGE real, série histórica (serie_historica_qx.csv, 2015-2024)
WARNING ALERTA salto_kappa: kappa_t variou +6.274 de 2021 para 2022 (limite 1.726 = 3 x |drift|). Possível quebra na série de dados de origem; projeções que usam esses anos podem estar distorcidas.
WARNING ALERTA salto_kappa: kappa_t variou -4.286 de 2022 para 2023 (limite 1.726 = 3 x |drift|). Possível quebra na série de dados de origem; projeções que usam esses anos podem estar distorcidas.
WARNING ALERTA drift_sensivel_aos_extremos: O drift do Passo 6 usa só o primeiro e o último ano (-0.5752); a reta ajustada a todos os anos dá -0.4035. Diferença acima de 25%: a projeção depende muito dos anos das pontas.
WARNING ALERTA corcova_de_acidentes: 7 casos de q(x,t) que não crescem com a idade abaixo de 30 anos. Comportamento esperado (mortes por causas externas em adultos jovens); fora da checagem de monotonia.
INFO Relatório APROVADO gravado em .../explicabilidade-model-risk/docs/lee_carter/relatorio_explicabilidade_lee_carter.json (1.07s)
codigo de saida: 0
```

## Observações

- O `rodada.commit` gravado no JSON é o commit do **código** no momento da rodada. Por isso a ordem é: (1) commitar o código, (2) rodar o script, (3) commitar as saídas e este arquivo. O JSON deve mostrar `commit_com_alteracoes_locais: false`. Esse campo olha o código desta pasta, o do Passo 6 e a série do IBGE, mas não `docs/` ([decisões, D11](decisoes.md)).
- **Testes com modelo de brinquedo** (fixture `params_brinquedo`) verificam a lógica, mas **não** comprovam a integração. A integração é comprovada pelos testes `test_integracao_*` e pela EVD-2, que usam o contrato real.
