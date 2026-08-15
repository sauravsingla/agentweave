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
from dataclasses import dataclass
from pathlib import Path

from datasets import load_dataset

from agentweave.engine import AgentMatcher, PlacementEngine, TrustEngine
from agentweave.models import AgentProfile, Capability, ExecutionProfile, Requirement, TrustVector

TOOLBENCH_OFFICIAL_REPO = "OpenBMB/ToolBench"
TOOLBENCH_OFFICIAL_PIN = "d56fdd89faf8c91fa135090b212bb9057ee5cfc2"
TOOLBENCH_MIRROR = "tuandunghcmut/toolbench-v1"
TOOLBENCH_MIRROR_PIN = "36de9b189753ad5de276181974f97df15e8c3202"
SPLITS = (
    "g1_instruction",
    "g1_category",
    "g1_tool",
    "g2_instruction",
    "g2_category",
    "g3_instruction",
)

STOP = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "could", "do", "for", "from",
    "get", "give", "help", "i", "in", "is", "it", "me", "my", "need", "of", "on", "or", "please",
    "provide", "retrieve", "show", "that", "the", "this", "to", "use", "using", "want", "with", "would",
    "you", "your", "all", "any", "some", "specific", "information", "details", "data", "find", "search",
}

ALIASES = {
    "weather": {"forecast", "temperature", "climate"},
    "forecast": {"weather", "prediction"},
    "location": {"place", "geo", "geography", "map", "address"},
    "map": {"location", "geo", "geography"},
    "finance": {"financial", "stock", "market", "currency", "price"},
    "stock": {"finance", "market", "equity"},
    "news": {"article", "press", "headline"},
    "article": {"news", "press"},
    "music": {"song", "artist", "album", "track"},
    "song": {"music", "track", "artist"},
    "sports": {"score", "match", "game", "player", "team"},
    "basketball": {"nba", "sports", "player", "team"},
    "football": {"soccer", "sports", "match", "team"},
    "translation": {"translate", "language", "translator"},
    "translate": {"translation", "language", "translator"},
    "image": {"photo", "picture", "visual"},
    "video": {"media", "clip"},
    "social": {"instagram", "twitter", "facebook", "tiktok"},
    "recipe": {"food", "nutrition", "ingredient"},
    "nutrition": {"food", "recipe", "ingredient"},
    "travel": {"tourism", "trip", "hotel", "flight", "attraction"},
    "movie": {"film", "cinema", "actor"},
    "book": {"author", "literature"},
}


@dataclass(frozen=True)
class ApiRecord:
    category: str
    tool: str
    api: str

    @property
    def key(self) -> str:
        return "|".join((_norm(self.category), _norm(self.tool), _norm(self.api)))

    @property
    def variants(self) -> set[str]:
        c, t, a = _norm(self.category), _norm(self.tool), _norm(self.api)
        out = {self.key}
        if t or a:
            out.add(f"{t}|{a}")
        if a:
            out.add(a)
        return {v for v in out if v.strip("|")}


