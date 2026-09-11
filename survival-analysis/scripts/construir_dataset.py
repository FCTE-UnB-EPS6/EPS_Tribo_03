"""
Construção do dataset analítico de sobrevivência — Passo 2

Extrai dados de participante, evento e exposição do Postgres do Passo 1
e monta um dataset analítico para survival analysis, com:
  - tempo observado (em anos)
  - indicador de evento (óbito = 1, censura = 0)
  - covariáveis: idade_ingresso, sexo, plano_tipo, submassa

Pode rodar contra o banco (--fonte banco) ou gerar dados sintéticos
localmente para desenvolvimento sem Docker (--fonte local, padrão).

Uso:
    python scripts/construir_dataset.py
    python scripts/construir_dataset.py --fonte banco
    python scripts/construir_dataset.py --n-participantes 500 --seed 42
"""

import argparse
import os
import random
import sys
from datetime import date, timedelta

import pandas as pd


def extrair_do_banco():
    """Extrai dataset analítico diretamente do Postgres do Passo 1."""
    try:
        import psycopg2
    except ImportError:
        print("psycopg2 não instalado. Use: pip install psycopg2-binary")
        sys.exit(1)

    conn = psycopg2.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5433"),
        dbname=os.environ.get("POSTGRES_DB", "tribo3"),
        user=os.environ.get("POSTGRES_USER", "tribo3"),
        password=os.environ.get("POSTGRES_PASSWORD", "tribo3_dev"),
    )

    query = """
    WITH ultimo_snapshot AS (
        SELECT DISTINCT ON (participante_id)
            participante_id, plano_tipo, submassa, sexo,
            data_nascimento, data_ingresso, data_desligamento,
            status_atual
        FROM participante
        WHERE data_vigencia_fim IS NULL
        ORDER BY participante_id, versao_registro DESC
    ),
    evento_obito AS (
        SELECT participante_id, MIN(data_evento) AS data_obito
        FROM evento
        WHERE tipo_evento = 'obito'
        GROUP BY participante_id
    )
    SELECT
        p.participante_id,
        p.sexo,
        p.plano_tipo,
        p.submassa,
        p.data_nascimento,
        p.data_ingresso,
        p.data_desligamento,
        p.status_atual,
        e.data_obito
    FROM ultimo_snapshot p
    LEFT JOIN evento_obito e ON e.participante_id = p.participante_id
    """

    df = pd.read_sql(query, conn)
    conn.close()
    return df


def gerar_dados_locais(n_participantes=300, seed=42):
    """Gera dados sintéticos localmente, espelhando o gerador do Passo 1."""
    rng = random.Random(seed)
    data_ref = date(2026, 8, 31)

    registros = []
    for i in range(n_participantes):
        sexo = rng.choice(["M", "F"])
        plano = rng.choice(["BD", "CD", "CV"])
        submassa = rng.choice(["Plano A", "Plano B", "Plano C"])
        nascimento = data_ref - timedelta(days=rng.randint(20, 70) * 365)
        ingresso = nascimento + timedelta(days=rng.randint(18, 40) * 365)
        if ingresso >= data_ref:
            ingresso = data_ref - timedelta(days=rng.randint(30, 365))

        status = rng.choices(
            ["ativo", "aposentado", "desligado", "obito", "pensionista"],
            weights=[0.55, 0.20, 0.15, 0.05, 0.05],
            k=1,
        )[0]

        data_desligamento = None
        data_obito = None
        if status == "obito":
            data_obito = ingresso + timedelta(days=rng.randint(30, (data_ref - ingresso).days))
            data_desligamento = data_obito
        elif status == "desligado":
            data_desligamento = ingresso + timedelta(days=rng.randint(30, (data_ref - ingresso).days))

        registros.append({
            "participante_id": f"p{i:04d}",
            "sexo": sexo,
            "plano_tipo": plano,
            "submassa": submassa,
            "data_nascimento": nascimento,
            "data_ingresso": ingresso,
            "data_desligamento": data_desligamento,
            "status_atual": status,
            "data_obito": data_obito,
        })

    return pd.DataFrame(registros)


