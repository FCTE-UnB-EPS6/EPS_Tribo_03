# Testes de Estacionariedade — ADF e KPSS (§3/§8 DoD)

**Objetivo:** Avaliar a presença de raiz unitária na série temporal de mortalidade para orientar a modelagem estocástica.

- **Período avaliado:** 2012 a 2021 (n = 10 anos)

## 1. Teste Augmented Dickey-Fuller (ADF)
- **Hipótese Nula (H0):** A série possui raiz unitária (é não-estacionária).
- **Estatística t-ADF:** 1.6786
- **p-valor:** 0.99808
- **Rejeita H0 a 5%?** Não (Presença de Raiz Unitária / Tendência)

## 2. Teste KPSS
- **Hipótese Nula (H0):** A série é estacionária em torno de um nível.
- **Estatística KPSS:** 0.5527
- **p-valor:** 0.0298
- **Rejeita H0 a 5%?** Sim (Não-estacionária)

## 3. Diagnóstico Conjunto e Implicação Metodológica

**Diagnóstico:** **Não estacionária com Raiz Unitária I(1)**

A série possui tendência estocástica e requer modelagem por primeira diferença ou Random Walk with Drift (justificativa matemática formal para o modelo Lee-Carter).

> [!IMPORTANT]
> A constatação de raiz unitária / não-estacionariedade em nível fundamenta a necessidade de modelar o índice temporal kappa_t como um **Passeio Aleatório com Drift (Random Walk with Drift)** no modelo Lee-Carter, em vez de assumir taxas fixas constantes.