"""
Conexão com o banco do Passo 1 (mesmo Postgres, mesmas variáveis).
"""

import os
import psycopg2


def conectar():
    """Abre conexão usando as variáveis de ambiente padrão da Tribo 3."""
    return psycopg2.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5433"),
        dbname=os.environ.get("POSTGRES_DB", "tribo3"),
        user=os.environ.get("POSTGRES_USER", "tribo3"),
        password=os.environ.get("POSTGRES_PASSWORD", "tribo3_dev"),
    )
