"""
Passo 6 — Séries Temporais de Mortalidade Histórica

Agrega as séries temporais de mortalidade por ano de calendário e idade inteira.

Conecta-se diretamente às fontes oficiais dos passos anteriores:
    1. Tabela `exposicao` no PostgreSQL da Tribo 3 (Passo 1), quando ativo.
    2. Planilha oficial de referência histórica do HMD (Passo 3), quando
       o banco local estiver offline.

Sem dados inventados: respeita 100% as estruturas e dados reais dos outros passos.

Uso:
    python scripts/series_temporais.py
"""

from datetime import date
from pathlib import Path
import csv
import sys

# Garante import local direto
PASTA_SCRIPTS = Path(__file__).resolve().parent
if str(PASTA_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(PASTA_SCRIPTS))

from config import PASTA_SERIES_TEMPORAIS
from ingestao_passos import carregar_historico_mortalidade


def carregar_dados():
    """Consome a série histórica diretamente do Passo 1 (Postgres) ou Passo 3 (HMD)."""
    return carregar_historico_mortalidade()


def gravar_csv(linhas, caminho):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        campos = ["ano", "idade", "obitos", "linhas_exposicao", "exposicao_central", "mx", "qx"]
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        writer.writerows(linhas)


def main():
    linhas, origem = carregar_dados()
    caminho = PASTA_SERIES_TEMPORAIS / f"serie_historica_{date.today().isoformat()}.csv"
    gravar_csv(linhas, caminho)

    anos = sorted({l["ano"] for l in linhas})
    idades = sorted({l["idade"] for l in linhas})
    print("Séries temporais históricas extraídas com sucesso!")
    print(f"  Origem dos dados: {origem}")
    print(f"  Período: {anos[0]} a {anos[-1]} ({len(anos)} anos)")
    print(f"  Faixa etária: {idades[0]} a {idades[-1]} anos ({len(idades)} idades)")
    print(f"  Total de células (ano x idade): {len(linhas)}")
    print(f"  Arquivo salvo em: {caminho}")


if __name__ == "__main__":
    main()
