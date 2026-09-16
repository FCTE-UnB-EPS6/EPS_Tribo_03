# Experiment Record — Tábua Biométrica Própria

Registro de cada rodada da tábua própria: parâmetros usados, dados de
entrada e resultado. Uma linha nova por execução completa do pipeline
(`taxas_brutas_qx.py` → `coortes.py` → `comparacao_ae.py` →
`suavizacao.py` → `teste_aderencia.py` → `credibility.py` →
`intervalos_confianca.py` → `validacao_temporal.py` → `tabua_propria.py`)
— não por script isolado.

## Parâmetros fixos no código (mudam só se editar o script)

| Parâmetro | Valor | Onde | Efeito se mudar |
| --- | --- | --- | --- |
| `JANELA` | 2 (±2 idades) | `suavizacao.py` | janela maior = curva mais lisa, mas mistura idades mais distantes |
| `LIMIAR_ESPERADO` | 1.0 óbito | `teste_aderencia.py` | limiar menor = menos pooling, mais células, teste mais sensível a ruído |
| `ALPHA` | 0.05 | `teste_aderencia.py`, `intervalos_confianca.py`, `validacao_temporal.py` | mais rígido/frouxo pra rejeitar H0 ou definir a largura do IC |
| `EXPOSICAO_PLENA` | 10.0 anos-pessoa | `credibility.py` | limiar menor = credibility pleno (Z=1) mais cedo, menos peso no baseline interno |
| `AE_FAIXA_ACEITAVEL` | (0.5, 2.0) | `tabua_propria.py` | faixa mais estreita = portão de A/E mais rígido pra oficializar a tábua |

## Log de execuções

| Data | Seed/versão do dataset (Passo 1) | Volume (N_PARTICIPANTES) | Razão A/E geral (Ambos) | Resultado teste de aderência | Resultado validação temporal | Veredito `tabua_propria.py` | Observações |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-09-11 | seed=42 | 301 | 0.6879 | Não calculável — 1 célula após pooling, gl=0 | Não calculável — 1 célula no holdout, gl=0 | PRONTA PARA OFICIALIZAR | Pipeline completo executado com sucesso (9/9). A/E geral dentro da faixa 0.5–2.0. Teste de aderência e validação temporal inconclusivos por exposição insuficiente. A/E M=0.3326 e F=1.5678. |
| 2026-09-11 | seed=42 | 301 | 0.6879 | Não calculável — 1 célula após pooling, gl=0 | Não calculável — 1 célula no holdout, gl=0 | REVISAR ANTES DE OFICIALIZAR | Pipeline 9/9 executado sem erro após correção do gate final. Aderência e validação temporal inconclusivas por dados insuficientes. A/E geral dentro da faixa. |

## Notas de implementação (contexto de quando cada etapa foi escrita)

- **Taxas brutas / coortes**: implementadas primeiro por não terem
  nenhuma dependência (nem do Passo 3).
- **Suavização / teste de aderência**: implementadas em seguida, também
  sem dependência do Passo 3.
- **Credibility / IC / validação temporal**: implementadas depois, todas
  também sem dependência do Passo 3. Credibility usa baseline interno
  (blend com o qx geral da massa, não com o IBGE) — confirmado como a
  leitura correta do escopo pela ordem do §3 e pelo §4.3 (credibility e
  "comparação com tábua externa" são etapas/entregáveis separados), além
  de bater com a teoria atuarial padrão (Bühlmann/limited fluctuation).
  Não é mais uma decisão em aberto — ver `model_card.md`.
- **Comparação A/E**: implementada em `comparacao_ae.py`, lendo os
  arquivos brutos do IBGE em `ambiente-de-dados/docs/referencias/`
  diretamente — não precisou esperar a outra dupla rodar
  `benchmark_ibge.py` de novo nem preencher `referencia_externa` no banco.
  Só HMD/BR-EMS/SOA (também já versionados naquela pasta) ficaram de fora
  por enquanto — extensão natural se fizer falta.
- **Consolidação final**: `tabua_propria.py` fecha o fluxo do §3. Junta
  bruto, suavizado, credibilizado e IC por (idade, submassa), adota
  `qx_credibilizado` como oficial, e condiciona isso a dois portões
  (aderência geral e A/E geral) reaproveitando os módulos anteriores —
  não recalcula nada do zero. Único item que falta agora em todo o Passo
  5 é rodar contra dados reais (sem Postgres nesta máquina) e ver se os
  portões realmente passam.
