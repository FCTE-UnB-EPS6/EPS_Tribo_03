# Testes de Estacionariedade — ADF e KPSS (§3/§8 DoD)

**Objetivo:** Avaliar a presença de raiz unitária na série temporal de mortalidade para orientar a modelagem estocástica.

- **Período avaliado:** 2015 a 2024 (n = 10 anos)

## 1. Teste Augmented Dickey-Fuller (ADF)
- **Hipótese Nula (H0):** A série possui raiz unitária (é não-estacionária).
- **Estatística t-ADF:** -1.9064
- **p-valor:** 0.32903
- **Rejeita H0 a 5%?** Não (Presença de Raiz Unitária / Tendência)

## 2. Teste KPSS
- **Hipótese Nula (H0):** A série é estacionária em torno de um nível.
- **Estatística KPSS:** 0.4501
- **p-valor:** 0.05557
- **Rejeita H0 a 5%?** Não (Estacionária)

## 3. Diagnóstico Conjunto e Implicação Metodológica

**Diagnóstico:** **Indício de não-estacionariedade fraca**

ADF não rejeita raiz unitária, sugerindo que projeções dinâmicas devem incorporar termo de drift.

> [!IMPORTANT]
> A constatação de raiz unitária / não-estacionariedade em nível fundamenta a necessidade de modelar o índice temporal kappa_t como um **Passeio Aleatório com Drift (Random Walk with Drift)** no modelo Lee-Carter, em vez de assumir taxas fixas constantes.