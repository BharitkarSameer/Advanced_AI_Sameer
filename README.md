# Bayesian network enumeration

A local web app for exact inference on discrete Bayesian networks. You describe a causal problem with probabilities, the app builds the graph and the conditional probability tables, and **enumeration** answers queries of the form P(query | evidence).

This is the same family of reasoning used when a diagnosis, an alarm, or a weather outcome depends on several uncertain causes. The network encodes “what depends on what.” Enumeration turns that into a number you can check.

## What it is for

Real decisions are rarely a single probability. A doctor may need P(disease | test, symptom). A city may need P(flood | rain, drain failure). A security system may need P(burglary | both neighbors called). Those questions are conditionals on a directed acyclic graph of causes.

A Bayesian network stores:

- nodes (Flu, Rain, Alarm, …)
- directed edges from causes to effects
- a CPT at each node: P(node | parents)

Once that structure is in place, any query that names some variables as unknown and some as observed can be answered by summing the joint over the hidden variables. That is **enumeration-ask** (Russell and Norvig): walk the nodes in topological order, multiply CPT entries, sum out variables that are not in the query or the evidence, then normalize.

The same network can later be queried with **variable elimination**, belief propagation, or sampling. Those methods reuse the graph and the CPTs; only the inference engine changes. This project starts with enumeration so every step is exact and easy to follow.

## How the project works

1. **Problem.** Paste a word problem that already contains domains, parents, and probabilities, or load a built-in example (rain / sprinkler / wet-grass, or burglary / earthquake / alarm).
2. **Tables and graph.** Built-in examples load fixed CPTs in Python. A new problem can be sent to a local Ollama model (`qwen2.5-coder:7b` by default), which returns CPTs as arrays of arrays. Python then checks that names are unique, the parent graph is a DAG, each CPT has the right number of rows, and each row sums to 1. The page draws the graph from those parent lists (an arrow from parent to child) and shows every table.
3. **Query.** Type `P(A=a | B=b, C=c)` or `P(A | B=b)` for a full distribution. The server parses the query, runs enumeration-ask, and returns the normalized probability plus a short trace: topological order, hidden variables, unnormalized mass, and the normalizer.

The language model never computes P(query | evidence). Enumeration does.

CPT layout: `cpt[row][column] = P(variable = domain[column] | parent assignment for that row)`. Rows nested-loop over parents from left to right; the last parent changes fastest. A node with no parents has one row.

## Real-world uses of this pattern

| Domain | Typical query |
| --- | --- |
| Medicine | P(disease \| test, symptom) |
| Weather and flooding | P(flood \| rain, soil saturation) |
| Home security | P(burglary \| John called, Mary called) |
| Traffic | P(late \| rain) after chaining rain → traffic → late |
| Reliability | P(system failure \| sensor, backup) |

The app is a teaching and prototyping front end for that pattern: write the story, see the DAG, read the tables, get an exact conditional.

## Further work

Enumeration is the first exact algorithm in the usual syllabus. The same `BayesianNetwork` object (variables, domains, parents, CPTs, topological order) is enough to add:

- **Variable elimination** — eliminate hidden variables in an order, with factors instead of a full tree of recursive sums
- **Junction tree / belief propagation** — reuse messages when many queries share one network
- **Likelihood weighting or Gibbs sampling** — approximate answers on larger graphs

Those would plug in next to `enumeration_ask` without changing how problems are turned into CPTs or how the page draws the graph.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Install [Ollama](https://ollama.com), then:

```powershell
ollama pull qwen2.5-coder:7b
```

`.env` defaults:

```
OLLAMA_HOST=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5-coder:7b
```

## Run

Keep Ollama running, then from the project root:

```powershell
uvicorn backend.main:app --reload
```

Open http://127.0.0.1:8000

1. Click **Rain example** for the sprinkler network with no model call. Query `P(Rain=T | WetGrass=T)` (about `0.384853`).
2. Click **Alarm example** for burglary / earthquake / alarm. Query `P(Burglary=T | JohnCalls=T, MaryCalls=T)` (about `0.284`).
3. For a new problem, paste the text and click **Build network**. Check the graph and tables, then ask a query.

`P(Name | Evidence=value)` returns a distribution. `P(Name=value | Evidence=value)` returns that probability. Several query variables are allowed when every one has a value, for example `P(Rain=T, Sprinkler=F | WetGrass=T)`.
