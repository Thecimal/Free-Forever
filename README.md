# FREE-Forever
<img width="1408" height="768" alt="free" src="https://github.com/user-attachments/assets/58362fed-ee1b-4693-a31f-5f8861355c4a" />

**Turn free AI access into one local compute pool.**

Free-Forever orchestrates AI access from **browser sessions, free APIs, and local models** through a single interface.

It can distribute a task across multiple available models, route requests through [OmniRoute](https://github.com/diegomura/omniroute), and combine the results into one response.

> **One interface. Any source. Multiple models.**

---

## What it does

Free-Forever sits above individual AI providers.

Instead of building your workflow around one API or one model:

```text
                         YOUR TASK
                            │
                            ▼
                     FREE-FOREVER
                            │
             ┌──────────────┼──────────────┐
             │              │              │
          Browser          API           Local
           access         access         models
             │              │              │
             └──────────────┼──────────────┘
                            ▼
                       OMNIROUTE
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
           Model A        Model B       Model C
              │             │             │
              └─────────────┼─────────────┘
                            ▼
                      ORCHESTRATION
                            │
                            ▼
                         RESULT
```

The goal is not another AI provider.

The goal is to make **available AI capacity composable**.

---

## Why

Free access to AI is fragmented.

You may have:

* a free browser account
* another provider with a free API tier
* multiple accounts
* local models
* temporary provider quotas
* different models with different strengths

Each source normally requires its own interface and workflow.

Free-Forever treats them as **one pool of available intelligence**.

```text
Provider ≠ Product

Provider → available compute
Free-Forever → orchestration
OmniRoute → routing
Your task → the thing being solved
```

---

## Any source

The abstraction is intentionally broader than "AI providers."

A source can be:

* Browser-based AI
* Free API
* Local model
* Open-source model
* Web source
* GitHub repository
* Document
* URL
* Dataset
* Other compatible source adapters

The system normalizes the input, decides how the work should be executed, and sends it to the available AI capacity.

---

## Orchestration

A task does not have to go to one model.

Free-Forever can eventually support patterns such as:

### Parallel

```text
             TASK
               │
       ┌───────┼───────┐
       ▼       ▼       ▼
    Model A Model B Model C
       │       │       │
       └───────┼───────┘
               ▼
          AGGREGATION
```

### Fallback

```text
Model A
   │
   ├── unavailable
   ▼
Model B
   │
   ├── unavailable
   ▼
Model C
```

### Sequential

```text
Research
   ↓
Analysis
   ↓
Critique
   ↓
Synthesis
```

### Cross-model synthesis

```text
       ┌── Model A ──┐
       │             │
TASK ──┼── Model B ──┼──→ Synthesizer
       │             │
       └── Model C ──┘
```

The orchestrator decides which pattern makes sense for the task and available capacity.

---

## Browser access

One of the project's important directions is making **browser-based free AI access usable as part of an automated workflow**.

Many AI services provide useful free access through their web interfaces without offering the same access through a conventional API.

Free-Forever aims to make those sources usable alongside APIs and local models.

Browser integrations should remain:

* isolated
* replaceable
* explicitly configured
* rate-limit aware
* compliant with the provider's terms

The browser is an **access mechanism**, not the architecture.

---

## OmniRoute

Free-Forever is not intended to replace a model gateway.

[OmniRoute](https://github.com/diegomura/omniroute) provides the routing layer between the orchestration system and supported model providers.

The separation is deliberate:

```text
FREE-FOREVER
    │
    │  What should happen?
    │
    ▼
ORCHESTRATOR
    │
    │  Where should this request go?
    │
    ▼
OMNIROUTE
    │
    │  Which provider/model is available?
    │
    ▼
AI PROVIDERS
```

**Free-Forever = orchestration**

**OmniRoute = model routing**

This keeps the project focused.

---

## Design principles

### Local-first

Configuration and orchestration should remain under the user's control.

### Provider-agnostic

No single AI provider should become a hard dependency.

### Replaceable adapters

A provider disappearing should mean replacing an adapter, not redesigning the system.

### Composable

Individual models and sources should be building blocks rather than isolated destinations.

### Observable

The system should make it possible to understand:

* which source was used
* which model responded
* how long it took
* whether it failed
* why fallback happened
* how the final result was produced

### No artificial lock-in

Free-Forever should work with whatever combination of sources the user actually has available.

---

## Status

**Early-stage / experimental.**

The architecture is being developed around a simple question:

> **What if all the free AI access you already have could behave like one local AI system?**

---

## License

Open source.
