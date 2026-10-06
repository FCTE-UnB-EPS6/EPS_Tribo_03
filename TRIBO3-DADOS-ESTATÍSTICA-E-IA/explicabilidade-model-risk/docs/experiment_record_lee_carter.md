# Experiment Record: Explicabilidade do Lee-Carter (SL-07, Etapa 1)

> Cada rodada do script `scripts/explicar_lee_carter.py` ganha uma linha nova aqui. **Nunca edite uma rodada antiga**: se algo mudar, rode de novo e registre uma rodada nova.
> Os blocos seguem o formato do MLflow (**params**, **metrics**, **tags**, **artifacts**), para facilitar a migração se a Tribo 5 pedir.
> A fonte de cada número é o arquivo `lee_carter/relatorio_explicabilidade_lee_carter.json` gerado na rodada. A versão desse arquivo em cada commit fica no histórico do Git.

---

## Rodada 1

### tags

| Campo | Valor |
|---|---|
| `rodada.id` | `20261006T125901Z` |
| `data_hora_utc` | 2026-10-06T12:59:01+00:00 |
| `commit` | `c1b08deb0123e22b9d212b434c901845d110ef1b` (`c1b08de`) |
| `commit_com_alteracoes_locais` | `false` |
| `quem_rodou` | Leticia Arisa Kobayashi Higa |
| `modelo` | Lee-Carter (Passo 6) |
| `status` | APROVADO |
| `origem_dados` | Passo 1 — IBGE real, série histórica (serie_historica_qx.csv, 2015-2024) |
| `versao_contrato_relatorio` | 1.0.0 |

### params

| Parâmetro | Valor | Onde está definido |
|---|---|---|
| `idades` | 20 a 70 (51 idades) | contrato do Passo 6 |
| `anos_historicos` | 2015 a 2024 (10 anos) | contrato do Passo 6 |
| `anos_analisados` | 2015 a 2054 | `HORIZONTE_PROJECAO_ANOS = 30` |
| `idade_minima_monotonia` | 30 | `IDADE_MINIMA_MONOTONIA` (decisão D3) |
| `fator_salto_kappa` | 3,0 × \|drift\| | `FATOR_SALTO_KAPPA` (decisão D4) |
| `grid_ale` | 20 faixas | `GRID_ALE` |
| `fundo_shap` | grade histórica 51 × 10 = 510 pontos | `calcular_shap` (decisão D2) |
| `limites_q` | 0,000001 a 0,999 | copiados do Passo 6 |
| Versões | Python 3.12.3, numpy 2.5.3, pandas 3.0.6, matplotlib 3.11.2, PyALE 1.2.0, jsonschema 4.26.0 | `rodada.versoes` do JSON |

### metrics

| Métrica | Valor |
|---|---|
| `drift` (Passo 6) | −0,5752 |
| `inclinacao_reta_kappa` | −0,4035 |
| `variancia_explicada` (1º componente do SVD) | 0,7635 |
| `q_min` / `q_max` (2015-2054) | 0,000839 / 0,024217 |
| `shap_valor_base` | 0,006104 |
| `shap_importancia_idade` | 0,004331 |
| `shap_importancia_ano` | 0,000848 |
| `checagens_aprovadas` | 5 de 5 (`estrutura_consistente`, `valores_finitos`, `q_cresce_com_idade`, `kappa_em_queda`, `restricoes_canonicas`) |
| `alertas` | 4 (2 × `salto_kappa`, `drift_sensivel_aos_extremos`, `corcova_de_acidentes`); `beta_negativo` e `q_no_limite_de_corte` não dispararam |
| `tempo_execucao_s` | 1,069 |

### artifacts

`docs/lee_carter/`: `relatorio_explicabilidade_lee_carter.json`, `alpha_x.png`, `beta_x.png`, `kappa_t.png`, `ale_idade.png`, `ale_ano.png`, `shap_dependencia.png`.

### Observações

- Primeira rodada da Etapa 1. Os alertas de model risk estão descritos no [model card](model_card_lee_carter.md#6-model-risk-alertas-não-bloqueiam-mas-precisam-de-resposta).
- O limite de tempo de execução (RNF02) será definido a partir desta medição.
- Rodada feita com o código que já inclui as decisões D8 a D12 (checagem `estrutura_consistente` ampliada, alerta `beta_negativo`, controle de alterações locais, `null` no lugar de NaN). Os números conferem com o JSON desta rodada.
- Testes no mesmo commit: 40 passed (ver [evidências, EVD-1](evidencias.md)).
