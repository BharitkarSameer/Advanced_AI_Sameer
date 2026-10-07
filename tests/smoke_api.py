"""Smoke-check the running server. Not part of the app."""

import json
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"


def get(path: str) -> bytes:
    with urllib.request.urlopen(BASE + path) as response:
        body = response.read()
        print(path, response.status, response.headers.get("content-type"), len(body))
        return body


html = get("/").decode()
assert "Build network" in html
assert 'id="query"' in html
css = get("/style.css").decode()
assert ".dist tr.hit" in css
js = get("/app.js").decode()
assert "/api/query" in js
print("health", get("/api/health").decode())

network = {
    "variables": [
        {"name": "Rain", "domain": ["T", "F"], "parents": [], "cpt": [[0.2, 0.8]]},
        {
            "name": "Sprinkler",
            "domain": ["T", "F"],
            "parents": ["Rain"],
            "cpt": [[0.01, 0.99], [0.4, 0.6]],
        },
        {
            "name": "WetGrass",
            "domain": ["T", "F"],
            "parents": ["Sprinkler", "Rain"],
            "cpt": [[0.99, 0.01], [0.90, 0.10], [0.90, 0.10], [0.00, 1.00]],
        },
    ]
}
request = urllib.request.Request(
    BASE + "/api/query",
    data=json.dumps(
        {"network": network, "query": "P(Rain=T | WetGrass=T)"}
    ).encode(),
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(request) as response:
    payload = json.load(response)
print("query", round(payload["query_probability"], 6), payload["topological_order"])

empty = urllib.request.Request(
    BASE + "/api/build",
    data=json.dumps({"problem": ""}).encode(),
    headers={"Content-Type": "application/json"},
)
try:
    urllib.request.urlopen(empty)
    raise SystemExit("empty build should fail")
except urllib.error.HTTPError as exc:
    print("empty build", exc.code, exc.read().decode())
