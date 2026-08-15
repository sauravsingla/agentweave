# AgentWeave Research Methodology

## Goal

Measure whether requirement-aware multi-agent selection improves capability coverage and team quality relative to simpler routing baselines while reporting the operational trade-offs.

## Reproducibility

The benchmark uses fixed random seeds, a versioned requirement dataset (`benchmark_cases.json`), a fixed synthetic-agent population generator, deterministic routing logic, and machine-readable JSON/CSV output. The generated Markdown table and SVG are derived from the same raw rows.

## Population

The default research run creates 1,000 heterogeneous agents with 1–4 capabilities drawn from analysis, research, coding, summarization, planning, vision, retrieval and verification. Capability proficiency, validation state, contextual trust, execution location, latency and cost vary under a fixed seed.

## Methods

The suite evaluates:

- **AgentWeave** global team optimizer.
- **single-best** top-ranked single agent.
- **random** random team of the same size as AgentWeave's selected team.
- **trust-only** highest-trust agents.
- **capability-greedy** greedy uncovered-capability selection.
- **embedding-only** semantic capability similarity without trust/placement optimization.
- **ablation-no-trust** ranking with the trust contribution removed approximately from the composite score.
- **ablation-no-placement** ranking with placement contribution removed approximately.
- **native-greedy** when the C++ native module is available.

## Metrics

For every requirement/method pair the suite records capability coverage, mean match score, mean trust, maximum team latency, aggregate cost, team size, pairwise capability redundancy, execution-location diversity and a declared `quality_proxy`. The quality proxy is not a substitute for human task-quality evaluation; it is an explicitly defined combination of coverage, match score, trust and redundancy for controlled routing experiments.

## Statistical analysis

Paired bootstrap resampling reports the 95% interval for AgentWeave's delta relative to the single-best baseline. The random seed and raw per-case rows are included in the JSON artifact.

## Scalability methodology

The scale suite physically evaluates 10K, 100K and 1M synthetic agents in bounded-memory batches. Smaller runs are never relabeled as larger populations. It reports ranking wall time, throughput, peak process RSS, team-selection throughput, a bounded graph-ingestion sample and Python/native C++ comparison. The graph sample size is explicitly reported because retaining a million-agent NetworkX graph on a GitHub-hosted runner is a different memory experiment from streaming matcher throughput.

## Limitations

Synthetic routing benchmarks isolate selection behavior; they do not prove end-task factual correctness or marketplace/edge reliability. Live A2A, cloud-marketplace, PostgreSQL, sandbox and edge proofs are reported separately. Results can also vary by CPU architecture, runner contention and compiler version, so published artifacts should retain environment metadata.
