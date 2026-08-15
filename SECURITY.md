# Security Policy

## Supported versions

Security fixes are applied to the latest minor release on the `main` branch. Older experimental releases may not receive backports.

## Reporting a vulnerability

Do not open a public issue for an unpatched vulnerability. Use GitHub's private security-advisory reporting flow for this repository when available, or contact the repository owner privately through the contact method listed on the GitHub profile.

Please include the affected version/commit, threat model, reproducible steps, impact, and any suggested mitigation. Avoid including real credentials, personal data, private keys or production secrets in reports.

## Security boundary

AgentWeave provides policy enforcement, validation and sandbox adapters, but a passing test suite is not a formal security certification. Production deployments should additionally use hardened container/VM runtimes, secret managers, network policy, signed images, workload identity, least-privilege cloud credentials and independent security review appropriate to the environment.

## Dependency and release hygiene

Release CI builds distributions from a clean checkout, runs the test suite before publication and uses trusted publishing for PyPI when configured. Security-sensitive optional integrations are isolated behind extras so deployments can minimize their dependency footprint.
