from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from agentweave.requirements import RequirementAnalyzer


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'untouched_generalization.py'
spec = spec_from_file_location('untouched_generalization_eval', SCRIPT)
module = module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)
predict_family = module.predict_family


def classify(text: str) -> str:
    return predict_family(RequirementAnalyzer().analyze(text))


def test_preregistered_family_rule_uses_frozen_requirement_outputs():
    assert classify('Use an MCP server and tool to inspect this resource') == 'mcpbench'
    assert classify('Run this bash command in the Linux terminal') == 'terminalbench'
    assert classify('Fix this Python software bug and update the code') == 'swebench'
    assert classify('Research who founded this organization and find evidence') == 'search'
    assert classify('Check this compliance policy and determine what is allowed') == 'tau2bench'
    assert classify('Solve the following mathematical reasoning problem') == 'mathhay'
