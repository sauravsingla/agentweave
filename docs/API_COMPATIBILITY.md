# API Compatibility Policy

AgentWeave uses Semantic Versioning for the Python package.

## Stable surface

The primary supported surface is the set of classes exported from `agentweave.__init__` plus `AgentWeaveSDK`. Additive methods and optional parameters may be introduced in minor releases. Backward-incompatible changes to that stable surface require a major version change unless the existing behavior is demonstrably unsafe.

`AgentWeaveSDK.API_VERSION` identifies the high-level SDK contract independently from the package release number.

## Experimental surface

Implementation-detail modules, internal helper functions, CI scripts and generated benchmark artifacts may evolve in minor releases. Experimental APIs should not be relied upon without pinning a package version.

## Deprecation

Where practical, public APIs are deprecated for at least one minor release before removal. Deprecation notices should name the replacement and target removal release.

## Protocol compatibility

A2A behavior is versioned independently from AgentWeave. Protocol clients should advertise/accept the A2A version appropriate to the remote Agent Card and validate conformance with the official A2A TCK where possible.
