"""Parse queries of the form P(A=a, B | C=c, D=d)."""

from __future__ import annotations

import re

from backend.bn import BayesianNetwork, NetworkError

_QUERY_RE = re.compile(
    r"^\s*P\s*\(\s*(?P<body>.+?)\s*\)\s*$",
    re.IGNORECASE | re.DOTALL,
)


def _split_terms(text: str) -> list[str]:
    return [part.strip() for part in text.split(",") if part.strip()]


def _parse_term(term: str, *, require_value: bool) -> tuple[str, str | None]:
    if "=" in term:
        name, value = term.split("=", 1)
        name = name.strip()
        value = value.strip()
        if not name or not value:
            raise NetworkError([f"Could not read assignment {term!r}."])
        return name, value
    name = term.strip()
    if not name:
        raise NetworkError(["The query contains an empty variable."])
    if require_value:
        raise NetworkError([f"{name} needs a value, written as {name}=value."])
    return name, None


def parse_query(
    text: str,
    network: BayesianNetwork,
) -> tuple[list[tuple[str, str | None]], dict[str, str]]:
    """Return (query assignments, evidence) checked against the network."""
    match = _QUERY_RE.match(text or "")
    if not match:
        raise NetworkError(
            ["Write the query as P(Variable=value | Evidence=value), or P(Variable | Evidence=value)."]
        )
    body = match.group("body").strip()
    if "|" in body:
        query_text, evidence_text = body.split("|", 1)
    else:
        query_text, evidence_text = body, ""

    query_terms = _split_terms(query_text)
    if not query_terms:
        raise NetworkError(["The query needs at least one variable before the bar."])
    evidence_terms = _split_terms(evidence_text) if evidence_text.strip() else []

    query = [_parse_term(term, require_value=False) for term in query_terms]
    evidence_pairs = [_parse_term(term, require_value=True) for term in evidence_terms]

    known = {var.name for var in network.variables}
    for name, _value in query + evidence_pairs:
        if name not in known:
            names = ", ".join(var.name for var in network.variables)
            raise NetworkError([f"Unknown variable {name!r}. Variables: {names}."])

    evidence: dict[str, str] = {}
    for name, value in evidence_pairs:
        if name in evidence:
            raise NetworkError([f"Evidence repeats {name!r}."])
        evidence[name] = value  # type: ignore[assignment]
    return query, evidence
