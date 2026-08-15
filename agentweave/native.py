from __future__ import annotations
from .models import MatchResult

class NativeAcceleration:
    """Optional bridge to the pybind11 C++ core with safe Python fallback."""
    def __init__(self):
        try:
            import _agentweave_core as core
        except Exception:
            core = None
        self.core = core

    @property
    def available(self) -> bool:
        return self.core is not None

    def _candidate(self, agent, trust_engine, placement_engine, req):
        placement = placement_engine.score(req, agent)
        if placement <= 0:
            return None
        c = self.core.Candidate()
        c.id = agent.agent_id
        c.capabilities = [x.name.lower() for x in agent.capabilities]
        c.proficiency = sum(x.proficiency for x in agent.capabilities) / max(1, len(agent.capabilities))
        c.trust = trust_engine.score(agent)
        c.placement = placement
        return c

    def rank(self, req, agents, trust_engine, placement_engine):
        if not self.core:
            return None
        candidates = []
        by_id = {}
        for agent in agents:
            candidate = self._candidate(agent, trust_engine, placement_engine, req)
            if candidate is None:
                continue
            candidates.append(candidate)
            by_id[agent.agent_id] = agent
        ranked = self.core.rank(sorted(req.capabilities), candidates)
        out = []
        for row in ranked:
            agent = by_id[row.id]
            matched = set(row.matched)
            missing = set(req.capabilities) - matched
            placement = placement_engine.score(req, agent)
            out.append(MatchResult(agent, float(row.score), matched, missing, placement))
        return out

    def select_team(self, req, ranked, max_agents=5):
        """Execute the native greedy team-selection primitive and return MatchResults."""
        if not self.core:
            return None
        native_rows = []
        by_id = {row.agent.agent_id: row for row in ranked}
        for row in ranked:
            native = self.core.Ranked()
            native.id = row.agent.agent_id
            native.score = float(row.score)
            native.matched = sorted(row.matched_capabilities)
            native_rows.append(native)
        ids = self.core.select_team(sorted(req.capabilities), native_rows, int(max_agents))
        return [by_id[agent_id] for agent_id in ids if agent_id in by_id]

    def benchmark_team_selection(self, req, ranked, max_agents=5, iterations=100):
        if not self.core:
            return None
        import time
        started = time.perf_counter()
        last = None
        for _ in range(iterations):
            last = self.select_team(req, ranked, max_agents)
        elapsed = time.perf_counter() - started
        return {'iterations': iterations, 'seconds': elapsed, 'ops_per_second': iterations / max(elapsed, 1e-12), 'team_size': len(last or [])}
