from __future__ import annotations
import json, sqlite3
from .models import AgentProfile, Capability, TrustVector, ExecutionProfile

class ReputationStore:
    def __init__(self,path='agentweave.db'):
        self.path=str(path)
        self._memory_conn=sqlite3.connect(':memory:') if self.path == ':memory:' else None
        self._init()
    def _conn(self):
        return self._memory_conn if self._memory_conn is not None else sqlite3.connect(self.path)
    def _init(self):
        with self._conn() as c:
            c.execute('create table if not exists agents (agent_id text primary key, payload text not null)')
            c.execute('create table if not exists outcomes (id integer primary key autoincrement, agent_id text, success integer, score real, detail text, created_at datetime default current_timestamp)')
    def save_agent(self,a:AgentProfile):
        with self._conn() as c: c.execute('insert into agents(agent_id,payload) values(?,?) on conflict(agent_id) do update set payload=excluded.payload',(a.agent_id,json.dumps(a.to_dict())))
    def load_agents(self):
        out=[]
        with self._conn() as c:
            for _,payload in c.execute('select agent_id,payload from agents'):
                d=json.loads(payload)
                d['capabilities']=[Capability(**x) for x in d.get('capabilities',[])]
                d['trust']=TrustVector(**d.get('trust',{})); d['execution']=ExecutionProfile(**d.get('execution',{}))
                out.append(AgentProfile(**d))
        return out
    def record_outcome(self,agent_id,success,score=0.0,detail=None):
        with self._conn() as c: c.execute('insert into outcomes(agent_id,success,score,detail) values(?,?,?,?)',(agent_id,int(bool(success)),float(score),json.dumps(detail or {})))
    def recent_outcomes(self,agent_id,limit=20):
        with self._conn() as c:
            rows=c.execute('select success,score,detail,created_at from outcomes where agent_id=? order by id desc limit ?',(agent_id,limit)).fetchall()
        return [{'success':bool(r[0]),'score':r[1],'detail':json.loads(r[2] or '{}'),'created_at':r[3]} for r in rows]
