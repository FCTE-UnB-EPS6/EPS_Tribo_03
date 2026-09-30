from datetime import date, datetime
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import unittest

from app.data_sources.bacen import validate_response
from app.data_sources.ibovespa import validate_extract
from app.calibration.artifact import _monthly_returns


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "real" / "v1"


class RealDataFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(
            (FIXTURES / "fixture-manifest.json").read_text(encoding="utf-8")
        )

    def test_manifest_covers_every_data_file_and_hashes(self):
        declared = set()
        for source in self.manifest["sources"]:
            relative = source["path"]
            path = FIXTURES / relative
            body = path.read_bytes()
            declared.add(relative)
            self.assertEqual(len(body), source["byte_count"])
            self.assertEqual(sha256(body).hexdigest(), source["sha256"])
        actual = {
            path.relative_to(FIXTURES).as_posix()
            for path in FIXTURES.rglob("*")
            if path.is_file() and path.suffix in (".json", ".csv")
            and path.name != "fixture-manifest.json"
        }
        self.assertEqual(actual, declared)

    def test_bacen_ipca_fixture_uses_real_2024_observations(self):
        path = FIXTURES / "bacen" / "ipca_2024.json"
        body = path.read_bytes()
        count = validate_response(body, date(2024, 1, 1), date(2024, 12, 31))
        records = json.loads(body, parse_float=Decimal)
        self.assertEqual(count, 12)
        self.assertEqual(records[0], {"data": "01/01/2024", "valor": "0.42"})
        self.assertEqual(records[-1], {"data": "01/12/2024", "valor": "0.52"})
        self.assertEqual(
            [record["data"] for record in records],
            [f"01/{month:02d}/2024" for month in range(1, 13)],
        )
        observations = {
            datetime.strptime(record["data"], "%d/%m/%Y").date(): Decimal(
                record["valor"]
            )
            for record in records
        }
        annual = _monthly_returns(observations, date(2024, 12, 31))
        self.assertEqual(annual[2024]["value"], Decimal("0.04831296"))
        self.assertEqual(annual[2024]["coverage"], "complete")

    def test_ibovespa_fixture_preserves_non_official_provenance(self):
        source = next(
            item for item in self.manifest["sources"]
            if item["id"] == "ibovespa-yahoo-2024-sample"
        )
        body = (FIXTURES / source["path"]).read_bytes()
        summary = validate_extract(body, date(2024, 1, 1), date(2024, 1, 8))
        self.assertEqual(summary.record_count, 5)
        self.assertEqual(summary.first_date, "2024-01-02")
        self.assertEqual(summary.last_date, "2024-01-08")
        self.assertFalse(source["is_official_b3_source"])
        self.assertIn("not official B3", source["notice"])

    def test_anbima_contract_drift_is_not_promoted_to_fixture(self):
        experimental = self.manifest["experimental_sources_without_fixture"]
        self.assertEqual([item["id"] for item in experimental], ["anbima-ettj"])
        self.assertFalse((FIXTURES / "anbima").exists())


if __name__ == "__main__":
    unittest.main()
