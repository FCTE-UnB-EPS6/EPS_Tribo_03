"""Conexão com o banco do Passo 1 (mesmo Postgres, mesmas variáveis).

Cópia deliberada de ambiente-de-dados/scripts/db.py::conectar() — os dois
diretórios são de duplas diferentes, cada um com seu próprio scripts/, e
duplicar essa função de ~10 linhas evita acoplar o Passo 5 ao layout interno
do Passo 1. Se algo mudar aqui (host, porta, nome do banco), replicar lá
também.
"""

import os

import psycopg2


def conectar():
    """Abre conexão usando as mesmas variáveis de ambiente do Passo 1.

    Default de porta 5433 porque é o que o docker-compose de
    ambiente-de-dados publica no host (ver ambiente-de-dados/.env.example).
    """
    return psycopg2.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5433"),
        dbname=os.environ.get("POSTGRES_DB", "tribo3"),
        user=os.environ.get("POSTGRES_USER", "tribo3"),
        password=os.environ.get("POSTGRES_PASSWORD", "tribo3_dev"),
    )
