"""Enumeration-ask for a discrete Bayesian network (Russell and Norvig)."""

from __future__ import annotations

from itertools import product
from typing import Any

from backend.bn import BayesianNetwork, NetworkError

MAX_QUERY_ASSIGNMENTS = 4096


def enumerate_all(
    variables: list,
    evidence: dict[str, str],
    network: BayesianNetwork,
) -> float:
    """Sum the joint of the remaining variables consistent with the evidence."""
    if not variables:
        return 1.0
    current = variables[0]
    rest = variables[1:]
    if current.name in evidence:
        probability = network.probability(current.name, evidence[current.name], evidence)
        return probability * enumerate_all(rest, evidence, network)
    total = 0.0
    for value in current.domain:
        probability = network.probability(current.name, value, evidence)
        extended = dict(evidence)
        extended[current.name] = value
        total += probability * enumerate_all(rest, extended, network)
    return total


def enumeration_ask(
    network: BayesianNetwork,
    query: list[tuple[str, str | None]],
    evidence: dict[str, str],
) -> dict[str, Any]:
    """P(query | evidence) by enumerating hidden variables, then normalizing.

    A query entry is (name, value) or (name, None). None is allowed only for a
    single query variable and means "return the full distribution".
    """
    if not query:
        raise NetworkError(["The query needs at least one variable."])

    query_names = [name for name, _ in query]
    if len(query_names) != len(set(query_names)):
        raise NetworkError(["The query repeats a variable."])
    overlap = set(query_names) & set(evidence)
    if overlap:
        names = ", ".join(sorted(overlap))
        raise NetworkError([f"A variable cannot be both query and evidence: {names}."])

    bare = [name for name, value in query if value is None]
    if bare and not (len(query) == 1 and len(bare) == 1):
        raise NetworkError(
            [
                "A full distribution is only supported for a single query variable. "
                "Assign a value to every query variable, or query one variable."
            ]
        )

    for name, value in query:
        var = network.variable(name)
        if value is not None and value not in var.domain:
            raise NetworkError([f"{name}={value!r} is not in {var.domain}."])
    for name, value in evidence.items():
        var = network.variable(name)
        if value not in var.domain:
            raise NetworkError([f"{name}={value!r} is not in {var.domain}."])

    order = network.topological_order()
    if bare:
        var = network.variable(query_names[0])
        assignments = [{var.name: value} for value in var.domain]
        requested: dict[str, str] | None = None
    else:
        domains = [network.variable(name).domain for name in query_names]
        count = 1
        for domain in domains:
            count *= len(domain)
        if count > MAX_QUERY_ASSIGNMENTS:
            raise NetworkError(
                [
                    f"The query ranges over {count} assignments, "
                    f"above the limit of {MAX_QUERY_ASSIGNMENTS}."
                ]
            )
        assignments = [
            dict(zip(query_names, values))
            for values in product(*domains)
        ]
        requested = {name: value for name, value in query if value is not None}

    unnormalized: list[dict[str, Any]] = []
    for assignment in assignments:
        extended = dict(evidence)
        extended.update(assignment)
        mass = enumerate_all(order, extended, network)
        unnormalized.append({"assignment": assignment, "mass": mass})

    total = sum(item["mass"] for item in unnormalized)
    if total == 0:
        raise NetworkError(
            ["The evidence has probability 0, so the conditional probability is undefined."]
        )

    distribution = [
        {
            "assignment": item["assignment"],
            "probability": item["mass"] / total,
        }
        for item in unnormalized
    ]
    query_probability = None
    if requested is not None:
        for item in distribution:
            if item["assignment"] == requested:
                query_probability = item["probability"]
                break

    hidden = [
        var.name
        for var in order
        if var.name not in evidence and var.name not in query_names
    ]
    return {
        "topological_order": [var.name for var in order],
        "hidden": hidden,
        "unnormalized": unnormalized,
        "distribution": distribution,
        "normalizer": total,
        "query_probability": query_probability,
        "requested": requested,
    }
