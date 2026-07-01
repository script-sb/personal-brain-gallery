# Workspace Facade

The workspace facade is a local-only prototype inspired by Mirage. It gives the local brain a controlled file surface before enabling any remote connector.

Commands:

```bash
python3 -m brain_core workspace status
python3 -m brain_core workspace smoke-test
python3 -m brain_core workspace write notes/hello.txt "hello local brain"
python3 -m brain_core workspace read notes/hello.txt
python3 -m brain_core workspace list --path /
python3 -m brain_core workspace command
```

Policy:

- Writes are limited to `workspace/`.
- Path traversal outside `workspace/` is rejected.
- No Gmail, Slack, S3, GitHub, or credentialed connectors are enabled.
- Mirage remains the target SDK for a future richer workspace, after dependency and security review.
