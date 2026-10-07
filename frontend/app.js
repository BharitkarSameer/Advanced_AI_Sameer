const EXAMPLE = `Boolean variables Rain, Sprinkler, and WetGrass use domain values T and F, with T first.

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
P(WetGrass=F | Sprinkler=F, Rain=F) = 1.00`;

const ALARM_EXAMPLE = `Boolean variables Burglary, Earthquake, Alarm, JohnCalls, and MaryCalls use domain values T and F, with T first.

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
P(MaryCalls=F | Alarm=F) = 0.99`;

const problemInput = document.querySelector("#problem");
const queryInput = document.querySelector("#query");
const buildButton = document.querySelector("#build");
const askButton = document.querySelector("#ask");
const buildStatus = document.querySelector("#build-status");
const queryStatus = document.querySelector("#query-status");
const warningsBox = document.querySelector("#warnings");
const networkPanel = document.querySelector("#network-panel");
const orderLine = document.querySelector("#order");
const tablesRoot = document.querySelector("#tables");
const answerRoot = document.querySelector("#answer");

let network = null;
let cy = null;

function setStatus(node, message, isError) {
  node.textContent = message || "";
  node.classList.toggle("error", Boolean(isError));
}

async function readError(response) {
  try {
    const payload = await response.json();
    if (Array.isArray(payload.detail)) return payload.detail.join(" ");
    if (typeof payload.detail === "string") return payload.detail;
  } catch (_error) {
    return "The server returned an unexpected response.";
  }
  return "Request failed.";
}

function formatProb(value) {
  if (!Number.isFinite(value)) return String(value);
  const text = value.toFixed(6).replace(/\.?0+$/, "");
  return text === "-0" ? "0" : text;
}

function sameAssignment(left, right) {
  const leftNames = Object.keys(left);
  const rightNames = Object.keys(right);
  if (leftNames.length !== rightNames.length) return false;
  return leftNames.every((name) => left[name] === right[name]);
}

function assignmentText(assignment) {
  const names = Object.keys(assignment);
  if (!names.length) return "(empty)";
  return names.map((name) => `${name}=${assignment[name]}`).join(", ");
}

function clearAnswer() {
  answerRoot.hidden = true;
  answerRoot.replaceChildren();
  setStatus(queryStatus, "");
}

function drawGraph(built) {
  const elements = [];
  for (const variable of built.network.variables) {
    elements.push({ data: { id: variable.name } });
  }
  let edge = 0;
  for (const variable of built.network.variables) {
    for (const parent of variable.parents) {
      edge += 1;
      elements.push({
        data: { id: `e${edge}`, source: parent, target: variable.name },
      });
    }
  }
  if (cy) cy.destroy();
  cy = cytoscape({
    container: document.querySelector("#graph"),
    elements,
    layout: {
      name: "breadthfirst",
      directed: true,
      padding: 28,
      spacingFactor: 1.35,
    },
    style: [
      {
        selector: "node",
        style: {
          label: "data(id)",
          "text-valign": "center",
          "text-halign": "center",
          "background-color": "#1f6f6a",
          color: "#f4fbfa",
          "font-size": 14,
          "font-family": "Georgia, serif",
          width: "label",
          height: 38,
          padding: "12px",
          shape: "round-rectangle",
        },
      },
      {
        selector: "edge",
        style: {
          width: 2,
          "line-color": "#8d8376",
          "target-arrow-color": "#8d8376",
          "target-arrow-shape": "triangle",
          "curve-style": "bezier",
          "arrow-scale": 1.1,
        },
      },
    ],
  });
}

function renderTables(tables) {
  tablesRoot.replaceChildren();
  for (const table of tables) {
    const card = document.createElement("article");
    card.className = "cpt";
    const title = document.createElement("h4");
    title.textContent = table.parents.length
      ? `P(${table.name} | ${table.parents.join(", ")})`
      : `P(${table.name})`;
    const caption = document.createElement("p");
    caption.textContent = `Domain: ${table.domain.join(", ")}`;
    const grid = document.createElement("table");
    const head = document.createElement("tr");
    for (const parent of table.parents) {
      const cell = document.createElement("th");
      cell.textContent = parent;
      head.append(cell);
    }
    if (!table.parents.length) {
      const cell = document.createElement("th");
      cell.textContent = "Parents";
      head.append(cell);
    }
    for (const value of table.domain) {
      const cell = document.createElement("th");
      cell.textContent = `${table.name}=${value}`;
      head.append(cell);
    }
    grid.append(head);
    for (const row of table.rows) {
      const line = document.createElement("tr");
      if (table.parents.length) {
        for (const parent of table.parents) {
          const cell = document.createElement("td");
          cell.textContent = row.parents[parent];
          line.append(cell);
        }
      } else {
        const cell = document.createElement("td");
        cell.textContent = "—";
        line.append(cell);
      }
      for (const probability of row.probs) {
        const cell = document.createElement("td");
        cell.textContent = formatProb(probability);
        line.append(cell);
      }
      grid.append(line);
    }
    card.append(title, caption, grid);
    tablesRoot.append(card);
  }
}

