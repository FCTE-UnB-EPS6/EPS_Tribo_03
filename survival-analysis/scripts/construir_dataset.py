"""Dataset de óbito: tabelas finais do Passo 1; gerador local só para testes.

Uso oficial: --fonte banco --data-referencia AAAA-MM-DD --identificacao-fonte LOTE
Nenhuma falha de conexão aciona geração local. Não modifica o banco.
"""
import argparse
from datetime import date, datetime, timedelta, timezone
import os
from pathlib import Path
import random
import sys

import pandas as pd
from registro import ambiente, salvar_json, sha256


def extrair_do_banco():
    import psycopg2
    conn = psycopg2.connect(
        host=os.environ.get('PGHOST', 'localhost'),
        port=os.environ.get('PGPORT', '5433'),
        dbname=os.environ.get('POSTGRES_DB', 'tribo3'),
        user=os.environ.get('POSTGRES_USER', 'tribo3'),
        password=os.environ.get('POSTGRES_PASSWORD', 'tribo3_dev'),
        connect_timeout=5,
    )
    # Snapshot atual: esta extração NÃO reconstrói conhecimento bitemporal histórico.
    query = """
    WITH ultimo_snapshot AS (
        SELECT DISTINCT ON (participante_id)
            participante_id, plano_tipo, submassa, sexo, data_nascimento,
            data_ingresso, data_desligamento, status_atual, versao_registro
        FROM participante
        WHERE data_vigencia_fim IS NULL
        ORDER BY participante_id, versao_registro DESC
    ), evento_obito AS (
        SELECT participante_id, MIN(data_evento) AS data_obito
        FROM evento WHERE tipo_evento = 'obito' GROUP BY participante_id
    ), exposicao_resumo AS (
        SELECT participante_id, SUM(tempo_exposto) AS exposicao_oficial_anos,
               COUNT(*) AS n_exposicoes, MAX(data_base) AS exposicao_data_fim
        FROM exposicao GROUP BY participante_id
    )
    SELECT p.*, e.data_obito, x.exposicao_oficial_anos,
           x.n_exposicoes, x.exposicao_data_fim
    FROM ultimo_snapshot p
    LEFT JOIN evento_obito e USING (participante_id)
    LEFT JOIN exposicao_resumo x USING (participante_id)
    ORDER BY p.participante_id
    """
    try:
        conn.set_session(readonly=True)
        with conn.cursor() as cur:
            cur.execute(query)
            return pd.DataFrame(cur.fetchall(), columns=[c.name for c in cur.description])
    finally:
        conn.close()


def gerar_dados_locais(n_participantes=300, seed=42, data_referencia=date(2026, 8, 31)):
    """Fixture sintética independente; não reproduz geração/curadoria do Passo 1."""
    if n_participantes <= 0:
        raise ValueError('n_participantes deve ser positivo')
    rng = random.Random(seed)
    registros = []
    for i in range(n_participantes):
        nascimento = data_referencia - timedelta(days=rng.randint(20, 70) * 365)
        inicio = nascimento + timedelta(days=18 * 365)
        limite = data_referencia - timedelta(days=30)
        ingresso = inicio + timedelta(days=rng.randint(0, (limite - inicio).days))
        status = rng.choices(['ativo', 'aposentado', 'desligado', 'obito', 'pensionista'],
                             weights=[.55, .20, .15, .05, .05])[0]
        fim = ingresso + timedelta(days=rng.randint(1, (data_referencia - ingresso).days))
        registros.append(dict(participante_id=f'local-{i:06d}', sexo=rng.choice(['M', 'F']),
            plano_tipo=rng.choice(['BD', 'CD', 'CV']),
            submassa=rng.choice(['Plano A', 'Plano B', 'Plano C']),
            data_nascimento=nascimento, data_ingresso=ingresso, status_atual=status,
            data_desligamento=fim if status in ['desligado', 'obito'] else None,
            data_obito=fim if status == 'obito' else None))
    return pd.DataFrame(registros)


