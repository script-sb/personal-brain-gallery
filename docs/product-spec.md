# GitHub-First Local Brain Product Spec

Last updated: 2026-05-26

## 1. Product Positioning

GitHub-First Local Brain is a local-first personal work brain. It is not a chat UI, not a one-click installer, and not a pile of AI repos. It is a control plane that uses GitHub projects as capability sources, then turns selected projects into safe local modules for memory, context, browser debugging, file/workspace access, and task execution.

The product goal is:

- remember personal/project context across sessions;
- inspect local files, code, browser state, and GitHub-sourced tools;
- plan before action;
- ask confirmation before risky operations;
- record what happened so future runs get smarter.

## 2. Target User

Primary user:

- an individual builder using a Mac as the main work machine;
- wants a local intelligent agent that can help with coding, research, file organization, browser debugging, and long-running personal workflows;
- prefers GitHub/open-source components but wants a coherent local architecture instead of fragmented installs.

Secondary future user:

- small team or studio wanting a shared local-agent framework with auditable integrations.

## 3. Product Principles

- Local-first: local memory and local context are the default.
- GitHub-first: open-source projects are discovered, mirrored, audited, and wrapped before integration.
- Confirm-before-risk: write operations, commands, browser sessions, desktop actions, credentials, and host config mutations require explicit confirmation.
- Wrapper-first: third-party projects are used through CLI, MCP, API, or sidecar wrappers before source modification.
- Auditable: every external project has status, commit, risk notes, and promotion criteria.
- Incremental: each module should be useful alone before it becomes part of an autonomous loop.

## 4. Current Product State

Implemented:

- Local CLI entrypoint: `python3 -m brain_core`.
- Project registry: `registry/projects.json`.
- Priority matrix: `registry/priority-matrix.md`.
- Mirror audit: `registry/mirror-audit.md`.
- Local SQLite memory store.
- Local context text search.
- Task planning/run-log scaffold.
- GitHub mirror plan and audit commands.
- Chrome DevTools MCP built and exposed through command generation.
- Agentmemory built and exposed as an opt-in memory adapter.
- DevTools smoke-test command.
- Memory JSON export/import.
- claude-context MCP build and adapter smoke-test.
- local-only workspace facade inspired by Mirage.
- first end-to-end local workflow artifact generation.
- run-log viewer for SQLite runs and workspace artifacts.
- educational index fund module for profiles, templates, scoring, and rebalancing.

Current commands:

```bash
python3 -m brain_core status
python3 -m brain_core registry list
python3 -m brain_core registry matrix
python3 -m brain_core github audit
python3 -m brain_core memory add "..." --tags ...
python3 -m brain_core memory search ...
python3 -m brain_core memory adapter-status
python3 -m brain_core memory export-json --output data/memories.backup.json
python3 -m brain_core memory import-json data/memories.backup.json
python3 -m brain_core devtools status
python3 -m brain_core devtools command
python3 -m brain_core devtools smoke-test
python3 -m brain_core context adapter-status
python3 -m brain_core context adapter-smoke-test
python3 -m brain_core workspace status
python3 -m brain_core workspace smoke-test
python3 -m brain_core workflow local-task "Summarize the current local brain state"
python3 -m brain_core runs list
python3 -m brain_core runs show 1
python3 -m brain_core funds profile --years 10 --risk 3
```

Current integrated mirrors:

| Project | Status | Product Role |
| --- | --- | --- |
| Chrome DevTools MCP | built, command-ready | Browser debugging tool |
| Agentmemory | built, adapter-ready | Optional external memory engine |
| claude-context | built, adapter-ready | Future code context/indexing |
| Mirage | mirrored, local facade ready | Future virtual workspace |

## 5. Product Architecture

The product has six layers:

| Layer | Purpose | Current State |
| --- | --- | --- |
| Brain Core | task state, registry, permission policy, run logs | v1 scaffold |
| Memory | durable personal/project memory | SQLite live, Agentmemory adapter ready |
| Context | local search and future semantic code search | text search live, claude-context adapter ready |
| Tools | browser, GitHub, shell, desktop, DevTools | GitHub/devtools partial |
| Funds | index fund education, allocation templates, scoring | profile/template/score/rebalance live |
| Skills | reusable task capabilities | initial skill manifests |
| Mirrors | audited GitHub source checkouts | first integrate batch mirrored |

## 6. Near-Term Roadmap

### Milestone 1: Make Browser Debugging Real

Goal: turn Chrome DevTools MCP from command-ready into a verified workflow.

