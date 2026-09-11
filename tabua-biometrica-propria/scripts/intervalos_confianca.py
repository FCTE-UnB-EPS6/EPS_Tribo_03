"""
Passo 5 — Intervalos de confiança por célula de qx

IC de Poisson exato (fórmula de Garwood, 1936) por célula (idade,
submassa), usando os óbitos observados e a exposição central já calculados
em taxas_brutas_qx.py. Escolhido em vez do IC binomial porque a exposição
aqui é medida em anos-pessoa (tempo_exposto fracionário), não em contagem
de indivíduos — Poisson é o modelo padrão pra taxa por unidade de
exposição contínua, o mesmo raciocínio usado no teste de aderência
(qui-quadrado sobre óbitos observados vs. esperados).

    limite_inferior = chi2.ppf(alpha/2,     2*obitos)     / (2*exposicao)
    limite_superior = chi2.ppf(1-alpha/2,   2*(obitos+1)) / (2*exposicao)

Com obitos=0 o limite inferior é 0 (não há chi-quadrado com 0 graus de
liberdade).

Uso:
    python intervalos_confianca.py
"""

from datetime import date
from pathlib import Path
import csv

from scipy.stats import chi2

from db import conectar
from taxas_brutas_qx import calcular_taxas_brutas

PASTA_SAIDA = Path(__file__).resolve().parent.parent / "docs" / "intervalos_confianca"
ALPHA = 0.05  # IC de 95%


def ic_poisson(obitos, exposicao, alpha=ALPHA):
    if exposicao <= 0:
        return None, None
    inferior = 0.0 if obitos == 0 else chi2.ppf(alpha / 2, 2 * obitos) / (2 * exposicao)
    superior = chi2.ppf(1 - alpha / 2, 2 * (obitos + 1)) / (2 * exposicao)
    return round(float(inferior), 6), round(float(superior), 6)


def calcular_ics(linhas):
    resultado = []
    for l in linhas:
        inferior, superior = ic_poisson(l["obitos"], l["exposicao_central"])
        resultado.append({
            "idade": l["idade"],
            "submassa": l["submassa"],
            "obitos": l["obitos"],
            "exposicao_central": l["exposicao_central"],
            "qx_bruto": l["qx_bruto"],
            "ic_inferior_95": inferior,
            "ic_superior_95": superior,
        })
    return resultado


def gravar_csv(linhas, caminho):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        campos = ["idade", "submassa", "obitos", "exposicao_central",
                  "qx_bruto", "ic_inferior_95", "ic_superior_95"]
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

    resultado = calcular_ics(brutas)

    caminho = PASTA_SAIDA / f"ic_qx_{date.today().isoformat()}.csv"
    gravar_csv(resultado, caminho)

    larguras = [
        l["ic_superior_95"] - l["ic_inferior_95"] for l in resultado
        if l["ic_inferior_95"] is not None
    ]
    print(f"{len(resultado)} células com IC de 95% (Poisson exato) calculadas.")
    if larguras:
        print(f"Largura média do IC: {sum(larguras) / len(larguras):.5f} "
              f"(larguras grandes = pouca exposição, célula candidata a credibility)")
    print(f"Gravado em {caminho}")


if __name__ == "__main__":
    main()
