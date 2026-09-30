# -*- coding: utf-8 -*-
"""Contrato de consumo do Passo 6 para os Passos 7/8 (docs/interfaces_interpassos.md, §3.1/§3.2).

Não recalcula nada por conta própria: chama exatamente as mesmas funções que
`scripts/main.py` já chama, na mesma ordem, e devolve os resultados em
estruturas simples (dict/list de tipos nativos) prontas para virar JSON --
sem numpy.ndarray, sem objetos de modelo. Cada valor devolvido tem uma
contrapartida direta num CSV/MD já gerado em `docs/`; este módulo não
inventa nenhuma métrica nova.

Ambas as funções são "no-args" de propósito: reproduzem o comportamento
padrão do pipeline (mesma fonte histórica priorizada por
`carregar_dados()` -- IBGE real, depois HMD, Postgres só como último
recurso, ver `dados/ingestao_passos.py`). Quem quiser rodar sobre um
subconjunto diferente de idades hoje precisa importar as funções de
`scripts/` diretamente; não é o caso de uso que este contrato cobre.

Uso:
    from contracts.api_modelos import obter_parametros_para_passo7, obter_dados_para_passo8
"""

import sys
from pathlib import Path

PASTA_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(PASTA_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(PASTA_SCRIPTS))

from dados.series_temporais import carregar_dados  # noqa: E402
from backtest.backtest_temporal import (  # noqa: E402
    separar_treino_holdout, avaliar_previsoes, executar_backtest,
)
from modelos.baseline import treinar_baseline, projetar_baseline  # noqa: E402
from modelos.lee_carter import treinar_lee_carter, projetar_lee_carter  # noqa: E402


class ContratoPasso6Error(RuntimeError):
    """Falha ao montar um dos dois contratos -- geralmente falta de dado histórico."""


def obter_parametros_para_passo7():
    """Decomposição de Lee-Carter para explicabilidade (SHAP/ALE) no Passo 7.

    Treina Lee-Carter sobre TODA a série histórica disponível (mesmo
    treino que `projecao/tabua_geracional.py` usa para o modelo final),
    independente de qual modelo venceu o backtest -- o Passo 7 quer
    explicar o padrão de mortalidade em si (perfil por idade, índice
    temporal), não o modelo de produção escolhido; Lee-Carter é a
    decomposição interpretável disponível aqui, o Baseline não tem um
    "beta_x" equivalente pra explicar.

    Retorna dict com:
        idades (list[int]): idades cobertas pela matriz, na ordem de ax/bx.
        alpha_x (list[float]): perfil médio de mortalidade por idade (log-mx).
        beta_x (list[float]): sensibilidade etária ao índice temporal kappa_t.
        kappa_t (list[float]): trajetória histórica do índice temporal, um
            valor por ano em `anos_historicos`, na mesma ordem.
        anos_historicos (list[int]): anos cobertos por kappa_t.
        drift (float): taxa anual de tendência estimada de kappa_t.
        variancia_explicada (float): fração da variância do SVD capturada
            pelo 1º componente -- quanto mais perto de 1.0, mais o modelo
            uniforme (mesma direção pra todas as idades) explica a série.
        origem_dados (str): rótulo de proveniência devolvido por
            `carregar_dados()` -- inclui aviso explícito se a fonte for o
            Postgres sem tendência real (ver `dados/ingestao_passos.py`).
    """
    linhas, origem = carregar_dados()
    if not linhas:
        raise ContratoPasso6Error("Nenhuma linha histórica disponível para ajustar Lee-Carter.")

    modelo = treinar_lee_carter(linhas)

    return {
        "idades": list(modelo["idades"]),
        "alpha_x": [float(v) for v in modelo["ax"]],
        "beta_x": [float(v) for v in modelo["bx"]],
        "kappa_t": [float(v) for v in modelo["kt"]],
        "anos_historicos": list(modelo["anos"]),
        "drift": float(modelo["drift"]),
        "variancia_explicada": float(modelo["variancia_explicada"]),
        "origem_dados": origem,
    }


