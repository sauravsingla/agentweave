from research.paper_stats import exact_mcnemar_pvalue, paired_bootstrap_difference, wilson_interval


def test_wilson_interval_contains_observed_rate():
    lo, hi = wilson_interval(80, 100)
    assert 0.0 <= lo < 0.8 < hi <= 1.0


def test_mcnemar_detects_discordance_direction():
    a = [True] * 18 + [False] * 2
    b = [False] * 18 + [True] * 2
    result = exact_mcnemar_pvalue(a, b)
    assert result["a_only"] == 18
    assert result["b_only"] == 2
    assert result["p_value"] < 0.01


def test_paired_bootstrap_difference_is_deterministic():
    a = [1.0, 1.0, 0.0, 1.0]
    b = [0.0, 1.0, 0.0, 0.0]
    first = paired_bootstrap_difference(a, b, samples=1000, seed=7)
    second = paired_bootstrap_difference(a, b, samples=1000, seed=7)
    assert first == second
    assert first["difference"] == 0.5
