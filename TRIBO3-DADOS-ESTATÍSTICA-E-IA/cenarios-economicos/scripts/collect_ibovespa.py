"""Coleta um extrato auditavel do Ibovespa fornecido pelo Yahoo Finance."""

import argparse
from datetime import date
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.data_sources.ibovespa import IbovespaCollectionError, collect_snapshot


def iso_date(value):
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            "Use uma data valida no formato YYYY-MM-DD."
        ) from None


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--start",
        type=iso_date,
        default=date(2015, 1, 1),
        help="Data inicial inclusiva em YYYY-MM-DD.",
    )
    parser.add_argument(
        "--end",
        type=iso_date,
        default=date.today(),
        help="Data final inclusiva em YYYY-MM-DD; padrao: hoje.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/raw/ibovespa"),
        help="Pasta que recebera um novo diretorio de snapshot.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30,
        help="Timeout da consulta em segundos.",
    )
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        destination = collect_snapshot(
            args.output,
            args.start,
            args.end,
            timeout=args.timeout,
        )
    except (IbovespaCollectionError, ValueError, OSError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
