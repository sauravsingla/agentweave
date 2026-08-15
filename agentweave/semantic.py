from __future__ import annotations
import math, re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

CitationChecker=Callable[[str],Awaitable[float]|float]
Verifier=Callable[[str,list[dict]],Awaitable[dict]|dict]

@dataclass
class SemanticVerdict:
    score: float
    factuality: float
    citation_quality: float
    consistency: float
    uncertainty: float
    contradictions: list[str]
    verifier: dict|None=None

class SemanticResultVerifier:
    """Pluggable semantic verifier without forcing one LLM/vendor dependency."""
    def __init__(self,citation_checker:CitationChecker|None=None,verifier_agent:Verifier|None=None):
        self.citation_checker=citation_checker; self.verifier_agent=verifier_agent
    def _text(self,r):
        x=r.get('response',r) if isinstance(r,dict) else r
        if isinstance(x,dict):
            for k in ('result','answer','text','content','decision'):
                if isinstance(x.get(k),str): return x[k]
            return str(x)
        return str(x or '')
    def _tokens(self,text): return set(re.findall(r'[a-z0-9]+',text.lower()))
    def _consistency(self,texts):
        if len(texts)<2: return 1.0,[]
        vals=[]; contradictions=[]
        neg=(' not ',' no ',' never ','false','incorrect','reject')
        for i in range(len(texts)):
            for j in range(i+1,len(texts)):
                a,b=self._tokens(texts[i]),self._tokens(texts[j]); sim=len(a&b)/max(1,len(a|b)); vals.append(sim)
                na=any(x in ' '+texts[i].lower()+' ' for x in neg); nb=any(x in ' '+texts[j].lower()+' ' for x in neg)
                if sim>.35 and na!=nb: contradictions.append(f'{i}:{j}')
        return sum(vals)/max(1,len(vals)),contradictions
    def _uncertainty(self,text):
        hits=sum(text.lower().count(x) for x in ('maybe','possibly','uncertain','approximately','likely','i think','cannot verify'))
        explicit=re.findall(r'\b(?:confidence|probability)\s*[:=]?\s*(0(?:\.\d+)?|1(?:\.0+)?|\d{1,2}%)',text.lower())
        if explicit:
            v=explicit[0]; conf=float(v[:-1])/100 if v.endswith('%') else float(v); return max(0.0,min(1.0,1-conf))
        return min(1.0,hits/5)
    async def verify(self,results:list[dict],question:str='')->dict:
        texts=[self._text(r) for r in results if r.get('success',True)]
        consistency,contradictions=self._consistency(texts)
        citation_scores=[]
        for t in texts:
            urls=re.findall(r'https?://\S+',t); markers=re.findall(r'\[[0-9]+\]|doi:|source:',t,re.I)
            base=min(1.0,.35*len(urls)+.2*len(markers))
            if self.citation_checker:
                x=self.citation_checker(t); x=await x if hasattr(x,'__await__') else x; base=.4*base+.6*float(x)
            citation_scores.append(base)
        citation_quality=sum(citation_scores)/max(1,len(citation_scores))
        uncertainty=sum(self._uncertainty(t) for t in texts)/max(1,len(texts))
        factuality=max(0.0,min(1.0,.55*consistency+.25*citation_quality+.20*(1-uncertainty)))
        verifier=None
        if self.verifier_agent:
            v=self.verifier_agent(question,results); verifier=await v if hasattr(v,'__await__') else v
            if isinstance(verifier,dict) and 'score' in verifier: factuality=.5*factuality+.5*float(verifier['score'])
        score=max(0.0,min(1.0,.55*factuality+.20*citation_quality+.20*consistency+.05*(1-uncertainty)))
        return SemanticVerdict(score,factuality,citation_quality,consistency,uncertainty,contradictions,verifier).__dict__
