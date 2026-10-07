"""Checks for CPT indexing, validation, and enumeration-ask."""

from __future__ import annotations

import unittest

from backend.bn import NetworkError, validate_network
from backend.enumeration import enumeration_ask
from backend.example_network import (
    ALARM_NETWORK,
    ALARM_PROBLEM,
    RAIN_NETWORK as RAIN,
    match_known_example,
)
from backend.ollama_cpt import _network_from_payload, _parse_json_object, normalize_extracted
from backend.query_parser import parse_query


class NetworkTests(unittest.TestCase):
    def test_row_index_last_parent_changes_fastest(self) -> None:
        network = validate_network(RAIN)
        wet = network.variable("WetGrass")
        self.assertEqual(
            network.row_index(wet, {"Sprinkler": "T", "Rain": "T"}),
            0,
        )
        self.assertEqual(
            network.row_index(wet, {"Sprinkler": "T", "Rain": "F"}),
            1,
        )
        self.assertEqual(
            network.row_index(wet, {"Sprinkler": "F", "Rain": "T"}),
            2,
        )
        self.assertEqual(
            network.parent_values(wet, 3),
            {"Sprinkler": "F", "Rain": "F"},
        )

    def test_rejects_a_cycle(self) -> None:
        with self.assertRaises(NetworkError):
            validate_network(
                {
                    "variables": [
                        {
                            "name": "A",
                            "domain": ["T", "F"],
                            "parents": ["B"],
                            "cpt": [[0.2, 0.8], [0.3, 0.7]],
                        },
                        {
                            "name": "B",
                            "domain": ["T", "F"],
                            "parents": ["A"],
                            "cpt": [[0.4, 0.6], [0.5, 0.5]],
                        },
                    ]
                }
            )

    def test_rejects_a_row_that_does_not_sum_to_one(self) -> None:
        broken = {
            "variables": [
                {
                    "name": "Rain",
                    "domain": ["T", "F"],
                    "parents": [],
                    "cpt": [[0.2, 0.2]],
                }
            ]
        }
        with self.assertRaises(NetworkError):
            validate_network(broken)

    def test_renormalizes_rounding(self) -> None:
        network = validate_network(
            {
                "variables": [
                    {
                        "name": "Coin",
                        "domain": ["H", "T"],
                        "parents": [],
                        "cpt": [[0.333, 0.666]],
                    }
                ]
            }
        )
        self.assertAlmostEqual(sum(network.variable("Coin").cpt[0]), 1.0)
        self.assertTrue(network.warnings)


class EnumerationTests(unittest.TestCase):
    def test_rain_given_wet_grass(self) -> None:
        network = validate_network(RAIN)
        query, evidence = parse_query("P(Rain=T | WetGrass=T)", network)
        result = enumeration_ask(network, query, evidence)
        rain_and_wet = 0.2 * 0.01 * 0.99 + 0.2 * 0.99 * 0.90
        wet = rain_and_wet + 0.8 * 0.4 * 0.90
        self.assertAlmostEqual(result["query_probability"], rain_and_wet / wet, places=9)

    def test_full_distribution_sums_to_one(self) -> None:
        network = validate_network(RAIN)
        query, evidence = parse_query("P(WetGrass | Rain=T)", network)
        result = enumeration_ask(network, query, evidence)
        total = sum(item["probability"] for item in result["distribution"])
        self.assertAlmostEqual(total, 1.0)
        wet_true = next(
            item["probability"]
            for item in result["distribution"]
            if item["assignment"] == {"WetGrass": "T"}
        )
        self.assertAlmostEqual(wet_true, 0.01 * 0.99 + 0.99 * 0.90)

    def test_joint_query(self) -> None:
        network = validate_network(RAIN)
        query, evidence = parse_query("P(Rain=T, Sprinkler=T | WetGrass=T)", network)
        result = enumeration_ask(network, query, evidence)
        self.assertAlmostEqual(result["query_probability"], (0.2 * 0.01 * 0.99) / (0.2 * 0.01 * 0.99 + 0.2 * 0.99 * 0.90 + 0.8 * 0.4 * 0.90), places=9)
        self.assertEqual(result["requested"], {"Rain": "T", "Sprinkler": "T"})

    def test_match_alarm_problem_text(self) -> None:
        matched, source = match_known_example(ALARM_PROBLEM)
        self.assertEqual(source, "example")
        self.assertEqual(matched["variables"][0]["name"], "Burglary")

    def test_alarm_john_and_mary_call(self) -> None:
        network = validate_network(ALARM_NETWORK)
        query, evidence = parse_query(
            "P(Burglary=T | JohnCalls=T, MaryCalls=T)",
            network,
        )
        result = enumeration_ask(network, query, evidence)
        self.assertGreater(result["query_probability"], 0.2)
        self.assertLess(result["query_probability"], 0.4)

    def test_rejects_unknown_variable(self) -> None:
        network = validate_network(RAIN)
        with self.assertRaises(NetworkError):
            parse_query("P(Fog=T)", network)


class OllamaJsonTests(unittest.TestCase):
    def test_strips_markdown_fence(self) -> None:
        payload = _parse_json_object(
            '```json\n{"error":"","variables":[]}\n```'
        )
        self.assertEqual(payload["variables"], [])

    def test_extracts_object_from_extra_text(self) -> None:
        payload = _parse_json_object('Here you go: {"error":"missing P(Rain)","variables":[]}')
        self.assertEqual(payload["error"], "missing P(Rain)")

    def test_normalizes_array_shaped_variables(self) -> None:
        payload = normalize_extracted(
            {
                "error": "",
                "variables": [
                    ["Rain", ["T", "F"], [], [[0.2, 0.8]]],
                    ["Sprinkler", ["T", "F"], ["Rain"], [[0.01, 0.99], [0.4, 0.6]]],
                    [
                        "WetGrass",
                        ["T", "F"],
                        ["Sprinkler", "Rain"],
                        [[0.99, 0.01], [0.90, 0.10], [0.90, 0.10], [0.00, 1.00]],
                    ],
                ],
            }
        )
        network = _network_from_payload(payload)
        self.assertEqual(network.variable("Rain").cpt[0][0], 0.2)


if __name__ == "__main__":
    unittest.main()
