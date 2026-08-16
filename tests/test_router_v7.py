from research.router_v7 import ResearchIntentRouterV7


def fitted_router() -> ResearchIntentRouterV7:
    examples = [
        ("What is the current population of Tokyo?", "search"),
        ("Find the latest release date for this software.", "search"),
        ("Create a new incident record and assign it to the network team.", "terminalbench"),
        ("Buy the cheapest red blanket and add it to the cart.", "terminalbench"),
        ("Write a Python function that sorts a list.", "swebench"),
        ("Calculate the probability of rolling two sixes.", "mathhay"),
    ]
    return ResearchIntentRouterV7().fit(examples)


def test_information_question_routes_to_search():
    router = fitted_router()
    assert router.predict("Which museums near Central Park are open before 9am on Sunday?").family == "search"


def test_multi_source_research_routes_to_search():
    router = fitted_router()
    assert router.predict("Find the latest prices for three nearby gyms and list their opening hours.").family == "search"


def test_mutating_web_task_remains_interactive():
    router = fitted_router()
    assert router.predict("Create a support ticket, set priority to high, and submit it.").family == "terminalbench"


def test_code_task_is_not_overridden():
    router = fitted_router()
    assert router.predict("Write Python code for a function that returns the largest integer.").family == "swebench"
