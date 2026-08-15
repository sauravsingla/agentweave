from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, asdict
import json, pathlib, random, time
from .models import AgentProfile, Capability
from .storage import PostgresReputationStore, ReplicatedStore

@dataclass
class StorageProofResult:
    name: str
    passed: bool
    detail: dict


class PostgresDurabilityProof:
    """Exercises concurrency, transactions, reconnect recovery, replication and audit durability."""
    def __init__(self, dsn: str, workers=8, writes=64):
        self.dsn = dsn
        self.workers = workers
        self.writes = writes

    def run(self):
        stamp = str(int(time.time() * 1000))[-8:]
        primary = PostgresReputationStore(self.dsn, namespace=f'awp{stamp}')
        replica = PostgresReputationStore(self.dsn, namespace=f'awr{stamp}')
        store = ReplicatedStore(primary, [replica], require_all=True)

        def write(i):
            agent = AgentProfile(f'pg-{stamp}-{i}', f'PG Agent {i}', [Capability('analysis', .5 + (i % 10) / 20, True)])
            store.save_agent(agent)
            store.record_outcome(agent.agent_id, i % 3 != 0, score=(i % 10) / 10, detail={'worker_case': i})
            return agent.agent_id

        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            ids = list(pool.map(write, range(self.writes)))

        primary_counts = primary.counts()
        replica_counts = replica.counts()
        concurrent_ok = primary_counts['agents'] == self.writes and primary_counts['outcomes'] == self.writes
        replica_ok = replica_counts['agents'] == self.writes and replica_counts['outcomes'] == self.writes

        recovered = PostgresReputationStore(self.dsn, namespace=f'awp{stamp}')
        recovered_ids = {a.agent_id for a in recovered.load_agents()}
        recovery_ok = set(ids) == recovered_ids and recovered.ping()
        audit_ok = primary_counts['audit'] >= self.writes * 2 and replica_counts['audit'] >= self.writes * 2

        results = [
            StorageProofResult('postgres-concurrent-writes', concurrent_ok, {'expected': self.writes, 'counts': primary_counts}),
            StorageProofResult('postgres-reconnect-recovery', recovery_ok, {'recovered': len(recovered_ids), 'expected': self.writes}),
            StorageProofResult('postgres-write-through-replication', replica_ok and not store.replication_errors, {'primary': primary_counts, 'replica': replica_counts, 'errors': store.replication_errors}),
            StorageProofResult('postgres-audit-durability', audit_ok, {'primary_audit': primary_counts['audit'], 'replica_audit': replica_counts['audit']}),
        ]
        return results


def write_storage_report(results, path='storage-proof.json'):
    payload = [asdict(x) for x in results]
    pathlib.Path(path).write_text(json.dumps(payload, indent=2))
    return all(x.passed for x in results)
