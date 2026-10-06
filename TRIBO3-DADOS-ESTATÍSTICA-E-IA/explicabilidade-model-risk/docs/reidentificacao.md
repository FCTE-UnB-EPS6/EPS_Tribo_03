# Análise de Reidentificação: Passo 7 / SL-07

> **Destinatário:** Tribo 4 (Segurança e Privacidade).
> **Etapa coberta:** 1 (Lee-Carter do Passo 6). As Etapas 2 e 3 atualizam este documento.

## Etapa 1: Lee-Carter (Passo 6)

| Pergunta | Resposta |
|---|---|
| Há dado pessoal? | **Não.** A entrada é a série do IBGE 2015-2024, pública e agregada por idade simples e ano. |
| Há registro individual em algum ponto? | Não. O contrato do Passo 6 entrega só parâmetros do modelo (alpha_x, beta_x, kappa_t, drift). |
| As saídas (JSON e PNG) têm linhas individuais? | Não. Só parâmetros, efeitos médios (ALE), contribuições por célula idade × ano (SHAP) e checagens. |
| Combinações raras de variáveis? | Não se aplica: as únicas entradas são idade e ano, e cada célula agrega a população brasileira daquela idade. |
| **Risco de reidentificação** | **Baixo.** |

## Etapas seguintes (onde o risco é real)

- **Etapa 3 (Passo 2):** usa dados **individuais** (massa sintética calibrada com dados reais), com covariáveis `idade_ingresso`, `sexo_M`, `plano_BD`, `plano_CD`, `submassa_A` e `submassa_B`. O SHAP de um modelo individual pode destacar combinações raras (por exemplo, uma submassa pequena com sexo e idade específicos). Se o mesmo pipeline for aplicado a dados reais no futuro, isso permitiria inferir dados de pessoas. Essa análise será entregue formalmente à Tribo 4 antes do fechamento da Etapa 3.
- **Controles já aplicados:** gráficos e relatórios só com valores agregados; nenhuma linha individual em logs.
