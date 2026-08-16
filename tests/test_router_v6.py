from research.router_v6 import WebGoalRouterV6


TRAIN = [
    ("Solve this algebra equation", "mathhay"),
    ("Use the API endpoint to invoke a tool", "mcpbench"),
    ("Who founded the company?", "search"),
    ("Fix this Python function", "swebench"),
    ("Check whether the customer is eligible for a refund", "tau2bench"),
    ("Open the browser and update the record", "terminalbench"),
]


def test_v6_routes_natural_web_goal_to_interactive_family():
    router = WebGoalRouterV6().fit(TRAIN)
    pred = router.predict("Find the most recent order and cancel it")
    assert pred.family == "terminalbench"


def test_v6_routes_account_mutation_to_interactive_family():
    router = WebGoalRouterV6().fit(TRAIN)
    pred = router.predict("Update the shipping address on the customer account")
    assert pred.family == "terminalbench"


def test_v6_does_not_override_code_task():
    router = WebGoalRouterV6().fit(TRAIN)
    pred = router.predict("Write Python code to update a dictionary and return the result")
    assert pred.family == "swebench"


def test_v6_requires_fit():
    router = WebGoalRouterV6()
    try:
        router.predict("Open the account settings")
    except RuntimeError:
        pass
    else:
        raise AssertionError("Expected RuntimeError before fit")
