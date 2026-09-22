"""Prototipo auditavel para o download XML da ETTJ da ANBIMA.

Este modulo pertence a um spike. Ele comprova o contrato observado da fonte,
mas nao esta integrado ao fluxo de geracao de cenarios economicos.
"""

import argparse
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from pathlib import Path
import shutil
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4
import xml.etree.ElementTree as ET


SPIKE_VERSION = "0.1.0"
MANIFEST_VERSION = "1.0.0"
SOURCE_NAME = "ANBIMA - Estrutura a Termo das Taxas de Juros Estimada"
SOURCE_PAGE_URL = "https://www.anbima.com.br/informacoes/est-termo/CZ.asp"
DOWNLOAD_URL = "https://www.anbima.com.br/informacoes/est-termo/CZ-down.asp"
PARAMETER_NAMES = ("B1", "B2", "B3", "B4", "L1", "L2")
EXPECTED_GROUPS = {"PREFIXADOS", "IPCA"}


class AnbimaCollectionError(RuntimeError):
    """Falha de transporte ou publicacao do snapshot experimental."""


class AnbimaResponseError(AnbimaCollectionError):
    """Resposta da ANBIMA nao segue o contrato observado no spike."""


@dataclass(frozen=True)
class ETTJSummary:
    reference_date: str
    parameter_groups: tuple[str, ...]
    parameter_count: int
    vertex_count: int
    circular_rate_count: int
    fitting_error_count: int


def build_form_body(reference_date):
    """Monta o formulario observado no download oficial da ANBIMA."""
    if type(reference_date) is not date:
        raise ValueError("A data de referencia deve ser uma data.")
    return urlencode({
        "Idioma": "PT",
        "Dt_Ref": reference_date.strftime("%d/%m/%Y"),
        "saida": "xml",
    }).encode("ascii")