Deliverables:

- Add a `devtools smoke-test` command that checks whether an MCP command can start. Done.
- Add docs for connecting to Chrome at `http://127.0.0.1:9222`.
- Add a browser-debug run template: collect console/network/page summary, then produce a diagnosis.

Acceptance criteria:

- `python3 -m brain_core devtools command --browser-url http://127.0.0.1:9222` emits a valid command.
- The user can follow one doc to connect Chrome and run a manual MCP session.
- Risk flags mention browser-session access and network-header redaction.

### Milestone 2: Memory Facade v2

Goal: keep SQLite as source of truth while allowing Agentmemory to be tested safely.

Deliverables:

- Add `memory export-json` and `memory import-json`. Done.
- Add adapter health check that runs `agentmemory status` without mutating host config.
- Add explicit product rule: no `agentmemory connect ...` unless requested.

Acceptance criteria:

- A memory can be written, exported, deleted from SQLite, and restored.
- Agentmemory command readiness is visible without starting a persistent service.
- Audit warnings remain visible in docs.

### Milestone 3: Code Context Wrapper

Goal: promote `claude-context` from mirror to read-only local code context candidate.

Deliverables:

- Inspect dependency setup and build requirements. Done.
- Add `context adapter-status` and `context adapter-command`. Done.
- Add `context adapter-smoke-test`. Done.
- Prototype indexing against this workspace only.

Acceptance criteria:

- Existing `context search` keeps working.
- Adapter status shows whether `claude-context` is built.
- No repository indexing happens without explicit path confirmation.

### Milestone 4: Local Workspace Prototype

Goal: test `Mirage` as a virtual workspace only with local RAM/Disk resources.

Deliverables:

- Add `workspace status`. Done.
- Add a local-only workspace prototype doc. Done.
- Avoid Gmail, Slack, S3, GitHub credentials in v1.

Acceptance criteria:

- Local workspace command can be generated.
- Remote connector setup is documented as future, not enabled by default.

### Milestone 5: First End-To-End Brain Loop

Goal: complete one useful personal workflow.

Candidate workflow:

1. User gives a local coding/debugging task.
2. Brain retrieves memory.
3. Brain searches local context.
4. Brain prepares plan.
5. User confirms browser/debug action.
6. Brain uses DevTools or generated command.
7. Brain records result and memory.

Acceptance criteria:

- One run is recorded in SQLite. Done.
- Risky action has a confirmation point.
- Final output includes what was learned for future tasks. Done.

## 7. Backlog

High priority:

- `devtools smoke-test`
- `memory export-json`
- `memory import-json`
- `context adapter-status`
- registry update command for mirror commits
- run-log viewer command. Done.

Medium priority:

- skill manifest validator
- project promotion checklist command
- weekly GitHub review report
- local model routing config
- web UI or TUI dashboard
- optional fund watchlist with manually entered tickers/expense ratios

Later:

- desktop observation mode with UI-TARS-desktop
- Open WebUI/Khoj/AnythingLLM comparison report
- GitHub issue/release monitoring automation
- team/shared memory mode

## 8. Risk Register

| Risk | Impact | Current Handling |
| --- | --- | --- |
| Third-party vulnerabilities | unsafe runtime exposure | keep adapters opt-in; record npm audit findings |
| Host config mutation | breaks Codex/Claude/Cursor setup | no `connect` command without explicit request |
| Browser data exposure | sensitive cookies/headers leak | redacted headers, scoped sessions, confirmation |
| Dependency drift | upstream updates break wrappers | mirror commits tracked in audit |
| Over-automation | accidental file/desktop changes | confirm-before-risk policy |
| Unclear canonical repos | wrong project integrated | watch status until verified |

## 9. Release Plan

### v0.1 Current

Local CLI, registry, mirror audit, SQLite memory, DevTools command generation, Agentmemory adapter command generation.

### v0.2 Proposed

DevTools smoke test, memory export/import, Agentmemory health probe, updated docs.

### v0.3 Proposed

claude-context adapter status and read-only code indexing prototype.

### v0.4 Proposed

Mirage local workspace prototype.

### v0.5 Proposed

First end-to-end local brain workflow with run logs and memory update.

## 10. Update Process

When a new integration step happens:

1. Update `registry/projects.json` if project status changes.
2. Update `registry/mirror-audit.md` with commit, build, audit, and readiness.
3. Update this product spec roadmap if priorities change.
4. Add or update tests for CLI-visible behavior.
5. Run `python3 -m unittest discover -s tests`.
