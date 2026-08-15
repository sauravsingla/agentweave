from __future__ import annotations
import asyncio, json, logging, time, uuid
from contextlib import contextmanager

class StructuredLogger:
    def __init__(self,name='agentweave'): self.log=logging.getLogger(name)
    def event(self,event,**fields): self.log.info(json.dumps({'event':event,'ts':time.time(),**fields},default=str,sort_keys=True))

class Metrics:
    def __init__(self): self.counters={}; self.histograms={}
    def inc(self,name,value=1,**labels): self.counters[(name,tuple(sorted(labels.items())))]=self.counters.get((name,tuple(sorted(labels.items()))),0)+value
    def observe(self,name,value,**labels): self.histograms.setdefault((name,tuple(sorted(labels.items()))),[]).append(float(value))

class Tracer:
    def __init__(self,service_name='agentweave'):
        self._tracer=None
        try:
            from opentelemetry import trace
            self._tracer=trace.get_tracer(service_name)
        except Exception: pass
    @contextmanager
    def span(self,name,**attrs):
        if self._tracer:
            with self._tracer.start_as_current_span(name) as span:
                for k,v in attrs.items(): span.set_attribute(k,str(v))
                yield span
        else: yield None

class AuditTrail:
    def __init__(self,store=None): self.store=store; self.events=[]
    def record(self,event_type,subject=None,**payload):
        item={'id':str(uuid.uuid4()),'event_type':event_type,'subject':subject,'payload':payload,'ts':time.time()}; self.events.append(item)
        if self.store and hasattr(self.store,'audit'):
            try: self.store.audit(event_type,subject,payload)
            except Exception: pass
        return item

class Observability:
    def __init__(self,store=None): self.log=StructuredLogger(); self.metrics=Metrics(); self.tracer=Tracer(); self.audit=AuditTrail(store)
