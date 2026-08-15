from __future__ import annotations
import json, logging, time, uuid
from contextlib import contextmanager

class StructuredLogger:
    def __init__(self, name='agentweave'):
        self.log = logging.getLogger(name)
    def event(self, event, **fields):
        self.log.info(json.dumps({'event':event,'ts':time.time(),**fields},default=str,sort_keys=True))

class Metrics:
    def __init__(self):
        self.counters={}; self.histograms={}
    def inc(self,name,value=1,**labels):
        self.counters[(name,tuple(sorted(labels.items())))]=self.counters.get((name,tuple(sorted(labels.items()))),0)+value
    def observe(self,name,value,**labels):
        self.histograms.setdefault((name,tuple(sorted(labels.items()))),[]).append(float(value))
    def snapshot(self):
        return {
            'counters': [{'name':k[0],'labels':dict(k[1]),'value':v} for k,v in self.counters.items()],
            'histograms': [{'name':k[0],'labels':dict(k[1]),'count':len(v),'sum':sum(v),'min':min(v),'max':max(v)} for k,v in self.histograms.items() if v],
        }

class Tracer:
    def __init__(self, service_name='agentweave'):
        self._tracer=None; self.spans=[]
        try:
            from opentelemetry import trace
            self._tracer=trace.get_tracer(service_name)
        except Exception:
            pass
    @contextmanager
    def span(self,name,**attrs):
        started=time.perf_counter(); record={'name':name,'attributes':dict(attrs),'started_at':time.time(),'status':'ok'}
        self.spans.append(record)
        try:
            if self._tracer:
                with self._tracer.start_as_current_span(name) as span:
                    for k,v in attrs.items(): span.set_attribute(k,str(v))
                    yield span
            else:
                yield None
        except Exception as exc:
            record['status']='error'; record['error']=str(exc)
            raise
        finally:
            record['duration_ms']=(time.perf_counter()-started)*1000

class AuditTrail:
    def __init__(self,store=None):
        self.store=store; self.events=[]
    def record(self,event_type,subject=None,**payload):
        item={'id':str(uuid.uuid4()),'event_type':event_type,'subject':subject,'payload':payload,'ts':time.time()}; self.events.append(item)
        if self.store and hasattr(self.store,'audit'):
            try: self.store.audit(event_type,subject,payload)
            except Exception: pass
        return item

class SelectionExplainer:
    def explain(self,req,ranked,selected,policy=None):
        chosen={x.agent.agent_id for x in selected}
        rows=[]
        for rank,row in enumerate(ranked,1):
            rows.append({
                'rank':rank,'agent_id':row.agent.agent_id,'selected':row.agent.agent_id in chosen,
                'score':float(row.score),'placement_score':float(row.placement_score),
                'matched_capabilities':sorted(row.matched_capabilities),'missing_capabilities':sorted(row.missing_capabilities),
                'trust':float(row.agent.trust.score()),'latency_ms':float(row.agent.execution.latency_ms),
                'cost':float(row.agent.execution.cost),'policy':(policy or {}).get(row.agent.agent_id),
            })
        return {'required_capabilities':sorted(req.capabilities),'selected_agents':sorted(chosen),'candidates':rows}

class Observability:
    def __init__(self,store=None):
        self.log=StructuredLogger(); self.metrics=Metrics(); self.tracer=Tracer(); self.audit=AuditTrail(store); self.explainer=SelectionExplainer()
    def snapshot(self):
        return {'metrics':self.metrics.snapshot(),'spans':list(self.tracer.spans),'audit_events':list(self.audit.events)}
