"""Discrete Bayesian network model, CPT indexing, and validation."""

from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# Rows within this distance of 1 are treated as rounding error and renormalized.
REPAIR_TOLERANCE = 1e-2
# Rows already this close to 1 are left unchanged.
EXACT_TOLERANCE = 1e-6


class NetworkError(Exception):
    """The submitted network is not a valid discrete Bayesian network."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


class Variable(BaseModel):
    """One node: domain, parents, and P(node | parents) as an array of arrays."""

    model_config = ConfigDict(extra="ignore")

    name: str
    domain: list[str]
    parents: list[str]
    cpt: list[list[float]]


class BayesianNetwork(BaseModel):
    """A validated discrete Bayesian network in topological parent order."""

    model_config = ConfigDict(extra="ignore")

    variables: list[Variable]
    warnings: list[str] = Field(default_factory=list)

    def variable(self, name: str) -> Variable:
        for var in self.variables:
            if var.name == name:
                return var
        known = ", ".join(var.name for var in self.variables)
        raise KeyError(f"Unknown variable {name!r}. Variables: {known}")

    def topological_order(self) -> list[Variable]:
        """Parents appear before their children. The graph is already acyclic."""
        by_name = {var.name: var for var in self.variables}
        remaining = set(by_name)
        ordered: list[Variable] = []
        while remaining:
            ready = [
                name
                for name in remaining
                if all(parent not in remaining for parent in by_name[name].parents)
            ]
            if not ready:
                raise NetworkError(["The parent graph contains a cycle."])
            ready.sort()
            for name in ready:
                remaining.remove(name)
                ordered.append(by_name[name])
        return ordered

    def row_index(self, var: Variable, assignment: dict[str, str]) -> int:
        """Index of a parent assignment. The last parent changes fastest."""
        index = 0
        for parent_name in var.parents:
            parent = self.variable(parent_name)
            if parent_name not in assignment:
                raise NetworkError(
                    [f"Cannot read P({var.name}|...) because {parent_name} is unassigned."]
                )
            value = assignment[parent_name]
            try:
                value_index = parent.domain.index(value)
            except ValueError as exc:
                raise NetworkError(
                    [f"{parent_name}={value!r} is not in {parent.domain}."]
                ) from exc
            index = index * len(parent.domain) + value_index
        return index

    def probability(self, name: str, value: str, assignment: dict[str, str]) -> float:
        """P(name = value | parents), reading the CPT row for this assignment."""
        var = self.variable(name)
        try:
            column = var.domain.index(value)
        except ValueError as exc:
            raise NetworkError(
                [f"{name}={value!r} is not in {var.domain}."]
            ) from exc
        return var.cpt[self.row_index(var, assignment)][column]

    def parent_values(self, var: Variable, row: int) -> dict[str, str]:
        """Decode a CPT row index back into parent = value labels."""
        values: list[str] = []
        index = row
        for parent_name in reversed(var.parents):
            parent = self.variable(parent_name)
            width = len(parent.domain)
            values.append(parent.domain[index % width])
            index //= width
        values.reverse()
        return dict(zip(var.parents, values))

    def tables(self) -> list[dict[str, Any]]:
        """CPT rows with parent labels, for the page to render."""
        rendered = []
        for var in self.variables:
            rows = []
            for row_index, probs in enumerate(var.cpt):
                rows.append(
                    {
                        "parents": self.parent_values(var, row_index),
                        "probs": probs,
                    }
                )
            rendered.append(
                {
                    "name": var.name,
                    "parents": list(var.parents),
                    "domain": list(var.domain),
                    "rows": rows,
                }
            )
        return rendered


def _clean_label(value: Any, what: str) -> str:
    if not isinstance(value, str):
        raise NetworkError([f"{what} must be a string."])
    label = value.strip()
    if not label:
        raise NetworkError([f"{what} cannot be empty."])
    return label


def validate_network(data: Any) -> BayesianNetwork:
    """Check domains, parents, the DAG, and CPT shape. Repair tiny rounding gaps."""
    if not isinstance(data, dict):
        raise NetworkError(["Network must be a JSON object with a variables list."])
    raw_variables = data.get("variables")
    if not isinstance(raw_variables, list) or not raw_variables:
        raise NetworkError(["The network needs at least one variable."])

    errors: list[str] = []
    warnings: list[str] = []
    variables: list[Variable] = []
    seen: set[str] = set()

    for index, item in enumerate(raw_variables):
        if not isinstance(item, dict):
            errors.append(f"Variable {index + 1} must be an object.")
            continue
        try:
            name = _clean_label(item.get("name", ""), f"Variable {index + 1} name")
        except NetworkError as exc:
            errors.extend(exc.errors)
            continue
        if name in seen:
            errors.append(f"Duplicate variable name {name!r}.")
            continue
        seen.add(name)

        raw_domain = item.get("domain")
        if not isinstance(raw_domain, list) or not raw_domain:
            errors.append(f"{name} needs a non-empty domain.")
            continue
        domain: list[str] = []
        domain_ok = True
        for entry in raw_domain:
            try:
                label = _clean_label(entry, f"{name} domain value")
            except NetworkError as exc:
                errors.extend(exc.errors)
                domain_ok = False
                break
            if label in domain:
                errors.append(f"{name} domain repeats {label!r}.")
                domain_ok = False
                break
            domain.append(label)
        if not domain_ok:
            continue

        raw_parents = item.get("parents", [])
        if not isinstance(raw_parents, list):
            errors.append(f"{name} parents must be a list.")
            continue
        parents: list[str] = []
        parents_ok = True
        for entry in raw_parents:
            try:
                parent = _clean_label(entry, f"{name} parent")
            except NetworkError as exc:
                errors.extend(exc.errors)
                parents_ok = False
                break
            if parent in parents:
                errors.append(f"{name} lists parent {parent!r} more than once.")
                parents_ok = False
                break
            parents.append(parent)
        if not parents_ok:
            continue

        raw_cpt = item.get("cpt")
        if not isinstance(raw_cpt, list):
            errors.append(f"{name} cpt must be an array of arrays.")
            continue
        cpt: list[list[float]] = []
        cpt_ok = True
        for row_index, row in enumerate(raw_cpt):
            if not isinstance(row, list):
                errors.append(f"{name} CPT row {row_index + 1} must be an array.")
                cpt_ok = False
                break
            probs: list[float] = []
            for cell in row:
                try:
                    number = float(cell)
                except (TypeError, ValueError):
                    errors.append(f"{name} CPT contains a non-numeric probability.")
                    cpt_ok = False
                    break
                if not math.isfinite(number) or number < 0:
                    errors.append(f"{name} CPT probabilities must be finite and >= 0.")
                    cpt_ok = False
                    break
                probs.append(number)
            if not cpt_ok:
                break
            cpt.append(probs)
        if not cpt_ok:
            continue

        variables.append(
            Variable(name=name, domain=domain, parents=parents, cpt=cpt)
        )

    if errors:
        raise NetworkError(errors)

    by_name = {var.name: var for var in variables}
    for var in variables:
        for parent in var.parents:
            if parent not in by_name:
                errors.append(f"{var.name} lists unknown parent {parent!r}.")
            elif parent == var.name:
                errors.append(f"{var.name} cannot be its own parent.")
    if errors:
        raise NetworkError(errors)

    network = BayesianNetwork(variables=variables)
    try:
        network.topological_order()
    except NetworkError as exc:
        raise NetworkError(exc.errors) from exc

    for var in variables:
        expected_rows = 1
        for parent in var.parents:
            expected_rows *= len(by_name[parent].domain)
        if len(var.cpt) != expected_rows:
            errors.append(
                f"{var.name} CPT has {len(var.cpt)} rows; "
                f"the parent domains require {expected_rows}."
            )
            continue
        for row_index, row in enumerate(var.cpt):
            if len(row) != len(var.domain):
                errors.append(
                    f"{var.name} CPT row {row_index + 1} has {len(row)} entries; "
                    f"the domain has {len(var.domain)}."
                )
                continue
            total = sum(row)
            if abs(total - 1.0) <= EXACT_TOLERANCE:
                continue
            if total <= 0 or abs(total - 1.0) > REPAIR_TOLERANCE:
                errors.append(
                    f"{var.name} CPT row {row_index + 1} sums to {total:.6g}, not 1."
                )
                continue
            var.cpt[row_index] = [cell / total for cell in row]
            labels = network.parent_values(var, row_index)
            condition = (
                ", ".join(f"{key}={value}" for key, value in labels.items())
                or "no parents"
            )
            warnings.append(
                f"Renormalized P({var.name} | {condition}) so the row sums to 1 "
                f"(it summed to {total:.6g})."
            )

    if errors:
        raise NetworkError(errors)

    network.warnings = warnings
    return network
