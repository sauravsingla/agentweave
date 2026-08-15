from __future__ import annotations
import httpx
from .models import AgentProfile, Capability, ExecutionProfile

class AgentCardDiscovery:
    async def fetch(self,url:str)->AgentProfile:
        async with httpx.AsyncClient(timeout=15,follow_redirects=True) as client:
            r=await client.get(url); r.raise_for_status(); card=r.json()
        caps=[]
        for s in card.get('skills',[]) or card.get('capabilities',[]):
            if isinstance(s,str): caps.append(Capability(s))
            else: caps.append(Capability(s.get('id') or s.get('name') or 'unknown', float(s.get('proficiency',.5))))
        endpoint=card.get('url') or card.get('endpoint')
        return AgentProfile(agent_id=str(card.get('id') or card.get('name') or endpoint), name=card.get('name','A2A Agent'), capabilities=caps, domains=list(card.get('domains',[])), knowledge=list(card.get('knowledge',[])), execution=ExecutionProfile(location=card.get('location','cloud'),endpoint=endpoint), metadata={'agent_card':card})

class HttpMarketplace:
    def __init__(self,url:str,token:str|None=None): self.url=url; self.token=token
    async def list_agents(self):
        headers={'Authorization':f'Bearer {self.token}'} if self.token else {}
        async with httpx.AsyncClient(timeout=20,follow_redirects=True) as client:
            r=await client.get(self.url,headers=headers); r.raise_for_status(); payload=r.json()
        items=payload.get('agents',payload) if isinstance(payload,dict) else payload
        out=[]
        for x in items:
            caps=[Capability(c if isinstance(c,str) else c.get('name','unknown'), .5 if isinstance(c,str) else float(c.get('proficiency',.5))) for c in x.get('capabilities',x.get('skills',[]))]
            out.append(AgentProfile(agent_id=str(x.get('id') or x.get('name')),name=x.get('name','Marketplace Agent'),capabilities=caps,domains=list(x.get('domains',[])),knowledge=list(x.get('knowledge',[])),execution=ExecutionProfile(location=x.get('location','cloud'),endpoint=x.get('endpoint') or x.get('url')),metadata={'marketplace':x}))
        return out

class StaticMarketplace:
    def __init__(self,agents): self.agents=list(agents)
    async def list_agents(self): return list(self.agents)
