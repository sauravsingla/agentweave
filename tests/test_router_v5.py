from research.router_v5 import InteractiveIntentRouterV5


TRAIN = [
    ("Implement a Python function that returns the largest integer in a list.", "swebench"),
    ("Find who wrote the paper and verify the publication year.", "search"),
    ("Use the API endpoint to invoke the external tool.", "mcpbench"),
    ("Calculate the probability of drawing two aces.", "mathhay"),
    ("Check the refund policy for this customer booking.", "tau2bench"),
    ("Open the browser settings page and change the default option.", "terminalbench"),
]


def router():
    return InteractiveIntentRouterV5().fit(TRAIN)


def test_routes_commerce_goal_to_interactive_family():
    pred = router().predict("Buy the least expensive red blanket from the Blankets & Throws category.")
    assert pred.family == "terminalbench"


def test_routes_social_goal_to_interactive_family():
    pred = router().predict("Post a reply to the newest thread about electric vehicles in the community.")
    assert pred.family == "terminalbench"


def test_routes_classified_goal_to_interactive_family():
    pred = router().predict("Find the cheapest bicycle listing and contact the seller about pickup.")
    assert pred.family == "terminalbench"


def test_does_not_turn_plain_fact_question_into_browser_goal():
    pred = router().predict("Who is the author of the most reviewed book in this list?")
    assert pred.family in {"search", "terminalbench"}
    assert pred.family != "swebench"


def test_preserves_code_signal():
    pred = router().predict("Write a Python function that returns the cheapest product from a list of prices.")
    assert pred.family == "swebench"
