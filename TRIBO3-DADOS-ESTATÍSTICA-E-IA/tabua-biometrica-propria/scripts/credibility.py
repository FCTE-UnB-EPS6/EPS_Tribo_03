"""
Passo 5 — Credibility (interno)

Confirmado (não é mais uma leitura ambígua) que credibility aqui usa
baseline **interno**, não o IBGE:

- O fluxo do §3 lista "credibility" e "comparação com tábua externa" como
  duas etapas separadas, nessa ordem. Se o credibility já usasse o IBGE, a
  etapa seguinte seria redundante — só faz sentido a comparação externa vir
  depois se o credibility for interno.
- O §4.3 lista "credibility" e "comparação com baseline externo" como dois
  itens distintos na lista de entregáveis, reforçando a mesma leitura.
- Bate com a teoria atuarial padrão: credibility (Bühlmann, limited
  fluctuation) combina a experiência da submassa com a experiência de um
  grupo maior *dentro da mesma população* ("collateral data"), não com uma
  tábua de mercado — a tábua externa entra como benchmark independente,
  numa etapa própria.

Implementação: blend entre o qx suavizado de cada submassa e um baseline
interno — o qx suavizado da massa inteira (todas as submassas somadas) na
mesma idade — sem tocar em `referencia_externa` (IBGE). Não depende do
Passo 3 e não precisa ser revisitado depois que a comparação A/E estiver
pronta; essa comparação é o checkpoint de validação separado que vem
depois na sequência do §3, não um insumo deste script.

Método: credibility de raiz quadrada (Z = sqrt(exposição / exposição
plena), limitado a 1) — o baseline mais simples de credibility, análogo à
escolha de média móvel na suavização em vez de Whittaker-Henderson.
EXPOSICAO_PLENA é um limiar arbitrário (documentado abaixo), não um cálculo
de fluctuation credibility clássico — ajustar conforme o julgamento do time
sobre quanto de exposição uma submassa precisa pra ter peso próprio.

Uso:
    python credibility.py
"""

from datetime import date
from pathlib import Path
from math import sqrt
import csv

from db import conectar
from taxas_brutas_qx import calcular_taxas_brutas
from suavizacao import suavizar_submassa, suavizar_por_submassa

PASTA_SAIDA = Path(__file__).resolve().parent.parent / "docs" / "qx_credibilizado"

# Exposição (anos-pessoa) a partir da qual uma submassa recebe peso 1.0
# (Z=1, ou seja, ignora o baseline interno). Limiar simples e ajustável —
# não é limited fluctuation credibility clássico (que exigiria um número
# alvo de óbitos esperados, tipicamente na casa de milhares).
EXPOSICAO_PLENA = 10.0


def montar_baseline_geral(linhas):
    """Pool de todas as submassas por idade -> {idade: linha} no mesmo
    formato usado por suavizar_submassa(), tratando a massa toda como uma
    'submassa geral' única."""
    por_idade = {}
    for l in linhas:
        if l["exposicao_central"] <= 0:
            continue
        acumulado = por_idade.setdefault(l["idade"], {
            "idade": l["idade"], "obitos": 0, "exposicao_central": 0.0,
        })
        acumulado["obitos"] += l["obitos"]
        acumulado["exposicao_central"] += l["exposicao_central"]

    for idade, acumulado in por_idade.items():
        acumulado["qx_bruto"] = (
            acumulado["obitos"] / acumulado["exposicao_central"]
            if acumulado["exposicao_central"] > 0 else None
        )
    return por_idade


def calcular_credibility(linhas):
    """Devolve uma lista com qx_suavizado (por submassa), qx_geral (baseline
    interno) e qx_credibilizado (blend pelos dois) por (idade, submassa)."""
    suavizadas = suavizar_por_submassa(linhas)

    baseline_idade = montar_baseline_geral(linhas)
    qx_geral_suavizado = suavizar_submassa(baseline_idade)

    resultado = []
    for l in suavizadas:
        qx_geral = qx_geral_suavizado.get(l["idade"])
        if l["qx_suavizado"] is None or qx_geral is None:
            qx_credibilizado, z = None, None
        else:
            z = min(1.0, sqrt(l["exposicao_central"] / EXPOSICAO_PLENA))
            qx_credibilizado = z * l["qx_suavizado"] + (1 - z) * qx_geral
        resultado.append({
            "idade": l["idade"],
            "submassa": l["submassa"],
            "exposicao_central": l["exposicao_central"],
            "qx_suavizado_submassa": l["qx_suavizado"],
            "qx_geral_interno": round(qx_geral, 6) if qx_geral is not None else None,
            "z_credibility": round(z, 4) if z is not None else None,
            "qx_credibilizado": round(qx_credibilizado, 6) if qx_credibilizado is not None else None,
        })
    return resultado


def gravar_csv(linhas, caminho):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        campos = ["idade", "submassa", "exposicao_central", "qx_suavizado_submassa",
                  "qx_geral_interno", "z_credibility", "qx_credibilizado"]
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        writer.writerows(linhas)


def main():
    conn = conectar()
    cur = conn.cursor()
    brutas = calcular_taxas_brutas(cur)
    cur.close()
    conn.close()

    if not brutas:
        print("Nenhuma linha em exposicao ainda — rode o seed do Passo 1 primeiro.")
        return

    resultado = calcular_credibility(brutas)

    caminho = PASTA_SAIDA / f"qx_credibilizado_{date.today().isoformat()}.csv"
    gravar_csv(resultado, caminho)

    z_medio = [l["z_credibility"] for l in resultado if l["z_credibility"] is not None]
    print(f"{len(resultado)} células credibilizadas (exposição plena = {EXPOSICAO_PLENA} anos).")
    if z_medio:
        print(f"Z médio: {sum(z_medio) / len(z_medio):.3f} "
              f"(perto de 1 = pouca dependência do baseline interno; "
              f"perto de 0 = submassa pouco exposta, puxada pro geral)")
    print(f"Gravado em {caminho}")


if __name__ == "__main__":
    main()