def _norm(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")


def _stem(token: str) -> str:
    if len(token) > 5 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 5 and token.endswith("ing"):
        return token[:-3]
    if len(token) > 4 and token.endswith("ed"):
        return token[:-2]
    if len(token) > 4 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def _features(text: str, max_features: int = 72) -> set[str]:
    raw = [_stem(t) for t in re.findall(r"[a-z0-9]+", str(text).lower())]
    tokens = [t for t in raw if len(t) > 2 and t not in STOP]
    out = set(tokens)
    for token in list(out):
        out.update(ALIASES.get(token, ()))
    for a, b in zip(tokens, tokens[1:]):
        out.add(f"{a}:{b}")
    # Keep deterministic bounded feature sets so matcher cost is controlled.
    return set(sorted(out, key=lambda x: (":" not in x, x))[:max_features])


def _json(value):
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return value
    if not isinstance(value, str):
        return value
    value = value.strip()
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _record_from_dict(item: dict) -> ApiRecord:
    return ApiRecord(
        str(item.get("category_name") or item.get("category") or ""),
        str(item.get("tool_name") or item.get("tool") or item.get("tool_name_standardized") or ""),
        str(item.get("api_name") or item.get("api") or item.get("name") or ""),
    )


def _parse_api_records(value) -> list[ApiRecord]:
    value = _json(value)
    if value is None:
        return []
    if isinstance(value, dict):
        if any(k in value for k in ("api_name", "tool_name", "category_name", "api", "tool")):
            return [_record_from_dict(value)]
        out = []
        for v in value.values():
            out.extend(_parse_api_records(v))
        return out
    if isinstance(value, (list, tuple)):
        # Some ToolBench representations use a compact [category, tool, api] triplet.
        if 1 <= len(value) <= 3 and all(isinstance(v, str) for v in value):
            vals = list(value)
            if len(vals) == 3:
                return [ApiRecord(vals[0], vals[1], vals[2])]
            if len(vals) == 2:
                return [ApiRecord("", vals[0], vals[1])]
            return [ApiRecord("", "", vals[0])]
        out = []
        for item in value:
            out.extend(_parse_api_records(item))
        return out
    if isinstance(value, str):
        return [ApiRecord("", "", value)]
    return []


def load_rows(limit_per_split: int | None = None) -> list[dict]:
    rows: list[dict] = []
    for split in SPLITS:
        ds = load_dataset(
            TOOLBENCH_MIRROR,
            "benchmark",
            split=split,
            revision=TOOLBENCH_MIRROR_PIN,
        )
        if limit_per_split:
            ds = ds.select(range(min(limit_per_split, len(ds))))
        for row in ds:
            apis = _parse_api_records(row.get("api_list"))
            relevant = _parse_api_records(row.get("relevant_apis"))
            if not relevant:
                # The mirror keeps both fields, but older exports may only expose api_list.
                relevant = list(apis)
            rows.append({
                "split": split,
                "query_id": str(row.get("query_id")),
                "query": str(row.get("query") or ""),
                "api_list": apis,
                "relevant": relevant,
            })
    return rows


def _profile(record: ApiRecord) -> AgentProfile:
    feature_text = " ".join((record.category, record.tool, record.api))
    features = _features(feature_text)
    if not features:
        features = {_norm(record.api) or _norm(record.tool) or "generic-tool"}
    digest = hashlib.sha1(record.key.encode("utf-8")).hexdigest()[:12]
    return AgentProfile(
        agent_id=f"tool-{digest}",
        name=" / ".join(v for v in (record.category, record.tool, record.api) if v) or record.key,
        capabilities=[Capability(f, 1.0, True) for f in sorted(features)],
        domains=[],
        knowledge=[],
        trust=TrustVector(*([0.8] * 7)),
        execution=ExecutionProfile(latency_ms=100.0, cost=0.0, privacy_level="standard"),
        metadata={
            "toolbench_key": record.key,
            "toolbench_variants": sorted(record.variants),
            "category": record.category,
            "tool": record.tool,
            "api": record.api,
        },
    )


def build_catalog(rows: list[dict]) -> tuple[list[AgentProfile], dict[str, ApiRecord]]:
    records: dict[str, ApiRecord] = {}
    for row in rows:
        for record in row["api_list"] + row["relevant"]:
            if record.key.strip("|"):
                records.setdefault(record.key, record)
    profiles = [_profile(records[k]) for k in sorted(records)]
    return profiles, records


def _ground_truth_variants(row: dict) -> set[str]:
    out: set[str] = set()
    for record in row["relevant"]:
        out.update(record.variants)
    return out


def _candidate_is_relevant(agent: AgentProfile, truth: set[str]) -> bool:
    return bool(set(agent.metadata.get("toolbench_variants", ())) & truth)


def _query_requirement(query: str) -> Requirement:
    features = _features(query)
    return Requirement(text=query, capabilities=features or {"generic"})


def _random_rank(catalog: list[AgentProfile], rng: random.Random, k: int) -> list[AgentProfile]:
    if len(catalog) <= k:
        return list(catalog)
    return rng.sample(catalog, k)


def _summarize(rows: list[dict]) -> dict:
    if not rows:
        return {}
    return {
        "tasks": len(rows),
        "hit_at_1": statistics.mean(r["hit_at_1"] for r in rows),
        "hit_at_3": statistics.mean(r["hit_at_3"] for r in rows),
        "hit_at_5": statistics.mean(r["hit_at_5"] for r in rows),
        "mrr": statistics.mean(r["reciprocal_rank"] for r in rows),
        "mean_recall_at_5": statistics.mean(r["recall_at_5"] for r in rows),
        "all_relevant_at_5": statistics.mean(r["all_relevant_at_5"] for r in rows),
        "mean_routing_ms": statistics.mean(r["routing_ms"] for r in rows),
        "p95_routing_ms": sorted(r["routing_ms"] for r in rows)[max(0, math.ceil(0.95 * len(rows)) - 1)],
    }


def evaluate(rows: list[dict], seed: int = 19) -> dict:
    catalog, records = build_catalog(rows)
    matcher = AgentMatcher(TrustEngine(), PlacementEngine(), use_native=False)
    rng = random.Random(seed)
    detailed: list[dict] = []
    random_rows: list[dict] = []

    for row in rows:
        truth = _ground_truth_variants(row)
        if not truth:
            continue
        req = _query_requirement(row["query"])
        started = time.perf_counter_ns()
        ranked = matcher.rank(req, catalog)
        routing_ms = (time.perf_counter_ns() - started) / 1_000_000.0
        top = [r.agent for r in ranked[:5]]
        rel_flags = [_candidate_is_relevant(a, truth) for a in top]
        first_rank = next((i + 1 for i, r in enumerate(ranked) if _candidate_is_relevant(r.agent, truth)), None)
        top5_relevant_variants = set()
        for a in top:
            if _candidate_is_relevant(a, truth):
                top5_relevant_variants.update(set(a.metadata.get("toolbench_variants", ())) & truth)
        # Count ground truth by API record rather than variant count.
        gt_records = row["relevant"]
        matched_gt = sum(any(v in set(a.metadata.get("toolbench_variants", ())) for v in rec.variants for a in top) for rec in gt_records)
        recall5 = matched_gt / max(1, len(gt_records))
        detailed.append({
            "split": row["split"],
            "query_id": row["query_id"],
            "query": row["query"],
            "ground_truth_api_count": len(gt_records),
            "hit_at_1": bool(rel_flags[:1] and rel_flags[0]),
            "hit_at_3": any(rel_flags[:3]),
            "hit_at_5": any(rel_flags),
            "reciprocal_rank": 1.0 / first_rank if first_rank else 0.0,
            "recall_at_5": recall5,
            "all_relevant_at_5": recall5 >= 0.999,
            "routing_ms": routing_ms,
            "top5": [a.metadata.get("toolbench_key") for a in top],
        })

        random_top = _random_rank(catalog, rng, 5)
        rflags = [_candidate_is_relevant(a, truth) for a in random_top]
        rmatched = sum(any(v in set(a.metadata.get("toolbench_variants", ())) for v in rec.variants for a in random_top) for rec in gt_records)
        random_rows.append({
            "hit_at_1": bool(rflags[:1] and rflags[0]),
            "hit_at_3": any(rflags[:3]),
            "hit_at_5": any(rflags),
            "reciprocal_rank": next((1.0 / (i + 1) for i, flag in enumerate(rflags) if flag), 0.0),
            "recall_at_5": rmatched / max(1, len(gt_records)),
            "all_relevant_at_5": rmatched >= len(gt_records),
            "routing_ms": 0.0,
        })

    per_split = {}
    for split in SPLITS:
        per_split[split] = _summarize([r for r in detailed if r["split"] == split])

    category_counts = Counter(_norm(rec.category) or "unknown" for rec in records.values())
    return {
        "benchmark": "ToolBench external open-catalog tool routing",
        "toolbench_official_repository": TOOLBENCH_OFFICIAL_REPO,
        "toolbench_official_commit": TOOLBENCH_OFFICIAL_PIN,
        "dataset_source": TOOLBENCH_MIRROR,
        "dataset_mirror_commit": TOOLBENCH_MIRROR_PIN,
        "splits": list(SPLITS),
        "total_loaded_tasks": len(rows),
        "scored_tasks": len(detailed),
        "catalog_unique_api_records": len(catalog),
        "catalog_categories": len(category_counts),
        "largest_categories": category_counts.most_common(15),
        "agentweave": _summarize(detailed),
        "random_baseline": _summarize(random_rows),
        "per_split": per_split,
        "protocol_boundary": {
            "router_input": "Raw ToolBench query text plus a global discovered catalog built from API metadata only.",
            "withheld_per_task": "The task-to-relevant-API association is not passed to the router; relevant_apis is used only after ranking for scoring.",
            "catalog": "Union of API metadata present across the six external ToolBench benchmark splits. All candidates use equal synthetic trust/placement so ranking is driven by capability metadata overlap.",
            "external_data": "ToolBench query text and API metadata/ground truth from a public mirror of the OpenBMB ToolBench benchmark, pinned to a mirror commit; official repository provenance is pinned separately.",
            "not_measured": "This is not ToolEval pass rate, live RapidAPI execution success, model answer quality, or provider latency/cost.",
        },
        "raw": detailed,
    }


def markdown_report(result: dict) -> str:
    a = result["agentweave"]
    r = result["random_baseline"]
    lines = [
        "# ToolBench external open-catalog tool-routing evaluation",
        "",
        f"Official ToolBench repo pin: `{result['toolbench_official_commit']}`",
        f"Dataset mirror pin: `{result['dataset_mirror_commit']}`",
        f"Tasks scored: **{result['scored_tasks']}** across **{len(result['splits'])}** benchmark splits",
        f"Discovered API catalog: **{result['catalog_unique_api_records']} unique API records** across **{result['catalog_categories']} categories**",
        "",
        "The router receives raw query text and a global catalog of tool/API metadata. Per-task relevant API associations are withheld until scoring.",
        "",
        "| Method | Hit@1 | Hit@3 | Hit@5 | MRR | Mean recall@5 | All relevant@5 |",
        "|---|---:|---:|---:|---:|---:|---:|",
        f"| **AgentWeave** | **{100*a['hit_at_1']:.1f}%** | **{100*a['hit_at_3']:.1f}%** | **{100*a['hit_at_5']:.1f}%** | **{a['mrr']:.3f}** | **{100*a['mean_recall_at_5']:.1f}%** | **{100*a['all_relevant_at_5']:.1f}%** |",
        f"| Random | {100*r['hit_at_1']:.1f}% | {100*r['hit_at_3']:.1f}% | {100*r['hit_at_5']:.1f}% | {r['mrr']:.3f} | {100*r['mean_recall_at_5']:.1f}% | {100*r['all_relevant_at_5']:.1f}% |",
        "",
        f"Mean AgentWeave ranking time: **{a['mean_routing_ms']:.2f} ms/task**; p95: **{a['p95_routing_ms']:.2f} ms/task**.",
        "",
        "## Per split",
        "",
        "| Split | Tasks | Hit@1 | Hit@5 | MRR | Recall@5 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for split in SPLITS:
        row = result["per_split"].get(split) or {}
        if row:
            lines.append(
                f"| {split} | {row['tasks']} | {100*row['hit_at_1']:.1f}% | {100*row['hit_at_5']:.1f}% | {row['mrr']:.3f} | {100*row['mean_recall_at_5']:.1f}% |"
            )
    lines += [
        "",
        "## Interpretation boundary",
        "",
        "- External ToolBench task queries and API metadata are used; the benchmark mirror and official upstream repo are both pinned.",
        "- The task-to-relevant-API relation is hidden during ranking and used only afterward as ground truth.",
        "- Candidate tools have equal synthetic trust, cost, and placement so this isolates capability/tool routing rather than rewarding synthetic priors.",
        "- This evaluates retrieval/routing, not ToolEval end-to-end tool execution or live RapidAPI success.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit-per-split", type=int, default=0)
    parser.add_argument("--seed", type=int, default=19)
    parser.add_argument("--json-out", default="toolbench-routing-results.json")
    parser.add_argument("--md-out", default="toolbench-routing-results.md")
    args = parser.parse_args()

    rows = load_rows(args.limit_per_split or None)
    result = evaluate(rows, seed=args.seed)
    Path(args.json_out).write_text(json.dumps(result, indent=2), encoding="utf-8")
    report = markdown_report(result)
    Path(args.md_out).write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
