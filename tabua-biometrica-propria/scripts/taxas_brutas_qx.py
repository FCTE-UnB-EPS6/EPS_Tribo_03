"""
Passo 5 — Taxas brutas de qx

Primeira etapa do fluxo do escopo (dados sintéticos → exposição ao risco →
eventos observados → taxas brutas → ...): agrega `exposicao` por idade e
submassa e calcula o qx bruto = óbitos observados / exposição central.

Não depende do Passo 3 (benchmark IBGE) nem de nenhuma limpeza adicional —
`exposicao` já é a tabela final, pós-pipeline de qualidade do Passo 1
(ambiente-de-dados/scripts/pipeline_qualidade.py só promove pra cá o que
passou pelas regras R01-R09).

Agrega por FLOOR(idade_exata), não pelo valor contínuo — ver README.md
("Por que agregar por idade inteira") para o motivo.

Uso:
    python taxas_brutas_qx.py
"""

from datetime import date
from pathlib import Path
import csv

from db import conectar

PASTA_SAIDA = Path(__file__).resolve().parent.parent / "docs" / "qx_bruto"


def calcular_taxas_brutas(cur):
    """Uma linha por (idade inteira, submassa): óbitos, exposição central e qx.

    Exposição central = soma de tempo_exposto (fração de ano), não contagem
    de linhas — é a definição atuarial correta de exposição ao risco, mais
    rigorosa do que a aproximação por COUNT(*) usada no benchmark
    preliminar do Passo 3 (que só precisava de ordem de grandeza).
    """
    cur.execute("""
        SELECT FLOOR(idade_exata)::int AS idade,
               submassa,
               COUNT(*) FILTER (WHERE tipo_saida = 'obito') AS obitos,
               COUNT(*) AS linhas_exposicao,
               SUM(tempo_exposto) AS exposicao_central
          FROM exposicao
         GROUP BY FLOOR(idade_exata), submassa
         ORDER BY idade, submassa
    """)
    linhas = []
    for idade, submassa, obitos, linhas_exposicao, exposicao_central in cur.fetchall():
        exposicao_central = float(exposicao_central) if exposicao_central else 0.0
        qx_bruto = (obitos / exposicao_central) if exposicao_central > 0 else None
        linhas.append({
            "idade": idade,
            "submassa": submassa,
            "obitos": obitos,
            "linhas_exposicao": linhas_exposicao,
            "exposicao_central": round(exposicao_central, 5),
            "qx_bruto": round(qx_bruto, 6) if qx_bruto is not None else None,
        })
    return linhas


def gravar_csv(linhas, caminho):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        campos = ["idade", "submassa", "obitos", "linhas_exposicao",
                  "exposicao_central", "qx_bruto"]
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        writer.writerows(linhas)


def main():
    conn = conectar()
    cur = conn.cursor()

    linhas = calcular_taxas_brutas(cur)

    cur.close()
    conn.close()

    if not linhas:
        print("Nenhuma linha em exposicao ainda — rode o seed do Passo 1 primeiro.")
        return

    caminho = PASTA_SAIDA / f"qx_bruto_{date.today().isoformat()}.csv"
    gravar_csv(linhas, caminho)

    celulas_sem_dado = sum(1 for l in linhas if l["qx_bruto"] is None)
    print(f"{len(linhas)} células (idade x submassa) calculadas.")
    if celulas_sem_dado:
        print(f"  {celulas_sem_dado} célula(s) sem exposição (qx_bruto vazio).")
    print(f"Gravado em {caminho}")


if __name__ == "__main__":
    main()
