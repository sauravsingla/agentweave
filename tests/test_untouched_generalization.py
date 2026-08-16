from agentweave.requirements import RequirementAnalyzer
from scripts.untouched_generalization import predict_family


def classify(text: str) -> str:
    return predict_family(RequirementAnalyzer().analyze(text))


def test_preregistered_family_rule_uses_frozen_requirement_outputs():
    assert classify('Use an MCP server and tool to inspect this resource') == 'mcpbench'
    assert classify('Run this bash command in the Linux terminal') == 'terminalbench'
    assert classify('Fix this Python software bug and update the code') == 'swebench'
    assert classify('Research who founded this organization and find evidence') == 'search'
    assert classify('Check this compliance policy and determine what is allowed') == 'tau2bench'
    assert classify('Solve the following mathematical reasoning problem') == 'mathhay'
