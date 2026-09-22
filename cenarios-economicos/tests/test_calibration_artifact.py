from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import unittest

from app.calibration.artifact import (
    ARTIFACT_SCHEMA_VERSION,
    BUILDER_VERSION,
    TRANSFORMATION_POLICY_VERSION,
    CalibrationError,
    CalibrationInputError,
    build_calibration_artifact,
)
from app.data_sources.bacen import collect_snapshot as collect_bacen
from app.data_sources.ibovespa import (
    ProviderExtract,
    collect_snapshot as collect_ibovespa,
)
from app.services.scenario_generator import loads_decimal


COLLECTED_AT = datetime(2026, 1, 2, 12, tzinfo=timezone.utc)
GENERATED_AT = datetime(2026, 1, 3, 12, tzinfo=timezone.utc)
START = date(2024, 1, 1)
CUTOFF = date(2025, 12, 31)


def weekdays(start, end):
    current = start
    while current <= end:
        if current.weekday() < 5:
            yield current
        current += timedelta(days=1)


def bacen_body(code):
    if code in (433, 189):
        value = "0.5" if code == 433 else "0.4"
        dates = [date(year, month, 1) for year in (2024, 2025)
                 for month in range(1, 13)]
    else:
        dates = list(weekdays(START, CUTOFF))
        if code == 11:
            value = "0.04"
        elif code == 12:
            value = "0.03"
        elif code == 432:
            value = "10.0"
        elif code == 1:
            value = None
        else:
            raise AssertionError(f"Codigo inesperado: {code}")
    rows = []
    for observed_at in dates:
        observed_value = value
        if code == 1:
            observed_value = "5.0" if observed_at.year == 2024 else "5.5"
        rows.append({
            "data": observed_at.strftime("%d/%m/%Y"),
            "valor": observed_value,
        })
    return json.dumps(rows, separators=(",", ":")).encode("utf-8")


def ibovespa_csv():
    rows = ["Date,Open,High,Low,Close,Adj Close,Volume"]
    for observed_at in weekdays(START, CUTOFF):
        close = "100" if observed_at.year == 2024 else "110"
        rows.append(
            f"{observed_at.isoformat()},{close},{close},{close},{close},{close},0"
        )
    return ("\n".join(rows) + "\n").encode("utf-8")


ANBIMA_XML = b"""<CURVAZERO>
<DATA_REFERENCIA>30/12/2025</DATA_REFERENCIA>
<PARAMETROS>
  <PARAMETRO Grupo='PREFIXADOS' B1='0,1' B2='0,1' B3='0,1' B4='0,1' L1='1,0' L2='1,0' />
  <PARAMETRO Grupo='IPCA' B1='0,1' B2='0,1' B3='0,1' B4='0,1' L1='1,0' L2='1,0' />
</PARAMETROS>
<ETTJ>
  <VERTICES Vertice='252' IPCA='5,0000' Prefixados='10,0000' Inflacao='4,7000' />
  <VERTICES Vertice='504' IPCA='6,0000' Prefixados='12,0000' Inflacao='5,6604' />
</ETTJ>
<CIRCULAR_3316><CIRCULAR Vertices='252' Taxa='10,0000' /></CIRCULAR_3316>
<ERROS><ERRO Erro='0,0000' /></ERROS>
</CURVAZERO>"""


