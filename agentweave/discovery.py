from __future__ import annotations
import httpx
from .models import AgentProfile, Capability, ExecutionProfile


def _first_interface(card: dict) -> dict:
    interfaces = card.get('supportedInterfaces') or card.get('supported_interfaces') or card.get('interfaces') or []
    if interfaces and isinstance(interfaces[0], dict):
        return interfaces[0]
    return {}


class AgentCardDiscovery:
    async def fetch(self,url:str)->AgentProfile:
        async with httpx.AsyncClient(timeout=20,follow_redirects=True) as client:
            r=await client.get(url); r.raise_for_status(); card=r.json()
        caps=[]
        skills=card.get('skills',[]) or card.get('capabilities',[])
        for s in skills:
            if isinstance(s,str):
                caps.append(Capability(s))
            elif isinstance(s,dict):
                caps.append(Capability(s.get('id') or s.get('name') or 'unknown', float(s.get('proficiency',.5))))
        interface=_first_interface(card)
        endpoint=(interface.get('url') or interface.get('endpoint') or card.get('url') or card.get('endpoint'))
        binding=(interface.get('protocolBinding') or interface.get('protocol_binding') or card.get('protocolBinding') or card.get('preferredTransport') or 'JSONRPC')
        protocol_version=(interface.get('protocolVersion') or interface.get('protocol_version') or card.get('protocolVersion') or '1.0')
        agent=AgentProfile(
            agent_id=str(card.get('id') or card.get('name') or endpoint or url),
            name=card.get('name','A2A Agent'),
            capabilities=caps,
            domains=list(card.get('domains',[])),
            knowledge=list(card.get('knowledge',[])),
            execution=ExecutionProfile(location=card.get('location','cloud'),endpoint=endpoint),
            metadata={
                'agent_card':card,
                'agent_card_url':url,
                'protocol_binding':binding,
                'protocol_version':protocol_version,
                'streaming':bool((card.get('capabilities') or {}).get('streaming',False)),
            },
        )
        return agent

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
