import asyncio
from agentweave import AgentWeave, AgentProfile, Capability, TrustVector, ExecutionProfile, StaticMarketplace
from agentweave.a2a import InMemoryA2AAdapter

async def main():
    bus = InMemoryA2AAdapter()
    weave = AgentWeave(a2a=bus)

    agents = [
        AgentProfile("researcher","Research Agent",[Capability("research",.95),Capability("summarization",.88)],domains=["science"],trust=TrustVector(.95,.9,.9,.9,.85,.9)),
        AgentProfile("analyst","Analysis Agent",[Capability("analysis",.94),Capability("reasoning",.86)],domains=["general"],trust=TrustVector(.9,.9,.85,.92,.88,.9)),
        AgentProfile("edge-vision","Edge Vision Agent",[Capability("vision",.91),Capability("analysis",.8)],domains=["general"],trust=TrustVector(.88,.86,.8,.95,.82,.85),execution=ExecutionProfile(location="edge",latency_ms=70,offline=True,privacy_level="local-only")),
    ]

    print("Marketplace validation:", weave.ingest_marketplace(StaticMarketplace(agents)))
    bus.register_handler("researcher", lambda task: {"finding":"evidence collected","task":task})
    bus.register_handler("analyst", lambda task: {"finding":"analysis completed","task":task})
    bus.register_handler("edge-vision", lambda task: {"finding":"local visual analysis completed","task":task})

    print("\nGeneral task:")
    print(await weave.solve("Research evidence, analyze it, and summarize the findings"))
    print("\nLocal edge task:")
    print(await weave.solve("Analyze this image offline on-device", local_only=True))

if __name__ == "__main__":
    asyncio.run(main())
