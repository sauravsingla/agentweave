from __future__ import annotations

import argparse
import asyncio
import json
import math
import random
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from agentweave import AgentProfile, Capability, ExecutionProfile, Requirement, TrustVector
from agentweave.a2a import InMemoryA2AAdapter
from agentweave.engine import AgentMatcher, PlacementEngine, TrustEngine
from agentweave.optimizer import GlobalTeamOptimizer


QUALITY_THRESHOLD = 0.85
DEFAULT_SEED = 20260816


@dataclass(frozen=True)
class Workload:
    task_id: str
    text: str
    capabilities: tuple[str, ...]


@dataclass
class TaskResult:
    task_id: str
    strategy: str
    selected_agents: list[str]
    effective_agents: list[str]
    completion: bool
    quality: float
    cost: float
    latency_ms: float
    failures: int
    recovered: bool
    recovery_attempts: int


WORKLOADS = [
    Workload('incident-response', 'Investigate an incident, analyze causes, and verify the conclusion.', ('research', 'analysis', 'verification')),
    Workload('fraud-review', 'Inspect a suspicious transaction graph, analyze patterns, and verify the decision.', ('graph', 'analysis', 'verification')),
    Workload('release-readiness', 'Review code, test the release, and assess security readiness.', ('code', 'test', 'security')),
    Workload('policy-assessment', 'Research the policy context, assess policy constraints, and verify the recommendation.', ('research', 'policy', 'verification')),
    Workload('data-investigation', 'Query the data, analyze the result, and prepare a visualization.', ('sql', 'analysis', 'visualization')),
    Workload('service-diagnosis', 'Retrieve service evidence, diagnose the issue, and communicate the resolution.', ('retrieval', 'diagnosis', 'communication')),
    Workload('risk-memo', 'Research the risk, quantify the analysis, and communicate a checked conclusion.', ('research', 'analysis', 'communication')),
    Workload('secure-change', 'Review code, assess security, and verify the change.', ('code', 'security', 'verification')),
    Workload('graph-report', 'Inspect the graph, analyze anomalies, and visualize the evidence.', ('graph', 'analysis', 'visualization')),
    Workload('data-policy', 'Query the data, assess policy constraints, and verify the finding.', ('sql', 'policy', 'verification')),
    Workload('test-diagnosis', 'Test the service, diagnose failures, and communicate next actions.', ('test', 'diagnosis', 'communication')),
    Workload('evidence-package', 'Retrieve evidence, research context, and verify the final package.', ('retrieval', 'research', 'verification')),
]

# Four tasks deliberately trigger a failure in the otherwise strongest specialist.
FAILURE_PLAN = {
    'incident-response': 'analysis-primary',
    'release-readiness': 'security-primary',
    'data-investigation': 'sql-primary',
    'service-diagnosis': 'diagnosis-primary',
}


CAPABILITIES = sorted({cap for workload in WORKLOADS for cap in workload.capabilities})


def _trust(value: float) -> TrustVector:
    return TrustVector(
        identity=value,
        capability=value,
        domain=value,
        execution=value,
        security=value,
        collaboration=value,
        historical=value,
    )


def _agent(agent_id: str, capabilities: list[tuple[str, float]], trust: float, latency_ms: float, cost: float, location: str) -> AgentProfile:
    return AgentProfile(
        agent_id=agent_id,
        name=agent_id.replace('-', ' ').title(),
        capabilities=[Capability(name, proficiency=proficiency, validated=True) for name, proficiency in capabilities],
        trust=_trust(trust),
        execution=ExecutionProfile(location=location, latency_ms=latency_ms, cost=cost, available=True),
    )


def build_agents() -> list[AgentProfile]:
    agents: list[AgentProfile] = []
    locations = ('edge', 'enterprise', 'cloud')
    for index, cap in enumerate(CAPABILITIES):
        agents.append(_agent(f'{cap}-primary', [(cap, 0.96)], 0.93, 18 + (index % 4) * 3, 0.045 + (index % 3) * 0.005, locations[index % len(locations)]))
        agents.append(_agent(f'{cap}-backup', [(cap, 0.90)], 0.82, 30 + (index % 5) * 3, 0.065 + (index % 2) * 0.005, locations[(index + 1) % len(locations)]))

    # A broad agent gives single-agent and capability-only baselines full coverage,
    # but lower per-capability quality, higher latency, and higher cost.
    agents.append(_agent('broad-generalist', [(cap, 0.72) for cap in CAPABILITIES], 0.62, 115, 0.42, 'cloud'))

    # High-coverage but unreliable agents make capability-only selection meaningfully
    # different from trust/cost-aware optimization without hiding their metadata.
    agents.append(_agent('ops-unreliable', [('analysis', 0.99), ('verification', 0.99), ('diagnosis', 0.99), ('security', 0.99)], 0.34, 72, 0.24, 'cloud'))
    agents.append(_agent('data-unreliable', [('sql', 0.99), ('graph', 0.99), ('visualization', 0.99), ('retrieval', 0.99)], 0.36, 68, 0.22, 'cloud'))
    return agents


