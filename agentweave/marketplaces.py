from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import httpx
from .models import AgentProfile, Capability, ExecutionProfile
from .discovery import AgentCardDiscovery

class AWSBedrockAgentConnector:
    """Lists agents from the caller's Amazon Bedrock account via boto3."""
    def __init__(self,region_name=None,client=None):
        if client is None:
            try:
                import boto3
            except ImportError as exc: raise RuntimeError('Install agentweave[aws]') from exc
            client=boto3.client('bedrock-agent',region_name=region_name)
        self.client=client
    async def list_agents(self):
        token=None; out=[]
        while True:
            kwargs={'maxResults':100}
            if token: kwargs['nextToken']=token
            page=self.client.list_agents(**kwargs)
            for x in page.get('agentSummaries',[]):
                caps=[Capability('reasoning',.5,False)]
                out.append(AgentProfile(str(x.get('agentId')),x.get('agentName','Bedrock Agent'),caps,domains=['aws-bedrock'],execution=ExecutionProfile(location='cloud'),metadata={'ecosystem':'aws-bedrock','summary':x}))
            token=page.get('nextToken')
            if not token: break
        return out

class MicrosoftFoundryAgentConnector:
    """Microsoft Foundry Agents REST connector."""
    def __init__(self,endpoint:str,token:str,api_version:str): self.endpoint=endpoint.rstrip('/'); self.token=token; self.api_version=api_version
    async def list_agents(self):
        headers={'Authorization':f'Bearer {self.token}'}; out=[]; url=f'{self.endpoint}/agents'
        async with httpx.AsyncClient(timeout=30,follow_redirects=True) as client:
            while url:
                r=await client.get(url,params={'api-version':self.api_version},headers=headers); r.raise_for_status(); data=r.json()
                items=data.get('value') or data.get('agents') or []
                for x in items:
                    latest=((x.get('versions') or {}).get('latest') or {})
                    card=x.get('agent_card') or latest.get('agent_card') or {}
                    skills=card.get('skills') or []
                    caps=[Capability(s.get('id') or s.get('name') or 'unknown',.5,False) if isinstance(s,dict) else Capability(str(s)) for s in skills]
                    ep=((x.get('agent_endpoint') or {}).get('url') or latest.get('endpoint'))
                    out.append(AgentProfile(str(x.get('id') or x.get('name')),x.get('name','Foundry Agent'),caps or [Capability('reasoning')],domains=['microsoft-foundry'],execution=ExecutionProfile(location='cloud',endpoint=ep),metadata={'ecosystem':'microsoft-foundry','agent_card':card,'raw':x}))
                url=data.get('nextLink')
        return out

class GoogleCloudMarketplaceA2AConnector:
    """Loads procured Google Cloud Marketplace A2A Agent Cards.

    Google Cloud Marketplace A2A products publish Agent Cards; after procurement,
    pass their card URLs here. This avoids pretending there is a public catalog API.
    """
    def __init__(self,agent_card_urls:list[str]): self.urls=list(agent_card_urls); self.discovery=AgentCardDiscovery()
    async def list_agents(self):
        out=[]
        for url in self.urls:
            a=await self.discovery.fetch(url); a.metadata['ecosystem']='google-cloud-marketplace'; a.metadata['marketplace_card_url']=url; out.append(a)
        return out

class CatalogManifestConnector:
    """Connector for curated enterprise A2A catalogs with explicit card URLs."""
    def __init__(self,manifest_url:str,token:str|None=None): self.url=manifest_url; self.token=token; self.discovery=AgentCardDiscovery()
    async def list_agents(self):
        headers={'Authorization':f'Bearer {self.token}'} if self.token else {}
        async with httpx.AsyncClient(timeout=30,follow_redirects=True) as client:
            r=await client.get(self.url,headers=headers); r.raise_for_status(); data=r.json()
        cards=data.get('agentCards') or data.get('agents') or data
        out=[]
        for item in cards:
            url=item if isinstance(item,str) else item.get('agentCardUrl') or item.get('url')
            if url: out.append(await self.discovery.fetch(url))
        return out
