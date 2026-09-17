# Validação técnica do núcleo 0.1.0

Data: 2026-09-13. Contrato: `0.1.0`. Gerador: `0.1.0`.

## Entrada e método

Execução local com a requisição `examples/generate.demo.v0.1.0.json` e as regras
`config/scenario_rules.demo.v0.1.0.json`. Conjunto de premissas `demo-economic`
versão `0.1.0`; regras `demo-additive` versão `0.1.0`.

Método: ajustes aditivos constantes, cálculo exato em escala de oito casas
decimais e dez períodos anuais a partir de 2026-09-13.

## Verificação executada

Comando, dentro de `cenarios-economicos/`:

```bash
python -m unittest discover -s tests -v
```

Resultado: **18 testes passaram**. O teste de gabarito confrontou os quatro
valores de cada cenário nos dez períodos com os resultados especificados em
[ASSUMPTIONS.md](ASSUMPTIONS.md). Também passaram verificações de reprodução,
cópias independentes, precisão sob contexto Decimal reduzido, ida e volta JSON,
calendário bissexto e rejeição de entradas/regras/resultados inválidos.

## Limites

Não houve execução sobre dados reais, projeção de obrigações, avaliação de
solvência ou calibração econômica. Não houve teste de API ou banco, que ainda
não estão implementados. Os alinhamentos entre consumidores permanecem pendentes.
Este registro demonstra a validação técnica do núcleo local, não a conclusão do MVP.
