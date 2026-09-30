import unittest

from app.api.schemas import (
    GENERATION_INPUT,
    GENERATION_RUN,
    GENERATION_SCENARIO_LOOKUP,
)


class ApiSchemaTests(unittest.TestCase):
    def test_generation_request_discriminates_both_contracts(self):
        self.assertEqual(
            GENERATION_INPUT["discriminator"], {"propertyName": "contract_version"}
        )
        versions = {
            schema["properties"]["contract_version"]["const"]
            for schema in GENERATION_INPUT["oneOf"]
        }
        self.assertEqual(versions, {"0.1.0", "0.2.0"})
        trajectory = next(
            schema
            for schema in GENERATION_INPUT["oneOf"]
            if schema["properties"]["contract_version"]["const"] == "0.2.0"
        )
        self.assertFalse(trajectory["additionalProperties"])
        self.assertIn("calibration", trajectory["required"])
        self.assertIn("trajectory", trajectory["required"])
        period = trajectory["properties"]["trajectory"]["properties"]["periods"]["items"]
        self.assertEqual(
            period["properties"]["variables"]["required"],
            ["inflation", "discount_rate"],
        )

    def test_response_schemas_cover_trajectory_identity(self):
        trajectory_run = next(
            schema
            for schema in GENERATION_RUN["oneOf"]
            if schema["properties"]["contract_version"]["const"] == "0.2.0"
        )
        scenario = trajectory_run["properties"]["scenarios"]["items"]
        self.assertIn("trajectory_id", scenario["required"])
        self.assertIn("trajectory_version", scenario["required"])
        self.assertEqual(len(GENERATION_SCENARIO_LOOKUP["oneOf"]), 2)


if __name__ == "__main__":
    unittest.main()
