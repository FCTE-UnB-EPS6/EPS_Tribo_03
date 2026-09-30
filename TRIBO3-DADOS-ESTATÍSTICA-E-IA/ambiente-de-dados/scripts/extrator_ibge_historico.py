# -*- coding: utf-8 -*-
"""Extrator de serie historica de mortalidade do IBGE (Passo 1, item pendente).

Constroi a serie historica que o Passo 6 (tabua geracional) precisa como
challenger nacional: qx por idade/sexo/ano, a partir das Tabuas Completas
de Mortalidade que o IBGE publica anualmente em
ftp.ibge.gov.br/Tabuas_Completas_de_Mortalidade/.

Desvio deliberado do plano original ("extrator SIM+IBGE"): o plano previa
combinar obitos brutos do SIM com populacao do IBGE para calcular o qx
historico. Na pratica, o IBGE ja publica o qx pronto, por idade e sexo,
em cada edicao anual da Tabua Completa -- e essas edicoes existem desde
1998. Usar a serie de tabuas prontas entrega o mesmo resultado (qx real
por idade/sexo/ano) sem depender de baixar e processar o microdado bruto
do SIM (arquivos DBC por UF/ano, dezenas a centenas de MB, formato que
muda de biblioteca de acesso com frequencia -- foi exatamente a fonte do
erro de sintaxe do pysus identificado no plano de dados reais). Se no
futuro o Passo 6 precisar do dado individual (para segmentar por outra
variavel que a tabua pronta do IBGE nao cobre), a extracao do SIM bruto
fica como trabalho futuro -- nao foi construida aqui.

Confirmado contra o FTP de verdade (nao suposto): o layout dos arquivos
muda de extensao ao longo dos anos, sempre nesse padrao:
  1998-2001  Tabua_Completas_de_Mortalidade_{ano}/*.zip (fora de escopo)
  2002-2014  Tabuas_Completas_de_Mortalidade_{ano}/*.zip (fora de escopo)
  2015-2020  Tabuas_Completas_de_Mortalidade_{ano}/xls/*.xls
  2021-2024  Tabuas_Completas_de_Mortalidade_{ano}/xlsx/*.xlsx
Este extrator cobre só 2015-2024 (dez anos, xls/xlsx direto, sem
descompactar zip) -- suficiente para o Passo 6 detectar tendencia, e sem
a fragilidade extra de lidar com um terceiro formato de arquivo so para
ganhar mais dez anos de historico.

Uso:
    python extrator_ibge_historico.py
    python extrator_ibge_historico.py --ano-inicio 2018 --ano-fim 2024
"""

import argparse
from pathlib import Path

import pandas as pd
import requests

PASTA_RAIZ = Path(__file__).resolve().parent.parent / "docs" / "referencias" / "ibge_historico"
BASE_URL = "https://ftp.ibge.gov.br/Tabuas_Completas_de_Mortalidade/Tabuas_Completas_de_Mortalidade_{ano}"

# Extensao por ano, confirmada contra o FTP real em 30/set/2026 (ver
# docstring do modulo). no site, o ano vira subpasta xls/ ou xlsx/.
EXTENSAO_POR_ANO = {ano: "xls" for ano in range(2015, 2021)}
EXTENSAO_POR_ANO.update({ano: "xlsx" for ano in range(2021, 2025)})

ARQUIVOS = {"Ambos": "ambos_os_sexos", "M": "homens", "F": "mulheres"}

ANO_MIN_SUPORTADO = min(EXTENSAO_POR_ANO)
ANO_MAX_SUPORTADO = max(EXTENSAO_POR_ANO)


class ExtracaoIbgeError(RuntimeError):
    """Falha de transporte ou de layout inesperado num arquivo do IBGE."""


def _url_arquivo(ano, categoria):
    ext = EXTENSAO_POR_ANO.get(ano)
    if ext is None:
        raise ValueError(
            f"Ano {ano} fora do intervalo suportado por este extrator "
            f"({ANO_MIN_SUPORTADO}-{ANO_MAX_SUPORTADO}). Anos anteriores a "
            "2015 vêm em .zip e não são lidos aqui -- ver docstring do módulo."
        )
    nome = ARQUIVOS[categoria]
    return f"{BASE_URL.format(ano=ano)}/{ext}/{nome}.{ext}"