def construir_dataset_analitico(df, data_referencia=None):
    """Transforma dados brutos no dataset analítico de survival.

    Retorna DataFrame com colunas:
      - tempo_observado: anos entre ingresso e evento/censura
      - evento: 1 se óbito, 0 se censurado
      - idade_ingresso: idade em anos na data de ingresso
      - sexo_M: 1 se masculino, 0 se feminino
      - plano_BD, plano_CD, plano_CV: one-hot encoding
      - submassa_A, submassa_B, submassa_C: one-hot encoding
    """
    if data_referencia is None:
        data_referencia = date(2026, 8, 31)

    for col in ["data_nascimento", "data_ingresso", "data_desligamento", "data_obito"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col])

    data_ref = pd.Timestamp(data_referencia)

    evento = (df["status_atual"] == "obito").astype(int)

    data_fim = df["data_obito"].copy()
    mask_censura = data_fim.isna()
    data_fim[mask_censura & df["data_desligamento"].notna()] = df.loc[
        mask_censura & df["data_desligamento"].notna(), "data_desligamento"
    ]
    data_fim[data_fim.isna()] = data_ref

    tempo_dias = (data_fim - df["data_ingresso"]).dt.days
    tempo_observado = tempo_dias / 365.25
    tempo_observado = tempo_observado.clip(lower=0.01)

    idade_ingresso = (df["data_ingresso"] - df["data_nascimento"]).dt.days / 365.25

    resultado = pd.DataFrame({
        "participante_id": df["participante_id"],
        "tempo_observado": tempo_observado.round(4),
        "evento": evento,
        "idade_ingresso": idade_ingresso.round(2),
        "sexo_M": (df["sexo"] == "M").astype(int),
        "plano_BD": (df["plano_tipo"] == "BD").astype(int),
        "plano_CD": (df["plano_tipo"] == "CD").astype(int),
        "plano_CV": (df["plano_tipo"] == "CV").astype(int),
        "submassa_A": (df["submassa"] == "Plano A").astype(int),
        "submassa_B": (df["submassa"] == "Plano B").astype(int),
        "submassa_C": (df["submassa"] == "Plano C").astype(int),
    })

    return resultado


def main():
    parser = argparse.ArgumentParser(description="Construir dataset analítico de sobrevivência")
    parser.add_argument("--fonte", choices=["banco", "local"], default="local",
                        help="Fonte dos dados: 'banco' (Postgres) ou 'local' (geração sintética)")
    parser.add_argument("--n-participantes", type=int, default=300)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--data-referencia", type=date.fromisoformat, default=date(2026, 8, 31))
    parser.add_argument("--saida", default=None, help="Caminho do CSV de saída")
    args = parser.parse_args()

    if args.fonte == "banco":
        print("Extraindo dados do Postgres...")
        df_bruto = extrair_do_banco()
    else:
        print(f"Gerando {args.n_participantes} participantes localmente (seed={args.seed})...")
        df_bruto = gerar_dados_locais(args.n_participantes, args.seed)

    df = construir_dataset_analitico(df_bruto, args.data_referencia)

    saida = args.saida or os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "data", "dataset_survival.csv"
    )
    os.makedirs(os.path.dirname(saida), exist_ok=True)
    df.to_csv(saida, index=False)

    print(f"\nDataset analítico salvo em {saida}")
    print(f"  {len(df)} registros")
    print(f"  Eventos (óbito): {df['evento'].sum()} ({df['evento'].mean():.1%})")
    print(f"  Censurados: {(1 - df['evento']).sum():.0f} ({1 - df['evento'].mean():.1%})")
    print(f"  Tempo médio observado: {df['tempo_observado'].mean():.2f} anos")
    print(f"  Idade média ao ingresso: {df['idade_ingresso'].mean():.1f} anos")


if __name__ == "__main__":
    main()
