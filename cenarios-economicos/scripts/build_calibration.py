"""Constroi um artefato versionado a partir de snapshots ja coletados."""

import argparse
from datetime import date
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.calibration.artifact import CalibrationError, build_calibration_artifact


def iso_date(value):
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            "Use uma data valida no formato YYYY-MM-DD."
        ) from None


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bacen-snapshot", required=True, type=Path)
    parser.add_argument("--ibovespa-snapshot", required=True, type=Path)
    parser.add_argument("--anbima-snapshot", type=Path)
    parser.add_argument(
        "--allow-experimental-anbima",
        action="store_true",
        help="Autoriza explicitamente o consumo do snapshot produzido pelo spike.",
    )
    parser.add_argument("--cutoff", required=True, type=iso_date, dest="cutoff_date")
    parser.add_argument("--calibration-id", required=True)
    parser.add_argument("--calibration-version", required=True)
    parser.add_argument("--responsible", required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/calibrated/economic"),
        help="Pasta que recebera o diretorio imutavel da calibracao.",
    )
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.allow_experimental_anbima and args.anbima_snapshot is None:
        parser.error("--allow-experimental-anbima exige --anbima-snapshot")
    try:
        destination = build_calibration_artifact(
            args.output,
            args.bacen_snapshot,
            args.ibovespa_snapshot,
            args.cutoff_date,
            args.calibration_id,
            args.calibration_version,
            args.responsible,
            anbima_snapshot=args.anbima_snapshot,
            allow_experimental_anbima=args.allow_experimental_anbima,
        )
    except (CalibrationError, ValueError, OSError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
