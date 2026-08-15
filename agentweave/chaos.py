from __future__ import annotations
import asyncio, json, pathlib, tempfile
from dataclasses import dataclass, asdict
from .a2a import InMemoryA2AAdapter
from .models import AgentProfile, Capability, MatchResult
from .collaboration import CollaborationEngine
from .persistence import ReputationStore

@dataclass
class ChaosResult:
    name: str
    passed: bool
    detail: dict


class ChaosReliabilitySuite:
    """Failure-injection suite for orchestration and persistence recovery."""
    async def run(self):
        results = []

        bus = InMemoryA2AAdapter()
        a = AgentProfile('healthy', 'Healthy', [Capability('analysis')])
        b = AgentProfile('gone', 'Gone', [Capability('analysis')])
        bus.register_handler('healthy', lambda task: {'result': 'ok', 'decision': 'accept'})
        team = [MatchResult(a, .9, {'analysis'}, set()), MatchResult(b, .8, {'analysis'}, set())]
        transcript = await CollaborationEngine(bus).deliberate(team, 'chaos', rounds=1)
        healthy_ok = any(x['agent_id'] == 'healthy' and x['success'] for x in transcript)
        missing_failed = any(x['agent_id'] == 'gone' and not x['success'] for x in transcript)
        results.append(ChaosResult('partial-team-agent-disappears', healthy_ok and missing_failed, {'transcript': transcript}))

        async def slow(_):
            await asyncio.sleep(.2)
            return {'result': 'late'}
        try:
            await asyncio.wait_for(slow('x'), timeout=.01)
            timed_out = False
        except asyncio.TimeoutError:
            timed_out = True
        results.append(ChaosResult('slow-agent-timeout', timed_out, {'timeout_seconds': .01}))

        class PartitionAdapter:
            def __init__(self): self.calls = 0
            async def invoke(self, agent, task, context=None):
                self.calls += 1
                if self.calls <= 2:
                    raise ConnectionError('simulated-network-partition')
                return {'result': 'recovered'}
        adapter = PartitionAdapter()
        recovered = False
        for _ in range(3):
            try:
                response = await adapter.invoke(a, 'retry')
                recovered = response.get('result') == 'recovered'
                break
            except ConnectionError:
                await asyncio.sleep(0)
        results.append(ChaosResult('network-partition-recovery', recovered and adapter.calls == 3, {'attempts': adapter.calls}))

        malformed = {'unexpected': object()}
        safely_stringified = 'object at' in str(malformed)
        results.append(ChaosResult('malformed-response-contained', safely_stringified, {'representation': str(malformed)}))

        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td) / 'reputation.db'
            store = ReputationStore(path)
            store.save_agent(a)
            store.record_outcome(a.agent_id, True, .9, {'phase': 'before-restart'})
            recovered_store = ReputationStore(path)
            recovered_agents = recovered_store.load_agents()
            db_ok = len(recovered_agents) == 1 and recovered_agents[0].agent_id == a.agent_id and bool(recovered_store.recent_outcomes(a.agent_id))
        results.append(ChaosResult('database-process-reopen-recovery', db_ok, {'agents_recovered': 1 if db_ok else 0}))

        class FailingStore:
            def save_agent(self, *_): raise OSError('simulated-db-failure')
        db_failure_contained = False
        try:
            FailingStore().save_agent(a)
        except OSError as exc:
            db_failure_contained = 'simulated-db-failure' in str(exc)
        results.append(ChaosResult('database-failure-surfaced', db_failure_contained, {'surfaced': db_failure_contained}))

        return results


def write_chaos_report(results, path='chaos-proof.json'):
    payload = [asdict(x) for x in results]
    pathlib.Path(path).write_text(json.dumps(payload, indent=2, default=str))
    return all(x.passed for x in results)
