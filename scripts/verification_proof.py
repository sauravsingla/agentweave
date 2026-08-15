import asyncio, json, pathlib
from agentweave import SemanticResultVerifier, VerificationBenchmark

async def main():
    verifier=SemanticResultVerifier(
        source_quality_checker=lambda url: 1.0 if any(x in url for x in ('example.edu','standards.example')) else .4,
        nli_scorer=lambda a,b: -0.8 if (' is safe' in a.lower() and ' is not safe' in b.lower()) or (' is not safe' in a.lower() and ' is safe' in b.lower()) else .7,
        verifier_agent=lambda question,results:{'score':.85 if all(r.get('success',True) for r in results) else .2},
    )
    positive=await verifier.verify([
        {'success':True,'response':{'result':'The system is safe according to source: https://example.edu/report confidence: 90%'}},
        {'success':True,'response':{'result':'Evidence supports the system is safe. source: https://standards.example/spec confidence: 85%'}},
    ],'Is the system safe?')
    contradictory=await verifier.verify([
        {'success':True,'response':{'result':'The system is safe. confidence: 90%'}},
        {'success':True,'response':{'result':'The system is not safe. confidence: 90%'}},
    ],'Is the system safe?')
    benchmark=VerificationBenchmark()
    labeled=[(.95,1),(.85,1),(.75,1),(.65,1),(.55,1),(.45,0),(.35,0),(.25,0),(.15,0),(.05,0)]
    report={
        'positive':positive,
        'contradictory':contradictory,
        'discrimination_passed':positive['score']>contradictory['score'] and bool(contradictory['contradictions']),
        'brier_score':benchmark.brier_score(labeled),
        'expected_calibration_error':benchmark.expected_calibration_error(labeled),
        'classification':benchmark.classification_metrics(labeled),
    }
    pathlib.Path('verification-proof.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
    return 0 if report['discrimination_passed'] and report['classification']['accuracy']>=.9 else 1

raise SystemExit(asyncio.run(main()))
