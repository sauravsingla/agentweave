from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path

from agentweave import RequirementAnalyzer

AGENCYBENCH_COMMIT = "ec65324be69e81bd4fe394ef6a86d48b8fa5da56"
FAMILIES = ["Backend", "Code", "Frontend", "Game", "Research", "MCP"]

PROFILES = {
    "Backend": "backend systems services server API database persistence authentication concurrency storage CLI Java Python C++ FastAPI MongoDB webhook transaction queue",
    "Code": "software engineering coding debugging refactoring repository implementation tests CI scientific programming algorithms equations solvers code agent developer tooling",
    "Frontend": "frontend web user interface browser HTML CSS JavaScript TypeScript responsive layout DOM SVG React visual UI 3D landing page interaction",
    "Game": "game development browser game gameplay controls physics score scoring win loss board puzzle persistence diagnostics animation player collision",
    "Research": "deep research web search evidence citations datasets filings sources analysis synthesis report verification public companies information retrieval",
    "MCP": "model context protocol MCP tool use tool server GitHub issue branch pull request workspace file operations protocol integration automation",
}

PHRASES = {
    "Backend": ["backend", "fastapi", "mongodb", "webhook", "transactional", "authentication", "concurrency", "task manager", "console chat"],
    "Code": ["debug", "refactor", "equation", "repository", "ci", "solver", "scientific", "implement", "code agent"],
    "Frontend": ["frontend", "responsive", "svg", "dom", "3d", "landing", "layout", "browser view", "user interface"],
    "Game": ["game", "gameplay", "score", "win detection", "flappy", "snake", "sudoku", "minesweeper", "tic-tac-toe", "gomoku", "fruit ninja", "2048"],
    "Research": ["research", "citations", "filings", "datasets", "web evidence", "public-company", "multi-hop", "report"],
    "MCP": ["mcp", "model context protocol", "github mcp", "create an issue", "pull request", "reorganize a workspace"],
}

TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+.#_-]*")
STOP = {
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with", "as", "is", "be", "by", "from", "that", "this", "it",
    "must", "should", "using", "use", "build", "create", "add", "make", "implement", "task", "final", "goal", "environment", "behavior",
}


def tokens(text: str) -> list[str]:
    return [t for t in TOKEN_RE.findall(text.lower()) if t not in STOP and len(t) > 1]


def visible_query(raw: str) -> str:
    text = raw
    for marker in ("\nDeliverables:", "\nRubric:"):
        if marker in text:
            text = text.split(marker, 1)[0]
    if text.startswith("Query:\n"):
        text = text[len("Query:\n"):]
    return text.strip()


