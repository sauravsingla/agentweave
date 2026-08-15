from __future__ import annotations

import argparse
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

# Generic capability-family descriptions. They are defined independently of any
# AgencyBench task or label and are the only specialist metadata visible during routing.
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
    # Do not expose deliverables/rubrics to the router. The user-facing query and
    # requirements before those sections are retained.
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
            for number, raw in sorted(subtasks):
                tasks.append({
                    "id": f"{family}/{path.parent.name}/subtask{number}",
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
    # IDF is fit without labels, using the fixed profiles plus raw task documents.
    docs = [set(tokens(t["query"])) for t in tasks] + [set(x) for x in (tokens(v) for v in PROFILES.values())]
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
        scores = {}
        for family in FAMILIES:
            score = cosine(qtf, profile_tf[family], idf)
            phrase_hits = sum(1 for p in PHRASES[family] if p in low)
            score += min(0.45, 0.09 * phrase_hits)
            caps = set(getattr(req, "capabilities", set()) or set())
            if family == "Research" and ("research" in caps or "retrieval" in caps):
                score += 0.18
            if family in {"Backend", "Code", "Frontend", "Game"} and "coding" in caps:
                score += 0.04
            if family == "MCP" and "mcp" in low:
                score += 0.30
            scores[family] = score
        return sorted(scores.items(), key=lambda x: (-x[1], x[0]))

    return rank


def evaluate(tasks: list[dict]) -> dict:
    rank = build_router(tasks)
    rng = random.Random(7)
    family_counts = Counter(t["family"] for t in tasks)
    single_best = family_counts.most_common(1)[0][0]
    correct1 = correct3 = 0
    random_correct = single_correct = 0
    confusion = defaultdict(Counter)
    latencies = []
    rows = []
    for task in tasks:
        start = time.perf_counter()
        ranked = rank(task["query"])
        latencies.append((time.perf_counter() - start) * 1000.0)
        predicted = ranked[0][0]
        top3 = [x[0] for x in ranked[:3]]
        ok = predicted == task["family"]
        correct1 += int(ok)
        correct3 += int(task["family"] in top3)
        random_correct += int(rng.choice(FAMILIES) == task["family"])
        single_correct += int(single_best == task["family"])
        confusion[task["family"]][predicted] += 1
        rows.append({"id": task["id"], "ground_truth": task["family"], "prediction": predicted, "top3": top3, "scores": ranked})

    per_family = {}
    for family in FAMILIES:
        total = family_counts[family]
        hit = confusion[family][family]
        per_family[family] = {"tasks": total, "hit1": hit / total if total else 0.0}

    acc1 = correct1 / len(tasks)
    return {
        "agencybench_commit": AGENCYBENCH_COMMIT,
        "tasks": len(tasks),
        "scenarios": len({x["id"].rsplit("/", 1)[0] for x in tasks}),
        "families": dict(family_counts),
        "method": {
            "agentweave": {"hit1": acc1, "hit3": correct3 / len(tasks)},
            "random": {"hit1": random_correct / len(tasks)},
            "single_best": {"family": single_best, "hit1": single_correct / len(tasks)},
        },
        "macro_hit1": statistics.mean(v["hit1"] for v in per_family.values()),
        "per_family": per_family,
        "mean_routing_ms": statistics.mean(latencies),
        "p95_routing_ms": sorted(latencies)[max(0, math.ceil(0.95 * len(latencies)) - 1)],
        "confusion": {k: dict(v) for k, v in confusion.items()},
        "rows": rows,
    }


def markdown(result: dict) -> str:
    aw = result["method"]["agentweave"]
    rnd = result["method"]["random"]
    sb = result["method"]["single_best"]
    lines = [
        "# AgencyBench external capability-family routing evaluation", "",
        f"Official AgencyBench pin: `{result['agencybench_commit']}`", "",
        f"Tasks scored: **{result['tasks']}** subtasks across **{result['scenarios']}** scenarios and **6** published capability families.", "",
        "**Blind protocol:** AgentWeave receives only the task query/requirements. The parent AgencyBench capability-family label is withheld until after routing and used only as scoring ground truth. Deliverables and rubrics are stripped before routing.", "",
        "| Method | Hit@1 | Hit@3 |", "|---|---:|---:|",
        f"| **AgentWeave** | **{aw['hit1']:.1%}** | **{aw['hit3']:.1%}** |",
        f"| Random | {rnd['hit1']:.1%} | — |",
        f"| Single-best ({sb['family']}) | {sb['hit1']:.1%} | — |", "",
        f"Macro Hit@1: **{result['macro_hit1']:.1%}**. Mean routing time: **{result['mean_routing_ms']:.3f} ms/task**; p95: **{result['p95_routing_ms']:.3f} ms/task**.", "",
        "## Per capability family", "", "| Family | Tasks | Hit@1 |", "|---|---:|---:|",
    ]
    for family in FAMILIES:
        x = result["per_family"][family]
        lines.append(f"| {family} | {x['tasks']} | {x['hit1']:.1%} |")
    lines += [
        "", "## Interpretation boundary", "",
        "- External published AgencyBench `description.json` task text is used from the pinned upstream repository.",
        "- Ground-truth family labels come only from the upstream directory structure and are hidden until scoring.",
        "- Deliverables and rubrics are not given to the router.",
        "- Candidate family descriptions are fixed generic capability metadata, not generated from AgencyBench labels or examples.",
        "- This measures capability-family routing only; it does **not** execute the hours-long AgencyBench scenarios, Docker visual/functional judges, user simulation, or model/tool calls.",
        "- It therefore must not be reported as AgencyBench end-to-end task score.",
    ]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agencybench-root", default="external/AgencyBench")
    args = parser.parse_args()
    tasks = load_tasks(Path(args.agencybench_root))
    if len(tasks) != 138:
        raise SystemExit(f"Expected 138 AgencyBench-v2 subtasks, found {len(tasks)}")
    result = evaluate(tasks)
    Path("agencybench-routing-results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    md = markdown(result)
    Path("agencybench-routing-results.md").write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
