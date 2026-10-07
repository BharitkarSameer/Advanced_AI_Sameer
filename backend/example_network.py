"""The rain / sprinkler / wet-grass network used as the built-in example."""

from __future__ import annotations

RAIN_PROBLEM = """Boolean variables Rain, Sprinkler, and WetGrass use domain values T and F, with T first.

Rain has no parents.
P(Rain=T) = 0.2
P(Rain=F) = 0.8

Sprinkler depends only on Rain.
P(Sprinkler=T | Rain=T) = 0.01
P(Sprinkler=F | Rain=T) = 0.99
P(Sprinkler=T | Rain=F) = 0.4
P(Sprinkler=F | Rain=F) = 0.6

WetGrass depends on Sprinkler and Rain, in that parent order.
P(WetGrass=T | Sprinkler=T, Rain=T) = 0.99
P(WetGrass=F | Sprinkler=T, Rain=T) = 0.01
P(WetGrass=T | Sprinkler=T, Rain=F) = 0.90
P(WetGrass=F | Sprinkler=T, Rain=F) = 0.10
P(WetGrass=T | Sprinkler=F, Rain=T) = 0.90
P(WetGrass=F | Sprinkler=F, Rain=T) = 0.10
P(WetGrass=T | Sprinkler=F, Rain=F) = 0.00
P(WetGrass=F | Sprinkler=F, Rain=F) = 1.00
"""

RAIN_NETWORK = {
    "variables": [
        {
            "name": "Rain",
            "domain": ["T", "F"],
            "parents": [],
            "cpt": [[0.2, 0.8]],
        },
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
            "cpt": [
                [0.99, 0.01],
                [0.90, 0.10],
                [0.90, 0.10],
                [0.00, 1.00],
            ],
        },
    ]
}

ALARM_PROBLEM = """Boolean variables Burglary, Earthquake, Alarm, JohnCalls, and MaryCalls use domain values T and F, with T first.

Burglary has no parents.
P(Burglary=T) = 0.001
P(Burglary=F) = 0.999

Earthquake has no parents.
P(Earthquake=T) = 0.002
P(Earthquake=F) = 0.998

Alarm depends on Burglary and Earthquake, in that parent order.
P(Alarm=T | Burglary=T, Earthquake=T) = 0.95
P(Alarm=F | Burglary=T, Earthquake=T) = 0.05
P(Alarm=T | Burglary=T, Earthquake=F) = 0.94
P(Alarm=F | Burglary=T, Earthquake=F) = 0.06
P(Alarm=T | Burglary=F, Earthquake=T) = 0.29
P(Alarm=F | Burglary=F, Earthquake=T) = 0.71
P(Alarm=T | Burglary=F, Earthquake=F) = 0.001
P(Alarm=F | Burglary=F, Earthquake=F) = 0.999

JohnCalls depends only on Alarm.
P(JohnCalls=T | Alarm=T) = 0.90
P(JohnCalls=F | Alarm=T) = 0.10
P(JohnCalls=T | Alarm=F) = 0.05
P(JohnCalls=F | Alarm=F) = 0.95

MaryCalls depends only on Alarm.
P(MaryCalls=T | Alarm=T) = 0.70
P(MaryCalls=F | Alarm=T) = 0.30
P(MaryCalls=T | Alarm=F) = 0.01
P(MaryCalls=F | Alarm=F) = 0.99
"""

ALARM_NETWORK = {
    "variables": [
        {
            "name": "Burglary",
            "domain": ["T", "F"],
            "parents": [],
            "cpt": [[0.001, 0.999]],
        },
        {
            "name": "Earthquake",
            "domain": ["T", "F"],
            "parents": [],
            "cpt": [[0.002, 0.998]],
        },
        {
            "name": "Alarm",
            "domain": ["T", "F"],
            "parents": ["Burglary", "Earthquake"],
            "cpt": [
                [0.95, 0.05],
                [0.94, 0.06],
                [0.29, 0.71],
                [0.001, 0.999],
            ],
        },
        {
            "name": "JohnCalls",
            "domain": ["T", "F"],
            "parents": ["Alarm"],
            "cpt": [[0.90, 0.10], [0.05, 0.95]],
        },
        {
            "name": "MaryCalls",
            "domain": ["T", "F"],
            "parents": ["Alarm"],
            "cpt": [[0.70, 0.30], [0.01, 0.99]],
        },
    ]
}


def _folded(text: str) -> str:
    return " ".join((text or "").split()).lower()


def match_known_example(problem: str) -> tuple[dict, str] | None:
    """Return canned tables when the user pasted a built-in problem."""
    folded = _folded(problem)
    if not folded:
        return None
    if folded == _folded(RAIN_PROBLEM) or (
        "wetgrass" in folded and "sprinkler" in folded and "p(rain=t) = 0.2" in folded
    ):
        return RAIN_NETWORK, "example"
    if folded == _folded(ALARM_PROBLEM) or (
        "burglary" in folded
        and "earthquake" in folded
        and "johncalls" in folded
        and "marycalls" in folded
        and "p(burglary=t) = 0.001" in folded
    ):
        return ALARM_NETWORK, "example"
    return None