def requirement(workload: Workload, capabilities: set[str] | None = None) -> Requirement:
    return Requirement(
        text=workload.text,
        capabilities=set(capabilities or workload.capabilities),
        inference_confidence=1.0,
        inference_source='benchmark-ground-truth-requirement',
    )


def _capability_only(req: Requirement, agents: list[AgentProfile], max_agents: int = 3) -> list[AgentProfile]:
    uncovered = set(req.capabilities)
    pool = [agent for agent in agents if agent.execution.available]
    team: list[AgentProfile] = []
    while uncovered and pool and len(team) < max_agents:
        def key(agent: AgentProfile):
            cmap = {cap.name: cap for cap in agent.capabilities}
            covered = uncovered & set(cmap)
            proficiency = sum(cmap[name].proficiency for name in covered) / max(1, len(covered))
            return len(covered), proficiency, agent.agent_id
        best = max(pool, key=key)
        covered = uncovered & {cap.name for cap in best.capabilities}
        if not covered:
            break
        team.append(best)
        uncovered -= covered
        pool.remove(best)
    return team


def select_team(strategy: str, req: Requirement, agents: list[AgentProfile], matcher: AgentMatcher, optimizer: GlobalTeamOptimizer, rng: random.Random, max_agents: int = 3) -> list[AgentProfile]:
    ranked = matcher.rank(req, agents)
    if strategy == 'agentweave-team':
        return [item.agent for item in optimizer.select(req, ranked, max_agents=max_agents)]
    if strategy == 'single-best-agent':
        return [ranked[0].agent] if ranked and ranked[0].score > 0 else []
    if strategy == 'capability-only-team':
        return _capability_only(req, agents, max_agents=max_agents)
    if strategy == 'random-team':
        pool = [agent for agent in agents if agent.execution.available]
        return rng.sample(pool, k=min(max_agents, len(pool)))
    raise ValueError(f'unknown strategy: {strategy}')


def _handler(agent: AgentProfile, workload_by_id: dict[str, Workload]):
    async def run(task_id: str):
        workload = workload_by_id[task_id]
        await asyncio.sleep(agent.execution.latency_ms / 1000.0)
        if FAILURE_PLAN.get(task_id) == agent.agent_id:
            raise RuntimeError(f'induced failure: {agent.agent_id}')
        cmap = {cap.name: cap for cap in agent.capabilities}
        delivered = {
            cap: cmap[cap].proficiency
            for cap in workload.capabilities
            if cap in cmap
        }
        return {'agent_id': agent.agent_id, 'delivered': delivered}
    return run


def _quality(required: set[str], delivered: dict[str, float]) -> float:
    if not required:
        return 1.0
    return sum(float(delivered.get(cap, 0.0)) for cap in required) / len(required)


async def _invoke_team(bus: InMemoryA2AAdapter, team: list[AgentProfile], task_id: str):
    async def invoke(agent: AgentProfile):
        started = time.perf_counter()
        try:
            result = await bus.invoke(agent, task_id, context={'benchmark': 'team-advantage'})
            return agent, result, None, (time.perf_counter() - started) * 1000.0
        except Exception as exc:  # benchmark intentionally injects failures
            return agent, None, str(exc), (time.perf_counter() - started) * 1000.0
    return await asyncio.gather(*(invoke(agent) for agent in team))


def _replacement(strategy: str, workload: Workload, missing: set[str], agents: list[AgentProfile], attempted: set[str], matcher: AgentMatcher, optimizer: GlobalTeamOptimizer, rng: random.Random) -> AgentProfile | None:
    pool = [agent for agent in agents if agent.agent_id not in attempted and agent.execution.available and missing & {c.name for c in agent.capabilities}]
    if not pool:
        return None
    req = requirement(workload, missing)
    if strategy == 'agentweave-team':
        ranked = matcher.rank(req, pool)
        selected = optimizer.select(req, ranked, max_agents=1)
        return selected[0].agent if selected else None
    if strategy == 'single-best-agent':
        ranked = matcher.rank(req, pool)
        return ranked[0].agent if ranked else None
    if strategy == 'capability-only-team':
        selected = _capability_only(req, pool, max_agents=1)
        return selected[0] if selected else None
    return rng.choice(pool)


