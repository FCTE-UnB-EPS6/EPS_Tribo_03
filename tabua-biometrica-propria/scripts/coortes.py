"""
Passo 5 — Coortes como artefato próprio (§4.2)

O §4.2 do escopo exige que a contagem de eventos por submassa seja
versionada como artefato em si, não só como cálculo de passagem dentro do
script do qx (taxas_brutas_qx.py). Por isso este é um script separado, com
sua própria saída versionada — mesmo que a query em si seja parecida.

Coorte aqui = participantes expostos num mesmo ano_calendario e submassa
(o campo já existe em `exposicao`, gerado pelo Passo 1 — não precisou criar
nada novo de infraestrutura).

Uso:
    python coortes.py
"""

from datetime import date
from pathlib import Path
import csv

from db import conectar

PASTA_SAIDA = Path(__file__).resolve().parent.parent / "docs" / "coortes"


def montar_coortes(cur):
    """Uma linha por (ano_calendario, submassa): participantes distintos,
    linhas de exposição, óbitos, censuras, saídas por estudo e exposição
    total (soma de tempo_exposto)."""
    cur.execute("""
        SELECT ano_calendario,
               submassa,
               COUNT(DISTINCT participante_id) AS participantes_distintos,
               COUNT(*) AS linhas_exposicao,
               COUNT(*) FILTER (WHERE tipo_saida = 'obito') AS obitos,
               COUNT(*) FILTER (WHERE tipo_saida = 'censura') AS censuras,
               COUNT(*) FILTER (WHERE tipo_saida = 'saida_estudo') AS saidas_estudo,
               SUM(tempo_exposto) AS exposicao_total
          FROM exposicao
         GROUP BY ano_calendario, submassa
         ORDER BY ano_calendario, submassa
    """)
    linhas = []
    for (ano, submassa, participantes, linhas_exp, obitos, censuras,
         saidas_estudo, exposicao_total) in cur.fetchall():
        linhas.append({
            "ano_calendario": ano,
            "submassa": submassa,
            "participantes_distintos": participantes,
            "linhas_exposicao": linhas_exp,
            "obitos": obitos,
            "censuras": censuras,
            "saidas_estudo": saidas_estudo,
            "exposicao_total": round(float(exposicao_total), 5) if exposicao_total else 0.0,
        })
    return linhas


def gravar_csv(linhas, caminho):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        campos = ["ano_calendario", "submassa", "participantes_distintos",
                  "linhas_exposicao", "obitos", "censuras", "saidas_estudo",
                  "exposicao_total"]
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        writer.writerows(linhas)


def main():
    conn = conectar()
    cur = conn.cursor()

    linhas = montar_coortes(cur)

    cur.close()
    conn.close()

    if not linhas:
        print("Nenhuma linha em exposicao ainda — rode o seed do Passo 1 primeiro.")
        return

    caminho = PASTA_SAIDA / f"coortes_{date.today().isoformat()}.csv"
    gravar_csv(linhas, caminho)

    anos = sorted({l["ano_calendario"] for l in linhas})
    print(f"{len(linhas)} coortes (ano x submassa) calculadas, "
          f"cobrindo {anos[0]}-{anos[-1]}.")
    print(f"Gravado em {caminho}")


if __name__ == "__main__":
    main()
