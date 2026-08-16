from __future__ import annotations

import math
import random
from collections.abc import Sequence


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if total <= 0:
        return (0.0, 0.0)
    p = successes / total
    z2 = z * z
    denom = 1.0 + z2 / total
    centre = (p + z2 / (2 * total)) / denom
    half = z * math.sqrt((p * (1 - p) / total) + z2 / (4 * total * total)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def exact_mcnemar_pvalue(a_correct: Sequence[bool], b_correct: Sequence[bool]) -> dict:
    if len(a_correct) != len(b_correct):
        raise ValueError("paired vectors must have the same length")
    b = sum(bool(a) and not bool(c) for a, c in zip(a_correct, b_correct))
    c = sum((not bool(a)) and bool(d) for a, d in zip(a_correct, b_correct))
    n = b + c
    if n == 0:
        return {"a_only": b, "b_only": c, "discordant": 0, "p_value": 1.0}
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return {"a_only": b, "b_only": c, "discordant": n, "p_value": min(1.0, 2.0 * tail)}


def paired_bootstrap_difference(
    a_values: Sequence[float],
    b_values: Sequence[float],
    *,
    samples: int = 10_000,
    seed: int = 20260816,
) -> dict:
    if len(a_values) != len(b_values):
        raise ValueError("paired vectors must have the same length")
    if not a_values:
        return {"difference": 0.0, "ci_low": 0.0, "ci_high": 0.0, "samples": samples, "seed": seed}
    diffs = [float(a) - float(b) for a, b in zip(a_values, b_values)]
    observed = sum(diffs) / len(diffs)
    rng = random.Random(seed)
    boot = []
    n = len(diffs)
    for _ in range(samples):
        boot.append(sum(diffs[rng.randrange(n)] for _ in range(n)) / n)
    boot.sort()
    lo_idx = max(0, int(0.025 * samples))
    hi_idx = min(samples - 1, int(0.975 * samples))
    return {
        "difference": observed,
        "ci_low": boot[lo_idx],
        "ci_high": boot[hi_idx],
        "samples": samples,
        "seed": seed,
    }