async def run_task(strategy: str, workload: Workload, seed: int) -> TaskResult:
    agents = build_agents()
    by_id = {agent.agent_id: agent for agent in agents}
    trust = TrustEngine()
    matcher = AgentMatcher(trust, PlacementEngine(), use_native=False)
    optimizer = GlobalTeamOptimizer()
    rng = random.Random(f'{seed}:{strategy}:{workload.task_id}')
    bus = InMemoryA2AAdapter()
    workload_by_id = {item.task_id: item for item in WORKLOADS}
    for agent in agents:
        bus.register_handler(agent.agent_id, _handler(agent, workload_by_id))

    req = requirement(workload)
    initial = select_team(strategy, req, agents, matcher, optimizer, rng)
    selected_ids = [agent.agent_id for agent in initial]
    attempted = set(selected_ids)
    effective = list(initial)
    delivered: dict[str, float] = {}
    total_cost = 0.0
    failures = 0
    recovery_attempts = 0
    started = time.perf_counter()

    results = await _invoke_team(bus, initial, workload.task_id)
    failed_agents: list[AgentProfile] = []
    for agent, result, error, _ in results:
        total_cost += agent.execution.cost
        if error:
            failures += 1
            failed_agents.append(agent)
            trust.update(agent, False, 0.0, {'benchmark': 'team-advantage', 'task_id': workload.task_id, 'error': error})
        else:
            values = result.get('delivered', {})
            delivered.update({name: max(delivered.get(name, 0.0), float(score)) for name, score in values.items()})
            trust.update(agent, True, _quality(set(values), values), {'benchmark': 'team-advantage', 'task_id': workload.task_id})

    # Recovery is evaluated under each strategy's own policy. AgentWeave therefore
    # re-ranks with the updated trust state; baselines retain their defining policy.
    for _ in range(2):
        missing = {cap for cap in workload.capabilities if delivered.get(cap, 0.0) < QUALITY_THRESHOLD}
        if not missing or not failed_agents:
            break
        replacement = _replacement(strategy, workload, missing, agents, attempted, matcher, optimizer, rng)
        if replacement is None:
            break
        recovery_attempts += 1
        attempted.add(replacement.agent_id)
        total_cost += replacement.execution.cost
        row = (await _invoke_team(bus, [replacement], workload.task_id))[0]
        agent, result, error, _ = row
        if error:
            failures += 1
            trust.update(agent, False, 0.0, {'benchmark': 'team-advantage', 'task_id': workload.task_id, 'error': error})
            continue
        values = result.get('delivered', {})
        delivered.update({name: max(delivered.get(name, 0.0), float(score)) for name, score in values.items()})
        trust.update(agent, True, _quality(set(values), values), {'benchmark': 'team-advantage', 'task_id': workload.task_id})
        effective = [member for member in effective if member.agent_id not in {failed.agent_id for failed in failed_agents}] + [replacement]
        failed_agents = []

    latency_ms = (time.perf_counter() - started) * 1000.0
    quality = _quality(set(workload.capabilities), delivered)
    completion = all(delivered.get(cap, 0.0) >= QUALITY_THRESHOLD for cap in workload.capabilities)
    induced = FAILURE_PLAN.get(workload.task_id)
    selected_induced_failure = bool(induced and induced in attempted and failures)
    recovered = bool(selected_induced_failure and completion)
    return TaskResult(
        task_id=workload.task_id,
        strategy=strategy,
        selected_agents=selected_ids,
        effective_agents=[agent.agent_id for agent in effective],
        completion=completion,
        quality=quality,
        cost=total_cost,
        latency_ms=latency_ms,
        failures=failures,
        recovered=recovered,
        recovery_attempts=recovery_attempts,
    )


def summarize(rows: list[TaskResult]) -> dict:
    by_strategy: dict[str, list[TaskResult]] = {}
    for row in rows:
        by_strategy.setdefault(row.strategy, []).append(row)
    result = {}
    for strategy, items in by_strategy.items():
        recovery_opportunities = [item for item in items if item.failures > 0]
        latencies = [item.latency_ms for item in items]
        result[strategy] = {
            'tasks': len(items),
            'completion_rate': sum(item.completion for item in items) / len(items),
            'mean_quality': statistics.fmean(item.quality for item in items),
            'mean_cost': statistics.fmean(item.cost for item in items),
            'mean_latency_ms': statistics.fmean(latencies),
            'p95_latency_ms': sorted(latencies)[max(0, math.ceil(0.95 * len(latencies)) - 1)],
            'failure_events': sum(item.failures for item in items),
            'recovery_opportunities': len(recovery_opportunities),
            'recovery_success_rate': (sum(item.recovered for item in recovery_opportunities) / len(recovery_opportunities)) if recovery_opportunities else None,
        }
    return result


