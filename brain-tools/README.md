# brain-tools

Tool subsystem for browser, terminal, GitHub, DevTools, and desktop capabilities.

Current slots:

- GitHub mirror planning/audit via `python3 -m brain_core github ...`
- Chrome DevTools MCP slot via `python3 -m brain_core devtools status`
- Desktop automation remains observation-only until a confirmed wrapper is added.

## Chrome DevTools MCP

The local mirror has been installed and built at:

```bash
third_party/chrome-devtools-mcp/build/src/bin/chrome-devtools-mcp.js
```

Check readiness:

```bash
python3 -m brain_core devtools status
```

Generate the recommended command:

```bash
python3 -m brain_core devtools command
```

Default recommended flags disable usage statistics, redact network headers, and use slim mode unless a richer debugging session is explicitly needed.