def fetch_bytes(reference_date, timeout=30):
    if type(timeout) not in (int, float) or isinstance(timeout, bool) or timeout <= 0:
        raise ValueError("O timeout deve ser um numero positivo.")

    request = Request(
        DOWNLOAD_URL,
        data=build_form_body(reference_date),
        headers={
            "Accept": "application/xml,text/xml;q=0.9,*/*;q=0.1",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": f"tribo3-anbima-ettj-spike/{SPIKE_VERSION}",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                raise AnbimaCollectionError(
                    f"ANBIMA respondeu com HTTP {response.status}."
                )
            return response.read()
    except HTTPError as exc:
        raise AnbimaCollectionError(
            f"ANBIMA respondeu com HTTP {exc.code}."
        ) from None
    except (URLError, TimeoutError, OSError):
        raise AnbimaCollectionError(
            "Nao foi possivel consultar a ANBIMA."
        ) from None


def _decimal_br(value, field, *, optional=False):
    if not isinstance(value, str):
        raise AnbimaResponseError(f"O campo {field} nao e texto.")
    value = value.strip()
    if not value:
        if optional:
            return None
        raise AnbimaResponseError(f"O campo {field} esta vazio.")
    try:
        parsed = Decimal(value.replace(".", "").replace(",", "."))
    except InvalidOperation:
        raise AnbimaResponseError(
            f"O campo {field} nao contem um decimal brasileiro valido."
        ) from None
    if not parsed.is_finite():
        raise AnbimaResponseError(f"O campo {field} nao e finito.")
    return parsed


def _positive_vertex(value, field):
    parsed = _decimal_br(value, field)
    if parsed != parsed.to_integral_value() or parsed <= 0:
        raise AnbimaResponseError(
            f"O campo {field} deve conter dias uteis inteiros e positivos."
        )
    return int(parsed)


def _parse_root(body):
    if not isinstance(body, bytes):
        raise AnbimaResponseError("O transportador deve retornar bytes.")
    if not body.strip():
        raise AnbimaResponseError(
            "A ANBIMA nao retornou dados para a data solicitada."
        )
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        raise AnbimaResponseError("A ANBIMA retornou XML invalido.") from None
    if root.tag != "CURVAZERO":
        raise AnbimaResponseError("A raiz XML esperada e CURVAZERO.")
    return root


def parse_response(body, expected_date=None):
    """Valida o XML sem alterar os bytes que serao guardados no snapshot."""
    if expected_date is not None and type(expected_date) is not date:
        raise ValueError("A data esperada deve ser uma data.")

    root = _parse_root(body)
    date_elements = root.findall("./DATA_REFERENCIA")
    if len(date_elements) != 1 or not date_elements[0].text:
        raise AnbimaResponseError("O XML deve conter uma data de referencia.")
    try:
        reference_date = datetime.strptime(
            date_elements[0].text.strip(), "%d/%m/%Y"
        ).date()
    except ValueError:
        raise AnbimaResponseError("A data de referencia e invalida.") from None
    if expected_date is not None and reference_date != expected_date:
        raise AnbimaResponseError(
            "A data retornada difere da data solicitada."
        )

    parameters = root.findall("./PARAMETROS/PARAMETRO")
    groups = [item.attrib.get("Grupo") for item in parameters]
    if len(parameters) != len(EXPECTED_GROUPS) or set(groups) != EXPECTED_GROUPS:
        raise AnbimaResponseError(
            "O XML deve conter parametros unicos para PREFIXADOS e IPCA."
        )
    for item in parameters:
        for name in PARAMETER_NAMES:
            _decimal_br(item.attrib.get(name), f"PARAMETRO.{name}")

    vertices = root.findall("./ETTJ/VERTICES")
    if not vertices:
        raise AnbimaResponseError("O XML nao contem vertices da ETTJ.")
    available_rates = {"IPCA": 0, "Prefixados": 0, "Inflacao": 0}
    previous_vertex = 0
    for index, item in enumerate(vertices):
        vertex = _positive_vertex(item.attrib.get("Vertice"), f"VERTICES[{index}].Vertice")
        if vertex <= previous_vertex:
            raise AnbimaResponseError("Os vertices da ETTJ nao estao crescentes.")
        previous_vertex = vertex
        for name in available_rates:
            value = _decimal_br(
                item.attrib.get(name), f"VERTICES[{index}].{name}", optional=True
            )
            if value is not None:
                available_rates[name] += 1
    if any(count == 0 for count in available_rates.values()):
        raise AnbimaResponseError(
            "Ao menos uma taxa de cada curva deve estar preenchida."
        )

    circular_rates = root.findall("./CIRCULAR_3316/CIRCULAR")
    if not circular_rates:
        raise AnbimaResponseError("O XML nao contem taxas circulares.")
    for index, item in enumerate(circular_rates):
        _positive_vertex(item.attrib.get("Vertices"), f"CIRCULAR[{index}].Vertices")
        _decimal_br(item.attrib.get("Taxa"), f"CIRCULAR[{index}].Taxa")

    fitting_errors = root.findall("./ERROS/ERRO")
    for index, item in enumerate(fitting_errors):
        _decimal_br(item.attrib.get("Erro"), f"ERRO[{index}].Erro")

    return ETTJSummary(
        reference_date=reference_date.isoformat(),
        parameter_groups=tuple(sorted(EXPECTED_GROUPS)),
        parameter_count=len(parameters),
        vertex_count=len(vertices),
        circular_rate_count=len(circular_rates),
        fitting_error_count=len(fitting_errors),
    )


def _utc_timestamp(value):
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("O horario da coleta deve possuir fuso horario.")
    return value.astimezone(timezone.utc)


def collect_snapshot(
    output_root,
    reference_date,
    *,
    fetcher=fetch_bytes,
    timeout=30,
    collected_at=None,
):
    """Executa uma coleta experimental e publica raw mais manifesto."""
    if type(reference_date) is not date:
        raise ValueError("A data de referencia deve ser uma data.")
    if type(timeout) not in (int, float) or isinstance(timeout, bool) or timeout <= 0:
        raise ValueError("O timeout deve ser um numero positivo.")

    collected_at = _utc_timestamp(collected_at or datetime.now(timezone.utc))
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    timestamp = collected_at.strftime("%Y%m%dT%H%M%SZ")
    snapshot_id = (
        f"anbima-ettj-{reference_date.isoformat()}-{timestamp}-{uuid4().hex[:12]}"
    )
    temporary = output_root / f".{snapshot_id}.tmp"
    destination = output_root / snapshot_id
    temporary.mkdir()

    try:
        body = fetcher(reference_date, timeout=timeout)
        summary = parse_response(body, expected_date=reference_date)
        relative_path = Path("raw") / f"ettj_{reference_date.isoformat()}.xml"
        raw_path = temporary / relative_path
        raw_path.parent.mkdir(parents=True)
        raw_path.write_bytes(body)

        manifest = {
            "schema_version": MANIFEST_VERSION,
            "snapshot_id": snapshot_id,
            "status": "experimental-spike",
            "collected_at": collected_at.isoformat().replace("+00:00", "Z"),
            "collector": {
                "name": "spikes.anbima_ettj.probe",
                "version": SPIKE_VERSION,
            },
            "source": {
                "name": SOURCE_NAME,
                "page_url": SOURCE_PAGE_URL,
                "download_url": DOWNLOAD_URL,
                "interface_status": "legacy-web-form-observed",
            },
            "request": {
                "method": "POST",
                "form": {
                    "Idioma": "PT",
                    "Dt_Ref": reference_date.strftime("%d/%m/%Y"),
                    "saida": "xml",
                },
            },
            "observed_content": asdict(summary),
            "file": {
                "path": relative_path.as_posix(),
                "format": "xml",
                "byte_count": len(body),
                "sha256": sha256(body).hexdigest(),
            },
        }
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(destination)
        return destination
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def _iso_date(value):
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use a data no formato AAAA-MM-DD.") from exc


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Executa o spike de coleta XML da ETTJ da ANBIMA."
    )
    parser.add_argument("--date", required=True, type=_iso_date, dest="reference_date")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args(argv)

    snapshot = collect_snapshot(
        args.output,
        args.reference_date,
        timeout=args.timeout,
    )
    print(snapshot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
