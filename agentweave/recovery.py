from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass
class RecoveryEvent:
    failed_agent_id: str
    replacement_agent_id: str | None
    attempt: int
    success: bool
    error: str | None = None

    def to_dict(self):
        return asdict(self)


class RuntimeRecoveryManager:
    """Recover failed runtime agent slots by degrading trust and selecting replacements."""

    def __init__(self, a2a, matcher, trust, register_callback=None, observability=None):
        self.a2a = a2a
        self.matcher = matcher
        self.trust = trust
        self.register_callback = register_callback
        self.observability = observability

    def _record_outcome(self, agent, success, quality_score=0.0, detail=None):
        self.trust.update(agent, success, quality_score, detail or {})
        if self.register_callback:
            self.register_callback(agent)

    async def recover(self, req, task, team, final_results, candidates, max_failovers=2):
        """Recover failed members from the final collaboration round.

        A failed member is immediately recorded as a negative runtime outcome. Candidate
        replacements are then re-ranked after that trust update, excluding agents that
        have already been attempted. A successful replacement receives the original task
        plus prior successful findings as recovery context. Failed replacement attempts
        are also recorded before the next candidate is tried.
        """
        if max_failovers <= 0:
            return {
                'effective_team': list(team),
                'final_results': list(final_results),
                'events': [],
                'failed_agent_ids': [],
                'recovered_agent_ids': [],
            }

        final_by_id = {r.get('agent_id'): r for r in final_results}
        successful_members = [m for m in team if final_by_id.get(m.agent.agent_id, {}).get('success')]
        failed_members = [m for m in team if not final_by_id.get(m.agent.agent_id, {}).get('success')]
        effective_team = list(successful_members)
        effective_results = [final_by_id[m.agent.agent_id] for m in successful_members]
        events = []
        failed_agent_ids = []
        recovered_agent_ids = []
        attempted_ids = {m.agent.agent_id for m in team}

        for failed_member in failed_members:
            failed_id = failed_member.agent.agent_id
            failed_result = final_by_id.get(failed_id, {
                'agent_id': failed_id,
                'agent_name': failed_member.agent.name,
                'matched_capabilities': sorted(failed_member.matched_capabilities),
                'response': {'error': 'missing-runtime-result'},
                'success': False,
                'round': 0,
            })
            failed_agent_ids.append(failed_id)
            error = str((failed_result.get('response') or {}).get('error', 'runtime-agent-failure'))
            self._record_outcome(
                failed_member.agent,
                False,
                0.0,
                {'phase': 'runtime-failure', 'error': error, 'task': task},
            )
            if self.observability:
                self.observability.audit.record('recovery.failure_detected', failed_id, error=error)
                self.observability.metrics.inc('runtime_agent_failures_total', agent_id=failed_id)

            recovered = False
            required_for_slot = set(failed_member.matched_capabilities) or set(req.capabilities)
            last_failed_result = failed_result

            for attempt in range(1, max_failovers + 1):
                pool = [a for a in candidates if a.agent_id not in attempted_ids and a.execution.available]
                ranked = self.matcher.rank(req, pool)
                replacement = next(
                    (r for r in ranked if (set(r.matched_capabilities) & required_for_slot) or not required_for_slot),
                    None,
                )
                if replacement is None:
                    events.append(RecoveryEvent(failed_id, None, attempt, False, 'no-suitable-replacement').to_dict())
                    break

                replacement_id = replacement.agent.agent_id
                attempted_ids.add(replacement_id)
                prior_successes = {
                    r['agent_id']: r.get('response')
                    for r in effective_results
                    if r.get('success')
                }
                try:
                    response = await self.a2a.invoke(
                        replacement.agent,
                        task,
                        context={
                            'mode': 'runtime-recovery',
                            'replaces': failed_id,
                            'attempt': attempt,
                            'prior_successes': prior_successes,
                        },
                    )
                    replacement_result = {
                        'agent_id': replacement_id,
                        'agent_name': replacement.agent.name,
                        'matched_capabilities': sorted(replacement.matched_capabilities),
                        'response': response,
                        'success': True,
                        'round': failed_result.get('round', 0),
                        'recovery': True,
                        'replaces': failed_id,
                        'recovery_attempt': attempt,
                    }
                    effective_team.append(replacement)
                    effective_results.append(replacement_result)
                    recovered_agent_ids.append(replacement_id)
                    events.append(RecoveryEvent(failed_id, replacement_id, attempt, True).to_dict())
                    if self.observability:
                        self.observability.audit.record('recovery.replacement_succeeded', replacement_id, replaces=failed_id, attempt=attempt)
                        self.observability.metrics.inc('runtime_recoveries_total', status='success')
                    recovered = True
                    break
                except Exception as exc:
                    error = str(exc)
                    last_failed_result = {
                        'agent_id': replacement_id,
                        'agent_name': replacement.agent.name,
                        'matched_capabilities': sorted(replacement.matched_capabilities),
                        'response': {'error': error},
                        'success': False,
                        'round': failed_result.get('round', 0),
                        'recovery': True,
                        'replaces': failed_id,
                        'recovery_attempt': attempt,
                    }
                    self._record_outcome(
                        replacement.agent,
                        False,
                        0.0,
                        {'phase': 'runtime-recovery-failure', 'error': error, 'task': task, 'replaces': failed_id},
                    )
                    events.append(RecoveryEvent(failed_id, replacement_id, attempt, False, error).to_dict())
                    if self.observability:
                        self.observability.audit.record('recovery.replacement_failed', replacement_id, replaces=failed_id, attempt=attempt, error=error)
                        self.observability.metrics.inc('runtime_recoveries_total', status='failed')

            if not recovered:
                effective_results.append(last_failed_result)

        return {
            'effective_team': effective_team,
            'final_results': effective_results,
            'events': events,
            'failed_agent_ids': failed_agent_ids,
            'recovered_agent_ids': recovered_agent_ids,
        }
