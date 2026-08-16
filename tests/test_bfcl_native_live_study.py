import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.bfcl_native_live_study import exact_mcnemar, select_ids, wilson
from scripts.bfcl_routing_proxy import _provider_group, _tool_name


def test_sample_selection_is_deterministic_and_content_blind(tmp_path: Path):
    path = tmp_path / "data.json"
    path.write_text('\n'.join([
        '{"id":"multi_turn_base_2","question":"z"}',
        '{"id":"multi_turn_base_1","question":"a"}',
        '{"id":"multi_turn_base_3","question":"m"}',
    ]))
    first = select_ids(path, 2)
    second = select_ids(path, 2)
    assert first == second
    assert len(first) == 2
    assert set(first) <= {"multi_turn_base_1", "multi_turn_base_2", "multi_turn_base_3"}


def test_wilson_and_exact_mcnemar_are_bounded():
    lo, hi = wilson(8, 10)
    assert 0 <= lo < .8 < hi <= 1
    assert exact_mcnemar([True, True, False], [False, True, False]) == 1.0


def test_bfcl_provider_grouping_is_stable():
    assert _provider_group("TwitterAPI_post_tweet") == "TwitterAPI"
    assert _provider_group("GorillaFileSystem_mv") == "GorillaFileSystem"
    tool = {"type": "function", "function": {"name": "TwitterAPI_post_tweet", "description": "post"}}
    assert _tool_name(tool) == "TwitterAPI_post_tweet"
