# A2A Compatibility

AgentWeave treats protocol compatibility as an explicit, tested contract rather than assuming that one SDK point release defines the whole A2A ecosystem.

## Current compatibility target

| Component | Current target | Evidence |
|---|---|---|
| A2A protocol | 1.x JSON-RPC interoperability | Official MUST-level TCK plus live external services |
| Python A2A SDK | `a2a-sdk==1.1.0` | Pinned in the `tck` extra for reproducible CI |
| Python SDK server | tested | Cross-SDK interoperability workflow |
| Go SDK server | tested | Cross-SDK interoperability workflow |
| JavaScript SDK server | tested | Cross-SDK interoperability workflow |
| Java SDK server | tested | Cross-SDK interoperability workflow |
| Independently hosted services | tested | Deep Research Archives and Delx external proof |
| gRPC lifecycle client | contract-tested | Generated-stub-compatible lifecycle proof; not claimed as official gRPC TCK conformance |
| HTTP+JSON lifecycle | implemented | Not claimed as official HTTP+JSON TCK conformance unless a dedicated proof is run |

## Version policy

The exact Python SDK version used by the TCK environment remains pinned so a passing proof is reproducible. AgentWeave protocol adapters should not depend on one provider-specific JSON shape when the protocol permits variation; external interoperability profiles may adapt method names, authentication bootstrap, headers, or payload envelopes while preserving the A2A lifecycle contract.

Before changing the pinned SDK version:

1. run the full CI suite;
2. run the official JSON-RPC MUST-level TCK;
3. run Python/Go/JavaScript/Java SDK interoperability;
4. run independently hosted external A2A proof where endpoints remain available;
5. record any wire-compatibility changes in `CHANGELOG.md`.

A successful contract test does not imply conformance for transports that were not exercised by the official TCK.
