from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

DATASETS = ("hotpotqa", "gaia_dev", "bfcl", "tau2")

ERROR_TERMS = (
    "error", "failed", "failure", "exception", "traceback", "timeout", "timed out",
    "not found", "invalid", "denied", "unauthorized", "forbidden", "cannot", "could not",
)
EXPLORATION_TERMS = (
    "let me", "i'll check", "i will check", "need to", "we need to", "perhaps", "maybe",
    "try another", "search for", "look for", "inspect", "investigate", "let's see",
)
CORRECTION_TERMS = (
    "correct", "correction", "instead", "retry with", "different approach", "updated",
    "revise", "fix", "adjust", "recover", "previous", "mistake",
)


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if isinstance(obj, dict):
                yield obj


def to_int(v: Any) -> int | None:
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, str) and v.strip().lstrip("-").isdigit():
        return int(v.strip())
    return None


def normalize_labels(value: Any) -> dict[str, int]:
    if isinstance(value, dict):
        out: dict[str, int] = {}
        for k, v in value.items():
            iv = to_int(v)
            if iv is not None:
                out[str(k)] = iv
        return out
    if isinstance(value, list):
        return {str(i): int(v) for i, v in enumerate(value) if to_int(v) is not None}
    return {}


def text_of(msg: dict[str, Any]) -> str:
    parts: list[str] = []
    content = msg.get("content")
    if isinstance(content, str):
        parts.append(content)
    elif isinstance(content, list):
        for x in content:
            if isinstance(x, str):
                parts.append(x)
            elif isinstance(x, dict):
                for key in ("text", "content", "name", "arguments"):
                    val = x.get(key)
                    if isinstance(val, str):
                        parts.append(val)
    for key in ("tool_calls", "function_call"):
        if key in msg:
            try:
                parts.append(json.dumps(msg[key], ensure_ascii=False, sort_keys=True))
            except Exception:
                parts.append(str(msg[key]))
    return " ".join(parts).strip()


def has_tool_call(msg: dict[str, Any]) -> bool:
    return bool(msg.get("tool_calls") or msg.get("function_call"))


def looks_like_error(text: str) -> bool:
    low = text.lower()
    return any(term in low for term in ERROR_TERMS)


def same_action(a: str, b: str) -> bool:
    def norm(s: str) -> str:
        s = s.lower()
        s = re.sub(r"\s+", " ", s)
        s = re.sub(r"\b\d+\b", "#", s)
        return s.strip()[:500]
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return False
    return na == nb or (len(na) > 80 and len(nb) > 80 and na[:160] == nb[:160])


def predict_step_labels(item: dict[str, Any]) -> dict[str, int]:
    messages = item.get("messages")
    if not isinstance(messages, list):
        return {}

    predictions: dict[str, int] = {}
    prior_assistant_text = ""
    prior_tool_error = False
    error_chain = False

    for idx, raw in enumerate(messages):
        if not isinstance(raw, dict):
            continue
        role = raw.get("role")
        if role == "tool":
            prior_tool_error = looks_like_error(text_of(raw))
            continue
        if role != "assistant":
            continue

        text = text_of(raw)
        low = text.lower()
        correction = any(term in low for term in CORRECTION_TERMS)
        tool_call = has_tool_call(raw)
        repeated = same_action(text, prior_assistant_text)

        # A repeated action immediately after a tool failure is the clearest deterministic
        # process-quality failure signal available without consulting benchmark labels.
        if prior_tool_error and repeated and not correction:
            label = -1
            error_chain = True
        elif error_chain and not correction:
            label = -1
        elif correction:
            # Explicit correction/recovery breaks propagated-error state.
            error_chain = False
            label = 1 if tool_call or len(text) > 30 else 0
        elif prior_tool_error:
            # A reasonable new action after an external/tool failure is exploratory.
            label = 0
        elif tool_call:
            label = 1
        elif any(term in low for term in EXPLORATION_TERMS):
            label = 0
        elif len(text.strip()) < 12:
            label = 0
        else:
            # Non-tool assistant steps are treated as effective unless they carry an
            # observable failure signal; this is intentionally conservative and label-blind.
            label = -1 if looks_like_error(text) and "cannot" in low else 1

        predictions[str(idx)] = label
        prior_assistant_text = text
        prior_tool_error = False

    return predictions


