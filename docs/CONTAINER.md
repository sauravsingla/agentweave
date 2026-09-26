# AgentWeave container image

AgentWeave publishes a base CLI image to GitHub Container Registry (GHCR):

```text
ghcr.io/sauravsingla/agentweave
```

## Pull the latest image

```bash
docker pull ghcr.io/sauravsingla/agentweave:latest
```

For reproducible use, prefer a release tag such as `v0.7.1` or `0.7.1` when that release has been published as a container image.

## Verify the installed version

```bash
docker run --rm ghcr.io/sauravsingla/agentweave:latest version
```

The image uses the `agentweave` CLI as its entry point, so any CLI subcommand can be supplied directly:

```bash
docker run --rm ghcr.io/sauravsingla/agentweave:latest plugins
docker run --rm ghcr.io/sauravsingla/agentweave:latest doctor
```

## Persist local runtime state

The image runs as an unprivileged user (`UID:GID 10001:10001`) with `/workspace` as its writable working directory. Mount a local directory when a command needs persistent files or a local AgentWeave database:

```bash
docker run --rm \
  -v "$PWD/agentweave-data:/workspace" \
  ghcr.io/sauravsingla/agentweave:latest agents
```

If the host directory is not writable by UID 10001, adjust its ownership or permissions before mounting it.

## Use a configuration file

Mount the configuration into `/workspace` and pass it to the CLI:

```bash
docker run --rm \
  -v "$PWD/agentweave.yaml:/workspace/agentweave.yaml:ro" \
  ghcr.io/sauravsingla/agentweave:latest \
  --config agentweave.yaml config-check
```

## Published tags

The GitHub Actions container workflow publishes:

- `latest` from container-relevant changes merged to `main`.
- `sha-<12-char-commit>` for every published build.
- `vX.Y.Z`, `X.Y.Z`, and `X.Y` for release tags matching `vX.Y.Z`.
- `manual-<12-char-commit>` for manually dispatched builds on refs other than `main` or a release tag.

Pull requests build and smoke-test the image but do not push packages.

## Image design

The repository `Dockerfile` uses a two-stage build. The build stage creates the Python wheel, while the runtime stage contains only the installed package and its runtime dependencies. The final image:

- is based on Python 3.11 slim;
- runs as a non-root user;
- carries OCI source, revision, version, documentation, and license labels;
- defaults to `agentweave version` when run without arguments;
- does not contain the repository test, benchmark, research, or documentation trees.

The base image contains the dependencies from the core `agentweave-router` package. Optional integration extras such as MCP, LangGraph, AutoGen, PostgreSQL, AWS, or observability dependencies are not installed in the base container image.
