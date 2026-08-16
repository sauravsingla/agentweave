from research.router_v3 import SemanticFamilyRouterV3


def _router():
    examples = [
        ("solve this arithmetic problem", "mathhay"),
        ("invoke an api tool server", "mcpbench"),
        ("research evidence and find factual information", "search"),
        ("fix a python repository bug", "swebench"),
        ("apply the customer support policy", "tau2bench"),
        ("run a linux shell command", "terminalbench"),
    ]
    return SemanticFamilyRouterV3().fit(examples)


def test_router_v3_detects_general_software_intent():
    router = _router()
    pred = router.predict("Write a function that takes a list of integers and returns the largest even value")
    assert pred.family == "swebench"
    assert 0.0 < pred.confidence <= 1.0


def test_router_v3_detects_factual_question_intent():
    router = _router()
    pred = router.predict("Who developed the first widely used polio vaccine?")
    assert pred.family == "search"


def test_router_v3_detects_os_interaction_intent():
    router = _router()
    pred = router.predict("Open the desktop settings and change the default application")
    assert pred.family == "terminalbench"


def test_router_v3_is_deterministic():
    router = _router()
    text = "Implement a method that returns the reverse of an input string"
    assert router.predict(text) == router.predict(text)
