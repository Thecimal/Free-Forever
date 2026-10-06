# FREE-Forever
<img width="1408" height="768" alt="free" src="https://github.com/user-attachments/assets/58362fed-ee1b-4693-a31f-5f8861355c4a" />

**Turn free AI access into one local compute pool.**

Free-Forever is an experimental local orchestration layer for combining **browser-based AI access, free APIs, and local models** through one interface.

The goal is simple:

> **One interface. Any source. Multiple models.**

Free-Forever handles **what work should happen**.
[OmniRoute](https://github.com/diegosouzapw/OmniRoute) handles **where model requests are routed**.

---

## What exists today

Free-Forever is currently **early-stage / experimental**, but the core path works.

**Implemented**

* A normalized execution contract: a `Task` goes in and a `Result` comes out, whatever source handled it
* A `Source` interface with two sources:
  * `OmniRouteSource` — any OpenAI-compatible endpoint, such as OmniRoute
  * `LocalModelSource` — a local model served through the Ollama API
* Composite sources, which are themselves sources and can be nested:
  * `FallbackSource` — try sources in order until one succeeds
  * `ParallelSource` — start every source at once; the first success wins
  * `AggregateSource` — run every source and combine the answers
* An attempts trail on composite results: which sources were tried, what failed, and which one answered
* A `qs-orchestrator analyze` command that runs through OmniRoute, with optional extra models, an optional local model, and a choice of how they are combined

**Not implemented yet**

* Browser-based AI access built into Free-Forever (OmniRoute's web providers can be used as models, but this is untested here)
* Sequential workflows
* Cross-model synthesis (a model that merges other models' answers)

The implementation is still under active development.

---

## Target architecture

```text
             YOUR TASK
                 │
                 ▼
           FREE-FOREVER
                 │
                 ▼
           ORCHESTRATOR
                 │
       ┌─────────┼─────────┐
       ▼         ▼         ▼
    Browser     API       Local
     access    sources    models
       │         │         │
       └─────────┼─────────┘
                 ▼
             OMNIROUTE
                 │
                 ▼
          MODELS / PROVIDERS
                 │
                 ▼
              RESULT
```

Free-Forever should make different AI sources behave like one available pool of compute.

---

## Capabilities

### Fallback (implemented)

```text
Model A → fails → Model B → result
```

### Parallel execution (implemented)

```text
          TASK
       ┌───┼───┐
       ▼   ▼   ▼
       A   B   C
       └───┼───┘
           ▼
       AGGREGATION
```

`ParallelSource` returns the first success; `AggregateSource` waits for every source and combines the answers.

### Sequential workflows (planned)

```text
Research → Analysis → Critique → Synthesis
```

### Cross-model synthesis (planned)

```text
Model A ─┐
Model B ─┼→ Synthesizer → Result
Model C ─┘
```

Fallback, parallel execution and aggregation are implemented. Sequential workflows and cross-model synthesis are **target capabilities, not claims about the current implementation**.

---

## Sources

A source may eventually be:

* Browser-based AI
* Free API
* Local model
* Open-source model
* Web source
* GitHub repository
* Document
* URL
* Dataset
* Other compatible adapters

Sources should be isolated and replaceable so that removing one provider does not require redesigning the system.

---

## Design principles

**Local-first** — Keep configuration and orchestration under the user's control.

**Provider-agnostic** — No single AI provider should be a hard dependency.

**Composable** — Models and sources should be building blocks.

**Observable** — Show which source/model was used, what failed, and how the result was produced.

**Replaceable** — Providers can disappear without breaking the core architecture.

---

## Configuration

`qs-orchestrator analyze` reads its settings from the environment or a `.env` file (see `.env.example`):

| Variable | Meaning |
| --- | --- |
| `LLM_BASE_URL` | Base URL of the OpenAI-compatible endpoint, for example a local OmniRoute such as `http://localhost:20128/v1` |
| `LLM_API_KEY` | API key for that endpoint |
| `LLM_MODEL` | Model to request (required unless `LLM_MODELS` is set) |
| `LLM_MODELS` | Optional. Comma-separated models; each becomes its own source. Overrides `LLM_MODEL` |
| `LLM_STRATEGY` | Optional. How several sources are combined: `fallback` (default), `parallel` or `aggregate` |
| `LOCAL_MODEL` | Optional. A local model name; when set, it is added as one more source (the last resort under the default `fallback` strategy) |
| `LOCAL_BASE_URL` | Optional. Local model server (Ollama API); defaults to `http://localhost:11434` |
| `REPO_PATH` | Repository to analyze; defaults to the current directory |
| `GITHUB_REPOSITORY` | Repository name used in the prompt |
| `MAX_CONTEXT_CHARS` | Maximum repository context sent to the model; defaults to `50000` |

OmniRoute can also expose browser sessions (such as ChatGPT Web or Claude Web) as models. To use them, connect the provider in OmniRoute and list its model names in `LLM_MODELS`; `qs-orchestrator check` shows which source answered. This path has not been tested against a live OmniRoute yet.

```text
qs-orchestrator analyze            # run the analysis and save a report under reports/
qs-orchestrator analyze --dry-run  # print the prompt without calling a model
qs-orchestrator check              # send one small task and report availability, result and attempts
```

The report is written to `reports/analysis-<timestamp>.md`. A summary on stderr says which source answered and lists any earlier failed attempts. If every source fails, the command exits with the error and writes no report.

---

## Roadmap

```text
1. [x] Single source execution
2. [x] Normalized source interface
3. [x] OmniRoute integration
4. [x] Fallback routing
5. [x] Parallel execution
6. [x] Result aggregation
7. [ ] Sequential workflows
8. [ ] Browser sources
9. [x] Observability (attempts trail; no logging or metrics yet)
10. [ ] Unified interface (`analyze` runs through the Source layer; no general-purpose interface yet)
```

---

## The goal

> **What if all the free AI access you already have could behave like one local AI system?**

That's what Free-Forever is building.

