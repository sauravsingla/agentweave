import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.bfcl_native_live_study import CATEGORY, exact_mcnemar, read_score_rows, select_ids, wilson
from scripts.bfcl_routing_proxy import _provider_group, _tool_name


def test_sample_selection_is_deterministic_and_content_blind(tmp_path: Path):
    path = tmp_path / "data.json"
    path.write_text('\n'.join([
        '{"id":"multiple_2","question":"z"}',
        '{"id":"multiple_1","question":"a"}',
        '{"id":"multiple_3","question":"m"}',
    ]))
    first = select_ids(path, 2)
    second = select_ids(path, 2)
    assert first == second
    assert len(first) == 2
    assert set(first) <= {"multiple_1", "multiple_2", "multiple_3"}


def test_wilson_and_exact_mcnemar_are_bounded():
    lo, hi = wilson(8, 10)
    assert 0 <= lo < .8 < hi <= 1
    assert exact_mcnemar([True, True, False], [False, True, False]) == 1.0


def test_bfcl_partial_score_omitted_success_is_inferred_from_aggregate(tmp_path: Path):
    score = tmp_path / "nested" / f"BFCL_v4_{CATEGORY}_score.json"
    score.parent.mkdir(parents=True)
    sampled_ids = [f"{CATEGORY}_1", f"{CATEGORY}_2", f"{CATEGORY}_3"]
    rows = [
        {"accuracy": 1 / 3, "correct_count": 1, "total_count": 3},
        {"id": sampled_ids[0], "valid": False},
        {"id": sampled_ids[2], "valid": False},
    ]
    score.write_text("\n".join(json.dumps(r) for r in rows))
    parsed = read_score_rows(tmp_path, sampled_ids)
    assert parsed == {sampled_ids[0]: False, sampled_ids[1]: True, sampled_ids[2]: False}


def test_bfcl_provider_grouping_is_stable():
    assert _provider_group("TwitterAPI_post_tweet") == "TwitterAPI"
    assert _provider_group("GorillaFileSystem_mv") == "GorillaFileSystem"
    tool = {"type": "function", "function": {"name": "TwitterAPI_post_tweet", "description": "post"}}
    assert _tool_name(tool) == "TwitterAPI_post_tweet"
