# FREE-Forever
<img width="1408" height="768" alt="free" src="https://github.com/user-attachments/assets/58362fed-ee1b-4693-a31f-5f8861355c4a" />

**Turn free AI access into one local compute pool.**

Free-Forever is an experimental local orchestration layer for combining **browser-based AI access, free APIs, and local models** through one interface.

The goal is simple:

> **One interface. Any source. Multiple models.**

Free-Forever handles **what work should happen**.
[OmniRoute](https://github.com/diegomura/omniroute) handles **where model requests are routed**.

---

## What exists today

Free-Forever is currently **early-stage / experimental**.

The project is establishing the core architecture for:

* normalized AI sources
* local orchestration
* OmniRoute integration
* browser-based AI access
* local models
* free API sources
* execution results and observability

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

## Planned capabilities

### Fallback

```text
Model A → unavailable → Model B → result
```

### Parallel execution

```text
          TASK
       ┌───┼───┐
       ▼   ▼   ▼
       A   B   C
       └───┼───┘
           ▼
       AGGREGATION
```

### Sequential workflows

```text
Research → Analysis → Critique → Synthesis
```

### Cross-model synthesis

```text
Model A ─┐
Model B ─┼→ Synthesizer → Result
Model C ─┘
```

These are **target capabilities, not claims about the current implementation**.

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

## Roadmap

```text
1. Single source execution
2. Normalized source interface
3. OmniRoute integration
4. Fallback routing
5. Parallel execution
6. Result aggregation
7. Sequential workflows
8. Browser sources
9. Observability
10. Unified interface
```

---

## The goal

> **What if all the free AI access you already have could behave like one local AI system?**

That's what Free-Forever is building.

