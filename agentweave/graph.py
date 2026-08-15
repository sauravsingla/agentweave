from __future__ import annotations
import networkx as nx
from .models import AgentProfile, Requirement

class CapabilityGraph:
    def __init__(self): self.g=nx.MultiDiGraph()
    def add_agent(self,a:AgentProfile):
        self.g.add_node(a.agent_id, kind='agent', name=a.name)
        for cap in a.capabilities:
            c=f'cap:{cap.name.lower()}'; self.g.add_node(c,kind='capability',name=cap.name.lower()); self.g.add_edge(a.agent_id,c,relation='has_capability',weight=cap.proficiency,validated=cap.validated)
        for d in a.domains:
            n=f'domain:{d.lower()}'; self.g.add_node(n,kind='domain',name=d.lower()); self.g.add_edge(a.agent_id,n,relation='domain')
        for k in a.knowledge:
            n=f'knowledge:{k.lower()}'; self.g.add_node(n,kind='knowledge',name=k.lower()); self.g.add_edge(a.agent_id,n,relation='knows')
    def remove_agent(self,agent_id):
        if self.g.has_node(agent_id): self.g.remove_node(agent_id)
    def coverage(self,req:Requirement,agents:list[AgentProfile]):
        need={f'cap:{c.lower()}' for c in req.capabilities}; covered=set()
        for a in agents:
            if not self.g.has_node(a.agent_id): continue
            covered |= {v for _,v,e in self.g.out_edges(a.agent_id,data=True) if e.get('relation')=='has_capability' and e.get('validated')}
        return len(need & covered)/max(1,len(need))
    def candidate_agents(self,req:Requirement):
        scores={}
        for cap in req.capabilities:
            node=f'cap:{cap.lower()}'
            if not self.g.has_node(node): continue
            for u,_,e in self.g.in_edges(node,data=True):
                if self.g.nodes[u].get('kind')=='agent': scores[u]=scores.get(u,0.0)+float(e.get('weight',0.0))
        return sorted(scores,key=scores.get,reverse=True)

class KnowledgeGraph(CapabilityGraph):
    def related_agents(self,topics:list[str]):
        out=set()
        for topic in topics:
            node=f'knowledge:{topic.lower()}'
            if self.g.has_node(node): out |= {u for u,_,_ in self.g.in_edges(node,data=True)}
        return sorted(out)
