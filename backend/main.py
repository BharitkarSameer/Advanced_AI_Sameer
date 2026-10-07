"""HTTP API and static page for Bayesian network enumeration."""

from __future__ import annotations

import logging
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.bn import BayesianNetwork, NetworkError, validate_network
from backend.enumeration import enumeration_ask
from backend.example_network import ALARM_NETWORK, RAIN_NETWORK, match_known_example
from backend.ollama_cpt import build_network_from_problem
from backend.query_parser import parse_query

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("bn.app")

app = FastAPI(title="Bayesian network enumeration")


class BuildRequest(BaseModel):
    problem: str = ""


class QueryRequest(BaseModel):
    network: dict
    query: str = ""


def _http_error(exc: NetworkError) -> HTTPException:
    log.warning("Request rejected: %s", "; ".join(exc.errors))
    return HTTPException(status_code=400, detail=exc.errors)


def _public_network(network: BayesianNetwork, source: str) -> dict:
    return {
        "network": {"variables": [var.model_dump() for var in network.variables]},
        "warnings": network.warnings,
        "topological_order": [var.name for var in network.topological_order()],
        "tables": network.tables(),
        "source": source,
    }


def _example_payload(raw: dict, source: str) -> dict:
    try:
        network = validate_network(raw)
    except NetworkError as exc:
        raise _http_error(exc) from exc
    return _public_network(network, source)


@app.post("/api/example")
def load_example() -> dict:
    return _example_payload(RAIN_NETWORK, "example")


@app.post("/api/example/alarm")
def load_alarm_example() -> dict:
    return _example_payload(ALARM_NETWORK, "example")


@app.post("/api/build")
def build_network(body: BuildRequest) -> dict:
    known = match_known_example(body.problem)
    if known:
        raw, source = known
        return _example_payload(raw, source)
    try:
        network = build_network_from_problem(body.problem)
    except NetworkError as exc:
        raise _http_error(exc) from exc
    return _public_network(network, "ollama")


@app.post("/api/query")
def query_network(body: QueryRequest) -> dict:
    try:
        network = validate_network(body.network)
        query, evidence = parse_query(body.query, network)
        result = enumeration_ask(network, query, evidence)
    except NetworkError as exc:
        raise _http_error(exc) from exc
    result["warnings"] = network.warnings
    result["query"] = body.query.strip()
    result["evidence"] = evidence
    return result


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True), name="frontend")
