# Workflow

The first end-to-end workflow is intentionally conservative. It creates a local artifact and memory record without executing browser, shell, desktop, or remote connector actions.

Run:

```bash
python3 -m brain_core workflow local-task "Summarize the current local brain state" --query "Local Brain"
```

Show a run:

```bash
python3 -m brain_core workflow show 1
```

What it does:

1. Reads recent memories from SQLite.
2. Searches local context.
3. Creates `workspace/runs/<id>/summary.md`.
4. Creates `workspace/runs/<id>/run.json`.
5. Writes a workflow recap memory.

Risk policy:

- No tool execution is performed.
- Generated commands are suggestions only.
- Use `--risky` to mark the run as confirmation-required.
