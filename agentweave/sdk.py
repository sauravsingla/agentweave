from __future__ import annotations
import argparse, importlib.metadata, json, pathlib, platform, shutil, sys
from dataclasses import dataclass, field

@dataclass
class AgentWeaveConfig:
    db_path: str = 'agentweave.db'
    max_agents: int = 5
    rounds: int = 2
    use_native: bool = True
    require_signed_cards: bool = False
    settings: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path):
        p = pathlib.Path(path); text = p.read_text()
        if p.suffix in {'.yaml','.yml'}:
            try:
                import yaml
            except ImportError as exc:
                raise RuntimeError('Install agentweave[yaml]') from exc
            data = yaml.safe_load(text) or {}
        else:
            data = json.loads(text)
        known = {k:data.pop(k) for k in list(data) if k in cls.__dataclass_fields__ and k != 'settings'}
        return cls(**known, settings=data)

    def to_dict(self):
        return {'db_path':self.db_path,'max_agents':self.max_agents,'rounds':self.rounds,'use_native':self.use_native,'require_signed_cards':self.require_signed_cards,**self.settings}


class PluginManager:
    def __init__(self, group='agentweave.plugins'):
        self.group=group; self.plugins={}
    def discover(self):
        eps=importlib.metadata.entry_points(); eps=eps.select(group=self.group) if hasattr(eps,'select') else eps.get(self.group,[])
        for ep in eps: self.plugins[ep.name]=ep.load()
        return dict(self.plugins)
    def register(self,name,plugin): self.plugins[name]=plugin
    def get(self,name): return self.plugins[name]


class AgentWeaveSDK:
    """Stable public facade; internal modules may evolve behind this boundary."""
    API_VERSION = '1'
    def __init__(self,weave): self.weave=weave
    async def register(self,agent): return self.weave.register(agent)
    async def solve(self,requirement,**kwargs): return await self.weave.solve(requirement,**kwargs)
    async def ingest(self,connector,**kwargs): return await self.weave.ingest_marketplace(connector,**kwargs)
    async def interop(self,targets,**kwargs): return await self.weave.test_interoperability(targets,**kwargs)
    def agents(self): return self.weave.registry.all()
    def graph_stats(self): return self.weave.knowledge_graph.stats()
    def observability(self): return self.weave.observability.snapshot()


def _version():
    try: return importlib.metadata.version('agentweave')
    except importlib.metadata.PackageNotFoundError: return '0+local'


def _doctor(weave):
    checks={
        'python':sys.version.split()[0],
        'platform':platform.platform(),
        'native_acceleration':weave.matcher.native_available,
        'docker':bool(shutil.which('docker')),
        'bubblewrap':bool(shutil.which('bwrap')),
        'llama_cpp':bool(shutil.which('llama-cli')),
    }
    try:
        import psycopg  # noqa: F401
        checks['postgres_driver']=True
    except Exception: checks['postgres_driver']=False
    try:
        import grpc  # noqa: F401
        checks['grpc']=True
    except Exception: checks['grpc']=False
    return checks


async def _run_cli(args):
    from .orchestrator import AgentWeave
    cfg=AgentWeaveConfig.load(args.config) if args.config else AgentWeaveConfig()
    if args.command=='version':
        print(_version()); return 0
    if args.command=='config-check':
        print(json.dumps(cfg.to_dict(),indent=2,default=str)); return 0
    weave=AgentWeave(db_path=cfg.db_path,use_native=cfg.use_native)
    weave.registry.load_persisted()
    if args.command=='agents':
        print(json.dumps([a.to_dict() for a in weave.registry.all()],indent=2,default=str)); return 0
    if args.command=='solve':
        print(json.dumps(await weave.solve(args.requirement,max_agents=cfg.max_agents,rounds=cfg.rounds,semantic_verify=args.semantic_verify),indent=2,default=str)); return 0
    if args.command=='doctor':
        print(json.dumps(_doctor(weave),indent=2)); return 0
    if args.command=='graph-stats':
        print(json.dumps(weave.knowledge_graph.stats(),indent=2)); return 0
    if args.command=='plugins':
        print(json.dumps(sorted(PluginManager().discover()),indent=2)); return 0
    return 1


def main(argv=None):
    parser=argparse.ArgumentParser(prog='agentweave'); parser.add_argument('--config')
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('agents')
    solve=sub.add_parser('solve'); solve.add_argument('requirement'); solve.add_argument('--semantic-verify',action='store_true')
    sub.add_parser('doctor'); sub.add_parser('graph-stats'); sub.add_parser('plugins'); sub.add_parser('version'); sub.add_parser('config-check')
    args=parser.parse_args(argv)
    import asyncio
    return asyncio.run(_run_cli(args))