def write_anbima_snapshot(output_root):
    snapshot = output_root / "anbima-ettj-2025-12-30-test"
    relative = Path("raw/ettj_2025-12-30.xml")
    raw = snapshot / relative
    raw.parent.mkdir(parents=True)
    raw.write_bytes(ANBIMA_XML)
    manifest = {
        "schema_version": "1.0.0",
        "snapshot_id": snapshot.name,
        "status": "experimental-spike",
        "collected_at": "2026-01-02T12:00:00Z",
        "collector": {"name": "spikes.anbima_ettj.probe", "version": "0.1.0"},
        "observed_content": {
            "reference_date": "2025-12-30",
            "vertex_count": 2,
        },
        "file": {
            "path": relative.as_posix(),
            "format": "xml",
            "byte_count": len(ANBIMA_XML),
            "sha256": sha256(ANBIMA_XML).hexdigest(),
        },
    }
    (snapshot / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return snapshot


class CalibrationArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)

        def bacen_fetcher(url, timeout):
            match = re.search(r"bcdata\.sgs\.(\d+)/dados", url)
            self.assertIsNotNone(match)
            return bacen_body(int(match.group(1)))

        self.bacen_snapshot = collect_bacen(
            self.root / "raw-bacen",
            START,
            CUTOFF,
            fetcher=bacen_fetcher,
            collected_at=COLLECTED_AT,
        )
        csv_body = ibovespa_csv()
        self.ibovespa_snapshot = collect_ibovespa(
            self.root / "raw-ibovespa",
            START,
            CUTOFF,
            fetcher=lambda start, end, timeout: ProviderExtract(
                csv_body, "1.7.0", "3.0.5"
            ),
            collected_at=COLLECTED_AT,
        )
        self.anbima_snapshot = write_anbima_snapshot(self.root / "raw-anbima")

    def tearDown(self):
        self.temporary.cleanup()

    def build(self, calibration_id="official-base", **overrides):
        arguments = {
            "output_root": self.root / "calibrated",
            "bacen_snapshot": self.bacen_snapshot,
            "ibovespa_snapshot": self.ibovespa_snapshot,
            "cutoff_date": CUTOFF,
            "calibration_id": calibration_id,
            "calibration_version": "1.0.0",
            "responsible": "Equipe de cenarios economicos",
            "anbima_snapshot": self.anbima_snapshot,
            "allow_experimental_anbima": True,
            "generated_at": GENERATED_AT,
        }
        arguments.update(overrides)
        return build_calibration_artifact(**arguments)

    def test_builds_versioned_artifact_with_exact_provenance(self):
        destination = self.build()
        calibration_body = (destination / "calibration.json").read_bytes()
        calibration = loads_decimal(calibration_body.decode("utf-8"))
        manifest = json.loads((destination / "manifest.json").read_text())

        self.assertEqual(destination.name, "calibration-official-base-v1.0.0")
        self.assertEqual(calibration["schema_version"], ARTIFACT_SCHEMA_VERSION)
        self.assertEqual(calibration["builder_version"], BUILDER_VERSION)
        self.assertEqual(
            calibration["transformation_policy_version"],
            TRANSFORMATION_POLICY_VERSION,
        )
        self.assertEqual(calibration["artifact_id"], "official-base@1.0.0")
        self.assertEqual(manifest["created_at"], "2026-01-03T12:00:00Z")
        self.assertEqual(calibration["historical"]["common_years"], [2025])
        self.assertEqual(len(calibration["historical"]["observations"]), 7)
        self.assertEqual(calibration["scope"], "historical_and_market_implied")

        self.assertEqual(manifest["file"]["byte_count"], len(calibration_body))
        self.assertEqual(
            manifest["file"]["sha256"], sha256(calibration_body).hexdigest()
        )
        self.assertEqual(len(manifest["source_manifests"]), 3)
        self.assertTrue(all(
            len(source["manifest_sha256"]) == 64
            for source in calibration["source_snapshots"]
        ))

    def test_applies_each_frequency_transformation(self):
        calibration = loads_decimal(
            (self.build() / "calibration.json").read_text()
        )
        records = {
            item["metric"]: item
            for item in calibration["historical"]["observations"]
        }

        self.assertEqual(records["ipca"]["value"], Decimal("0.06167781"))
        self.assertEqual(records["igpm"]["value"], Decimal("0.04907021"))
        self.assertEqual(records["selic_target"]["value"], Decimal("0.10000000"))
        self.assertEqual(records["usd_brl"]["value"], Decimal("0.10000000"))
        self.assertEqual(records["ibovespa"]["value"], Decimal("0.10000000"))
        self.assertEqual(records["selic_effective"]["coverage"], "source_consistent")
        self.assertEqual(records["cdi"]["coverage"], "source_consistent")
        self.assertEqual(records["ibovespa"]["source_series"], "close")
        self.assertGreater(records["selic_effective"]["value"], records["cdi"]["value"])

    def test_curve_preserves_published_spot_and_builds_forwards(self):
        calibration = loads_decimal(
            (self.build() / "calibration.json").read_text()
        )
        curve = calibration["market_curve"]

        self.assertEqual(curve["reference_date"], "2025-12-30")
        self.assertEqual(curve["status"], "market_implied")
        self.assertEqual(len(curve["annual_forwards"]), 2)
        self.assertEqual(
            curve["annual_forwards"][0]["nominal_rate"], Decimal("0.10000000")
        )
        self.assertEqual(
            curve["annual_forwards"][0]["real_rate"], Decimal("0.05000000")
        )
        self.assertEqual(
            curve["annual_forwards"][0]["implied_inflation"],
            Decimal("0.04761905"),
        )
        first_vertex = curve["vertices"][0]
        self.assertEqual(
            first_vertex["published_implied_inflation_spot"], Decimal("0.04700000")
        )
        self.assertEqual(
            first_vertex["recomputed_implied_inflation_spot"],
            Decimal("0.04761905"),
        )

    def test_experimental_curve_requires_explicit_authorization(self):
        with self.assertRaisesRegex(CalibrationInputError, "autorizacao explicita"):
            self.build(allow_experimental_anbima=False)
        self.assertFalse((self.root / "calibrated").exists())

    def test_historical_only_artifact_is_explicit(self):
        destination = self.build(
            calibration_id="historical-only",
            anbima_snapshot=None,
            allow_experimental_anbima=False,
        )
        calibration = loads_decimal((destination / "calibration.json").read_text())

        self.assertEqual(calibration["scope"], "historical_only")
        self.assertIsNone(calibration["market_curve"])
        self.assertIsNone(
            calibration["variable_mapping"]["inflation"]["trajectory_metric"]
        )

    def test_same_identity_is_immutable(self):
        destination = self.build()
        before = (destination / "calibration.json").read_bytes()

        with self.assertRaisesRegex(CalibrationError, "Ja existe artefato"):
            self.build()

        self.assertEqual((destination / "calibration.json").read_bytes(), before)
        self.assertEqual(
            sorted(item.name for item in destination.parent.iterdir()),
            [destination.name],
        )

    def test_calibration_content_is_reproducible_across_generation_times(self):
        first = self.build(output_root=self.root / "first-output")
        second = self.build(
            output_root=self.root / "second-output",
            generated_at=GENERATED_AT + timedelta(days=1),
        )

        first_body = (first / "calibration.json").read_bytes()
        second_body = (second / "calibration.json").read_bytes()
        first_manifest = json.loads((first / "manifest.json").read_text())
        second_manifest = json.loads((second / "manifest.json").read_text())

        self.assertEqual(first_body, second_body)
        self.assertEqual(
            first_manifest["file"]["sha256"], second_manifest["file"]["sha256"]
        )
        self.assertNotEqual(first_manifest["created_at"], second_manifest["created_at"])

    def test_tampered_source_is_rejected_without_partial_artifact(self):
        manifest = json.loads(
            (self.ibovespa_snapshot / "manifest.json").read_text()
        )
        source_file = self.ibovespa_snapshot / manifest["file"]["path"]
        source_file.write_bytes(source_file.read_bytes() + b"\n")

        with self.assertRaisesRegex(CalibrationInputError, "byte_count"):
            self.build()

        self.assertFalse((self.root / "calibrated").exists())

    def test_invalid_identity_is_rejected_before_reading_snapshots(self):
        with self.assertRaises(ValueError):
            build_calibration_artifact(
                self.root / "calibrated",
                self.root / "missing-bacen",
                self.root / "missing-ibovespa",
                CUTOFF,
                "Invalid ID",
                "1.0",
                "Equipe",
            )


if __name__ == "__main__":
    unittest.main()
