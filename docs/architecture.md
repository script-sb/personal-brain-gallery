# Local Brain Architecture

The local brain is a control plane, not a pile of cloned AI projects.

## Layers

1. Brain Core: task planning, run logs, permission gates, routing decisions.
2. Memory: durable memories, preferences, project facts, failures, reusable lessons.
3. Context: local file search, code search, virtual workspace adapters.
4. Tools: GitHub, shell, browser, DevTools, desktop automation, model calls.
5. Skills: small declarative wrappers with triggers, inputs, outputs, and permission levels.
6. Mirrors: GitHub source checkouts under `third_party/`, pinned and audited.

## Permission Policy

Default behavior is confirm-before-risk.

- Read registry, read local text, and search local context: automatic.
- Write files, run commands, clone/pull GitHub repos, use browser sessions, or control desktop UI: confirmation required.
- Desktop automation starts in observation-only mode.

## Integration Policy

Each GitHub project starts as `watch`, `mirror`, or `integrate`.

- `watch`: track repository and concepts.
- `mirror`: clone locally for source study.
- `integrate`: connect through wrapper, CLI, MCP, sidecar, or API.

Direct source modification of third-party projects is a later step, not the v1 default.