def markdown(summary: dict) -> str:
    names = {
        'agentweave-team': 'AgentWeave team',
        'single-best-agent': 'Single best agent',
        'random-team': 'Random team',
        'capability-only-team': 'Capability-only team',
    }
    lines = [
        '# AgentWeave multi-agent team advantage benchmark',
        '',
        'Controlled executable workload benchmark. Every strategy sees the same tasks and agent catalog. Handlers really execute, induced failures really raise exceptions, wall-clock latency is measured, invocation cost is accumulated from execution profiles, and quality is computed from delivered capability outputs. This is not presented as a production-user or external-provider benchmark.',
        '',
        '| Strategy | Task completion | Mean quality | Mean cost | Mean latency | P95 latency | Recovery success |',
        '|---|---:|---:|---:|---:|---:|---:|',
    ]
    for key in ('agentweave-team', 'single-best-agent', 'random-team', 'capability-only-team'):
        item = summary[key]
        recovery = 'n/a' if item['recovery_success_rate'] is None else f"{100*item['recovery_success_rate']:.1f}%"
        lines.append(
            f"| {names[key]} | {100*item['completion_rate']:.1f}% | {item['mean_quality']:.3f} | {item['mean_cost']:.3f} | {item['mean_latency_ms']:.1f} ms | {item['p95_latency_ms']:.1f} ms | {recovery} |"
        )
    lines += [
        '',
        f'- Quality threshold for per-capability completion: `{QUALITY_THRESHOLD:.2f}`.',
        f'- Workloads: `{len(WORKLOADS)}`; induced primary-specialist failures: `{len(FAILURE_PLAN)}`.',
        '- AgentWeave team uses `AgentMatcher` + `GlobalTeamOptimizer`; after a failure it updates trust and re-ranks before replacement.',
        '- Single-best uses the top AgentWeave-ranked candidate; random-team uses a deterministic seeded sample; capability-only greedily maximizes uncovered capabilities/proficiency while ignoring trust, cost, and latency.',
        '- All four strategies get at most two replacement attempts so recovery is compared rather than withheld from baselines.',
    ]
    return '\n'.join(lines) + '\n'


async def run_benchmark(seed: int = DEFAULT_SEED) -> dict:
    strategies = ('agentweave-team', 'single-best-agent', 'random-team', 'capability-only-team')
    rows: list[TaskResult] = []
    for strategy in strategies:
        for workload in WORKLOADS:
            rows.append(await run_task(strategy, workload, seed))
    return {
        'schema_version': 1,
        'seed': seed,
        'quality_threshold': QUALITY_THRESHOLD,
        'workloads': [asdict(item) for item in WORKLOADS],
        'failure_plan': FAILURE_PLAN,
        'summary': summarize(rows),
        'tasks': [asdict(row) for row in rows],
    }


def validate_evidence(payload: dict) -> None:
    summary = payload['summary']
    aw = summary['agentweave-team']
    competitors = [summary[key] for key in ('single-best-agent', 'random-team', 'capability-only-team')]
    if aw['completion_rate'] <= max(item['completion_rate'] for item in competitors):
        raise AssertionError('AgentWeave team must demonstrate a higher task-completion rate than all baselines in this controlled benchmark')
    if aw['mean_quality'] <= max(item['mean_quality'] for item in competitors):
        raise AssertionError('AgentWeave team must demonstrate higher mean quality than all baselines in this controlled benchmark')
    if aw['recovery_opportunities'] < 1 or aw['recovery_success_rate'] is None:
        raise AssertionError('benchmark must exercise AgentWeave recovery')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed', type=int, default=DEFAULT_SEED)
    parser.add_argument('--json-out', default='team-advantage-results.json')
    parser.add_argument('--markdown-out', default='team-advantage-results.md')
    parser.add_argument('--validate', action='store_true')
    args = parser.parse_args()

    payload = asyncio.run(run_benchmark(args.seed))
    if args.validate:
        validate_evidence(payload)
    Path(args.json_out).write_text(json.dumps(payload, indent=2) + '\n')
    Path(args.markdown_out).write_text(markdown(payload['summary']))
    print(markdown(payload['summary']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