def baixar_ano(ano, pasta_destino=PASTA_RAIZ, timeout=30):
    """Baixa os 3 arquivos (Ambos/M/F) de um ano e devolve os caminhos locais.

    Não baixa de novo se o arquivo já existe -- os arquivos do IBGE não
    mudam depois de publicados (mesma prática do Passo 3 com
    docs/referencias/).
    """
    destino = Path(pasta_destino) / str(ano)
    destino.mkdir(parents=True, exist_ok=True)
    ext = EXTENSAO_POR_ANO[ano]

    caminhos = {}
    for categoria in ARQUIVOS:
        caminho = destino / f"{ARQUIVOS[categoria]}.{ext}"
        if not caminho.exists():
            url = _url_arquivo(ano, categoria)
            resposta = requests.get(url, timeout=timeout)
            if resposta.status_code != 200:
                raise ExtracaoIbgeError(
                    f"HTTP {resposta.status_code} ao buscar {url}"
                )
            caminho.write_bytes(resposta.content)
        caminhos[categoria] = caminho
    return caminhos


def carregar_tabua(caminho):
    """Lê idade (coluna A) e qx em fração (coluna B / 1000).

    Mesmo layout usado por benchmark_ibge.py (dados a partir da linha 7,
    colunas A:B) -- confirmado contra arquivo real de 2015 e de 2020
    nesta mesma extração, não só contra o de 2024 que o Passo 3 já usava.
    """
    df = pd.read_excel(
        caminho, sheet_name=0, header=None, skiprows=6,
        usecols="A:B", names=["idade", "qx_por_mil"],
    )
    df = df.dropna(subset=["idade"])
    df["idade"] = pd.to_numeric(df["idade"], errors="coerce")
    df = df.dropna(subset=["idade"])
    if df.empty:
        raise ExtracaoIbgeError(f"{caminho} foi lido vazio -- layout mudou?")
    df["idade"] = df["idade"].astype(int)
    df["qx"] = df["qx_por_mil"] / 1000
    return df[["idade", "qx"]]


def construir_serie_historica(ano_inicio=2015, ano_fim=2024, pasta_destino=PASTA_RAIZ):
    """Baixa (se preciso) e consolida qx por ano/sexo/idade num único DataFrame."""
    linhas = []
    for ano in range(ano_inicio, ano_fim + 1):
        caminhos = baixar_ano(ano, pasta_destino)
        for categoria, caminho in caminhos.items():
            tabua = carregar_tabua(caminho)
            tabua["ano"] = ano
            tabua["sexo"] = categoria
            linhas.append(tabua)
    serie = pd.concat(linhas, ignore_index=True)
    return serie[["ano", "sexo", "idade", "qx"]].sort_values(["sexo", "idade", "ano"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ano-inicio", type=int, default=2015)
    parser.add_argument("--ano-fim", type=int, default=2024)
    parser.add_argument(
        "--saida", type=Path,
        default=PASTA_RAIZ / "serie_historica_qx.csv",
    )
    args = parser.parse_args()

    serie = construir_serie_historica(args.ano_inicio, args.ano_fim)
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    serie.to_csv(args.saida, index=False)

    anos = serie["ano"].nunique()
    print(f"Série histórica construída: {anos} anos "
          f"({args.ano_inicio}-{args.ano_fim}), {len(serie)} linhas.")
    print(f"Arquivos brutos em: {PASTA_RAIZ}")
    print(f"CSV consolidado em: {args.saida}")

    # Checagem barata de tendência: qx aos 70 anos deveria cair ao longo
    # do tempo (mortalidade vem melhorando) -- se não cair, vale olhar
    # os arquivos brutos antes de usar a série no Passo 6.
    amostra = serie[(serie["sexo"] == "Ambos") & (serie["idade"] == 70)]
    if len(amostra) >= 2:
        primeiro = amostra.sort_values("ano").iloc[0]
        ultimo = amostra.sort_values("ano").iloc[-1]
        print(f"qx aos 70 anos (Ambos): {primeiro['ano']}={primeiro['qx']:.5f} "
              f"-> {ultimo['ano']}={ultimo['qx']:.5f} "
              f"({'melhora' if ultimo['qx'] < primeiro['qx'] else 'ATENÇÃO: piora'})")


if __name__ == "__main__":
    main()
