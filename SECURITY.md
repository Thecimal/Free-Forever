# Security Policy

## Supported Versions

We provide security updates for the current active development branch and latest release series:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| main    | :white_check_mark: |
| < 0.1.0 | :x:                |

---

## Reporting a Vulnerability

If you discover a security vulnerability in **Free-Forever** (`qs-ai-orchestrator`), please report it privately. **Do not create a public GitHub issue or discussion.**

### How to Report

1. **GitHub Security Advisory (Preferred):**  
   Navigate to the repository's **Security** tab and click **"Report a vulnerability"** to submit a private draft advisory.
2. **Email:**  
   If you cannot use GitHub Advisories, email **behnoud.mhm@gmail.com** with the subject line `[SECURITY] Free-Forever Vulnerability Report`.

### What to Include in Your Report

To help us triage and resolve the issue quickly, please provide:

* A clear description of the vulnerability and its potential impact.
* Steps to reproduce or a minimal proof of concept (PoC).
* Affected versions, operating system, and Python version.
* Any potential mitigations or suggested fixes, if known.

### Response Timeline

* **Acknowledgment:** Within 48 hours of receipt.
* **Assessment & Triage:** Within 5 business days with a severity evaluation and mitigation plan.
* **Fix & Advisory Release:** A patched release will be published alongside a coordinated security advisory.

---

## Security Best Practices for Users & Integrators

When using Free-Forever with external and local AI providers:

1. **API Keys & Secrets:**
   * Never commit your `.env` file or API keys to version control. The repository's `.gitignore` excludes `.env*` by default.
   * `qs-orchestrator check` and the attempts trail are designed never to print credentials or API keys to terminal logs or reports.
2. **Local Model Endpoints:**
   * Ensure local endpoints (e.g., Ollama at `http://localhost:11434` or OmniRoute at `http://localhost:20128`) are bound to `localhost` or secured with authentication if exposed to a network.
3. **Repository Context & Prompts:**
   * When using `qs-orchestrator analyze`, be mindful of repository contents. Sensitive files (such as `.env` or credentials) should be kept outside analyzed paths or excluded.
4. **Third-Party Proxy / Providers:**
   * Verify third-party endpoints configured via `LLM_BASE_URL` to ensure prompts and analysis data are transmitted only to trusted providers.
