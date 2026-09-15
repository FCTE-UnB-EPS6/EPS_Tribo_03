"""
Passo 6 — Modelo Baseline de Projeção (Extrapolação de Tendência)

Implementa o modelo de referência simples exigido pelo princípio
"baseline antes de complexidade" (§3/§8 DoD).

Ajusta uma taxa geométrica de melhoria anual (fx) para cada idade x a partir
da série histórica, projetando:
    qx(t) = qx(t0) * (1 - fx)^(t - t0)

Com travas atuariais de sanidade para evitar taxas negativas ou melhorias irreais.

Uso:
    python scripts/modelos/baseline.py
"""

from collections import defaultdict
from datetime import date
from pathlib import Path
import sys
import numpy as np

# Adiciona scripts/ ao sys.path para imports limpos
PASTA_SCRIPTS = Path(__file__).resolve().parents[1]
if str(PASTA_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(PASTA_SCRIPTS))

from config import LIMITE_FX_MAX, PASTA_TABUA_GERACIONAL
from dados.series_temporais import carregar_dados


def agrupar_por_idade(linhas):
    por_idade = defaultdict(list)
    for l in linhas:
        por_idade[l["idade"]].append(l)
    return por_idade


def treinar_baseline(linhas_treino, ano_base=None):
    """Ajusta a taxa anual de melhoria fx para cada idade via regressão linear
    no log da mortalidade: ln(qx) = a + b * (ano - ano_base).
    """
    if ano_base is None:
        ano_base = max(l["ano"] for l in linhas_treino)

    dados_idade = agrupar_por_idade(linhas_treino)
    parametros = {}

    for idade, registros in dados_idade.items():
        registros_ordenados = sorted(registros, key=lambda r: r["ano"])
        anos = np.array([r["ano"] for r in registros_ordenados]) - ano_base
        q_vals = np.array([max(r["qx"], 1e-6) for r in registros_ordenados])
        log_q = np.log(q_vals)

        if len(anos) >= 2 and np.var(anos) > 0:
            pesos = np.sqrt([max(r["exposicao_central"], 1.0) for r in registros_ordenados])
            pesos /= np.sum(pesos)
            try:
                poly = np.polyfit(anos, log_q, deg=1, w=pesos)
                slope, intercept = poly[0], poly[1]
                fx_bruto = 1.0 - np.exp(slope)
            except Exception:
                slope, intercept = 0.0, np.mean(log_q)
                fx_bruto = 0.0
        else:
            slope, intercept = 0.0, np.mean(log_q)
            fx_bruto = 0.0

        # Trava atuarial de prudência (clamping entre 0% e LIMITE_FX_MAX ao ano)
        fx_ajustado = float(np.clip(fx_bruto, 0.0, LIMITE_FX_MAX))
        qx_base = float(np.clip(np.exp(intercept), 1e-6, 0.999))

        parametros[idade] = {
            "idade": idade,
            "ano_base": ano_base,
            "qx_base": qx_base,
            "slope": float(slope),
            "fx_bruto": round(float(fx_bruto), 5),
            "fx": round(fx_ajustado, 5),
        }

    return {"ano_base": ano_base, "por_idade": parametros}


def projetar_baseline(modelo, idade, ano_alvo):
    """Projeta o qx para uma idade no ano_alvo."""
    par = modelo["por_idade"].get(idade)
    if not par:
        return None
    delta = max(ano_alvo - modelo["ano_base"], 0)
    qx_proj = par["qx_base"] * ((1.0 - par["fx"]) ** delta)
    return max(min(qx_proj, 0.999), 1e-6)


def main():
    linhas, origem = carregar_dados()
    modelo = treinar_baseline(linhas)
    print("Modelo Baseline de Mortality Improvement ajustado com sucesso!")
    print(f"  Origem dos dados: {origem}")
    print(f"  Ano base (t0): {modelo['ano_base']}")
    print(f"  Total de idades modeladas: {len(modelo['por_idade'])}")

    idades_teste = [30, 45, 60]
    print("\nExemplo de projeção para 10 e 20 anos:")
    for id_ in idades_teste:
        if id_ in modelo["por_idade"]:
            q0 = modelo["por_idade"][id_]["qx_base"]
            fx = modelo["por_idade"][id_]["fx"]
            q10 = projetar_baseline(modelo, id_, modelo["ano_base"] + 10)
            q20 = projetar_baseline(modelo, id_, modelo["ano_base"] + 20)
            print(f"  Idade {id_} (fx = {fx*100:.2f}% a.a.): qx_t0={q0:.6f} -> qx_t+10={q10:.6f} -> qx_t+20={q20:.6f}")


if __name__ == "__main__":
    main()
