# Mirror Audit

Generated after the first integration mirror run on 2026-05-26.

## Integrated Mirrors

| Project | Path | Commit | Size | Runtime Notes |
| --- | --- | --- | --- | --- |
| claude-context | `third_party/claude-context` | `56b3751` | 36M | Node >=20, pnpm >=10, MIT. Best first use: MCP/code-context wrapper. |
| Agentmemory | `third_party/agentmemory` | `bfb5e66` | 58M | Node >=20, Apache-2.0. Best first use: CLI/library memory wrapper. |
| Chrome DevTools MCP | `third_party/chrome-devtools-mcp` | `57f32b0` | 24M | Node >=20.19 or compatible, Apache-2.0. Best first use: MCP server slot. |
| Mirage | `third_party/mirage` | `5622225` | 58M | Python >=3.12 and/or Node >=20. Best first use: virtual workspace prototype. |

## Next Integration Order

1. Agentmemory: add a wrapper behind the existing SQLite memory facade.
2. claude-context: add code-index/search wrapper after dependency check.
3. Mirage: prototype a local-only RAM/Disk workspace before adding remote connectors.

## Tool Readiness

| Project | Readiness |
| --- | --- |
| Chrome DevTools MCP | Dependencies installed, build completed, command generated through `python3 -m brain_core devtools command`. |
| Agentmemory | Dependencies installed with legacy peer resolution, build completed, command generated through `python3 -m brain_core memory adapter-command`. |
| claude-context | Dependencies installed with temporary pnpm via `npm exec pnpm@10`, MCP build completed, command generated through `python3 -m brain_core context adapter-command`. |
| Mirage | Mirror present; local-only workspace facade implemented in `brain_core workspace`. Mirage SDK dependency install deferred. |

## Dependency Audit

Chrome DevTools MCP `npm audit --audit-level=moderate` currently reports:

| Package | Severity | Advisory | Handling |
| --- | --- | --- | --- |
| `qs` | moderate | GHSA-q8mj-m7cp-5q26 | Do not auto-fix third-party lockfile; track before production use. |
| `ws` | moderate | GHSA-58qx-3vcg-4xpx | Do not auto-fix third-party lockfile; track before production use. |

This local brain should use the DevTools MCP with scoped browser sessions, redacted network headers, and explicit user confirmation.

Agentmemory `npm audit --audit-level=moderate` currently reports:

| Package Chain | Severity | Advisory Summary | Handling |
| --- | --- | --- | --- |
| `@xenova/transformers` -> `onnxruntime-web` -> `onnx-proto` -> `protobufjs` | critical/high | Multiple `protobufjs` advisories including code execution, prototype/code injection, and DoS. | Do not auto-fix with `--force`; it would install a breaking transformer version. Keep adapter opt-in and avoid production exposure until reviewed. |

Agentmemory required `npm install --legacy-peer-deps` because upstream currently combines `typescript@6.0.3` with `tsdown@0.20.3`, whose peer range prefers TypeScript 5.

claude-context `pnpm audit --audit-level moderate` currently reports 90 vulnerabilities:

| Severity | Count | Handling |
| --- | ---: | --- |
| critical | 5 | Keep adapter opt-in; do not run semantic indexing against private code until dependencies are reviewed. |
| high | 41 | Track upstream; avoid default service exposure. |
| moderate | 35 | Track upstream; wrapper remains command-generation only. |
| low | 9 | Track upstream. |

Notable vulnerable package paths include `protobufjs` through `@zilliz/milvus2-sdk-node`, `form-data` through OpenAI/LangChain dependencies, `ws` through Google GenAI, and extension-only dependencies through the Chrome/VS Code packages. pnpm also ignored native build scripts until explicitly approved; the MCP package still builds and smoke-tests, but real indexing remains a separate opt-in step.

## Safety Notes

- No dependency install was run during mirroring.
- No third-party project code was modified.
- `third_party/` is intentionally ignored by Git.
- Browser sessions, shell commands, and remote connectors remain confirm-required.
