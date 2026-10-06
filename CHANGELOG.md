# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] - 2026-10-07

### Added
- **Unified Contract**: Introduced normalized `Task` and `Result` data structures across all execution sources.
- **Source Adapters**:
  - `OmniRouteSource` — Support for OpenAI-compatible endpoints and OmniRoute model routing.
  - `LocalModelSource` — Support for locally hosted models via Ollama API.
- **Composite Execution Strategies**:
  - `FallbackSource` — Sequential failover routing across multiple configured sources.
  - `ParallelSource` — Concurrent source execution with first-success return.
  - `AggregateSource` — Concurrent multi-source execution with aggregated result combination.
  - `SequentialSource` — Multi-step chained workflows with template-based prompt propagation (`{input}` and `{previous}`).
  - `synthesize()` — Cross-model synthesis asking multiple sources in parallel and merging their outputs through a synthesizer model.
- **Observability**: Complete attempts trail tracking which sources succeeded or failed, latency, and model origins.
- **CLI Utilities**:
  - `qs-orchestrator analyze`: Run repository code review and analysis workflows with configurable strategies.
  - `qs-orchestrator check`: Probe source connectivity and verify end-to-end task execution without leaking secrets.
- **Project Infrastructure**: Added full GitHub community health files, security policy, CI workflows, and documentation.