def load_tasks(root: Path) -> list[dict]:
    tasks = []
    for family in FAMILIES:
        for path in sorted((root / "AgencyBench-v2" / family).glob("scenario*/description.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            subtasks = []
            for key, value in data.items():
                if re.fullmatch(r"subtask\d+", str(key)) and isinstance(value, str):
                    subtasks.append((int(str(key)[7:]), value))
            scenario_id = f"{family}/{path.parent.name}"
            for number, raw in sorted(subtasks):
                tasks.append({
                    "id": f"{scenario_id}/subtask{number}",
                    "scenario": scenario_id,
                    "subtask": number,
                    "family": family,
                    "query": visible_query(raw),
                })
    return tasks


def cosine(q: Counter, p: Counter, idf: dict[str, float]) -> float:
    dot = sum(q[t] * p.get(t, 0) * (idf.get(t, 1.0) ** 2) for t in q)
    qn = math.sqrt(sum((v * idf.get(t, 1.0)) ** 2 for t, v in q.items()))
    pn = math.sqrt(sum((v * idf.get(t, 1.0)) ** 2 for t, v in p.items()))
    return dot / (qn * pn) if qn and pn else 0.0


def build_router(tasks: list[dict]):
    profile_tf = {k: Counter(tokens(v)) for k, v in PROFILES.items()}
    docs = [set(tokens(t["query"])) for t in tasks] + [set(tokens(v)) for v in PROFILES.values()]
    df = Counter()
    for d in docs:
        df.update(d)
    n = len(docs)
    idf = {t: math.log((n + 1) / (c + 1)) + 1.0 for t, c in df.items()}
    analyzer = RequirementAnalyzer()

    def rank(text: str) -> list[tuple[str, float]]:
        qtf = Counter(tokens(text))
        low = text.lower()
        req = analyzer.analyze(text)
        caps = set(getattr(req, "capabilities", set()) or set())
        scores = {}
        for family in FAMILIES:
            score = cosine(qtf, profile_tf[family], idf)
            score += min(0.45, 0.09 * sum(1 for p in PHRASES[family] if p in low))
            if family == "Research" and ("research" in caps or "retrieval" in caps):
                score += 0.18
            if family in {"Backend", "Code", "Frontend", "Game"} and "coding" in caps:
                score += 0.04
            if family == "MCP" and "mcp" in low:
                score += 0.30
            scores[family] = score
        return sorted(scores.items(), key=lambda x: (-x[1], x[0]))

    return rank


def _scenario_groups(tasks: list[dict]) -> dict[str, list[dict]]:
    groups = defaultdict(list)
    for task in tasks:
        groups[task["scenario"]].append(task)
    for values in groups.values():
        values.sort(key=lambda x: x["subtask"])
    return dict(groups)


def _margin(ranked: list[tuple[str, float]]) -> float:
    if len(ranked) < 2:
        return ranked[0][1] if ranked else 0.0
    return ranked[0][1] - ranked[1][1]


def _heldout_split(tasks: list[dict], train_fraction: float = 0.6):
    groups = _scenario_groups(tasks)
    train_scenarios = set()
    test_scenarios = set()
    for family in FAMILIES:
        names = [name for name, rows in groups.items() if rows[0]["family"] == family]
        names = sorted(names, key=lambda name: hashlib.sha256(("agentweave-agencybench-v1:" + name).encode()).hexdigest())
        cut = max(1, min(len(names) - 1, int(round(len(names) * train_fraction)))) if len(names) > 1 else len(names)
        train_scenarios.update(names[:cut])
        test_scenarios.update(names[cut:])
    train = [t for t in tasks if t["scenario"] in train_scenarios]
    test = [t for t in tasks if t["scenario"] in test_scenarios]
    return train, test, sorted(train_scenarios), sorted(test_scenarios)


def build_dev_trained_router(train_tasks: list[dict]):
    family_text = {family: [PROFILES[family]] for family in FAMILIES}
    for task in train_tasks:
        family_text[task["family"]].append(task["query"])
    family_tf = {family: Counter(tokens("\n".join(parts))) for family, parts in family_text.items()}
    docs = [set(tf) for tf in family_tf.values()]
    df = Counter()
    for d in docs:
        df.update(d)
    n = len(docs)
    idf = {t: math.log((n + 1) / (c + 1)) + 1.0 for t, c in df.items()}

    def rank(text: str):
        qtf = Counter(tokens(text))
        return sorted(((family, cosine(qtf, family_tf[family], idf)) for family in FAMILIES), key=lambda x: (-x[1], x[0]))

    return rank


def evaluate_heldout(tasks: list[dict]) -> dict:
    train, test, train_scenarios, test_scenarios = _heldout_split(tasks)
    rank = build_dev_trained_router(train)
    hits1 = hits2 = hits3 = 0
    per_family_total = Counter()
    per_family_hit = Counter()
    for task in test:
        ranked = rank(task["query"])
        names = [x[0] for x in ranked]
        per_family_total[task["family"]] += 1
        ok = names[0] == task["family"]
        hits1 += int(ok)
        hits2 += int(task["family"] in names[:2])
        hits3 += int(task["family"] in names[:3])
        per_family_hit[task["family"]] += int(ok)
    return {
        "protocol": "deterministic scenario-stratified 60/40 split; family centroids built only from development-scenario query text plus fixed generic profiles",
        "train_tasks": len(train),
        "test_tasks": len(test),
        "train_scenarios": train_scenarios,
        "test_scenarios": test_scenarios,
        "hit1": hits1 / len(test) if test else 0.0,
        "hit2": hits2 / len(test) if test else 0.0,
        "hit3": hits3 / len(test) if test else 0.0,
        "per_family": {
            f: {"tasks": per_family_total[f], "hit1": per_family_hit[f] / per_family_total[f] if per_family_total[f] else 0.0}
            for f in FAMILIES
        },
    }


def evaluate(tasks: list[dict]) -> dict:
    rank = build_router(tasks)
    rng = random.Random(7)
    family_counts = Counter(t["family"] for t in tasks)
    single_best = family_counts.most_common(1)[0][0]
    correct1 = correct2 = correct3 = random_correct = single_correct = 0
    confusion = defaultdict(Counter)
    latencies = []
    margins = []
    rows = []

    for task in tasks:
        start = time.perf_counter()
        ranked = rank(task["query"])
        latencies.append((time.perf_counter() - start) * 1000.0)
        predicted = ranked[0][0]
        top2 = [x[0] for x in ranked[:2]]
        top3 = [x[0] for x in ranked[:3]]
        correct1 += int(predicted == task["family"])
        correct2 += int(task["family"] in top2)
        correct3 += int(task["family"] in top3)
        random_correct += int(rng.choice(FAMILIES) == task["family"])
        single_correct += int(single_best == task["family"])
        confusion[task["family"]][predicted] += 1
        margins.append(_margin(ranked))
        rows.append({"id": task["id"], "scenario": task["scenario"], "subtask": task["subtask"], "ground_truth": task["family"], "prediction": predicted, "top2": top2, "top3": top3, "margin": _margin(ranked), "scores": ranked})

    per_family = {}
    for family in FAMILIES:
        total = family_counts[family]
        hit = confusion[family][family]
        per_family[family] = {"tasks": total, "hit1": hit / total if total else 0.0}

    groups = _scenario_groups(tasks)
    scenario_rows = []
    cumulative_correct1 = cumulative_correct3 = 0
    first_correct = later_correct = first_total = later_total = 0
    stable_transitions = total_transitions = 0
    scenario_majority_correct = 0

    for scenario, subtasks in sorted(groups.items()):
        cumulative_text = []
        independent_predictions = []
        cumulative_predictions = []
        family = subtasks[0]["family"]
        for idx, task in enumerate(subtasks):
            independent = rank(task["query"])
            independent_predictions.append(independent[0][0])
            cumulative_text.append(task["query"])
            cumulative_ranked = rank("\n\nPrevious/Current task context:\n" + "\n\n".join(cumulative_text))
            cumulative_predictions.append(cumulative_ranked[0][0])
            cumulative_correct1 += int(cumulative_ranked[0][0] == family)
            cumulative_correct3 += int(family in [x[0] for x in cumulative_ranked[:3]])
            if idx == 0:
                first_total += 1
                first_correct += int(independent[0][0] == family)
            else:
                later_total += 1
                later_correct += int(independent[0][0] == family)
                total_transitions += 1
                stable_transitions += int(independent_predictions[-1] == independent_predictions[-2])

        majority = Counter(independent_predictions).most_common()
        max_count = majority[0][1]
        tied = sorted([name for name, count in majority if count == max_count])
        majority_prediction = tied[0]
        scenario_majority_correct += int(majority_prediction == family)
        scenario_rows.append({"scenario": scenario, "ground_truth": family, "subtasks": len(subtasks), "independent_predictions": independent_predictions, "cumulative_predictions": cumulative_predictions, "majority_prediction": majority_prediction})

    selective = []
    for threshold in [0.00, 0.03, 0.05, 0.08, 0.10, 0.15]:
        committed = [r for r in rows if r["margin"] >= threshold]
        correct = sum(r["prediction"] == r["ground_truth"] for r in committed)
        selective.append({"margin_threshold": threshold, "committed": len(committed), "coverage": len(committed) / len(rows), "accuracy_when_committed": correct / len(committed) if committed else 0.0, "full_dataset_correct": correct / len(rows)})

    return {
        "agencybench_commit": AGENCYBENCH_COMMIT,
        "tasks": len(tasks),
        "published_paper_task_count": 138,
        "parsed_description_subtasks": len(tasks),
        "scenarios": len(groups),
        "families": dict(family_counts),
        "method": {"agentweave": {"hit1": correct1 / len(tasks), "hit2_team_coverage": correct2 / len(tasks), "hit3": correct3 / len(tasks)}, "random": {"hit1": random_correct / len(tasks)}, "single_best": {"family": single_best, "hit1": single_correct / len(tasks)}},
        "macro_hit1": statistics.mean(v["hit1"] for v in per_family.values()),
        "per_family": per_family,
        "sequential": {"cumulative_context_hit1": cumulative_correct1 / len(tasks), "cumulative_context_hit3": cumulative_correct3 / len(tasks), "first_subtask_hit1": first_correct / first_total if first_total else 0.0, "later_subtask_hit1": later_correct / later_total if later_total else 0.0, "prediction_stability_across_subtasks": stable_transitions / total_transitions if total_transitions else 0.0, "scenario_majority_hit1": scenario_majority_correct / len(groups)},
        "heldout_development": evaluate_heldout(tasks),
        "selective_by_margin": selective,
        "mean_margin": statistics.mean(margins),
        "mean_routing_ms": statistics.mean(latencies),
        "p95_routing_ms": sorted(latencies)[max(0, math.ceil(0.95 * len(latencies)) - 1)],
        "confusion": {k: dict(v) for k, v in confusion.items()},
        "scenario_rows": scenario_rows,
        "rows": rows,
    }


def markdown(result: dict) -> str:
    aw = result["method"]["agentweave"]
    rnd = result["method"]["random"]
    sb = result["method"]["single_best"]
    seq = result["sequential"]
    ho = result["heldout_development"]
    lines = [
        "# AgencyBench external capability-family routing evaluation", "", f"Official AgencyBench pin: `{result['agencybench_commit']}`", "",
        f"Machine-readable `description.json` subtasks scored: **{result['tasks']}** across **{result['scenarios']}** scenarios and **6** capability families.", "",
        f"AgencyBench's paper/README describes **{result['published_paper_task_count']} tasks** overall; this run found **{result['parsed_description_subtasks']} string subtasks** in the pinned V2 `description.json` files, so the result is explicitly reported on that parsed subset rather than claiming all 138.", "",
        "**Blind protocol:** AgentWeave receives only the task query/requirements. The parent AgencyBench capability-family label is withheld until after routing; deliverables and rubrics are stripped before routing.", "",
        "| Method | Hit@1 | Top-2 team coverage | Hit@3 |", "|---|---:|---:|---:|",
        f"| **AgentWeave** | **{aw['hit1']:.1%}** | **{aw['hit2_team_coverage']:.1%}** | **{aw['hit3']:.1%}** |",
        f"| Random | {rnd['hit1']:.1%} | — | — |", f"| Single-best ({sb['family']}) | {sb['hit1']:.1%} | — | — |", "",
        f"Macro Hit@1: **{result['macro_hit1']:.1%}**. Mean routing time: **{result['mean_routing_ms']:.3f} ms/task**; p95: **{result['p95_routing_ms']:.3f} ms/task**.", "",
        "## Sequential / scenario-aware analysis", "",
        "This secondary analysis tests AgencyBench's multi-stage structure without executing the environment. For each later subtask, a cumulative variant gives the router the visible queries from previous subtasks in the same scenario; no family label, deliverable, or rubric is exposed.", "",
        "| Metric | Result |", "|---|---:|", f"| Independent task Hit@1 | {aw['hit1']:.1%} |", f"| Cumulative-context Hit@1 | **{seq['cumulative_context_hit1']:.1%}** |", f"| Cumulative-context Hit@3 | **{seq['cumulative_context_hit3']:.1%}** |", f"| First-subtask cold-start Hit@1 | {seq['first_subtask_hit1']:.1%} |", f"| Later-subtask independent Hit@1 | {seq['later_subtask_hit1']:.1%} |", f"| Prediction stability across consecutive subtasks | {seq['prediction_stability_across_subtasks']:.1%} |", f"| Scenario-majority family Hit@1 | **{seq['scenario_majority_hit1']:.1%}** |", "",
        "## Development-trained held-out scenario analysis", "",
        "A deterministic scenario-stratified split trains a simple family text centroid on 60% of scenarios and evaluates only on the remaining 40%. Test scenario labels are never used to construct the router.", "",
        f"Development: **{ho['train_tasks']} tasks / {len(ho['train_scenarios'])} scenarios**. Held-out test: **{ho['test_tasks']} tasks / {len(ho['test_scenarios'])} scenarios**.", "",
        "| Held-out metric | Result |", "|---|---:|", f"| Hit@1 | **{ho['hit1']:.1%}** |", f"| Hit@2 | **{ho['hit2']:.1%}** |", f"| Hit@3 | **{ho['hit3']:.1%}** |", "",
        "| Family | Held-out tasks | Hit@1 |", "|---|---:|---:|",
    ]
    for family in FAMILIES:
        x = ho["per_family"][family]
        lines.append(f"| {family} | {x['tasks']} | {x['hit1']:.1%} |")

    lines += ["", "## Confidence / abstention analysis", "", "The score margin between the first- and second-ranked families is used only as a simple, label-free confidence signal.", "", "| Margin threshold | Coverage | Accuracy when committed | Correct over full set |", "|---:|---:|---:|---:|"]
    for x in result["selective_by_margin"]:
        lines.append(f"| {x['margin_threshold']:.2f} | {x['coverage']:.1%} | {x['accuracy_when_committed']:.1%} | {x['full_dataset_correct']:.1%} |")

    lines += ["", "## Per capability family", "", "| Family | Tasks | Hit@1 |", "|---|---:|---:|"]
    for family in FAMILIES:
        x = result["per_family"][family]
        lines.append(f"| {family} | {x['tasks']} | {x['hit1']:.1%} |")

    lines += ["", "## Interpretation boundary", "", "- External published AgencyBench `description.json` task text is used from the pinned upstream repository.", "- Ground-truth family labels come only from the upstream directory structure and are hidden until scoring.", "- Deliverables and rubrics are not given to the router.", "- Candidate family descriptions are fixed generic capability metadata, not derived from benchmark examples.", "- Top-2 is potential specialist-team coverage only; it does not claim that two agents were executed.", "- Cumulative-context routing uses only earlier visible task queries from the same scenario.", "- The development-trained held-out analysis uses labels only from its development scenarios; test labels are used only for scoring. Because this split was added after earlier aggregate inspection of the benchmark, it is stronger than same-set tuning but is not presented as a preregistered untouched benchmark.", "- This still measures routing only; it does **not** execute the hours-long AgencyBench scenarios, Docker visual/functional judges, user simulation, model/tool calls, or final task outcomes.", "- It must not be reported as AgencyBench end-to-end task score."]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agencybench-root", default="external/AgencyBench")
    args = parser.parse_args()
    tasks = load_tasks(Path(args.agencybench_root))
    if len(tasks) < 100:
        raise SystemExit(f"Unexpectedly few AgencyBench-v2 subtasks: {len(tasks)}")
    result = evaluate(tasks)
    Path("agencybench-routing-results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    md = markdown(result)
    Path("agencybench-routing-results.md").write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