def first_error(labels: dict[str, int]) -> int:
    vals: list[int] = []
    for k, v in labels.items():
        if v == -1:
            try:
                vals.append(int(k))
            except ValueError:
                pass
    return min(vals) if vals else -1


def evaluate(root: Path) -> dict[str, Any]:
    overall_matches = overall_steps = overall_first = overall_records = 0
    per_dataset: dict[str, Any] = {}
    pred_dist: Counter[int] = Counter()
    ref_dist: Counter[int] = Counter()

    for dataset in DATASETS:
        path = root / f"{dataset}.jsonl"
        if not path.exists():
            raise FileNotFoundError(path)
        records = list(iter_jsonl(path))
        matches = steps = first_matches = exact_matches = 0
        for item in records:
            ref = normalize_labels(item.get("step_labels"))
            pred = predict_step_labels(item)
            for key, val in ref.items():
                ref_dist[val] += 1
                if key in pred:
                    pred_dist[pred[key]] += 1
                steps += 1
                if pred.get(key) == val:
                    matches += 1
            if pred == ref:
                exact_matches += 1
            if first_error(pred) == first_error(ref):
                first_matches += 1

        n = len(records)
        per_dataset[dataset] = {
            "records": n,
            "steps": steps,
            "step_micro_acc": matches / steps if steps else 0.0,
            "first_error_acc": first_matches / n if n else 0.0,
            "trajectory_exact_acc": exact_matches / n if n else 0.0,
        }
        overall_matches += matches
        overall_steps += steps
        overall_first += first_matches
        overall_records += n

    return {
        "benchmark": "RUCBM/AgentProcessBench",
        "evaluation_mode": "label-blind deterministic process-quality baseline",
        "datasets": list(DATASETS),
        "records": overall_records,
        "steps": overall_steps,
        "step_micro_acc": overall_matches / overall_steps if overall_steps else 0.0,
        "first_error_acc": overall_first / overall_records if overall_records else 0.0,
        "per_dataset": per_dataset,
        "reference_label_distribution": {str(k): v for k, v in sorted(ref_dist.items())},
        "prediction_label_distribution": {str(k): v for k, v in sorted(pred_dist.items())},
        "boundary": (
            "AgentWeave receives trajectory messages/tool traces without step_labels while predicting. "
            "Human step_labels are read only after prediction for scoring. This measures a deterministic "
            "process-quality verification baseline, not end-to-end task execution and not the official LLM judge configuration."
        ),
    }


def write_outputs(result: dict[str, Any], prefix: str) -> None:
    Path(f"{prefix}.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# AgentProcessBench external process-quality evaluation",
        "",
        f"- Records: **{result['records']}**",
        f"- Human-labeled assistant steps: **{result['steps']}**",
        f"- Step micro accuracy: **{100*result['step_micro_acc']:.2f}%**",
        f"- First-error accuracy: **{100*result['first_error_acc']:.2f}%**",
        "",
        "| Dataset | Records | Steps | Step micro acc. | First-error acc. | Trajectory exact acc. |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, row in result["per_dataset"].items():
        lines.append(
            f"| {name} | {row['records']} | {row['steps']} | {100*row['step_micro_acc']:.2f}% | "
            f"{100*row['first_error_acc']:.2f}% | {100*row['trajectory_exact_acc']:.2f}% |"
        )
    lines.extend(["", f"Boundary: {result['boundary']}"])
    Path(f"{prefix}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--data-root", type=Path, required=True)
    p.add_argument("--output-prefix", default="agentprocessbench-results")
    args = p.parse_args()
    result = evaluate(args.data_root)
    write_outputs(result, args.output_prefix)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
