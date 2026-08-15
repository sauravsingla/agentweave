from __future__ import annotations
import re
from .models import Requirement

class RequirementAnalyzer:
    ontology = {
        'research': {'research','evidence','literature','investigate'},
        'summarization': {'summarize','summary','brief'},
        'analysis': {'analyze','analyse','evaluate','assess'},
        'coding': {'code','program','python','c++','software'},
        'vision': {'image','video','vision','camera'},
        'forecasting': {'forecast','predict','prediction'},
        'optimization': {'optimize','optimise','schedule','routing'},
        'compliance': {'compliance','regulation','policy','legal'},
        'reasoning': {'reason','decision','recommend','plan','solve'}
    }
    def analyze(self,text:str,domains=None,knowledge=None,local_only=False,max_latency_ms=None,privacy_level=None):
        tokens=set(re.findall(r'[a-z0-9+.-]+', text.lower()))
        caps={k for k,v in self.ontology.items() if tokens & v} or {'reasoning'}
        local_only = local_only or any(x in text.lower() for x in ('local only','on-device','offline','do not send outside'))
        return Requirement(text=text, capabilities=caps, domains=set(domains or []), knowledge=set(knowledge or []), local_only=local_only, max_latency_ms=max_latency_ms, privacy_level=privacy_level)
