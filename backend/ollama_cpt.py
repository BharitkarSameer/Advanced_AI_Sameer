"""Turn a word problem into a validated Bayesian network with a local Ollama model."""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

from backend.bn import BayesianNetwork, NetworkError, validate_network

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

log = logging.getLogger("ollama_cpt")

DEFAULT_HOST = "http://127.0.0.1:11434"
DEFAULT_MODEL = "qwen2.5-coder:7b"
REQUEST_TIMEOUT = 180

SYSTEM = """You extract a discrete Bayesian network from a word problem.

Use only probabilities that are stated or that follow by complement when the problem gives the other value. Do not invent a missing conditional probability. If any CPT entry cannot be filled from the problem, set error to a short explanation and return an empty variables list.

When the problem is complete, set error to an empty string.

Return a single JSON object and nothing else. No markdown.

JSON rules:
- variables is a JSON array of objects. Each object has keys name, domain, parents, and cpt.
- Do not write a variable as a nested array such as ["Rain", ["T","F"], [], [[0.2,0.8]]]. Always use an object.
- domain is the list of values for that node, in the order used by the CPT columns. Put the affirmative or true value first when the problem uses true/false, yes/no, or T/F.
- parents lists the conditioning variables from left to right. Use an empty list when the node is unconditional.
- cpt is an array of arrays. cpt[row][column] = P(this variable = domain[column] | parent assignment for that row).
- Row order is nested loops over the parents from left to right. The last parent changes fastest. A node with no parents has exactly one row.
- Every row must sum to 1. Every probability must be between 0 and 1.
- Use the same variable name spelling everywhere. Prefer the names in the problem, without spaces if the problem uses a single token such as WetGrass.
- Edges run from each parent to the child. The parent graph must be acyclic.

Example. Rain has domain ["T","F"] and no parents, with P(Rain=T)=0.2:
{"name":"Rain","domain":["T","F"],"parents":[],"cpt":[[0.2,0.8]]}

Sprinkler has domain ["T","F"] and parent ["Rain"]. The first row is Rain=T and the second row is Rain=F:
{"name":"Sprinkler","domain":["T","F"],"parents":["Rain"],"cpt":[[0.01,0.99],[0.4,0.6]]}

WetGrass given parents ["Sprinkler","Rain"] has four rows, in this order:
Sprinkler=T Rain=T, Sprinkler=T Rain=F, Sprinkler=F Rain=T, Sprinkler=F Rain=F.
"""


class IncompleteProblem(NetworkError):
    """The problem statement does not contain a complete CPT."""


def _settings() -> tuple[str, str]:
    host = os.environ.get("OLLAMA_HOST", DEFAULT_HOST).strip() or DEFAULT_HOST
    model = os.environ.get("OLLAMA_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    return host.rstrip("/"), model


def _strip_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def _parse_json_object(text: str) -> dict:
    stripped = _strip_fence(text)
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start < 0 or end <= start:
            raise NetworkError(["Ollama did not return valid JSON."]) from None
        try:
            payload = json.loads(stripped[start : end + 1])
        except json.JSONDecodeError as exc:
            raise NetworkError([f"Ollama did not return valid JSON ({exc})."]) from exc
    if not isinstance(payload, dict):
        raise NetworkError(["Ollama returned JSON that is not an object."])
    return payload


def _generate(host: str, model: str, prompt: str) -> dict:
    url = f"{host}/api/chat"
    body = {
        "model": model,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0},
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise NetworkError(
            [f"Ollama request failed ({exc.code}). Is the model {model!r} pulled? {detail[:400]}"]
        ) from exc
    except urllib.error.URLError as exc:
        raise NetworkError(
            [
                f"Cannot reach Ollama at {host}. Start it with `ollama serve`, "
                f"then confirm `ollama list` includes {model}."
            ]
        ) from exc
    except TimeoutError as exc:
        raise NetworkError(
            [f"Ollama timed out after {REQUEST_TIMEOUT}s. The first load of {model} can be slow."]
        ) from exc

    message = raw.get("message") or {}
    text = message.get("content") if isinstance(message, dict) else None
    if not text:
        raise NetworkError(["Ollama returned an empty response."])
    return _parse_json_object(text)


def _as_variable_object(item: object, index: int) -> dict | None:
    """Turn common Ollama list/tuple shapes into {name, domain, parents, cpt}."""
    if isinstance(item, dict):
        return item
    if not isinstance(item, list) or len(item) < 3:
        return None
    name, domain, third = item[0], item[1], item[2]
    if not isinstance(name, str):
        return None
    if len(item) >= 4:
        return {
            "name": name,
            "domain": domain,
            "parents": third,
            "cpt": item[3],
        }
    if isinstance(third, list) and third and isinstance(third[0], list):
        return {"name": name, "domain": domain, "parents": [], "cpt": third}
    return None


def normalize_extracted(payload: dict) -> dict:
    """Accept a few messy layouts from small local models, then validate strictly."""
    variables = payload.get("variables")
    if isinstance(variables, dict):
        converted = []
        for name, body in variables.items():
            if isinstance(body, dict):
                converted.append({"name": body.get("name", name), **body})
            elif isinstance(body, list):
                converted.append(
                    _as_variable_object([name] + body, 0)
                    or {"name": name, "cpt": body}
                )
            else:
                converted.append(body)
        payload = dict(payload)
        payload["variables"] = converted
        variables = converted
    if isinstance(variables, list):
        payload = dict(payload)
        payload["variables"] = [
            _as_variable_object(item, index) or item
            for index, item in enumerate(variables)
        ]
    return payload


def _network_from_payload(payload: dict) -> BayesianNetwork:
    payload = normalize_extracted(payload)
    variables = payload.get("variables")
    message = str(payload.get("error") or "").strip()
    if not variables:
        if message:
            raise IncompleteProblem([message])
        raise NetworkError(["Ollama returned no variables."])
    return validate_network(payload)


def build_network_from_problem(problem: str) -> BayesianNetwork:
    """Ask Ollama for CPT JSON, validate it, and retry once if validation fails."""
    text = (problem or "").strip()
    if not text:
        raise NetworkError(["Paste a problem statement first."])

    host, model = _settings()
    first = _generate(
        host,
        model,
        "Extract the Bayesian network from this problem.\n\n" + text,
    )
    try:
        return _network_from_payload(first)
    except IncompleteProblem:
        raise
    except NetworkError as exc:
        log.warning("Ollama CPT failed validation: %s", "; ".join(exc.errors))
        log.warning("Ollama JSON: %s", json.dumps(first)[:2000])
        errors = "\n".join(f"- {error}" for error in exc.errors)
        repair = (
            "The previous JSON failed validation. Return a corrected network for the "
            "same problem. Keep every probability that the problem states. "
            "Return JSON only.\n\n"
            f"Validation errors:\n{errors}\n\n"
            f"Previous JSON:\n{json.dumps(first)}\n\n"
            f"Problem:\n{text}"
        )
        second = _generate(host, model, repair)
        try:
            return _network_from_payload(second)
        except IncompleteProblem:
            raise
        except NetworkError as second_error:
            joined = " ".join(second_error.errors)
            raise NetworkError(
                [f"The CPT is still invalid after a correction attempt. {joined}"]
            ) from second_error