def construir_dataset_analitico(df, data_referencia=None, retornar_exclusoes=False):
    """Uma linha por pessoa; exclui inconsistências com motivo, sem imputar óbito.

    Óbito válido até referência/saída é evento. Saída anterior censura, inclusive
    se houver óbito posterior. Aposentadoria/invalidez não encerram acompanhamento.
    Empate óbito/saída é óbito. Duração zero/negativa é excluída, nunca truncada.
    """
    ref = pd.Timestamp(data_referencia or date(2026, 8, 31))
    df = df.copy().reset_index(drop=True)
    required = ['participante_id', 'data_nascimento', 'data_ingresso',
                'data_desligamento', 'data_obito', 'status_atual', 'sexo', 'plano_tipo', 'submassa']
    missing = sorted(set(required) - set(df.columns))
    if missing:
        raise ValueError(f'Colunas ausentes: {missing}')
    if df.participante_id.isna().any() or df.participante_id.duplicated().any():
        raise ValueError('IDs ausentes ou duplicados: verificar snapshots/junções antes de continuar')
    motivos = [[] for _ in range(len(df))]
    def marcar(mask, motivo):
        for i in df.index[mask.fillna(False)]:
            motivos[i].append(motivo)
    for col in ['data_nascimento', 'data_ingresso', 'data_desligamento', 'data_obito']:
        raw = df[col]
        df[col] = pd.to_datetime(raw, errors='coerce')
        marcar(raw.notna() & df[col].isna(), f'{col}_invalida')
    for col in ['data_nascimento', 'data_ingresso']:
        marcar(df[col].isna(), f'{col}_ausente')
    marcar(df.data_nascimento >= df.data_ingresso, 'nascimento_nao_anterior_ingresso')
    marcar(df.data_ingresso >= ref, 'ingresso_sem_acompanhamento_na_referencia')
    for col in ['data_obito', 'data_desligamento']:
        marcar(df[col] < df.data_ingresso, f'{col}_anterior_ingresso')
    marcar(df.status_atual.eq('obito') & df.data_obito.isna(), 'obito_sem_data')
    marcar(df.status_atual.eq('desligado') & df.data_desligamento.isna(), 'desligado_sem_data')
    for col, values in {'sexo':['M', 'F'], 'plano_tipo':['BD', 'CD', 'CV'],
                        'submassa':['Plano A', 'Plano B', 'Plano C'],
                        'status_atual':['ativo', 'aposentado', 'desligado', 'obito', 'pensionista']}.items():
        marcar(~df[col].isin(values), f'{col}_fora_dominio')
    fim = pd.DataFrame({'referencia': ref, 'saida': df.data_desligamento,
                        'obito': df.data_obito}).min(axis=1)
    evento = df.data_obito.notna() & df.data_obito.eq(fim) & df.data_obito.le(ref)
    marcar(fim <= df.data_ingresso, 'duracao_nao_positiva')
    df['data_fim'] = fim
    df['data_referencia'] = ref
    df['evento'] = evento.astype(int)
    df['tempo_observado'] = (fim - df.data_ingresso).dt.days / 365.25
    df['idade_ingresso'] = (df.data_ingresso - df.data_nascimento).dt.days / 365.25
    df['sexo_M'] = df.sexo.eq('M').astype(int)
    for value in ['BD', 'CD', 'CV']:
        df[f'plano_{value}'] = df.plano_tipo.eq(value).astype(int)
    for value in ['A', 'B', 'C']:
        df[f'submassa_{value}'] = df.submassa.eq(f'Plano {value}').astype(int)
    # A exposição oficial usa dias inclusivos e teto anual 1.0: não é idêntica
    # à duração contínua. Guardamos a diferença para inspeção, sem alterar tempos.
    if 'exposicao_oficial_anos' in df:
        df['exposicao_oficial_anos'] = pd.to_numeric(df.exposicao_oficial_anos)
        df['diferenca_exposicao_anos'] = df.exposicao_oficial_anos - df.tempo_observado
    exclusoes = pd.DataFrame({'participante_id': df.participante_id,
                              'motivos': [';'.join(m) for m in motivos]})
    validos = exclusoes.motivos.eq('')
    resultado = df.loc[validos].reset_index(drop=True)
    exclusoes = exclusoes.loc[~validos].reset_index(drop=True)
    if retornar_exclusoes:
        return resultado, exclusoes
    if len(exclusoes):
        raise ValueError(f'{len(exclusoes)} registros inconsistentes; use retornar_exclusoes=True para auditar')
    return resultado


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fonte', choices=['banco', 'local'], default='banco')
    parser.add_argument('--data-referencia', type=date.fromisoformat, required=True)
    parser.add_argument('--identificacao-fonte', help='Lote/versão do Passo 1; descrição declarada pelo operador')
    parser.add_argument('--n-participantes', type=int, default=300)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--saida', type=Path)
    args = parser.parse_args()
    if args.fonte == 'banco' and not args.identificacao_fonte:
        parser.error('--identificacao-fonte é obrigatório para registrar a extração oficial')
    raw = (extrair_do_banco() if args.fonte == 'banco' else
           gerar_dados_locais(args.n_participantes, args.seed, args.data_referencia))
    df, excl = construir_dataset_analitico(raw, args.data_referencia, retornar_exclusoes=True)
    base = Path(__file__).resolve().parents[1] / 'data'
    out = args.saida or base / ('dataset_survival.csv' if args.fonte == 'banco' else 'local/dataset_survival.csv')
    out.parent.mkdir(parents=True, exist_ok=True)
    raw.to_csv(out.with_suffix('.bruto.csv'), index=False)
    excl.to_csv(out.with_suffix('.exclusoes.csv'), index=False)
    df['fonte_dados'] = args.fonte
    df.to_csv(out, index=False)
    meta = dict(fonte=args.fonte, identificacao_fonte=args.identificacao_fonte,
                identificacao_declarada=True, data_referencia=str(args.data_referencia),
                extraido_em=datetime.now(timezone.utc).isoformat(),
                comando=sys.argv, n_bruto=len(raw), n_analitico=len(df),
                n_excluidos=len(excl), n_obitos=int(df.evento.sum()),
                dataset_sha256=sha256(out), bruto_sha256=sha256(out.with_suffix('.bruto.csv')),
                ambiente=ambiente())
    if args.fonte == 'local':
        meta.update(seed=args.seed, n_solicitado=args.n_participantes,
                    aviso='Fixture independente; não é a massa oficial do Passo 1')
    if 'diferenca_exposicao_anos' in df:
        meta['exposicao'] = dict(n_sem_exposicao=int(df.exposicao_oficial_anos.isna().sum()),
            n_diferencas_acima_003_anos=int(df.diferenca_exposicao_anos.abs().gt(.03).sum()),
            aviso='Diagnóstico; diferenças podem refletir curadoria, dias inclusivos ou referência distinta')
    salvar_json(out.with_suffix('.metadata.json'), meta)
    print(f'{out}: fonte={args.fonte}; n={len(df)}; óbitos={df.evento.sum()}; exclusões={len(excl)}')
    if df.empty:
        raise SystemExit('Nenhuma linha válida; ver exclusões. Modelos não devem ser executados.')


if __name__ == '__main__':
    main()
