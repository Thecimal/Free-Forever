# Contributing to Free-Forever

Thank you for your interest in contributing to **Free-Forever**! We welcome community contributions of all kinds: bug reports, documentation improvements, architectural feedback, and pull requests.

Please take a moment to review this document to ensure a smooth collaboration process.

---

## Code of Conduct

By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md). Please treat all contributors with respect and kindness.

---

## How Can I Contribute?

### 1. Reporting Bugs

Before creating an issue, please search existing GitHub issues to verify that the bug hasn't already been reported.

When submitting a bug report:
* Use the **Bug Report** issue template.
* Provide clear, step-by-step reproduction instructions.
* Include relevant environment details (OS, Python version, OmniRoute/Ollama version if applicable).
* Strip all API keys, authorization tokens, or sensitive context from logs and terminal outputs.

### 2. Proposing Features & Improvements

Have an idea for a new source adapter, execution strategy, or CLI improvement?
* Open an issue using the **Feature Request** template.
* Describe the problem it solves and proposed API/architecture.
* Keep in mind the project design principles: **Local-first**, **Provider-agnostic**, **Composable**, **Observable**, and **Replaceable**.

### 3. Improving Documentation

Documentation, diagrams, and code comments are always welcome! Feel free to submit a pull request directly for typos, clarifications, or missing setup instructions.

---

## Development Setup

### Prerequisites

* Python **3.10** or higher
* `git`
* (Optional) [OmniRoute](https://github.com/diegosouzapw/OmniRoute) or [Ollama](https://ollama.com/) for running live endpoint tests

### Step-by-Step Setup

1. **Fork and clone the repository:**
   ```bash
   git clone https://github.com/Thecimal/Free-Forever.git
   cd Free-Forever
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install the package in editable mode with development dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -e ".[dev]"
   ```

4. **Verify the installation:**
   ```bash
   pytest
   ruff check .
   ```

---

## Development Guidelines

### Architecture & Design Principles

* **Normalized Contract:** Every execution flow consumes a `Task` and produces a `Result`.
* **Composability:** New composite sources should implement the `Source` interface so they can be nested seamlessly with `FallbackSource`, `ParallelSource`, `AggregateSource`, and `SequentialSource`.
* **Observability:** Maintain the attempts trail on composite results. Callers should always know which sources were tried, what failed, and which source produced the answer.
* **Security & Privacy:** Never log or leak `LLM_API_KEY` or credentials in terminal output, attempts trails, or error strings.

### Code Style & Linting

We use [Ruff](https://astral.sh/ruff) for linting and code formatting:

```bash
# Check for lint issues
ruff check .

# Automatically apply safe fixes
ruff check --fix .

# Check formatting
ruff format --check .
```

### Running Tests

All new functionality or bug fixes must include unit tests:

```bash
# Run the complete test suite
pytest

# Run tests with verbose output
pytest -v

# Run a specific test module
pytest tests/test_synthesis.py
```

---

## Pull Request Workflow

1. **Create a branch:**
   ```bash
   git checkout -b feat/your-feature-name
   # or
   git checkout -b fix/your-bugfix-name
   ```
2. **Make your changes:**
   * Keep commits focused and logically grouped.
   * Write descriptive commit messages.
3. **Run tests and linters:**
   Ensure all checks pass before pushing:
   ```bash
   ruff check .
   pytest
   ```
4. **Push to your fork:**
   ```bash
   git push origin feat/your-feature-name
   ```
5. **Open a Pull Request:**
   * Target the `main` branch.
   * Fill out the Pull Request template completely.
   * Link any related issues (e.g., `Closes #12`).
