from __future__ import annotations
import json, re, uuid
from .models import AgentProfile, Capability, TrustVector, ExecutionProfile


def _safe_namespace(value: str) -> str:
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,30}', value):
        raise ValueError('namespace must be a simple SQL identifier')
    return value


class PostgresReputationStore:
    """Transactional PostgreSQL registry/reputation/checkpoint store with audit history.

    ``namespace`` prefixes tables so one PostgreSQL service can host an isolated
    primary and replica target for deterministic replication/recovery tests.
    """
    def __init__(self, dsn: str, connect=None, namespace='aw'):
        if connect is None:
            try:
                import psycopg
            except ImportError as exc:
                raise RuntimeError('Install agentweave[postgres]') from exc
            connect = psycopg.connect
        self._connect = connect
        self.dsn = dsn
        self.namespace = _safe_namespace(namespace)
        self.agents_table = f'{self.namespace}_agents'
        self.outcomes_table = f'{self.namespace}_outcomes'
        self.audit_table = f'{self.namespace}_audit'
        self.workflows_table = f'{self.namespace}_workflow_checkpoints'
        self._init()

    def _conn(self):
        return self._connect(self.dsn)

    def _init(self):
        with self._conn() as c:
            with c.cursor() as cur:
                cur.execute(f'create table if not exists {self.agents_table} (agent_id text primary key, payload jsonb not null, version bigint not null default 1, updated_at timestamptz not null default now())')
                cur.execute(f'create table if not exists {self.outcomes_table} (id uuid primary key, agent_id text not null, success boolean not null, score double precision not null, detail jsonb not null, created_at timestamptz not null default now())')
                cur.execute(f'create index if not exists {self.namespace}_outcomes_agent_created on {self.outcomes_table}(agent_id,created_at desc)')
                cur.execute(f'create table if not exists {self.audit_table} (id uuid primary key, event_type text not null, subject text, payload jsonb not null, created_at timestamptz not null default now())')
                cur.execute(f'create table if not exists {self.workflows_table} (workflow_id text primary key, payload jsonb not null, version bigint not null default 1, updated_at timestamptz not null default now())')
                cur.execute(f'create index if not exists {self.namespace}_workflow_updated on {self.workflows_table}(updated_at desc)')

    def save_agent(self, a):
        payload = json.dumps(a.to_dict())
        with self._conn() as c:
            with c.cursor() as cur:
                cur.execute(
                    f'insert into {self.agents_table}(agent_id,payload) values(%s,%s::jsonb) '
                    f'on conflict(agent_id) do update set payload=excluded.payload,version={self.agents_table}.version+1,updated_at=now()',
                    (a.agent_id, payload),
                )
                cur.execute(
                    f'insert into {self.audit_table}(id,event_type,subject,payload) values(%s,%s,%s,%s::jsonb)',
                    (str(uuid.uuid4()), 'agent.saved', a.agent_id, payload),
                )

    def load_agents(self):
        with self._conn() as c:
            with c.cursor() as cur:
                cur.execute(f'select payload from {self.agents_table} order by agent_id')
                rows = cur.fetchall()
        out = []
        for (payload,) in rows:
            d = payload if isinstance(payload, dict) else json.loads(payload)
            d['capabilities'] = [Capability(**x) for x in d.get('capabilities', [])]
            d['trust'] = TrustVector(**d.get('trust', {}))
            d['execution'] = ExecutionProfile(**d.get('execution', {}))
            out.append(AgentProfile(**d))
        return out

    def record_outcome(self, agent_id, success, score=0.0, detail=None):
        payload = json.dumps(detail or {})
        with self._conn() as c:
            with c.cursor() as cur:
                cur.execute(
                    f'insert into {self.outcomes_table}(id,agent_id,success,score,detail) values(%s,%s,%s,%s,%s::jsonb)',
                    (str(uuid.uuid4()), agent_id, bool(success), float(score), payload),
                )
                cur.execute(
                    f'insert into {self.audit_table}(id,event_type,subject,payload) values(%s,%s,%s,%s::jsonb)',
                    (str(uuid.uuid4()), 'outcome.recorded', agent_id, json.dumps({'success': bool(success), 'score': float(score)})),
                )

    def audit(self, event_type, subject=None, payload=None):
        with self._conn() as c:
            with c.cursor() as cur:
                cur.execute(
                    f'insert into {self.audit_table}(id,event_type,subject,payload) values(%s,%s,%s,%s::jsonb)',
                    (str(uuid.uuid4()), event_type, subject, json.dumps(payload or {})),
                )

    def recent_outcomes(self, agent_id, limit=20):
        with self._conn() as c:
            with c.cursor() as cur:
                cur.execute(
                    f'select success,score,detail,created_at from {self.outcomes_table} where agent_id=%s order by created_at desc limit %s',
                    (agent_id, limit),
                )
                rows = cur.fetchall()
        return [{'success': r[0], 'score': r[1], 'detail': r[2], 'created_at': r[3].isoformat()} for r in rows]

    def save_workflow_checkpoint(self, workflow_id, payload):
        body = json.dumps(payload)
        with self._conn() as c:
            with c.cursor() as cur:
                cur.execute(
                    f'insert into {self.workflows_table}(workflow_id,payload) values(%s,%s::jsonb) '
                    f'on conflict(workflow_id) do update set payload=excluded.payload,version={self.workflows_table}.version+1,updated_at=now()',
                    (workflow_id, body),
                )
                cur.execute(
                    f'insert into {self.audit_table}(id,event_type,subject,payload) values(%s,%s,%s,%s::jsonb)',
                    (str(uuid.uuid4()), 'workflow.checkpoint.saved', workflow_id, json.dumps({'workflow_id': workflow_id, 'status': payload.get('status'), 'version': payload.get('version')})),
                )

    def load_workflow_checkpoint(self, workflow_id):
        with self._conn() as c:
            with c.cursor() as cur:
                cur.execute(f'select payload from {self.workflows_table} where workflow_id=%s', (workflow_id,))
                row = cur.fetchone()
        if not row:
            return None
        return row[0] if isinstance(row[0], dict) else json.loads(row[0])

    def list_workflow_checkpoints(self, limit=100):
        with self._conn() as c:
            with c.cursor() as cur:
                cur.execute(f'select payload from {self.workflows_table} order by updated_at desc limit %s', (int(limit),))
                rows = cur.fetchall()
        return [payload if isinstance(payload, dict) else json.loads(payload) for (payload,) in rows]

    def delete_workflow_checkpoint(self, workflow_id):
        with self._conn() as c:
            with c.cursor() as cur:
                cur.execute(f'delete from {self.workflows_table} where workflow_id=%s', (workflow_id,))
                deleted = cur.rowcount
        return bool(deleted)

    def counts(self):
        with self._conn() as c:
            with c.cursor() as cur:
                cur.execute(f'select count(*) from {self.agents_table}')
                agents = int(cur.fetchone()[0])
                cur.execute(f'select count(*) from {self.outcomes_table}')
                outcomes = int(cur.fetchone()[0])
                cur.execute(f'select count(*) from {self.audit_table}')
                audit = int(cur.fetchone()[0])
                cur.execute(f'select count(*) from {self.workflows_table}')
                workflows = int(cur.fetchone()[0])
        return {'agents': agents, 'outcomes': outcomes, 'audit': audit, 'workflows': workflows}

    def ping(self):
        with self._conn() as c:
            with c.cursor() as cur:
                cur.execute('select 1')
                return cur.fetchone()[0] == 1


