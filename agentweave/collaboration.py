from __future__ import annotations
import asyncio
from collections import Counter

class CollaborationEngine:
    def __init__(self,a2a): self.a2a=a2a
    async def deliberate(self,team,task,rounds=2):
        transcript=[]; context={}
        for round_no in range(rounds):
            async def one(member):
                prompt=task if round_no==0 else f'{task}\nReview the other agents\' prior findings and either support, correct, or challenge them. Prior findings: {context}'
                try:
                    resp=await self.a2a.invoke(member.agent,prompt,context={'round':round_no,'prior':context})
                    ok=True
                except Exception as e:
                    resp={'error':str(e)}; ok=False
                return {'agent_id':member.agent.agent_id,'agent_name':member.agent.name,'matched_capabilities':sorted(member.matched_capabilities),'response':resp,'success':ok,'round':round_no}
            batch=await asyncio.gather(*(one(m) for m in team))
            transcript.extend(batch); context={x['agent_id']:x['response'] for x in batch if x['success']}
        return transcript

class ConsensusEngine:
    def _extract_vote(self,response):
        if isinstance(response,dict):
            for k in ('decision','vote','answer','result'):
                v=response.get(k)
                if isinstance(v,(str,int,float,bool)): return str(v).strip().lower()
        if isinstance(response,(str,int,float,bool)): return str(response).strip().lower()
        return None
    def evaluate(self,results):
        votes=[self._extract_vote(r.get('response')) for r in results if r.get('success')]
        votes=[v for v in votes if v is not None]
        if not votes: return {'consensus':False,'decision':None,'agreement':0.0,'votes':{}}
        counts=Counter(votes); decision,n=counts.most_common(1)[0]; agreement=n/len(votes)
        return {'consensus':agreement>=.6,'decision':decision,'agreement':agreement,'votes':dict(counts)}

class ConflictResolver:
    def __init__(self,a2a): self.a2a=a2a
    async def resolve(self,team,task,results,consensus):
        if consensus.get('consensus'): return {'resolved':True,'decision':consensus.get('decision'),'method':'majority'}
        judge=max(team,key=lambda m:m.score) if team else None
        if not judge: return {'resolved':False,'decision':None,'method':'none'}
        prompt=f'Act as arbiter. Resolve conflicting agent outputs for this task: {task}. Outputs: {results}. Return a concise decision with justification.'
        try:
            resp=await self.a2a.invoke(judge.agent,prompt,context={'role':'arbiter'})
            return {'resolved':True,'decision':resp,'method':'arbiter','agent_id':judge.agent.agent_id}
        except Exception as e:
            return {'resolved':False,'decision':None,'method':'arbiter-failed','error':str(e)}
