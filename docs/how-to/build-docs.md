# Build Documentation

Install the documentation dependencies:

```bash
python3 -m pip install -r docs/requirements.txt
```

Build the site:

```bash
python3 scripts/build_docs.py
```

Serve the site locally:

```bash
PYTHONPATH=python/src python3 -m mkdocs serve
```

The build script generates API reference pages under `docs/generated/` and then
runs `mkdocs build --strict`. Generated pages and built HTML are ignored by git.

`docs/generated/` is disposable. The build script removes and recreates it on
each run, writes a small `manifest.json`, and applies the shared template in
`scripts/templates/api_page.md.tmpl`. Edit source docstrings or the template;
do not edit generated Markdown directly.
