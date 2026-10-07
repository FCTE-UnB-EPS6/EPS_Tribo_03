"""Única entrada da análise de sobrevivência: Postgres, KM, Cox, RSF e evidências."""
import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
import shutil
import sys

import numpy as np

from scripts.avaliacao import COVARIAVEIS, dividir_temporal
from scripts.comparar_modelos import gerar_resultados_comparacao
from scripts.construir_dataset import extrair_e_salvar_dataset
from scripts.cox_ph import ajustar_cox, gerar_graficos, verificar_proporcionalidade
from scripts.diagnosticos import verificar_padrao_mortalidade
from scripts.kaplan_meier import gerar_resultados_km
from scripts.registro import NOTA_USO, ambiente, salvar_json, sha256, validar_procedencia
from scripts.relatorios import criterios_issue34, escrever_cards, verificar_pendencias


def executar_pipeline(*, saida, data_corte, horizonte=5., seed=42,
                      data_referencia=None, identificacao_fonte=None, dataset=None,
                      sobrescrever=False):
    """Executa as implementações diretamente, sem chamar scripts em subprocessos.

    Dataset existente deve ser extração rastreada do Postgres. A aplicação nunca
    usa gerar_dados_locais; fixtures e mocks ficam exclusivamente nos testes.
    """
    corte = date.fromisoformat(str(data_corte))
    ref = date.fromisoformat(str(data_referencia)) if data_referencia is not None else None
    if not np.isfinite(horizonte) or horizonte <= 0:
        raise ValueError('Horizonte deve ser positivo e finito')
    if dataset is None:
        if ref is None or not identificacao_fonte or not identificacao_fonte.strip():
            raise ValueError('Extração exige --data-referencia e --identificacao-fonte')
        if corte >= ref:
            raise ValueError('Corte deve anteceder referência')
    if sobrescrever and Path(saida).is_symlink():
        raise ValueError('Não é possível sobrescrever um link simbólico')
    out = Path(saida).resolve()
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        if not sobrescrever:
            raise ValueError('--saida deve ser pasta nova ou vazia; use --sobrescrever para substituir resultados anteriores')
        if dataset is not None and Path(dataset).resolve().is_relative_to(out):
            raise ValueError('Não é possível sobrescrever a pasta que contém o snapshot de entrada')
        manifesto = out/'manifesto_artefatos.json'
        if not manifesto.is_file():
            raise ValueError('--sobrescrever exige uma pasta de resultados concluídos com manifesto')
        anterior = json.loads(manifesto.read_text(encoding='utf-8'))
        if anterior.get('fonte') != 'banco' or not isinstance(anterior.get('arquivos'), dict):
            raise ValueError('Manifesto de resultados inválido; pasta preservada')
        arquivos = {str(p.relative_to(out)) for p in out.rglob('*') if p.is_file()}
        esperados = set(anterior['arquivos']) | {'manifesto_artefatos.json'}
        if arquivos != esperados or any(p.is_symlink() for p in out.rglob('*')) or out.is_symlink():
            raise ValueError('Pasta contém arquivos externos ao manifesto; pasta preservada')
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    etapas = []

    def etapa(nome, operacao):
        print(f'Executando {nome}...', flush=True)
        registro = dict(etapa=nome, inicio_utc=datetime.now(timezone.utc).isoformat())
        try:
            resultado = operacao()
        except Exception as exc:
            print(f'{type(exc).__name__}: {exc}', file=sys.stderr)
            registro.update(status='falha', tipo_erro=type(exc).__name__)
            etapas.append(registro)
            salvar_json(out/'falha_execucao.json', dict(status='erro_execucao', etapas=etapas,
                etapa=nome, tipo_erro=type(exc).__name__, nota_uso=NOTA_USO))
            raise RuntimeError(f'Etapa {nome} falhou ({type(exc).__name__}); confira os dados e a conexão. '
                               f'Diagnóstico: {out/"falha_execucao.json"}') from exc
        registro.update(status='concluida', fim_utc=datetime.now(timezone.utc).isoformat())
        etapas.append(registro)
        return resultado

    destino = out/'dataset_survival.csv'

    def preparar_dataset():
        if dataset is None:
            extrair_e_salvar_dataset(ref, identificacao_fonte, destino)
        else:
            origem = Path(dataset).resolve()
            _, meta_origem = validar_procedencia(origem)
            if ref is not None and str(ref) != meta_origem['data_referencia']:
                raise ValueError('Referência solicitada diverge do snapshot existente')
            if identificacao_fonte is not None and identificacao_fonte != meta_origem['identificacao_fonte']:
                raise ValueError('Identificação solicitada diverge do snapshot existente')
            for sufixo in ['.csv', '.metadata.json', '.bruto.csv', '.exclusoes.csv']:
                fonte = origem.with_suffix(sufixo)
                if fonte.exists():
                    shutil.copy2(fonte, destino.with_suffix(sufixo))
        df, meta = validar_procedencia(destino)
        # Falhar antes de produzir relatórios quando o corte não permite avaliar.
        dividir_temporal(df, corte)
        return df, meta

    df, meta = etapa('construir_dataset', preparar_dataset)
    etapa('kaplan_meier', lambda: gerar_resultados_km(df, out/'km'))
    avaliacao = etapa('comparar_modelos', lambda: gerar_resultados_comparacao(
        df, meta, destino, corte, horizonte, seed, out/'avaliacao'))

    def diagnostico_descritivo():
        cox, erro = None, None
        covs = [c for c in COVARIAVEIS if df[c].nunique() > 1]
        try:
            if df.evento.sum() < 2 or not covs:
                raise ValueError('Menos de dois eventos ou nenhuma covariável variável')
            cox = ajustar_cox(df, covs)
            pasta = out/'cox_descritivo'
            pasta.mkdir()
            cox.summary.to_csv(pasta/'coeficientes.csv')
            ph = verificar_proporcionalidade(cox, df, covs)
            if ph is not None:
                ph.summary.to_csv(pasta/'schoenfeld.csv')
            gerar_graficos(cox, str(pasta))
        except (ValueError, ArithmeticError) as exc:
            erro = str(exc)
        padrao = verificar_padrao_mortalidade(df, cox, horizonte)
        padrao['erro_cox_descritivo'] = erro
        salvar_json(out/'padrao_mortalidade.json', padrao)
        return padrao

    padrao = etapa('cox_descritivo', diagnostico_descritivo)
    pendencias = verificar_pendencias(meta, avaliacao, padrao)
    fechamento = dict(status='revisao_necessaria' if pendencias else 'pronto_para_revisao',
        status_execucao='concluida', criterios_issue34=criterios_issue34(avaliacao),
        pendencias=pendencias, executado_em=datetime.now(timezone.utc).isoformat(),
        comando=sys.argv, nota_uso=NOTA_USO, ambiente=ambiente(), etapas=etapas,
        revisao_humana='Pendente: dupla autora, consumidores 7/8 e governança T6',
        issue='FCTE-UnB-EPS6/estudos-populacionais#34')
    # Publicar fechamento somente depois que os cards forem escritos com sucesso.
    etapa('relatorios', lambda: escrever_cards(out, meta, avaliacao, padrao, fechamento))
    try:
        salvar_json(out/'fechamento.json', fechamento)
        salvar_json(out/'manifesto_artefatos.json', dict(versao='0.2.1', nota_uso=NOTA_USO,
            fonte='banco', dataset_sha256=sha256(destino), status=fechamento['status'],
            arquivos={str(p.relative_to(out)): sha256(p) for p in sorted(out.rglob('*')) if p.is_file()}))
    except Exception as exc:
        # Uma falha de gravação/integridade não pode deixar conclusão utilizável.
        (out/'fechamento.json').unlink(missing_ok=True)
        (out/'manifesto_artefatos.json').unlink(missing_ok=True)
        salvar_json(out/'falha_execucao.json', dict(status='erro_execucao', etapas=etapas,
            etapa='manifesto', tipo_erro=type(exc).__name__, nota_uso=NOTA_USO))
        raise RuntimeError(f'Falha ao finalizar evidências em {out}') from exc
    print(f"{fechamento['status']}: {out/'fechamento.json'}")
    print(f"Execução concluída: {len(df)} participantes, {int(df.evento.sum())} óbitos; "
          f"treino/teste {avaliacao['n_treino']}/{avaliacao['n_teste']}.")
    for motivo in pendencias:
        print(f'- {motivo}')
    return 2 if pendencias else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fonte', choices=['banco'], default='banco', help='Única fonte oficial aceita')
    parser.add_argument('--dataset', type=Path, help='Reavaliar snapshot Postgres com manifesto íntegro')
    parser.add_argument('--data-referencia', type=date.fromisoformat)
    parser.add_argument('--identificacao-fonte', help='Commit/lote/seed/n do Passo 1')
    parser.add_argument('--data-corte', type=date.fromisoformat, required=True)
    parser.add_argument('--horizonte', type=float, default=5.)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--saida', type=Path, default=Path('data/resultado'), help='Pasta de resultados (padrão: data/resultado)')
    parser.add_argument('--sobrescrever', action='store_true', help='Substituir resultados concluídos na mesma pasta')
    args = parser.parse_args(argv)
    try:
        return executar_pipeline(saida=args.saida, data_corte=args.data_corte,
            horizonte=args.horizonte, seed=args.seed, data_referencia=args.data_referencia,
            identificacao_fonte=args.identificacao_fonte, dataset=args.dataset,
            sobrescrever=args.sobrescrever)
    except ValueError as exc:
        parser.error(str(exc))
    except (RuntimeError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
