# syntax=docker/dockerfile:1

FROM python:3.11-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /src

RUN python -m pip install --upgrade pip build

COPY pyproject.toml README.md LICENSE ./
COPY agentweave ./agentweave
COPY agentweave_byom ./agentweave_byom
COPY agentweave_security ./agentweave_security

RUN python -m build --wheel --outdir /dist


FROM python:3.11-slim-bookworm AS runtime

ARG VERSION=dev
ARG VCS_REF=unknown

LABEL org.opencontainers.image.title="AgentWeave" \
      org.opencontainers.image.description="Pre-inference routing and secure execution for tool-rich LLM and multi-agent systems." \
      org.opencontainers.image.source="https://github.com/sauravsingla/agentweave" \
      org.opencontainers.image.url="https://github.com/sauravsingla/agentweave" \
      org.opencontainers.image.documentation="https://sauravsingla.github.io/agentweave/" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}"

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --from=builder /dist /tmp/dist
RUN python -m pip install --upgrade pip \
    && python -m pip install /tmp/dist/*.whl \
    && rm -rf /tmp/dist \
    && groupadd --gid 10001 agentweave \
    && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin agentweave \
    && mkdir -p /workspace \
    && chown agentweave:agentweave /workspace

WORKDIR /workspace
USER 10001:10001

ENTRYPOINT ["agentweave"]
CMD ["version"]
