# BRIEFR Learn — pathway overlays

Editable pathway definitions live in `pathways.json`.

Regenerate the deployable site:

```bash
python scripts/build_study_guide_book.py
python scripts/audit_study_guide.py --strict
python scripts/build_learn_site.py
```

Output: `docs/learn-site/` (self-contained; see that folder’s `DEPLOY.md`).
