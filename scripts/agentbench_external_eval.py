from __future__ import annotations

import argparse
import glob
import json
import random
import statistics
import time
from pathlib import Path

from agentweave.engine import AgentMatcher, PlacementEngine, TrustEngine
from agentweave.models import AgentProfile, Capability, ExecutionProfile, Requirement, TrustVector

AGENTBENCH_PIN = "d1e4a10db08c87075c78972e48ecc182be03e2d5"

DOMAIN_SPECS = {
    "database": {
        "capabilities": {"database", "sql", "reasoning"},
        "knowledge": {"tabular-data"},
    },
    "knowledge-graph": {
        "capabilities": {"knowledge-graph", "retrieval", "reasoning"},
        "knowledge": {"graph-data"},
    },
    "operating-system": {
        "capabilities": {"operating-system", "shell", "reasoning"},
        "knowledge": {"linux"},
    },
}


def _trust(v: float) -> TrustVector:
    return TrustVector(v, v, v, v, v, v, v)


def _caps(names, proficiency: float, validated: bool):
    return [Capability(name, proficiency, validated) for name in sorted(names)]


def build_agent_catalog() -> list[AgentProfile]:
    """Synthetic catalog used to isolate AgentWeave routing on external tasks.

    AgentBench task text/environment labels are external published data. The candidate
    agent catalog, declared proficiencies, trust, latency and cost are deliberately
    synthetic and fixed so routing methods can be compared reproducibly.
    """
    return [
        AgentProfile(
            "db-specialist",
            "Database Specialist",
            _caps(DOMAIN_SPECS["database"]["capabilities"], 0.90, True),
            domains=["database"],
            knowledge=["tabular-data"],
            trust=_trust(0.80),
            execution=ExecutionProfile(latency_ms=130.0, cost=0.30, privacy_level="confidential"),
            metadata={"agentbench_domains": ["database"]},
        ),
        AgentProfile(
            "kg-specialist",
            "Knowledge Graph Specialist",
            _caps(DOMAIN_SPECS["knowledge-graph"]["capabilities"], 0.91, True),
            domains=["knowledge-graph"],
            knowledge=["graph-data"],
            trust=_trust(0.82),
            execution=ExecutionProfile(latency_ms=170.0, cost=0.36, privacy_level="confidential"),
            metadata={"agentbench_domains": ["knowledge-graph"]},
        ),
        AgentProfile(
            "os-specialist",
            "Operating System Specialist",
            _caps(DOMAIN_SPECS["operating-system"]["capabilities"], 0.89, True),
            domains=["operating-system"],
            knowledge=["linux"],
            trust=_trust(0.79),
            execution=ExecutionProfile(latency_ms=95.0, cost=0.24, privacy_level="confidential"),
            metadata={"agentbench_domains": ["operating-system"]},
        ),
        AgentProfile(
            "broad-generalist",
            "Broad Generalist",
            _caps(set().union(*(v["capabilities"] for v in DOMAIN_SPECS.values())), 0.96, False),
            domains=["general"],
            knowledge=[],
            trust=_trust(0.95),
            execution=ExecutionProfile(latency_ms=70.0, cost=0.15, privacy_level="standard"),
            metadata={"agentbench_domains": []},
        ),
        AgentProfile(
            "reasoning-generalist",
            "Reasoning Generalist",
            _caps({"reasoning", "analysis"}, 0.93, True),
            domains=["general"],
            knowledge=[],
            trust=_trust(0.88),
            execution=ExecutionProfile(latency_ms=60.0, cost=0.12, privacy_level="standard"),
            metadata={"agentbench_domains": []},
        ),
    ]


def load_dbbench(root: Path, limit: int) -> list[dict]:
    path = root / "data/dbbench/standard.jsonl"
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            if not line.strip():
                continue
            item = json.loads(line)
            rows.append({
                "domain": "database",
                "id": f"db-{idx}",
                "text": item.get("description", ""),
                "source": item.get("source"),
            })
            if len(rows) >= limit:
                break
    return rows


