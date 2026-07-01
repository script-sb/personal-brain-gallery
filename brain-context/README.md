# brain-context

Context and workspace subsystem.

The v1 scaffold includes simple local text search:

```bash
python3 -m brain_core context search "permission" --path .
```

`claude-context` and `Mirage` are tracked as primary integration candidates.

## claude-context Adapter

claude-context MCP has been installed and built locally, but semantic indexing is not enabled by default.

Check readiness:

```bash
python3 -m brain_core context adapter-status
python3 -m brain_core context adapter-smoke-test
```

Generate a command:

```bash
python3 -m brain_core context adapter-command
python3 -m brain_core context adapter-command --provider Ollama --model nomic-embed-text --milvus-address localhost:19530
```

Policy:

- The default context search remains local text search.
- Semantic indexing requires explicit confirmation of the target path.
- claude-context requires an embedding provider plus Milvus before real indexing.
- Do not index private repositories until the provider and vector database settings are reviewed.
