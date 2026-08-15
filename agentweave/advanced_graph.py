from __future__ import annotations
import hashlib, math, time
from dataclasses import dataclass
import networkx as nx

class AdvancedKnowledgeGraph:
    """Ontology-aware, freshness-aware capability/knowledge graph."""
    def __init__(self,half_life_seconds=30*86400):
        self.g=nx.MultiDiGraph(); self.half_life=half_life_seconds
    def add_concept(self,name,kind='knowledge',aliases=None,parents=None):
        n=f'{kind}:{name.lower()}'; self.g.add_node(n,kind=kind,name=name.lower(),updated_at=time.time())
        for a in aliases or []:
            x=f'{kind}:{a.lower()}'; self.g.add_node(x,kind=kind,name=a.lower()); self.g.add_edge(x,n,relation='alias_of',weight=1.0)
        for p in parents or []:
            x=f'{kind}:{p.lower()}'; self.g.add_node(x,kind=kind,name=p.lower()); self.g.add_edge(n,x,relation='is_a',weight=.9)
        return n
    def add_agent(self,agent):
        self.g.add_node(agent.agent_id,kind='agent',updated_at=time.time())
        for cap in agent.capabilities:
            c=self.add_concept(cap.name,'capability'); self.g.add_edge(agent.agent_id,c,relation='has_capability',weight=cap.proficiency,validated=cap.validated,updated_at=time.time())
        for k in agent.knowledge:
            c=self.add_concept(k,'knowledge'); self.g.add_edge(agent.agent_id,c,relation='knows',weight=1.0,updated_at=time.time())
    def inherit(self,child,parent,kind='capability',weight=.85):
        a=self.add_concept(child,kind); b=self.add_concept(parent,kind); self.g.add_edge(a,b,relation='is_a',weight=weight)
    def freshness(self,updated_at,now=None):
        age=max(0,(now or time.time())-float(updated_at or 0)); return math.pow(.5,age/max(1,self.half_life))
    def semantic_similarity(self,a,b,vectorizer=None):
        if a.lower()==b.lower(): return 1.0
        if vectorizer:
            va,vb=vectorizer(a),vectorizer(b); dot=sum(x*y for x,y in zip(va,vb)); na=math.sqrt(sum(x*x for x in va)); nb=math.sqrt(sum(x*x for x in vb)); return dot/max(1e-12,na*nb)
        # deterministic token-hash embedding fallback
        def v(s):
            out=[0.0]*64
            for tok in s.lower().replace('-',' ').replace('_',' ').split(): out[int(hashlib.sha256(tok.encode()).hexdigest(),16)%64]+=1
            return out
        return self.semantic_similarity(a,b,v)
    def agent_score(self,agent_id,required:list[str],kind='capability',semantic_threshold=.35):
        if not self.g.has_node(agent_id): return 0.0
        edges=[(v,d) for _,v,d in self.g.out_edges(agent_id,data=True) if self.g.nodes[v].get('kind')==kind]
        if not required: return 1.0
        scores=[]
        for req in required:
            best=0.0
            for node,data in edges:
                name=self.g.nodes[node].get('name',''); sim=self.semantic_similarity(req,name)
                if sim>=semantic_threshold: best=max(best,sim*float(data.get('weight',1))*self.freshness(data.get('updated_at',time.time())))
                for _,parent,pd in self.g.out_edges(node,data=True):
                    if pd.get('relation')=='is_a': best=max(best,self.semantic_similarity(req,self.g.nodes[parent].get('name',''))*float(pd.get('weight',.8)))
            scores.append(best)
        return sum(scores)/len(scores)
