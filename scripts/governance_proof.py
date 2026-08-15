import json, pathlib
from agentweave import AgentProfile, Capability, ExecutionProfile, GovernancePolicyEngine, PolicyContext

engine=GovernancePolicyEngine(allowed_jurisdictions={'EU','IN'},allowed_residencies={'EU','IN'},blocked_tools={'shell'},human_approval_tiers={'high','critical'})
Req=type('Req',(),{'local_only':False})
agent=AgentProfile('policy-agent','Policy Agent',[Capability('analysis')],execution=ExecutionProfile(location='cloud'),metadata={'tools':['retrieval']})
scenarios=[
    ('allowed-standard',PolicyContext(jurisdiction='IN',data_residency='IN',risk_tier='standard',allowed_tools={'retrieval'}),True),
    ('jurisdiction-denied',PolicyContext(jurisdiction='US',data_residency='IN',allowed_tools={'retrieval'}),False),
    ('residency-denied',PolicyContext(jurisdiction='IN',data_residency='US',allowed_tools={'retrieval'}),False),
    ('tool-denied',PolicyContext(jurisdiction='IN',data_residency='IN',allowed_tools={'other'}),False),
    ('human-approval-required',PolicyContext(jurisdiction='IN',data_residency='IN',risk_tier='critical',allowed_tools={'retrieval'},human_approved=False),False),
    ('human-approved',PolicyContext(jurisdiction='IN',data_residency='IN',risk_tier='critical',allowed_tools={'retrieval'},human_approved=True),True),
]
rows=[]
for name,context,expected in scenarios:
    decision=engine.evaluate(agent,Req(),context)
    rows.append({'name':name,'expected_allowed':expected,'allowed':decision.allowed,'passed':decision.allowed==expected,'reasons':decision.reasons,'requires_human':decision.requires_human})
local_agent=AgentProfile('remote','Remote',[Capability('analysis')],execution=ExecutionProfile(location='cloud'))
local_decision=engine.evaluate(local_agent,type('Req',(),{'local_only':True})(),PolicyContext(jurisdiction='IN',data_residency='IN'))
rows.append({'name':'locality-denied','expected_allowed':False,'allowed':local_decision.allowed,'passed':not local_decision.allowed,'reasons':local_decision.reasons,'requires_human':local_decision.requires_human})
pathlib.Path('governance-proof.json').write_text(json.dumps(rows,indent=2))
print(json.dumps(rows,indent=2))
raise SystemExit(0 if all(x['passed'] for x in rows) else 1)
