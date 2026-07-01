# GitHub-First Playbook

## Weekly Review

1. Run `python3 -m brain_core registry matrix`.
2. Run `python3 -m brain_core github audit`.
3. Review upstream releases/issues for `integrate` projects.
4. Decide: keep, upgrade, replace, pause, or promote.
5. Record important decisions with `python3 -m brain_core memory add`.

## Mirroring

Preview commands:

```bash
python3 -m brain_core github mirror-plan --status integrate
python3 -m brain_core github mirror-plan --status mirror
```

Execute only after reviewing network and disk impact:

```bash
python3 -m brain_core github mirror-execute --status integrate --yes
```

## Promotion Criteria

Promote a project from `mirror` to `integrate` only if:

- license is acceptable;
- install path is reproducible;
- local-only mode is possible or sensitive data is scoped;
- wrapper boundary is clear;
- failure modes are understood;
- rollback is easy.

