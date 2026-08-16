from research.router_v2 import PrototypeFamilyRouterV2


def test_router_v2_is_deterministic_and_label_blind_at_prediction_time():
    examples = [
        ("solve this arithmetic problem with numbers", "mathhay"),
        ("use an mcp server tool", "mcpbench"),
        ("research sources and find evidence", "search"),
        ("fix the python code bug and tests", "swebench"),
        ("apply the customer support policy", "tau2bench"),
        ("use bash shell commands on linux files", "terminalbench"),
    ]
    router = PrototypeFamilyRouterV2().fit(examples)

    first = router.predict("run a bash command to list files in a directory")
    second = router.predict("run a bash command to list files in a directory")

    assert first.family == "terminalbench"
    assert first == second
    assert 0.0 < first.confidence <= 1.0
    assert set(first.scores) == {
        "mathhay", "mcpbench", "search", "swebench", "tau2bench", "terminalbench"
    }


def test_router_v2_requires_fit():
    router = PrototypeFamilyRouterV2()
    try:
        router.predict("anything")
    except RuntimeError as exc:
        assert "fitted" in str(exc)
    else:
        raise AssertionError("predict() should require fit()")
