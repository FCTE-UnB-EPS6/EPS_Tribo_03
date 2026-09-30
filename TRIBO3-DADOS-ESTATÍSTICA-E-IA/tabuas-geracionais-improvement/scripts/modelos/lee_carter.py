"""
Passo 6 — Modelo Estocástico de Lee-Carter (1992)

Implementa o modelo clássico de Lee-Carter para decomposição e projeção
estocástica de mortalidade:
    ln(mx,t) = ax + bx * kt + e(x,t)

Ajuste via SVD (Singular Value Decomposition) de posto 1 e projeção do índice kt
via Passeio Aleatório com Drift (Random Walk with Drift).

Uso:
    python scripts/modelos/lee_carter.py
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

from config import PASTA_TABUA_GERACIONAL
from dados.series_temporais import carregar_dados


def montar_matriz_mortalidade(linhas):
    idades = sorted({l["idade"] for l in linhas})
    anos = sorted({l["ano"] for l in linhas})

    mapa = {(l["idade"], l["ano"]): l["mx"] for l in linhas}
    matriz = np.zeros((len(idades), len(anos)), dtype=float)

    for i, idade in enumerate(idades):
        for j, ano in enumerate(anos):
            mx = mapa.get((idade, ano), 0.0)
            matriz[i, j] = max(mx, 1e-6)

    return idades, anos, matriz


def ajustar_lee_carter(idades, anos, matriz_mx):
    log_m = np.log(matriz_mx)

    # 1. ax é a média histórica do log(mx) para cada idade
    ax = np.mean(log_m, axis=1)

    # 2. Matriz centrada Z
    z = log_m - ax[:, np.newaxis]

    # 3. Decomposição SVD: Z = U * S * Vt
    u, s, vt = np.linalg.svd(z, full_matrices=False)

    u1 = u[:, 0]
    v1 = vt[0, :]
    s1 = s[0]

    # Convenção canônica: se a trajetória de v1 for crescente no tempo,
    # orienta ambos os autovetores para que kt decresça à medida que a mortalidade cai
    if len(v1) > 1 and v1[-1] > v1[0]:
        u1 = -u1
        v1 = -v1

    # 4. Normalização padrão: sum(bx) = 1 e mean(kt) = 0
    soma_u = np.sum(u1)
    if abs(soma_u) < 1e-9:
        soma_u = 1.0

    bx = u1 / soma_u
    kt = v1 * s1 * soma_u

    media_kt = np.mean(kt)
    kt = kt - media_kt
    ax = ax + bx * media_kt

    # 5. Drift do passeio aleatório de kt: d = (kt[-1] - kt[0]) / (T - 1)
    drift = (kt[-1] - kt[0]) / max(len(kt) - 1, 1)

    diff_kt = np.diff(kt)
    se_drift = np.std(diff_kt) if len(diff_kt) > 1 else 0.0

    return {
        "idades": idades,
        "anos": anos,
        "ax": ax,
        "bx": bx,
        "kt": kt,
        "drift": float(drift),
        "se_drift": float(se_drift),
        "variancia_explicada": float((s1**2) / np.sum(s**2)) if np.sum(s**2) > 0 else 1.0,
    }


def treinar_lee_carter(linhas_treino):
    idades, anos, matriz_mx = montar_matriz_mortalidade(linhas_treino)
    return ajustar_lee_carter(idades, anos, matriz_mx)


def projetar_lee_carter(modelo, idade, ano_alvo):
    if idade not in modelo["idades"]:
        return None

    idx_idade = modelo["idades"].index(idade)
    ano_ultimo = modelo["anos"][-1]
    h = max(ano_alvo - ano_ultimo, 0)

    kt_projetado = modelo["kt"][-1] + h * modelo["drift"]
    log_mx_proj = modelo["ax"][idx_idade] + modelo["bx"][idx_idade] * kt_projetado
    mx_proj = np.exp(log_mx_proj)

    qx_proj = 1.0 - np.exp(-mx_proj) if mx_proj < 1.0 else 0.999
    return float(np.clip(qx_proj, 1e-6, 0.999))


def main():
    linhas, origem = carregar_dados()
    modelo = treinar_lee_carter(linhas)

    print("Modelo Lee-Carter ajustado com sucesso!")
    print(f"  Origem dos dados: {origem}")
    print(f"  Período histórico de calibração: {modelo['anos'][0]} a {modelo['anos'][-1]}")
    print(f"  Variância explicada pelo 1º componente (SVD): {modelo['variancia_explicada']*100:.2f}%")
    print(f"  Drift anual do índice kt: {modelo['drift']:.4f}")
    print(f"  Soma dos coeficientes bx: {np.sum(modelo['bx']):.4f} (deve ser 1.0)")
    print(f"  Média do índice histórico kt: {np.mean(modelo['kt']):.6f} (deve ser 0.0)")

    idades_teste = [30, 45, 60]
    print("\nExemplo de projeção Lee-Carter para 10 e 20 anos:")
    ano_ultimo = modelo["anos"][-1]
    for id_ in idades_teste:
        if id_ in modelo["idades"]:
            q0 = projetar_lee_carter(modelo, id_, ano_ultimo)
            q10 = projetar_lee_carter(modelo, id_, ano_ultimo + 10)
            q20 = projetar_lee_carter(modelo, id_, ano_ultimo + 20)
            print(f"  Idade {id_}: qx({ano_ultimo})={q0:.6f} -> qx({ano_ultimo+10})={q10:.6f} -> qx({ano_ultimo+20})={q20:.6f}")


if __name__ == "__main__":
    main()
