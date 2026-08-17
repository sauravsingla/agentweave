from __future__ import annotations

import numpy as np

from agentweave.bfcl import BFCLToolRouter


class _FakeEmbeddingModel:
    def encode(self, texts, normalize_embeddings=True):
        vectors = []
        for text in texts:
            text = text.lower()
            vectors.append(
                np.array(
                    [
                        1.0 if "weather" in text else 0.0,
                        1.0 if "file" in text else 0.0,
                        1.0 if "calendar" in text else 0.0,
                        0.25,
                    ],
                    dtype=float,
                )
            )
        if normalize_embeddings:
            normalized = []
            for vector in vectors:
                norm = np.linalg.norm(vector)
                normalized.append(vector / norm if norm else vector)
            return np.stack(normalized)
        return np.stack(vectors)


def _fn(name: str, description: str):
    return {
        "name": name,
        "description": description,
        "parameters": {"type": "object", "properties": {}},
    }


def test_bfcl_router_preserves_standard_functions_and_budget():
    functions = [
        _fn("WeatherAPI_forecast", "weather forecast"),
        _fn("WeatherAPI_alerts", "weather alerts"),
        _fn("CalendarAPI_create", "calendar event"),
        _fn("CalendarAPI_list", "calendar list"),
        _fn("GorillaFileSystem_mv", "move file"),
        _fn("GorillaFileSystem_cp", "copy file"),
        _fn("MapsAPI_route", "map route"),
        _fn("MusicAPI_play", "play music"),
    ]
    router = BFCLToolRouter(max_provider_agents=2, max_tools=3)
    router._model = _FakeEmbeddingModel()

    selected = router.select(
        [{"role": "user", "content": "Give me the weather forecast"}],
        functions,
    )

    assert 1 <= len(selected) <= 3
    assert all(item in functions for item in selected)
    assert functions == [
        _fn("WeatherAPI_forecast", "weather forecast"),
        _fn("WeatherAPI_alerts", "weather alerts"),
        _fn("CalendarAPI_create", "calendar event"),
        _fn("CalendarAPI_list", "calendar list"),
        _fn("GorillaFileSystem_mv", "move file"),
        _fn("GorillaFileSystem_cp", "copy file"),
        _fn("MapsAPI_route", "map route"),
        _fn("MusicAPI_play", "play music"),
    ]


def test_bfcl_router_returns_all_functions_when_under_budget():
    functions = [_fn("WeatherAPI_forecast", "weather forecast")]
    router = BFCLToolRouter(max_provider_agents=4, max_tools=6)
    assert router.select([{"role": "user", "content": "weather"}], functions) == functions
