from __future__ import annotations
import json, uuid
from .models import AgentProfile, Capability, TrustVector, ExecutionProfile

class PostgresReputationStore:
    """Transactional PostgreSQL registry/reputation store with append-only audit history."""
    def __init__(self,dsn:str,connect=None):
        if connect is None:
            try: import psycopg
            except ImportError as exc: raise RuntimeError('Install agentweave[postgres]') from exc
            connect=psycopg.connect
        self._connect=connect; self.dsn=dsn; self._init()
    def _conn(self): return self._connect(self.dsn)
    def _init(self):
        with self._conn() as c:
            with c.cursor() as cur:
                cur.execute('create table if not exists aw_agents (agent_id text primary key, payload jsonb not null, version bigint not null default 1, updated_at timestamptz not null default now())')
                cur.execute('create table if not exists aw_outcomes (id uuid primary key, agent_id text not null, success boolean not null, score double precision not null, detail jsonb not null, created_at timestamptz not null default now())')
                cur.execute('create index if not exists aw_outcomes_agent_created on aw_outcomes(agent_id,created_at desc)')
                cur.execute('create table if not exists aw_audit (id uuid primary key, event_type text not null, subject text, payload jsonb not null, created_at timestamptz not null default now())')
    def save_agent(self,a):
        payload=json.dumps(a.to_dict())
        with self._conn() as c:
            with c.cursor() as cur:
                cur.execute('insert into aw_agents(agent_id,payload) values(%s,%s::jsonb) on conflict(agent_id) do update set payload=excluded.payload,version=aw_agents.version+1,updated_at=now()',(a.agent_id,payload))
                cur.execute('insert into aw_audit(id,event_type,subject,payload) values(%s,%s,%s,%s::jsonb)',(str(uuid.uuid4()),'agent.saved',a.agent_id,payload))
    def load_agents(self):
        with self._conn() as c:
            with c.cursor() as cur: cur.execute('select payload from aw_agents order by agent_id'); rows=cur.fetchall()
        out=[]
        for (payload,) in rows:
            d=payload if isinstance(payload,dict) else json.loads(payload); d['capabilities']=[Capability(**x) for x in d.get('capabilities',[])]; d['trust']=TrustVector(**d.get('trust',{})); d['execution']=ExecutionProfile(**d.get('execution',{})); out.append(AgentProfile(**d))
        return out
    def record_outcome(self,agent_id,success,score=0.0,detail=None):
        payload=json.dumps(detail or {})
        with self._conn() as c:
            with c.cursor() as cur:
                cur.execute('insert into aw_outcomes(id,agent_id,success,score,detail) values(%s,%s,%s,%s,%s::jsonb)',(str(uuid.uuid4()),agent_id,bool(success),float(score),payload))
                cur.execute('insert into aw_audit(id,event_type,subject,payload) values(%s,%s,%s,%s::jsonb)',(str(uuid.uuid4()),'outcome.recorded',agent_id,json.dumps({'success':bool(success),'score':float(score)})))
    def audit(self,event_type,subject=None,payload=None):
        with self._conn() as c:
            with c.cursor() as cur: cur.execute('insert into aw_audit(id,event_type,subject,payload) values(%s,%s,%s,%s::jsonb)',(str(uuid.uuid4()),event_type,subject,json.dumps(payload or {})))
    def recent_outcomes(self,agent_id,limit=20):
        with self._conn() as c:
            with c.cursor() as cur: cur.execute('select success,score,detail,created_at from aw_outcomes where agent_id=%s order by created_at desc limit %s',(agent_id,limit)); rows=cur.fetchall()
        return [{'success':r[0],'score':r[1],'detail':r[2],'created_at':r[3].isoformat()} for r in rows]

class ReplicatedStore:
    """Write-through primary plus best-effort replicas for HA deployments."""
    def __init__(self,primary,replicas=None): self.primary=primary; self.replicas=list(replicas or [])
    def load_agents(self): return self.primary.load_agents()
    def recent_outcomes(self,*a,**k): return self.primary.recent_outcomes(*a,**k)
    def save_agent(self,a):
        self.primary.save_agent(a)
        for r in self.replicas:
            try: r.save_agent(a)
            except Exception: pass
    def record_outcome(self,*args,**kwargs):
        self.primary.record_outcome(*args,**kwargs)
        for r in self.replicas:
            try: r.record_outcome(*args,**kwargs)
            except Exception: pass
    def audit(self,*args,**kwargs):
        if hasattr(self.primary,'audit'): self.primary.audit(*args,**kwargs)
        for r in self.replicas:
            try:
                if hasattr(r,'audit'): r.audit(*args,**kwargs)
            except Exception: pass
