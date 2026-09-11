"""
Passo 5 — Pipeline completo

Roda os 9 scripts do fluxo do §3, na ordem que cada um espera:

    taxas_brutas_qx -> coortes -> comparacao_ae -> suavizacao ->
    teste_aderencia -> credibility -> intervalos_confianca ->
    validacao_temporal -> tabua_propria

Para no primeiro erro — não faz sentido rodar a suavização se as taxas
brutas falharam, por exemplo. Cada script continua podendo ser rodado
isoladamente (foi assim que todos foram testados); isto aqui só poupa de
digitar 9 comandos toda vez.

Uso:
    python pipeline.py
"""

import subprocess
import sys
from pathlib import Path

PASTA_SCRIPTS = Path(__file__).resolve().parent

ETAPAS = [
    "taxas_brutas_qx.py",
    "coortes.py",
    "comparacao_ae.py",
    "suavizacao.py",
    "teste_aderencia.py",
    "credibility.py",
    "intervalos_confianca.py",
    "validacao_temporal.py",
    "tabua_propria.py",
]


def rodar_etapa(nome_script):
    """Roda o script como subprocesso (mesmo interpretador Python desta
    execução), com o diretório de scripts como cwd — os imports internos
    entre scripts (ex.: suavizacao importa taxas_brutas_qx) dependem disso."""
    caminho = PASTA_SCRIPTS / nome_script
    resultado = subprocess.run([sys.executable, str(caminho)], cwd=PASTA_SCRIPTS)
    return resultado.returncode == 0


def main():
    total = len(ETAPAS)
    print(f"Pipeline do Passo 5 — {total} etapas\n")

    for i, script in enumerate(ETAPAS, start=1):
        print(f"{'=' * 60}\n[{i}/{total}] {script}\n{'=' * 60}")
        if not rodar_etapa(script):
            print(f"\nFALHOU em {script} (etapa {i}/{total}). Pipeline interrompido — "
                  f"as etapas seguintes não rodaram.")
            sys.exit(1)
        print()

    print(f"{'=' * 60}\nPipeline completo — todas as {total} etapas rodaram sem erro.")
    print("Ver docs/tabua_propria/*.md para o veredito final (pronta pra "
          "oficializar ou precisa revisar).")


if __name__ == "__main__":
    main()
