# BRIEFR Learn

Static pathway chooser (System Design / Security analyst / Security architect) that links into the audited textbook at [`../study-guide/`](../study-guide/).

## Files

| Path | Role |
|------|------|
| `pathways.json` | Editable pathway order (source of truth) |
| `index.html`, `pathways/*.html`, `assets/` | Generated — do not hand-edit |
| `../study-guide/` | Textbook chapters |

## Regenerate

```bash
python scripts/build_study_guide_book.py   # if the textbook changed
python scripts/build_learn_site.py
```

Open `index.html` in a browser, or serve the `docs/` tree so `learn/` and `study-guide/` stay siblings.
