# brain-memory

Long-term memory subsystem.

The v1 implementation stores memories in `data/brain.sqlite` through:

```bash
python3 -m brain_core memory add "..." --tags preference,project
python3 -m brain_core memory search keyword
```

Agentmemory is tracked as the primary GitHub integration candidate.

## Agentmemory Adapter

Agentmemory has been installed and built locally, but it is not the default source of truth yet.

Check adapter readiness:

```bash
python3 -m brain_core memory adapter-status
```

Generate commands:

```bash
python3 -m brain_core memory adapter-command --mode server
python3 -m brain_core memory adapter-command --mode mcp
python3 -m brain_core memory adapter-command --mode status
```

Policy:

- SQLite remains the default memory store for v1.
- Agentmemory server/MCP startup is opt-in and confirm-required.
- Do not run `agentmemory connect ...` until we choose which host app should receive hooks/config changes.
