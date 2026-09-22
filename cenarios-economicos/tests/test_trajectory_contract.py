from copy import deepcopy
from datetime import date
from decimal import Decimal
from pathlib import Path
import unittest

from app.contracts.trajectory import (
    TRAJECTORY_CONTRACT_VERSION,
    TrajectoryContractError,
    validate_trajectory_request,
)
from app.services.scenario_generator import generate_scenarios, loads_decimal


ROOT = Path(__file__).resolve().parents[1]


class TrajectoryContractTests(unittest.TestCase):
    def setUp(self):
        self.request = loads_decimal(
            (ROOT / "examples/trajectory.demo.v0.2.0.json").read_text()
        )

    def validate(self):
        return validate_trajectory_request(self.request)

    def error(self, code, field=None):
        with self.assertRaises(TrajectoryContractError) as caught:
            self.validate()
        self.assertEqual(caught.exception.code, code)
        if field is not None:
            self.assertEqual(caught.exception.field, field)
        self.assertEqual(
            set(caught.exception.as_dict()["error"]), {"code", "field", "message"}
        )

    def test_valid_example_and_independent_copy(self):
        result = self.validate()
        self.assertEqual(result, self.request)
        self.assertIsNot(result, self.request)
        result["trajectory"]["periods"][0]["variables"]["inflation"]["value"] = 0
        self.assertEqual(
            self.request["trajectory"]["periods"][0]["variables"]["inflation"]["value"],
            Decimal("0.04761905"),
        )
        self.assertEqual(TRAJECTORY_CONTRACT_VERSION, "0.2.0")

    def test_contract_0_1_0_remains_supported_by_existing_generator(self):
        old_request = loads_decimal(
            (ROOT / "examples/generate.demo.v0.1.0.json").read_text()
        )
        old_rules = loads_decimal(
            (ROOT / "config/scenario_rules.demo.v0.1.0.json").read_text()
        )
        result = generate_scenarios(old_request, old_rules)
        self.assertEqual(result["contract_version"], "0.1.0")
        self.assertEqual(len(result["scenarios"]), 3)

    def test_request_structure_and_metadata(self):
        original = deepcopy(self.request)
        for field in original:
            with self.subTest(field=field):
                self.request = deepcopy(original)
                del self.request[field]
                self.error("INVALID_TRAJECTORY_REQUEST")
        self.request = deepcopy(original)
        self.request["unexpected"] = True
        self.error("INVALID_TRAJECTORY_REQUEST")
        self.request = deepcopy(original)
        self.request["contract_version"] = "0.3.0"
        self.error("UNSUPPORTED_TRAJECTORY_CONTRACT_VERSION", "contract_version")
        for field, value in (
            ("purpose", "simulation"),
            ("unit", "%"),
            ("rate_basis", "real"),
            ("ruleset_version", "latest"),
        ):
            with self.subTest(field=field):
                self.request = deepcopy(original)
                self.request[field] = value
                self.error("INVALID_TRAJECTORY_REQUEST", field)

    def test_horizon_period_sequence_and_dates(self):
        original = deepcopy(self.request)
        for value in (0, 121, True, Decimal("2"), "2"):
            with self.subTest(value=value):
                self.request = deepcopy(original)
                self.request["horizon_years"] = value
                self.error("INVALID_TRAJECTORY_REQUEST", "horizon_years")
        self.request = deepcopy(original)
        self.request["horizon_years"] = 1
        self.error("INVALID_TRAJECTORY", "trajectory.periods")
        self.request = deepcopy(original)
        self.request["trajectory"]["periods"][1]["period"] = 3
        self.error("INVALID_TRAJECTORY", "trajectory.periods.1.period")
        self.request = deepcopy(original)
        self.request["trajectory"]["periods"][1]["period_start"] = "2027-01-02"
        self.error("INVALID_TRAJECTORY", "trajectory.periods.1")

    def test_leap_day_anniversaries(self):
        self.request["base_date"] = "2024-02-29"
        self.request["calibration"]["cutoff_date"] = "2024-02-28"
        for index, period in enumerate(self.request["trajectory"]["periods"]):
            period["period_start"] = ("2024-02-29", "2025-02-28")[index]
            period["period_end"] = ("2025-02-28", "2026-02-28")[index]
            for variable in period["variables"].values():
                variable["source"]["reference_date"] = "2024-02-28"
        self.validate()

    def test_calibration_identity_versions_scope_and_freshness(self):
        original = deepcopy(self.request)
        cases = (
            ("artifact_id", "other@1.0.0"),
            ("artifact_schema_version", "2.0.0"),
            ("transformation_policy_version", "0.2.0"),
            ("sha256", "A" * 64),
            ("scope", "unknown"),
            ("cutoff_date", "2025-12-20"),
            ("cutoff_date", "2026-01-02"),
        )
        for field, value in cases:
            with self.subTest(field=field, value=value):
                self.request = deepcopy(original)
                self.request["calibration"][field] = value
                self.error("INVALID_CALIBRATION_REFERENCE", f"calibration.{field}")

    def test_rate_precision_and_types(self):
        original = deepcopy(self.request)
        target = lambda request: request["trajectory"]["periods"][0]["variables"]["inflation"]
        for value in (True, None, "0.04", 0.04, Decimal("NaN"), -1, Decimal("0.000000001")):
            with self.subTest(value=value):
                self.request = deepcopy(original)
                target(self.request)["value"] = value
                self.error("INVALID_TRAJECTORY_VALUE")
        self.request = deepcopy(original)
        target(self.request)["value"] = Decimal("0.040000000000")
        self.validate()

    def test_variable_set_and_semantics(self):
        original = deepcopy(self.request)
        variables = self.request["trajectory"]["periods"][0]["variables"]
        del variables["inflation"]
        self.error("INVALID_TRAJECTORY")
        self.request = deepcopy(original)
        self.request["trajectory"]["periods"][0]["variables"]["unknown"] = {}
        self.error("INVALID_TRAJECTORY")
        self.request = deepcopy(original)
        modeled = deepcopy(
            self.request["trajectory"]["periods"][1]["variables"]["inflation"]
        )
        self.request["trajectory"]["periods"][0]["variables"]["salary_growth"] = modeled
        self.error("INVALID_TRAJECTORY", "trajectory.periods.1.variables")
        self.request = deepcopy(original)
        item = self.request["trajectory"]["periods"][0]["variables"]["inflation"]
        item["measure"] = "annual_rate_level"
        self.error("INVALID_TRAJECTORY_VALUE", "trajectory.periods.0.variables.inflation.measure")

    def test_market_implied_provenance(self):
        original = deepcopy(self.request)
        item = lambda request: request["trajectory"]["periods"][0]["variables"]["inflation"]
        cases = (
            ("source_metric", "ipca"),
            ("source.reference", "other@1.0.0"),
            ("source.reference_version", "2.0.0"),
            ("source.reference_date", "2026-01-01"),
            ("source.path", "market_curve/value"),
            ("source.kind", "model"),
        )
        for path, value in cases:
            with self.subTest(path=path):
                self.request = deepcopy(original)
                target = item(self.request)
                parts = path.split(".")
                for part in parts[:-1]:
                    target = target[part]
                target[parts[-1]] = value
                self.error("INVALID_TRAJECTORY_VALUE")
        self.request = deepcopy(original)
        self.request["calibration"]["scope"] = "historical_only"
        self.error("INVALID_TRAJECTORY_VALUE")

    def test_modeled_value_requires_model_source(self):
        item = self.request["trajectory"]["periods"][1]["variables"]["inflation"]
        item["source"]["kind"] = "calibration_artifact"
        item["source"]["reference"] = self.request["calibration"]["artifact_id"]
        item["source"]["reference_version"] = self.request["calibration"]["calibration_version"]
        self.error("INVALID_TRAJECTORY_VALUE", "trajectory.periods.1.variables.inflation.source.kind")

    def test_projection_rejects_observed_and_backtest_accepts_finished_periods(self):
        item = self.request["trajectory"]["periods"][0]["variables"]["inflation"]
        item.update(status="observed", measure="effective_return", source_metric="ipca")
        self.error("INVALID_TRAJECTORY_VALUE", "trajectory.periods.0.variables.inflation.status")

        self.request["purpose"] = "backtest"
        self.request["base_date"] = "2022-01-01"
        self.request["calibration"]["cutoff_date"] = "2024-01-01"
        self.request["calibration"]["scope"] = "historical_only"
        periods = self.request["trajectory"]["periods"]
        for index, period in enumerate(periods):
            period["period_start"] = f"{2022 + index}-01-01"
            period["period_end"] = f"{2023 + index}-01-01"
            inflation = period["variables"]["inflation"]
            inflation.update(status="observed", measure="effective_return", source_metric="ipca")
            inflation["source"].update(
                kind="calibration_artifact",
                reference=self.request["calibration"]["artifact_id"],
                reference_version=self.request["calibration"]["calibration_version"],
                reference_date=period["period_end"],
                path=f"/historical/observations/{index}/metrics/ipca",
            )
            discount = period["variables"]["discount_rate"]
            discount.update(
                status="modeled",
                measure="modeled_rate",
                source_metric="historical_discount_model",
            )
            discount["source"].update(
                kind="model",
                reference="historical-discount-model",
                reference_version="0.1.0",
                reference_date="2022-01-01",
                path=f"/periods/{index}/discount_rate",
            )
        self.validate()

        self.request["calibration"]["cutoff_date"] = "2023-12-31"
        self.error(
            "INVALID_TRAJECTORY_VALUE",
            "trajectory.periods.1.variables.inflation.status",
        )


if __name__ == "__main__":
    unittest.main()
