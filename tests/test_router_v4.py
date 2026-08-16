from research.router_v4 import HierarchicalFamilyRouterV4


def _router():
    examples = [
        ("Solve the equation 2x + 3 = 9", "mathhay"),
        ("Use an API endpoint to invoke an external tool", "mcpbench"),
        ("Who discovered penicillin?", "search"),
        ("Implement a Python function that returns a sorted list", "swebench"),
        ("Check the customer refund policy for an account", "tau2bench"),
        ("Open a terminal and rename the file", "terminalbench"),
    ]
    return HierarchicalFamilyRouterV4().fit(examples)


def test_v4_hierarchy_marks_code_syntax_as_software():
    router = _router()
    evidence = router._mode_evidence("def f(values):\n    return sorted(values)\nInput: [3, 1, 2]")
    assert evidence["swebench"] > evidence["terminalbench"]
    assert router.predict("def f(values):\n    return sorted(values)\nInput: [3, 1, 2]").family == "swebench"


def test_v4_hierarchy_marks_browser_record_action_as_interactive():
    router = _router()
    text = "Navigate to the incident list, open the record, update the priority field, and submit the form."
    evidence = router._mode_evidence(text)
    assert evidence["terminalbench"] > evidence["swebench"]
    assert router.predict(text).family == "terminalbench"


def test_v4_preserves_factual_question_routing():
    router = _router()
    assert router.predict("Who developed the first successful polio vaccine?").family == "search"