def load_kg(root: Path, limit: int) -> list[dict]:
    path = root / "data/knowledgegraph/std.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for idx, item in enumerate(data[:limit]):
        rows.append({
            "domain": "knowledge-graph",
            "id": item.get("qid") or f"kg-{idx}",
            "text": item.get("question", ""),
            "source": item.get("source"),
        })
    return rows


def load_os(root: Path, limit: int) -> list[dict]:
    rows = []
    for filename in sorted(glob.glob(str(root / "data/os_interaction/data/*/*.json"))):
        try:
            data = json.loads(Path(filename).read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(data, list):
            continue
        for idx, item in enumerate(data):
            text = item.get("description", "") if isinstance(item, dict) else ""
            if not text:
                continue
            rows.append({
                "domain": "operating-system",
                "id": f"os-{Path(filename).stem}-{idx}",
                "text": text,
                "source": Path(filename).name,
            })
            if len(rows) >= limit:
                return rows
    return rows


def load_tasks(root: Path, per_domain: int) -> list[dict]:
    tasks = []
    tasks.extend(load_dbbench(root, per_domain))
    tasks.extend(load_kg(root, per_domain))
    tasks.extend(load_os(root, per_domain))
    if not tasks:
        raise RuntimeError("No AgentBench tasks were loaded")
    return tasks


def requirement_for(task: dict) -> Requirement:
    spec = DOMAIN_SPECS[task["domain"]]
    return Requirement(
        text=task["text"],
        capabilities=set(spec["capabilities"]),
        domains={task["domain"]},
        knowledge=set(spec["knowledge"]),
    )


def capability_only(req: Requirement, agents: list[AgentProfile]) -> AgentProfile:
    def score(a: AgentProfile):
        cmap = {c.name: c for c in a.capabilities}
        matched = req.capabilities & set(cmap)
        coverage = len(matched) / max(1, len(req.capabilities))
        proficiency = statistics.mean(cmap[c].proficiency for c in matched) if matched else 0.0
        return coverage, proficiency
    return max(agents, key=score)


def trust_only(agents: list[AgentProfile]) -> AgentProfile:
    return max(agents, key=lambda a: a.trust.score())


def fixed_single_best(agents: list[AgentProfile]) -> AgentProfile:
    # A conventional fixed-router baseline: choose one globally strongest prior agent
    # for every task, without looking at the task domain.
    return max(agents, key=lambda a: (a.trust.score(), -a.execution.cost, -a.execution.latency_ms))


def is_specialist_success(agent: AgentProfile, domain: str) -> bool:
    return domain in set(agent.metadata.get("agentbench_domains", []))


def evaluate(tasks: list[dict], seed: int = 17) -> dict:
    agents = build_agent_catalog()
    matcher = AgentMatcher(TrustEngine(), PlacementEngine(), use_native=False)
    rng = random.Random(seed)
    fixed_agent = fixed_single_best(agents)
    methods = {name: [] for name in ("agentweave", "single-best", "random", "capability-only", "trust-only")}

    for task in tasks:
        req = requirement_for(task)
        selectors = {
            "agentweave": lambda: matcher.rank(req, agents)[0].agent,
            "single-best": lambda: fixed_agent,
            "random": lambda: rng.choice(agents),
            "capability-only": lambda: capability_only(req, agents),
            "trust-only": lambda: trust_only(agents),
        }
        for method, select in selectors.items():
            started = time.perf_counter_ns()
            selected = select()
            elapsed_us = (time.perf_counter_ns() - started) / 1000.0
            methods[method].append({
                "domain": task["domain"],
                "task_id": task["id"],
                "selected_agent": selected.agent_id,
                "specialist_selection_success": is_specialist_success(selected, task["domain"]),
                "selection_compute_us": elapsed_us,
                "catalog_latency_ms": selected.execution.latency_ms,
                "catalog_cost": selected.execution.cost,
            })

    def summarize(rows: list[dict]):
        return {
            "tasks": len(rows),
            "specialist_selection_rate": sum(r["specialist_selection_success"] for r in rows) / max(1, len(rows)),
            "mean_selection_compute_us": statistics.mean(r["selection_compute_us"] for r in rows),
            "mean_catalog_latency_ms": statistics.mean(r["catalog_latency_ms"] for r in rows),
            "mean_catalog_cost": statistics.mean(r["catalog_cost"] for r in rows),
        }

    aggregate = {name: summarize(rows) for name, rows in methods.items()}
    per_domain = {}
    for name, rows in methods.items():
        per_domain[name] = {}
        for domain in DOMAIN_SPECS:
            subset = [r for r in rows if r["domain"] == domain]
            if subset:
                per_domain[name][domain] = summarize(subset)

    counts = {domain: sum(t["domain"] == domain for t in tasks) for domain in DOMAIN_SPECS}
    return {
        "benchmark": "AgentBench external routing evaluation",
        "agentbench_repository": "THUDM/AgentBench",
        "agentbench_commit": AGENTBENCH_PIN,
        "task_counts": counts,
        "total_tasks": len(tasks),
        "metric_boundary": {
            "external_real_data": "Published AgentBench task descriptions and environment labels from DBBench, KnowledgeGraph and OS Interaction.",
            "synthetic_data": "Candidate agent catalog, proficiencies, validation flags, trust, latency and cost values.",
            "success_metric": "Specialist-selection rate: whether the router selected the synthetic specialist assigned to the published AgentBench environment.",
            "not_measured": "This is not original AgentBench environment task-completion success rate; no LLM or full AgentBench Docker task environment is executed in this proof.",
            "real_timing": "selection_compute_us is measured wall-clock routing computation in this run.",
            "proxy_timing_cost": "catalog_latency_ms and catalog_cost are fixed synthetic catalog attributes, not observed model latency or billed cost.",
        },
        "aggregate": aggregate,
        "per_domain": per_domain,
        "raw": methods,
    }


def markdown_report(result: dict) -> str:
    lines = [
        "# AgentBench external routing evaluation",
        "",
        f"Pinned AgentBench commit: `{result['agentbench_commit']}`",
        f"Tasks: **{result['total_tasks']}** — " + ", ".join(f"{k}: {v}" for k, v in result["task_counts"].items()),
        "",
        "This uses **external published AgentBench task data** but a **synthetic candidate-agent catalog**. The success metric below is specialist-selection accuracy, not the original AgentBench end-to-end task success rate.",
        "",
        "| Method | Specialist selection | Router compute | Catalog latency proxy | Catalog cost proxy |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, row in result["aggregate"].items():
        lines.append(
            f"| {name} | {100*row['specialist_selection_rate']:.1f}% | "
            f"{row['mean_selection_compute_us']:.1f} us | {row['mean_catalog_latency_ms']:.1f} ms | {row['mean_catalog_cost']:.3f} |"
        )
    lines += [
        "",
        "## Interpretation boundary",
        "",
        "- **External data:** task descriptions/environment labels come from the official AgentBench repository.",
        "- **Synthetic data:** candidate agents, trust, proficiency, latency and cost are fixed synthetic values.",
        "- **Real measurement:** router compute latency is measured during this run.",
        "- **Not claimed:** original AgentBench task-completion SR, model answer quality, real provider latency, or billed model cost.",
        "",
    ]
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--agentbench-root", required=True)
    p.add_argument("--per-domain", type=int, default=200)
    p.add_argument("--seed", type=int, default=17)
    p.add_argument("--json-out", default="agentbench-routing-results.json")
    p.add_argument("--md-out", default="agentbench-routing-results.md")
    args = p.parse_args()

    root = Path(args.agentbench_root)
    tasks = load_tasks(root, args.per_domain)
    result = evaluate(tasks, args.seed)
    Path(args.json_out).write_text(json.dumps(result, indent=2), encoding="utf-8")
    report = markdown_report(result)
    Path(args.md_out).write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
