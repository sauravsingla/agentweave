from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

import numpy as np
from sentence_transformers import SentenceTransformer


ROOT = Path(__file__).resolve().parent


class AgentWeaveSemanticRouter:
    """Prototype-based semantic capability router built on MiniLM embeddings.

    This is an experimental semantic companion to AgentWeave's default
    deterministic routing path. It does not replace AgentWeave policy,
    authorization, or execution controls.
    """

    def __init__(
        self,
        config_path: str | Path = ROOT / "config.json",
        prototypes_path: str | Path = ROOT / "route_prototypes.json",
    ) -> None:
        self.config = json.loads(Path(config_path).read_text(encoding="utf-8"))
        self.prototypes: Dict[str, List[str]] = json.loads(
            Path(prototypes_path).read_text(encoding="utf-8")
        )
        self.model = SentenceTransformer(self.config["base_model"], device="cpu")

        texts: List[str] = []
        labels: List[str] = []
        for label, examples in self.prototypes.items():
            for example in examples:
                labels.append(label)
                texts.append(example)

        self._prototype_labels = labels
        self._prototype_embeddings = self.model.encode(
            texts,
            normalize_embeddings=bool(self.config.get("normalize_embeddings", True)),
            convert_to_numpy=True,
            show_progress_bar=False,
        )

    def route(self, query: str, top_k: int | None = None) -> List[dict]:
        if not query or not query.strip():
            raise ValueError("query must be a non-empty string")

        top_k = int(top_k or self.config.get("default_top_k", 3))
        query_embedding = self.model.encode(
            [query],
            normalize_embeddings=bool(self.config.get("normalize_embeddings", True)),
            convert_to_numpy=True,
            show_progress_bar=False,
        )[0]

        similarities = self._prototype_embeddings @ query_embedding
        best_by_label: Dict[str, float] = {}
        for label, score in zip(self._prototype_labels, similarities):
            best_by_label[label] = max(best_by_label.get(label, -1.0), float(score))

        ranked = sorted(best_by_label.items(), key=lambda item: item[1], reverse=True)
        return [
            {"route": label, "score": round(score, 6)}
            for label, score in ranked[: max(1, min(top_k, len(ranked)))]
        ]


def main() -> None:
    parser = argparse.ArgumentParser(description="AgentWeave MiniLM semantic router")
    parser.add_argument("query", help="Task or request to route")
    parser.add_argument("--top-k", type=int, default=None, help="Number of routes to return")
    args = parser.parse_args()

    router = AgentWeaveSemanticRouter()
    print(json.dumps(router.route(args.query, args.top_k), indent=2))


if __name__ == "__main__":
    main()