def obter_dados_para_passo8():
    """Métricas de erro fora da amostra e previsões vs. observado no holdout, para o Passo 8.

    Roda o mesmo protocolo de `backtest_temporal.executar_backtest()` (que
    já é o que `scripts/main.py` chama), e adicionalmente reconstrói a
    lista célula a célula de previsão vs. observado do holdout para o
    modelo campeão -- `executar_backtest()` sozinho só devolve as métricas
    agregadas (RMSE/MAE/MAPE/Chi2), não as previsões individuais; o Passo 8
    precisa das duas coisas (agregado pra decidir, granular pra montar
    ensemble/CVaR).

    Retorna dict com:
        modelo_campeao (str): "Baseline" ou "Lee-Carter".
        justificativa (str): mesmo texto que já vai pro relatório do backtest.
        anos_treino / anos_holdout (list[int]).
        metricas_baseline / metricas_lee_carter (dict): rmse, mae, mape,
            chi2_obitos, n_celulas -- os mesmos 4 números que o §3.2 pede
            (RMSE, MAE, MAPE, Chi2), um bloco por modelo.
        previsoes_holdout_campeao (list[dict]): uma linha por (idade, ano)
            do holdout, com idade, ano, q_observado, q_previsto, obitos,
            exposicao -- usando o modelo campeão, o mesmo que
            `projecao/tabua_geracional.py` adota pra virar produção.
        origem_dados (str): idem `obter_parametros_para_passo7`.
    """
    linhas, origem = carregar_dados()
    if not linhas:
        raise ContratoPasso6Error("Nenhuma linha histórica disponível para rodar o backtest.")

    resultado = executar_backtest(linhas)

    # executar_backtest() já fez esse split internamente; refeito aqui só
    # pra expor as previsões granulares do campeão, que a função não
    # devolve (ver docstring). Mesma função, mesmo resultado -- não é uma
    # segunda fonte de verdade.
    _, _, treino, holdout = separar_treino_holdout(linhas)
    campeao = resultado["modelo_campeao"]

    if campeao == "Baseline":
        modelo = treinar_baseline(treino)
        projetar = lambda idade, ano: projetar_baseline(modelo, idade, ano)  # noqa: E731
    else:
        modelo = treinar_lee_carter(treino)
        projetar = lambda idade, ano: projetar_lee_carter(modelo, idade, ano)  # noqa: E731

    previsoes_campeao = [
        {
            "idade": reg["idade"],
            "ano": reg["ano"],
            "q_observado": reg["qx"],
            "q_previsto": projetar(reg["idade"], reg["ano"]),
            "obitos": reg["obitos"],
            "exposicao": reg["exposicao_central"],
        }
        for reg in holdout
    ]

    return {
        "modelo_campeao": campeao,
        "justificativa": resultado["justificativa"],
        "anos_treino": list(resultado["anos_treino"]),
        "anos_holdout": list(resultado["anos_holdout"]),
        "metricas_baseline": dict(resultado["baseline"]),
        "metricas_lee_carter": dict(resultado["lee_carter"]),
        "previsoes_holdout_campeao": previsoes_campeao,
        "origem_dados": origem,
    }


if __name__ == "__main__":
    # Smoke test manual: roda os dois contratos e imprime um resumo --
    # não substitui tests/test_api_modelos.py, só serve pra conferência
    # rápida de quem estiver mexendo no módulo.
    p7 = obter_parametros_para_passo7()
    print(f"[Passo 7] {len(p7['idades'])} idades, "
          f"{len(p7['anos_historicos'])} anos históricos, "
          f"drift={p7['drift']:.4f}, origem={p7['origem_dados']}")

    p8 = obter_dados_para_passo8()
    print(f"[Passo 8] campeão={p8['modelo_campeao']}, "
          f"{len(p8['previsoes_holdout_campeao'])} previsões no holdout, "
          f"RMSE baseline={p8['metricas_baseline']['rmse']}, "
          f"RMSE lee-carter={p8['metricas_lee_carter']['rmse']}")
