# Deploying BRIEFR Learn

This folder (`docs/learn-site/`) is a **self-contained static site**.
No application server is required.

## Preview locally (no subdomain)

```bash
# from repo root
python scripts/build_learn_site.py
cd docs/learn-site && python3 -m http.server 8765
# open http://127.0.0.1:8765/
```

## When `docs.<your-domain>` is ready

Point the host document root (or Cloudflare Pages / Netlify / nginx `root`) at **this directory**:

- Cloudflare Pages: connect the repo, build command `python scripts/build_learn_site.py`, output `docs/learn-site`
- nginx: `root /path/to/briefr/docs/learn-site;`
- Any static bucket: upload the contents of `docs/learn-site/`

The nested `book/` tree is the audited study guide. Pathway pages only link into those chapters.

## Rebuild after textbook changes

```bash
python scripts/build_study_guide_book.py
python scripts/audit_study_guide.py --strict
python scripts/build_learn_site.py
```

## Optional later: separate learn repo

Copy `docs/learn/`, `scripts/build_learn_site.py`, and CI that pulls a truth bundle from BRIEFR. Until then, this in-repo artifact is the deploy target.
