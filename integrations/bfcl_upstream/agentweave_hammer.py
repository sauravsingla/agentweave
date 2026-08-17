from __future__ import annotations

import importlib.util
import os
from pathlib import Path

try:
    # Upstream Gorilla/BFCL location after submission.
    from bfcl_eval.model_handler.local_inference.agentweave_router import BFCLToolRouter
except ImportError:  # Repository-local compatibility-tree location.
    router_path = Path(__file__).with_name("agentweave_router.py")
    spec = importlib.util.spec_from_file_location("agentweave_bfcl_router_local", router_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load AgentWeave BFCL router from {router_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    BFCLToolRouter = module.BFCLToolRouter

from bfcl_eval.model_handler.local_inference.hammer import HammerHandler
from overrides import override


class AgentWeaveHammerHandler(HammerHandler):
    """BFCL handler for AgentWeave + Hammer2.1-1.5B.

    BFCL supplies its normal candidate function list. AgentWeave performs routing
    immediately before Hammer prompt construction, so the BFCL question,
    evaluator ground truth, and function definitions remain unchanged.
    """

    def __init__(
        self,
        model_name,
        temperature,
        registry_name,
        is_fc_model,
        dtype="bfloat16",
        **kwargs,
    ) -> None:
        super().__init__(
            model_name,
            temperature,
            registry_name,
            is_fc_model,
            dtype=dtype,
            **kwargs,
        )
        self.agentweave_router = BFCLToolRouter(
            max_provider_agents=int(os.getenv("AGENTWEAVE_BFCL_MAX_AGENTS", "4")),
            max_tools=int(os.getenv("AGENTWEAVE_BFCL_MAX_TOOLS", "6")),
            embedding_model=os.getenv(
                "AGENTWEAVE_BFCL_EMBEDDING_MODEL",
                "sentence-transformers/all-MiniLM-L6-v2",
            ),
        )
        self.last_agentweave_selected_tools: list[str] = []

    @override
    def _format_prompt(self, messages, function):
        routed_functions = self.agentweave_router.select(messages, function)
        self.last_agentweave_selected_tools = [
            str(item.get("function", item).get("name", ""))
            for item in routed_functions
        ]
        return super()._format_prompt(messages, routed_functions)
