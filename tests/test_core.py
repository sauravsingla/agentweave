import pytest
from agentweave import AgentWeave, AgentProfile, Capability, ExecutionProfile, StaticMarketplace
from agentweave.a2a import InMemoryA2AAdapter


def test_requirement_and_matching():
    weave=AgentWeave()
    a=AgentProfile("a","A",[Capability("research",.9),Capability("analysis",.8)])
    b=AgentProfile("b","B",[Capability("coding",.95)])
    weave.validator.validate(a); weave.validator.validate(b)
    weave.registry.register(a); weave.registry.register(b)
    req=weave.analyzer.analyze("research and analyze evidence")
    ranked=weave.matcher.rank(req,weave.registry.all())
    assert ranked[0].agent.agent_id=="a"
    assert ranked[0].score>ranked[1].score


def test_team_formation_covers_multiple_capabilities():
    weave=AgentWeave()
    agents=[AgentProfile("r","R",[Capability("research",.95)]),AgentProfile("a","A",[Capability("analysis",.95)])]
    for x in agents: weave.validator.validate(x); weave.registry.register(x)
    req=weave.analyzer.analyze("research and analyze evidence")
    team=weave.selector.select(req,weave.matcher.rank(req,weave.registry.all()))
    assert {m.agent.agent_id for m in team}=={"r","a"}


def test_local_only_selects_edge():
    weave=AgentWeave()
    cloud=AgentProfile("cloud","Cloud",[Capability("vision",.99)])
    edge=AgentProfile("edge","Edge",[Capability("vision",.8)],execution=ExecutionProfile(location="edge",offline=True))
    for x in (cloud,edge): weave.validator.validate(x); weave.registry.register(x)
    req=weave.analyzer.analyze("analyze image offline",local_only=True)
    ranked=weave.matcher.rank(req,weave.registry.all())
    assert ranked[0].agent.agent_id=="edge"


@pytest.mark.asyncio
async def test_end_to_end_and_reputation_update():
    bus=InMemoryA2AAdapter(); weave=AgentWeave(a2a=bus)
    agent=AgentProfile("researcher","Researcher",[Capability("research",.95)])
    weave.ingest_marketplace(StaticMarketplace([agent]))
    bus.register_handler("researcher",lambda task:{"answer":"ok"})
    result=await weave.solve("research evidence")
    assert result["status"]=="completed"
    assert result["selected_agents"]==["researcher"]
    assert agent.tasks_completed==1
    assert agent.tasks_succeeded==1
