# Dashboard Preview — Passo 6 (Tábuas Geracionais e Improvement)

Painel visual e interativo desenvolvido especificamente para o **Passo 6**, servindo de preview executivo e técnico das análises de longevidade e *mortality improvement*.

---

## O Que Está Apresentado no Preview

1. **Visão Geral e Metadados do Passo 6:** Dupla responsável (Danielle e Maria Eduarda), período histórico analisado e horizonte projetado.
2. **KPIs Principais:** Resultados dos testes de Mann-Kendall ($S$, $Z$, $p$-valor), diagnóstico conjunto ADF/KPSS e modelo selecionado pelo backtest.
3. **Evolução Temporal da Mortalidade $q(x, t)$:** Curvas interativas para idades 30, 45, 60 e 70 anos de 2024 até 2054.
4. **Escala de Mortality Improvement ($f_x$):** Taxa percentual anual de redução da mortalidade por idade.
5. **Superfície Interativa de Coortes (Heatmap Plotly):** Mapa de calor cruzando idade e ano de calendário para rastreamento de coortes ($c = t - x$).
6. **Amostra da Tábua Geracional:** Tabela com probabilidades de morte projetadas em 10, 20 e 30 anos e reduções percentuais acumuladas.
7. **Termômetro de Conformidade do Definition of Done (§8 DoD).**

---

## Como Gerar ou Atualizar o Preview

Para regerar o preview após rodar novas rodadas de experimentos:

```bash
python tabuas-geracionais-improvement/dashboard/gerar_preview.py
```

## Como Visualizar

O arquivo gerado é **100% autocontido**:

- **Basta dar duplo clique** no arquivo `tabuas-geracionais-improvement/dashboard/preview.html` no seu explorador de arquivos (Windows Explorer) para abri-lo em qualquer navegador (Chrome, Edge, Firefox).
- Não é necessário ter nenhum servidor web ou banco ativo para visualizar o dashboard.
