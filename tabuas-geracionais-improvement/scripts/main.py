"""
Passo 6 — Orquestrador Principal: Tábuas Geracionais e Mortality Improvement

Ponto único de entrada para executar todas as etapas sequenciais do Passo 6:
    1. series_temporais.py       — Extração e agregação de dados históricos
    2. teste_mann_kendall.py     — Teste não-paramétrico de tendência de mortalidade
    3. teste_estacionariedade.py — Testes econométricos ADF e KPSS de raiz unitária
    4. backtest_temporal.py      — Backtesting cego e seleção Champion-Challenger (DoD)
    5. tabua_geracional.py       — Projeção dinâmica a 30 anos e consolidação da tábua

Uso:
    python scripts/main.py
"""

import subprocess
import sys
from pathlib import Path

PASTA_SCRIPTS = Path(__file__).resolve().parent

ETAPAS = [
    ("series_temporais.py", "Agregação da série temporal de mortalidade"),
    ("teste_mann_kendall.py", "Teste de tendência não-paramétrica de Mann-Kendall"),
    ("teste_estacionariedade.py", "Testes de raiz unitária ADF e KPSS"),
    ("backtest_temporal.py", "Backtesting temporal e seleção Champion-Challenger"),
    ("tabua_geracional.py", "Consolidação e projeção da Tábua Geracional"),
]


def rodar_etapa(nome_script):
    caminho = PASTA_SCRIPTS / nome_script
    res = subprocess.run([sys.executable, str(caminho)], cwd=PASTA_SCRIPTS)
    return res.returncode == 0


def main():
    total = len(ETAPAS)
    print("=" * 70)
    print(f"EXECUÇÃO PRINCIPAL DO PASSO 6 — TÁBUAS GERACIONAIS ({total} ETAPAS)")
    print("=" * 70)
    print()

    for i, (script, descricao) in enumerate(ETAPAS, start=1):
        print(f"[{i}/{total}] {script} — {descricao}")
        print("-" * 70)
        sucesso = rodar_etapa(script)
        if not sucesso:
            print()
            print("!" * 70)
            print(f"FALHA na etapa [{i}/{total}] {script}. Execução abortada!")
            print("!" * 70)
            sys.exit(1)
        print()

    # Compilação do dashboard preview do Passo 6 se disponível
    script_dashboard = PASTA_SCRIPTS.parent / "dashboard" / "gerar_preview.py"
    if script_dashboard.exists():
        print("[EXTRA] Compilando dashboard de preview do Passo 6...")
        subprocess.run([sys.executable, str(script_dashboard)], cwd=script_dashboard.parent)
        print()

    print("=" * 70)
    print("PASSO 6 CONCLUÍDO COM SUCESSO! Todas as etapas executadas sem erro.")
    print("Consulte os artefatos em docs/:")
    print("  - docs/series_temporais/")
    print("  - docs/testes_estatisticos/")
    print("  - docs/backtest/")
    print("  - docs/tabua_geracional/")
    print("Dashboard interativo:")
    print("  - dashboard/preview.html (abra diretamente no navegador)")
    print("=" * 70)


if __name__ == "__main__":
    main()