function applyNetwork(built, readyMessage) {
  network = built.network;
  networkPanel.hidden = false;
  orderLine.textContent = `Order: ${built.topological_order.join(" → ")}`;
  drawGraph(built);
  renderTables(built.tables);
  showWarnings(built.warnings || []);
  queryInput.disabled = false;
  askButton.disabled = false;
  setStatus(buildStatus, readyMessage);
}

function resetNetwork() {
  network = null;
  networkPanel.hidden = true;
  queryInput.disabled = true;
  askButton.disabled = true;
  showWarnings([]);
  if (cy) {
    cy.destroy();
    cy = null;
  }
}

function showWarnings(warnings) {
  warningsBox.replaceChildren();
  if (!warnings.length) {
    warningsBox.hidden = true;
    return;
  }
  for (const warning of warnings) {
    const line = document.createElement("p");
    line.textContent = warning;
    warningsBox.append(line);
  }
  warningsBox.hidden = false;
}

function renderAnswer(result) {
  answerRoot.replaceChildren();
  const lead = document.createElement("p");
  lead.className = "answer-lead";
  if (result.query_probability == null) {
    const only = result.distribution[0];
    const name = only ? Object.keys(only.assignment)[0] : "query";
    lead.textContent = `Distribution of ${name}`;
  } else {
    lead.textContent = `${result.query.trim()} = ${formatProb(result.query_probability)}`;
  }

  const hidden = result.hidden.length
    ? result.hidden.join(", ")
    : "none";
  const trace = document.createElement("ol");
  trace.className = "trace";
  for (const sentence of [
    `Topological order: ${result.topological_order.join(" → ")}.`,
    `Hidden variables summed by enumeration: ${hidden}.`,
    `Each unnormalized mass is the sum of the joint over those hidden variables. Divide by ${formatProb(result.normalizer)} to normalize.`,
  ]) {
    const item = document.createElement("li");
    item.textContent = sentence;
    trace.append(item);
  }

  const grid = document.createElement("table");
  grid.className = "dist";
  const head = document.createElement("tr");
  for (const label of ["Assignment", "Unnormalized", "Probability"]) {
    const cell = document.createElement("th");
    cell.textContent = label;
    head.append(cell);
  }
  grid.append(head);
  result.distribution.forEach((item, index) => {
    const line = document.createElement("tr");
    if (result.requested && sameAssignment(item.assignment, result.requested)) {
      line.classList.add("hit");
    }
    const cells = [
      assignmentText(item.assignment),
      formatProb(result.unnormalized[index].mass),
      formatProb(item.probability),
    ];
    for (const text of cells) {
      const cell = document.createElement("td");
      cell.textContent = text;
      line.append(cell);
    }
    grid.append(line);
  });

  answerRoot.append(lead, trace, grid);
  answerRoot.hidden = false;
}

async function loadFixedExample(button, text, path, query) {
  problemInput.value = text;
  queryInput.value = query;
  button.disabled = true;
  buildButton.disabled = true;
  setStatus(buildStatus, "Loading the example tables…");
  clearAnswer();
  try {
    const response = await fetch(path, { method: "POST" });
    if (!response.ok) throw new Error(await readError(response));
    applyNetwork(
      await response.json(),
      `Example loaded without Ollama. Check the tables, then solve ${query}.`,
    );
  } catch (error) {
    resetNetwork();
    setStatus(buildStatus, error.message, true);
  } finally {
    button.disabled = false;
    buildButton.disabled = false;
  }
}

document.querySelector("#load-example").addEventListener("click", () => {
  loadFixedExample(
    document.querySelector("#load-example"),
    EXAMPLE,
    "/api/example",
    "P(Rain=T | WetGrass=T)",
  );
});

document.querySelector("#load-alarm").addEventListener("click", () => {
  loadFixedExample(
    document.querySelector("#load-alarm"),
    ALARM_EXAMPLE,
    "/api/example/alarm",
    "P(Burglary=T | JohnCalls=T, MaryCalls=T)",
  );
});

buildButton.addEventListener("click", async () => {
  buildButton.disabled = true;
  setStatus(buildStatus, "Asking Ollama (qwen2.5-coder:7b) for the CPT tables. The first call can take a minute…");
  clearAnswer();
  try {
    const response = await fetch("/api/build", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ problem: problemInput.value }),
    });
    if (!response.ok) throw new Error(await readError(response));
    applyNetwork(
      await response.json(),
      "Network ready from Ollama. Check the tables, then ask a query.",
    );
  } catch (error) {
    resetNetwork();
    setStatus(buildStatus, error.message, true);
  } finally {
    buildButton.disabled = false;
  }
});

askButton.addEventListener("click", async () => {
  if (!network) return;
  askButton.disabled = true;
  setStatus(queryStatus, "Running enumeration…");
  try {
    const response = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ network, query: queryInput.value }),
    });
    if (!response.ok) throw new Error(await readError(response));
    renderAnswer(await response.json());
    setStatus(queryStatus, "");
  } catch (error) {
    answerRoot.hidden = true;
    answerRoot.replaceChildren();
    setStatus(queryStatus, error.message, true);
  } finally {
    askButton.disabled = false;
  }
});

queryInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !askButton.disabled) askButton.click();
});
