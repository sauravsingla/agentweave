from __future__ import annotations
import argparse, importlib, importlib.metadata, json, pathlib
from dataclasses import dataclass, field

@dataclass
class AgentWeaveConfig:
    db_path:str='agentweave.db'
    max_agents:int=5
    rounds:int=2
    use_native:bool=True
    require_signed_cards:bool=False
    settings:dict=field(default_factory=dict)
    @classmethod
    def load(cls,path):
        p=pathlib.Path(path); text=p.read_text()
        if p.suffix in {'.yaml','.yml'}:
            try: import yaml
            except ImportError as exc: raise RuntimeError('Install agentweave[yaml]') from exc
            data=yaml.safe_load(text) or {}
        else: data=json.loads(text)
        known={k:data.pop(k) for k in list(data) if k in cls.__dataclass_fields__ and k!='settings'}
        return cls(**known,settings=data)

class PluginManager:
    def __init__(self,group='agentweave.plugins'): self.group=group; self.plugins={}
    def discover(self):
        eps=importlib.metadata.entry_points(); eps=eps.select(group=self.group) if hasattr(eps,'select') else eps.get(self.group,[])
        for ep in eps: self.plugins[ep.name]=ep.load()
        return dict(self.plugins)
    def register(self,name,plugin): self.plugins[name]=plugin
    def get(self,name): return self.plugins[name]

class AgentWeaveSDK:
    def __init__(self,weave): self.weave=weave
    async def register(self,agent): return self.weave.registry.register(agent)
    async def solve(self,requirement,**kwargs): return await self.weave.solve(requirement,**kwargs)
    async def ingest(self,connector,**kwargs): return await self.weave.ingest_marketplace(connector,**kwargs)
    def agents(self): return self.weave.registry.all()

async def _run_cli(args):
    from .orchestrator import AgentWeave
    cfg=AgentWeaveConfig.load(args.config) if args.config else AgentWeaveConfig()
    weave=AgentWeave(db_path=cfg.db_path,use_native=cfg.use_native)
    weave.registry.load_persisted()
    if args.command=='agents':
        print(json.dumps([a.to_dict() for a in weave.registry.all()],indent=2,default=str)); return 0
    if args.command=='solve':
        print(json.dumps(await weave.solve(args.requirement,max_agents=cfg.max_agents,rounds=cfg.rounds),indent=2,default=str)); return 0
    return 1

def main(argv=None):
    p=argparse.ArgumentParser(prog='agentweave'); p.add_argument('--config')
    s=p.add_subparsers(dest='command',required=True)
    s.add_parser('agents'); q=s.add_parser('solve'); q.add_argument('requirement')
    args=p.parse_args(argv)
    import asyncio; return asyncio.run(_run_cli(args))
