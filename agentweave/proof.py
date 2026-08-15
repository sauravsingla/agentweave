from __future__ import annotations
import json, os, pathlib, time
from dataclasses import dataclass, asdict
from typing import Any
from .marketplaces import AWSBedrockAgentConnector, MicrosoftFoundryAgentConnector, GoogleCloudMarketplaceA2AConnector
from .edge import OllamaRuntime, LlamaCppRuntime
from .edge_lab import EdgeRuntimeTest
from .models import AgentProfile, Capability, ExecutionProfile
from .storage import PostgresReputationStore

@dataclass
class ProofResult:
    name: str
    passed: bool
    detail: dict[str,Any]

class MarketplaceDeploymentProof:
    """Runs live marketplace discovery when the corresponding credentials/config exist."""
    async def run(self):
        results=[]
        if os.getenv('AWS_REGION'):
            try:
                agents=await AWSBedrockAgentConnector(region_name=os.getenv('AWS_REGION')).list_agents()
                results.append(ProofResult('aws-bedrock',True,{'agents':len(agents)}))
            except Exception as exc: results.append(ProofResult('aws-bedrock',False,{'error':str(exc)}))
        if os.getenv('AZURE_FOUNDRY_ENDPOINT') and os.getenv('AZURE_FOUNDRY_TOKEN') and os.getenv('AZURE_FOUNDRY_API_VERSION'):
            try:
                agents=await MicrosoftFoundryAgentConnector(os.environ['AZURE_FOUNDRY_ENDPOINT'],os.environ['AZURE_FOUNDRY_TOKEN'],os.environ['AZURE_FOUNDRY_API_VERSION']).list_agents()
                results.append(ProofResult('microsoft-foundry',True,{'agents':len(agents)}))
            except Exception as exc: results.append(ProofResult('microsoft-foundry',False,{'error':str(exc)}))
        urls=[x.strip() for x in os.getenv('GOOGLE_A2A_AGENT_CARDS','').split(',') if x.strip()]
        if urls:
            try:
                agents=await GoogleCloudMarketplaceA2AConnector(urls).list_agents()
                results.append(ProofResult('google-cloud-marketplace',len(agents)==len(urls),{'agents':len(agents),'requested':len(urls)}))
            except Exception as exc: results.append(ProofResult('google-cloud-marketplace',False,{'error':str(exc)}))
        return results

class EdgeDeploymentProof:
    """Executes a real configured Ollama or llama.cpp runtime and captures hardware telemetry."""
    async def run(self):
        runtime_name=os.getenv('AGENTWEAVE_EDGE_RUNTIME','').lower()
        if not runtime_name: return ProofResult('edge-runtime',False,{'skipped':'AGENTWEAVE_EDGE_RUNTIME not configured'})
        agent=AgentProfile('edge-proof','Edge Proof',[Capability('reasoning',.5,True)],execution=ExecutionProfile(location='edge',runtime=runtime_name))
        if runtime_name=='ollama':
            agent.metadata['model']=os.getenv('OLLAMA_MODEL','llama3.2:1b')
            runtime=OllamaRuntime(base_url=os.getenv('OLLAMA_URL','http://127.0.0.1:11434'))
        elif runtime_name=='llama.cpp':
            model=os.getenv('LLAMA_CPP_MODEL')
            if not model: return ProofResult('edge-runtime',False,{'error':'LLAMA_CPP_MODEL not configured'})
            agent.metadata['model_path']=model; agent.metadata['max_tokens']=int(os.getenv('LLAMA_CPP_MAX_TOKENS','64'))
            runtime=LlamaCppRuntime(binary=os.getenv('LLAMA_CPP_BINARY','llama-cli'))
        else: return ProofResult('edge-runtime',False,{'error':f'unsupported runtime {runtime_name}'})
        report=await EdgeRuntimeTest().run(runtime,agent,iterations=int(os.getenv('EDGE_PROOF_ITERATIONS','3')))
        return ProofResult('edge-runtime',report['success_rate']==1.0,report)

class PostgresDeploymentProof:
    def run(self,dsn=None):
        dsn=dsn or os.getenv('AGENTWEAVE_POSTGRES_DSN')
        if not dsn: return ProofResult('postgres',False,{'skipped':'AGENTWEAVE_POSTGRES_DSN not configured'})
        store=PostgresReputationStore(dsn); marker=str(time.time_ns())
        a=AgentProfile('postgres-proof-'+marker,'Postgres Proof',[Capability('analysis',.9,True)])
        store.save_agent(a); store.record_outcome(a.agent_id,True,.95,{'proof':'live'})
        loaded={x.agent_id for x in store.load_agents()}; outcomes=store.recent_outcomes(a.agent_id,5)
        passed=a.agent_id in loaded and bool(outcomes) and bool(outcomes[0]['success'])
        return ProofResult('postgres',passed,{'agent_roundtrip':a.agent_id in loaded,'outcomes':len(outcomes)})

async def run_all_proofs(output='proof-results.json'):
    marketplace=await MarketplaceDeploymentProof().run(); edge=await EdgeDeploymentProof().run(); postgres=PostgresDeploymentProof().run()
    rows=[*marketplace,edge,postgres]; pathlib.Path(output).write_text(json.dumps([asdict(x) for x in rows],indent=2,default=str)); return rows
