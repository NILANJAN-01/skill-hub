# 01. Never hand-edit generated files

Change the sources, then run `python tools/build_catalog.py`.

Generated files:
- `catalog.json`
- `skills/README.md`
- `examples/PROMPTS.md`
- `prompts.html`
- `user-guide.html` (the master user guide; edit `tools/user_guide_template.html` for wording, everything else comes from the repository)
- `README.md`: the `<!-- agents:start/end -->` block, and the `categories`, `plugin-names` and `counts` blocks
- `GUIDE.md`: the `<!-- agents-simple:start/end -->` block
