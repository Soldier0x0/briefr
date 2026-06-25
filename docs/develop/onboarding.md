# Developer onboarding

**Full guide:** [`ONBOARDING.md`](../ONBOARDING.md) (reading order, local dev, tests, module map).

## Quick path

1. [Quickstart](../deploy/quickstart.md) — run locally
2. [`CODEBASE_CONTEXT.md`](../../CODEBASE_CONTEXT.md) — dense architecture for AI/contributors
3. [`concepts/`](../concepts/) — subsystem behavior and decisions
4. `backend/tests/` — `pytest tests/ -q` from `backend/`

## When you change code

| Change type | Also update |
|-------------|-------------|
| User-facing behavior | `docs/use/` or `docs/concepts/` |
| Deploy / env | `docs/deploy/`, `PRODUCT_STATUS.md` |
| New diagram needed | `IMAGE_BRIEFS.md` + export to `assets/` |
| Architectural choice | New `decisions/ADR-*.md` |

## Templates

- [TEMPLATE_concept.md](../TEMPLATE_concept.md)
- [TEMPLATE_adr.md](../TEMPLATE_adr.md)

## Legacy maps

- [`FOLDER_STRUCTURE_GUIDE.md`](../../FOLDER_STRUCTURE_GUIDE.md)
- [`APPLICATION_EXECUTION_MAP.md`](../../APPLICATION_EXECUTION_MAP.md)
- [`TECHNICAL_INVENTORY.md`](../../TECHNICAL_INVENTORY.md)