class ReplicatedStore:
    """Write-through primary plus replicas with explicit failure accounting."""
    def __init__(self, primary, replicas=None, *, require_all=False):
        self.primary = primary
        self.replicas = list(replicas or [])
        self.require_all = require_all
        self.replication_errors = []

    def load_agents(self):
        return self.primary.load_agents()

    def recent_outcomes(self, *a, **k):
        return self.primary.recent_outcomes(*a, **k)

    def load_workflow_checkpoint(self, *a, **k):
        return self.primary.load_workflow_checkpoint(*a, **k)

    def list_workflow_checkpoints(self, *a, **k):
        return self.primary.list_workflow_checkpoints(*a, **k)

    def _replicate(self, method, *args, **kwargs):
        failures = []
        for index, replica in enumerate(self.replicas):
            try:
                getattr(replica, method)(*args, **kwargs)
            except Exception as exc:
                item = {'replica': index, 'method': method, 'error': str(exc)}
                failures.append(item)
                self.replication_errors.append(item)
        if failures and self.require_all:
            raise RuntimeError(f'replication failed: {failures}')
        return failures

    def save_agent(self, a):
        self.primary.save_agent(a)
        return self._replicate('save_agent', a)

    def record_outcome(self, *args, **kwargs):
        self.primary.record_outcome(*args, **kwargs)
        return self._replicate('record_outcome', *args, **kwargs)

    def save_workflow_checkpoint(self, *args, **kwargs):
        self.primary.save_workflow_checkpoint(*args, **kwargs)
        return self._replicate('save_workflow_checkpoint', *args, **kwargs)

    def delete_workflow_checkpoint(self, *args, **kwargs):
        result = self.primary.delete_workflow_checkpoint(*args, **kwargs)
        self._replicate('delete_workflow_checkpoint', *args, **kwargs)
        return result

    def audit(self, *args, **kwargs):
        if hasattr(self.primary, 'audit'):
            self.primary.audit(*args, **kwargs)
        return self._replicate('audit', *args, **kwargs)
