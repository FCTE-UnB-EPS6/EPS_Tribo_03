from copy import deepcopy
from decimal import Decimal
from pathlib import Path
import unittest

from app.services.scenario_application import RulesCatalog, ScenarioApplication
from app.services.scenario_generator import (
    ScenarioError,
    generate_scenarios,
    loads_decimal,
)


ROOT = Path(__file__).resolve().parents[1]


class MemoryRepository:
    def __init__(self):
        self.saved = []

    def save(self, result):
        self.saved.append(deepcopy(result))


class TrajectoryGeneratorTests(unittest.TestCase):
    def setUp(self):
        self.request = loads_decimal(
            (ROOT / "examples/trajectory.demo.v0.2.0.json").read_text()
        )
        self.rules = loads_decimal(
            (ROOT / "config/scenario_rules.trajectory.v0.2.0.json").read_text()
        )

    def generate(self):
        return generate_scenarios(self.request, self.rules)

    def error(self, code):
        with self.assertRaises(ScenarioError) as caught:
            self.generate()
        self.assertEqual(caught.exception.code, code)

    def test_golden_trajectory_and_provenance_snapshot(self):
        result = self.generate()
        self.assertEqual(result["contract_version"], "0.2.0")
        self.assertEqual(result["generator_version"], "0.2.0")
        expected = {
            "base": (("0.04761905", "0.10000000"), ("0.05000000", "0.09500000")),
            "adverse": (("0.06761905", "0.08000000"), ("0.07000000", "0.07500000")),
            "favorable": (("0.03761905", "0.11000000"), ("0.04000000", "0.10500000")),
        }
        for scenario in result["scenarios"]:
            values = tuple(
                tuple(str(period["variables"][name]) for name in ("inflation", "discount_rate"))
                for period in scenario["values"]
            )
            self.assertEqual(values, expected[scenario["scenario_key"]])
            self.assertEqual(scenario["trajectory_id"], "demo-market-trajectory")
            self.assertEqual(scenario["trajectory_version"], "0.1.0")
        self.assertEqual(result["request_snapshot"], self.request)
        self.assertEqual(
            result["request_snapshot"]["calibration"]["sha256"], "a" * 64
        )

    def test_is_deterministic_and_does_not_mutate_input(self):
        original = deepcopy((self.request, self.rules))
        first = self.generate()
        second = self.generate()
        self.assertEqual(first, second)
        first["scenarios"][0]["values"][0]["variables"]["inflation"] = 0
        self.assertEqual((self.request, self.rules), original)
        self.assertEqual(
            second["scenarios"][0]["values"][0]["variables"]["inflation"],
            Decimal("0.04761905"),
        )

    def test_rules_identity_structure_and_atomic_result_validation(self):
        self.rules["ruleset_version"] = "0.2.0"
        self.error("RULESET_NOT_FOUND")
        self.setUp()
        self.rules["scenarios"]["base"]["adjustments"]["inflation"] = Decimal("0.01")
        self.error("INVALID_RULESET")
        self.setUp()
        self.rules["scenarios"]["favorable"]["adjustments"]["inflation"] = Decimal("-1.05")
        self.error("INVALID_SCENARIO")

    def test_optional_variables_require_corresponding_rules(self):
        modeled = deepcopy(
            self.request["trajectory"]["periods"][1]["variables"]["inflation"]
        )
        modeled.update(source_metric="salary_model", method="salary_projection")
        for index, period in enumerate(self.request["trajectory"]["periods"]):
            value = deepcopy(modeled)
            value["source"]["path"] = f"/periods/{index}/salary_growth"
            period["variables"]["salary_growth"] = value
        self.error("INVALID_RULESET")
        for scenario in self.rules["scenarios"].values():
            scenario["adjustments"]["salary_growth"] = 0
        result = self.generate()
        self.assertIn("salary_growth", result["scenarios"][0]["values"][0]["variables"])

    def test_application_persists_completed_v02_run(self):
        repository = MemoryRepository()
        catalog = RulesCatalog([ROOT / "config/scenario_rules.trajectory.v0.2.0.json"])
        result = ScenarioApplication(repository, catalog).generate(self.request)
        self.assertEqual(result["status"], "completed")
        self.assertTrue(result["created_at"].endswith("Z"))
        self.assertEqual(len(repository.saved), 1)
        self.assertEqual(repository.saved[0], result)
        self.assertTrue(all("scenario_id" in item for item in result["scenarios"]))


if __name__ == "__main__":
    unittest.main()
