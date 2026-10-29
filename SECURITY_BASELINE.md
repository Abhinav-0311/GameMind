# GameMind: Security Baseline & Project Governance

This document establishes the security guidelines and project governance rules for all development, testing, and operations. These rules are binding on all developers, automated systems, and agentic AI coding assistants.

---

## Credential Isolation & Scope Rules

### 1. Repository & Workspace Boundaries
* **Rule:** Never inspect, read, search, or reuse credentials (including passwords, tokens, API keys, or certificates) from other repositories, projects, folders, applications, containers, or environment files outside the immediate scope of this project's workspace.
* **Scope:** No file system scans, directory listings, or searches are permitted outside of the current project directory (`<REPO_ROOT>/`).

### 2. Allowable Credential Sources
* **Rule:** Only use credentials explicitly provided through:
  * The current project's local `.env` file (e.g. `<REPO_ROOT>/.env`).
  * Process environment variables of the active shell context.
  * Direct, explicit user inputs.
* **Single Environment File Policy:**
  * Only one environment file is permitted:
    `<REPO_ROOT>/.env`
  * Duplicate `.env` files are prohibited because they create configuration drift.

### 3. Procedure for Missing Credentials
* **Rule:** If the credentials required to run services, databases, or test suites are unavailable, misconfigured, or expired, you must:
  * **Stop immediately.**
  * **Report the specific configuration issue.**
  * **Request explicit user action or input** to provide the needed credentials.

### 4. Prohibition of Credential Discovery
* **Rule:** Never attempt to discover database passwords or access keys by searching unrelated directories, system logs, or configuration stores of other projects.

### 5. Prohibition of Cross-Project Secret Reuse
* **Rule:** Never use secrets or connection strings found in other projects for testing, staging, or verification of the current application.

---

## Compliance & Enforcement
All code edits, environment configurations, and verification runs must strictly comply with these rules. Any automated test execution or database connection setup must fail gracefully and request user configuration if local environment variables are not supplied.

---

## Development & Repository Governance
* **Rule:** All future implementation, testing, documentation, and builds must occur inside `<REPO_ROOT>/` unless explicit approval is given.

